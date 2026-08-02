from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import _support  # noqa: F401
import build_dip_pulse_site
import persist_dip_pulse_store as pulse_store
from features import all_selection, default_selection


class CollectAbgeordneteTests(unittest.TestCase):
    def test_offline_main_migrates_legacy_database_before_collecting_mps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "site"
            database_path = output_dir / "data" / "bundestag-pulse.sqlite"
            conn = pulse_store.connect(database_path)
            try:
                conn.executescript(
                    """
                    CREATE TABLE parties (
                      id INTEGER PRIMARY KEY,
                      name TEXT NOT NULL UNIQUE,
                      created_at TEXT NOT NULL,
                      updated_at TEXT NOT NULL
                    );

                    CREATE TABLE mps (
                      id INTEGER PRIMARY KEY,
                      identity_key TEXT NOT NULL UNIQUE,
                      dip_person_id TEXT UNIQUE,
                      xml_redner_id TEXT,
                      display_name TEXT NOT NULL,
                      title TEXT,
                      function TEXT,
                      wahlperiode TEXT,
                      profile_url TEXT,
                      party_id INTEGER,
                      created_at TEXT NOT NULL,
                      updated_at TEXT NOT NULL
                    );
                    """
                )
            finally:
                conn.close()

            args = SimpleNamespace(
                output_dir=output_dir,
                database_path=None,
                offline=True,
                no_persist=False,
            )
            with (
                mock.patch.object(build_dip_pulse_site, "parse_args", return_value=args),
                mock.patch.object(build_dip_pulse_site, "load_cached_protocols", return_value=[{"id": "cached"}]),
                mock.patch.object(build_dip_pulse_site, "rebuild_cached_detail_pages", return_value=[]),
                mock.patch.object(
                    build_dip_pulse_site,
                    "render_site",
                    return_value=output_dir / "index.html",
                ),
            ):
                self.assertEqual(build_dip_pulse_site.main(), 0)

            conn = pulse_store.connect(database_path)
            try:
                columns = {row["name"] for row in conn.execute("PRAGMA table_info(mps)")}
            finally:
                conn.close()
            self.assertIn("birth_year", columns)

    def test_write_report_reuses_catalog_protocol_metadata(self) -> None:
        protocol = {
            "id": "5805",
            "dokumentnummer": "21/87",
            "fundstelle": {"xml_url": "https://example.test/protocol.xml"},
        }
        report = {"protocol": {"id": "5805"}, "agenda_items": []}
        expected_entry = {"report": report}

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(build_dip_pulse_site.dip, "build_report", return_value=report) as build_report,
            mock.patch.object(
                build_dip_pulse_site,
                "write_report_files",
                return_value=expected_entry,
            ),
        ):
            entry = build_dip_pulse_site.write_report_and_page(
                protocol=protocol,
                output_dir=Path(tmp),
                api_key="test-key",
                sleep=0,
                person_limit=0,
                vote_scan_pages=0,
                roll_call_list_id=None,
                summary_mode="off",
                summary_provider="auto",
                anthropic_api_key=None,
                gemini_api_key=None,
                summary_model=None,
                existing_report=None,
            )

        self.assertIs(entry, expected_entry)
        self.assertIs(build_report.call_args.kwargs["protocol"], protocol)

    def test_collect_abgeordnete_groups_rows_sharing_external_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                now = pulse_store.utc_now()
                with conn:
                    party_id = pulse_store.upsert_party(conn, "SPD", now)
                    roster_mp_id = pulse_store.upsert_mp(
                        conn,
                        now=now,
                        display_name="Ada Lovelace, MdB, SPD",
                        party_id=party_id,
                        identity_key=pulse_store.mp_identity(dip_person_id="dip-ada"),
                        dip_person_id="dip-ada",
                        aw_politician_id=77,
                        profession="Mathematician",
                        is_mdb=True,
                    )
                    speaker_mp_id = pulse_store.upsert_mp(
                        conn,
                        now=now,
                        display_name="Ada Lovelace",
                        party_id=party_id,
                        identity_key=pulse_store.mp_identity(xml_redner_id="11001"),
                        xml_redner_id="11001",
                        aw_politician_id=77,
                    )
                    conn.execute(
                        """
                        INSERT INTO protocols(id, document_number, date, title, xml_header_json, created_at, updated_at)
                        VALUES ('pp-test', '20/999', '2024-05-15', 'Test protocol', '{}', ?, ?)
                        """,
                        (now, now),
                    )
                    conn.execute(
                        """
                        INSERT INTO agenda_items(protocol_id, item_index, top_id, heading, created_at, updated_at)
                        VALUES ('pp-test', 1, 'T1', 'TOP 1 Test', ?, ?)
                        """,
                        (now, now),
                    )
                    agenda_item_id = conn.execute("SELECT id FROM agenda_items").fetchone()["id"]
                    conn.execute(
                        """
                        INSERT INTO speeches(
                          protocol_id, agenda_item_id, rede_id, sequence, mp_id, page,
                          paragraph_count, char_count, text, paragraphs_json, snippet,
                          created_at, updated_at
                        )
                        VALUES ('pp-test', ?, 'R1', 1, ?, 101, 1, 24, 'Rede text', '[]', 'Rede text', ?, ?)
                        """,
                        (agenda_item_id, speaker_mp_id, now, now),
                    )

                mps, lookup = build_dip_pulse_site.collect_abgeordnete(conn)

                self.assertEqual(len(mps), 1)
                mp = mps[0]
                self.assertEqual(mp["id"], roster_mp_id)
                self.assertEqual(mp["name"], "Ada Lovelace")
                self.assertEqual(mp["profession"], "Mathematician")
                self.assertEqual(mp["speech_count"], 1)
                self.assertEqual(mp["speeches"][0]["rede_id"], "R1")
                self.assertEqual(lookup["aw:77"], roster_mp_id)
                self.assertEqual(lookup["dip:dip-ada"], roster_mp_id)
                self.assertEqual(lookup["xml:11001"], roster_mp_id)
            finally:
                conn.close()


