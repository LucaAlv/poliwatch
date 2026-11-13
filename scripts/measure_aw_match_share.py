#!/usr/bin/env python3
"""The abgeordnetenwatch match share of WP 18/19 Redner (A3 plan item 1.5).

    python3 scripts/measure_aw_match_share.py OUTPUT_DIR --cache SCRATCH/aw-cache.json \\
        [--stammdaten ZIP] [--offline] [--name-fallback] [--json RECEIPT] [--verdicts JSON]

Reads OUTPUT_DIR and writes nothing under it: the store is opened read-only, and
the reports of its WP 18/19 sittings are loaded and re-parsed from their cached
XML in memory, one at a time, by the build's own functions
(``load_existing_detail_entries``, ``without_recorded_exclusions``,
``reparse_cached_xml``). ``enrich_report_with_profiles`` then runs with a
recording resolver, so the Redner-IDs counted are the ones a fresh enrichment
would look up (docs/plans/a3-item-1-5-aw-match-share.md).

Each distinct Redner-ID (``derive.first_redner_id``) is looked up with
``AbgeordnetenwatchResolver.lookup_ext_id`` against the scratch cache
``--cache``, which a first run seeds byte for byte from
``OUTPUT_DIR/data/abgeordnetenwatch-cache.json`` where that exists.
``--offline`` sends nothing and prints bounds and the number of requests an
online run sends; an online run asks again about every id, cached answers
included, so the figure is as of the run date and a changed cached hit shows
up. Answers are kept in ``<cache>.answers.json`` beside the cache, so a rerun
after failures asks only about the ids not yet answered, or whose answer the
cache no longer holds. ``--name-fallback``
also runs the build's name search for every MdB-Stammdaten id that missed.

"MdB in WP n" means a Mandat in WP n, by the store's ``mdb_zugehoerigkeiten``
where it holds rows, else by the Stammdaten zip (``--stammdaten``, else the
store's cached zip in its private directory). The zip also gives the names the
precision check compares against and whether an id is in the Stammdaten at all.

Exit codes: 0 a complete result, 1 an id or name search had no answer (rerun),
2 bad input.
"""

from __future__ import annotations

if __name__ == "__main__":
    from python_version_guard import require_supported_python

    require_supported_python()

import argparse
import hashlib
import json
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import abgeordnetenwatch as aw
import build_dip_pulse_site as build
import derive
import person_registry as registry
import stammdaten

SCRIPTS = Path(__file__).resolve().parent
STORE = Path("data") / "bundestag-pulse.sqlite"
STORE_CACHE = Path("data") / "abgeordnetenwatch-cache.json"
WAHLPERIODEN = (18, 19)
#: Name-search links reviewed by hand: all of them up to this many, else a sample.
REVIEW_SAMPLE = 50
REVIEW_SEED = 1505
#: Failed lookups in a row after which an online run stops asking.
MAX_FAILED_IN_A_ROW = 5
SAVE_EVERY = 25


class UsageError(Exception):
    """Bad input: exit 2."""


class Recorder:
    """A resolver for ``enrich_report_with_profiles`` that records each call and
    resolves nothing."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def resolve(self, **call: Any) -> None:
        self.calls.append(call)
        return None


def _home(path: Path) -> str:
    text = str(path)
    home = str(Path.home())
    return "~" + text[len(home):] if text == home or text.startswith(home + "/") else text


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _commit() -> str:
    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(SCRIPTS), *args], capture_output=True, text=True).stdout.strip()

    commit = git("rev-parse", "--short", "HEAD")
    return f"{commit}-dirty" if commit and git("status", "--porcelain", "--untracked-files=no") else commit


def _share(hits: int, total: int) -> float | None:
    return round(hits / total, 4) if total else None


# -- the speaker set ----------------------------------------------------------


def stored_sittings(conn: sqlite3.Connection) -> list[tuple[int, str]]:
    """(Wahlperiode, document number) of the store's WP 18/19 sittings."""
    rows = []
    for (number,) in conn.execute("SELECT document_number FROM protocols ORDER BY document_number"):
        wahlperiode, _, sitzung = str(number).partition("/")
        if wahlperiode.isdigit() and int(wahlperiode) in WAHLPERIODEN and sitzung:
            rows.append((int(wahlperiode), str(number)))
    return sorted(rows, key=lambda row: (row[0], row[1].partition("/")[2].zfill(6)))


