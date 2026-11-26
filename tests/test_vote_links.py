"""One vote-link rule (scripts/vote_links.py) for the online run, the replay and
the carry-forward, and its basis in ``agenda_item_votes`` (vote plan part 1, PR B)."""

from __future__ import annotations

import contextlib
import copy
import io
import json
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any

import _support
import protocol_cut
import build_dip_pulse_site as build
import speech_kinds
import validate_dip_protocol as dip
import xml.etree.ElementTree as ET
import persist_dip_pulse_store as pulse_store
import vote_links
from _support import FIXTURES


def item(index: int, heading: str, printed: list[str] = (), linked: list[str] = (), titles: list[str] = (),
         mitberaten: list[str] = (), votes: list[dict] | None = None) -> dict[str, Any]:
    return {
        "index": index, "top_id": f"TOP {index}", "heading": heading,
        "xml_drucksachen": [{"dokumentnummer": number} for number in printed],
        "api": {
            "linked_drucksachen": [{"dokumentnummer": number, "herausgeber": "BT"} for number in linked],
            "positions": [{"titel": title, "mitberaten": [{"titel": other} for other in mitberaten]} for title in titles],
        },
        "votes": votes or [],
    }


def vote(vote_id: str, title: str, *numbers: str) -> dict[str, Any]:
    return {"id": vote_id, "title": title, "document_numbers": list(numbers)}


def report(items: list[dict], votes: list[dict]) -> dict[str, Any]:
    """A sitting whose votes the list page gave in this order, none placed yet."""
    return {"agenda_items": items, "sitting_votes": [],
            "api_records": {"roll_call_vote_candidates": [dict(v) for v in votes], "matched_roll_call_votes": votes}}


ITEMS = [
    item(1, "Beratung des Rentengesetzes", printed=["21/10"], linked=["21/11"]),
    item(2, "Beratung des Heizungsgesetzes", linked=["21/20", "21/21"], titles=["Gebäudeenergiegesetz"],
         mitberaten=["Wärmeplanungsgesetz"]),
    item(3, "Wahl der Bundeskanzlerin", titles=["Kanzlerwahl"]),
    item(4, "Vereinbarte Debatte zur Lage der Landwirtschaft"),
    item(5, "Aktuelle Stunde zur Lage der Landwirtschaft"),
]


class TopLinksTests(unittest.TestCase):
    def links(self, *votes: dict) -> dict[str, dict[int, str]]:
        return {vote_id: link.tops for vote_id, link in vote_links.top_links(copy.deepcopy(ITEMS), votes).items()}

    def test_a_printed_number_is_drucksache_xml_and_wins_over_a_dip_number_of_the_same_top(self) -> None:
        self.assertEqual(self.links(vote("1", "Rente", "21/10", "21/11")), {"1": {0: "drucksache_xml"}})

    def test_a_number_read_off_a_news_site_url_is_not_a_printed_number(self) -> None:
        # A report cached before the host check keeps "21/10" read off a quoted URL
        # (derive.xml_drucksachen drops it, as persist and the dossier do).
        items = copy.deepcopy(ITEMS)
        items[3]["xml_drucksachen"] = [{"dokumentnummer": "21/10", "url": "https://euronews.com/2025/21/10"}]
        items[0]["xml_drucksachen"] = [{"dokumentnummer": "21/10", "url": "https://www.bundestag.de/dokument/21/10"}]
        self.assertEqual(vote_links.top_links(items, [vote("1", "Rente", "21/10")]), {"1": ({0: "drucksache_xml"}, "match")})

    def test_a_number_only_a_dip_vorgang_holds_is_drucksache_vorgang(self) -> None:
        self.assertEqual(self.links(vote("1", "Rente", "21/11")), {"1": {0: "drucksache_vorgang"}})
        # A mitberaten Vorgang's Drucksachen sit in linked_drucksachen like any other.
        self.assertEqual(self.links(vote("2", "Heizung", "21/21")), {"2": {1: "drucksache_vorgang"}})

    def test_a_vote_links_to_every_top_sharing_a_number(self) -> None:
        self.assertEqual(self.links(vote("1", "Omnibus", "21/10", "21/20")),
                         {"1": {0: "drucksache_xml", 1: "drucksache_vorgang"}})

    def test_a_unique_title_links_without_a_shared_number(self) -> None:
        self.assertEqual(self.links(vote("1", "Wahl der Bundeskanzlerin")), {"1": {2: "title"}})
        # Through a DIP position title and a mitberaten one too, and for a vote
        # whose numbers match no TOP.
        self.assertEqual(self.links(vote("2", "Gebäudeenergiegesetz", "21/99")), {"2": {1: "title"}})
        self.assertEqual(self.links(vote("3", "Wärmeplanungsgesetz")), {"3": {1: "title"}})

    def test_an_ambiguous_or_missing_title_links_nowhere(self) -> None:
        self.assertEqual(self.links(vote("1", "zur Lage der Landwirtschaft")), {"1": {}})
        self.assertEqual(self.links(vote("2", "Geschäftsordnungsantrag")), {"2": {}})

    def test_a_shared_number_anywhere_skips_the_title(self) -> None:
        # The title matches TOP 3, but a number matches TOP 1: only the number counts.
        self.assertEqual(self.links(vote("1", "Wahl der Bundeskanzlerin", "21/10")), {"1": {0: "drucksache_xml"}})

    # Value: protects=the links depend on the votes and TOPs, not on list order (checklist class 3); fails_when=the title fallback or a first-match rule reads list order; why_new=the inline rule had no order test; seam=none
    def test_shuffled_votes_give_the_same_links(self) -> None:
        votes = [vote("1", "Rente", "21/10"), vote("2", "Wahl der Bundeskanzlerin"), vote("3", "zur Lage der Landwirtschaft"),
                 vote("4", "Heizung", "21/20", "21/10")]
        expected = self.links(*votes)
        for seed in range(5):
            shuffled = votes[:]
            random.Random(seed).shuffle(shuffled)
            self.assertEqual(self.links(*shuffled), expected)


