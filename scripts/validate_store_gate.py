#!/usr/bin/env python3
"""The merged-store gate: replay, integrity, order independence, links, export.

    python3 scripts/validate_store_gate.py OUTPUT_DIR --receipt RECEIPT.json [--scratch DIR] [--today YYYY-MM-DD]

OUTPUT_DIR is a site output directory (``data/`` holds the cached reports,
their XML, the catalog and ``bundestag-pulse.sqlite``). It is replayed in place,
so run the gate on a clone (``cp -cR``), never on the reference directory. The
checks, in order:

1. ``--offline --repersist`` of OUTPUT_DIR (exit code, timing, whether the store
   was replaced), then ``PRAGMA integrity_check`` and ``foreign_key_check``.
   The replayed store must group the input store's bindings into persons as the
   input did and render the same Personenseiten with the same Reden, Beiträge
   and Stimmen (``replay_vs_input``).
2. Order independence: a fresh store from all cached reports, and a store built
   from every other report and then replayed with all of them, must group the
   person bindings into persons identically (``grouping_fingerprint``). All three
   run database-only on clones of ``data/`` under SCRATCH, each as an online build
   with ``--enrich mp-roster`` would, the DIP roster answered from
   ``data/dip-person-cache.json`` (``CachedRoster``). The fresh store must list the
   input store's roster records, and the replayed store must group the fresh
   store's bindings and render its Personenseiten as the fresh store does
   (``replay_vs_fresh``): a replay carries the registry and the preserved roster
   rows forward, while the fresh build starts from neither and ingests the roster.
3. A second unchanged replay must keep the store file as it is (same bytes and
   modification time) and say so.
4. A link audit over the rendered pages: every local ``href``/``src`` names an
   existing file, and every ``#fragment`` an existing id in it.
5. The export: ``data/exports/datenstand.json`` passes the manifest validator,
   every listed file exists with its size and checksum, and the protocol and
   vote counts match the store; ``--validate-publication`` passes.

The receipt (JSON) records each check, the store counts, the timings and the
fingerprints. Exit codes: 0 every check passed, 1 a check failed, 2 bad input.
Recreates the A1/A2 harness of 2026-10-05, which lived in /tmp and is gone
(docs/plans/a3-coverage.md, Phase 0).
"""

from __future__ import annotations

if __name__ == "__main__":
    from python_version_guard import require_supported_python

    require_supported_python()

import argparse
import hashlib
import html
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from dip_cache import PERSON_FILENAME  # noqa: E402
from stable_ids import key_prefix  # noqa: E402
BUILD = SCRIPTS / "build_dip_pulse_site.py"
STORE = Path("data") / "bundestag-pulse.sqlite"
# The figures of the last combined A1/A2 run (docs/plans/a1-scratch-validation.json,
# 2026-10-05), which this gate is measured against.
REFERENCE_2026_10_05 = {"speeches": 26271, "contributions": 16799, "persons": 3370}

_LINK = re.compile(r'\b(?:href|src)\s*=\s*"([^"]*)"')
_ID = re.compile(r'\bid\s*=\s*"([^"]*)"')


def _open_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)


def binding_ids(database_path: Path) -> set[str]:
    conn = _open_readonly(database_path)
    try:
        return {row[0] for row in conn.execute("SELECT id FROM person_bindings")}
    finally:
        conn.close()


def grouping_fingerprint(database_path: Path, *, only: set[str] | None = None) -> dict[str, Any]:
    """How the store groups occurrence bindings into persons, independent of the
    person ids it minted: each person becomes the sorted list of its binding
    ids, and the sorted list of those groups is hashed. ``only`` restricts it to
    those bindings (a replayed store also keeps the bindings of retired
    occurrences, which a fresh store cannot have)."""
    conn = _open_readonly(database_path)
    try:
        groups: dict[str, list[str]] = {}
        for binding_id, person_id in conn.execute("SELECT id, person_id FROM person_bindings"):
            if only is None or binding_id in only:
                groups.setdefault(person_id, []).append(binding_id)
    finally:
        conn.close()
    canonical = sorted("\x1f".join(sorted(ids)) for ids in groups.values())
    digest = hashlib.sha256("\x1e".join(canonical).encode("utf-8")).hexdigest()
    return {
        "fingerprint": digest,
        "groups": len(groups),
        "bindings": sum(len(ids) for ids in groups.values()),
    }


