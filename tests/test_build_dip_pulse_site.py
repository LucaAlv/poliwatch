from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import _support  # noqa: F401
import build_dip_pulse_site
import facts
import persist_dip_pulse_store as pulse_store
import render_dip_pulse_html as pulse_html
from features import EnrichmentSelection, all_selection, default_selection


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

    def test_expected_dossier_failure_keeps_valid_dossiers(self) -> None:
        protocols = [
            {"id": "5805", "dokumentnummer": "21/87"},
            {"id": "5806", "dokumentnummer": "21/88"},
        ]

        def build(protocol: dict[str, Any], _existing: dict[str, Any] | None) -> dict[str, Any]:
            if protocol["id"] == "5805":
                raise build_dip_pulse_site.dip.DipError("XML unavailable")
            return {"report": {"protocol": protocol}}

        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            entries = build_dip_pulse_site.build_dossiers_with_progress(
                protocols,
                load_existing=lambda _protocol: None,
                build_dossier=build,
            )

        self.assertEqual([entry["report"]["protocol"]["id"] for entry in entries], ["5806"])
        self.assertEqual(protocols[0]["dossier_failure_reasons"], ["source_unavailable"])
        self.assertIn("Completed 1/2 dossier(s)", stderr.getvalue())


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

    def test_database_rebuild_carries_the_facts_tables_into_the_fresh_store(self) -> None:
        # An online build replaces the store file (rebuild_database_from_entries
        # writes a temp store and renames it over the old one). Without the
        # carry-over the engine would have nothing to diff against on the one
        # build that actually runs in production, and the changed-winners
        # report (D11) would never fire. The engine overwrites these rows right
        # afterwards if anything moved.
        with tempfile.TemporaryDirectory() as tmp:
            database_path = Path(tmp) / "pulse.sqlite"
            conn = pulse_store.connect(database_path)
            try:
                pulse_store.initialize(conn)
                facts.write_snapshot(
                    conn,
                    {
                        "fact_metrics": [facts.metric_row(facts.REGISTRY[0])],
                        "facts": [
                            facts._fact_values(
                                {
                                    "metric_id": facts.REGISTRY[0]["id"],
                                    "metric_version": 1,
                                    "period_kind": "week",
                                    "period_key": "2026-W37",
                                    "iso_year": 2026,
                                    "iso_week": 37,
                                    "wahlperiode": 21,
                                    "complete": 1,
                                    "week_n": 2,
                                    "value": 0.01,
                                    "eligible": 1,
                                    "publishable": 1,
                                    "rank": 1,
                                }
                            )
                        ],
                        "fact_sources": [
                            ["week", "2026-W37", facts.REGISTRY[0]["id"],
                             "vote", "21/94", None, None, None, "https://example.test/v", 0]
                        ],
                    },
                )
                before = facts.read_snapshot(conn)
            finally:
                conn.close()

            build_dip_pulse_site.rebuild_database_from_entries(database_path, [])

            conn = pulse_store.connect(database_path)
            try:
                self.assertEqual(facts.read_snapshot(conn), before)
                stored = facts.load_facts(conn)
                self.assertEqual(len(stored), 1)
                self.assertEqual(stored[0]["period_key"], "2026-W37")
                self.assertEqual(
                    [r["document_number"] for r in stored[0]["receipts"]], ["21/94"]
                )
            finally:
                conn.close()

    def test_rebuild_warns_and_continues_when_the_previous_stores_facts_are_unreadable(self) -> None:
        # The except sqlite3.Error branch around the carry-over read (D1A):
        # a store too damaged to read there is about to be replaced anyway,
        # so the rebuild must still succeed, just without the carry-over
        # (facts_snapshot stays None, nothing written for facts.* yet -- the
        # engine that runs right after this recomputes them from scratch).
        with tempfile.TemporaryDirectory() as tmp:
            database_path = Path(tmp) / "pulse.sqlite"
            conn = pulse_store.connect(database_path)
            try:
                pulse_store.initialize(conn)
            finally:
                conn.close()

            stderr = io.StringIO()
            with mock.patch.object(
                build_dip_pulse_site.facts,
                "read_snapshot",
                side_effect=build_dip_pulse_site.sqlite3.OperationalError("disk I/O error"),
            ), mock.patch("sys.stderr", stderr):
                build_dip_pulse_site.rebuild_database_from_entries(database_path, [])

            self.assertIn("previous facts unreadable", stderr.getvalue())
            conn = pulse_store.connect(database_path)
            try:
                self.assertFalse(facts.tables_exist(conn))
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

    def test_required_summaries_use_valid_cache_after_provider_failure(self) -> None:
        speeches = [
            {
                "rede_id": f"rede-{index}",
                "source_page": {"page": 20 + index},
                "speaker": {"display_name": f"Person {index}"},
                "text": f"Quellentext {index}",
            }
            for index in range(1, 5)
        ]
        top = {"top_id": "TOP 1", "heading": "Beratung", "speeches": speeches}
        chunks = build_dip_pulse_site.dip.summary_source_chunks(top)[:3]
        cached_summary = {
            "provider": "test",
            "model": "test",
            "summary_schema_version": build_dip_pulse_site.dip.SUMMARY_SCHEMA_VERSION,
            "prompt_version": build_dip_pulse_site.dip.SUMMARY_PROMPT_VERSION,
            "source_fingerprint": build_dip_pulse_site.dip.summary_source_fingerprint(top),
            "text": "Eine belegte Zusammenfassung.",
            "source_chunk_ids": [chunk["id"] for chunk in chunks],
            "source_chunks": chunks,
        }
        current_item = {
            "index": 1,
            "top_id": top["top_id"],
            "heading": top["heading"],
            "xml_speakers": speeches,
        }
        report = {
            "protocol": {"id": "5805", "pdf_url": "https://dserver.bundestag.de/btp/21/21084.pdf"},
            "agenda_items": [current_item],
            "summary_generation": {
                "enabled": True,
                "generated_top_count": 0,
                "failures": [{"top_id": "TOP 1", "reason": "provider_timeout"}],
            },
            "acquisition": {
                "summaries": {
                    "eligible": 1,
                    "generated": 0,
                    "omitted": 0,
                    "failed": 1,
                    "fallbacks": 0,
                    "records": 0,
                    "reused": 0,
                    "rejected": 1,
                    "failure_reasons": ["provider_timeout"],
                    "source": "llm-with-bundestag-citations",
                    "acquisition_state": "failed",
                    "attempted": True,
                    "attempted_at": "2026-09-19T10:00:00Z",
                }
            },
        }
        existing = {
            "agenda_items": [{**current_item, "llm_summary": cached_summary}],
            "acquisition": {"summaries": {"acquired_at": "2026-09-18T10:00:00Z"}},
        }

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(build_dip_pulse_site.dip, "build_report", return_value=report),
            mock.patch.object(
                build_dip_pulse_site,
                "write_report_files",
                return_value={"report": report},
            ) as write_files,
        ):
            build_dip_pulse_site.write_report_and_page(
                protocol={"id": "5805"},
                output_dir=Path(tmp),
                api_key="test-key",
                sleep=0,
                person_limit=0,
                vote_scan_pages=0,
                roll_call_list_id=None,
                summary_mode="required",
                summary_provider="anthropic",
                anthropic_api_key="test-key",
                gemini_api_key=None,
                summary_model=None,
                existing_report=existing,
            )

        written = write_files.call_args.args[0]
        self.assertEqual(written["agenda_items"][0]["llm_summary"], cached_summary)
        self.assertEqual(written["acquisition"]["summaries"]["acquisition_state"], "complete")
        self.assertEqual(written["acquisition"]["summaries"]["reused"], 1)
        self.assertEqual(written["acquisition"]["summaries"]["fallbacks"], 1)
        self.assertEqual(written["summary_generation"]["failures"], [])

    def test_summary_cache_reconciliation_preserves_domain_failure(self) -> None:
        speeches = [
            {"rede_id": f"rede-{index}", "text": f"Text {index}"}
            for index in range(1, 5)
        ]
        report = {
            "protocol": {},
            "agenda_items": [{
                "index": 1,
                "top_id": "TOP 1",
                "heading": "Beratung",
                "xml_speakers": speeches,
            }],
            "summary_generation": {"enabled": False, "reason": "source_unavailable"},
            "acquisition": {"summaries": {
                "eligible": 1,
                "generated": 0,
                "omitted": 0,
                "failed": 1,
                "fallbacks": 0,
                "failure_reasons": ["source_unavailable"],
            }},
        }

        build_dip_pulse_site.reconcile_generated_and_cached_summaries(report, None)

        facts = report["acquisition"]["summaries"]
        self.assertEqual(facts["acquisition_state"], "failed")
        self.assertEqual(facts["failed"], 1)
        self.assertEqual(facts["failure_reasons"], ["source_unavailable"])

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
                          paragraph_count, char_count, text, snippet,
                          created_at, updated_at
                        )
                        VALUES ('pp-test', ?, 'R1', 1, ?, 101, 1, 24, 'Rede text', 'Rede text', ?, ?)
                        """,
                        (agenda_item_id, speaker_mp_id, now, now),
                    )

                mps, lookup, canonical_by_mp_id = build_dip_pulse_site.collect_abgeordnete(conn)

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
                self.assertEqual(canonical_by_mp_id[roster_mp_id], roster_mp_id)
                self.assertEqual(canonical_by_mp_id[speaker_mp_id], roster_mp_id)
            finally:
                conn.close()


class CurrentPulseOrderTests(unittest.TestCase):
    """The site treats entries[0]/protocols[0] as the current pulse; puls.html renders its week."""

    def setUp(self) -> None:
        # puls.html logs its week to stderr on every render; keep the test output clean.
        patcher = mock.patch.object(sys, "stderr", new_callable=io.StringIO)
        patcher.start()
        self.addCleanup(patcher.stop)

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

    @staticmethod
    def _agenda_item(
        index: int,
        speech_count: int,
        fractions: tuple[str, ...],
        heading: str | None = None,
    ) -> dict[str, Any]:
        return {
            "index": index,
            "top_id": f"TOP {index}",
            "heading": f"Beratung des Antrags {index}" if heading is None else heading,
            "xml_speech_count": speech_count,
            "xml_speakers": [
                {"speaker": {"fraktion": fraction}, "char_count": 1000}
                for fraction in fractions
            ],
        }

    def _render_pulse(
        self,
        sittings: list[tuple[dict[str, Any], list[dict[str, Any]]]],
        features: Any = None,
        warnings: list[str] | None = None,
    ) -> str:
        """Render a whole site for the given (protocol, agenda_items) sittings.

        Returns puls.html, built on 2026-09-15 for the newest dated week.
        `warnings` are attached to the newest report.
        """
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._output_dir(tmp)
            entries = []
            for protocol, items in sittings:
                entry = self._entry(output_dir, protocol)
                entry["report"]["agenda_items"] = items
                entries.append(entry)
            if warnings:
                entries[0]["report"]["warnings"] = warnings
            kwargs: dict[str, Any] = dict(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=[protocol for protocol, _ in sittings],
                entries=entries,
                abg_mps=[],
                mp_lookup={},
            )
            if features is not None:
                kwargs["features"] = features
            build_dip_pulse_site.render_site(**kwargs, today=date(2026, 9, 15))
            return (output_dir / "puls.html").read_text(encoding="utf-8")

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
                today=date(2026, 9, 15),
            )

            for page in ("puls.html", "index.html", "overview.html", "sources.html"):
                markup = (output_dir / page).read_text(encoding="utf-8")
                self.assertIn("21/84", markup, msg=page)

            # The sitting chip keeps the ISO date in the markup as <time datetime>.
            pulse_markup = (output_dir / "puls.html").read_text(encoding="utf-8")
            self.assertIn('<time datetime="2026-06-12">Fr 12.06.</time> · 21/84', pulse_markup)
            self.assertIn("KW 24/2026", pulse_markup)
            self.assertNotIn("2023-04-27", pulse_markup)
            self.assertNotIn("KW 17/2023", pulse_markup)

    def test_page_actions_never_link_the_votes_panel(self) -> None:
        # The old hero carried a "#abstimmungen" action link that dangled
        # whenever the votes Baustein was off. Neither Baustein state may bring
        # it back, and the retired .pulse-actions styling must stay retired.
        sitting = [
            (
                self._protocol("21/84", "5799", "2026-06-12"),
                [self._agenda_item(1, 1, ("SPD",))],
            )
        ]

        for label, features in (("votes off", default_selection()), ("votes on", all_selection())):
            with self.subTest(features=label):
                markup = self._render_pulse(sitting, features=features)
                self.assertEqual(markup.count("#abstimmungen"), 0)
                self.assertNotIn("pulse-actions", markup)
                self.assertNotIn("primary-link", markup)
                # The votes card still renders as an anchor target. Publication
                # is deliberately independent of the build-time selection --
                # render_site() pins publication_selection() so a reduced
                # enrichment run never removes a visitor-facing block -- so the
                # id is present under either Baustein state and visitors toggle
                # it client-side through data-feature="votes".
                self.assertIn('id="abstimmungen"', markup)
                self.assertNotIn('data-feature="votes"', markup)

    def test_pulse_page_carries_no_attention_ranking(self) -> None:
        # The per-item Aufmerksamkeitsranking cards were retired from puls.html:
        # the dossier page already ranks the same items. Neither Baustein state
        # may bring the section, the validation-warning banner that used to live
        # inside it, or the retired Themenbewegung anchor back; the page actions
        # are the Wochenvergleich and the newest protocol of the week.
        sitting = [
            (
                self._protocol("21/84", "5799", "2026-06-12"),
                [self._agenda_item(1, 1, ("SPD",))],
            )
        ]

        for label, features in (("votes off", default_selection()), ("votes on", all_selection())):
            with self.subTest(features=label):
                markup = self._render_pulse(
                    sitting, features=features, warnings=["TOP 1: Redezahl weicht ab"]
                )
                for retired in (
                    "#aufmerksamkeit",
                    "attention-card",
                    "ranking-intro",
                    "Aufmerksamkeitsranking",
                    "Validierungswarnung",
                    "#bewegung",
                    "Protokolldossier",
                ):
                    self.assertNotIn(retired, markup)
                self.assertIn('href="#wochenvergleich"', markup)
                self.assertIn(
                    'href="protocols/plenarprotokoll-21-84.html">Neuestes Protokoll</a>', markup
                )

    def test_header_is_the_week_identity(self) -> None:
        # The page header names the sitting week, not one sitting: eyebrow, h1,
        # one chip per sitting, the facts sentence and the two actions. The
        # former hero's identity line, fact tiles and raw-source links are gone
        # (the dossier carries them).
        protocol = self._protocol("21/84", "5799", "2026-06-12")
        protocol["verteildatum"] = "2026-06-15"
        protocol["xml_url"] = "https://dserver.bundestag.de/btp/21/21084.xml"
        protocol["pdf_url"] = "https://dserver.bundestag.de/btp/21/21084.pdf"
        markup = self._render_pulse([(protocol, [self._agenda_item(1, 1, ("SPD",))])])
        header = re.search(r'<header class="page-header">(.*?)</header>', markup, re.S).group(1)

        # _render_pulse builds on 2026-09-15, fourteen ISO weeks after KW 24:
        # the stale-archive state, which leads with the age.
        self.assertIn('<span class="eyebrow">Letzte Sitzungswoche</span>', header)
        self.assertIn("<h1>Was der Bundestag in KW 24/2026 verhandelt hat</h1>", header)
        self.assertIn(
            '<a href="protocols/plenarprotokoll-21-84.html"><time datetime="2026-06-12">Fr 12.06.</time> · 21/84</a>',
            header,
        )
        self.assertIn(
            "Letzte Sitzungswoche vor 14 Wochen · 1 Rede in 1 Tagesordnungspunkt · 1 Sitzung, "
            'letztes Protokoll 21/84 verteilt am <time datetime="2026-06-15">15.06.2026</time> · '
            'Auswertung vom <time datetime="2026-09-15">15.09.2026</time>',
            header,
        )
        self.assertIn('<a href="#wochenvergleich">Wochenvergleich</a>', header)
        self.assertIn('<a href="protocols/plenarprotokoll-21-84.html">Neuestes Protokoll</a>', header)
        for retired in ("BT-PlPr", "Sitzung vom", "metric-grid", "Drucksachen", "21084.xml", "Erzeugtes JSON", "lede-sources"):
            self.assertNotIn(retired, markup, msg=retired)
        self.assertNotIn("source-panel", markup)
        self.assertNotIn("Datenbank erkunden", markup)

    def test_header_falls_back_to_the_sitting_date_without_verteildatum(self) -> None:
        # Cached protocols from older builds can lack verteildatum and the
        # source URLs. The old panel rendered the links as href="" -- a link
        # back to puls.html itself -- and a dangling "verteilt am".
        markup = self._render_pulse(
            [(self._protocol("21/84", "5799", "2026-06-12"), [self._agenda_item(1, 1, ("SPD",))])]
        )
        header = re.search(r'<header class="page-header">(.*?)</header>', markup, re.S).group(1)

        self.assertNotIn('href=""', markup)
        self.assertIn('letztes Protokoll 21/84 vom <time datetime="2026-06-12">12.06.2026</time>', header)
        self.assertNotIn("verteilt am", header)

    def test_retired_hero_blocks_are_gone(self) -> None:
        # The hero card, the fact tiles, the "Quellen" row, the Themenbewegung
        # card and the per-sitting votes panel were dissolved into the radar and
        # the Wochenvergleich band. None of their markup or copy may survive.
        sitting = [(self._protocol("21/84", "5799", "2026-06-12"), [self._agenda_item(1, 1, ("SPD",))])]
        markup = self._render_pulse(sitting, features=all_selection())
        for retired in (
            "pulse-feature ",
            "feature-grid",
            "feature-microgrid",
            "radar-hero",
            "latest-panel",
            "pulse-lede",
            "lede-",
            "Themenbewegung",
            "Was nach vorne r",
            "Zusammenfassung der aktuellsten Sitzung",
            "Abstimmungsverschiebung",
            "Wo Stimmen das Bild ver",
            "Aktueller Lageblick",
            "Belege zum Schwerpunkt",
            "sobald gen",
        ):
            self.assertNotIn(retired, markup, msg=retired)
        self.assertIn('<section class="radar" aria-labelledby="radar-h2">', markup)
        self.assertIn('id="wochenvergleich"', markup)

    def test_radar_hrefs_resolve_in_the_generated_dossier(self) -> None:
        # Every radar href (title, footer link, trace, receipts) has to land on
        # a real anchor in the dossier page this same build wrote. A receipt
        # whose speech is not in the item's speaker list degrades to a span.
        protocol = self._protocol("21/84", "5799", "2026-06-12")
        items = [
            self._agenda_item(1, 3, ("SPD", "CDU/CSU", "AfD")),
            self._agenda_item(2, 2, ("AfD", "SPD")),
            self._agenda_item(3, 1, ("SPD",)),
        ]
        for item in items:
            for n, speech in enumerate(item["xml_speakers"], start=1):
                speech["rede_id"] = f"ID{item['index']}0{n}"
                speech["speaker"]["display_name"] = f"Person {n}"
        items[0]["llm_summary"] = {
            "text": "Kurz gesagt.",
            "source_chunks": [
                {"id": "R-1", "rede_id": "ID101", "source_page": {"page": "100"}},
                {"id": "R-9", "rede_id": "NOPE", "source_page": {"page": "101"}},
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._output_dir(tmp)
            # Written through write_report_files() so the dossier page really
            # exists on disk, the way it does in a production build.
            entry = build_dip_pulse_site.write_report_files(
                report={"protocol": protocol, "validation_summary": {}, "agenda_items": items},
                output_dir=output_dir,
            )

            build_dip_pulse_site.render_site(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=[protocol],
                entries=[entry],
                abg_mps=[],
                mp_lookup={},
                today=date(2026, 9, 15),
            )

            markup = (output_dir / "puls.html").read_text(encoding="utf-8")
            radar = re.search(r'<section class="radar".*?</section>', markup, re.S).group(0)
            hrefs = re.findall(r'href="(protocols/[^"]+)"', radar)
            self.assertEqual(len(re.findall(r'<li class="radar-row"', radar)), 3)
            self.assertIn("protocols/plenarprotokoll-21-84.html#speech-1-ID101", hrefs)
            self.assertIn("<span>R-9 · S. 101</span>", radar)
            self.assertGreaterEqual(len(hrefs), 7)
            for href in hrefs:
                with self.subTest(href=href):
                    page, _, anchor = href.partition("#")
                    target = output_dir / page
                    self.assertTrue(target.exists(), msg=href)
                    self.assertIn(f'id="{anchor}"', target.read_text(encoding="utf-8"), msg=href)

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
                today=date(2026, 9, 15),
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
                today=date(2026, 9, 15),
            )
            self.assertTrue((output_dir / "bills" / "index.html").exists())
            self.assertTrue((output_dir / "abgeordnete" / "index.html").exists())
            self.assertIn("--no-persist", (output_dir / "database.html").read_text(encoding="utf-8"))
            rendered = "\n".join(path.read_text(encoding="utf-8") for path in output_dir.rglob("*.html"))
            self.assertIn('href="bills/index.html"', rendered)
            self.assertNotIn('data-feature=', rendered)

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
            build_dip_pulse_site.render_site(**kwargs, features=all_selection(), today=date(2026, 9, 15))
            self.assertTrue((output_dir / "bills" / "index.html").exists())
            self.assertTrue((output_dir / "abgeordnete" / "index.html").exists())
            stale_bill = output_dir / "bills" / "bill-removed.html"
            stale_mp = output_dir / "abgeordnete" / "999.html"
            stale_bill.write_text("stale", encoding="utf-8")
            stale_mp.write_text("stale", encoding="utf-8")
            build_dip_pulse_site.render_site(**kwargs, features=default_selection(), today=date(2026, 9, 15))
            self.assertTrue((output_dir / "bills" / "index.html").exists())
            self.assertTrue((output_dir / "abgeordnete" / "index.html").exists())
            self.assertTrue((output_dir / "data" / "bills.json").exists())
            self.assertTrue((output_dir / "data" / "abgeordnete.json").exists())
            self.assertFalse(stale_bill.exists())
            self.assertFalse(stale_mp.exists())

    def test_schema_v2_manifest_and_fixed_presentation_are_written_everywhere(self) -> None:
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
                today=date(2026, 9, 15),
            )
            manifest = json.loads((output_dir / "data" / "features.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 2)
            self.assertEqual(manifest["presentation"], {"mode": "fixed", "ai_summary_default": "expanded"})
            self.assertEqual(
                set(manifest["domains"]),
                {"catalog", "dossiers", "votes", "profiles", "roster", "bills", "summaries"},
            )
            for page in output_dir.rglob("*.html"):
                markup = page.read_text(encoding="utf-8")
                self.assertNotIn("bundestag-pulse-features", markup, msg=str(page))
                self.assertNotIn("data-feature", markup, msg=str(page))
                self.assertNotIn("settings-toggle", markup, msg=str(page))

    def test_settings_page_is_compatibility_copy_without_switches(self) -> None:
        markup = build_dip_pulse_site.render_settings_page(
            default_selection(),
            {"votes": "unavailable", "summaries": "partial"},
        )
        self.assertNotIn("data-feature", markup)
        self.assertNotIn('role="switch"', markup)
        self.assertIn("Frühere Baustein-Einstellungen", markup)
        self.assertIn("Datenstand dieser Veröffentlichung", markup)
        self.assertIn('href="sources.html#datenstand"', markup)

    def test_mp_pages_render_separate_roster_and_profile_provenance(self) -> None:
        markup = build_dip_pulse_site.render_abgeordnete_index(
            [],
            default_selection(),
            {
                "roster": {"acquisition_state": "not_requested"},
                "profiles": {"acquisition_state": "failed"},
            },
        )
        self.assertIn("Der vollständige Abgeordnetenkader wurde nicht abgerufen", markup)
        self.assertIn("Profilverknüpfungen konnten nicht abgerufen werden", markup)

    def test_manifest_preserves_cached_acquisition_times_and_fails_empty_requested_roster(self) -> None:
        previous_time = "2026-08-01T10:00:00Z"
        previous = {
            "domains": {
                "catalog": {"acquired_at": previous_time},
                "dossiers": {"acquired_at": previous_time},
                "roster": {"acquired_at": previous_time},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            cached = build_dip_pulse_site.build_publication_manifest(
                root=Path(tmp),
                protocols=[self._protocol("21/84", "5799", "2026-06-12")],
                entries=[],
                abg_mps=[{"is_mdb": True}],
                bill_count=0,
                enrichments=EnrichmentSelection(frozenset()),
                summary_mode="reuse",
                acquisition_attempted=False,
                development_output=False,
                previous_manifest=previous,
            )
            self.assertEqual(cached["domains"]["catalog"]["acquired_at"], previous_time)
            self.assertEqual(cached["domains"]["roster"]["acquired_at"], previous_time)

            failed = build_dip_pulse_site.build_publication_manifest(
                root=Path(tmp),
                protocols=[self._protocol("21/84", "5799", "2026-06-12")],
                entries=[],
                abg_mps=[],
                bill_count=0,
                enrichments=EnrichmentSelection(frozenset({"mp-roster"})),
                summary_mode="reuse",
                acquisition_attempted=True,
                development_output=False,
            )
            self.assertEqual(failed["domains"]["roster"]["acquisition_state"], "failed")
            self.assertEqual(failed["domains"]["roster"]["failure_reasons"], ["empty_required_dataset"])


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
    @staticmethod
    def _config_args(**overrides: Any) -> SimpleNamespace:
        values = {
            "enrich": [],
            "enable": [],
            "disable": [],
            "features": None,
            "features_file": None,
            "vote_scan_pages": None,
            "no_roster": False,
            "no_abgeordnetenwatch": False,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_enrichment_precedence_matrix(self) -> None:
        scenarios = (
            ("local replaces repository", {"repo": ["votes"], "local": ["aw-profiles"]}, {}, {"aw-profiles"}),
            ("explicit file replaces local", {"local": ["votes"], "explicit": ["mp-roster"]}, {}, {"mp-roster"}),
            (
                "canonical env follows legacy env",
                {},
                {"env": {"BUNDESTAG_PULSE_FEATURES": "votes", "BUNDESTAG_PULSE_ENRICHMENTS": "aw-profiles"}},
                {"votes", "aw-profiles"},
            ),
            ("canonical CLI supersedes legacy negative", {}, {"args": {"no_roster": True, "enrich": ["mp-roster"]}}, {"mp-roster"}),
            ("empty local replacement clears repository", {"repo": ["votes"], "local": []}, {}, set()),
            ("all and duplicates deduplicate", {}, {"args": {"enrich": ["all", "votes"]}}, {"votes", "aw-profiles", "mp-roster"}),
        )
        for label, files, inputs, expected in scenarios:
            with self.subTest(label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                if "repo" in files:
                    (root / "features.json").write_text(json.dumps({"enrich": files["repo"]}), encoding="utf-8")
                if "local" in files:
                    (root / "features.local.json").write_text(json.dumps({"enrich": files["local"]}), encoding="utf-8")
                args_values = dict(inputs.get("args") or {})
                if "explicit" in files:
                    explicit = root / "operator.json"
                    explicit.write_text(json.dumps({"enrich": files["explicit"]}), encoding="utf-8")
                    args_values["features_file"] = explicit
                with mock.patch.dict("os.environ", inputs.get("env") or {}, clear=True):
                    selection = build_dip_pulse_site.resolve_from_args(
                        self._config_args(**args_values), root=root
                    )
                self.assertEqual(set(selection), expected)
                self.assertTrue(selection.provenance or not files and not inputs)

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
            "invalid-enrichment",
        ):
            build_dip_pulse_site.resolve_from_args(args, root=Path(tmp))

    def test_capability_commands_exit_before_network_access(self) -> None:
        stdout = io.StringIO()
        with mock.patch("sys.argv", ["build_dip_pulse_site.py", "--list-capabilities"]), mock.patch(
            "build_dip_pulse_site.dip.load_local_env"
        ), mock.patch("build_dip_pulse_site.dip.ApiClient") as api_client, mock.patch(
            "sys.stdout", stdout
        ):
            self.assertEqual(build_dip_pulse_site.main(), 0)
        api_client.assert_not_called()
        self.assertIn("Feste öffentliche Bereiche", stdout.getvalue())
        self.assertIn("mp-roster", stdout.getvalue())

        stdout = io.StringIO()
        with mock.patch(
            "sys.argv",
            ["build_dip_pulse_site.py", "--enrich", "votes", "--explain-config"],
        ), mock.patch("build_dip_pulse_site.dip.load_local_env"), mock.patch(
            "build_dip_pulse_site.dip.ApiClient"
        ) as api_client, mock.patch("sys.stdout", stdout):
            self.assertEqual(build_dip_pulse_site.main(), 0)
        api_client.assert_not_called()
        self.assertIn("enrichment=votes", stdout.getvalue())
        self.assertIn("source=--enrich", stdout.getvalue())

    def test_developer_view_refuses_the_public_output_directory_before_writes(self) -> None:
        stderr = io.StringIO()
        with mock.patch(
            "sys.argv", ["build_dip_pulse_site.py", "--include-dev-view"]
        ), mock.patch("build_dip_pulse_site.dip.load_local_env"), mock.patch(
            "sys.stderr", stderr
        ):
            self.assertEqual(build_dip_pulse_site.main(), 2)
        self.assertIn("unsafe-dev-output", stderr.getvalue())



class SittingWeekComparisonTests(unittest.TestCase):
    """The Wochenvergleich band on puls.html, and the aggregation behind it."""

    def setUp(self) -> None:
        # puls.html logs its week to stderr on every render; keep the test output clean.
        patcher = mock.patch.object(sys, "stderr", new_callable=io.StringIO)
        patcher.start()
        self.addCleanup(patcher.stop)

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

    # -- Debattenprofil glossary ------------------------------------------

    def test_type_mix_links_known_types_to_the_glossary(self) -> None:
        # Known vorgangstyp labels become links carrying the one-line explanation
        # as data-tip (the hover bubble); unknown labels stay plain spans.
        markup = pulse_html.render_type_mix(Counter({"Antrag": 3, "Nie gesehen": 1}), None)

        self.assertIn('<a class="week-label" href="sources.html#vorgangstyp-antrag" data-tip="', markup)
        self.assertIn('data-tip="Aufforderung einer Fraktion', markup)
        self.assertIn('<span class="week-label">Nie gesehen</span>', markup)
        self.assertEqual(markup.count("data-tip="), 1)
        self.assertNotIn("title=", markup)

    def test_type_mix_glossary_href_follows_page_depth(self) -> None:
        markup = pulse_html.render_type_mix(Counter({"Antrag": 1}), None, glossary_href="../sources.html")
        self.assertIn('href="../sources.html#vorgangstyp-antrag"', markup)

    def test_debattenprofil_links_to_the_glossary_and_entries(self) -> None:
        positions = [{"vorgangstyp": "Antrag"}, {"vorgangstyp": "Gesetzgebung"}]
        entries = [
            self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100)], positions)]),
            self._entry("2026-05-22", "21/81", [self._item(1, [("SPD", 100)], positions[:1])]),
        ]
        markup = self._render(entries)

        self.assertIn('href="sources.html#vorgangstypen"', markup)
        self.assertIn('href="sources.html#vorgangstyp-antrag"', markup)
        self.assertIn('href="sources.html#vorgangstyp-gesetzgebung"', markup)
        self.assertIn("a.week-label[data-tip]::after", markup)

    def test_glossary_entries_are_complete_and_anchor_safe(self) -> None:
        slugs = [entry["slug"] for entry in pulse_html.VORGANGSTYP_GLOSSARY.values()]
        self.assertEqual(len(slugs), len(set(slugs)), "glossary slugs must be unique")
        for kind, entry in pulse_html.VORGANGSTYP_GLOSSARY.items():
            self.assertRegex(entry["slug"], r"^[a-z0-9-]+$", msg=kind)
            self.assertTrue(entry["kurz"].strip(), msg=kind)
            self.assertTrue(entry["lang"].strip(), msg=kind)
            self.assertLessEqual(len(entry["kurz"]), 200, msg=f"{kind}: bubble text too long")
        self.assertIsNone(pulse_html.vorgangstyp_anchor("Nie gesehen"))

    def test_sources_page_has_a_glossary_entry_per_vorgangstyp(self) -> None:
        markup = build_dip_pulse_site.render_sources_page([], features=default_selection())

        self.assertIn('id="vorgangstypen"', markup)
        self.assertIn("Vorgangstypen im Debattenprofil", markup)
        for kind, entry in pulse_html.VORGANGSTYP_GLOSSARY.items():
            self.assertIn(f'<li id="vorgangstyp-{entry["slug"]}"><strong>{pulse_html.esc(kind)}</strong>', markup)
        self.assertIn(".method-list li:target", markup)


class WeekRadarDataTests(unittest.TestCase):
    """Occurrence index, returning card on the index, week_stats extensions (build order §3-4)."""

    # Reuse the sitting/item builders without re-running the parent's tests.
    _item = SittingWeekComparisonTests._item
    _entry = SittingWeekComparisonTests._entry

    @staticmethod
    def _pos(vorgang_id: str, titel: str, typ: str = "Antrag", stage: str = "Beratung", twins=()):
        return {
            "vorgang_id": vorgang_id,
            "titel": titel,
            "vorgangstyp": typ,
            "vorgangsposition": stage,
            "mitberaten": [
                {"id": tid, "titel": tt, "vorgangstyp": ttyp, "vorgangsposition": tstage}
                for tid, tt, ttyp, tstage in twins
            ],
        }

    def test_occurrence_index_keeps_twins_and_week_order(self) -> None:
        older = self._entry("2026-05-20", "21/70", [
            self._item(1, [("SPD", 100)], [self._pos("B", "Gesetz B", "Gesetzgebung", "1. Beratung")]),
        ])
        current = self._entry("2026-06-10", "21/82", [
            self._item(1, [("SPD", 100)], [self._pos("A", "Antrag A", twins=[("B", "Gesetz B", "Gesetzgebung", "2. Beratung")])]),
        ])
        weeks = pulse_html.group_entries_by_week([older, current])
        index = pulse_html.vorgang_occurrences(weeks, (2026, 24))
        self.assertEqual([o["week"] for o in index["B"]], [(2026, 21), (2026, 24)])
        self.assertEqual([o["twin"] for o in index["B"]], [False, True])
        self.assertEqual(index["B"][1]["vorgangsposition"], "2. Beratung")
        self.assertEqual([o["week"] for o in index["A"]], [(2026, 24)])

    def test_returning_card_ignores_twin_only_appearances_and_accepts_a_prebuilt_index(self) -> None:
        # B appears as a position only in the older week; in the current week it is
        # only a twin of A, so the card (positions in two weeks) must not list it.
        older = self._entry("2026-05-20", "21/70", [
            self._item(1, [("SPD", 100)], [self._pos("B", "Gesetz B", "Gesetzgebung", "1. Beratung")]),
        ])
        current = self._entry("2026-06-10", "21/82", [
            self._item(1, [("SPD", 100)], [self._pos("A", "Antrag A", twins=[("B", "Gesetz B", "Gesetzgebung", "2. Beratung")])]),
        ])
        weeks = pulse_html.group_entries_by_week([older, current])
        index = pulse_html.vorgang_occurrences(weeks, (2026, 24))
        self.assertEqual(pulse_html.returning_vorgaenge(weeks, (2026, 24)), [])
        self.assertEqual(pulse_html.returning_vorgaenge(weeks, (2026, 24), index), [])
        # With B as a position in both weeks, the card lists it whichever way it is built.
        current_pos = self._entry("2026-06-10", "21/82", [
            self._item(1, [("SPD", 100)], [self._pos("B", "Gesetz B", "Gesetzgebung", "2. Beratung")]),
        ])
        weeks = pulse_html.group_entries_by_week([older, current_pos])
        direct = pulse_html.returning_vorgaenge(weeks, (2026, 24))
        via_index = pulse_html.returning_vorgaenge(weeks, (2026, 24), pulse_html.vorgang_occurrences(weeks, (2026, 24)))
        self.assertEqual([r["vorgang_id"] for r in direct], ["B"])
        self.assertEqual(direct, via_index)

    def test_week_stats_counts_distinct_votes_not_attachments(self) -> None:
        vote = {"id": "v1", "title": "Namentlich", "date": "2026-06-10"}
        entry = self._entry("2026-06-10", "21/82", [
            dict(self._item(1, [("SPD", 100)]), votes=[vote]),
            dict(self._item(2, [("SPD", 100)]), votes=[vote, {"id": "v2", "title": "Zweite", "date": "2026-06-10"}]),
            dict(self._item(3, [("SPD", 100)]), vote={"title": "Legacy", "date": "2026-06-10"}),
        ])
        stats = pulse_html.week_stats((2026, 24), [entry])
        self.assertEqual(stats["vote_count"], 3)  # v1 once, v2, legacy
        self.assertEqual(stats["vote_top_count"], 3)
        self.assertEqual(stats["vote_sittings"], [("21/82", Path("plenarprotokoll-21-82.html"), 1, 3)])

    def test_week_stats_has_no_vote_sittings_without_votes(self) -> None:
        stats = pulse_html.week_stats((2026, 24), [self._entry("2026-06-10", "21/82", [self._item(1, [("SPD", 100)])])])
        self.assertEqual((stats["vote_count"], stats["vote_top_count"], stats["vote_sittings"]), (0, 0, []))

    def test_week_stats_coverage_flags(self) -> None:
        complete = self._entry("2026-06-10", "21/82", [self._item(1, [("SPD", 100), ("CDU/CSU", 100)])])
        self.assertTrue(pulse_html.week_stats((2026, 24), [complete])["speakers_complete"])
        self.assertTrue(pulse_html.week_stats((2026, 24), [complete])["chars_complete"])

        truncated_item = self._item(1, [("SPD", 100)] * 5)
        truncated_item["xml_speech_count"] = 40
        truncated_item["xml_speakers_first"] = truncated_item.pop("xml_speakers")
        truncated = self._entry("2026-06-11", "21/83", [truncated_item])
        stats = pulse_html.week_stats((2026, 24), [truncated])
        self.assertEqual(stats["speech_count"], 40)
        self.assertFalse(stats["speakers_complete"])
        self.assertFalse(stats["chars_complete"])

        bare_item = {"index": 1, "top_id": "TOP 1", "heading": "x", "xml_speech_count": 12, "api": {"positions": []}}
        stats = pulse_html.week_stats((2026, 24), [self._entry("2026-06-12", "21/84", [bare_item])])
        self.assertEqual(stats["speech_count"], 12)
        self.assertFalse(stats["speakers_complete"])
        self.assertFalse(stats["chars_complete"])  # speeches without any speaker array are incomplete text


class WeekTopicRowsTests(unittest.TestCase):
    """week_topic_rows / topic_row on a three-sitting week (build order §6)."""

    _item = SittingWeekComparisonTests._item
    _entry = SittingWeekComparisonTests._entry
    _pos = staticmethod(WeekRadarDataTests._pos)

    @staticmethod
    def _href(entry) -> str:
        return f"protocols/{entry['page_path'].name}"

    def _week(self):
        """Wed/Thu/Fri sittings: a Befragung (most speeches), a bill, a 4-Antrag group, ties."""
        wed = self._entry("2026-06-10", "21/82", [
            dict(self._item(1, [("Regierung", 50)] * 2 + [("SPD", 50)] * 4), heading="Befragung der Bundesregierung"),
            self._item(2, [("SPD", 100)] * 3, [self._pos("K1", "KI-Antrag")]),
            self._item(3, [("CDU/CSU", 100)] * 3, [self._pos("W1", "Wohngeld retten")]),
        ])
        thu = self._entry("2026-06-11", "21/83", [
            self._item(1, [("CDU/CSU", 100)] * 5 + [("AfD", 100)] * 2,
                       [self._pos("G1", "Gesetz zur Sache", "Gesetzgebung", "1. Beratung")]),
            self._item(2, [("SPD", 100)] * 4, [
                self._pos("A1", "Bildung bezahlbar machen", twins=[("A2", "Zukunftsinvestitionen", "Antrag", "Beratung")]),
                self._pos("A2", "Zukunftsinvestitionen", twins=[("A1", "Bildung bezahlbar machen", "Antrag", "Beratung")]),
            ]),
            self._item(3, [("SPD", 100)], [self._pos("Z1", "Zwerg")]),
            dict(self._item(4, []), xml_speech_count=0),
        ])
        fri = self._entry("2026-06-12", "21/84", [
            self._item(1, [("AfD", 100)] * 3, [self._pos("F1", "Freitag drei")]),
            self._item(2, [("Die Linke", 100)] * 2, [self._pos("F2", "Freitag zwei")]),
        ])
        return [wed, thu, fri]

    def _radar(self, entries, older=(), **kwargs):
        weeks = pulse_html.group_entries_by_week(list(older) + list(entries))
        stats = pulse_html.week_stats((2026, 24), weeks[(2026, 24)])
        index = pulse_html.vorgang_occurrences(weeks, (2026, 24))
        radar = pulse_html.week_topic_rows(weeks[(2026, 24)], index, total=stats["speech_count"], dossier_href_for=self._href, **kwargs)
        return radar, stats

    def test_rows_rank_across_sittings_with_formats_in_the_denominator(self) -> None:
        radar, stats = self._radar(self._week())
        self.assertEqual(stats["speech_count"], 29)
        rows = radar["rows"]
        self.assertEqual([r["speech_count"] for r in rows], [7, 4, 3, 3, 3])
        self.assertEqual(rows[0]["identity"]["lead_title"], "Gesetz zur Sache")
        self.assertEqual(rows[0]["dossier_href"], "protocols/plenarprotokoll-21-83.html")
        self.assertAlmostEqual(rows[0]["share"], 7 / 29 * 100)
        # Ties at 3: newest sitting first (Fri), then Wed by agenda order.
        self.assertEqual([(r["dokumentnummer"], r["index"]) for r in rows[2:]], [("21/84", 1), ("21/82", 2), ("21/82", 3)])
        befragung = radar["formats"][0]
        self.assertEqual(
            (befragung["heading"], befragung["speech_count"], befragung["href"], befragung["datum"], befragung["index"]),
            ("Befragung der Bundesregierung", 6, "protocols/plenarprotokoll-21-82.html#top-1", "2026-06-10", 1),
        )
        self.assertAlmostEqual(befragung["share"], 6 / 29 * 100)
        self.assertEqual(radar["remaining"], [("21/83", Path("plenarprotokoll-21-83.html"), 1), ("21/84", Path("plenarprotokoll-21-84.html"), 1)])

    def test_tied_rows_at_the_cutoff_are_included_up_to_the_cap(self) -> None:
        entries = [self._entry("2026-06-10", "21/82", [
            self._item(i, [("SPD", 100)] * (10 if i == 1 else 2), [self._pos(f"P{i}", f"Titel {i}")]) for i in range(1, 8)
        ])]
        radar, _ = self._radar(entries)
        self.assertEqual(len(radar["rows"]), 7)  # 1 + 6 tied at 2, within the cap of 8
        self.assertEqual(radar["remaining"], [])

    def test_a_tied_group_that_overflows_the_cap_is_cut_back_to_the_last_full_rank(self) -> None:
        entries = [self._entry("2026-06-10", "21/82", [
            self._item(i, [("SPD", 100)] * (10 if i == 1 else 2), [self._pos(f"P{i}", f"Titel {i}")]) for i in range(1, 11)
        ])]
        radar, _ = self._radar(entries)
        self.assertEqual([r["index"] for r in radar["rows"]], [1])
        self.assertEqual(radar["remaining"], [("21/82", Path("plenarprotokoll-21-82.html"), 9)])

    def test_without_any_full_rank_the_first_rank_limit_rows_are_shown(self) -> None:
        entries = [self._entry("2026-06-10", "21/82", [
            self._item(i, [("SPD", 100)] * 2, [self._pos(f"P{i}", f"Titel {i}")]) for i in range(1, 11)
        ])]
        radar, _ = self._radar(entries)
        self.assertEqual([r["index"] for r in radar["rows"]], [1, 2, 3, 4, 5])
        self.assertEqual(radar["remaining"][0][2], 5)

    def test_trace_uses_the_occurrence_index_over_positions_and_twins(self) -> None:
        older = [self._entry("2026-05-20", "21/70", [
            self._item(1, [("SPD", 100)], [self._pos("B", "Gesetz B", "Gesetzgebung", "1. Beratung")]),
            self._item(2, [("SPD", 100)], [self._pos("L", "Lead-Antrag")]),
        ])]
        current = [self._entry("2026-06-10", "21/82", [
            # asymmetric twins: B is only a twin here, but was a position in KW 21 -> trace
            self._item(1, [("SPD", 100)] * 5, [self._pos("A", "Antrag A", twins=[("B", "Gesetz B", "Gesetzgebung", "2. Beratung")])]),
            # mitberaten-only with no earlier position anywhere -> no trace
            self._item(2, [("SPD", 100)] * 4, [self._pos("C", "Antrag C", twins=[("D", "Antrag D", "Antrag", "Beratung")])]),
            # lead id preferred: both L and M returned? only L did; the lead (Gesetzgebung M) has no history
            self._item(3, [("SPD", 100)] * 3, [self._pos("M", "Gesetz M", "Gesetzgebung", "1. Beratung"), self._pos("L", "Lead-Antrag")]),
            # no ids at all -> no trace
            self._item(4, [("SPD", 100)] * 2, []),
        ])]
        radar, _ = self._radar(current, older=older)
        by_index = {row["index"]: row for row in radar["rows"]}
        self.assertEqual(by_index[1]["trace"]["vorgang_id"], "B")
        self.assertEqual(by_index[1]["trace"]["first"]["label"], "KW 21/2026")
        self.assertEqual(by_index[1]["trace"]["first"]["vorgangsposition"], "1. Beratung")
        self.assertEqual(by_index[1]["trace"]["current_position"], "2. Beratung")
        self.assertIsNone(by_index[2]["trace"])
        self.assertEqual(by_index[3]["trace"]["vorgang_id"], "L")  # lead M has no history, so L
        self.assertIsNone(by_index[4]["trace"])

    def test_one_procedure_in_two_current_tops_traces_each_to_the_earlier_week(self) -> None:
        older = [self._entry("2026-05-20", "21/70", [self._item(1, [("SPD", 100)], [self._pos("B", "Gesetz B", "Gesetzgebung", "1. Beratung")])])]
        current = [self._entry("2026-06-10", "21/82", [
            self._item(1, [("SPD", 100)] * 3, [self._pos("B", "Gesetz B", "Gesetzgebung", "2. Beratung")]),
            self._item(2, [("SPD", 100)] * 2, [self._pos("B", "Gesetz B", "Gesetzgebung", "3. Beratung")]),
        ])]
        radar, _ = self._radar(current, older=older)
        self.assertEqual(len(radar["rows"]), 2)
        for row in radar["rows"]:
            self.assertEqual(row["trace"]["first"]["label"], "KW 21/2026")

    def test_row_carries_coverage_summary_and_vote_flags(self) -> None:
        item = self._item(1, [("SPD", 100)] * 5, [self._pos("A", "Antrag A")])
        item["xml_speech_count"] = 40
        item["xml_speakers_first"] = item.pop("xml_speakers")
        item["llm_summary"] = {"text": "Text", "source_chunks": [{"id": "C1"}]}
        item["votes"] = [{"id": "v1"}]
        no_chunks = self._item(2, [("SPD", 100)] * 2, [self._pos("B", "Antrag B")])
        no_chunks["llm_summary"] = {"text": "Text ohne Belege"}
        radar, _ = self._radar([self._entry("2026-06-10", "21/82", [item, no_chunks])])
        row, other = radar["rows"]
        self.assertFalse(row["speakers_complete"])
        self.assertEqual(row["party_total"], 5)
        self.assertEqual(row["speech_count"], 40)
        self.assertEqual(row["summary"]["text"], "Text")
        self.assertTrue(row["has_votes"])
        self.assertTrue(other["speakers_complete"])
        self.assertIsNone(other["summary"])
        self.assertFalse(other["has_votes"])

    def test_zero_speech_week_yields_nothing(self) -> None:
        radar, stats = self._radar([self._entry("2026-06-10", "21/82", [dict(self._item(1, []), xml_speech_count=0)])])
        self.assertEqual(stats["speech_count"], 0)
        self.assertEqual(radar, {"rows": [], "formats": [], "remaining": []})

    def test_occurrence_index_dedups_within_a_top_and_stops_at_the_current_week(self) -> None:
        # B is a position and its own twin inside one TOP (real DIP shape): one record, as position.
        current = self._entry("2026-06-10", "21/82", [
            self._item(1, [("SPD", 100)], [
                self._pos("B", "Gesetz B", "Gesetzgebung", "2. Beratung", twins=[("B", "Gesetz B", "Gesetzgebung", "2. Beratung")]),
                self._pos("", "Ohne Id"),
            ]),
            self._item(2, [("SPD", 100)], [self._pos("B", "Gesetz B", "Gesetzgebung", "2. Beratung")]),
        ])
        later = self._entry("2026-06-17", "21/85", [self._item(1, [("SPD", 100)], [self._pos("B", "Gesetz B", "Gesetzgebung", "3. Beratung")])])
        weeks = pulse_html.group_entries_by_week([current, later])
        index = pulse_html.vorgang_occurrences(weeks, (2026, 24))
        self.assertEqual(sorted(index), ["B"])
        self.assertEqual([(o["index"], o["twin"]) for o in index["B"]], [(1, False), (2, False)])
        self.assertNotIn((2026, 25), {o["week"] for o in index["B"]})
        # The current week is included when asked for a later one, in week order.
        self.assertEqual([o["week"] for o in pulse_html.vorgang_occurrences(weeks, (2026, 25))["B"]], [(2026, 24), (2026, 24), (2026, 25)])

    def test_undated_sittings_in_topic_row_and_in_the_tie_sort(self) -> None:
        older = self._entry("2026-05-20", "21/70", [self._item(1, [("SPD", 100)], [self._pos("B", "Gesetz B", "Gesetzgebung", "1. Beratung")])])
        weeks = pulse_html.group_entries_by_week([older])
        index = pulse_html.vorgang_occurrences(weeks, (2026, 24))
        item = dict(self._item(3, [("SPD", 100)] * 2, [self._pos("B", "Gesetz B", "Gesetzgebung", "2. Beratung")]), vote={"title": "Legacy"})
        undated = self._entry("", "21/99", [item])
        row = pulse_html.topic_row(item, undated, total=10, occurrences=index, dossier_href="protocols/x.html")
        # No week of its own: the sitting cannot be placed in time, so no trace
        # is claimed even though the Vorgang is indexed for KW 21.
        self.assertIsNone(row["trace"])
        self.assertTrue(row["has_votes"])
        self.assertEqual(row["datum"], "")  # passed through raw; the sort treats it as date.min
        self.assertEqual((row["speech_count"], row["share"]), (2, 20.0))
        self.assertEqual(row["dossier_href"], "protocols/x.html")
        # A sitting in the same week as the only appearance has nothing earlier to trace.
        same_week = self._entry("2026-05-22", "21/71", [item])
        row = pulse_html.topic_row(item, same_week, total=10, occurrences=index, dossier_href="protocols/y.html")
        self.assertIsNone(row["trace"])
        # In the ranking, an undated sitting sorts after a dated one within a tie.
        dated = self._entry("2026-06-10", "21/82", [self._item(1, [("SPD", 100)] * 2, [self._pos("P1", "Datiert")])])
        undated = self._entry("", "21/99", [self._item(1, [("SPD", 100)] * 2, [self._pos("P2", "Undatiert")])])
        index = pulse_html.vorgang_occurrences(pulse_html.group_entries_by_week([dated]), (2026, 24))
        radar = pulse_html.week_topic_rows([undated, dated], index, total=4, dossier_href_for=self._href)
        self.assertEqual([r["dokumentnummer"] for r in radar["rows"]], ["21/82", "21/99"])
        self.assertEqual(radar["remaining"], [])

    def test_remaining_keeps_unnumbered_sittings_apart(self) -> None:
        # Two sittings without a dokumentnummer must not merge into one "Weitere" bucket;
        # the sitting is told apart by its page and labelled by the page stem.
        def sitting(page: str, indexes: list[int]) -> dict:
            entry = self._entry("2026-06-10", "", [self._item(i, [("SPD", 100)] * 2, [self._pos(f"P{page}{i}", f"Thema {i}")]) for i in indexes])
            entry["page_path"] = Path(page)
            return entry
        first = sitting("plenarprotokoll-21-98.html", [1, 2, 3])
        second = sitting("plenarprotokoll-21-99.html", [1, 2])
        index = pulse_html.vorgang_occurrences(pulse_html.group_entries_by_week([first, second]), (2026, 24))
        radar = pulse_html.week_topic_rows([first, second], index, total=10, dossier_href_for=self._href, rank_limit=1, hard_cap=1)
        self.assertEqual(len(radar["rows"]), 1)
        self.assertEqual(radar["rows"][0]["page_path"], Path("plenarprotokoll-21-98.html"))
        self.assertEqual(
            radar["remaining"],
            [("plenarprotokoll-21-98", Path("plenarprotokoll-21-98.html"), 2), ("plenarprotokoll-21-99", Path("plenarprotokoll-21-99.html"), 2)],
        )


class WeekStatsVoteSittingTests(unittest.TestCase):
    """week_stats vote bookkeeping over several sittings of one week."""

    _item = SittingWeekComparisonTests._item
    _entry = SittingWeekComparisonTests._entry

    def test_vote_sittings_follow_sitting_order_and_ids_dedup_across_the_week(self) -> None:
        shared = {"id": "v-shared", "title": "Geteilt", "date": "2026-06-10"}
        wed = self._entry("2026-06-10", "21/82", [
            self._item(1, [("SPD", 100)]),
            dict(self._item(3, [("SPD", 100)]), votes=[shared, {"id": "v-wed"}]),
            dict(self._item(4, [("SPD", 100)]), votes=[shared]),
        ])
        thu = self._entry("2026-06-11", "21/83", [
            dict(self._item(1, [("SPD", 100)]), vote={"title": "Legacy", "date": "2026-06-11"}),
            dict(self._item(2, [("SPD", 100)]), votes=[shared]),
        ])
        fri = self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100)])])
        stats = pulse_html.week_stats((2026, 24), [wed, thu, fri])
        self.assertEqual(stats["vote_count"], 3)  # v-shared, v-wed, Legacy|2026-06-11
        self.assertEqual(stats["vote_top_count"], 4)
        self.assertEqual(
            stats["vote_sittings"],
            [
                ("21/82", Path("plenarprotokoll-21-82.html"), 3, 2),
                ("21/83", Path("plenarprotokoll-21-83.html"), 1, 2),
            ],
        )
        # A sitting without a dokumentnummer is labelled by its page stem.
        unnumbered = self._entry("2026-06-12", "", [dict(self._item(2, [("SPD", 100)]), votes=[{"id": "v-fri"}])])
        unnumbered["page_path"] = Path("plenarprotokoll-21-99.html")
        stats = pulse_html.week_stats((2026, 24), [unnumbered])
        self.assertEqual(stats["vote_sittings"], [("plenarprotokoll-21-99", Path("plenarprotokoll-21-99.html"), 2, 1)])
        self.assertEqual(pulse_html._vote_key({"title": "Legacy", "date": "2026-06-11"}), "Legacy|2026-06-11")
        self.assertEqual(pulse_html._vote_key({}), "|")
        self.assertEqual(pulse_html._vote_key({"id": 42, "title": "x"}), "42")


class BuildClockAndWeekTests(unittest.TestCase):
    """--today / --week / SOURCE_DATE_EPOCH threading for puls.html (build order §7)."""

    def setUp(self) -> None:
        # puls.html logs its week to stderr on every render; keep the test output clean.
        patcher = mock.patch.object(sys, "stderr", new_callable=io.StringIO)
        patcher.start()
        self.addCleanup(patcher.stop)

    _item = SittingWeekComparisonTests._item
    _entry = SittingWeekComparisonTests._entry

    def test_resolve_today_prefers_explicit_then_epoch_then_clock(self) -> None:
        self.assertEqual(build_dip_pulse_site.resolve_today(date(2026, 9, 15)), date(2026, 9, 15))
        self.assertEqual(build_dip_pulse_site.resolve_today(datetime(2026, 9, 15, 23, 59)), date(2026, 9, 15))
        # 2026-09-13T22:30Z is still Sunday in UTC even though it is Monday in CEST.
        self.assertEqual(build_dip_pulse_site.resolve_today(None, environ={"SOURCE_DATE_EPOCH": "1789338600"}), date(2026, 9, 13))
        self.assertEqual(build_dip_pulse_site.resolve_today(None, environ={}), date.today())
        with self.assertRaises(ValueError):
            build_dip_pulse_site.resolve_today(None, environ={"SOURCE_DATE_EPOCH": "gestern"})

    def test_today_converter_accepts_only_the_dashed_form(self) -> None:
        self.assertEqual(build_dip_pulse_site.parse_iso_date_arg(" 2026-06-15 "), date(2026, 6, 15))
        for bad in ("20260615", "2026-W25-1", "2026-6-15", "15.06.2026", ""):
            with self.assertRaises(argparse.ArgumentTypeError):
                build_dip_pulse_site.parse_iso_date_arg(bad)

    def test_argparse_converters_reject_bad_values_with_a_readable_error(self) -> None:
        self.assertEqual(build_dip_pulse_site.parse_iso_date_arg("2026-09-15"), date(2026, 9, 15))
        self.assertEqual(build_dip_pulse_site.parse_iso_week_arg("2026-24"), (2026, 24))
        self.assertEqual(build_dip_pulse_site.parse_iso_week_arg("2026-W05"), (2026, 5))
        for bad in ("15.09.2026", "2026-13-01"):
            with self.assertRaises(argparse.ArgumentTypeError):
                build_dip_pulse_site.parse_iso_date_arg(bad)
        for bad in ("2026-99", "24", "2026/24"):
            with self.assertRaises(argparse.ArgumentTypeError):
                build_dip_pulse_site.parse_iso_week_arg(bad)

    def test_select_pulse_week_defaults_to_newest_and_fails_fast_on_an_unknown_week(self) -> None:
        entries = [
            self._entry("2026-05-20", "21/70", [self._item(1, [("SPD", 100)])]),
            self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100)])]),
            self._entry("", "21/85", [self._item(1, [("SPD", 100)])]),
        ]
        selected, weeks = build_dip_pulse_site.select_pulse_week(entries)
        self.assertEqual(selected, (2026, 24))
        self.assertEqual(sorted(weeks), [(2026, 21), (2026, 24)])
        self.assertEqual(build_dip_pulse_site.select_pulse_week(entries, (2026, 21))[0], (2026, 21))
        with self.assertRaises(ValueError) as caught:
            build_dip_pulse_site.select_pulse_week(entries, (2026, 30))
        self.assertIn("2026-21, 2026-24", str(caught.exception))
        self.assertEqual(build_dip_pulse_site.select_pulse_week([])[0], None)

    def test_render_front_page_accepts_the_clock_and_week_keywords(self) -> None:
        entries = [self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100)])])]
        for entry in entries:
            entry["report"]["validation_summary"] = {"xml_top_count": 1, "xml_speech_count": 1}
        markup = build_dip_pulse_site.render_front_page(entries, database_href=None, today=date(2026, 9, 15), week=(2026, 24))
        self.assertIn("Bundestag-Puls", markup)
        with self.assertRaises(ValueError):
            build_dip_pulse_site.render_front_page(entries, database_href=None, week=(2025, 1))

    def test_cli_parses_the_new_flags(self) -> None:
        with mock.patch.object(sys, "argv", ["build", "--offline", "--today", "2026-09-15", "--week", "2026-24"]):
            args = build_dip_pulse_site.parse_args()
        self.assertEqual(args.today, date(2026, 9, 15))
        self.assertEqual(args.week, (2026, 24))
        with mock.patch.object(sys, "argv", ["build", "--offline"]):
            args = build_dip_pulse_site.parse_args()
        self.assertIsNone(args.today)
        self.assertIsNone(args.week)

    def test_offline_main_refuses_an_unknown_week_before_rendering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            entry = self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100)])])
            args = SimpleNamespace(output_dir=output_dir, database_path=None, offline=True, no_persist=True, week=(2030, 1), today=None)
            with (
                mock.patch.object(build_dip_pulse_site, "parse_args", return_value=args),
                mock.patch.object(build_dip_pulse_site, "load_cached_protocols", return_value=[{"id": "cached", "datum": "2026-06-12"}]),
                mock.patch.object(build_dip_pulse_site, "load_existing_detail_entries", return_value=[entry]),
                mock.patch.object(build_dip_pulse_site, "rebuild_cached_detail_pages", return_value=[entry]) as rebuild,
                mock.patch.object(build_dip_pulse_site, "render_site") as render_site,
                mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr,
            ):
                code = build_dip_pulse_site.main()
            self.assertEqual(code, 2)
            rebuild.assert_not_called()  # nothing written before the week check
            render_site.assert_not_called()
            self.assertIn("2026-24", stderr.getvalue())

    # -- PR1 invariant: the clock and week are threaded, not yet rendered ------

    def test_puls_page_is_reproducible_for_the_same_clock_and_week(self) -> None:
        # The page reads the clock and the week now, so two renders agree byte
        # for byte only when both are pinned the same way: --today and an
        # equivalent SOURCE_DATE_EPOCH are interchangeable, and a different
        # clock or week changes the header.
        older = self._entry("2026-05-20", "21/70", [self._item(1, [("SPD", 100), ("CDU/CSU", 100)])])
        newest = self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100)] * 3), self._item(2, [("AfD", 100)])])
        entries = [newest, older]
        pinned = build_dip_pulse_site.render_front_page(entries, database_href=None, today=date(2026, 9, 15), week=(2026, 24))
        again = build_dip_pulse_site.render_front_page(entries, database_href=None, today=datetime(2026, 9, 15, 23, 59), week=(2026, 24))
        self.assertEqual(pinned, again)
        self.assertIn("Wochenvergleich", pinned)
        # 1789453800 is 2026-09-15 06:30 UTC.
        with mock.patch.dict(os.environ, {"SOURCE_DATE_EPOCH": "1789453800"}):
            via_epoch = build_dip_pulse_site.render_front_page(entries, database_href=None, week=(2026, 24))
        self.assertEqual(pinned, via_epoch)
        other_day = build_dip_pulse_site.render_front_page(entries, database_href=None, today=date(2026, 6, 16), week=(2026, 24))
        other_week = build_dip_pulse_site.render_front_page(entries, database_href=None, today=date(2026, 9, 15), week=(2026, 21))
        self.assertNotEqual(pinned, other_day)
        self.assertIn("Stand: 1 Sitzung", other_day)
        self.assertIn("KW 21/2026 verhandelt hat", other_week)

    def test_render_front_page_fails_on_a_bad_epoch_and_on_an_unknown_week_even_for_an_empty_archive(self) -> None:
        with mock.patch.dict(os.environ, {"SOURCE_DATE_EPOCH": "gestern"}):
            with self.assertRaises(ValueError) as caught:
                build_dip_pulse_site.render_front_page([], database_href=None)
        self.assertIn("SOURCE_DATE_EPOCH", str(caught.exception))
        with mock.patch.dict(os.environ, {}, clear=True):
            empty = build_dip_pulse_site.render_front_page([], database_href=None)
        self.assertIn("Es wurden noch keine Sitzungen erzeugt.", empty)
        with self.assertRaises(ValueError) as caught:
            build_dip_pulse_site.render_front_page([], database_href=None, week=(2026, 1))
        self.assertIn("vorhanden: keine", str(caught.exception))

    def test_resolve_today_edge_cases_for_the_epoch_convention(self) -> None:
        self.assertEqual(build_dip_pulse_site.resolve_today(None, environ={"SOURCE_DATE_EPOCH": ""}), date.today())
        self.assertEqual(build_dip_pulse_site.resolve_today(None, environ={"SOURCE_DATE_EPOCH": "0"}), date(1970, 1, 1))
        for bad in ("99999999999999999999", "1.5", "-"):
            with self.assertRaises(ValueError) as caught:
                build_dip_pulse_site.resolve_today(None, environ={"SOURCE_DATE_EPOCH": bad})
            self.assertIn(repr(bad), str(caught.exception))
        # environ=None reads the process environment.
        with mock.patch.dict(os.environ, {"SOURCE_DATE_EPOCH": "1789338600"}):
            self.assertEqual(build_dip_pulse_site.resolve_today(), date(2026, 9, 13))
        # An explicit value wins over the environment without even reading it.
        with mock.patch.dict(os.environ, {"SOURCE_DATE_EPOCH": "gestern"}):
            self.assertEqual(build_dip_pulse_site.resolve_today(date(2026, 9, 15)), date(2026, 9, 15))

    def test_parse_iso_week_arg_knows_which_years_have_a_53rd_week(self) -> None:
        self.assertEqual(build_dip_pulse_site.parse_iso_week_arg("2020-53"), (2020, 53))
        self.assertEqual(build_dip_pulse_site.parse_iso_week_arg(" 2026-24 "), (2026, 24))
        self.assertEqual(build_dip_pulse_site.parse_iso_week_arg("2026-1"), (2026, 1))
        for bad in ("2021-53", "2026-00", "2026-W", "2026-W123", ""):
            with self.assertRaises(argparse.ArgumentTypeError):
                build_dip_pulse_site.parse_iso_week_arg(bad)

    def test_unknown_week_error_skips_undated_protocols_and_lists_what_exists(self) -> None:
        protocols = [
            {"dokumentnummer": "21/84", "datum": "2026-06-12"},
            {"dokumentnummer": "21/70", "datum": "2026-05-20"},
            {"dokumentnummer": "21/85"},
            {"dokumentnummer": "21/86", "datum": "12.06.2026"},
        ]
        self.assertIsNone(build_dip_pulse_site.unknown_week_error(None, protocols))
        self.assertIsNone(build_dip_pulse_site.unknown_week_error(None, []))
        self.assertIsNone(build_dip_pulse_site.unknown_week_error((2026, 21), protocols))
        self.assertEqual(
            build_dip_pulse_site.unknown_week_error((2026, 30), protocols),
            "--week 2026-30 ist nicht im Archiv; vorhanden: 2026-21, 2026-24",
        )
        self.assertEqual(
            build_dip_pulse_site.unknown_week_error((2026, 5), []),
            "--week 2026-05 ist nicht im Archiv; vorhanden: keine",
        )

    def test_render_site_threads_today_and_week_into_the_front_page(self) -> None:
        protocol = CurrentPulseOrderTests._protocol("21/84", "5799", "2026-06-12")
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = CurrentPulseOrderTests._output_dir(tmp)
            entries = [CurrentPulseOrderTests._entry(output_dir, protocol)]
            kwargs: dict[str, Any] = dict(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=[protocol],
                entries=entries,
                abg_mps=[],
                mp_lookup={},
            )
            with (
                mock.patch.object(build_dip_pulse_site, "render_front_page", return_value="<html></html>") as front,
                mock.patch.object(sys, "stderr", new_callable=io.StringIO),
            ):
                build_dip_pulse_site.render_site(**kwargs, today=date(2026, 9, 15), week=(2026, 24))
                self.assertEqual(front.call_args.kwargs["today"], date(2026, 9, 15))
                self.assertEqual(front.call_args.kwargs["week"], (2026, 24))
                build_dip_pulse_site.render_site(**kwargs)
                self.assertIsNone(front.call_args.kwargs["today"])
                self.assertIsNone(front.call_args.kwargs["week"])
            # Unmocked, an unknown week is the renderer's ValueError, so main() must pre-check.
            with mock.patch.object(sys, "stderr", new_callable=io.StringIO), self.assertRaises(ValueError):
                build_dip_pulse_site.render_site(**kwargs, week=(2030, 1))

    def test_offline_main_threads_a_known_week_and_the_clock_into_render_site(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            entry = self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100)])])
            args = SimpleNamespace(
                output_dir=output_dir, database_path=None, offline=True, no_persist=True, week=(2026, 24), today=date(2026, 9, 15)
            )
            with (
                mock.patch.dict(os.environ, {"SOURCE_DATE_EPOCH": "gestern"}),  # --today wins, the env is never read
                mock.patch.object(build_dip_pulse_site, "parse_args", return_value=args),
                mock.patch.object(build_dip_pulse_site, "load_cached_protocols", return_value=[{"id": "cached", "datum": "2026-06-12"}]),
                mock.patch.object(build_dip_pulse_site, "load_existing_detail_entries", return_value=[entry]),
                mock.patch.object(build_dip_pulse_site, "rebuild_cached_detail_pages", return_value=[entry]) as rebuild,
                mock.patch.object(build_dip_pulse_site, "render_site", return_value=output_dir / "index.html") as render_site,
                mock.patch.object(sys, "stderr", new_callable=io.StringIO),
                mock.patch.object(sys, "stdout", new_callable=io.StringIO),
            ):
                code = build_dip_pulse_site.main()
            self.assertEqual(code, 0)
            rebuild.assert_called_once()
            # The dossiers loaded for the --week check are handed on, not parsed twice.
            self.assertEqual(rebuild.call_args.kwargs["cached_entries"], [entry])
            self.assertEqual(render_site.call_args.kwargs["today"], date(2026, 9, 15))
            self.assertEqual(render_site.call_args.kwargs["week"], (2026, 24))
            self.assertIs(render_site.call_args.kwargs["entries"][0], entry)

    def _online_argv(self, output_dir: Path, *extra: str) -> list[str]:
        return ["build", "--api-key", "k", "--no-abgeordnetenwatch", "--no-persist", "--output-dir", str(output_dir), *extra]

    @staticmethod
    def _catalog_protocol(document_number: str, protocol_id: str, datum: str) -> dict[str, Any]:
        return {
            "id": protocol_id,
            "dokumentnummer": document_number,
            "datum": datum,
            "titel": f"Protokoll {document_number}",
            "fundstelle": {"xml_url": f"https://example.test/{protocol_id}.xml"},
        }

    def test_online_main_refuses_an_unknown_week_before_building_any_dossier(self) -> None:
        catalog = [self._catalog_protocol("21/84", "5799", "2026-06-12"), self._catalog_protocol("21/70", "5780", "2026-05-20")]
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "site"
            with (
                mock.patch.object(sys, "argv", self._online_argv(output_dir, "--week", "2030-01")),
                mock.patch.object(build_dip_pulse_site, "fetch_protocols", return_value=catalog),
                mock.patch.object(build_dip_pulse_site, "build_dossiers_with_progress") as build_dossiers,
                mock.patch.object(build_dip_pulse_site, "render_site") as render_site,
                mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr,
            ):
                code = build_dip_pulse_site.main()
            self.assertEqual(code, 2)
            self.assertIn("--week 2030-01 ist nicht im Archiv; vorhanden: 2026-21, 2026-24", stderr.getvalue())
            build_dossiers.assert_not_called()
            render_site.assert_not_called()
            # Only the empty output directories exist; not a single file was written.
            self.assertEqual([p for p in output_dir.rglob("*") if p.is_file()], [])

    def test_online_main_threads_a_known_week_and_the_clock_into_render_site(self) -> None:
        protocol = self._catalog_protocol("21/84", "5799", "2026-06-12")
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "site"
            entry = self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100)])])
            entry["report"]["protocol"]["id"] = "5799"
            with (
                mock.patch.object(sys, "argv", self._online_argv(output_dir, "--week", "2026-24", "--today", "2026-09-15")),
                mock.patch.object(build_dip_pulse_site, "fetch_protocols", return_value=[protocol]),
                mock.patch.object(build_dip_pulse_site, "build_dossiers_with_progress", return_value=[entry]) as build_dossiers,
                mock.patch.object(build_dip_pulse_site, "render_site", return_value=output_dir / "index.html") as render_site,
                mock.patch.object(sys, "stderr", new_callable=io.StringIO),
                mock.patch.object(sys, "stdout", new_callable=io.StringIO),
            ):
                code = build_dip_pulse_site.main()
            self.assertEqual(code, 0)
            build_dossiers.assert_called_once()
            self.assertEqual(render_site.call_args.kwargs["today"], date(2026, 9, 15))
            self.assertEqual(render_site.call_args.kwargs["week"], (2026, 24))
            self.assertEqual([e["slug"] for e in render_site.call_args.kwargs["entries"]], ["21-84"])

    def test_online_main_accepts_a_week_held_only_by_preserved_dossiers(self) -> None:
        # The catalog holds both sittings, this run rebuilds only 21/84, and the
        # preserved 21/70 dossier keeps KW 21 in the archive.
        catalog = [self._catalog_protocol("21/84", "5799", "2026-06-12"), self._catalog_protocol("21/70", "5780", "2026-05-20")]
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "site"
            preserved = self._entry("2026-05-20", "21/70", [self._item(1, [("SPD", 100)])])
            preserved["report"]["protocol"]["id"] = "5780"
            fresh = self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100)])])
            fresh["report"]["protocol"]["id"] = "5799"
            with (
                mock.patch.object(
                    sys, "argv",
                    self._online_argv(output_dir, "--week", "2026-21", "--detail-limit", "1", "--preserve-existing-dossiers"),
                ),
                mock.patch.object(build_dip_pulse_site, "fetch_protocols", return_value=catalog),
                mock.patch.object(build_dip_pulse_site, "load_existing_detail_entries", return_value=[preserved]),
                mock.patch.object(build_dip_pulse_site, "build_dossiers_with_progress", return_value=[fresh]),
                mock.patch.object(build_dip_pulse_site, "render_site", return_value=output_dir / "index.html") as render_site,
                mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr,
                mock.patch.object(sys, "stdout", new_callable=io.StringIO),
            ):
                code = build_dip_pulse_site.main()
            self.assertEqual(code, 0, stderr.getvalue())
            self.assertEqual(render_site.call_args.kwargs["week"], (2026, 21))
            self.assertEqual([e["slug"] for e in render_site.call_args.kwargs["entries"]], ["21-84", "21-70"])

    def test_online_main_reports_a_week_whose_dossiers_failed_to_build(self) -> None:
        catalog = [self._catalog_protocol("21/84", "5799", "2026-06-12"), self._catalog_protocol("21/70", "5780", "2026-05-20")]
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "site"
            fresh = self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100)])])
            fresh["report"]["protocol"]["id"] = "5799"
            with (
                mock.patch.object(sys, "argv", self._online_argv(output_dir, "--week", "2026-21")),
                mock.patch.object(build_dip_pulse_site, "fetch_protocols", return_value=catalog),
                # 21/70 is in the catalog (so the pre-check passes) but its dossier never materialises.
                mock.patch.object(build_dip_pulse_site, "build_dossiers_with_progress", return_value=[fresh]),
                mock.patch.object(build_dip_pulse_site, "render_site") as render_site,
                mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr,
                mock.patch.object(sys, "stdout", new_callable=io.StringIO),
            ):
                code = build_dip_pulse_site.main()
            self.assertEqual(code, 2)
            self.assertIn("--week 2026-21 ist nicht im Archiv; vorhanden: 2026-24 (Dossiers wurden bereits geschrieben", stderr.getvalue())
            render_site.assert_not_called()

    def test_online_main_without_week_skips_the_archive_check(self) -> None:
        protocol = self._catalog_protocol("21/84", "5799", "2026-06-12")
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "site"
            with (
                mock.patch.object(sys, "argv", self._online_argv(output_dir)),
                mock.patch.object(build_dip_pulse_site, "fetch_protocols", return_value=[protocol]),
                mock.patch.object(build_dip_pulse_site, "unknown_week_error", wraps=build_dip_pulse_site.unknown_week_error) as check,
                mock.patch.object(build_dip_pulse_site, "build_dossiers_with_progress", return_value=[]),
                mock.patch.object(build_dip_pulse_site, "render_site", return_value=output_dir / "index.html") as render_site,
                mock.patch.object(sys, "stderr", new_callable=io.StringIO),
                mock.patch.object(sys, "stdout", new_callable=io.StringIO),
            ):
                code = build_dip_pulse_site.main()
            self.assertEqual(code, 0)
            # Both archive checks (catalog, then built entries) run with no week and refuse nothing.
            self.assertEqual([c.args[0] for c in check.call_args_list], [None, None])
            self.assertEqual(check.call_args_list[0].args[1], [protocol])
            self.assertIsNone(render_site.call_args.kwargs["week"])
            self.assertEqual(render_site.call_args.kwargs["today"], date.today())


class OfflineRebuildEndToEndTests(unittest.TestCase):
    """[E2E] The offline build path with --week/--today against a fixture cache, unmocked."""

    @staticmethod
    def _seed(tmp: str) -> Path:
        output_dir = Path(tmp) / "site"
        (output_dir / "data").mkdir(parents=True)
        report = (_support.FIXTURES / "report.json").read_bytes()
        (output_dir / "data" / "plenarprotokoll-20-999.json").write_bytes(report)
        return output_dir

    def _build(self, output_dir: Path, *extra: str) -> tuple[int, str]:
        argv = ["build", "--offline", "--no-persist", "--output-dir", str(output_dir), *extra]
        with (
            mock.patch.dict(os.environ, {}, clear=False),
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr,
            mock.patch.object(sys, "stdout", new_callable=io.StringIO),
        ):
            os.environ.pop("SOURCE_DATE_EPOCH", None)
            code = build_dip_pulse_site.main()
        return code, stderr.getvalue()

    def test_offline_rebuild_with_pinned_flags_is_byte_identical(self) -> None:
        # Two offline rebuilds with the same --week/--today produce the same
        # puls.html; the plain rebuild (wall clock) differs only in the header
        # clock, and the dossier does not read the clock at all.
        with (
            tempfile.TemporaryDirectory() as plain_tmp,
            tempfile.TemporaryDirectory() as first_tmp,
            tempfile.TemporaryDirectory() as second_tmp,
        ):
            plain_dir = self._seed(plain_tmp)
            first_dir = self._seed(first_tmp)
            second_dir = self._seed(second_tmp)
            code, stderr = self._build(plain_dir)
            self.assertEqual(code, 0, stderr)
            for output_dir in (first_dir, second_dir):
                code, stderr = self._build(output_dir, "--week", "2024-20", "--today", "2026-09-17")
                self.assertEqual(code, 0, stderr)
            self.assertIn("offline: rendered 1 cached dossiers", stderr)
            self.assertRegex(stderr, r"\[puls\] KW 20/2024: 1 Sitzung, \d+ Themen?, \d+ Frageformate?, \d+ weitere, today=2026-09-17")
            first = (first_dir / "puls.html").read_text(encoding="utf-8")
            second = (second_dir / "puls.html").read_text(encoding="utf-8")
            plain = (plain_dir / "puls.html").read_text(encoding="utf-8")
            self.assertIn("20/999", first)
            self.assertIn("KW 20/2024", first)
            self.assertIn('Auswertung vom <time datetime="2026-09-17">17.09.2026</time>', first)
            self.assertEqual(first, second)
            self.assertNotEqual(plain, first)
            plain_dossier = (plain_dir / "protocols" / "plenarprotokoll-20-999.html").read_text(encoding="utf-8")
            pinned_dossier = (first_dir / "protocols" / "plenarprotokoll-20-999.html").read_text(encoding="utf-8")
            self.assertEqual(plain_dossier, pinned_dossier)

    def test_offline_rebuild_with_an_unknown_week_writes_no_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._seed(tmp)
            code, stderr = self._build(output_dir, "--week", "2024-21")
            self.assertEqual(code, 2)
            self.assertIn("--week 2024-21 ist nicht im Archiv; vorhanden: 2024-20", stderr)
            self.assertFalse((output_dir / "puls.html").exists())
            self.assertFalse((output_dir / "index.html").exists())
            self.assertEqual(list((output_dir / "protocols").iterdir()), [])
            self.assertEqual([p.name for p in (output_dir / "data").iterdir()], ["plenarprotokoll-20-999.json"])

    def test_offline_rebuild_with_a_bad_epoch_exits_before_reading_the_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._seed(tmp)
            argv = ["build", "--offline", "--no-persist", "--output-dir", str(output_dir)]
            with (
                mock.patch.dict(os.environ, {"SOURCE_DATE_EPOCH": "gestern"}),
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr,
            ):
                code = build_dip_pulse_site.main()
            self.assertEqual(code, 2)
            self.assertIn("SOURCE_DATE_EPOCH must be an integer Unix timestamp, got 'gestern'", stderr.getvalue())
            self.assertFalse((output_dir / "protocols").exists())


class SourceLinkGuardTests(unittest.TestCase):
    """The overview cards and Daten table only link to allowlisted https sources."""

    def _pages(self, xml_url: str, pdf_url: str) -> tuple[str, str]:
        protocol = dict(CurrentPulseOrderTests._protocol("21/84", "5799", "2026-06-12"), xml_url=xml_url, pdf_url=pdf_url)
        with tempfile.TemporaryDirectory() as tmp:
            entry = CurrentPulseOrderTests._entry(CurrentPulseOrderTests._output_dir(tmp), protocol)
            overview = build_dip_pulse_site.render_overview([protocol], [entry], features=default_selection())
            sources = build_dip_pulse_site.render_sources_page([entry], features=default_selection())
        return overview, sources

    def test_unsafe_protocol_urls_are_omitted(self) -> None:
        overview, sources = self._pages("javascript:alert(1)", "data:text/html,x")
        for markup in (overview, sources):
            self.assertNotIn("javascript:", markup)
            self.assertNotIn("data:text", markup)
            self.assertNotIn('href=""', markup)

    def test_http_protocol_urls_keep_their_links(self) -> None:
        overview, sources = self._pages("https://dserver.bundestag.de/btp/21/21084.xml", "https://dserver.bundestag.de/btp/21/21084.pdf")
        for markup in (overview, sources):
            self.assertIn('<a href="https://dserver.bundestag.de/btp/21/21084.xml">XML</a>', markup)
            self.assertIn('<a href="https://dserver.bundestag.de/btp/21/21084.pdf">PDF</a>', markup)


class WeekRadarPageTests(unittest.TestCase):
    """puls.html as a week radar: header, rows, Außerdem line, band states (build order §9-13)."""

    _item = SittingWeekComparisonTests._item
    _entry = SittingWeekComparisonTests._entry
    _pos = staticmethod(WeekRadarDataTests._pos)
    TODAY = date(2026, 9, 15)

    def _week(self) -> list[dict[str, Any]]:
        """Wed/Thu/Fri of KW 24/2026 plus an older week sharing one procedure.

        Wed: Befragung (6, the week's biggest), KI-Antrag (3), Wohngeld (3).
        Thu: bill with two Antrag twins (7, roll-call vote, summary), a four-Antrag
        group (4, returning from KW 21), Zwerg (1), a zero-speech item.
        Fri: Freitag drei (3), an untitled TOP (2 speeches, one recorded speaker).
        """
        wed = self._entry("2026-06-10", "21/82", [
            dict(self._item(1, [("Regierung", 50)] * 2 + [("SPD", 50)] * 4), heading="Befragung der Bundesregierung (einleitend BMJ)"),
            self._item(2, [("SPD", 100)] * 3, [self._pos("K1", "KI-Antrag")]),
            self._item(3, [("CDU/CSU", 100)] * 3, [self._pos("W1", "Wohngeld retten")]),
        ])
        thu = self._entry("2026-06-11", "21/83", [
            dict(
                self._item(
                    1,
                    [("CDU/CSU", 100)] * 3 + [("BÜNDNIS 90/DIE GRÜNEN", 100)] * 2 + [("AfD", 100)] * 2,
                    [self._pos("G1", "Gesetz zur Sache", "Gesetzgebung", "1. Beratung",
                               twins=[("A8", "Begleitantrag eins", "Antrag", "Beratung"), ("A9", "Begleitantrag zwei", "Antrag", "Beratung")])],
                ),
                heading="Erste Beratung des von der Bundesregierung eingebrachten Entwurfs eines Gesetzes zur Sache",
                votes=[{"id": "vote-1"}, {"id": "vote-1"}],
                llm_summary={
                    "text": "Die Koalition warb für das Gesetz, die Opposition hielt dagegen.",
                    "source_chunks": [
                        {"id": "R-1", "rede_id": "R1", "source_page": {"page": "100", "quadrant": "A"}},
                        {"id": "R-2", "rede_id": "MISSING", "source_page": {"page": "101"}},
                    ],
                },
            ),
            dict(
                self._item(2, [("SPD", 100)] * 4, [
                    self._pos("A1", "Bildung bezahlbar machen"),
                    self._pos("A2", "Zukunftsinvestitionen statt Kürzungen"),
                    self._pos("A3", "BAföG stärken"),
                    self._pos("A4", "Studienstarthilfe ausweiten"),
                ]),
                heading="Beratung der Anträge zur Bildung",
            ),
            self._item(3, [("SPD", 100)], [self._pos("Z1", "Zwerg")]),
            dict(self._item(4, []), xml_speech_count=0),
        ])
        thu["report"]["protocol"]["verteildatum"] = "2026-06-15"
        thu["report"]["protocol"]["pdf_url"] = "https://dserver.bundestag.de/btp/21/21083.pdf"
        thu["report"]["agenda_items"][0]["xml_speakers"][0]["rede_id"] = "R1"
        fri = self._entry("2026-06-12", "21/84", [
            self._item(1, [("AfD", 100)] * 3, [self._pos("F1", "Freitag drei")]),
            dict(self._item(2, [("Die Linke", 100)]), xml_speech_count=2),
        ])
        older = self._entry("2026-05-21", "21/80", [
            self._item(1, [("SPD", 100)] * 2, [self._pos("A2", "Zukunftsinvestitionen statt Kürzungen", "Antrag", "1. Beratung")]),
        ])
        return [fri, thu, wed, older]

    def _render(self, entries=None, *, today=None, features=None, week=None) -> str:
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO):
            return build_dip_pulse_site.render_front_page(
                entries if entries is not None else self._week(),
                database_href=None,
                features=features or all_selection(),
                today=today or self.TODAY,
                week=week,
            )

    @staticmethod
    def _section(markup: str, class_name: str) -> str:
        match = re.search(rf'<section class="{class_name}".*?</section>', markup, re.S)
        assert match, f"no <section class=\"{class_name}\">"
        return match.group(0)

    @staticmethod
    def _rows(radar: str) -> list[str]:
        return radar.split('<li class="radar-row"')[1:]

    # -- header -----------------------------------------------------------

    def test_header_running_week(self) -> None:
        markup = self._render(today=date(2026, 6, 11))
        header = re.search(r'<header class="page-header">(.*?)</header>', markup, re.S).group(1)
        self.assertIn('<span class="eyebrow">Sitzungswoche · Aktueller Puls</span>', header)
        self.assertIn("<h1>Was der Bundestag in KW 24/2026 bisher verhandelt hat</h1>", header)
        self.assertIn(
            '29 Reden in 9 Tagesordnungspunkten · Stand <time datetime="2026-06-11">11.06.2026</time>: '
            "3 Sitzungen erfasst, Sitzungswoche l&auml;uft",
            header,
        )
        self.assertNotIn("Auswertung vom", header)
        self.assertNotIn("Datenstand", header)

    def test_header_past_week_within_one_iso_week(self) -> None:
        markup = self._render(today=date(2026, 6, 16))
        header = re.search(r'<header class="page-header">(.*?)</header>', markup, re.S).group(1)
        self.assertIn('<span class="eyebrow">Sitzungswoche · Aktueller Puls</span>', header)
        self.assertIn("<h1>Was der Bundestag in KW 24/2026 verhandelt hat</h1>", header)
        self.assertIn(
            "29 Reden in 9 Tagesordnungspunkten · Stand: 3 Sitzungen, letztes Protokoll 21/84 vom "
            '<time datetime="2026-06-12">12.06.2026</time> · Auswertung vom <time datetime="2026-06-16">16.06.2026</time>',
            header,
        )

    def test_header_older_week_leads_with_its_age(self) -> None:
        markup = self._render(today=date(2026, 9, 15))
        header = re.search(r'<header class="page-header">(.*?)</header>', markup, re.S).group(1)
        self.assertIn('<span class="eyebrow">Letzte Sitzungswoche</span>', header)
        self.assertIn("Letzte Sitzungswoche vor 14 Wochen · 29 Reden in 9 Tagesordnungspunkten · 3 Sitzungen, letztes Protokoll 21/84 vom", header)
        self.assertIn('Auswertung vom <time datetime="2026-09-15">15.09.2026</time>', header)
        # A build dated before the week renders as a past week and warns.
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
            early = build_dip_pulse_site.render_front_page(self._week(), database_href=None, today=date(2026, 6, 1))
        self.assertIn("Stand: 3 Sitzungen", early)
        self.assertIn("warning: [puls] Auswertung liegt vor der Sitzungswoche", stderr.getvalue())

    def test_header_uses_verteildatum_when_the_newest_protocol_has_one(self) -> None:
        entries = self._week()
        entries[0]["report"]["protocol"]["verteildatum"] = "2026-06-15T00:00:00"
        markup = self._render(entries, today=date(2026, 6, 16))
        self.assertIn('letztes Protokoll 21/84 verteilt am <time datetime="2026-06-15">15.06.2026</time>', markup)

    def test_sitting_chips_in_date_order_with_stem_fallback(self) -> None:
        entries = self._week()
        del entries[2]["report"]["protocol"]["dokumentnummer"]
        markup = self._render(entries)
        chips = re.search(r'<nav class="week-chips" aria-label="Sitzungen dieser Woche">(.*?)</nav>', markup, re.S).group(1)
        self.assertEqual(
            re.findall(r'<a href="([^"]+)">(.*?)</a>', chips),
            [
                ("protocols/plenarprotokoll-21-82.html", '<time datetime="2026-06-10">Mi 10.06.</time> · plenarprotokoll-21-82'),
                ("protocols/plenarprotokoll-21-83.html", '<time datetime="2026-06-11">Do 11.06.</time> · 21/83'),
                ("protocols/plenarprotokoll-21-84.html", '<time datetime="2026-06-12">Fr 12.06.</time> · 21/84'),
            ],
        )
        self.assertIn('<a href="protocols/plenarprotokoll-21-84.html">Neuestes Protokoll</a>', markup)

    def test_undated_sittings_are_noted_and_warned_about(self) -> None:
        entries = self._week()
        entries.append(self._entry("", "21/90", [self._item(1, [("SPD", 100)])]))
        entries.append(self._entry("kein Datum", "21/91", [self._item(1, [("SPD", 100)])]))
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
            markup = build_dip_pulse_site.render_front_page(entries, database_href=None, today=self.TODAY)
        self.assertIn('<p class="week-note">2 neuere Sitzungen ohne Datum nicht ber&uuml;cksichtigt</p>', markup)
        self.assertIn("warning: [puls] 2 Sitzungen ohne Datum ausgeschlossen (21/90, 21/91)", stderr.getvalue())
        self.assertRegex(stderr.getvalue(), r"\[puls\] KW 24/2026: 3 Sitzungen, 5 Themen, 1 Frageformat, 2 weitere, today=2026-09-15, 2 Sitzungen ohne gültiges Datum")

    def test_only_undated_sittings_render_the_shell_sentence(self) -> None:
        entries = [self._entry("", "21/90", [self._item(1, [("SPD", 100)])])]
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
            markup = build_dip_pulse_site.render_front_page(entries, database_href=None, today=self.TODAY)
        self.assertIn("Die erzeugten Sitzungen tragen kein Datum, ein Wochenradar ist nicht möglich.", markup)
        self.assertNotIn("Es wurden noch keine Sitzungen erzeugt.", markup)
        self.assertNotIn('<li class="radar-row"', markup)
        self.assertIn("warning: [puls] kein Wochenradar möglich: keine datierte Sitzung", stderr.getvalue())
        empty = self._render([])
        self.assertIn("Es wurden noch keine Sitzungen erzeugt.", empty)

    def test_zero_speech_week_keeps_the_heading_and_one_note(self) -> None:
        entries = [self._entry("2026-06-12", "21/84", [dict(self._item(1, []), xml_speech_count=0), dict(self._item(2, []), xml_speech_count=0)])]
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
            markup = build_dip_pulse_site.render_front_page(entries, database_href=None, today=self.TODAY)
        radar = self._section(markup, "radar")
        self.assertIn("<h2 id=\"radar-h2\">Wor&uuml;ber am meisten gesprochen wurde</h2>", radar)
        self.assertIn('<p class="week-note">In dieser Sitzungswoche wurden keine Reden extrahiert.</p>', radar)
        self.assertNotIn("radar-method", radar)
        self.assertNotIn("radar-row", radar)
        self.assertNotIn("radar-also", radar)
        self.assertIn("0 Reden in 2 Tagesordnungspunkten", markup)
        self.assertIn("warning: [puls] KW 24/2026: keine Reden extrahiert (leere Eingabe oder Extraktion), Abruf prüfen", stderr.getvalue())

    # -- radar rows -------------------------------------------------------

    def test_rows_rank_across_the_three_sittings_with_one_denominator(self) -> None:
        markup = self._render()
        radar = self._section(markup, "radar")
        self.assertIn("Anteil an allen 29 Reden; Frageformate wie die Befragung der Bundesregierung (einleitend BMJ) (6 Wortmeldungen) zählen mit, werden aber nicht als Thema gerankt.", radar)
        rows = self._rows(radar)
        self.assertEqual(len(rows), 5)
        self.assertEqual(
            [re.search(r'<strong>(\d+ Reden?)</strong><small>([^<]+)</small>', row).groups() for row in rows],
            [("7 Reden", "24,1% der Woche"), ("4 Reden", "13,8% der Woche"), ("3 Reden", "10,3% der Woche"), ("3 Reden", "10,3% der Woche"), ("3 Reden", "10,3% der Woche")],
        )
        self.assertEqual([re.search(r'style="width:([\d.]+)%"', row).group(1) for row in rows], ["100.00", "57.14", "42.86", "42.86", "42.86"])
        self.assertEqual(
            [re.search(r'class="radar-open"><a href="([^"]+)">', row).group(1) for row in rows],
            [
                "protocols/plenarprotokoll-21-83.html#top-1",
                "protocols/plenarprotokoll-21-83.html#top-2",
                "protocols/plenarprotokoll-21-84.html#top-1",
                "protocols/plenarprotokoll-21-82.html#top-2",
                "protocols/plenarprotokoll-21-82.html#top-3",
            ],
        )
        self.assertIn("Do 11.06. · Tagesordnungspunkt 1 · Debatte im Protokoll öffnen", rows[0])
        self.assertNotIn("Aufmerksamkeit", radar)
        self.assertNotIn("Neu auf der Tagesordnung", radar)
        # No rank ordinals: the rows are an unordered list with ids only.
        self.assertIn('<ul class="radar-list">', radar)
        self.assertNotIn("<ol", radar)

    def test_lead_title_row_with_twins_and_the_heading_in_the_title_attribute(self) -> None:
        row = self._rows(self._section(self._render(), "radar"))[0]
        self.assertIn('<span class="eyebrow">Gesetzgebung · 1. Beratung · mit 2 Anträgen</span>', row)
        self.assertIn(
            '<strong class="radar-title"><a href="protocols/plenarprotokoll-21-83.html#top-1" '
            'title="Erste Beratung des von der Bundesregierung eingebrachten Entwurfs eines Gesetzes zur Sache">Gesetz zur Sache</a></strong>',
            row,
        )
        self.assertIn('<p class="radar-siblings">mit: Begleitantrag eins · Begleitantrag zwei</p>', row)
        self.assertNotIn("Erste Beratung des von", row.split("radar-title")[1].split("</strong>")[1])

    def test_equal_weight_row_links_the_label_and_lists_titles_alike(self) -> None:
        row = self._rows(self._section(self._render(), "radar"))[1]
        self.assertNotIn('<strong class="radar-title">', row)
        self.assertIn(
            '<span class="eyebrow"><a href="protocols/plenarprotokoll-21-83.html#top-2" title="Beratung der Anträge zur Bildung">'
            "Antrag · Beratung · 4 Anträge gemeinsam</a></span>",
            row,
        )
        titles = re.search(r'<ul class="radar-titles">(.*?)</ul>', row, re.S).group(1)
        self.assertEqual(
            re.findall(r'<li class="radar-group-title">([^<]+)</li>', titles),
            ["Bildung bezahlbar machen", "Zukunftsinvestitionen statt Kürzungen", "BAföG stärken"],
        )
        self.assertIn(
            '<li class="radar-group-more"><a href="protocols/plenarprotokoll-21-83.html#top-2" title="Studienstarthilfe ausweiten">und 1 weitere</a></li>',
            titles,
        )
        # The heading is only ever a title attribute, never a visible title.
        self.assertEqual(row.count("Beratung der Anträge zur Bildung"), 1)
        self.assertNotIn(">Beratung der Anträge zur Bildung<", row)

    def test_trace_links_only_the_earlier_occurrence(self) -> None:
        rows = self._rows(self._section(self._render(), "radar"))
        self.assertIn(
            '<p class="radar-trace">Fortgesetzt: <a href="protocols/plenarprotokoll-21-80.html#top-1">1. Beratung in KW 21/2026</a> &rarr; Beratung diese Woche</p>',
            rows[1],
        )
        self.assertEqual(sum("radar-trace" in row for row in rows), 1)

    def test_who_stack_legend_short_names_and_truncation_suffix(self) -> None:
        rows = self._rows(self._section(self._render(), "radar"))
        self.assertIn('<p class="radar-legend">CDU/CSU 3 · Grüne 2 · AfD 2</p>', rows[0])
        stack = re.search(r'<div aria-hidden="true"><div class="who-stack">(.*?)</div></div>', rows[0]).group(1)
        self.assertEqual(re.findall(r'width:([\d.]+)%', stack), ["42.86", "28.57", "28.57"])
        self.assertIn('title="BÜNDNIS 90/DIE GRÜNEN: 2"', stack)
        # Five speeches, two recorded speakers: the stack spans the two recorded
        # ones and the legend says so (item_stats' xml_speakers_first fallback).
        entries = [self._entry("2026-06-12", "21/84", [dict(self._item(1, [("Die Linke", 100), ("SPD", 100)]), xml_speech_count=5)])]
        truncated = self._rows(self._section(self._render(entries), "radar"))[0]
        self.assertIn("<strong>5 Reden</strong>", truncated)
        self.assertIn('<p class="radar-legend">Linke 1 · SPD 1 · Fraktionen nur für die ersten 2 Reden bekannt</p>', truncated)
        self.assertEqual(re.findall(r'width:([\d.]+)%', truncated.split("who-stack")[1]), ["50.00", "50.00"])

    def test_who_stack_without_any_recorded_fraktion(self) -> None:
        entries = [self._entry("2026-06-12", "21/84", [dict(self._item(1, []), xml_speech_count=4)])]
        row = self._rows(self._section(self._render(entries), "radar"))[0]
        self.assertIn('<div class="who-stack empty"></div>', row)
        self.assertIn('<p class="radar-legend">Fraktionen nicht erfasst</p>', row)

    def test_summary_block_is_unconditional_and_receipts_point_at_the_dossier(self) -> None:
        with_summaries = self._rows(self._section(self._render(), "radar"))[0]
        self.assertIn('<div class="radar-summary"><p>Die Koalition warb für das Gesetz, die Opposition hielt dagegen.</p>', with_summaries)
        receipts = re.search(r'<p class="radar-receipts">(.*?)</p>', with_summaries).group(1)
        self.assertEqual(
            receipts,
            '<a href="protocols/plenarprotokoll-21-83.html#speech-1-R1">R-1 · S. 100A</a>'
            "<span>R-2 · S. 101</span>"
            '<a href="https://dserver.bundestag.de/btp/21/21083.pdf">Originalprotokoll</a>',
        )
        without = self._rows(self._section(self._render(features=default_selection()), "radar"))[0]
        self.assertIn("radar-summary", without)
        # Rows without a usable summary have no slot at all.
        self.assertEqual(sum("radar-summary" in row for row in self._rows(self._section(self._render(), "radar"))), 1)

    def test_vote_badge_is_unconditional(self) -> None:
        rows = self._rows(self._section(self._render(), "radar"))
        self.assertIn('<span class="badge radar-badge">namentlich abgestimmt</span>', rows[0])
        self.assertEqual(sum("radar-badge" in row for row in rows), 1)
        without = self._rows(self._section(self._render(features=default_selection()), "radar"))
        self.assertEqual(sum("radar-badge" in row for row in without), 1)

    def test_api_titles_and_headings_are_escaped(self) -> None:
        entries = [self._entry("2026-06-12", "21/84", [
            dict(self._item(1, [("SPD", 100)] * 2, [self._pos("X1", "<script>alert(1)</script> & Co")]), heading="<b>fett</b>"),
        ])]
        markup = self._render(entries)
        self.assertNotIn("<script>alert(1)</script>", markup)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; &amp; Co", markup)
        self.assertIn('title="&lt;b&gt;fett&lt;/b&gt;"', markup)

    # -- Außerdem line ----------------------------------------------------

    def test_ausserdem_line_formats_and_remaining(self) -> None:
        radar = self._section(self._render(), "radar")
        self.assertIn(
            '<p class="radar-also">Außerdem, nicht als Thema gerankt: '
            '<a href="protocols/plenarprotokoll-21-82.html#top-1">Befragung der Bundesregierung (einleitend BMJ)</a> · 6 Wortmeldungen · 20,7% (Mi 10.06., TOP 1) · '
            'Weitere 2 Tagesordnungspunkte: <a href="protocols/plenarprotokoll-21-83.html">21/83</a> (1) · <a href="protocols/plenarprotokoll-21-84.html">21/84</a> (1)</p>',
            radar,
        )

    def test_ausserdem_line_formats_only(self) -> None:
        entries = [self._entry("2026-06-10", "21/82", [
            dict(self._item(1, [("SPD", 50)] * 2), heading="Fragestunde"),
            self._item(2, [("SPD", 100)] * 3, [self._pos("K1", "KI-Antrag")]),
        ])]
        radar = self._section(self._render(entries), "radar")
        self.assertIn('<p class="radar-also">Außerdem, nicht als Thema gerankt: <a href="protocols/plenarprotokoll-21-82.html#top-1">Fragestunde</a> · 2 Wortmeldungen · 40,0% (Mi 10.06., TOP 1)</p>', radar)
        self.assertNotIn("Weitere", radar)

    def test_ausserdem_line_remaining_only_and_singular(self) -> None:
        items = [self._item(i, [("SPD", 100)] * (7 - i), [self._pos(f"P{i}", f"Punkt {i}")]) for i in range(1, 7)]
        entries = [self._entry("2026-06-10", "21/82", items)]
        radar = self._section(self._render(entries), "radar")
        self.assertIn('<p class="radar-also">1 weiterer Tagesordnungspunkt: <a href="protocols/plenarprotokoll-21-82.html">21/82</a> (1)</p>', radar)
        self.assertNotIn("Außerdem", radar)

    def test_ausserdem_line_absent_without_formats_or_remaining(self) -> None:
        entries = [self._entry("2026-06-10", "21/82", [self._item(1, [("SPD", 100)] * 2, [self._pos("K1", "KI-Antrag")])])]
        self.assertNotIn("radar-also", self._section(self._render(entries), "radar"))

    # -- Wochenvergleich band ---------------------------------------------

    def test_votes_card_counts_distinct_votes_across_the_week(self) -> None:
        entries = self._week()
        entries[0]["report"]["agenda_items"][0]["votes"] = [{"id": "vote-2"}]
        entries[0]["report"]["agenda_items"][1]["votes"] = [{"id": "vote-2"}, {"id": "vote-3"}]
        band = self._section(self._render(entries), "week-compare")
        card = re.search(r'<article class="week-card votes-card" id="abstimmungen">(.*?)</article>', band, re.S).group(1)
        self.assertIn('<span class="eyebrow">Erfasst</span>', card)
        self.assertIn("<h3>Namentliche Abstimmungen</h3>", card)
        self.assertIn('<p class="week-text">3 namentliche Abstimmungen in 3 Tagesordnungspunkten dieser Woche</p>', card)
        self.assertEqual(
            re.findall(r'<li class="vote-row"><a href="([^"]+)">([^<]+)</a></li>', card),
            [
                ("protocols/plenarprotokoll-21-83.html#top-1", "21/83 · 1 Abstimmung"),
                ("protocols/plenarprotokoll-21-84.html#top-1", "21/84 · 2 Abstimmungen"),
            ],
        )
        self.assertNotIn("Vergleichsdaten", card)
        self.assertNotIn("Sitzungsbelege", card)

    def test_votes_card_singulars_and_empty_state(self) -> None:
        card = re.search(r'<article class="week-card votes-card".*?</article>', self._render(), re.S).group(0)
        self.assertIn("1 namentliche Abstimmung in 1 Tagesordnungspunkt dieser Woche", card)
        entries = [self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100)])])]
        markup = self._render(entries)
        card = re.search(r'<article class="week-card votes-card".*?</article>', markup, re.S).group(0)
        self.assertIn("Keine namentlichen Abstimmungen in dieser Sitzungswoche erfasst.", card)
        self.assertIn('<a class="feature-link" href="protocols/plenarprotokoll-21-84.html">Sitzungsbelege pr&uuml;fen</a>', card)
        # Not built at all without the votes Baustein; present in both band states with it.
        self.assertNotIn('<article class="week-card votes-card"', self._render(entries, features=default_selection()))
        self.assertIn('id="abstimmungen"', self._section(self._render(entries), "week-compare"))
        self.assertIn('id="abstimmungen"', self._section(self._render(), "week-compare"))

    def test_no_comparison_state_renders_the_current_week_without_deltas(self) -> None:
        entries = [self._entry("2026-06-12", "21/84", [self._item(1, [("SPD", 100), ("AfD", 100)]), dict(self._item(2, []), xml_speech_count=3)])]
        band = self._section(self._render(entries), "week-compare")
        self.assertIn('<h2 id="wochenvergleich-h2">Noch keine Vergleichswoche</h2>', band)
        self.assertIn("<h3>Wochenpuls</h3>", band)
        self.assertIn("<h3>Redeanteil der Fraktionen</h3>", band)
        self.assertEqual(re.findall(r"<span>(Reden|Tagesordnungspunkte|Redetext \(Zeichen\))</span>", band), ["Reden", "Tagesordnungspunkte"])
        metrics = re.search(r'<div class="week-metrics">(.*?)</div>\s*<p class="week-note">', band, re.S).group(1)
        self.assertEqual(metrics.count('<span class="week-delta flat">n/a</span>'), 2)
        self.assertNotIn("<em>", metrics)
        self.assertNotIn("week-spark", band)
        self.assertNotIn("Debattenprofil", band)
        self.assertIn("Anteil an allen Reden der Woche. Fraktionen f&uuml;r 2 von 5 Reden erfasst.", band)
        self.assertIn('<li class="week-row">', band)

    def test_normalised_comparison_uses_na_chips_and_the_caveat_note(self) -> None:
        # E16 middle path: differing sitting counts keep the per-sitting figures
        # and the Redeanteil pp column, but the Wochenpuls chips read n/a.
        entries = self._week()
        entries.append(self._entry("2026-05-22", "21/81", [self._item(1, [("SPD", 100)] * 2)]))
        band = self._section(self._render(entries), "week-compare")
        self.assertIn("Werte je Sitzung", band)
        metrics = re.search(r'<div class="week-metrics">(.*?)</div>\s*<div class="week-spark', band, re.S).group(1)
        self.assertEqual(metrics.count('<span class="week-delta flat">n/a</span>'), 3)
        self.assertIn("Anteile gegen&uuml;ber KW 21/2026 (2 Sitzungen); bei abweichender Sitzungszahl verschiebt die Tagesmischung die Anteile.", band)
        self.assertIn("Fraktionen f&uuml;r 28 von 29 Reden erfasst.", band)
        shares = re.search(r'<h3>Redeanteil der Fraktionen</h3>(.*?)</article>', band, re.S).group(1)
        self.assertRegex(shares, r'<span class="week-delta (up|down|flat)">')

    def test_equal_sitting_counts_keep_the_delta_chips(self) -> None:
        entries = self._week()
        for datum, document in (("2026-05-20", "21/78"), ("2026-05-22", "21/81")):
            entries.append(self._entry(datum, document, [self._item(1, [("SPD", 100)] * 2)]))
        band = self._section(self._render(entries), "week-compare")
        self.assertNotIn("Werte je Sitzung", band)
        metrics = re.search(r'<div class="week-metrics">(.*?)</div>\s*<div class="week-spark', band, re.S).group(1)
        self.assertNotIn("n/a", metrics)
        self.assertNotIn("je Sitzung</span>", metrics)
        self.assertIn("Anteil an allen Reden der Woche, Ver&auml;nderung in Prozentpunkten gegen&uuml;ber KW 21/2026.", band)

    # -- CSS contract -----------------------------------------------------

    def test_content_hiding_rules_are_screen_scoped(self) -> None:
        # Print must keep every block: display:none is only allowed inside a
        # screen or max-width media block, on pseudo-elements, or on the page
        # actions in print.
        markup = self._render()
        css = re.search(r"<style>(.*?)</style>", markup, re.S).group(1)
        for query, body in re.findall(r"@media([^{]*)\{((?:[^{}]*\{[^{}]*\})*)\s*\}", css, re.S):
            if "screen" in query or "max-width" in query:
                continue
            for selector, rules in re.findall(r"([^{}]+)\{([^{}]*)\}", body):
                if "display:none" in rules.replace(" ", ""):
                    self.assertTrue(
                        "::before" in selector or "::after" in selector or ".page-actions" in selector,
                        msg=f"@media{query.strip()} hides {selector.strip()}",
                    )
        self.assertIn("@media print", css)
        # New rules use tokens only, no hex literals.
        for selector, rules in re.findall(r"([^{}@]+)\{([^{}]*)\}", css):
            if ".radar" in selector or ".who-stack" in selector:
                self.assertNotIn("#", rules, msg=selector.strip())
        self.assertIn(".radar-row a { text-decoration-line:underline; text-decoration-color:transparent;", css)
        self.assertIn(".radar-row a:visited { text-decoration-color:var(--muted); }", css)
        for class_name in (".radar", ".radar-row", ".radar-title", ".radar-titles", ".radar-group-title", ".radar-share", ".who-stack", ".radar-legend", ".radar-trace", ".radar-summary", ".radar-also"):
            self.assertRegex(css, rf"(^|[\s,]){re.escape(class_name)}[\s,][^{{]*{{", msg=class_name)
        self.assertIn('<section class="radar" aria-labelledby="radar-h2">', markup)
        self.assertIn('<section class="week-compare" id="wochenvergleich" aria-labelledby="wochenvergleich-h2">', markup)
        self.assertIn('<div class="radar-bar" aria-hidden="true">', markup)
        self.assertIn('<div aria-hidden="true"><div class="who-stack">', markup)

    def test_format_percent_strings(self) -> None:
        self.assertEqual(pulse_html.format_percent(4.64), "4,6%")
        self.assertEqual(pulse_html.format_percent(28.36), "28,4%")
        self.assertEqual(pulse_html.format_percent(0.0), "0,0%")
        self.assertEqual(pulse_html.format_percent(100.0), "100,0%")


class DossierDatenLinkTests(unittest.TestCase):
    """Dossiers are written before the manifest exists, so their footer
    predicts it from the export's own condition."""

    def _href(self, *, no_persist: bool, store: bool, data_manifest: str | None = None, env: str | None = None):
        args = SimpleNamespace(no_persist=no_persist, data_manifest=data_manifest)
        environ = {"BUNDESTAG_PULSE_DATA_MANIFEST": env} if env else {}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, environ, clear=False):
            if not env:
                os.environ.pop("BUNDESTAG_PULSE_DATA_MANIFEST", None)
            database_path = Path(tmp) / "bundestag-pulse.sqlite"
            if store:
                database_path.write_bytes(b"")
            return build_dip_pulse_site.dossier_database_page_href(args, database_path)

    def test_persisted_store_links_daten(self) -> None:
        self.assertEqual(self._href(no_persist=False, store=True), "../database.html")

    def test_no_persist_or_missing_store_omits_daten(self) -> None:
        self.assertIsNone(self._href(no_persist=True, store=True))
        self.assertIsNone(self._href(no_persist=False, store=False))

    def test_manifest_override_links_daten_even_without_a_store(self) -> None:
        self.assertEqual(self._href(no_persist=True, store=False, data_manifest="m.json"), "../database.html")
        self.assertEqual(self._href(no_persist=True, store=False, env="https://example.org/m.json"), "../database.html")

    def test_written_dossier_carries_the_link_only_when_given(self) -> None:
        report = {
            "protocol": {"dokumentnummer": "21/1", "titel": "Protokoll 21/1"},
            "validation_summary": {},
            "agenda_items": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "data").mkdir()
            (output_dir / "protocols").mkdir()
            footer = lambda entry: re.search(r"<footer>.*?</footer>", entry["page_path"].read_text(encoding="utf-8"), re.S).group(0)
            with_link = build_dip_pulse_site.write_report_files(report, output_dir, database_page_href="../database.html")
            self.assertIn('<a href="../database.html">Daten</a>', footer(with_link))
            # The site-wide header links Daten on every page regardless; only
            # the footer link follows the build's data state.
            without = build_dip_pulse_site.write_report_files(report, output_dir)
            self.assertNotIn("database.html", footer(without))


if __name__ == "__main__":
    unittest.main()
