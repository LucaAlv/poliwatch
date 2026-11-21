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
            ({"entries": [raw(action="flag", note="")]}, "note must not be empty"),
            ({"entries": [raw(action="drop", note="ein Einzelfall")]}, "a right link cannot have action drop"),
            ({"entries": [raw(verdict="wrong", pattern="D", action="drop", note="ein Einzelfall")]}, "needs a pattern A to D, and only it"),
            ({"entries": [raw(pattern="A", action="flag", note="unsicher")]}, "needs a pattern A to D, and only it"),
            ({"entries": [raw(verdict="wrong", action="drop", note="ein Einzelfall", source="plan vote-pr-c")]},
             "a drop entry needs the date of its review"),
            ({"entries": [raw(action="flag", note="unsicher", source="plan vote-pr-c")]}, "a flag entry needs the date of its review"),
            ({"entries": [raw(source="by hand")]}, "source"),
            ({"entries": [raw(evidence="x" * 4001)]}, "at most 4000"),
            ({"entries": [raw(), raw(evidence="again")]}, "listed twice"),
        ]
        for data, message in cases:
            with self.subTest(message=message):
                self.refused(data, message)

    # Value: protects=a drop and a flag load as acting entries with their review date (vote PR C2); fails_when=the loader still refuses them or loses the date the vote page names; why_new=C2 lets one-off entries act; seam=none
    def test_drop_and_flag_entries_load_with_their_review_date(self) -> None:
        drop, flag = reviewed.check({"entries": [
            raw(verdict="wrong", action="drop", note="gehört zu TOP I"),
            raw(vote_id="981", action="flag", note="Aufruf unklar", source="sheet 2026-11-30")]})
        self.assertEqual((drop.action, drop.reviewed_on), ("drop", "2026-11-21"))
        self.assertEqual((flag.action, flag.reviewed_on), ("flag", "2026-11-30"))
        self.assertEqual(reviewed.parse(reviewed.dump([drop, flag])), [drop, flag])

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

    # Value: protects=a drop holds where its link is gone and the store keeps its record, a flag where the link stays with the entry's note (plan section 4 table); fails_when=problems reads a drop or flag by its verdict alone; why_new=vote PR C2; seam=none
    def test_a_holding_drop_and_flag_have_no_problem(self) -> None:
        key = ("21/45", "980", "Tagesordnungspunkt II", 1)
        drop = self.entry(verdict="wrong", action="drop", note="gehört nicht dazu")
        dropped = sitting(set())
        dropped.reviews = {key: ("drop", "gehört nicht dazu")}
        self.assertEqual(reviewed.problems([drop], dropped), [])
        flag = self.entry(action="flag", note="Aufruf unklar")
        flagged = sitting({("980", 1)})
        flagged.notes = {("980", 1): "Aufruf unklar"}
        flagged.reviews = {key: ("flag", "Aufruf unklar")}
        self.assertEqual(reviewed.problems([flag], flagged), [])
        wrong_flag = self.entry(verdict="wrong", action="flag", note="Aufruf unklar")
        self.assertEqual(reviewed.problems([wrong_flag], flagged), [])

    # Value: protects=a stale drop or flag in the store fails the store gate and the release like a stale verdict (plan section 4: "the store gate and the release refuse for any entry"); fails_when=a made dropped link, a lost or re-noted flag, or a review the file no longer names passes; why_new=vote PR C2; seam=none
    def test_each_way_a_drop_or_flag_stops_holding_is_named(self) -> None:
        key = ("21/45", "980", "Tagesordnungspunkt II", 1)
        drop = self.entry(verdict="wrong", action="drop", note="gehört nicht dazu")
        flag = self.entry(action="flag", note="Aufruf unklar")

        def state(links, notes=None, reviews=None):
            made = sitting(links)
            made.notes, made.reviews = notes or {}, reviews or {}
            return made

        cases = [
            ([drop], state({("980", 1)}, reviews={key: ("drop", "gehört nicht dazu")}), "dropped, but the link is made"),
            ([drop], state(set()), "holds no record of the drop"),
            ([flag], state(set(), reviews={key: ("flag", "Aufruf unklar")}), "flagged, but the link is not made"),
            ([flag], state({("980", 1)}, {("980", 1): "anders"}, {key: ("flag", "Aufruf unklar")}), "carries the note 'anders'"),
            ([flag], state({("980", 1)}, {("980", 1): "Aufruf unklar"}), "holds no record of the flag"),
            ([], state(set(), reviews={key: ("drop", "gehört nicht dazu")}), "no acting entry of the file names it"),
            ([], state({("980", 1)}, {("980", 1): "Aufruf unklar"}), "no acting entry of the file names it"),
            ([self.entry()], state({("980", 1)}, {("980", 1): "Aufruf unklar"}), "no acting entry of the file names it"),
        ]
        for entries, made, message in cases:
            with self.subTest(message=message):
                found = reviewed.problems(entries, made)
                self.assertEqual(len(found), 1, found)
                self.assertIn(message, found[0])

    def test_store_rows_carry_the_notes_and_the_review_records(self) -> None:
        sittings = reviewed.sittings_of_rows(
            [("p1", "21/45")],
            [("a", "p1", "0", "Tagesordnungspunkt I", "Zweite Beratung", "4900"),
             ("b", "p1", "1", "Tagesordnungspunkt II", "Dritte Beratung", "5000")],
            [("980", "p1", "match"), ("981", "p1", "none")],
            [("b", "980", "Aufruf unklar"), ("a", "980", "")],
            [("980", "21/45", "Tagesordnungspunkt II", "1", "flag", "Aufruf unklar"),
             ("981", "21/45", "Tagesordnungspunkt I", "1", "drop", "gehört nicht dazu")])
        made = sittings["21/45"]
        self.assertEqual(made.notes, {("980", 1): "Aufruf unklar"})
        self.assertEqual(made.reviews, {("21/45", "980", "Tagesordnungspunkt II", 1): ("flag", "Aufruf unklar"),
                                        ("21/45", "981", "Tagesordnungspunkt I", 1): ("drop", "gehört nicht dazu")})

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

    # Value: protects=a contested link reviewed as unsure (flag) may be released with its note, and a dropped link leaves nothing to gate (decision 2); fails_when=the gate refuses a flagged link or a holding drop; why_new=vote PR C2; seam=none
    def test_a_flagged_contested_link_and_a_holding_drop_pass(self) -> None:
        key = ("21/45", "980", "Tagesordnungspunkt II", 1)
        flagged = sitting({("980", 1)}, {"980": "narrowed"})
        flagged.notes, flagged.reviews = {("980", 1): "unsicher"}, {key: ("flag", "unsicher")}
        result = reviewed.gate(self.entries({"verdict": "wrong", "action": "flag", "note": "unsicher"}), {"21/45": flagged})
        self.assertEqual((result["refusals"], result["contested"]), ([], 1))
        dropped = sitting(set(), {"980": "none"})
        dropped.reviews = {key: ("drop", "nicht dazu")}
        result = reviewed.gate(self.entries({"verdict": "wrong", "action": "drop", "note": "nicht dazu"}), {"21/45": dropped})
        self.assertEqual((result["refusals"], result["contested"]), ([], 0))

    def test_entries_of_sittings_outside_the_store_are_skipped_and_counted(self) -> None:
        result = reviewed.gate(self.entries({}, {"protocol": "18/1"}), {"21/45": sitting({("980", 1)})})
        self.assertEqual((result["reviewed"], result["skipped"], result["refusals"]), (1, 1, []))


