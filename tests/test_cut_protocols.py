"""A Protokoll XML that is a first edition and stops partway through the sitting
(docs/plans/cut-protocols.md, docs/source-errors.md E16): the notice, DIP's
check of it and the list of what DIP names after the cut."""

import copy
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import _support  # noqa: F401
import protocol_cut as cut
import reviewed_end_times
import build_dip_pulse_site as site
import facts
import validate_store_gate as gate
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
        # pregate-literal: VERSION=16 a date, not the speech rule
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

    # Value: protects=two Reden on one page and quadrant: the last printed is the later one in the Sitzungsverlauf,
    #   not the larger id as text ("ID9" > "ID10") nor the later Inhaltsverzeichnis line; fails_when=the cut's last
    #   Rede and its surname (which unplaced_reden discounts) name the wrong Rede; why_new=TODOS cut-protocols item 6;
    #   seam=parser
    def test_a_tie_on_one_page_and_quadrant_goes_to_the_later_rede_of_the_sitzungsverlauf(self):
        def tied(notice):
            return dip.ET.fromstring(
                f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="99"><vorspann><inhaltsverzeichnis>'
                f'{xref("ID1", 10, "A")}{xref("ID10", 12, "B")}{xref("ID9", 12, "B")}<p>{notice}</p></inhaltsverzeichnis>'
                f'</vorspann><sitzungsverlauf><rede id="ID1"><p>{redner("Alt")}</p></rede>'
                f'<rede id="ID9"><p>{redner("Neun")}</p></rede><rede id="ID10"><p>{redner("Zehn")}</p></rede>'
                f'</sitzungsverlauf></dbtplenarprotokoll>')
        self.assertEqual(cut.first_edition_notice(tied(NOTICE))["last_rede"],
                         {"rede_id": "ID10", "page": 12, "quadrant": "B", "surname": "Zehn"})
        later = [activity(f"l{n}", "Rede", f"Later Page{n}, MdB", "13A") for n in range(6)]
        self.assertEqual(cut.unmarked_cut_evidence(tied(""), later, 0)["last_rede_id"], "ID10")

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

    # Value: protects=a DIP Aktivität repeated across cursor pages counts once, and one without an id is refused;
    #   fails_when=persist stops on UNIQUE(protocol_id, dip_activity_id), or a repeat marks a whole sitting cut;
    #   why_new=ship review of steps 1-6 (Codex); seam=none
    def test_a_repeated_dip_aktivitaet_counts_once(self):
        repeated = [*ACTIVITIES, *copy.deepcopy(ACTIVITIES[3:5])]
        self.assertEqual(cut.protocol_cut(parsed(NOTICE_READ), repeated), cut.protocol_cut(parsed(NOTICE_READ), ACTIVITIES))
        self.assertIsNone(cut.protocol_cut(parsed(NOTICE_READ, reden=5, zu_protokoll=("Dreher", "Esch")), repeated))
        root = protocol_root(notice="")
        late = [activity(f"x{n}", "Rede", f"Late Speaker{n}, MdB", f"{20 + n}A") for n in range(4)]
        self.assertIsNone(cut.unmarked_cut_evidence(root, [*late, *copy.deepcopy(late)], 0))

    def test_a_dip_aktivitaet_without_an_id_is_refused(self):
        blank = [*ACTIVITIES, {**activity("", "Rede", "Fritz Fink, MdB, SPD", "13B", "16")}]
        with self.assertRaisesRegex(cut.ProtocolCutError, "without an id"):
            cut.protocol_cut(parsed(NOTICE_READ), blank)
        written = [*ACTIVITIES, activity("", "Rede (zu Protokoll gegeben)", "Fritz Fink, MdB, SPD", "92A", "16")]
        with self.assertRaisesRegex(cut.ProtocolCutError, "without an id"):
            cut.protocol_cut(parsed(NOTICE_READ), written)

    # Value: protects=only an id-less Aktivität that can become an entry (stored under its DIP id) stops the sitting: a
    #   Kurzintervention or a chair's farewell typed "Rede" never becomes one, so it is kept as it is; fails_when=an
    #   id-less Kurzintervention or chair farewell stops a sitting the rule would have read; why_new=TODOS
    #   cut-protocols item 10 (first half), eng review R5; seam=parser
    def test_an_id_less_dip_aktivitaet_that_can_become_no_entry_is_kept(self):
        expected = cut.protocol_cut(parsed(NOTICE_READ), ACTIVITIES)
        for kind, title in (("Kurzintervention", "Fritz Fink, MdB, SPD"), ("Rede", "Petra Pau, Bundestagsvizepräs.")):
            with self.subTest(kind=kind, title=title):
                extra = [*ACTIVITIES, activity("", kind, title, "13D", "16")]
                self.assertEqual(cut.protocol_cut(parsed(NOTICE_READ), extra), expected)

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

    # Value: protects=a whole first edition holding a withheld Rede is not marked cut: DIP lists the withheld Rede,
    #   the file prints it; fails_when=such a sitting is marked and CUT_PROTOCOL hides WITHHELD_REDEN;
    #   why_new=TODOS cut-protocols item 2; seam=parser
    def test_withheld_reden_count_as_printed_in_the_whole_test(self):
        whole = parsed(NOTICE_READ, reden=3, zu_protokoll=("Dreher", "Esch"))
        whole["agenda_items"][0]["withheld"] = [{"rede_id": "ID4", "would_be": "speech"}, {"rede_id": "ID5", "would_be": "speech"}]
        self.assertIsNone(cut.protocol_cut(whole, ACTIVITIES))
        whole["agenda_items"][0]["withheld"] = [{"rede_id": "ID4", "would_be": "speech"}]
        self.assertEqual([e["dip_activity_id"] for e in cut.protocol_cut(whole, ACTIVITIES)["entries"]], ["a4", "a5"])

    # Value: protects=only a withheld unit that would be a Rede is printed as one: a would-be Beitrag (a Befragung
    #   question) or a unit nobody has reviewed yet is not, so it cannot make a cut file look whole and drop the Reden
    #   DIP lists after the cut; fails_when=a withheld Beitrag fills the count and the sitting is left unmarked;
    #   why_new=TODOS cut-protocols item 15 (Codex, blocking); seam=parser
    def test_only_a_withheld_unit_that_would_be_a_rede_counts_as_printed(self):
        cut_file = parsed(NOTICE_READ, reden=3, zu_protokoll=("Dreher", "Esch"))
        for would_be in ("beitrag", "procedural", "unreviewed", "zu_protokoll"):
            with self.subTest(would_be=would_be):
                cut_file["agenda_items"][0]["withheld"] = [{"rede_id": "ID4", "would_be": "speech"},
                                                           {"rede_id": "ID5", "would_be": would_be}]
                self.assertEqual(cut.printed_reden(cut_file), 4)
                self.assertEqual([e["dip_activity_id"] for e in cut.protocol_cut(cut_file, ACTIVITIES)["entries"]],
                                 ["a4", "a5"])

    # Value: protects=a withheld unit that would be a Rede zu Protokoll is printed, so DIP's entry for it matches it by
    #   surname and is not listed as unprinted; fails_when=a withheld Rede zu Protokoll is counted nowhere and its DIP
    #   entry lands in unprinted_contributions; why_new=TODOS cut-protocols item 15; seam=parser
    def test_a_withheld_rede_zu_protokoll_matches_dips_entry(self):
        cut_file = parsed(NOTICE_READ)
        self.assertIn("a8", [e["dip_activity_id"] for e in cut.protocol_cut(cut_file, ACTIVITIES)["entries"]])
        cut_file["agenda_items"][0]["withheld"] = [
            {"rede_id": "A1", "would_be": "zu_protokoll", "speaker": {"display_name": "Emil Esch"}}]
        self.assertEqual([e["dip_activity_id"] for e in cut.protocol_cut(cut_file, ACTIVITIES)["entries"]], ["a4", "a5"])
        # With every DIP Rede printed, the withheld one makes the file whole.
        cut_file["agenda_items"][0]["speeches"] = [{"rede_id": f"ID{n}"} for n in range(1, 6)]
        self.assertIsNone(cut.protocol_cut(cut_file, ACTIVITIES))
        # It counts as no Rede.
        self.assertEqual(cut.printed_reden(cut_file), 5)

    # Value: protects=the rule writes its own count of printed Reden into the report, so gate rule 3 judges an unmarked
    #   file by the number the rule uses (one definition); fails_when=the gate sums the counts on its own again and
    #   drifts from the rule; why_new=TODOS cut-protocols item 15, eng review R1; seam=parser
    def test_the_cut_summary_carries_the_count_of_printed_reden(self):
        cut_file = parsed(NOTICE_READ, reden=3)
        cut_file["agenda_items"][0]["withheld"] = [{"rede_id": "ID4", "would_be": "speech"},
                                                   {"rede_id": "ID5", "would_be": "beitrag"}]
        summary = cut.cut_summary(cut_file, ACTIVITIES)
        self.assertEqual((summary["printed_reden"], summary["cut_rule_version"]), (4, cut.CUT_RULE_VERSION))
        self.assertEqual(cut.cut_summary(parsed(None, reden=2), [])["printed_reden"], 2)

    # Value: protects=a cut place without a quadrant: only a later page is after it, so the last printed Rede and its
    #   page neighbours are never listed as unprinted; a DIP Rede without a quadrant on the cut's page is not after it;
    #   fails_when=the last Rede itself is listed as missing; why_new=TODOS cut-protocols item 3; seam=parser
    def test_a_cut_place_without_a_quadrant_counts_only_later_pages(self):
        notice = {**NOTICE_READ, "last_rede": {"rede_id": "ID2", "page": 12, "quadrant": None, "surname": "Berg"}}
        result = cut.protocol_cut(parsed(notice), ACTIVITIES)
        self.assertEqual([e["dip_activity_id"] for e in result["entries"] if e["kind"] == "rede"], ["a5"])
        bare = [*ACTIVITIES, activity("b1", "Rede", "Fritz Fink, MdB, SPD", "12", "17"),
                activity("b2", "Rede", "Gerd Gans, MdB, SPD", "13", "18")]
        result = cut.protocol_cut(parsed(NOTICE_READ), bare)
        self.assertEqual([e["dip_activity_id"] for e in result["entries"] if e["kind"] == "rede"], ["a4", "b2", "a5"])
        self.assertEqual([cut.after_cut(place, (12, "B")) for place in ((12, ""), (12, "C"), (13, ""), (12, "A"))],
                         [False, True, True, False])
        self.assertEqual([cut.after_cut(place, (12, "")) for place in ((12, "D"), (12, ""), (13, ""), (11, "D"))],
                         [False, False, True, False])

    # Value: protects=a DIP Aktivität that gives its place in anfangsseite and anfangsquadrant (no seite) is placed by
    #   them, and one with a page alone has no quadrant; fails_when=such an entry has no page and is never shown to lie
    #   after the cut, or is listed with a guessed quadrant; why_new=TODOS cut-protocols item 8 (coverage); seam=parser
    def test_a_dip_place_from_the_separate_page_and_quadrant_fields(self):
        separate = [*ACTIVITIES,
                    {"id": "f1", "aktivitaetsart": "Rede", "titel": "Fritz Fink, MdB, SPD", "person_id": "17",
                     "fundstelle": {"anfangsseite": "14", "anfangsquadrant": "c"}},
                    {"id": "f2", "aktivitaetsart": "Rede", "titel": "Gerd Gans, MdB, SPD", "person_id": "18",
                     "fundstelle": {"anfangsseite": "15"}}]
        entries = cut.protocol_cut(parsed(NOTICE_READ), separate)["entries"]
        self.assertEqual([(e["dip_activity_id"], e["page"], e["quadrant"]) for e in entries if e["kind"] == "rede"],
                         [("a4", 12, "C"), ("a5", 13, "A"), ("f1", 14, "C"), ("f2", 15, None)])

    # Value: protects=rule 3 needs both of its counts at RULE3_MIN: 4 DIP Reden after the last <rede>, or 4 more than the
    #   file prints, is no evidence; fails_when=a whole file with a few late DIP Reden stops the gate; why_new=TODOS
    #   cut-protocols item 8 (coverage); seam=parser
    def test_rule_3_needs_both_counts_at_its_threshold(self):
        root = protocol_root(notice="")
        before = [activity(f"b{n}", "Rede", f"Before Page{n}, MdB", "11A") for n in range(6)]
        after = [activity(f"l{n}", "Rede", f"Later Page{n}, MdB", "13A") for n in range(6)]
        self.assertIsNone(cut.unmarked_cut_evidence(root, [*before, *after[:4]], 0))
        self.assertIsNone(cut.unmarked_cut_evidence(root, after, 2))
        self.assertEqual(cut.unmarked_cut_evidence(root, after[:5], 0),
                         {"last_rede_id": "ID2", "dip_reden_after": 5, "dip_reden_more": 5})

    def test_rule_3_counts_only_later_pages_without_a_quadrant(self):
        root = protocol_root(notice="", toc=xref("ID1", 10, "A") + xref("ID2", 12, ""))
        same_page = [activity(f"s{n}", "Rede", f"Same Page{n}, MdB", "12C") for n in range(6)]
        self.assertIsNone(cut.unmarked_cut_evidence(root, same_page, 0))
        later = [activity(f"l{n}", "Rede", f"Later Page{n}, MdB", "13A") for n in range(6)]
        self.assertEqual(cut.unmarked_cut_evidence(root, later, 0)["dip_reden_after"], 6)

    # Value: protects=the count of DIP Reden after the cut is exact only where no DIP Rede lies at the cut's place
    #   besides the last printed one; the rest are counted as unplaced, so a page can say "mindestens" there and
    #   nowhere else; fails_when=a reader takes a floor for the number missing, or a dossier says "0 Reden fehlen" for
    #   a sitting DIP lists more Reden of; why_new=code review of steps 7-10, finding 2; seam=parser
    def test_dip_reden_at_the_cut_place_besides_the_last_printed_one_are_unplaced(self):
        # a3 shares 12B with Berg's last printed Rede: before or after it, the quadrant cannot say.
        self.assertEqual(cut.protocol_cut(parsed(NOTICE_READ), ACTIVITIES)["unplaced_reden"], 1)
        alone = [a for a in ACTIVITIES if a["id"] != "a3"]
        self.assertEqual(cut.protocol_cut(parsed(NOTICE_READ), alone)["unplaced_reden"], 0)
        # Without a quadrant the cut's whole page is its place: a3 and a4 are unplaced, Berg's own Rede is not.
        notice = {**NOTICE_READ, "last_rede": {"rede_id": "ID2", "page": 12, "quadrant": None, "surname": "Berg"}}
        self.assertEqual(cut.protocol_cut(parsed(notice), ACTIVITIES)["unplaced_reden"], 2)
        # A DIP Rede without a page, or without a quadrant on the cut's page, cannot be placed either; one on the cut's
        # page in an earlier quadrant is printed.
        extra = [*alone, activity("n1", "Rede", "Nora Nopage, MdB, SPD", ""),
                 activity("n2", "Rede", "Olga Ohne, MdB, SPD", "12"), activity("n3", "Rede", "Paul Prior, MdB, SPD", "12A")]
        self.assertEqual(cut.protocol_cut(parsed(NOTICE_READ, reden=4), extra)["unplaced_reden"], 2)
        # No DIP Rede at the place matches the last speaker: every one there is unplaced.
        stranger = [activity("s1", "Rede", "Sara Stranger, MdB, SPD", "12B"), *ACTIVITIES[3:]]
        self.assertEqual(cut.protocol_cut(parsed(NOTICE_READ, reden=0), stranger)["unplaced_reden"], 1)

    def test_a_sitting_dip_has_not_indexed_has_no_count_of_unplaced_reden(self):
        self.assertIsNone(cut.protocol_cut(parsed(NOTICE_READ, reden=40), [])["unplaced_reden"])

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
        self.assertEqual((summary["cut_rule_version"], summary["printed_reden"]), (cut.CUT_RULE_VERSION, 3))  # pregate-literal: CUT_RULE_VERSION=3 the 3 is a speech count; the version comes from the constant
        self.assertEqual((summary["protocol_cut"]["page"], summary["protocol_cut"]["quadrant"]), (103, "B"))
        self.assertEqual([e["dip_activity_id"] for e in summary["protocol_cut"]["entries"]], ["x1"])

    # Value: protects=an online build records the cut, the rule's version and its count of printed Reden from DIP's
    #   Aktivitäten, as the offline re-parse does; fails_when=an online build leaves the cut keys out and the sitting
    #   is re-read on every replay, or gate rule 3 finds no count; why_new=TODOS cut-protocols item 8 (coverage), R1;
    #   seam=fetch_text and enrich_with_api stubbed; no_claim=build_report's refusal of a cut the rule cannot read
    #   (session 2's change)
    def test_an_online_build_records_the_cut_the_rule_version_and_the_printed_reden(self):
        import io
        from types import SimpleNamespace

        def enrich(client, protocol, parsed_xml, *args, **kwargs):
            return {"agenda_items": [{**top, "api": dip.no_api_fields()} for top in parsed_xml["agenda_items"]],
                    "api_totals": {}, "api_records": {"aktivitaeten": copy.deepcopy(CUT_AKTIVITAETEN)}, "warnings": [],
                    "sampled_people": [], "sitting_votes": [], "acquisition": {}}

        protocol = {"id": "p1", "dokumentnummer": "20/999",
                    "fundstelle": {"xml_url": "https://dserver.bundestag.de/btp/20/20999.xml"}}
        args = SimpleNamespace(api_key="test", sleep=0, person_limit=0, vote_scan_pages=0, limit_tops=None)
        with mock.patch.object(dip, "fetch_text", return_value=cut_fixture_xml()), \
                mock.patch.object(dip, "enrich_with_api", side_effect=enrich), mock.patch("sys.stderr", new_callable=io.StringIO):
            summary = dip.build_report(args, protocol)["validation_summary"]
        self.assertEqual((summary["cut_rule_version"], summary["printed_reden"]), (cut.CUT_RULE_VERSION, 3))  # pregate-literal: CUT_RULE_VERSION=3 the 3 is a speech count; the version comes from the constant
        self.assertEqual(([e["dip_activity_id"] for e in summary["protocol_cut"]["entries"]],
                          summary["protocol_cut"]["unplaced_reden"]), (["x1", "x2"], 0))

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
        # Rule 1 counted a withheld Rede as missing and placed a quadrant-less cut on page 0 of its quadrant
        # (TODOS cut-protocols items 2, 3 and 9): a report read under it is re-read.
        report["validation_summary"]["cut_rule_version"] = 1
        self.assertIn("cut", site.stale_causes(report))
        # Rule 2 gave no count of the DIP Reden a cut cannot place (code review of steps 7 to 10, finding 2).
        report["validation_summary"]["cut_rule_version"] = 2
        self.assertIn("cut", site.stale_causes(report))
        # Rule 3 counted every withheld unit as a printed Rede and wrote no count of its own (TODOS cut-protocols
        # item 15).
        report["validation_summary"]["cut_rule_version"] = 3  # pregate-literal: CUT_RULE_VERSION=3 rule 3 is the old version this test feeds in on purpose
        self.assertIn("cut", site.stale_causes(report))
        self.assertGreater(cut.CUT_RULE_VERSION, 3)  # pregate-literal: CUT_RULE_VERSION=3 asserts the rule moved past version 3


