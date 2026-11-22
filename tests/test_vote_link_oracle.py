"""The CI oracle of the vote-link review (docs/plans/vote-pr-c.md, section 6).

``vote_links.links`` runs on every sitting that holds a reviewed entry, frozen in
``tests/fixtures/vote_links/reviewed-sittings.json.gz`` (``vote_link_review.py
--fixture``), and every entry must hold: a right link made, a wrong one not.
A drop must be made by the rule and removed, a flag made and carrying its note.
A later rule change that moves a reviewed link fails here, without a store.
It cannot see a change in the rule's inputs (the parser, DIP), which the
fixture freezes, nor a sitting without an entry: the replay comparison and the
store gate cover those.
"""

from __future__ import annotations

import copy
import gzip
import json
import unittest

import _support
import reviewed_vote_links as reviewed
import vote_links

FIXTURE = _support.FIXTURES / "vote_links" / "reviewed-sittings.json.gz"


def frozen_sittings() -> dict[str, dict]:
    sittings = json.loads(gzip.decompress(FIXTURE.read_bytes()))["sittings"]
    return {sitting["protocol"]["dokumentnummer"]: sitting for sitting in sittings}


class OracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.entries = reviewed.load()
        cls.frozen = frozen_sittings()
        cls.sittings = {number: reviewed.sitting_of_report(report, *vote_links.reviewed_links(report, cls.entries))
                        for number, report in cls.frozen.items()}

    def test_every_sitting_with_an_entry_is_frozen(self) -> None:
        self.assertEqual(set(self.frozen), {entry.protocol for entry in self.entries})

    # Value: protects=every reviewed verdict holds under the current rule, sitting by sitting, in CI without a store; fails_when=a rule change makes a reviewed wrong link again or loses a reviewed right one; why_new=PR C turns the review into a regression test; seam=none
    def test_every_reviewed_link_holds(self) -> None:
        problems = [problem for number, sitting in sorted(self.sittings.items())
                    for problem in reviewed.problems(self.entries, sitting)]
        self.assertEqual(problems, [], "a rule change moved a reviewed link; the message names the sitting and the TOP")

    def test_every_contested_vote_of_the_frozen_sittings_is_reviewed(self) -> None:
        result = reviewed.gate(self.entries, self.sittings)
        self.assertEqual(result["refusals"], [])
        self.assertEqual(result["contested"], 35)


def acting(report: dict, vote_id: str, position: int, **fields) -> reviewed.Entry:
    """An acting entry for the link of ``vote_id`` to the TOP at ``position`` of a frozen sitting."""
    item = report["agenda_items"][position]
    top_id = item["top_id"]
    occurrence = sum(1 for other in report["agenda_items"][:position + 1] if other["top_id"] == top_id)
    entry = {"protocol": report["protocol"]["dokumentnummer"], "vote_id": vote_id, "top_id": top_id,
             "top_occurrence": occurrence, "heading_starts": reviewed.heading_start(item.get("heading")),
             "page_start": reviewed.page_of((item.get("page_range") or {}).get("start")),
             "verdict": "wrong", "pattern": "-", "action": "drop", "note": "gehört zu einem anderen Abschnitt",
             "evidence": "test", "reviewer": "test", "source": "sheet 2026-11-22"}
    entry.update(fields)
    return reviewed.check({"entries": [entry]})[0]


class ActingEntryTests(unittest.TestCase):
    """Drop and flag entries acting on real frozen sittings (vote PR C2): 21/45
    links vote 980 to TOP II (position 8) alone; 18/18 links 254 to TOP 16."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.frozen = frozen_sittings()

    def sitting(self, number: str) -> dict:
        return copy.deepcopy(self.frozen[number])

    # Value: protects=a drop removes the link the rule makes, the vote falls back to its sitting, and the review is kept for the vote page (decision 2); fails_when=a drop entry has no effect, or the dropped vote vanishes from the sitting; why_new=vote PR C2; seam=reviewed_vote_links.use
    def test_a_drop_removes_the_rule_s_link_and_keeps_its_record(self) -> None:
        report = self.sitting("21/45")
        self.assertEqual(vote_links.links(report)["980"], ({8: "drucksache_xml"}, "narrowed"))
        drop = acting(report, "980", 8)
        placed, reviews = vote_links.reviewed_links(report, [drop])
        self.assertEqual(placed["980"], ({}, "none"))
        self.assertEqual([(review.entry, review.position) for review in reviews], [(drop, 8)])
        with reviewed.using([drop]):
            vote_links.attribute_votes(report)
            self.assertEqual(vote_links.placement_errors(report), [])
        self.assertEqual(report["agenda_items"][8].get("votes") or [], [])
        self.assertEqual([vote["id"] for vote in report["sitting_votes"]], ["980"])
        made = reviewed.sitting_of_report(report, placed, reviews)
        self.assertEqual(reviewed.problems([drop], made), [])

    # Value: protects=a flag keeps the link and carries the entry's note (decision 2); fails_when=a flag drops the link or loses its note; why_new=vote PR C2; seam=none
    def test_a_flag_keeps_the_link_and_carries_its_note(self) -> None:
        report = self.sitting("18/18")
        rule = vote_links.links(report)
        [position] = rule["254"].tops
        flag = acting(report, "254", position, verdict="right", action="flag", note="Aufruf nicht eindeutig")
        placed, reviews = vote_links.reviewed_links(report, [flag])
        self.assertEqual(placed, rule)
        self.assertEqual([(review.entry.action, review.position, review.entry.note) for review in reviews],
                         [("flag", position, "Aufruf nicht eindeutig")])
        made = reviewed.sitting_of_report(report, placed, reviews)
        self.assertEqual(made.notes, {("254", position): "Aufruf nicht eindeutig"})
        self.assertEqual(reviewed.problems([flag], made), [])

    # Value: protects=a drop or flag the rule no longer needs, or one that no longer fits its TOP, stops the run until it is deleted (plan section 4, the reviewed_units model); fails_when=a stale acting entry is silently ignored; why_new=vote PR C2; seam=none
    def test_a_stale_drop_or_flag_stops_the_run(self) -> None:
        report = self.sitting("21/45")
        # TOP I.19 (position 1) is a reviewed wrong link the rule no longer makes.
        cases = [
            (acting(report, "980", 1), "the rule does not make this link"),
            (acting(report, "980", 1, verdict="right", action="flag", note="unsicher"), "the rule does not make this link"),
            (acting(report, "980", 8, heading_starts="Zweite Beratung"), "heading no longer starts"),
            (acting(report, "980", 8, action="flag", note="unsicher", page_start=5248), "starts on page 5247, not 5248"),
            (acting(report, "999", 8), "holds no vote 999"),
            (acting(report, "980", 8, action="flag", note="unsicher", top_occurrence=3), "holds no such TOP"),
        ]
        for entry, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(reviewed.ReviewedVoteLinksError, message):
                    vote_links.links(copy.deepcopy(report), [entry])
                with reviewed.using([entry]), self.assertRaisesRegex(reviewed.ReviewedVoteLinksError, "delete or correct the entry"):
                    vote_links.attribute_votes(copy.deepcopy(report))

    def test_an_entry_that_does_not_act_or_names_another_sitting_changes_nothing(self) -> None:
        report = self.sitting("21/45")
        rule = vote_links.links(report)
        other = acting(self.sitting("18/18"), "254", 0, top_id="Tagesordnungspunkt 16")
        self.assertEqual(vote_links.reviewed_links(report, [*reviewed.load(), other]), (rule, []))


if __name__ == "__main__":
    unittest.main()
