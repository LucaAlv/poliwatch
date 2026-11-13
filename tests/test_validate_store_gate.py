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
import speech_kinds
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


class PersistOnlyAntragCacheTests(unittest.TestCase):
    # Value: protects=the gate's fresh and half-store persistence keeps extracted Antrag passages and state; fails_when=persist_only omits the separate Drucksache text cache; why_new=the gate loader previously passed only the Vorgang cache; seam=none; no_claim=local fixture report and cache, no live DIP source
    def test_persist_only_loads_antrag_cache_like_normal_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = antrag_report()
            report["validation_summary"] = {"speech_kinds_version": speech_kinds.VERSION}
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


if __name__ == "__main__":
    unittest.main()