class RefusalTests(unittest.TestCase):
    """A file or a DIP list the cut rule cannot place stops the run with a fix that fits it: a re-fetch of the
    same files gives the same refusal."""

    PROTOCOL = {"id": "p1", "dokumentnummer": "20/999",
                "fundstelle": {"xml_url": "https://dserver.bundestag.de/btp/20/20999.xml"}}
    NO_ID = [{"aktivitaetsart": "Rede", "titel": "Ada Lovelace, MdB", "fundstelle": {"seite": "101A"}}]

    @staticmethod
    def other_sitting():
        xml = cut_fixture_xml()
        assert "Bericht der 999. Sitzung" in xml
        return xml.replace("Bericht der 999. Sitzung", "Bericht der 998. Sitzung")

    # Value: protects=an offline replay a cut refusal stops names the cause and its fix; fails_when=it says the file is
    #   not the Plenarprotokoll XML and to delete it, which a re-fetch undoes; why_new=TODOS cut review item 1;
    #   seam=reparse_cached_xml
    def test_the_replay_gives_the_refusal_its_own_fix(self):
        cases = (("notice names another sitting", self.other_sitting(), [], "names the 998. Sitzung"),
                 ("Aktivität without an id", cut_fixture_xml(), self.NO_ID, "without an id"))
        for name, xml, aktivitaeten, said in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                path = site.xml_cache_path(Path(tmp), "20/999")
                path.parent.mkdir(parents=True)
                path.write_text(xml, encoding="utf-8")
                report = report_of(dip.parse_protocol_xml(cut_fixture_xml()), aktivitaeten)
                with self.assertRaises(site.CachedReportError) as caught:
                    site.reparse_cached_xml(Path(tmp), [{"report": report}])
                self.assertIn(said, str(caught.exception))
                self.assertEqual(caught.exception.fix, f"Fix: {cut.REFUSAL_FIX}")
                self.assertNotIn("is not the Plenarprotokoll XML", str(caught.exception))
                self.assertNotIn("--fetch-xml", str(caught.exception) + caught.exception.fix)

    # Value: protects=an online build refuses the source with the same fix, for the notice at parse time and for DIP's
    #   list after the enrichment; fails_when=the second escapes as a traceback; why_new=TODOS cut review item 1;
    #   seam=fetch_text and enrich_with_api stubbed
    def test_the_online_build_refuses_the_source_with_the_fix(self):
        enrichment = {"agenda_items": [], "warnings": [], "sampled_people": [], "sitting_votes": [],
                      "api_totals": {}, "api_records": {"aktivitaeten": self.NO_ID}}
        args = SimpleNamespace(api_key="test", sleep=0, person_limit=0, vote_scan_pages=0, limit_tops=None)
        cases = (("at parse time", self.other_sitting(), "names the 998. Sitzung"),
                 ("after the enrichment", cut_fixture_xml(), "without an id"))
        for name, xml, said in cases:
            with self.subTest(name), mock.patch.object(dip, "fetch_text", return_value=xml), \
                    mock.patch.object(dip, "enrich_with_api", return_value=enrichment), \
                    mock.patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(dip.DipError) as raised:
                dip.build_report(args, protocol=self.PROTOCOL)
            self.assertTrue(raised.exception.source_rejected)
            self.assertIn(said, str(raised.exception))
            self.assertIn(cut.REFUSAL_FIX, str(raised.exception))


