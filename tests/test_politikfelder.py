from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import sqlite3
import tempfile
import time
import unittest
from datetime import date
from pathlib import Path
from typing import Any
from unittest import mock

import _support  # noqa: F401
import build_dip_pulse_site as build
import derive
import persist_dip_pulse_store as pulse_store
import politikfelder as pf
import render_dip_pulse_html as pulse_html
import validate_dip_protocol as dip
from _support import FIXTURES

#: The 28 DIP Sachgebiete (DIP documentation, checked against /vorgang on 2026-10-04).
DIP_SACHGEBIETE = (
    "Arbeit und Beschäftigung",
    "Außenpolitik und internationale Beziehungen",
    "Außenwirtschaft",
    "Bildung und Erziehung",
    "Bundestag",
    "Deutsche Einheit / Innerdeutsche Beziehungen (bis 1990)",
    "Energie",
    "Entwicklungspolitik",
    "Europapolitik und Europäische Union",
    "Gesellschaftspolitik, soziale Gruppen",
    "Gesundheit",
    "Innere Sicherheit",
    "Kultur",
    "Landwirtschaft und Ernährung",
    "Medien, Kommunikation und Informationstechnik",
    "Migration und Aufenthaltsrecht",
    "Politisches Leben, Parteien",
    "Raumordnung, Bau- und Wohnungswesen",
    "Recht",
    "Soziale Sicherung",
    "Sport, Freizeit und Tourismus",
    "Staat und Verwaltung",
    "Umwelt",
    "Verkehr",
    "Verteidigung",
    "Wirtschaft",
    "Wissenschaft, Forschung und Technologie",
    "Öffentliche Finanzen, Steuern und Abgaben",
)

#: Every (Wahlperiode, Einzelplan) pair in the Einzelplan headings of the WP 20 and
#: 21 cache on 2026-10-04.
EINZELPLAENE_IN_THE_CACHE = (
    [("20", n) for n in "01 02 03 04 05 06 07 08 09 10 11 12 14 15 16 17 19 20 21 22 23 25 30 32 60".split()]
    + [("21", n) for n in "01 02 03 04 05 06 07 08 09 10 11 12 14 15 16 17 19 20 21 22 23 24 25 30 32 60".split()]
)


def vorgang(*sachgebiete: str, typ: str = "Gesetzgebung") -> dict[str, Any]:
    """A complete cache record: a vote's Vorgang with an abstract is not refetched (D11); the title labels its block (D12)."""
    return {"sachgebiet": list(sachgebiete), "vorgangstyp": typ, "titel": "Titel", "abstract": "Worum es geht."}


def position(vorgang_id: str, typ: str = "Antrag", *, twins: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "id": f"pos-{vorgang_id}",
        "vorgang_id": vorgang_id,
        "vorgangstyp": typ,
        "vorgangsposition": "Beschlussempfehlung",
        "titel": f"Titel {vorgang_id}",
        "mitberaten": [{"id": twin, "titel": f"Twin {twin}", "vorgangstyp": "Antrag"} for twin in twins],
    }


def item(index: int = 1, *, positions: tuple[dict[str, Any], ...] = (), heading: str = "Beratung", votes=(), numbers=()) -> dict[str, Any]:
    return {
        "index": index,
        "top_id": f"TOP {index}",
        "heading": heading,
        "api": {"positions": list(positions), "linked_drucksachen": []},
        "xml_drucksachen": [{"dokumentnummer": n} for n in numbers],
        "votes": list(votes),
    }


def cache_of(vorgaenge: dict[str, Any] | None = None, numbers: dict[str, list[str]] | None = None) -> dict[str, Any]:
    return {"version": 1, "vorgaenge": vorgaenge or {}, "dokumentnummern": numbers or {}}


class ClosedListTests(unittest.TestCase):
    def test_every_mapped_value_is_in_the_closed_list(self) -> None:
        self.assertEqual(len(pf.POLITIKFELDER), 13)
        self.assertEqual(len(set(pf.POLITIKFELDER)), 13)
        allowed = set(pf.POLITIKFELDER) | {pf.UNTAGGED}
        self.assertLessEqual(set(pf.SACHGEBIET_TO_POLITIKFELD.values()), allowed)
        for key, fields in pf.EINZELPLAN_TO_POLITIKFELDER.items():
            self.assertTrue(fields, key)
            self.assertLessEqual(set(fields), set(pf.POLITIKFELDER), key)
        self.assertEqual(set(pf.ALLOWED_LABELS), allowed)

    def test_all_28_sachgebiete_are_mapped_and_every_field_is_reachable(self) -> None:
        self.assertEqual(len(DIP_SACHGEBIETE), 28)
        self.assertEqual(set(pf.SACHGEBIET_TO_POLITIKFELD), set(DIP_SACHGEBIETE))
        self.assertEqual(set(pf.SACHGEBIET_TO_POLITIKFELD.values()), set(pf.POLITIKFELDER))

    def test_every_einzelplan_pair_of_the_cache_is_mapped(self) -> None:
        for pair in EINZELPLAENE_IN_THE_CACHE:
            self.assertIn(pair, pf.EINZELPLAN_TO_POLITIKFELDER)

    def test_every_einzelplan_of_the_real_store_is_mapped(self) -> None:
        data = Path(__file__).resolve().parent.parent / ".context" / "dip-pulse-site" / "data"
        reports = sorted(data.glob("plenarprotokoll-2*.json"))
        if not reports:
            self.skipTest("no cached store in this checkout")
        seen = set()
        for path in reports:
            report = json.loads(path.read_text(encoding="utf-8"))
            wahlperiode = derive.report_wahlperiode(report)
            for agenda_item in report.get("agenda_items") or []:
                for match in pf._EINZELPLAN_RE.finditer(f"{agenda_item.get('heading') or ''} {agenda_item.get('top_id') or ''}"):
                    seen.add((wahlperiode, match.group(1).zfill(2)))
        self.assertLessEqual(seen, set(pf.EINZELPLAN_TO_POLITIKFELDER))

    def test_an_unknown_sachgebiet_is_skipped_and_reported(self) -> None:
        self.assertEqual(pf.fields_for_sachgebiete(["Gesundheit", "Neues Gebiet", "Recht"]), ["Gesundheit", "Justiz"])
        cache = cache_of({"1": vorgang("Neues Gebiet", "Gesundheit")})
        self.assertEqual(pf.unknown_sachgebiete(cache), {"Neues Gebiet"})


class AgendaItemTests(unittest.TestCase):
    def tags(self, agenda_item: dict[str, Any], cache: dict[str, Any], wahlperiode: str = "21"):
        return pf.tags_for_agenda_item(agenda_item, cache, wahlperiode=wahlperiode)

    def test_lead_vorgang_comes_first_and_the_rest_by_frequency(self) -> None:
        cache = cache_of(
            {
                "lead": vorgang("Wirtschaft", "Umwelt"),
                "a": vorgang("Gesundheit"),
                "b": vorgang("Gesundheit", "Recht"),
                "c": vorgang("Recht"),
                "d": vorgang("Verkehr"),
            }
        )
        # The Antrag comes first in DIP order, the Gesetzgebung Vorgang leads anyway.
        top = item(positions=(position("a"), position("lead", "Gesetzgebung"), position("b"), position("c"), position("d")))
        tags, source = self.tags(top, cache)
        self.assertEqual(source, "sachgebiet")
        # Gesundheit and Recht are each carried by two other Vorgänge: the tie goes to POLITIKFELDER order.
        self.assertEqual(tags, ["Wirtschaft & Finanzen", "Energie & Klima", "Justiz"])

    def test_ties_break_in_closed_list_order_and_the_cap_is_three(self) -> None:
        cache = cache_of({"a": vorgang("Recht"), "b": vorgang("Gesundheit"), "c": vorgang("Verkehr"), "d": vorgang("Bundestag")})
        top = item(positions=(position("a"), position("b"), position("c"), position("d")))
        tags, _ = self.tags(top, cache)
        self.assertEqual(tags, ["Justiz", "Gesundheit", "Verkehr"])
        self.assertLessEqual(len(tags), pf.MAX_TAGS)

    def test_a_mitberaten_twin_counts_as_a_vorgang(self) -> None:
        cache = cache_of({"a": vorgang(), "twin": vorgang("Verteidigung")})
        top = item(positions=(position("a", twins=("twin",)),))
        self.assertEqual(self.tags(top, cache), (["Verteidigung"], "sachgebiet"))

    def test_no_positions_uses_the_drucksache_numbers_of_the_top(self) -> None:
        cache = cache_of({"b": vorgang("Kultur")}, {"21/7": ["b"]})
        top = item(numbers=("21/7",))
        self.assertEqual(self.tags(top, cache), (["Bildung"], "drucksache"))

    def test_numbers_count_only_for_the_sittings_or_the_previous_wahlperiode(self) -> None:
        top = item(heading="Streitsachen 10/21, 1/22, 21/9 und 20/8", numbers=("76/787", "21/3"))
        self.assertEqual(derive.item_document_numbers(top, "21"), ["21/3", "21/9", "20/8"])
        self.assertEqual(derive.item_document_numbers(top, ""), ["76/787", "21/3", "10/21", "1/22", "21/9", "20/8"])

    # Value: protects=tagging takes a TOP's Drucksache numbers by the store's rules: no Bundesrat paper by herausgeber, no XML number off the Bundestag XML host, ASCII digits only, canonical spelling; fails_when=the URL-only /brd/ test, the missing host check, \\d or the raw spelling come back, so a BR paper or a news-URL fragment tags a TOP or one number costs two lookups; why_new=the store applies these rules since v0.19, tagging did not; seam=none
    def test_document_numbers_follow_the_store_rules(self) -> None:
        top = item(heading="Beratung 21/7 und 21/\u0668")
        top["xml_drucksachen"] = [
            {"dokumentnummer": "21/06561", "url": "https://dserver.bundestag.de/btd/21/065/2106561.pdf"},
            {"dokumentnummer": "21/12", "url": "https://www.euronews.com/2021/12/foo"},
            {"dokumentnummer": "21/13"},
        ]
        top["api"]["linked_drucksachen"] = [
            {"dokumentnummer": "21/23", "herausgeber": "BR", "url": "https://dip.bundestag.de/moved.pdf"},
            {"dokumentnummer": "21/24", "herausgeber": "BT", "url": "https://dserver.bundestag.de/btd/21/000/2100024.pdf"},
            {"dokumentnummer": "21/25", "url": "https://dserver.bundestag.de/brd/2025/0025-25.pdf"},
        ]
        self.assertEqual(derive.item_document_numbers(top, "21"), ["21/6561", "21/13", "21/24", "21/7"])
        self.assertTrue(derive.plausible_document_number("21/1", "\u0662\u0661"))  # a non-ASCII Wahlperiode filters nothing
        vote = {"document_numbers": ["21/0042", "21/42", "76/787"]}
        self.assertEqual(pf.vote_document_numbers(vote, "21"), ["21/42"])

    def test_a_bundled_drucksache_ranks_the_vorgang_most_numbers_name(self) -> None:
        cache = cache_of(
            {"x": vorgang("Verkehr"), "y": vorgang("Gesundheit"), "z": vorgang("Recht")},
            {"21/1": ["x", "y", "z"], "21/2": ["y"], "21/3": ["y"]},
        )
        top = item(numbers=("21/1", "21/2", "21/3"))
        self.assertEqual(self.tags(top, cache)[0][0], "Gesundheit")

    def test_einzelplan_by_wahlperiode_and_number(self) -> None:
        cache = cache_of()
        # Einzelplan 12 is Digitales und Verkehr in WP 20 and Verkehr in WP 21.
        top = item(heading="Einzelplan 12 Bundesministerium für Verkehr")
        self.assertEqual(self.tags(top, cache_of(), "20"), (["Verkehr", "Digitales"], "einzelplan"))
        self.assertEqual(self.tags(top, cache, "21"), (["Verkehr"], "einzelplan"))

    def test_the_einzelplan_may_be_only_in_the_top_id(self) -> None:
        top = dict(item(heading=""), top_id="Einzelplan 04")
        self.assertEqual(self.tags(top, cache_of()), (["Staat & Demokratie"], "einzelplan"))

    def test_a_bundled_einzelplan_heading_takes_each_in_order_and_caps_at_three(self) -> None:
        top = item(heading="Einzelplan 06 Inneres b) hier: Einzelplan 07 Justiz und Einzelplan 14")
        tags, source = self.tags(top, cache_of(), "21")
        self.assertEqual(source, "einzelplan")
        self.assertEqual(tags, ["Innere Sicherheit", "Migration", "Justiz"])

    def test_a_dotted_outline_top_id_is_not_an_einzelplan(self) -> None:
        # Report 21/42 item 10: heading names Einzelplan 17, top_id is the outline number 1.7.
        top = dict(item(heading="hier: Einzelplan 17 Bundesministerium für Bildung, Familie"), top_id="Einzelplan 1.7")
        self.assertEqual(self.tags(top, cache_of(), "21"), (["Bildung", "Soziales"], "einzelplan"))
        self.assertEqual(self.tags(dict(item(heading=""), top_id="Einzelplan 1.7"), cache_of(), "21"), ([pf.UNTAGGED], "untagged"))

    def test_an_unknown_einzelplan_pair_is_marked(self) -> None:
        top = item(heading="Einzelplan 99 Neu")
        self.assertEqual(self.tags(top, cache_of()), ([pf.UNTAGGED], "einzelplan_unknown"))
        self.assertEqual(self.tags(item(heading="Einzelplan 06"), cache_of(), "17"), ([pf.UNTAGGED], "einzelplan_unknown"))

    def test_a_fragestunde_is_untagged(self) -> None:
        self.assertEqual(self.tags(item(heading="Fragestunde"), cache_of()), ([pf.UNTAGGED], "untagged"))

    def test_a_cache_miss_is_not_fetched_and_a_fetched_empty_vorgang_is_untagged(self) -> None:
        top = item(positions=(position("a"),))
        self.assertEqual(self.tags(top, cache_of()), ([pf.UNTAGGED], "not_fetched"))
        self.assertEqual(self.tags(top, cache_of({"a": vorgang()})), ([pf.UNTAGGED], "untagged"))
        numbers = item(numbers=("21/7",))
        self.assertEqual(self.tags(numbers, cache_of()), ([pf.UNTAGGED], "not_fetched"))
        self.assertEqual(self.tags(numbers, cache_of(numbers={"21/7": []})), ([pf.UNTAGGED], "untagged"))

    def test_tags_beat_a_missing_entry(self) -> None:
        cache = cache_of({"a": vorgang("Gesundheit")})
        top = item(positions=(position("a"), position("missing")))
        self.assertEqual(self.tags(top, cache), (["Gesundheit"], "sachgebiet"))


