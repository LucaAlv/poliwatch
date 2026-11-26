"""A Protokoll XML that is a first edition and stops partway through the sitting
(docs/plans/cut-protocols.md, docs/source-errors.md E16): the notice, DIP's
check of it and the list of what DIP names after the cut."""

import unittest

import _support  # noqa: F401
import protocol_cut as cut
import build_dip_pulse_site as site
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


if __name__ == "__main__":
    unittest.main()
