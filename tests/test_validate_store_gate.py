from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import _daten_fixture
import antrag_text
import build_dip_pulse_site as site
import persist_dip_pulse_store as pulse_store
import politikfelder
import reviewed_units
import reviewed_vote_links
import speech_kinds
import validate_dip_protocol as dip
import validate_store_gate as gate
from test_antrag_text import DEMANDS, OPENING, cache as antrag_cache, report as antrag_report


def _store(path: Path, bindings: list[tuple[str, str]]) -> Path:
    """A store holding only ``person_bindings`` rows (binding id, person id)."""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE person_bindings (id TEXT PRIMARY KEY, record_id TEXT, person_id TEXT)")
    conn.executemany(
        "INSERT INTO person_bindings(id, record_id, person_id) VALUES (?, 'r', ?)", bindings
    )
    conn.commit()
    conn.close()
    return path


def _drop_snippet(database: Path) -> None:
    """Stage a store from an older schema: one without ``speeches.snippet``,
    which ``collect_abgeordnete`` reads."""
    with contextlib.closing(sqlite3.connect(database)) as conn:
        conn.execute("ALTER TABLE speeches DROP COLUMN snippet")
        conn.commit()


def _person_cache(output: Path, *records: dict) -> None:
    """``data/dip-person-cache.json`` holding ``records``, as dip_cache saves it."""
    path = output / "data" / gate.PERSON_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    persons = {str(record["id"]): {"fetched_at": "2026-01-01T00:00:00Z", "record": record} for record in records}
    path.write_text(json.dumps({"persons": persons}), encoding="utf-8")


class PersistOnlyRosterTests(unittest.TestCase):
    # Value: protects=the gate's fresh and half clones build as an online --enrich mp-roster build,
    #   the roster served from the person cache by Wahlperiode; fails_when=persist_only builds
    #   store-less (no roster records, so replay_vs_fresh compares against a store that never had
    #   the roster) or lists a record outside the roster's periods; why_new=the store-less clone
    #   hid the R1 replay (docs/plans/registry-split-koestering-krampe.md); seam=none
    def test_persist_only_ingests_the_cached_roster_of_the_catalog_periods(self) -> None:
        from test_registry_contracts import dip_person

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "gate"
            report = antrag_report()
            report["validation_summary"] = {"speech_kinds_version": speech_kinds.VERSION}
            _support.stamp_reviewed(report)
            report_path, _, _ = site.report_paths(output, report["protocol"]["dokumentnummer"])
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report), encoding="utf-8")
            listed = {**dip_person("5", "Bo Voter"), "wahlperiode": [19, 20]}
            later = {**dip_person("6", "Cy Later"), "wahlperiode": 99}
            _person_cache(output, listed, later)
            with contextlib.redirect_stderr(io.StringIO()):
                gate.persist_only(output, "2024-05-15")
            database = output / "data" / "bundestag-pulse.sqlite"
            with sqlite3.connect(database) as conn:
                mdbs = conn.execute("SELECT dip_person_id FROM mps WHERE is_mdb = 1").fetchall()
            self.assertEqual(mdbs, [("5",)])
            # The report samples one DIP person of its own (is_mdb 0); the roster adds Bo.
            self.assertEqual(sorted(mdb for _binding, mdb in gate.dip_person_occurrences(database)), [0, 1])

    # Value: protects=the gate's fresh build ingests the roster of a Wahlperiode the sitting catalog lists
    #   although no sitting of it is cached, as an online build does; fails_when=persist_only takes the
    #   periods from the cached reports alone; why_new=TODOS "Registry fix review" (i); seam=none
    def test_persist_only_takes_roster_periods_from_the_catalog_too(self) -> None:
        from test_registry_contracts import dip_person
        import facts

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "gate"
            report = antrag_report()
            report["validation_summary"] = {"speech_kinds_version": speech_kinds.VERSION}
            _support.stamp_reviewed(report)
            report_path, _, _ = site.report_paths(output, report["protocol"]["dokumentnummer"])
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report), encoding="utf-8")
            (output / "data" / facts.CATALOG_FILENAME).write_text(
                json.dumps({"protocols": [{"id": "x", "dokumentnummer": "21/1", "datum": "2025-03-25"}]}), encoding="utf-8")
            _person_cache(output, {**dip_person("7", "Di Neu"), "wahlperiode": 21})
            with contextlib.redirect_stderr(io.StringIO()):
                gate.persist_only(output, "2025-05-15")
            with sqlite3.connect(output / "data" / "bundestag-pulse.sqlite") as conn:
                mdbs = conn.execute("SELECT dip_person_id FROM mps WHERE is_mdb = 1").fetchall()
            self.assertEqual(mdbs, [("7",)])

    # Value: protects=a clone without a readable person cache is a clear refusal (exit 2), not a
    #   store-less build that passes as the fresh reference; fails_when=cached_roster falls back
    #   to no roster; why_new=persist_only needs the cache now; seam=none
    def test_a_missing_person_cache_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "data").mkdir()
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = gate.main([tmp, "--persist-only"])
        self.assertEqual(code, 2)
        self.assertIn("no readable DIP person cache", stderr.getvalue())

    # Value: protects=the cached roster answers only the request ingest_mdb_roster makes, and lists
    #   a record for each period it names (int, digit text or a list); fails_when=another request is
    #   answered from the cache or a period form is missed; why_new=CachedRoster is new; seam=none
    def test_the_cached_roster_lists_by_period_and_refuses_other_requests(self) -> None:
        roster = gate.CachedRoster([{"id": "1", "wahlperiode": [19, "20"]}, {"id": "2", "wahlperiode": 21}, {"id": "3"}])
        self.assertEqual([r["id"] for r in roster.list_all("/person", {"f.wahlperiode": 20})], ["1"])
        self.assertEqual([r["id"] for r in roster.list_all("/person", {"f.wahlperiode": 21})], ["2"])
        with self.assertRaises(ValueError):
            roster.list_all("/aktivitaet", {"f.wahlperiode": 20})

    # Value: protects=a boolean wahlperiode is no Wahlperiode, so a record with wahlperiode true is not listed
    #   under WP 1; fails_when=_wahlperioden tests isinstance(int) first, which a bool passes;
    #   why_new=TODOS "Registry fix review" (g); seam=none
    def test_a_boolean_wahlperiode_lists_the_record_under_no_period(self) -> None:
        self.assertEqual(gate._wahlperioden({"wahlperiode": True}), set())
        self.assertEqual(gate._wahlperioden({"wahlperiode": [True, False, 20, "21"]}), {20, 21})
        self.assertEqual(gate.CachedRoster([{"id": "1", "wahlperiode": True}]).list_all("/person", {"f.wahlperiode": 1}), [])

    # Value: protects=main's --persist-only path turns only the person-cache refusal into "ERROR [gate]" with
    #   exit 2; any other ValueError from the build code keeps its traceback instead of reading like a
    #   person-cache problem; fails_when=main catches every ValueError from persist_only;
    #   why_new=TODOS "Registry fix review" (i), second half; seam=persist_only patched
    def test_persist_only_reports_only_the_person_cache_refusal_as_bad_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "data").mkdir()
            with mock.patch.object(gate, "persist_only", side_effect=ValueError("a build bug")), \
                    contextlib.redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaisesRegex(ValueError, "a build bug"):
                    gate.main([tmp, "--persist-only"])
            self.assertNotIn("ERROR [gate]", stderr.getvalue())
            with mock.patch.object(gate, "persist_only", side_effect=gate.CachedRosterError("no person cache")), \
                    contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(gate.main([tmp, "--persist-only"]), 2)
            self.assertIn("ERROR [gate]: no person cache", stderr.getvalue())


