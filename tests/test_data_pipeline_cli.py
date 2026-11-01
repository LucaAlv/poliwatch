"""Coverage for the CLI/pipeline glue added around the Daten export:

resolve_data_export_options() (CLI > env > default precedence),
resolve_commit(), load_remote_manifest(), the new parse_args() validation
branches, run_data_pipeline() (the function both the offline and the online
path in main() call after their respective --week checks), and the
renamed "Daten" label wired into the page-specific links of render_overview,
render_catalog_page, render_sources_page and the render_landing_page area
card (the ship-audit REGRESSION RULE: nav label rename + render_site's
manifest=None branch).
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import _support  # noqa: F401
import _daten_fixture
import build_dip_pulse_site as b
import facts
import persist_dip_pulse_store as pulse_store


def _pipeline_args(**overrides) -> SimpleNamespace:
    base = dict(
        data_base_url=None,
        data_manifest=None,
        force_export=False,
        data_license=None,
        data_issues_url=None,
        no_persist=False,
        offline=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class ResolveDataExportOptionsTests(unittest.TestCase):
    def test_cli_flags_take_precedence_over_env(self) -> None:
        args = _pipeline_args(
            data_base_url="https://cli.example/",
            data_manifest="cli-manifest.json",
            data_license="CLI licence",
            data_issues_url="https://cli.example/issues",
        )
        env = {
            "BUNDESTAG_PULSE_DATA_BASE_URL": "https://env.example/",
            "BUNDESTAG_PULSE_DATA_MANIFEST": "env-manifest.json",
            "BUNDESTAG_PULSE_DATA_LICENSE": "ENV licence",
            "BUNDESTAG_PULSE_DATA_ISSUES_URL": "https://env.example/issues",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            result = b.resolve_data_export_options(args)
        self.assertEqual(
            result,
            ("https://cli.example/", "cli-manifest.json", "CLI licence", "https://cli.example/issues"),
        )

    def test_env_fallback_used_when_cli_absent(self) -> None:
        args = _pipeline_args()
        env = {
            "BUNDESTAG_PULSE_DATA_BASE_URL": "https://env.example/",
            "BUNDESTAG_PULSE_DATA_MANIFEST": "env-manifest.json",
            "BUNDESTAG_PULSE_DATA_LICENSE": "ENV licence",
            "BUNDESTAG_PULSE_DATA_ISSUES_URL": "https://env.example/issues",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            result = b.resolve_data_export_options(args)
        self.assertEqual(
            result,
            ("https://env.example/", "env-manifest.json", "ENV licence", "https://env.example/issues"),
        )

    def test_issues_url_with_an_unsupported_scheme_is_rejected(self) -> None:
        for bad in ("javascript:alert(1)", "ftp://x", "  ", "data:text/html,x"):
            with self.subTest(url=bad):
                args = _pipeline_args(data_issues_url=bad)
                if bad.strip():
                    with self.assertRaises(ValueError):
                        b.resolve_data_export_options(args)
                else:
                    self.assertIsNone(b.resolve_data_export_options(args)[3])
        for ok in ("https://example.org/issues", "http://example.org", "mailto:x@example.org", "/issues.html"):
            with self.subTest(url=ok):
                self.assertEqual(b.resolve_data_export_options(_pipeline_args(data_issues_url=ok))[3], ok)

    def test_defaults_when_neither_cli_nor_env_set(self) -> None:
        # Covers both a fully-populated-but-None namespace and a bare
        # SimpleNamespace() lacking these attributes entirely - main() is
        # tested elsewhere with such a bare stub that predates these flags,
        # so resolve_data_export_options must not raise via getattr().
        env_keys = (
            "BUNDESTAG_PULSE_DATA_BASE_URL",
            "BUNDESTAG_PULSE_DATA_MANIFEST",
            "BUNDESTAG_PULSE_DATA_LICENSE",
            "BUNDESTAG_PULSE_DATA_ISSUES_URL",
        )
        for args in (_pipeline_args(), SimpleNamespace()):
            with self.subTest(args=args):
                with mock.patch.dict(os.environ, {}, clear=False):
                    for key in env_keys:
                        os.environ.pop(key, None)
                    result = b.resolve_data_export_options(args)
                self.assertEqual(result, ("data/exports/", None, "", None))


class ResolveCommitTests(unittest.TestCase):
    # Value: protects=the site build cites the revision of its own checkout through build_revision; fails_when=resolve_commit stops delegating or points at another directory; why_new=the git logic moved to scripts/build_revision.py (tested there against real git); seam=none; no_claim=git behaviour
    def test_delegates_to_build_revision_for_this_checkout(self) -> None:
        with mock.patch.object(b.build_revision, "resolve_commit", return_value="0123456789ab") as resolve:
            self.assertEqual(b.resolve_commit(), "0123456789ab")
        resolve.assert_called_once_with(b.REPO_ROOT)


class LoadRemoteManifestTests(unittest.TestCase):
    def test_returns_the_parsed_json_on_success(self) -> None:
        payload = json.dumps({"generation": "g-abc"}).encode("utf-8")
        response = mock.MagicMock()
        response.read.return_value = payload
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        with mock.patch.object(b.urllib.request, "urlopen", return_value=response):
            manifest = b.load_remote_manifest("https://example.org/datenstand.json")
        self.assertEqual(manifest, {"generation": "g-abc"})

    def test_raises_runtime_error_on_network_failure(self) -> None:
        with mock.patch.object(
            b.urllib.request, "urlopen", side_effect=urllib.error.URLError("no route")
        ):
            with self.assertRaises(RuntimeError) as ctx:
                b.load_remote_manifest("https://example.org/datenstand.json")
        self.assertIn("could not fetch", str(ctx.exception))

    def test_raises_runtime_error_on_invalid_json(self) -> None:
        response = mock.MagicMock()
        response.read.return_value = b"{not json"
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        with mock.patch.object(b.urllib.request, "urlopen", return_value=response):
            with self.assertRaises(RuntimeError) as ctx:
                b.load_remote_manifest("https://example.org/datenstand.json")
        self.assertIn("did not return valid JSON", str(ctx.exception))

    def test_refuses_a_response_larger_than_the_cap(self) -> None:
        response = mock.MagicMock()
        response.read.return_value = b"x" * (b.MAX_REMOTE_MANIFEST_BYTES + 1)
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        with mock.patch.object(b.urllib.request, "urlopen", return_value=response):
            with self.assertRaises(RuntimeError) as ctx:
                b.load_remote_manifest("https://example.org/datenstand.json")
        self.assertIn("exceeds 32 MB", str(ctx.exception))
        response.read.assert_called_once_with(b.MAX_REMOTE_MANIFEST_BYTES + 1)


class ParseArgsValidationTests(unittest.TestCase):
    def test_force_export_with_no_persist_is_rejected(self) -> None:
        with (
            mock.patch.object(sys, "argv", ["build", "--force-export", "--no-persist"]),
            mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr,
        ):
            with self.assertRaises(SystemExit) as ctx:
                b.parse_args()
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("--force-export cannot be combined with --no-persist", stderr.getvalue())

    # Value: protects=--fetch-xml downloads and exits, so it refuses --offline, --repersist and --backfill-incomplete with a parser error naming it, and alone it parses;
    #   fails_when=parse_args drops one of the three refusals (the run would silently ignore the other flag) or also refuses --fetch-xml alone;
    #   why_new=the fetch-xml tests call main() with --fetch-xml alone; the flag combinations are a separate parse_args branch; seam=none
    def test_fetch_xml_cannot_be_combined_with_offline_repersist_or_backfill_incomplete(self) -> None:
        for other in (["--offline"], ["--offline", "--repersist"], ["--backfill-incomplete"]):
            with self.subTest(other=other):
                with (
                    mock.patch.object(sys, "argv", ["build", "--fetch-xml", *other]),
                    mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr,
                ):
                    with self.assertRaises(SystemExit) as ctx:
                        b.parse_args()
                self.assertEqual(ctx.exception.code, 2)
                # The usage line lists every option; the error itself names --fetch-xml.
                self.assertIn("error: --fetch-xml downloads the missing XML files and exits", stderr.getvalue())
        with mock.patch.object(sys, "argv", ["build", "--fetch-xml"]):
            self.assertTrue(b.parse_args().fetch_xml)

    def test_offline_with_a_remote_data_manifest_is_rejected(self) -> None:
        with (
            mock.patch.object(
                sys,
                "argv",
                ["build", "--offline", "--data-manifest", "https://example.org/datenstand.json"],
            ),
            mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr,
        ):
            with self.assertRaises(SystemExit) as ctx:
                b.parse_args()
        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("cannot fetch --data-manifest", stderr.getvalue())

    def test_offline_with_a_local_data_manifest_path_is_accepted(self) -> None:
        with mock.patch.object(sys, "argv", ["build", "--offline", "--data-manifest", "local/datenstand.json"]):
            args = b.parse_args()
        self.assertEqual(args.data_manifest, "local/datenstand.json")

    def test_data_tag_flag_is_parsed(self) -> None:
        with mock.patch.object(sys, "argv", ["build", "--data-tag", "2026.11.01"]):
            self.assertEqual(b.parse_args().data_tag, "2026.11.01")
        with mock.patch.object(sys, "argv", ["build"]):
            self.assertIsNone(b.parse_args().data_tag)
        with mock.patch.object(sys, "argv", ["build", "--data-tag", "local"]):
            self.assertEqual(b.parse_args().data_tag, "local")

    # Value: protects=--data-tag takes only "local" or a release version, so the site and DATA.md never say "Release <typo>"; fails_when=any file-name-safe token passes as a release tag; why_new=/ship red team 2026-10-31: --data-tag draft labelled the export "Release draft"; seam=none; no_claim=export content
    def test_data_tag_must_be_local_or_a_release_version(self) -> None:
        for bad in ("draft", "v1", "2026.13.01", "2026.11.1"):
            with self.subTest(tag=bad), mock.patch.object(sys, "argv", ["build", "--data-tag", bad]), contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit):
                    b.parse_args()
                self.assertIn("--data-tag", err.getvalue())

    # Value: protects=a release --data-tag cannot be combined with --no-persist or --data-manifest, which skip the export; fails_when=the build accepts them and exits 0 with no export carrying the tag; why_new=release item 10c (P1); seam=parse_args; no_claim=the local tag
    def test_a_release_tag_refuses_the_flags_that_skip_the_export(self) -> None:
        for extra in (["--no-persist"], ["--data-manifest", "elsewhere/datenstand.json"]):
            argv = ["build", "--data-tag", "2026.11.01", *extra]
            with self.subTest(extra=extra[0]), mock.patch.object(sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit):
                    b.parse_args()
                self.assertIn(extra[0], err.getvalue())
        with mock.patch.object(sys, "argv", ["build", "--data-tag", "local", "--no-persist"]), contextlib.redirect_stderr(io.StringIO()):
            self.assertTrue(b.parse_args().no_persist)

    def test_data_base_url_with_no_persist_warns_but_does_not_exit(self) -> None:
        with (
            mock.patch.object(sys, "argv", ["build", "--no-persist", "--data-base-url", "https://cdn.example/"]),
            mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr,
        ):
            args = b.parse_args()
        self.assertEqual(args.data_base_url, "https://cdn.example/")
        self.assertIn("warning: --data-base-url has no effect with --no-persist", stderr.getvalue())


class RunDataPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.output_dir = self.tmp / "site"
        (self.output_dir / "data").mkdir(parents=True)
        self.database_path = self.output_dir / "data" / "bundestag-pulse.sqlite"
        _daten_fixture.seed_store(self.database_path)
        conn = pulse_store.connect(self.database_path)
        try:
            self.mps, self.lookup = b.collect_abgeordnete(conn)
        finally:
            conn.close()

    def _run(self, **overrides):
        args = _pipeline_args(**overrides)
        return b.run_data_pipeline(
            args=args,
            output_dir=self.output_dir,
            database_path=self.database_path,
            entries=[],
            protocols=[],
            abg_mps=self.mps,
            mp_lookup=self.lookup,
            catalog=None,
        )

    def test_exports_when_the_store_exists_and_not_no_persist(self) -> None:
        manifest, data_export_error, bill_slugs, data_base_url, is_remote = self._run()
        self.assertIsNotNone(manifest)
        self.assertIsNone(data_export_error)
        self.assertEqual(bill_slugs, set())
        self.assertEqual(data_base_url, "data/exports/")
        self.assertFalse(is_remote)
        self.assertTrue((self.output_dir / "data" / "exports" / "datenstand.json").exists())

    def test_the_facts_engine_runs_before_the_export(self) -> None:
        # D1A/D3A: the engine sits between the finalised store and the export,
        # so the three tables are part of what the export copies and hashes.
        self._run()
        conn = pulse_store.connect(self.database_path)
        try:
            self.assertTrue(facts.tables_exist(conn))
            self.assertEqual(
                [metric["id"] for metric in facts.load_metrics(conn)],
                [metric["id"] for metric in facts.ALL_REGISTRY],
            )
            self.assertTrue(facts.load_facts(conn))
        finally:
            conn.close()

    def test_no_persist_leaves_the_store_without_facts_tables(self) -> None:
        # D3A: --no-persist writes nothing; the pages render whatever the store
        # already holds, which here is nothing.
        b.run_data_pipeline(
            args=_pipeline_args(no_persist=True),
            output_dir=self.output_dir,
            database_path=self.database_path,
            entries=[],
            protocols=[],
            abg_mps=self.mps,
            mp_lookup=self.lookup,
            catalog=None,
        )
        conn = pulse_store.connect(self.database_path)
        try:
            self.assertFalse(facts.tables_exist(conn))
            self.assertEqual(facts.load_facts(conn), [])
        finally:
            conn.close()

    def test_skips_export_when_no_persist_or_the_database_is_missing(self) -> None:
        missing_db = self.output_dir / "data" / "does-not-exist.sqlite"
        cases = {
            "no_persist": dict(
                args=_pipeline_args(no_persist=True), database_path=self.database_path
            ),
            "missing_database": dict(args=_pipeline_args(), database_path=missing_db),
        }
        for label, kwargs in cases.items():
            with self.subTest(case=label):
                with mock.patch.object(b, "export_distribution_data") as export_mock:
                    manifest, data_export_error, _bill_slugs, _base, is_remote = b.run_data_pipeline(
                        args=kwargs["args"],
                        output_dir=self.output_dir,
                        database_path=kwargs["database_path"],
                        entries=[],
                        protocols=[],
                        abg_mps=self.mps,
                        mp_lookup=self.lookup,
                        catalog=None,
                    )
                export_mock.assert_not_called()
                self.assertIsNone(manifest)
                self.assertIsNone(data_export_error)
                self.assertFalse(is_remote)

    def _override_manifest(self, **changes) -> Path:
        # A real manifest (exported once into a scratch dir) with a distinct
        # tag so the override is recognisable; shape-valid by construction.
        scratch = self.tmp / "scratch-exports"
        with mock.patch.object(b.build_revision, "authored_inputs_problem", return_value=None):
            exported = b.export_distribution_data(
                self.database_path, scratch, mp_lookup=self.lookup, tag="override", commit="0123456789ab"
            )
        exported.update(changes)
        override_path = self.tmp / "override-manifest.json"
        override_path.write_text(json.dumps(exported), encoding="utf-8")
        return override_path

    def test_local_data_manifest_overrides_and_skips_the_export(self) -> None:
        override_path = self._override_manifest()
        with mock.patch.object(b, "export_distribution_data") as export_mock:
            manifest, _data_export_error, _bill_slugs, _base, is_remote = self._run(data_manifest=str(override_path))
        export_mock.assert_not_called()
        self.assertEqual(manifest["tag"], "override")
        self.assertFalse(is_remote)

    # Value: protects=--data-tag reaches the export as its tag and --data-tag-less builds stay local; fails_when=the tag is dropped, or a release tag is exported with a revision other than resolve_commit's; why_new=no production caller passed a tag before the release script; seam=none; no_claim=export content
    def test_data_tag_becomes_the_export_tag_and_defaults_to_local(self) -> None:
        for given, expected in ((None, "local"), ("2026.11.01", "2026.11.01")):
            with self.subTest(tag=given), mock.patch.object(b, "export_distribution_data", side_effect=b.DataExportUnavailable("stop")) as export_mock, mock.patch.object(b, "resolve_commit", return_value="0123456789ab"):
                if given is None:
                    self._run(data_tag=given)
                else:
                    with self.assertRaises(RuntimeError):
                        self._run(data_tag=given)
            self.assertEqual(export_mock.call_args.kwargs["tag"], expected)
            self.assertEqual(export_mock.call_args.kwargs["commit"], "0123456789ab")

    # Value: protects=a release --data-tag that exports nothing (store missing, old SQLite, a $BUNDESTAG_PULSE_DATA_MANIFEST override) stops the build instead of exiting 0 beside an older release-tagged export; fails_when=any of the three is reported as a warning and the build succeeds; why_new=release item 10c (P1), reachable once --publish opens; seam=run_data_pipeline; no_claim=the local tag (unchanged: a warning)
    def test_a_release_tag_that_exports_nothing_stops_the_build(self) -> None:
        missing_db = self.output_dir / "data" / "does-not-exist.sqlite"
        with self.assertRaisesRegex(RuntimeError, "release 2026.11.01 was not exported: there is no store"):
            b.run_data_pipeline(
                args=_pipeline_args(data_tag="2026.11.01"), output_dir=self.output_dir, database_path=missing_db,
                entries=[], protocols=[], abg_mps=self.mps, mp_lookup=self.lookup, catalog=None,
            )
        with mock.patch.object(b, "export_distribution_data", side_effect=b.DataExportUnavailable("SQLite too old")):
            with self.assertRaisesRegex(RuntimeError, "release 2026.11.01 was not exported: SQLite too old"):
                self._run(data_tag="2026.11.01")
        override_path = self._override_manifest()
        with mock.patch.dict(os.environ, {"BUNDESTAG_PULSE_DATA_MANIFEST": str(override_path)}), mock.patch.object(b, "export_distribution_data") as export_mock:
            with self.assertRaisesRegex(RuntimeError, "BUNDESTAG_PULSE_DATA_MANIFEST"):
                self._run(data_tag="2026.11.01")
        export_mock.assert_not_called()

    def test_force_export_still_exports_under_a_data_manifest_override(self) -> None:
        override_path = self._override_manifest()
        manifest, _data_export_error, _bill_slugs, _base, _remote = self._run(
            data_manifest=str(override_path), force_export=True
        )
        self.assertEqual(manifest["tag"], "override")
        self.assertTrue((self.output_dir / "data" / "exports" / "datenstand.json").exists())

    def test_wrong_shaped_data_manifest_fails_with_a_named_error(self) -> None:
        cases = {
            "empty object": {},
            "files empty": {"files": []},
            "path in file name": {"files": [{"name": "../x.gz", "bytes": 1, "unpacked_bytes": 1, "sha256": "a"}]},
            "bad generation": {"generation": "../../etc"},
            # re.match's $ also matches before a final newline, which would split the page's curl line.
            "generation with trailing newline": {"generation": "g-0123456789ab\n"},
            "not an object": [],
        }
        for label, payload in cases.items():
            with self.subTest(case=label):
                if isinstance(payload, dict) and label != "empty object":
                    full = json.loads(self._override_manifest().read_text(encoding="utf-8"))
                    full.update(payload)
                    payload = full
                override_path = self.tmp / f"bad-{label.replace(' ', '-')}.json"
                override_path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(RuntimeError) as ctx:
                    self._run(data_manifest=str(override_path))
                self.assertIn("--data-manifest", str(ctx.exception))
                self.assertIn(str(override_path), str(ctx.exception))

    # Value: protects=an override manifest can only show this build's recipes, with this build's SQL, next to its rows; fails_when=validate_manifest accepts an unknown recipe id, altered SQL (e.g. a sqlite3 dot-command the copy button would paste), a missing recipe or a reordered list, or a recipe without empty_reason; why_new=TODOS "Validate remote-manifest recipes before showing their SQL"; seam=none
    def test_an_override_with_other_recipes_fails_naming_the_recipe(self) -> None:
        full = json.loads(self._override_manifest().read_text(encoding="utf-8"))
        recipes = full["recipes"]
        cases = {
            "unknown id": ([{**recipes[0], "id": "r9-erfunden"}, *recipes[1:]], "'r9-erfunden' is not a recipe of this build"),
            "altered sql": (
                [{**recipes[0], "sql": recipes[0]["sql"] + "\n.shell rm -rf ~"}, *recipes[1:]],
                f"({recipes[0]['id']}) SQL differs from this build's",
            ),
            "missing recipe": (recipes[1:], "differ from this build's"),
            "swapped order": ([recipes[1], recipes[0], *recipes[2:]], "differ from this build's"),
            "empty_reason not text": ([{**recipes[0], "empty_reason": 5}, *recipes[1:]], "empty_reason"),
            "row not an object": ([{**recipes[0], "rows": [[1, 2]]}, *recipes[1:]], "a list of objects"),
        }
        for label, (changed, message) in cases.items():
            with self.subTest(case=label):
                override_path = self.tmp / f"recipes-{label.replace(' ', '-')}.json"
                override_path.write_text(json.dumps({**full, "recipes": changed}), encoding="utf-8")
                with self.assertRaises(RuntimeError) as ctx:
                    self._run(data_manifest=str(override_path))
                self.assertIn("is not a usable Daten manifest", str(ctx.exception))
                self.assertIn(message, str(ctx.exception))
        retitled = self.tmp / "recipes-retitled.json"
        retitled.write_text(json.dumps({**full, "recipes": [{**recipes[0], "title": "Anders"}, *recipes[1:]]}), encoding="utf-8")
        manifest, *_ = self._run(data_manifest=str(retitled))
        self.assertEqual(manifest["recipes"][0]["title"], "Anders")

    def test_changing_the_issues_url_reexports(self) -> None:
        first, *_ = self._run(data_issues_url="https://example.org/a")
        reused, *_ = self._run(data_issues_url="https://example.org/a")
        self.assertEqual(first["generation"], reused["generation"])
        changed, *_ = self._run(data_issues_url="https://example.org/b")
        self.assertNotEqual(first["generation"], changed["generation"])
        self.assertEqual(changed["issues_url"], "https://example.org/b")

    def test_remote_data_manifest_marks_is_remote_and_delegates_to_load_remote_manifest(self) -> None:
        remote = json.loads(self._override_manifest(tag="remote").read_text(encoding="utf-8"))
        with mock.patch.object(b, "load_remote_manifest", return_value=remote) as remote_mock:
            manifest, _data_export_error, _bill_slugs, _base, is_remote = self._run(
                data_manifest="https://example.org/datenstand.json"
            )
        remote_mock.assert_called_once_with("https://example.org/datenstand.json")
        self.assertEqual(manifest["tag"], "remote")
        self.assertTrue(is_remote)

    def test_remote_manifest_is_shape_validated_too(self) -> None:
        with mock.patch.object(b, "load_remote_manifest", return_value={"generation": "g-remote"}):
            with self.assertRaises(RuntimeError) as ctx:
                self._run(data_manifest="https://example.org/datenstand.json")
        self.assertIn("https://example.org/datenstand.json", str(ctx.exception))

    def test_export_unavailable_is_caught_and_surfaced_as_data_export_error(self) -> None:
        with mock.patch.object(sqlite3, "sqlite_version_info", (3, 34, 0)):
            manifest, data_export_error, _bill_slugs, _base, _remote = self._run()
        self.assertIsNone(manifest)
        self.assertIsNotNone(data_export_error)
        self.assertIn("SQLite 3.35", data_export_error)


class DatenLabelRenameAcrossPagesTests(unittest.TestCase):
    """Every page-specific link (not just the shared nav) must say "Daten"."""

    def test_overview_catalog_and_sources_pages_all_use_the_new_label(self) -> None:
        cases = (
            (b.render_overview, dict(protocols=[], detail_entries=[], database_page_href="database.html")),
            (
                b.render_catalog_page,
                dict(protocols=[], detail_entries=[], catalog_path=Path("catalog.json"), database_page_href="database.html"),
            ),
            (b.render_sources_page, dict(entries=[], database_page_href="database.html")),
        )
        for renderer, kwargs in cases:
            with self.subTest(renderer=renderer.__name__):
                markup = renderer(**kwargs)
                self.assertIn(">Daten<", markup)
                self.assertNotIn("Datenbank", markup)


class RenderLandingPageDatenCardTests(unittest.TestCase):
    def test_daten_card_present_with_meta_or_absent_by_database_page_href(self) -> None:
        with_page = b.render_landing_page(
            [],
            database_page_href="database.html",
            data_stand="Stand 15.09.2026, 12:00 MESZ · 42 Protokolle",
        )
        self.assertIn(">Daten<", with_page)
        self.assertIn("Stand 15.09.2026, 12:00 MESZ · 42 Protokolle", with_page)
        self.assertNotIn("Datenbank erkunden", with_page)
        self.assertRegex(with_page, r'<li><h3><a href="database.html">Daten</a></h3>')
        # Value: protects=the landing card counts the recipes the Daten page runs ("sechs geprüfte SQL-Abfragen" for six); fails_when=the card's count word is hard-coded again and stays "fünf" after a recipe is added; why_new=the Daten page test counts its own eyebrow, nothing read the landing card's number; seam=none; no_claim=German wording beyond the count word
        word = {5: "fünf", 6: "sechs", 7: "sieben", 8: "acht"}[len(b.RECIPES)]
        self.assertIn(f"{word} geprüfte SQL-Abfragen", with_page)

        # The global header nav always links to database.html regardless (a
        # separate, always-on NAV_ITEMS entry), and a second, unrelated
        # source row also links to its destination, so identify the optional
        # data row by its unique description text.
        without_page = b.render_landing_page([], database_page_href=None, data_stand=None)
        self.assertNotIn("geprüfte SQL-Abfragen", without_page)


class RenderSiteUnavailablePageWiringTests(unittest.TestCase):
    def test_render_site_writes_the_unavailable_page_and_threads_the_reason_when_manifest_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / "data").mkdir()
            b.render_site(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=[],
                entries=[],
                abg_mps=[],
                mp_lookup={},
                manifest=None,
                data_export_error="data export needs SQLite 3.35+ (found 3.30.0)",
            )
            content = (output_dir / "database.html").read_text(encoding="utf-8")
        self.assertIn("SQLite 3.35", content)
        self.assertIn("Daten nicht erzeugt", content)


if __name__ == "__main__":
    unittest.main()