def load_report(output_dir: Path, document_number: str, view_root: Path) -> tuple[dict[str, Any] | None, bool]:
    """The report of one sitting as the offline build loads it, re-parsed from
    its cached XML in memory: (report, re-parsed), or (None, False) when the
    exclusion record lists the sitting. The build's loader reads every report in
    ``data/``, so it is given a view holding links to this report and the XML
    directory only; nothing is written under OUTPUT_DIR."""
    report_path, _, _ = build.report_paths(output_dir, document_number)
    if not report_path.exists():
        raise UsageError(f"the store holds {document_number}, but {report_path} does not exist")
    view = view_root / document_number.replace("/", "-")
    (view / "data").mkdir(parents=True)
    (view / "data" / report_path.name).symlink_to(report_path)
    xml_dir = output_dir / "data" / "xml"
    if xml_dir.is_dir():
        (view / "data" / "xml").symlink_to(xml_dir, target_is_directory=True)
    try:
        entries = build.load_existing_detail_entries(view, [{"dokumentnummer": document_number}], strict=True)
        if not entries:
            raise UsageError(f"{report_path} is not the report of {document_number}")
        entries = build.without_recorded_exclusions(output_dir, entries)
        if not entries:
            return None, False
        reparsed = build.reparse_cached_xml(view, entries, profiles_from=[])
    except (build.CachedReportError, build.CoverageExclusionsError) as exc:
        raise UsageError(str(exc)) from exc
    finally:
        shutil.rmtree(view)
    return entries[0]["report"], bool(reparsed)


def collect(output_dir: Path, sittings: list[tuple[int, str]], view_root: Path) -> dict[str, Any]:
    """Per Redner-ID: Wahlperioden, Reden per Wahlperiode, printed names,
    Fraktionen and raw values; plus the Reden without a Redner-ID."""
    ids: dict[str, dict[str, Any]] = {}
    reden_without_id = Counter()
    reden_total = Counter()
    counted = {wp: 0 for wp in WAHLPERIODEN}
    excluded: list[str] = []
    not_reparsed: list[str] = []
    for index, (wahlperiode, number) in enumerate(sittings, 1):
        report, reparsed = load_report(output_dir, number, view_root)
        if report is None:
            excluded.append(number)
            continue
        counted[wahlperiode] += 1
        if not reparsed:
            not_reparsed.append(number)
        items = [report, *(report.get("agenda_items") or [])]
        # The build skips a speaker that holds a profile; a fresh enrichment holds none.
        for item in items:
            for key in build.SPEAKER_LISTS:
                for unit in item.get(key) or []:
                    if isinstance(unit.get("speaker"), dict):
                        unit["speaker"].pop("abgeordnetenwatch", None)
        recorder = Recorder()
        build.enrich_report_with_profiles(report, recorder)
        for call in recorder.calls:
            raw = str(call.get("ext_id") or "").strip()
            if not raw:
                continue  # a roll-call member or a Rede without a Redner-ID: a name search
            redner_id = derive.first_redner_id(raw)
            record = ids.setdefault(redner_id, {
                "wahlperioden": set(), "reden": Counter(), "names": Counter(), "fraktionen": Counter(), "raw": set()})
            record["wahlperioden"].add(wahlperiode)
            record["names"][(str(call.get("first_name") or "").strip(), str(call.get("last_name") or "").strip())] += 1
            if call.get("fraktion"):
                record["fraktionen"][str(call["fraktion"])] += 1
            if len(derive.redner_ids(raw)) > 1:
                record["raw"].add(raw)
        for item in items:
            for unit in item.get("xml_speakers") or []:
                speaker = unit.get("speaker") if isinstance(unit.get("speaker"), dict) else {}
                redner_id = derive.first_redner_id(speaker.get("xml_redner_id"))
                reden_total[wahlperiode] += 1
                if redner_id:
                    ids[redner_id]["reden"][wahlperiode] += 1
                else:
                    reden_without_id[wahlperiode] += 1
        if index % 50 == 0:
            print(f"[aw-share] {index}/{len(sittings)} sittings read, {len(ids)} Redner-IDs", file=sys.stderr)
    return {"ids": ids, "reden_total": reden_total, "reden_without_id": reden_without_id,
            "sittings": counted, "excluded": excluded, "not_reparsed": not_reparsed}


