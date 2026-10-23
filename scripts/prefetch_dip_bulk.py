"""DIP option B (docs/plans/a3-option-b-handoff.md, owner approved 2026-10-23): fill the
cross-run DIP caches (dip_cache) for a closed Wahlperiode from a few bulk lists, so a
backfill sitting stops paying one request per Vorgang and per person. DIP answers
about a hundred requests and then goes silent for hours, and a WP 18/19 backfill
one Vorgang at a time is about 7,000 Vorgang requests; these lists are about 1,150.

- Drucksache positions: ``/vorgangsposition?f.wahlperiode=N&f.dokumentart=Drucksache``
  in month chunks over the Wahlperiode's sittings, the first and last chunk open, so
  positions dated before the first or after the last sitting are not lost. Each chunk
  is checked against its own ``numFound`` and staged under ``data/dip-bulk/wp<N>/``
  once whole, so a run DIP stops resumes at the first chunk not staged. Chunks go
  newest first. Only when every chunk is staged and they add up to the Wahlperiode's
  total are the positions grouped per Vorgang, in the order the one-at-a-time query
  gives (date, then position id), and merged into the Vorgang cache.
- Persons: ``/person?f.wahlperiode=N`` into the person cache, fetched now, so they
  expire like a single lookup (PERSON_MAX_AGE_DAYS); re-run before a backfill session.

The build is unchanged: a cached Vorgang or person costs it no request, and one the
bulk lists did not hold is fetched one at a time, as before. Only Vorgänge the bulk
saw are written, never an empty answer for one it did not. A cached entry that
differs from the bulk answer is kept and reported, never overwritten. A Vorgang
found in two Wahlperioden' bulk lists is incomplete in each, so it is dropped from
the cache and left to the one-at-a-time query.

Never run this while a build writes the same output directory: a build loads the
caches once and rewrites them after every sitting.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import dip_cache
import facts
import validate_dip_protocol as dip

STAGING_DIRNAME = "dip-bulk"
#: The build's backfill pace (build_dip_pulse_site.BACKFILL_SLEEP_SECONDS).
SLEEP_SECONDS = 2.0
#: Fields of a person record that change without the person changing.
VOLATILE_PERSON_FIELDS = frozenset({"aktualisiert"})


class PrefetchError(dip.DipError):
    """A bulk list that cannot be trusted: a count that does not add up, or a
    Wahlperiode this command does not serve."""


@dataclass
class DrucksachenResult:
    wahlperiode: int
    chunks: int
    chunks_staged: int
    complete: bool = False
    total: int | None = None
    positions: int = 0
    vorgaenge_written: int = 0
    vorgaenge_matching_cache: int = 0
    #: Vorgang ids whose cached entry differs from the bulk answer (kept as cached).
    vorgaenge_differing: list[str] = field(default_factory=list)
    #: Vorgang ids also in another Wahlperiode's bulk list (dropped from the cache).
    vorgaenge_in_two_wahlperioden: list[str] = field(default_factory=list)


@dataclass
class PersonsResult:
    wahlperiode: int
    persons: int = 0
    #: person id -> fields that differ from the cached record (volatile ones aside).
    differing: dict[str, list[str]] = field(default_factory=dict)


def counted_list(
    client: Any, path: str, params: dict[str, Any], *, below: int | None = None
) -> tuple[list[dict[str, Any]], int]:
    """Every document of a cursor-paged list and DIP's count, raising unless the
    distinct ids equal the count, and after the first page when the count is not
    ``below`` the given bound."""
    params = dict(params)
    documents: list[dict[str, Any]] = []
    num_found: int | None = None
    previous_cursor = None
    while True:
        page = client.get_json(path, params)
        batch = page.get("documents") or [] if isinstance(page, dict) else None
        if not isinstance(batch, list) or not all(isinstance(d, dict) for d in batch):
            raise dip.DipError(f"DIP API returned an unexpected body for {path}: {str(page)[:200]}")
        documents.extend(batch)
        num_found = dip.page_count(page) if dip.page_count(page) is not None else num_found
        if below is not None and (num_found is None or num_found >= below):
            raise PrefetchError(f"DIP counts {num_found} documents for {path} {params}, not fewer than {below}")
        below = None
        cursor = page.get("cursor")
        if not batch or not cursor or cursor == previous_cursor or dip.holds_all(documents, num_found):
            break
        previous_cursor = cursor
        params["cursor"] = cursor
    distinct = len({str(d.get("id")) for d in documents})
    if num_found is None or distinct != num_found:
        raise PrefetchError(f"DIP listed {distinct} distinct documents for {path} {params}, not {num_found}")
    return documents, num_found


def _catalog_protocols(output_dir: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads((output_dir / "data" / facts.CATALOG_FILENAME).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PrefetchError(f"no readable catalog in {output_dir / 'data'}: run a build first ({exc})") from exc
    if not isinstance(payload, dict) or payload.get("authoritative") is not True:
        raise PrefetchError("the cached catalog is not authoritative: run a build first")
    return [p for p in payload.get("protocols") or [] if isinstance(p, dict)]


def _wahlperiode_of(protocol: dict[str, Any]) -> int | None:
    head = str(protocol.get("dokumentnummer") or "").split("/", 1)[0].strip()
    return int(head) if head.isdigit() else None


def newest_wahlperiode(output_dir: Path) -> int | None:
    return max(filter(None, map(_wahlperiode_of, _catalog_protocols(output_dir))), default=None)


def sitting_span(output_dir: Path, wahlperiode: int) -> tuple[date, date]:
    """First and last sitting date of a closed Wahlperiode, from the cached catalog."""
    protocols = _catalog_protocols(output_dir)
    newest = max(filter(None, map(_wahlperiode_of, protocols)), default=None)
    if newest is None or wahlperiode >= newest:
        raise PrefetchError(f"Wahlperiode {wahlperiode} is not closed (newest in the catalog: {newest})")
    dates = sorted(
        date.fromisoformat(str(p["datum"])[:10]) for p in protocols if _wahlperiode_of(p) == wahlperiode and p.get("datum")
    )
    if not dates:
        raise PrefetchError(f"the catalog lists no sitting of Wahlperiode {wahlperiode}")
    return dates[0], dates[-1]


def month_chunks(first: date, last: date) -> list[tuple[str | None, str | None]]:
    """Inclusive (f.datum.start, f.datum.end) per calendar month from ``first`` to
    ``last``, newest first; the oldest has no start and the newest no end."""
    chunks: list[tuple[str | None, str | None]] = []
    month = first.replace(day=1)
    while month <= last:
        following = (month + timedelta(days=32)).replace(day=1)
        chunks.append((month.isoformat(), (following - timedelta(days=1)).isoformat()))
        month = following
    chunks[0] = (None, chunks[0][1])
    chunks[-1] = (chunks[-1][0], None)
    return chunks[::-1]


def staging_dir(output_dir: Path, wahlperiode: int) -> Path:
    return output_dir / "data" / STAGING_DIRNAME / f"wp{wahlperiode}"


def _chunk_path(output_dir: Path, wahlperiode: int, chunk: tuple[str | None, str | None]) -> Path:
    start, end = chunk
    return staging_dir(output_dir, wahlperiode) / f"drucksachen-{start or 'open'}_{end or 'open'}.json"


def _read_chunk(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) and isinstance(payload.get("positions"), list) else None


def _staged_position(position: dict[str, Any]) -> dict[str, Any]:
    # The position's own date and id are kept beside the compact entry: they are
    # the sort keys, and compact_drucksache_position keeps only the Fundstelle date.
    return {"id": position.get("id"), "datum": position.get("datum"), "compact": dip.compact_drucksache_position(position)}


def _order_key(staged: dict[str, Any]) -> tuple[str, int, str]:
    pid = str(staged.get("id") or "")
    return (str(staged.get("datum") or ""), int(pid) if pid.isdigit() else -1, pid)


def group_by_vorgang(staged: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Staged positions as the one-at-a-time query gives a Vorgang's Drucksachen:
    compact entries, one per position id, by date, then position id."""
    by_id = {str(p["id"]): p for p in staged if p.get("id") is not None}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in sorted(by_id.values(), key=_order_key):
        vorgang_id = item["compact"].get("vorgang_id")
        if vorgang_id:
            grouped.setdefault(str(vorgang_id), []).append(item["compact"])
    return grouped


