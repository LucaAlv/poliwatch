"""The reviewed vote links: the file's refusals, whether an entry still holds,
and the release condition (docs/plans/vote-pr-c.md sections 4 and 5)."""

from __future__ import annotations

import collections
import copy
import json
import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401
import reviewed_vote_links as reviewed
from reviewed_vote_links import ReviewedVoteLinksError, Sitting


def raw(**fields) -> dict:
    entry = {"protocol": "21/45", "vote_id": "980", "top_id": "Tagesordnungspunkt II", "top_occurrence": 1,
             "heading_starts": "Dritte Beratung des von der Bundesregier", "page_start": 5000,
             "verdict": "right", "pattern": "-", "action": "none", "note": "", "evidence": "the chair calls it here",
             "reviewer": "agent pass 1", "source": "sheet 2026-11-21"}
    entry.update(fields)
    return entry


def sitting(links: set[tuple[str, int]], steps: dict[str, str] | None = None) -> Sitting:
    """21/45: TOP I (Haushaltsgesetz), TOP II (third reading), TOP I again (an Einzelplan)."""
    return Sitting("21/45", [("Tagesordnungspunkt I", "Zweite Beratung des Haushaltsgesetzes", 4900),
                             ("Tagesordnungspunkt II", "Dritte Beratung des von der Bundesregierung eingebrachten", 5000),
                             ("Tagesordnungspunkt I", "Einzelplan 04 Bundeskanzleramt", 4950)],
                   {"980", "981", "982"}, links, steps or {})


class FileTests(unittest.TestCase):
    def refused(self, data, message: str) -> None:
        with self.assertRaisesRegex(ReviewedVoteLinksError, message):
            reviewed.check(data)

    def test_a_well_formed_entry_loads_and_round_trips(self) -> None:
        [entry] = reviewed.check({"entries": [raw()]})
        self.assertEqual(entry.key, ("21/45", "980", "Tagesordnungspunkt II", 1))
        self.assertEqual(reviewed.parse(reviewed.dump([entry])), [entry])

    # Value: protects=every malformed entry stops the run with its position and field named (checklist class 9); fails_when=a wrong type, blank, over-long or unknown value is accepted or raises a traceback; why_new=the file is new in PR C; seam=none
    def test_malformed_entries_are_refused_by_name(self) -> None:
        cases = [
            ([], 'exactly one key, "entries"'),
            ({"entries": [raw(extra=1)]}, "exactly the keys"),
            ({"entries": [{k: v for k, v in raw().items() if k != "note"}]}, "exactly the keys"),
            ({"entries": [raw(protocol="21-45")]}, "not WP/NR"),
            ({"entries": [raw(protocol=None)]}, "protocol must be a string"),
            ({"entries": [raw(vote_id="")]}, "vote_id must not be empty"),
            ({"entries": [raw(top_id=" TOP 1")]}, "leading, trailing or repeated whitespace"),
            ({"entries": [raw(top_occurrence=0)]}, "top_occurrence"),
            ({"entries": [raw(top_occurrence=True)]}, "top_occurrence"),
            ({"entries": [raw(top_occurrence="1")]}, "top_occurrence"),
            ({"entries": [raw(heading_starts="x" * 41)]}, "more than 40"),
            ({"entries": [raw(page_start="5000")]}, "page_start"),
            ({"entries": [raw(page_start=-1)]}, "page_start"),
            ({"entries": [raw(verdict="unsure")]}, "verdict 'unsure'"),
            ({"entries": [raw(pattern="E")]}, "pattern 'E'"),
            ({"entries": [raw(action="keep")]}, "action 'keep'"),
            ({"entries": [raw(verdict="wrong")]}, "a wrong link cannot have action none"),
            ({"entries": [raw(action="rule")]}, "a right link cannot have action rule"),
            ({"entries": [raw(verdict="wrong", action="rule")]}, "needs a pattern A to D"),
            ({"entries": [raw(pattern="A")]}, "needs a pattern A to D, and only it"),
            ({"entries": [raw(verdict="wrong", action="drop", note="")]}, "note must not be empty"),
            ({"entries": [raw(verdict="wrong", action="drop", note="ein Einzelfall")]}, "vote PR C2"),
            ({"entries": [raw(action="flag", note="unsicher")]}, "vote PR C2"),
            ({"entries": [raw(source="by hand")]}, "source"),
            ({"entries": [raw(evidence="x" * 4001)]}, "at most 4000"),
            ({"entries": [raw(), raw(evidence="again")]}, "listed twice"),
        ]
        for data, message in cases:
            with self.subTest(message=message):
                self.refused(data, message)

    def test_a_missing_or_unreadable_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ReviewedVoteLinksError, "is missing; it is checked in"):
                reviewed.load(Path(tmp) / "reviewed_vote_links.json")
            broken = Path(tmp) / "broken.json"
            broken.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ReviewedVoteLinksError, "not valid JSON"):
                reviewed.load(broken)
            deep = Path(tmp) / "deep.json"
            deep.write_text("[" * 100000 + "]" * 100000, encoding="utf-8")
            with self.assertRaisesRegex(ReviewedVoteLinksError, "not valid JSON|exactly one key"):
                reviewed.load(deep)

    def test_the_shipped_file_holds_the_review(self) -> None:
        entries = reviewed.load()
        self.assertEqual(len(entries), 428)
        self.assertEqual(collections.Counter((e.verdict, e.pattern) for e in entries),
                         {("right", "-"): 376, ("wrong", "A"): 43, ("wrong", "B"): 2, ("wrong", "C"): 2, ("wrong", "D"): 5})
        self.assertEqual(collections.Counter(e.source for e in entries), {"sheet 2026-11-21": 408, "plan vote-pr-c": 20})
        self.assertEqual(reviewed.load(), reviewed.parse(reviewed.dump(entries)))


