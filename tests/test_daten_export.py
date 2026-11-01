from __future__ import annotations

import contextlib
import csv
import dataclasses
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import antrag_text
import person_registry
import publication_state as publication
import _daten_fixture
import build_dip_pulse_site as b
import facts
import persist_dip_pulse_store as pulse_store
from stable_ids import stable_key


READINESS = {"votes": "ready", "aw-profiles": "unavailable", "mp-roster": "ready"}


def _r2_limited_to_4() -> tuple[dict, ...]:
    return tuple({**r, "sql": r["sql"].replace("LIMIT 5", "LIMIT 4")} if r["id"] == "r2-redeanteil-fraktion" else r for r in b.RECIPES)


def authored(field: str) -> Path:
    return b.REPO_ROOT / b.CODEBOOK_INPUT_FILES[field]


class ExportHelpersTests(unittest.TestCase):
    # Value: protects=the export's authored codebook inputs point at committed files; fails_when=an input is renamed or moved without updating CODEBOOK_INPUT_FILES, which would fail every export run; why_new=other tests read the inputs through the mapping; seam=none; no_claim=input content
    def test_codebook_inputs_are_committed_files(self) -> None:
        for field in b.CODEBOOK_INPUT_FILES:
            self.assertTrue(authored(field).is_file(), field)

    # Value: protects=DATA.md names the codes and period units the store actually holds; fails_when=result_scope is documented with German labels instead of its codes, or min_history_weeks as weeks while monthly metrics store months; why_new=both definitions were wrong until the 2026-10-30 review; seam=none; no_claim=other columns' wording
    def test_codebook_matches_stored_codes_and_period_units(self) -> None:
        dictionary = json.loads(authored("dictionary").read_text())["tables"]
        scope = dictionary["votes"]["columns"]["result_scope"]
        for code in ("application", "proposition"):
            self.assertIn(code, scope["unit"])
            self.assertIn(code, scope["meaning"])
        self.assertTrue(any(metric["min_history_weeks"] == facts.MIN_HISTORY_MONTHS for metric in facts.MONTHLY_REGISTRY))
        history = dictionary["fact_metrics"]["columns"]["min_history_weeks"]
        self.assertIn("Monate", history["unit"])
        self.assertIn("Monatskennzahlen", history["meaning"])
        self.assertIn("vor Einführung des Felds", scope["unit"])
        self.assertIn("chancellor_election", dictionary["votes"]["columns"]["procedure_type"]["unit"])

    # Value: protects=a column the project computes is licensed and tagged as our own work, not as source data; fails_when=a derived column (result_scope, procedure_type, person_id, aw_match) falls back to its table's source tag or layer; why_new=the layer guard sees only tag-layer contradictions, and these columns were tagged as source until the 2026-10-30 review; seam=none; no_claim=columns whose source text does not start with Projektableitung
    def test_project_derived_columns_carry_our_own_layer_and_tag(self) -> None:
        dictionary = json.loads(authored("dictionary").read_text())["tables"]
        for table, column in (("votes", "result_scope"), ("votes", "procedure_type"), ("mps", "person_id"), ("mps", "aw_match")):
            with self.subTest(column=f"{table}.{column}"):
                self.assertEqual(b.column_source(table, column), "derived")
                self.assertEqual(dictionary[table]["columns"][column]["license"], "eigene-auswertung")
        for table, entry in dictionary.items():
            for column, definition in entry["columns"].items():
                if definition["source"].startswith("Projektableitung"):
                    with self.subTest(derived=f"{table}.{column}"):
                        self.assertTrue(definition["license"].startswith("eigene-"), definition["license"])
        for column in ("display_name", "party_id"):
            self.assertEqual(dictionary["mps"]["columns"][column]["license"], "dip-oder-bundestag-abstimmungen")

    # Value: protects=definitions corrected against the real store (source kind, unit, created_at semantics) and the methods doc quoting CONTEXT.md/ADRs verbatim; fails_when=a correction is reverted (e.g. created_at of re-persisted tables called a first-ingest time) or a quotation drifts from its source; why_new=completeness checks cannot see wrong content; seam=none; no_claim=every other definition is true
    def test_authored_definitions_distinguish_sources_units_and_exact_quotations(self) -> None:
        dictionary = json.loads(authored("dictionary").read_text())["tables"]
        # replace_protocol deletes and re-inserts a sitting's rows; and every
        # store rebuild (online build, --repersist) stages a fresh store, so no
        # created_at is a first-ingest time.
        for table in ("agenda_items", "speeches", "contributions"):
            self.assertIn("gleich updated_at", dictionary[table]["columns"]["created_at"]["meaning"])
        created = {name: entry["columns"]["created_at"]["meaning"] for name, entry in dictionary.items() if "created_at" in entry["columns"]}
        self.assertGreaterEqual(len(created), 10)
        for table, meaning in created.items():
            with self.subTest(table=table):
                self.assertNotIn("erstmals", meaning)
                self.assertIn("kein Zeitpunkt der ersten Erfassung", meaning)
        self.assertIn("neu auf", created["protocols"])
        self.assertIn("DIP-API", dictionary["proceedings"]["columns"]["title"]["source"])
        self.assertIn("XML", dictionary["speeches"]["columns"]["text"]["source"])
        self.assertIn("UTC", dictionary["speeches"]["columns"]["created_at"]["unit"])
        self.assertIn("nicht aus einer externen Quelle", dictionary["speeches"]["columns"]["created_at"]["source"])
        self.assertIn("0 bis einschließlich 1", dictionary["facts"]["columns"]["percentile"]["unit"])
        self.assertIn("Kandidaten", dictionary["facts"]["columns"]["week_n"]["meaning"])
        self.assertIn("Bundestag", dictionary["mps"]["columns"]["profile_url"]["source"])
        for table in dictionary.values():
            for column in table["columns"].values():
                self.assertNotIn("übernommen oder berechnet gemäß", column["meaning"])
        root = Path(b.__file__).resolve().parent.parent
        sources = "\n".join((root / path).read_text() for path in ("CONTEXT.md", "docs/adr/0001-count-speeches-by-sprechrolle.md", "docs/adr/0002-kurzinterventionen-are-not-reden.md"))
        quotes = re.findall("“([^“”]+)”", authored("methods").read_text())
        self.assertGreaterEqual(len(quotes), 10)
        for quote in quotes:
            self.assertIn(quote, sources)

    # Value: protects=an embedded document's code block keeps its "#" lines while real headings move down a level; fails_when=demotion ignores fences and a shell comment becomes a DATA.md heading; why_new=the embedded docs had no code block, so no test held one; seam=none; no_claim=other Markdown block types
    def test_heading_demotion_leaves_fenced_code_alone(self) -> None:
        text = "## Teil\n```sh\n# Kommentar\n```\n~~~~\n# auch Code\n~~~\n# noch Code\n~~~~\n### Unterteil\n"
        self.assertEqual(
            b._demote_headings(text).split("\n"),
            ["### Teil", "```sh", "# Kommentar", "```", "~~~~", "# auch Code", "~~~", "# noch Code", "~~~~", "#### Unterteil"],
        )

    # Value: protects=documents.id is described as the project key docs/stable-ids.md defines, not a DIP id; fails_when=the dictionary source again calls it a DIP-API id; why_new=the adversarial review found the stale text on 2026-10-30; seam=none; no_claim=other id columns
    def test_documents_id_source_names_the_project_key(self) -> None:
        source = json.loads(authored("dictionary").read_text())["tables"]["documents"]["columns"]["id"]["source"]
        self.assertIn("Herausgeber", source)
        self.assertNotIn("DIP-API: id", source)

    def test_recipes_hash_ignores_html_only_column_keys(self) -> None:
        display_only = tuple(
            {**recipe, "columns": tuple({**column, "align": "text", "truncate": 5, "hidden": False} for column in recipe["columns"])}
            for recipe in b.RECIPES
        )
        self.assertEqual(b._recipes_hash(display_only), b._recipes_hash(b.RECIPES))
        renamed = ({**b.RECIPES[0], "columns": ({**b.RECIPES[0]["columns"][0], "meaning": "anders"},) + b.RECIPES[0]["columns"][1:]},)
        self.assertNotEqual(b._recipes_hash(renamed + b.RECIPES[1:]), b._recipes_hash(b.RECIPES))

    def test_recipe_csv_counts_unencodable_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recipe.csv"
            self.assertEqual(b._write_recipe_csv(path, ["a", "b"], [{"a": "x\udc80", "b": None}, {"a": 1, "b": "ok"}]), 1)
            self.assertEqual(path.read_text(encoding="utf-8"), "a,b\nx?,\n1,ok\n")

    # Value: protects=a bare CR in a CSV cell is quoted so a reader does not see a row break, on every Python patch level; fails_when=_write_csv_row stops quoting rows that hold a CR or csv.writer's own quoting is relied on for it; why_new=csv.writer with lineterminator LF quotes CR only on newer Python patch levels, and DATA.md promises line breaks stay unchanged; seam=none; no_claim=other cell conventions
    def test_csv_writers_quote_a_bare_carriage_return_on_every_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recipe.csv"
            rows = [{"a": "x\ry", "b": 'q"\r\n'}, {"a": "plain", "b": "1,2"}]
            b._write_recipe_csv(path, ["a", "b"], rows)
            raw = path.read_bytes().decode("utf-8")
            self.assertEqual(raw, 'a,b\n"x\ry","q""\r\n"\nplain,"1,2"\n')
            back = list(csv.reader(io.StringIO(raw, newline="")))
            self.assertEqual(back, [["a", "b"], ["x\ry", 'q"\r\n'], ["plain", "1,2"]])
        with tempfile.TemporaryDirectory() as tmp:
            conn = sqlite3.connect(":memory:")
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
            conn.execute("INSERT INTO t VALUES (1, ?)", ("a\rb",))
            path = Path(tmp) / "t.csv.gz"
            columns = [{"name": "id", "pk": 1}, {"name": "v", "pk": 0}]
            b._write_csv(conn, "t", columns, path)
            text = gzip.decompress(path.read_bytes()).decode("utf-8")
            self.assertEqual(text, 'id,v\n1,"a\rb"\n')

    # Value: protects=a BLOB or a repeated recipe output name stops the export instead of writing b'...' text or one value in two columns; fails_when=_csv_cell_text or the duplicate-name check in _write_recipe_csv is removed; why_new=both were silent wrong output, though no stored column or recipe triggers them today; seam=none; no_claim=where main() reports the error
    def test_recipe_csv_refuses_blobs_and_repeated_column_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recipe.csv"
            with self.assertRaisesRegex(RuntimeError, "BLOB"):
                b._write_recipe_csv(path, ["a"], [{"a": b"\x00"}])
            with self.assertRaisesRegex(RuntimeError, "repeats the column name 'a'"):
                b._write_recipe_csv(path, ["a", "a"], [{"a": 1}])
            # The stored-table writer refuses a BLOB the same way (no b'...' repr in a CSV).
            conn = sqlite3.connect(":memory:")
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v BLOB)")
            conn.execute("INSERT INTO t VALUES (1, ?)", (b"\x00",))
            with self.assertRaisesRegex(RuntimeError, "BLOB"):
                b._write_csv(conn, "t", [{"name": "id", "pk": 1}, {"name": "v", "pk": 0}], Path(tmp) / "t.csv.gz")

    # Value: protects=a CR or CRLF from an edited input stays inside its DATA.md table cell; fails_when=_md_cell escapes only LF, leaving a CR that ends the table row in some renderers; why_new=only LF and the pipe were tested; seam=none; no_claim=other markdown escaping
    def test_md_cell_turns_every_line_break_form_into_br(self) -> None:
        self.assertEqual(b._md_cell("a|b\r\nc\rd\ne"), "a\\|b<br>c<br>d<br>e")

    # Value: protects=DATA.md's licence line prints one full stop after the operator text, also when the text already ends in one; fails_when=_license_line_text appends a stop unconditionally, printing two dots after the real short string; why_new=the real string ends in a stop and printed two; seam=none; no_claim=the licence wording
    def test_licence_line_ends_in_exactly_one_full_stop(self) -> None:
        self.assertEqual(b._license_line_text("CC BY 4.0. Details in LICENSE-DATA.md."), "CC BY 4.0. Details in LICENSE-DATA.md.")
        self.assertEqual(b._license_line_text("CC BY 4.0"), "CC BY 4.0.")

    def test_recipe_output_definitions_name_no_other_recipe(self) -> None:
        for recipe in b.RECIPES:
            for column in recipe["columns"]:
                with self.subTest(recipe=recipe["id"], column=column["name"]):
                    self.assertIsNone(re.search(r"\br[1-6]\b", column["meaning"]))

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
        # A release export checks the real checkout's authored inputs; these tests
        # do not depend on whether the developer has committed them.
        patcher = mock.patch.object(b.build_revision, "authored_inputs_problem", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

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

    # Value: protects=a real export (DATA.md with the authored inputs, datenstand.json) passes the public-output validator that now scans both; fails_when=authored text or the manifest holds a denylisted pattern, which would turn CI red on every build; why_new=validate_public_output started scanning data/exports documents; seam=none; no_claim=other surfaces
    def test_a_real_export_passes_the_public_output_validator(self) -> None:
        self.exports_dir = self.tmp / "site" / "data" / "exports"
        self.export()
        self.assertTrue((self.exports_dir / "datenstand.json").is_file())
        self.assertEqual(publication.validate_public_output(self.tmp / "site"), [])

    def test_every_recipe_has_at_least_one_row_on_the_fixture(self) -> None:
        manifest = self.export()
        for recipe in manifest["recipes"]:
            with self.subTest(recipe=recipe["id"]):
                self.assertGreaterEqual(len(recipe["rows"]), 1, recipe["empty_reason"])

    def test_recipe_csvs_replay_the_distribution_snapshot_in_sql_order(self) -> None:
        manifest = self.export(tag="v-test", commit="abc123def456")
        gen_dir = self.exports_dir / manifest["generation"]
        snapshot = self.tmp / "recipe-replay.sqlite"
        snapshot.write_bytes(gzip.decompress((gen_dir / manifest["files"][0]["name"]).read_bytes()))
        inventory = {entry["name"]: entry for entry in manifest["files"]}
        with contextlib.closing(sqlite3.connect(snapshot)) as conn:
            conn.row_factory = sqlite3.Row
            for recipe in manifest["recipes"]:
                with self.subTest(recipe=recipe["id"]):
                    original = b.RECIPES_BY_ID[recipe["id"]]
                    self.assertEqual(recipe["sql"], original["sql"])
                    self.assertTrue(recipe["sql"].endswith("LIMIT 5;"))
                    cursor = conn.execute(recipe["sql"])
                    columns = [column[0] for column in cursor.description]
                    rows = [dict(row) for row in cursor.fetchall()]
                    self.assertEqual(recipe["columns"], columns)
                    self.assertEqual(recipe["rows"], rows)
                    path = gen_dir / recipe["file"]
                    with path.open(encoding="utf-8", newline="") as handle:
                        csv_rows = list(csv.reader(handle))
                    self.assertEqual(csv_rows, [columns] + [["" if row[name] is None else str(row[name]) for name in columns] for row in rows])
                    entry = inventory[recipe["file"]]
                    self.assertEqual(entry["kind"], "recipe_csv")
                    self.assertEqual(entry["rows"], len(rows))
                    self.assertEqual(entry["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
                    self.assertEqual(entry["bytes"], path.stat().st_size)
        r5 = manifest["recipes"][4]
        self.assertEqual(r5["columns"], ["proceeding_id", "wahlperiode", "title", "typ", "reden", "sitzungen", "erste_drucksache"])
        with (gen_dir / r5["file"]).open(newline="", encoding="utf-8") as handle:
            self.assertEqual(list(csv.reader(handle))[1][4:], ["7", "2", "20/100"])

    def test_recipe_csv_keeps_quotes_newlines_unicode_formula_text_and_nulls(self) -> None:
        text = '=1,"Grüße"\nzweite Zeile'
        changed = ({**b.RECIPES[0], "sql": "SELECT " + "'" + text + "' AS display_name, NULL AS fraktion, '' AS mp_id;"},)
        manifest = self.export(recipes=changed)
        recipe = manifest["recipes"][0]
        with (self.exports_dir / manifest["generation"] / recipe["file"]).open(encoding="utf-8", newline="") as handle:
            self.assertEqual(list(csv.reader(handle)), [["display_name", "fraktion", "mp_id"], [text, "", ""]])
        self.assertIsNone(recipe["rows"][0]["fraktion"])
        self.assertEqual(recipe["rows"][0]["mp_id"], "")

    def test_empty_store_has_header_only_recipes_and_explicit_empty_coverage(self) -> None:
        database = self.tmp / "empty.sqlite"
        conn = pulse_store.connect(database)
        pulse_store.initialize(conn)
        conn.close()
        manifest = b.export_distribution_data(database, self.exports_dir)
        gen_dir = self.exports_dir / manifest["generation"]
        codebook = (gen_dir / "DATA.md").read_text()
        self.assertEqual(manifest["coverage"]["wahlperioden"], [])
        self.assertIn("Leerer Datenbestand", codebook)
        self.assertIn("lokaler Export", codebook)
        self.assertIn("Revision unbekannt", codebook)
        self.assertIn("keinen Versions-DOI", codebook)
        self.assertNotIn("https://github.com/", codebook.split("## Diesen Export zitieren")[1])
        snapshot = self.tmp / "empty-replay.sqlite"
        snapshot.write_bytes(gzip.decompress((gen_dir / manifest["files"][0]["name"]).read_bytes()))
        with contextlib.closing(sqlite3.connect(snapshot)) as conn:
            for recipe in manifest["recipes"]:
                with self.subTest(recipe=recipe["id"]):
                    cursor = conn.execute(recipe["sql"])
                    columns = [column[0] for column in cursor.description]
                    self.assertEqual(cursor.fetchall(), [])
                    self.assertEqual(recipe["columns"], columns)
                    with (gen_dir / recipe["file"]).open(encoding="utf-8", newline="") as handle:
                        self.assertEqual(list(csv.reader(handle)), [columns])
                    self.assertEqual(recipe["rows"], [])
                    # The whole line, so a reason that ends in a period does not get a second one.
                    self.assertIn(f"Leeres Ergebnis: {recipe['empty_reason'].rstrip('.')}.\n", codebook)
                    entry = next(file for file in manifest["files"] if file["name"] == recipe["file"])
                    self.assertEqual(entry["rows"], 0)
                    self.assertEqual(entry["sha256"], b._hash_file(gen_dir / recipe["file"]))

    def test_codebook_describes_all_real_columns_and_snapshot_coverage(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE protocols SET document_number = '21/101', date = '2025-05-22' WHERE id = '5802'")
            conn.execute("UPDATE votes SET protocol_id = CASE id WHEN 'v1' THEN '5801' ELSE '5802' END")
        b.run_facts_engine(self.db_path, self.FACTS_ENTRIES, self.facts_catalog())
        manifest = self.export(tag="v-test", commit="abc123def456", catalog_count=100, dossier_count=2)
        codebook_path = self.exports_dir / manifest["generation"] / "DATA.md"
        codebook = codebook_path.read_text()
        self.assertIn("Release v-test", codebook)
        self.assertIn("`abc123def456`", codebook)
        self.assertIn(f"Store-Schema: {pulse_store.SCHEMA_VERSION}", codebook)
        self.assertIn(f"Schlüsselversion: {b.KEY_VERSION}", codebook)
        payload = json.loads(authored("dictionary").read_text())
        dictionary = payload["tables"]
        for table in manifest["tables"]:
            self.assertIn(f"### `{table['name']}`", codebook)
            self.assertIn(dictionary[table["name"]]["meaning"], codebook)
            for column in table["columns"]:
                meta = dictionary[table["name"]]["columns"][column["name"]]
                meta = {**meta, "license": payload["licenses"][meta["license"]]}
                for key in ("meaning", "unit", "source", "license"):
                    self.assertTrue(meta[key].strip())
                    self.assertIn(meta[key].replace("|", "\\|").replace("\n", "<br>"), codebook)
                self.assertNotEqual(column["name"], "paragraphs_json")
        observed = manifest["coverage"]["wahlperioden"]
        self.assertEqual([(row["wp"], row["sittings"], row["speeches"], row["agenda_items"], row["votes"], row["vote_members"]) for row in observed], [("20", 1, 4, 1, 1, 1), ("21", 1, 3, 1, 1, 1)])
        self.assertEqual(observed[0]["date_from"], "2024-05-15")
        self.assertEqual(observed[1]["date_to"], "2025-05-22")
        self.assertIn("Erwerbsvollständigkeit je Wahlperiode: **unbekannt**", codebook)
        self.assertIn("Katalog 100, Dossiers 2", codebook)
        self.assertIn("Bausteine: Namentliche Abstimmungen erfasst; abgeordnetenwatch-Profile nicht erfasst; MdB-Kader erfasst.", codebook)
        self.assertNotIn("{'", codebook)
        self.assertIn("Aliasauflösung: `canonical_id` verweist auf `persons.id`", codebook)
        self.assertIn("Aliasauflösung: entfällt", codebook)
        self.assertIn("Sitzung mit Dossier", codebook)
        self.assertIn("docs/adr/0001-count-speeches-by-sprechrolle.md", codebook)
        self.assertIn("Weiterverbreitung", codebook)
        self.assertEqual(re.findall(r"^# .*", codebook, flags=re.MULTILINE), ["# DATA — Datenwörterbuch dieses Exports"])
        self.assertIn("## Datenstand und Auswertungsmethoden", codebook)
        self.assertIn("### Short string", codebook)
        self.assertIn("wörtlich ab seinem ersten Abschnitt („Short string“), Überschriften eine Ebene tiefer", codebook)
        self.assertNotIn("Status: decided", codebook)
        self.assertNotIn("not yet wired into the build", codebook)
        self.assertNotIn("Die sechs Rezept-CSV-Dateien", codebook)
        self.assertIn("Bundestag-Puls (Arbeitstitel; der Produktname ist nicht festgelegt), Release v-test", codebook)
        self.assertNotIn("Einzelstimme", codebook)
        for path in b.CODEBOOK_INPUT_FILES.values():
            self.assertIn(f"- `{path}`: `{manifest['codebook_inputs'][path]}`", codebook)
        for recipe in manifest["recipes"]:
            self.assertIn(recipe["sql"], codebook)
            self.assertIn(recipe["file"], codebook)
            self.assertEqual(recipe["method"], b.RECIPES_BY_ID[recipe["id"]]["method"])
            self.assertIn(recipe["method"], codebook)
        entry = next(file for file in manifest["files"] if file["kind"] == "codebook")
        self.assertEqual(entry["sha256"], b._hash_file(codebook_path))
        self.assertNotIn(entry["sha256"], codebook)
        # O3: every generation carries the licence file DATA.md's short string
        # points to, as the bytes the codebook input hashed.
        self.assertNotIn("docs/data-license.md", codebook)
        self.assertNotIn("This file states the terms", codebook)
        self.assertIn("Die vollständige Datei liegt diesem Export als `LICENSE-DATA.md` bei", codebook)
        (licence,) = [file for file in manifest["files"] if file["kind"] == "license"]
        licence_path = codebook_path.parent / "LICENSE-DATA.md"
        self.assertEqual(licence["name"], "LICENSE-DATA.md")
        self.assertEqual(licence["bytes"], licence_path.stat().st_size)
        self.assertEqual(licence["sha256"], b._hash_file(licence_path))
        self.assertEqual(licence["sha256"], manifest["codebook_inputs"]["LICENSE-DATA.md"])
        self.assertEqual(licence_path.read_bytes(), (b.REPO_ROOT / "LICENSE-DATA.md").read_bytes().replace(b"\r\n", b"\n"))

    def test_missing_dictionary_entries_fail_by_name_and_preserve_publication(self) -> None:
        self.export()
        before = {path.relative_to(self.exports_dir): path.read_bytes() for path in self.exports_dir.rglob("*") if path.is_file()}
        inputs = b._read_codebook_inputs()

        def export_with(dictionary, message):
            changed = dataclasses.replace(inputs, dictionary=json.dumps(dictionary))
            with mock.patch.object(b, "_read_codebook_inputs", return_value=changed):
                with self.assertRaisesRegex(RuntimeError, message):
                    self.export(force=True)
            self.assertEqual({path.relative_to(self.exports_dir): path.read_bytes() for path in self.exports_dir.rglob("*") if path.is_file()}, before)

        for table, column in (("speeches", None), ("speeches", "meaning"), ("speeches", "text"), ("mp_canonical", "has_page"), ("datenstand", "tag")):
            dictionary = json.loads(inputs.dictionary)
            if column == "meaning":
                del dictionary["tables"][table]["meaning"]
            elif column:
                del dictionary["tables"][table]["columns"][column]
            else:
                del dictionary["tables"][table]
            with self.subTest(table=table, column=column):
                export_with(dictionary, re.escape(table + ("." + column if column else "")))
        cases = {
            "unknown licence layer 'no-such-layer' for speeches.text": lambda d: d["tables"]["speeches"]["columns"]["text"].update(license="no-such-layer"),
            "missing speeches.text.license": lambda d: d["tables"]["speeches"]["columns"]["text"].pop("license"),
            "placeholder text at speeches.text.unit": lambda d: d["tables"]["speeches"]["columns"]["text"].update(unit="TODO"),
            "placeholder text at speeches.text.meaning": lambda d: d["tables"]["speeches"]["columns"]["text"].update(meaning="Text der Rede, TBD"),
            "placeholder text at licenses.dip": lambda d: d["licenses"].update(dip="?"),
            "same meaning": lambda d: d["tables"]["speeches"]["columns"]["text"].update(meaning=d["tables"]["speeches"]["columns"]["id"]["meaning"]),
            "describes tables no export has: removed_table": lambda d: d["tables"].update(removed_table={"meaning": "Entfernte Tabelle.", "columns": {}}),
            "describes speeches columns the export lacks: paragraphs_json": lambda d: d["tables"]["speeches"]["columns"].update(paragraphs_json=d["tables"]["speeches"]["columns"]["text"]),
            # DATA.md and datenstand.json must not give one column different terms.
            "licence layer eigene-auswertung for speeches.text contradicts its manifest source tag dip": lambda d: d["tables"]["speeches"]["columns"]["text"].update(license="eigene-auswertung"),
            "licence layer bundestag-abstimmungen for vote_fractions.leading_vote contradicts its manifest source tag derived": lambda d: d["tables"]["vote_fractions"]["columns"]["leading_vote"].update(license="bundestag-abstimmungen"),
            "licence layers without allowed source tags: neue-schicht": lambda d: d["licenses"].update({"neue-schicht": "Neue Lizenzschicht ohne Zuordnung."}),
        }
        for message, change in cases.items():
            dictionary = json.loads(inputs.dictionary)
            change(dictionary)
            with self.subTest(message=message):
                export_with(dictionary, re.escape(message))
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE future_table (new_field TEXT)")
        with self.assertRaisesRegex(RuntimeError, "future_table"):
            self.export()

    def test_a_table_without_a_safe_csv_name_fails_the_export(self) -> None:
        self.export()
        before = (self.exports_dir / "datenstand.json").read_bytes()
        inputs = b._read_codebook_inputs()
        # A trailing newline passes a $-anchored re.match, so the check must be a full match.
        for name in ("bad-name", "trailing\n"):
            with self.subTest(name=name):
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(f'CREATE TABLE "{name}" (id TEXT PRIMARY KEY)')
                dictionary = json.loads(inputs.dictionary)
                dictionary["tables"][name] = {"meaning": "Tabelle mit unsicherem Namen.", "columns": {"id": dictionary["tables"]["speeches"]["columns"]["id"]}}
                with mock.patch.object(b, "_read_codebook_inputs", return_value=dataclasses.replace(inputs, dictionary=json.dumps(dictionary))):
                    with self.assertRaisesRegex(RuntimeError, re.escape(f"{name!r} has no safe CSV file name")):
                        self.export()
                self.assertEqual((self.exports_dir / "datenstand.json").read_bytes(), before)
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(f'DROP TABLE "{name}"')

    def authored_copy(self) -> Path:
        root = self.tmp / "repo"
        for relative in b.CODEBOOK_INPUT_FILES.values():
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            (root / relative).write_bytes((b.REPO_ROOT / relative).read_bytes())
        return root

    def test_each_authored_input_revision_and_recipe_metadata_invalidate_cache(self) -> None:
        root = self.authored_copy()
        with mock.patch.object(b, "REPO_ROOT", root):
            first = self.export()
            self.assertEqual(first, self.export())
            self.assertEqual(set(first["codebook_inputs"]), set(b.CODEBOOK_INPUT_FILES.values()))
            for relative in b.CODEBOOK_INPUT_FILES.values():
                path = root / relative
                with self.subTest(input=relative):
                    original = path.read_bytes()
                    path.write_bytes(original + b"\n")
                    changed = self.export()
                    self.assertNotEqual(changed["generation"], first["generation"])
                    self.assertEqual(changed["codebook_inputs"][relative], hashlib.sha256(path.read_bytes()).hexdigest())
                    path.write_bytes(original)
            for field in ("title", "caveat", "method", "columns"):
                recipe = dict(b.RECIPES[0])
                recipe[field] = ([{**column, "meaning": column["meaning"] + " Zusatz"} for column in recipe[field]]
                                 if field == "columns" else str(recipe[field]) + " Zusatz")
                with self.subTest(field=field):
                    changed = self.export(recipes=(recipe,) + b.RECIPES[1:])
                    self.assertNotEqual(first["generation"], changed["generation"])
                    self.assertIn("Zusatz", (self.exports_dir / changed["generation"] / "DATA.md").read_text())
            self.assertNotEqual(first["generation"], self.export(commit="def456")["generation"])

    def test_codebook_hashing_and_rendering_use_one_capture(self) -> None:
        root = self.authored_copy()
        path = root / b.CODEBOOK_INPUT_FILES["methods"]
        path.write_text("Methoden vorher")
        read_bytes = Path.read_bytes
        reads = []

        def changing_read(file):
            content = read_bytes(file)
            if file == path:
                reads.append(file)
                file.write_text("Methoden nachher")
            return content

        with mock.patch.object(b, "REPO_ROOT", root), mock.patch.object(Path, "read_bytes", changing_read):
            manifest = self.export()
        self.assertEqual(len(reads), 1)
        codebook = (self.exports_dir / manifest["generation"] / "DATA.md").read_text()
        self.assertIn("Methoden vorher", codebook)
        self.assertNotIn("Methoden nachher", codebook)
        self.assertEqual(manifest["codebook_inputs"][b.CODEBOOK_INPUT_FILES["methods"]], hashlib.sha256(b"Methoden vorher").hexdigest())

    def test_missing_or_truncated_new_assets_trigger_regeneration(self) -> None:
        manifest = self.export()
        for name in ("DATA.md", "LICENSE-DATA.md", manifest["recipes"][0]["file"]):
            for damage in ("missing", "truncated", "same size, altered"):
                with self.subTest(name=name, damage=damage):
                    path = self.exports_dir / manifest["generation"] / name
                    if damage == "truncated":
                        path.write_bytes(b"short")
                    elif damage == "same size, altered":
                        original = path.read_bytes()
                        path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
                    else:
                        path.unlink()
                    rebuilt = self.export()
                    entry = next(file for file in rebuilt["files"] if file["name"] == name)
                    self.assertEqual(path.stat().st_size, entry["bytes"])
                    self.assertEqual(b._hash_file(path), entry["sha256"])
                    self.assertNotEqual(rebuilt["generated_at"], manifest["generated_at"])
                    manifest = rebuilt

    # Value: protects=an edit to the exporter code re-exports even without a git revision, and the operator licence text cannot add lines to DATA.md; fails_when=EXPORTER_SHA256 leaves the cache key, the licence text is written raw, or an empty one leaves a blank licence line; why_new=commit was the only code identity and None without git, and no test read the empty-licence default; seam=none; no_claim=which edits matter
    def test_exporter_code_and_licence_text_reach_the_codebook_safely(self) -> None:
        first = self.export(commit=None)
        # No operator licence text (the default): DATA.md says so instead of leaving the line blank.
        first_codebook = (self.exports_dir / first["generation"] / "DATA.md").read_text()
        self.assertIn("(`--data-license` oder `$BUNDESTAG_PULSE_DATA_LICENSE`): keiner; es gelten die geschichteten Quellenbedingungen unten.", first_codebook)
        self.assertIn("beim bloßen Öffnen per Doppelklick", first_codebook)
        self.assertIn("entschärfen solchen Quelltext nicht", first_codebook)
        with mock.patch.object(b, "EXPORTER_SHA256", "0" * 64):
            second = self.export(commit=None)
        self.assertNotEqual(first["generation"], second["generation"])
        manifest = self.export(commit=None, license_text="CC BY 4.0\n## Gefälschter Abschnitt\n")
        codebook = (self.exports_dir / manifest["generation"] / "DATA.md").read_text()
        self.assertIn("Vom Betreiber übergebener Lizenzhinweis (`--data-license` oder `$BUNDESTAG_PULSE_DATA_LICENSE`): CC BY 4.0 ## Gefälschter Abschnitt.", codebook)
        self.assertNotIn("\n## Gefälschter Abschnitt", codebook)

    # Value: protects=a published datenstand.json the validator now rejects is rebuilt, not reused; fails_when=_manifest_reusable stops calling validate_manifest; why_new=the truncated-asset test covers only file sizes; seam=none; no_claim=which validator rule fired
    def test_cached_manifest_with_invalid_inventory_is_regenerated(self) -> None:
        manifest = self.export()
        path = self.exports_dir / "datenstand.json"
        cached = json.loads(path.read_text())
        cached["files"] = [file for file in cached["files"] if file["kind"] != "codebook"]
        path.write_text(json.dumps(cached))
        rebuilt = self.export()
        self.assertNotEqual(rebuilt["generated_at"], manifest["generated_at"])
        self.assertEqual([file["name"] for file in rebuilt["files"] if file["kind"] == "codebook"], ["DATA.md"])

    # Value: protects=an export the site's own validator would refuse is never published, and a tag that cannot be a file name fails before any work; fails_when=the pre-publish validate_manifest call or the tag check is removed; why_new=only cached and remote manifests were validated; seam=none; no_claim=every validator rule
    def test_an_export_its_validator_rejects_is_not_published(self) -> None:
        for tag in ("v1/2", "v 1", ".hidden", ""):
            with self.subTest(tag=tag), self.assertRaisesRegex(RuntimeError, "cannot be part of a file name"):
                self.export(tag=tag)
        self.assertFalse(self.exports_dir.exists())
        for commit in ("abc123def456-dirty-0123abcd", "abc123def456-unverified", "abc123def456-unverified-0123abcd", "abc123", None):
            with self.subTest(commit=commit), self.assertRaisesRegex(RuntimeError, "needs a clean, known build revision"):
                self.export(tag="v-test", commit=commit)
        self.assertFalse(self.exports_dir.exists())
        with mock.patch.object(b.build_revision, "authored_inputs_problem", return_value="not tracked by git: docs/data-methods.md"):
            with self.assertRaisesRegex(RuntimeError, "authored input.*not tracked by git: docs/data-methods.md"):
                self.export(tag="v-test", commit="abc123def456")
            self.assertFalse(self.exports_dir.exists())
            self.export(tag="local", commit=None)  # a local export never asks
        shutil.rmtree(self.exports_dir)
        self.export()
        before = {path.relative_to(self.exports_dir): path.read_bytes() for path in self.exports_dir.rglob("*") if path.is_file()}
        # A real validator rule: the new manifest's recipe CSV rows disagree with the file.
        real_run_export = b._run_export

        def miscounted(**kwargs):
            manifest = real_run_export(**kwargs)
            next(file for file in manifest["files"] if file["kind"] == "recipe_csv")["rows"] += 1
            return manifest

        with mock.patch.object(b, "_run_export", side_effect=miscounted), self.assertRaisesRegex(RuntimeError, "the export's new datenstand.json is not a usable Daten manifest: .*rows mismatch"):
            self.export(force=True)
        self.assertEqual({path.relative_to(self.exports_dir): path.read_bytes() for path in self.exports_dir.rglob("*") if path.is_file()}, before)
        self.assertEqual(list(b.export_work_dir(self.exports_dir).iterdir()), [])

    # Value: protects=a first export or a new generation the pre-publish validator refuses leaves nothing new published; fails_when=publication runs before validate_manifest on those paths; why_new=the test above covers only a forced re-export of the same generation; seam=none; no_claim=rename failures after validation (deferred)
    def test_a_rejected_first_or_new_generation_export_publishes_nothing(self) -> None:
        real_run_export = b._run_export

        def miscounted(**kwargs):
            manifest = real_run_export(**kwargs)
            next(file for file in manifest["files"] if file["kind"] == "recipe_csv")["rows"] += 1
            return manifest

        def published():
            return {path.relative_to(self.exports_dir): path.read_bytes() for path in self.exports_dir.rglob("*") if path.is_file()}

        with mock.patch.object(b, "_run_export", side_effect=miscounted), self.assertRaisesRegex(RuntimeError, "rows mismatch"):
            self.export()
        self.assertEqual(published(), {})
        self.export()
        before = published()
        changed = _r2_limited_to_4()
        with mock.patch.object(b, "_run_export", side_effect=miscounted), self.assertRaisesRegex(RuntimeError, "rows mismatch"):
            self.export(recipes=changed)
        self.assertEqual(published(), before)
        self.assertEqual(list(b.export_work_dir(self.exports_dir).iterdir()), [])

    # Value: protects=an export's own manifest is checked against the recipes it ran, so unchanged custom recipes reuse it and a cached manifest whose recipe SQL differs is rebuilt; fails_when=recipes= is dropped from the reuse check (every custom export re-exports) or the reuse check stops comparing SQL; why_new=reuse tests use only the default RECIPES; seam=none; no_claim=the --data-manifest page path
    def test_custom_recipes_reuse_and_a_cached_sql_change_rebuilds(self) -> None:
        changed = _r2_limited_to_4()
        first = self.export(recipes=changed)
        self.assertEqual(self.export(recipes=changed)["generated_at"], first["generated_at"])
        path = self.exports_dir / "datenstand.json"
        cached = json.loads(path.read_text())
        cached["recipes"][0]["sql"] += " "
        path.write_text(json.dumps(cached))
        self.assertNotEqual(self.export(recipes=changed)["generated_at"], first["generated_at"])

    # Value: protects=equal inputs give equal DATA.md bytes, and DATA.md names the latest stored sitting instead of the build time; fails_when=generated_at or another clock value enters DATA.md; why_new=a forced rebuild was only checked for a new generated_at; seam=none; no_claim=the sqlite and CSV bytes
    def test_forced_rebuild_gives_byte_identical_codebook(self) -> None:
        first = self.export()
        codebook = (self.exports_dir / first["generation"] / "DATA.md").read_bytes()
        second = self.export(force=True)
        self.assertNotEqual(first["generated_at"], second["generated_at"])
        self.assertEqual((self.exports_dir / second["generation"] / "DATA.md").read_bytes(), codebook)
        latest = max(row["date_to"] for row in first["coverage"]["wahlperioden"] if row["date_to"])
        self.assertIn(f"letzte gespeicherte Sitzung: {latest}.", codebook.decode())
        self.assertNotIn(first["generated_at"], codebook.decode())

    def test_new_writer_failures_preserve_published_assets_and_clean_staging(self) -> None:
        self.export()
        before = {path.relative_to(self.exports_dir): path.read_bytes() for path in self.exports_dir.rglob("*") if path.is_file()}
        real_write_text = Path.write_text

        def fail_codebook_write(path, *args, **kwargs):
            if path.name == "DATA.md":
                raise OSError("disk full")
            return real_write_text(path, *args, **kwargs)

        for writer in ("recipe CSV", "codebook"):
            for kwargs in ({"force": True}, {"commit": "newrevision"}):
                failure = (mock.patch.object(b, "_write_recipe_csv", side_effect=OSError("disk full"))
                           if writer == "recipe CSV" else mock.patch.object(Path, "write_text", fail_codebook_write))
                with self.subTest(writer=writer, kwargs=kwargs), failure:
                    with self.assertRaisesRegex(OSError, "disk full"):
                        self.export(**kwargs)
                self.assertEqual({path.relative_to(self.exports_dir): path.read_bytes() for path in self.exports_dir.rglob("*") if path.is_file()}, before)
                self.assertEqual(list(b.export_work_dir(self.exports_dir).iterdir()), [])

    # Value: protects=a sitting whose protocol number names no Wahlperiode is counted under unbekannt, listed after the numbered WPs (numeric order), and no record is lost or double counted; fails_when=_protocol_wahlperiode stops catching FactsError, the sort turns textual, or unknown rows drop out; why_new=the fixture has only WP 20/21 and the empty store has no rows; seam=none; no_claim=wording of the cells
    def test_snapshot_coverage_lists_unknown_wahlperiode_last_and_loses_no_record(self) -> None:
        now = "2024-06-01T00:00:00+00:00"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE protocols SET document_number = 'Sondersitzung', date = '' WHERE id = '5802'")
            conn.execute(
                "INSERT INTO protocols(id, document_number, date, title, xml_header_json, created_at, updated_at) "
                "VALUES ('5700', '9/1', '1980-01-01', 'Alte Sitzung', '{}', ?, ?)", (now, now))
            conn.execute("INSERT INTO speech_rule_inputs(protocol_id, version) VALUES ('5700', ?)", (pulse_store.speech_kinds.VERSION,))
            conn.execute("UPDATE votes SET protocol_id = CASE id WHEN 'v1' THEN '5801' ELSE '5802' END")
            totals = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                      for table in ("agenda_items", "speeches", "contributions", "votes", "vote_members")}
        manifest = self.export()
        rows = manifest["coverage"]["wahlperioden"]
        self.assertEqual([row["wp"] for row in rows], ["9", "20", "unbekannt"])
        unknown = rows[-1]
        self.assertEqual((unknown["sittings"], unknown["date_from"], unknown["date_to"], unknown["agenda_items"], unknown["votes"]), (1, None, None, 1, 1))
        for table, total in totals.items():
            with self.subTest(table=table):
                self.assertEqual(sum(row[table] for row in rows), total)
        codebook = (self.exports_dir / manifest["generation"] / "DATA.md").read_text()
        self.assertRegex(codebook, r"(?m)^\| unbekannt \| 1 \| unbekannt \| unbekannt \| 1 \|")

    # Value: protects=a Wahlperiode with several sittings sums them across protocol numbers, with the earliest and latest date and empty dates ignored; fails_when=the min/max comparison flips, an empty date wins, or one sitting overwrites another; why_new=every existing coverage fixture has one sitting per WP; seam=none; no_claim=counts of the other tables
    def test_snapshot_coverage_merges_the_sittings_of_one_wahlperiode(self) -> None:
        now = "2024-06-01T00:00:00+00:00"
        with sqlite3.connect(self.db_path) as conn:
            for protocol_id, number, date in (("5701", "20/10", ""), ("5702", "20/99", "2024-03-01"), ("5703", "20/98", "2024-09-30")):
                conn.execute(
                    "INSERT INTO protocols(id, document_number, date, title, xml_header_json, created_at, updated_at) "
                    "VALUES (?, ?, ?, 'Weitere Sitzung', '{}', ?, ?)", (protocol_id, number, date, now, now))
            conn.execute("INSERT OR REPLACE INTO speech_rule_inputs SELECT id, ? FROM protocols", (pulse_store.speech_kinds.VERSION,))
        (row,) = [row for row in self.export()["coverage"]["wahlperioden"] if row["wp"] == "20"]
        self.assertEqual((row["wp"], row["sittings"], row["date_from"], row["date_to"]), ("20", 5, "2024-03-01", "2024-09-30"))

    # Value: protects=votes without a protocol, and their members, are counted under unbekannt instead of dropping out of the per-WP totals; fails_when=a coverage join becomes inner or a NULL protocol_id raises; why_new=the unknown-WP test only has votes whose protocol exists but has no number; seam=none; no_claim=agenda_items/speeches
    def test_snapshot_coverage_counts_a_vote_without_protocol_as_unbekannt(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE votes SET protocol_id = CASE id WHEN 'v1' THEN NULL ELSE '5801' END")
            totals = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("votes", "vote_members")}
        rows = {row["wp"]: row for row in self.export()["coverage"]["wahlperioden"]}
        self.assertEqual(list(rows), ["20", "unbekannt"])
        self.assertEqual((rows["unbekannt"]["votes"], rows["unbekannt"]["vote_members"], rows["unbekannt"]["sittings"]), (1, 1, 0))
        self.assertEqual((rows["unbekannt"]["date_from"], rows["unbekannt"]["date_to"]), (None, None))
        for table, total in totals.items():
            with self.subTest(table=table):
                self.assertEqual(sum(row[table] for row in rows.values()), total)

    # Value: protects=a pipe or line break inside an authored column definition stays inside its DATA.md table cell; fails_when=_md_cell stops escaping, splitting the row into extra columns or ending the table; why_new=no authored text holds a pipe or newline, so the escape assertion elsewhere is vacuous; seam=none; no_claim=table meanings
    def test_codebook_cell_text_cannot_break_the_table_row(self) -> None:
        inputs = b._read_codebook_inputs()
        dictionary = json.loads(inputs.dictionary)
        dictionary["tables"]["speeches"]["columns"]["text"]["meaning"] = "Volltext a | b\nzweite Zeile"
        with mock.patch.object(b, "_read_codebook_inputs", return_value=dataclasses.replace(inputs, dictionary=json.dumps(dictionary))):
            manifest = self.export()
        codebook = (self.exports_dir / manifest["generation"] / "DATA.md").read_text()
        (row,) = re.findall(r"(?m)^\| `text` \| Volltext .*$", re.search(r"(?ms)^### `speeches`\n(.*?)(?=^### )", codebook).group(1))
        self.assertIn("Volltext a \\| b<br>zweite Zeile", row)
        self.assertEqual(len(re.split(r"(?<!\\)\|", row.strip())) - 2, 9)

    # Value: protects=DATA.md's file table lists every file of the generation except itself, with the manifest's kind, rows, bytes and SHA-256; fails_when=a file kind drops out, rows or bytes shift a column, or a hash is not the file's; why_new=readers verify downloads from this table, and only the manifest was compared; seam=none; no_claim=wording
    def test_codebook_file_table_matches_the_manifest_files(self) -> None:
        manifest = self.export()
        codebook = (self.exports_dir / manifest["generation"] / "DATA.md").read_text()
        table = re.search(r"(?ms)^\| Datei \| Art .*?\n\| --- .*?\n(.*?)(?=\n\n)", codebook).group(1).split("\n")
        listed = [[cell.strip(" `") for cell in line.strip("| ").split(" | ")] for line in table]
        files = [file for file in manifest["files"] if file["kind"] != "codebook"]
        self.assertEqual(
            [[cells[0].split("](")[0].lstrip("["), *cells[1:]] for cells in listed],
            [[file["name"], file["kind"], str(file.get("rows", "\u2014")), str(file["bytes"]), file["sha256"]] for file in files],
        )
        self.assertEqual({file["kind"] for file in files}, {"sqlite", "table_csv", "recipe_csv", "license"})
        for file in files:
            self.assertEqual(b._hash_file(self.exports_dir / manifest["generation"] / file["name"]), file["sha256"])

    # Value: protects=every link in DATA.md, including those in the embedded methods and licence documents, resolves for a reader of the published generation; fails_when=an embedded doc gains a repo-relative link (e.g. research/...md) that is dead beside DATA.md; why_new=the embedded docs are authored for the repository, not the release folder; seam=none; no_claim=that the absolute URLs are reachable
    def test_codebook_links_resolve_inside_the_generation_or_are_absolute(self) -> None:
        manifest = self.export()
        codebook = (self.exports_dir / manifest["generation"] / "DATA.md").read_text()
        names = {file["name"] for file in manifest["files"]}
        targets = re.findall(r"\]\(([^)\s]+)\)", codebook)
        self.assertTrue(targets)
        relative = [target for target in targets if not re.match(r"https?://", target) and target not in names]
        self.assertEqual(relative, [])

    # Value: protects=a datenstand.json that is valid JSON but not an object is treated like any other unusable manifest and re-exported; fails_when=_read_previous_manifest returns the list and _source_sha256 calls .get on it; why_new=only unparsable and missing manifests were covered; seam=none; no_claim=other damaged manifest shapes
    def test_a_previous_manifest_that_is_not_an_object_is_re_exported(self) -> None:
        self.export()
        (self.exports_dir / "datenstand.json").write_text("[1]\n", encoding="utf-8")
        manifest = self.export()
        self.assertEqual(json.loads((self.exports_dir / "datenstand.json").read_text(encoding="utf-8"))["generation"], manifest["generation"])
        self.assertTrue((self.exports_dir / manifest["generation"] / "DATA.md").is_file())

    # Value: protects=a broken authored input (unreadable, not UTF-8, bad JSON, wrong shape, licence doc without a "## " section) fails the export with a named RuntimeError and leaves the published generation untouched; fails_when=a raw OSError/UnicodeDecodeError/JSON error escapes or a half-written generation replaces the published one; why_new=only dictionary content errors were pinned, not file or shape errors; seam=none; no_claim=message wording beyond the cause
    def test_unreadable_or_malformed_authored_inputs_fail_by_name_and_preserve_publication(self) -> None:
        root = self.authored_copy()
        with mock.patch.object(b, "REPO_ROOT", root):
            self.export()
            before = {path.relative_to(self.exports_dir): path.read_bytes() for path in self.exports_dir.rglob("*") if path.is_file()}
            dictionary, methods, license_doc = (root / b.CODEBOOK_INPUT_FILES[field] for field in ("dictionary", "methods", "license"))
            originals = {path: path.read_bytes() for path in (dictionary, methods, license_doc)}
            cases = [
                ("missing licence file", license_doc, None, "codebook input .*LICENSE-DATA.md"),
                ("not UTF-8", methods, b"\xff\xfe\x00", "codebook input .*data-methods.md"),
                ("empty methods", methods, b"", "data-methods.md is empty"),
                ("whitespace-only methods", methods, b" \n\t\n", "data-methods.md is empty"),
                ("invalid JSON", dictionary, b"{", "data dictionary is not valid JSON"),
                ("no tables object", dictionary, b'{"licenses": {}}', 'needs "licenses" and "tables" objects'),
                ("no licenses object", dictionary, b'{"tables": {}}', 'needs "licenses" and "tables" objects'),
                ("licence doc without section", license_doc, b"# Titel\nnur Betreiberhinweise\n", 'has no "## " section'),
            ]
            for label, path, content, message in cases:
                with self.subTest(label=label):
                    try:
                        if content is None:
                            path.unlink()
                        else:
                            path.write_bytes(content)
                        with self.assertRaisesRegex(RuntimeError, message):
                            self.export()
                    finally:
                        path.write_bytes(originals[path])
                    self.assertEqual({p.relative_to(self.exports_dir): p.read_bytes() for p in self.exports_dir.rglob("*") if p.is_file()}, before)
                    self.assertEqual(list(b.export_work_dir(self.exports_dir).iterdir()), [])

    # Value: protects=DATA.md tells readers per table how to resolve retired person ids (alias list, persons, one or several person columns, none); fails_when=_codebook_alias_line swaps or drops a branch so a join guidance is wrong for a table; why_new=only canonical_id and the "entfällt" case were asserted; seam=none; no_claim=German wording beyond the key phrases
    def test_codebook_alias_guidance_is_specific_to_each_kind_of_table(self) -> None:
        manifest = self.export()
        codebook = (self.exports_dir / manifest["generation"] / "DATA.md").read_text()

        def section(table):
            return re.search(rf"(?ms)^### `{table}`\n(.*?)(?=^##)", codebook).group(1)

        self.assertIn("diese Tabelle ist die Aliasliste", section("person_aliases"))
        self.assertIn("eine zurückgezogene Kennung bleibt hier als Zeile stehen", section("persons"))
        self.assertIn("`person_id`, `home_person_id` verweisen auf `persons.id`", section("person_records"))
        self.assertIn("`person_id` verweist auf `persons.id`", section("person_bindings"))
        self.assertIn("entfällt, keine Spalte verweist auf `persons.id`", section("speeches"))
        for table in ("person_aliases", "persons", "speeches"):
            self.assertNotIn("früher ausgestellte Kennungen vor generationsübergreifenden Joins", section(table))

    # Value: protects=a recipe whose SQL selects a column without an authored definition fails the export before publishing, so no undocumented CSV column ships; fails_when=the missing-definition check is removed or only checks declared columns; why_new=the fixture recipes are all fully defined; seam=none; no_claim=other recipe failure modes
    def test_recipe_column_without_definition_fails_and_preserves_publication(self) -> None:
        self.export()
        before = {path.relative_to(self.exports_dir): path.read_bytes() for path in self.exports_dir.rglob("*") if path.is_file()}
        undocumented = ({**b.RECIPES[0], "sql": "SELECT '1' AS mp_id, 2 AS zusatz_b, 3 AS zusatz_a;"},) + b.RECIPES[1:]
        with self.assertRaisesRegex(RuntimeError, "recipe r1-meiste-reden missing output definitions: zusatz_a, zusatz_b"):
            self.export(recipes=undocumented)
        self.assertEqual({path.relative_to(self.exports_dir): path.read_bytes() for path in self.exports_dir.rglob("*") if path.is_file()}, before)
        self.assertEqual(list(b.export_work_dir(self.exports_dir).iterdir()), [])

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

    # Value (Fraktion stopgap, plan 2.7): protects=no Daten recipe blends Wahlperioden while
    # parties stay keyed by name; fails_when=a recipe row lacks its Wahlperiode, or r2 pools
    # an SPD of WP 18 with the SPD of WP 20 in one share; seam=export_distribution_data.
    def test_every_recipe_row_names_its_wahlperiode_and_r2_shares_are_per_wahlperiode(self) -> None:
        conn = pulse_store.connect(self.db_path)
        try:
            with conn:
                now = pulse_store.utc_now()
                conn.execute("INSERT INTO protocols(id, document_number, date, title, xml_header_json, created_at, updated_at)"
                             " VALUES ('1805', '18/5', '2013-12-18', 'Alt', '{}', ?, ?)", (now, now))
                conn.execute("INSERT INTO agenda_items(id, protocol_id, item_index, top_id, heading, created_at, updated_at)"
                             " VALUES ('ai-1805', '1805', 1, 'T1', 'TOP 1', ?, ?)", (now, now))
                mp_id = conn.execute("SELECT mp_id FROM speeches WHERE fraktion = 'SPD' LIMIT 1").fetchone()[0]
                conn.execute("INSERT INTO speeches(id, protocol_id, agenda_item_id, rede_id, sequence, mp_id, char_count,"
                             " text, fraktion, created_at, updated_at) VALUES ('s-1805', '1805', 'ai-1805', 'R1805', 1, ?,"
                             " 500, 'Alt', 'SPD', ?, ?)", (mp_id, now, now))
                conn.execute("INSERT OR REPLACE INTO speech_rule_inputs SELECT id, ? FROM protocols",
                             (pulse_store.speech_kinds.VERSION,))
        finally:
            conn.close()
        manifest = self.export()
        self.assertEqual(manifest["export_format"], b.EXPORT_FORMAT)
        for recipe in manifest["recipes"]:
            with self.subTest(recipe=recipe["id"]):
                self.assertIn("wahlperiode", recipe["columns"])
                self.assertTrue(all(isinstance(row["wahlperiode"], int) for row in recipe["rows"]), recipe["rows"])
        r2 = next(r for r in manifest["recipes"] if r["id"] == "r2-redeanteil-fraktion")
        spd = {row["wahlperiode"]: row for row in r2["rows"] if row["fraktion"] == "SPD"}
        self.assertEqual((spd[18]["reden"], spd[18]["anteil_prozent"]), (1, 100.0))
        self.assertEqual(spd[20]["reden"], 3)

    # Value (rule 5, 6c): protects=a Rede the parser split out of the <rede> it was printed
    # in is counted in the manifest like a synthetic id; fails_when=the split id goes uncounted
    # or is taken for a synthetic one; seam=export_distribution_data.
    def test_a_split_rede_id_is_counted_in_the_manifest(self) -> None:
        before = self.export(force=True)["coverage"]
        conn = pulse_store.connect(self.db_path)
        try:
            with conn:
                now = pulse_store.utc_now()
                row = conn.execute("SELECT protocol_id, agenda_item_id, mp_id FROM speeches LIMIT 1").fetchone()
                conn.execute("INSERT INTO speeches(id, protocol_id, agenda_item_id, rede_id, sequence, mp_id, char_count,"
                             " text, fraktion, created_at, updated_at) VALUES ('s-split', ?, ?, 'ID1801002600:2', 99, ?,"
                             " 500, 'Geteilt', 'SPD', ?, ?)", (*row, now, now))
        finally:
            conn.close()
        after = self.export(force=True)["coverage"]
        self.assertEqual(after["split_rede_ids"], before["split_rede_ids"] + 1)
        self.assertEqual(after["synthetic_rede_ids"], before["synthetic_rede_ids"])

    # Value (D2): protects=a sitting kept out by the reviewed exclusion list is a visible,
    # counted coverage gap on the Daten page; fails_when=the export forgets it or the page
    # does not name it; seam=export_distribution_data + render_daten_datenstand.
    def test_an_excluded_sitting_is_counted_as_not_covered(self) -> None:
        manifest = self.export(excluded_sittings=["18/84"])
        self.assertEqual(manifest["coverage"]["excluded"], ["18/84"])
        self.assertNotIn("source_rejected", manifest["coverage"])
        html = b.render_daten_datenstand(manifest)
        self.assertIn("1 nicht erfasst (ausgeschlossen): 18/84", html)
        self.assertNotIn("ausgeschlossen", b.render_daten_datenstand(self.export(force=True)))

    # Value (A3): protects=the Daten page states the v1 scope beside the measured
    # range, so a reader can tell a gap inside the scope from history outside it;
    # fails_when=the line is dropped or names another first Wahlperiode;
    # seam=render_daten_datenstand.
    def test_datenstand_states_the_v1_scope(self) -> None:
        html = b.render_daten_datenstand(self.export(force=True))
        self.assertIn(f"ab der {b.V1_FIRST_WAHLPERIODE}. Wahlperiode", html)
        self.assertIn('class="scope-line"', html)

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

    def test_all_twenty_nine_csvs_named_and_headered(self) -> None:
        # The facts tables (T5/T6) are part of the store by the time export
        # runs in a real build; run the engine first so they are here too.
        b.run_facts_engine(self.db_path, self.FACTS_ENTRIES, self.facts_catalog())
        manifest = self.export()
        csv_files = [f["name"] for f in manifest["files"] if f["name"].endswith(".csv.gz")]
        self.assertEqual(len(csv_files), 29)
        for name in (
            "fact_metrics-local.csv.gz", "facts-local.csv.gz", "fact_sources-local.csv.gz",
            "agenda_item_politikfelder-local.csv.gz", "vote_politikfelder-local.csv.gz",
            "vote_proceedings-local.csv.gz", "vote_passages-local.csv.gz",
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

    # Value: protects=the export carries vote context, the Bundestag report source URL and the quoted Antrag passage through downloads and captions; fails_when=a source column is dropped or its caption is generic; why_new=B4 adds the fields; seam=none
    def test_vote_context_debate_url_and_passage_round_trip_with_captions(self) -> None:
        conn = pulse_store.connect(self.db_path)
        try:
            conn.execute("UPDATE proceedings SET abstract = ? WHERE id = 'vg-1'", ("Erster Absatz\n\nZweiter",))
            conn.execute("UPDATE votes SET context_state = CASE id WHEN 'v1' THEN 'resolved' ELSE 'not_fetched' END")
            conn.execute("UPDATE votes SET debate_url = ? WHERE id = 'v1'", ("https://www.bundestag.de/dokumente/textarchiv/2024/kw11-debatte-123456",))
            conn.execute("INSERT INTO vote_proceedings(vote_id, proceeding_id, rank) VALUES ('v1', 'vg-1', 1)")
            document_id = pulse_store.upsert_document(conn, now="2024-01-01T00:00:00Z", document_number="20/1234", herausgeber="BT")
            conn.execute(
                "UPDATE documents SET forderung = ?, forderung_state = 'extracted', forderung_version = ? WHERE id = ?",
                ("Der Deutsche Bundestag fordert die Bundesregierung auf,\n\n1. zu handeln.", antrag_text.EXTRACTOR_VERSION, document_id),
            )
            conn.execute("INSERT INTO vote_passages(vote_id, document_id, proceeding_id, rank) VALUES ('v1', ?, 'vg-1', 1)", (document_id,))
            conn.execute("UPDATE votes SET passage_state = CASE id WHEN 'v1' THEN 'extracted' ELSE 'not_applicable' END")
            conn.commit()
        finally:
            conn.close()
        manifest = self.export()
        self.assertEqual(manifest["export_format"], 12)
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
        self.assertEqual({r["id"]: r["passage_state"] for r in read("votes")}, {"v1": "extracted", "v2": "not_applicable"})
        self.assertEqual([(r["vote_id"], r["proceeding_id"], r["rank"]) for r in read("vote_passages")], [("v1", "vg-1", "1")])
        quoted = {r["document_number"]: r for r in read("documents")}["20/1234"]
        self.assertEqual((quoted["forderung"], quoted["forderung_state"]), (
            "Der Deutsche Bundestag fordert die Bundesregierung auf,\n\n1. zu handeln.", "extracted"))
        self.assertEqual(b.column_source("documents", "forderung"), "derived")
        for name in ("vote_proceedings", "vote_passages", "proceedings", "votes", "documents"):
            with self.subTest(table=name):
                self.assertIn(b.DATABASE_TABLE_DESCRIPTIONS[name], table_rows_html)
        self.assertIn("context_state", b.DATABASE_TABLE_DESCRIPTIONS["votes"])
        self.assertIn("debate_url", b.DATABASE_TABLE_DESCRIPTIONS["votes"])
        self.assertIn("passage_state", b.DATABASE_TABLE_DESCRIPTIONS["votes"])
        self.assertIn("forderung", b.DATABASE_TABLE_DESCRIPTIONS["documents"])
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

    # Value: protects=an exported distribution SQLite (user_version or datenstand table) given as --database-path is refused by the facts engine before anything is computed or staged, and the file stays byte for byte as it was; fails_when=run_facts_engine checks only the schema again and writes changed facts into a downloaded release; why_new=v0.19.0.0 ship review (1): the build-store guard lived only in pulse_store.connect; seam=run_facts_engine
    def test_engine_refuses_a_distribution_copy_and_leaves_it_untouched(self) -> None:
        for marker in ("PRAGMA user_version = 1", "CREATE TABLE datenstand (tag TEXT)"):
            with self.subTest(marker=marker):
                copy = self.tmp / "distribution.sqlite"
                shutil.copyfile(self.db_path, copy)
                conn = sqlite3.connect(copy)
                conn.execute(marker)
                conn.commit()
                conn.close()
                before = copy.read_bytes()
                with mock.patch.object(facts, "compute_and_store") as compute:
                    with self.assertRaisesRegex(RuntimeError, "distribution copy"):
                        b.run_facts_engine(copy, self.FACTS_ENTRIES, self.facts_catalog())
                compute.assert_not_called()
                self.assertEqual(copy.read_bytes(), before)
                self.assertEqual([p.name for p in self.tmp.iterdir() if p.name.startswith(copy.name + "-")], [])
                copy.unlink()

    # Value: protects=a rebuild (online build or --offline --repersist) given an exported distribution SQLite as --database-path refuses before staging and leaves the file byte for byte as it was; fails_when=the rebuild probe checks only that the store reads and replaces the downloaded release with a fresh build store; why_new=/ship QA probes 004/005 (2026-10-31): user_version 1 became 0 with a new inode; seam=none
    def test_rebuild_refuses_a_distribution_copy_and_leaves_it_untouched(self) -> None:
        for upgrade in (False, True):
            with self.subTest(upgrade=upgrade):
                copy = self.tmp / "distribution.sqlite"
                shutil.copyfile(self.db_path, copy)
                conn = sqlite3.connect(copy)
                conn.execute("PRAGMA user_version = 1")
                conn.commit()
                conn.close()
                before, inode = copy.read_bytes(), copy.stat().st_ino
                with self.assertRaisesRegex(b.DatabaseRebuildError, "distribution copy"):
                    b.rebuild_database_from_entries(copy, [], upgrade=upgrade)
                self.assertEqual(copy.read_bytes(), before)
                self.assertEqual(copy.stat().st_ino, inode)
                copy.unlink()

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

    # Value: protects=a rename that fails while the export is being published (the generation going in, or datenstand.json after it) leaves the published tree byte-for-byte as it was: nothing at all for a first export, the previous generation and manifest otherwise; fails_when=the set-aside generation is deleted, the new generation stays beside the old manifest, or the old manifest sits over new files; why_new=the five cells (first and new-generation rename-in, first/new-generation/forced manifest rename) were untested and the manifest-rename ones lost the previous generation; seam=none; no_claim=failures of the validator or the file writes
    def test_a_rename_failure_while_publishing_restores_the_published_tree(self) -> None:
        def tree():
            return {path.relative_to(self.exports_dir): path.read_bytes() for path in self.exports_dir.rglob("*") if path.is_file()} if self.exports_dir.exists() else {}

        def inodes():
            # Byte-identical regenerated files would pass a content comparison: the
            # published files themselves, not copies, must be the ones that remain.
            return {path.relative_to(self.exports_dir): path.stat().st_ino for path in self.exports_dir.rglob("*") if path.is_file()} if self.exports_dir.exists() else {}

        real_replace = Path.replace

        def failing(step):
            def replace(path, target):
                target = Path(target)
                into_tree = target.parent == self.exports_dir
                generation_in = into_tree and target.name.startswith("g-") and path.name.startswith("g-") and path.parent.name.startswith("export-")
                manifest_in = into_tree and target.name == "datenstand.json"
                if (step == "generation" and generation_in) or (step == "manifest" and manifest_in):
                    raise OSError(f"{step} rename failed")
                return real_replace(path, target)
            return replace

        changed = _r2_limited_to_4()
        cases = (
            ("first export, generation rename", "generation", False, {}),
            ("first export, manifest rename", "manifest", False, {}),
            ("new generation, generation rename", "generation", True, {"recipes": changed}),
            ("new generation, manifest rename", "manifest", True, {"recipes": changed}),
            ("forced re-export, manifest rename", "manifest", True, {"force": True}),
        )
        for label, step, has_previous, kwargs in cases:
            with self.subTest(label):
                shutil.rmtree(self.exports_dir, ignore_errors=True)
                if has_previous:
                    self.export()
                before, before_inodes = tree(), inodes()
                self.assertEqual(bool(before), has_previous)
                with mock.patch.object(Path, "replace", failing(step)), self.assertRaisesRegex(OSError, f"{step} rename failed"):
                    self.export(**kwargs)
                self.assertEqual(tree(), before)
                self.assertEqual(inodes(), before_inodes)
                self.assertEqual(list(b.export_work_dir(self.exports_dir).iterdir()), [])
                if has_previous:
                    # the restored publication is still the one the next run reuses
                    self.assertEqual(self.export()["generation"], json.loads((self.exports_dir / "datenstand.json").read_text())["generation"])

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
            "tag": {"tag": "v1", "commit": "abc123def456"},
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
            "vote_members": ["vote_id", "mp_id"], "vote_passages": ["vote_id", "document_id"],
            "vote_politikfelder": ["vote_id", "politikfeld"],
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
            CREATE TABLE protocols (id TEXT PRIMARY KEY, document_number TEXT);
            CREATE TABLE votes (id TEXT PRIMARY KEY, protocol_id TEXT);
            CREATE TABLE agenda_items (id TEXT PRIMARY KEY, protocol_id TEXT);
            CREATE TABLE agenda_item_votes (agenda_item_id TEXT, vote_id TEXT);
            CREATE TABLE speeches (mp_id TEXT, protocol_id TEXT, char_count INTEGER);
            CREATE TABLE vote_members (vote_id TEXT, mp_id TEXT, party_id TEXT, vote TEXT);
            CREATE TABLE vote_fractions (vote_id TEXT, party_id TEXT, leading_vote TEXT);
            INSERT INTO parties VALUES ('spd', 'SPD');
            INSERT INTO vote_fractions VALUES ('v1', 'spd', 'yes');
            INSERT INTO protocols VALUES ('pp-1', '21/1');
            INSERT INTO votes VALUES ('v1', 'pp-1');
            """
        )
        for mp_id, (person, identity, name, is_mdb, xml) in members:
            conn.execute("INSERT INTO mps VALUES (?, ?, ?, ?, 'spd', ?, ?)", (mp_id, identity, person, name, is_mdb, xml))
            conn.execute("INSERT INTO mp_canonical VALUES (?, ?, 1)", (mp_id, person))
            conn.execute("INSERT INTO speeches VALUES (?, 'pp-1', 100)", (mp_id,))
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
                    "p-1": (21, "Ada Lovelace", "SPD", 2, 200),
                    "p-2": (21, "Bea Zwei", "SPD", 2, 200),
                    "p-3": (21, "Dr. Cem Drei", "SPD", 2, 200),
                })
                self.assertEqual(rows["r3-abweichler"], {
                    "p-1": (21, "Ada Lovelace", "SPD", 1),
                    "p-2": (21, "Bea Zwei", "SPD", 1),
                    "p-3": (21, "Dr. Cem Drei", "SPD", 1),
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
