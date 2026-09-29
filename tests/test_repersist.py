"""``--offline --repersist`` (DX-O1, E5, E9): every cached report into a fresh
store, swapped in only when all of them persisted."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import build_dip_pulse_site as build
import persist_dip_pulse_store as pulse_store
from _support import FIXTURES


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RepersistTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.output_dir = Path(self._tmp.name) / "site"
        (self.output_dir / "data").mkdir(parents=True)
        (self.output_dir / "protocols").mkdir()
        self.database = self.output_dir / "data" / "bundestag-pulse.sqlite"
        for fixture, slug in (("report.json", "20-999"), ("demo-report-21-84.json", "21-84")):
            report = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
            (self.output_dir / "data" / f"plenarprotokoll-{slug}.json").write_text(
                json.dumps(report), encoding="utf-8"
            )

    def protocols(self) -> list[dict]:
        return build.load_cached_protocols(self.output_dir)

    def repersist(self, **kwargs):
        return build.repersist_cached_reports(self.output_dir, self.database, self.protocols(), **kwargs)

    def count(self, table: str) -> int:
        conn = sqlite3.connect(self.database)
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            conn.close()

    def test_every_cached_report_lands_in_a_fresh_store(self) -> None:
        entries, replaced = self.repersist()
        self.assertTrue(replaced)
        self.assertEqual(len(entries), 2)
        self.assertEqual(self.count("protocols"), 2)
        # Rows of a protocol that is no longer cached do not survive a re-persist.
        conn = sqlite3.connect(self.database)
        try:
            conn.execute("INSERT INTO protocols(id, document_number, created_at, updated_at) VALUES ('x', '99/1', 't', 't')")
            conn.commit()
        finally:
            conn.close()
        self.repersist()
        self.assertEqual(self.count("protocols"), 2)

    def test_the_roster_rows_are_preserved(self) -> None:
        conn = pulse_store.connect(self.database)
        try:
            pulse_store.initialize(conn)
            now = pulse_store.utc_now()
            with conn:
                pulse_store.upsert_mp(
                    conn,
                    now=now,
                    display_name="Ada Lovelace",
                    party_id=pulse_store.upsert_party(conn, "SPD", now),
                    identity_key="dip:ada",
                    dip_person_id="ada",
                    is_mdb=True,
                )
        finally:
            conn.close()
        self.repersist()
        conn = sqlite3.connect(self.database)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM mps WHERE identity_key = 'dip:ada' AND is_mdb = 1").fetchone()[0], 1)
        finally:
            conn.close()

    def test_malformed_cached_json_aborts_and_leaves_the_store_alone(self) -> None:
        self.repersist()
        before = sha(self.database)
        (self.output_dir / "data" / "plenarprotokoll-21-99.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(build.CachedReportError) as caught:
            self.repersist()
        self.assertIn("plenarprotokoll-21-99.json", str(caught.exception))
        self.assertEqual(before, sha(self.database))
        self.assertFalse(self.database.with_name(f".{self.database.name}.tmp").exists())

    def test_a_report_that_fails_to_persist_leaves_an_old_schema_store_byte_identical(self) -> None:
        # An older schema: a column the current initialize() would add is
        # missing. The source must be read as it is, not migrated, so even a
        # failed run cannot change its bytes.
        conn = pulse_store.connect(self.database)
        try:
            pulse_store.initialize(conn)
            conn.execute("ALTER TABLE mps DROP COLUMN person_roles_json")
            conn.commit()
        finally:
            conn.close()
        before = sha(self.database)
        real = pulse_store.persist_report

        def failing(store, report):
            if (report.get("protocol") or {}).get("dokumentnummer") == "21/84":
                raise ValueError("boom")
            return real(store, report)

        with mock.patch.object(pulse_store, "persist_report", side_effect=failing):
            with self.assertRaises(build.DatabaseRebuildError) as caught:
                self.repersist()
        self.assertIn("21/84", str(caught.exception))
        self.assertIn("boom", str(caught.exception))
        self.assertEqual(before, sha(self.database))
        self.assertNotIn("person_roles_json", self.columns("mps"))
        self.assertFalse(self.database.with_name(f".{self.database.name}.tmp").exists())

    def columns(self, table: str) -> set[str]:
        conn = sqlite3.connect(self.database)
        try:
            return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        finally:
            conn.close()

    def test_a_second_run_with_a_different_clock_keeps_the_file(self) -> None:
        _, replaced = self.repersist()
        self.assertTrue(replaced)
        stat = self.database.stat()
        before = sha(self.database)
        with mock.patch.object(pulse_store, "utc_now", return_value="2099-01-01T00:00:00Z"):
            _, replaced = self.repersist()
        self.assertFalse(replaced)
        after = self.database.stat()
        self.assertEqual((stat.st_ino, stat.st_mtime_ns), (after.st_ino, after.st_mtime_ns))
        self.assertEqual(before, sha(self.database))

    def test_a_content_change_replaces_the_file(self) -> None:
        self.repersist()
        path = self.output_dir / "data" / "plenarprotokoll-21-84.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report["protocol"]["titel"] = "Ein anderer Titel"
        path.write_text(json.dumps(report), encoding="utf-8")
        _, replaced = self.repersist()
        self.assertTrue(replaced)

    def run_main(self, *extra: str) -> tuple[int, str]:
        argv = ["build", "--offline", "--output-dir", str(self.output_dir), *extra]
        err = io.StringIO()
        # What follows the re-persist (Daten export, page rendering) is not under
        # test here, and the fixture MPs carry profile URLs the renderer refuses.
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stderr(err), contextlib.redirect_stdout(
            io.StringIO()
        ), mock.patch.object(build, "run_data_pipeline", return_value=(None, None, [], None, False)), mock.patch.object(
            build, "render_site", return_value=self.output_dir / "index.html"
        ):
            code = build.main()
        return code, err.getvalue()

    def test_the_command_reports_a_failure_as_one_error_line_and_exits_1(self) -> None:
        self.repersist()
        before = sha(self.database)
        (self.output_dir / "data" / "plenarprotokoll-21-99.json").write_text("[1, 2", encoding="utf-8")
        code, err = self.run_main("--repersist")
        self.assertEqual(code, 1)
        self.assertIn("ERROR [repersist]:", err)
        self.assertIn("plenarprotokoll-21-99.json", err)
        self.assertIn("Fix:", err)
        self.assertIn("Docs: README.md#re-persist-the-cached-reports", err)
        self.assertEqual(before, sha(self.database))

    def test_the_command_repersists_then_renders(self) -> None:
        code, err = self.run_main("--repersist")
        self.assertEqual(code, 0, err)
        self.assertIn("repersist: 2 cached reports persisted; store replaced", err)
        code, err = self.run_main("--repersist")
        self.assertEqual(code, 0, err)
        self.assertIn("store content unchanged, file kept", err)

    def test_the_flag_needs_offline_and_persistence(self) -> None:
        for argv in (["build", "--repersist"], ["build", "--offline", "--repersist", "--no-persist"]):
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    build.parse_args()
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