class CurrentPulseOrderTests(unittest.TestCase):
    """The site treats entries[0]/protocols[0] as the current pulse."""

    @staticmethod
    def _protocol(document_number: str, protocol_id: str, datum: str) -> dict[str, Any]:
        return {
            "id": protocol_id,
            "dokumentnummer": document_number,
            "datum": datum,
            "titel": f"Protokoll der Sitzung {document_number}",
        }

    @staticmethod
    def _entry(output_dir: Path, protocol: dict[str, Any]) -> dict[str, Any]:
        report_path, page_path, slug = build_dip_pulse_site.report_paths(
            output_dir, protocol["dokumentnummer"]
        )
        return {
            "report": {"protocol": protocol, "agenda_items": [], "validation_summary": {}},
            "report_path": report_path,
            "page_path": page_path,
            "slug": slug,
        }

    @staticmethod
    def _output_dir(tmp: str) -> Path:
        output_dir = Path(tmp) / "site"
        for name in ("data", "protocols", "bills", "abgeordnete"):
            (output_dir / name).mkdir(parents=True, exist_ok=True)
        return output_dir

    def test_render_site_puts_newest_sitting_first(self) -> None:
        # Cached dossiers reach render_site in glob order, where the slug "20-100"
        # sorts before "21-84" even though its sitting is three years older.
        old = self._protocol("20/100", "4200", "2023-04-27")
        new = self._protocol("21/84", "5799", "2026-06-12")
        protocols = [old, new]

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._output_dir(tmp)
            entries = [self._entry(output_dir, old), self._entry(output_dir, new)]

            build_dip_pulse_site.render_site(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=protocols,
                entries=entries,
                abg_mps=[],
                mp_lookup={},
            )

            for page in ("puls.html", "index.html", "overview.html", "sources.html"):
                markup = (output_dir / page).read_text(encoding="utf-8")
                self.assertIn("21/84", markup, msg=page)

            pulse_markup = (output_dir / "puls.html").read_text(encoding="utf-8")
            self.assertIn("2026-06-12", pulse_markup)
            self.assertNotIn("2023-04-27", pulse_markup)

    def test_render_site_writes_catalog_newest_first(self) -> None:
        # The DIP API orders by aktualisiert, so a corrected old protocol can arrive
        # ahead of the newest sitting; the cached catalog must still be date-ordered.
        protocols = [
            self._protocol("20/100", "4200", "2023-04-27"),
            self._protocol("21/84", "5799", "2026-06-12"),
            self._protocol("21/9", "5010", "2025-07-10"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._output_dir(tmp)
            build_dip_pulse_site.render_site(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=protocols,
                entries=[],
                abg_mps=[],
                mp_lookup={},
            )

            catalog = json.loads(
                (output_dir / "data" / "plenarprotokoll-catalog.json").read_text(encoding="utf-8")
            )

        self.assertEqual([item["dokumentnummer"] for item in catalog], ["21/84", "21/9", "20/100"])

    def test_entry_sort_key_tolerates_incomplete_reports(self) -> None:
        # A truncated or hand-edited dossier JSON must sort last, not crash the build.
        complete = {"report": {"protocol": self._protocol("21/84", "5799", "2026-06-12")}}
        self.assertEqual(build_dip_pulse_site.entry_sort_key(complete), ("2026-06-12", "5799"))

        for label, entry in (
            ("no report", {"slug": "21-84"}),
            ("null report", {"report": None}),
            ("no protocol", {"report": {"agenda_items": []}}),
            ("null protocol", {"report": {"protocol": None}}),
            ("no datum", {"report": {"protocol": {"id": "5799"}}}),
        ):
            with self.subTest(entry=label):
                key = build_dip_pulse_site.entry_sort_key(entry)
                self.assertEqual(key[0], "")
                self.assertLess(key, build_dip_pulse_site.entry_sort_key(complete))

    def test_reduced_render_skips_addon_pages_and_dangling_links(self) -> None:
        protocol = self._protocol("21/84", "5799", "2026-06-12")
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._output_dir(tmp)
            build_dip_pulse_site.render_site(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=[protocol],
                entries=[self._entry(output_dir, protocol)],
                abg_mps=[],
                mp_lookup={},
                features=default_selection(),
            )
            self.assertFalse((output_dir / "bills" / "index.html").exists())
            self.assertFalse((output_dir / "abgeordnete" / "index.html").exists())
            self.assertIn("--no-persist", (output_dir / "database.html").read_text(encoding="utf-8"))
            rendered = "\n".join(path.read_text(encoding="utf-8") for path in output_dir.rglob("*.html"))
            self.assertNotIn('href="bills/index.html"', rendered)
            self.assertNotIn('href="../bills/index.html"', rendered)

    def test_reduced_render_removes_stale_addon_pages(self) -> None:
        protocol = self._protocol("21/84", "5799", "2026-06-12")
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._output_dir(tmp)
            kwargs = dict(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=[protocol],
                entries=[self._entry(output_dir, protocol)],
                abg_mps=[],
                mp_lookup={},
            )
            build_dip_pulse_site.render_site(**kwargs, features=all_selection())
            self.assertTrue((output_dir / "bills" / "index.html").exists())
            self.assertTrue((output_dir / "abgeordnete" / "index.html").exists())
            build_dip_pulse_site.render_site(**kwargs, features=default_selection())
            self.assertFalse((output_dir / "bills" / "index.html").exists())
            self.assertFalse((output_dir / "abgeordnete" / "index.html").exists())
            self.assertFalse((output_dir / "data" / "bills.json").exists())
            self.assertFalse((output_dir / "data" / "abgeordnete.json").exists())

    def test_feature_manifest_and_bootstrap_are_written_everywhere(self) -> None:
        protocol = self._protocol("21/84", "5799", "2026-06-12")
        selection = all_selection()
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._output_dir(tmp)
            build_dip_pulse_site.render_site(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=[protocol],
                entries=[],
                abg_mps=[],
                mp_lookup={},
                features=selection,
            )
            manifest = json.loads((output_dir / "data" / "features.json").read_text(encoding="utf-8"))
            available = {item["id"] for item in manifest["features"] if item["available"]}
            self.assertEqual(available, selection.ids)
            for page in output_dir.rglob("*.html"):
                markup = page.read_text(encoding="utf-8")
                self.assertIn("bundestag-pulse-features", markup, msg=str(page))
                self.assertIn("data-feature-", markup, msg=str(page))
                self.assertIn("settings-toggle", markup, msg=str(page))

    def test_settings_page_distinguishes_core_and_unbuilt_features(self) -> None:
        markup = build_dip_pulse_site.render_settings_page(default_selection())
        self.assertIn("is-unavailable", markup)
        self.assertIn("--enable votes", markup)
        self.assertRegex(markup, r'data-feature-toggle="dip-fetch"[^>]*checked disabled')
        self.assertRegex(markup, r'data-feature-toggle="votes"[^>]*disabled')


class FeatureArgumentCompatibilityTests(unittest.TestCase):
    def test_legacy_flags_map_with_sparse_namespaces(self) -> None:
        args = SimpleNamespace(no_roster=True, no_abgeordnetenwatch=True, summary_mode="off")
        with tempfile.TemporaryDirectory() as tmp:
            selection = build_dip_pulse_site.resolve_from_args(args, root=Path(tmp))
        self.assertNotIn("mp-roster", selection)
        self.assertNotIn("aw-profiles", selection)
        self.assertNotIn("summaries", selection)

    def test_cli_enable_overrides_file_disable_and_cli_disable_wins(self) -> None:
        args = SimpleNamespace(enable=["votes"], disable=["bills"], features=None, features_file=None)
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "features.json").write_text('{"disable":["votes"]}', encoding="utf-8")
            with mock.patch.dict("os.environ", {"BUNDESTAG_PULSE_FEATURES": "+bills"}):
                selection = build_dip_pulse_site.resolve_from_args(args, root=Path(tmp))
        self.assertIn("votes", selection)
        self.assertNotIn("bills", selection)


if __name__ == "__main__":
    unittest.main()
