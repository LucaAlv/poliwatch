from __future__ import annotations

import unittest
from datetime import date

import _support  # noqa: F401
import release_version as rv


class VersionSchemeTests(unittest.TestCase):
    # Value: protects=the default scheme: a calendar version, .2/.3 for further releases of the same day, other days ignored; fails_when=a second release of a day reuses the first version or a different day's version raises the counter; why_new=the owner may still change the scheme and this pins today's; seam=next_version; no_claim=the scheme being the right one
    def test_next_version_is_the_date_with_a_counter_for_the_same_day(self) -> None:
        today = date(2026, 11, 1)
        self.assertEqual(rv.next_version(today, []), "2026.11.01")
        self.assertEqual(rv.next_version(today, ["2026.10.31", "2026.11.02"]), "2026.11.01")
        self.assertEqual(rv.next_version(today, ["2026.11.01"]), "2026.11.01.2")
        self.assertEqual(rv.next_version(today, ["2026.11.01", "2026.11.01.2"]), "2026.11.01.3")
        self.assertEqual(rv.next_version(today, ["2026.11.01.9", "2026.11.01"]), "2026.11.01.10")
        self.assertEqual(rv.next_version(today, ["not-a-version", "data-2026.11.01"]), "2026.11.01")

    def test_only_real_calendar_versions_are_versions(self) -> None:
        for good in ("2026.11.01", "2026.11.01.2", "2026.11.01.10", "2024.02.29"):
            with self.subTest(good=good):
                self.assertTrue(rv.is_version(good))
        for bad in ("local", "v1", "2026.13.01", "2026.02.30", "2026.11.1", "2026.11.01.1", "2026.11.01.0", "2026.11.01.", "2026.11.01.2.3", "2026.11.01\n", None, 20261101):
            with self.subTest(bad=bad):
                self.assertFalse(rv.is_version(bad))

    def test_tags_and_ordering(self) -> None:
        self.assertEqual(rv.tag_for("2026.11.01"), "data-2026.11.01")
        self.assertEqual(rv.version_of("data-2026.11.01.2"), "2026.11.01.2")
        self.assertIsNone(rv.version_of("v1.0"))
        self.assertIsNone(rv.version_of("data-local"))
        versions = ["2026.11.01.10", "2026.11.01", "2026.11.01.2", "2026.10.31"]
        self.assertEqual(sorted(versions, key=rv.version_key), ["2026.10.31", "2026.11.01", "2026.11.01.2", "2026.11.01.10"])
        with self.assertRaises(ValueError):
            rv.version_key("local")


if __name__ == "__main__":
    unittest.main()
