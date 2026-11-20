"""The panel's note on re-filed members never prints a missing group as "None"."""

from __future__ import annotations

import unittest

import _support  # noqa: F401
from features import votes


class RefiledNoteTests(unittest.TestCase):
    # Value: protects=a re-filed member whose own group is missing reads "dort Unbekannt", the label the member grid uses; fails_when=the note interpolates the missing faction; why_new=the note read "(dort None)"; seam=_refiled_note_html
    def test_a_moved_member_without_a_faction_is_not_printed_as_none(self) -> None:
        for faction in (None, ""):
            note = votes._refiled_note_html(
                {"members": [{"name": "Kamann, Uwe", "faction": faction, "refiled_to": "AfD"}]}
            )
            self.assertIn("Kamann, Uwe bei AfD (dort Unbekannt)", note)
            self.assertNotIn("None", note)

    def test_a_moved_member_with_a_faction_keeps_it(self) -> None:
        note = votes._refiled_note_html(
            {"members": [{"name": "Kamann, Uwe", "faction": "fraktionslos", "refiled_to": "AfD"}]}
        )
        self.assertIn("Kamann, Uwe bei AfD (dort fraktionslos)", note)


if __name__ == "__main__":
    unittest.main()