class MainStopsCleanlyTests(unittest.TestCase):
    # Value: protects=a missing scripts/reviewed_units.json stops the gate (and its --persist-only
    #   clones) with "ERROR [reviewed-units]" and exit 2, not a traceback from deep in a replay;
    #   fails_when=main does not call reviewed_units.load() before it starts; why_new=TODOS
    #   "Withheld-Reden PRs A and B" B robustness; seam=reviewed_units.load patched
    def test_a_missing_reviewed_list_is_a_clean_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "data").mkdir()
            for argv in ([tmp, "--persist-only"], [tmp, "--receipt", str(Path(tmp) / "r.json")]):
                with mock.patch.object(reviewed_units, "load", side_effect=reviewed_units.ReviewedUnitsError("list is missing")), \
                        contextlib.redirect_stderr(io.StringIO()) as stderr:
                    self.assertEqual(gate.main(argv), 2)
                self.assertIn("ERROR [reviewed-units]: list is missing", stderr.getvalue())

    # Value: protects=a clone that cannot be made (permissions, disk full) ends the gate with
    #   "ERROR [gate]" and exit 2, not a traceback; fails_when=main catches only ValueError around
    #   run_gate; why_new=TODOS "C1 seat counts" item 41; seam=_data_clone patched
    def test_a_clone_that_cannot_be_made_is_bad_input(self) -> None:
        import subprocess

        for failure in (OSError("No space left on device"), subprocess.CalledProcessError(1, ["cp"])):
            with self.subTest(type(failure).__name__), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "gate"
                (output / "data").mkdir(parents=True)
                with mock.patch.object(gate, "run_gate", side_effect=failure), \
                        contextlib.redirect_stderr(io.StringIO()) as stderr:
                    self.assertEqual(gate.main([str(output), "--receipt", str(Path(tmp) / "r.json")]), 2)
                self.assertIn("ERROR [gate]:", stderr.getvalue())


class ReviewedVoteLinkCheckTests(unittest.TestCase):
    # Value: protects=the store gate fails on a reviewed vote link that no longer holds and reports the release condition without failing on it (plan section 5); fails_when=the check ignores the entries, or a contested vote fails the store gate and so every weekly build; why_new=PR C adds the reviewed file; seam=none
    def test_a_stale_entry_fails_and_the_release_condition_is_only_reported(self) -> None:
        report = _support.stamp_reviewed(json.loads((_support.FIXTURES / "report.json").read_text(encoding="utf-8")))
        report["validation_summary"]["speech_kinds_version"] = speech_kinds.VERSION

        def entry(top_id: str, verdict: str, **fields) -> dict:
            return {"protocol": "20/999", "vote_id": "12345", "top_id": top_id, "top_occurrence": 1,
                    "heading_starts": "TOP 1 Beratung Testgesetz" if top_id == "T1" else "TOP 2 Fragestunde",
                    "page_start": 101 if top_id == "T1" else 103, "verdict": verdict,
                    "pattern": "A" if verdict == "wrong" else "-", "action": "rule" if verdict == "wrong" else "none",
                    "note": "", "evidence": "", "reviewer": "", "source": "sheet 2026-11-21", **fields}

        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()):
            database = Path(tmp) / "data" / "bundestag-pulse.sqlite"
            database.parent.mkdir()
            site.rebuild_database_from_entries(database, [{"report": report}])
            holding = reviewed_vote_links.check({"entries": [entry("T1", "right"), entry("T2", "wrong"),
                                                             entry("T1", "right", protocol="18/1")]})
            result = gate.reviewed_vote_link_check(database, holding)
            self.assertEqual((result["stale_count"], result["checked"], result["skipped_not_in_store"]), (0, 2, 1))
            self.assertEqual(result["release"], {"contested_votes": 0, "refusals": [], "refusal_count": 0})
            stale = gate.reviewed_vote_link_check(database, reviewed_vote_links.check({"entries": [entry("T2", "right")]}))
            self.assertEqual(stale["stale"], ["20/999 vote 12345 T2 #1: reviewed right, but the rule no longer makes the link"])
            self.assertEqual(stale["release"]["refusal_count"], 1)

    def test_a_malformed_entries_file_is_a_clean_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "data").mkdir()
            with mock.patch.object(reviewed_vote_links, "load", side_effect=reviewed_vote_links.ReviewedVoteLinksError("bad entry")), \
                    contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(gate.main([tmp, "--receipt", str(Path(tmp) / "r.json")]), 2)
            self.assertIn("ERROR [reviewed-vote-links]: bad entry", stderr.getvalue())


