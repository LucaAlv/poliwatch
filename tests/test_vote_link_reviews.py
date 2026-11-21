"""One-off drop and flag entries reach the store, the dossier and the bill page
(vote PR C2, docs/plans/vote-pr-c.md section 9; owner decision 2 in
docs/plans/vote-links-and-figures.md).

The fixture sitting 20/999 links vote 12345 to its TOP T1 ("TOP 1 Beratung
Testgesetz", page 101) by a printed Drucksache; T1 carries the bill vorgang-1.
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import _support
import build_dip_pulse_site as build
import persist_dip_pulse_store as pulse_store
import render_dip_pulse_html as page
import reviewed_vote_links as reviewed
import vote_links
from _support import FIXTURES


def fixture_report() -> dict[str, Any]:
    return _support.stamp_reviewed(json.loads((FIXTURES / "report.json").read_text(encoding="utf-8")))


def entry(**fields: Any) -> reviewed.Entry:
    raw = {"protocol": "20/999", "vote_id": "12345", "top_id": "T1", "top_occurrence": 1,
           "heading_starts": "TOP 1 Beratung Testgesetz", "page_start": 101,
           "verdict": "wrong", "pattern": "-", "action": "drop", "note": "Die Abstimmung galt dem Antrag unter TOP 2.",
           "evidence": "test", "reviewer": "test", "source": "sheet 2026-11-22"}
    raw.update(fields)
    return reviewed.check({"entries": [raw]})[0]


FLAG = {"verdict": "right", "action": "flag", "note": "Der Aufruf nennt die Drucksache nicht."}


class StoreTests(unittest.TestCase):
    def persist(self, conn, entries: list[reviewed.Entry]) -> None:
        report = fixture_report()
        with reviewed.using(entries):
            vote_links.attribute_votes(report)
            with conn:
                pulse_store.persist_report(conn, report)

    def rows(self, conn) -> dict[str, list[tuple]]:
        return {
            "links": [tuple(row) for row in conn.execute(
                "SELECT ai.top_id, aiv.vote_id, aiv.basis, aiv.review_note FROM agenda_item_votes aiv "
                "JOIN agenda_items ai ON ai.id = aiv.agenda_item_id ORDER BY ai.item_index")],
            "reviews": [tuple(row) for row in conn.execute(
                "SELECT vote_id, protocol, top_id, top_occurrence, heading, action, note, reviewed_on FROM vote_link_reviews")],
            "steps": [tuple(row) for row in conn.execute("SELECT id, top_link_step FROM votes")],
        }

    # Value: protects=a flag keeps the link and stores its note on it and in vote_link_reviews, a drop removes the link and keeps its record, and an edited entry reaches the store on the next persist without a re-read (plan sections 4 and 9); fails_when=persist ignores the entries, keeps a stale note or review row, or leaves a dropped link; why_new=vote PR C2 fills the column and table C1 created empty; seam=reviewed_vote_links.using
    def test_flag_and_drop_reach_the_store_and_follow_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                self.persist(conn, [])
                self.assertEqual(self.rows(conn), {"links": [("T1", "12345", "drucksache_xml", None)], "reviews": [],
                                                   "steps": [("12345", "match")]})
                self.persist(conn, [entry(**FLAG)])
                self.assertEqual(self.rows(conn), {
                    "links": [("T1", "12345", "drucksache_xml", FLAG["note"])],
                    "reviews": [("12345", "20/999", "T1", 1, "TOP 1 Beratung Testgesetz", "flag", FLAG["note"], "2026-11-22")],
                    "steps": [("12345", "match")]})
                self.persist(conn, [entry()])
                self.assertEqual(self.rows(conn), {
                    "links": [],
                    "reviews": [("12345", "20/999", "T1", 1, "TOP 1 Beratung Testgesetz", "drop",
                                 "Die Abstimmung galt dem Antrag unter TOP 2.", "2026-11-22")],
                    "steps": [("12345", "none")]})
                sittings = reviewed.sittings_of_store(conn)
                self.assertEqual(reviewed.problems([entry()], sittings["20/999"]), [])
                self.assertEqual(reviewed.problems([], sittings["20/999"]),
                                 ["20/999 vote 12345 T1 #1: the store holds a reviewed drop, but no acting entry of the file names it"])
                self.persist(conn, [])
                self.assertEqual(self.rows(conn)["reviews"], [])
                self.assertEqual(self.rows(conn)["links"], [("T1", "12345", "drucksache_xml", None)])
            finally:
                conn.close()

    # Value: protects=persist refuses a report placed before a drop entry took effect, so a cached placement cannot outlive the entry (choke point, plan section 7); fails_when=placement_errors ignores the entries; why_new=vote PR C2; seam=reviewed_vote_links.using
    def test_persist_refuses_a_placement_that_ignores_a_drop(self) -> None:
        report = fixture_report()
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                with reviewed.using([entry()]), self.assertRaisesRegex(ValueError, "vote 12345 sits under T1"):
                    pulse_store.persist_report(conn, report)
            finally:
                conn.close()

    # Value: protects=a stale drop stops the persist with the entry named (plan section 9: "a stale drop stops the run"); fails_when=the rebuild skips the entry and writes the rule's link; why_new=vote PR C2; seam=reviewed_vote_links.using
    def test_a_stale_drop_stops_the_rebuild(self) -> None:
        stale = entry(top_id="T2", heading_starts="TOP 2 Fragestunde", page_start=103)
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                with reviewed.using([stale]), self.assertRaisesRegex(
                        reviewed.ReviewedVoteLinksError, r"drop entry 20/999 vote 12345 T2 #1 no longer fits: the rule does not make this link"):
                    self.persist(conn, [stale])
            finally:
                conn.close()


class PageTests(unittest.TestCase):
    def html(self, entries: list[reviewed.Entry]) -> str:
        report = fixture_report()
        with reviewed.using(entries):
            vote_links.attribute_votes(report)
            return page.render_html(report)

    # Value: protects=the vote panel says a review flagged its TOP as unsure, with the note and the review date (decision 2); fails_when=a flagged link renders like any other; why_new=vote PR C2; seam=reviewed_vote_links.using
    def test_a_flag_shows_its_note_on_the_vote_panel(self) -> None:
        self.assertNotIn("vote-link-review", self.html([]))
        text = self.html([entry(**FLAG)])
        self.assertIn('<p class="vote-state-note vote-link-review">', text)
        self.assertIn("Die Zuordnung zu T1 ist nicht sicher geprüft (Prüfung vom 22.11.2026): "
                      "Der Aufruf nennt die Drucksache nicht.", text)

    # Value: protects=a dropped link is gone from the TOP's panel, the vote moves to the sitting's votes, and its panel says which TOP a review removed and why (decision 2); fails_when=the dropped vote still renders under its TOP or the line is missing; why_new=vote PR C2; seam=reviewed_vote_links.using
    def test_a_drop_moves_the_vote_off_its_top_and_says_so(self) -> None:
        text = self.html([entry()])
        self.assertIn("Ein Abgleich verband diese Abstimmung mit T1; die Prüfung vom 22.11.2026 ergab, dass sie nicht "
                      "dazu gehört: Die Abstimmung galt dem Antrag unter TOP 2.", text)
        self.assertNotIn("Zuordnung zu T1", text)
        report = fixture_report()
        with reviewed.using([entry()]):
            vote_links.attribute_votes(report)
        self.assertEqual(report["agenda_items"][0].get("votes") or [], [])

    # Value: protects=a drop on one of a vote's TOPs says the vote also sat under the dropped one, and each review gets its own line; fails_when=the linked wording is lost or a second review overwrites the first; why_new=fixtures link one TOP, so the linked branch never renders; seam=none; no_claim=the full page (calls the line renderer)
    def test_a_drop_on_a_vote_that_keeps_another_top_says_also(self) -> None:
        from features import votes

        drop, flag = reviewed.Review(entry(), 0), reviewed.Review(entry(**FLAG), 1)
        kept = votes._link_review_html([drop, flag], True)
        self.assertEqual(kept.count("vote-link-review"), 2)
        self.assertIn("verband diese Abstimmung auch mit T1;", kept)
        self.assertNotIn("auch mit", votes._link_review_html([drop], False))
        self.assertEqual(votes._link_review_html([], True), "")

    # Value: protects=a dropped link leaves the bill page of the TOP's Vorgang (plan section 9); fails_when=the bill page reads the vote from a placement the drop did not reach; why_new=vote PR C2; seam=reviewed_vote_links.using
    def test_a_drop_removes_the_vote_from_the_bill_page(self) -> None:
        for entries, expected in (([], ["12345"]), ([entry()], [])):
            report = fixture_report()
            with reviewed.using(entries):
                vote_links.attribute_votes(report)
            [bill] = build.collect_bill_pages([{"report": copy.deepcopy(report), "page_path": Path("p.html")}])
            self.assertEqual([vote["id"] for vote in bill["votes"]], expected)


if __name__ == "__main__":
    unittest.main()