def top(index: int, heading: str, *, printed: list[str] = (), docs: list[tuple] = (), positions: list[dict] = (),
        pages: tuple[int, int] | None = None, called: list[str] | None = None, speeches: int = 0) -> dict[str, Any]:
    """A TOP as the rule reads it. ``docs`` are (number, vorgang_id[, herausgeber]) DIP links;
    ``positions`` are DIP positions (``position``)."""
    return {
        "index": index, "top_id": f"TOP {index}", "heading": heading,
        "page_range": {"start": {"page": pages[0]}, "end": {"page": pages[1]}} if pages else {},
        "xml_speech_count": speeches,
        "xml_drucksachen": [{"dokumentnummer": number} for number in printed],
        **({"called_drucksachen": list(called)} if called is not None else {}),
        "api": {
            "linked_drucksachen": [{"dokumentnummer": d[0], "vorgang_id": d[1], "herausgeber": d[2] if len(d) > 2 else "BT"}
                                   for d in docs],
            "positions": list(positions),
        },
        "votes": [],
    }


def position(vorgang_id: str, kind: str = "Beratung", *, mitberaten: list[str] = (), pages: tuple[int, int] | None = None,
             title: str = "") -> dict[str, Any]:
    return {"vorgang_id": vorgang_id, "vorgangsposition": kind, "titel": title,
            "mitberaten": [{"id": other, "titel": ""} for other in mitberaten],
            "source": {"anfangsseite": pages[0], "endseite": pages[1]} if pages else {}}


def full_vote(vote_id: str, title: str, *numbers: str, description: str = "") -> dict[str, Any]:
    return {"id": vote_id, "title": title, "description": description, "document_numbers": list(numbers)}