def dip_person_occurrences(database_path: Path) -> set[tuple[str, int]]:
    """The DIP person occurrences (roster rows and the people a report samples)
    of the store's current records, each with its record's ``mps.is_mdb``: which
    DIP persons the build saw and which of them the roster listed as MdBs. A
    record of this build has an ``mps`` row; a retired one keeps only its binding."""
    prefix = key_prefix("roster")
    conn = _open_readonly(database_path)
    try:
        return {(row[0], int(row[1])) for row in conn.execute(
            "SELECT b.id, m.is_mdb FROM person_bindings b JOIN mps m ON m.id = b.record_id WHERE substr(b.id, 1, ?) = ?",
            (len(prefix), prefix))}
    finally:
        conn.close()


def _group_key(binding_ids: list[str]) -> str:
    return hashlib.sha256("\x1f".join(sorted(binding_ids)).encode("utf-8")).hexdigest()


def person_pages(database_path: Path, *, only: set[str] | None = None) -> dict[str, dict[str, Any]]:
    """Every person with a Personenseite and its Reden, Beiträge and Stimmen, as
    ``collect_abgeordnete`` pools them, keyed by the person's binding ids (not its
    person id), so two stores compare person by person whatever keys they minted.
    ``only`` keys each person on those of its bindings (as ``grouping_fingerprint``
    restricts them); a person holding none of them keys on all of its own."""
    import build_dip_pulse_site as site

    conn = _open_readonly(database_path)
    conn.row_factory = sqlite3.Row
    try:
        bindings: dict[str, list[str]] = {}
        for binding_id, person_id in conn.execute("SELECT id, person_id FROM person_bindings"):
            bindings.setdefault(person_id, []).append(binding_id)
        mps, _lookup = site.collect_abgeordnete(conn)
    finally:
        conn.close()
    pages: dict[str, dict[str, Any]] = {}
    for mp in mps:
        if site.has_abgeordnete_page(mp):
            own = bindings.get(mp["id"], [mp["id"]])
            kept = [binding for binding in own if only is None or binding in only]
            pages[_group_key(kept or own)] = {
                "id": mp["id"], "name": mp["name"], "reden": mp["speech_count"],
                "beitraege": mp["contribution_count"], "stimmen": len(mp["votes"]),
            }
    return pages


_COUNTS = ("reden", "beitraege", "stimmen")


def compare_pages(before: dict[str, dict[str, Any]], after: dict[str, dict[str, Any]], *, limit: int = 50) -> dict[str, Any]:
    """Which Personenseiten a replay lost, gained or changed the counts of, with
    the page and count totals on each side."""
    def label(page: dict[str, Any]) -> dict[str, Any]:
        return {key: page[key] for key in ("id", "name", *_COUNTS)}

    lost = [label(before[key]) for key in sorted(before.keys() - after.keys())]
    gained = [label(after[key]) for key in sorted(after.keys() - before.keys())]
    changed = [{"before": label(before[key]), "after": label(after[key])} for key in sorted(before.keys() & after.keys())
               if any(before[key][count] != after[key][count] for count in _COUNTS)]
    totals = {side: {"pages": len(pages), **{count: sum(page[count] for page in pages.values()) for count in _COUNTS}}
              for side, pages in (("before", before), ("after", after))}
    return {"equal": not (lost or gained or changed), "totals": totals, "lost_count": len(lost), "gained_count": len(gained),
            "changed_count": len(changed), "lost": lost[:limit], "gained": gained[:limit], "changed": changed[:limit]}


def _ids(path: Path, cache: dict[Path, set[str]]) -> set[str]:
    if path not in cache:
        cache[path] = {html.unescape(value) for value in _ID.findall(path.read_text(encoding="utf-8", errors="replace"))}
    return cache[path]


