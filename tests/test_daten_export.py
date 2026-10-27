from __future__ import annotations

import contextlib
import csv
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
import person_registry
import _daten_fixture
import build_dip_pulse_site as b
import facts
import persist_dip_pulse_store as pulse_store
from stable_ids import stable_key


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
            self.mps, self.lookup = b.collect_abgeordnete(conn)
        finally:
            conn.close()

    def export(self, **overrides):
        kwargs = dict(
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
                identity_key="dip:ada",
                occurrence_id="fixture:dip:ada", dip_person_id="ada", is_mdb=True,
            )
            conn.execute(
                """INSERT INTO protocols(id, document_number, date, title, xml_header_json, created_at, updated_at)
                   VALUES ('5900', '20/200', '2024-06-01', 't', '{}', ?, ?)""",
                (now, now),
            )
            conn.execute(
                """INSERT INTO agenda_items(id, protocol_id, item_index, top_id, heading, created_at, updated_at)
                   VALUES ('ai-5900', '5900', 1, 'T1', 'TOP', ?, ?)""",
                (now, now),
            )
            ai = conn.execute("SELECT id FROM agenda_items").fetchone()["id"]
            conn.execute(
                """INSERT INTO speeches(id, protocol_id, agenda_item_id, rede_id, sequence, mp_id, page,
                   paragraph_count, char_count, text, snippet, created_at, updated_at)
                   VALUES ('speech-5900', '5900', ?, 'R1', 1, ?, 1, 1, 50, 'x', 'x', ?, ?)""",
                (ai, mp_id, now, now),
            )
        conn.execute("INSERT INTO speech_rule_inputs SELECT id, ? FROM protocols", (pulse_store.speech_kinds.VERSION,))
        person_registry.reconcile(conn)
        conn.commit()
        conn.close()

        no_votes_conn = pulse_store.connect(no_votes_db)
        mps, lookup = b.collect_abgeordnete(no_votes_conn)
        no_votes_conn.close()
        readiness = {**READINESS, "votes": "unavailable"}
        manifest = b.export_distribution_data(
            no_votes_db, self.tmp / "no-votes-exports",
            mp_lookup=lookup,
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

    def test_unmigrated_store_exports_without_paragraphs_json(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("ALTER TABLE speeches ADD COLUMN paragraphs_json TEXT NOT NULL DEFAULT '[]'")
        self.test_distribution_copy_has_no_paragraphs_json_and_keeps_row_counts()
        with sqlite3.connect(self.db_path) as conn:
            self.assertIn("paragraphs_json", {row[1] for row in conn.execute("PRAGMA table_info(speeches)")})

    def test_distribution_copy_has_no_paragraphs_json_and_keeps_row_counts(self) -> None:
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

    def test_all_twenty_eight_csvs_named_and_headered(self) -> None:
        # The facts tables (T5/T6) are part of the store by the time export
        # runs in a real build; run the engine first so they are here too.
        b.run_facts_engine(self.db_path, self.FACTS_ENTRIES, self.facts_catalog())
        manifest = self.export()
        csv_files = [f["name"] for f in manifest["files"] if f["name"].endswith(".csv.gz")]
        self.assertEqual(len(csv_files), 28)
        for name in (
            "fact_metrics-local.csv.gz", "facts-local.csv.gz", "fact_sources-local.csv.gz",
            "agenda_item_politikfelder-local.csv.gz", "vote_politikfelder-local.csv.gz",
            "vote_proceedings-local.csv.gz",
        ):
            with self.subTest(name=name):
                self.assertIn(name, csv_files)
        gen_dir = self.exports_dir / manifest["generation"]
        speeches_csv = gen_dir / "speeches-local.csv.gz"
        with gzip.open(speeches_csv, "rt", encoding="utf-8", newline="") as handle:
            header = handle.readline().strip().split(",")
        self.assertIn("mp_id", header)
        self.assertNotIn("paragraphs_json", header)

    def test_facts_tables_get_real_captions_not_the_fallback(self) -> None:
        b.run_facts_engine(self.db_path, self.FACTS_ENTRIES, self.facts_catalog())
        manifest = self.export()
        _chips, table_rows_html, _relationships = b.render_daten_schema(manifest)
        self.assertNotIn("Persistierte Tabelle aus dem Bundestag-Puls-Graph.", table_rows_html)
        for name in facts.FACTS_TABLES:
            with self.subTest(table=name):
                self.assertIn(b.DATABASE_TABLE_DESCRIPTIONS[name], table_rows_html)

    # Value: protects=format 8 carries vote context and the Bundestag report source URL through downloads and captions; fails_when=a source column is dropped or its caption is generic; why_new=B4 adds the fields; seam=none
    def test_vote_context_and_debate_url_round_trip_in_format_8_with_captions(self) -> None:
        conn = pulse_store.connect(self.db_path)
        try:
            conn.execute("UPDATE proceedings SET abstract = ? WHERE id = 'vg-1'", ("Erster Absatz\n\nZweiter",))
            conn.execute("UPDATE votes SET context_state = CASE id WHEN 'v1' THEN 'resolved' ELSE 'not_fetched' END")
            conn.execute("UPDATE votes SET debate_url = ? WHERE id = 'v1'", ("https://www.bundestag.de/dokumente/textarchiv/2024/kw11-debatte-123456",))
            conn.execute("INSERT INTO vote_proceedings(vote_id, proceeding_id, rank) VALUES ('v1', 'vg-1', 1)")
            conn.commit()
        finally:
            conn.close()
        manifest = self.export()
        self.assertEqual(manifest["export_format"], 8)
        gen_dir = self.exports_dir / manifest["generation"]

        def read(table):
            with gzip.open(gen_dir / f"{table}-local.csv.gz", "rt", encoding="utf-8", newline="") as handle:
                return list(csv.DictReader(handle))

        self.assertEqual([(r["vote_id"], r["proceeding_id"], r["rank"]) for r in read("vote_proceedings")], [("v1", "vg-1", "1")])
        self.assertEqual({r["id"]: r["context_state"] for r in read("votes")}, {"v1": "resolved", "v2": "not_fetched"})
        self.assertEqual({r["id"]: r["debate_url"] for r in read("votes")}['v1'], "https://www.bundestag.de/dokumente/textarchiv/2024/kw11-debatte-123456")
        self.assertEqual({r["id"]: r["debate_url"] for r in read("votes")}['v2'], "")
        self.assertEqual(b.column_source("votes", "debate_url"), "bundestag.de")
        self.assertEqual({r["id"]: r["abstract"] for r in read("proceedings")}["vg-1"], "Erster Absatz\n\nZweiter")
        _chips, table_rows_html, _relationships = b.render_daten_schema(manifest)
        for name in ("vote_proceedings", "proceedings", "votes"):
            with self.subTest(table=name):
                self.assertIn(b.DATABASE_TABLE_DESCRIPTIONS[name], table_rows_html)
        self.assertIn("context_state", b.DATABASE_TABLE_DESCRIPTIONS["votes"])
        self.assertIn("debate_url", b.DATABASE_TABLE_DESCRIPTIONS["votes"])
        self.assertIn("abstract", b.DATABASE_TABLE_DESCRIPTIONS["proceedings"])

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
        mp_columns = {c["name"]: c for c in mps_table["columns"]}
        for name in ("aw_politician_id", "profile_url", "birth_year", "gender", "profession", "wahlkreis", "bundesland"):
            with self.subTest(column=name):
                self.assertEqual(mp_columns[name]["source"], "abgeordnetenwatch")
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
                "acquisition": {"votes": {"acquisition_state": "complete", "acquired_at": "2026-09-28T10:00:00Z"}},
            }
        }
        for number in ("20/100", "20/101")
    ]

    def facts_catalog(self) -> facts.SittingCatalog:
        """The catalog DIP would list for exactly the sittings this store holds."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            return facts.sitting_catalog(facts.load_protocols(conn), authoritative=True)
        finally:
            conn.close()

    def test_engine_twice_leaves_the_store_unchanged_and_the_export_reused(self) -> None:
        first_run = b.run_facts_engine(self.db_path, self.FACTS_ENTRIES, self.facts_catalog())
        self.assertTrue(first_run["written"])
        first = self.export()
        before = self.db_path.stat().st_mtime_ns
        second_run = b.run_facts_engine(self.db_path, self.FACTS_ENTRIES, self.facts_catalog())
        self.assertFalse(second_run["written"])
        self.assertEqual(self.db_path.stat().st_mtime_ns, before)
        second = self.export()
        self.assertEqual(first["generation"], second["generation"])
        self.assertEqual(first["inputs_hash"], second["inputs_hash"])

    # Value: protects=the standalone facts engine never writes the published store in place: while the snapshot is written no -journal/-wal/-shm sits beside the store, the store is swapped in as a new file with the same mode and the same facts an in-place write gives, and an unchanged snapshot keeps the file; fails_when=run_facts_engine writes through a writable connection to the store again; why_new=handoff 05 left the facts engine's rollback journal beside the published store; seam=write_snapshot wrapped
    def test_engine_writes_a_staged_copy_never_the_published_store(self) -> None:
        reference = self.tmp / "in-place.sqlite"
        import shutil as _shutil
        _shutil.copyfile(self.db_path, reference)
        conn = pulse_store.connect(reference)
        try:
            facts.compute_and_store(conn, facts.ALL_REGISTRY, facts.completeness_from_entries(self.FACTS_ENTRIES),
                                    catalog=self.facts_catalog(), built=facts.built_sources(conn), out=io.StringIO())
            conn.commit()
        finally:
            conn.close()
        os.chmod(self.db_path, 0o640)
        inode = self.db_path.stat().st_ino
        real_write = facts.write_snapshot
        beside = []

        def watching_write(conn, snapshot):
            # Looked at inside the write transaction, while a rollback journal exists.
            def look(statement):
                if statement.startswith("INSERT INTO fact_sources"):
                    beside.extend(path.name for path in self.db_path.parent.iterdir()
                                  if path.name.startswith(self.db_path.name + "-"))
            conn.set_trace_callback(look)
            try:
                real_write(conn, snapshot)
            finally:
                conn.set_trace_callback(None)

        with mock.patch.object(facts, "write_snapshot", side_effect=watching_write) as write:
            self.assertTrue(b.run_facts_engine(self.db_path, self.FACTS_ENTRIES, self.facts_catalog())["written"])
        write.assert_called_once()
        self.assertEqual(beside, [])
        self.assertNotEqual(self.db_path.stat().st_ino, inode)
        self.assertEqual(self.db_path.stat().st_mode & 0o777, 0o640)
        self.assertEqual(list(person_registry.private_dir(self.db_path).glob("*.tmp*")), [])

        def facts_rows(path):
            snapshot = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                return {table: snapshot.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall() for table in facts.FACTS_TABLES}
            finally:
                snapshot.close()

        self.assertEqual(facts_rows(self.db_path), facts_rows(reference))
        inode = self.db_path.stat().st_ino
        self.assertFalse(b.run_facts_engine(self.db_path, self.FACTS_ENTRIES, self.facts_catalog())["written"])
        self.assertEqual(self.db_path.stat().st_ino, inode)

    # Value: protects=a facts write that fails midway leaves the published store byte for byte as it was and no staged copy (full speech text) behind; fails_when=_write_facts_staged stops removing its temp file or swaps in before the write succeeded; why_new=only the successful staged write was pinned; seam=write_snapshot raises
    def test_a_failing_facts_write_keeps_the_store_and_leaves_no_staged_copy(self) -> None:
        before = self.db_path.read_bytes()
        with mock.patch.object(facts, "write_snapshot", side_effect=sqlite3.OperationalError("database or disk is full")):
            with self.assertRaisesRegex(sqlite3.OperationalError, "disk is full"):
                b.run_facts_engine(self.db_path, self.FACTS_ENTRIES, self.facts_catalog())
        self.assertEqual(self.db_path.read_bytes(), before)
        self.assertEqual(list(person_registry.private_dir(self.db_path).glob("*.tmp*")), [])
        self.assertEqual([p.name for p in self.db_path.parent.iterdir() if p.name.startswith(self.db_path.name + "-")], [])

    # Value: protects=the standalone facts engine computes for the build date it is given, with the votes the store holds; fails_when=run_facts_engine drops today or computes with a constant built set; why_new=third ship round (12) today forwarding: only run_data_pipeline's hop into run_facts_engine was pinned; seam=compute_and_store spy
    def test_engine_forwards_the_build_date_and_the_built_set(self) -> None:
        from datetime import date

        with mock.patch.object(facts, "compute_and_store", wraps=facts.compute_and_store) as engine:
            b.run_facts_engine(self.db_path, self.FACTS_ENTRIES, self.facts_catalog(), today=date(2026, 7, 1))
        self.assertEqual(engine.call_args.kwargs["today"], date(2026, 7, 1))
        self.assertEqual(engine.call_args.kwargs["built"], {"votes"})

    def test_engine_output_is_exported_as_derived_data(self) -> None:
        b.run_facts_engine(self.db_path, self.FACTS_ENTRIES, self.facts_catalog())
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
            conn.execute("UPDATE mps SET display_name = 'Ada Lovelace Renamed' WHERE id = ?", (self.ids["roster_mp"],))
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

    # Value: protects=the export regenerates when the store schema or the key version changes while the source bytes stay equal; fails_when=store_schema or key_version is dropped from _inputs_hash so a key-format change reuses stale CSVs; why_new=the skip tests vary only export_format, recipes and store content; seam=none
    def test_skip_rule_reexports_when_store_schema_or_key_version_changes(self) -> None:
        first = self.export()
        with mock.patch.object(b.pulse_store, "SCHEMA_VERSION", b.pulse_store.SCHEMA_VERSION + 1):
            schema = self.export()
        self.assertNotEqual(first["generation"], schema["generation"])
        with mock.patch.object(b, "KEY_VERSION", b.KEY_VERSION + 1):
            keys = self.export()
        self.assertNotEqual(first["generation"], keys["generation"])

    # Value: protects=an export that fails midway leaves the published tree byte for byte as it was (the same manifest, the same generation, nothing new), for a new generation and for a forced re-export of the published one; fails_when=the generation is built inside exports_dir or the published one is removed before the new one is complete; why_new=handoff 05 left the export building inside the published tree; seam=_write_csv fails on its second table
    def test_a_failed_export_leaves_the_published_tree_as_it_was(self) -> None:
        def tree():
            return {path.relative_to(self.exports_dir).as_posix(): path.read_bytes() if path.is_file() else None
                    for path in self.exports_dir.rglob("*")}

        self.export()
        before = tree()
        real_write = b._write_csv
        calls = []

        def failing_write(*args, **kwargs):
            calls.append(args[1])
            if len(calls) == 2:
                self.assertEqual(tree(), before, "nothing appears in the published tree while the export runs")
                raise OSError("disk full")
            return real_write(*args, **kwargs)

        changed = tuple({**r, "sql": r["sql"] + " "} if r["id"] == "r2-redeanteil-fraktion" else r for r in b.RECIPES)
        for label, kwargs in (("new generation", {"recipes": changed}), ("forced re-export", {"force": True})):
            with self.subTest(label), mock.patch.object(b, "_write_csv", side_effect=failing_write):
                calls.clear()
                with self.assertRaises(OSError):
                    self.export(**kwargs)
                self.assertEqual(tree(), before)
                self.assertEqual(list(b.export_work_dir(self.exports_dir).iterdir()), [])
        # A forced re-export failing between setting the published generation
        # aside and renaming the new one in puts the published one back.
        real_replace = Path.replace

        def failing_rename_in(path, target):
            if Path(target).parent == self.exports_dir and Path(target).name.startswith("g-") and path.name.startswith("g-") and path.parent.name.startswith("export-"):
                raise OSError("rename failed")
            return real_replace(path, target)

        with mock.patch.object(Path, "replace", failing_rename_in), self.assertRaises(OSError):
            self.export(force=True)
        self.assertEqual(tree(), before)

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

    # Value: protects=a crashed export's scratch (a store copy, a half-written generation) is swept from the private work directory, and the published tree only ever holds the manifest and complete generations; fails_when=the sweep stops or the export builds inside exports_dir again; why_new=handoff 05 left the export's work files in the published tree; seam=none
    def test_stale_work_files_are_swept_and_none_left_behind(self) -> None:
        work = b.export_work_dir(self.exports_dir)
        crashed = work / "export-crashed" / "g-000000000000"
        crashed.mkdir(parents=True)
        (crashed / "partial.csv.gz.tmp").write_text("stale")
        (work / "export-crashed" / "dist-x.sqlite").write_text("stale")
        manifest = self.export()
        self.assertEqual(sorted(path.name for path in work.iterdir()), [])
        published = {path.relative_to(self.exports_dir).as_posix() for path in self.exports_dir.rglob("*")}
        self.assertEqual(published, {"datenstand.json", manifest["generation"]}
                         | {f"{manifest['generation']}/{file['name']}" for file in manifest["files"]})

    def test_concurrent_export_is_refused_while_the_lock_is_held(self) -> None:
        # The recorded pid is this very process, so the holder is alive.
        lock_path = b.export_work_dir(self.exports_dir) / ".lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
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
        lock_path = b.export_work_dir(self.exports_dir) / ".lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
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
        lock_path = b.export_work_dir(self.exports_dir) / ".lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
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
        lock_path = b.export_work_dir(self.exports_dir) / ".lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        in_flight = lock_path.parent / "export-inflight" / "datenstand.json"
        in_flight.parent.mkdir()
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

    # Value: protects=every manifest input the page renders from re-exports when it changes (tag, licence, catalog and dossier counts, each readiness state) and the same inputs reuse the generation; fails_when=one of them is dropped from _inputs_hash, so a stale manifest keeps the old tag in its file names or the old counts on the page; why_new=A.2 test follow-ups: only source, recipes, format, schema/key version and issues URL were pinned; seam=none
    def test_skip_rule_reexports_when_any_rendered_input_changes(self) -> None:
        first = self.export()
        self.assertEqual(self.export()["generation"], first["generation"])
        changes = {
            "tag": {"tag": "v1"},
            "license": {"license_text": "CC BY 4.0"},
            "catalog_count": {"catalog_count": 3},
            "dossier_count": {"dossier_count": 3},
            **{f"readiness {feature}": {"readiness": {**READINESS, feature: "partial"}} for feature in READINESS},
        }
        for label, override in changes.items():
            with self.subTest(label):
                self.assertNotEqual(self.export(**override)["generation"], first["generation"])
        self.assertEqual(self.export()["generation"], first["generation"])

    # Value: protects=the manifest names each table's stable key exactly: its declared primary-key columns in key order; fails_when=stable_keys lists other columns or drops one of a composite key (no composite key of this schema declares its columns out of table order, so key order is not distinguishable here); why_new=registry follow-ups (3): the manifest test checked only that the list is not empty; seam=none
    def test_manifest_stable_keys_are_the_declared_primary_keys(self) -> None:
        manifest = self.export()
        keys = {table["name"]: table["stable_keys"] for table in manifest["tables"]}
        self.assertEqual(keys, {
            "agenda_item_documents": ["agenda_item_id", "document_id", "source"],
            "agenda_item_politikfelder": ["agenda_item_id", "politikfeld"],
            "agenda_item_votes": ["agenda_item_id", "vote_id"],
            "agenda_items": ["id"], "contributions": ["id"], "datenstand": ["tag"], "documents": ["id"],
            "mp_canonical": ["mp_id"], "mps": ["id"], "parties": ["id"], "person_aliases": ["id"],
            "person_bindings": ["id"], "person_records": ["id"], "persons": ["id"],
            "proceeding_positions": ["id"], "proceedings": ["id"], "protocols": ["id"],
            "schema_migrations": ["version"], "speech_rule_inputs": ["protocol_id"], "speeches": ["id"],
            "vote_documents": ["vote_id", "document_id"], "vote_fractions": ["vote_id", "party_id"],
            "vote_members": ["vote_id", "mp_id"], "vote_politikfelder": ["vote_id", "politikfeld"],
            "vote_proceedings": ["vote_id", "proceeding_id"], "votes": ["id"],
        })

    def _export_acting_after_copy(self, act):
        """Export with ``act()`` run right after the build store was copied into
        the distribution copy (the window another build's swap could hit)."""
        real_connect = sqlite3.connect

        class ActAfterBackup(sqlite3.Connection):
            def backup(self, target, *args, **kwargs):
                super().backup(target, *args, **kwargs)
                act()

        def connect(*args, **kwargs):
            if kwargs.get("uri"):
                kwargs["factory"] = ActAfterBackup
            return real_connect(*args, **kwargs)

        with mock.patch.object(b.sqlite3, "connect", side_effect=connect):
            return self.export()

    # Value: protects=a store replaced while the export copies it is refused instead of published under the hash of the file it replaced; fails_when=the stat comparison after backup() is dropped; why_new=export snapshot/swap guards had no test; seam=the read-only source connection's backup() touches the store's mtime after copying
    def test_a_store_changed_during_the_copy_is_refused(self) -> None:
        def touch():
            stat = self.db_path.stat()
            os.utime(self.db_path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

        with self.assertRaisesRegex(RuntimeError, "changed while it was copied"):
            self._export_acting_after_copy(touch)
        self.assertEqual([p.name for p in self.exports_dir.glob("g-*")], [])
        self.assertFalse((self.exports_dir / "datenstand.json").exists())

    # Value: protects=mp_canonical is read from the distribution copy, so it maps exactly the mps rows it is published with even if the store moves on after the copy; fails_when=the mapping is read from the build store (or the caller) instead of the copy; why_new=export snapshot/swap guards had no test; seam=after backup() two mps rows swap persons in the store, its mtime restored so the swap guard passes
    def test_mp_canonical_maps_the_rows_of_the_copy(self) -> None:
        with contextlib.closing(sqlite3.connect(self.db_path)) as conn:
            before = dict(conn.execute("SELECT id, person_id FROM mps"))
        (a, person_a), (c, person_c) = next(
            (x, y) for x in sorted(before.items()) for y in sorted(before.items()) if x[1] != y[1] and len(x[1]) == len(y[1])
        )

        def swap():
            stat = self.db_path.stat()
            with contextlib.closing(sqlite3.connect(self.db_path)) as conn:
                conn.execute("UPDATE mps SET person_id = CASE id WHEN ? THEN ? ELSE ? END WHERE id IN (?, ?)", (a, person_c, person_a, a, c))
                conn.commit()
            self.assertEqual(self.db_path.stat().st_size, stat.st_size)
            os.utime(self.db_path, ns=(stat.st_atime_ns, stat.st_mtime_ns))

        manifest = self._export_acting_after_copy(swap)
        gz_path = self.exports_dir / manifest["generation"] / manifest["files"][0]["name"]
        dist_path = self.tmp / "distribution.sqlite"
        with gzip.open(gz_path, "rb") as src, dist_path.open("wb") as dst:
            dst.write(src.read())
        with contextlib.closing(sqlite3.connect(dist_path)) as conn:
            self.assertEqual(dict(conn.execute("SELECT mp_id, canonical_id FROM mp_canonical")), before)
        with contextlib.closing(sqlite3.connect(self.db_path)) as conn:
            self.assertEqual(conn.execute("SELECT person_id FROM mps WHERE id = ?", (a,)).fetchone()[0], person_c)

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


class RecipeRepresentativeTests(unittest.TestCase):
    """r1 and r3 show each person under one row of theirs, chosen by content:
    a roster row, then a speaker row, then the smallest identity_key, never
    by the hashed mps.id."""

    PERSONS = (
        # person, identity_key, display_name, is_mdb, xml_redner_id
        ("p-1", "dip:1", "Ada Lovelace, MdB, SPD", 0, None),
        ("p-1", "xml:11", "Ada Lovelace", 0, "11"),
        ("p-2", "dip:7", "Bea Zwei", 0, None),
        ("p-2", "profile:x", "Zwei, Bea", 0, None),
        ("p-3", "dip:9", "Dr. Cem Drei", 1, None),
        ("p-3", "xml:33", "Cem Drei", 0, "33"),
    )

    def rows(self, members: list[tuple[str, tuple]]) -> dict[str, dict[str, tuple]]:
        conn = sqlite3.connect(":memory:")
        conn.executescript(
            """
            CREATE TABLE parties (id TEXT PRIMARY KEY, name TEXT);
            CREATE TABLE mps (id TEXT PRIMARY KEY, identity_key TEXT, person_id TEXT, display_name TEXT,
                              party_id TEXT, is_mdb INTEGER, xml_redner_id TEXT);
            CREATE TABLE mp_canonical (mp_id TEXT PRIMARY KEY, canonical_id TEXT, has_page INTEGER);
            CREATE TABLE speeches (mp_id TEXT, char_count INTEGER);
            CREATE TABLE vote_members (vote_id TEXT, mp_id TEXT, party_id TEXT, vote TEXT);
            CREATE TABLE vote_fractions (vote_id TEXT, party_id TEXT, leading_vote TEXT);
            INSERT INTO parties VALUES ('spd', 'SPD');
            INSERT INTO vote_fractions VALUES ('v1', 'spd', 'yes');
            """
        )
        for mp_id, (person, identity, name, is_mdb, xml) in members:
            conn.execute("INSERT INTO mps VALUES (?, ?, ?, ?, 'spd', ?, ?)", (mp_id, identity, person, name, is_mdb, xml))
            conn.execute("INSERT INTO mp_canonical VALUES (?, ?, 1)", (mp_id, person))
            conn.execute("INSERT INTO speeches VALUES (?, 100)", (mp_id,))
            conn.execute("INSERT INTO vote_members VALUES ('v1', ?, 'spd', 'no')", (mp_id,))
        try:
            return {
                recipe_id: {row[0]: row[1:] for row in conn.execute(b.RECIPES_BY_ID[recipe_id]["sql"])}
                for recipe_id in ("r1-meiste-reden", "r3-abweichler")
            }
        finally:
            conn.close()

    def test_the_representative_row_is_chosen_by_content_not_by_its_hashed_id(self) -> None:
        ids = [f"mp-{n}" for n in range(len(self.PERSONS))]
        forward = list(zip(ids, self.PERSONS))
        backward = list(zip(reversed(ids), self.PERSONS))[::-1]
        # Neither the id order nor the insert order may decide.
        for order, members in (("forward", forward), ("backward", backward)):
            with self.subTest(order=order):
                rows = self.rows(members)
                # The speaker row over a DIP title; identity_key over the id hash;
                # the roster row over a speaker row. Every row's Reden pool.
                self.assertEqual(rows["r1-meiste-reden"], {
                    "p-1": ("Ada Lovelace", "SPD", 2, 200),
                    "p-2": ("Bea Zwei", "SPD", 2, 200),
                    "p-3": ("Dr. Cem Drei", "SPD", 2, 200),
                })
                self.assertEqual(rows["r3-abweichler"], {
                    "p-1": ("Ada Lovelace", "SPD", 1),
                    "p-2": ("Bea Zwei", "SPD", 1),
                    "p-3": ("Dr. Cem Drei", "SPD", 1),
                })

    def test_the_personenseite_takes_its_heading_from_the_same_row(self) -> None:
        # Two roll-call style rows of one person, neither roster nor speaker:
        # the smaller identity_key (dip:1) wins although its mps.id sorts last.
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                now = pulse_store.utc_now()
                with conn:
                    spd = pulse_store.upsert_party(conn, "SPD", now)
                    dip_row = pulse_store.upsert_mp(
                        conn, now=now, display_name="Aydan Özoguz, MdB, SPD", party_id=spd,
                        identity_key=pulse_store.mp_identity(dip_person_id="1"), dip_person_id="1",
                        occurrence_id=stable_key("contribution", "c1"))
                    profile_url = "https://example.org/oezoguz"
                    profile_row = pulse_store.upsert_mp(
                        conn, now=now, display_name="Özoguz, Aydan", party_id=spd,
                        identity_key=pulse_store.mp_identity(profile_url=profile_url),
                        occurrence_id="fixture:" + pulse_store.mp_identity(profile_url=profile_url), profile_url=profile_url)
                    self.assertLess(profile_row, dip_row)
                    persons = [row[0] for row in conn.execute("SELECT person_id FROM mps ORDER BY id")]
                    person_registry.merge(conn, persons)
                conn.row_factory = sqlite3.Row
                mps, _ = b.collect_abgeordnete(conn)
                conn.row_factory = None
                self.assertEqual([(mp["name"], mp["has_page"]) for mp in mps], [("Aydan Özoguz", True)])
            finally:
                conn.close()