class RuleStepTests(unittest.TestCase):
    """The PR C steps (docs/plans/vote-pr-c.md section 2), each with its guard."""

    def link(self, items: list[dict], one_vote: dict) -> tuple[dict[int, str], str]:
        result = vote_links.top_links(copy.deepcopy(items), [one_vote])[one_vote["id"]]
        return result.tops, result.step

    # B. Procedural motions bring no Drucksachen.
    def test_a_procedural_motion_brings_none_of_the_vorgaenge_it_names(self) -> None:
        motion = top(1, "Zusatzpunkt 12", docs=[("19/1", "v-own"), ("19/50", "v-named")],
                     positions=[position("v-own", "Geschäftsordnungsantrag", mitberaten=["v-named"])])
        debate = top(2, "Antrag zum Klimaschutz", docs=[("19/50", "v-named")], positions=[position("v-named")])
        self.assertEqual(self.link([motion, debate], full_vote("1", "Klima", "19/50")), ({1: "drucksache_vorgang"}, "match"))
        # The TOP keeps its own position's Vorgang.
        self.assertEqual(self.link([motion, debate], full_vote("2", "Antrag", "19/1")), ({0: "drucksache_vorgang"}, "match"))
        other = top(1, "Zusatzpunkt 12", docs=[("19/50", "v-named")],
                    positions=[position("v-own", "Antrag zur Geschäftsordnung", mitberaten=["v-named"])])
        self.assertEqual(self.link([other, debate], full_vote("3", "Klima", "19/50")), ({1: "drucksache_vorgang"}, "match"))

    def test_a_section_62_report_keeps_its_mitberaten(self) -> None:
        report_top = top(1, "Bericht gemäß § 62", docs=[("19/50", "v-named")],
                         positions=[position("v-own", "Beratung über Bericht gemäß § 62 Abs. 2 Geschäftsordnung BT",
                                             mitberaten=["v-named"])])
        self.assertEqual(self.link([report_top], full_vote("1", "Gesetz", "19/50")), ({0: "drucksache_vorgang"}, "match"))

    def test_a_bundesrat_number_is_no_shared_number(self) -> None:
        items = [top(1, "Beratung A", docs=[("19/50", "v", "BR")]), top(2, "Beratung B", printed=["19/50"])]
        self.assertEqual(self.link(items, full_vote("1", "x", "19/50")), ({1: "drucksache_xml"}, "match"))

    def test_numbers_compare_without_leading_zeros(self) -> None:
        items = [top(1, "Beratung A", printed=["20/0301"]), top(2, "Beratung B", docs=[("20/0302", "v")])]
        self.assertEqual(self.link(items, full_vote("1", "x", "20/301")), ({0: "drucksache_xml"}, "match"))
        self.assertEqual(self.link(items, full_vote("2", "x", "20/00302")), ({1: "drucksache_vorgang"}, "match"))

    # Step 2 (D). The section where the chair calls the vote.
    def joint(self, **section: Any) -> list[dict]:
        return [top(1, "Beratung der Anträge A und B", docs=[("18/10", "a"), ("18/11", "b")], speeches=6),
                top(2, "", **{"called": ["18/11"], **section})]

    def test_the_headingless_section_the_chair_names_takes_the_vote(self) -> None:
        self.assertEqual(self.link(self.joint(), full_vote("1", "Antrag B", "18/11")), ({1: "drucksache_call"}, "call"))
        # A vote the section does not name stays on the joint debate.
        self.assertEqual(self.link(self.joint(), full_vote("2", "Antrag A", "18/10")), ({0: "drucksache_vorgang"}, "match"))

    def test_a_section_with_a_rede_does_not_take_the_vote(self) -> None:
        # A section that gains a Rede (a re-parse that wraps a turn in a Rede) stops taking it.
        self.assertEqual(self.link(self.joint(speeches=1), full_vote("1", "Antrag B", "18/11")),
                         ({0: "drucksache_vorgang"}, "match"))
        items = self.joint()
        items[1]["heading"] = "Abstimmung über den Antrag B"
        self.assertEqual(self.link(items, full_vote("1", "Antrag B", "18/11")), ({0: "drucksache_vorgang"}, "match"))

    def test_two_sections_naming_the_vote_take_none(self) -> None:
        items = [*self.joint(), top(3, "", called=["18/11"])]
        self.assertEqual(self.link(items, full_vote("1", "Antrag B", "18/11")), ({0: "drucksache_vorgang"}, "match"))

    def test_the_chair_text_yields_bundestag_numbers_only(self) -> None:
        self.assertEqual(vote_links.chair_numbers(
            "Abstimmung über den Antrag auf Drucksache 18/12639. Bundesrat Drucksache 447/26 und Drucksachen 18/1, 18/02 und 18/3"),
            ["18/12639", "18/1", "18/02", "18/3"])
        self.assertEqual(vote_links.chair_numbers("Drucksache 447/26; Drucksache 118/1234; ohne Drucksache"), [])

    def test_the_chair_text_scan_is_linear(self) -> None:
        import time
        hostile = "Drucksachen " + "18/1 , und , sowie " * 20000 + "x"
        started = time.perf_counter()
        vote_links.chair_numbers(hostile)
        vote_links.chair_numbers("Drucksache " + "1" * 50000)
        vote_links.einzelplan_numbers("Einzelplan " * 50000 + "1")
        vote_links._third_reading("–" * 100000 + " x")
        vote_links._third_reading("I " * 50000 + "Dritte")
        self.assertLess(time.perf_counter() - started, 2.0)  # gstack-timing-ok: a backtracking regex takes minutes here

    # Step 3 (A1). The Einzelplan.
    def budget(self, *, extra: list[dict] = ()) -> list[dict]:
        return [top(1, "Zweite Beratung des Haushaltsgesetzes 2019", docs=[("19/1", "h")]),
                top(2, "Einzelplan 04 Bundeskanzlerin und Bundeskanzleramt"),
                top(3, "Einzelplan 14 Bundesministerium der Verteidigung", docs=[("19/1", "h")]),
                *extra]

    def test_one_einzelplan_moves_the_vote_to_its_section(self) -> None:
        text = "Haushaltsgesetz 2019, Einzelplan 4, Geschäftsbereich der Bundeskanzlerin, zweiten Beratung"
        self.assertEqual(self.link(self.budget(), full_vote("1", "Bundeskanzleramt", "19/1", description=text)),
                         ({1: "einzelplan"}, "einzelplan"))
        # A vote with no TOP today is placed too.
        self.assertEqual(self.link(self.budget(), full_vote("2", "Geschäftsbereich der Bundeskanzlerin", description=text)),
                         ({1: "einzelplan"}, "einzelplan"))

    def test_the_third_reading_and_an_entschliessungsantrag_stay(self) -> None:
        third = "Haushaltsgesetz 2019, Einzelplan 14, dritten Beratung"
        self.assertEqual(self.link(self.budget(), full_vote("1", "Haushalt", "19/1", description=third)),
                         ({0: "drucksache_vorgang", 2: "drucksache_vorgang"}, "match"))
        motion = "Entschließungsantrag der Fraktion X zu der zweiten Beratung, Einzelplan 14"
        self.assertEqual(self.link(self.budget(), full_vote("2", "Haushalt", "19/1", description=motion)),
                         ({0: "drucksache_vorgang", 2: "drucksache_vorgang"}, "match"))

    def test_two_einzelplaene_or_two_sections_move_nothing(self) -> None:
        two = "Einzelplan 04 und Einzelplan 14, zweiten Beratung"
        self.assertEqual(self.link(self.budget(), full_vote("1", "Ausgaben", description=two)), ({}, "none"))
        twice = self.budget(extra=[top(4, "Einzelplan 04 Bundeskanzleramt (Fortsetzung)")])
        self.assertEqual(self.link(twice, full_vote("2", "Ausgaben", description="Einzelplan 04")), ({}, "none"))

    def test_an_einzelplan_vote_already_on_its_section_is_a_plain_match(self) -> None:
        items = [top(1, "Einzelplan 04 Bundeskanzleramt", printed=["19/4"]), top(2, "Einzelplan 14", printed=["19/5"])]
        self.assertEqual(self.link(items, full_vote("1", "Haushalt", "19/4", description="Einzelplan 04")),
                         ({0: "einzelplan"}, "match"))

    # Step 4 (A2). Drop the umbrella.
    def test_a_top_whose_shared_numbers_another_holds_is_dropped(self) -> None:
        items = [top(1, "Haushaltsgesetz", docs=[("19/1", "h")]), top(2, "Einzelplan 60", docs=[("19/1", "h"), ("19/2", "e")])]
        self.assertEqual(self.link(items, full_vote("1", "Haushalt", "19/1", "19/2")), ({1: "drucksache_vorgang"}, "narrowed"))

    def test_equal_shared_sets_are_both_kept(self) -> None:
        items = [top(1, "Beratung A", docs=[("19/1", "h")]), top(2, "Beratung B", docs=[("19/1", "h")])]
        self.assertEqual(self.link(items, full_vote("1", "x", "19/1")),
                         ({0: "drucksache_vorgang", 1: "drucksache_vorgang"}, "match"))

    def test_only_the_top_another_contains_is_dropped(self) -> None:
        # X {a, b} lies inside Y {a, b, c}; Z {c, d} lies inside nothing.
        items = [top(1, "X", docs=[("19/1", "a"), ("19/2", "b")]),
                 top(2, "Y", docs=[("19/1", "a"), ("19/2", "b"), ("19/3", "c")]),
                 top(3, "Z", docs=[("19/3", "c"), ("19/4", "d")])]
        self.assertEqual(self.link(items, full_vote("1", "x", "19/1", "19/2", "19/3", "19/4")),
                         ({1: "drucksache_vorgang", 2: "drucksache_vorgang"}, "narrowed"))

    # Step 5 (C). Drop the neighbour.
    def neighbours(self, *, printed: list[str] = ()) -> list[dict]:
        mission = position("minusma", pages=(3725, 3733))
        return [top(1, "MINUSMA", docs=[("18/9", "minusma")], positions=[mission], pages=(3725, 3732)),
                top(2, "Bundeswehr Irak", docs=[("18/9", "minusma")], positions=[mission], pages=(3733, 3740), printed=printed)]

    def test_a_top_the_position_touches_on_one_page_only_is_dropped(self) -> None:
        self.assertEqual(self.link(self.neighbours(), full_vote("1", "MINUSMA", "18/9")), ({0: "drucksache_vorgang"}, "narrowed"))

    def test_a_printed_number_keeps_the_boundary_top(self) -> None:
        self.assertEqual(self.link(self.neighbours(printed=["18/9"]), full_vote("1", "MINUSMA", "18/9")),
                         ({0: "drucksache_vorgang", 1: "drucksache_xml"}, "match"))

    # Step 6 (A3). The third reading.
    def test_the_heading_that_begins_with_dritte_beratung_is_kept(self) -> None:
        items = [top(1, "Zweite Beratung des Haushaltsgesetzes", docs=[("21/1", "h")]),
                 top(2, "a) Dritte Beratung des Haushaltsgesetzes", docs=[("21/1", "h")]),
                 top(3, "Zweite und dritte Beratung des Begleitgesetzes", docs=[("21/1", "h")])]
        self.assertEqual(self.link(items, full_vote("1", "Haushalt", "21/1")), ({1: "drucksache_vorgang"}, "narrowed"))
        items[1]["heading"] = "– Dritte Beratung"
        self.assertEqual(self.link(items, full_vote("1", "Haushalt", "21/1"))[0], {1: "drucksache_vorgang"})
        items[1]["heading"] = "Zweite und dritte Beratung des Haushaltsgesetzes"
        self.assertEqual(self.link(items, full_vote("1", "Haushalt", "21/1"))[1], "match")

    # Value: protects=every step looks only at the vote and its sitting, so the links do not depend on list order (checklist class 3); fails_when=a step reads the first match or the order of TOPs or votes; why_new=PR C adds five steps; seam=none
    def test_shuffled_votes_give_the_same_links_through_every_step(self) -> None:
        items = [*self.budget(), *self.joint(), *self.neighbours()]
        votes = [full_vote("e", "Haushalt", "19/1", description="Einzelplan 04"), full_vote("c", "B", "18/11"),
                 full_vote("n", "MINUSMA", "18/9"), full_vote("m", "A", "18/10"), full_vote("u", "x", "19/1")]
        expected = vote_links.top_links(copy.deepcopy(items), votes)
        self.assertEqual({v: link.step for v, link in expected.items()},
                         {"e": "einzelplan", "c": "call", "n": "narrowed", "m": "match", "u": "match"})
        for seed in range(5):
            shuffled = votes[:]
            random.Random(seed).shuffle(shuffled)
            self.assertEqual(vote_links.top_links(copy.deepcopy(items), shuffled), expected)