def staged_positions(output_dir: Path, wahlperiode: int) -> list[dict[str, Any]]:
    """Every staged position of a Wahlperiode, whatever chunks are staged so far."""
    positions: list[dict[str, Any]] = []
    for path in sorted(staging_dir(output_dir, wahlperiode).glob("drucksachen-*.json")):
        positions.extend((_read_chunk(path) or {}).get("positions") or [])
    return positions


def prefetch_drucksachen(
    client: Any, output_dir: Path, wahlperiode: int, *, now: datetime | None = None, max_chunks: int = 0
) -> DrucksachenResult:
    """Stage the chunks not yet staged (at most ``max_chunks`` this run, 0 for all),
    then, once all are, merge them into the Vorgang cache. A DIP failure is raised
    after the chunks before it are staged."""
    now = now or datetime.now(timezone.utc)
    chunks = month_chunks(*sitting_span(output_dir, wahlperiode))
    base = {"f.wahlperiode": wahlperiode, "f.dokumentart": "Drucksache"}
    # A dated chunk must be smaller than the whole Wahlperiode: one that is not
    # had its date filter ignored, and paging it would spend several windows.
    total_path = staging_dir(output_dir, wahlperiode) / "total.json"
    wahlperiode_total: int | None = None
    if any(_read_chunk(_chunk_path(output_dir, wahlperiode, chunk)) is None for chunk in chunks):
        try:
            wahlperiode_total = int(json.loads(total_path.read_text(encoding="utf-8"))["numFound"])
        except (OSError, ValueError, KeyError, TypeError):
            wahlperiode_total = dip.page_count(client.get_json("/vorgangsposition", base))
            if wahlperiode_total is None:
                raise PrefetchError(f"DIP gives no count for Wahlperiode {wahlperiode}'s Drucksache positions")
            total_path.parent.mkdir(parents=True, exist_ok=True)
            dip.write_text_atomic(total_path, json.dumps({"numFound": wahlperiode_total, "fetched_at": now.strftime(
                "%Y-%m-%dT%H:%M:%SZ")}) + "\n")
    fetched = 0
    for chunk in chunks:
        path = _chunk_path(output_dir, wahlperiode, chunk)
        if _read_chunk(path) is not None:
            continue
        if max_chunks and fetched >= max_chunks:
            break
        start, end = chunk
        params = {**base, **({"f.datum.start": start} if start else {}), **({"f.datum.end": end} if end else {})}
        documents, num_found = counted_list(
            client, "/vorgangsposition", params, below=wahlperiode_total if len(chunks) > 1 else None
        )
        positions = [_staged_position(d) for d in documents if d.get("dokumentart") == "Drucksache"]
        path.parent.mkdir(parents=True, exist_ok=True)
        dip.write_text_atomic(path, json.dumps(
            {"params": params, "numFound": num_found, "fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
             "positions": positions}, ensure_ascii=False) + "\n")
        fetched += 1
        print(f"[bulk] WP {wahlperiode} {start or '…'}–{end or '…'}: {num_found} positions staged.", file=sys.stderr)
    staged = [_read_chunk(_chunk_path(output_dir, wahlperiode, chunk)) for chunk in chunks]
    result = DrucksachenResult(wahlperiode, len(chunks), sum(1 for s in staged if s is not None))
    if result.chunks_staged < len(chunks):
        return result
    result.total = dip.page_count(client.get_json("/vorgangsposition", base))
    positions = [p for s in staged if s for p in s["positions"]]
    counted = sum(int(s.get("numFound") or 0) for s in staged if s)
    distinct = len({str(p.get("id")) for p in positions})
    result.positions = distinct
    if result.total is None or not counted == distinct == result.total:
        raise PrefetchError(
            f"Wahlperiode {wahlperiode}: the chunks count {counted} positions ({distinct} distinct), DIP lists "
            f"{result.total}; nothing is merged"
        )
    _merge_vorgaenge(output_dir, wahlperiode, group_by_vorgang(positions), result, now)
    result.complete = True
    return result


