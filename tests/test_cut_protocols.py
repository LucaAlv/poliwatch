"""A Protokoll XML that is a first edition and stops partway through the sitting
(docs/plans/cut-protocols.md, docs/source-errors.md E16): the notice, DIP's
check of it and the list of what DIP names after the cut."""

import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401
import protocol_cut as cut
import reviewed_end_times
import build_dip_pulse_site as site
import facts
import persist_dip_pulse_store as pulse_store
import validate_dip_protocol as dip

NOTICE = ('Der gesamte und damit end­gültige Stenografische Bericht der 99. Sitzung wird am '
          '13. Oktober 2026 veröffentlicht.')


def xref(rede_id, page, quadrant):
    return f'<xref ref-type="rede" rid="{rede_id}" pnr="{page}" div="{quadrant}"/>'


def redner(surname):
    return f'<redner id="1"><name><vorname>A</vorname><nachname>{surname}</nachname></name></redner>'


def protocol_root(notice=NOTICE, sitting="99", toc=None):
    """Two Reden in the Sitzungsverlauf, one in an annex printed on a later page."""
    toc = toc if toc is not None else xref("ID1", 10, "A") + xref("ID2", 12, "B") + xref("ID9", 90, "C")
    return dip.ET.fromstring(
        f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="{sitting}"><vorspann><inhaltsverzeichnis>{toc}'
        f'<p>{notice}</p></inhaltsverzeichnis></vorspann><sitzungsverlauf>'
        f'<rede id="ID1"><p>{redner("Alt")}</p></rede><rede id="ID2"><p>{redner("Berg")}</p></rede><p>{notice}</p>'
        f'</sitzungsverlauf><anlagen><rede id="ID9"/></anlagen></dbtplenarprotokoll>')


class FirstEditionNoticeTests(unittest.TestCase):
    # Value: protects=the notice is read through soft hyphens and gives its date and the last printed Rede;
    #   fails_when=a cut file is read as whole, or the cut lands on an annex Rede; why_new=new rule; seam=parser
    def test_the_notice_gives_the_announced_date_and_the_last_rede_of_the_sitzungsverlauf(self):
        self.assertEqual(cut.first_edition_notice(protocol_root()), {
            "announced": "2026-10-13",
            "last_rede": {"rede_id": "ID2", "page": 12, "quadrant": "B", "surname": "Berg"},
        })

    def test_19_55_spells_the_date_without_a_space(self):
        notice = NOTICE.replace("13. Oktober", "16.Oktober")
        self.assertEqual(cut.first_edition_notice(protocol_root(notice))["announced"], "2026-10-16")

    def test_a_file_without_the_notice_has_none(self):
        self.assertIsNone(cut.first_edition_notice(protocol_root(notice="Schluss: 01:07 Uhr")))

    # Value: protects=a notice naming another sitting is never taken for this one's;
    #   fails_when=a file with a foreign notice is marked or passed silently; why_new=new rule; seam=parser
    def test_a_notice_naming_another_sitting_refuses(self):
        with self.assertRaisesRegex(cut.ProtocolCutError, "21/98.*names the 99. Sitzung"):
            cut.first_edition_notice(protocol_root(sitting="98"))

    def test_two_dates_refuse(self):
        root = protocol_root()
        extra = dip.ET.SubElement(root.find("sitzungsverlauf"), "p")
        extra.text = NOTICE.replace("13. Oktober", "14. Oktober")
        with self.assertRaisesRegex(cut.ProtocolCutError, "two dates"):
            cut.first_edition_notice(root)

    # Value: protects=20/210's shape, an Inhaltsverzeichnis without pages: the last Rede by order, no place;
    #   fails_when=the cut falls on page 0 and every DIP Rede counts as after it; why_new=new rule; seam=parser
    def test_an_inhaltsverzeichnis_without_pages_gives_the_last_rede_without_a_place(self):
        toc = xref("ID1", "", "") + xref("ID2", "", "")
        self.assertEqual(cut.first_edition_notice(protocol_root(toc=toc))["last_rede"],
                         {"rede_id": "ID2", "page": None, "quadrant": None, "surname": "Berg"})