def audit_links(site_dir: Path) -> dict[str, Any]:
    """Every local ``href``/``src`` of every rendered page names an existing file
    (a directory link means its ``index.html``), and every ``#fragment`` an id in
    that file. Links with a scheme or host, and ``data:`` URIs, are not checked."""
    site_dir = Path(site_dir).resolve()
    ids: dict[Path, set[str]] = {}
    broken: list[dict[str, str]] = []
    pages = links = 0
    for page in sorted(site_dir.rglob("*.html")):
        pages += 1
        text = page.read_text(encoding="utf-8", errors="replace")
        for raw in _LINK.findall(text):
            href = html.unescape(raw).strip()
            parts = urlsplit(href)
            if not href or parts.scheme or parts.netloc:
                continue
            links += 1
            if parts.path:
                target = (page.parent / unquote(parts.path)).resolve()
                if target.is_dir():
                    target = target / "index.html"
            else:
                target = page
            relative = str(page.relative_to(site_dir))
            if not target.is_file():
                broken.append({"page": relative, "href": href, "reason": "missing file"})
            elif parts.fragment and target.suffix == ".html" and unquote(parts.fragment) not in _ids(target, ids):
                broken.append({"page": relative, "href": href, "reason": "missing anchor"})
    return {"pages": pages, "links": links, "broken": broken}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_export(output_dir: Path) -> dict[str, Any]:
    """The export the Daten page publishes matches the store: the manifest passes
    the Daten validator, each listed file has its size and checksum, and the
    protocol and vote counts are the store's."""
    import build_dip_pulse_site as site

    exports = Path(output_dir) / "data" / "exports"
    manifest_path = exports / "datenstand.json"
    try:
        manifest = site.validate_manifest(json.loads(manifest_path.read_text(encoding="utf-8")), str(manifest_path))
    except (OSError, ValueError, RuntimeError) as exc:
        return {"problems": [str(exc)]}
    problems: list[str] = []
    generation = exports / manifest["generation"]
    for entry in manifest["files"]:
        path = generation / entry["name"]
        if not path.is_file():
            problems.append(f"{entry['name']}: listed in the manifest, missing in {generation.name}")
        elif path.stat().st_size != entry["bytes"] or _sha256(path) != entry["sha256"]:
            problems.append(f"{entry['name']}: size or sha256 differs from the manifest")
    conn = _open_readonly(Path(output_dir) / "data" / "bundestag-pulse.sqlite")
    try:
        store = {
            "protocols": conn.execute("SELECT COUNT(*) FROM protocols").fetchone()[0],
            "votes": conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0],
            "vote members": conn.execute("SELECT COUNT(*) FROM vote_members").fetchone()[0],
        }
    finally:
        conn.close()
    listed = {
        "protocols": manifest["protocols"].get("count"),
        "votes": manifest["votes"].get("count"),
        "vote members": manifest["votes"].get("members"),
    }
    for key, count in store.items():
        if listed[key] != count:
            problems.append(f"{key}: the manifest lists {listed[key]}, the store holds {count}")
    return {"generation": manifest["generation"], "files": len(manifest["files"]), "counts": store, "problems": problems}


def store_counts(database_path: Path) -> dict[str, Any]:
    """The row counts the receipt records, plus Beiträge per kind. The withheld
    tables (schema 12, ADR 0005) read as None in a store from before them: the
    gate counts the owner's store before the replay that upgrades it."""
    conn = _open_readonly(database_path)
    try:
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("protocols", "agenda_items", "speeches", "contributions", "mps", "person_records",
                          "person_bindings", "person_aliases", "documents", "votes", "vote_members", "facts")
        }
        has_withheld = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'withheld_units'").fetchone() is not None
        for table in ("withheld_units", "withheld_turns"):
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] if has_withheld else None
        counts["withheld_reasons"] = dict(conn.execute(
            "SELECT reason, COUNT(*) FROM withheld_units GROUP BY reason ORDER BY reason")) if has_withheld else None
        counts["withheld_words"] = conn.execute(
            "SELECT COALESCE(SUM(word_count), 0) FROM withheld_units").fetchone()[0] if has_withheld else None
        counts["persons"] = conn.execute("SELECT COUNT(DISTINCT person_id) FROM person_records").fetchone()[0]
        # Schema 10 stores a total the source did not give as NULL, not 0.
        counts["votes_without_total"] = conn.execute(
            "SELECT COUNT(*) FROM votes WHERE yes_count IS NULL OR no_count IS NULL OR abstain_count IS NULL OR absent_count IS NULL"
        ).fetchone()[0]
        counts["contribution_kinds"] = dict(conn.execute("SELECT kind, COUNT(*) FROM contributions GROUP BY kind ORDER BY kind"))
        counts["protocols_per_wahlperiode"] = dict(conn.execute(
            "SELECT substr(document_number, 1, instr(document_number, '/') - 1), COUNT(*) FROM protocols GROUP BY 1 ORDER BY 1"
        ))
    finally:
        conn.close()
    return counts


