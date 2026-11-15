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

import _support  # noqa: F401
import build_dip_pulse_site as build
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
        return vote_links.top_links(copy.deepcopy(ITEMS), votes)

    def test_a_printed_number_is_drucksache_xml_and_wins_over_a_dip_number_of_the_same_top(self) -> None:
        self.assertEqual(self.links(vote("1", "Rente", "21/10", "21/11")), {"1": {0: "drucksache_xml"}})

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

    def test_a_report_without_a_list_keeps_the_order_it_holds(self) -> None:
        carried = report(copy.deepcopy(ITEMS), [])
        carried["api_records"] = {}
        carried["agenda_items"][0]["votes"] = [vote("9", "Rente", "21/10"), vote("10", "Rente 2", "21/10")]
        vote_links.attribute_votes(carried)
        self.assertEqual([v["id"] for v in carried["agenda_items"][0]["votes"]], ["9", "10"])


def fixture_report() -> dict[str, Any]:
    """The fixture sitting: TOP 1 prints 20/123 and links 20/456; its vote 12345 shares 20/123."""
    return json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))


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
