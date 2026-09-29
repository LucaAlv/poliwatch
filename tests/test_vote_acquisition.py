"""E4: a vote acquisition is `complete` only with full evidence.

The roll-call list is read newest first. A scan proves it saw every vote of a
sitting's date only when it passed that date or ran off the end of the list;
using every --vote-scan-pages page without either proves nothing about older
sittings. These tests pin the state each ending produces, what a cached report
keeps, and that a failed scan does not delete the votes an earlier one found.
"""

from __future__ import annotations

import io
import unittest
from unittest import mock

import _support  # noqa: F401
import build_dip_pulse_site as build_site
import publication_state as publication
import validate_dip_protocol as dip


def list_page(*entries: tuple[str, str, str]) -> str:
    """One roll-call list page: (vote id, DD.MM.YYYY, document number) per entry."""
    return "".join(
        f"""
        <div class="col-xs-12 bt-slide">
          <canvas id="canvas-na-{vote_id}"></canvas>
          <span class="bt-date">{date}</span>
          <span class="bt-dachzeile">TOP</span>
          <h3>TOP Abstimmung {vote_id}</h3>
          <div class="bt-teaser-haupttext"><p>Drucksache {number}</p></div>
          <div data-chart-values="10,5,1,2"></div>
        </div>
        """
        for vote_id, date, number in entries
    )


def paged(pages: list[str]):
    """A fetch_html stand-in serving `pages` by offset; past the end it is empty."""
    requested: list[str] = []

    def fake(url: str) -> str:
        requested.append(url)
        offset = int(url.split("offset=")[1].split("&")[0])
        index = offset // 10
        return pages[index] if index < len(pages) else ""

    fake.requested = requested  # type: ignore[attr-defined]
    return fake


class ScanEndTests(unittest.TestCase):
    def fetch(self, pages: list[str], date: str, scan_pages: int, **kwargs):
        with mock.patch.object(dip, "fetch_html", side_effect=paged(pages)):
            return dip.fetch_roll_call_vote_candidates(
                date, scan_pages, include_diagnostics=True, **kwargs
            )

    def test_passing_the_sittings_date_ends_the_scan_as_date_passed(self) -> None:
        pages = [list_page(("1", "02.07.2026", "21/1")), list_page(("2", "01.07.2026", "21/2"), ("3", "30.06.2026", "21/3"))]
        result = self.fetch(pages, "2026-07-01", 5)
        self.assertEqual(result.scan_end, "date_passed")
        self.assertEqual([c["id"] for c in result.candidates], ["2"])

    def test_running_off_the_end_of_the_list_is_list_end(self) -> None:
        pages = [list_page(("1", "02.07.2026", "21/1"))]
        result = self.fetch(pages, "2026-07-01", 5)
        self.assertEqual(result.scan_end, "list_end")
        self.assertFalse(result.selector_warning)

    def test_using_every_page_without_reaching_the_date_is_budget_exhausted(self) -> None:
        pages = [list_page(("1", "05.07.2026", "21/1")), list_page(("2", "04.07.2026", "21/2")), list_page(("3", "03.07.2026", "21/3"))]
        result = self.fetch(pages, "2026-07-01", 2)
        self.assertEqual(result.scan_end, "budget_exhausted")
        self.assertEqual(result.pages_fetched, 2)

    def test_a_page_cache_shares_list_pages_between_sittings(self) -> None:
        pages = [list_page(("1", "05.07.2026", "21/1")), list_page(("2", "01.07.2026", "21/2"), ("3", "30.06.2026", "21/3"))]
        fake = paged(pages)
        cache: dict[str, str] = {}
        with mock.patch.object(dip, "fetch_html", side_effect=fake):
            first = dip.fetch_roll_call_vote_candidates("2026-07-01", 5, include_diagnostics=True, page_cache=cache)
            second = dip.fetch_roll_call_vote_candidates("2026-07-05", 5, include_diagnostics=True, page_cache=cache)
        self.assertEqual(len(fake.requested), 2)
        self.assertEqual((first.pages_fetched, first.pages_from_cache), (2, 0))
        self.assertEqual((second.pages_fetched, second.pages_from_cache), (0, 2))

    def test_a_failed_page_is_not_cached_as_a_page(self) -> None:
        cache: dict[str, str] = {}
        with mock.patch.object(dip, "fetch_html", side_effect=dip.DipError("boom")):
            with self.assertRaises(dip.DipError):
                dip.fetch_roll_call_vote_candidates("2026-07-01", 3, page_cache=cache)
        # Only the outage marker is remembered, never a page.
        self.assertEqual(cache, {dip.ROLL_CALL_OUTAGE_KEY: "boom"})

    def test_one_failed_list_page_stops_further_list_fetches_in_the_build(self) -> None:
        cache: dict[str, str] = {}
        opener = mock.Mock(side_effect=dip.DipError("boom"))
        with mock.patch.object(dip, "fetch_html", opener):
            with self.assertRaises(dip.DipError):
                dip.fetch_roll_call_vote_candidates("2026-07-01", 5, page_cache=cache)
            with self.assertRaisesRegex(dip.DipError, "unavailable earlier in this build"):
                dip.fetch_roll_call_vote_candidates("2026-07-02", 5, page_cache=cache)
        self.assertEqual(opener.call_count, 1)
        # Without a shared cache nothing is remembered.
        with mock.patch.object(dip, "fetch_html", opener):
            with self.assertRaises(dip.DipError):
                dip.fetch_roll_call_vote_candidates("2026-07-02", 5)
        self.assertEqual(opener.call_count, 2)

    def test_not_scanning_is_not_a_scan_end(self) -> None:
        result = dip.fetch_roll_call_vote_candidates("2026-07-01", 0, include_diagnostics=True)
        self.assertEqual(result.scan_end, "not_scanned")