def activity(activity_id, kind, title, seite, person="1"):
    return {"id": activity_id, "aktivitaetsart": kind, "titel": title, "person_id": person,
            "fundstelle": {"seite": seite}}


ACTIVITIES = [
    activity("a1", "Rede", "Anna Alt, MdB, SPD", "10A", "11"),
    activity("a2", "Rede", "Bernd Berg, MdB, AfD", "12B", "12"),
    activity("a3", "Rede", "Carla Cut, MdB, SPD", "12B", "13"),
    activity("a4", "Rede", "Dora Dreher, MdB, Die Linke", "12C", "14"),
    activity("a5", "Rede", "Emil Esch, MdB, CDU/CSU", "13A", "15"),
    activity("a6", "Rede", "Petra Pau, Bundestagsvizepräs.", "13B", "16"),
    activity("a7", "Kurzintervention", "Anna Alt, MdB, SPD", "13C", "11"),
    activity("a8", "Rede (zu Protokoll gegeben)", "Emil Esch, MdB, CDU/CSU", "90C", "15"),
    activity("a9", "Rede (zu Protokoll gegeben)", "Dora Dreher, MdB, Die Linke", "91A", "14"),
]


def parsed(notice, reden=2, zu_protokoll=("Dreher",)):
    """What parse_protocol_xml gives, as far as the rule reads it."""
    speeches = [{"rede_id": f"ID{index}"} for index in range(1, reden + 1)]
    written = [{"kind": "zu_protokoll", "speaker": {"display_name": f"Dora {name}"}} for name in zu_protokoll]
    return {"first_edition": notice, "agenda_items": [{"speeches": speeches, "contributions": []}],
            "sitting_contributions": written}


NOTICE_READ = {"announced": "2026-10-13", "last_rede": {"rede_id": "ID2", "page": 12, "quadrant": "B", "surname": "Berg"}}


class ProtocolCutTests(unittest.TestCase):
    # Value: protects=the list after the cut: none in the cut's own quadrant, no chair's farewell, no Kurzintervention,
    #   and a Rede zu Protokoll only where no stored one has the name; fails_when=the 1,189 or 429 move; why_new=new rule; seam=parser
    def test_a_cut_file_lists_what_dip_names_after_its_last_rede(self):
        result = cut.protocol_cut(parsed(NOTICE_READ), ACTIVITIES)
        self.assertEqual({key: result[key] for key in ("announced", "last_rede_id", "page", "quadrant", "place_from")},
                         {"announced": "2026-10-13", "last_rede_id": "ID2", "page": 12, "quadrant": "B",
                          "place_from": "inhaltsverzeichnis"})
        self.assertEqual(result["entries"], [
            {"dip_activity_id": "a4", "kind": "rede", "dip_person_id": "14", "speaker": "Dora Dreher, MdB, Die Linke",
             "page": 12, "quadrant": "C"},
            {"dip_activity_id": "a5", "kind": "rede", "dip_person_id": "15", "speaker": "Emil Esch, MdB, CDU/CSU",
             "page": 13, "quadrant": "A"},
            {"dip_activity_id": "a8", "kind": "zu_protokoll", "dip_person_id": "15", "speaker": "Emil Esch, MdB, CDU/CSU",
             "page": 90, "quadrant": "C"},
        ])

    def test_a_file_without_the_notice_is_whole_whatever_dip_lists(self):
        # 18/3's shape: a Fragestunde after the last <rede>, no notice.
        self.assertIsNone(cut.protocol_cut(parsed(None), ACTIVITIES))

    # Value: protects=19/107, which prints the notice and is whole: DIP lists no more Reden (without the chair's) and
    #   Reden zu Protokoll than the file; fails_when=19/107 is marked, or the chair's farewells mark a whole sitting;
    #   why_new=new rule; seam=parser
    def test_a_notice_with_everything_dip_lists_is_whole(self):
        self.assertIsNone(cut.protocol_cut(parsed(NOTICE_READ, reden=5, zu_protokoll=("Dreher", "Esch")), ACTIVITIES))

    def test_one_dip_rede_more_than_the_file_marks_it(self):
        result = cut.protocol_cut(parsed(NOTICE_READ, reden=4, zu_protokoll=("Dreher", "Esch")), ACTIVITIES)
        self.assertEqual([entry["dip_activity_id"] for entry in result["entries"]], ["a4", "a5"])

    # Value: protects=a sitting DIP has not indexed yet is marked, not assumed whole; fails_when=a fresh cut Thursday
    #   counts as complete; why_new=new rule; seam=parser
    def test_no_aktivitaeten_marks_it_with_an_empty_list(self):
        result = cut.protocol_cut(parsed(NOTICE_READ, reden=40, zu_protokoll=("Dreher", "Esch")), [])
        self.assertEqual((result["last_rede_id"], result["entries"]), ("ID2", []))

    # Value: protects=20/210, whose Inhaltsverzeichnis has no pages: the place is DIP's only Rede of that speaker;
    #   fails_when=the 62 Reden of 20/210 go unlisted, or a guess places the cut; why_new=new rule; seam=parser
    def test_without_pages_the_place_is_dips_single_rede_of_the_last_speaker(self):
        notice = {**NOTICE_READ, "last_rede": {"rede_id": "ID2", "page": None, "quadrant": None, "surname": "Berg"}}
        result = cut.protocol_cut(parsed(notice), ACTIVITIES)
        self.assertEqual((result["page"], result["quadrant"], result["place_from"]), (12, "B", "dip"))
        self.assertEqual([entry["dip_activity_id"] for entry in result["entries"]], ["a4", "a5", "a8"])

    def test_without_pages_two_dip_reden_of_the_last_speaker_refuse(self):
        notice = {**NOTICE_READ, "last_rede": {"rede_id": "ID2", "page": None, "quadrant": None, "surname": "Berg"}}
        twice = [*ACTIVITIES, activity("b1", "Rede", "Bernd Berg, MdB, AfD", "14A", "12")]
        with self.assertRaisesRegex(cut.ProtocolCutError, "2 DIP Reden of Berg"):
            cut.protocol_cut(parsed(notice), twice)