class CalledDrucksachenParseTests(unittest.TestCase):
    """The parse field step 2 reads (docs/plans/vote-pr-c.md section 6)."""

    def sections(self) -> dict[str, ET.Element]:
        root = ET.parse(FIXTURES / "vote_links" / "chair-sections.xml").getroot()
        return {top.get("sitting"): top for top in root}

    def test_the_chair_section_of_18_237_names_its_drucksache(self) -> None:
        zp10 = self.sections()["18/237"]
        self.assertEqual(dip.called_drucksachen(zp10, heading="", speech_count=0), ["18/12639"])

    def test_a_section_with_reden_or_a_heading_stays_empty(self) -> None:
        # 19/197's headingless section filed under "Einzelplan 20" holds 15 Reden and names 19/24969.
        section = self.sections()["19/197"]
        self.assertEqual(dip.called_drucksachen(section, heading="", speech_count=15), [])
        self.assertEqual(dip.called_drucksachen(section, heading="", speech_count=0), ["19/24969"])
        self.assertEqual(dip.called_drucksachen(self.sections()["18/237"], heading="Zusatzpunkt 10", speech_count=0), [])

    def parsed(self) -> dict[str, Any]:
        xml = (FIXTURES / "protocol.xml").read_text(encoding="utf-8").replace(
            "  </sitzungsverlauf>",
            '    <tagesordnungspunkt top-id="Zusatzpunkt 3">\n      <p klasse="J">Zusatzpunkt 3. Abstimmung über den Antrag '
            'auf Drucksache 20/0777. <a href="https://dserver.bundestag.de/btd/20/001/2000124.pdf">20/124</a></p>\n'
            "    </tagesordnungspunkt>\n  </sitzungsverlauf>")
        return dip.parse_protocol_xml(xml)

    def test_the_parse_fills_the_field_for_every_item(self) -> None:
        parsed = self.parsed()
        fields = [dip.xml_top_fields(top) for top in parsed["agenda_items"]]
        self.assertEqual([item["called_drucksachen"] for item in fields], [[], [], ["20/0777"]])
        # The chair's numbers stay out of the printed Drucksachen.
        self.assertEqual([d["dokumentnummer"] for d in fields[2]["xml_drucksachen"]], ["20/124"])

    def test_the_parse_stamps_the_vote_inputs_version(self) -> None:
        summary = dip.contribution_summary(self.parsed()["agenda_items"])
        self.assertEqual(summary["vote_inputs_version"], vote_links.INPUTS_VERSION)