if __name__ == "__main__":
    unittest.main()


class ReviewParagraphTests(unittest.TestCase):
    """What DATA.md says about who reviewed the links must match the entries."""

    def test_the_paragraph_names_the_agent_readers_not_a_hand_review(self) -> None:
        import build_dip_pulse_site as b

        entries = reviewed.load()
        # The sheet's verdicts were read by agents (vote-links-review-summary.md, "Outcome of passes 1 and 2").
        self.assertTrue(all("Sonnet" in entry.reviewer for entry in entries if entry.source.startswith("sheet ")))
        text = b.vote_link_review_paragraph(entries)
        self.assertNotIn("von Hand", text)
        self.assertIn("KI-Agenten", text)

    # Value: protects=DATA.md counts the one-off drops and flags from the entries, and says nothing of them while none acts; fails_when=the paragraph omits acting entries or names them when there are none; why_new=vote PR C2; seam=none
    def test_the_paragraph_counts_drops_and_flags_only_when_there_are_some(self) -> None:
        import build_dip_pulse_site as b

        self.assertNotIn("Einzelfall", b.vote_link_review_paragraph(reviewed.load()))
        acting = reviewed.check({"entries": [raw(verdict="wrong", action="drop", note="nicht dazu"),
                                             raw(vote_id="981", action="flag", note="unsicher")]})
        self.assertIn("Als Einzelfall entfernt sind 1 Verknüpfungen, als nicht sicher geprüft markiert 1",
                      b.vote_link_review_paragraph(acting))
