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


class ReparseCachedXmlTests(unittest.TestCase):
    """A rule change in the parser reaches the cached reports and the store from the
    cached XML, with no re-fetch (A1)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.output_dir = Path(self._tmp.name) / "site"
        (self.output_dir / "data" / "xml").mkdir(parents=True)
        (self.output_dir / "protocols").mkdir()
        self.database = self.output_dir / "data" / "bundestag-pulse.sqlite"
        xml = (FIXTURES / "speech-kinds-befragung-fragestunde.xml").read_text(encoding="utf-8")
        (self.output_dir / "data" / "xml" / "plenarprotokoll-21-6.xml").write_text(xml, encoding="utf-8")
        # The report as the parser of before A1 wrote it: every <rede> a Rede.
        # Dobrindt's opening report (Rede) carries the profile resolved online; Kraft's
        # only sitting item in the report is a Rede of an older parse.
        self.dobrindt = {"id": 4711, "url": "https://www.abgeordnetenwatch.de/profile/dobrindt", "match": "ext_id"}
        self.kraft = {"id": 815, "url": "https://www.abgeordnetenwatch.de/profile/kraft", "match": "ext_id"}
        stale = {
            "rede_id": "OLD",
            "speaker": {"xml_redner_id": "11003516", "first_name": "Alexander", "last_name": "Dobrindt",
                        "display_name": "Alexander Dobrindt", "abgeordnetenwatch": self.dobrindt},
            "char_count": 5,
            "text": "alt",
        }
        stale_kraft = {
            "rede_id": "OLDK",
            "speaker": {"xml_redner_id": "11004792", "first_name": "Rainer", "last_name": "Kraft",
                        "display_name": "Dr. Rainer Kraft", "abgeordnetenwatch": self.kraft},
            "char_count": 5,
            "text": "alt",
        }
        self.report = {
            "protocol": {"id": "5709", "dokumentnummer": "21/6", "datum": "2025-05-14"},
            "validation_summary": {"xml_speech_count": 1},
            "warnings": ["Die XML zählt 9 Erwiderungen, DIP 0.", "Anderes."],
            "api_records": {"aktivitaeten": [{"aktivitaetsart": "Kurzintervention"}]},
            "agenda_items": [
                {"index": 1, "top_id": "Tagesordnungspunkt 1", "heading": "Befragung der Bundesregierung",
                 "xml_speech_count": 1, "xml_speakers": [stale], "xml_speakers_first": [stale]},
                {"index": 2, "top_id": "Tagesordnungspunkt 2", "heading": "Fragestunde",
                 "xml_speech_count": 1, "xml_speakers": [stale_kraft]},
            ],
        }
        (self.output_dir / "data" / "plenarprotokoll-21-6.json").write_text(json.dumps(self.report), encoding="utf-8")

    def entries(self) -> list[dict]:
        return build.load_existing_detail_entries(self.output_dir, [{"dokumentnummer": "21/6"}])

    def test_the_report_is_reparsed_from_its_cached_xml(self) -> None:
        entries = self.entries()
        self.assertEqual(build.reparse_cached_xml(self.output_dir, entries), 1)
        report = entries[0]["report"]
        befragung, fragestunde = report["agenda_items"]
        self.assertEqual([s["speaker"]["display_name"] for s in befragung["xml_speakers"]], ["Alexander Dobrindt", "Verena Hubertz"])
        self.assertEqual(befragung["xml_speech_count"], 2)
        self.assertEqual(befragung["question_formats"], ["befragung"])
        self.assertEqual(befragung["xml_contributions"][0]["kind"], "befragung_frage")
        self.assertEqual(fragestunde["xml_contributions"][0]["kind"], "fragestunde_frage")
        summary = report["validation_summary"]
        self.assertEqual(summary["xml_speech_count"], 2)
        self.assertGreater(summary["xml_contribution_counts"]["fragestunde_antwort"], 0)
        # The DIP check is refreshed: the stale warning goes, the unrelated one stays.
        self.assertEqual(
            summary["contribution_dip_mismatches"], [{"kind": "kurzintervention", "xml": 0, "dip": 1}]
        )
        self.assertEqual(
            report["warnings"],
            ["Anderes.", "Die XML zählt 0 Kurzinterventionen, DIP 1."],
        )

    def test_the_profiles_resolved_online_survive_the_reparse(self) -> None:
        entries = self.entries()
        build.reparse_cached_xml(self.output_dir, entries)
        befragung, fragestunde = entries[0]["report"]["agenda_items"]
        # Dobrindt's Reden and the Antworten he gives carry the profile ...
        for speech in [*befragung["xml_speakers"], *befragung["xml_contributions"]]:
            if speech["speaker"]["last_name"] == "Dobrindt":
                self.assertEqual(speech["speaker"]["abgeordnetenwatch"], self.dobrindt)
        # ... and so does a Fragestunde question of an MdB, by the Redner-ID.
        kraft = [c for c in fragestunde["xml_contributions"] if c["speaker"]["last_name"] == "Kraft"]
        self.assertTrue(kraft)
        self.assertTrue(all(c["speaker"]["abgeordnetenwatch"] == self.kraft for c in kraft))
        # A speaker nobody resolved stays unresolved.
        curio = next(c for c in befragung["xml_contributions"] if c["speaker"]["last_name"] == "Curio")
        self.assertNotIn("abgeordnetenwatch", curio["speaker"])

    def test_the_xml_of_a_cached_report_can_be_fetched_and_a_missing_one_is_said(self) -> None:
        (self.output_dir / "data" / "xml" / "plenarprotokoll-21-6.xml").unlink()
        report_path = self.output_dir / "data" / "plenarprotokoll-21-6.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["protocol"]["xml_url"] = "https://www.bundestag.de/resource/blob/x/21006.xml"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        stderr = io.StringIO()
        with mock.patch.object(build.dip, "fetch_text", return_value="<dbtplenarprotokoll/>") as fetch, \
                contextlib.redirect_stderr(stderr):
            fetched, failed = build.fetch_missing_xml(self.output_dir, self.entries(), pause=0)
            # Nothing is fetched twice.
            self.assertEqual(build.fetch_missing_xml(self.output_dir, self.entries(), pause=0), (0, 0))
        self.assertEqual((fetched, failed), (1, 0))
        fetch.assert_called_once_with("https://www.bundestag.de/resource/blob/x/21006.xml")
        self.assertEqual(
            (self.output_dir / "data" / "xml" / "plenarprotokoll-21-6.xml").read_text(encoding="utf-8"),
            "<dbtplenarprotokoll/>",
        )
        # A repersist over a report with no cached XML says what that leaves behind.
        (self.output_dir / "data" / "xml" / "plenarprotokoll-21-6.xml").unlink()
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            build.repersist_cached_reports(self.output_dir, self.database, build.load_cached_protocols(self.output_dir))
        self.assertIn("1 of 1 cached reports have no cached XML", stderr.getvalue())
        self.assertIn("--fetch-xml", stderr.getvalue())

    def test_a_report_without_cached_xml_is_left_alone(self) -> None:
        (self.output_dir / "data" / "xml" / "plenarprotokoll-21-6.xml").unlink()
        entries = self.entries()
        self.assertEqual(build.reparse_cached_xml(self.output_dir, entries), 0)
        self.assertEqual(entries[0]["report"]["agenda_items"][0]["xml_speakers"][0]["rede_id"], "OLD")

    def test_repersist_stores_reden_and_contributions_apart(self) -> None:
        build.repersist_cached_reports(self.output_dir, self.database, build.load_cached_protocols(self.output_dir))
        conn = sqlite3.connect(self.database)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM speeches").fetchone()[0], 2)
            kinds = dict(conn.execute("SELECT kind, COUNT(*) FROM contributions GROUP BY kind"))
            self.assertGreater(kinds["befragung_frage"], 0)
            self.assertGreater(kinds["fragestunde_antwort"], 0)
            # A Beitrag names its speaker like a Rede does: MdB row, Fraktion, Sprechrolle.
            row = conn.execute(
                "SELECT c.speaker_name, c.fraktion, c.sprechrolle, c.mp_id, c.rede_id, c.page FROM contributions c "
                "WHERE c.kind = 'befragung_antwort' ORDER BY c.sequence LIMIT 1"
            ).fetchone()
            self.assertEqual(row[0], "Alexander Dobrindt")
            self.assertEqual(row[2], "bundesregierung")
            self.assertIsNotNone(row[3])
            # A Fragestunde turn has neither a rede_id nor a page.
            turn = conn.execute(
                "SELECT rede_id, page, agenda_item_id FROM contributions WHERE kind = 'fragestunde_frage' LIMIT 1"
            ).fetchone()
            self.assertEqual((turn[0], turn[1]), (None, None))
            self.assertIsNotNone(turn[2])
        finally:
            conn.close()


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

    def test_non_object_cached_json_aborts_and_leaves_the_store_alone(self) -> None:
        self.repersist()
        before = sha(self.database)
        (self.output_dir / "data" / "plenarprotokoll-21-99.json").write_text("[]", encoding="utf-8")
        with self.assertRaises(build.CachedReportError) as caught:
            self.repersist()
        self.assertIn("top-level JSON value is not an object", str(caught.exception))
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

    def test_the_command_preserves_roster_when_mp_roster_is_selected(self) -> None:
        self.repersist()
        conn = pulse_store.connect(self.database)
        try:
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

        code, err = self.run_main("--repersist", "--enrich", "mp-roster")

        self.assertEqual(code, 0, err)
        conn = sqlite3.connect(self.database)
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM mps WHERE identity_key = 'dip:ada' AND is_mdb = 1").fetchone()[0],
                1,
            )
        finally:
            conn.close()

    def test_the_flag_needs_offline_and_persistence(self) -> None:
        for argv in (["build", "--repersist"], ["build", "--offline", "--repersist", "--no-persist"]):
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    build.parse_args()
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
