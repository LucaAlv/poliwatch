from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


def _mandate(period_id: int, period_label: str, constituency: str, electoral_list: str) -> dict:
    return {
        "parliament_period": {"id": period_id, "label": period_label},
        "electoral_data": {"constituency": {"label": constituency}, "electoral_list": {"label": electoral_list}},
    }


BUNDESTAG = _mandate(111, "Bundestag 2017 - 2021", "174 - Fulda (Bundestag 2017 - 2021)",
                     "Landesliste Hessen (Bundestag 2017 - 2021)")
LANDTAG = _mandate(150, "Hessen 2023 - 2028", "Fulda I (Hessen 2023 - 2028)", "Landesliste Hessen 2023")


class AbgeordnetenwatchBioTests(unittest.TestCase):
    # Value (Former-MPs answer, O3): protects=a former MdB who moved to a Landtag keeps the
    # Bundestag Wahlkreis, also when the cache was filled by the old rule; fails_when=the newest
    # mandate wins regardless of parliament, or a cached Landtag pick survives an upgrade;
    # seam=AbgeordnetenwatchResolver.fetch_bio; no_claim=every real aw mandate shape.
    def test_a_landtag_mandate_never_supplies_the_wahlkreis(self) -> None:
        resolver = aw.AbgeordnetenwatchResolver(sleep_seconds=0)
        with mock.patch.object(resolver, "_request", return_value=[LANDTAG, BUNDESTAG]):
            bio = resolver.fetch_bio(4711)
        self.assertEqual(bio, {"wahlkreis": "174 - Fulda", "bundesland": "Hessen"})
        resolver = aw.AbgeordnetenwatchResolver(sleep_seconds=0)
        with mock.patch.object(resolver, "_request", return_value=[LANDTAG]):
            self.assertEqual(resolver.fetch_bio(4712), {"wahlkreis": None, "bundesland": None})

    def test_bios_cached_by_the_old_rule_are_selected_again(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "aw-cache.json"
            cache_path.write_text(json.dumps({
                "version": 2,
                "by_ext_id": {"11001": {"id": 4711, "match": "ext_id"}},
                "by_name": {},
                "by_bio": {"4711": {"wahlkreis": "Fulda I", "bundesland": None}},
            }), encoding="utf-8")
            resolver = aw.AbgeordnetenwatchResolver(cache_path=cache_path, sleep_seconds=0)
            with mock.patch.object(resolver, "_request", return_value=[LANDTAG, BUNDESTAG]) as request:
                self.assertEqual(resolver.fetch_bio(4711)["wahlkreis"], "174 - Fulda")
            request.assert_called_once()
            self.assertEqual(resolver.resolve(ext_id="11001"), {"id": 4711, "match": "ext_id"})
            resolver.save()
            reloaded = aw.AbgeordnetenwatchResolver(cache_path=cache_path, sleep_seconds=0)
            with mock.patch.object(reloaded, "_request") as request:
                self.assertEqual(reloaded.fetch_bio(4711)["wahlkreis"], "174 - Fulda")
            request.assert_not_called()


if __name__ == "__main__":
    unittest.main()

