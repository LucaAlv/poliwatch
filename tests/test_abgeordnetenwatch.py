from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401
import abgeordnetenwatch as aw


class AbgeordnetenwatchPartyTests(unittest.TestCase):
    def test_party_tokens_handle_common_variants(self) -> None:
        self.assertEqual(aw._party_tokens("CDU/CSU"), {"cdu", "csu"})
        self.assertEqual(aw._party_tokens("B\u00fcndnis 90/Die Gr\u00fcnen"), {"gruene"})
        self.assertEqual(aw._party_tokens("B\u00fcndnis 90/Die Gr\u00fc\u00adnen"), {"gruene"})
        self.assertEqual(aw._party_tokens("DIE LINKE"), {"linke"})

    def test_party_matches_common_variants(self) -> None:
        self.assertTrue(aw._party_matches("CDU/CSU", "CSU"))
        self.assertTrue(aw._party_matches("B90/Gr\u00fcne", "B\u00fcndnis 90/Die Gr\u00fcnen"))
        self.assertTrue(aw._party_matches("Die Linke", "DIE LINKE"))
        self.assertFalse(aw._party_matches("SPD", "FDP"))


class AbgeordnetenwatchCacheTests(unittest.TestCase):
    def test_cache_round_trip_resolves_ext_id_without_network(self) -> None:
        profile = {
            "id": 77,
            "label": "Ada Lovelace",
            "url": "https://www.abgeordnetenwatch.de/profile/ada-lovelace",
            "party": "SPD",
            "match": "ext_id",
        }

        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "aw-cache.json"
            resolver = aw.AbgeordnetenwatchResolver(cache_path=cache_path, sleep_seconds=0)
            resolver._by_ext_id["11001"] = profile
            resolver._dirty = True
            resolver.save()

            reloaded = aw.AbgeordnetenwatchResolver(cache_path=cache_path, sleep_seconds=0)
            self.assertEqual(reloaded.resolve(ext_id="11001"), profile)
            self.assertEqual(reloaded.stats["api_calls"], 0)
            self.assertEqual(reloaded.stats["ext_id"], 1)


if __name__ == "__main__":
    unittest.main()

