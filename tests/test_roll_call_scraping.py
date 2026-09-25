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


FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"


class VoteResultTests(unittest.TestCase):
    def test_official_result_wins_over_counts(self) -> None:
        self.assertEqual(
            dip.vote_result(official="accepted", yes_count=1, no_count=99), ("accepted", "official")
        )
        self.assertEqual(
            dip.vote_result(official="rejected", yes_count=99, no_count=1), ("rejected", "official")
        )

    def test_derived_yes_greater_than_no_is_accepted(self) -> None:
        self.assertEqual(dip.vote_result(official=None, yes_count=300, no_count=200), ("accepted", "derived"))

    def test_derived_tie_is_rejected(self) -> None:
        # GOBT Section 48 Abs. 2: at a tie the question is answered no.
        self.assertEqual(dip.vote_result(official=None, yes_count=200, no_count=200), ("rejected", "derived"))

    def test_derived_no_greater_than_yes_is_rejected(self) -> None:
        self.assertEqual(dip.vote_result(official=None, yes_count=100, no_count=300), ("rejected", "derived"))

    def test_missing_counts_are_unknown(self) -> None:
        self.assertEqual(dip.vote_result(official=None, yes_count=0, no_count=0), (None, None))


class ScrapeOfficialVoteResultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (FIXTURES_DIR / "roll_call_detail_beschluss.html").read_text(encoding="utf-8")

    def test_finds_accepted_result_by_its_own_counts(self) -> None:
        self.assertEqual(dip.scrape_official_vote_result(self.html, 434, 128), "accepted")

    def test_finds_rejected_result_for_a_different_vote_in_the_same_text(self) -> None:
        self.assertEqual(dip.scrape_official_vote_result(self.html, 127, 418), "rejected")

    def test_no_matching_counts_returns_none(self) -> None:
        self.assertIsNone(dip.scrape_official_vote_result(self.html, 1, 2))

    def test_missing_beschluss_section_returns_none(self) -> None:
        self.assertIsNone(dip.scrape_official_vote_result("<html><body>no beschluss here</body></html>", 434, 128))


class NamenslistenMatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        html = (FIXTURES_DIR / "namenslisten_list.html").read_text(encoding="utf-8")
        self.entries = dip.parse_namenslisten_page(html)

    def test_parses_every_row(self) -> None:
        self.assertEqual(len(self.entries), 3)
        self.assertEqual(
            {entry["date"] for entry in self.entries}, {"2026-06-12", "2026-06-11"}
        )

    def test_exact_title_matches(self) -> None:
        url = dip.find_roll_call_xlsx_url("2026-06-11", "Bundeswehreinsatz in Kosovo (KFOR)", self.entries)
        self.assertEqual(url, "https://www.bundestag.de/resource/blob/1184016/20260611_3_xls.xlsx")

    def test_hyphenation_difference_still_matches(self) -> None:
        # bundestag.de hyphenates "Jahresemissionsgesamtmengen-Verordnung"
        # differently on this page than on the roll-call candidate list.
        url = dip.find_roll_call_xlsx_url(
            "2026-06-11", "Jahresemissionsgesamtmengen-Verordnung 2031-2040", self.entries
        )
        self.assertEqual(url, "https://www.bundestag.de/resource/blob/1184018/20260611_4_xls.xlsx")

    def test_no_match_returns_none_never_a_guess(self) -> None:
        self.assertIsNone(dip.find_roll_call_xlsx_url("2026-06-11", "Something else entirely", self.entries))
        self.assertIsNone(dip.find_roll_call_xlsx_url("2026-01-01", "Bundeswehreinsatz in Kosovo (KFOR)", self.entries))


class FetchRollCallVoteDetailTests(unittest.TestCase):
    def test_wires_official_result_and_xlsx_url_onto_the_vote(self) -> None:
        beschluss_html = (FIXTURES_DIR / "roll_call_detail_beschluss.html").read_text(encoding="utf-8")
        namenslisten_html = (FIXTURES_DIR / "namenslisten_list.html").read_text(encoding="utf-8")

        def fake_fetch_html(url: str) -> str:
            if "namenslisten" in url or "/liste/" in url:
                return namenslisten_html
            if "namensliste.form" in url:
                return ""
            return beschluss_html

        vote = {
            "id": "1007",
            "date": "2026-06-11",
            "title": "Bundeswehreinsatz in Kosovo (KFOR)",
            "total": {"yes": 434, "no": 128, "abstain": 0, "absent": 68},
        }
        with patch.object(dip, "fetch_html", side_effect=fake_fetch_html):
            enriched = dip.fetch_roll_call_vote_detail(vote)

        self.assertEqual(enriched["result_raw"], "accepted")
        self.assertEqual(enriched["result_source"], "official")
        self.assertEqual(enriched["xlsx_url"], "https://www.bundestag.de/resource/blob/1184016/20260611_3_xls.xlsx")

    def test_falls_back_to_derived_result_and_no_xlsx_when_nothing_matches(self) -> None:
        def fake_fetch_html(url: str) -> str:
            return ""

        vote = {
            "id": "9999",
            "date": "2026-01-01",
            "title": "Unmatched vote",
            "total": {"yes": 100, "no": 300, "abstain": 0, "absent": 0},
        }
        with patch.object(dip, "fetch_html", side_effect=fake_fetch_html):
            enriched = dip.fetch_roll_call_vote_detail(vote)

        self.assertEqual(enriched["result_raw"], "rejected")
        self.assertEqual(enriched["result_source"], "derived")
        self.assertIsNone(enriched["xlsx_url"])


if __name__ == "__main__":
    unittest.main()
