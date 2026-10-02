"""E6 and DX-B1: backfilling keeps everything else, and every build says what
is incomplete and how to fix it.

Acquisition scope (what an update fetches again) and retained scope (what the
store and the site keep) are separate: the store is rebuilt from the whole
catalog plus every cached dossier, refreshing only the acquired sittings.
"""

from __future__ import annotations

import copy
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import _facts_fixture
import _support
import build_dip_pulse_site as build
import facts
import persist_dip_pulse_store as pulse_store
from test_facts import StoreCase, week_specs

STAMP = "2026-09-28T10:00:00Z"


def catalog_protocol(number: str, protocol_id: str, day: str, *, xml: bool = True) -> dict:
    protocol = {"id": protocol_id, "dokumentnummer": number, "datum": day, "titel": f"Protokoll {number}"}
    if xml:
        protocol["fundstelle"] = {"xml_url": f"https://example.test/{protocol_id}.xml"}
    return protocol


def report_for(n: int, *, acquisition: dict | None = None, day: str | None = None) -> dict:
    """A cached dossier report for sitting 21/n, from the repo fixture."""
    report = json.loads((_support.FIXTURES / "report.json").read_text(encoding="utf-8"))
    report["protocol"].update(
        {"id": f"pp-{n}", "dokumentnummer": f"21/{n}", "datum": day or f"2026-06-{10 + n:02d}"}
    )
    for item in report["agenda_items"]:
        for speech in item["xml_speakers"]:
            speech["rede_id"] = f"{n}-{speech['rede_id']}"
        for vote in item.get("votes") or []:
            vote["id"] = f"{n}{vote['id']}"
            vote["detail_url"] = f"{vote['detail_url']}{n}"
    report["validation_summary"] = {"xml_speech_count": 3}
    if acquisition is not None:
        report["acquisition"] = {"votes": acquisition}
        # The evidence a scan records (how it ended); a report cached before
        # it existed has none and is unverified.
        report["validation_summary"]["roll_call_scan_end"] = "date_passed"
    return report


COMPLETE_VOTES = {"acquisition_state": "complete", "acquired_at": STAMP, "failure_reasons": []}


def write_cached(output_dir: Path, report: dict) -> dict:
    return build.write_report_files(report, output_dir, {}, None)