def _merge_vorgaenge(
    output_dir: Path, wahlperiode: int, grouped: dict[str, list[dict[str, Any]]], result: DrucksachenResult, now: datetime
) -> None:
    dip.write_text_atomic(staging_dir(output_dir, wahlperiode) / "vorgaenge.json",
                          json.dumps(sorted(grouped), ensure_ascii=False) + "\n")
    elsewhere: set[str] = set()
    for other in (output_dir / "data" / STAGING_DIRNAME).glob("wp*/vorgaenge.json"):
        if other.parent.name != f"wp{wahlperiode}":
            try:
                elsewhere.update(map(str, json.loads(other.read_text(encoding="utf-8"))))
            except (OSError, ValueError):
                pass
    cache = dip_cache.DipCache.load(output_dir, newest_wahlperiode=newest_wahlperiode(output_dir), now=now)
    for vorgang_id, drucksachen in sorted(grouped.items()):
        if vorgang_id in elsewhere:
            result.vorgaenge_in_two_wahlperioden.append(vorgang_id)
            cache.vorgang_drucksachen.pop(vorgang_id, None)
            continue
        existing = cache.vorgang_drucksachen.get(vorgang_id)
        if existing is not None:
            if existing.get("drucksachen") == drucksachen:
                result.vorgaenge_matching_cache += 1
            else:
                result.vorgaenge_differing.append(vorgang_id)
            continue
        cache.vorgang_drucksachen[vorgang_id] = {"wahlperiode": wahlperiode, "drucksachen": drucksachen}
        result.vorgaenge_written += 1
    cache.save()


