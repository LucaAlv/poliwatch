"""DIP option B (docs/plans/a3-option-b-handoff.md): a closed Wahlperiode's Drucksache
positions and persons are downloaded in bulk, into the cross-run caches the build
already reads, so a backfill sitting stops paying one request per Vorgang and person."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import dip_cache
import prefetch_dip_bulk as prefetch
import validate_dip_protocol as dip

NOW = datetime(2026, 10, 23, 20, 0, tzinfo=timezone.utc)


def position(pid: str, vorgang: str, datum: str, number: str, *, wp: int = 19) -> dict:
    return {"id": pid, "vorgang_id": vorgang, "datum": datum, "dokumentart": "Drucksache", "wahlperiode": wp,
            "vorgangsposition": "Gesetzentwurf", "titel": f"Titel {vorgang}",
            "fundstelle": {"dokumentnummer": number, "herausgeber": "BT", "drucksachetyp": "Gesetzentwurf",
                           "datum": datum, "pdf_url": f"https://dserver.bundestag.de/{number}.pdf", "urheber": []}}


class FakeDip:
    """DIP's cursor-paged /vorgangsposition and /person lists over fixed records,
    ``page_size`` per page, honouring f.datum.start/f.datum.end (inclusive)."""

    def __init__(self, positions: list[dict], persons: list[dict] | None = None, page_size: int = 2,
                 fail_after: int | None = None) -> None:
        self.positions, self.persons, self.page_size, self.fail_after = positions, persons or [], page_size, fail_after
        self.requests: list[dict] = []

    def get_json(self, path: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        if self.fail_after is not None and len(self.requests) >= self.fail_after:
            raise dip.DipUnavailable("DIP stopped answering")
        self.requests.append({"path": path, **params})
        if path == "/person":
            records = self.persons
        else:
            start, end = params.get("f.datum.start"), params.get("f.datum.end")
            records = [p for p in self.positions if str(p["wahlperiode"]) == str(params["f.wahlperiode"])
                       and (start is None or p["datum"] >= start) and (end is None or p["datum"] <= end)]
        offset = int(params.get("cursor") or 0)
        page = records[offset:offset + self.page_size]
        return {"numFound": len(records), "documents": [dict(r) for r in page],
                "cursor": str(offset + len(page)) if page else str(offset)}


def catalog(*sittings: tuple[str, str]) -> dict:
    return {"authoritative": True, "fetched_at": "2026-10-23T00:00:00Z", "full_fetched_at": "2026-10-23T00:00:00Z",
            "protocols": [{"id": n, "dokumentnummer": n, "datum": d} for n, d in sittings]}


class PrefetchTestCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.output_dir = Path(tmp.name)
        (self.output_dir / "data").mkdir()
        self.write_catalog(catalog(("19/1", "2017-10-24"), ("19/2", "2017-12-12"), ("20/1", "2021-10-26")))

    def write_catalog(self, payload: dict) -> None:
        (self.output_dir / "data" / "plenarprotokoll-catalog.json").write_text(json.dumps(payload), encoding="utf-8")

    def drucksachen(self, fake: FakeDip, wahlperiode: int = 19) -> prefetch.DrucksachenResult:
        with mock.patch("sys.stderr"):
            return prefetch.prefetch_drucksachen(fake, self.output_dir, wahlperiode, now=NOW)

    def cache(self) -> dip_cache.DipCache:
        return dip_cache.DipCache.load(self.output_dir, newest_wahlperiode=20, now=NOW)


class DrucksachenTests(PrefetchTestCase):
    # Value: protects=a bulk-filled Vorgang holds what the one-at-a-time query gives, in its
    # order (date, then position id; 19/238's 23 Vorgänge), across month chunks; fails_when=
    # positions are grouped per chunk, unordered, or cached under the wrong Wahlperiode;
    # seam=prefetch_drucksachen with DIP stubbed, read back through DipCache.load.
    def test_positions_are_grouped_per_vorgang_in_date_then_id_order(self) -> None:
        fake = FakeDip([
            position("30", "v1", "2017-12-01", "19/300"),
            position("10", "v1", "2017-10-30", "19/100"),
            position("9", "v2", "2017-11-15", "19/90"),
            position("12", "v1", "2017-11-15", "19/120"),
            position("11", "v1", "2017-11-15", "19/110"),
            position("13", "v1", "2017-11-01", "19/130"),
            position("100", "v1", "2017-11-15", "19/1000"),
        ])
        result = self.drucksachen(fake)
        self.assertTrue(result.complete)
        entries = self.cache().vorgang_drucksachen
        self.assertEqual(entries["v1"]["wahlperiode"], 19)
        self.assertEqual([d["vorgangsposition_id"] for d in entries["v1"]["drucksachen"]], ["10", "13", "11", "12", "100", "30"])
        self.assertEqual(entries["v1"]["drucksachen"][0],
                         dip.compact_drucksache_position(position("10", "v1", "2017-10-30", "19/100")))
        self.assertEqual([d["dokumentnummer"] for d in entries["v2"]["drucksachen"]], ["19/90"])

    # Value: protects=a run capped by --max-chunks stages what it fetched and neither asks for
    # the total nor merges; fails_when=a partial download reaches the cache; seam=prefetch_drucksachen.
    def test_a_capped_run_stages_chunks_and_merges_nothing(self) -> None:
        fake = FakeDip([position("1", "v1", "2017-11-02", "19/1"), position("2", "v2", "2017-12-03", "19/2")])
        with mock.patch("sys.stderr"):
            result = prefetch.prefetch_drucksachen(fake, self.output_dir, 19, now=NOW, max_chunks=2)
        self.assertEqual((result.complete, result.chunks_staged, result.chunks), (False, 2, 3))
        self.assertEqual(len(fake.requests), 3)  # the Wahlperiode's total, then one page per chunk
        self.assertEqual(self.cache().vorgang_drucksachen, {})
        self.assertEqual(len(prefetch.staged_positions(self.output_dir, 19)), 2)

    # Value: protects=positions dated before the first or after the last sitting are kept
    # (a Bundesrat decision follows the last sitting), and a run DIP stops keeps its whole
    # chunks and resumes after them, merging only once all are staged; fails_when=edge
    # chunks are closed, a stop loses staged chunks, a resume re-asks for them, or a
    # partial download reaches the cache; seam=prefetch_drucksachen.
    def test_a_stopped_run_resumes_at_the_first_chunk_not_staged(self) -> None:
        positions = [position("1", "v1", "2017-01-05", "19/1"), position("2", "v1", "2017-11-02", "19/2"),
                     position("3", "v2", "2018-03-01", "19/3")]
        stopped = FakeDip(positions, fail_after=2)
        with self.assertRaises(dip.DipUnavailable):
            self.drucksachen(stopped)
        self.assertEqual(self.cache().vorgang_drucksachen, {})
        resumed = FakeDip(positions)
        result = self.drucksachen(resumed)
        self.assertTrue(result.complete)
        self.assertEqual((result.chunks, result.total, result.positions), (3, 3, 3))
        # Newest first: the open last chunk was staged before the stop and is not asked again.
        self.assertEqual(stopped.requests[1].get("f.datum.start"), "2017-12-01")
        self.assertNotIn("f.datum.end", stopped.requests[1])
        self.assertTrue(all(r.get("f.datum.start") != "2017-12-01" for r in resumed.requests))
        self.assertEqual(sorted(self.cache().vorgang_drucksachen), ["v1", "v2"])

    # Value: protects=nothing is merged when the chunks do not add up to the Wahlperiode's
    # total (a boundary that drops or doubles a day); fails_when=the merge trusts the chunks
    # alone; seam=prefetch_drucksachen.
    def test_chunks_that_do_not_add_up_to_the_total_merge_nothing(self) -> None:
        fake = FakeDip([position("1", "v1", "2017-11-02", "19/1")])
        real = fake.get_json

        def short_total(path, params=None):
            page = real(path, params)
            if "f.datum.start" not in (params or {}) and "f.datum.end" not in (params or {}):
                page["numFound"] += 1
            return page

        fake.get_json = short_total
        with self.assertRaises(prefetch.PrefetchError):
            self.drucksachen(fake)
        self.assertEqual(self.cache().vorgang_drucksachen, {})

    # Value: protects=the current Wahlperiode, which DIP still extends, keeps the
    # one-at-a-time path; fails_when=it is bulk-cached; seam=prefetch_drucksachen.
    def test_the_current_wahlperiode_is_refused_before_any_request(self) -> None:
        fake = FakeDip([])
        with self.assertRaises(prefetch.PrefetchError):
            self.drucksachen(fake, wahlperiode=20)
        self.assertEqual(fake.requests, [])

    # Value: protects=a Vorgang the bulk list did not hold stays uncached, so the build
    # fetches it one at a time (19/238 has one with no Drucksache, and a mitberaten Vorgang
    # may sit in another Wahlperiode), and a cached entry that differs from the bulk answer
    # is kept and reported; fails_when=the bulk writes empty entries for unseen Vorgänge or
    # overwrites a one-at-a-time answer; seam=prefetch_drucksachen, read back via DipCache.
    def test_only_seen_vorgaenge_are_written_and_a_differing_entry_is_kept(self) -> None:
        cache = self.cache()
        cache.vorgang_drucksachen["v1"] = {"wahlperiode": 19, "drucksachen": [{"dokumentnummer": "19/0"}]}
        cache.vorgang_drucksachen["v3"] = {"wahlperiode": 19, "drucksachen": []}
        cache.save()
        result = self.drucksachen(FakeDip([position("1", "v1", "2017-11-02", "19/1"),
                                           position("2", "v2", "2017-12-03", "19/2")]))
        entries = self.cache().vorgang_drucksachen
        self.assertEqual(sorted(entries), ["v1", "v2", "v3"])
        self.assertEqual(entries["v1"]["drucksachen"], [{"dokumentnummer": "19/0"}])
        self.assertEqual(entries["v3"]["drucksachen"], [])
        self.assertEqual((result.vorgaenge_written, result.vorgaenge_differing), (1, ["v1"]))

    # Value: protects=a Vorgang listed in two Wahlperioden is incomplete in each bulk list,
    # so it is left to the one-at-a-time query; fails_when=either half is cached as the
    # whole; seam=prefetch_drucksachen for WP 18, then WP 19.
    def test_a_vorgang_in_two_wahlperioden_is_dropped_from_the_cache(self) -> None:
        self.write_catalog(catalog(("18/1", "2014-01-10"), ("19/1", "2017-11-01"), ("20/1", "2021-10-26")))
        fake = FakeDip([position("1", "v1", "2014-01-10", "18/1", wp=18), position("2", "v9", "2014-01-11", "18/2", wp=18),
                        position("3", "v1", "2017-11-01", "19/1"), position("4", "v2", "2017-11-02", "19/2")])
        self.drucksachen(fake, wahlperiode=18)
        self.assertIn("v1", self.cache().vorgang_drucksachen)
        result = self.drucksachen(fake, wahlperiode=19)
        self.assertEqual(result.vorgaenge_in_two_wahlperioden, ["v1"])
        self.assertEqual(sorted(self.cache().vorgang_drucksachen), ["v2", "v9"])

    # Value: protects=a dated chunk that DIP answers with the whole Wahlperiode (a date filter
    # ignored or misnamed) stops after one page, before paging ~740 pages of it; fails_when=
    # the chunk is paged through and passes its own count; seam=prefetch_drucksachen.
    def test_a_chunk_as_large_as_the_whole_wahlperiode_stops_after_one_page(self) -> None:
        fake = FakeDip([position(str(i), "v1", "2017-11-02", f"19/{i}") for i in range(1, 6)])
        real = fake.get_json
        fake.get_json = lambda path, params=None: real(path, {k: v for k, v in (params or {}).items()
                                                               if not k.startswith("f.datum")})
        with self.assertRaises(prefetch.PrefetchError):
            self.drucksachen(fake)
        self.assertEqual(len(fake.requests), 2)  # the Wahlperiode's total, then the chunk's first page
        self.assertEqual(prefetch.staged_positions(self.output_dir, 19), [])

    # Value: protects=a neighbouring Wahlperiode downloaded only as evidence (WP 17, or WP 20,
    # whose Vorgänge run on into the open WP 21) drops the Vorgänge it shares from the cache
    # and caches none of its own; fails_when=its possibly incomplete Vorgänge are cached, or
    # the shared ones stay; seam=prefetch_drucksachen(overlap_only=True) after a full WP 18.
    def test_an_overlap_only_wahlperiode_drops_shared_vorgaenge_and_caches_nothing(self) -> None:
        self.write_catalog(catalog(("17/1", "2009-10-27"), ("18/1", "2014-01-10"), ("20/1", "2021-10-26")))
        fake = FakeDip([position("1", "v1", "2014-01-10", "18/1", wp=18), position("2", "v9", "2014-01-11", "18/2", wp=18),
                        position("3", "v9", "2009-11-01", "17/1", wp=17), position("4", "v5", "2009-11-02", "17/2", wp=17)])
        self.drucksachen(fake, wahlperiode=18)
        with mock.patch("sys.stderr"):
            result = prefetch.prefetch_drucksachen(fake, self.output_dir, 17, now=NOW, overlap_only=True)
        self.assertTrue(result.complete)
        self.assertEqual((result.vorgaenge_in_two_wahlperioden, result.vorgaenge_written), (["v9"], 0))
        self.assertEqual(sorted(self.cache().vorgang_drucksachen), ["v1"])


class PersonsTests(PrefetchTestCase):
    # Value: protects=bulk persons enter the person cache as fetched now (so they expire like
    # a single lookup) and a cached record that differs in more than a volatile field is
    # named; fails_when=bulk records skip the expiry, or differences go unreported;
    # seam=prefetch_persons, read back via DipCache.load.
    def test_bulk_persons_are_cached_as_fetched_now_and_differences_named(self) -> None:
        cache = dip_cache.DipCache.load(self.output_dir, newest_wahlperiode=20, now=NOW - prefetch.timedelta(days=20))
        cache.persons["7"] = {"id": "7", "nachname": "Alt", "aktualisiert": "2020"}
        cache.persons["8"] = {"id": "8", "nachname": "Gleich", "aktualisiert": "2020"}
        cache.save()
        fake = FakeDip([], persons=[{"id": "7", "nachname": "Neu", "aktualisiert": "2026"},
                                    {"id": "8", "nachname": "Gleich", "aktualisiert": "2026"},
                                    {"id": "9", "nachname": "Dritte"}])
        with mock.patch("sys.stderr"):
            result = prefetch.prefetch_persons(fake, self.output_dir, 19, now=NOW)
        self.assertEqual((result.persons, result.differing), (3, {"7": ["nachname"]}))
        self.assertEqual(self.cache().persons["7"]["nachname"], "Neu")
        def alive(days: int) -> list[str]:
            return sorted(dip_cache.DipCache.load(self.output_dir, newest_wahlperiode=20,
                                                  now=NOW + prefetch.timedelta(days=days)).persons)
        self.assertEqual(alive(dip_cache.PERSON_MAX_AGE_DAYS - 1), ["7", "8", "9"])
        self.assertEqual(alive(dip_cache.PERSON_MAX_AGE_DAYS + 1), [])


class ExitCodeTests(PrefetchTestCase):
    """bulk_drip.py rests on exit 3 and stops for a human on 1, so a silent DIP must be 3."""

    def main(self, read_logged) -> int:
        with mock.patch.object(dip, "_read_logged", side_effect=read_logged), \
                mock.patch.object(dip, "load_local_env"), mock.patch.object(dip.time, "sleep"), \
                mock.patch.dict("os.environ", {"DIP_API_KEY": "k"}), mock.patch("sys.stderr"), mock.patch("sys.stdout"):
            return prefetch.main(["--output-dir", str(self.output_dir), "--wahlperiode", "19", "--drucksachen"])

    # Value: protects=the request that finds DIP silent (a plain DipError, before the breaker
    # opens) ends the run as "DIP stopped", while a count that does not add up stops for a
    # human; fails_when=a timeout exits 1 and the runner gives up instead of resting;
    # seam=prefetch_dip_bulk.main with the HTTP read stubbed.
    def test_a_silent_dip_exits_3_and_a_bad_count_exits_1(self) -> None:
        self.assertEqual(self.main(TimeoutError("timed out")), 3)
        page = json.dumps({"numFound": 5, "documents": [{"id": "1", "dokumentart": "Drucksache"}]}).encode()
        self.assertEqual(self.main(lambda *a: page), 1)


if __name__ == "__main__":
    unittest.main()