# -- MdB-Stammdaten -------------------------------------------------------------


def mdb_sources(conn: sqlite3.Connection, database_path: Path, zip_arg: Path | None) -> dict[str, Any]:
    """The Mandat rule's source and the Stammdaten names. ``mandates`` maps an
    MdB id to its Wahlperioden; ``names`` maps a Stammdaten id to its given-name
    and surname words (every NAMEN entry, the historical ones included)."""
    zip_path = zip_arg if zip_arg is not None else stammdaten.cache_path(database_path)
    data = None
    if zip_arg is not None or zip_path.exists():
        try:
            data = stammdaten.read_zip(zip_path)
        except (OSError, stammdaten.StammdatenError) as exc:
            raise UsageError(f"cannot read the MdB-Stammdaten {zip_path}: {exc}") from exc
    table: dict[str, set[int]] = {}
    has_table = conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'mdb_zugehoerigkeiten'").fetchone()
    if has_table:
        for mdb_id, wahlperiode in conn.execute("SELECT mdb_id, wahlperiode FROM mdb_zugehoerigkeiten"):
            table.setdefault(str(mdb_id), set()).add(int(wahlperiode))
    from_zip: dict[str, set[int]] = {}
    names: dict[str, dict[str, Any]] = {}
    for record in data.records if data else []:
        from_zip[record["ID"]] = {int(period["WP"]) for period in record["WAHLPERIODEN"]}
        given: set[str] = set()
        surname: set[str] = set()
        spelled = []
        for name in record["NAMEN"]:
            given |= registry._name_words(name.get("VORNAME"))
            surname |= registry._name_words(name.get("NACHNAME"))
            spelled.append(" ".join(part for part in (name.get("VORNAME"), name.get("PRAEFIX"), name.get("ADEL"), name.get("NACHNAME")) if part))
        names[record["ID"]] = {"given": given, "surname": surname, "spelled": sorted(set(spelled))}
    if table:
        source, mandates = "mdb_zugehoerigkeiten", table
    elif data:
        source, mandates = f"zip:{_home(zip_path.resolve())}", from_zip
    else:
        source, mandates = "none", {}
    disagreements: list[str] = []
    if table and data:
        wanted = set(WAHLPERIODEN)
        either = {key for source_map in (table, from_zip) for key, periods in source_map.items() if periods & wanted}
        disagreements = sorted(key for key in either
                               if table.get(key, set()) & wanted != from_zip.get(key, set()) & wanted)
    return {
        "source": source,
        "mandates": mandates,
        "known": set(from_zip) if data else set(table),
        "names": names,
        "zip": {"path": _home(zip_path.resolve()), "stand": data.stand, "sha256": data.sha256} if data else None,
        "table_zip_disagreements_wp18_19": disagreements,
    }


def name_matches(label: Any, given: set[str] | frozenset[str], surname: set[str] | frozenset[str]) -> bool:
    """The precision rule: the label holds a given-name word and a surname word."""
    words = registry._name_words(label)
    return bool(words & given) and bool(words & surname)


def printed_name_matches(label: Any, names: Counter) -> bool:
    return any(name_matches(label, registry._name_words(first), registry._name_words(last)) for first, last in names)


# -- the measurement ------------------------------------------------------------


def _answers_path(cache: Path) -> Path:
    return cache.with_name(cache.name + ".answers.json")


def _load_answers(cache: Path) -> dict[str, Any]:
    path = _answers_path(cache)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise UsageError(f"{path} is unreadable: {exc}; delete it to ask every id again") from exc
    if not isinstance(data, dict) or not isinstance(data.get("answers"), dict):
        raise UsageError(f"{path} is not an answers file; delete it to ask every id again")
    return data


