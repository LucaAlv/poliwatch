"""ADR 0004 census: precision of the P4/P5 detector text tests over the store.

Scratch tooling, not shipped. Read-only. Runs the two text tests of the
revised P4 and P5 over every stored Rede and Beitrag and reports any hit the
census did not review as procedural (a detector false positive would refuse a
sitting once the code lands).

Usage: python3 sweep.py --store-dir <.context/dip-pulse-site>
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OATH = re.compile(r"\b[Ii]ch schwöre\b")
ACCEPT = re.compile(r"\b[Nn]ehme\b[^.!?]{0,40}\b(?:[Ww]ahl|sie)\b[^.!?]{0,30}\ban\b")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store-dir", type=Path, required=True)
    args = ap.parse_args()
    tsv = ROOT / "docs" / "plans" / "adr-0004-census.tsv"
    reviewed = {(r["sitting"], r["rede_id"]) for r in csv.DictReader(tsv.open(encoding="utf-8"), delimiter="\t")
                if r["proposed_kind"] == "procedural"}
    conn = sqlite3.connect(f"file:{args.store_dir / 'data' / 'bundestag-pulse.sqlite'}?mode=ro", uri=True)
    q = ("SELECT 'speech', p.document_number, s.rede_id, s.char_count, s.text FROM speeches s "
         "JOIN protocols p ON p.id = s.protocol_id "
         "UNION ALL SELECT c.kind, p.document_number, c.rede_id, c.char_count, c.text FROM contributions c "
         "JOIN protocols p ON p.id = c.protocol_id")
    hits = {"P5 oath (<=400)": [], "P4 acceptance (<=200)": []}
    for kind, number, rid, chars, text in conn.execute(q):
        text = text or ""
        if chars <= 400 and OATH.search(text):
            hits["P5 oath (<=400)"].append((kind, number, rid, text[:90], (number, rid) in reviewed))
        if chars <= 200 and ACCEPT.search(text):
            hits["P4 acceptance (<=200)"].append((kind, number, rid, text[:90], (number, rid) in reviewed))
    for name, rows in hits.items():
        print(f"{name}: {len(rows)} stored units, {sum(r[-1] for r in rows)} reviewed as procedural")
        for row in rows:
            if not row[-1]:
                print("  NOT REVIEWED:", row[:-1])


if __name__ == "__main__":
    main()
