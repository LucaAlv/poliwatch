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


def _politician(politician_id: int, label: str) -> dict:
    return {"id": politician_id, "label": label, "abgeordnetenwatch_url": f"https://aw.example/{politician_id}"}


class _Reply:
    """A urlopen result whose body is ``payload`` as JSON."""

    def __init__(self, payload: object) -> None:
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_Reply":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body


class LookupExtIdTests(unittest.TestCase):
    # Value (A3 item 1.5): protects=the measured ext_id match share counts an API
    # error as no answer, never as "no match", and a build caches no false
    # negative; fails_when=a non-ok reply or a stopped resolver reads as a miss, or
    # refresh serves the cache; seam=lookup_ext_id over _request; no_claim=the
    # live API's reply shapes.
    def resolver(self) -> aw.AbgeordnetenwatchResolver:
        return aw.AbgeordnetenwatchResolver(sleep_seconds=0)

    def test_each_state(self) -> None:
        resolver = self.resolver()
        with mock.patch.object(resolver, "_get", return_value=[_politician(7, "Ada Lovelace")]):
            hit = resolver.lookup_ext_id("11001")
        self.assertEqual((hit.state, hit.profile["id"], hit.profile["match"], hit.candidates), ("hit", 7, "ext_id", 1))
        self.assertEqual(hit.cached_state, "not_cached")
        with mock.patch.object(resolver, "_get", return_value=[]):
            miss = resolver.lookup_ext_id("11002")
        self.assertEqual((miss.state, miss.profile, miss.candidates), ("miss", None, 0))
        with mock.patch.object(resolver, "_get", return_value=None):
            failed = resolver.lookup_ext_id("11003")
        self.assertEqual((failed.state, failed.profile), ("failed", None))
        self.assertNotIn("11003", resolver._by_ext_id)
        with mock.patch.object(resolver, "_get") as get:
            self.assertEqual(resolver.lookup_ext_id("11004", network=False).state, "not_cached")
            self.assertEqual(resolver.lookup_ext_id("11001", network=False).state, "hit")
            self.assertEqual(resolver.lookup_ext_id("11002").state, "miss")
        get.assert_not_called()
        with self.assertRaises(ValueError):
            resolver.lookup_ext_id(" ")

    def test_several_politicians_take_the_first_and_report_the_count(self) -> None:
        resolver = self.resolver()
        reply = [_politician(7, "Ada Lovelace"), _politician(8, "Ada Byron")]
        with mock.patch.object(resolver, "_get", return_value=reply):
            found = resolver.lookup_ext_id("11001")
        self.assertEqual((found.state, found.profile["id"], found.candidates), ("hit", 7, 2))

    def test_refresh_asks_again_and_reports_the_cached_answer(self) -> None:
        resolver = self.resolver()
        resolver._by_ext_id.update({"11001": {"id": 7, "match": "ext_id"}, "11002": None})
        with mock.patch.object(resolver, "_get", return_value=[_politician(9, "Grace Hopper")]) as get:
            changed = resolver.lookup_ext_id("11001", refresh=True)
            filled = resolver.lookup_ext_id("11002", refresh=True)
        self.assertEqual(get.call_count, 2)
        self.assertEqual((changed.state, changed.profile["id"], changed.cached_state, changed.cached_profile["id"]),
                         ("hit", 9, "hit", 7))
        self.assertEqual((filled.state, filled.cached_state, filled.cached_profile), ("hit", "miss", None))
        self.assertEqual(resolver._by_ext_id["11002"]["id"], 9)
        # A failed refresh keeps the cached answer.
        with mock.patch.object(resolver, "_get", return_value=None):
            failed = resolver.lookup_ext_id("11001", refresh=True)
        self.assertEqual((failed.state, failed.cached_profile["id"]), ("failed", 9))
        self.assertEqual(resolver._by_ext_id["11001"]["id"], 9)
        with mock.patch.object(resolver, "_get") as get:
            self.assertEqual(resolver.lookup_ext_id("11001", network=False, refresh=True).state, "hit")
        get.assert_not_called()

    def test_network_false_sends_nothing(self) -> None:
        resolver = self.resolver()
        with mock.patch("urllib.request.urlopen") as urlopen:
            self.assertEqual(resolver.lookup_ext_id("11001", network=False).state, "not_cached")
        urlopen.assert_not_called()
        self.assertEqual(resolver.stats["api_calls"], 0)

    def test_the_failure_cut_off_gives_failed_not_miss(self) -> None:
        resolver = self.resolver()
        error = aw.urllib.error.URLError("down")
        with mock.patch("urllib.request.urlopen", side_effect=error) as urlopen:
            states = [resolver.lookup_ext_id(str(11000 + n)).state for n in range(aw.MAX_CONSECUTIVE_FAILURES + 2)]
        self.assertEqual(set(states), {"failed"})
        self.assertEqual(urlopen.call_count, aw.MAX_CONSECUTIVE_FAILURES)
        self.assertEqual(resolver._by_ext_id, {})

    def test_a_non_ok_reply_is_a_failure_and_caches_nothing(self) -> None:
        for payload in ({"meta": {"status": "error"}, "data": []}, {"meta": None}, ["not", "an", "object"]):
            with self.subTest(payload=payload):
                resolver = self.resolver()
                with mock.patch("urllib.request.urlopen", return_value=_Reply(payload)):
                    self.assertEqual(resolver.lookup_ext_id("11001").state, "failed")
                    # resolve: no cached negative, and the name search's own
                    # error reply caches nothing either.
                    self.assertIsNone(resolver.resolve(ext_id="11002", first_name="Ada", last_name="Lovelace"))
                self.assertEqual(resolver._by_ext_id, {})
                self.assertEqual(resolver._by_name, {})
                self.assertEqual(resolver.stats["errors"], 3)

    def test_an_ok_reply_without_politicians_is_a_cached_miss(self) -> None:
        resolver = self.resolver()
        with mock.patch("urllib.request.urlopen", return_value=_Reply({"meta": {"status": "ok"}, "data": []})):
            self.assertEqual(resolver.lookup_ext_id("11001").state, "miss")
        self.assertEqual(resolver._by_ext_id, {"11001": None})
        self.assertEqual(resolver.stats["errors"], 0)

    def test_resolve_uses_the_lookup_and_falls_back_to_the_name(self) -> None:
        resolver = self.resolver()
        replies = {"ext_id_bundestagsverwaltung": [], "last_name": [_politician(5, "Ada Lovelace")]}

        def get(params: dict) -> list:
            return replies["last_name" if "last_name" in params else "ext_id_bundestagsverwaltung"]

        with mock.patch.object(resolver, "_get", side_effect=get):
            profile = resolver.resolve(ext_id="11001", first_name="Ada", last_name="Lovelace", fraktion="SPD")
        self.assertEqual((profile["id"], profile["match"]), (5, "name"))
        self.assertEqual(resolver._by_ext_id, {"11001": None})
        resolver._by_ext_id["11003"] = {"id": 6, "match": "ext_id"}
        with mock.patch.object(resolver, "_get") as request:
            self.assertEqual(resolver.resolve(ext_id="11003")["id"], 6)
        request.assert_not_called()


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