CUT = {"announced": "2026-10-13", "last_rede_id": "R3", "page": 103, "quadrant": "B", "place_from": "inhaltsverzeichnis",
       "unplaced_reden": 0, "entries": [
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

    # Value: protects=the store keeps how many DIP Reden a cut cannot place, and NULL where DIP has not indexed the
    #   sitting, so the export says "mindestens" or "offen" instead of an exact 0; fails_when=an unindexed sitting
    #   exports as 0 Reden missing; why_new=code review of steps 7-10, findings 1 and 2; seam=persist
    def test_the_store_keeps_the_unplaced_reden_and_null_for_a_sitting_dip_has_not_indexed(self):
        conn = self.store()
        pulse_store.persist_report(conn, cut_report({**CUT, "unplaced_reden": 2}), None)
        self.assertEqual(conn.execute("SELECT xml_cut, xml_cut_unplaced_reden FROM protocols").fetchone()[:], (1, 2))
        pulse_store.persist_report(conn, cut_report({**CUT, "unplaced_reden": None, "entries": []}), None)
        self.assertEqual(conn.execute("SELECT xml_cut, xml_cut_unplaced_reden FROM protocols").fetchone()[:], (1, None))
        pulse_store.persist_report(conn, cut_report(None), None)
        self.assertEqual(conn.execute("SELECT xml_cut, xml_cut_unplaced_reden FROM protocols").fetchone()[:], (0, None))

    # Value: protects=a cached report cut under rule 2 (no unplaced_reden key) persists with NULL, and the store's
    #   rule-version check then asks for a replay instead of a KeyError traceback; fails_when=persist stops on
    #   cut["unplaced_reden"]; why_new=TODOS cut-protocols item 16e; seam=persist
    def test_a_cut_from_an_older_rule_without_unplaced_reden_persists_null_and_reads_stale(self):
        conn = self.store()
        old = {key: value for key, value in CUT.items() if key != "unplaced_reden"}
        report = cut_report(old)
        report["validation_summary"]["cut_rule_version"] = 2
        pulse_store.persist_report(conn, report, None)
        self.assertEqual(conn.execute("SELECT xml_cut, xml_cut_unplaced_reden FROM protocols").fetchone()[:], (1, None))
        with self.assertRaisesRegex(RuntimeError, "cut Protokoll files"):
            pulse_store.require_current_speech_rules(conn)

    def test_a_schema_16_store_is_refused(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE protocols (id TEXT PRIMARY KEY, document_number TEXT, xml_header_json TEXT, "
                     "xml_cut INTEGER, sitting_end_corrected TEXT)")
        with self.assertRaisesRegex(RuntimeError, "Old build-store schema"):
            pulse_store.initialize(conn)
        conn.close()

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
        "api_records": {"aktivitaeten": copy.deepcopy(ACTIVITIES)},
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

    # Value: protects=a cut sitting DIP has not indexed yet carries a reason of its own, so a re-fetch can read its
    #   Aktivitäten (which may show it whole, as 19/107); fails_when=it stays marked with an empty list for good;
    #   why_new=review of steps 1-6; seam=facts
    def test_a_cut_dip_has_not_indexed_has_its_own_reason(self):
        report = judged(protocol_cut=CUT)
        report["api_records"]["aktivitaeten"] = []
        state = facts.completeness_from_reports([report])["21/99"]
        self.assertEqual((state["speeches"], state["reasons"]["speeches"]), (False, facts.CUT_PROTOCOL_UNINDEXED))
        del report["api_records"]
        state = facts.completeness_from_reports([report])["21/99"]
        self.assertEqual(state["reasons"]["speeches"], facts.CUT_PROTOCOL_UNINDEXED)

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

    # Value: protects=19 WP 19 heads print "13.00", "2.09" or "13.00 Uhr": both times are there, so the sitting
    #   counts for times and the SQL reads its length; fails_when=2019-W07 and 2019-W39 are withheld, or a longer
    #   sitting is skipped (19/124, 9.00 to 2.09, 1,029 minutes); why_new=the times basis; seam=facts
    def test_times_printed_with_a_dot_count(self):
        state = facts.completeness_from_reports([judged("19/124", header={"sitzung_start": "9.00", "sitzung_end": "2.09"}),
                                                 judged("19/117", header={"sitzung_start": "13.00 Uhr", "sitzung_end": "17:05"}),
                                                 judged("19/1", header={"sitzung_start": "ab:cd", "sitzung_end": "17:05"})])
        self.assertEqual((state["19/124"]["times"], state["19/117"]["times"], state["19/1"]["times"]), (True, True, False))
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE protocols (id, document_number, date, pdf_url, xml_header_json, sitting_end_corrected)")
        for number, start, end in (("19/124", "9.00", "2.09"), ("19/117", "13.00 Uhr", "17:05"), ("19/1", "ab:cd", "17:05")):
            conn.execute("INSERT INTO protocols VALUES (?, ?, '2019-11-07', NULL, ?, NULL)",
                         (number, number, json.dumps({"sitzung_start": start, "sitzung_end": end})))
        sql = facts.REGISTRY_BY_ID["laengste-sitzung"]["sql"]
        self.assertEqual(dict(conn.execute(f"SELECT document_number, value FROM ({sql})")),
                         {"19/124": 1029, "19/117": 245, "19/1": None})

    def test_laengste_sitzung_is_judged_by_times(self):
        metric = facts.REGISTRY_BY_ID["laengste-sitzung"]
        self.assertEqual((metric["coverage"], metric["version"]), ("times", 2))
        facts.validate_registry(facts.ALL_REGISTRY)

    # Value: protects=the note a withheld Fakt shows names the cut file, and the times domain has words;
    #   fails_when=gap_note raises a KeyError on times or words a cut as "Reden nicht erfasst"; why_new=new reason; seam=facts
    def test_the_gap_notes_name_the_cut_file_and_missing_times(self):
        self.assertEqual(facts.gap_note([{"document_number": "21/99", "date": "2026-10-08", "reason": facts.CUT_PROTOCOL}],
                                        "speeches"), "Sitzung 21/99: Protokolldatei abgebrochen")
        self.assertEqual(facts.gap_note([{"document_number": "21/99", "date": "2026-10-08",
                                          "reason": facts.CUT_PROTOCOL_UNINDEXED}], "speeches"),
                         "Sitzung 21/99: Protokolldatei abgebrochen")
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

    # Value: protects=a missing, unreadable or malformed list stops the run with a ReviewedEndTimesError naming the
    #   file, never a raw OSError or a list read as empty; fails_when=a deleted list silently drops the four corrected
    #   ends, or a traceback replaces the fix; why_new=TODOS cut-protocols item 8 (coverage); seam=list
    def test_a_missing_unreadable_or_malformed_list_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "binary.json").write_bytes(b'{"entries": ["\xff"]}')
            (folder / "broken.json").write_text('{"entries": [', encoding="utf-8")
            for name, message in (("absent.json", "is missing; it is checked in"), (".", "cannot be read"),
                                  ("binary.json", "cannot be read"), ("broken.json", "is not valid JSON")):
                with self.subTest(name), self.assertRaisesRegex(reviewed_end_times.ReviewedEndTimesError, message):
                    reviewed_end_times.load(folder / name)

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


class BackfillTests(unittest.TestCase):
    @staticmethod
    def cut_entry(n, aktivitaeten=ACTIVITIES):
        from test_backfill import COMPLETE_VOTES, report_for
        report = report_for(n, acquisition=COMPLETE_VOTES)
        report["validation_summary"]["protocol_cut"] = copy.deepcopy(CUT)
        report.setdefault("api_records", {})["aktivitaeten"] = copy.deepcopy(aktivitaeten)
        return {"report": report}

    @staticmethod
    def catalog(n, xml_hash=None):
        from test_backfill import catalog_protocol
        protocol = catalog_protocol(f"21/{n}", f"pp-{n}", f"2026-06-{10 + n:02d}")
        if xml_hash is not None:
            protocol["xml_hash"] = xml_hash
        return protocol

    # Value: protects=a backfill does not fetch a cut file again and again; fails_when=every run re-downloads the 33
    #   sittings and they stay cut; why_new=step 5; seam=incomplete_sitting_protocols
    def test_a_cut_sitting_is_left_alone(self):
        acquirable, _waiting, _vote_only, structural, held = site.incomplete_sitting_protocols(
            [self.cut_entry(1)], [self.catalog(1)])
        self.assertEqual(([p["dokumentnummer"] for p in held], acquirable, structural), (["21/1"], [], []))

    # Value: protects=a cut sitting fetched before DIP indexed its Aktivitäten is fetched again, so the rule can read
    #   them; fails_when=it stays out of every backfill once it leaves the --limit window, marked with an empty list;
    #   why_new=review of steps 1-6; seam=incomplete_sitting_protocols
    def test_a_cut_sitting_without_aktivitaeten_is_acquired_again(self):
        acquirable, _waiting, _vote_only, structural, held = site.incomplete_sitting_protocols(
            [self.cut_entry(1, aktivitaeten=[])], [self.catalog(1)])
        self.assertEqual(([p["dokumentnummer"] for p in acquirable], structural, held), (["21/1"], [], []))

    # Value: protects=a cut file the Bundestag replaced is fetched again: DIP's xml_hash no longer matches the md5 of
    #   the cached file; fails_when=a replaced, whole file never reaches the store; why_new=step 5; seam=replaced_cut_files
    def test_a_cut_file_whose_catalog_hash_changed_is_acquired_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            path = site.xml_cache_path(output_dir, "21/1")
            path.parent.mkdir(parents=True)
            path.write_bytes(b"<dbtplenarprotokoll/>")
            md5 = hashlib.md5(b"<dbtplenarprotokoll/>").hexdigest()
            entries = [self.cut_entry(1), self.cut_entry(2)]
            same, _deferred = site.replaced_cut_files(output_dir, entries, [self.catalog(1, md5), self.catalog(2, md5)])
            self.assertEqual(same, set())
            changed, _deferred = site.replaced_cut_files(output_dir, entries, [self.catalog(1, "0" * 32), self.catalog(2, None)])
            self.assertEqual(changed, {"21/1"})
        acquirable, *_rest, held = site.incomplete_sitting_protocols(
            entries, [self.catalog(2), self.catalog(1)], replaced=changed)
        self.assertEqual(([p["dokumentnummer"] for p in acquirable], [p["dokumentnummer"] for p in held]),
                         (["21/1"], ["21/2"]))

    # Value: protects=a run stopped after writing a replaced XML and before its report is fetched again: the report
    #   read another file than the cached one; fails_when=the sitting stays held with an old cut report beside a final
    #   file whose md5 matches DIP's; why_new=ship review of steps 1-6 (Codex); seam=replaced_cut_files
    def test_a_cut_report_read_from_another_file_than_the_cached_one_is_acquired_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            path = site.xml_cache_path(output_dir, "21/1")
            path.parent.mkdir(parents=True)
            path.write_text("<dbtplenarprotokoll/>", encoding="utf-8")
            md5 = hashlib.md5(path.read_bytes()).hexdigest()
            entry = self.cut_entry(1)
            entry["report"]["protocol"]["xml_sha256"] = dip.xml_source_sha256("<dbtplenarprotokoll/>")
            self.assertEqual(site.replaced_cut_files(output_dir, [entry], [self.catalog(1, md5)]), (set(), set()))
            entry["report"]["protocol"]["xml_sha256"] = "0" * 64
            self.assertEqual(site.replaced_cut_files(output_dir, [entry], [self.catalog(1, md5)]), ({"21/1"}, set()))

    def selection(self, tmp, listed, *, record=None, sha=None):
        """What replaced_cut_files says of a cut sitting whose cached XML is ``<dbtplenarprotokoll/>``, with DIP
        listing ``listed`` and the report's record of its last fetch ``record``."""
        path = site.xml_cache_path(Path(tmp), "21/1")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"<dbtplenarprotokoll/>")
        entry = self.cut_entry(1)
        entry["report"]["protocol"].update({"xml_sha256": sha or dip.xml_source_sha256("<dbtplenarprotokoll/>"),
                                            **(record or {})})
        return site.replaced_cut_files(Path(tmp), [entry], [self.catalog(1, listed)],
                                       now=datetime(2026, 11, 20, 12, tzinfo=timezone.utc))

    # Value: protects=a cut sitting whose served XML never matches DIP's hash is not fetched on every backfill, and a
    #   file DIP listed before dserver served it is still read within 7 days; fails_when=every run fetches it, or the
    #   deferral never expires; why_new=TODOS cut review item 7; seam=replaced_cut_files(now)
    def test_a_fetch_that_gave_a_file_unlike_dips_hash_is_left_for_seven_days(self):
        listed, left, fetch = "a" * 32, (set(), {"21/1"}), ({"21/1"}, set())
        cases = (
            ("fetched an hour ago", {"xml_listed_hash": listed, "xml_fetched_at": "2026-11-20T11:00:00Z"}, left),
            ("hash case and spaces", {"xml_listed_hash": f" {listed.upper()} ", "xml_fetched_at": "2026-11-20T11:00:00Z"}, left),
            ("one second short of 7 days", {"xml_listed_hash": listed, "xml_fetched_at": "2026-11-13T12:00:01Z"}, left),
            ("7 days ago", {"xml_listed_hash": listed, "xml_fetched_at": "2026-11-13T12:00:00Z"}, fetch),
            ("DIP lists another hash now", {"xml_listed_hash": "b" * 32, "xml_fetched_at": "2026-11-20T11:00:00Z"}, fetch),
            ("no record", {}, fetch),
            ("no time", {"xml_listed_hash": listed}, fetch),
            ("unreadable time", {"xml_listed_hash": listed, "xml_fetched_at": "gestern"}, fetch),
            ("time ahead of the clock", {"xml_listed_hash": listed, "xml_fetched_at": "2026-11-21T00:00:00Z"}, fetch),
            ("wrong types", {"xml_listed_hash": 7, "xml_fetched_at": 7}, fetch),
        )
        for name, record, expected in cases:
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                self.assertEqual(self.selection(tmp, listed, record=record), expected)
        with self.subTest("a report read from another file is fetched at once"), tempfile.TemporaryDirectory() as tmp:
            record = {"xml_listed_hash": listed, "xml_fetched_at": "2026-11-20T11:00:00Z"}
            self.assertEqual(self.selection(tmp, listed, record=record, sha="0" * 64), fetch)

    # Value: protects=a real fetch records what DIP listed for the file it read and when, and a replay keeps that
    #   record; fails_when=the next backfill has nothing to defer by, or a replay restarts the 7 days;
    #   why_new=TODOS cut review item 7; seam=fetch_text and enrich_with_api stubbed
    def test_an_online_build_records_the_fetch_and_a_replay_keeps_it(self):
        protocol = {"id": "p1", "dokumentnummer": "20/999", "xml_hash": " " + "A" * 32,
                    "fundstelle": {"xml_url": "https://dserver.bundestag.de/btp/20/20999.xml"}}
        enrichment = {"agenda_items": [], "warnings": [], "sampled_people": [], "sitting_votes": [],
                      "api_totals": {}, "api_records": {"aktivitaeten": []}}
        args = SimpleNamespace(api_key="test", sleep=0, person_limit=0, vote_scan_pages=0, limit_tops=None)
        with mock.patch.object(dip, "fetch_text", return_value=cut_fixture_xml()), \
                mock.patch.object(dip, "enrich_with_api", return_value=enrichment), \
                mock.patch.object(dip, "utc_now", return_value="2026-11-20T11:00:00Z"), \
                mock.patch("sys.stderr", new_callable=io.StringIO):
            report = dip.build_report(args, protocol=protocol)
        record = ("a" * 32, "2026-11-20T11:00:00Z")
        self.assertEqual((report["protocol"]["xml_listed_hash"], report["protocol"]["xml_fetched_at"]), record)
        parsed = dip.parse_protocol_xml(cut_fixture_xml())
        report["agenda_items"] = report_of(parsed, [])["agenda_items"]
        dip.reparse_report_xml(report, parsed)
        self.assertEqual((report["protocol"]["xml_listed_hash"], report["protocol"]["xml_fetched_at"]), record)

    # Value: protects=the run names the cut files apart from withheld Reden; fails_when=they read as withheld Reden or
    #   as sittings a backfill would fix; why_new=step 5; seam=format_incomplete_report
    def test_the_run_names_the_cut_files_on_a_line_of_their_own(self):
        from test_backfill import catalog_protocol
        gaps = {"21/99": {"date": "2026-10-08", "reasons": {"speeches": facts.CUT_PROTOCOL}},
                "18/3": {"date": "2013-11-18", "reasons": {"speeches": facts.WITHHELD_REDEN}}}
        catalog = [catalog_protocol(n, f"pp-{n}", gap["date"]) for n, gap in gaps.items()]
        text = "\n".join(site.format_incomplete_report({"incomplete_periods": [], "sitting_gaps": gaps},
                                                       output_dir=Path("site"), catalog_protocols=catalog,
                                                       vote_scan_pages=30))
        self.assertIn("1 sittings hold a Protokoll file that stops partway (E16): only a replaced file closes them, "
                      "not a backfill (21/99)", text)
        self.assertIn("1 sittings hold withheld Reden", text)
        self.assertIn("Fix: none available now", text)

    def test_the_backfill_says_why_it_leaves_each_sitting(self):
        from test_backfill import report_for
        withheld = report_for(2)
        withheld["validation_summary"]["withheld_rede_count"] = 1
        no_times = report_for(3)
        entries = [self.cut_entry(1), {"report": withheld}, {"report": no_times}]
        lines = site.unacquirable_lines([self.catalog(n) for n in (1, 2, 3)], entries, {"21/4"}, [self.catalog(4)])
        self.assertEqual([line.split(":")[0] for line in lines], [
            "[backfill] leaving 1 sitting(s) whose Protokoll file stops partway (E16)",
            "[backfill] leaving 1 sitting(s) held back only by withheld Reden (ADR 0005)",
            "[backfill] leaving 1 sitting(s) whose XML prints no start or end time",
            "[backfill] acquiring 1 cut sitting(s) again"])

    # Value: protects=the run says "acquiring ... again" only of replaced cut sittings it acquires; fails_when=a
    #   sitting outside --protocol-wahlperiode, or one DIP has no XML for, is counted; why_new=TODOS cut review item 5;
    #   seam=unacquirable_lines
    def test_only_the_replaced_sittings_the_run_acquires_are_counted(self):
        lines = site.unacquirable_lines([], [], {"21/4", "21/5", "20/9"}, [self.catalog(4), self.catalog(6)])
        # Both causes of ``replaced_cut_files`` are named: the hash, and a report read from another file.
        self.assertEqual(lines, ["[backfill] acquiring 1 cut sitting(s) again: DIP lists their XML with another hash "
                                 "now, so the file may have been replaced, or the report was read from another file "
                                 "than the cached one (21/4)."])
        self.assertEqual(site.unacquirable_lines([], [], {"20/9"}, [self.catalog(4)]), [])

    # Value: protects=a deferred sitting is named, so the run is not silent about a hash that does not match;
    #   fails_when=it reads only as a file the Bundestag has not replaced, or a sitting acquired for another gap is
    #   named as left alone; why_new=TODOS cut review item 7; seam=unacquirable_lines
    def test_a_deferred_sitting_the_run_leaves_is_named(self):
        lines = site.unacquirable_lines([self.catalog(1)], [self.cut_entry(1)], set(), [self.catalog(2)],
                                        {"21/1", "21/2"})
        self.assertEqual(lines[1:], [
            "[backfill] not fetching 1 cut sitting(s) again yet: their last fetch, made while DIP listed the same hash, "
            "gave a file with another one; the first backfill 7 days after that fetch tries again (21/1)."])


#: DIP's Aktivitäten for cut_fixture_xml() that give CUT under the current rule: the file's three Reden (101 A to
#: 103 B), Dreher's Rede after the cut (x1) and Esch's Rede zu Protokoll, unplaced and with no DIP person (x2).
CUT_AKTIVITAETEN = [
    *(activity(f"r{n}", "Rede", f"{name}, MdB", seite) for n, (name, seite) in
      enumerate((("Ada Lovelace", "101A"), ("Bruno Beispiel", "102C"), ("Clara Kontrolle", "103B")))),
    activity("x1", "Rede", "Dora Dreher, MdB, Die Linke", "104A", "8173"),
    {"id": "x2", "aktivitaetsart": "Rede (zu Protokoll gegeben)", "titel": "Emil Esch, MdB, CDU/CSU", "person_id": None,
     "fundstelle": {}},
]


class GateTests(unittest.TestCase):
    def output(self, xml, report, *, catalog=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        output = Path(tmp.name)
        data = output / "data"
        (data / "xml").mkdir(parents=True)
        number = report["protocol"]["dokumentnummer"]
        (data / "xml" / f"plenarprotokoll-{number.replace('/', '-')}.xml").write_text(xml, encoding="utf-8")
        (data / f"plenarprotokoll-{number.replace('/', '-')}.json").write_text(json.dumps(report), encoding="utf-8")
        (data / "plenarprotokoll-catalog.json").write_text(json.dumps({"protocols": catalog or []}), encoding="utf-8")
        conn = pulse_store.connect(data / "bundestag-pulse.sqlite")
        try:
            pulse_store.persist_report(conn, report, None)
            # The build binds unprinted entries once the roster is in: x1's DIP person is an MdB here.
            conn.execute("UPDATE mps SET dip_person_id = '8173' WHERE id = (SELECT MIN(id) FROM mps)")
            pulse_store.resolve_unprinted_people(conn)
            conn.commit()
        finally:
            conn.close()
        return output, data / "bundestag-pulse.sqlite"

    def gate_report(self, protocol_cut, aktivitaeten=CUT_AKTIVITAETEN):
        report = cut_report(protocol_cut)
        report["api_records"] = {"aktivitaeten": list(aktivitaeten)}
        report["validation_summary"]["xml_speech_count"] = 3
        report["validation_summary"]["withheld_rede_count"] = 0
        report["validation_summary"]["printed_reden"] = 3
        return report

    # Value: protects=the mark and the notice agree, and the receipt carries the counts; fails_when=a sitting is
    #   marked whose file is whole, or the 33 and the two counts are missing from the receipt; why_new=step 6; seam=gate
    def test_a_marked_sitting_with_the_notice_passes_and_is_counted(self):
        self.assertEqual(cut.protocol_cut(dip.parse_protocol_xml(cut_fixture_xml()), CUT_AKTIVITAETEN)["entries"],
                         CUT["entries"])
        output, database = self.output(cut_fixture_xml(), self.gate_report(CUT))
        result = gate.cut_protocol_check(output, database)
        self.assertEqual((result["problems"], result["sittings"], result["rede"], result["zu_protokoll"], result["marked"]),
                         ([], 1, 1, 1, ["20/999"]))

    # Value: protects=check 8 judges every marked sitting, not only those whose report it happens to read, and a run
    #   that reads no report fails instead of passing with nothing checked; fails_when=a marked sitting without its
    #   cached report, or an empty data/, passes check 8; why_new=TODOS cut-protocols item 4; seam=gate
    def test_a_marked_sitting_without_a_cached_report_fails(self):
        output, database = self.output(cut_fixture_xml(), self.gate_report(CUT))
        (output / "data" / "plenarprotokoll-20-999.json").unlink()
        problems = " ".join(gate.cut_protocol_check(output, database)["problems"])
        self.assertIn("20/999: marked cut, but no cached report was read for it", problems)

    def test_an_empty_data_directory_fails(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        output = Path(tmp.name)
        (output / "data").mkdir()
        conn = pulse_store.connect(output / "data" / "bundestag-pulse.sqlite")
        pulse_store.initialize(conn)
        conn.close()
        result = gate.cut_protocol_check(output, output / "data" / "bundestag-pulse.sqlite")
        self.assertIn("no cached report was read", " ".join(result["problems"]))

    # Value: protects=check 8 re-runs the rule on each marked sitting's cached XML and Aktivitäten: a mark the current
    #   rule no longer gives (the old 19/107 case) fails; fails_when=a whole sitting stays marked after a rule change
    #   because the gate only checks that the notice is printed; why_new=TODOS cut-protocols item 4; seam=gate
    def test_a_marked_sitting_the_rule_now_reads_whole_fails(self):
        printed = [activity(f"r{n}", "Rede", "X Y, MdB", "101A") for n in range(3)]
        output, database = self.output(cut_fixture_xml(), self.gate_report(CUT, printed))
        self.assertIn("20/999: marked cut, but the cut rule reads its cached XML and DIP's Aktivitäten whole",
                      " ".join(gate.cut_protocol_check(output, database)["problems"]))

    # Value: protects=the stored count of DIP Reden a cut cannot place is the rule's, NULL included (NULL means DIP has
    #   not indexed the sitting, never 0); fails_when=a page says "mindestens" or an exact count the rule does not give;
    #   why_new=TODOS cut-protocols item 16d; seam=gate
    def test_a_stored_count_of_unplaced_reden_the_rule_does_not_give_fails(self):
        output, database = self.output(cut_fixture_xml(), self.gate_report(CUT))
        for stored, shown in ((2, "2"), (None, "None")):
            with self.subTest(stored=stored), sqlite3.connect(database) as conn:
                conn.execute("UPDATE protocols SET xml_cut_unplaced_reden = ?", (stored,))
                conn.commit()
                self.assertIn(f"20/999: xml_cut_unplaced_reden {shown}, the cut rule gives 0",
                              " ".join(gate.cut_protocol_check(output, database)["problems"]))

    # Value: protects=the stored unprinted rows are the rule's, row for row with DIP id, kind, DIP person, page and
    #   quadrant (R4: the DIP person on each row, not the later mp_id binding); fails_when=a stale row, a dropped row,
    #   or a row naming another DIP person passes the gate; why_new=TODOS cut-protocols item 4, eng review R4; seam=gate
    def test_unprinted_rows_the_rule_does_not_give_fail(self):
        without_x2 = [a for a in CUT_AKTIVITAETEN if a["id"] != "x2"]
        output, database = self.output(cut_fixture_xml(), self.gate_report(CUT, without_x2))
        self.assertIn("20/999: unprinted_contributions holds rows the cut rule does not give: x2 zu_protokoll",
                      " ".join(gate.cut_protocol_check(output, database)["problems"]))
        output, database = self.output(cut_fixture_xml(), self.gate_report(CUT))
        with sqlite3.connect(database) as conn:
            conn.execute("UPDATE unprinted_contributions SET dip_person_id = '9999' WHERE dip_activity_id = 'x1'")
        problems = " ".join(gate.cut_protocol_check(output, database)["problems"])
        self.assertIn("20/999: unprinted_contributions holds rows the cut rule does not give: x1 rede person 9999 104A", problems)
        self.assertIn("20/999: the cut rule gives rows unprinted_contributions does not hold: x1 rede person 8173 104A", problems)

    # Value: protects=a marked sitting whose recompute the rule or the parser refuses is a named problem, not a
    #   traceback that stops the gate; fails_when=an id-less DIP Rede or a stale reviewed entry crashes check 8;
    #   why_new=TODOS cut-protocols item 4 (O5: ReviewedUnitsError is no ValueError); seam=gate
    def test_a_marked_sitting_whose_recompute_refuses_is_named(self):
        id_less = [*CUT_AKTIVITAETEN, activity("", "Rede", "Fritz Fink, MdB, SPD", "104B")]
        output, database = self.output(cut_fixture_xml(), self.gate_report(CUT, id_less))
        self.assertIn("20/999: the cut rule refuses its cached XML and DIP's Aktivitäten: 20/999: DIP lists an Aktivität "
                      "without an id", " ".join(gate.cut_protocol_check(output, database)["problems"]))
        output, database = self.output(cut_fixture_xml(), self.gate_report(CUT))
        with mock.patch.object(dip, "parse_protocol_xml", side_effect=dip.reviewed_units.ReviewedUnitsError("stale entry")):
            self.assertIn("20/999: the cut rule refuses its cached XML and DIP's Aktivitäten: stale entry",
                          " ".join(gate.cut_protocol_check(output, database)["problems"]))

    def test_a_marked_sitting_without_the_notice_fails(self):
        xml = (_support.FIXTURES / "protocol.xml").read_text(encoding="utf-8")
        output, database = self.output(xml, self.gate_report(CUT))
        self.assertIn("prints no notice", " ".join(gate.cut_protocol_check(output, database)["problems"]))

    def test_the_notice_without_a_mark_fails_unless_the_rule_reads_it_whole(self):
        output, database = self.output(cut_fixture_xml(), self.gate_report(None))
        self.assertIn("not marked", " ".join(gate.cut_protocol_check(output, database)["problems"]))
        printed = [activity(f"r{n}", "Rede", "X Y, MdB", "101A") for n in range(3)]
        output, database = self.output(cut_fixture_xml(), self.gate_report(None, printed))
        result = gate.cut_protocol_check(output, database)
        self.assertEqual((result["problems"], result["notice_but_whole"]), ([], ["20/999"]))

    # Value: protects=rule 3: a file without the notice that looks cut stops the gate for a person; fails_when=a cut
    #   file the Bundestag printed without the notice counts as whole unnoticed; why_new=step 6; seam=gate
    def test_a_file_without_the_notice_that_looks_cut_fails(self):
        xml = (_support.FIXTURES / "protocol.xml").read_text(encoding="utf-8").replace("<xref ", '<xref ref-type="rede" ')
        after = [activity(f"x{n}", "Rede", f"Late Speaker{n}, MdB", f"{110 + n}A") for n in range(8)]
        output, database = self.output(xml, self.gate_report(None, after))
        result = gate.cut_protocol_check(output, database)
        self.assertEqual([entry["dip_reden_after"] for entry in result["rule3"]], [8])
        self.assertIn("look cut by rule 3", " ".join(result["problems"]))
        # A withheld Rede is printed: DIP's 8 against the rule's 4 printed Reden (3 stored, 1 withheld) is 4 more,
        # below rule 3's 5 (item 2).
        report = self.gate_report(None, after)
        report["validation_summary"].update({"withheld_rede_count": 1, "printed_reden": 4})
        output, database = self.output(xml, report)
        self.assertEqual(gate.cut_protocol_check(output, database)["rule3"], [])
        # A withheld unit that would be a Beitrag is no printed Rede: the rule's count stays 3, and the file looks cut
        # (item 15).
        report["validation_summary"]["printed_reden"] = 3
        output, database = self.output(xml, report)
        self.assertEqual([entry["dip_reden_more"] for entry in gate.cut_protocol_check(output, database)["rule3"]], [5])

    # Value: protects=the gate names a report without the rule's count of printed Reden instead of judging rule 3 by a
    #   guess; fails_when=the type check is dropped and None - int raises, or the gate sums the counts on its own;
    #   why_new=item 15 (R1: the rule writes printed_reden); seam=none; no_claim=the real parser's output (report built by hand)
    def test_a_report_without_the_count_of_printed_reden_is_named_not_judged(self):
        xml = (_support.FIXTURES / "protocol.xml").read_text(encoding="utf-8")
        for broken in (None, "3", True):
            with self.subTest(printed_reden=broken):
                report = self.gate_report(None)
                if broken is None:
                    del report["validation_summary"]["printed_reden"]
                else:
                    report["validation_summary"]["printed_reden"] = broken
                output, database = self.output(xml, report)
                result = gate.cut_protocol_check(output, database)
                self.assertIn("holds no count of printed Reden", " ".join(result["problems"]))
                self.assertEqual(result["rule3"], [])

    # Value: protects=no unprinted entry is a stored Rede over again; fails_when=a DIP Rede the file prints is listed as
    #   missing; why_new=step 6; seam=gate
    def test_an_unprinted_entry_on_a_stored_redes_place_fails(self):
        output, database = self.output(cut_fixture_xml(), self.gate_report(CUT))
        with sqlite3.connect(database) as conn:
            mp_id, page, quadrant = conn.execute("SELECT mp_id, page, page_quadrant FROM speeches LIMIT 1").fetchone()
            conn.execute("UPDATE unprinted_contributions SET mp_id = ?, page = ?, page_quadrant = ? WHERE dip_activity_id = 'x1'",
                         (mp_id, page, quadrant))
        self.assertIn("share person, place and sitting", " ".join(gate.cut_protocol_check(output, database)["problems"]))

    # Value: protects=every unprinted Rede is bound to an mps row, or the gate stops; fails_when=an unbound one drops
    #   out of erste-reden v4 and a later Rede reads as the debut; why_new=ship review of steps 1-6 (Codex); seam=gate
    def test_an_unbound_unprinted_rede_fails(self):
        output, database = self.output(cut_fixture_xml(), self.gate_report(CUT))
        self.assertEqual(gate.cut_protocol_check(output, database)["problems"], [])
        with sqlite3.connect(database) as conn:
            conn.execute("UPDATE unprinted_contributions SET mp_id = NULL WHERE dip_activity_id = 'x1'")
        self.assertIn("1 unprinted Reden are bound to no MdB: 20/999 x1",
                      " ".join(gate.cut_protocol_check(output, database)["problems"]))

    # Value: protects=the corrected end times hold in the store and against DIP's pdf_hash; fails_when=a PDF replaced
    #   since the reading goes unnoticed, or the column holds a time no entry gives; why_new=step 6 (3b); seam=gate
    # Value: protects=without a cached catalog check 9 still names each entry's pdf_md5 as unconfirmed, with "(none)"
    #   for the catalog's hash; fails_when=a missing catalog passes check 9 or prints an empty hash; why_new=TODOS
    #   cut-protocols item 8 (coverage); seam=gate
    def test_without_a_catalog_the_end_time_check_names_no_hash(self):
        entries = reviewed_end_times.check({"entries": [end_entry()]})
        with reviewed_end_times.using(entries):
            output, database = self.output(cut_fixture_xml(), timed_report())
        (output / "data" / "plenarprotokoll-catalog.json").unlink()
        with mock.patch.object(gate.reviewed_end_times, "load", return_value=entries):
            self.assertIn("20/999: pdf_md5 8eea57bbf4299710b4dabd82d557abfb is not the catalog's pdf_hash (none): "
                          "read the PDF again", " ".join(gate.end_time_check(output, database)["problems"]))

    def test_the_end_time_entries_hold_against_the_store_and_the_catalog(self):
        entries = reviewed_end_times.check({"entries": [end_entry()]})
        catalog = [{"dokumentnummer": "20/999", "pdf_hash": "8eea57bbf4299710b4dabd82d557abfb"}]
        with reviewed_end_times.using(entries):
            output, database = self.output(cut_fixture_xml(), timed_report(), catalog=catalog)
        with mock.patch.object(gate.reviewed_end_times, "load", return_value=entries):
            self.assertEqual(gate.end_time_check(output, database)["problems"], [])
            (output / "data" / "plenarprotokoll-catalog.json").write_text(
                json.dumps({"protocols": [{"dokumentnummer": "20/999", "pdf_hash": "0" * 32}]}), encoding="utf-8")
            self.assertIn("read the PDF again", " ".join(gate.end_time_check(output, database)["problems"]))
        with mock.patch.object(gate.reviewed_end_times, "load", return_value=[]):
            self.assertIn("without an entry", " ".join(gate.end_time_check(output, database)["problems"]))



import render_dip_pulse_html as pulse_html  # noqa: E402


class CutSentenceTests(unittest.TestCase):
    # Value: protects=the one sentence the Puls week and the person page share (owner, 2026-11-26): which sittings,
    #   how many Reden laut DIP, where they are missing; fails_when=a reader takes a week's Redeanteil or a person's
    #   count for complete; why_new=step 7; seam=renderer
    def test_one_sitting_of_a_week(self):
        self.assertEqual(
            pulse_html.cut_gap_sentence(["21/99"], 66, None, "in Redeanteil und Rangfolge dieser Woche", scope="dieser Woche"),
            "In Sitzung 21/99 endet die Protokolldatei vorzeitig; 66 Reden laut DIP fehlen in Redeanteil und Rangfolge dieser Woche.")

    def test_several_sittings_and_both_kinds(self):
        self.assertEqual(
            pulse_html.cut_gap_sentence(["21/102", "21/105"], 118, None, "in Redeanteil und Rangfolge dieser Woche",
                                        scope="dieser Woche"),
            "In 2 Sitzungen dieser Woche (21/102, 21/105) endet die Protokolldatei vorzeitig; 118 Reden laut DIP fehlen "
            "in Redeanteil und Rangfolge dieser Woche.")
        self.assertEqual(
            pulse_html.cut_gap_sentence(["21/96", "21/99"], 3, 1, "auf dieser Seite"),
            "In 2 Sitzungen (21/96, 21/99) endet die Protokolldatei vorzeitig; 3 Reden und 1 zu Protokoll gegebene Rede "
            "laut DIP fehlen auf dieser Seite.")

    def test_one_missing_rede_is_singular_and_many_sittings_are_cut_short(self):
        self.assertEqual(pulse_html.cut_gap_sentence(["21/99"], 0, 1, "auf dieser Seite"),
                         "In Sitzung 21/99 endet die Protokolldatei vorzeitig; 1 zu Protokoll gegebene Rede laut DIP fehlt "
                         "auf dieser Seite.")
        numbers = [f"21/{n}" for n in range(10, 17)]
        self.assertIn("In 7 Sitzungen (21/10, 21/11, 21/12, 21/13, 21/14 und 2 weitere) endet",
                      pulse_html.cut_gap_sentence(numbers, 9, 0, "auf dieser Seite"))

    # Value: protects=a count that is only a floor (DIP Reden the cut cannot place) says "mindestens"; fails_when=a
    #   reader takes a floor for the number missing; why_new=code review of steps 7-10, finding 2; seam=renderer
    def test_a_floor_says_mindestens(self):
        self.assertEqual(
            pulse_html.cut_gap_sentence(["21/99"], 66, None, "in Redeanteil und Rangfolge dieser Woche", scope="dieser Woche",
                                        floor=True),
            "In Sitzung 21/99 endet die Protokolldatei vorzeitig; mindestens 66 Reden laut DIP fehlen in Redeanteil und "
            "Rangfolge dieser Woche.")
        self.assertEqual(
            pulse_html.cut_gap_sentence(["21/99"], 1, 2, "auf dieser Seite", floor=True),
            "In Sitzung 21/99 endet die Protokolldatei vorzeitig; mindestens 1 Rede und 2 zu Protokoll gegebene Reden "
            "laut DIP fehlen auf dieser Seite.")

    # Value: protects=a count of zero reads as words, and a floor of zero as an open count; fails_when=a page prints
    #   "0 Reden laut DIP fehlen" or "mindestens 0 Reden"; why_new=TODOS cut review item 11; seam=renderer
    def test_zero_reads_keine_rede_and_a_floor_of_zero_is_open(self):
        week = "in Redeanteil und Rangfolge dieser Woche"
        head = "In Sitzung 21/99 endet die Protokolldatei vorzeitig; "
        for written in (None, 0):
            with self.subTest(written=written):
                self.assertEqual(pulse_html.cut_gap_sentence(["21/99"], 0, written, week),
                                 f"{head}keine Rede laut DIP fehlt {week}.")
                self.assertEqual(pulse_html.cut_gap_sentence(["21/99"], 0, written, week, floor=True),
                                 f"{head}wie viele Reden {week} fehlen, ist offen.")
        self.assertEqual(pulse_html.cut_gap_sentence(["21/99"], 0, 1, "auf dieser Seite", floor=True),
                         f"{head}1 zu Protokoll gegebene Rede laut DIP fehlt auf dieser Seite; ob auch Reden fehlen, ist offen.")
        # A sitting DIP has not indexed may hold more written Reden too; an unplaced Rede is a spoken one.
        two = ["21/105", "21/108"]
        self.assertEqual(
            pulse_html.cut_gap_sentence(two, 0, 1, "auf dieser Seite", floor=True, unindexed=["21/108"]),
            "In 2 Sitzungen (21/105, 21/108) endet die Protokolldatei vorzeitig; mindestens 1 zu Protokoll gegebene Rede "
            "laut DIP fehlt auf dieser Seite; ob auch Reden fehlen, ist offen, und 21/108 hat DIP noch nicht erfasst.")
        self.assertEqual(
            pulse_html.cut_gap_sentence(["21/105", "21/108"], 0, 0, "auf dieser Seite", floor=True, unindexed=["21/108"]),
            "In 2 Sitzungen (21/105, 21/108) endet die Protokolldatei vorzeitig; wie viele Reden auf dieser Seite fehlen, "
            "ist offen, und 21/108 hat DIP noch nicht erfasst.")

    def test_a_sitting_dip_has_not_indexed_says_so(self):
        self.assertEqual(
            pulse_html.cut_gap_sentence(["21/108"], 0, None, "in Redeanteil und Rangfolge dieser Woche",
                                        scope="dieser Woche", unindexed=["21/108"]),
            "In Sitzung 21/108 endet die Protokolldatei vorzeitig; was fehlt, hat DIP noch nicht erfasst.")
        self.assertEqual(
            pulse_html.cut_gap_sentence(["21/105", "21/108"], 12, None, "in Redeanteil und Rangfolge dieser Woche",
                                        scope="dieser Woche", unindexed=["21/108"]),
            "In 2 Sitzungen dieser Woche (21/105, 21/108) endet die Protokolldatei vorzeitig; 12 Reden laut DIP fehlen "
            "in Redeanteil und Rangfolge dieser Woche, und 21/108 hat DIP noch nicht erfasst.")


def dossier_report(protocol_cut=CUT, aktivitaeten=("present",)):
    report = cut_report(protocol_cut)
    report["protocol"]["xml_header"] = {**report["protocol"].get("xml_header", {}), "start_page": "101"}
    report["api_records"] = {"aktivitaeten": [{"id": "z"}] if aktivitaeten else []}
    return report


class DossierNoteTests(unittest.TestCase):
    # Value: protects=a cut sitting's dossier says where the file stops, how much DIP lists after it, links the PDF
    #   at that page and lists DIP's speakers without making them look like Reden; fails_when=a reader takes the
    #   dossier's Redeanteil or ranking for the whole sitting; why_new=step 7; seam=renderer
    def test_the_note_names_the_place_the_counts_the_pdf_page_and_dips_speakers(self):
        html = pulse_html.render_html(dossier_report())
        note = html[html.index('<section class="cut-gap"'):html.index("</section>", html.index('<section class="cut-gap"'))]
        self.assertIn("Protokolldatei endet vorzeitig", note)
        self.assertIn("endet nach der Rede auf Seite 103 B", note)
        self.assertIn("den endgültigen Bericht kündigt sie für den 13.10.2026 an", note)
        self.assertIn("Laut DIP fehlen danach 1 Rede und 1 zu Protokoll gegebene Rede", note)
        self.assertIn('href="https://www.bundestag.de/pp.pdf#page=3"', note)
        self.assertIn("Von DIP genannt, nicht gedruckt (2)", note)
        self.assertIn("<li>Dora Dreher, MdB, Die Linke · S. 104 A</li>", note)
        self.assertIn("<li>Emil Esch, MdB, CDU/CSU · zu Protokoll</li>", note)
        self.assertNotIn("speech-card", note)
        self.assertNotIn("<a href=\"../abgeordnete", note)

    # Value: protects=the link says "ab Seite" only where it opens at that page; fails_when=a head without a readable
    #   start page links the cover and promises the page; why_new=TODOS cut review item 12; seam=renderer
    def test_the_pdf_link_names_a_page_only_where_it_opens_there(self):
        for start_page in (None, "", "S. 101", "200"):
            with self.subTest(start_page=start_page):
                report = dossier_report()
                report["protocol"]["xml_header"]["start_page"] = start_page
                html = pulse_html.render_html(report)
                self.assertIn('<a href="https://www.bundestag.de/pp.pdf">Vollständiges Protokoll als PDF ↗</a>', html)
                self.assertNotIn("Im PDF ab Seite", html)

    def test_a_whole_sitting_has_no_note(self):
        self.assertNotIn("<section class=\"cut-gap\"", pulse_html.render_html(dossier_report(None)))

    def test_unindexed_and_dip_placed_cuts_say_so(self):
        unindexed = {**CUT, "entries": []}
        self.assertIn("DIP hat diese Sitzung noch nicht erfasst; wie viel fehlt, ist offen.",
                      pulse_html.render_html(dossier_report(unindexed, aktivitaeten=())))
        placed = {**CUT, "place_from": "dip"}
        self.assertIn("endet nach der Rede auf Seite 103 B (Seite laut DIP)", pulse_html.render_html(dossier_report(placed)))
        no_quadrant = {**CUT, "quadrant": None}
        self.assertIn("endet nach der Rede auf Seite 103.", pulse_html.render_html(dossier_report(no_quadrant)))

    # Value: protects=a cut whose count is a floor says "mindestens" and why; fails_when=the dossier says "fehlen danach
    #   0 Reden" for a sitting DIP lists more Reden of; why_new=code review of steps 7-10, finding 2; seam=renderer
    def test_unplaced_dip_reden_make_the_count_a_floor(self):
        html = pulse_html.render_html(dossier_report({**CUT, "unplaced_reden": 2}))
        self.assertIn("Laut DIP fehlen danach mindestens 1 Rede und 1 zu Protokoll gegebene Rede; keine Zahl auf dieser Seite "
                      "enthält sie. 2 weitere Reden nennt DIP an der Stelle des Abbruchs, ohne dass sich sagen lässt, ob sie "
                      "davor oder danach liegen.", html)
        self.assertNotIn("mindestens", pulse_html.render_html(dossier_report()))


class PulsWeekSentenceTests(unittest.TestCase):
    # Value: protects=a Puls week holding a cut sitting says its Redeanteil and Rangfolge lack the Reden DIP lists;
    #   fails_when=the week's shares read as complete; why_new=step 7; seam=renderer
    def test_the_week_names_its_cut_sitting(self):
        import io
        from datetime import date
        from test_build_dip_pulse_site import SittingWeekComparisonTests as W
        entries = [W._entry("2026-06-11", "21/83", [W._item(1, [("SPD", 100)])]),
                   W._entry("2026-06-12", "21/84", [W._item(1, [("CDU/CSU", 100)])])]
        for entry in entries:
            entry["report"]["validation_summary"].update({"xml_top_count": 1, "xml_speech_count": 1})
        entries[0]["report"]["validation_summary"]["protocol_cut"] = copy.deepcopy(CUT)
        entries[0]["report"]["api_records"] = {"aktivitaeten": [{"id": "z"}]}
        with mock.patch("sys.stderr", new_callable=io.StringIO):
            html = site.render_front_page(entries, database_href=None, today=date(2026, 9, 15), week=(2026, 24))
        self.assertIn("In Sitzung 21/83 endet die Protokolldatei vorzeitig; 1 Rede laut DIP fehlt in Redeanteil und "
                      "Rangfolge dieser Woche.", html)
        entries[0]["report"]["validation_summary"]["protocol_cut"]["unplaced_reden"] = 1
        with mock.patch("sys.stderr", new_callable=io.StringIO):
            html = site.render_front_page(entries, database_href=None, today=date(2026, 9, 15), week=(2026, 24))
        self.assertIn("In Sitzung 21/83 endet die Protokolldatei vorzeitig; mindestens 1 Rede laut DIP fehlt", html)
        entries[0]["report"]["validation_summary"]["protocol_cut"] = None
        with mock.patch("sys.stderr", new_callable=io.StringIO):
            html = site.render_front_page(entries, database_href=None, today=date(2026, 9, 15), week=(2026, 24))
        self.assertNotIn("Protokolldatei", html)


def week_entry(datum, number, party="SPD", *, protocol_cut=None, indexed=True):
    """A sitting of the Puls week fixtures with one Rede; ``protocol_cut`` marks it cut."""
    from test_build_dip_pulse_site import SittingWeekComparisonTests as W
    entry = W._entry(datum, number, [W._item(1, [(party, 100)])])
    entry["report"]["validation_summary"].update(
        {"xml_top_count": 1, "xml_speech_count": 1, "protocol_cut": copy.deepcopy(protocol_cut)})
    if protocol_cut:
        entry["report"]["api_records"] = {"aktivitaeten": [{"id": "z"}] if indexed else []}
    return entry


def front_page(entries, week):
    with mock.patch("sys.stderr", new_callable=io.StringIO):
        return site.render_front_page(entries, database_href=None, today=date(2026, 9, 15), week=week)


class PulsWeekFloorTests(unittest.TestCase):
    # Value: protects=a week holding a cut sitting DIP has not indexed gives its count of the others as a floor, as
    #   DATA.md and the Daten page do; fails_when=the sentence gives an exact count; why_new=TODOS cut review item 16a;
    #   seam=render_front_page
    def test_an_unindexed_sitting_makes_the_weeks_count_a_floor(self):
        unindexed = {**CUT, "unplaced_reden": None, "entries": []}
        html = front_page([week_entry("2026-06-11", "21/83", protocol_cut=CUT),
                           week_entry("2026-06-12", "21/84", protocol_cut=unindexed, indexed=False)], (2026, 24))
        self.assertIn("In 2 Sitzungen dieser Woche (21/83, 21/84) endet die Protokolldatei vorzeitig; mindestens 1 Rede "
                      "laut DIP fehlt in Redeanteil und Rangfolge dieser Woche, und 21/84 hat DIP noch nicht erfasst.", html)


    # Value: protects=a week holding a cut sitting with Reden DIP lists but cannot place gives its count as a floor;
    #   fails_when=week_cut_note drops the unplaced_reden term and the sentence states an exact count;
    #   why_new=PulsWeekFloorTests covers only the unindexed cause of the floor; seam=none;
    #   no_claim=the Daten page and DATA.md wording (separate renderers)
    def test_unplaced_reden_make_the_weeks_count_a_floor(self):
        html = front_page([week_entry("2026-06-11", "21/83", protocol_cut={**CUT, "unplaced_reden": 2})], (2026, 24))
        self.assertIn("In Sitzung 21/83 endet die Protokolldatei vorzeitig; mindestens 1 Rede laut DIP fehlt in "
                      "Redeanteil und Rangfolge dieser Woche.", html)


class WeekComparisonCutTests(unittest.TestCase):
    """KW 24/2026 against KW 23/2026: the deltas shift by what the earlier week's cut files lack."""

    @staticmethod
    def comparison(entries):
        html = front_page(entries, (2026, 24))
        start = html.index('id="wochenvergleich"')
        return html[start:html.index("</section>", start)]

    @staticmethod
    def note(number):
        return (f'<p class="week-note week-cut">In Sitzung {number} endet die Protokolldatei vorzeitig; 1 Rede laut DIP '
                "fehlt in den Vergleichswerten aus KW 23/2026.</p>")

    # Value: protects=a Wochenvergleich against a week holding a cut sitting names it; fails_when=Redeanteil deltas
    #   shift with no word of it; why_new=TODOS cut review item 11; seam=render_front_page
    def test_the_comparison_names_the_earlier_weeks_cut_sitting(self):
        section = self.comparison([week_entry("2026-06-04", "21/81", protocol_cut=CUT),
                                   week_entry("2026-06-11", "21/83")])
        self.assertIn(self.note("21/81"), section)
        whole = self.comparison([week_entry("2026-06-04", "21/81"), week_entry("2026-06-11", "21/83")])
        self.assertNotIn("Protokolldatei", whole)
        own = self.comparison([week_entry("2026-06-04", "21/81"),
                               week_entry("2026-06-11", "21/83", protocol_cut=CUT)])
        self.assertNotIn("Protokolldatei", own)

    # Value: protects=with unequal sitting counts only the compared weekdays' cuts are named, and with no shared
    #   weekday every cut of the week whose figures stand beside this one's; fails_when=the note names a sitting no
    #   compared figure holds, or drops one it does; why_new=TODOS cut review item 11; seam=render_front_page
    def test_only_the_compared_sittings_are_named(self):
        thursday = week_entry("2026-06-11", "21/83")
        outside = self.comparison([week_entry("2026-06-03", "21/80", protocol_cut=CUT),
                                   week_entry("2026-06-04", "21/81"), thursday])
        self.assertNotIn("Protokolldatei", outside)
        inside = self.comparison([week_entry("2026-06-03", "21/80", protocol_cut=CUT),
                                  week_entry("2026-06-04", "21/81", protocol_cut=CUT), thursday])
        self.assertIn(self.note("21/81"), inside)
        self.assertNotIn("21/80 ", inside.split('week-cut">')[1].split("</p>")[0] + " ")
        no_shared = self.comparison([week_entry("2026-06-02", "21/79", protocol_cut=CUT),
                                     week_entry("2026-06-03", "21/80"), thursday])
        self.assertIn(self.note("21/79"), no_shared)


class PersonPageTests(unittest.TestCase):
    # Value: protects=a person page names the Reden and Reden zu Protokoll DIP lists for that person in cut files,
    #   pooled over every row of the person; fails_when=a person's Reden count reads as complete; why_new=step 7;
    #   seam=store+renderer
    def test_the_store_pools_a_persons_unprinted_rows_and_the_page_says_so(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = pulse_store.connect(Path(tmp.name) / "s.sqlite")
        self.addCleanup(conn.close)
        report = cut_report(copy.deepcopy(CUT))
        report["validation_summary"]["protocol_cut"]["entries"][1]["dip_person_id"] = "8173"
        pulse_store.persist_report(conn, report, None)
        conn.execute("UPDATE mps SET dip_person_id = '8173' WHERE id = (SELECT MIN(id) FROM mps)")
        pulse_store.resolve_unprinted_people(conn)
        conn.commit()
        mps, _ = site.collect_abgeordnete(conn)
        person = next(mp for mp in mps if mp.get("unprinted"))
        self.assertEqual(person["unprinted"], {"rede": 1, "zu_protokoll": 1, "sittings": ["20/999"], "floor": False,
                                               "unindexed": []})
        self.assertIn("In Sitzung 20/999 endet die Protokolldatei vorzeitig; 1 Rede und 1 zu Protokoll gegebene Rede "
                      "laut DIP fehlen auf dieser Seite.", site.render_abgeordnete_detail(person))
        others = [mp for mp in mps if not mp.get("unprinted")]
        self.assertTrue(others)
        self.assertNotIn("Protokolldatei", site.render_abgeordnete_detail(others[0]))
        # A sitting whose cut leaves DIP Reden unplaced: one of them may be this person's, so the count is a floor.
        conn.execute("UPDATE protocols SET xml_cut_unplaced_reden = 1")
        person = next(mp for mp in site.collect_abgeordnete(conn)[0] if mp.get("unprinted"))
        self.assertTrue(person["unprinted"]["floor"])
        self.assertIn("vorzeitig; mindestens 1 Rede und 1 zu Protokoll gegebene Rede laut DIP fehlen",
                      site.render_abgeordnete_detail(person))


    # Value: protects=a page that names unprinted Reden also names every cut sitting of the person's Wahlperioden whose
    #   speakers nobody can tell (unindexed, or unplaced Reden), and calls its count a floor; fails_when=it gives an
    #   exact count while one of those Reden may be the person's; why_new=TODOS cut review item 16b; seam=store+renderer
    def test_a_persons_note_adds_the_open_cut_sittings_of_their_wahlperioden(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = pulse_store.connect(Path(tmp.name) / "s.sqlite")
        self.addCleanup(conn.close)
        report = cut_report(copy.deepcopy(CUT))
        report["validation_summary"]["protocol_cut"]["entries"][1]["dip_person_id"] = "8173"
        pulse_store.persist_report(conn, report, None)
        conn.execute("UPDATE mps SET dip_person_id = '8173' WHERE id = (SELECT MIN(id) FROM mps)")
        pulse_store.resolve_unprinted_people(conn)
        for number, day, unplaced in (("20/998", "2024-05-01", 2), ("20/1000", "2024-06-01", None),
                                      ("20/997", "2024-04-01", 0), ("19/5", "2017-11-21", None)):
            conn.execute(
                "INSERT INTO protocols(id, document_number, date, created_at, updated_at, xml_cut, xml_cut_unplaced_reden) "
                "VALUES (?, ?, ?, 'now', 'now', 1, ?)", (f"pp-{number}", number, day, unplaced))
        conn.commit()
        mps = site.collect_abgeordnete(conn)[0]
        noted = [mp for mp in mps if mp.get("unprinted")]
        self.assertEqual([mp["unprinted"] for mp in noted], [
            {"rede": 1, "zu_protokoll": 1, "sittings": ["20/998", "20/999", "20/1000"], "floor": True,
             "unindexed": ["20/1000"]}])
        self.assertIn("In 3 Sitzungen (20/998, 20/999, 20/1000) endet die Protokolldatei vorzeitig; mindestens 1 Rede und "
                      "mindestens 1 zu Protokoll gegebene Rede laut DIP fehlen auf dieser Seite, und 20/1000 hat DIP noch "
                      "nicht erfasst.", site.render_abgeordnete_detail(noted[0]))
        # A namentliche Abstimmung is a Wahlperiode the person belongs to as well (only MdBs vote).
        voter = conn.execute("SELECT mp_id FROM unprinted_contributions WHERE mp_id IS NOT NULL").fetchone()[0]
        conn.execute("INSERT INTO protocols(id, document_number, date, created_at, updated_at) "
                     "VALUES ('pp-19/9', '19/9', '2017-12-01', 'now', 'now')")
        conn.execute("INSERT INTO votes(id, protocol_id, date, top_link_step, created_at, updated_at) "
                     "VALUES ('v-19', 'pp-19/9', '2017-12-01', 'none', 'now', 'now')")
        conn.execute("INSERT INTO vote_members(vote_id, mp_id, vote) VALUES ('v-19', ?, 'yes')", (voter,))
        voted = next(mp for mp in site.collect_abgeordnete(conn)[0] if mp.get("unprinted"))
        self.assertEqual((voted["unprinted"]["sittings"], voted["unprinted"]["unindexed"]),
                         (["19/5", "20/998", "20/999", "20/1000"], ["19/5", "20/1000"]))
        # data/abgeordnete.json writes these entries whole: the Wahlperiode of a vote is read beside them.
        self.assertEqual(set(voted["votes"][0]), {"vote_id", "vote", "date", "title", "topic", "detail_url"})
        # A person with no unprinted row of their own gets no note (TODOS.md; ADR 0006).
        self.assertTrue(any(mp["speech_count"] and not mp.get("unprinted") for mp in mps))


class CorrectedEndReceiptTests(unittest.TestCase):
    # Value: protects=a Fakt whose sitting end the PDF corrects names both ends and the PDF page, so a reader who
    #   checks the XML is not misled; fails_when=the receipt shows only the corrected end; why_new=step 7 (3b);
    #   seam=renderer
    def test_the_protocol_receipt_names_both_ends(self):
        row = {"metric_id": "laengste-sitzung",
               "citation": {"document_number": "19/55", "sitting_end_corrected": "01:28", "xml_sitting_end": "01:30"},
               "receipts": [{"entity_kind": "protocol", "document_number": "19/55", "position": 0}]}
        with reviewed_end_times.using(reviewed_end_times.load()):
            html = site._render_fact_sources(row, mp_lookup={}, document_numbers={"19/55"}, bill_slugs=set())
        self.assertIn('Ende laut PDF 01:28 Uhr (<a href="https://dserver.bundestag.de/btp/19/19055.pdf#page=214">S. 214 ↗</a>), '
                      "laut Protokolldatei 01:30 Uhr", html)
        # The citation carries both ends from the store.
        conn = StoreTests.store(self)
        with reviewed_end_times.using(reviewed_end_times.check({"entries": [end_entry(xml_end="01:30", end="01:28")]})):
            pulse_store.persist_report(conn, timed_report("01:30"), None)
        conn.row_factory = sqlite3.Row
        citation = site.resolve_fact_citation(conn, facts.REGISTRY_BY_ID["laengste-sitzung"], {
            "receipts": [{"entity_kind": "protocol", "document_number": "20/999", "position": 0}]})
        self.assertEqual((citation["sitzung_end"], citation["sitting_end_corrected"], citation["xml_sitting_end"]),
                         ("01:28", "01:28", "01:30"))
        row["citation"]["sitting_end_corrected"] = None
        self.assertNotIn("Ende laut PDF", site._render_fact_sources(row, mp_lookup={}, document_numbers={"19/55"},
                                                                    bill_slugs=set()))



    # Value: protects=the corrected end stands under the cited sitting's receipt alone, and only on a Fakt whose
    #   metric reads the sitting end; fails_when=one sitting's end and PDF page print under another's receipt;
    #   why_new=TODOS cut review item 13; seam=renderer
    def test_only_the_cited_sittings_receipt_carries_the_corrected_end(self):
        receipts = [{"entity_kind": "protocol", "document_number": number, "position": position}
                    for position, number in enumerate(("19/55", "19/56"))]
        row = {"metric_id": "laengste-sitzung", "receipts": receipts,
               "citation": {"document_number": "19/55", "sitting_end_corrected": "01:28", "xml_sitting_end": "01:30"}}
        render = lambda fact: site._render_fact_sources(fact, mp_lookup={}, document_numbers=set(), bill_slugs=set())
        with reviewed_end_times.using(reviewed_end_times.load()):
            first, second = render(row).split("<li>")[1:]
            self.assertIn("Ende laut PDF 01:28 Uhr", first)
            self.assertNotIn("Ende laut PDF", second)
            self.assertNotIn("Ende laut PDF", render({**row, "metric_id": "laengste-rede"}))

class FaktenWeekGapTests(unittest.TestCase):
    # Value: protects=a Fakten week that posts a Fakt still names the metrics a cut sitting keeps incomplete, with the
    #   gap note; fails_when=2026-W41 shows the längste Sitzung of 21/99 and nothing says its Reden metrics lack data;
    #   why_new=step 7 browser check; seam=renderer
    def test_a_posted_week_lists_its_incomplete_metrics(self):
        base = {"period_kind": "week", "period_key": "2026-W41", "iso_year": 2026, "iso_week": 41, "wahlperiode": 21,
                "receipts": []}
        posted = {**base, "id": 1, "metric_id": "laengste-sitzung", "complete": 1, "publishable": 1, "rank": 1,
                  "value": 967, "withheld": None}
        held = {**base, "id": 2, "metric_id": "laengste-rede", "complete": 0, "publishable": 0, "rank": None,
                "value": None, "withheld": "incomplete", "gap_note": "Sitzung 21/99: Protokolldatei abgebrochen"}
        html = site.render_facts_week("2026-W41", [posted, held], {}, {}, {}, mp_lookup={}, document_numbers=set(),
                                      bill_slugs=set())
        self.assertIn("Nicht vollständig erfasst", html)
        self.assertIn("unvollständig erfasst: Sitzung 21/99: Protokolldatei abgebrochen", html)
        complete = {**held, "complete": 1, "withheld": "below_floor"}
        self.assertNotIn("Nicht vollständig erfasst", site.render_facts_week(
            "2026-W41", [posted, complete], {}, {}, {}, mp_lookup={}, document_numbers=set(), bill_slugs=set()))


if __name__ == "__main__":
    unittest.main()
