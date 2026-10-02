"""Regression tests for the adversarial-review findings of the ship review.

Each class pins one failure path the reviewers reproduced: cached votes lost
in a partial rescan, an empty page remembered for a whole build, legacy
completion stamps trusted forever, a first week or month judged on the
sittings the store happens to hold, a changed catalog date, a truncated
catalog fetch, non-atomic writes and small CLI guards.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import _facts_fixture
import build_dip_pulse_site as build
import facts
import validate_dip_protocol as dip
from test_facts import StoreCase, week_specs
from test_vote_acquisition import list_page, paged, report_with, votes_facts

STAMP = "2026-09-01T10:00:00Z"


def vote(n: str) -> dict:
    return {"id": n, "title": f"V{n}", "date": "2026-07-10"}


def two_vote_report(acquisition: dict | None) -> dict:
    report = report_with(0, acquisition)
    report["agenda_items"][0]["votes"] = [vote("1"), vote("2")]
    return report



class ScanEndEvidenceTests(unittest.TestCase):
    def annotate(self, report: dict, existing: dict | None, scan_pages: int) -> None:
        build.annotate_report_acquisition(
            report, existing, vote_scan_pages=scan_pages, profile_resolver=None, summary_mode="off"
        )

    def test_reused_votes_keep_the_scan_end_their_scan_recorded(self) -> None:
        prior = votes_facts("complete", records=0, acquired_at=STAMP, attempted_at=STAMP)
        existing = report_with(0, prior)
        existing["validation_summary"] = {"roll_call_scan_end": "date_passed"}
        fresh = report_with(0, None)
        fresh["validation_summary"] = {"roll_call_scan_end": "not_scanned"}  # this build did not scan
        self.annotate(fresh, existing, scan_pages=0)
        self.assertEqual(fresh["validation_summary"]["roll_call_scan_end"], "date_passed")
        self.assertTrue(facts.completeness_from_reports([fresh])["21/90"]["votes"])

    def test_a_no_scan_rebuild_does_not_unhold_a_sitting_with_unmatched_votes(self) -> None:
        prior = votes_facts("complete", records=1, acquired_at=STAMP, attempted_at=STAMP)
        existing = report_with(1, prior)
        existing["validation_summary"] = {"roll_call_scan_end": "date_passed", "unmatched_roll_call_vote_count": 2}
        fresh = report_with(1, None)
        fresh["validation_summary"] = {"roll_call_scan_end": "not_scanned", "unmatched_roll_call_vote_count": 0}
        self.annotate(fresh, existing, scan_pages=0)
        self.assertEqual(fresh["validation_summary"]["unmatched_roll_call_vote_count"], 2)
        self.assertFalse(facts.completeness_from_reports([fresh])["21/90"]["votes"])

    def test_a_blank_first_page_is_not_a_verified_empty_list(self) -> None:
        for html in ("", "   ", "<html><body>Wartungsarbeiten</body></html>"):
            with self.subTest(html=html), mock.patch.object(dip, "fetch_html", return_value=html):
                result = dip.fetch_roll_call_vote_candidates("2026-07-01", 3, include_diagnostics=True)
            self.assertTrue(result.selector_warning)

    def test_a_stamp_from_before_scan_ends_were_recorded_stays_unverified(self) -> None:
        prior = votes_facts("complete", records=2, acquired_at=STAMP, attempted_at=STAMP)
        existing = two_vote_report(prior)  # no roll_call_scan_end: cached by an older build
        fresh = report_with(0, None)
        fresh["validation_summary"] = {"roll_call_scan_end": "not_scanned"}
        self.annotate(fresh, existing, scan_pages=0)
        state = facts.completeness_from_reports([fresh])["21/90"]
        self.assertFalse(state["votes"])
        self.assertEqual(state["reasons"]["votes"], "no scan-end evidence (report predates it)")



class LaterDetailFailureKeepsTheVotesAlreadyFetchedTests(unittest.TestCase):
    def test_the_first_vote_of_a_top_survives_a_failure_on_the_second(self) -> None:
        candidates = [
            {"id": "1", "document_numbers": ["21/1"]},
            {"id": "2", "document_numbers": ["21/1"]},
        ]

        def detail(candidate: dict) -> dict:
            if candidate["id"] == "2":
                raise dip.DipError("timeout")
            return {**candidate, "fractions": [], "members": []}

        top = {"drucksachen": [{"dokumentnummer": "21/1"}]}
        cache: dict = {}
        errors: list = []
        with mock.patch.object(dip, "fetch_roll_call_vote_detail", side_effect=detail):
            matches = dip.match_roll_call_votes(top, [], candidates, cache, errors)
            self.assertEqual([m["id"] for m in matches], ["1"])
            self.assertEqual(len(errors), 1)
            with self.assertRaises(dip.DipError):  # without a collector the error still propagates
                dip.match_roll_call_votes(top, [], candidates, {}, None)


class DateCorrectionBeforeTheJudgedRangeStillCountsTests(StoreCase):
    def test_a_stored_sitting_moved_to_before_the_range_is_a_gap(self) -> None:
        seeded = self.seed(week_specs(6))
        first = dict(seeded["catalog_sittings"][0])
        moved = {**first, "date": "2024-06-03"}  # long before the store's earliest sitting
        listed = [moved] + seeded["catalog_sittings"][1:]
        gaps = facts.sitting_gaps(facts.load_protocols(self.conn), seeded["completeness"], _facts_fixture.catalog_for(listed))
        self.assertEqual(gaps[first["document_number"]]["reasons"], {"dossier": "date_changed"})


class OutageCooldownTests(unittest.TestCase):
    def test_the_outage_marker_expires_and_the_list_is_tried_again(self) -> None:
        pages = [list_page(("1", "01.07.2026", "21/1"), ("2", "30.06.2026", "21/2"))]
        cache = {dip.ROLL_CALL_OUTAGE_KEY: f"{dip.time.monotonic() - dip.ROLL_CALL_OUTAGE_COOLDOWN_SECONDS - 1}|boom"}
        with mock.patch.object(dip, "fetch_html", side_effect=paged(pages)):
            result = dip.fetch_roll_call_vote_candidates("2026-07-01", 3, include_diagnostics=True, page_cache=cache)
        self.assertEqual(result.scan_end, "date_passed")
        self.assertNotIn(dip.ROLL_CALL_OUTAGE_KEY, cache)



class BudgetStuckSittingsAreNotRedownloadedTests(unittest.TestCase):
    GAP = {"reasons": {"votes": "votes partial (scan_budget_exhausted after 30 pages)"}}

    def test_a_scan_that_used_its_pages_is_structural_until_the_budget_grows(self) -> None:
        self.assertTrue(build._structural_vote_gap(self.GAP, 30))
        self.assertTrue(build._structural_vote_gap(self.GAP, 20))
        self.assertFalse(build._structural_vote_gap(self.GAP, 60))
        self.assertFalse(build._structural_vote_gap(self.GAP, None))
        self.assertFalse(build._structural_vote_gap({"reasons": {"votes": "votes partial (scan_budget_exhausted)"}}, 30))

    def test_completeness_names_the_budget_that_was_not_enough(self) -> None:
        report = report_with(1, votes_facts("partial", records=1, reasons=("scan_budget_exhausted",), acquired_at=STAMP, attempted_at=STAMP))
        report["validation_summary"] = {"xml_speech_count": 3, "roll_call_scan_pages": 30}
        state = facts.completeness_from_reports([report])["21/90"]
        self.assertEqual(state["reasons"]["votes"], "votes partial (scan_budget_exhausted after 30 pages)")

    def test_the_printed_fix_raises_the_budget_and_counts_what_it_would_reach(self) -> None:
        report = {
            "sitting_gaps": {"21/1": {"date": "2026-06-11", "reasons": {"votes": "votes partial (scan_budget_exhausted after 30 pages)"}}},
            "incomplete_periods": [],
        }
        catalog = [{"id": "pp-1", "dokumentnummer": "21/1", "datum": "2026-06-11", "fundstelle": {"xml_url": "https://example.test/1.xml"}}]
        text = "\n".join(build.format_incomplete_report(report, output_dir=Path("out"), catalog_protocols=catalog, vote_scan_pages=30))
        self.assertIn("--vote-scan-pages 60", text)
        self.assertIn("(acquires 1 sittings;", text)
        self.assertNotIn("a backfill cannot fix", text)

    def test_backfill_at_the_same_budget_leaves_it_alone_and_a_larger_one_takes_it(self) -> None:
        stuck = report_with(1, votes_facts("partial", records=1, reasons=("scan_budget_exhausted",), acquired_at=STAMP, attempted_at=STAMP))
        stuck["validation_summary"] = {"xml_speech_count": 3, "roll_call_scan_pages": 30, "roll_call_scan_end": "budget_exhausted"}
        stuck["protocol"] = {"dokumentnummer": "21/1", "datum": "2026-06-11"}
        catalog = [{"id": "pp-1", "dokumentnummer": "21/1", "datum": "2026-06-11", "fundstelle": {"xml_url": "https://example.test/1.xml"}}]
        same = build.incomplete_sitting_protocols([{"report": stuck}], catalog, scan_pages=30)
        self.assertEqual(([p["dokumentnummer"] for p in same[0]], [p["dokumentnummer"] for p in same[3]]), ([], ["21/1"]))
        wider = build.incomplete_sitting_protocols([{"report": stuck}], catalog, scan_pages=60)
        self.assertEqual([p["dokumentnummer"] for p in wider[0]], ["21/1"])


class StaleListIsNotAVerifiedZeroVoteSittingTests(unittest.TestCase):
    def enrich(self, pages: list[str], date: str):
        from test_vote_acquisition import FakeClient, agenda

        with mock.patch.object(dip, "fetch_html", side_effect=paged(pages)), mock.patch.object(
            dip, "fetch_roll_call_vote_detail",
            side_effect=lambda candidate: {**candidate, "fractions": [], "members": [], "result_raw": None, "result_source": None},
        ), mock.patch("sys.stderr", io.StringIO()):
            return dip.enrich_with_api(
                FakeClient(), {"id": "p1", "dokumentnummer": "21/90", "datum": date}, agenda("21/9"), person_limit=0, vote_scan_pages=30
            )

    def test_a_recent_sitting_newer_than_the_lists_newest_entry_is_partial_source_stale(self) -> None:
        import datetime as _dt

        today = dip.datetime.now(dip.timezone.utc).date()
        newest = (today - _dt.timedelta(days=9)).strftime("%d.%m.%Y")
        sitting = (today - _dt.timedelta(days=2)).isoformat()
        enrichment = self.enrich([list_page(("1", newest, "21/1"))], sitting)
        votes = enrichment["acquisition"]["votes"]
        self.assertEqual((votes["acquisition_state"], votes["failure_reasons"]), ("partial", ["source_stale"]))

    def test_an_old_sitting_or_a_list_that_has_caught_up_is_verified(self) -> None:
        import datetime as _dt

        today = dip.datetime.now(dip.timezone.utc).date()
        # A sitting long ago: no lag possible any more.
        old = self.enrich([list_page(("1", "05.07.2026", "21/1"), ("2", "30.06.2026", "21/2"))], "2026-07-01")
        self.assertEqual(old["acquisition"]["votes"]["acquisition_state"], "complete")
        # The list already shows a vote on the sitting's day or later: it has caught up.
        recent = (today - _dt.timedelta(days=2))
        caught_up = self.enrich(
            [list_page(("1", recent.strftime("%d.%m.%Y"), "21/1"), ("2", (recent - _dt.timedelta(days=3)).strftime("%d.%m.%Y"), "21/2"))],
            recent.isoformat(),
        )
        self.assertEqual(caught_up["acquisition"]["votes"]["acquisition_state"], "complete")
        self.assertNotIn("source_stale", caught_up["acquisition"]["votes"]["failure_reasons"])


class NonConvergingGapsAreKnownTests(unittest.TestCase):
    def test_a_budget_gap_is_not_structural_when_votes_are_off(self) -> None:
        gap = {"reasons": {"votes": "votes partial (scan_budget_exhausted after 30 pages)"}}
        self.assertFalse(build._structural_vote_gap(gap, 0))
        # So it is a vote-only gap, and the votes-off hint applies.
        catalog = [{"id": "pp-1", "dokumentnummer": "21/1", "datum": "2026-06-11", "fundstelle": {"xml_url": "https://example.test/1.xml"}}]
        stuck = report_with(1, votes_facts("partial", records=1, reasons=("scan_budget_exhausted",), acquired_at=STAMP, attempted_at=STAMP))
        stuck["validation_summary"] = {"xml_speech_count": 3, "roll_call_scan_pages": 30, "roll_call_scan_end": "budget_exhausted"}
        stuck["protocol"] = {"dokumentnummer": "21/1", "datum": "2026-06-11"}
        _acq, _wait, vote_only, structural = build.incomplete_sitting_protocols([{"report": stuck}], catalog, votes=False, scan_pages=0)
        self.assertEqual(([p["dokumentnummer"] for p in vote_only], structural), (["21/1"], []))

    def test_source_stale_is_left_alone_only_while_the_list_may_be_catching_up(self) -> None:
        import datetime as _dt

        today = dip.datetime.now(dip.timezone.utc).date()
        recent = {"date": (today - _dt.timedelta(days=3)).isoformat(), "reasons": {"votes": "votes partial (source_stale)"}}
        old = {"date": (today - _dt.timedelta(days=30)).isoformat(), "reasons": {"votes": "votes partial (source_stale)"}}
        self.assertTrue(build._structural_vote_gap(recent, 30))
        self.assertFalse(build._structural_vote_gap(old, 30))  # now a rescan can settle it




class CombinedReasonsAreParsedNotMatchedAsTextTests(unittest.TestCase):
    def test_a_budget_reason_combined_with_unmatched_is_structural_at_any_budget(self) -> None:
        gap = {"reasons": {"votes": "votes partial (scan_budget_exhausted after 30 pages, unmatched_candidate)"}}
        self.assertTrue(build._structural_vote_gap(gap, 30))
        self.assertTrue(build._structural_vote_gap(gap, 90))

    def test_the_scan_budget_travels_through_a_no_scan_rebuild(self) -> None:
        prior = votes_facts("partial", records=1, reasons=("scan_budget_exhausted",), acquired_at=STAMP, attempted_at=STAMP)
        existing = report_with(1, prior)
        existing["validation_summary"] = {"roll_call_scan_end": "budget_exhausted", "roll_call_scan_pages": 30}
        fresh = report_with(1, None)
        fresh["validation_summary"] = {"roll_call_scan_end": "not_scanned", "roll_call_scan_pages": 0}
        build.annotate_report_acquisition(fresh, existing, vote_scan_pages=0, profile_resolver=None, summary_mode="off")
        self.assertEqual(fresh["validation_summary"]["roll_call_scan_pages"], 30)


class ScanResultStandsAsItIsTests(unittest.TestCase):
    """The carry-forward is gone: a scan's result replaces the cache, or, when the
    scan failed for a transient reason over a cache with votes, the whole cached
    dossier is kept."""

    def annotate(self, report: dict, existing: dict | None, scan_pages: int) -> dict:
        build.annotate_report_acquisition(
            report, existing, vote_scan_pages=scan_pages, profile_resolver=None, summary_mode="off"
        )
        return report["acquisition"]["votes"]

    def test_a_complete_scan_replaces_the_cache_even_with_fewer_votes(self) -> None:
        existing = two_vote_report(votes_facts("complete", records=2, acquired_at=STAMP, attempted_at=STAMP))
        fresh = report_with(0, votes_facts("complete", acquired_at="2026-09-28T10:00:00Z", attempted_at="2026-09-28T10:00:00Z"))
        build.reuse_existing_dossier_enrichments(fresh, existing, votes=False, profiles=True)  # a scan run
        votes = self.annotate(fresh, existing, scan_pages=30)
        self.assertEqual(fresh["agenda_items"][0]["votes"], [])
        self.assertEqual((votes["acquisition_state"], votes["records"]), ("complete", 0))

    def test_a_partial_scan_keeps_its_own_state_and_votes_and_merges_nothing(self) -> None:
        existing = two_vote_report(votes_facts("complete", records=2, acquired_at=STAMP, attempted_at=STAMP))
        fresh = report_with(0, votes_facts("partial", records=1, reasons=("scan_budget_exhausted",), acquired_at=STAMP, attempted_at=STAMP))
        fresh["agenda_items"][0]["votes"] = [vote("1")]
        build.reuse_existing_dossier_enrichments(fresh, existing, votes=False, profiles=True)
        votes = self.annotate(fresh, existing, scan_pages=30)
        self.assertEqual([v["id"] for v in fresh["agenda_items"][0]["votes"]], ["1"])
        self.assertEqual((votes["acquisition_state"], votes["failure_reasons"]), ("partial", ["scan_budget_exhausted"]))

    def test_a_transient_failure_over_cached_votes_keeps_the_cached_dossier(self) -> None:
        existing = two_vote_report(votes_facts("complete", records=2, acquired_at=STAMP, attempted_at=STAMP))
        for reason in ("source_unavailable", "source_changed"):
            with self.subTest(reason=reason):
                fresh = report_with(0, votes_facts("failed", reasons=(reason,), attempted_at=STAMP))
                with self.assertRaisesRegex(dip.DipError, "keeping the cached dossier"):
                    build.keep_cached_dossier_when_votes_failed(fresh, existing, 30)

    def test_a_no_scan_rebuild_that_lost_votes_to_a_reparse_loses_the_evidence_too(self) -> None:
        prior = votes_facts("complete", records=2, acquired_at=STAMP, attempted_at=STAMP)
        existing = two_vote_report(prior)
        existing["validation_summary"] = {"roll_call_scan_end": "date_passed"}
        fresh = report_with(0, None)
        fresh["agenda_items"][0]["top_id"] = "TOP 9"  # re-parsed with other ids: nothing to copy the votes onto
        fresh["validation_summary"] = {"roll_call_scan_end": "not_scanned"}
        build.reuse_existing_dossier_enrichments(fresh, existing, votes=True, profiles=True)
        build.annotate_report_acquisition(fresh, existing, vote_scan_pages=0, profile_resolver=None, summary_mode="off")
        fresh["protocol"] = {"dokumentnummer": "21/90"}
        self.assertFalse(facts.completeness_from_reports([fresh])["21/90"]["votes"])

    def test_the_cached_dossier_survives_a_skipped_refresh_through_the_merge(self) -> None:
        cached = {"report": {"protocol": {"id": "pp-1", "dokumentnummer": "21/1", "datum": "2026-06-11"}}, "slug": "21-1"}
        protocol = {"id": "pp-1", "dokumentnummer": "21/1", "datum": "2026-06-11"}

        def failing_build(_protocol: dict, _existing: dict | None) -> dict:
            raise dip.DipError("Roll-call scan failed (source_unavailable); keeping the cached dossier with its votes.")

        with mock.patch("sys.stderr", io.StringIO()):
            generated = build.build_dossiers_with_progress([protocol], load_existing=lambda p: None, build_dossier=failing_build)
        self.assertEqual(generated, [])
        self.assertEqual(protocol["dossier_failure_reasons"], ["source_unavailable"])
        merged = build.merge_detail_entries([protocol], [cached], generated)
        self.assertEqual(merged, [cached])

    def test_a_complete_scan_that_attaches_nothing_over_cached_votes_keeps_the_cached_dossier(self) -> None:
        existing = two_vote_report(votes_facts("complete", records=2, acquired_at=STAMP, attempted_at=STAMP))
        empty_but_complete = report_with(0, votes_facts("complete", acquired_at=STAMP, attempted_at=STAMP))
        with self.assertRaisesRegex(dip.DipError, "attached no vote"):
            build.keep_cached_dossier_when_votes_failed(empty_but_complete, existing, 30)
        one_found = report_with(1, votes_facts("complete", records=1, acquired_at=STAMP, attempted_at=STAMP))
        build.keep_cached_dossier_when_votes_failed(one_found, existing, 30)  # a scan that found something stands

    def test_an_impossible_calendar_date_does_not_abort_the_lag_check(self) -> None:
        self.assertIsNone(dip._days_since("2026-02-30"))
        self.assertIsInstance(dip._days_since("2026-02-20"), int)

    def test_other_outcomes_do_not_keep_the_cached_dossier(self) -> None:
        with_votes = two_vote_report(votes_facts("complete", records=2, acquired_at=STAMP, attempted_at=STAMP))
        cases = (
            ("no cache", None, votes_facts("failed", reasons=("source_unavailable",), attempted_at=STAMP), 30),
            ("cache without votes", report_with(0, None), votes_facts("failed", reasons=("source_unavailable",), attempted_at=STAMP), 30),
            ("no scan requested", with_votes, votes_facts("failed", reasons=("source_unavailable",), attempted_at=STAMP), 0),
            ("budget exhausted", with_votes, votes_facts("partial", records=1, reasons=("scan_budget_exhausted",), attempted_at=STAMP), 30),
            ("unmatched", with_votes, votes_facts("partial", records=1, reasons=("unmatched_candidate",), attempted_at=STAMP), 30),
            ("complete with votes", with_votes, votes_facts("complete", records=1, acquired_at=STAMP, attempted_at=STAMP), 30),
        )
        for label, existing, facts_dict, pages in cases:
            with self.subTest(label):
                build.keep_cached_dossier_when_votes_failed(report_with(0, facts_dict), existing, pages)

    def test_a_no_scan_run_copies_cached_votes_into_items_without_votes_only(self) -> None:
        existing = two_vote_report(votes_facts("complete", records=2, acquired_at=STAMP, attempted_at=STAMP))
        empty = report_with(0, None)
        build.reuse_existing_dossier_enrichments(empty, existing, votes=True, profiles=True)
        self.assertEqual([v["id"] for v in empty["agenda_items"][0]["votes"]], ["1", "2"])
        has_votes = report_with(0, None)
        has_votes["agenda_items"][0]["votes"] = [vote("9")]
        build.reuse_existing_dossier_enrichments(has_votes, existing, votes=True, profiles=True)
        self.assertEqual([v["id"] for v in has_votes["agenda_items"][0]["votes"]], ["9"])


class MergeRequiresTheSameTopIdTests(unittest.TestCase):
    def test_votes_are_not_carried_between_tops_that_only_share_an_index(self) -> None:
        existing = report_with(0, votes_facts("complete", records=1, acquired_at=STAMP, attempted_at=STAMP))
        existing["agenda_items"][0].update({"top_id": "TOP 1", "index": 1, "votes": [vote("1")]})
        fresh = report_with(0, votes_facts("partial", records=0, reasons=("source_unavailable",), attempted_at=STAMP))
        fresh["agenda_items"][0].update({"top_id": "TOP 7", "index": 1, "votes": []})  # another TOP, same index
        build.reuse_existing_dossier_enrichments(fresh, existing, votes=True, profiles=True)
        self.assertEqual(fresh["agenda_items"][0]["votes"], [])


class OutageFlagOnlyForTransientFailuresTests(unittest.TestCase):
    def test_a_404_on_one_page_does_not_disable_the_rest_of_the_build(self) -> None:
        import urllib.error

        cache: dict[str, str] = {}
        not_found = urllib.error.HTTPError("https://example.test/x", 404, "nf", {}, None)  # type: ignore[arg-type]
        with mock.patch.object(dip.urllib.request, "urlopen", side_effect=not_found), mock.patch.object(dip.time, "sleep"):
            with self.assertRaises(dip.DipError):
                dip.fetch_roll_call_vote_candidates("2026-07-01", 3, page_cache=cache)
        self.assertNotIn(dip.ROLL_CALL_OUTAGE_KEY, cache)

    def test_a_network_failure_after_its_retries_does_set_it(self) -> None:
        cache: dict[str, str] = {}
        with mock.patch.object(dip.urllib.request, "urlopen", side_effect=ConnectionResetError(54, "reset")), mock.patch.object(
            dip.time, "sleep"
        ), mock.patch("sys.stderr"):
            with self.assertRaises(dip.DipError):
                dip.fetch_roll_call_vote_candidates("2026-07-01", 3, page_cache=cache)
        self.assertIn(dip.ROLL_CALL_OUTAGE_KEY, cache)





class BackfillLeavesStructuralUnmatchedSittingsAloneTests(unittest.TestCase):
    def test_a_budget_exhausted_sitting_that_also_has_unmatched_votes_is_structural(self) -> None:
        # A wider scan settles the budget part, but the unmatched part survives it.
        gap = {"reasons": {"votes": "votes partial (scan_budget_exhausted, unmatched_candidate)"}}
        self.assertTrue(build._structural_vote_gap(gap))
        self.assertTrue(build._structural_vote_gap({"reasons": {"votes": "votes partial (unmatched_candidate)"}}))

    def test_a_sitting_held_back_only_by_unmatched_votes_is_not_reacquired(self) -> None:
        stuck = report_with(1, votes_facts("partial", records=1, reasons=("unmatched_candidate",), acquired_at=STAMP, attempted_at=STAMP))
        stuck["validation_summary"] = {"xml_speech_count": 3, "roll_call_scan_end": "date_passed"}
        stuck["protocol"] = {"dokumentnummer": "21/1", "datum": "2026-06-11"}
        legacy = report_with(1, None)
        legacy["protocol"] = {"dokumentnummer": "21/2", "datum": "2026-06-12"}
        legacy["validation_summary"] = {"xml_speech_count": 3}
        catalog = [
            {"id": "pp-2", "dokumentnummer": "21/2", "datum": "2026-06-12", "fundstelle": {"xml_url": "https://example.test/2.xml"}},
            {"id": "pp-1", "dokumentnummer": "21/1", "datum": "2026-06-11", "fundstelle": {"xml_url": "https://example.test/1.xml"}},
        ]
        acquirable, waiting, vote_only, structural = build.incomplete_sitting_protocols(
            [{"report": stuck}, {"report": legacy}], catalog
        )
        self.assertEqual([p["dokumentnummer"] for p in acquirable], ["21/2"])
        self.assertEqual([p["dokumentnummer"] for p in structural], ["21/1"])
        report = {
            "sitting_gaps": {
                "21/1": {"date": "2026-06-11", "reasons": {"votes": "votes partial (unmatched_candidate)"}},
                "21/2": {"date": "2026-06-12", "reasons": {"votes": "no vote acquisition metadata (report predates it)"}},
            },
            "incomplete_periods": [],
        }
        text = "\n".join(build.format_incomplete_report(report, output_dir=Path("out"), catalog_protocols=catalog, vote_scan_pages=30))
        self.assertIn("1 sittings a backfill cannot fix now: roll-call votes no agenda item claims", text)
        self.assertIn("(21/1)", text)
        self.assertIn("(acquires 1 sittings;", text)

    def test_a_gap_without_an_xml_url_is_not_counted_as_acquirable(self) -> None:
        report = {
            "sitting_gaps": {"21/1": {"date": "2026-06-11", "reasons": {"dossier": "date_changed"}}},
            "incomplete_periods": [],
        }
        catalog = [{"id": "pp-1", "dokumentnummer": "21/1", "datum": "2026-06-11"}]
        text = "\n".join(build.format_incomplete_report(report, output_dir=Path("out"), catalog_protocols=catalog, vote_scan_pages=30))
        self.assertIn("Fix: none available now", text)


class UnmatchedVotesHoldACachedReportBackTests(unittest.TestCase):
    def test_a_report_stamped_complete_that_records_unmatched_votes_is_not_complete(self) -> None:
        report = report_with(1, votes_facts("complete", records=1, acquired_at=STAMP, attempted_at=STAMP))
        report["validation_summary"] = {"xml_speech_count": 3, "roll_call_scan_end": "date_passed",
                                        "unmatched_roll_call_vote_count": 2}
        state = facts.completeness_from_reports([report])["21/90"]
        self.assertFalse(state["votes"])
        self.assertEqual(state["reasons"]["votes"], "roll-call votes matched no TOP")
        report["validation_summary"]["unmatched_roll_call_vote_count"] = 0
        self.assertTrue(facts.completeness_from_reports([report])["21/90"]["votes"])


class RollCallPageCacheTests(unittest.TestCase):
    def test_an_empty_page_is_never_cached_as_the_end_of_the_list(self) -> None:
        pages = [list_page(("1", "05.07.2026", "21/1"))]  # page 2 comes back empty
        cache: dict[str, str] = {}
        fake = paged(pages)
        with mock.patch.object(dip, "fetch_html", side_effect=fake):
            first = dip.fetch_roll_call_vote_candidates("2026-07-01", 5, include_diagnostics=True, page_cache=cache)
            second = dip.fetch_roll_call_vote_candidates("2026-07-01", 5, include_diagnostics=True, page_cache=cache)
        self.assertEqual(first.scan_end, "list_end")
        self.assertEqual(len(cache), 1)
        # The second sitting had to ask for the empty page again instead of reusing it.
        self.assertEqual((second.pages_fetched, second.pages_from_cache), (1, 1))

    def test_pages_already_cached_are_served_during_an_outage(self) -> None:
        pages = [list_page(("1", "01.07.2026", "21/1"), ("2", "30.06.2026", "21/2"))]
        cache: dict[str, str] = {}
        with mock.patch.object(dip, "fetch_html", side_effect=paged(pages)):
            dip.fetch_roll_call_vote_candidates("2026-07-01", 3, page_cache=cache)
        cache[dip.ROLL_CALL_OUTAGE_KEY] = f"{dip.time.monotonic()}|boom"
        opener = mock.Mock(side_effect=dip.DipError("still down"))
        with mock.patch.object(dip, "fetch_html", opener):
            result = dip.fetch_roll_call_vote_candidates("2026-07-01", 3, include_diagnostics=True, page_cache=cache)
        self.assertEqual(result.scan_end, "date_passed")
        opener.assert_not_called()
        with mock.patch.object(dip, "fetch_html", opener), self.assertRaisesRegex(dip.DipError, "unavailable earlier"):
            dip.fetch_roll_call_vote_candidates("2026-05-01", 3, page_cache=cache)  # needs an uncached page


class CatalogFetchIsCheckedAgainstDipsCountTests(unittest.TestCase):
    def test_duplicates_across_cursor_pages_do_not_mask_missing_protocols(self) -> None:
        pages = [
            {"documents": [{"id": "1"}, {"id": "2"}], "cursor": "a", "numFound": 3},
            {"documents": [{"id": "2"}], "cursor": "b", "numFound": 3},
            {"documents": [], "cursor": "b", "numFound": 3},
        ]
        client = mock.Mock()
        client.get_json.side_effect = pages
        with self.assertRaisesRegex(dip.DipError, "2 of 3 protocols"):
            build.fetch_protocols(client, 0, [], None)

    def client(self, pages: list[dict]) -> mock.Mock:
        client = mock.Mock()
        client.get_json.side_effect = pages
        return client

    def test_a_short_fetch_stops_the_build(self) -> None:
        pages = [{"documents": [{"id": "1"}], "cursor": "a", "numFound": 3}, {"documents": [{"id": "2"}], "cursor": "a", "numFound": 3}]
        with self.assertRaisesRegex(dip.DipError, "2 of 3 protocols"):
            build.fetch_protocols(self.client(pages), 0, [], None)

    def test_a_complete_fetch_passes_and_a_missing_count_is_tolerated(self) -> None:
        full = [{"documents": [{"id": "1"}, {"id": "2"}], "cursor": "a", "numFound": 2}, {"documents": [], "cursor": "a", "numFound": 2}]
        self.assertEqual(len(build.fetch_protocols(self.client(full), 0, [], None)), 2)
        bare = [{"documents": [{"id": "1"}], "cursor": "a"}, {"documents": [], "cursor": "a"}]
        self.assertEqual(len(build.fetch_protocols(self.client(bare), 0, [], None)), 1)

    def test_a_limited_fetch_is_not_held_to_the_count(self) -> None:
        pages = [{"documents": [{"id": "1"}, {"id": "2"}], "cursor": "a", "numFound": 50}]
        self.assertEqual(len(build.fetch_protocols(self.client(pages), 2, [], 21)), 2)


class AtomicWriteTests(unittest.TestCase):
    def test_a_failed_write_leaves_the_previous_file_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plenarprotokoll-21-1.json"
            path.write_text("old", encoding="utf-8")
            with mock.patch.object(build.os, "replace", side_effect=OSError("disk")):
                with self.assertRaises(OSError):
                    build.write_text_atomic(path, "new")
            self.assertEqual(path.read_text(encoding="utf-8"), "old")
            build.write_text_atomic(path, "new")
            self.assertEqual(path.read_text(encoding="utf-8"), "new")
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["plenarprotokoll-21-1.json"])


class PeriodBoundaryTests(StoreCase):
    def test_earlier_listed_sittings_of_the_first_stored_week_and_month_count(self) -> None:
        specs = week_specs(6)
        seeded = self.seed(specs)
        first = facts.date.fromisoformat(specs[0]["date"])  # a Wednesday
        earlier = {"document_number": "21/50", "date": (first - facts.timedelta(days=1)).isoformat()}
        rows = self.compute(catalog=_facts_fixture.catalog_for(seeded["catalog_sittings"] + [earlier]))
        weekly = self.rows_for(rows, "laengste-rede")
        self.assertEqual(weekly[0]["complete"], 0)
        gaps = facts.sitting_gaps(facts.load_protocols(self.conn), seeded["completeness"],
                                  _facts_fixture.catalog_for(seeded["catalog_sittings"] + [earlier]))
        self.assertEqual(gaps["21/50"]["reasons"], {"dossier": "not_persisted"})

    def test_a_sitting_dated_differently_by_dip_holds_both_periods_back(self) -> None:
        seeded = self.seed(week_specs(6))
        moved = dict(seeded["catalog_sittings"][3])  # store: week 3+3, DIP: a week later
        moved["date"] = (facts.date.fromisoformat(moved["date"]) + facts.timedelta(days=7)).isoformat()
        listed = [s for s in seeded["catalog_sittings"] if s["document_number"] != moved["document_number"]] + [moved]
        catalog = _facts_fixture.catalog_for(listed)
        rows = self.rows_for(self.compute(catalog=catalog), "laengste-rede")
        by_key = {row["period_key"]: row for row in rows}
        old_week = facts.iso_week_key(seeded["catalog_sittings"][3]["date"])
        new_week = facts.iso_week_key(moved["date"])
        self.assertEqual(by_key[facts.week_label(old_week)]["complete"], 0)
        self.assertEqual(by_key[facts.week_label(new_week)]["complete"], 0)
        gaps = facts.sitting_gaps(facts.load_protocols(self.conn), seeded["completeness"], catalog)
        self.assertEqual(gaps[moved["document_number"]]["reasons"], {"dossier": "date_changed"})
        weeks, _months = facts.build_periods(facts.load_protocols(self.conn), catalog)
        note = facts.gap_note(
            facts.period_gaps({w.period_key: w for w in weeks}[facts.week_label(old_week)], seeded["completeness"], "votes"),
            "votes",
        )
        self.assertIn("Datum laut DIP geändert", note)

    def test_the_facts_engine_uses_the_build_date_not_the_wall_clock(self) -> None:
        args = SimpleNamespace(no_persist=False, vote_scan_pages=30, data_base_url=None, data_manifest=None,
                               data_license=None, data_issues_url=None, force_export=False,
                               today=facts.date(2026, 7, 1))
        self.seed(week_specs(3))
        with (
            mock.patch.object(build, "export_distribution_data", return_value={}),
            mock.patch.object(build, "collect_bill_pages", return_value=[]),
            mock.patch.object(build, "derive_feature_readiness", return_value={}),
            mock.patch.object(build, "run_facts_engine", return_value={}) as engine,
            mock.patch.object(build, "format_incomplete_report", return_value=[]),
        ):
            build.run_data_pipeline(
                args=args, output_dir=Path(self.tmp.name), database_path=self.path, entries=[], protocols=[],
                abg_mps=[], mp_lookup={}, catalog=None,
            )
        self.assertEqual(engine.call_args.kwargs["today"], facts.date(2026, 7, 1))


class CliGuardTests(unittest.TestCase):
    def test_a_negative_vote_scan_page_count_is_rejected(self) -> None:
        with mock.patch.object(sys, "argv", ["build", "--vote-scan-pages", "-3"]), mock.patch.object(
            sys, "stderr", new_callable=io.StringIO
        ) as stderr, self.assertRaises(SystemExit):
            build.parse_args()
        self.assertIn("--vote-scan-pages must be 0", stderr.getvalue())

    def test_the_printed_fix_quotes_an_output_directory_with_spaces(self) -> None:
        report = {
            "sitting_gaps": {"21/1": {"date": "2026-07-01", "reasons": {"dossier": "not_persisted"}}},
            "incomplete_periods": [{"period_kind": "week", "period_key": "2026-W27",
                                    "sittings": [{"document_number": "21/1", "date": "2026-07-01", "reasons": {"dossier": "not_persisted"}}]}],
        }
        text = "\n".join(build.format_incomplete_report(
            report, output_dir=Path("my site/out"), catalog_protocols=[], vote_scan_pages=30))
        self.assertIn("--output-dir 'my site/out' --backfill-incomplete", text)

    def test_the_printed_report_names_a_sitting_dip_dates_differently(self) -> None:
        report = {
            "sitting_gaps": {"21/4": {"date": "2026-07-01", "reasons": {"dossier": "date_changed"}}},
            "incomplete_periods": [{"period_kind": "week", "period_key": "2026-W27",
                                    "sittings": [{"document_number": "21/4", "date": "2026-07-01", "reasons": {"dossier": "date_changed"}}]}],
        }
        text = "\n".join(build.format_incomplete_report(
            report, output_dir=Path("out"), catalog_protocols=[], vote_scan_pages=30))
        self.assertIn("DIP dates 1 stored sittings differently now: 21/4", text)


if __name__ == "__main__":
    unittest.main()
