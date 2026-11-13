"""The abgeordnetenwatch match share script (A3 plan item 1.5), offline.

The store, reports and Stammdaten are small fixtures; abgeordnetenwatch is a stub
behind ``AbgeordnetenwatchResolver._get``, so ``lookup_ext_id`` and the name search
run as in a build.
"""
from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import _support
import abgeordnetenwatch as aw
import build_dip_pulse_site as site
import measure_aw_match_share as share
import person_registry as registry
import validate_dip_protocol as dip

MDB = """<MDB><ID>{id}</ID><NAMEN>{names}</NAMEN><WAHLPERIODEN>{periods}</WAHLPERIODEN></MDB>"""
NAME = "<NAME><NACHNAME>{last}</NACHNAME><VORNAME>{first}</VORNAME><ADEL>{adel}</ADEL><PRAEFIX /><HISTORIE_VON>{since}</HISTORIE_VON></NAME>"
PERIOD = "<WAHLPERIODE><WP>{wp}</WP><MDBWP_VON /><MDBWP_BIS /><INSTITUTIONEN /></WAHLPERIODE>"


def mdb(mdb_id: str, names: list[tuple[str, str]], periods: list[int], adel: str = "") -> str:
    return MDB.format(
        id=mdb_id,
        names="".join(NAME.format(first=first, last=last, adel=adel, since=f"0{n + 1}.01.2010") for n, (first, last) in enumerate(names)),
        periods="".join(PERIOD.format(wp=wp) for wp in periods))


STAMMDATEN = "<DOCUMENT><VERSION>1777449783</VERSION>{}</DOCUMENT>".format("".join([
    mdb("11000001", [("Ada", "Byron"), ("Ada", "Lovelace")], [18, 19]),  # a historical surname
    mdb("11000002", [("Bob", "Builder")], [17]),  # an MdB of WP 17 only: M1a
    mdb("11000005", [("Eve", "Merged")], [18]),
    mdb("11000006", [("Jürgen", "Förster")], [19]),  # an umlaut
    mdb("11000007", [("Fritz", "Namesake")], [19]),
    mdb("11000008", [("Karl-Theodor", "Guttenberg")], [19], adel="Freiherr von und zu"),
]))
TABLE = [("11000001", 18), ("11000001", 19), ("11000005", 18), ("11000006", 19), ("11000007", 19), ("11000008", 19)]


def speech(redner_id: str | None, first: str, last: str, fraktion: str = "SPD", **extra: object) -> dict:
    return {"rede_id": f"ID-{redner_id}-{last}", "speaker": {
        "xml_redner_id": redner_id, "first_name": first, "last_name": last, "fraktion": fraktion, **extra}}


REPORTS = {
    "18/1": [{
        "index": 1,
        "xml_speakers": [
            # A profile cached in the report: still counted (the build skips a speaker holding one).
            speech("11000001", "Ada", "Lovelace", abgeordnetenwatch={"id": 1, "match": "ext_id"}),
            speech("11000001", "Ada", "Lovelace"),
            speech("11000002", "Bob", "Builder"),
            speech("999990001", "Carl", "Minister", "Bundesregierung"),
            speech(None, "Dora", "Nobody"),
        ],
        "xml_speakers_first": [],
        "xml_contributions": [
            speech("11000005 999990074", "Eve", "Merged"),
            speech(None, "Gus", "Asker"),  # a question whose asker never speaks: a name only
        ],
    }],
    "19/1": [{
        "index": 1,
        "xml_speakers": [
            speech("11000001", "Ada", "Lovelace"),
            speech("11000006", "Jürgen", "Förster"),
            speech("11000007", "Fritz", "Namesake"),
            speech("11000008", "Karl-Theodor", "Guttenberg", "CDU/CSU"),
        ],
        "xml_speakers_first": [],
        "xml_contributions": [],
    }],
    # A report the store does not hold: not counted.
    "18/2": [{"index": 1, "xml_speakers": [speech("11000099", "Not", "Stored")], "xml_speakers_first": [], "xml_contributions": []}],
}


def politician(politician_id: int, label: str) -> dict:
    return {"id": politician_id, "label": label, "abgeordnetenwatch_url": f"https://aw.example/{politician_id}"}