class VoteInputsStaleTests(unittest.TestCase):
    # Value: protects=a report parsed before the rule read called_drucksachen is re-read from its XML (cause "votes"), so step 2 never runs on a field the cached JSON lacks; fails_when=stale_causes ignores vote_inputs_version; why_new=PR C adds a parse field without a speech-rule bump (plan section 7); seam=stale_causes
    def test_a_report_without_the_vote_inputs_version_is_stale_for_votes(self) -> None:
        protocol = {"dokumentnummer": "21/7", "xml_url": "https://example.test/21-7.xml"}
        current = {"speech_kinds_version": speech_kinds.VERSION, "cut_rule_version": protocol_cut.CUT_RULE_VERSION, "protocol_cut": None, "vote_inputs_version": vote_links.INPUTS_VERSION}
        fresh = _support.stamp_reviewed({"protocol": dict(protocol), "validation_summary": dict(current)})
        self.assertEqual(build.stale_causes(fresh), ())
        old = _support.stamp_reviewed({"protocol": dict(protocol), "validation_summary": {**current, "vote_inputs_version": None}})
        self.assertEqual(build.stale_causes(old), ("votes",))
        with self.assertRaises(build.CachedReportError) as caught:
            build.require_parsed_reports([{"report": old}])
        self.assertIn(f"1 predate the current inputs of the vote-link rule ({vote_links.INPUTS_VERSION}) (21/7)", str(caught.exception))
        self.assertNotIn("speech-counting rule", str(caught.exception))