class VoteTests(unittest.TestCase):
    def test_own_drucksache_comes_before_the_tops_tags(self) -> None:
        cache = cache_of({"mine": vorgang("Gesundheit")}, {"21/1": ["mine"]})
        vote = {"id": "v", "document_numbers": ["21/1"]}
        top_tags = [(["Verkehr", "Recht"], "sachgebiet")]
        self.assertEqual(pf.tags_for_vote(vote, top_tags, cache), (["Gesundheit"], "drucksache"))

    def test_a_beschlussempfehlung_ranks_its_own_vorgang_among_a_bundle(self) -> None:
        cache = cache_of(
            {"main": vorgang("Verkehr"), "other": vorgang("Recht")},
            {"21/1": ["main"], "21/2": ["main"], "21/3": ["other", "main"]},
        )
        vote = {"document_numbers": ["21/3", "21/1", "21/2"]}
        # 21/3 names two Vorgänge, which is still narrow: `other` counts, `main` (named 3 times) leads.
        self.assertEqual(pf.tags_for_vote(vote, [], cache), (["Verkehr", "Justiz"], "drucksache"))

    def test_without_a_resolvable_drucksache_the_votes_tops_decide(self) -> None:
        cache = cache_of({"x": vorgang()}, {"21/1": ["x"]})
        vote = {"document_numbers": ["21/1"]}
        union = pf.tags_for_vote(vote, [(["Verkehr", "Recht"], "sachgebiet"), (["Recht", "Bildung"], "einzelplan")], cache)
        self.assertEqual(union, (["Verkehr", "Recht", "Bildung"], "top"))

    def test_untagged_tops_give_an_untagged_vote_and_a_miss_gives_not_fetched(self) -> None:
        vote = {"document_numbers": []}
        self.assertEqual(pf.tags_for_vote(vote, [([pf.UNTAGGED], "untagged")], cache_of()), ([pf.UNTAGGED], "untagged"))
        self.assertEqual(pf.tags_for_vote(vote, [], cache_of()), ([pf.UNTAGGED], "untagged"))
        self.assertEqual(pf.tags_for_vote(vote, [([pf.UNTAGGED], "not_fetched")], cache_of()), ([pf.UNTAGGED], "not_fetched"))
        self.assertEqual(pf.tags_for_vote({"document_numbers": ["21/9"]}, [], cache_of()), ([pf.UNTAGGED], "not_fetched"))

    def test_a_vote_under_two_tops_takes_the_union_over_both(self) -> None:
        cache = cache_of({"a": vorgang("Verkehr"), "b": vorgang("Recht")})
        shared = {"id": "v1", "title": "Geteilt", "date": "2026-01-01"}
        report = {
            "protocol": {"dokumentnummer": "21/5"},
            "agenda_items": [
                item(1, positions=(position("a"),), votes=(shared,)),
                item(2, positions=(position("b"),), votes=(shared,)),
            ],
        }
        _, vote_tags = pf.report_politikfelder(report, cache)
        self.assertEqual(vote_tags["v1"], (["Verkehr", "Justiz"], "top"))

    def test_sitting_votes_without_a_top_use_their_own_drucksache(self) -> None:
        cache = cache_of({"a": vorgang("Energie")}, {"21/1": ["a"]})
        report = {"protocol": {"dokumentnummer": "21/5"}, "agenda_items": [], "sitting_votes": [{"id": "s", "document_numbers": ["21/1"]}]}
        _, vote_tags = pf.report_politikfelder(report, cache)
        self.assertEqual(vote_tags["s"], (["Energie & Klima"], "drucksache"))


class VoteNumberTests(unittest.TestCase):
    # Value: protects=a fragment the roll-call scraper read as a Drucksache ("76/787", "2/3") is neither looked up nor allowed to outrank the TOP's tags; fails_when=vote numbers are used unfiltered, so a junk number that DIP happens to resolve decides a vote's Politikfelder; why_new=the TOP path filtered numbers by Wahlperiode, the vote path did not; seam=none
    def test_a_vote_ignores_numbers_of_another_wahlperiode(self) -> None:
        cache = cache_of({"junk": vorgang("Kultur"), "real": vorgang("Verkehr")}, {"76/787": ["junk"], "20/5": ["real"]})
        vote = {"document_numbers": ["76/787", "20/5", "2/3"]}
        self.assertEqual(pf.vote_document_numbers(vote, "20"), ["20/5"])
        self.assertEqual(pf.tags_for_vote(vote, [], cache, wahlperiode="20"), (["Verkehr"], "drucksache"))
        report = {"protocol": {"dokumentnummer": "20/9"}, "agenda_items": [], "sitting_votes": [dict(vote, id="v")]}
        self.assertEqual(pf.fetch_targets([report], cache_of({"real": vorgang("Verkehr")}, {"20/5": ["real"]})), ([], []))

    # Value: protects=a vote's specific Drucksache decides its tags and a Sammelübersicht with dozens of Vorgänge decides nothing; fails_when=every number counts alike, so the 20/195 Terrorismusbekämpfung bill gets Migration and Außenpolitik from its bundled Beschlussempfehlung; why_new=the ranking tests never mixed a specific number with a bundle; seam=none
    def test_a_specific_number_beats_a_bundle_and_a_huge_fanout_is_ignored(self) -> None:
        many = [f"w{i}" for i in range(pf.MAX_NUMBER_FANOUT + 1)]
        cache = cache_of(
            {"gesetz": vorgang("Innere Sicherheit"), "b": vorgang("Migration und Aufenthaltsrecht"), "c": vorgang("Außenpolitik und internationale Beziehungen"),
             **{w: vorgang("Verteidigung") for w in many}},
            {"20/12806": ["gesetz"], "20/13413": ["gesetz", "b", "c"], "20/1": many},
        )
        self.assertEqual(pf.tags_for_vote({"document_numbers": ["20/12806", "20/13413"]}, [], cache),
                         (["Innere Sicherheit"], "drucksache"))
        # Only bundles: all with a fan-out up to the cap count, the huge one does not.
        self.assertEqual(pf.tags_for_vote({"document_numbers": ["20/13413", "20/1"]}, [], cache)[0],
                         ["Innere Sicherheit", "Migration", "Außenpolitik"])
        self.assertEqual(pf.tags_for_vote({"document_numbers": ["20/1"]}, [], cache), ([pf.UNTAGGED], "untagged"))

    # Value: protects=a TOP's Antrag that names two Vorgänge (the Antrag and the EU paper it comments on) is not outvoted by a later single-Vorgang number; fails_when=numbers are tiered for TOPs as they are for votes, so the heading's lead subject is dropped; why_new=the TOP path only had bundle tests; seam=none
    def test_a_tops_numbers_all_count_whatever_their_fanout_up_to_the_cap(self) -> None:
        cache = cache_of(
            {"u1": vorgang("Umwelt"), "u2": vorgang("Recht"), "s": vorgang("Gesundheit")},
            {"21/3835": ["u1", "u2"], "21/772": ["s"]},
        )
        top = item(numbers=("21/3835", "21/772"))
        tags, source = pf.tags_for_agenda_item(top, cache, wahlperiode="21")
        self.assertEqual((tags[0], source), ("Energie & Klima", "drucksache"))
        self.assertEqual(set(tags), {"Energie & Klima", "Justiz", "Gesundheit"})

    # Value: protects=a TOP that has Vorgänge of its own but no Sachgebiet is not tagged from the Drucksachen it only cites; fails_when=the fall-through to cited numbers is allowed again, so a Wahlprüfung Sammelübersicht is tagged Bildung and Gesundheit; why_new=no test gave a TOP both own Vorgänge and cited numbers; seam=none
    def test_cited_numbers_do_not_tag_a_top_whose_own_vorgaenge_lack_a_sachgebiet(self) -> None:
        cache = cache_of({"own": vorgang(), "cited": vorgang("Kultur")}, {"20/9": ["cited"]})
        top = item(positions=(position("own"),), numbers=("20/9",))
        self.assertEqual(pf.tags_for_agenda_item(top, cache, wahlperiode="20"), ([pf.UNTAGGED], "untagged"))
        self.assertEqual(pf.tags_for_agenda_item(item(numbers=("20/9",)), cache, wahlperiode="20"), (["Bildung"], "drucksache"))

    # Value: protects=a vote falls through to the next tier when the narrow tier has no Sachgebiet, and a tier that holds the TOP's own Vorgang goes before an unrelated narrow one; fails_when=the first non-empty tier decides regardless, so a Petition without Sachgebiet leaves the vote untagged or an unrelated Antrag outranks the TOP's bundle; why_new=tiers were tested only with one narrow number; seam=none
    def test_a_vote_falls_through_tiers_and_prefers_the_tier_of_its_own_top(self) -> None:
        cache = cache_of(
            {"petition": vorgang(), "mine": vorgang("Gesundheit"), "x": vorgang("Verkehr"), "y": vorgang("Recht"), "unrelated": vorgang("Kultur")},
            {"21/1": ["petition"], "21/2": ["mine", "x", "y"], "21/3": ["unrelated"]},
        )
        self.assertEqual(pf.tags_for_vote({"document_numbers": ["21/1", "21/2"]}, [], cache)[0][0], "Gesundheit")
        vote = {"document_numbers": ["21/3", "21/2"]}
        self.assertEqual(pf.tags_for_vote(vote, [], cache)[0], ["Bildung"])  # narrow tier first, nothing says otherwise
        self.assertEqual(pf.tags_for_vote(vote, [], cache, linked_vorgang_ids=["mine"]), (["Gesundheit"], "drucksache"))

    def test_bundesrat_papers_are_not_looked_up_as_bundestag_numbers(self) -> None:
        top = item(numbers=("20/5",))
        top["api"]["linked_drucksachen"] = [
            {"dokumentnummer": "20/23", "url": "https://dserver.bundestag.de/brd/2023/0020-23.pdf"},
            {"dokumentnummer": "20/6", "url": "https://dserver.bundestag.de/btd/20/000/2000006.pdf"},
        ]
        self.assertEqual(derive.item_document_numbers(top, "20"), ["20/5", "20/6"])

    # Value: protects=a Beschlussempfehlung that names several Vorgänge tags the vote from the Vorgänge of the TOP it sits under, not from DIP's result order; fails_when=the intersection with the TOP's Vorgänge is dropped, so an unrelated Antrag of a Sammelübersicht leads the vote; why_new=bundle ranking was tested only by number counts; seam=none
    def test_a_bundled_number_is_narrowed_to_the_vorgaenge_of_the_votes_top(self) -> None:
        cache = cache_of(
            {"mine": vorgang("Gesundheit"), "other": vorgang("Verteidigung"), "third": vorgang("Kultur")},
            {"21/9": ["other", "mine", "third"]},
        )
        vote = {"document_numbers": ["21/9"]}
        self.assertEqual(pf.tags_for_vote(vote, [], cache), (["Verteidigung", "Gesundheit", "Bildung"], "drucksache"))
        narrowed = pf.tags_for_vote(vote, [], cache, linked_vorgang_ids=["mine"])
        self.assertEqual(narrowed, (["Gesundheit"], "drucksache"))
        # No overlap with the TOP: nothing to narrow by, the plain ranking stands.
        self.assertEqual(pf.tags_for_vote(vote, [], cache, linked_vorgang_ids=["x"])[0][0], "Verteidigung")

    # Value: protects=a Drucksache that DIP had not linked to a Vorgang yet (resolved to []) is asked again on the next online build; fails_when=want_number treats an empty list as resolved, so the vote stays untagged for good; why_new=fetch_targets was tested only for a complete cache; seam=none
    def test_a_number_that_resolved_to_nothing_is_asked_again(self) -> None:
        report = {"protocol": {"dokumentnummer": "21/5"}, "agenda_items": [], "sitting_votes": [{"id": "s", "document_numbers": ["21/8"]}]}
        self.assertEqual(pf.fetch_targets([report], cache_of(numbers={"21/8": []})), ([], ["21/8"]))
        self.assertEqual(pf.fetch_targets([report], cache_of({"d": vorgang("Recht")}, {"21/8": ["d"]})), ([], []))