def _save(resolver: aw.AbgeordnetenwatchResolver, cache: Path, answers: dict[str, Any]) -> None:
    resolver.save()
    path = _answers_path(cache)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(answers, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _profile_view(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    if not profile:
        return None
    return {"id": profile.get("id"), "label": profile.get("label"), "url": profile.get("url"), "match": profile.get("match")}


def lookup_all(resolver: aw.AbgeordnetenwatchResolver, keys: list[str], cache: Path, *, offline: bool) -> dict[str, Any]:
    """The answer for every key (a Redner-ID, or a merged raw value). Online, a
    key answered in an earlier run of this cache is not asked again."""
    answers = {"answers": {}} if offline else _load_answers(cache) or {
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "answers": {}}
    found: dict[str, Any] = {}
    failed_in_a_row = 0
    asked = 0
    try:
        for key in keys:
            earlier = answers["answers"].get(key)
            if earlier and earlier["state"] != "failed":
                current = resolver.lookup_ext_id(key, network=False)
                if current.state == earlier["state"]:
                    found[key] = {**earlier, "profile": current.profile}
                    continue
                # The cache no longer holds this answer (deleted, dropped by a
                # format change or unreadable), so the profile is gone: ask again.
            if offline:
                result = resolver.lookup_ext_id(key, network=False)
                found[key] = {"state": result.state, "candidates": None, "cached_state": result.cached_state,
                              "cached_id": (result.cached_profile or {}).get("id"), "profile": result.profile}
                continue
            if failed_in_a_row >= MAX_FAILED_IN_A_ROW:
                found[key] = {"state": "failed", "candidates": None, "cached_state": None, "cached_id": None,
                              "profile": None, "error": f"not asked: stopped after {MAX_FAILED_IN_A_ROW} failures in a row"}
                continue
            result = resolver.lookup_ext_id(key, refresh=True)
            asked += 1
            failed_in_a_row = failed_in_a_row + 1 if result.state == "failed" else 0
            answer = {"state": result.state, "candidates": result.candidates, "cached_state": result.cached_state,
                      "cached_id": (result.cached_profile or {}).get("id")}
            if result.state == "failed":
                answer["error"] = resolver.last_error
            answers["answers"][key] = answer
            found[key] = {**answer, "profile": result.profile}
            if asked % SAVE_EVERY == 0:
                _save(resolver, cache, answers)
                print(f"[aw-share] {asked} asked, {len(found)}/{len(keys)} answered; stats {resolver.stats}", file=sys.stderr)
        if failed_in_a_row >= MAX_FAILED_IN_A_ROW:
            print(f"[aw-share] stopped asking after {MAX_FAILED_IN_A_ROW} failed lookups in a row", file=sys.stderr)
    finally:
        if not offline:
            _save(resolver, cache, answers)
    return found


def name_fallback(resolver: aw.AbgeordnetenwatchResolver, ids: dict[str, Any], misses: list[str]) -> dict[str, Any]:
    """The build's name search for each miss, with its most often printed name."""
    found = {}
    for redner_id in misses:
        (first, last), _ = ids[redner_id]["names"].most_common(1)[0]
        fraktion = ids[redner_id]["fraktionen"].most_common(1)[0][0] if ids[redner_id]["fraktionen"] else None
        searched = {"first_name": first, "last_name": last, "fraktion": fraktion}
        if resolver._network_disabled:
            # resolve() would answer None without asking: no answer, not a miss.
            found[redner_id] = {"state": "failed", "profile": None, "searched": searched, "error": resolver.last_error}
            continue
        errors = resolver.stats["errors"]
        profile = resolver.resolve(first_name=first or None, last_name=last or None, fraktion=fraktion)
        failed = profile is None and resolver.stats["errors"] > errors
        found[redner_id] = {"state": "failed" if failed else ("hit" if profile else "miss"), "profile": profile,
                            "searched": searched, **({"error": resolver.last_error} if failed else {})}
    resolver.save()
    return found


def category(redner_id: str, wahlperiode: int | None, mdb: dict[str, Any], spoke_in: set[int]) -> str:
    """M1 (a Mandat in the Wahlperiode; for the union, in one it spoke in), M1a
    (in the Stammdaten, no such Mandat) or M1b (not in the Stammdaten)."""
    periods = mdb["mandates"].get(redner_id, set())
    wanted = {wahlperiode} if wahlperiode is not None else spoke_in
    if periods & wanted:
        return "M1"
    return "M1a" if redner_id in mdb["known"] else "M1b"


def measure(collected: dict[str, Any], found: dict[str, Any], mdb: dict[str, Any],
            fallback: dict[str, Any] | None, partitions: list[dict[str, Any]], m6: dict[str, Any]) -> dict[str, Any]:
    ids = collected["ids"]

    def label_ok(redner_id: str, label: Any) -> bool:
        if redner_id in mdb["names"]:
            names = mdb["names"][redner_id]
            return name_matches(label, names["given"], names["surname"])
        return printed_name_matches(label, ids[redner_id]["names"])

    def describe(redner_id: str) -> dict[str, Any]:
        record = ids[redner_id]
        answer = found[redner_id]
        return {
            "redner_id": redner_id,
            "wahlperioden": sorted(record["wahlperioden"]),
            "printed": [f"{first} {last}".strip() for (first, last), _ in record["names"].most_common()],
            "fraktionen": [name for name, _ in record["fraktionen"].most_common()],
            "stammdaten": mdb["names"].get(redner_id, {}).get("spelled"),
            "category": category(redner_id, None, mdb, record["wahlperioden"]),
            "aw": _profile_view(answer.get("profile")),
            "candidates": answer.get("candidates"),
        }

    figures: dict[str, Any] = {}
    scopes: list[tuple[str, int | None]] = [(str(wp), wp) for wp in WAHLPERIODEN] + [("union", None)]
    for name, wahlperiode in scopes:
        members = [rid for rid, record in ids.items() if wahlperiode is None or wahlperiode in record["wahlperioden"]]
        row: dict[str, Any] = {"redner_ids": len(members)}
        for kind in ("M1", "M1a", "M1b"):
            group = [rid for rid in members if category(rid, wahlperiode, mdb, ids[rid]["wahlperioden"]) == kind]
            states = Counter(found[rid]["state"] for rid in group)
            # An id without an answer (failed or not asked) may still be a hit: the
            # share stays open and the upper bound counts it.
            unresolved = states["failed"] + states["not_cached"]
            row[kind] = {"ids": len(group), "hits": states["hit"], "misses": states["miss"],
                         "failed": states["failed"], "not_cached": states["not_cached"],
                         "share": _share(states["hit"], len(group)) if not unresolved else None,
                         "bounds": [_share(states["hit"], len(group)), _share(states["hit"] + unresolved, len(group))]}
        if mdb["source"] == "none":
            row["M1"] = None
        reden = [(rid, ids[rid]["reden"][wahlperiode] if wahlperiode else sum(ids[rid]["reden"].values())) for rid in members]
        reden_total = collected["reden_total"][wahlperiode] if wahlperiode else sum(collected["reden_total"].values())
        reden_hit = sum(count for rid, count in reden if found[rid]["state"] == "hit")
        reden_open = sum(count for rid, count in reden if found[rid]["state"] in ("failed", "not_cached"))
        without = collected["reden_without_id"][wahlperiode] if wahlperiode else sum(collected["reden_without_id"].values())
        row["M2"] = {"reden": reden_total, "reden_hit": reden_hit, "reden_unresolved": reden_open,
                     "share": _share(reden_hit, reden_total) if not reden_open else None,
                     "bounds": [_share(reden_hit, reden_total), _share(reden_hit + reden_open, reden_total)],
                     "reden_without_redner_id": without}
        figures[name] = row

    hits = {rid: answer for rid, answer in found.items() if rid in ids and answer["state"] == "hit"}
    # M3 flag 1: the name rule; flag 2: several politicians; flag 3: one profile for
    # several Redner-IDs; flag 4: a cached hit the fresh answer does not repeat.
    flag_name = [describe(rid) for rid, answer in sorted(hits.items()) if not label_ok(rid, answer["profile"].get("label"))]
    flag_multi = [describe(rid) for rid, answer in sorted(hits.items()) if (answer.get("candidates") or 0) > 1]
    by_aw: dict[Any, list[str]] = {}
    for rid, answer in sorted(hits.items()):
        by_aw.setdefault(answer["profile"].get("id"), []).append(rid)
    flag_shared = []
    for aw_id, rids in sorted(by_aw.items(), key=lambda item: str(item[0])):
        if len(rids) > 1:
            same = all(label_ok(rid, hits[rid]["profile"].get("label")) for rid in rids)
            flag_shared.append({"aw_id": aw_id, "key": f"aw:{aw_id}", "redner_ids": [describe(rid) for rid in rids],
                                "classified": "every id's names match the profile" if same else "names differ"})
    flag_cache = [
        {**describe(rid), "cached_id": found[rid]["cached_id"]}
        for rid in sorted(ids)
        if found[rid].get("cached_state") == "hit" and found[rid]["state"] in ("hit", "miss")
        and (found[rid]["state"] == "miss" or found[rid]["profile"].get("id") != found[rid]["cached_id"])
    ]
    role_ids = []
    for rid in sorted(hits):
        if category(rid, None, mdb, ids[rid]["wahlperioden"]) != "M1b":
            continue
        label = hits[rid]["profile"].get("label")
        owners = sorted(mdb_id for mdb_id, names in mdb["names"].items() if name_matches(label, names["given"], names["surname"]))
        role_ids.append({**describe(rid), "mdb_ids_by_name": owners})

    # M4: the name search for MdB-Stammdaten misses.
    m4 = None
    if fallback is not None:
        linked = sorted(rid for rid, answer in fallback.items() if answer["state"] == "hit")
        sample = linked if len(linked) <= REVIEW_SAMPLE else sorted(random.Random(REVIEW_SEED).sample(linked, REVIEW_SAMPLE))
        m4 = {
            "searched": len(fallback),
            "linked": len(linked),
            "unlinked": sum(1 for answer in fallback.values() if answer["state"] == "miss"),
            "failed": sum(1 for answer in fallback.values() if answer["state"] == "failed"),
            "review_sample_seed": REVIEW_SEED if len(linked) > REVIEW_SAMPLE else None,
            "review": [{**describe(rid), "aw": _profile_view(fallback[rid]["profile"]), "searched": fallback[rid]["searched"],
                        "name_rule": label_ok(rid, fallback[rid]["profile"].get("label"))} for rid in sample],
            "unlinked_ids": [describe(rid) for rid in sorted(fallback) if fallback[rid]["state"] == "miss"],
        }

    # M5: partitioned (shared) Redner-IDs and merged raw values.
    partitioned = []
    for partition in partitions:
        rid = partition["xml_redner_id"]
        if rid in ids:
            partitioned.append({**describe(rid), "profile_owner": partition.get("profile_owner"),
                                "hit": found[rid]["state"] == "hit"})
    merged = []
    for rid in sorted(ids):
        for raw in sorted(ids[rid]["raw"]):
            merged.append({"raw": raw, "redner_id": rid, "first_id_state": found[rid]["state"],
                           "raw_state": found.get(raw, {}).get("state")})

    return {
        "figures": figures,
        "m3": {"name_rule": flag_name, "several_politicians": flag_multi, "one_profile_several_ids": flag_shared,
               "cache_disagrees": flag_cache, "m1b_hits_matching_an_mdb_by_name": role_ids},
        "m4": m4,
        "m5": {"partitioned_ids": partitioned, "merged_raw_values": merged,
               "merged_hit_by_first_not_by_raw": sum(1 for row in merged if row["first_id_state"] == "hit" and row["raw_state"] != "hit")},
        "m6": {**m6, "wp18_19_mdb_ids_without_a_profile": {
            str(wp): sum(1 for rid, record in ids.items() if wp in record["wahlperioden"]
                         and category(rid, wp, mdb, record["wahlperioden"]) == "M1" and rid not in m6["ids_with_profile"])
            for wp in WAHLPERIODEN}},
        "failures": sorted(key for key, answer in found.items() if answer["state"] == "failed")
                    + sorted(f"name:{rid}" for rid, answer in (fallback or {}).items() if answer["state"] == "failed"),
        "failure_reasons": {**{key: answer.get("error") for key, answer in sorted(found.items()) if answer["state"] == "failed"},
                            **{f"name:{rid}": answer.get("error") for rid, answer in sorted((fallback or {}).items())
                               if answer["state"] == "failed"}},
    }


def carry_over(conn: sqlite3.Connection) -> dict[str, Any]:
    """M6: WP 18/19 Reden whose ``mps`` row holds a trusted profile today."""
    reden = Counter()
    with_profile = Counter()
    ids_with_profile: set[str] = set()
    rows = conn.execute(
        "SELECT p.document_number, m.xml_redner_id, m.aw_match FROM speeches s "
        "JOIN protocols p ON p.id = s.protocol_id LEFT JOIN mps m ON m.id = s.mp_id")
    for number, redner_id, aw_match in rows:
        wahlperiode = str(number).partition("/")[0]
        if not wahlperiode.isdigit() or int(wahlperiode) not in WAHLPERIODEN:
            continue
        reden[wahlperiode] += 1
        if aw_match == derive.TRUSTED_AW_MATCH:
            with_profile[wahlperiode] += 1
            if derive.first_redner_id(redner_id):
                ids_with_profile.add(derive.first_redner_id(redner_id))
    return {"store_reden": dict(reden), "reden_with_ext_id_profile": dict(with_profile), "ids_with_profile": ids_with_profile}


def apply_verdicts(result: dict[str, Any], verdicts: dict[str, Any]) -> None:
    """Add the hand review's verdict to each listed id (key: Redner-ID, or aw:<id>
    for a profile found for several ids)."""
    lists = [*result["m3"].values(), result["m5"]["partitioned_ids"]]
    if result["m4"]:
        lists.append(result["m4"]["review"])
    for entries in lists:
        for entry in entries:
            key = entry.get("key") or entry.get("redner_id")
            if key in verdicts:
                entry["verdict"] = verdicts[key]


def print_table(result: dict[str, Any], *, offline: bool) -> None:
    print(f"{'scope':6} {'kind':4} {'ids':>5} {'hits':>5} {'miss':>5} {'fail':>5} {'uncached':>8}  share")
    for scope, row in result["figures"].items():
        for kind in ("M1", "M1a", "M1b"):
            cell = row[kind]
            if cell is None:
                print(f"{scope:6} {kind:4}  (no MdB source)")
                continue
            share = cell["share"] if cell["share"] is not None else "bounds {}-{}".format(*cell["bounds"])
            print(f"{scope:6} {kind:4} {cell['ids']:5} {cell['hits']:5} {cell['misses']:5} {cell['failed']:5} {cell['not_cached']:8}  {share}")
        m2 = row["M2"]
        m2_share = m2["share"] if m2["share"] is not None else "bounds {}-{}".format(*m2["bounds"])
        print(f"{scope:6} M2   {m2['reden_hit']}/{m2['reden']} Reden hit ({m2_share}), {m2['reden_without_redner_id']} without a Redner-ID")
    if not offline:
        m3 = result["m3"]
        print("M3 flags: " + ", ".join(f"{name} {len(entries)}" for name, entries in m3.items()))
        if result["m4"]:
            m4 = result["m4"]
            print(f"M4 name search: {m4['linked']} linked, {m4['unlinked']} unlinked, {m4['failed']} failed of {m4['searched']}")
        print(f"M5: {len(result['m5']['partitioned_ids'])} partitioned ids spoke, {len(result['m5']['merged_raw_values'])} merged raw values, "
              f"{result['m5']['merged_hit_by_first_not_by_raw']} hit by the first id only")
    print(f"M6: {result['m6']['reden_with_ext_id_profile']} WP 18/19 Reden hold a trusted profile in the store")
    print(f"failures: {len(result['failures'])}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="measure_aw_match_share.py",
        description="Measure the abgeordnetenwatch ext_id match share of the WP 18/19 Redner of a store. Reads "
                    "OUTPUT_DIR only. Exit codes: 0 a complete result, 1 a lookup had no answer (rerun), 2 bad input.")
    parser.add_argument("output_dir", type=Path, help="site output directory (holds data/bundestag-pulse.sqlite)")
    parser.add_argument("--cache", type=Path, required=True,
                        help="scratch abgeordnetenwatch cache, outside OUTPUT_DIR; a first run seeds it from the store's")
    parser.add_argument("--stammdaten", type=Path,
                        help="MdB-Stammdaten zip (default: the store's cached zip in its private directory)")
    parser.add_argument("--offline", action="store_true", help="send nothing: print bounds and the request count")
    parser.add_argument("--name-fallback", action="store_true",
                        help="also run the name search for every MdB-Stammdaten id that missed")
    parser.add_argument("--json", type=Path, help="where the JSON receipt is written")
    parser.add_argument("--verdicts", type=Path, help="JSON object of review verdicts, by Redner-ID or aw:<id>")
    parser.add_argument("--sleep", type=float, default=None,
                        help=f"seconds between abgeordnetenwatch requests (default {aw.DEFAULT_MIN_INTERVAL})")
    return parser


def run(args: argparse.Namespace) -> int:
    output_dir = args.output_dir.resolve()
    database_path = output_dir / STORE
    if not database_path.is_file():
        raise UsageError(f"{database_path} does not exist")
    cache = args.cache.resolve()
    if cache == output_dir or output_dir in cache.parents:
        raise UsageError(f"--cache {cache} is inside OUTPUT_DIR, which this script never writes")
    if args.json is not None:
        receipt_path = args.json.resolve()
        if receipt_path == output_dir or output_dir in receipt_path.parents:
            raise UsageError(f"--json {receipt_path} is inside OUTPUT_DIR, which this script never writes")
        inputs = [cache, _answers_path(cache)] + [path.resolve() for path in (args.verdicts, args.stammdaten) if path is not None]
        if receipt_path in inputs:
            raise UsageError(f"--json {receipt_path} would overwrite an input of this run")
    if args.verdicts is not None:
        try:
            verdicts = json.loads(args.verdicts.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise UsageError(f"--verdicts {args.verdicts}: {exc}") from exc
        if not isinstance(verdicts, dict):
            raise UsageError(f"--verdicts {args.verdicts} is not a JSON object")
    else:
        verdicts = {}
    if args.sleep is not None and args.sleep < aw.DEFAULT_MIN_INTERVAL:
        raise UsageError(f"--sleep {args.sleep} is faster than abgeordnetenwatch's fair-use limit ({aw.DEFAULT_MIN_INTERVAL} s)")

    conn = sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True)
    try:
        sittings = stored_sittings(conn)
        if not sittings:
            raise UsageError(f"{database_path} holds no WP 18/19 sitting")
        mdb = mdb_sources(conn, database_path, args.stammdaten)
        m6 = carry_over(conn)
    finally:
        conn.close()

    started = datetime.now(timezone.utc)
    seeded_from = None
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists() and (output_dir / STORE_CACHE).exists():
        shutil.copyfile(output_dir / STORE_CACHE, cache)
        seeded_from = _home(output_dir / STORE_CACHE)
    resolver = aw.AbgeordnetenwatchResolver(cache_path=cache, sleep_seconds=args.sleep)
    cached_before = len(resolver._by_ext_id)

    with tempfile.TemporaryDirectory(prefix="aw-share-view-", dir=cache.parent) as view_root:
        collected = collect(output_dir, sittings, Path(view_root))
    ids = collected["ids"]
    merged_raw = sorted({raw for record in ids.values() for raw in record["raw"]})
    keys = sorted(ids) + merged_raw
    print(f"[aw-share] {len(ids)} Redner-IDs and {len(merged_raw)} merged raw values from "
          f"{sum(collected['sittings'].values())} sittings", file=sys.stderr)

    found = lookup_all(resolver, keys, cache, offline=args.offline)
    fallback = None
    if args.name_fallback and not args.offline:
        misses = sorted(rid for rid in ids if rid in mdb["known"] and found[rid]["state"] == "miss")
        fallback = name_fallback(resolver, ids, misses)
    partitions = registry.corrections()["partitions"]
    result = measure(collected, found, mdb, fallback, partitions, m6)
    apply_verdicts(result, verdicts)
    print_table(result, offline=args.offline)
    if args.offline:
        print(f"an online run sends {len(keys)} ext_id requests ({len(ids)} ids, {len(merged_raw)} merged raw values), "
              "plus one name search per MdB-Stammdaten miss with --name-fallback")

    if args.json:
        result["m6"]["ids_with_profile"] = len(result["m6"]["ids_with_profile"])
        receipt = {
            "commit": _commit(),
            "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "mode": "offline" if args.offline else "online",
            "name_fallback": bool(fallback is not None),
            "store": {"path": _home(database_path), "sha256": _sha256(database_path)},
            "person_corrections_sha256": _sha256(registry.CORRECTIONS_PATH),
            "cache": {"path": _home(cache), "seeded_from": seeded_from, "ext_id_entries_before": cached_before,
                      # When the answers this result counts were first asked for (an
                      # online rerun asks only the ids not answered since then).
                      "answers_started_at": None if args.offline else _load_answers(cache).get("started_at")},
            "mdb_source": mdb["source"],
            "stammdaten": mdb["zip"],
            "mandate_table_zip_disagreements_wp18_19": mdb["table_zip_disagreements_wp18_19"],
            "sittings": collected["sittings"],
            "sittings_excluded_by_record": collected["excluded"],
            "sittings_without_xml": collected["not_reparsed"],
            "requests": {"ext_id_keys": len(keys), **resolver.stats},
            **result,
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(receipt, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 1 if result["failures"] else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except UsageError as exc:
        print(f"ERROR [aw-share]: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