FIXTURE_NOTICE = ('<p klasse="J">Der gesamte und damit endgültige Stenografische Bericht der 999. Sitzung wird am '
                  '21. Mai 2024 veröffentlicht.</p>')


def cut_fixture_xml():
    """tests/fixtures/protocol.xml (20/999, Reden R1 to R3 on 101 A to 103 B) as a first edition."""
    xml = (_support.FIXTURES / "protocol.xml").read_text(encoding="utf-8")
    return xml.replace("</sitzungsverlauf>", f"{FIXTURE_NOTICE}</sitzungsverlauf>").replace("<xref ", '<xref ref-type="rede" ')


def report_of(parsed, aktivitaeten):
    return {"protocol": {"dokumentnummer": "20/999"},
            "agenda_items": [{"index": top["index"], **dip.xml_top_fields(top), "api": dip.no_api_fields(), "votes": []}
                             for top in parsed["agenda_items"]],
            "api_records": {"aktivitaeten": aktivitaeten}, "validation_summary": {}}


class ParsedReportTests(unittest.TestCase):
    # Value: protects=both paths that read a report's XML record the cut, so an offline replay marks what an online
    #   build marks; fails_when=--offline --repersist leaves protocol_cut unset; why_new=new rule; seam=parser
    def test_a_reparsed_report_records_the_cut_and_the_rule_version(self):
        parsed = dip.parse_protocol_xml(cut_fixture_xml())
        self.assertEqual(parsed["first_edition"]["last_rede"]["rede_id"], "R3")
        printed = [activity(f"r{n}", "Rede", f"{name}, MdB", seite) for n, (name, seite) in
                   enumerate((("Ada Lovelace", "101A"), ("Bruno Beispiel", "102C"), ("Clara Kontrolle", "103B")))]
        report = report_of(parsed, [*printed, activity("x1", "Rede", "Dora Dreher, MdB, Die Linke", "104A", "14")])
        dip.reparse_report_xml(report, parsed)
        summary = report["validation_summary"]
        self.assertEqual(summary["cut_rule_version"], cut.CUT_RULE_VERSION)
        self.assertEqual((summary["protocol_cut"]["page"], summary["protocol_cut"]["quadrant"]), (103, "B"))
        self.assertEqual([e["dip_activity_id"] for e in summary["protocol_cut"]["entries"]], ["x1"])

    def test_a_whole_file_records_no_cut(self):
        parsed = dip.parse_protocol_xml((_support.FIXTURES / "protocol.xml").read_text(encoding="utf-8"))
        self.assertIsNone(parsed["first_edition"])
        report = report_of(parsed, [])
        dip.reparse_report_xml(report, parsed)
        self.assertEqual(report["validation_summary"]["protocol_cut"], None)

    # Value: protects=a report cached before the rule (or under an older one) is re-read, never taken as whole;
    #   fails_when=--offline --repersist skips the 806 reports and no sitting is marked; why_new=new rule; seam=build
    def test_a_report_without_the_rule_version_is_stale_for_the_cut(self):
        report = _support.stamp_reviewed({"protocol": {"dokumentnummer": "20/999"}, "validation_summary": {}})
        del report["validation_summary"]["cut_rule_version"]
        self.assertIn("cut", site.stale_causes(report))
        report["validation_summary"]["cut_rule_version"] = cut.CUT_RULE_VERSION
        self.assertNotIn("cut", site.stale_causes(report))


