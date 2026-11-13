"""ADR 0004 census, step 1: measure the figures that move in the kept store.

Scratch tooling, not shipped. Read-only on the store. Takes the census TSV,
selects the kept-sitting rows whose proposed kind takes a stored Rede out of
``speeches`` (``procedural``, ``sitzungsleitung``, ``ansprache``; optionally
the hard ``nomination`` rows), and reports old and new values for:
Reden per Redeanteil group (Zusammenschluss or Sprechrolle) per sitting and in
total, the Reden share per sitting, Textanteil (characters), TOP Reden counts,
Reden per Person, and erste-reden (the facts.py debut rule).

Usage (Python 3.11+):
  python3 measure.py --store-dir <.context/dip-pulse-site> --census docs/plans/adr-0004-census.tsv [--with-nominations]
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import facts  # noqa: E402

LEAVING = {"procedural", "sitzungsleitung", "ansprache"}
GROUP = ("CASE WHEN s.sprechrolle IS NOT NULL THEN 'Sprechrolle ' || s.sprechrolle "
         "ELSE COALESCE(NULLIF(s.fraktion, ''), pa.name) END")


def excluded(census: Path, xml_dir: Path, sittings: list[str]) -> dict:
    """Excluded sittings have no store row: parse each with the current parser
    and count Reden and Beiträge as it emits them today, then as the proposed
    kinds would (Reden that leave, Ansprachen added as Beiträge)."""
    import validate_dip_protocol as v
    rows = list(csv.DictReader(census.open(encoding="utf-8"), delimiter="\t"))
    out = {}
    for number in sittings:
        path = xml_dir / f"plenarprotokoll-{number.replace('/', '-')}.xml"
        if not path.exists():
            out[number] = {"xml": "missing"}
            continue
        try:
            report = v.parse_protocol_xml(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - recorded
            out[number] = {"parser": f"refused: {str(exc)[:160]}"}
            continue
        reden = {s["rede_id"] for item in report["agenda_items"] for s in item["speeches"]}
        beitraege = sum(len(item["contributions"]) for item in report["agenda_items"])
        mine = [r for r in rows if r["sitting"] == number and not r["marker"]]
        kinds = collections.Counter(r["proposed_kind"] for r in mine if r["rede_id"] in reden)
        leave = sum(kinds[k] for k in LEAVING)
        out[number] = {"reden": [len(reden), len(reden) - leave], "beitraege": [beitraege, beitraege + kinds["ansprache"]],
                       "leaving_by_kind": {k: kinds[k] for k in sorted(LEAVING | {"nomination"}) if kinds[k]}}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store-dir", type=Path, required=True)
    ap.add_argument("--census", type=Path, required=True)
    ap.add_argument("--with-nominations", action="store_true")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--excluded-xml-dir", type=Path, help="W1's XML: also measure the excluded sittings named by --excluded")
    ap.add_argument("--excluded", nargs="*", default=[])
    args = ap.parse_args()
    if args.excluded_xml_dir:
        print(json.dumps(excluded(args.census, args.excluded_xml_dir, args.excluded), ensure_ascii=False, indent=1))
        return
    leaving = LEAVING | ({"nomination"} if args.with_nominations else set())
    rows = [r for r in csv.DictReader(args.census.open(encoding="utf-8"), delimiter="\t")
            if r["stored"] == "kept" and r["proposed_kind"] in leaving and r["store_today"].startswith("speeches")
            and not r["marker"]]
    keys = {(r["sitting"], r["rede_id"]) for r in rows}
    source = sqlite3.connect(f"file:{args.store_dir / 'data' / 'bundestag-pulse.sqlite'}?mode=ro", uri=True)
    conn = sqlite3.connect(":memory:")
    source.backup(conn)
    source.close()
    facts.ensure_canonical(conn)
    conn.row_factory = sqlite3.Row
    speeches = conn.execute(
        f"SELECT s.id, p.document_number AS sitting, s.rede_id, s.char_count, s.agenda_item_id, COALESCE(ai.top_id, '') || ' ' || COALESCE(substr(ai.heading, 1, 50), '') AS heading, "
        f"{GROUP} AS grp, mc.canonical_id AS person, m.display_name "
        "FROM speeches s JOIN protocols p ON p.id = s.protocol_id JOIN agenda_items ai ON ai.id = s.agenda_item_id "
        "LEFT JOIN mps m ON m.id = s.mp_id LEFT JOIN parties pa ON pa.id = m.party_id "
        "LEFT JOIN mp_canonical mc ON mc.mp_id = m.id").fetchall()
    moved = [s for s in speeches if (s["sitting"], s["rede_id"]) in keys]
    missing = keys - {(s["sitting"], s["rede_id"]) for s in moved}
    moved_ids = {s["id"] for s in moved}
    sittings = sorted({s["sitting"] for s in moved}, key=lambda n: tuple(int(x) for x in n.split("/")))
    out = {"moved_reden": len(moved), "missing_in_store": sorted(missing), "per_sitting": {}, "totals": {}}

    total_old, total_new = collections.Counter(), collections.Counter()
    for s in speeches:
        total_old[s["grp"]] += 1
        if s["id"] not in moved_ids:
            total_new[s["grp"]] += 1
    out["totals"] = {g: [total_old[g], total_new[g]] for g in sorted(total_old, key=str) if total_old[g] != total_new[g]}
    out["totals_all"] = [sum(total_old.values()), sum(total_new.values())]

    for number in sittings:
        here = [s for s in speeches if s["sitting"] == number]
        old = collections.Counter(s["grp"] for s in here)
        new = collections.Counter(s["grp"] for s in here if s["id"] not in moved_ids)
        chars_old = collections.Counter()
        chars_new = collections.Counter()
        for s in here:
            chars_old[s["grp"]] += s["char_count"]
            if s["id"] not in moved_ids:
                chars_new[s["grp"]] += s["char_count"]
        n_old, n_new = sum(old.values()), sum(new.values())
        c_old, c_new = sum(chars_old.values()), sum(chars_new.values())
        groups = {}
        for g in sorted(old, key=str):
            groups[str(g)] = {
                "reden": [old[g], new[g]],
                "share_pct": [round(100 * old[g] / n_old, 2), round(100 * new[g] / n_new, 2) if n_new else None],
                "textanteil_pct": [round(100 * chars_old[g] / c_old, 2), round(100 * chars_new[g] / c_new, 2) if c_new else None],
            }
        tops = collections.Counter(s["heading"][:70] for s in here if s["id"] in moved_ids)
        top_old = collections.Counter(s["heading"][:70] for s in here)
        out["per_sitting"][number] = {
            "reden": [n_old, n_new], "chars": [c_old, c_new], "groups": groups,
            "tops": {t: [top_old[t], top_old[t] - tops[t]] for t in tops},
        }

    person_old = collections.Counter(s["person"] for s in speeches if s["person"])
    person_moved = collections.Counter(s["person"] for s in moved if s["person"])
    names = {s["person"]: s["display_name"] for s in moved}
    out["per_person"] = {f"{names[p]} ({p})": [person_old[p], person_old[p] - person_moved[p]]
                         for p in sorted(person_moved, key=lambda p: names[p])}

    # erste-reden: the facts.py debut query, before and after removing the moved Reden.
    metric = next(m for m in facts.REGISTRY if m["id"] == "erste-reden")
    debut_old = {r[0] for r in conn.execute(metric["sql"]).fetchall()}
    conn_mem = sqlite3.connect(":memory:")
    conn.backup(conn_mem)
    facts.ensure_canonical(conn_mem)
    conn_mem.executemany("DELETE FROM speeches WHERE id = ?", [(i,) for i in moved_ids])
    debut_new = {r[0] for r in conn_mem.execute(metric["sql"]).fetchall()}
    lost = debut_old - debut_new
    gained = debut_new - debut_old
    by_id = {s["id"]: s for s in speeches}
    import datetime
    dates = dict(conn.execute("SELECT document_number, date FROM protocols"))

    def week(i):
        y, w, _ = datetime.date.fromisoformat(dates[by_id[i]["sitting"]][:10]).isocalendar()
        return f"{y}-W{w:02d}"
    weeks_old = collections.Counter(week(i) for i in debut_old)
    weeks_new = collections.Counter(week(i) for i in debut_new)
    out["erste_reden_weeks"] = {w: [weeks_old[w], weeks_new[w]] for w in sorted(set(weeks_old) | set(weeks_new))
                                if weeks_old[w] != weeks_new[w]}
    out["erste_reden"] = {
        "old_count": len(debut_old), "new_count": len(debut_new),
        "lost": sorted(f"{by_id[i]['sitting']} {by_id[i]['rede_id']} {by_id[i]['display_name']}" for i in lost),
        "gained": sorted(f"{by_id[i]['sitting']} {by_id[i]['rede_id']} {by_id[i]['display_name']}" for i in gained),
    }
    text = json.dumps(out, ensure_ascii=False, indent=1)
    if args.json:
        args.json.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