def person_differences(cached: dict[str, Any], fresh: dict[str, Any]) -> list[str]:
    return sorted(k for k in set(cached) | set(fresh) if k not in VOLATILE_PERSON_FIELDS and cached.get(k) != fresh.get(k))


def prefetch_persons(client: Any, output_dir: Path, wahlperiode: int, *, now: datetime | None = None) -> PersonsResult:
    """Every person DIP lists for the Wahlperiode, into the person cache as fetched now."""
    now = now or datetime.now(timezone.utc)
    records, _ = counted_list(client, "/person", {"f.wahlperiode": wahlperiode})
    cache = dip_cache.DipCache.load(output_dir, newest_wahlperiode=newest_wahlperiode(output_dir), now=now)
    result = PersonsResult(wahlperiode)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    for record in records:
        person_id = str(record.get("id") or "")
        if not person_id:
            continue
        if person_id in cache.persons and (fields := person_differences(cache.persons[person_id], record)):
            result.differing[person_id] = fields
        cache.persons[person_id] = record
        cache.person_fetched_at[person_id] = stamp
        result.persons += 1
    cache.save()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--wahlperiode", required=True, type=int)
    parser.add_argument("--drucksachen", action="store_true", help="stage and merge the Drucksache positions")
    parser.add_argument("--persons", action="store_true", help="refresh the persons of the Wahlperiode")
    parser.add_argument("--max-chunks", type=int, default=0, help="stage at most this many chunks (0: all)")
    parser.add_argument("--sleep", type=float, default=SLEEP_SECONDS)
    args = parser.parse_args(argv)
    if not (args.drucksachen or args.persons):
        parser.error("name --drucksachen, --persons or both")
    dip.load_local_env()
    api_key = os.environ.get("DIP_API_KEY")
    if not api_key:
        print("error: set DIP_API_KEY.", file=sys.stderr)
        return 1
    breaker = dip.DipBreaker()
    client = dip.ApiClient(api_key=api_key, sleep_seconds=args.sleep, breaker=breaker)
    try:
        if args.drucksachen:
            result = prefetch_drucksachen(client, args.output_dir, args.wahlperiode, max_chunks=args.max_chunks)
            print(f"[bulk] drucksachen {json.dumps(result.__dict__, ensure_ascii=False)}")
            if not result.complete:
                return 2
        if args.persons:
            persons = prefetch_persons(client, args.output_dir, args.wahlperiode)
            print(f"[bulk] persons {json.dumps(persons.__dict__, ensure_ascii=False)}")
    except dip.DipError as exc:
        # The request that finds DIP silent raises a plain DipError; the breaker
        # counts it, and only the requests after it raise DipUnavailable.
        if isinstance(exc, dip.DipUnavailable) or breaker.consecutive:
            print(f"[bulk] stopped, DIP did not answer: {exc}", file=sys.stderr)
            return 3
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