def integrity(database_path: Path) -> dict[str, Any]:
    conn = _open_readonly(database_path)
    try:
        check = [row[0] for row in conn.execute("PRAGMA integrity_check")]
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        conn.close()
    return {"integrity_check": check, "integrity_ok": check == ["ok"], "foreign_key_violations": len(violations)}


def withheld_also_counted(database_path: Path) -> list[str]:
    """Up to five withheld Reden whose rede_id is also a stored Rede or Beitrag
    of the same sitting. A withheld Rede is outside every count (ADR 0005)."""
    conn = _open_readonly(database_path)
    try:
        return [f"{protocol_id} {rede_id}" for protocol_id, rede_id in conn.execute(
            "SELECT w.protocol_id, w.rede_id FROM withheld_units w WHERE EXISTS (SELECT 1 FROM speeches s "
            "WHERE s.protocol_id = w.protocol_id AND s.rede_id = w.rede_id) OR EXISTS (SELECT 1 FROM contributions c "
            "WHERE c.protocol_id = w.protocol_id AND c.rede_id = w.rede_id) LIMIT 5")]
    finally:
        conn.close()


def _store_identity(database_path: Path) -> dict[str, Any]:
    status = database_path.stat()
    return {"sha256": _sha256(database_path), "bytes": status.st_size, "mtime_ns": status.st_mtime_ns, "inode": status.st_ino}


def _run(command: list[str], log_path: Path) -> dict[str, Any]:
    """Run one build command, its output into ``log_path``; returns exit code,
    seconds and the stderr tail."""
    started = time.monotonic()
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, text=True)
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return {
        "command": command[1:],
        "exit_code": process.returncode,
        "seconds": round(time.monotonic() - started, 1),
        "log": str(log_path),
        "store_replaced": "store replaced" in text,
        "store_kept": "store content unchanged, file kept" in text,
        "tail": text.splitlines()[-5:],
    }


def replay(output_dir: Path, today: str, log_path: Path) -> dict[str, Any]:
    """``--offline --repersist`` of ``output_dir``: store, pages and export."""
    return _run([sys.executable, str(BUILD), "--offline", "--repersist", "--output-dir", str(output_dir),
                 "--today", today], log_path)


