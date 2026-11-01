#!/usr/bin/env python3
"""The merged-store gate: replay, integrity, order independence, links, export.

    python3 scripts/validate_store_gate.py OUTPUT_DIR --receipt RECEIPT.json [--scratch DIR] [--today YYYY-MM-DD]

OUTPUT_DIR is a site output directory (``data/`` holds the cached reports,
their XML, the catalog and ``bundestag-pulse.sqlite``). It is replayed in place,
so run the gate on a clone (``cp -cR``), never on the reference directory. The
checks, in order:

1. ``--offline --repersist`` of OUTPUT_DIR (exit code, timing, whether the store
   was replaced), then ``PRAGMA integrity_check`` and ``foreign_key_check``.
2. Order independence: a fresh store from all cached reports, and a store built
   from every other report and then replayed with all of them, must group the
   person bindings into persons identically (``grouping_fingerprint``). Both
   run database-only on clones of ``data/`` under SCRATCH.
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
    """The row counts the receipt records, plus Beiträge per kind."""
    conn = _open_readonly(database_path)
    try:
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("protocols", "agenda_items", "speeches", "contributions", "mps", "person_records",
                          "person_bindings", "person_aliases", "documents", "votes", "vote_members", "facts")
        }
        counts["persons"] = conn.execute("SELECT COUNT(DISTINCT person_id) FROM person_records").fetchone()[0]
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


def persist_only(output_dir: Path, today: str) -> None:
    """The database half of ``--offline --repersist``, without the render or the
    export: what the order-independence clones need."""
    import build_dip_pulse_site as site
    import antrag_text
    import politikfelder

    database_path = output_dir / STORE
    vorgang_cache = politikfelder.load_cache(output_dir)
    vorgang_cache[antrag_text.CACHE_NAMESPACE] = antrag_text.load_cache(output_dir)
    site.repersist_cached_reports(
        output_dir, database_path, site.load_cached_protocols(output_dir), preserve_roster=True,
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
    if database_path.exists():
        receipt["counts_before"] = store_counts(database_path)
    checks: dict[str, bool] = {}

    receipt["replay"] = replay(output_dir, today, scratch / "replay.log")
    checks["replay_exit_0"] = receipt["replay"]["exit_code"] == 0
    if checks["replay_exit_0"]:
        receipt["integrity"] = integrity(database_path)
        checks["sqlite_integrity_ok"] = receipt["integrity"]["integrity_ok"]
        checks["no_foreign_key_violations"] = receipt["integrity"]["foreign_key_violations"] == 0
        receipt["counts"] = store_counts(database_path)
        receipt["counts_vs_2026_10_05"] = {
            key: {"old": old, "new": receipt["counts"][key], "delta": receipt["counts"][key] - old}
            for key, old in REFERENCE_2026_10_05.items()
        }
        receipt["grouping"] = grouping_fingerprint(database_path)

    receipt["order_independence"] = order_independence(output_dir, scratch, today)
    checks["half_then_full_groups_like_fresh"] = receipt["order_independence"]["equal"]
    if checks["replay_exit_0"] and "grouping" in receipt["order_independence"]["fresh"]:
        # Not a plan check: the replayed store carries its registry forward, so it
        # is compared on the bindings a fresh store holds, and the bindings it
        # keeps for retired occurrences are counted.
        live = binding_ids(scratch / "fresh" / STORE)
        receipt["grouping_on_fresh_bindings"] = grouping_fingerprint(database_path, only=live)
        receipt["bindings_of_retired_occurrences"] = len(binding_ids(database_path) - live)
        checks["replayed_store_groups_like_fresh"] = (
            receipt["grouping_on_fresh_bindings"] == receipt["order_independence"]["fresh"]["grouping"]
        )

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
        persist_only(output_dir, args.today)
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
