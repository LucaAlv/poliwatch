"""Write the loose_* entries of scripts/reviewed_units.json from loose-speaker-markers.tsv.

The owner took the TSV's kind and attach per marker as the review
(docs/plans/loose-speaker-markers.md, section 4, decided 2026-11-22). Each entry
names its marker as M<ordinal>, read from the XML by the parser's own
loose_marker_ordinals, and is checked against the marker's printed Redner-ID.
Only loose_* entries are replaced; every other entry is kept as it is.

Usage: python -I make_entries.py <store dir>   (rewrites scripts/reviewed_units.json)
"""
import csv
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import validate_dip_protocol as dip  # noqa: E402

TSV = ROOT / "docs/plans/loose-speaker-markers.tsv"
LIST = ROOT / "scripts/reviewed_units.json"
REASONS = {
    "rede": "a whole Rede printed outside any <rede>",
    "own_words": "the speaker's own words printed outside their <rede>",
    "zwischenfrage": "a Zwischenfrage printed outside any <rede>",
    "befragung_frage": "a Frage in a Befragung printed outside any <rede>",
    "befragung_antwort": "an Antwort in a Befragung printed outside any <rede>",
    "procedural": "a procedural turn printed outside any <rede>",
    "sitzungsleitung": "the chair printed with a speaker marker outside any <rede>",
    "remark": "a remark printed outside any <rede>: stored nowhere",
}


def main(store: str) -> None:
    rows = list(csv.DictReader(TSV.open(encoding="utf-8"), delimiter="\t"))
    entries = []
    roots: dict[str, ET.Element] = {}
    for row in rows:
        sitting = row["sitting"]
        if sitting not in roots:
            wp, nr = sitting.split("/")
            roots[sitting] = ET.parse(Path(store) / f"data/xml/plenarprotokoll-{wp}-{nr}.xml").getroot()
        root = roots[sitting]
        ordinals = dip.loose_marker_ordinals(root)
        by_ordinal = {ordinal: marker for marker in root.iter("p") for ordinal in [ordinals.get(id(marker))] if ordinal}
        marker = by_ordinal.get(int(row["marker"][1:]))
        if marker is None or marker.find("redner").get("id") != row["redner_id"]:
            raise SystemExit(f"{sitting} {row['marker']}: the XML's marker does not print Redner-ID {row['redner_id']}")
        note = f": {row['note']}" if row["note"] else ""
        entries.append({"sitting": sitting, "rede_id": row["marker"], "redner_id": row["redner_id"],
                        "kind": f"loose_{row['kind']}", "reason": f"{REASONS[row['kind']]}{note} (loose-speaker-markers.tsv)",
                        "attach": row["attach"]})
    data = json.loads(LIST.read_text(encoding="utf-8"))
    kept = [e for e in data["entries"] if not e["kind"].startswith("loose_")]
    order = lambda e: tuple(int(x) for x in e["sitting"].split("/"))
    merged = sorted(kept + entries, key=order)
    LIST.write_text(json.dumps({"entries": merged}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(entries)} loose entries written; {len(merged)} entries in all")


if __name__ == "__main__":
    main(sys.argv[1])