class RetainedScopeTests(unittest.TestCase):
    """E6: backfilling one sitting keeps every other protocol, speech, vote and page."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output_dir = Path(self.tmp.name) / "site"
        for name in ("protocols", "data"):
            (self.output_dir / name).mkdir(parents=True)
        self.catalog = [
            catalog_protocol("21/3", "pp-3", "2026-06-13"),
            catalog_protocol("21/2", "pp-2", "2026-06-12"),
            catalog_protocol("21/1", "pp-1", "2026-06-11"),
        ]
        self.cached = [write_cached(self.output_dir, report_for(n, acquisition=COMPLETE_VOTES)) for n in (1, 2, 3)]
        self.database = self.output_dir / "data" / "bundestag-pulse.sqlite"
        build.rebuild_database_from_entries(self.database, self.cached)

    def counts(self) -> dict[str, int]:
        conn = sqlite3.connect(self.database)
        try:
            return {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("protocols", "agenda_items", "speeches", "votes", "vote_members")
            }
        finally:
            conn.close()

    def run_main(self, *extra: str, generated: list[dict]):
        argv = ["build", "--api-key", "k", "--no-abgeordnetenwatch", "--output-dir", str(self.output_dir), *extra]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(build, "fetch_protocols", return_value=copy.deepcopy(self.catalog)) as fetch,
            mock.patch.object(build, "build_dossiers_with_progress", return_value=generated) as build_dossiers,
            mock.patch.object(build, "run_data_pipeline", return_value=(None, None, set(), "data/exports/", False)),
            mock.patch.object(build, "render_site", return_value=self.output_dir / "index.html") as render_site,
            mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr,
            mock.patch.object(sys, "stdout", new_callable=io.StringIO),
        ):
            code = build.main()
        return code, fetch, build_dossiers, render_site, stderr.getvalue()

    def test_backfilling_one_sitting_keeps_every_other_protocol_speech_vote_and_page(self) -> None:
        before = self.counts()
        self.assertEqual(before["protocols"], 3)
        self.assertGreaterEqual(before["speeches"], 9)
        self.assertGreaterEqual(before["votes"], 3)
        refreshed = write_cached(self.output_dir, report_for(2, acquisition={**COMPLETE_VOTES, "acquired_at": "2026-09-29T10:00:00Z"}))
        pages_before = {p.name: p.read_bytes() for p in (self.output_dir / "protocols").glob("*.html")}

        code, _fetch, build_dossiers, render_site, stderr = self.run_main("--document-number", "21/2", generated=[refreshed])

        self.assertEqual(code, 0, stderr)
        # Only the named sitting was acquired ...
        self.assertEqual([p["dokumentnummer"] for p in build_dossiers.call_args.args[0]], ["21/2"])
        # ... and nothing else left the store, the site or the cache.
        self.assertEqual(self.counts(), before)
        self.assertEqual(
            sorted(entry["slug"] for entry in render_site.call_args.kwargs["entries"]), ["21-1", "21-2", "21-3"]
        )
        self.assertEqual(sorted(p.name for p in (self.output_dir / "protocols").glob("*.html")), sorted(pages_before))
        for n in (1, 2, 3):
            self.assertTrue((self.output_dir / "data" / f"plenarprotokoll-21-{n}.json").exists())

    # Value: protects=an online build whose staged rebuild is refused (here: another writer holds the store lock) exits 1 with an error line and leaves the store as it was; fails_when=main lets DatabaseRebuildError escape as a traceback (only SprechrolleError and DipError are caught around the rebuild); why_new=only the offline --repersist path and rebuild_database_from_entries itself were tested for rebuild failures; seam=none
    def test_an_online_build_reports_a_refused_rebuild_instead_of_a_traceback(self) -> None:
        import fcntl

        before = self.database.read_bytes()
        refreshed = write_cached(self.output_dir, report_for(2, acquisition=COMPLETE_VOTES))
        lock = self.database.with_suffix(self.database.suffix + ".writer.lock")
        with lock.open("a") as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)  # a second open file description conflicts, in-process too
            try:
                code, _fetch, _build_dossiers, _render_site, stderr = self.run_main(
                    "--document-number", "21/2", generated=[refreshed]
                )
            except build.DatabaseRebuildError as exc:
                self.fail(f"main raised DatabaseRebuildError instead of reporting it: {exc}")
        self.assertEqual(code, 1, stderr)
        self.assertIn("Another writer", stderr)
        self.assertEqual(before, self.database.read_bytes())

    # Value: protects=an online build with --enrich mp-roster ingests the roster into the staged store and hands the cached sitting catalog to the facts engine; fails_when=main drops roster_ingest or catalog= on the staged rebuild call, so no roster row or no Fakt is ever published online; why_new=the staged rebuild is tested through its function, and the only main()-level test stops at the writer lock; seam=none
    def test_an_online_build_ingests_the_roster_into_the_staged_store_and_forwards_the_catalog(self) -> None:
        (self.output_dir / "data" / facts.CATALOG_FILENAME).write_text(
            json.dumps({"authoritative": True, "protocols": [{"dokumentnummer": "21/84", "datum": "2026-03-04"}]}),
            encoding="utf-8",
        )
        refreshed = write_cached(self.output_dir, report_for(2, acquisition=COMPLETE_VOTES))
        seen = {}

        def fake_ingest(_client, staged, **_kwargs):
            seen["database"] = staged.execute("PRAGMA database_list").fetchone()[2]
            return {"fetched": 0, "mdb": 0, "enriched": 0}

        with (
            mock.patch.object(build, "ingest_mdb_roster", side_effect=fake_ingest),
            mock.patch.object(facts, "compute_and_store", wraps=facts.compute_and_store) as engine,
        ):
            code, _fetch, _build_dossiers, _render_site, stderr = self.run_main(
                "--document-number", "21/2", "--enrich", "mp-roster", generated=[refreshed]
            )
        self.assertEqual(code, 0, stderr)
        self.assertNotEqual(Path(seen["database"]), self.database)  # the staged copy, not the published store
        self.assertIn("roster: 0 MdBs", stderr)
        self.assertTrue(engine.call_args.kwargs["catalog"].authoritative)

    # Value: protects=a roster fetch that fails during an online build exits 1 with the staged-rebuild error, never swaps the store and names the roster; fails_when=the roster failure escapes as a traceback or is swallowed so protocols persist without the roster; why_new=the user confirmed the abort as intended, so the exit code, the message and the untouched store must be pinned at main(); seam=none
    def test_an_online_build_aborts_cleanly_when_the_roster_fetch_fails(self) -> None:
        before = self.database.read_bytes()
        refreshed = write_cached(self.output_dir, report_for(2, acquisition=COMPLETE_VOTES))
        with mock.patch.object(build, "ingest_mdb_roster", side_effect=build.dip.DipError("DIP 503")):
            code, _fetch, _build_dossiers, _render_site, stderr = self.run_main(
                "--document-number", "21/2", "--enrich", "mp-roster", generated=[refreshed]
            )
        self.assertEqual(code, 1, stderr)
        self.assertIn("Abgeordnetenkader could not be fetched: DIP 503", stderr)
        self.assertIn("previous store is untouched", stderr)
        self.assertEqual(before, self.database.read_bytes())

    def test_the_catalog_is_fetched_whole_and_the_store_keeps_dossiers_cut_by_detail_limit(self) -> None:
        before = self.counts()
        code, fetch, build_dossiers, _render_site, stderr = self.run_main("--detail-limit", "1", generated=[])
        self.assertEqual(code, 0, stderr)
        self.assertEqual(fetch.call_args.args[1:], (0, [], None))
        self.assertEqual(len(build_dossiers.call_args.args[0]), 1)
        self.assertEqual(self.counts(), before)

    def test_a_failed_acquisition_keeps_the_previous_dossier_of_that_sitting(self) -> None:
        before = self.counts()
        code, _fetch, _build_dossiers, render_site, stderr = self.run_main("--document-number", "21/2", generated=[])
        self.assertEqual(code, 0, stderr)
        self.assertEqual(self.counts(), before)
        self.assertEqual(len(render_site.call_args.kwargs["entries"]), 3)


class BackfillSelectionTests(unittest.TestCase):
    def entries(self, *reports: dict) -> list[dict]:
        return [{"report": report} for report in reports]

    def test_only_missing_or_incompletely_acquired_sittings_are_selected(self) -> None:
        entries = self.entries(
            report_for(1, acquisition=COMPLETE_VOTES),
            report_for(2),  # cached before acquisition metadata existed
            report_for(3, acquisition={"acquisition_state": "partial", "failure_reasons": ["scan_budget_exhausted"]}),
        )
        catalog = [
            catalog_protocol("21/5", "pp-5", "2026-06-15"),
            catalog_protocol("21/4", "pp-4", "2026-06-14", xml=False),
            catalog_protocol("21/3", "pp-3", "2026-06-13"),
            catalog_protocol("21/2", "pp-2", "2026-06-12"),
            catalog_protocol("21/1", "pp-1", "2026-06-11"),
            catalog_protocol("20/9", "pp-old", "2020-01-01"),
        ]
        acquirable, waiting, vote_only, structural = build.incomplete_sitting_protocols(entries, catalog)
        self.assertEqual([p["dokumentnummer"] for p in acquirable], ["21/5", "21/3", "21/2"])
        self.assertEqual([p["dokumentnummer"] for p in waiting], ["21/4"])

    def test_with_votes_off_sittings_held_back_only_by_votes_are_skipped(self) -> None:
        entries = self.entries(
            report_for(1, acquisition=COMPLETE_VOTES),
            report_for(2),  # only its votes are unknown
            {**report_for(3, acquisition=COMPLETE_VOTES), "validation_summary": {}},  # speeches not parsed
        )
        catalog = [catalog_protocol(f"21/{n}", f"pp-{n}", f"2026-06-{10 + n:02d}") for n in (4, 3, 2, 1)]
        acquirable, _waiting, vote_only, _structural = build.incomplete_sitting_protocols(entries, catalog, votes=False)
        self.assertEqual([p["dokumentnummer"] for p in acquirable], ["21/4", "21/3"])
        self.assertEqual([p["dokumentnummer"] for p in vote_only], ["21/2"])
        acquirable, _waiting, vote_only, _structural = build.incomplete_sitting_protocols(entries, catalog)
        self.assertEqual([p["dokumentnummer"] for p in acquirable], ["21/4", "21/3", "21/2"])
        self.assertEqual(vote_only, [])

    def test_backfill_with_votes_off_says_what_it_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "site"
            for name in ("protocols", "data"):
                (output_dir / name).mkdir(parents=True)
            write_cached(output_dir, report_for(1, acquisition=COMPLETE_VOTES))
            write_cached(output_dir, report_for(2))
            catalog = [catalog_protocol("21/2", "pp-2", "2026-06-12"), catalog_protocol("21/1", "pp-1", "2026-06-11")]
            argv = ["build", "--api-key", "k", "--no-abgeordnetenwatch", "--no-persist", "--output-dir", str(output_dir),
                    "--backfill-incomplete", "--no-votes"]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(build, "fetch_protocols", return_value=catalog),
                mock.patch.object(build, "build_dossiers_with_progress", return_value=[]) as build_dossiers,
                mock.patch.object(build, "run_data_pipeline", return_value=(None, None, set(), "data/exports/", False)),
                mock.patch.object(build, "render_site", return_value=output_dir / "index.html"),
                mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr,
                mock.patch.object(sys, "stdout", new_callable=io.StringIO),
            ):
                code = build.main()
        self.assertEqual(code, 0, stderr.getvalue())
        self.assertEqual(build_dossiers.call_args.args[0], [])
        self.assertIn("skipping 1 sitting(s) held back only by votes", stderr.getvalue())
        self.assertIn("add --enrich votes", stderr.getvalue())

    def test_nothing_is_selected_when_every_sitting_is_complete(self) -> None:
        entries = self.entries(report_for(1, acquisition=COMPLETE_VOTES), report_for(2, acquisition=COMPLETE_VOTES))
        catalog = [catalog_protocol("21/2", "pp-2", "2026-06-12"), catalog_protocol("21/1", "pp-1", "2026-06-11")]
        self.assertEqual(build.incomplete_sitting_protocols(entries, catalog), ([], [], [], []))

    def test_backfill_incomplete_acquires_exactly_those_ignoring_detail_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "site"
            for name in ("protocols", "data"):
                (output_dir / name).mkdir(parents=True)
            write_cached(output_dir, report_for(1, acquisition=COMPLETE_VOTES))
            write_cached(output_dir, report_for(2))
            catalog = [
                catalog_protocol("21/4", "pp-4", "2026-06-14"),
                catalog_protocol("21/3", "pp-3", "2026-06-13", xml=False),
                catalog_protocol("21/2", "pp-2", "2026-06-12"),
                catalog_protocol("21/1", "pp-1", "2026-06-11"),
            ]
            argv = ["build", "--api-key", "k", "--no-abgeordnetenwatch", "--no-persist", "--output-dir", str(output_dir),
                    "--backfill-incomplete", "--detail-limit", "1"]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(build, "fetch_protocols", return_value=catalog),
                mock.patch.object(build, "build_dossiers_with_progress", return_value=[]) as build_dossiers,
                mock.patch.object(build, "run_data_pipeline", return_value=(None, None, set(), "data/exports/", False)),
                mock.patch.object(build, "render_site", return_value=output_dir / "index.html"),
                mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr,
                mock.patch.object(sys, "stdout", new_callable=io.StringIO),
            ):
                code = build.main()
        self.assertEqual(code, 0, stderr.getvalue())
        self.assertEqual([p["dokumentnummer"] for p in build_dossiers.call_args.args[0]], ["21/4", "21/2"])
        self.assertIn("[backfill] 2 incomplete or missing sitting(s) to acquire", stderr.getvalue())
        self.assertIn("1 not acquirable yet (DIP has no XML): 21/3", stderr.getvalue())

    def test_backfill_incomplete_cannot_be_combined_with_document_number_or_offline(self) -> None:
        for extra, message in (
            (["--document-number", "21/1"], "cannot be combined with --document-number"),
            (["--offline"], "needs the network"),
        ):
            with self.subTest(extra=extra), mock.patch.object(
                sys, "argv", ["build", "--backfill-incomplete", *extra]
            ), mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr, self.assertRaises(SystemExit):
                build.parse_args()
            self.assertIn(message, stderr.getvalue())


class IncompleteReportTests(StoreCase):
    """DX-B1: every build prints the incomplete weeks and months, the missing
    sittings and the exact backfill command."""

    def report_for_week(self, *, extra: tuple[str, ...] = ("21/50", "21/51"), completeness=None):
        seeded = self.seed(week_specs(10))
        listed = seeded["catalog_sittings"] + [
            {"document_number": number, "date": facts.date.fromisocalendar(2025, 7, 2 + offset).isoformat()}
            for offset, number in enumerate(extra)
        ]
        conn = self.writable()
        report = facts.compute_and_store(
            conn,
            facts.ALL_REGISTRY,
            completeness or seeded["completeness"],
            catalog=_facts_fixture.catalog_for(listed),
            built={"votes"},
            out=io.StringIO(),
        )
        catalog_protocols = [
            catalog_protocol(s["document_number"], f"c{i}", s["date"]) for i, s in enumerate(listed)
        ]
        return report, catalog_protocols

    def lines(self, report, catalog_protocols, **kwargs) -> list[str]:
        return build.format_incomplete_report(
            report,
            output_dir=Path(".context/dip-pulse-site"),
            catalog_protocols=catalog_protocols,
            vote_scan_pages=30,
            **kwargs,
        )

    def test_a_seeded_incomplete_week_is_named_with_its_missing_sittings_and_the_command(self) -> None:
        report, catalog_protocols = self.report_for_week()
        text = "\n".join(self.lines(report, catalog_protocols))
        self.assertIn("warning: [facts] 1 weeks and 1 months are incomplete", text)
        self.assertIn("2 listed sittings are not in the store: 21/50, 21/51", text)
        self.assertIn("incomplete weeks: 2025-W07 (missing 21/50, 21/51)", text)
        self.assertIn(
            "Fix: python3 scripts/build_dip_pulse_site.py --output-dir .context/dip-pulse-site --backfill-incomplete",
            text,
        )
        self.assertIn("(acquires 2 sittings; every other cached dossier is kept)", text)
        self.assertIn("Docs: README.md#backfill-incomplete-sittings", text)

    def test_sittings_dip_has_no_xml_for_are_named_and_left_out_of_the_fix(self) -> None:
        report, catalog_protocols = self.report_for_week()
        for protocol in catalog_protocols:
            if protocol["dokumentnummer"] == "21/51":
                protocol.pop("fundstelle", None)
        text = "\n".join(self.lines(report, catalog_protocols))
        self.assertIn("not acquirable yet (DIP has no XML for them): 21/51", text)
        self.assertIn("(acquires 1 sittings;", text)

    def test_only_sittings_without_xml_left_means_no_command(self) -> None:
        report, catalog_protocols = self.report_for_week(extra=("21/51",))
        for protocol in catalog_protocols:
            protocol.pop("fundstelle", None)
        text = "\n".join(self.lines(report, catalog_protocols))
        self.assertIn("Fix: none available now", text)
        self.assertNotIn("--backfill-incomplete", text)

    def test_incompletely_acquired_sittings_are_counted_by_reason(self) -> None:
        seeded = self.seed(week_specs(10))
        completeness = {n: dict(state) for n, state in seeded["completeness"].items()}
        for number in ("21/3", "21/4"):
            completeness[number]["votes"] = False
            completeness[number]["reasons"] = {"votes": "votes partial (scan_budget_exhausted)"}
        completeness["21/6"]["votes"] = False
        completeness["21/6"]["reasons"] = {"votes": "no vote acquisition metadata (report predates it)"}
        conn = self.writable()
        report = facts.compute_and_store(
            conn, facts.ALL_REGISTRY, completeness, catalog=seeded["catalog"], built={"votes"}, out=io.StringIO()
        )
        text = "\n".join(self.lines(report, []))
        self.assertIn("3 sittings are in the store but not fully acquired:", text)
        self.assertIn("votes: votes partial (scan_budget_exhausted) (2×)", text)
        self.assertIn("votes: no vote acquisition metadata (report predates it) (1×)", text)
        # A budget-exhausted scan is only fixed by a wider scan.
        self.assertIn("--backfill-incomplete --vote-scan-pages 60", text)

    def test_the_printed_fix_lifts_a_vote_veto_instead_of_repeating_it(self) -> None:
        seeded = self.seed(week_specs(10))
        completeness = {n: {**st, "votes": False, "reasons": {"votes": "votes not_requested"}} for n, st in seeded["completeness"].items()}
        conn = self.writable()
        report = facts.compute_and_store(
            conn, facts.ALL_REGISTRY, completeness, catalog=seeded["catalog"], built={"votes"}, out=io.StringIO()
        )
        off = "\n".join(build.format_incomplete_report(
            report, output_dir=Path("out"), catalog_protocols=[], vote_scan_pages=0))
        self.assertIn("--backfill-incomplete --enrich votes", off)
        self.assertNotIn("--vote-scan-pages", off)
        on = "\n".join(build.format_incomplete_report(
            report, output_dir=Path("out"), catalog_protocols=[], vote_scan_pages=30))
        self.assertNotIn("--enrich votes", on)

    def test_run_data_pipeline_passes_the_real_scan_setting_not_a_default(self) -> None:
        args = SimpleNamespace(no_persist=False, vote_scan_pages=0, data_base_url=None, data_manifest=None,
                               data_license=None, data_issues_url=None, force_export=False)
        seeded = self.seed(week_specs(3))
        with (
            mock.patch.object(build, "export_distribution_data", return_value={}),
            mock.patch.object(build, "collect_bill_pages", return_value=[]),
            mock.patch.object(build, "derive_feature_readiness", return_value={}),
            mock.patch.object(build, "run_facts_engine", return_value={}),
            mock.patch.object(build, "format_incomplete_report", return_value=[]) as fmt,
        ):
            build.run_data_pipeline(
                args=args, output_dir=Path(self.tmp.name), database_path=self.path, entries=[], protocols=[],
                abg_mps=[], mp_lookup={}, catalog=seeded["catalog"],
            )
        self.assertEqual(fmt.call_args.kwargs["vote_scan_pages"], 0)

    def test_a_complete_store_prints_nothing(self) -> None:
        seeded = self.seed(week_specs(10))
        conn = self.writable()
        report = facts.compute_and_store(
            conn, facts.ALL_REGISTRY, seeded["completeness"], catalog=seeded["catalog"], built={"votes"}, out=io.StringIO()
        )
        self.assertEqual(self.lines(report, []), [])

    def test_long_lists_are_cut_to_the_newest_periods(self) -> None:
        seeded = self.seed(week_specs(10))
        completeness = {n: {**state, "votes": False, "reasons": {"votes": "votes not_requested"}} for n, state in seeded["completeness"].items()}
        conn = self.writable()
        report = facts.compute_and_store(
            conn, facts.ALL_REGISTRY, completeness, catalog=seeded["catalog"], built={"votes"}, out=io.StringIO()
        )
        text = "\n".join(self.lines(report, [], shown_periods=3))
        self.assertIn("incomplete weeks (newest 3 of 10):", text)
        self.assertIn("2025-W12", text)
        self.assertNotIn("2025-W03 (", text)

    def test_run_data_pipeline_prints_the_report_on_every_build(self) -> None:
        report, catalog_protocols = self.report_for_week()
        entries = [{"report": {"protocol": {"dokumentnummer": n}, "validation_summary": {"xml_speech_count": 3},
                               "acquisition": {"votes": COMPLETE_VOTES}}} for n in self.seeded["completeness"]]
        args = SimpleNamespace(no_persist=False, vote_scan_pages=None, data_base_url=None, data_manifest=None,
                               data_license=None, data_issues_url=None, force_export=False)
        stderr = io.StringIO()
        listed = self.seeded["catalog_sittings"] + [{"document_number": "21/50", "date": "2025-02-12"}]
        with (
            mock.patch.object(build, "export_distribution_data", return_value={}),
            mock.patch.object(build, "collect_bill_pages", return_value=[]),
            mock.patch.object(build, "derive_feature_readiness", return_value={}),
            mock.patch.object(sys, "stderr", stderr),
        ):
            build.run_data_pipeline(
                args=args,
                output_dir=Path(self.tmp.name),
                database_path=self.path,
                entries=entries,
                protocols=catalog_protocols,
                abg_mps=[],
                mp_lookup={},
                catalog=_facts_fixture.catalog_for(listed),
            )
        output = stderr.getvalue()
        self.assertIn("warning: [facts]", output)
        self.assertIn("--output-dir " + self.tmp.name, output)
        self.assertIn("--backfill-incomplete", output)


class WithheldCellNamesTheMissingSittingTests(StoreCase):
    def test_an_incomplete_week_says_which_sitting_is_missing(self) -> None:
        seeded = self.seed(week_specs(10))
        listed = seeded["catalog_sittings"] + [{"document_number": "21/50", "date": "2025-02-12"}]
        conn = self.writable()
        facts.compute_and_store(
            conn, facts.REGISTRY, seeded["completeness"], catalog=_facts_fixture.catalog_for(listed), built={"votes"}, out=io.StringIO()
        )
        output_dir = Path(self.tmp.name) / "site"
        (output_dir / "data").mkdir(parents=True)
        (output_dir / "data" / facts.CATALOG_FILENAME).write_text(
            json.dumps({"authoritative": True, "protocols": [
                {"dokumentnummer": s["document_number"], "datum": s["date"]} for s in listed
            ]}),
            encoding="utf-8",
        )
        entries = [
            {"report": {"protocol": {"dokumentnummer": n}, "validation_summary": {"xml_speech_count": 3},
                        "acquisition": {"votes": COMPLETE_VOTES}}}
            for n in seeded["completeness"]
        ]
        build.write_facts_pages(output_dir, self.path, False, {}, set(seeded["completeness"]), set(), None, entries)
        week = (output_dir / "fakt" / "2025-W07.html").read_text(encoding="utf-8")
        self.assertIn("unvollständig erfasst: Sitzung 21/50 (2025-02-12) fehlt", week)
        archive = (output_dir / "fakt" / "index.html").read_text(encoding="utf-8")
        # The archive keeps the cell short and puts the sitting in a tooltip.
        self.assertIn('title="Sitzung 21/50 (2025-02-12) fehlt"', archive)
        self.assertNotIn("unvollständig erfasst: Sitzung", archive)

    def test_without_a_cached_catalog_the_cell_says_why_nothing_can_be_judged(self) -> None:
        seeded = self.seed(week_specs(10))
        conn = self.writable()
        facts.compute_and_store(
            conn, facts.REGISTRY, seeded["completeness"], catalog=None, built={"votes"}, out=io.StringIO()
        )
        output_dir = Path(self.tmp.name) / "site2"
        output_dir.mkdir()
        build.write_facts_pages(output_dir, self.path, False, {}, set(seeded["completeness"]), set(), None, [])
        week = (output_dir / "fakt" / "2025-W07.html").read_text(encoding="utf-8")
        self.assertIn("kein vollständiger DIP-Katalog zwischengespeichert", week)

    def test_the_status_text_stays_short_without_a_note(self) -> None:
        row = {"metric_id": "laengste-rede", "complete": 0, "withheld": facts.WITHHELD_NO_OBSERVATION, "publishable": 0}
        self.assertEqual(build._fact_status_text(row), ("unvollständig erfasst", None, False))
        row["gap_note"] = "Sitzung 21/50 (2025-02-12) fehlt"
        self.assertEqual(
            build._fact_status_text(row), ("unvollständig erfasst: Sitzung 21/50 (2025-02-12) fehlt", None, False)
        )
        self.assertEqual(build._fact_status_text(row, with_note=False), ("unvollständig erfasst", None, False))

    def test_gap_note_names_two_sittings_and_counts_the_rest(self) -> None:
        gaps = [
            {"document_number": "21/1", "date": "2025-01-01", "reason": "not_persisted"},
            {"document_number": "21/2", "date": "2025-01-02", "reason": "no_report"},
            {"document_number": "21/3", "date": "2025-01-03", "reason": "votes partial"},
            {"document_number": "21/4", "date": "2025-01-04", "reason": "not_persisted"},
        ]
        self.assertEqual(
            facts.gap_note(gaps, "votes"),
            "Sitzung 21/1 (2025-01-01) fehlt, Sitzung 21/2: kein Bericht, und 2 weitere",
        )
        self.assertEqual(facts.gap_note(gaps[2:3], "votes"), "Sitzung 21/3: Abstimmungen nicht vollständig erfasst")
        self.assertEqual(facts.gap_note(gaps[2:3], "speeches"), "Sitzung 21/3: Reden nicht erfasst")


if __name__ == "__main__":
    unittest.main()


class GapPrimitiveTests(unittest.TestCase):
    """The pure functions behind the incomplete report and the withheld-cell notes."""

    PERSISTED = [
        {"document_number": "21/1", "date": "2025-01-02"},
        {"document_number": "21/2", "date": "2025-01-09"},
    ]
    LISTED = PERSISTED + [{"document_number": "21/3", "date": "2025-01-16"}]

    @staticmethod
    def state(votes: bool, speeches: bool = True, reason: str | None = None) -> dict:
        return {"votes": votes, "speeches": speeches, "reasons": {"votes": reason, "speeches": None}}

    def completeness(self) -> dict:
        return {"21/1": self.state(False, reason="votes partial (scan_budget_exhausted)")}

    def test_sitting_gaps_name_missing_unreported_and_partial_sittings_oldest_first(self) -> None:
        catalog = facts.sitting_catalog(self.LISTED, authoritative=True)
        gaps = facts.sitting_gaps(self.PERSISTED, self.completeness(), catalog)
        self.assertEqual(list(gaps), ["21/1", "21/2", "21/3"])
        self.assertEqual(gaps["21/1"]["reasons"], {"votes": "votes partial (scan_budget_exhausted)"})
        self.assertEqual(gaps["21/2"]["reasons"], {"dossier": "no_report"})
        self.assertEqual(gaps["21/3"], {"date": "2025-01-16", "reasons": {"dossier": "not_persisted"}})

    def test_without_an_authoritative_catalog_nothing_can_be_listed(self) -> None:
        for catalog in (None, facts.sitting_catalog(self.LISTED, authoritative=False)):
            with self.subTest(catalog=catalog):
                self.assertEqual(facts.sitting_gaps(self.PERSISTED, self.completeness(), catalog), {})
                self.assertEqual(facts.incomplete_periods(self.PERSISTED, self.completeness(), catalog), [])

    def test_a_sitting_without_a_dossier_is_named_once_under_dossier_in_every_period(self) -> None:
        catalog = facts.sitting_catalog(self.LISTED, authoritative=True)
        periods = facts.incomplete_periods(self.PERSISTED, self.completeness(), catalog)
        self.assertEqual({p["period_kind"] for p in periods}, {"week", "month"})
        for period in periods:
            missing = [s for s in period["sittings"] if s["document_number"] == "21/3"]
            if missing:
                self.assertEqual(missing[0]["reasons"], {"dossier": "not_persisted"}, period["period_key"])
        month = next(p for p in periods if p["period_kind"] == "month")
        self.assertEqual([s["document_number"] for s in month["sittings"]], ["21/1", "21/2", "21/3"])

    def test_gap_notes_cover_every_domain_and_period_or_say_why_none_can_be_judged(self) -> None:
        catalog = facts.sitting_catalog(self.LISTED, authoritative=True)
        notes = facts.gap_notes(self.PERSISTED, self.completeness(), catalog)
        week_key = facts.build_periods(self.PERSISTED, catalog)[0][0].period_key
        self.assertIn("Sitzung 21/1: Abstimmungen nicht vollständig erfasst", notes[("week", week_key, "votes")])
        self.assertNotIn(("week", week_key, "speeches"), notes)
        blind = facts.gap_notes(self.PERSISTED, self.completeness(), None)
        self.assertTrue(blind)
        self.assertTrue(all("DIP-Katalog" in note for note in blind.values()))
        self.assertEqual({domain for _kind, _key, domain in blind}, {"votes", "speeches"})

    def test_a_period_only_the_catalog_knows_takes_its_date_and_newest_wahlperiode_from_the_catalog(self) -> None:
        catalog = facts.sitting_catalog(
            self.PERSISTED
            + [
                {"document_number": "20/300", "date": "2025-03-04"},
                {"document_number": "21/9", "date": "2025-03-05"},
            ],
            authoritative=True,
        )
        weeks, months = facts.build_periods(self.PERSISTED, catalog)
        week = next(w for w in weeks if not w.protocols)
        month = next(m for m in months if not m.protocols)
        self.assertEqual((week.wahlperiode, month.wahlperiode), (21, 21))
        self.assertEqual(week.first_date, date(2025, 3, 4))
        self.assertEqual(month.first_date, date(2025, 3, 4))
        self.assertFalse(facts.week_is_complete(week, {}, "votes"))

    def test_sitting_catalog_dedups_by_number_reads_both_spellings_and_counts_the_unplaceable(self) -> None:
        catalog = facts.sitting_catalog(
            [
                {"dokumentnummer": " 21/2 ", "datum": "2025-01-09T00:00:00"},
                {"document_number": "21/2", "date": "2025-01-09"},
                {"dokumentnummer": "21/1", "datum": "2025-01-02"},
                {"dokumentnummer": "21/4", "datum": "kein Datum"},
                {"dokumentnummer": "", "datum": "2025-01-10"},
            ],
            authoritative=True,
        )
        self.assertEqual([s["document_number"] for s in catalog.sittings], ["21/1", "21/2"])
        self.assertEqual(catalog.unusable, 2)
