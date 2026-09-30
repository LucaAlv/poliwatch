from __future__ import annotations

import io
import unittest
from unittest import mock

import _support  # noqa: F401
import validate_dip_protocol as dip


def candidate_page(entries: list[tuple[str, str, str | None]]) -> str:
    blocks = []
    for vote_id, title, number in entries:
        doc = f"<p>Drucksache {number}</p>" if number else "<p>Beschluss</p>"
        blocks.append(
            f'<div class="col-xs-12 bt-slide"><canvas id="canvas-na-{vote_id}"></canvas>'
            f'<span class="bt-date">01.07.2026</span><span class="bt-dachzeile"></span>'
            f'<h3>{title}</h3><div class="bt-teaser-haupttext">{doc}</div>'
            '<div data-chart-values="10,5,1,2"></div></div>'
        )
    return "".join(blocks)


class Client:
    def list_all(self, path: str, params: dict[str, str]) -> list[dict]:
        return []


def agenda(*headings: str) -> dict:
    return {"agenda_items": [
        {"index": i, "top_id": f"TOP {i}", "heading": heading, "page_range": None,
         "drucksachen": [], "speeches": [], "contributions": [], "question_formats": []}
        for i, heading in enumerate(headings, 1)
    ]}


def detail(candidate: dict) -> dict:
    return {**candidate, "fractions": [], "members": [], "result_raw": None, "result_source": None}


class SittingVoteCaptureTests(unittest.TestCase):
    def enrich(self, html: str, tops: dict) -> dict:
        def fetch(url: str) -> str:
            return html if "offset=0" in url else ""

        with mock.patch.object(dip, "fetch_html", side_effect=fetch), mock.patch.object(
            dip, "fetch_roll_call_vote_detail", side_effect=detail
        ), mock.patch("sys.stderr", io.StringIO()):
            return dip.enrich_with_api(
                Client(), {"id": "p1", "dokumentnummer": "21/90", "datum": "2026-07-01"},
                tops, person_limit=0, vote_scan_pages=3,
            )

    def test_unique_title_match_attaches_candidate_even_without_drucksache(self) -> None:
        report = self.enrich(candidate_page([("1", "Entwurf eines Gesetzes zur Beratung", None)]),
                             agenda("Entwurf eines Gesetzes zur Beratung"))
        vote = report["agenda_items"][0]["votes"][0]
        self.assertEqual(vote["id"], "1")
        self.assertEqual(vote["protocol_id"], "p1")
        self.assertEqual(report["sitting_votes"], [])
        self.assertEqual(report["acquisition"]["votes"]["acquisition_state"], "complete")

    def test_ambiguous_title_match_is_preserved_at_sitting_level_and_complete(self) -> None:
        report = self.enrich(candidate_page([("1", "Entwurf eines Gesetzes zur Beratung", None)]),
                             agenda("Entwurf eines Gesetzes zur Beratung", "Entwurf eines Gesetzes zur Beratung"))
        self.assertEqual([v["id"] for v in report["sitting_votes"]], ["1"])
        self.assertEqual(report["sitting_votes"][0]["protocol_id"], "p1")
        self.assertEqual(report["agenda_items"][0]["votes"], [])
        self.assertEqual(report["acquisition"]["votes"]["records"], 1)
        self.assertEqual(report["acquisition"]["votes"]["acquisition_state"], "complete")

    def test_failed_fetch_of_unassigned_candidate_still_marks_incomplete(self) -> None:
        html = candidate_page([("1", "Nicht zuordenbarer Vorgang", None)])
        def fetch(url: str) -> str:
            return html if "offset=0" in url else ""

        with mock.patch.object(dip, "fetch_html", side_effect=fetch), mock.patch.object(
            dip, "fetch_roll_call_vote_detail", side_effect=dip.DipError("timeout")
        ), mock.patch("sys.stderr", io.StringIO()):
            report = dip.enrich_with_api(
                Client(), {"id": "p1", "dokumentnummer": "21/90", "datum": "2026-07-01"},
                agenda("Haushalt"), person_limit=0, vote_scan_pages=3,
            )
        self.assertEqual(report["sitting_votes"], [])
        self.assertEqual(report["acquisition"]["votes"]["acquisition_state"], "failed")
        self.assertEqual(report["acquisition"]["votes"]["failure_reasons"], ["source_unavailable"])


if __name__ == "__main__":
    unittest.main()
