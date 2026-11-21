"""The CI oracle of the vote-link review (docs/plans/vote-pr-c.md, section 6).

``vote_links.links`` runs on every sitting that holds a reviewed entry, frozen in
``tests/fixtures/vote_links/reviewed-sittings.json.gz`` (``vote_link_review.py
--fixture``), and every entry must hold: a right link made, a wrong one not.
A later rule change that moves a reviewed link fails here, without a store.
It cannot see a change in the rule's inputs (the parser, DIP), which the
fixture freezes, nor a sitting without an entry: the replay comparison and the
store gate cover those.
"""

from __future__ import annotations

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
        cls.sittings = {number: reviewed.sitting_of_report(report, vote_links.links(report)) for number, report in cls.frozen.items()}

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


if __name__ == "__main__":
    unittest.main()
