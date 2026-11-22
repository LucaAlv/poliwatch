"""Write the name_* entries of scripts/reviewed_units.json from name-tag-speakers.tsv.

The owner took the TSV's kind and proposed Redner-ID per entry as the review
(docs/plans/name-tag-speakers.md, section 4, decided 2026-11-21). An entry inside
a <rede> names the host <rede> and the printed tag; one outside any <rede> names
its tag's position among the Sitzungsverlauf's <name> elements (N<ordinal>),
read from the XML by the parser's own name_tags, one entry per turn.

Usage: python -I make_entries.py <store dir>   (rewrites scripts/reviewed_units.json)
"""
import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import validate_dip_protocol as dip  # noqa: E402

TSV = ROOT / "docs/plans/name-tag-speakers.tsv"
LIST = ROOT / "scripts/reviewed_units.json"
REASONS = {
    "rede": "a whole Rede the chair gave the floor to, printed under <name>",
    "zwischenfrage": "a Zwischenfrage printed under <name>",
    "befragung_frage": "a Frage in a Befragung printed under <name>",
    "befragung_antwort": "an Antwort in a Befragung printed under <name>",
    "fragestunde_frage": "a Zusatzfrage in a Fragestunde printed under <name>",
    "own_words": "the host Rede's own speaker printed under <name>",
    "oath_answer": "an oath answer printed under <name>: procedural (ADR 0004)",
    "ansprache": "an invited guest's address printed under <name>: an Ansprache with no Redner-ID (owner, 2026-11-21)",
    "remark": "a remark at the lectern before the floor is given, printed under <name>: stored nowhere",
}


def redner_id(row, owner):
    proposed = row["proposed_redner_id"]
    if row["kind"] in ("oath_answer", "ansprache", "remark"):
        return ""
    if proposed == "host owner's":
        return owner
    if proposed.startswith("none: bind by DIP person "):
        return "dip:" + proposed.rsplit(" ", 1)[1]
    match = re.match(r"\d+", proposed)
    if not match:
        raise SystemExit(f"{row['sitting']} {row['name_tag']}: no Redner-ID in {proposed!r}")
    return match.group()


def main(store):
    rows = list(csv.DictReader((line for line in TSV.open(encoding="utf-8") if not line.startswith("#")), delimiter="\t"))
    entries, seen = [], set()
    by_sitting = {}
    for row in rows:
        by_sitting.setdefault(row["sitting"], []).append(row)
    for sitting, sitting_rows in by_sitting.items():
        wp, nr = sitting.split("/")
        root = ET.parse(Path(store) / f"data/xml/plenarprotokoll-{wp}-{nr}.xml").getroot()
        dip.mark_stage_direction_names(root)
        tags = dip.name_tags(root)
        chairs = dip.sitting_chairs(tags)
        parents = {child: parent for parent in root.iter() for child in parent}

        def host(element):
            node = parents.get(element)
            while node is not None and node.tag != "rede":
                node = parents.get(node)
            return node

        outside = [(ordinal, dip.name_tag(el)) for ordinal, el in enumerate(tags, 1)
                   if host(el) is None and not dip.chair_tag(dip.name_tag(el), chairs)]
        outside_rows = sorted((r for r in sitting_rows if r["population"] == "outside_rede"), key=lambda r: int(r["turn_index"]))
        if [tag for _, tag in outside] != [r["name_tag"] for r in outside_rows]:
            raise SystemExit(f"{sitting}: outside tags {outside} do not match the TSV's {[r['name_tag'] for r in outside_rows]}")
        for (ordinal, tag), row in zip(outside, outside_rows):
            entries.append({"sitting": sitting, "rede_id": f"N{ordinal}", "redner_id": redner_id(row, None),
                            "kind": f"name_{'procedural' if row['kind'] == 'oath_answer' else row['kind']}",
                            "reason": f"{REASONS[row['kind']]} (name-tag-speakers.tsv entry {row['entry']})", "name": tag})
        for row in (r for r in sitting_rows if r["population"] == "in_rede"):
            key = (sitting, row["rede_id"], row["name_tag"])
            if key in seen:
                continue
            seen.add(key)
            rede = next(r for r in root.iter("rede") if r.get("id") == row["rede_id"])
            if not any(dip.name_tag(el) == row["name_tag"] for el in rede.iter("name") if len(el) == 0):
                raise SystemExit(f"{sitting} {row['rede_id']}: no <name> {row['name_tag']!r}")
            owner = dip.redner_key(rede.find("./p[@klasse='redner']/redner"))
            entries.append({"sitting": sitting, "rede_id": row["rede_id"], "redner_id": redner_id(row, owner),
                            "kind": f"name_{'procedural' if row['kind'] == 'oath_answer' else row['kind']}",
                            "reason": f"{REASONS[row['kind']]} (name-tag-speakers.tsv entry {row['entry']})", "name": row["name_tag"]})
    data = json.loads(LIST.read_text(encoding="utf-8"))
    kept = [e for e in data["entries"] if not e["kind"].startswith("name_")]
    for e in kept:
        # Frei's and Bartz's Reden now split off before Groth's § 31 part.
        if (e["sitting"], e["rede_id"]) == ("18/29", "ID1802902700:2"):
            e["rede_id"] = "ID1802902700:2:2:2"
    order = lambda e: tuple(int(x) for x in e["sitting"].split("/"))
    merged = sorted(kept + entries, key=order)
    LIST.write_text(json.dumps({"entries": merged}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(entries)} name entries written; {len(merged)} entries in all")


if __name__ == "__main__":
    main(sys.argv[1])
