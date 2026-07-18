from __future__ import annotations

import os
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import build_dip_pulse_site as build_site  # noqa: E402
import validate_dip_protocol as dip  # noqa: E402


class RollCallScrapingTests(unittest.TestCase):
    def test_default_roll_call_list_url_matches_previous_path(self) -> None:
        self.assertEqual(
            dip.roll_call_list_url(None, 0, 10),
            "https://www.bundestag.de/ajax/filterlist/de/parlament/plenum/abstimmung/484422-484422?offset=0&limit=10",
        )

    def test_layout_change_html_parses_empty_and_sets_selector_warning(self) -> None:
        changed_html = """
        <html>
          <body>
            <article class="vote-card">
              <time>01.07.2026</time>
              <h2>Namentliche Abstimmung</h2>
            </article>
          </body>
        </html>
        """

        self.assertEqual(dip.parse_roll_call_list_page(changed_html), [])

        with patch.object(dip, "fetch_html", return_value=changed_html):
            result = dip.fetch_roll_call_vote_candidates(
                "2026-07-01",
                1,
                include_diagnostics=True,
            )

        self.assertIsInstance(result, dip.RollCallCandidateFetch)
        assert isinstance(result, dip.RollCallCandidateFetch)
        self.assertEqual(result.candidates, [])
        self.assertTrue(result.list_html_seen)
        self.assertEqual(result.parsed_entry_count, 0)
        self.assertTrue(result.selector_warning)

    def test_valid_list_without_same_day_votes_does_not_set_selector_warning(self) -> None:
        valid_other_day_html = """
        <div class="col-xs-12 bt-slide">
          <canvas id="canvas-na-123456"></canvas>
          <span class="bt-date">01.07.2026</span>
          <span class="bt-dachzeile">TOP</span>
          <h3>TOP Abstimmung</h3>
          <div class="bt-teaser-haupttext"><p>Drucksache 21/123</p></div>
          <div data-chart-values="1,2,3,4"></div>
        </div>
        """

        with patch.object(dip, "fetch_html", return_value=valid_other_day_html):
            result = dip.fetch_roll_call_vote_candidates(
                "2026-07-02",
                1,
                include_diagnostics=True,
            )

        self.assertIsInstance(result, dip.RollCallCandidateFetch)
        assert isinstance(result, dip.RollCallCandidateFetch)
        self.assertEqual(result.candidates, [])
        self.assertEqual(result.parsed_entry_count, 1)
        self.assertFalse(result.selector_warning)

    def test_broken_selector_warning_reaches_report_and_stderr(self) -> None:
        class FakeClient:
            def list_all(self, path: str, params: dict[str, str]) -> list[dict[str, str]]:
                return []

        stderr = StringIO()
        with patch.object(dip, "fetch_html", return_value="<html><main>changed</main></html>"):
            with patch("sys.stderr", stderr):
                enrichment = dip.enrich_with_api(
                    FakeClient(),  # type: ignore[arg-type]
                    {"id": "protocol-1", "datum": "2026-07-01"},
                    {"agenda_items": []},
                    person_limit=0,
                    vote_scan_pages=1,
                )

        self.assertIn(dip.ROLL_CALL_LIST_PARSE_WARNING, enrichment["warnings"])
        self.assertIn(f"warning: {dip.ROLL_CALL_LIST_PARSE_WARNING}", stderr.getvalue())

    def test_roll_call_list_id_env_override_changes_requested_url(self) -> None:
        requested_urls: list[str] = []

        def fake_fetch_html(url: str) -> str:
            requested_urls.append(url)
            return ""

        with patch.dict(os.environ, {"BT_ROLL_CALL_LIST_ID": "999999-999999"}):
            with patch.object(dip, "fetch_html", side_effect=fake_fetch_html):
                dip.fetch_roll_call_vote_candidates("2026-07-01", 1)

        self.assertEqual(len(requested_urls), 1)
        self.assertIn("/abstimmung/999999-999999?", requested_urls[0])

    def test_roll_call_list_id_argument_overrides_env_url(self) -> None:
        requested_urls: list[str] = []

        def fake_fetch_html(url: str) -> str:
            requested_urls.append(url)
            return ""

        with patch.dict(os.environ, {"BT_ROLL_CALL_LIST_ID": "999999-999999"}):
            with patch.object(dip, "fetch_html", side_effect=fake_fetch_html):
                dip.fetch_roll_call_vote_candidates("2026-07-01", 1, "111111-111111")

        self.assertEqual(len(requested_urls), 1)
        self.assertIn("/abstimmung/111111-111111?", requested_urls[0])
        self.assertNotIn("999999-999999", requested_urls[0])

    def test_roll_call_list_id_flag_is_available_on_both_entry_points(self) -> None:
        with patch.object(sys, "argv", ["validate_dip_protocol.py", "--roll-call-list-id", "111111-111111"]):
            self.assertEqual(dip.parse_args().roll_call_list_id, "111111-111111")

        with patch.object(sys, "argv", ["build_dip_pulse_site.py", "--roll-call-list-id", "222222-222222"]):
            self.assertEqual(build_site.parse_args().roll_call_list_id, "222222-222222")


if __name__ == "__main__":
    unittest.main()
