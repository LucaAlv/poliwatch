from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401
import validate_store_gate as gate


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
        "votes": {"count": 1, "members": 3}, "recipes": [],
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