class AttributeVotesTests(unittest.TestCase):
    def test_votes_go_under_their_tops_in_list_order_and_the_rest_to_the_sitting(self) -> None:
        votes = [vote("b", "Rente", "21/10"), vote("a", "Rente 2", "21/11"), vote("c", "Geschäftsordnungsantrag")]
        placed = vote_links.attribute_votes(report(copy.deepcopy(ITEMS), votes))
        self.assertEqual([v["id"] for v in placed["agenda_items"][0]["votes"]], ["b", "a"])
        self.assertEqual([v["id"] for v in placed["sitting_votes"]], ["c"])
        self.assertEqual(vote_links.placement_errors(placed), [])

    def test_a_stale_placement_moves_and_a_kept_copy_stays_the_same_object(self) -> None:
        stale = report(copy.deepcopy(ITEMS), [])
        kept = vote("1", "Rente", "21/10")
        wrong = vote("2", "Kanzlerwahl")
        stale["agenda_items"][0]["votes"] = [kept, wrong]  # 2 belongs under TOP 3 by its title
        self.assertEqual(vote_links.placement_errors(stale), [
            "vote 2 sits under TOP 1, which the rule does not link it to",
            "vote 2 is missing under TOP 3, which the rule links it to",
        ])
        vote_links.attribute_votes(stale)
        self.assertIs(stale["agenda_items"][0]["votes"][0], kept)
        self.assertEqual([v["id"] for v in stale["agenda_items"][0]["votes"]], ["1"])
        self.assertIs(stale["agenda_items"][2]["votes"][0], wrong)

    def test_a_fetched_vote_in_no_top_and_not_in_the_sitting_votes_is_named(self) -> None:
        lost = report(copy.deepcopy(ITEMS), [vote("c", "Geschäftsordnungsantrag")])
        self.assertEqual(vote_links.placement_errors(lost),
                         ["vote c is linked to no TOP and missing from sitting_votes"])
        self.assertEqual(vote_links.placement_errors(vote_links.attribute_votes(lost)), [])

    # Value: protects=persist's gate names a vote that sits in sitting_votes although the rule links it to a TOP (a reader of sitting_votes would show it twice); fails_when=placement_errors checks only what sitting_votes lacks; why_new=TODOS.md "Check that vote links are right" item 9; seam=none
    def test_a_linked_vote_that_also_sits_in_the_sitting_votes_is_named(self) -> None:
        both = report(copy.deepcopy(ITEMS), [])
        both["agenda_items"][0]["votes"] = [vote("1", "Rente", "21/10")]
        both["sitting_votes"] = [vote("1", "Rente", "21/10")]
        self.assertEqual(vote_links.placement_errors(both),
                         ["vote 1 is linked to a TOP and also sits in sitting_votes"])
        self.assertEqual(vote_links.placement_errors(vote_links.attribute_votes(both)), [])

    # Value: protects=one misplaced unlinked vote (held under a TOP, absent from sitting_votes) gives one error, so persist's first three errors cannot hide a third fault; fails_when=placement_errors names it as missing from sitting_votes and as sitting under the TOP; why_new=TODOS.md "Check that vote links are right" item 12; seam=none
    def test_one_misplaced_unlinked_vote_gives_one_error(self) -> None:
        misplaced = report(copy.deepcopy(ITEMS), [])
        misplaced["agenda_items"][0]["votes"] = [vote("c", "Geschäftsordnungsantrag")]
        self.assertEqual(vote_links.placement_errors(misplaced),
                         ["vote c sits under TOP 1, which the rule does not link it to"])

    def test_a_report_without_a_list_keeps_the_order_it_holds(self) -> None:
        carried = report(copy.deepcopy(ITEMS), [])
        carried["api_records"] = {}
        carried["agenda_items"][0]["votes"] = [vote("9", "Rente", "21/10"), vote("10", "Rente 2", "21/10")]
        vote_links.attribute_votes(carried)
        self.assertEqual([v["id"] for v in carried["agenda_items"][0]["votes"]], ["9", "10"])


def fixture_report() -> dict[str, Any]:
    """The fixture sitting: TOP 1 prints 20/123 and links 20/456; its vote 12345 shares 20/123."""
    return json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))


class TextCleanerTests(unittest.TestCase):
    # Value: protects=vote_links reads derive's public text cleaner, not a private name; fails_when=vote_links.py mentions derive._clean again; why_new=TODOS.md "Check that vote links are right" item 13; seam=none
    def test_vote_links_uses_no_private_name_of_derive(self) -> None:
        source = (Path(vote_links.__file__)).read_text(encoding="utf-8")
        self.assertNotIn("derive._", source)
        self.assertEqual(vote_links.norm_title("  Entwurf\xa0eines  Gesetzes! "), "entwurf eines gesetzes")