class CachedRosterFileTests(unittest.TestCase):
    # Value: protects=a person cache that is not a person cache is a refusal, and entries without a
    #   record are skipped, not read as roster rows; fails_when=cached_roster returns an empty or
    #   partial roster instead of raising, so the fresh clone passes with no roster;
    #   why_new=only the missing-file refusal was tested; seam=none
    def test_cached_roster_refuses_unreadable_files_and_skips_entries_without_a_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            path = output / "data" / gate.PERSON_FILENAME
            path.parent.mkdir()
            for text in ("{not json", "[]", json.dumps({"persons": []}), json.dumps({})):
                path.write_text(text, encoding="utf-8")
                with self.subTest(text=text), self.assertRaises(gate.CachedRosterError):
                    gate.cached_roster(output)
            path.write_text(json.dumps({"persons": {"1": {"record": {"id": "1", "wahlperiode": 21}}, "2": "x", "3": {"record": 5}, "4": {}}}), encoding="utf-8")
            self.assertEqual([r["id"] for r in gate.cached_roster(output).records], ["1"])


class PersistOnlyAntragCacheTests(unittest.TestCase):
    # Value: protects=the gate's fresh and half-store persistence keeps extracted Antrag passages and state; fails_when=persist_only omits the separate Drucksache text cache; why_new=the gate loader previously passed only the Vorgang cache; seam=none; no_claim=local fixture report and cache, no live DIP source
    def test_persist_only_loads_antrag_cache_like_normal_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = antrag_report()
            report["validation_summary"] = {"speech_kinds_version": speech_kinds.VERSION}
            _support.stamp_reviewed(report)
            cache = antrag_cache()
            outputs = [root / "gate", root / "normal"]
            for output in outputs:
                report_path, _, _ = site.report_paths(output, report["protocol"]["dokumentnummer"])
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(json.dumps(report), encoding="utf-8")
                politikfelder.save_cache(output, cache)
                antrag_text.save_cache(output, cache[antrag_text.CACHE_NAMESPACE])
            _person_cache(outputs[0])

            gate.persist_only(outputs[0], "2024-05-15")
            normal_cache = politikfelder.load_cache(outputs[1])
            normal_cache[antrag_text.CACHE_NAMESPACE] = antrag_text.load_cache(outputs[1])
            site.repersist_cached_reports(
                outputs[1], outputs[1] / "data" / "bundestag-pulse.sqlite",
                site.load_cached_protocols(outputs[1]), today=date(2024, 5, 15),
                vorgang_cache=normal_cache,
            )

            def stored(output: Path) -> tuple[object, ...]:
                with sqlite3.connect(output / "data" / "bundestag-pulse.sqlite") as conn:
                    vote = conn.execute("SELECT passage_state FROM votes WHERE id='12345'").fetchone()
                    passage = conn.execute(
                        "SELECT d.document_number, d.forderung, d.forderung_state "
                        "FROM vote_passages vp JOIN documents d ON d.id=vp.document_id "
                        "WHERE vp.vote_id='12345'"
                    ).fetchone()
                return (vote[0] if vote else None, *(passage or (None, None, None)))

            expected = ("extracted", "20/123", "\n\n".join((OPENING, *DEMANDS)), "extracted")
            self.assertEqual(stored(outputs[0]), expected)
            self.assertEqual(stored(outputs[0]), stored(outputs[1]))


class GroupingFingerprintTest(unittest.TestCase):
    # Value: protects=the order-independence check compares groupings, not minted ids;
    # fails_when=the fingerprint depends on person ids or misses a moved binding;
    # why_new=the 2026-10-05 harness was lost; seam=grouping_fingerprint(store path).
    def test_same_grouping_under_other_person_ids_is_equal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = _store(Path(tmp) / "a.sqlite", [("b1", "p1"), ("b2", "p1"), ("b3", "p2")])
            b = _store(Path(tmp) / "b.sqlite", [("b3", "x9"), ("b2", "x7"), ("b1", "x7")])
            self.assertEqual(gate.grouping_fingerprint(a), gate.grouping_fingerprint(b))

    def test_a_binding_in_another_group_changes_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = _store(Path(tmp) / "a.sqlite", [("b1", "p1"), ("b2", "p1"), ("b3", "p2")])
            b = _store(Path(tmp) / "b.sqlite", [("b1", "p1"), ("b2", "p2"), ("b3", "p2")])
            self.assertNotEqual(gate.grouping_fingerprint(a)["fingerprint"], gate.grouping_fingerprint(b)["fingerprint"])
            self.assertEqual(gate.grouping_fingerprint(a)["groups"], 2)
            self.assertEqual(gate.grouping_fingerprint(a)["bindings"], 3)


    def test_bindings_kept_for_retired_occurrences_can_be_left_out(self) -> None:
        # A replayed store carries the registry's bindings of occurrences the
        # reports no longer hold; a fresh one cannot have them.
        with tempfile.TemporaryDirectory() as tmp:
            fresh = _store(Path(tmp) / "fresh.sqlite", [("b1", "p1"), ("b2", "p1")])
            replayed = _store(Path(tmp) / "replayed.sqlite", [("b1", "q"), ("b2", "q"), ("retired", "q")])
            live = gate.binding_ids(fresh)
            self.assertNotEqual(gate.grouping_fingerprint(replayed), gate.grouping_fingerprint(fresh))
            self.assertEqual(gate.grouping_fingerprint(replayed, only=live), gate.grouping_fingerprint(fresh))


