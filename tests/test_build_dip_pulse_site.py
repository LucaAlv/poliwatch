from __future__ import annotations

import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import _support  # noqa: F401
import build_dip_pulse_site
import persist_dip_pulse_store as pulse_store
import render_dip_pulse_html as pulse_html
from features import all_selection, default_selection


class DossierProgressTests(unittest.TestCase):
    def test_reports_new_cached_and_completed_dossiers(self) -> None:
        protocols = [
            {"id": "5805", "dokumentnummer": "21/87", "datum": "2026-06-25"},
            {"id": "5806", "dokumentnummer": "21/88", "datum": "2026-06-26"},
        ]
        cached_report = {"protocol": protocols[1]}
        built: list[tuple[str, dict[str, Any] | None]] = []

        def load_existing(protocol: dict[str, Any]) -> dict[str, Any] | None:
            return cached_report if protocol["id"] == "5806" else None

        def build_dossier(
            protocol: dict[str, Any], existing: dict[str, Any] | None
        ) -> dict[str, Any]:
            built.append((protocol["id"], existing))
            return {"report": {"protocol": protocol}}

        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            entries = build_dip_pulse_site.build_dossiers_with_progress(
                protocols,
                load_existing=load_existing,
                build_dossier=build_dossier,
            )

        output = stderr.getvalue()
        self.assertIn("[dossiers] Processing 2 dossier(s).", output)
        self.assertIn("[1/2] Downloading new dossier: BT-PlPr 21/87 (ID 5805) from 2026-06-25.", output)
        self.assertIn("[2/2] Refreshing cached dossier: BT-PlPr 21/88 (ID 5806) from 2026-06-26.", output)
        self.assertIn("[dossiers] Completed 2/2 dossier(s)", output)
        self.assertEqual(built, [("5805", None), ("5806", cached_report)])
        self.assertEqual(len(entries), 2)


class CollectAbgeordneteTests(unittest.TestCase):
    def test_database_rebuild_preserves_cached_roster_unless_refreshing_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database_path = Path(tmp) / "pulse.sqlite"
            conn = pulse_store.connect(database_path)
            try:
                pulse_store.initialize(conn)
                now = pulse_store.utc_now()
                with conn:
                    party_id = pulse_store.upsert_party(conn, "SPD", now)
                    pulse_store.upsert_mp(
                        conn,
                        now=now,
                        display_name="Ada Lovelace",
                        party_id=party_id,
                        identity_key="dip:ada",
                        dip_person_id="ada",
                        is_mdb=True,
                    )
            finally:
                conn.close()

            build_dip_pulse_site.rebuild_database_from_entries(database_path, [])
            conn = pulse_store.connect(database_path)
            try:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM mps WHERE is_mdb = 1").fetchone()[0], 1)
            finally:
                conn.close()

            build_dip_pulse_site.rebuild_database_from_entries(
                database_path,
                [],
                preserve_roster=False,
            )
            conn = pulse_store.connect(database_path)
            try:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM mps WHERE is_mdb = 1").fetchone()[0], 0)
            finally:
                conn.close()

    def test_cached_votes_and_profiles_survive_non_enriching_update(self) -> None:
        cached_profile = {"id": 42, "url": "https://example.test/ada"}
        previous = {
            "agenda_items": [{
                "index": 1,
                "top_id": "T1",
                "votes": [{"id": "vote-1", "members": []}],
                "xml_speakers": [{"speaker": {
                    "xml_redner_id": "11001",
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                    "abgeordnetenwatch": cached_profile,
                }}],
            }],
        }
        report = {
            "agenda_items": [{
                "index": 1,
                "top_id": "T1",
                "xml_speakers": [{"speaker": {
                    "xml_redner_id": "11001",
                    "first_name": "Ada",
                    "last_name": "Lovelace",
                }}],
            }],
        }

        build_dip_pulse_site.reuse_existing_dossier_enrichments(
            report,
            previous,
            votes=True,
            profiles=True,
        )

        item = report["agenda_items"][0]
        self.assertEqual(item["votes"][0]["id"], "vote-1")
        self.assertEqual(item["xml_speakers"][0]["speaker"]["abgeordnetenwatch"], cached_profile)
        self.assertIsNot(item["votes"], previous["agenda_items"][0]["votes"])

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

    def test_reduced_enrichment_selection_still_publishes_addon_pages(self) -> None:
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
            self.assertTrue((output_dir / "bills" / "index.html").exists())
            self.assertTrue((output_dir / "abgeordnete" / "index.html").exists())
            self.assertIn("--no-persist", (output_dir / "database.html").read_text(encoding="utf-8"))
            rendered = "\n".join(path.read_text(encoding="utf-8") for path in output_dir.rglob("*.html"))
            self.assertIn('href="bills/index.html"', rendered)
            self.assertIn('data-feature="bills"', rendered)

    def test_later_reduced_enrichment_render_keeps_addon_pages(self) -> None:
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
            stale_bill = output_dir / "bills" / "bill-removed.html"
            stale_mp = output_dir / "abgeordnete" / "999.html"
            stale_bill.write_text("stale", encoding="utf-8")
            stale_mp.write_text("stale", encoding="utf-8")
            build_dip_pulse_site.render_site(**kwargs, features=default_selection())
            self.assertTrue((output_dir / "bills" / "index.html").exists())
            self.assertTrue((output_dir / "abgeordnete" / "index.html").exists())
            self.assertTrue((output_dir / "data" / "bills.json").exists())
            self.assertTrue((output_dir / "data" / "abgeordnete.json").exists())
            self.assertFalse(stale_bill.exists())
            self.assertFalse(stale_mp.exists())

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
            self.assertEqual(available, all_selection().ids)
            self.assertTrue(all(item["readiness"] in {"ready", "partial", "unavailable"} for item in manifest["features"]))
            for page in output_dir.rglob("*.html"):
                markup = page.read_text(encoding="utf-8")
                self.assertIn("bundestag-pulse-features", markup, msg=str(page))
                self.assertIn("data-feature-", markup, msg=str(page))
                self.assertIn("settings-toggle", markup, msg=str(page))

    def test_settings_page_only_switches_user_facing_experiences(self) -> None:
        markup = build_dip_pulse_site.render_settings_page(
            default_selection(),
            {"votes": "unavailable", "summaries": "partial"},
        )
        self.assertNotIn("--enable votes", markup)
        self.assertNotIn('data-feature-toggle="dip-fetch"', markup)
        self.assertNotIn('data-feature-toggle="mp-roster"', markup)
        self.assertRegex(markup, r'data-feature-toggle="votes"[^>]*>')
        self.assertIn("Noch keine Daten verfügbar", markup)
        self.assertIn("Datenstand dieser Veröffentlichung", markup)