class PathsTests(unittest.TestCase):
    """Every path that places votes runs the rule (checklist class 1 and 2)."""

    def test_a_replay_without_xml_corrects_a_stale_placement(self) -> None:
        stale = fixture_report()
        moved = stale["agenda_items"][0]["votes"].pop()
        stale["agenda_items"][1]["votes"] = [moved]
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            build.reparse_cached_xml(Path(tmp), [{"report": stale}])
        self.assertEqual([v["id"] for v in stale["agenda_items"][0]["votes"]], ["12345"])
        self.assertEqual(stale["agenda_items"][1]["votes"], [])

    # Value: protects=a re-parse that adds a TOP places a vote under it when the rule links it there (step 2 reads the parse field of the added TOP); fails_when=reparse_cached_xml attributes before the re-parse adds the TOP, or the added TOP lacks called_drucksachen; why_new=TODOS "Check that vote links are right" item 8; seam=none
    def test_a_reparse_that_adds_a_top_places_the_vote_under_it(self) -> None:
        import test_reden_outside_tops as outside

        xml = outside.source("18-49")
        cached = outside.report_before_adoption(xml)  # only "Einzelplan 07"; the re-parse adopts three TOPs before it
        for item in cached["agenda_items"]:
            item["votes"] = []
        budget = vote("v", "Haushaltsgesetz 2015")
        cached["sitting_votes"] = [budget]
        self.assertEqual(vote_links.links(cached)["v"], ({}, "none"))
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            path = build.xml_cache_path(Path(tmp), "18/49")
            path.parent.mkdir(parents=True)
            path.write_text(xml, encoding="utf-8")
            self.assertEqual(build.reparse_cached_xml(Path(tmp), [{"report": cached}]), 1)
        self.assertEqual(cached["agenda_items"][0]["top_id"], "Tagesordnungspunkt 1")
        self.assertEqual([[v["id"] for v in item["votes"]] for item in cached["agenda_items"]], [["v"], [], [], []])
        self.assertEqual(cached["sitting_votes"], [])
        self.assertEqual(vote_links.placement_errors(cached), [])

    # Value: protects=a carried-forward TOP cannot restore a link the rule no longer makes; fails_when=reuse_existing_dossier_enrichments copies previous["votes"] and nothing re-attributes; why_new=checklist class 2 named this path in the plan; seam=none
    def test_the_carry_forward_cannot_restore_a_link_the_rule_no_longer_makes(self) -> None:
        cached = fixture_report()
        fresh = fixture_report()
        fresh["agenda_items"][0]["votes"] = []
        # This run's TOP 1 no longer prints or links the vote's Drucksache.
        fresh["agenda_items"][0]["xml_drucksachen"] = []
        fresh["agenda_items"][0]["api"]["linked_drucksachen"] = []
        build.reuse_existing_dossier_enrichments(fresh, cached, votes=True, profiles=False)
        self.assertEqual(fresh["agenda_items"][0]["votes"], [])
        self.assertEqual([v["id"] for v in fresh["sitting_votes"]], ["12345"])


class CarryForwardRepeatedTopTests(unittest.TestCase):
    # Value: protects=a no-scan run keeps every cached vote of a sitting whose TOP id repeats (20/152 "Tagesordnungspunkt I" twice); fails_when=the carry-forward keys cached TOPs by top_id, so the last occurrence wins and the first one's votes are lost; why_new=TODOS "Check that vote links are right" item 4; seam=none
    def test_the_votes_of_both_occurrences_of_a_top_id_carry_forward(self) -> None:
        def sitting() -> dict[str, Any]:
            first = {**item(1, "Zweite Beratung Haushalt", printed=["20/1"]), "top_id": "Tagesordnungspunkt I"}
            second = {**item(2, "Dritte Beratung Haushalt", printed=["20/2"]), "top_id": "Tagesordnungspunkt I"}
            return {"agenda_items": [first, second], "sitting_votes": [], "api_records": {}}
        cached = sitting()
        cached["agenda_items"][0]["votes"] = [vote("a", "Haushalt", "20/1")]
        cached["agenda_items"][1]["votes"] = [vote("b", "Haushalt", "20/2")]
        fresh = sitting()
        build.reuse_existing_dossier_enrichments(fresh, cached, votes=True, profiles=False)
        self.assertEqual([[v["id"] for v in it["votes"]] for it in fresh["agenda_items"]], [["a"], ["b"]])
        self.assertEqual(fresh["sitting_votes"], [])
        self.assertEqual(vote_links.placement_errors(fresh), [])


class ChokePointTests(unittest.TestCase):
    # Value: protects=a kept report whose cached placement predates the rule persists with the rule's placement instead of stopping the build (deferred item 1); fails_when=rebuild_database_from_entries persists entries as loaded; why_new=PR C changes the rule, and an online run re-reads only stale reports; seam=rebuild_database_from_entries
    def test_a_kept_report_with_an_old_placement_persists_the_rule_s(self) -> None:
        stale = _support.stamp_reviewed(fixture_report())
        stale.setdefault("validation_summary", {})["speech_kinds_version"] = speech_kinds.VERSION
        stale.setdefault("validation_summary", {})["cut_rule_version"] = protocol_cut.CUT_RULE_VERSION
        stale.setdefault("validation_summary", {}).setdefault("protocol_cut", None)
        stale["agenda_items"][1]["votes"] = stale["agenda_items"][0]["votes"]
        stale["agenda_items"][0]["votes"] = []
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            path = Path(tmp) / "pulse.sqlite"
            build.rebuild_database_from_entries(path, [{"report": stale}])
            conn = sqlite3.connect(path)
            try:
                rows = conn.execute("SELECT ai.item_index, aiv.vote_id FROM agenda_item_votes aiv "
                                    "JOIN agenda_items ai ON ai.id = aiv.agenda_item_id").fetchall()
            finally:
                conn.close()
        self.assertEqual(rows, [(1, "12345")])

    # Value: protects=a dossier rendered from the cached JSON without a persist shows the rule's placement, as the store does (plan section 7, item 3); fails_when=load_existing_detail_entries hands on the cached placement; why_new=the offline render without --repersist only warns about stale reports; seam=load_existing_detail_entries
    def test_a_loaded_report_carries_the_rule_s_placement(self) -> None:
        stale = fixture_report()
        stale["agenda_items"][1]["votes"] = stale["agenda_items"][0]["votes"]
        stale["agenda_items"][0]["votes"] = []
        number = stale["protocol"]["dokumentnummer"]
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            data.mkdir()
            (data / f"plenarprotokoll-{number.replace('/', '-')}.json").write_text(json.dumps(stale), encoding="utf-8")
            [entry] = build.load_existing_detail_entries(Path(tmp), [{"dokumentnummer": number}])
        self.assertEqual([[v["id"] for v in it["votes"]] for it in entry["report"]["agenda_items"]], [["12345"], []])