class FakeClient:
    def list_all(self, path: str, params: dict[str, str]) -> list[dict[str, str]]:
        return []


def agenda(*numbers: str) -> dict:
    return {
        "agenda_items": [
            {
                "index": index,
                "top_id": f"TOP {index}",
                "heading": f"Punkt {index}",
                "page_range": None,
                "drucksachen": [{"dokumentnummer": number}],
                "speeches": [],
            }
            for index, number in enumerate(numbers, start=1)
        ]
    }


def fake_detail(candidate: dict) -> dict:
    return {**candidate, "fractions": [], "members": [], "result_raw": None, "result_source": None}


class EnrichWithApiVoteStateTests(unittest.TestCase):
    def enrich(self, pages: list[str], date: str, numbers: tuple[str, ...], scan_pages: int = 30):
        stderr = io.StringIO()
        with mock.patch.object(dip, "fetch_html", side_effect=paged(pages)), mock.patch.object(
            dip, "fetch_roll_call_vote_detail", side_effect=fake_detail
        ), mock.patch("sys.stderr", stderr):
            enrichment = dip.enrich_with_api(
                FakeClient(),  # type: ignore[arg-type]
                {"id": "p1", "dokumentnummer": "21/90", "datum": date},
                agenda(*numbers),
                person_limit=0,
                vote_scan_pages=scan_pages,
            )
        return enrichment, stderr.getvalue()

    def test_a_verified_zero_vote_sitting_is_complete_and_stamped(self) -> None:
        # The list reaches an older date, so the sitting's date was fully read:
        # no vote that day is a fact, not a gap.
        pages = [list_page(("1", "05.07.2026", "21/1"), ("2", "30.06.2026", "21/2"))]
        enrichment, _ = self.enrich(pages, "2026-07-01", ("21/9",))
        votes = enrichment["acquisition"]["votes"]
        self.assertEqual(votes["acquisition_state"], "complete")
        self.assertEqual(votes["records"], 0)
        self.assertTrue(votes["acquired_at"])
        self.assertEqual(votes["failure_reasons"], [])
        self.assertEqual(enrichment["api_totals"]["roll_call_scan_end"], "date_passed")

    def test_matched_votes_make_a_complete_acquisition(self) -> None:
        pages = [list_page(("1", "01.07.2026", "21/1"), ("2", "30.06.2026", "21/2"))]
        enrichment, _ = self.enrich(pages, "2026-07-01", ("21/1",))
        votes = enrichment["acquisition"]["votes"]
        self.assertEqual((votes["acquisition_state"], votes["records"]), ("complete", 1))
        self.assertEqual(enrichment["api_totals"]["unmatched_roll_call_vote_count"], 0)

    def test_an_unmatched_candidate_is_logged_and_recorded(self) -> None:
        pages = [list_page(("1", "01.07.2026", "21/1"), ("2", "01.07.2026", "21/77"), ("3", "30.06.2026", "21/3"))]
        enrichment, stderr = self.enrich(pages, "2026-07-01", ("21/1",))
        self.assertEqual(enrichment["api_totals"]["unmatched_roll_call_vote_count"], 1)
        self.assertEqual(enrichment["api_records"]["unmatched_roll_call_vote_ids"], ["2"])
        self.assertIn("roll-call vote 2", stderr)
        self.assertIn("matched no TOP", stderr)
        self.assertTrue(any("1 von 2" in warning for warning in enrichment["warnings"]))
        # The vote is on the list but in no TOP, so it is not in the store: the
        # sitting's votes are known to be short.
        votes = enrichment["acquisition"]["votes"]
        self.assertEqual((votes["acquisition_state"], votes["failure_reasons"]), ("partial", ["unmatched_candidate"]))
        self.assertEqual(votes["records"], 1)
        self.assertEqual(enrichment["api_totals"]["roll_call_scan_end"], "date_passed")

    def test_no_candidate_matching_any_top_keeps_the_existing_warning(self) -> None:
        pages = [list_page(("1", "01.07.2026", "21/77"), ("2", "30.06.2026", "21/2"))]
        enrichment, _ = self.enrich(pages, "2026-07-01", ("21/1",))
        self.assertTrue(any("keine passte" in warning for warning in enrichment["warnings"]))
        self.assertEqual(enrichment["api_totals"]["unmatched_roll_call_vote_count"], 1)

    def test_budget_exhaustion_with_some_votes_is_partial_with_its_own_reason(self) -> None:
        pages = [list_page(("1", "01.07.2026", "21/1")), list_page(("2", "01.07.2026", "21/2"))]
        enrichment, stderr = self.enrich(pages, "2026-07-01", ("21/1", "21/2"), scan_pages=2)
        votes = enrichment["acquisition"]["votes"]
        self.assertEqual(votes["acquisition_state"], "partial")
        self.assertEqual(votes["failure_reasons"], ["scan_budget_exhausted"])
        self.assertEqual(votes["records"], 2)
        self.assertEqual(votes["rejected"], 0)
        self.assertIn("raise --vote-scan-pages", stderr)

    def test_budget_exhaustion_without_votes_is_failed_not_complete(self) -> None:
        pages = [list_page(("1", "05.07.2026", "21/1")), list_page(("2", "04.07.2026", "21/2"))]
        enrichment, _ = self.enrich(pages, "2026-07-01", ("21/1",), scan_pages=2)
        votes = enrichment["acquisition"]["votes"]
        self.assertEqual(votes["acquisition_state"], "failed")
        self.assertEqual(votes["failure_reasons"], ["scan_budget_exhausted"])
        self.assertEqual(votes["presentation_state"], "unavailable")
        self.assertIsNone(votes["acquired_at"])

    def test_a_failed_list_fetch_fails_the_votes_not_the_dossier(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(dip, "fetch_html", side_effect=dip.DipError("boom")), mock.patch("sys.stderr", stderr):
            enrichment = dip.enrich_with_api(
                FakeClient(),  # type: ignore[arg-type]
                {"id": "p1", "dokumentnummer": "21/90", "datum": "2026-07-01"},
                agenda("21/1"),
                person_limit=0,
                vote_scan_pages=3,
            )
        votes = enrichment["acquisition"]["votes"]
        self.assertEqual((votes["acquisition_state"], votes["failure_reasons"]), ("failed", ["source_unavailable"]))
        self.assertEqual(enrichment["agenda_items"][0]["votes"], [])
        self.assertIn("roll-call list unavailable", stderr.getvalue())

    def test_a_failing_vote_detail_makes_the_acquisition_partial(self) -> None:
        pages = [list_page(("1", "01.07.2026", "21/1"), ("2", "01.07.2026", "21/2"), ("3", "30.06.2026", "21/3"))]

        def detail(candidate: dict) -> dict:
            if candidate["id"] == "2":
                raise dip.DipError("timeout")
            return fake_detail(candidate)

        stderr = io.StringIO()
        with mock.patch.object(dip, "fetch_html", side_effect=paged(pages)), mock.patch.object(
            dip, "fetch_roll_call_vote_detail", side_effect=detail
        ), mock.patch("sys.stderr", stderr):
            enrichment = dip.enrich_with_api(
                FakeClient(),  # type: ignore[arg-type]
                {"id": "p1", "dokumentnummer": "21/90", "datum": "2026-07-01"},
                agenda("21/1", "21/2"),
                person_limit=0,
                vote_scan_pages=3,
            )
        votes = enrichment["acquisition"]["votes"]
        self.assertEqual((votes["acquisition_state"], votes["records"]), ("partial", 1))
        self.assertEqual(votes["failure_reasons"], ["source_unavailable"])

    def test_a_failed_vote_request_does_not_blame_the_top_matching_for_the_votes_it_never_read(self) -> None:
        pages = [list_page(("1", "01.07.2026", "21/1"), ("2", "01.07.2026", "21/2"), ("3", "30.06.2026", "21/3"))]
        calls: list[str] = []

        def detail(candidate: dict) -> dict:
            calls.append(candidate["id"])
            raise dip.DipError("timeout")

        stderr = io.StringIO()
        with mock.patch.object(dip, "fetch_html", side_effect=paged(pages)), mock.patch.object(
            dip, "fetch_roll_call_vote_detail", side_effect=detail
        ), mock.patch("sys.stderr", stderr):
            enrichment = dip.enrich_with_api(
                FakeClient(),  # type: ignore[arg-type]
                {"id": "p1", "dokumentnummer": "21/90", "datum": "2026-07-01"},
                agenda("21/1", "21/2"),
                person_limit=0,
                vote_scan_pages=3,
            )
        # The first failure stops further vote requests for this sitting.
        self.assertEqual(len(calls), 1)
        votes = enrichment["acquisition"]["votes"]
        self.assertEqual((votes["acquisition_state"], votes["records"]), ("failed", 0))
        self.assertEqual(votes["failure_reasons"], ["source_unavailable"])
        self.assertIn("vote details unavailable", stderr.getvalue())
        self.assertNotIn("matched no TOP", stderr.getvalue())
        self.assertFalse(any("keinem TOP" in warning for warning in enrichment["warnings"]))

    def test_the_progress_log_counts_the_requests_the_vote_scan_made(self) -> None:
        pages = [list_page(("1", "01.07.2026", "21/1"), ("2", "01.07.2026", "21/77"), ("3", "30.06.2026", "21/3"))]
        lines: list[str] = []
        with mock.patch.object(dip, "fetch_html", side_effect=paged(pages)), mock.patch.object(
            dip, "fetch_roll_call_vote_detail", side_effect=fake_detail
        ), mock.patch("sys.stderr", io.StringIO()):
            dip.enrich_with_api(
                FakeClient(),  # type: ignore[arg-type]
                {"id": "p1", "dokumentnummer": "21/90", "datum": "2026-07-01"},
                agenda("21/1"),
                person_limit=0,
                vote_scan_pages=30,
                progress=lines.append,
            )
        self.assertIn("Roll-call scan ended by date_passed: 1 list page(s) fetched, 0 reused from this build.", lines)
        self.assertIn("Roll-call details: 1 vote(s) fetched (2 requests), 1 candidate(s) matched no TOP.", lines)

    def test_a_vote_without_an_xlsx_link_or_official_result_is_still_complete(self) -> None:
        # The Namenslisten endpoint only serves a rolling window, so an older
        # vote normally has neither; only the votes themselves count.
        pages = [list_page(("1", "01.07.2026", "21/1"), ("2", "30.06.2026", "21/2"))]
        enrichment, _ = self.enrich(pages, "2026-07-01", ("21/1",))
        vote = enrichment["agenda_items"][0]["votes"][0]
        self.assertIsNone(vote.get("xlsx_url"))
        self.assertIsNone(vote.get("result_source"))
        self.assertEqual(enrichment["acquisition"]["votes"]["acquisition_state"], "complete")

    def test_no_scan_is_not_requested(self) -> None:
        enrichment, _ = self.enrich([], "2026-07-01", ("21/1",), scan_pages=0)
        self.assertEqual(enrichment["acquisition"]["votes"]["acquisition_state"], "not_requested")

    def test_build_report_refuses_to_claim_a_requested_scan_without_evidence(self) -> None:
        # enrich_with_api always reports its own state; a caller that gets none
        # back must not turn "requested" into "complete".
        protocol = {"id": "5805", "dokumentnummer": "21/87", "fundstelle": {"xml_url": "https://example.test/p.xml"}}
        args = mock.Mock(api_key="k", sleep=0, person_limit=0, vote_scan_pages=30, roll_call_list_id=None, limit_tops=None)
        enrichment = {"agenda_items": [], "api_totals": {}, "warnings": [], "sampled_people": [], "api_records": {}}
        with mock.patch.object(dip, "fetch_text", return_value="<xml />"), mock.patch.object(
            dip, "parse_protocol_xml", return_value={"xml_protocol": {}, "agenda_items": []}
        ), mock.patch.object(dip, "enrich_with_api", return_value=enrichment), mock.patch("sys.stderr", io.StringIO()):
            with self.assertRaises(dip.DipError):
                dip.build_report(args, protocol=protocol)


def votes_facts(state: str, *, records: int = 0, reasons: tuple[str, ...] = (), acquired_at: str | None = None,
                attempted_at: str | None = None) -> dict:
    return publication.DomainFacts(
        domain="votes",
        acquisition_state=state,
        source="bundestag-roll-call",
        records=records,
        failure_reasons=reasons,
        acquired_at=acquired_at,
        attempted_at=attempted_at,
        attempted=attempted_at is not None,
    ).as_dict()


def report_with(votes: int, acquisition: dict | None) -> dict:
    report: dict = {
        "protocol": {"dokumentnummer": "21/90"},
        "agenda_items": [
            {"top_id": "TOP 1", "index": 1, "votes": [{"id": str(n), "title": f"V{n}", "date": "2026-07-10"} for n in range(votes)]}
        ],
    }
    if acquisition is not None:
        report["acquisition"] = {"votes": acquisition}
    return report


class CachedVoteStateTests(unittest.TestCase):
    def annotate(self, report: dict, existing: dict | None, scan_pages: int) -> dict:
        build_site.annotate_report_acquisition(
            report, existing, vote_scan_pages=scan_pages, profile_resolver=None, summary_mode="off"
        )
        return report["acquisition"]["votes"]

    def test_reusing_a_cached_partial_report_keeps_its_partial_state(self) -> None:
        prior = votes_facts("partial", records=3, reasons=("scan_budget_exhausted",),
                            acquired_at="2026-09-01T10:00:00Z", attempted_at="2026-09-01T10:00:00Z")
        votes = self.annotate(report_with(3, None), report_with(3, prior), scan_pages=0)
        self.assertEqual(votes["acquisition_state"], "partial")
        self.assertEqual(votes["failure_reasons"], ["scan_budget_exhausted"])
        self.assertEqual(votes["acquired_at"], "2026-09-01T10:00:00Z")
        self.assertEqual((votes["records"], votes["reused"]), (3, 3))

    def test_reusing_a_cached_failed_report_keeps_the_failure(self) -> None:
        prior = votes_facts("failed", reasons=("source_unavailable",), attempted_at="2026-09-01T10:00:00Z")
        votes = self.annotate(report_with(0, None), report_with(0, prior), scan_pages=0)
        self.assertEqual((votes["acquisition_state"], votes["failure_reasons"]), ("failed", ["source_unavailable"]))

    def test_reusing_a_verified_zero_vote_sitting_keeps_it_complete(self) -> None:
        prior = votes_facts("complete", acquired_at="2026-09-01T10:00:00Z", attempted_at="2026-09-01T10:00:00Z")
        votes = self.annotate(report_with(0, None), report_with(0, prior), scan_pages=0)
        self.assertEqual(votes["acquisition_state"], "complete")
        self.assertEqual(votes["acquired_at"], "2026-09-01T10:00:00Z")

    def test_cached_votes_from_a_report_without_metadata_have_no_acquired_at(self) -> None:
        votes = self.annotate(report_with(2, None), report_with(2, None), scan_pages=0)
        self.assertEqual(votes["acquisition_state"], "complete")
        self.assertIsNone(votes["acquired_at"])

    def test_no_votes_and_no_history_is_not_requested(self) -> None:
        votes = self.annotate(report_with(0, None), None, scan_pages=0)
        self.assertEqual(votes["acquisition_state"], "not_requested")

    def test_a_failed_recheck_keeps_a_verified_acquisition_and_records_the_attempt(self) -> None:
        prior = votes_facts("complete", records=2, acquired_at="2026-09-01T10:00:00Z", attempted_at="2026-09-01T10:00:00Z")
        existing = report_with(2, prior)
        fresh = report_with(0, votes_facts("failed", reasons=("scan_budget_exhausted",), attempted_at="2026-09-28T10:00:00Z"))
        build_site.reuse_existing_dossier_enrichments(fresh, existing, votes=True, profiles=True)
        votes = self.annotate(fresh, existing, scan_pages=30)
        self.assertEqual(len(fresh["agenda_items"][0]["votes"]), 2)
        # The earlier scan verified this sitting; a failed re-check does not undo it.
        self.assertEqual(votes["acquisition_state"], "complete")
        self.assertEqual(votes["acquired_at"], "2026-09-01T10:00:00Z")
        self.assertEqual(votes["attempted_at"], "2026-09-28T10:00:00Z")
        self.assertEqual(votes["failure_reasons"], ["scan_budget_exhausted"])
        self.assertEqual((votes["records"], votes["reused"]), (2, 2))

    def test_a_failed_recheck_keeps_a_verified_zero_vote_sitting(self) -> None:
        prior = votes_facts("complete", records=0, acquired_at="2026-09-01T10:00:00Z", attempted_at="2026-09-01T10:00:00Z")
        existing = report_with(0, prior)
        fresh = report_with(0, votes_facts("failed", reasons=("source_unavailable",), attempted_at="2026-09-28T10:00:00Z"))
        build_site.reuse_existing_dossier_enrichments(fresh, existing, votes=True, profiles=True)
        votes = self.annotate(fresh, existing, scan_pages=30)
        self.assertEqual((votes["acquisition_state"], votes["records"]), ("complete", 0))
        self.assertEqual(votes["acquired_at"], "2026-09-01T10:00:00Z")
        self.assertEqual(votes["failure_reasons"], ["source_unavailable"])

    def test_a_failed_scan_over_partial_cached_votes_stays_partial(self) -> None:
        prior = votes_facts("partial", records=2, reasons=("scan_budget_exhausted",),
                            acquired_at="2026-09-01T10:00:00Z", attempted_at="2026-09-01T10:00:00Z")
        existing = report_with(2, prior)
        fresh = report_with(0, votes_facts("failed", reasons=("source_unavailable",), attempted_at="2026-09-28T10:00:00Z"))
        build_site.reuse_existing_dossier_enrichments(fresh, existing, votes=True, profiles=True)
        votes = self.annotate(fresh, existing, scan_pages=30)
        self.assertEqual(votes["acquisition_state"], "partial")
        self.assertEqual(votes["failure_reasons"], ["source_unavailable"])

    def test_a_failed_scan_over_unstamped_cached_votes_stays_partial(self) -> None:
        existing = report_with(2, None)  # cached before acquisition metadata existed
        fresh = report_with(0, votes_facts("failed", reasons=("source_unavailable",), attempted_at="2026-09-28T10:00:00Z"))
        build_site.reuse_existing_dossier_enrichments(fresh, existing, votes=True, profiles=True)
        self.assertEqual(self.annotate(fresh, existing, scan_pages=30)["acquisition_state"], "partial")

    def test_a_vote_on_two_tops_is_one_reused_vote(self) -> None:
        prior = votes_facts("partial", records=1, reasons=("scan_budget_exhausted",), acquired_at="2026-09-01T10:00:00Z",
                            attempted_at="2026-09-01T10:00:00Z")
        existing = report_with(1, prior)
        second = {"top_id": "TOP 2", "index": 2, "votes": [dict(existing["agenda_items"][0]["votes"][0])]}
        existing["agenda_items"].append(second)
        fresh = report_with(0, votes_facts("failed", reasons=("source_unavailable",), attempted_at="2026-09-28T10:00:00Z"))
        fresh["agenda_items"].append({"top_id": "TOP 2", "index": 2, "votes": []})
        build_site.reuse_existing_dossier_enrichments(fresh, existing, votes=True, profiles=True)
        votes = self.annotate(fresh, existing, scan_pages=30)
        self.assertEqual((votes["records"], votes["reused"]), (1, 1))

    def test_a_complete_scan_replaces_cached_votes(self) -> None:
        prior = votes_facts("complete", records=2, acquired_at="2026-09-01T10:00:00Z", attempted_at="2026-09-01T10:00:00Z")
        fresh = report_with(0, votes_facts("complete", acquired_at="2026-09-28T10:00:00Z", attempted_at="2026-09-28T10:00:00Z"))
        build_site.reuse_existing_dossier_enrichments(fresh, report_with(2, prior), votes=False, profiles=True)
        votes = self.annotate(fresh, report_with(2, prior), scan_pages=30)
        self.assertEqual(fresh["agenda_items"][0]["votes"], [])
        self.assertEqual((votes["acquisition_state"], votes["records"]), ("complete", 0))


if __name__ == "__main__":
    unittest.main()