class VoteContextTests(unittest.TestCase):
    """politikfelder.vote_vorgang_ids: the Vorgänge a vote's "Worum es geht" reads (B4 Slice 2)."""

    # Value: protects=a vote's prose context comes from its narrow numbers only, narrowed to its TOP's Vorgänge when they meet; fails_when=the wide tier (a Beschlussempfehlung bundle) feeds the context, so a vote shows abstracts of Vorgänge it is not about; why_new=B4 adds the helper; seam=none
    def test_only_the_narrow_tier_counts_and_it_is_narrowed_to_the_tops_vorgaenge(self) -> None:
        cache = cache_of(
            {"a": vorgang(), "b": vorgang(), "x": vorgang(), "y": vorgang(), "z": vorgang()},
            {"21/1": ["a", "b"], "21/2": ["x", "y", "z"]},
        )
        vote = {"document_numbers": ["21/1", "21/2"]}
        self.assertEqual(pf.vote_vorgang_ids(vote, cache), (["a", "b"], "resolved"))
        self.assertEqual(pf.vote_vorgang_ids(vote, cache, linked_vorgang_ids=["b"]), (["b"], "resolved"))
        # The TOP's Vorgang is only in the wide tier: nothing to narrow by, and the wide tier is never prose.
        self.assertEqual(pf.vote_vorgang_ids(vote, cache, linked_vorgang_ids=["z"]), (["a", "b"], "resolved"))
        self.assertEqual(pf.vote_vorgang_ids({"document_numbers": ["21/2"]}, cache), ([], "none"))

    # Value: protects=the export tells "no Vorgang" from "not fetched" (D7) by one fixed precedence; fails_when=a cache miss is stored as none, so a fetch outage reads as "DIP has no description"; why_new=votes.context_state is new; seam=none
    def test_the_state_is_resolved_then_not_fetched_then_none(self) -> None:
        cache = cache_of({"a": vorgang()}, {"21/1": ["a"], "21/2": ["a", "gone"], "21/3": []})
        self.assertEqual(pf.vote_vorgang_ids({"document_numbers": ["21/1"]}, cache), (["a"], "resolved"))
        # Another of the vote's numbers is not in the cache: the ids stay, the answer is not_fetched.
        self.assertEqual(pf.vote_vorgang_ids({"document_numbers": ["21/1", "21/9"]}, cache), (["a"], "not_fetched"))
        # A resolved Vorgang without a cached record: the ids stay, the answer is not_fetched (D7).
        self.assertEqual(pf.vote_vorgang_ids({"document_numbers": ["21/2"]}, cache), (["a", "gone"], "not_fetched"))
        self.assertEqual(pf.vote_vorgang_ids({"document_numbers": ["21/9"]}, cache), ([], "not_fetched"))
        self.assertEqual(pf.vote_vorgang_ids({"document_numbers": ["21/3"]}, cache), ([], "none"))
        self.assertEqual(pf.vote_vorgang_ids({"document_numbers": []}, cache), ([], "none"))
        # A number of another Wahlperiode is not the vote's, so it is neither looked up nor missing.
        self.assertEqual(pf.vote_vorgang_ids({"document_numbers": ["76/787"]}, cache, wahlperiode="21"), ([], "none"))
        self.assertEqual(set(pf.CONTEXT_STATES), {"resolved", "none", "not_fetched"})

    # Value: protects=D8: where a vote's tags come from the narrow tier, tags and context read the same Vorgänge; fails_when=vote_vorgang_ids narrows or ranks differently from tags_for_vote; why_new=the two are separate entry points over one tier rule; seam=none
    def test_context_and_narrow_tier_tags_pick_the_same_vorgaenge(self) -> None:
        cache = cache_of(
            {"mine": vorgang("Gesundheit"), "eu": vorgang("Europapolitik und Europäische Union"), "far": vorgang("Kultur")},
            {"21/1": ["mine", "eu"], "21/2": ["mine"], "21/4": ["far", "mine", "eu"]},
        )
        for vote, linked in (
            ({"document_numbers": ["21/1", "21/2", "21/4"]}, ()),
            ({"document_numbers": ["21/1", "21/4"]}, ("eu",)),
        ):
            with self.subTest(vote=vote, linked=linked):
                ids, _ = pf.vote_vorgang_ids(vote, cache, linked_vorgang_ids=linked)
                tags, source = pf.tags_for_vote(vote, [], cache, linked_vorgang_ids=linked)
                self.assertEqual(source, "drucksache")
                self.assertEqual(tags, pf._from_vorgaenge(ids, cache)[0])

    # Value: protects=D13: a vote under two TOPs gets one Vorgang selection, from the union of both TOPs' Vorgänge, like its tags; fails_when=the context is narrowed by one TOP only, so the vote's two panels and vote_proceedings can disagree; why_new=the union lived inside report_politikfelder; seam=none
    def test_a_vote_under_two_tops_is_narrowed_by_the_union_of_both(self) -> None:
        cache = cache_of({"a": vorgang(), "b": vorgang(), "c": vorgang()}, {"21/1": ["a", "c"], "21/2": ["b"]})
        shared = {"id": "v1", "title": "Geteilt", "date": "2026-01-01", "document_numbers": ["21/1", "21/2"]}
        report = {
            "protocol": {"dokumentnummer": "21/5"},
            "agenda_items": [
                item(1, positions=(position("a"),), votes=(shared,)),
                item(2, positions=(position("b"),), votes=(shared,)),
            ],
            "sitting_votes": [{"id": "s", "document_numbers": ["21/1"]}],
        }
        self.assertEqual(pf.vote_linked_vorgang_ids(report), {"v1": ["a", "b"]})
        contexts = pf.report_vote_vorgaenge(report, cache)
        self.assertEqual(contexts["v1"], (["a", "b"], "resolved"))
        self.assertEqual(contexts["s"], (["a", "c"], "resolved"))  # a sitting-level vote has no TOP to narrow by