class ProblemsTests(unittest.TestCase):
    def entry(self, **fields):
        return reviewed.check({"entries": [raw(**fields)]})[0]

    def test_a_holding_entry_has_no_problem(self) -> None:
        self.assertEqual(reviewed.problems([self.entry()], sitting({("980", 1)})), [])
        wrong = self.entry(verdict="wrong", pattern="A", action="rule", top_id="Tagesordnungspunkt I", top_occurrence=2,
                           heading_starts="Einzelplan 04", page_start=4950)
        self.assertEqual(reviewed.problems([wrong], sitting({("980", 1)})), [])

    def test_each_way_an_entry_stops_holding_is_named(self) -> None:
        made = sitting({("980", 1), ("980", 2)})
        cases = [
            (self.entry(), sitting(set()), "the rule no longer makes the link"),
            (self.entry(verdict="wrong", pattern="A", action="rule", top_id="Tagesordnungspunkt I", top_occurrence=2,
                        heading_starts="Einzelplan 04", page_start=4950), made, "reviewed wrong, but the rule makes the link"),
            (self.entry(vote_id="999"), made, "holds no vote 999"),
            (self.entry(top_occurrence=2), made, "holds no such TOP"),
            (self.entry(heading_starts="Zweite Beratung"), made, "heading no longer starts"),
            (self.entry(page_start=5001), made, "starts on page 5000, not 5001"),
        ]
        for entry, state, message in cases:
            with self.subTest(message=message):
                [problem] = reviewed.problems([entry], state)
                self.assertIn(message, problem)

    def test_an_entry_of_another_sitting_is_not_checked_here(self) -> None:
        self.assertEqual(reviewed.problems([self.entry(protocol="21/44")], sitting(set())), [])


class GateTests(unittest.TestCase):
    """The release condition (section 5): every contested vote's links reviewed right."""

    def entries(self, *fields: dict):
        return reviewed.check({"entries": [raw(**f) for f in fields]})

    # Value: protects=a vote a later step decided, or one linked to two TOPs, cannot be released without a reviewed entry for each link; fails_when=the gate keys on two or more TOPs only (decision 6 as first written) or skips a step; why_new=owner decision of 2026-11-21 (plan section 13); seam=none
    def test_an_unreviewed_contested_vote_is_refused_for_each_step_and_two_links(self) -> None:
        for step in ("call", "einzelplan", "narrowed"):
            with self.subTest(step=step):
                result = reviewed.gate([], {"21/45": sitting({("981", 1)}, {"981": step})})
                self.assertEqual(result["refusals"], [f"21/45 vote 981 Tagesordnungspunkt II #1: contested link ({step}, 1 TOP(s)) has no reviewed entry"])
                self.assertEqual(result["contested"], 1)
        two = reviewed.gate([], {"21/45": sitting({("981", 0), ("981", 1)}, {"981": "match"})})
        self.assertEqual(len(two["refusals"]), 2)
        plain = reviewed.gate([], {"21/45": sitting({("982", 0)}, {"982": "match"})})
        self.assertEqual((plain["refusals"], plain["contested"]), ([], 0))

    def test_a_reviewed_contested_vote_passes_and_a_wrong_or_stale_entry_is_refused(self) -> None:
        state = {"21/45": sitting({("980", 1)}, {"980": "narrowed"})}
        self.assertEqual(reviewed.gate(self.entries({}), state)["refusals"], [])
        wrong_made = self.entries({"verdict": "wrong", "pattern": "A", "action": "rule"})
        refusals = reviewed.gate(wrong_made, state)["refusals"]
        self.assertIn("21/45 vote 980 Tagesordnungspunkt II #1: contested link is reviewed wrong", refusals)
        self.assertIn("21/45 vote 980 Tagesordnungspunkt II #1: reviewed wrong, but the rule makes the link", refusals)
        moved_page = reviewed.gate(self.entries({"page_start": 4999}), state)["refusals"]
        self.assertEqual(moved_page, ["21/45 vote 980 Tagesordnungspunkt II #1: the TOP starts on page 5000, not 4999"])
        # A plain vote's stale entry refuses too: the release ships no broken review.
        plain = {"21/45": sitting(set(), {"980": "none"})}
        self.assertEqual(reviewed.gate(self.entries({}), plain)["refusals"],
                         ["21/45 vote 980 Tagesordnungspunkt II #1: reviewed right, but the rule no longer makes the link"])

    def test_entries_of_sittings_outside_the_store_are_skipped_and_counted(self) -> None:
        result = reviewed.gate(self.entries({}, {"protocol": "18/1"}), {"21/45": sitting({("980", 1)})})
        self.assertEqual((result["reviewed"], result["skipped"], result["refusals"]), (1, 1, []))


if __name__ == "__main__":
    unittest.main()