CUT = {"announced": "2026-10-13", "last_rede_id": "R3", "page": 103, "quadrant": "B", "place_from": "inhaltsverzeichnis",
       "entries": [
           {"dip_activity_id": "x1", "kind": "rede", "dip_person_id": "8173", "speaker": "Dora Dreher, MdB, Die Linke",
            "page": 104, "quadrant": "A"},
           {"dip_activity_id": "x2", "kind": "zu_protokoll", "dip_person_id": None, "speaker": "Emil Esch, MdB, CDU/CSU",
            "page": None, "quadrant": None},
       ]}


def cut_report(protocol_cut=CUT):
    report = json.loads((_support.FIXTURES / "report.json").read_text(encoding="utf-8"))
    summary = report.setdefault("validation_summary", {})
    summary.update({"protocol_cut": copy.deepcopy(protocol_cut), "cut_rule_version": cut.CUT_RULE_VERSION,
                    "speech_kinds_version": dip.speech_kinds.VERSION})
    return _support.stamp_reviewed(report)


class StoreTests(unittest.TestCase):
    def store(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = pulse_store.connect(Path(tmp.name) / "store.sqlite")
        self.addCleanup(conn.close)
        return conn

    # Value: protects=a cut sitting is marked in protocols and its DIP entries are rows of their own, never Reden;
    #   fails_when=the mark or the 1,618 rows are lost, or they land in speeches/contributions; why_new=schema 16; seam=persist
    def test_a_cut_sitting_is_marked_and_its_dip_entries_are_stored_apart(self):
        conn = self.store()
        pulse_store.persist_report(conn, cut_report(), None)
        self.assertEqual(tuple(map(tuple, conn.execute("SELECT xml_cut, xml_final_announced, xml_last_rede_id FROM protocols"))),
                         ((1, "2026-10-13", "R3"),))
        rows = [tuple(r) for r in conn.execute(
            "SELECT protocol_id, dip_activity_id, kind, mp_id, dip_person_id, speaker, page, page_quadrant "
            "FROM unprinted_contributions ORDER BY dip_activity_id")]
        self.assertEqual(rows, [
            ("pp-test-1", "x1", "rede", None, "8173", "Dora Dreher, MdB, Die Linke", 104, "A"),
            ("pp-test-1", "x2", "zu_protokoll", None, None, "Emil Esch, MdB, CDU/CSU", None, None),
        ])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM speeches WHERE text LIKE '%Dreher%'").fetchone()[0], 0)

    def test_a_whole_sitting_has_no_mark_and_a_repersist_drops_old_rows(self):
        conn = self.store()
        pulse_store.persist_report(conn, cut_report(), None)
        pulse_store.persist_report(conn, cut_report(None), None)
        self.assertEqual(tuple(map(tuple, conn.execute("SELECT xml_cut, xml_final_announced, xml_last_rede_id FROM protocols"))),
                         ((0, None, None),))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM unprinted_contributions").fetchone()[0], 0)

    # Value: protects=the person of an entry resolves by DIP person id after every report and the roster are in,
    #   so the order of sittings never decides it; fails_when=an entry persisted before its person's mps row stays
    #   unbound, or a fresh and an incremental build differ; why_new=new table; seam=persist
    def test_entries_bind_to_the_mps_row_of_their_dip_person_once_all_are_in(self):
        conn = self.store()
        pulse_store.persist_report(conn, cut_report(), None)
        mp_id = conn.execute("SELECT id FROM mps ORDER BY id LIMIT 1").fetchone()[0]
        conn.execute("UPDATE mps SET dip_person_id = '8173' WHERE id = ?", (mp_id,))
        pulse_store.resolve_unprinted_people(conn)
        self.assertEqual([tuple(r) for r in conn.execute(
            "SELECT dip_activity_id, mp_id FROM unprinted_contributions ORDER BY 1")], [("x1", mp_id), ("x2", None)])

    # Value: protects=a store persisted under another cut rule is stale, as one under another speech rule is;
    #   fails_when=a store from an older rule reads as current and its marks are wrong; why_new=new rule; seam=persist
    def test_a_store_under_another_cut_rule_is_stale(self):
        conn = self.store()
        pulse_store.persist_report(conn, cut_report(), None)
        pulse_store.require_current_speech_rules(conn)
        conn.execute("UPDATE speech_rule_inputs SET cut_rule_version = ?", (cut.CUT_RULE_VERSION - 1,))
        with self.assertRaisesRegex(RuntimeError, "cut Protokoll files"):
            pulse_store.require_current_speech_rules(conn)

    def test_a_schema_15_store_is_refused(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE protocols (id TEXT PRIMARY KEY, document_number TEXT, xml_header_json TEXT)")
        with self.assertRaisesRegex(RuntimeError, "Old build-store schema"):
            pulse_store.initialize(conn)
        conn.close()


def judged(number="21/99", protocol_cut=None, header=None, **summary):
    """A cached report as completeness_from_reports reads it: parsed, no withheld
    Rede, votes acquired."""
    report = {
        "protocol": {"dokumentnummer": number,
                     "xml_header": {"sitzung_start": "09:00", "sitzung_end": "01:07"} if header is None else header},
        "validation_summary": {"xml_speech_count": 3, "withheld_rede_count": 0, "protocol_cut": protocol_cut,
                               "cut_rule_version": cut.CUT_RULE_VERSION, "roll_call_scan_end": "list_end", **summary},
        "acquisition": {"votes": {"acquisition_state": "complete", "acquired_at": "2026-10-09T10:00:00Z"}},
    }
    return report


class CompletenessTests(unittest.TestCase):
    # Value: protects=a cut sitting is incomplete for speeches with its own reason, and its votes are not touched;
    #   fails_when=the 31 weeks and 20 months of the plan stay complete; why_new=new rule; seam=facts
    def test_a_cut_sitting_is_incomplete_for_speeches_only(self):
        state = facts.completeness_from_reports([judged(protocol_cut=CUT)])["21/99"]
        self.assertEqual((state["speeches"], state["reasons"]["speeches"]), (False, facts.CUT_PROTOCOL))
        self.assertTrue(state["votes"])
        self.assertTrue(state["times"])

    def test_a_cut_outranks_withheld_reden(self):
        state = facts.completeness_from_reports([judged(protocol_cut=CUT, withheld_rede_count=2)])["21/99"]
        self.assertEqual(state["reasons"]["speeches"], facts.CUT_PROTOCOL)

    # Value: protects=a report cached before the rule never reads as whole; fails_when=an old report with no
    #   protocol_cut key counts its week complete; why_new=new rule; seam=facts
    def test_a_report_without_the_cut_check_is_unknown_and_incomplete(self):
        report = judged()
        del report["validation_summary"]["protocol_cut"]
        state = facts.completeness_from_reports([report])["21/99"]
        self.assertEqual((state["speeches"], state["reasons"]["speeches"]), (False, "no cut check (report predates it)"))

    def test_a_whole_sitting_is_complete(self):
        state = facts.completeness_from_reports([judged()])["21/99"]
        self.assertEqual((state["speeches"], state["votes"], state["times"]), (True, True, True))

    # Value: protects=basis times: a cut file still prints both times, and 18/23, which prints no end, is incomplete
    #   for laengste-sitzung whatever its Reden; fails_when=laengste-sitzung loses the cut weeks or keeps 18/23;
    #   why_new=D2; seam=facts
    def test_times_need_both_times_of_a_parsed_xml(self):
        no_end = facts.completeness_from_reports([judged("18/23", header={"sitzung_start": "09:00", "sitzung_end": ""})])
        self.assertEqual((no_end["18/23"]["times"], no_end["18/23"]["reasons"]["times"]), (False, facts.NO_SITTING_TIMES))
        self.assertTrue(no_end["18/23"]["speeches"])
        unparsed = judged("18/24")
        del unparsed["validation_summary"]["xml_speech_count"]
        state = facts.completeness_from_reports([unparsed])["18/24"]
        self.assertEqual((state["times"], state["reasons"]["times"]), (False, "XML not parsed"))

    def test_laengste_sitzung_is_judged_by_times(self):
        metric = facts.REGISTRY_BY_ID["laengste-sitzung"]
        self.assertEqual((metric["coverage"], metric["version"]), ("times", 2))
        facts.validate_registry(facts.ALL_REGISTRY)

    # Value: protects=the note a withheld Fakt shows names the cut file, and the times domain has words;
    #   fails_when=gap_note raises a KeyError on times or words a cut as "Reden nicht erfasst"; why_new=new reason; seam=facts
    def test_the_gap_notes_name_the_cut_file_and_missing_times(self):
        self.assertEqual(facts.gap_note([{"document_number": "21/99", "date": "2026-10-08", "reason": facts.CUT_PROTOCOL}],
                                        "speeches"), "Sitzung 21/99: Protokolldatei abgebrochen")
        self.assertEqual(facts.gap_note([{"document_number": "18/23", "date": "2014-03-20",
                                          "reason": facts.NO_SITTING_TIMES}], "times"),
                         "Sitzung 18/23: Beginn oder Ende nicht im Protokoll")


def end_entry(**overrides):
    entry = {"sitting": "20/999", "xml_end": "12:00", "end": "11:58",
             "pdf_url": "https://dserver.bundestag.de/btp/20/20999.pdf", "pdf_md5": "8eea57bbf4299710b4dabd82d557abfb",
             "pdf_page": 214, "reason": "the PDF prints (Schluss: 11.58 Uhr)"}
    entry.update(overrides)
    return entry


class ReviewedEndTimesListTests(unittest.TestCase):
    # Value: protects=the list is read whole and refuses anything it cannot apply; fails_when=a typo moves a
    #   published duration, or a refusal is a ValueError a caller swallows; why_new=D2 list; seam=list
    def test_the_shipped_list_holds_the_four_corrections(self):
        entries = reviewed_end_times.load()
        self.assertEqual([(e.sitting, e.xml_end, e.end, e.pdf_page) for e in entries], [
            ("19/55", "01:30", "01:28", 214), ("20/178", "23:11", "23:12", 203),
            ("21/89", "23:36", "23:37", 206), ("21/96", "00:16", "00:15", 214)])

    def test_malformed_entries_refuse(self):
        for broken in ({"entries": [end_entry(end="1.28")]}, {"entries": [end_entry(pdf_md5="xyz")]},
                       {"entries": [end_entry(pdf_page=0)]}, {"entries": [end_entry(pdf_url="http://evil.test/a.pdf")]},
                       {"entries": [{**end_entry(), "extra": 1}]}, {"entries": [end_entry(reason="")]},
                       {"entries": [end_entry(sitting="20/999/1")]}, [], {"entries": None}):
            with self.subTest(broken=broken), self.assertRaises(reviewed_end_times.ReviewedEndTimesError):
                reviewed_end_times.check(broken)
        self.assertFalse(issubclass(reviewed_end_times.ReviewedEndTimesError, ValueError))

    def test_a_repeated_sitting_and_an_end_equal_to_the_xml_refuse(self):
        with self.assertRaisesRegex(reviewed_end_times.ReviewedEndTimesError, "twice"):
            reviewed_end_times.check({"entries": [end_entry(), end_entry(end="11:57")]})
        with self.assertRaisesRegex(reviewed_end_times.ReviewedEndTimesError, "equals xml_end"):
            reviewed_end_times.check({"entries": [end_entry(end="12:00")]})


def timed_report(end="12:00"):
    report = cut_report(None)
    report["protocol"]["xml_header"].update({"sitzung_start": "09:00", "sitzung_end": end})
    return report


class CorrectedEndTimeStoreTests(unittest.TestCase):
    def store(self):
        return StoreTests.store(self)

    # Value: protects=the corrected end lands beside the XML head, which stays as printed; fails_when=the head is
    #   overwritten (a reader comparing with the XML finds another time) or the entry is not applied; why_new=D2; seam=persist
    def test_persist_applies_an_entry_and_leaves_the_xml_head_alone(self):
        conn = self.store()
        with reviewed_end_times.using(reviewed_end_times.check({"entries": [end_entry()]})):
            pulse_store.persist_report(conn, timed_report(), None)
        row = conn.execute("SELECT sitting_end_corrected, json_extract(xml_header_json, '$.sitzung_end') FROM protocols").fetchone()
        self.assertEqual(tuple(row), ("11:58", "12:00"))

    def test_a_sitting_without_an_entry_keeps_no_correction(self):
        conn = self.store()
        with reviewed_end_times.using(reviewed_end_times.check({"entries": [end_entry(sitting="21/1")]})):
            pulse_store.persist_report(conn, timed_report(), None)
        self.assertIsNone(conn.execute("SELECT sitting_end_corrected FROM protocols").fetchone()[0])

    # Value: protects=an entry whose XML end no longer matches stops the run, so a replaced file is noticed and the
    #   entry deleted; fails_when=a correction is applied to a file it was not read against; why_new=D2; seam=persist
    def test_persist_refuses_an_entry_whose_xml_end_changed(self):
        conn = self.store()
        with reviewed_end_times.using(reviewed_end_times.check({"entries": [end_entry()]})):
            with self.assertRaisesRegex(reviewed_end_times.ReviewedEndTimesError, "20/999 corrects the end 12:00.*prints '12:01'"):
                pulse_store.persist_report(conn, timed_report("12:01"), None)

    # Value: protects=a store persisted under other entries is stale and asks for a replay; fails_when=an edit of
    #   the list leaves an old duration in the store; why_new=D2; seam=persist
    def test_a_store_under_other_entries_is_stale(self):
        conn = self.store()
        with reviewed_end_times.using(reviewed_end_times.check({"entries": [end_entry()]})):
            pulse_store.persist_report(conn, timed_report(), None)
            pulse_store.require_current_speech_rules(conn)
        with reviewed_end_times.using([]):
            with self.assertRaisesRegex(RuntimeError, "20/999.*reviewed_end_times.json"):
                pulse_store.require_current_speech_rules(conn)

    # Value: protects=laengste-sitzung reads the corrected end: 19/55's shape, 09:00 to 01:28 past midnight, is 988
    #   minutes, and a sitting without an entry keeps the XML's value; fails_when=the SQL reads the head alone;
    #   why_new=D2; seam=facts SQL
    def test_laengste_sitzung_reads_the_corrected_end(self):
        conn = self.store()
        entries = reviewed_end_times.check({"entries": [end_entry(xml_end="01:30", end="01:28")]})
        with reviewed_end_times.using(entries):
            pulse_store.persist_report(conn, timed_report("01:30"), None)
        sql = facts.REGISTRY_BY_ID["laengste-sitzung"]["sql"]
        row = conn.execute(f"SELECT sitzung_end, value FROM ({sql})").fetchone()
        self.assertEqual(tuple(row), ("01:28", 988))
        conn.execute("UPDATE protocols SET sitting_end_corrected = NULL")
        self.assertEqual(tuple(conn.execute(f"SELECT sitzung_end, value FROM ({sql})").fetchone()), ("01:30", 990))


if __name__ == "__main__":
    unittest.main()
