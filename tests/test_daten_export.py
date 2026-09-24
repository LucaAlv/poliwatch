from __future__ import annotations

import contextlib
import gzip
import hashlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import _daten_fixture
import build_dip_pulse_site as b
import facts
import persist_dip_pulse_store as pulse_store


READINESS = {"votes": "ready", "aw-profiles": "unavailable", "mp-roster": "ready"}


class ExportHelpersTests(unittest.TestCase):
    def test_format_size_de_uses_german_decimal_comma(self) -> None:
        self.assertEqual(b.format_size_de(512), "512 B")
        self.assertEqual(b.format_size_de(47_200_000), "45,0 MB")

    def test_resolve_data_base_url_accepts_https_http_and_leading_slash(self) -> None:
        self.assertEqual(b.resolve_data_base_url("data/exports"), "data/exports/")
        self.assertEqual(b.resolve_data_base_url("https://example.org/x"), "https://example.org/x/")
        self.assertEqual(b.resolve_data_base_url("http://example.org/x/"), "http://example.org/x/")
        self.assertEqual(b.resolve_data_base_url("/data/"), "/data/")

    def test_resolve_data_base_url_rejects_other_schemes(self) -> None:
        for bad in ("javascript://x", "ftp://example.org/x"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    b.resolve_data_base_url(bad)

    def test_is_url(self) -> None:
        self.assertTrue(b.is_url("https://example.org/datenstand.json"))
        self.assertTrue(b.is_url("http://example.org/datenstand.json"))
        self.assertFalse(b.is_url("data/exports/datenstand.json"))

    def test_surrogate_count(self) -> None:
        self.assertEqual(b._surrogate_count("plain text"), 0)
        self.assertEqual(b._surrogate_count("a\udcffb\udcfe"), 2)

    def test_data_table_name_regex(self) -> None:
        self.assertTrue(b.DATA_TABLE_NAME_RE.match("speeches"))
        self.assertTrue(b.DATA_TABLE_NAME_RE.match("mp_canonical"))
        self.assertFalse(b.DATA_TABLE_NAME_RE.match("bad;name"))
        self.assertFalse(b.DATA_TABLE_NAME_RE.match("bad name"))


class ExportDistributionDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.db_path = self.tmp / "pulse.sqlite"
        self.exports_dir = self.tmp / "exports"
        self.ids = _daten_fixture.seed_store(self.db_path)
        conn = pulse_store.connect(self.db_path)
        try:
            self.mps, self.lookup, self.canonical_by_mp_id = b.collect_abgeordnete(conn)
        finally:
            conn.close()

    def export(self, **overrides):
        kwargs = dict(
            canonical_by_mp_id=self.canonical_by_mp_id,
            mp_lookup=self.lookup,
            readiness=READINESS,
            catalog_count=2,
            dossier_count=2,
            license_text="",
            commit="abc123",
        )
        kwargs.update(overrides)
        return b.export_distribution_data(self.db_path, self.exports_dir, **kwargs)

    def test_every_recipe_has_at_least_one_row_on_the_fixture(self) -> None:
        manifest = self.export()
        for recipe in manifest["recipes"]:
            with self.subTest(recipe=recipe["id"]):
                self.assertGreaterEqual(len(recipe["rows"]), 1, recipe["empty_reason"])

    def test_r1_pools_the_consolidated_mp_like_the_profile_page(self) -> None:
        manifest = self.export()
        ada = next(mp for mp in self.mps if mp["name"] == "Ada Lovelace")
        r1 = next(r for r in manifest["recipes"] if r["id"] == "r1-meiste-reden")
        ada_row = next(row for row in r1["rows"] if row["display_name"].startswith("Ada"))
        self.assertEqual(ada_row["reden"], ada["speech_count"])

    def test_r3_counts_the_vote_only_person_who_never_gets_a_page(self) -> None:
        manifest = self.export()
        r3 = next(r for r in manifest["recipes"] if r["id"] == "r3-abweichler")
        names = {row["display_name"] for row in r3["rows"]}
        self.assertIn("Vera Stimme", names)
        vera_row = next(row for row in r3["rows"] if row["display_name"] == "Vera Stimme")
        # Vera has no aw:/dip:/xml: key in the lookup, so her identity_key
        # (profile:...) must not resolve to a page.
        self.assertNotIn(vera_row["mp_id"], self.lookup)

    def test_r2_groups_by_speech_time_fraktion_not_current_party(self) -> None:
        # switcher_mp's seeded Rede carries speeches.fraktion = 'SPD' even
        # though their mps.party_id is CDU/CSU today (D18/T8: a Fraktionswechsel
        # must not rewrite history). Without the switch, CDU/CSU would read 4
        # Reden and SPD 2; with it, both read 3.
        manifest = self.export()
        r2 = next(r for r in manifest["recipes"] if r["id"] == "r2-redeanteil-fraktion")
        spd_row = next(row for row in r2["rows"] if row["fraktion"] == "SPD")
        cdu_row = next(row for row in r2["rows"] if row["fraktion"] == "CDU/CSU")
        self.assertEqual(spd_row["reden"], 3)
        self.assertEqual(cdu_row["reden"], 3)

    def test_recipe_sql_error_fails_the_export_naming_the_recipe(self) -> None:
        broken = tuple(
            {**recipe, "sql": "SELECT * FROM speeches_does_not_exist LIMIT 5;"}
            if recipe["id"] == "r2-redeanteil-fraktion"
            else recipe
            for recipe in b.RECIPES
        )
        with self.assertRaises(RuntimeError) as ctx:
            self.export(recipes=broken)
        self.assertIn("r2-redeanteil-fraktion", str(ctx.exception))

    def test_recipe_on_empty_votes_table_yields_empty_reason_not_a_failure(self) -> None:
        # A separate, narrower store: dossiers exist (so R1/R2/R5 have rows)
        # but no roll-call vote was ever recorded, the way a build without
        # --enrich votes looks.
        no_votes_db = self.tmp / "no-votes.sqlite"
        conn = pulse_store.connect(no_votes_db)
        pulse_store.initialize(conn)
        now = pulse_store.utc_now()
        with conn:
            party_id = pulse_store.upsert_party(conn, "SPD", now)
            mp_id = pulse_store.upsert_mp(
                conn, now=now, display_name="Ada Lovelace", party_id=party_id,
                identity_key="dip:ada", dip_person_id="ada", is_mdb=True,
            )
            conn.execute(
                """INSERT INTO protocols(id, document_number, date, title, xml_header_json, created_at, updated_at)
                   VALUES ('5900', '20/200', '2024-06-01', 't', '{}', ?, ?)""",
                (now, now),
            )
            conn.execute(
                """INSERT INTO agenda_items(protocol_id, item_index, top_id, heading, created_at, updated_at)
                   VALUES ('5900', 1, 'T1', 'TOP', ?, ?)""",
                (now, now),
            )
            ai = conn.execute("SELECT id FROM agenda_items").fetchone()["id"]
            conn.execute(
                """INSERT INTO speeches(protocol_id, agenda_item_id, rede_id, sequence, mp_id, page,
                   paragraph_count, char_count, text, paragraphs_json, snippet, created_at, updated_at)
                   VALUES ('5900', ?, 'R1', 1, ?, 1, 1, 50, 'x', '[]', 'x', ?, ?)""",
                (ai, mp_id, now, now),
            )
        conn.close()

        no_votes_conn = pulse_store.connect(no_votes_db)
        mps, lookup, canonical_by_mp_id = b.collect_abgeordnete(no_votes_conn)
        no_votes_conn.close()
        readiness = {**READINESS, "votes": "unavailable"}
        manifest = b.export_distribution_data(
            no_votes_db, self.tmp / "no-votes-exports",
            canonical_by_mp_id=canonical_by_mp_id, mp_lookup=lookup,
            readiness=readiness, catalog_count=1, dossier_count=1,
        )
        r3 = next(r for r in manifest["recipes"] if r["id"] == "r3-abweichler")
        r4 = next(r for r in manifest["recipes"] if r["id"] == "r4-knappste-abstimmungen")
        r1 = next(r for r in manifest["recipes"] if r["id"] == "r1-meiste-reden")
        self.assertEqual(r3["rows"], [])
        self.assertEqual(r4["rows"], [])
        self.assertIn("nicht erfasst", r3["empty_reason"])
        self.assertIn("--enrich votes", r3["empty_reason"])
        self.assertGreaterEqual(len(r1["rows"]), 1)

    def test_distribution_copy_drops_paragraphs_json_and_keeps_row_counts(self) -> None:
        manifest = self.export()
        conn = sqlite3.connect(self.exports_dir / manifest["generation"] / manifest["files"][0]["name"])
        # The file on disk is gzipped; unpack it to a temp file to inspect.
        gz_path = self.exports_dir / manifest["generation"] / manifest["files"][0]["name"]
        raw_path = self.tmp / "unpacked.sqlite"
        with gzip.open(gz_path, "rb") as src, raw_path.open("wb") as dst:
            dst.write(src.read())
        dist_conn = sqlite3.connect(raw_path)
        columns = {row[1] for row in dist_conn.execute("PRAGMA table_info(speeches)")}
        self.assertNotIn("paragraphs_json", columns)
        speech_count = dist_conn.execute("SELECT COUNT(*) FROM speeches").fetchone()[0]
        build_conn = sqlite3.connect(self.db_path)
        build_speech_count = build_conn.execute("SELECT COUNT(*) FROM speeches").fetchone()[0]
        self.assertEqual(speech_count, build_speech_count)
        dist_conn.close()
        build_conn.close()
        conn.close()

    def test_mp_canonical_covers_every_mps_row_including_the_vote_only_person(self) -> None:
        manifest = self.export()
        gz_path = self.exports_dir / manifest["generation"] / manifest["files"][0]["name"]
        raw_path = self.tmp / "unpacked2.sqlite"
        with gzip.open(gz_path, "rb") as src, raw_path.open("wb") as dst:
            dst.write(src.read())
        conn = sqlite3.connect(raw_path)
        conn.row_factory = sqlite3.Row
        rows = {row["mp_id"]: (row["canonical_id"], row["has_page"]) for row in conn.execute("SELECT * FROM mp_canonical")}
        conn.close()
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[self.ids["roster_mp"]][0], rows[self.ids["speaker_mp"]][0])
        self.assertEqual(rows[self.ids["vote_only_mp"]][1], 0)
        self.assertEqual(rows[self.ids["roster_mp"]][1], 1)

    def test_manifest_file_sha256_matches_the_file_on_disk(self) -> None:
        manifest = self.export()
        gen_dir = self.exports_dir / manifest["generation"]
        for file_info in manifest["files"]:
            with self.subTest(file=file_info["name"]):
                digest = hashlib.sha256((gen_dir / file_info["name"]).read_bytes()).hexdigest()
                self.assertEqual(digest, file_info["sha256"])

    def test_nineteen_csvs_named_and_headered(self) -> None:
        # The facts tables (T5/T6) are part of the store by the time export
        # runs in a real build; run the engine first so they are here too.
        b.run_facts_engine(self.db_path, self.FACTS_ENTRIES)
        manifest = self.export()
        csv_files = [f["name"] for f in manifest["files"] if f["name"].endswith(".csv.gz")]
        self.assertEqual(len(csv_files), 19)
        for name in ("fact_metrics-local.csv.gz", "facts-local.csv.gz", "fact_sources-local.csv.gz"):
            with self.subTest(name=name):
                self.assertIn(name, csv_files)
        gen_dir = self.exports_dir / manifest["generation"]
        speeches_csv = gen_dir / "speeches-local.csv.gz"
        with gzip.open(speeches_csv, "rt", encoding="utf-8", newline="") as handle:
            header = handle.readline().strip().split(",")
        self.assertIn("mp_id", header)
        self.assertNotIn("paragraphs_json", header)

    def test_facts_tables_get_real_captions_not_the_fallback(self) -> None:
        b.run_facts_engine(self.db_path, self.FACTS_ENTRIES)
        manifest = self.export()
        _chips, table_rows_html, _relationships = b.render_daten_schema(manifest)
        self.assertNotIn("Persistierte Tabelle aus dem Bundestag-Puls-Graph.", table_rows_html)
        for name in facts.FACTS_TABLES:
            with self.subTest(table=name):
                self.assertIn(b.DATABASE_TABLE_DESCRIPTIONS[name], table_rows_html)

    def test_dash_leading_text_is_exported_verbatim(self) -> None:
        manifest = self.export()
        gen_dir = self.exports_dir / manifest["generation"]
        with gzip.open(gen_dir / "speeches-local.csv.gz", "rt", encoding="utf-8", newline="") as handle:
            content = handle.read()
        self.assertIn("-beginnt mit Bindestrich", content)

    def test_null_mp_id_becomes_empty_csv_cell(self) -> None:
        manifest = self.export()
        gen_dir = self.exports_dir / manifest["generation"]
        with gzip.open(gen_dir / "speeches-local.csv.gz", "rt", encoding="utf-8", newline="") as handle:
            import csv as csv_module

            rows = list(csv_module.DictReader(handle))
        null_row = next(row for row in rows if row["rede_id"] == "R3")
        self.assertEqual(null_row["mp_id"], "")

    def test_tables_carry_column_provenance_and_fk_targets(self) -> None:
        manifest = self.export()
        mps_table = next(t for t in manifest["tables"] if t["name"] == "mps")
        aw_column = next(c for c in mps_table["columns"] if c["name"] == "aw_politician_id")
        self.assertEqual(aw_column["source"], "abgeordnetenwatch")
        speeches_table = next(t for t in manifest["tables"] if t["name"] == "speeches")
        mp_id_column = next(c for c in speeches_table["columns"] if c["name"] == "mp_id")
        self.assertEqual(mp_id_column["fk"], "mps.id")

    def test_skip_rule_reuses_unchanged_export(self) -> None:
        first = self.export()
        second = self.export()
        self.assertEqual(first["generation"], second["generation"])
        self.assertEqual(first["inputs_hash"], second["inputs_hash"])

    # T5/D1A: the Fakt der Woche engine runs on every build, right before the
    # export. Two builds on an unchanged store must leave the store's mtime
    # alone, or the export's (mtime, size) rehash guard trips and a 291 MB
    # store is re-hashed and re-exported for nothing.
    FACTS_ENTRIES = [
        {
            "report": {
                "protocol": {"dokumentnummer": number},
                "validation_summary": {"xml_speech_count": 3},
                "acquisition": {"votes": {"acquisition_state": "complete"}},
            }
        }
        for number in ("20/100", "20/101")
    ]

    def test_engine_twice_leaves_the_store_unchanged_and_the_export_reused(self) -> None:
        first_run = b.run_facts_engine(self.db_path, self.FACTS_ENTRIES)
        self.assertTrue(first_run["written"])
        first = self.export()
        before = self.db_path.stat().st_mtime_ns
        second_run = b.run_facts_engine(self.db_path, self.FACTS_ENTRIES)
        self.assertFalse(second_run["written"])
        self.assertEqual(self.db_path.stat().st_mtime_ns, before)
        second = self.export()
        self.assertEqual(first["generation"], second["generation"])
        self.assertEqual(first["inputs_hash"], second["inputs_hash"])

    def test_engine_output_is_exported_as_derived_data(self) -> None:
        b.run_facts_engine(self.db_path, self.FACTS_ENTRIES)
        manifest = self.export()
        tables = {table["name"]: table for table in manifest["tables"]}
        self.assertLessEqual(set(facts.FACTS_TABLES), set(tables))
        # scripts/facts.py computes these from the rest of the store; the
        # fallback would claim DIP as their source.
        for name in facts.FACTS_TABLES:
            with self.subTest(table=name):
                self.assertEqual(
                    {column["source"] for column in tables[name]["columns"]}, {"derived"}
                )

    def test_skip_rule_reexports_when_store_changes(self) -> None:
        first = self.export()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE mps SET display_name = 'Ada Lovelace Renamed' WHERE id = 1")
        # Push the mtime a full second ahead so the (mtime, size) rehash guard
        # trips on every filesystem, including ones with 1 s resolution.
        stat = self.db_path.stat()
        os.utime(self.db_path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        second = self.export()
        self.assertNotEqual(first["source_sha256"], second["source_sha256"])
        self.assertNotEqual(first["generation"], second["generation"])

    def test_skip_rule_reexports_when_recipes_change(self) -> None:
        first = self.export()
        changed = tuple(
            {**r, "sql": r["sql"].replace("LIMIT 5", "LIMIT 4")} if r["id"] == "r2-redeanteil-fraktion" else r
            for r in b.RECIPES
        )
        second = self.export(recipes=changed)
        self.assertNotEqual(first["generation"], second["generation"])

    def test_skip_rule_reexports_when_export_format_bumps(self) -> None:
        first = self.export()
        with mock.patch.object(b, "EXPORT_FORMAT", first["export_format"] + 1):
            second = self.export()
        self.assertNotEqual(first["generation"], second["generation"])
        self.assertEqual(second["export_format"], first["export_format"] + 1)

    def test_force_reexports_even_when_unchanged(self) -> None:
        first = self.export()
        second = self.export(force=True)
        self.assertEqual(first["inputs_hash"], second["inputs_hash"])
        self.assertNotEqual(first["generated_at"], second["generated_at"])

    def test_corrupt_manifest_triggers_a_reexport(self) -> None:
        self.export()
        (self.exports_dir / "datenstand.json").write_text("{not json", encoding="utf-8")
        manifest = self.export()
        self.assertTrue((self.exports_dir / "datenstand.json").exists())
        self.assertEqual(json.loads((self.exports_dir / "datenstand.json").read_text())["generation"], manifest["generation"])

    def test_missing_named_file_triggers_a_reexport(self) -> None:
        first = self.export()
        gen_dir = self.exports_dir / first["generation"]
        (gen_dir / first["files"][0]["name"]).unlink()
        second = self.export()
        self.assertTrue((gen_dir / second["files"][0]["name"]).exists())

    def test_stale_generation_directory_is_removed_after_a_reexport(self) -> None:
        first = self.export()
        first_gen_dir = self.exports_dir / first["generation"]
        self.assertTrue(first_gen_dir.exists())
        changed = tuple(
            {**r, "sql": r["sql"].replace("LIMIT 5", "LIMIT 4")} if r["id"] == "r2-redeanteil-fraktion" else r
            for r in b.RECIPES
        )
        self.export(recipes=changed)
        self.assertFalse(first_gen_dir.exists())

    def test_stale_tmp_files_are_swept_and_none_left_behind(self) -> None:
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        stale = self.exports_dir / "leftover.tmp"
        stale.write_text("stale")
        self.export()
        self.assertFalse(stale.exists())
        remaining_tmp = list(self.exports_dir.rglob("*.tmp"))
        self.assertEqual(remaining_tmp, [])

    def test_concurrent_export_is_refused_while_the_lock_is_held(self) -> None:
        # The recorded pid is this very process, so the holder is alive.
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.exports_dir / ".lock"
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
        try:
            with self.assertRaises(RuntimeError) as ctx:
                self.export()
            self.assertIn(str(os.getpid()), str(ctx.exception))
            self.assertTrue(lock_path.exists())
        finally:
            lock_path.unlink(missing_ok=True)

    def test_lock_left_by_a_dead_process_is_cleared_and_the_export_proceeds(self) -> None:
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.exports_dir / ".lock"
        with mock.patch.object(os, "kill", side_effect=ProcessLookupError):
            lock_path.write_text("4242", encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                manifest = self.export()
        self.assertIn("clearing stale", stderr.getvalue())
        self.assertIn("4242", stderr.getvalue())
        self.assertEqual(manifest["export_format"], b.EXPORT_FORMAT)
        self.assertFalse(lock_path.exists())

    def test_lock_with_an_unreadable_pid_is_treated_as_held(self) -> None:
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.exports_dir / ".lock"
        lock_path.write_text("not-a-pid", encoding="utf-8")
        try:
            with self.assertRaises(RuntimeError):
                self.export()
            self.assertTrue(lock_path.exists())
        finally:
            lock_path.unlink(missing_ok=True)

    def test_refused_export_never_sweeps_the_lock_holders_temp_files(self) -> None:
        # The stale-temp sweep runs only under the lock: a build that loses the
        # lock race must leave the winner's in-flight manifest temp file alone.
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.exports_dir / ".lock"
        in_flight = self.exports_dir / ".datenstand-inflight.json"
        in_flight.write_text("{}", encoding="utf-8")
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        try:
            with self.assertRaises(RuntimeError):
                self.export()
            self.assertTrue(in_flight.exists())
        finally:
            lock_path.unlink(missing_ok=True)

    def test_sqlite_errors_during_the_copy_become_runtime_errors(self) -> None:
        # sqlite3.Connection is immutable, so fail the first statement the
        # copy runs on the fresh distribution connection instead.
        real_connect = sqlite3.connect

        def failing_connect(*args, **kwargs):
            conn = real_connect(*args, **kwargs)
            if kwargs.get("isolation_level", "unset") is None:
                raise sqlite3.OperationalError("database is locked")
            return conn

        with mock.patch.object(b.sqlite3, "connect", side_effect=failing_connect):
            with self.assertRaises(RuntimeError) as ctx:
                self.export()
        self.assertIn("distribution copy failed", str(ctx.exception))
        self.assertIn("database is locked", str(ctx.exception))
        self.assertEqual([p.name for p in self.exports_dir.glob("g-*")], [])

    def test_old_sqlite_raises_data_export_unavailable(self) -> None:
        with mock.patch.object(sqlite3, "sqlite_version_info", (3, 34, 0)):
            with self.assertRaises(b.DataExportUnavailable):
                self.export()

    def test_store_guard_refuses_a_distribution_copy_as_the_build_store(self) -> None:
        manifest = self.export()
        gz_path = self.exports_dir / manifest["generation"] / manifest["files"][0]["name"]
        dist_path = self.tmp / "distribution.sqlite"
        with gzip.open(gz_path, "rb") as src, dist_path.open("wb") as dst:
            dst.write(src.read())
        with self.assertRaises(RuntimeError):
            pulse_store.connect(dist_path)


if __name__ == "__main__":
    unittest.main()