# What the stub API answers by ext_id; any id not listed is a miss.
API = {
    "11000001": [politician(1, "Ada Lovelace")],
    "11000005": [politician(5, "Eve Merged")],
    "11000006": [politician(6, "Jürgen Förster")],
    "11000007": [politician(7, "Fritz Other"), politician(70, "Fritz Namesake")],  # two politicians; the first fails the names
    "11000008": [politician(8, "Dr. Karl-Theodor zu Guttenberg")],
    "999990001": [politician(1, "Ada Lovelace")],  # a non-MdB id whose profile another id has
}
NAMES = {"Builder": [politician(2, "Bob Builder")]}


def fake_get(api: dict, names: dict | None = None, fail: set | None = None):
    calls: list[dict] = []

    def get(self: aw.AbgeordnetenwatchResolver, params: dict) -> list | None:
        calls.append(params)
        key = params.get("ext_id_bundestagsverwaltung") or params.get("last_name")
        if key in (fail or set()):
            self._call_failed = True
            self.stats["errors"] += 1
            self.last_error = "stub failure"
            return None
        self._call_failed = False
        if "ext_id_bundestagsverwaltung" in params:
            return list(api.get(key, []))
        return list((names or {}).get(key, []))

    get.calls = calls  # type: ignore[attr-defined]
    return get


class Fixture:
    def __init__(self, root: Path, *, table: bool = True, zip_: bool = True) -> None:
        self.output = root / "site"
        data = self.output / "data"
        data.mkdir(parents=True)
        self.cache = root / "scratch" / "aw-cache.json"
        for number, items in REPORTS.items():
            report = {"protocol": {"dokumentnummer": number}, "agenda_items": items}
            site.report_paths(self.output, number)[0].write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        conn = sqlite3.connect(data / "bundestag-pulse.sqlite")
        conn.executescript(
            "CREATE TABLE protocols (id TEXT PRIMARY KEY, document_number TEXT);"
            "CREATE TABLE mps (id TEXT PRIMARY KEY, xml_redner_id TEXT, aw_match TEXT);"
            "CREATE TABLE speeches (id TEXT PRIMARY KEY, protocol_id TEXT, mp_id TEXT);")
        conn.executemany("INSERT INTO protocols VALUES (?, ?)", [("p18", "18/1"), ("p19", "19/1"), ("p21", "21/1")])
        conn.executemany("INSERT INTO mps VALUES (?, ?, ?)", [("m1", "11000001", "ext_id"), ("m2", "11000002", None)])
        conn.executemany("INSERT INTO speeches VALUES (?, ?, ?)",
                         [("s1", "p18", "m1"), ("s2", "p18", "m2"), ("s3", "p19", "m1"), ("s4", "p21", "m1")])
        if table:
            conn.execute("CREATE TABLE mdb_zugehoerigkeiten (mdb_id TEXT, name TEXT, wahlperiode INTEGER, party_id TEXT, valid_from TEXT, valid_until TEXT)")
            conn.executemany("INSERT INTO mdb_zugehoerigkeiten VALUES (?, '', ?, '', '', NULL)", TABLE)
        conn.commit()
        conn.close()
        if zip_:
            stammdaten_dir = registry.private_dir(data / "bundestag-pulse.sqlite")
            stammdaten_dir.mkdir()
            with zipfile.ZipFile(stammdaten_dir / "mdb-stammdaten.zip", "w") as archive:
                archive.writestr("MDB_STAMMDATEN.XML", STAMMDATEN)

    def run(self, *args: str, api: dict = API, names: dict = NAMES, fail: set | None = None) -> tuple[int, dict, list]:
        receipt = self.output.parent / "receipt.json"
        get = fake_get(api, names, fail)
        with mock.patch.object(aw.AbgeordnetenwatchResolver, "_get", get), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = share.main([str(self.output), "--cache", str(self.cache), "--json", str(receipt), *args])
        if code == 2:
            raise AssertionError(err.getvalue())
        return code, json.loads(receipt.read_text(encoding="utf-8")), get.calls