class CacheFileTests(unittest.TestCase):
    def test_absent_file_is_an_empty_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(pf.load_cache(tmp), pf.empty_cache())

    def test_corrupt_or_misshapen_json_warns_and_is_treated_as_empty(self) -> None:
        for text in ("{not json", json.dumps({"vorgaenge": []}), json.dumps({"vorgaenge": {}}), "[]"):
            with tempfile.TemporaryDirectory() as tmp:
                path = pf.cache_path(tmp)
                path.parent.mkdir(parents=True)
                path.write_text(text, encoding="utf-8")
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    cache = pf.load_cache(tmp)
                self.assertEqual(cache, pf.empty_cache(), text)
                self.assertIn("warning", err.getvalue())

    # Value: protects=a cache entry of the wrong shape is dropped as a cache miss instead of crashing the build, and an unreadable file is kept for inspection; fails_when=load_cache trusts the values or overwrites the corrupt file; why_new=only the top-level shape was checked; seam=none
    def test_wrong_shaped_entries_are_dropped_and_a_corrupt_file_is_kept(self) -> None:
        good = {"sachgebiet": ["Recht"]}
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp) / "site"
            path = pf.cache_path(tmp)
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"vorgaenge": {"1": good, "2": ["x"], "3": None}, "dokumentnummern": {"21/1": ["1"], "21/2": "12", "21/3": None}}), encoding="utf-8")
            self.assertEqual(pf.load_cache(tmp), cache_of({"1": good}, {"21/1": ["1"]}))
            path.write_text("{broken", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(pf.load_cache(tmp), pf.empty_cache())
            self.assertFalse(path.exists())
            # Kept for inspection in the private directory, not in the published data/.
            kept, = (tmp.parent / ".site.private").glob(path.name + ".*.corrupt")
            self.assertEqual(kept.read_text(encoding="utf-8"), "{broken")
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()), [])

    def test_a_record_with_a_non_list_sachgebiet_is_dropped_and_the_saved_file_is_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            pf.save_cache(site, cache_of({"1": {"sachgebiet": "Verkehr"}, "2": {"sachgebiet": ["Recht"]}}))
            path = pf.cache_path(site)
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()), [path.name])  # no temp left behind
            self.assertEqual(list(pf.load_cache(site)["vorgaenge"]), ["2"])

    # Value: protects=a save killed before its rename leaves its temp file in the private directory beside the site, never in the published data/; fails_when=save_cache stages the temp next to the cache again; why_new=the other test only sees the cleanup path, which deletes the temp either way; seam=none; no_claim=a real SIGKILL (simulated by a cleanup that does nothing)
    def test_a_killed_save_leaves_nothing_in_the_published_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            with mock.patch.object(pf.os, "fsync", side_effect=KeyboardInterrupt), mock.patch.object(Path, "unlink"):
                with self.assertRaises(KeyboardInterrupt):
                    pf.save_cache(site, cache_of({"1": vorgang("Recht")}))
            self.assertEqual(sorted(p.name for p in site.rglob("*") if p.is_file()), [])
            leftovers = list((Path(tmp) / ".site.private").glob(".dip-vorgang-cache.json.*.tmp"))
            self.assertEqual(len(leftovers), 1)

    # Value: protects=a cache written with a leading-zero number keeps its answer under the canonical key the lookups use, and a missing cache says so; fails_when=load_cache keeps raw keys, so "21/06561" is a miss (not_fetched offline, a refetch online), or the absent file is silent; why_new=numbers were not canonical before the review fix; seam=none
    def test_number_keys_are_canonical_and_an_absent_cache_is_named(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(pf.load_cache(site), pf.empty_cache())
            self.assertIn("no Vorgang cache", err.getvalue())
            path = pf.cache_path(site)
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(cache_of({}, {"21/06561": ["v"], "21/7": []})), encoding="utf-8")
            self.assertEqual(pf.load_cache(site)["dokumentnummern"], {"21/6561": ["v"], "21/7": []})

    # Value: protects=a private directory on another file system or one that cannot be made (a read-only parent of OUTPUT) still lets the cache save, staged next to the cache; fails_when=the st_dev check or the OSError fallback goes, so the rename fails across devices or every build loses its fetch; why_new=only same-file-system staging was tested; seam=none; no_claim=a real second device (st_dev is patched)
    def test_save_falls_back_to_data_on_another_file_system_or_a_read_only_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            real_stat = Path.stat

            def other_device(self, *args, **kwargs):
                st = real_stat(self, *args, **kwargs)
                if not self.name.endswith(".private"):
                    return st
                return os.stat_result((st.st_mode, st.st_ino, st.st_dev + 1, *tuple(st)[3:]))

            with mock.patch.object(Path, "stat", other_device), mock.patch.object(pf.os, "fsync", side_effect=KeyboardInterrupt), mock.patch.object(Path, "unlink"):
                with self.assertRaises(KeyboardInterrupt):
                    pf.save_cache(site, cache_of({"1": vorgang("Recht")}))
            self.assertEqual(len(list((site / "data").glob(".dip-vorgang-cache.json.*.tmp"))), 1)  # staged beside the cache

        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp) / "ro"
            site = parent / "site"
            (site / "data").mkdir(parents=True)
            parent.chmod(0o555)
            try:
                pf.save_cache(site, cache_of({"1": vorgang("Recht")}))
            finally:
                parent.chmod(0o755)
            self.assertEqual(list(pf.load_cache(site)["vorgaenge"]), ["1"])
            self.assertFalse((parent / ".site.private").exists())

    # Value: protects=a killed save's temp file in the private directory is swept once it is old, and a running build's young one is left alone; fails_when=the sweep goes (orphans the size of the cache pile up) or ignores the age (a concurrent save loses its file); why_new=the private staging added in this branch had no sweep; seam=none
    def test_old_temp_files_in_the_private_directory_are_swept(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            staging = Path(tmp) / ".site.private"
            staging.mkdir()
            old, young, other = (staging / ".dip-vorgang-cache.json.old.tmp", staging / ".dip-vorgang-cache.json.young.tmp", staging / "bundestag-pulse.sqlite.x.tmp")
            for path in (old, young, other):
                path.write_text("x", encoding="utf-8")
            hours_ago = time.time() - 2 * pf.STALE_TEMP_SECONDS
            os.utime(old, (hours_ago, hours_ago))
            os.utime(other, (hours_ago, hours_ago))
            pf.save_cache(site, cache_of({"1": vorgang("Recht")}))
            self.assertEqual(sorted(p.name for p in staging.iterdir()), sorted([young.name, other.name]))

    # Value: protects=two spellings of one number keep the union of their answers in either key order, and a deeply nested file is treated as unreadable instead of crashing the build; fails_when=the canonical re-key lets the last spelling win (an empty answer erases a real one) or RecursionError escapes load_cache; why_new=canonicalisation and its merge are new in this ship; seam=none
    def test_spellings_merge_and_a_deeply_nested_file_is_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            path = pf.cache_path(site)
            path.parent.mkdir(parents=True)
            for numbers in ({"21/6561": ["1", "2"], "21/06561": []}, {"21/06561": [], "21/6561": ["1", "2"]}, {"21/06561": ["3"], "21/6561": ["1"]}):
                path.write_text(json.dumps(cache_of({}, numbers)), encoding="utf-8")
                merged = pf.load_cache(site)["dokumentnummern"]["21/6561"]
                self.assertEqual(sorted(merged), sorted({i for ids in numbers.values() for i in ids}), numbers)
            path.write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(pf.load_cache(site), pf.empty_cache())
            self.assertIn("unreadable", err.getvalue())

    # Value: protects=a private directory that exists but cannot be written (left by another user) still lets the cache save, next to the cache; fails_when=only mkdir and stat errors fall back, so NamedTemporaryFile raises and every build loses its fetch; why_new=the read-only-parent test makes mkdir fail, not the temp file; seam=none
    def test_save_falls_back_when_the_private_directory_is_not_writable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            private = Path(tmp) / ".site.private"
            private.mkdir(mode=0o500)
            try:
                pf.save_cache(site, cache_of({"1": vorgang("Recht")}))
            finally:
                private.chmod(0o700)
            self.assertEqual(list(pf.load_cache(site)["vorgaenge"]), ["1"])
            self.assertEqual(list(private.iterdir()), [])

    def test_save_then_load_round_trips(self) -> None:
        cache = cache_of({"1": vorgang("Recht")}, {"21/1": ["1"]})
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            pf.save_cache(site, cache)
            self.assertEqual(pf.load_cache(site), cache)

    def test_versions_are_checked_before_v1_fields_without_touching_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            path = pf.cache_path(site)
            path.parent.mkdir(parents=True)
            for version in (2, 0, -1, True, False, "1", None, 1.0, [], {}):
                with self.subTest(version=version):
                    original = json.dumps({"version": version, "records": {}}).encode()
                    path.write_bytes(original)
                    with self.assertRaisesRegex(pf.CacheLoadError, "Unsupported.*compatible code.*version 1"):
                        pf.load_cache(site)
                    self.assertEqual(path.read_bytes(), original)
                    self.assertEqual(list(Path(tmp).rglob("*.corrupt")), [])
            for versioned in (False, True):
                cache = cache_of({"1": vorgang("Recht")})
                if not versioned:
                    del cache["version"]
                path.write_text(json.dumps(cache), encoding="utf-8")
                self.assertEqual(pf.load_cache(site), cache_of({"1": vorgang("Recht")}))

    def test_read_errors_refuse_and_null_sachgebiet_retains_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            records = {"null": {"sachgebiet": None, "abstract": "keep"}, "missing": {"vorgangstyp": "Antrag"}}
            records.update({str(i): {"sachgebiet": value} for i, value in enumerate((False, "", {}, 0, [1]))})
            pf.save_cache(site, cache_of(records))
            path = pf.cache_path(site)
            original = path.read_bytes()
            for failure in (PermissionError("denied"), OSError("read failure")):
                with mock.patch.object(Path, "read_text", side_effect=failure):
                    with self.assertRaisesRegex(pf.CacheLoadError, "Cannot read.*restore read access"):
                        pf.load_cache(site)
                self.assertEqual(path.read_bytes(), original)
            self.assertEqual(pf.load_cache(site)["vorgaenge"], {
                "null": {"sachgebiet": [], "abstract": "keep"}, "missing": {"sachgebiet": [], "vorgangstyp": "Antrag"},
            })

    def test_repeated_corruption_keeps_unique_backups_and_private_failure_falls_back(self) -> None:
        for fallback in (False, True):
            with self.subTest(fallback=fallback), tempfile.TemporaryDirectory() as tmp:
                site = Path(tmp) / "site"
                path = pf.cache_path(site)
                path.parent.mkdir(parents=True)
                private = Path(tmp) / ".site.private"
                if fallback:
                    private.write_text("blocked", encoding="utf-8")
                err = io.StringIO()
                for text in ("{broken one", "{broken two"):
                    path.write_text(text, encoding="utf-8")
                    with contextlib.redirect_stderr(err):
                        self.assertEqual(pf.load_cache(site), pf.empty_cache())
                kept = list((path.parent if fallback else private).glob(path.name + ".*.corrupt"))
                self.assertEqual({p.read_text(encoding="utf-8") for p in kept}, {"{broken one", "{broken two"})
                for backup in kept:
                    self.assertIn(str(backup), err.getvalue())

    def test_complete_atomic_save_retries_locally_and_double_failure_preserves_old_cache(self) -> None:
        for fail_at in ("replace", "fsync", "write", "flush"):
            for both_fail in (False, True):
                with self.subTest(fail_at=fail_at, both_fail=both_fail), tempfile.TemporaryDirectory() as tmp:
                    site = Path(tmp) / "site"
                    pf.save_cache(site, cache_of({"old": vorgang("Recht")}))
                    path = pf.cache_path(site)
                    original = path.read_bytes()
                    attempts = []
                    real_replace, real_fsync, real_temp = Path.replace, pf.os.fsync, pf.tempfile.NamedTemporaryFile

                    def replace(temporary, target):
                        attempts.append(temporary.parent)
                        if both_fail or temporary.parent.name.endswith(".private"):
                            raise OSError("rename failed")
                        return real_replace(temporary, target)

                    def fsync(fd):
                        attempts.append(fd)
                        if both_fail or len(attempts) == 1:
                            raise OSError("fsync failed")
                        return real_fsync(fd)

                    def make_temp(*args, **kwargs):
                        handle = real_temp(*args, **kwargs)
                        attempts.append(kwargs["dir"])
                        if both_fail or len(attempts) == 1:
                            setattr(handle, fail_at, mock.Mock(side_effect=OSError(f"{fail_at} failed")))
                        return handle

                    patch = (mock.patch.object(Path, "replace", replace) if fail_at == "replace" else
                             mock.patch.object(pf.os, "fsync", fsync) if fail_at == "fsync" else
                             mock.patch.object(pf.tempfile, "NamedTemporaryFile", make_temp))
                    with patch:
                        if both_fail:
                            with self.assertRaises(OSError):
                                pf.save_cache(site, cache_of({"new": vorgang("Verkehr")}))
                        else:
                            pf.save_cache(site, cache_of({"new": vorgang("Verkehr")}))
                    self.assertEqual(len(attempts), 2)
                    self.assertEqual(list(Path(tmp).rglob("*.tmp")), [])
                    if both_fail:
                        self.assertEqual(path.read_bytes(), original)
                    else:
                        self.assertEqual(set(pf.load_cache(site)["vorgaenge"]), {"new"})


class FakeClient:
    """An ApiClient stand-in that answers ``/vorgang`` from a dict and records the calls."""

    def __init__(
        self, records: dict[str, dict[str, Any]], numbers: dict[str, list[str]] | None = None, fail: bool = False,
        fail_numbers: bool = False,
    ):
        self.records = records
        self.numbers = numbers or {}
        self.fail = fail
        self.fail_numbers = fail_numbers
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list_all(self, path: str, params: dict[str, Any] | None = None, **_: Any) -> list[dict[str, Any]]:
        self.calls.append((path, dict(params or {})))
        if self.fail or (self.fail_numbers and "f.dokumentnummer" in params):
            raise dip.DipError("boom")
        if "f.id" in params:
            return [{"id": i, **self.records[i]} for i in params["f.id"] if i in self.records]
        return [{"id": i, **self.records[i]} for i in self.numbers.get(params["f.dokumentnummer"], [])]


def raw(*sachgebiete: str) -> dict[str, Any]:
    return {"sachgebiet": list(sachgebiete), "abstract": "A", "vorgangstyp": "Antrag", "aktualisiert": "2026-01-01",
            "deskriptor": [{"name": "Wolf", "typ": "Sachbegriffe"}, {"name": "Bund", "typ": "Geografisch"}]}


class FetchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entries = [
            {
                "report": {
                    "protocol": {"dokumentnummer": "21/5"},
                    "agenda_items": [
                        item(1, positions=(position("a"), position("b"))),
                        item(2, heading="Beratung", numbers=("21/7",)),
                        item(3, heading="Fragestunde"),
                    ],
                    "sitting_votes": [{"id": "s", "document_numbers": ["21/8"]}],
                }
            }
        ]

    def run_refresh(self, client: FakeClient, cache: dict[str, Any]):
        self.enterContext(mock.patch.object(build, "NUMBER_LOOKUP_PAUSE", 0))
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()) as err:
            site = Path(tmp) / "site"  # save_cache stages beside the site, so keep that inside tmp too
            stats = build.refresh_vorgang_cache(client, self.entries, cache, site)
            saved = pf.load_cache(site)
        return stats, saved, err.getvalue()

    def test_only_missing_vorgaenge_and_numbers_are_fetched_and_the_cache_is_saved(self) -> None:
        client = FakeClient(
            {"a": raw("Gesundheit"), "b": raw("Recht"), "c": raw("Kultur"), "d": raw("Energie")},
            {"21/7": ["c"], "21/8": ["d"]},
        )
        cache = cache_of({"a": dip.vorgang_cache_record(raw("Gesundheit"))})
        stats, saved, _ = self.run_refresh(client, cache)
        id_calls = [params["f.id"] for path, params in client.calls if "f.id" in params]
        self.assertEqual(id_calls, [["b"]])  # a was complete, so it stays cached
        number_calls = [params["f.dokumentnummer"] for _, params in client.calls if "f.dokumentnummer" in params]
        self.assertEqual(number_calls, ["21/7", "21/8"])  # the Fragestunde names none
        self.assertEqual(stats["nummern"], 2)
        self.assertEqual(saved["dokumentnummern"], {"21/7": ["c"], "21/8": ["d"]})
        self.assertEqual(saved["vorgaenge"]["c"]["sachgebiet"], ["Kultur"])
        self.assertEqual(saved["vorgaenge"]["c"]["deskriptor_sachbegriffe"], ["Wolf"])
        self.assertEqual(saved["vorgaenge"]["c"]["abstract"], "A")

    def test_a_cached_vorgang_without_sachgebiet_is_refetched_and_a_second_run_fetches_nothing(self) -> None:
        records = {"a": raw("Gesundheit"), "b": raw("Recht")}
        cache = cache_of(
            {n: dip.vorgang_cache_record(raw("Recht")) for n in "bcd"} | {"a": dip.vorgang_cache_record(raw())},
            {"21/7": ["c"], "21/8": ["d"]},
        )
        client = FakeClient(records)
        self.run_refresh(client, cache)
        self.assertEqual([p["f.id"] for _, p in client.calls], [["a"]])
        self.assertEqual(cache["vorgaenge"]["a"]["sachgebiet"], ["Gesundheit"])
        again = FakeClient(records)
        self.run_refresh(again, cache)
        self.assertEqual(again.calls, [])

    def test_ids_are_batched_by_the_batch_size(self) -> None:
        ids = [str(i) for i in range(dip.VORGANG_BATCH * 2 + 5)]
        client = FakeClient({i: raw("Recht") for i in ids})
        found = dip.fetch_vorgaenge(client, ids)
        self.assertEqual([len(p["f.id"]) for _, p in client.calls], [dip.VORGANG_BATCH, dip.VORGANG_BATCH, 5])
        self.assertEqual(len(found), len(ids))

    def test_an_id_dip_does_not_return_is_recorded_as_empty(self) -> None:
        self.assertEqual(dip.fetch_vorgaenge(FakeClient({}), ["gone"])["gone"]["sachgebiet"], [])

    def test_a_failed_fetch_warns_leaves_a_cache_miss_and_does_not_abort(self) -> None:
        stats, saved, err = self.run_refresh(FakeClient({}, fail=True), pf.empty_cache())
        self.assertIn("warning", err)
        self.assertEqual(saved["vorgaenge"], {})
        self.assertGreater(stats["vorgaenge_failed"], 0)
        self.assertGreater(stats["nummern_failed"], 0)
        top_tags, vote_tags = pf.report_politikfelder(self.entries[0]["report"], saved)
        self.assertEqual(top_tags[0], ([pf.UNTAGGED], "not_fetched"))
        self.assertEqual(top_tags[2], ([pf.UNTAGGED], "untagged"))
        self.assertEqual(vote_tags["s"], ([pf.UNTAGGED], "not_fetched"))

    # Value: protects=an outage or a DIP bot challenge stops the fetch after 5 failed calls in a row and the build still finishes; fails_when=the breaker is removed or off by one, so a dead API gets a call per Vorgang batch and per number at 0.5 s pacing; why_new=test_a_failed_fetch... fails only 1 batch and 2 numbers, never reaching 5; seam=none
    def test_five_failures_in_a_row_stop_the_fetch_and_the_build_still_finishes(self) -> None:
        many = [item(i, positions=(position(f"v{i}"),)) for i in range(1, 9)]
        self.entries = [{"report": {"protocol": {"dokumentnummer": "21/5"}, "agenda_items": many}}]
        self.enterContext(mock.patch.object(dip, "VORGANG_BATCH", 1))
        client = FakeClient({}, fail=True)
        stats, _saved, _err = self.run_refresh(client, pf.empty_cache())
        self.assertEqual([p["f.id"] for _, p in client.calls], [[f"v{i}"] for i in range(1, 6)])  # 5 of 8 batches, then stop
        self.assertEqual((stats["vorgaenge"], stats["vorgaenge_failed"], stats["nummern"]), (0, 8, 0))  # 3 never tried

        numbered = [item(i, numbers=(f"21/{i}",)) for i in range(1, 8)]
        self.entries = [{"report": {"protocol": {"dokumentnummer": "21/5"}, "agenda_items": numbered}}]
        client = FakeClient({}, fail_numbers=True)
        stats, _saved, _err = self.run_refresh(client, pf.empty_cache())
        lookups = [p["f.dokumentnummer"] for _, p in client.calls if "f.dokumentnummer" in p]
        self.assertEqual(lookups, [f"21/{i}" for i in range(1, 6)])
        self.assertEqual((stats["nummern"], stats["nummern_failed"]), (0, 7))  # the 2 left over count as failed

    # Value: protects=a success between failures resets the breaker, so one flaky call never aborts a long fill; fails_when=the failure counter is not reset on success; why_new=the breaker test fails every call; seam=none
    def test_a_success_between_failures_resets_the_breaker(self) -> None:
        numbered = [item(i, numbers=(f"21/{i}",)) for i in range(1, 11)]
        self.entries = [{"report": {"protocol": {"dokumentnummer": "21/5"}, "agenda_items": numbered}}]

        class Flaky(FakeClient):
            def list_all(self, path, params=None, **kwargs):
                number = (params or {}).get("f.dokumentnummer")
                if number and int(number.split("/")[1]) % 5:  # 4 failures, then a success, repeatedly
                    self.calls.append((path, dict(params)))
                    raise dip.DipError("boom")
                return super().list_all(path, params, **kwargs)

        stats, saved, _err = self.run_refresh(Flaky({}, {"21/5": [], "21/10": []}), pf.empty_cache())
        self.assertEqual(stats["nummern"], 2)
        self.assertEqual(stats["nummern_failed"], 8)
        self.assertEqual(sorted(saved["dokumentnummern"]), ["21/10", "21/5"])

    # Value: protects=when the Vorgang pass shows the API is down, the Drucksache-number lookups are not even tried; fails_when=the `if not down` guard is dropped, so a dead API or a bot challenge gets one more call per number at 0.5 s pacing after the breaker already tripped; why_new=the breaker test's id pass names no Drucksache number, so it cannot tell; seam=none
    def test_an_outage_on_the_id_pass_skips_the_number_lookups(self) -> None:
        many = [item(i, positions=(position(f"v{i}"),)) for i in range(1, 7)] + [item(7, numbers=("21/7",))]
        self.entries = [{"report": {"protocol": {"dokumentnummer": "21/5"}, "agenda_items": many}}]
        self.enterContext(mock.patch.object(dip, "VORGANG_BATCH", 1))
        client = FakeClient({}, {"21/7": ["x"]}, fail=True)
        stats, _saved, _err = self.run_refresh(client, pf.empty_cache())
        self.assertEqual([p for _, p in client.calls if "f.dokumentnummer" in p], [])
        self.assertEqual((stats["nummern"], stats["nummern_failed"]), (0, 0))
        self.assertEqual(stats["vorgaenge_failed"], 6)

    # Value: protects=a full disk is a warning that does not end the build, and an interrupted first fill keeps what it resolved (saved every CACHE_SAVE_EVERY lookups and again on the way out); fails_when=save() stops catching OSError, or resolve_numbers loses its periodic save or its finally; why_new=every other test saves to a healthy directory and runs to the end; seam=none; no_claim=a real full disk or SIGKILL (a patched save_cache, a KeyboardInterrupt from the fake client)
    def test_a_failed_save_is_a_warning_and_an_interrupted_fill_keeps_its_progress(self) -> None:
        numbered = [item(i, numbers=(f"21/{i}",)) for i in range(1, 7)]
        self.entries = [{"report": {"protocol": {"dokumentnummer": "21/5"}, "agenda_items": numbered}}]
        self.enterContext(mock.patch.object(build, "NUMBER_LOOKUP_PAUSE", 0))

        with mock.patch.object(pf, "save_cache", side_effect=OSError("disk full")), contextlib.redirect_stderr(io.StringIO()) as err:
            stats = build.refresh_vorgang_cache(FakeClient({}, {}), self.entries, pf.empty_cache(), Path("unused"))
        self.assertEqual(stats["nummern"], 6)
        self.assertIn("could not save the Vorgang cache: disk full", err.getvalue())

        class Interrupted(FakeClient):
            def list_all(self, path, params=None, **kwargs):
                if "f.dokumentnummer" in (params or {}) and params["f.dokumentnummer"] == "21/4":
                    raise KeyboardInterrupt
                return super().list_all(path, params, **kwargs)

        self.enterContext(mock.patch.object(build, "CACHE_SAVE_EVERY", 2))
        seen: list[int] = []
        real_save = pf.save_cache

        def spy(output_dir, cache):
            seen.append(len(cache["dokumentnummern"]))
            real_save(output_dir, cache)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(pf, "save_cache", side_effect=spy):
            site = Path(tmp) / "site"
            client = Interrupted({}, {f"21/{i}": [] for i in range(1, 7)})
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(KeyboardInterrupt):
                build.refresh_vorgang_cache(client, self.entries, pf.empty_cache(), site)
            self.assertEqual(sorted(pf.load_cache(site)["dokumentnummern"]), ["21/1", "21/2", "21/3"])
        self.assertEqual(seen, [0, 2, 3])  # after the (empty) id pass, at the 2nd lookup, on the way out

    # Value: protects=no Drucksache number is fetched for a TOP with Vorgänge of its own, because tagging never reads it there; fails_when=fetch_targets asks numbers whenever the TOP's Vorgänge give no tag, so paced lookups that change nothing repeat on every online build; why_new=the two rules were separate and drifted; seam=none
    def test_fetch_targets_asks_no_numbers_for_a_top_with_own_vorgaenge(self) -> None:
        report = {"protocol": {"dokumentnummer": "21/10"}, "agenda_items": [
            item(1, heading="Antrag 21/123", positions=(position("V1"),)),
            item(2, heading="Antrag 21/124"),
        ]}
        ids, numbers = pf.fetch_targets([report], cache_of({"V1": vorgang()}))
        self.assertEqual((ids, numbers), (["V1"], ["21/124"]))

    # Value: protects=a paced caller's list_all pauses before every page after the first, so one lookup (two requests) stays under DIP's bot-challenge rate; fails_when=page_pause is dropped or applied before the first request only; why_new=fake clients hid that a lookup is two requests; seam=none
    def test_list_all_pauses_between_pages(self) -> None:
        client = dip.ApiClient.__new__(dip.ApiClient)
        pages = iter([{"documents": [{"id": "1"}], "cursor": "c1"}, {"documents": [{"id": "2"}], "cursor": "c2"}, {"documents": [], "cursor": "c2"}])
        with mock.patch.object(dip.ApiClient, "get_json", lambda self, path, params: next(pages)), mock.patch.object(dip.time, "sleep") as sleep:
            self.assertEqual([d["id"] for d in client.list_all("/vorgang", {}, page_pause=0.5)], ["1", "2"])
        self.assertEqual(sleep.call_args_list, [mock.call(0.5), mock.call(0.5)])

    # Value: protects=a DIP record whose sachgebiet is a string is a failed fetch (retried next build), never cached as single letters; fails_when=vorgang_cache_record iterates the string again, so "Gesundheit" is cached as ['G','e',...] for good; why_new=found by both adversarial passes of this ship; seam=none
    def test_a_string_sachgebiet_is_a_failed_fetch_not_a_cached_record(self) -> None:
        with self.assertRaises(dip.DipError):
            dip.vorgang_cache_record({"id": "x", "sachgebiet": "Gesundheit"})
        self.assertEqual(dip.vorgang_cache_record({"sachgebiet": None, "deskriptor": "x"})["sachgebiet"], [])
        bad = {"sachgebiet": "Gesundheit", "abstract": "A"}
        client = FakeClient({"a": bad, "b": bad, "c": raw("Verkehr")}, {"21/7": ["b"]})
        self.entries = [{"report": {"protocol": {"dokumentnummer": "21/5"}, "agenda_items": [
            item(1, positions=(position("a"),)), item(2, numbers=("21/7",)), item(3, positions=(position("c"),)),
        ]}}]
        self.enterContext(mock.patch.object(dip, "VORGANG_BATCH", 1))
        stats, saved, err = self.run_refresh(client, pf.empty_cache())
        self.assertEqual(sorted(saved["vorgaenge"]), ["c"])
        self.assertEqual(saved["dokumentnummern"]["21/7"], ["b"])
        self.assertEqual((stats["vorgaenge_failed"], stats["nummern_failed"], stats["shape_errors"]), (1, 0, 2))
        self.assertIn("b", pf.fetch_targets([self.entries[0]["report"]], saved)[0])
        self.assertIn("unexpected sachgebiet", err)

    # Value: protects=D12: the cache keeps a Vorgang's titel, the label of its "Worum es geht" block; fails_when=vorgang_cache_record drops titel, so blocks of vote-only Vorgänge have no name; why_new=the record kept no title before B4; seam=none
    def test_the_cache_record_keeps_the_titel(self) -> None:
        self.assertEqual(dip.vorgang_cache_record(dict(raw("Recht"), titel="Gesetz über X"))["titel"], "Gesetz über X")
        self.assertIsNone(dip.vorgang_cache_record({})["titel"])  # DIP gave no title

    # Value: protects=D11: an online build asks DIP again for a vote's context Vorgang whose abstract is still empty, and for nothing else (a record without titel is not refetched for it); fails_when=fetch_targets keeps refetching only on an empty Sachgebiet, so "Keine Beschreibung in DIP" stays false for good, or it refetches TOP-only or wide-tier Vorgänge on every build; why_new=the refetch rule is new in B4; seam=none
    def test_fetch_targets_refetches_vote_vorgaenge_without_abstract(self) -> None:
        complete = vorgang("Recht")
        no_abstract = dict(complete, abstract="")
        no_titel = {k: v for k, v in complete.items() if k != "titel"}
        untitled = dict(complete, titel=None)
        report = {
            "protocol": {"dokumentnummer": "21/5"},
            "agenda_items": [item(1, positions=(position("top"),), votes=({"id": "v", "document_numbers": ["21/1", "21/2", "21/3", "21/4", "21/6"]},))],
        }
        cache = cache_of(
            {"top": no_abstract, "a": no_abstract, "b": no_titel, "c": untitled, "d": complete, "w1": no_abstract, "w2": no_abstract, "w3": no_abstract},
            {"21/1": ["a"], "21/2": ["b"], "21/3": ["c"], "21/4": ["d"], "21/6": ["w1", "w2", "w3"]},
        )
        # top: a TOP's own Vorgang with a Sachgebiet; w1-w3: wide tier only, never the vote's prose.
        self.assertEqual(pf.fetch_targets([report], cache), (["a"], []))
        cache["vorgaenge"]["a"] = complete
        self.assertEqual(pf.fetch_targets([report], cache), ([], []))

    def test_mixed_batch_keeps_99_records_counts_results_and_continues(self) -> None:
        ids = [str(i) for i in range(101)]
        self.entries = [{"report": {"agenda_items": [
            item(i, positions=(position(key),)) for i, key in enumerate(ids, 1)
        ] + [item(102, numbers=("21/7",))]}}]
        client = FakeClient({key: raw("Recht") for key in ids} | {"0": {"sachgebiet": False}}, {"21/7": ["1", "0"]})
        stats, saved, err = self.run_refresh(client, pf.empty_cache())
        self.assertEqual(len(saved["vorgaenge"]), 100)
        self.assertEqual((stats["vorgaenge"], stats["vorgaenge_failed"], stats["shape_errors"]), (100, 1, 2))
        self.assertEqual(saved["dokumentnummern"], {"21/7": ["1", "0"]})
        self.assertEqual(pf.fetch_targets([self.entries[0]["report"]], saved), (["0"], []))
        self.assertIn("Vorgang validation", err)

    def test_shape_errors_do_not_trip_either_breaker_and_reset_outage_streaks(self) -> None:
        self.enterContext(mock.patch.object(dip, "VORGANG_BATCH", 1))
        for numbered in (False, True):
            for malformed_envelope in (False, True):
                with self.subTest(numbered=numbered, envelope=malformed_envelope):
                    self.entries = [{"report": {"agenda_items": [
                        item(i, numbers=(f"21/{i}",)) if numbered else item(i, positions=(position(str(i)),))
                        for i in range(1, 16)
                    ]}}]
                    calls = []

                    def answer(path, params, **kwargs):
                        calls.append(params)
                        n = len(calls)
                        if n < 5 or 5 < n < 10:
                            raise dip.DipError("outage")
                        if malformed_envelope:
                            raise dip.DipShapeError("bad envelope")
                        return [{"id": str(n), "sachgebiet": False}]

                    client = mock.Mock(list_all=mock.Mock(side_effect=answer))
                    stats, saved, err = self.run_refresh(client, pf.empty_cache())
                    self.assertEqual(len(calls), 15)
                    self.assertEqual(stats["shape_errors"], 7)
                    self.assertNotIn("outage", err.split("validation:")[-1])

    def test_list_boundary_salvages_pages_without_certifying_membership(self) -> None:
        good = [{"id": str(i), **raw("Recht")} for i in range(99)]
        cases = [
            [{"documents": good + [None]}],
            [{"documents": good[:50], "cursor": "c1"}, {"documents": [None], "cursor": "c2"},
             {"documents": good[50:], "cursor": "c3"}, {"documents": []}],
            [{"documents": good, "cursor": "c1"}, {"documents": None}],
        ]
        for pages in cases:
            with self.subTest(pages=len(pages)):
                client = dip.ApiClient("unused")
                with mock.patch.object(dip.ApiClient, "get_json", side_effect=pages), mock.patch.object(dip.time, "sleep") as sleep:
                    with self.assertRaises(dip.DipShapeError) as caught:
                        client.list_all("/vorgang", page_pause=0.5)
                self.assertEqual(len(caught.exception.documents), 99)
                self.assertTrue(caught.exception.incomplete_membership)
                self.assertEqual(sleep.call_count, len(pages) - 1)
                with mock.patch.object(dip.ApiClient, "get_json", side_effect=pages), contextlib.redirect_stderr(io.StringIO()):
                    records = dip.fetch_vorgaenge(client, [str(i) for i in range(100)])
                self.assertEqual(set(records), {str(i) for i in range(99)})
                self.entries = [{"report": {"agenda_items": [item(1, numbers=("21/7",))]}}]
                with mock.patch.object(dip.ApiClient, "get_json", side_effect=pages):
                    stats, saved, _ = self.run_refresh(client, pf.empty_cache())
                self.assertEqual(len(saved["vorgaenge"]), 99)
                self.assertEqual(saved["dokumentnummern"], {})
                self.assertEqual(stats["nummern_failed"], 1)
                self.assertEqual(pf.fetch_targets([self.entries[0]["report"]], saved)[1], ["21/7"])

    # Value: protects=integer DIP IDs are normalized to string cache keys while malformed IDs remain retryable; fails_when=vorgang_id rejects integers or the caller stores them under a non-string key; why_new=the existing case covers only string IDs and malformed values; seam=none; no_claim=live DIP ID types (fixture response)
    def test_unusable_ids_keep_good_records_and_leave_membership_retryable(self) -> None:
        for bad in (None, "", "  ", [], {}, True, 1.5):
            with self.subTest(bad=bad):
                client = mock.Mock(list_all=mock.Mock(return_value=[{"id": "a", **raw("Recht")}, {"id": bad}]))
                stats, saved, _ = self.run_refresh(client, pf.empty_cache())
                self.assertEqual(set(saved["vorgaenge"]), {"a"})
                self.assertEqual(saved["dokumentnummern"], {})
                self.assertEqual(pf.fetch_targets([self.entries[0]["report"]], saved), (["b"], ["21/7", "21/8"]))
        client.list_all.return_value = [{"id": "a", **raw("Recht")}, {}]
        _, saved, _ = self.run_refresh(client, pf.empty_cache())
        self.assertEqual(set(saved["vorgaenge"]), {"a"})
        self.assertEqual(saved["dokumentnummern"], {})
        client.list_all.return_value = [{"id": 42, **raw("Recht")}]
        self.assertEqual(set(dip.fetch_vorgaenge(client, ["42"])), {"42"})

    # Value: protects=an ID fetch cannot overwrite a cached record outside its requested IDs; fails_when=unrequested response records enter the returned cache update; why_new=existing cases only return requested or malformed IDs; seam=none; no_claim=live DIP filtering
    def test_id_fetch_does_not_overwrite_a_cached_unrequested_vorgang(self) -> None:
        cache = cache_of({"outside": vorgang("Gesundheit")})
        client = mock.Mock(list_all=mock.Mock(return_value=[
            {"id": "a", **raw("Recht")}, {"id": "outside", **raw("Verkehr")},
        ]))
        cache["vorgaenge"].update(dip.fetch_vorgaenge(client, ["a", "b"]))
        self.assertEqual(cache["vorgaenge"]["outside"], vorgang("Gesundheit"))
        self.assertEqual(cache["vorgaenge"]["a"]["sachgebiet"], ["Recht"])
        self.assertEqual(cache["vorgaenge"]["b"]["sachgebiet"], [])

    def test_documents_must_be_an_explicit_list_and_sachgebiet_only_normalizes_null(self) -> None:
        client = dip.ApiClient("unused")
        for page in ({}, {"documents": None}, {"documents": False}, {"documents": ""}, {"documents": {}}, [], None):
            with self.subTest(page=page), mock.patch.object(dip.ApiClient, "get_json", return_value=page):
                with self.assertRaises(dip.DipShapeError):
                    client.list_all("/person")
        with mock.patch.object(dip.ApiClient, "get_json", return_value={"documents": []}):
            self.assertEqual(dip.fetch_vorgaenge(client, ["missing"])["missing"]["sachgebiet"], [])
        for value in (False, "", {}, 0, [1]):
            with self.subTest(value=value), self.assertRaises(dip.DipShapeError):
                dip.vorgang_cache_record({"sachgebiet": value})
        for document in ({}, {"sachgebiet": None}):
            self.assertEqual(dip.vorgang_cache_record(document)["sachgebiet"], [])

    def test_fetch_targets_asks_for_nothing_when_the_cache_is_complete(self) -> None:
        reports = [self.entries[0]["report"]]
        cache = cache_of(
            {"a": vorgang("Recht"), "b": vorgang("Recht"), "c": vorgang("Kultur"), "d": vorgang("Energie")},
            {"21/7": ["c"], "21/8": ["d"]},
        )
        self.assertEqual(pf.fetch_targets(reports, cache), ([], []))


