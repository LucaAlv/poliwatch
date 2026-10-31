from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import antrag_text
import build_dip_pulse_site as site
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


def _export_dir(root: Path, *, protocols_in_manifest: int = 2, corrupt: bool = False) -> Path:
    """An output directory with a two-protocol, one-vote store and its export."""
    data = root / "data"
    generation = data / "exports" / "g-0123456789ab"
    generation.mkdir(parents=True)
    conn = sqlite3.connect(data / "bundestag-pulse.sqlite")
    conn.executescript(
        "CREATE TABLE protocols (id TEXT); INSERT INTO protocols VALUES ('a'), ('b');"
        "CREATE TABLE votes (id TEXT); INSERT INTO votes VALUES ('v');"
        "CREATE TABLE vote_members (id TEXT); INSERT INTO vote_members VALUES ('m1'), ('m2'), ('m3');"
    )
    conn.commit()
    conn.close()
    payload = b"id\nv\n"
    (generation / "votes-local.csv.gz").write_bytes(b"tampered" if corrupt else payload)
    manifest = {
        "export_format": 5, "generated_at": "2026-10-19T00:00:00+00:00", "generation": "g-0123456789ab",
        "files": [{"name": "votes-local.csv.gz", "bytes": len(payload), "unpacked_bytes": len(payload),
                   "sha256": hashlib.sha256(payload).hexdigest()}],
        "protocols": {"count": protocols_in_manifest}, "tables": [], "relationships": 0, "total_rows": 6,
        "votes": {"count": 1, "members": 3},
        "recipes": [{"id": recipe["id"], "sql": recipe["sql"], "rows": []} for recipe in site.RECIPES],
        "coverage": {"catalog_count": 2, "dossier_count": 2, "bausteine": {}},
    }
    (data / "exports" / "datenstand.json").write_text(json.dumps(manifest), encoding="utf-8")
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
            problems = gate.check_export(_export_dir(Path(tmp), protocols_in_manifest=3, corrupt=True))["problems"]
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(any("votes-local.csv.gz" in problem for problem in problems))
        self.assertTrue(any("protocols" in problem for problem in problems))


if __name__ == "__main__":
    unittest.main()