class PersistBasisTests(unittest.TestCase):
    def store(self, built: dict[str, Any]) -> list[tuple]:
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                with conn:
                    pulse_store.persist_report(conn, built)
                return [tuple(row) for row in conn.execute(
                    "SELECT ai.item_index, aiv.vote_id, aiv.basis FROM agenda_item_votes aiv "
                    "JOIN agenda_items ai ON ai.id = aiv.agenda_item_id ORDER BY ai.item_index, aiv.vote_id")]
            finally:
                conn.close()

    def test_each_basis_is_persisted(self) -> None:
        built = fixture_report()
        base = built["agenda_items"][0]["votes"][0]
        built["agenda_items"][0]["votes"].append({**copy.deepcopy(base), "id": "v-dip", "document_numbers": ["20/456"]})
        built["agenda_items"][1]["votes"] = [{**copy.deepcopy(base), "id": "v-title", "document_numbers": [], "title": "Fragestunde"}]
        self.assertEqual(self.store(built), [(1, "12345", "drucksache_xml"), (1, "v-dip", "drucksache_vorgang"),
                                             (2, "v-title", "title")])

    def test_the_deciding_step_is_persisted_per_vote(self) -> None:
        built = fixture_report()
        base = built["agenda_items"][0]["votes"][0]
        built["sitting_votes"] = [{**copy.deepcopy(base), "id": "v-none", "document_numbers": [], "title": "Nichts"}]
        built["agenda_items"][1]["heading"] = "Einzelplan 04 Bundeskanzleramt"
        built["agenda_items"][1]["votes"] = [{**copy.deepcopy(base), "id": "v-plan", "document_numbers": [],
                                              "title": "Haushalt", "description": "Einzelplan 04"}]
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                with conn:
                    pulse_store.persist_report(conn, built)
                steps = dict(conn.execute("SELECT id, top_link_step FROM votes"))
                bases = dict(conn.execute("SELECT vote_id, basis FROM agenda_item_votes"))
            finally:
                conn.close()
        self.assertEqual(steps, {"12345": "match", "v-none": "none", "v-plan": "einzelplan"})
        self.assertEqual(bases, {"12345": "drucksache_xml", "v-plan": "einzelplan"})

    def test_the_step_check_refuses_another_value_and_the_new_bases_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                table = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'agenda_item_votes'").fetchone()[0]
                self.assertIn("'einzelplan', 'drucksache_call'", table)
                with self.assertRaisesRegex(sqlite3.IntegrityError, "CHECK"):
                    conn.execute("INSERT INTO votes(id, top_link_step, created_at, updated_at) VALUES ('v', 'moved', 'x', 'x')")
                # C2's columns exist, empty (docs/plans/vote-pr-c.md section 9).
                self.assertIn("review_note", {row[1] for row in conn.execute("PRAGMA table_info(agenda_item_votes)")})
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM vote_link_reviews").fetchone()[0], 0)
            finally:
                conn.close()

    def test_a_schema_14_store_without_the_step_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                conn.execute("ALTER TABLE votes DROP COLUMN top_link_step")
                with self.assertRaisesRegex(RuntimeError, "Old build-store schema"):
                    pulse_store.require_current_schema(conn)
            finally:
                conn.close()
        self.assertEqual(pulse_store.SCHEMA_VERSION, 16)

    def test_persist_refuses_a_placement_the_rule_does_not_make(self) -> None:
        built = fixture_report()
        built["agenda_items"][1]["votes"] = built["agenda_items"][0]["votes"]
        with self.assertRaisesRegex(ValueError, "vote 12345 sits under .*Fragestunde|vote 12345 sits under"):
            self.store(built)

    def test_a_store_without_the_basis_column_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                conn.execute("ALTER TABLE agenda_item_votes DROP COLUMN basis")
                with self.assertRaisesRegex(RuntimeError, "Old build-store schema"):
                    pulse_store.require_current_schema(conn)
            finally:
                conn.close()

    def test_the_basis_check_refuses_another_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                with self.assertRaisesRegex(sqlite3.IntegrityError, "CHECK"):
                    conn.execute("INSERT INTO agenda_item_votes(agenda_item_id, vote_id, basis) VALUES ('a', 'v', 'placed')")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
