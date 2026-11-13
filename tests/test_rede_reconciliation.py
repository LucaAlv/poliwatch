"""Every <rede> of the source XML ends with exactly one status, or the sitting is
refused (coverage gate, W2: docs/plans/coverage-gate-w1-w2.md)."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import _support  # noqa: F401
from _support import FIXTURES
import build_dip_pulse_site as build
import speech_kinds as sk
import validate_dip_protocol as dip


def rede(rid, last="Haupt", words="Rede."):
    return (f'<rede id="{rid}"><p klasse="redner"><redner id="{rid}-r"><name><nachname>{last}</nachname>'
            f'<fraktion>SPD</fraktion></name></redner></p><p klasse="J">{words}</p></rede>')


def sitting(verlauf="", anlagen="", beginn=""):
    top = f'<tagesordnungspunkt top-id="T1"><p klasse="T_NaS">Beratung</p>{rede("R1")}</tagesordnungspunkt>'
    return (f'<dbtplenarprotokoll wahlperiode="18" sitzung-nr="7">'
            f'<sitzungsverlauf>{beginn}{top}{verlauf}</sitzungsverlauf>'
            f'<anlagen>{anlagen}</anlagen></dbtplenarprotokoll>')


def annex(title, body):
    return f'<anlage><anlagen-text anlagen-typ="{title}">{body}</anlagen-text></anlage>'


def protocol_fixtures():
    for path in sorted(FIXTURES.rglob("*.xml")):
        text = path.read_text(encoding="utf-8")
        try:
            if dip.ET.fromstring(text).tag == "dbtplenarprotokoll":
                yield path, text
        except dip.ET.ParseError:
            continue


class SourceShapeTests(unittest.TestCase):
    # Value: protects=a sitting whose every <rede> has a status parses, including annex Reden read or excluded by a named rule;
    #   fails_when=a status is not recorded for a read Rede, or a named annex rule stops matching; why_new=no test reconciled units before; seam=none
    def test_a_sitting_whose_reden_all_have_a_status_parses(self):
        for title in ["Zu Protokoll gegebene Reden", "Erklärungen nach § 31 GO",
                      "Erklärung nach § 31 GO zur namentlichen Abstimmung",
                      "zu der Abstimmung über den Entwurf eines Gesetzes",
                      "Neudruck eines Redebeitrages  (34. Sitzung, Seite 3222 C f.)"]:
            with self.subTest(title=title):
                parsed = dip.parse_protocol_xml(sitting(anlagen=annex(title, rede("A1") + rede("", "Ohne"))))
                self.assertEqual([s["rede_id"] for s in parsed["agenda_items"][0]["speeches"]], ["R1"])

    # Value: protects=a <rede> outside every place the parser reads refuses, naming id and place;
    #   fails_when=the inventory is narrowed to sitzungsverlauf and anlagen; why_new=such a Rede was dropped silently; seam=none
    def test_a_rede_where_the_parser_does_not_read_refuses(self):
        for xml, where in [(sitting(beginn=f"<sitzungsbeginn>{rede('B1')}</sitzungsbeginn>"), "sitzungsverlauf/sitzungsbeginn"),
                           (sitting(verlauf=f"<sitzungsende>{rede('B1')}</sitzungsende>"), "sitzungsverlauf/sitzungsende"),
                           (sitting().replace(rede("R1"), rede("R1")[:-7] + rede("B1") + "</rede>"), "tagesordnungspunkt/rede")]:
            with self.subTest(where=where), self.assertRaises(dip.ReconciliationError) as raised:
                dip.parse_protocol_xml(xml)
            self.assertIn("18/7", str(raised.exception))
            self.assertIn("B1", str(raised.exception))
            self.assertIn(where, str(raised.exception))

    # Value: protects=an annex Rede under a title no rule names refuses, while the written-submission reader still skips it;
    #   fails_when=the bare continue returns or the exclusion table gains a catch-all; why_new=an unknown title vanished silently; seam=none
    def test_an_annex_rede_under_an_unnamed_title_refuses(self):
        for title in ["Zu Protokoll gegebene Ergänzung", "Technisch bedingter Neudruck der zu Protokoll gegebenen Rede", "Anlage ohne Regel"]:
            with self.subTest(title=title), self.assertRaises(dip.ReconciliationError) as raised:
                dip.parse_protocol_xml(sitting(anlagen=annex(title, rede("A1"))))
            self.assertIn("A1", str(raised.exception))
            self.assertIn(title, str(raised.exception))
        # A block with no <rede> is no matter for the reconciliation.
        dip.parse_protocol_xml(sitting(anlagen=annex("Anlage ohne Regel", '<p klasse="J">Liste</p>')))

    # Value: protects=19/36's Anlage 2, a Zu-Protokoll continuation under Anlage 1's title "Liste der entschuldigten
    #   Abgeordneten", is read by its own heading and joins TOP 5, while that title without the heading, or the heading
    #   under another unnamed title, still refuses; fails_when=MISTITLED_ZU_PROTOKOLL is dropped, widened to any title or
    #   heading, or the page in "(Tagesordnungspunkt 5, Seite 3370 C)" breaks the TOP match; why_new=19/36 refused; seam=none
    def test_a_zu_protokoll_block_under_the_absentee_list_title_is_read_by_its_heading(self):
        title = "Liste der entschuldigten Abgeordneten"
        heading = ('<p klasse="Anlage_2">Anlage 2</p><p klasse="Anlage_3">Zu Protokoll gegebene Fortsetzung des abgebrochenen '
                   'Redebeitrages der Abgeordneten Martina Stamm-Fibich (SPD)</p>')
        top_ref = '<p klasse="Anlage_3">(Tagesordnungspunkt 5, Seite 3370 C)</p>'
        top5 = f'<tagesordnungspunkt top-id="Tagesordnungspunkt 5">{rede("R5")}</tagesordnungspunkt>'
        listing = annex(title, f'<p klasse="Anlage_2">{title}</p><p klasse="J">Albani, Stephan</p>')
        parsed = dip.parse_protocol_xml(sitting(verlauf=top5, anlagen=listing + annex(title, heading + top_ref + rede("A1", "Stamm-Fibich"))))
        top = next(t for t in parsed["agenda_items"] if t["top_id"] == "Tagesordnungspunkt 5")
        [unit] = [c for c in top["contributions"] if c["rede_id"] == "A1"]
        self.assertEqual(unit["kind"], sk.ZU_PROTOKOLL)
        self.assertTrue(unit["annex_type"].startswith("Zu Protokoll gegebene Fortsetzung"))
        self.assertEqual(parsed["sitting_contributions"], [])
        for other_title, body in [(title, top_ref + rede("A1")),  # the list title alone reads nothing
                                  (title, '<p klasse="Anlage_3">Abgeordnete im Mutterschutz</p>' + rede("A1")),
                                  ("Anlage ohne Regel", heading + rede("A1"))]:  # the heading alone reads nothing
            with self.subTest(title=other_title, body=body[:40]), self.assertRaises(dip.ReconciliationError) as raised:
                dip.parse_protocol_xml(sitting(verlauf=top5, anlagen=annex(other_title, body)))
            self.assertIn("A1", str(raised.exception))

    # Value: protects=one id is one <rede>, and a <rede> outside an annex has an id;
    #   fails_when=the by_id dict silently keeps the last of two Reden again (validate_dip_protocol parse loop); why_new=nothing checked uniqueness; seam=none
    def test_a_repeated_or_missing_rede_id_refuses(self):
        cases = {
            "occurs twice": sitting(verlauf=f'<tagesordnungspunkt top-id="T2">{rede("R1", "Zweit")}</tagesordnungspunkt>'),
            "occurs twice ": sitting(anlagen=annex("Zu Protokoll gegebene Reden", rede("R1"))),
            "without id": sitting(verlauf=f'<tagesordnungspunkt top-id="T2">{rede("")}</tagesordnungspunkt>'),
        }
        for message, xml in cases.items():
            with self.subTest(message=message), self.assertRaisesRegex(dip.ReconciliationError, message.strip()):
                dip.parse_protocol_xml(xml)

    # Value: protects=annex Reden without id are keyed one way by the reader and the inventory;
    #   fails_when=written_contributions and raw_rede_inventory count blocks or Reden differently; why_new=two keys built in two places; seam=none
    def test_annex_reden_without_id_are_keyed_alike_by_reader_and_inventory(self):
        xml = sitting(anlagen=annex("Anlage ohne Regel", '<p klasse="J">Liste</p>')
                      + annex("Zu Protokoll gegebene Reden", rede("", "Erst") + rede("", "Zweit")))
        root = dip.ET.fromstring(xml)
        self.assertEqual(sorted(k for k in dip.raw_rede_inventory(root) if k.startswith("annex:")), ["annex:2:1", "annex:2:2"])
        parsed = dip.parse_protocol_xml(xml)
        self.assertEqual([c["rede_id"] for c in parsed["sitting_contributions"]], ["annex:2:1", "annex:2:2"])


class ReconcileTests(unittest.TestCase):
    # Value: protects=a part split_nested_reden made needs its own status, and no unit gets a status the source lacks;
    #   fails_when=PR 2's withholding or a new kind forgets to record a part, or ids are mangled; why_new=no XML shape triggers it today; seam=reconcile_reden called directly
    def test_every_split_part_needs_a_status_and_nothing_else_has_one(self):
        inventory = {"R1": "TOP T1"}
        dip.reconcile_reden("18/7", inventory, {"R1": "speech", "R1:2": "beitrag"}, {"R1:2"})
        with self.assertRaisesRegex(dip.ReconciliationError, "part R1:2 of R1 has no status"):
            dip.reconcile_reden("18/7", inventory, {"R1": "speech"}, {"R1:2"})
        with self.assertRaisesRegex(dip.ReconciliationError, r"R1 \(TOP T1\) has no status"):
            dip.reconcile_reden("18/7", inventory, {"R1:2": "beitrag"}, {"R1:2"})
        with self.assertRaisesRegex(dip.ReconciliationError, "does not hold: X9"):
            dip.reconcile_reden("18/7", inventory, {"R1": "speech", "X9": "speech"}, set())
        with self.assertRaisesRegex(dip.ReconciliationError, "two statuses"):
            dip.record_status({"R1": "speech"}, "R1", "procedural")

    # Value: protects=every Fragestunde marker opens a turn; fails_when=a later change drops a marker's turn beyond the empty ones;
    #   why_new=the empty drop was silent; seam=fragestunde_turns patched to report fewer turns
    def test_a_fragestunde_marker_without_its_turn_refuses(self):
        xml = (FIXTURES / "speech-kinds-befragung-fragestunde.xml").read_text(encoding="utf-8")
        dip.parse_protocol_xml(xml)
        real = sk.fragestunde_turns

        def short(top, candidates=None, counts=None):
            result = real(top, candidates, counts)
            counts["markers"] -= 1
            return result

        with patch.object(sk, "fragestunde_turns", short), \
                self.assertRaisesRegex(dip.ReconciliationError, "Fragestunde markers"):
            dip.parse_protocol_xml(xml)

    # Value: protects=every Kind the parser can make of a whole <rede> has a status row, so a new Kind (ADR 0004) adds one;
    #   fails_when=a Kind is added to CONTRIBUTION_KINDS without a REDE_STATUS row or a NOT_REDE_KINDS entry; why_new=no registry existed; seam=none
    def test_every_kind_has_a_status_or_is_never_a_whole_rede(self):
        rede_kinds = set(sk.REDE_STATUS) - {None}
        self.assertEqual(rede_kinds & sk.NOT_REDE_KINDS, set())
        self.assertEqual(rede_kinds | sk.NOT_REDE_KINDS, set(sk.CONTRIBUTION_KINDS))


class RealSittingTests(unittest.TestCase):
    # Value: protects=every protocol fixture reconciles; fails_when=a rule refuses a known-good sitting shape;
    #   why_new=test_reden_outside_tops covers two sittings; seam=none; no_claim=the 716 held sittings (most fixtures are excerpts; corpus run)
    def test_every_protocol_fixture_reconciles(self):
        count = 0
        for path, text in protocol_fixtures():
            with self.subTest(fixture=str(path.relative_to(FIXTURES))):
                dip.parse_protocol_xml(text)
                count += 1
        self.assertGreaterEqual(count, 75)


class RefusalPathTests(unittest.TestCase):
    BAD = sitting(beginn=f"<sitzungsbeginn>{rede('B1')}</sitzungsbeginn>")

    # Value: protects=a reconciliation failure is a source refusal online; fails_when=ReconciliationError stops being a ValueError;
    #   why_new=no reconciliation error existed; seam=none
    def test_online_build_refuses_the_source(self):
        protocol = {"id": "p1", "dokumentnummer": "18/7", "fundstelle": {"xml_url": "https://dserver.bundestag.de/btp/18/18007.xml"}}
        with patch.object(dip, "fetch_text", return_value=self.BAD), self.assertRaises(dip.DipError) as raised:
            dip.build_report(SimpleNamespace(api_key="test", sleep=0), protocol)
        self.assertTrue(raised.exception.source_rejected)
        self.assertIn("rede reconciliation", str(raised.exception))

    # Value: protects=offline, a reconciliation failure names itself, not a corrupt file; fails_when=the generic "is not the Plenarprotokoll XML" message returns;
    #   why_new=the offline message would send the operator to refetch good XML; seam=none
    def test_offline_reparse_says_reconciliation_not_corrupt_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "data" / "xml").mkdir(parents=True)
            (output_dir / "data" / "xml" / "plenarprotokoll-18-7.xml").write_text(self.BAD, encoding="utf-8")
            report = {"protocol": {"id": "p1", "dokumentnummer": "18/7"}, "agenda_items": []}
            (output_dir / "data" / "plenarprotokoll-18-7.json").write_text(json.dumps(report), encoding="utf-8")
            entries = build.load_existing_detail_entries(output_dir, [{"dokumentnummer": "18/7"}])
            with self.assertRaises(build.CachedReportError) as raised:
                build.reparse_cached_xml(output_dir, entries)
        self.assertIn("rede reconciliation failed for 18/7", str(raised.exception))
        self.assertNotIn("--fetch-xml", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