class ReplayVsInputTest(unittest.TestCase):
    """The gate compares its replay with the input store it replayed."""

    def build(self, root: Path) -> Path:
        from test_registry_contracts import dip_person, report_with_vote, roster_client

        root.mkdir(parents=True, exist_ok=True)
        database = root / "store.sqlite"
        report = report_with_vote(member="Voter, Bo", url="https://www.bundestag.de/abgeordnete/biografien/V/voter_bo-123")
        entries = [{"report": report, "report_path": root / "s1.json"}]
        with contextlib.redirect_stderr(io.StringIO()):
            site.rebuild_database_from_entries(
                database, entries, preserve_roster=False,
                roster_ingest=lambda staged: site.ingest_mdb_roster(
                    roster_client(dip_person("5", "Bo Voter")), staged, wahlperioden=[21]))
        return database

    def snapshot(self, database: Path) -> dict:
        return {"bindings": gate.binding_ids(database), "grouping": gate.grouping_fingerprint(database),
                "pages": gate.person_pages(database)}

    # Value: protects=an unchanged replay passes, and one that moves a roster MdB's Stimmen to a
    #   pageless roll-call person fails with the moved counts in the receipt (the 227 Stimmen the
    #   fresh store lost in a replay at 34a4615); fails_when=the check compares only the bindings
    #   a store-less build holds, or only person counts, as replayed_store_groups_like_fresh did;
    #   why_new=replay_vs_input is new; seam=none; no_claim=the full-data run
    def test_a_replay_that_moves_stimmen_off_a_page_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = self.build(Path(tmp))
            before = self.snapshot(database)
            self.assertTrue(gate.replay_vs_input(before, database)["equal"])
            bo = {page["name"]: page for page in before["pages"].values()}["Bo Voter"]
            self.assertEqual((bo["stimmen"], bo["reden"]), (1, 0))

            conn = sqlite3.connect(database)
            voter = conn.execute("SELECT id FROM mps WHERE identity_key LIKE 'profile:%'").fetchone()[0]
            alone = conn.execute("SELECT person_id FROM mps WHERE identity_key LIKE 'xml:%'").fetchone()[0]
            for table, column in (("mps", "id"), ("person_records", "id"), ("person_bindings", "record_id")):
                conn.execute(f"UPDATE {table} SET person_id = ? WHERE {column} = ?", (alone, voter))
            conn.commit()
            conn.close()
            result = gate.replay_vs_input(before, database)

        self.assertFalse(result["equal"])
        self.assertNotEqual(result["grouping_before"], result["grouping_after"])
        pages = result["pages"]
        self.assertEqual((pages["totals"]["before"]["stimmen"], pages["totals"]["after"]["stimmen"]), (1, 1))
        self.assertEqual(pages["lost_count"] + pages["changed_count"], 2)
        lost_names = {page["name"] for page in pages["lost"]}
        self.assertIn("Bo Voter", lost_names)

    # Value: protects=pages compare by their binding sets and counts, so the same pages under other
    #   person keys are equal, and each kind of difference is counted; fails_when=compare_pages keys
    #   on person ids or drops a changed count; why_new=compare_pages is new; seam=none
    def test_compare_pages_counts_lost_gained_and_changed_pages(self) -> None:
        page = lambda pid, stimmen: {"id": pid, "name": pid, "reden": 1, "beitraege": 0, "stimmen": stimmen}
        before = {"a": page("p1", 2), "b": page("p2", 3)}
        self.assertTrue(gate.compare_pages(before, {"a": page("x1", 2), "b": page("x2", 3)})["equal"])
        result = gate.compare_pages(before, {"a": page("p1", 1), "c": page("p3", 3)})
        self.assertFalse(result["equal"])
        self.assertEqual((result["lost_count"], result["gained_count"], result["changed_count"]), (1, 1, 1))
        self.assertEqual((result["totals"]["before"]["stimmen"], result["totals"]["after"]["stimmen"]), (5, 4))

    # Value: protects=a replay that drifts from a fresh build fails even when the gate's input was
    #   itself such a replay, so replay_vs_input sees no difference; fails_when=the gate checks the
    #   replay only against its input (the gap after replayed_store_groups_like_fresh became
    #   report-only); why_new=replay_vs_fresh is new; seam=none; no_claim=the full-data run
    def test_a_replay_that_drifted_from_fresh_fails_although_its_input_drifted_too(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fresh = self.build(Path(tmp) / "fresh")
            replayed = self.build(Path(tmp) / "replayed")
            roster = gate.dip_person_occurrences(fresh)
            self.assertTrue(gate.replay_vs_fresh(fresh, replayed, roster)["equal"])

            conn = sqlite3.connect(replayed)
            voter = conn.execute("SELECT id FROM mps WHERE identity_key LIKE 'profile:%'").fetchone()[0]
            alone = conn.execute("SELECT person_id FROM mps WHERE identity_key LIKE 'xml:%'").fetchone()[0]
            for table, column in (("mps", "id"), ("person_records", "id"), ("person_bindings", "record_id")):
                conn.execute(f"UPDATE {table} SET person_id = ? WHERE {column} = ?", (alone, voter))
            conn.commit()
            conn.close()
            # The input is the drifted store, so a replay that keeps the drift matches it.
            self.assertTrue(gate.replay_vs_input(self.snapshot(replayed), replayed)["equal"])
            result = gate.replay_vs_fresh(fresh, replayed, gate.dip_person_occurrences(replayed))

        self.assertFalse(result["equal"])
        self.assertTrue(result["roster"]["equal"])
        self.assertNotEqual(result["grouping"]["fresh"], result["grouping"]["replay"])
        self.assertIn("Bo Voter", {page["name"] for page in result["pages"]["lost"]})

    # Value: protects=the fresh build is the reference only when it lists the input's roster
    #   records; a person cache lacking one is reported, not read as a passing reference;
    #   fails_when=the roster comparison is dropped or counts retired roster bindings; why_new=same; seam=none
    def test_a_fresh_build_missing_an_input_roster_record_fails_the_roster_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fresh = self.build(Path(tmp))
            roster = gate.dip_person_occurrences(fresh)
            result = gate.replay_vs_fresh(fresh, fresh, roster | {("roster-v1-missing", 1)})
        self.assertEqual(roster, {(next(iter(roster))[0], 1)})
        self.assertFalse(result["roster"]["equal"])
        self.assertEqual(result["roster"]["missing_from_fresh"], 1)
        self.assertTrue(result["equal"])

    # Value: protects=a gate run without an input store cannot pass the replay comparison;
    #   fails_when=a missing snapshot reads as equal; why_new=replay_vs_input is new; seam=none
    def test_no_input_store_fails_the_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = gate.replay_vs_input(None, Path(tmp) / "missing.sqlite")
        self.assertEqual(result, {"equal": False, "reason": "no input store to compare the replay with"})

    # Value: protects=an input store the current code cannot read (an older schema lacking a column
    #   collect_abgeordnete reads) gives an unavailable snapshot with the cause, which fails the replay
    #   comparison with a reason, instead of an OperationalError that ends the gate without a receipt;
    #   fails_when=input_snapshot lets sqlite3.OperationalError out, or replay_vs_input reads an unavailable
    #   snapshot as a store; why_new=TODOS "Registry fix review" (c); seam=none
    def test_an_unreadable_input_store_gives_an_unavailable_snapshot_that_fails_the_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = self.build(Path(tmp))
            snapshot = gate.input_snapshot(database)
            self.assertEqual(set(snapshot), {"bindings", "grouping", "pages", "roster"})
            self.assertTrue(gate.replay_vs_input(snapshot, database)["equal"])
            _drop_snippet(database)
            snapshot = gate.input_snapshot(database)
            result = gate.replay_vs_input(snapshot, database)
        self.assertEqual(set(snapshot), {"unavailable"})
        self.assertIn("snippet", snapshot["unavailable"])
        self.assertFalse(result["equal"])
        self.assertIn("the input store's snapshot is unavailable", result["reason"])
        self.assertIn("snippet", result["reason"])


class IntegrityTest(unittest.TestCase):
    # Value: protects=the store gate reports SQLite foreign-key violations even when integrity_check is clean; fails_when=the FK check is removed or ignored; why_new=existing gate tests covered grouping, links and export but not database integrity; seam=none; no_claim=SQLite's own pragma checks only
    def test_reports_foreign_key_violations_separately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "store.sqlite"
            conn = sqlite3.connect(path)
            conn.executescript(
                "PRAGMA foreign_keys=OFF;"
                "CREATE TABLE parent (id TEXT PRIMARY KEY);"
                "CREATE TABLE child (parent_id TEXT REFERENCES parent(id));"
                "INSERT INTO child VALUES ('missing');"
            )
            conn.commit()
            conn.close()

            result = gate.integrity(path)

        self.assertTrue(result["integrity_ok"])
        self.assertEqual(result["foreign_key_violations"], 1)


class WithheldGateTest(unittest.TestCase):
    def persisted_store(self, tmp: str) -> Path:
        """A one-sitting store at the current schema, with R1 stored and R2 withheld."""
        refused = (
            '<rede id="R2"><p klasse="redner"><redner id="R2-r"><name><nachname>Zwei</nachname><fraktion>SPD</fraktion></name></redner></p>'
            '<p klasse="J">Rede von Zwei.</p><p klasse="redner"><redner id="B"><name><nachname>Gast</nachname><fraktion>Grüne</fraktion></name></redner></p>'
            '<p>Herzlichen Dank, dass Sie die Frage nicht zulassen. Eine Bemerkung</p></rede>'
        )
        kept = '<rede id="R1"><p klasse="redner"><redner id="R1-r"><name><nachname>Eins</nachname><fraktion>SPD</fraktion></name></redner></p><p klasse="J">Rede.</p></rede>'
        xml = ('<dbtplenarprotokoll wahlperiode="18" sitzung-nr="7"><sitzungsverlauf><tagesordnungspunkt top-id="T1">'
               f'<p klasse="T_NaS">Beratung</p>{kept}{refused}</tagesordnungspunkt></sitzungsverlauf><anlagen/></dbtplenarprotokoll>')
        parsed = dip.parse_protocol_xml(xml, reviewed=[])
        report = {"protocol": {"id": "18/7", "dokumentnummer": "18/7", "datum": "2015-04-23", "reviewed_digest": parsed["reviewed_digest"]},
                  "agenda_items": [dict(index=t["index"], **dip.xml_top_fields(t)) for t in parsed["agenda_items"]],
                  "xml_contributions": [], "validation_summary": dip.contribution_summary(parsed["agenda_items"])}
        path = Path(tmp) / "store.sqlite"
        conn = pulse_store.connect(path)
        pulse_store.persist_report(conn, report)
        conn.execute("CREATE TABLE IF NOT EXISTS facts (id TEXT)")  # the facts engine's table, which persist alone leaves out
        conn.commit()
        conn.close()
        return path

    # Value: protects=the gate flags a withheld Rede whose rede_id is also a stored Rede; fails_when=a withheld Rede reaches speeches unnoticed or the check is dropped; why_new=the withheld tables are new in schema 12; seam=none  # pregate-literal: SCHEMA_VERSION=12 the schema that added the withheld tables, on purpose
    def test_flags_a_withheld_rede_that_is_also_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.persisted_store(tmp)
            self.assertEqual(gate.withheld_also_counted(path), [])
            conn = sqlite3.connect(path)
            conn.execute("UPDATE withheld_units SET rede_id = 'R1'")
            conn.commit()
            conn.close()
            self.assertEqual(gate.withheld_also_counted(path), ["18/7 R1"])

    # Value: protects=the gate also flags a counted nested Beitrag of a withheld Rede (P3d), and only that; fails_when=withheld_also_counted compares rede_id alone, or flags a Beitrag of the stored outer Rede of a withheld split part; why_new=Codex at PR 2's ship; seam=none
    def test_flags_a_counted_beitrag_inside_a_withheld_rede(self) -> None:
        def add_beitrag(conn, rede_id, parent, sequence):
            conn.execute(
                "INSERT INTO contributions(id, protocol_id, agenda_item_id, kind, rede_id, parent_rede_id, sequence, "
                "created_at, updated_at) SELECT ?, protocol_id, agenda_item_id, 'zwischenfrage', ?, ?, ?, 'x', 'x' "
                "FROM withheld_units LIMIT 1",
                (f"c-{rede_id}", rede_id, parent, sequence),
            )

        with tempfile.TemporaryDirectory() as tmp:
            path = self.persisted_store(tmp)
            conn = sqlite3.connect(path)
            add_beitrag(conn, "nested:R1:2", "R1", 90)  # a Beitrag of the stored R1
            conn.commit()
            self.assertEqual(gate.withheld_also_counted(path), [])
            add_beitrag(conn, "nested:R2:2", "R2", 91)  # a Beitrag inside the withheld R2
            conn.commit()
            self.assertEqual(gate.withheld_also_counted(path), ["18/7 R2"])
            # D4: only the split part R2:2 is withheld, so a Beitrag of the outer
            # Rede R2, which stays stored, is legitimate.
            conn.execute("DELETE FROM contributions WHERE rede_id = 'nested:R2:2'")
            conn.execute("UPDATE withheld_units SET rede_id = 'R2:2'")
            add_beitrag(conn, "nested:R2:3", "R2", 92)
            conn.commit()
            self.assertEqual(gate.withheld_also_counted(path), [])
            add_beitrag(conn, "nested:R2:2:1", "R2:2", 93)
            conn.commit()
            conn.close()
            self.assertEqual(gate.withheld_also_counted(path), ["18/7 R2:2"])

    # Value: protects=a Kurzintervention or Erwiderung that answers a withheld Rede is its own <rede>, stored and counted
    #   by right, so the gate passes it; fails_when=withheld_also_counted reads every parent_rede_id as "nested inside",
    #   and the gate fails falsely on the T4 store (1,237 of 54,855 stored Reden are answered by one, 2026-11-15);
    #   why_new=the P3d check reused parent_rede_id, which also links a reply <rede> to the Rede it answers; seam=none
    def test_passes_a_stored_reply_to_a_withheld_rede(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.persisted_store(tmp)
            conn = sqlite3.connect(path)
            for kind, rede_id, sequence in (("kurzintervention", "R3", 3), ("erwiderung", "R4", 4)):
                conn.execute(
                    "INSERT INTO contributions(id, protocol_id, agenda_item_id, kind, rede_id, parent_rede_id, sequence, "
                    "created_at, updated_at) SELECT ?, protocol_id, agenda_item_id, ?, ?, 'R2', ?, 'x', 'x' "
                    "FROM withheld_units LIMIT 1",
                    (f"c-{rede_id}", kind, rede_id, sequence),
                )
            conn.commit()
            conn.close()
            self.assertEqual(gate.withheld_also_counted(path), [])

    # Value: protects=the gate fails on a withheld Rede with no Redner-ID, the one assumption erste-reden v3 rests on (ADR 0005 "Facts"); fails_when=such a Rede binds no one and its speaker's next stored Rede posts as a debut unnoticed; why_new=PR A; seam=none
    def test_counts_withheld_reden_without_a_redner_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.persisted_store(tmp)
            self.assertEqual(gate.withheld_without_redner_id(path), [])
            conn = sqlite3.connect(path)
            for value in (None, ""):
                with self.subTest(value=value):
                    conn.execute("UPDATE withheld_units SET xml_redner_id = ?", (value,))
                    conn.commit()
                    self.assertEqual(gate.withheld_without_redner_id(path), ["18/7 R2"])
            conn.close()

    # Value: protects=run_gate counts the owner's store before the replay that upgrades it, so store_counts reads a store
    #   without the schema 12 withheld tables as None instead of crashing, and counts them once present;  # pregate-literal: SCHEMA_VERSION=12 the schema that added the withheld tables, on purpose
    #   fails_when=store_counts queries withheld_units unconditionally (OperationalError on a schema 11 store, Codex P1 at ship);
    #   why_new=no test counted a store from before schema 12; seam=none  # pregate-literal: SCHEMA_VERSION=12 the schema that added the withheld tables, on purpose
    def test_counts_a_store_from_before_the_withheld_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.persisted_store(tmp)
            counts = gate.store_counts(path)
            self.assertEqual((counts["withheld_units"], counts["withheld_reasons"]), (1, {"refused_nested_contribution": 1}))
            self.assertGreater(counts["withheld_words"], 0)
            conn = sqlite3.connect(path)
            conn.executescript("DROP TABLE withheld_turns; DROP TABLE withheld_units;")
            conn.close()
            counts = gate.store_counts(path)
        self.assertEqual([counts[key] for key in ("withheld_units", "withheld_turns", "withheld_reasons", "withheld_words")],
                         [None, None, None, None])
        self.assertEqual(counts["speeches"], 1)


class ClonePathSafetyTest(unittest.TestCase):
    # Value: protects=cloning cannot remove overlapping input data; fails_when=resolved overlap reaches deletion; why_new=QA reproduced source deletion; seam=none
    def test_overlapping_clone_paths_preserve_the_source(self) -> None:
        for relation in ("same", "parent", "child"):
            with self.subTest(relation=relation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root / "site"
                (source / "data").mkdir(parents=True)
                evidence = source / "data" / "evidence.txt"
                evidence.write_text("keep")
                target = {"same": source, "parent": root, "child": source / "scratch"}[relation]
                error = None
                # Avoid recursive OS copies on the deliberately invalid child path.
                with mock.patch.object(gate.subprocess, "run"):
                    try:
                        gate._data_clone(source, target)
                    except Exception as exc:
                        error = exc
                self.assertIsInstance(error, ValueError)
                self.assertEqual(evidence.read_text(), "keep")

    # Value: protects=symlinks cannot hide clone/input overlap; fails_when=only lexical paths are compared; why_new=aliases reach the same destructive boundary; seam=none
    def test_symlink_to_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "site"
            (source / "data").mkdir(parents=True)
            alias = Path(tmp) / "alias"
            alias.symlink_to(source, target_is_directory=True)
            error = None
            try:
                gate._data_clone(source, alias)
            except Exception as exc:
                error = exc
            self.assertIsInstance(error, ValueError)
            self.assertTrue((source / "data").is_dir())

    # Value: protects=invalid CLI scratch is refused before replay changes the input; fails_when=validation occurs only in the late clone stage; why_new=helper-only coverage misses earlier mutation; seam=none
    def test_cli_refuses_overlap_before_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "fresh"
            (source / "data").mkdir(parents=True)
            with mock.patch.object(gate, "replay", side_effect=AssertionError("replay must not run")) as replay:
                with mock.patch("sys.stderr"):
                    result = gate.main([str(source), "--scratch", tmp, "--receipt", str(Path(tmp) / "receipt.json")])
            self.assertEqual(result, 2)
            replay.assert_not_called()
            self.assertTrue((source / "data").is_dir())

    # Value: protects=separate scratch still copies evidence and removes only cloned stores/exports; fails_when=the safety guard blocks normal clones; why_new=positive control for overlap checks; seam=none
    def test_separate_clone_preserves_source_and_drops_derived_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "site", Path(tmp) / "scratch" / "fresh"
            (source / "data" / "exports").mkdir(parents=True)
            for relative in ("evidence.txt", "bundestag-pulse.sqlite", "bundestag-pulse.sqlite-wal", "exports/old.txt"):
                (source / "data" / relative).write_text("keep")
            gate._data_clone(source, target)
            self.assertEqual((target / "data" / "evidence.txt").read_text(), "keep")
            self.assertFalse((target / "data" / "bundestag-pulse.sqlite").exists())
            self.assertFalse((target / "data" / "bundestag-pulse.sqlite-wal").exists())
            self.assertFalse((target / "data" / "exports").exists())
            self.assertEqual((source / "data" / "bundestag-pulse.sqlite").read_text(), "keep")

    # Value: protects=the gate's fresh and half clones get the source's cached MdB-Stammdaten (zip and ETag
    #   sidecar) in their own private directory, so their rebuilds re-file the Stimmen as the input store
    #   does, and a stale file from an earlier run is not left behind when the source has none; a clone that
    #   lacks the file the source has is refused; fails_when=_data_clone copies only data/, so the gate never
    #   sees a re-filed Stimme and a forgotten copy gives only a warning; why_new=TODOS E4 /gstack-review
    #   item 5, the _data_clone part; seam=shutil.copy2 patched for the refusal
    def test_the_clone_gets_the_sources_cached_stammdaten(self) -> None:
        import person_registry as registry
        import stammdaten

        with tempfile.TemporaryDirectory() as tmp:
            source, target = Path(tmp) / "site", Path(tmp) / "scratch" / "fresh"
            (source / "data").mkdir(parents=True)
            private = registry.private_dir(source / gate.STORE)
            private.mkdir(mode=0o700)
            (private / stammdaten.CACHE_NAME).write_bytes(b"zip bytes")
            (private / stammdaten.ETAG_NAME).write_text('{"etag": "x"}', encoding="utf-8")
            (private / "seat-crosscheck.json").write_text("{}", encoding="utf-8")
            cloned = registry.private_dir(target / gate.STORE)
            gate._data_clone(source, target)
            self.assertEqual(sorted(path.name for path in cloned.iterdir()), [stammdaten.ETAG_NAME, stammdaten.CACHE_NAME])
            self.assertEqual((cloned / stammdaten.CACHE_NAME).read_bytes(), b"zip bytes")
            self.assertEqual(stammdaten.cache_path(target / gate.STORE), cloned / stammdaten.CACHE_NAME)

            with mock.patch.object(gate.shutil, "copy2"), self.assertRaisesRegex(ValueError, "MdB-Stammdaten"):
                gate._data_clone(source, target)

            for path in private.iterdir():
                path.unlink()
            gate._data_clone(source, target)
            self.assertEqual([path.name for path in cloned.iterdir()], [])


class LinkAuditTest(unittest.TestCase):
    # Value: protects=every page a replay renders links only to pages and anchors that exist;
    # fails_when=a missing target or anchor goes unreported, or an external link is flagged;
    # why_new=the A2 link audit was an ad hoc script; seam=audit_links(site dir).
    def test_reports_missing_files_and_anchors_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp)
            (site / "abgeordnete").mkdir()
            (site / "abgeordnete" / "index.html").write_text('<a href="../index.html#top">x</a>', encoding="utf-8")
            (site / "a.html").write_text('<h2 id="ok">A</h2>', encoding="utf-8")
            (site / "index.html").write_text(
                '<p id="top"></p>'
                '<a href="a.html">a</a> <a href="a.html#ok">ok</a> <a href="#top">self</a>'
                '<a href="abgeordnete/">dir</a> <a href="a.html?x=1">query</a>'
                '<a href="https://example.org/x.html">ext</a> <a href="mailto:a@b.c">m</a>'
                '<img src="data:image/png;base64,AAAA">'
                '<a href="missing.html">bad</a> <a href="a.html#gone">bad anchor</a>',
                encoding="utf-8",
            )
            result = gate.audit_links(site)
        self.assertEqual(result["pages"], 3)
        self.assertEqual(
            sorted((b["page"], b["href"]) for b in result["broken"]),
            [("index.html", "a.html#gone"), ("index.html", "missing.html")],
        )


def _export_dir(root: Path, *, protocols_in_manifest: int | None = None, corrupt: bool = False) -> Path:
    """An output directory with the Daten fixture store and a real export of it.
    ``protocols_in_manifest`` makes the manifest's protocol count stale;
    ``corrupt`` damages the votes table CSV after the export."""
    data = root / "data"
    data.mkdir(parents=True)
    db_path = data / "bundestag-pulse.sqlite"
    _daten_fixture.seed_store(db_path)
    conn = pulse_store.connect(db_path)
    try:
        _, lookup = site.collect_abgeordnete(conn)
    finally:
        conn.close()
    manifest = site.export_distribution_data(
        db_path, data / "exports", mp_lookup=lookup,
        readiness={"votes": "ready", "aw-profiles": "unavailable", "mp-roster": "ready"},
        catalog_count=2, dossier_count=2, commit="abc123",
    )
    if corrupt:
        (data / "exports" / manifest["generation"] / "votes-local.csv.gz").write_bytes(b"tampered")
    if protocols_in_manifest is not None:
        manifest_path = data / "exports" / "datenstand.json"
        stored = json.loads(manifest_path.read_text(encoding="utf-8"))
        stored["protocols"]["count"] = protocols_in_manifest
        manifest_path.write_text(json.dumps(stored), encoding="utf-8")
    return root


class ExportCheckTest(unittest.TestCase):
    # Value: protects=the published export is the one the store holds and its files are intact;
    # fails_when=a stale manifest or a damaged file passes; why_new=the A2 export check was ad hoc;
    # seam=check_export(output dir).
    def test_a_matching_export_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(gate.check_export(_export_dir(Path(tmp)))["problems"], [])

    def test_a_damaged_file_and_a_stale_count_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            problems = gate.check_export(_export_dir(Path(tmp), protocols_in_manifest=99, corrupt=True))["problems"]
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(any("votes-local.csv.gz" in problem for problem in problems))
        self.assertTrue(any("protocols" in problem for problem in problems))


class OrderIndependenceTest(unittest.TestCase):
    NAMES = [f"plenarprotokoll-18-{n}.json" for n in range(1, 5)]

    def site(self, root: Path) -> Path:
        data = root / "site" / "data"
        data.mkdir(parents=True)
        for name in (*self.NAMES, "plenarprotokoll-catalog.json"):
            (data / name).write_text("{}")
        return root / "site"

    def run_steps(self, root: Path, exit_codes: list[int], same: bool = False) -> tuple[dict, list[list[str]]]:
        seen: list[list[str]] = []
        codes = iter(exit_codes)

        def persist(clone: Path, today: str, log: Path) -> dict:
            seen.append(sorted(p.name for p in (clone / "data").glob("plenarprotokoll-*.json")))
            return {"exit_code": next(codes)}

        with mock.patch.object(gate, "_persist_clone", side_effect=persist), \
                mock.patch.object(gate, "grouping_fingerprint", side_effect=lambda path, **_: {"store": "same" if same else path.parent.parent.name}):
            return gate.order_independence(self.site(root), root / "scratch", "2026-11-01"), seen

    # Value: protects=the order-independence check really replays a half-built store, then all reports, against a fresh one; fails_when=the half step keeps every report (the check passes vacuously) or the held-back reports are not returned before the final step; why_new=only the clone helpers are tested, not the three-step sequence; seam=none; no_claim=the grouping fingerprint itself, tested above
    def test_the_half_store_holds_back_every_second_report_and_the_last_step_has_them_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result, seen = self.run_steps(Path(tmp), [0, 0, 0])
        catalog = "plenarprotokoll-catalog.json"
        everything = sorted([*self.NAMES, catalog])
        self.assertEqual(seen, [everything, sorted([self.NAMES[0], self.NAMES[2], catalog]), everything])
        self.assertEqual(result["half"]["reports"], 2)

    # Value: protects=the gate calls the stores equal only when all three persist steps succeed and their groupings match; fails_when=equal ignores a failed step or the fingerprint comparison; why_new=same as above; seam=none
    def test_equal_needs_every_step_to_succeed_and_the_groupings_to_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            same, _ = self.run_steps(Path(tmp) / "a", [0, 0, 0], same=True)
            differs, _ = self.run_steps(Path(tmp) / "b", [0, 0, 0])
            failed, _ = self.run_steps(Path(tmp) / "c", [0, 1, 0], same=True)
        self.assertTrue(same["equal"])
        self.assertFalse(differs["equal"])
        self.assertFalse(failed["equal"])
        self.assertNotIn("grouping", failed["fresh"])


class GateVerdictTest(unittest.TestCase):
    # Value: protects=the gate exits 1 and writes its receipt, all_passed false, when the replay fails, even if the order-independence check says equal; fails_when=a failed replay or a missing check leaves the exit code 0 or the receipt unwritten; why_new=only the usage errors of main() are tested; seam=none; no_claim=the passing run, which needs a real store and takes about 20 minutes
    def test_a_failed_replay_fails_the_gate_and_the_receipt_says_so(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "site" / "data" / "xml").mkdir(parents=True)
            receipt = root / "out" / "receipt.json"
            failed = {"exit_code": 1, "store_replaced": False, "store_kept": False, "tail": []}
            with mock.patch.object(gate, "replay", return_value=failed), \
                    mock.patch.object(gate, "order_independence", return_value={"equal": True}), \
                    mock.patch("sys.stderr"):
                code = gate.main([str(root / "site"), "--scratch", str(root / "scratch"), "--receipt", str(receipt)])
            written = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertFalse(written["checks"]["replay_exit_0"])
        self.assertFalse(written["checks"]["all_passed"])
        self.assertNotIn("integrity", written)

    # Value: protects=a gate run on an input store the current code cannot read writes its receipt, with
    #   replay_keeps_input_grouping_and_pages false, the snapshot recorded as unavailable and the cause as the
    #   comparison's reason; fails_when=the snapshot's sqlite3.OperationalError ends the gate before the replay
    #   with no receipt; why_new=TODOS "Registry fix review" (c); seam=replay patched to swap in a current store;
    #   no_claim=the order-independence clones and the publication check (patched)
    def test_an_unreadable_input_store_fails_the_replay_comparison_with_a_reason(self) -> None:
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current = ReplayVsInputTest.build(self, root / "current")
            (root / "site" / "data" / "xml").mkdir(parents=True)
            shutil.copy(current, root / "site" / gate.STORE)
            _drop_snippet(root / "site" / gate.STORE)
            receipt = root / "out" / "receipt.json"

            def replay(output_dir: Path, today: str, log_path: Path) -> dict:
                shutil.copy(current, output_dir / gate.STORE)
                return {"exit_code": 0, "store_replaced": True, "store_kept": True, "tail": []}

            with mock.patch.object(gate, "replay", side_effect=replay), \
                    mock.patch.object(gate, "order_independence", return_value={"equal": True, "fresh": {}}), \
                    mock.patch.object(gate, "_run", return_value={"exit_code": 0}), \
                    mock.patch("sys.stderr"):
                code = gate.main([str(root / "site"), "--scratch", str(root / "scratch"), "--receipt", str(receipt)])
            written = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(code, 1)
        self.assertTrue(written["checks"]["replay_exit_0"])
        self.assertFalse(written["checks"]["replay_keeps_input_grouping_and_pages"])
        self.assertIn("snippet", written["input_snapshot_unavailable"])
        self.assertIn("the input store's snapshot is unavailable", written["replay_vs_input"]["reason"])
        self.assertFalse(written["checks"]["all_passed"])


if __name__ == "__main__":
    unittest.main()
