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
   run database-only on clones of ``data/`` under SCRATCH (with the cached
   MdB-Stammdaten copied to each clone's private directory), each as an online build
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
6. The reviewed vote links (``scripts/reviewed_vote_links.json``): every entry
   of a sitting the store holds still holds (right links made, wrong ones not,
   keys matching by heading and first page). The release condition over the
   store (every contested vote reviewed, docs/plans/vote-pr-c.md section 5) is
   reported, not failed: it stops ``--publish``, never a build.
7. The Kinds (ADR 0002, amendment 2026-11-23): no stored unit has another Kind
   in DIP unless the reviewed list names it, and every sitting is one DIP has
   indexed (``speech_kinds.dip_typed_reden``, which a tagged export refuses
   too): no Rede is a Kurzintervention, an Erwiderung, an oral Erklärung or a
   Rede zu Protokoll in DIP, no whole-``<rede>`` Befragung turn an Erklärung,
   and no Kurzintervention, Erwiderung or Erklärung a Rede. It reads the
   reports of the sittings the store holds, one at a time, and fails when it
   reads none.
8. The cut Protokoll files (E16, docs/plans/cut-protocols.md): a sitting is
   marked (``protocols.xml_cut``) only when its cached XML prints the notice of
   a first edition and the rule, re-run over that XML and its report's DIP
   Aktivitäten, gives a cut; one with the notice is marked unless the rule
   reads it whole (19/107). For each marked sitting the store holds what the
   rule gives: ``xml_cut_unplaced_reden`` (NULL where DIP has not indexed it)
   and each ``unprinted_contributions`` row with its DIP id, kind, DIP person,
   page and quadrant (the DIP person, not the ``mp_id`` bound to it later).
   Every marked sitting has a cached report, and a run that reads none fails.
   No file without the notice looks cut by rule 3 (at least 5 DIP Reden after
   its last ``<rede>`` and 5 more than the rule's count of printed Reden),
   which a person reads; no row of ``unprinted_contributions`` shares person,
   place and sitting with a stored Rede. The marked sittings and the two
   counts are in the receipt.
9. The corrected end times (``scripts/reviewed_end_times.json``): every entry
   whose sitting the store holds is in ``protocols.sitting_end_corrected``, the
   column holds no other, and each entry's ``pdf_md5`` is the ``pdf_hash`` of
   the cached DIP catalog, so a PDF replaced since is read again.

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
import protocol_cut  # noqa: E402
import reviewed_end_times  # noqa: E402
import reviewed_units  # noqa: E402
import reviewed_vote_links  # noqa: E402
from sqlite_open import open_readonly  # noqa: E402
from stable_ids import canonical_dip_person_id, key_prefix  # noqa: E402
BUILD = SCRIPTS / "build_dip_pulse_site.py"
STORE = Path("data") / "bundestag-pulse.sqlite"
# The figures of the last combined A1/A2 run (docs/plans/a1-scratch-validation.json,
# 2026-10-05), which this gate is measured against.
REFERENCE_2026_10_05 = {"speeches": 26271, "contributions": 16799, "persons": 3370}

_LINK = re.compile(r'\b(?:href|src)\s*=\s*"([^"]*)"')
_ID = re.compile(r'\bid\s*=\s*"([^"]*)"')


def binding_ids(database_path: Path) -> set[str]:
    conn = open_readonly(database_path)
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
    conn = open_readonly(database_path)
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
    conn = open_readonly(database_path)
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

    conn = open_readonly(database_path)
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
    conn = open_readonly(Path(output_dir) / "data" / "bundestag-pulse.sqlite")
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
    conn = open_readonly(database_path)
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
    conn = open_readonly(database_path)
    try:
        check = [row[0] for row in conn.execute("PRAGMA integrity_check")]
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        conn.close()
    return {"integrity_check": check, "integrity_ok": check == ["ok"], "foreign_key_violations": len(violations)}


def withheld_also_counted(database_path: Path) -> list[str]:
    """Up to five withheld Reden whose rede_id is also a stored Rede or Beitrag
    of the same sitting, or that a stored Beitrag names as its parent (a
    nested Beitrag inside it). A withheld Rede is outside every count (ADR
    0005). Only a nested Beitrag (``nested:…``) is inside its parent: a
    Kurzintervention or Erwiderung is its own ``<rede>`` whose parent_rede_id
    names the Rede it answers, and it stays counted when that Rede is withheld.
    The parent is compared exactly: when only a split part ``R:n`` is withheld,
    the outer ``R`` stays stored (D4) and may have Beiträge."""
    conn = open_readonly(database_path)
    try:
        return [f"{protocol_id} {rede_id}" for protocol_id, rede_id in conn.execute(
            "SELECT w.protocol_id, w.rede_id FROM withheld_units w WHERE EXISTS (SELECT 1 FROM speeches s "
            "WHERE s.protocol_id = w.protocol_id AND s.rede_id = w.rede_id) OR EXISTS (SELECT 1 FROM contributions c "
            "WHERE c.protocol_id = w.protocol_id AND (c.rede_id = w.rede_id "
            "OR (c.parent_rede_id = w.rede_id AND substr(c.rede_id, 1, 7) = 'nested:'))) LIMIT 5")]
    finally:
        conn.close()


def withheld_without_redner_id(database_path: Path) -> list[str]:
    """Up to five withheld Reden with no Redner-ID. erste-reden binds a withheld
    Rede to its speaker by Redner-ID (ADR 0005 "Facts"); one without binds no
    one, so the owner reads it before the gate passes."""
    conn = open_readonly(database_path)
    try:
        return [f"{protocol_id} {rede_id}" for protocol_id, rede_id in conn.execute(
            "SELECT protocol_id, rede_id FROM withheld_units WHERE xml_redner_id IS NULL OR TRIM(xml_redner_id) = '' "
            "ORDER BY protocol_id, rede_id LIMIT 5")]
    finally:
        conn.close()


def abweichler_count_mismatches(database_path: Path) -> list[str]:
    """Up to five votes whose persisted Abweichler count is not the sum of their
    members' persisted Abweichungen. Persist writes both from one derive call,
    so a difference is a registry merge folding two listed members into one
    row, or a writer that skipped one of the columns."""
    conn = open_readonly(database_path)
    try:
        return [f"{vote_id} abweichler_count {count}, SUM(abweichung) {total}" for vote_id, count, total in conn.execute(
            "SELECT v.id, v.abweichler_count, COALESCE(SUM(vm.abweichung), 0) FROM votes v "
            "LEFT JOIN vote_members vm ON vm.vote_id = v.id WHERE v.abweichler_count IS NOT NULL "
            "GROUP BY v.id HAVING v.abweichler_count <> COALESCE(SUM(vm.abweichung), 0) ORDER BY v.id LIMIT 5")]
    finally:
        conn.close()


def reviewed_vote_link_check(database_path: Path, entries: list[reviewed_vote_links.Entry]) -> dict[str, Any]:
    """Check 6: the entries that no longer hold (``stale``, failing) and the
    release condition over the store (``release``, reported only)."""
    conn = open_readonly(database_path)
    try:
        sittings = reviewed_vote_links.sittings_of_store(conn)
    finally:
        conn.close()
    by_protocol: dict[str, list[reviewed_vote_links.Entry]] = {}
    for entry in entries:
        by_protocol.setdefault(entry.protocol, []).append(entry)
    stale = [problem for protocol, sitting in sorted(sittings.items())
             for problem in reviewed_vote_links.problems(by_protocol.get(protocol, []), sitting)]
    release = reviewed_vote_links.gate(entries, sittings)
    return {"entries": len(entries), "checked": release["reviewed"], "skipped_not_in_store": release["skipped"],
            "stale": stale[:50], "stale_count": len(stale),
            "release": {"contested_votes": release["contested"], "refusals": release["refusals"][:50],
                        "refusal_count": len(release["refusals"])}}


def dip_typed_check(output_dir: Path) -> dict[str, Any]:
    """Check 7, over the cached reports of the sittings the store holds (less those
    ``coverage-exclusions.json`` records), read one at a time: the reports read and
    the named rows."""
    import build_dip_pulse_site as site

    recorded = site.recorded_exclusions(output_dir)
    read = 0

    def reports() -> Any:
        nonlocal read
        for path in sorted((output_dir / "data").glob("plenarprotokoll-[0-9]*-[0-9]*.json")):
            report = json.loads(path.read_text(encoding="utf-8"))
            if site.normalized_document_number((report.get("protocol") or {}).get("dokumentnummer")) in recorded:
                continue
            read += 1
            yield {"report": report}

    rows = site.unlisted_dip_typed_reden(reports())
    return {"reports": read, "rows": rows}


def dip_typed_check_passes(result: dict[str, Any]) -> bool:
    """Check 7 passes when it read a report and named no row."""
    return result["reports"] > 0 and not result["rows"]


def _recomputed_cut(number: str, text: str, aktivitaeten: Any) -> tuple[dict[str, Any] | None, str | None]:
    """The cut rule over a sitting's cached XML and its report's Aktivitäten,
    parsed as the replay parses it: (the cut or None, None), or (None, the
    problem) where the parser or the rule refuses."""
    import validate_dip_protocol as dip

    try:
        return protocol_cut.protocol_cut(dip.parse_protocol_xml(text), aktivitaeten), None
    except (protocol_cut.ProtocolCutError, ValueError, reviewed_units.ReviewedUnitsError) as exc:
        return None, f"{number}: the cut rule refuses its cached XML and DIP's Aktivitäten: {exc}"


def _unprinted_row(dip_activity_id: str, kind: str, dip_person_id: str | None, page: int | None,
                   quadrant: str | None) -> str:
    return f"{dip_activity_id} {kind} person {dip_person_id or '(none)'} {page if page is not None else '(no page)'}{quadrant or ''}"


def cut_protocol_check(output_dir: Path, database_path: Path) -> dict[str, Any]:
    """Check 8, over the cached reports and XML and the replayed store."""
    import xml.etree.ElementTree as ET

    from persist_dip_pulse_store import clean

    conn = open_readonly(database_path)
    try:
        marked = dict(conn.execute("SELECT document_number, xml_cut FROM protocols"))
        unplaced_stored = dict(conn.execute("SELECT document_number, xml_cut_unplaced_reden FROM protocols WHERE xml_cut = 1"))
        rows_stored: dict[str, set[str]] = {}
        for number, *row in conn.execute(
                "SELECT p.document_number, u.dip_activity_id, u.kind, u.dip_person_id, u.page, u.page_quadrant "
                "FROM unprinted_contributions u JOIN protocols p ON p.id = u.protocol_id"):
            rows_stored.setdefault(number, set()).add(_unprinted_row(*row))
        counts = dict(((number, kind), count) for number, kind, count in conn.execute(
            "SELECT p.document_number, u.kind, COUNT(*) FROM unprinted_contributions u "
            "JOIN protocols p ON p.id = u.protocol_id GROUP BY 1, 2"))
        shared = [f"{number} {activity} {page}{quadrant or ''}" for number, activity, page, quadrant in conn.execute(
            "SELECT p.document_number, u.dip_activity_id, u.page, u.page_quadrant FROM unprinted_contributions u "
            "JOIN protocols p ON p.id = u.protocol_id JOIN mps mu ON mu.id = u.mp_id "
            "WHERE EXISTS (SELECT 1 FROM speeches s JOIN mps ms ON ms.id = s.mp_id WHERE s.protocol_id = u.protocol_id "
            "AND s.page = u.page AND s.page_quadrant IS u.page_quadrant AND ms.person_id = mu.person_id) "
            "ORDER BY 1, 2 LIMIT 50")]
        # erste-reden v4 joins an unprinted Rede by its MdB: one bound to none
        # would drop out and let a later Rede read as the debut.
        unbound = [f"{number} {activity}" for number, activity in conn.execute(
            "SELECT p.document_number, u.dip_activity_id FROM unprinted_contributions u "
            "JOIN protocols p ON p.id = u.protocol_id WHERE u.kind = 'rede' AND u.mp_id IS NULL ORDER BY 1, 2")]
    finally:
        conn.close()
    problems: list[str] = []
    whole: list[str] = []
    looks_cut: list[dict[str, Any]] = []
    read: set[str] = set()
    for path in sorted((output_dir / "data").glob("plenarprotokoll-[0-9]*-[0-9]*.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        number = str((report.get("protocol") or {}).get("dokumentnummer") or "")
        if number not in marked:
            continue
        read.add(number)
        xml_path = output_dir / "data" / "xml" / f"plenarprotokoll-{number.replace('/', '-')}.xml"
        if not xml_path.is_file():
            problems.append(f"{number}: no cached XML to check the mark against")
            continue
        text = xml_path.read_text(encoding="utf-8")
        root = ET.fromstring(text)
        aktivitaeten = (report.get("api_records") or {}).get("aktivitaeten")
        try:
            notice = protocol_cut.first_edition_notice(root)
        except protocol_cut.ProtocolCutError as exc:
            problems.append(str(exc))
            continue
        if marked[number] and not notice:
            problems.append(f"{number}: marked cut, but its cached XML prints no notice of a first edition")
        elif notice:
            cut, refusal = _recomputed_cut(number, text, aktivitaeten)
            if refusal:
                problems.append(refusal)
            elif marked[number] and cut is None:
                problems.append(f"{number}: marked cut, but the cut rule reads its cached XML and DIP's Aktivitäten whole")
            elif marked[number]:
                # The store holds what the rule gives: the count it cannot place
                # (NULL where DIP has not indexed the sitting) and each row with
                # its DIP person, normalized as persist_unprinted stores it.
                if unplaced_stored.get(number) != cut["unplaced_reden"]:
                    problems.append(f"{number}: xml_cut_unplaced_reden {unplaced_stored.get(number)}, "
                                    f"the cut rule gives {cut['unplaced_reden']}")
                given = {_unprinted_row(str(entry["dip_activity_id"]), entry["kind"],
                                        canonical_dip_person_id(entry.get("dip_person_id")), entry.get("page"),
                                        clean(entry.get("quadrant"))) for entry in cut["entries"]}
                stored = rows_stored.get(number, set())
                if stored - given:
                    problems.append(f"{number}: unprinted_contributions holds rows the cut rule does not give: "
                                    f"{', '.join(sorted(stored - given)[:10])}")
                if given - stored:
                    problems.append(f"{number}: the cut rule gives rows unprinted_contributions does not hold: "
                                    f"{', '.join(sorted(given - stored)[:10])}")
            elif cut is not None:
                problems.append(f"{number}: its XML prints the notice and DIP lists more than it holds, but it is not marked")
            else:
                whole.append(number)
        else:
            # The cut rule's own count (protocol_cut.printed_reden, written by
            # cut_summary): the stored Reden and the withheld units that would be one.
            printed = (report.get("validation_summary") or {}).get("printed_reden")
            if type(printed) is not int:
                # Not parsed under the rule: rule 3 has no count to compare DIP's with.
                problems.append(f"{number}: its report holds no count of printed Reden to judge rule 3 by")
                continue
            evidence = protocol_cut.unmarked_cut_evidence(root, aktivitaeten, printed)
            if evidence:
                looks_cut.append({"document_number": number, **evidence})
    if not read:
        problems.append("no cached report was read for a sitting of the store: check 8 judged nothing")
    unread = sorted((number for number, flag in marked.items() if flag and number not in read),
                    key=lambda n: tuple(int(part) for part in n.split("/")))
    problems += [f"{number}: marked cut, but no cached report was read for it" for number in unread]
    if looks_cut:
        problems.append(f"{len(looks_cut)} sittings without the notice look cut by rule 3: read them "
                        f"({', '.join(entry['document_number'] for entry in looks_cut[:10])})")
    if unbound:
        problems.append(f"{len(unbound)} unprinted Reden are bound to no MdB: {', '.join(unbound[:10])}")
    if shared:
        problems.append(f"{len(shared)} unprinted entries share person, place and sitting with a stored Rede: {', '.join(shared[:10])}")
    cut = sorted((number for number, flag in marked.items() if flag),
                 key=lambda n: tuple(int(part) for part in n.split("/")))
    return {
        "sittings": len(cut),
        "rede": sum(count for (_n, kind), count in counts.items() if kind == "rede"),
        "zu_protokoll": sum(count for (_n, kind), count in counts.items() if kind == "zu_protokoll"),
        "marked": cut,
        "notice_but_whole": whole,
        "rule3": looks_cut,
        "problems": problems,
    }


def end_time_check(output_dir: Path, database_path: Path) -> dict[str, Any]:
    """Check 9, over the replayed store and the cached catalog."""
    entries = reviewed_end_times.load()
    conn = open_readonly(database_path)
    try:
        stored = dict(conn.execute("SELECT document_number, sitting_end_corrected FROM protocols"))
    finally:
        conn.close()
    try:
        catalog = json.loads((output_dir / "data" / "plenarprotokoll-catalog.json").read_text(encoding="utf-8"))
        hashes = {str(p.get("dokumentnummer")): str(p.get("pdf_hash") or "") for p in catalog.get("protocols") or []
                  if isinstance(p, dict)}
    except (OSError, ValueError, AttributeError):
        hashes = {}
    problems = []
    listed = {entry.sitting for entry in entries}
    for entry in entries:
        if entry.sitting not in stored:
            continue
        if stored[entry.sitting] != entry.end:
            problems.append(f"{entry.sitting}: sitting_end_corrected {stored[entry.sitting]!r}, the list says {entry.end}")
        if hashes.get(entry.sitting) != entry.pdf_md5:
            problems.append(f"{entry.sitting}: pdf_md5 {entry.pdf_md5} is not the catalog's pdf_hash "
                            f"{hashes.get(entry.sitting) or '(none)'}: read the PDF again")
    problems += [f"{number}: sitting_end_corrected {value!r} without an entry" for number, value in sorted(stored.items())
                 if value is not None and number not in listed]
    return {"entries": len(entries), "applied": sorted(listed & set(stored)), "problems": problems}


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
    # bool is an int subclass: true is no Wahlperiode 1.
    return {int(number) for number in values
            if (isinstance(number, int) and not isinstance(number, bool)) or (isinstance(number, str) and number.isdigit())}


class CachedRosterError(ValueError):
    """The person cache the gate's fresh build reads its roster from is missing
    or is not a person cache: bad input, reported without a traceback."""


def cached_roster(output_dir: Path) -> CachedRoster:
    """Every /person record ``data/dip-person-cache.json`` holds, whatever its age
    (the gate rebuilds a store from them, it fetches nothing). Raises
    CachedRosterError when the file is missing or not a person cache."""
    path = output_dir / "data" / PERSON_FILENAME
    try:
        persons = json.loads(path.read_text(encoding="utf-8")).get("persons")
    except (OSError, ValueError, AttributeError) as exc:
        raise CachedRosterError(f"no readable DIP person cache at {path}: {exc}") from None
    if not isinstance(persons, dict):
        raise CachedRosterError(f"{path} holds no persons object")
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


def _require_stammdaten_of_store(store: Path, cache: Path) -> None:
    """ValueError when ``store`` was built with a MdB-Stammdaten file and ``cache``
    does not hold it (missing, or another sha256): the clone's rebuild would drop
    the store's re-filed Stimmen or file them from another file. A store that
    cannot be read, or whose schema predates the table, has no such record; the
    gate's own reads of the source report an unreadable store."""
    if not store.is_file():
        return
    try:
        conn = open_readonly(store)
        try:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'mdb_stammdaten_stand'").fetchone():
                return
            built_with = conn.execute("SELECT stand, sha256 FROM mdb_stammdaten_stand").fetchone()
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return
    if built_with is None:
        return
    cached = hashlib.sha256(cache.read_bytes()).hexdigest() if cache.is_file() else None
    if cached != built_with[1]:
        found = f"a file with sha256 {cached[:12]}…" if cached else "no file"
        raise ValueError(f"the source store {store} was built with a MdB-Stammdaten file (Stand {built_with[0]}, sha256 "
                         f"{built_with[1][:12]}…), but {cache} holds {found}; restore that file before running the gate")


def _data_clone(source: Path, target: Path) -> Path:
    """A copy of ``source/data`` under ``target`` without its store: an APFS clone
    where the file system offers one. The source's cached MdB-Stammdaten
    (``mdb-stammdaten.*`` in its private directory) go to the clone's private
    directory, so the clone's rebuild re-files the Stimmen as the input store
    does; a stale copy there from an earlier run is removed first. Raises
    ValueError, before cloning, when the source store was built with a file
    (``mdb_stammdaten_stand``) and the source caches no file with that sha256,
    and when the source caches the file and the clone ends up without it."""
    import person_registry as registry
    import stammdaten

    _require_disjoint_paths(source, target)
    _require_stammdaten_of_store(source / STORE, registry.private_dir(source / STORE) / stammdaten.CACHE_NAME)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    clone = ["cp", "-cR"] if sys.platform == "darwin" else ["cp", "-R"]
    subprocess.run([*clone, str(source / "data"), str(target / "data")], check=True)
    for path in (target / "data").glob("bundestag-pulse.sqlite*"):
        path.unlink()
    shutil.rmtree(target / "data" / "exports", ignore_errors=True)
    source_private = registry.private_dir(source / STORE)
    target_private = registry.private_dir(target / STORE)
    _require_disjoint_paths(source_private, target_private)
    cached = sorted(source_private.glob("mdb-stammdaten.*")) if source_private.is_dir() else []
    if target_private.is_dir():
        for stale in target_private.glob("mdb-stammdaten.*"):
            stale.unlink()
    if cached:
        registry.ensure_private_dir(target_private)
        for path in cached:
            shutil.copy2(path, target_private / path.name)
    if (source_private / stammdaten.CACHE_NAME).is_file() and not (target_private / stammdaten.CACHE_NAME).is_file():
        raise ValueError(f"the source caches the MdB-Stammdaten ({source_private / stammdaten.CACHE_NAME}), but the clone's "
                         f"private directory {target_private} holds no copy, so the clone's rebuild would leave every "
                         "Stimme under the group its roll-call page lists")
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


def input_snapshot(database_path: Path) -> dict[str, Any]:
    """The input store as the replay finds it: its bindings, their grouping, its
    Personenseiten and its DIP person occurrences, which an unchanged replay must
    reproduce. The snapshot runs the current code on a store the replay has not
    upgraded yet, so a store whose schema lacks what that code reads (or that is
    no SQLite file) gives ``{"unavailable": cause}``, which fails
    ``replay_vs_input`` with that cause instead of ending the gate unreceipted."""
    try:
        return {"bindings": binding_ids(database_path), "grouping": grouping_fingerprint(database_path),
                "pages": person_pages(database_path), "roster": dip_person_occurrences(database_path)}
    except sqlite3.DatabaseError as exc:  # OperationalError: a missing table or column
        return {"unavailable": f"{type(exc).__name__}: {exc}"}


def replay_vs_input(input_store: dict[str, Any] | None, database_path: Path) -> dict[str, Any]:
    """The replayed store against the input store it replayed: the same grouping of
    the input's bindings into persons, and the same Personenseiten with the same
    Reden, Beiträge and Stimmen. The input is the reference (a fresh online build or
    an earlier replay of one), so any difference is the replay's doing; a branch
    that moves persons on purpose shows its moves here."""
    if input_store is None:
        return {"equal": False, "reason": "no input store to compare the replay with"}
    if "unavailable" in input_store:
        return {"equal": False, "reason": f"the input store's snapshot is unavailable: {input_store['unavailable']}"}
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
        try:
            receipt["counts_before"] = store_counts(database_path)
        except sqlite3.DatabaseError as exc:
            receipt["counts_before"] = {"unavailable": f"{type(exc).__name__}: {exc}"}
        # The input store as the replay finds it: an unchanged replay must
        # reproduce its grouping and every page's counts.
        started_snapshot = time.monotonic()
        input_store = input_snapshot(database_path)
        receipt["input_snapshot_seconds"] = round(time.monotonic() - started_snapshot, 1)
        if "unavailable" in input_store:
            receipt["input_snapshot_unavailable"] = input_store["unavailable"]
    checks: dict[str, bool] = {}

    receipt["replay"] = replay(output_dir, today, scratch / "replay.log")
    checks["replay_exit_0"] = receipt["replay"]["exit_code"] == 0
    if checks["replay_exit_0"]:
        receipt["integrity"] = integrity(database_path)
        checks["sqlite_integrity_ok"] = receipt["integrity"]["integrity_ok"]
        checks["no_foreign_key_violations"] = receipt["integrity"]["foreign_key_violations"] == 0
        receipt["withheld_also_counted"] = withheld_also_counted(database_path)
        checks["no_withheld_rede_counted"] = not receipt["withheld_also_counted"]
        receipt["withheld_without_redner_id"] = withheld_without_redner_id(database_path)
        checks["every_withheld_rede_has_a_redner_id"] = not receipt["withheld_without_redner_id"]
        receipt["abweichler_count_mismatches"] = abweichler_count_mismatches(database_path)
        checks["abweichler_count_matches_members"] = not receipt["abweichler_count_mismatches"]
        receipt["reviewed_vote_links"] = reviewed_vote_link_check(database_path, reviewed_vote_links.load())
        checks["reviewed_vote_links_hold"] = receipt["reviewed_vote_links"]["stale_count"] == 0
        receipt["dip_typed_reden"] = dip_typed_check(output_dir)
        checks["no_unlisted_dip_typed_rede"] = dip_typed_check_passes(receipt["dip_typed_reden"])
        receipt["cut_protocols"] = cut_protocol_check(output_dir, database_path)
        checks["cut_protocols_hold"] = not receipt["cut_protocols"]["problems"]
        receipt["end_times"] = end_time_check(output_dir, database_path)
        checks["corrected_end_times_hold"] = not receipt["end_times"]["problems"]
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
                scratch / "fresh" / STORE, database_path, input_store.get("roster") if input_store else None)
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
    # The order-independence clones run --persist-only, which parses nothing
    # without the reviewed list: a missing or malformed file stops here, never
    # halfway through a replay.
    try:
        reviewed_units.load()
    except reviewed_units.ReviewedUnitsError as exc:
        print(f"ERROR [reviewed-units]: {exc}. Fix: repair scripts/reviewed_units.json (docs/adr/0005-withhold-refused-reden.md), then re-run.", file=sys.stderr)
        return 2
    try:
        reviewed_vote_links.load()
    except reviewed_vote_links.ReviewedVoteLinksError as exc:
        print(f"ERROR [reviewed-vote-links]: {exc}. Fix: repair scripts/reviewed_vote_links.json (docs/plans/vote-pr-c.md, section 4), then re-run.", file=sys.stderr)
        return 2
    output_dir = args.output_dir.resolve()
    if not (output_dir / "data").is_dir():
        print(f"ERROR [gate]: {output_dir} has no data/ directory", file=sys.stderr)
        return 2
    if args.persist_only:
        try:
            persist_only(output_dir, args.today)
        except CachedRosterError as exc:
            print(f"ERROR [gate]: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.receipt is None:
        print("ERROR [gate]: --receipt is required", file=sys.stderr)
        return 2
    scratch = (args.scratch or output_dir.with_name(f"{output_dir.name}-gate-scratch")).resolve()
    try:
        receipt = run_gate(output_dir, scratch, args.today)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR [gate]: {exc}", file=sys.stderr)
        return 2
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(receipt["checks"], indent=2), file=sys.stderr)
    return 0 if receipt["checks"]["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
