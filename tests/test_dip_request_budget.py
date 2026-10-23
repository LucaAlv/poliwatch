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



def protocol(number: str, *, xml: bool = True) -> dict:
    wp, _, n = number.partition("/")
    return {"id": f"{wp}{int(n):04d}", "dokumentnummer": number,
            "fundstelle": {"xml_url": f"https://dserver.bundestag.de/btp/{wp}/{wp}{int(n):03d}.xml" if xml else ""}}


class CatalogReuseTests(unittest.TestCase):
    """Owner decision 2026-10-23: a closed Wahlperiode's catalog comes from the cache;
    the whole catalog is fetched when the cache is missing, older than 7 days since
    its last full fetch, or does not add up to DIP's total."""

    NOW = build.datetime(2026, 10, 23, 12, 0, tzinfo=build.timezone.utc)

    def setUp(self) -> None:
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.output_dir = build.Path(tmp.name)
        (self.output_dir / "data").mkdir()
        self.cached = [protocol("21/2"), protocol("21/1"), protocol("20/2"), protocol("20/1"), protocol("19/1")]

    def write_cache(self, protocols: list[dict], *, full: str = "2026-10-20T00:00:00Z") -> None:
        payload = {"authoritative": True, "fetched_at": "2026-10-22T00:00:00Z", "full_fetched_at": full,
                   "protocols": protocols}
        (self.output_dir / "data" / build.facts.CATALOG_FILENAME).write_text(build.json.dumps(payload), encoding="utf-8")

    def client(self, total: int, by_wp: dict[int, list[dict]]) -> mock.Mock:
        def get_json(path, params):
            wp = params.get("f.wahlperiode")
            if wp is None:
                return {"documents": [protocol("21/3")], "cursor": "x", "numFound": total}
            documents = by_wp[int(wp)]
            return {"documents": documents, "cursor": "c", "numFound": len(documents)}
        client = mock.Mock()
        client.get_json.side_effect = get_json
        return client

    def fetch(self, client: mock.Mock) -> tuple[list[str], str, mock.Mock]:
        full = mock.Mock(return_value=[protocol("21/3"), *self.cached])
        with mock.patch.object(build, "fetch_protocols", full):
            protocols, full_fetched_at = build.fetch_catalog(client, self.output_dir, now=self.NOW)
        return sorted(p["dokumentnummer"] for p in protocols), full_fetched_at, full

    # Value: protects=a run pays for the current Wahlperiode and one count, not 48 catalog pages;
    # fails_when=closed Wahlperioden are fetched again, or the merged catalog drops or repeats
    # a sitting; seam=fetch_catalog with the client stubbed.
    def test_a_fresh_cache_supplies_the_closed_wahlperioden(self) -> None:
        self.write_cache(self.cached)
        client = self.client(6, {21: [protocol("21/3"), protocol("21/2"), protocol("21/1")]})
        numbers, full_fetched_at, full = self.fetch(client)
        self.assertEqual(numbers, ["19/1", "20/1", "20/2", "21/1", "21/2", "21/3"])
        self.assertEqual(full_fetched_at, "2026-10-20T00:00:00Z")
        full.assert_not_called()
        self.assertEqual(client.get_json.call_count, 2)

    # Value: protects=the merged catalog is only used when it adds up to DIP's total, so a new
    # Wahlperiode or a gap in the cache forces the full fetch; seam=fetch_catalog.
    def test_a_count_mismatch_falls_back_to_the_full_fetch(self) -> None:
        self.write_cache(self.cached)
        numbers, full_fetched_at, full = self.fetch(self.client(7, {21: [protocol("21/3"), protocol("21/2"), protocol("21/1")]}))
        full.assert_called_once()
        self.assertEqual(full_fetched_at, "2026-10-23T12:00:00Z")
        self.assertEqual(len(numbers), 6)

    def test_a_missing_or_old_cache_falls_back_to_the_full_fetch(self) -> None:
        for case in ("missing", "old", "not authoritative"):
            with self.subTest(case=case):
                path = self.output_dir / "data" / build.facts.CATALOG_FILENAME
                path.unlink(missing_ok=True)
                if case == "old":
                    self.write_cache(self.cached, full="2026-10-15T11:59:00Z")
                elif case == "not authoritative":
                    path.write_text(build.json.dumps({"protocols": self.cached}), encoding="utf-8")
                client = self.client(6, {})
                _, _, full = self.fetch(client)
                full.assert_called_once()
                client.get_json.assert_not_called()

    # Value: protects=a closed Wahlperiode whose sitting has no XML yet is fetched fresh, so the
    # sitting becomes acquirable once DIP lists its XML; seam=fetch_catalog.
    def test_a_closed_wahlperiode_with_a_sitting_without_xml_is_fetched_fresh(self) -> None:
        self.cached[2] = protocol("20/2", xml=False)
        self.write_cache(self.cached)
        client = self.client(6, {21: [protocol("21/3"), protocol("21/2"), protocol("21/1")],
                                 20: [protocol("20/2"), protocol("20/1")]})
        numbers, _, full = self.fetch(client)
        full.assert_not_called()
        self.assertEqual(client.get_json.call_count, 3)
        self.assertEqual(numbers, ["19/1", "20/1", "20/2", "21/1", "21/2", "21/3"])

    # Value: protects=the real catalog's shape still reuses the cache: Wahlperioden 1-17 list no
    # XML for any sitting, and Sonderdrucke ("SDr 1981") carry no Wahlperiode; fails_when=either
    # forces a full fetch or a fresh fetch every run (found on the 4,677-entry catalog);
    # seam=fetch_catalog.
    def test_wahlperioden_without_any_xml_and_sonderdrucke_come_from_the_cache(self) -> None:
        self.cached += [protocol("17/1", xml=False), protocol("17/2", xml=False),
                        {"id": "sdr81", "dokumentnummer": "SDr 1981", "fundstelle": {}}]
        self.write_cache(self.cached)
        client = self.client(9, {21: [protocol("21/3"), protocol("21/2"), protocol("21/1")]})
        numbers, _, full = self.fetch(client)
        full.assert_not_called()
        self.assertEqual(client.get_json.call_count, 2)
        self.assertEqual(len(numbers), 9)

    # Value: protects=the age counts from the last full fetch, not the last merge, so a run every
    # day still refetches the whole catalog weekly; seam=render_site's catalog file.
    def test_a_merged_catalog_keeps_its_full_fetch_time(self) -> None:
        payload = build.catalog_payload([protocol("21/1")], full_fetched_at="2026-10-20T00:00:00Z")
        self.assertEqual(payload["full_fetched_at"], "2026-10-20T00:00:00Z")
        self.assertTrue(payload["authoritative"])


if __name__ == "__main__":
    unittest.main()
