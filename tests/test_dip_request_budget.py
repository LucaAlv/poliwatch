"""DIP request budget (a3-pilot.md, second attempt 2026-10-23): DIP stops answering
after about a hundred requests, so no request may be spent on what is already
known."""

from __future__ import annotations

import unittest
from unittest import mock

import _support  # noqa: F401
import build_dip_pulse_site as build
import validate_dip_protocol as dip


def paged(pages: list[dict]) -> mock.Mock:
    return mock.Mock(side_effect=[dict(page) for page in pages])


class NumFoundStopTests(unittest.TestCase):
    def list_all(self, pages: list[dict]) -> tuple[list[dict], int]:
        get_json = paged(pages)
        with mock.patch.object(dip.ApiClient, "get_json", get_json):
            documents = dip.ApiClient(api_key="k").list_all("/vorgangsposition", {"f.vorgang": "1"})
        return documents, get_json.call_count

    # Value: protects=a list that fits in one page costs one request; fails_when=list_all asks
    # for the next cursor page only to learn the list has ended (23 of 46 requests in the
    # 2026-10-23 pilot); seam=ApiClient.list_all with get_json stubbed.
    def test_a_list_complete_on_its_first_page_costs_one_request(self) -> None:
        documents, calls = self.list_all([
            {"documents": [{"id": "1"}, {"id": "2"}], "cursor": "a", "numFound": 2},
            {"documents": [], "cursor": "a", "numFound": 2},
        ])
        self.assertEqual([d["id"] for d in documents], ["1", "2"])
        self.assertEqual(calls, 1)

    # Value: protects=a repeated document across pages does not end the list early;
    # fails_when=the stop counts documents, not distinct ids; seam=ApiClient.list_all.
    def test_a_duplicate_across_pages_keeps_paging(self) -> None:
        documents, calls = self.list_all([
            {"documents": [{"id": "1"}, {"id": "2"}], "cursor": "a", "numFound": 3},
            {"documents": [{"id": "2"}, {"id": "3"}], "cursor": "b", "numFound": 3},
            {"documents": [], "cursor": "b", "numFound": 3},
        ])
        self.assertEqual(calls, 2)
        self.assertEqual(sorted({d["id"] for d in documents}), ["1", "2", "3"])

    def test_without_a_count_the_cursor_still_ends_the_list(self) -> None:
        for count in (None, True, "2"):
            with self.subTest(numFound=count):
                pages = [{"documents": [{"id": "1"}, {"id": "2"}], "cursor": "a"}, {"documents": [], "cursor": "a"}]
                if count is not None:
                    for page in pages:
                        page["numFound"] = count
                _, calls = self.list_all(pages)
                self.assertEqual(calls, 2)

    # Value: protects=the catalog fetch also stops once DIP's count is reached;
    # fails_when=fetch_protocols pays for an end-of-list page each run; seam=fetch_protocols
    # with the client stubbed.
    def test_the_catalog_stops_once_the_count_is_reached(self) -> None:
        client = mock.Mock()
        client.get_json.side_effect = [
            {"documents": [{"id": "1"}, {"id": "2"}], "cursor": "a", "numFound": 3},
            {"documents": [{"id": "3"}], "cursor": "b", "numFound": 3},
            {"documents": [], "cursor": "b", "numFound": 3},
        ]
        self.assertEqual(len(build.fetch_protocols(client, 0, [], None)), 3)
        self.assertEqual(client.get_json.call_count, 2)


if __name__ == "__main__":
    unittest.main()