class PeriodOrderTests(unittest.TestCase):
    """Wahlperiode buckets are keyed by string, so they need a numeric sort."""

    @staticmethod
    def _protocol(wahlperiode: int | None, number: int) -> dict[str, Any]:
        protocol: dict[str, Any] = {
            "id": f"{number}",
            "dokumentnummer": f"{wahlperiode or 0}/{number}",
            "datum": "2026-06-12",
            "titel": f"Protokoll {number}",
        }
        if wahlperiode is not None:
            protocol["wahlperiode"] = wahlperiode
        return protocol

    def test_period_sort_key_orders_numerically_with_fallback_last(self) -> None:
        periods = ["9", "21", "1", "unbekannt", "10", "2"]
        self.assertEqual(
            sorted(periods, key=build_dip_pulse_site.period_sort_key),
            ["1", "2", "9", "10", "21", "unbekannt"],
        )

    def test_catalog_page_orders_periods_lowest_first(self) -> None:
        # Shuffled input so the assertion cannot pass by accident of arrival order.
        protocols = [
            self._protocol(9, 1),
            self._protocol(21, 2),
            self._protocol(1, 3),
            self._protocol(None, 4),
            self._protocol(10, 5),
            self._protocol(2, 6),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "site"
            markup = build_dip_pulse_site.render_catalog_page(
                protocols,
                [],
                output_dir / "data" / "katalog.json",
                output_dir,
            )

        expected = ["1", "2", "9", "10", "21", "unbekannt"]
        # The clickable badges in div.periods and the Wahlperiode dropdown render
        # from the same list, so both must read lowest period first.
        self.assertEqual(re.findall(r'data-wp-filter="([^"]+)"', markup), expected)
        self.assertEqual(re.findall(r'<option value="([^"]+)">WP ', markup), expected)

    def test_overview_page_orders_periods_lowest_first(self) -> None:
        protocols = [
            self._protocol(9, 1),
            self._protocol(21, 2),
            self._protocol(1, 3),
            self._protocol(10, 4),
        ]

        markup = build_dip_pulse_site.render_overview(protocols, [])

        self.assertEqual(re.findall(r'class="badge">WP ([^ ]+) ', markup), ["1", "9", "10", "21"])


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

    def test_enrich_selects_network_work_without_ui_features(self) -> None:
        args = SimpleNamespace(
            enrich=["votes", "mp-roster"],
            enable=[],
            disable=[],
            features=None,
            features_file=None,
            vote_scan_pages=None,
        )
        with tempfile.TemporaryDirectory() as tmp:
            selection = build_dip_pulse_site.resolve_from_args(args, root=Path(tmp))
        build_dip_pulse_site.apply_to_args(args, selection)
        self.assertIn("votes", selection)
        self.assertIn("mp-roster", selection)
        self.assertNotIn("bills", selection)
        self.assertEqual(args.vote_scan_pages, 30)
        self.assertFalse(args.no_roster)
        self.assertTrue(args.no_abgeordnetenwatch)

    def test_default_update_enrichments_do_not_make_network_side_jobs(self) -> None:
        args = SimpleNamespace(
            enrich=[],
            enable=[],
            disable=[],
            features=None,
            features_file=None,
            vote_scan_pages=None,
        )
        with tempfile.TemporaryDirectory() as tmp:
            selection = build_dip_pulse_site.resolve_from_args(args, root=Path(tmp))
        build_dip_pulse_site.apply_to_args(args, selection)
        self.assertEqual(args.vote_scan_pages, 0)
        self.assertTrue(args.no_roster)
        self.assertTrue(args.no_abgeordnetenwatch)

    def test_positive_vote_scan_pages_implies_vote_enrichment(self) -> None:
        args = SimpleNamespace(
            enrich=[],
            enable=[],
            disable=[],
            features=None,
            features_file=None,
            vote_scan_pages=4,
        )
        with tempfile.TemporaryDirectory() as tmp:
            selection = build_dip_pulse_site.resolve_from_args(args, root=Path(tmp))
        build_dip_pulse_site.apply_to_args(args, selection)
        self.assertIn("votes", selection)
        self.assertEqual(args.vote_scan_pages, 4)

    def test_unknown_enrichment_fails_with_available_choices(self) -> None:
        args = SimpleNamespace(
            enrich=["bills"],
            enable=[],
            disable=[],
            features=None,
            features_file=None,
            vote_scan_pages=None,
        )
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(
            build_dip_pulse_site.FeatureError,
            "Verfügbar",
        ):
            build_dip_pulse_site.resolve_from_args(args, root=Path(tmp))



class SittingWeekComparisonTests(unittest.TestCase):
    """The Wochenvergleich band on puls.html, and the aggregation behind it."""

    @staticmethod
    def _speaker(fraktion: str | None, chars: int, role: str | None = None) -> dict[str, Any]:
        return {
            "char_count": chars,
            "speaker": {"fraktion": fraktion, "role": role, "display_name": "Test Person"},
        }

    @classmethod
    def _item(
        cls,
        index: int,
        parties: list[tuple[str, int]],
        positions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        speakers = [cls._speaker(party, chars) for party, chars in parties]
        return {
            "index": index,
            "top_id": f"Tagesordnungspunkt {index}",
            "heading": f"Beratung {index}",
            "xml_speakers": speakers,
            "xml_speech_count": len(speakers),
            "api": {"positions": positions or []},
        }

    @classmethod
    def _entry(cls, datum: str, document_number: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        slug = document_number.replace("/", "-")
        return {
            "report": {
                "protocol": {"datum": datum, "dokumentnummer": document_number, "titel": "T"},
                "agenda_items": items,
                "validation_summary": {},
            },
            "page_path": Path(f"plenarprotokoll-{slug}.html"),
            "report_path": Path(f"plenarprotokoll-{slug}.json"),
            "slug": slug,
        }

    # -- bucketing ---------------------------------------------------------

    def test_iso_week_key_and_grouping(self) -> None:
        self.assertEqual(pulse_html.iso_week_key("2026-06-12"), (2026, 24))
        self.assertIsNone(pulse_html.iso_week_key(None))
        self.assertIsNone(pulse_html.iso_week_key("nicht-ein-datum"))

        entries = [
            self._entry("2026-06-10", "21/82", []),
            self._entry("2026-06-11", "21/83", []),
            self._entry("2026-06-12", "21/84", []),
        ]
        weeks = pulse_html.group_entries_by_week(entries)
        self.assertEqual(list(weeks), [(2026, 24)])
        self.assertEqual(len(weeks[(2026, 24)]), 3)

    def test_group_entries_by_week_drops_undated_sittings(self) -> None:
        weeks = pulse_html.group_entries_by_week(
            [self._entry("2026-06-12", "21/84", []), self._entry("", "21/85", [])]
        )
        self.assertEqual(list(weeks), [(2026, 24)])

    # -- comparison --------------------------------------------------------

    def test_equal_sitting_counts_compare_raw_totals(self) -> None:
        current = pulse_html.week_stats(
            (2026, 24),
            [
                self._entry("2026-06-10", "21/82", [self._item(1, [("SPD", 100), ("AfD", 100)])]),
                self._entry("2026-06-11", "21/83", [self._item(1, [("SPD", 100)])]),
            ],
        )
        previous = pulse_html.week_stats(
            (2026, 21),
            [
                self._entry("2026-05-20", "21/79", [self._item(1, [("SPD", 100)])]),
                self._entry("2026-05-21", "21/80", [self._item(1, [("SPD", 100)])]),
            ],
        )
        comparison = pulse_html.week_comparison(current, previous)

        self.assertFalse(comparison["normalised"])
        speeches = next(m for m in comparison["metrics"] if m["key"] == "speech_count")
        self.assertEqual(speeches["current"], 3.0)
        self.assertEqual(speeches["previous"], 2.0)
        self.assertEqual(speeches["delta"], 1.0)
        self.assertAlmostEqual(speeches["delta_percent"], 50.0)

    def test_unequal_sitting_counts_switch_to_per_sitting_figures(self) -> None:
        # A week caught mid-flight - one sitting of the usual two - must not read
        # as a collapse just for being unfinished.
        current = pulse_html.week_stats(
            (2026, 24),
            [self._entry("2026-06-10", "21/82", [self._item(1, [("SPD", 100), ("AfD", 100)])])],
        )
        previous = pulse_html.week_stats(
            (2026, 21),
            [
                self._entry("2026-05-20", "21/79", [self._item(1, [("SPD", 100), ("AfD", 100)])]),
                self._entry("2026-05-21", "21/80", [self._item(1, [("SPD", 100), ("AfD", 100)])]),
            ],
        )
        comparison = pulse_html.week_comparison(current, previous)

        self.assertTrue(comparison["normalised"])
        speeches = next(m for m in comparison["metrics"] if m["key"] == "speech_count")
        self.assertEqual(speeches["current"], 2.0)
        self.assertEqual(speeches["previous"], 2.0)
        self.assertEqual(speeches["delta"], 0.0)

    def test_truncated_dossier_drops_the_text_metric(self) -> None:
        # item_stats() falls back to xml_speakers_first, which carries no text, so
        # a character total from such a sitting would be short. Better no metric
        # than a wrong one.
        truncated = self._entry("2026-06-10", "21/82", [self._item(1, [("SPD", 100)])])
        item = truncated["report"]["agenda_items"][0]
        item["xml_speakers_first"] = item.pop("xml_speakers")

        stats = pulse_html.week_stats((2026, 24), [truncated])
        self.assertFalse(stats["chars_complete"])
        self.assertEqual(stats["speech_count"], 1)

        whole = pulse_html.week_stats(
            (2026, 21), [self._entry("2026-05-20", "21/79", [self._item(1, [("SPD", 100)])])]
        )
        comparison = pulse_html.week_comparison(stats, whole)
        self.assertNotIn("total_chars", [m["key"] for m in comparison["metrics"]])

    def test_week_span_measures_whole_weeks(self) -> None:
        self.assertEqual(pulse_html.week_span((2026, 21), (2026, 24)), 3)
        self.assertEqual(pulse_html.week_span((2023, 17), (2026, 24)), 163)

    # -- returning procedures ---------------------------------------------

    def test_returning_vorgaenge_match_on_vorgang_id(self) -> None:
        weeks = pulse_html.group_entries_by_week(
            [
                self._entry(
                    "2026-03-04",
                    "21/58",
                    [self._item(6, [("SPD", 10)], [{"vorgang_id": "331625", "vorgangsposition": "1. Beratung",
                                                    "vorgangstyp": "Gesetzgebung", "titel": "Ein Gesetz"}])],
                ),
                self._entry(
                    "2026-06-12",
                    "21/84",
                    [self._item(5, [("SPD", 10)], [{"vorgang_id": "331625", "vorgangsposition": "2. Beratung",
                                                    "vorgangstyp": "Gesetzgebung", "titel": "Ein Gesetz"}])],
                ),
            ]
        )
        rows = pulse_html.returning_vorgaenge(weeks, (2026, 24))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["vorgang_id"], "331625")
        self.assertEqual(rows[0]["first"]["vorgangsposition"], "1. Beratung")
        self.assertEqual(rows[0]["latest"]["vorgangsposition"], "2. Beratung")
        self.assertEqual(rows[0]["latest"]["index"], 5)

    def test_returning_vorgaenge_ignores_one_off_procedures(self) -> None:
        weeks = pulse_html.group_entries_by_week(
            [
                self._entry("2026-03-04", "21/58",
                            [self._item(1, [("SPD", 10)], [{"vorgang_id": "111", "titel": "A"}])]),
                self._entry("2026-06-12", "21/84",
                            [self._item(1, [("SPD", 10)], [{"vorgang_id": "222", "titel": "B"}])]),
            ]
        )
        self.assertEqual(pulse_html.returning_vorgaenge(weeks, (2026, 24)), [])

    def test_returning_vorgaenge_dedupes_mitberaten_twins(self) -> None:
        # DIP issues one vorgang_id per document, so a single bill can surface
        # twice under sibling ids that name each other in `mitberaten`.
        def positions(position: str) -> list[dict[str, Any]]:
            return [
                {"vorgang_id": "331625", "vorgangsposition": position, "vorgangstyp": "Gesetzgebung",
                 "titel": "Vaterschaft A", "mitberaten": [{"id": "329481"}]},
                {"vorgang_id": "329481", "vorgangsposition": position, "vorgangstyp": "Gesetzgebung",
                 "titel": "Vaterschaft B", "mitberaten": [{"id": "331625"}]},
            ]

        weeks = pulse_html.group_entries_by_week(
            [
                self._entry("2026-03-04", "21/58", [self._item(6, [("SPD", 10)], positions("1. Beratung"))]),
                self._entry("2026-06-12", "21/84", [self._item(5, [("SPD", 10)], positions("2. Beratung"))]),
            ]
        )
        rows = pulse_html.returning_vorgaenge(weeks, (2026, 24))
        self.assertEqual(len(rows), 1)

    # -- rendered markup ---------------------------------------------------

    def _render(self, entries: list[dict[str, Any]]) -> str:
        return build_dip_pulse_site.render_front_page(entries, features=default_selection())

    def test_front_page_renders_the_week_comparison(self) -> None:
        entries = [
            self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100), ("AfD", 100)])]),
            self._entry("2026-05-22", "21/81", [self._item(1, [("SPD", 100)])]),
        ]
        markup = self._render(entries)

        self.assertIn('id="wochenvergleich"', markup)
        self.assertIn("KW 24/2026", markup)
        self.assertIn("KW 21/2026", markup)
        self.assertIn("Redeanteil der Fraktionen", markup)
        self.assertIn("Debattenprofil", markup)

    def test_placeholder_is_gone(self) -> None:
        markup = self._render(
            [self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100)])])]
        )
        self.assertNotIn("sobald mehrere Sitzungswochen", markup)
        self.assertNotIn("im selben Modell normalisiert", markup)

    def test_gap_guard_suppresses_an_unrelated_week(self) -> None:
        # Two sittings three years apart are not a Wochenvergleich. The band must
        # say so rather than name a week from a different era.
        entries = [
            self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100)])]),
            self._entry("2023-04-27", "20/100", [self._item(1, [("SPD", 100)])]),
        ]
        markup = self._render(entries)

        self.assertIn("Noch keine Vergleichswoche", markup)
        self.assertNotIn("KW 17/2023", markup)
        self.assertNotIn("2023-04-27", markup)

    def test_single_week_has_no_comparison(self) -> None:
        markup = self._render(
            [self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100)])])]
        )
        self.assertIn("Noch keine Vergleichswoche", markup)

    def test_running_week_is_labelled_per_sitting(self) -> None:
        entries = [
            self._entry("2026-06-10", "21/82", [self._item(1, [("SPD", 100), ("AfD", 100)])]),
            self._entry("2026-05-21", "21/80", [self._item(1, [("SPD", 100)])]),
            self._entry("2026-05-22", "21/81", [self._item(1, [("SPD", 100)])]),
        ]
        markup = self._render(entries)

        self.assertIn("Werte je Sitzung", markup)
        self.assertIn("je Sitzung", markup)


if __name__ == "__main__":
    unittest.main()