class MeasureTests(unittest.TestCase):
    # Value (A3 item 1.5): protects=the WP 18/19 match share counts the build's own
    # speaker set, splits MdBs by their Mandat in the Wahlperiode whatever the
    # source, never counts a failure as a miss, and flags every hit a precision
    # review must see; fails_when=a denominator, the MdB split, the failure rule or a
    # flag drifts; seam=measure_aw_match_share.main over a fixture store with a stub
    # API; no_claim=the live API's answers or the real store's figures.
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_denominators_split_and_reden(self) -> None:
        fixture = Fixture(self.root)
        code, receipt, _ = fixture.run()
        self.assertEqual(code, 0)
        self.assertEqual(receipt["mdb_source"], "mdb_zugehoerigkeiten")
        self.assertEqual(receipt["sittings"], {"18": 1, "19": 1})
        figures = receipt["figures"]
        # WP 18: 11000001 (the cached profile stripped), 11000005 (merged raw); M1a
        # 11000002 (WP 17 only); M1b 999990001. 18/2 is not in the store.
        self.assertEqual(figures["18"]["redner_ids"], 4)
        self.assertEqual((figures["18"]["M1"]["ids"], figures["18"]["M1"]["hits"]), (2, 2))
        self.assertEqual((figures["18"]["M1a"]["ids"], figures["18"]["M1a"]["hits"]), (1, 0))
        self.assertEqual((figures["18"]["M1b"]["ids"], figures["18"]["M1b"]["hits"]), (1, 1))
        self.assertEqual(figures["19"]["redner_ids"], 4)
        self.assertEqual((figures["19"]["M1"]["ids"], figures["19"]["M1"]["hits"], figures["19"]["M1"]["share"]), (4, 4, 1.0))
        # 11000001 speaks in both Wahlperioden and counts once in the union.
        self.assertEqual(figures["union"]["redner_ids"], 7)
        self.assertEqual(figures["union"]["M1"]["ids"], 5)
        # M2: Reden are xml_speakers entries; Dora has no Redner-ID; Bob's Rede missed.
        self.assertEqual(figures["18"]["M2"], {"reden": 5, "reden_hit": 3, "share": 0.6, "reden_without_redner_id": 1})
        self.assertEqual(figures["union"]["M2"]["reden"], 9)
        # M6 from the store: WP 21 rows are not counted.
        self.assertEqual(receipt["m6"]["reden_with_ext_id_profile"], {"18": 1, "19": 1})
        self.assertEqual(receipt["m6"]["wp18_19_mdb_ids_without_a_profile"], {"18": 1, "19": 3})
        self.assertNotIn("11000099", json.dumps(receipt))

    def test_the_mandate_split_is_the_same_from_the_zip(self) -> None:
        fixture = Fixture(self.root, table=False)
        code, receipt, _ = fixture.run()
        self.assertEqual(code, 0)
        self.assertTrue(receipt["mdb_source"].startswith("zip:"))
        self.assertEqual(receipt["figures"]["18"]["M1a"]["ids"], 1)
        self.assertEqual(receipt["figures"]["18"]["M1"]["ids"], 2)

    def test_no_mdb_source_reports_no_m1(self) -> None:
        fixture = Fixture(self.root, table=False, zip_=False)
        code, receipt, _ = fixture.run()
        self.assertEqual((code, receipt["mdb_source"]), (0, "none"))
        self.assertIsNone(receipt["figures"]["18"]["M1"])

    def test_merged_raw_counts_once_under_its_first_id(self) -> None:
        fixture = Fixture(self.root)
        code, receipt, calls = fixture.run()
        self.assertEqual(code, 0)
        self.assertEqual(receipt["m5"]["merged_raw_values"],
                         [{"raw": "11000005 999990074", "redner_id": "11000005", "first_id_state": "hit", "raw_state": "miss"}])
        self.assertEqual(receipt["m5"]["merged_hit_by_first_not_by_raw"], 1)
        self.assertNotIn("999990074", [row["redner_id"] for row in receipt["m3"]["name_rule"]])
        asked = [call["ext_id_bundestagsverwaltung"] for call in calls if "ext_id_bundestagsverwaltung" in call]
        self.assertEqual(sorted(asked), sorted(["11000001", "11000002", "11000005", "11000006", "11000007",
                                                "11000008", "999990001", "11000005 999990074"]))

    def test_precision_flags(self) -> None:
        fixture = Fixture(self.root)
        code, receipt, _ = fixture.run()
        self.assertEqual(code, 0)
        m3 = receipt["m3"]
        # Fritz fails the names ("Fritz Other" shares the given name only), and so does
        # the non-MdB id printed for Carl Minister that returns Ada's profile. The
        # title, umlaut, particles and historical surname all pass.
        self.assertEqual([row["redner_id"] for row in m3["name_rule"]], ["11000007", "999990001"])
        self.assertEqual([(row["redner_id"], row["candidates"]) for row in m3["several_politicians"]], [("11000007", 2)])
        self.assertEqual([(row["aw_id"], [r["redner_id"] for r in row["redner_ids"]], row["classified"])
                          for row in m3["one_profile_several_ids"]],
                         [(1, ["11000001", "999990001"], "names differ")])
        self.assertEqual(m3["cache_disagrees"], [])
        self.assertEqual([row["redner_id"] for row in m3["m1b_hits_matching_an_mdb_by_name"]], ["999990001"])
        self.assertEqual(m3["m1b_hits_matching_an_mdb_by_name"][0]["mdb_ids_by_name"], ["11000001"])

    def test_the_name_rule(self) -> None:
        given, surname = {"ada"}, {"byron", "lovelace"}
        self.assertTrue(share.name_matches("Dr. Ada Lovelace", given, surname))
        self.assertTrue(share.name_matches("Ada Byron", given, surname))
        self.assertFalse(share.name_matches("Grace Lovelace", given, surname))  # a namesake by surname
        self.assertFalse(share.name_matches("Ada Turing", given, surname))  # a namesake by given name
        self.assertTrue(share.name_matches("Jürgen Förster", {"jürgen"}, {"förster"}))

    def test_a_cached_hit_the_fresh_answer_does_not_repeat_is_flagged(self) -> None:
        fixture = Fixture(self.root)
        fixture.cache.parent.mkdir(parents=True)
        fixture.cache.write_text(json.dumps({"version": aw.CACHE_VERSION, "by_ext_id": {
            "11000006": {"id": 66, "label": "Jürgen Förster", "match": "ext_id"},
            "11000002": {"id": 2, "label": "Bob Builder", "match": "ext_id"}}, "by_name": {}}), encoding="utf-8")
        code, receipt, calls = fixture.run()
        self.assertEqual(code, 0)
        self.assertEqual([(row["redner_id"], row["cached_id"]) for row in receipt["m3"]["cache_disagrees"]],
                         [("11000002", 2), ("11000006", 66)])
        # Every id is asked again, the cached hits included.
        self.assertIn({"ext_id_bundestagsverwaltung": "11000006"}, calls)
        self.assertEqual(receipt["cache"]["ext_id_entries_before"], 2)

    def test_the_store_cache_seeds_the_scratch_cache_and_is_never_written(self) -> None:
        fixture = Fixture(self.root)
        store_cache = fixture.output / "data" / "abgeordnetenwatch-cache.json"
        store_cache.write_text(json.dumps({"version": aw.CACHE_VERSION, "by_ext_id": {"11000002": None}, "by_name": {}}),
                               encoding="utf-8")
        before = store_cache.read_bytes()
        code, receipt, _ = fixture.run()
        self.assertEqual(code, 0)
        self.assertEqual(store_cache.read_bytes(), before)
        self.assertTrue(receipt["cache"]["seeded_from"].endswith("abgeordnetenwatch-cache.json"))
        self.assertEqual(json.loads(fixture.cache.read_text(encoding="utf-8"))["by_ext_id"]["11000001"]["id"], 1)
        with self.assertRaises(AssertionError):
            fixture.cache = fixture.output / "data" / "aw.json"
            fixture.run()

    def test_offline_sends_nothing(self) -> None:
        fixture = Fixture(self.root)
        with mock.patch("urllib.request.urlopen") as urlopen:
            code, receipt, calls = fixture.run("--offline")
        urlopen.assert_not_called()
        self.assertEqual((code, calls), (0, []))
        m1 = receipt["figures"]["union"]["M1"]
        self.assertEqual((m1["not_cached"], m1["share"], m1["bounds"]), (5, None, [0.0, 1.0]))
        self.assertEqual(receipt["requests"]["ext_id_keys"], 8)
        self.assertFalse(fixture.cache.exists())

    def test_a_failure_is_not_a_miss_and_a_rerun_asks_only_the_rest(self) -> None:
        fixture = Fixture(self.root)
        code, receipt, _ = fixture.run(fail={"11000006"})
        self.assertEqual(code, 1)
        self.assertEqual(receipt["failures"], ["11000006"])
        self.assertEqual(receipt["failure_reasons"], {"11000006": "stub failure"})
        m1 = receipt["figures"]["19"]["M1"]
        self.assertEqual((m1["failed"], m1["misses"], m1["share"]), (1, 0, None))
        code, receipt, calls = fixture.run()
        self.assertEqual((code, receipt["failures"]), (0, []))
        self.assertEqual(calls, [{"ext_id_bundestagsverwaltung": "11000006"}])
        self.assertEqual(receipt["figures"]["19"]["M1"]["share"], 1.0)

    def test_an_answer_the_cache_lost_is_asked_again(self) -> None:
        # The answers file says an id was answered, but the cache no longer holds
        # the profile: deleted, dropped by a format change, or unreadable.
        for damage in ("deleted", "other version", "unreadable"):
            with self.subTest(damage=damage):
                fixture = Fixture(self.root / damage)
                code, first, _ = fixture.run()
                self.assertEqual(code, 0)
                if damage == "deleted":
                    fixture.cache.unlink()
                elif damage == "other version":
                    fixture.cache.write_text(json.dumps({"version": aw.CACHE_VERSION + 1, "by_ext_id": {}}), encoding="utf-8")
                else:
                    fixture.cache.write_text('{"version": 2, "by_ext_id": {"110', encoding="utf-8")
                code, again, calls = fixture.run()
                self.assertEqual(code, 0)
                # Every answer the cache lost is asked again, the misses included.
                self.assertEqual(len(calls), first["requests"]["ext_id_keys"])
                self.assertEqual(again["figures"], first["figures"])
                self.assertEqual(again["m3"]["name_rule"], first["m3"]["name_rule"])

    def test_a_name_search_the_stopped_resolver_never_sends_is_a_failure(self) -> None:
        resolver = aw.AbgeordnetenwatchResolver(sleep_seconds=0)
        resolver._network_disabled = True
        resolver.last_error = "not asked: stopped"
        ids = {"11000002": {"names": share.Counter({("Bob", "Builder"): 1}), "fraktionen": share.Counter()}}
        with mock.patch("urllib.request.urlopen") as urlopen:
            found = share.name_fallback(resolver, ids, ["11000002"])
        urlopen.assert_not_called()
        self.assertEqual((found["11000002"]["state"], found["11000002"]["error"]), ("failed", "not asked: stopped"))

    def test_repeated_failures_stop_asking(self) -> None:
        fixture = Fixture(self.root)
        everything = set(API) | {"11000002", "11000005 999990074"}
        code, receipt, calls = fixture.run(fail=everything)
        self.assertEqual(code, 1)
        self.assertEqual(len(calls), share.MAX_FAILED_IN_A_ROW)
        self.assertEqual(len(receipt["failures"]), 8)

    def test_name_fallback_and_verdicts(self) -> None:
        fixture = Fixture(self.root)
        verdicts = self.root / "verdicts.json"
        verdicts.write_text(json.dumps({"11000002": "right person", "aw:1": "two people"}), encoding="utf-8")
        code, receipt, _ = fixture.run("--name-fallback", "--verdicts", str(verdicts))
        self.assertEqual(code, 0)
        m4 = receipt["m4"]
        self.assertEqual((m4["searched"], m4["linked"], m4["unlinked"], m4["failed"]), (1, 1, 0, 0))
        self.assertEqual(m4["review"][0]["aw"]["match"], "name")
        self.assertTrue(m4["review"][0]["name_rule"])
        self.assertEqual(m4["review"][0]["verdict"], "right person")
        self.assertEqual(receipt["m3"]["one_profile_several_ids"][0]["verdict"], "two people")
        code, receipt, _ = Fixture(self.root / "b").run("--name-fallback", fail={"Builder"})
        self.assertEqual((code, receipt["failures"]), (1, ["name:11000002"]))

    def test_a_report_is_read_from_its_xml(self) -> None:
        xml = (_support.FIXTURES / "reden-outside-tops" / "18-44.xml").read_text(encoding="utf-8")
        parsed = dip.parse_protocol_xml(xml)
        expected = {speech["speaker"]["xml_redner_id"].split()[0]
                    for item in parsed["agenda_items"] for speech in item["speeches"] if speech["speaker"].get("xml_redner_id")}
        fixture = Fixture(self.root)
        # The JSON holds the wrapped TOPs without a single speaker; the XML has them all.
        items = [{"index": n + 1, **dip.xml_top_fields(top), "xml_speakers": [], "xml_speakers_first": [], "xml_contributions": []}
                 for n, top in enumerate(top for top in parsed["agenda_items"] if not top["top_source"])]
        site.report_paths(fixture.output, "18/44")[0].write_text(json.dumps(
            {"protocol": {"dokumentnummer": "18/44"}, "agenda_items": items, "validation_summary": {"xml_top_count": len(items)}}),
            encoding="utf-8")
        xml_path = site.xml_cache_path(fixture.output, "18/44")
        xml_path.parent.mkdir(parents=True)
        xml_path.write_text(xml, encoding="utf-8")
        with sqlite3.connect(fixture.output / "data" / "bundestag-pulse.sqlite") as conn:
            conn.execute("INSERT INTO protocols VALUES ('p44', '18/44')")
        code, receipt, calls = fixture.run("--offline")
        self.assertEqual(code, 0)
        self.assertEqual(receipt["sittings"]["18"], 2)
        self.assertNotIn("18/44", receipt["sittings_without_xml"])
        self.assertIn("18/1", receipt["sittings_without_xml"])
        self.assertTrue(expected)
        self.assertGreaterEqual(receipt["figures"]["18"]["redner_ids"], len(expected | {"11000001"}))

    # Value: protects=a damaged answers file or a --verdicts file that is no JSON object ends in exit 2 naming the file, never a traceback or a fresh start; fails_when=garbage reads as no earlier answers or a bad input exits other than 2; why_new=_load_answers and --verdicts validation had no test; seam=none; no_claim=none beyond protects. Generated by gstack /ship coverage pass
    def test_corrupt_answers_and_verdicts_files_exit_2_naming_the_file(self) -> None:
        answers_bodies = ["not json {", "[1, 2]", '{"answers": 5}']
        for body in answers_bodies:
            with self.subTest(answers=body):
                fixture = Fixture(self.root / f"a{answers_bodies.index(body)}")
                self.assertEqual(fixture.run()[0], 0)
                answers = fixture.cache.with_name(fixture.cache.name + ".answers.json")
                answers.write_text(body, encoding="utf-8")
                with self.assertRaises(AssertionError) as raised:
                    fixture.run()
                self.assertIn(str(answers.name), str(raised.exception))
                self.assertNotIn("Traceback", str(raised.exception))
                self.assertEqual(answers.read_text(encoding="utf-8"), body)
        fixture = Fixture(self.root / "v")
        for body in ("not json {", "[1, 2]"):
            with self.subTest(verdicts=body):
                verdicts = self.root / "bad-verdicts.json"
                verdicts.write_text(body, encoding="utf-8")
                with self.assertRaises(AssertionError) as raised:
                    fixture.run("--verdicts", str(verdicts))
                self.assertIn("--verdicts", str(raised.exception))
                self.assertIn(verdicts.name, str(raised.exception))

    # Value: protects=a sitting the coverage-exclusion record lists is left out of every figure and named in sittings_excluded_by_record; fails_when=load_report stops applying the record, so an excluded sitting's Redner are counted; why_new=the plan asked for this case and no test covered it; seam=none; no_claim=the real store's exclusion list. Generated by gstack /ship coverage pass
    def test_a_sitting_in_the_exclusion_record_is_skipped_and_reported(self) -> None:
        fixture = Fixture(self.root)
        record = fixture.output / "data" / site.COVERAGE_EXCLUSIONS_FILENAME
        record.write_text(json.dumps({"exclusions": [{"document_number": "19/1"}]}), encoding="utf-8")
        code, receipt, _ = fixture.run("--offline")
        self.assertEqual(code, 0)
        self.assertEqual(receipt["sittings_excluded_by_record"], ["19/1"])
        self.assertEqual(receipt["sittings"], {"18": 1, "19": 0})
        self.assertEqual(receipt["figures"]["19"]["redner_ids"], 0)

    def test_the_command_line_entry_point(self) -> None:
        result = subprocess.run([sys.executable, "scripts/measure_aw_match_share.py", str(self.root / "missing"),
                                 "--cache", str(self.root / "c.json")], cwd=_support.ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("ERROR [aw-share]", result.stderr)

    def test_bad_input_exits_2(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(share.main([str(self.root / "missing"), "--cache", str(self.root / "c.json")]), 2)
            fixture = Fixture(self.root)
            self.assertEqual(share.main([str(fixture.output), "--cache", str(self.root / "c.json"),
                                         "--stammdaten", str(self.root / "none.zip")]), 2)
            self.assertEqual(share.main([str(fixture.output), "--cache", str(self.root / "c.json"), "--sleep", "0.1"]), 2)
            site.report_paths(fixture.output, "19/1")[0].unlink()
            self.assertEqual(share.main([str(fixture.output), "--cache", str(self.root / "c.json"), "--offline"]), 2)


if __name__ == "__main__":
    unittest.main()