class CachedRoster:
    """The DIP /person roster answered from the cached /person records, the only
    request ``ingest_mdb_roster`` makes: a record is listed for every Wahlperiode
    it names, as DIP's ``f.wahlperiode`` filter lists it."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records

    def list_all(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        if path != "/person" or set(params) != {"f.wahlperiode"}:
            raise ValueError(f"the cached roster answers only /person by f.wahlperiode, not {path} {sorted(params)}")
        return [record for record in self.records if params["f.wahlperiode"] in _wahlperioden(record)]


def _wahlperioden(record: dict[str, Any]) -> set[int]:
    value = record.get("wahlperiode")
    values = value if isinstance(value, list) else [value]
    return {int(number) for number in values if isinstance(number, int) or (isinstance(number, str) and number.isdigit())}


def cached_roster(output_dir: Path) -> CachedRoster:
    """Every /person record ``data/dip-person-cache.json`` holds, whatever its age
    (the gate rebuilds a store from them, it fetches nothing). Raises ValueError
    when the file is missing or not a person cache."""
    path = output_dir / "data" / PERSON_FILENAME
    try:
        persons = json.loads(path.read_text(encoding="utf-8")).get("persons")
    except (OSError, ValueError, AttributeError) as exc:
        raise ValueError(f"no readable DIP person cache at {path}: {exc}") from None
    if not isinstance(persons, dict):
        raise ValueError(f"{path} holds no persons object")
    return CachedRoster([entry["record"] for _key, entry in sorted(persons.items())
                         if isinstance(entry, dict) and isinstance(entry.get("record"), dict)])


def persist_only(output_dir: Path, today: str) -> None:
    """The database half of an online build with ``--enrich mp-roster``, offline:
    the cached reports, and the roster answered from the person cache. What the
    order-independence clones need; nothing is fetched, rendered or exported."""
    import build_dip_pulse_site as site
    import antrag_text
    import politikfelder

    roster = cached_roster(output_dir)
    database_path = output_dir / STORE
    protocols = site.load_cached_protocols(output_dir)
    periods = site.roster_periods(None, protocols)
    vorgang_cache = politikfelder.load_cache(output_dir)
    vorgang_cache[antrag_text.CACHE_NAMESPACE] = antrag_text.load_cache(output_dir)

    def ingest(staged: sqlite3.Connection) -> None:
        stats = site.ingest_mdb_roster(roster, staged, wahlperioden=periods)
        print(f"roster (cached): {stats}", file=sys.stderr)

    site.repersist_cached_reports(
        output_dir, database_path, protocols, preserve_roster=False, roster_ingest=ingest,
        today=date.fromisoformat(today), vorgang_cache=vorgang_cache,
    )


def _persist_clone(output_dir: Path, today: str, log_path: Path) -> dict[str, Any]:
    return _run([sys.executable, str(Path(__file__).resolve()), "--persist-only", str(output_dir), "--today", today], log_path)


def _require_disjoint_paths(source: Path, target: Path) -> None:
    source, target = source.resolve(), target.resolve()
    if source.is_relative_to(target) or target.is_relative_to(source):
        raise ValueError(f"clone target {target} must not overlap input {source}")


def _data_clone(source: Path, target: Path) -> Path:
    """A copy of ``source/data`` under ``target`` without its store: an APFS clone
    where the file system offers one."""
    _require_disjoint_paths(source, target)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    clone = ["cp", "-cR"] if sys.platform == "darwin" else ["cp", "-R"]
    subprocess.run([*clone, str(source / "data"), str(target / "data")], check=True)
    for path in (target / "data").glob("bundestag-pulse.sqlite*"):
        path.unlink()
    shutil.rmtree(target / "data" / "exports", ignore_errors=True)
    return target


def order_independence(output_dir: Path, scratch: Path, today: str) -> dict[str, Any]:
    """A fresh store from every cached report against one built from every other
    report and then replayed with all of them."""
    fresh = _data_clone(output_dir, scratch / "fresh")
    half = _data_clone(output_dir, scratch / "half")
    result: dict[str, Any] = {"fresh": _persist_clone(fresh, today, scratch / "fresh.log")}
    reports = sorted(p for p in (half / "data").glob("plenarprotokoll-*.json") if p.name != "plenarprotokoll-catalog.json")
    held_back = half / "held-back"
    held_back.mkdir()
    for report in reports[1::2]:
        report.rename(held_back / report.name)
    result["half"] = _persist_clone(half, today, scratch / "half.log")
    result["half"]["reports"] = len(reports) - len(reports[1::2])
    for report in held_back.iterdir():
        report.rename(half / "data" / report.name)
    result["half_then_full"] = _persist_clone(half, today, scratch / "half-then-full.log")
    if all(result[step]["exit_code"] == 0 for step in ("fresh", "half", "half_then_full")):
        result["fresh"]["grouping"] = grouping_fingerprint(fresh / STORE)
        result["half_then_full"]["grouping"] = grouping_fingerprint(half / STORE)
        result["equal"] = result["fresh"]["grouping"] == result["half_then_full"]["grouping"]
    else:
        result["equal"] = False
    return result


def replay_vs_input(input_store: dict[str, Any] | None, database_path: Path) -> dict[str, Any]:
    """The replayed store against the input store it replayed: the same grouping of
    the input's bindings into persons, and the same Personenseiten with the same
    Reden, Beiträge and Stimmen. The input is the reference (a fresh online build or
    an earlier replay of one), so any difference is the replay's doing; a branch
    that moves persons on purpose shows its moves here."""
    if input_store is None:
        return {"equal": False, "reason": "no input store to compare the replay with"}
    grouping = grouping_fingerprint(database_path, only=input_store["bindings"])
    pages = compare_pages(input_store["pages"], person_pages(database_path, only=input_store["bindings"]))
    return {"equal": grouping == input_store["grouping"] and pages["equal"],
            "grouping_before": input_store["grouping"], "grouping_after": grouping, "pages": pages}


def replay_vs_fresh(fresh_path: Path, database_path: Path, input_roster: set[tuple[str, int]] | None) -> dict[str, Any]:
    """The replayed store against a fresh build of the same reports and roster:
    the replay must group the fresh store's bindings and render its Personenseiten
    as the fresh build does. Unlike ``replay_vs_input`` this holds when the input
    was itself a replay. The fresh build counts as that reference only when it
    lists the input store's DIP persons as the input did (the person cache may
    lack a roster record)."""
    fresh_roster = dip_person_occurrences(fresh_path)
    roster = {"input": len(input_roster) if input_roster is not None else None, "fresh": len(fresh_roster),
              "missing_from_fresh": len(input_roster - fresh_roster) if input_roster is not None else None,
              "only_in_fresh": len(fresh_roster - input_roster) if input_roster is not None else None}
    roster["equal"] = input_roster is not None and input_roster == fresh_roster
    live = binding_ids(fresh_path)
    grouping = {"fresh": grouping_fingerprint(fresh_path), "replay": grouping_fingerprint(database_path, only=live)}
    pages = compare_pages(person_pages(fresh_path), person_pages(database_path, only=live))
    return {"equal": grouping["fresh"] == grouping["replay"] and pages["equal"], "roster": roster,
            "grouping": grouping, "pages": pages,
            "bindings_of_retired_occurrences": len(binding_ids(database_path) - live)}


def run_gate(output_dir: Path, scratch: Path, today: str) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    scratch = scratch.resolve()
    # Refuse unsafe scratch before even the first replay can change the input.
    for name in ("fresh", "half"):
        _require_disjoint_paths(output_dir, scratch / name)
    scratch.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    receipt: dict[str, Any] = {
        "output_dir": str(output_dir),
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": subprocess.run(["git", "-C", str(SCRIPTS), "rev-parse", "--short", "HEAD"],
                                 capture_output=True, text=True).stdout.strip(),
        "today": today,
        "reports": len([p for p in (output_dir / "data").glob("plenarprotokoll-*.json")
                        if p.name != "plenarprotokoll-catalog.json"]),
        "xml_files": len(list((output_dir / "data" / "xml").glob("*.xml"))),
    }
    database_path = output_dir / STORE
    input_store: dict[str, Any] | None = None
    if database_path.exists():
        receipt["counts_before"] = store_counts(database_path)
        # The input store as the replay finds it: an unchanged replay must
        # reproduce its grouping and every page's counts.
        started_snapshot = time.monotonic()
        input_store = {"bindings": binding_ids(database_path), "grouping": grouping_fingerprint(database_path),
                       "pages": person_pages(database_path), "roster": dip_person_occurrences(database_path)}
        receipt["input_snapshot_seconds"] = round(time.monotonic() - started_snapshot, 1)
    checks: dict[str, bool] = {}

    receipt["replay"] = replay(output_dir, today, scratch / "replay.log")
    checks["replay_exit_0"] = receipt["replay"]["exit_code"] == 0
    if checks["replay_exit_0"]:
        receipt["integrity"] = integrity(database_path)
        checks["sqlite_integrity_ok"] = receipt["integrity"]["integrity_ok"]
        checks["no_foreign_key_violations"] = receipt["integrity"]["foreign_key_violations"] == 0
        receipt["withheld_also_counted"] = withheld_also_counted(database_path)
        checks["no_withheld_rede_counted"] = not receipt["withheld_also_counted"]
        receipt["counts"] = store_counts(database_path)
        receipt["counts_vs_2026_10_05"] = {
            key: {"old": old, "new": receipt["counts"][key], "delta": receipt["counts"][key] - old}
            for key, old in REFERENCE_2026_10_05.items()
        }
        receipt["grouping"] = grouping_fingerprint(database_path)

    if checks["replay_exit_0"]:
        receipt["replay_vs_input"] = replay_vs_input(input_store, database_path)
        checks["replay_keeps_input_grouping_and_pages"] = receipt["replay_vs_input"]["equal"]

    receipt["order_independence"] = order_independence(output_dir, scratch, today)
    checks["half_then_full_groups_like_fresh"] = receipt["order_independence"]["equal"]
    if checks["replay_exit_0"]:
        # replay_vs_input compares with the input, which may itself be a replay;
        # this compares with a fresh build of the same reports and roster.
        if "grouping" in receipt["order_independence"]["fresh"]:
            receipt["replay_vs_fresh"] = replay_vs_fresh(
                scratch / "fresh" / STORE, database_path, input_store["roster"] if input_store else None)
        else:
            receipt["replay_vs_fresh"] = {"equal": False, "roster": {"equal": False},
                                          "reason": "the fresh build failed (order_independence.fresh)"}
        checks["fresh_build_lists_the_input_roster"] = receipt["replay_vs_fresh"]["roster"]["equal"]
        checks["replay_groups_like_fresh"] = receipt["replay_vs_fresh"]["equal"]

    if checks["replay_exit_0"]:
        before = _store_identity(database_path)
        receipt["unchanged_replay"] = replay(output_dir, today, scratch / "replay-unchanged.log")
        after = _store_identity(database_path)
        receipt["unchanged_replay"]["store_before"] = before
        receipt["unchanged_replay"]["store_after"] = after
        checks["unchanged_replay_exit_0"] = receipt["unchanged_replay"]["exit_code"] == 0
        checks["unchanged_replay_keeps_store"] = before == after and receipt["unchanged_replay"]["store_kept"]

        links = audit_links(output_dir)
        receipt["links"] = {**links, "broken": links["broken"][:50], "broken_count": len(links["broken"])}
        checks["no_broken_local_links"] = not links["broken"]
        receipt["export"] = check_export(output_dir)
        checks["export_matches_store"] = not receipt["export"]["problems"]
        publication = _run([sys.executable, str(BUILD), "--validate-publication", str(output_dir)],
                           scratch / "validate-publication.log")
        receipt["publication"] = publication
        checks["publication_valid"] = publication["exit_code"] == 0

    checks["all_passed"] = all(checks.values())
    receipt["checks"] = checks
    receipt["seconds_total"] = round(time.monotonic() - started, 1)
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate_store_gate.py",
        description="Replay a cloned output directory and check integrity, order independence, links and export. "
                    "Mutates OUTPUT_DIR: run it on a clone. Exit codes: 0 all checks passed, 1 a check failed, 2 bad input.",
    )
    parser.add_argument("output_dir", type=Path, help="cloned site output directory (holds data/)")
    parser.add_argument("--receipt", type=Path, help="where the JSON receipt is written (required unless --persist-only)")
    parser.add_argument("--scratch", type=Path, help="work directory for logs and the order-independence clones "
                        "(default: OUTPUT_DIR beside, named <name>-gate-scratch)")
    parser.add_argument("--today", default=date.today().isoformat(),
                        help="build date passed to every replay, so facts are comparable (default: today)")
    parser.add_argument("--persist-only", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir.resolve()
    if not (output_dir / "data").is_dir():
        print(f"ERROR [gate]: {output_dir} has no data/ directory", file=sys.stderr)
        return 2
    if args.persist_only:
        try:
            persist_only(output_dir, args.today)
        except ValueError as exc:
            print(f"ERROR [gate]: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.receipt is None:
        print("ERROR [gate]: --receipt is required", file=sys.stderr)
        return 2
    scratch = (args.scratch or output_dir.with_name(f"{output_dir.name}-gate-scratch")).resolve()
    try:
        receipt = run_gate(output_dir, scratch, args.today)
    except ValueError as exc:
        print(f"ERROR [gate]: {exc}", file=sys.stderr)
        return 2
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt["checks"], indent=2), file=sys.stderr)
    return 0 if receipt["checks"]["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