def fixture_report() -> dict[str, Any]:
    return json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))


class PersistTests(unittest.TestCase):
    def persisted(self, cache: dict[str, Any] | None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = pulse_store.connect(Path(tmp.name) / "store.sqlite")
        self.addCleanup(conn.close)
        report = fixture_report()
        report["agenda_items"][0]["api"]["positions"] = [position("v1", "Gesetzgebung")]
        pulse_store.persist_report(conn, report, cache)
        return conn

    def test_rows_are_written_with_source_and_rank(self) -> None:
        conn = self.persisted(cache_of({"v1": vorgang("Gesundheit", "Recht")}))
        top = [tuple(r) for r in conn.execute(
            "SELECT politikfeld, rank, source FROM agenda_item_politikfelder JOIN agenda_items a ON a.id = agenda_item_id "
            "WHERE a.item_index = 1 ORDER BY rank")]
        self.assertEqual(top, [("Gesundheit", 1, "sachgebiet"), ("Justiz", 2, "sachgebiet")])
        votes = [tuple(r) for r in conn.execute("SELECT politikfeld, rank, source FROM vote_politikfelder ORDER BY rank")]
        self.assertEqual(votes, [("Gesundheit", 1, "top"), ("Justiz", 2, "top")])
        self.assertEqual(
            conn.execute("SELECT sachgebiet FROM proceedings WHERE id = 'v1'").fetchone()[0],
            json.dumps(["Gesundheit", "Recht"], ensure_ascii=False),
        )

    def test_untagged_and_not_fetched_are_stored_as_explicit_rows(self) -> None:
        conn = self.persisted(None)
        rows = {tuple(r) for r in conn.execute("SELECT politikfeld, source FROM agenda_item_politikfelder")}
        self.assertEqual(rows, {("untagged", "not_fetched"), ("untagged", "untagged")})
        self.assertEqual({tuple(r) for r in conn.execute("SELECT politikfeld, source FROM vote_politikfelder")}, {("untagged", "not_fetched")})
        self.assertIsNone(conn.execute("SELECT sachgebiet FROM proceedings WHERE id = 'v1'").fetchone()[0])

    def test_every_vote_has_at_least_one_row(self) -> None:
        for cache in (None, cache_of({"v1": vorgang("Gesundheit")})):
            conn = self.persisted(cache)
            self.assertGreater(conn.execute("SELECT count(*) FROM votes").fetchone()[0], 0)
            self.assertEqual(
                conn.execute("SELECT count(*) FROM votes WHERE id NOT IN (SELECT vote_id FROM vote_politikfelder)").fetchone()[0], 0
            )

    def test_the_check_constraint_rejects_a_label_outside_the_list(self) -> None:
        conn = self.persisted(cache_of({"v1": vorgang("Gesundheit")}))
        vote_id = conn.execute("SELECT id FROM votes").fetchone()[0]
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO vote_politikfelder VALUES (?, 'Esoterik', 9, 'sachgebiet')", (vote_id,))
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO vote_politikfelder VALUES (?, 'Recht', 9, 'sachgebiet')", (vote_id,))
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO vote_politikfelder VALUES (?, 'Justiz', 9, 'geraten')", (vote_id,))

    # Value: protects=an agenda item whose source index is the text "1" or " 02 " still gets its tag rows, and a vote without an id gets none and crashes nothing; fails_when=persist_politikfelder looks agenda_ids up by the raw item["index"] instead of stable_ids.source_index (the #91 merge fix), so those TOPs are silently stored untagged; why_new=every persist test uses integer indexes and votes with ids; seam=none
    def test_text_indexes_find_their_agenda_item(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = pulse_store.connect(Path(tmp.name) / "store.sqlite")
        self.addCleanup(conn.close)
        report = fixture_report()
        report["agenda_items"][0]["index"] = "1"
        report["agenda_items"][0]["api"]["positions"] = [position("v1", "Gesetzgebung")]
        report["agenda_items"][1]["index"] = " 02 "
        report["agenda_items"][1]["api"] = {"positions": [position("v2", "Antrag")]}
        pulse_store.persist_report(conn, report, cache_of({"v1": vorgang("Gesundheit"), "v2": vorgang("Verkehr")}))
        rows = {tuple(r) for r in conn.execute(
            "SELECT a.item_index, politikfeld FROM agenda_item_politikfelder JOIN agenda_items a ON a.id = agenda_item_id")}
        self.assertEqual(rows, {(1, "Gesundheit"), (2, "Verkehr")})
        self.assertEqual({r[0] for r in conn.execute("SELECT DISTINCT vote_id FROM vote_politikfelder")}, {"12345"})

    def test_persisting_again_replaces_the_rows(self) -> None:
        conn = self.persisted(cache_of({"v1": vorgang("Gesundheit")}))
        report = fixture_report()
        report["agenda_items"][0]["api"]["positions"] = [position("v1", "Gesetzgebung")]
        pulse_store.persist_report(conn, report, cache_of({"v1": vorgang("Verkehr")}))
        self.assertEqual(
            {r[0] for r in conn.execute("SELECT politikfeld FROM vote_politikfelder")}, {"Verkehr"}
        )


class RepersistGuardTests(unittest.TestCase):
    """build.require_vorgang_cache_for_tags on a store holding only the two tag tables."""

    def top_id(self, index: Any, protocol: str = "p1") -> str:
        return pulse_store.stable_key("agenda", pulse_store.clean(protocol), build.source_index(index))

    def store(self, tmp: str, tops: list[tuple[str, str]], votes: list[tuple[str, str]]) -> Path:
        path = Path(tmp) / "site" / "data" / "bundestag-pulse.sqlite"
        path.parent.mkdir(parents=True)
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE agenda_item_politikfelder (agenda_item_id, politikfeld, rank, source)")
        conn.execute("CREATE TABLE vote_politikfelder (vote_id, politikfeld, rank, source)")
        conn.executemany("INSERT INTO agenda_item_politikfelder VALUES (?, 'x', 1, ?)", tops)
        conn.executemany("INSERT INTO vote_politikfelder VALUES (?, 'x', 1, ?)", votes)
        conn.commit()
        conn.close()
        return path

    def test_known_identities_are_protected_and_einzelplan_needs_no_cache(self) -> None:
        einzelplan = item(1, heading="Einzelplan 12 Bundesministerium für Verkehr", votes=[{"id": "v1", "title": "T", "date": "2026-01-01"}])
        report = {"protocol": {"id": "p1", "dokumentnummer": "21/5"}, "agenda_items": [einzelplan]}
        with tempfile.TemporaryDirectory() as tmp:
            path = self.store(tmp, [(self.top_id(1), "einzelplan")], [("v1", "top")])
            build.require_vorgang_cache_for_tags(path, None, path.parent.parent, [{"report": report}])

        positioned = item(1, positions=(position("V1"),), votes=[{"id": "v1", "title": "T", "date": "2026-01-01"}])
        report = {"protocol": {"id": "p1", "dokumentnummer": "21/5"}, "agenda_items": [positioned]}
        with tempfile.TemporaryDirectory() as tmp:
            path = self.store(tmp, [(self.top_id(1), "sachgebiet")], [("v1", "top")])
            for partial in (None, cache_of({"unrelated": vorgang("Recht")})):
                with self.assertRaisesRegex(build.DatabaseRebuildError, "1 previously known TOPs and 1 previously known votes"):
                    build.require_vorgang_cache_for_tags(path, partial, path.parent.parent, [{"report": report}])
            build.require_vorgang_cache_for_tags(path, cache_of({"V1": vorgang("Recht")}), path.parent.parent, [{"report": report}])

    # Value: protects=a replay refuses a cache that would turn a stored resolved or none vote context (votes.context_state, none since D5) into not_fetched even while the vote's tags stay known; fails_when=the guard checks only the tag tables, so a partial cache silently drops abstracts and vote_proceedings; why_new=the guard covered tags only; seam=none
    def test_a_resolved_vote_context_is_protected_even_when_its_tags_stay_known(self) -> None:
        positioned = item(1, positions=(position("V1"),), votes=[{"id": "v1", "document_numbers": ["21/1"]}])
        report = {"protocol": {"id": "p1", "dokumentnummer": "21/5"}, "agenda_items": [positioned]}
        full = cache_of({"V1": vorgang("Recht"), "A": vorgang("Recht")}, {"21/1": ["A"]})
        partial = cache_of({"V1": vorgang("Recht")})
        for with_context in (True, False):
            with self.subTest(schema6=with_context), tempfile.TemporaryDirectory() as tmp:
                path = self.store(tmp, [(self.top_id(1), "sachgebiet")], [("v1", "top")])
                with contextlib.closing(sqlite3.connect(path)) as conn, conn:
                    if with_context:
                        conn.execute("CREATE TABLE votes (id, context_state)")
                        conn.execute("INSERT INTO votes VALUES ('v1', 'resolved')")
                    else:
                        conn.execute("CREATE TABLE votes (id)")  # schema 5: no context stored yet
                        conn.execute("INSERT INTO votes VALUES ('v1')")
                if with_context:
                    with self.assertRaisesRegex(
                        build.DatabaseRebuildError, "0 previously known votes not_fetched and 1 previously known vote contexts not_fetched \\(1 resolved, 0 none\\)"
                    ):
                        build.require_vorgang_cache_for_tags(path, partial, path.parent.parent, [{"report": report}])
                else:
                    build.require_vorgang_cache_for_tags(path, partial, path.parent.parent, [{"report": report}])
                build.require_vorgang_cache_for_tags(path, full, path.parent.parent, [{"report": report}])
        # A context stored as none is a known answer too (D5, 2026-10-22); one stored
        # as not_fetched or NULL was never known and may stay or degrade.
        for stored in ("none", "not_fetched", None):
            with self.subTest(stored=stored), tempfile.TemporaryDirectory() as tmp:
                path = self.store(tmp, [(self.top_id(1), "sachgebiet")], [("v1", "top")])
                with contextlib.closing(sqlite3.connect(path)) as conn, conn:
                    conn.execute("CREATE TABLE votes (id, context_state)")
                    conn.execute("INSERT INTO votes VALUES ('v1', ?)", (stored,))
                if stored == "none":
                    with self.assertRaisesRegex(build.DatabaseRebuildError, r"1 previously known vote contexts not_fetched \(0 resolved, 1 none\)"):
                        build.require_vorgang_cache_for_tags(path, partial, path.parent.parent, [{"report": report}])
                else:
                    build.require_vorgang_cache_for_tags(path, partial, path.parent.parent, [{"report": report}])

    # Value: protects=a replay refuses a cache that lost one of a resolved vote's two numbers while the other still names a Vorgang; fails_when=the context stays resolved with fewer Vorgänge, the guard passes and the replay drops a vote_proceedings row; why_new=B4 ship review (2026-10-22) found the gap; seam=none
    def test_a_cache_that_lost_one_of_two_vote_numbers_is_refused(self) -> None:
        positioned = item(1, positions=(position("V1"),), votes=[{"id": "v1", "document_numbers": ["21/1", "21/2"]}])
        report = {"protocol": {"id": "p1", "dokumentnummer": "21/5"}, "agenda_items": [positioned]}
        records = {"V1": vorgang("Recht"), "A": vorgang("Recht"), "B": vorgang("Recht")}
        with tempfile.TemporaryDirectory() as tmp:
            path = self.store(tmp, [(self.top_id(1), "sachgebiet")], [("v1", "top")])
            with contextlib.closing(sqlite3.connect(path)) as conn, conn:
                conn.execute("CREATE TABLE votes (id, context_state)")
                conn.execute("INSERT INTO votes VALUES ('v1', 'resolved')")
            with self.assertRaisesRegex(build.DatabaseRebuildError, "1 previously known vote contexts"):
                build.require_vorgang_cache_for_tags(
                    path, cache_of(records, {"21/1": ["A"]}), path.parent.parent, [{"report": report}]
                )
            build.require_vorgang_cache_for_tags(
                path, cache_of(records, {"21/1": ["A"], "21/2": ["B"]}), path.parent.parent, [{"report": report}]
            )

    def test_equal_swaps_and_net_improvements_cannot_hide_a_known_identity_loss(self) -> None:
        for kind in ("top", "vote"):
            for recovered in (1, 2):
                with self.subTest(kind=kind, recovered=recovered), tempfile.TemporaryDirectory() as tmp:
                    states = [(1, "sachgebiet")] + [(i, "not_fetched") for i in range(2, recovered + 2)]
                    tops = [(self.top_id(i), source) for i, source in states] if kind == "top" else []
                    votes = [(f"v{i}", source) for i, source in states] if kind == "vote" else []
                    path = self.store(tmp, tops, votes)
                    # String indexes and cleaned protocol/vote IDs match persistence.
                    report = {"protocol": {"id": " p1 "}, "agenda_items": [
                        item(f" {i:02} ", positions=(position(f"V{i}"),), votes=[{"id": f" v{i} "}])
                        for i, _ in states
                    ]}
                    cache = cache_of({f"V{i}": vorgang("Recht") for i, _ in states if i != 1})
                    with self.assertRaisesRegex(build.DatabaseRebuildError, "previously known.*online update") as caught:
                        build.require_vorgang_cache_for_tags(path, cache, path.parent.parent, [{"report": report}])
                    self.assertIn(self.top_id(1) if kind == "top" else "v1", str(caught.exception))

    def test_unchanged_degradation_recovery_and_new_missing_entities_pass(self) -> None:
        report = {"protocol": {"id": "p1"}, "agenda_items": [
            item(i, positions=(position(f"V{i}"),), votes=[{"id": f"v{i}"}]) for i in range(1, 4)
        ]}
        with tempfile.TemporaryDirectory() as tmp:
            path = self.store(tmp, [(self.top_id(1), "untagged"), (self.top_id(2), "not_fetched")],
                              [("v1", "untagged"), ("v2", "not_fetched")])
            for records in ({"V1": vorgang()}, {"V1": vorgang(), "V2": vorgang("Recht")}):
                build.require_vorgang_cache_for_tags(path, cache_of(records), path.parent.parent, [{"report": report}])
            with self.assertRaises(build.DatabaseRebuildError):
                build.require_vorgang_cache_for_tags(path, None, path.parent.parent, [{"report": report}])

    # Votes without an id never get here: report loading refuses them (derive.require_vote_shape).
    def test_stored_blank_ids_are_ignored_and_normalized_duplicates_follow_persistence(self) -> None:
        for final_missing in (True, False):
            with self.subTest(final_missing=final_missing), tempfile.TemporaryDirectory() as tmp:
                path = self.store(tmp, [], [("v1", "untagged"), ("", "untagged"), ("  ", "untagged")])
                early = {"protocol": {"id": "p2", "datum": "2026-02-01"}, "sitting_votes": [
                    {"id": " v1 ", "document_numbers": ["21/1" if final_missing else "21/2"]},
                ]}
                late = {"protocol": {"id": "p1", "datum": "2026-01-01"}, "sitting_votes": [
                    {"id": "v1", "document_numbers": ["21/2" if final_missing else "21/1"]},
                ]}
                entries = [{"report": late}, {"report": early}]
                cache = cache_of({"V1": vorgang("Recht")}, {"21/1": ["V1"]})
                if final_missing:
                    with self.assertRaisesRegex(build.DatabaseRebuildError, "0 previously known TOPs and 1 previously known votes"):
                        build.require_vorgang_cache_for_tags(path, cache, path.parent.parent, entries)
                else:
                    build.require_vorgang_cache_for_tags(path, cache, path.parent.parent, entries)
                # Verify the prospective state against the actual persistence routine.
                conn = sqlite3.connect(":memory:")
                self.addCleanup(conn.close)
                conn.execute("CREATE TABLE vote_politikfelder (vote_id, politikfeld, rank, source)")
                for entry in sorted(entries, key=build.entry_sort_key, reverse=True):
                    pulse_store.persist_politikfelder(conn, entry["report"], {}, cache)
                self.assertEqual(conn.execute("SELECT source FROM vote_politikfelder WHERE vote_id='v1'").fetchone()[0],
                                 "not_fetched" if final_missing else "drucksache")
                # Also exercise overwrite order within a single report.
                late["sitting_votes"] = early["sitting_votes"] + late["sitting_votes"]
                if final_missing:
                    with self.assertRaises(build.DatabaseRebuildError):
                        build.require_vorgang_cache_for_tags(path, cache, path.parent.parent, [{"report": late}])
                else:
                    build.require_vorgang_cache_for_tags(path, cache, path.parent.parent, [{"report": late}])

    def test_only_both_absent_legacy_tables_bypass_the_guard(self) -> None:
        for missing in ("agenda_item_politikfelder", "vote_politikfelder"):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as tmp:
                path = self.store(tmp, [(self.top_id(1), "sachgebiet")], [("v1", "top")])
                with contextlib.closing(sqlite3.connect(path)) as conn, conn:
                    conn.execute(f"DROP TABLE {missing}")
                with self.assertRaisesRegex(build.DatabaseRebuildError, "incomplete store.*restore"):
                    build.require_vorgang_cache_for_tags(path, None, path.parent.parent, [])
                with contextlib.closing(sqlite3.connect(path)) as conn, conn:
                    conn.execute(f"DROP TABLE {'vote_politikfelder' if missing.startswith('agenda') else 'agenda_item_politikfelder'}")
                    conn.execute("CREATE TABLE schema_migrations (version INTEGER)")
                    conn.execute("INSERT INTO schema_migrations VALUES (5)")
                with self.assertRaisesRegex(build.DatabaseRebuildError, "incomplete store.*restore"):
                    build.require_vorgang_cache_for_tags(path, None, path.parent.parent, [])
                with contextlib.closing(sqlite3.connect(path)) as conn, conn:
                    conn.execute("UPDATE schema_migrations SET version=4")
                build.require_vorgang_cache_for_tags(path, None, path.parent.parent, [])

    def test_sqlite_errors_refuse_and_connections_are_closed(self) -> None:
        for diagnostic in ("database is locked", "database disk image is malformed", "no such table: other", "no such column: source"):
            with self.subTest(diagnostic=diagnostic), tempfile.TemporaryDirectory() as tmp:
                path = self.store(tmp, [], [])
                conn = mock.Mock()
                conn.execute.side_effect = sqlite3.OperationalError(diagnostic)
                with mock.patch.object(build.sqlite3, "connect", return_value=conn):
                    with self.assertRaisesRegex(build.DatabaseRebuildError, diagnostic):
                        build.require_vorgang_cache_for_tags(path, None, path.parent.parent, [])
                conn.close.assert_called_once()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.sqlite"
            path.write_bytes(b"not a database")
            with self.assertRaisesRegex(build.DatabaseRebuildError, "not a database.*restore"):
                build.require_vorgang_cache_for_tags(path, None, path.parent, [])
        with tempfile.TemporaryDirectory() as tmp:
            path = self.store(tmp, [], [])
            with contextlib.closing(sqlite3.connect(path)) as conn, conn:
                conn.execute("ALTER TABLE vote_politikfelder RENAME COLUMN source TO wrong")
            with self.assertRaisesRegex(build.DatabaseRebuildError, "no such column: source"):
                build.require_vorgang_cache_for_tags(path, None, path.parent.parent, [])


class SummaryTests(unittest.TestCase):
    # Value: protects=every build says how the Politikfelder came out, surfaces a Sachgebiet label DIP added, and a missing store never crashes it; fails_when=the unknown-label warning or the sqlite3.Error guard is removed; why_new=only the not_fetched branch is covered (test_repersist); seam=none
    def test_the_summary_lists_sources_warns_on_a_new_label_and_survives_a_missing_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "store.sqlite"
            conn = pulse_store.connect(path)
            report = fixture_report()
            report["agenda_items"][0]["api"]["positions"] = [position("v1", "Gesetzgebung")]
            cache = cache_of({"v1": vorgang("Gesundheit", "Neues Gebiet")})
            pulse_store.persist_report(conn, report, cache)
            conn.close()
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                build.log_politikfelder_summary(path, cache)
                build.log_politikfelder_summary(Path(tmp) / "absent.sqlite", cache)
            lines = err.getvalue().splitlines()
        self.assertIn("politikfelder: TOPs: 1 sachgebiet, 1 untagged", lines)
        self.assertIn("politikfelder: Abstimmungen: 1 top", lines)
        self.assertEqual(sum(line.startswith("politikfelder: TOPs") for line in lines), 1)  # the absent store printed nothing
        self.assertTrue(any("'Neues Gebiet'" in line and "does not know" in line for line in lines), lines)
        self.assertFalse(any("not_fetched" in line for line in lines))


class RenderTests(unittest.TestCase):
    def report(self) -> dict[str, Any]:
        report = fixture_report()
        report["agenda_items"][0]["api"]["positions"] = [position("v1", "Gesetzgebung")]
        return report

    def test_the_dossier_shows_static_chips_and_none_for_an_untagged_top(self) -> None:
        report = self.report()
        before = copy.deepcopy(report)
        markup = pulse_html.render_html(report, vorgang_cache=cache_of({"v1": vorgang("Gesundheit", "Recht")}))
        self.assertIn('<ul class="pf-tags" aria-label="Politikfelder"><li class="pf-tag">Gesundheit</li><li class="pf-tag">Justiz</li></ul>', markup)
        self.assertEqual(markup.count('class="pf-tags"'), 1)  # the Fragestunde TOP has no chip
        self.assertNotIn("untagged", markup)
        self.assertEqual(report, before)  # nothing is written into the report

    # Value: protects=the cache main loads reaches the dossier page that write_report_files writes, and the cached report JSON stays free of tags; fails_when=write_report_files stops passing vorgang_cache to render_html, so pages ship with no chips while the unit tests stay green; why_new=every other render test calls render_html directly; seam=none
    def test_write_report_files_threads_the_cache_into_the_page_and_keeps_the_report_untagged(self) -> None:
        report = self.report()
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "data").mkdir()
            (Path(tmp) / "protocols").mkdir()
            entry = build.write_report_files(report, Path(tmp), vorgang_cache=cache_of({"v1": vorgang("Verkehr")}))
            self.assertIn('<li class="pf-tag">Verkehr</li>', entry["page_path"].read_text(encoding="utf-8"))
            self.assertNotIn("politikfeld", entry["report_path"].read_text(encoding="utf-8").lower())

    def test_no_cache_means_no_chips(self) -> None:
        self.assertNotIn('class="pf-tags"', pulse_html.render_html(self.report()))

    def archive_rows(self, cache: dict[str, Any] | None):
        entry = {"report": self.report(), "page_path": Path("plenarprotokoll-20-999.html")}
        return build.collect_votes_archive([entry], cache)

    def test_the_archive_rows_carry_the_votes_politikfelder_and_page_has_chips_and_filter(self) -> None:
        rows = self.archive_rows(cache_of({"v1": vorgang("Gesundheit", "Recht")}))
        self.assertEqual(rows[0]["politikfelder"], ["Gesundheit", "Justiz"])
        page = build.render_votes_archive_index(rows)
        self.assertIn('data-politikfeld-chip="Gesundheit"', page)
        self.assertIn('data-politikfeld-chip="Justiz"', page)
        self.assertNotIn('data-politikfeld-chip="Verkehr"', page)  # only fields a vote carries
        self.assertNotIn('data-politikfeld-chip="untagged"', page)
        self.assertIn("data-politikfelder='[&quot;Gesundheit&quot;, &quot;Justiz&quot;]'", page)
        self.assertIn("getAll('politikfeld')", page)
        self.assertIn('<li class="pf-tag">Gesundheit</li>', page)
        # Without script every row stays visible: nothing is hidden in the markup.
        self.assertNotIn(" hidden>", page.split('data-archive>')[1].split("data-no-results")[0])

    def test_the_archive_offers_untagged_as_a_filter_but_not_as_a_label(self) -> None:
        tagged = self.archive_rows(cache_of({"v1": vorgang("Gesundheit")}))[0]
        untagged = self.archive_rows(cache_of({"v1": vorgang()}, {"20/123": ["v1"], "20/456": ["v1"]}))[0]
        self.assertEqual(untagged["politikfelder"], [pf.UNTAGGED])
        # A cache miss is not "no Politikfeld": the page shows it as nothing, and the chip does not offer it.
        self.assertEqual(self.archive_rows(None)[0]["politikfelder"], [])
        page = build.render_votes_archive_index([tagged, untagged])
        self.assertIn('data-politikfeld-chip="untagged">Ohne Politikfeld</button>', page)
        self.assertEqual(page.count('class="pf-tag"'), 1)  # the untagged row gets no label
        # With no tag anywhere there is nothing to filter by, so no filter row.
        self.assertNotIn('data-politikfeld-chip="', build.render_votes_archive_index([untagged]))

    # Value: protects=the cache main loads reaches the pages render_site writes itself: the front page radar and, through the votes component, votes/index.html; fails_when=render_site stops handing vorgang_cache to render_front_page or to the component context (or the context key is renamed), so the live site ships without Politikfeld chips and filters while every direct-call render test stays green; why_new=the other render tests call render_html, write_report_files, collect_votes_archive and week_topic_rows directly; seam=none
    def test_render_site_threads_the_cache_into_the_front_page_and_the_votes_archive(self) -> None:
        report = self.report()
        report["agenda_items"][0]["xml_speakers"] = [
            {"speaker": {"name": "A", "faction": "SPD"}, "text": "x", "text_length": 1, "rede_id": "r1"}
        ]
        pages: dict[bool, tuple[str, str]] = {}
        for cached in (True, False):
            with tempfile.TemporaryDirectory() as tmp:
                output_dir = Path(tmp) / "site"
                for name in ("data", "protocols", "bills", "abgeordnete"):
                    (output_dir / name).mkdir(parents=True)
                report_path, page_path, slug = build.report_paths(output_dir, report["protocol"]["dokumentnummer"])
                entry = {"report": copy.deepcopy(report), "report_path": report_path, "page_path": page_path, "slug": slug}
                with contextlib.redirect_stderr(io.StringIO()):
                    build.render_site(
                        output_dir=output_dir, database_path=output_dir / "data" / "bundestag-pulse.sqlite", no_persist=True,
                        protocols=[report["protocol"]], entries=[entry], abg_mps=[], mp_lookup={}, today=date(2026, 9, 15),
                        vorgang_cache=cache_of({"v1": vorgang("Verkehr")}) if cached else None,
                    )
                pages[cached] = (
                    (output_dir / "puls.html").read_text(encoding="utf-8"),
                    (output_dir / "votes" / "index.html").read_text(encoding="utf-8"),
                )
        front, archive = pages[True]
        self.assertIn('data-radar-chip="Verkehr"', front)
        self.assertIn('data-politikfeld-chip="Verkehr"', archive)
        self.assertIn('<li class="pf-tag">Verkehr</li>', archive)
        self.assertRegex(front, r"@media \(pointer:coarse\)\s*\{[^}]+\}[^}]*\.radar-filter \.chip\s*\{ min-height:44px; \}")
        self.assertRegex(archive, r"@media \(pointer:coarse\)\s*\{\s*\.chip\s*\{ min-height:44px; \}")
        front_without, archive_without = pages[False]
        self.assertNotIn('data-radar-chip="', front_without)
        self.assertNotIn('data-politikfeld-chip="', archive_without)

    def test_the_radar_has_no_filter_when_nothing_is_tagged(self) -> None:
        self.assertEqual(build.render_radar_filter([{"politikfelder": []}, {"politikfelder": [pf.UNTAGGED]}]), "")

    def test_the_week_radar_rows_carry_chips_and_a_filter(self) -> None:
        report = self.report()
        report["agenda_items"][0]["xml_speakers"] = [
            {"speaker": {"name": "A", "faction": "SPD"}, "text": "x", "text_length": 1, "rede_id": "r1"}
        ]
        entry = {"report": report, "page_path": Path("plenarprotokoll-20-999.html")}
        radar = pulse_html.week_topic_rows(
            [entry], {}, total=1, dossier_href_for=lambda e: "protocols/x.html",
            vorgang_cache=cache_of({"v1": vorgang("Verkehr")}),
        )
        self.assertTrue(radar["rows"], "the fixture has a ranked speech")
        row = radar["rows"][0]
        self.assertEqual(row["politikfelder"], ["Verkehr"])
        markup = build.render_radar_section(radar, {"speech_count": 1}, build.publication_selection())
        self.assertIn('data-radar-chip="Verkehr"', markup)
        self.assertIn('<li class="pf-tag">Verkehr</li>', markup)
        self.assertIn("data-politikfelder='[&quot;Verkehr&quot;]'", markup)
        self.assertIn('<ul class="radar-list">', markup)


if __name__ == "__main__":
    unittest.main()
