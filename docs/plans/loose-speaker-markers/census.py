"""Census of speaker markers that stand directly in a Tagesordnungspunkt that is
not a Fragestunde, outside any ``<rede>`` (docs/plans/loose-speaker-markers.md).

usage: python -I docs/plans/loose-speaker-markers/census.py <store> <out.tsv>

<store> is a site directory with data/xml/plenarprotokoll-*.xml and
data/bundestag-pulse.sqlite (opened read-only). One row per marker:
- ``marker``: ``M<ordinal>``, the marker's 1-based position among all
  ``<p klasse="redner">`` children of the sitting's TOPs (Fragestunde TOPs
  included), in source order;
- ``run``: the run it belongs to, the stretch of TOP children between two
  ``<rede>`` elements (or the TOP's start or end);
- ``prev_owner`` / ``next_owner``: the owner of the ``<rede>`` before and after the run;
- ``words``: words of the marker's paragraphs up to the next marker, ``<name>``
  or ``<rede>``; ``words_to_first_kommentar``: the same, stopping at the first
  non-paragraph element (the method of the 2026-11-12 count, which undercounts);
- ``in_store``: whether 80 characters from the middle of the marker's longest
  paragraph occur in any stored speech or contribution text of the sitting.
"""
import csv
import pathlib
import sqlite3
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import speech_kinds  # noqa: E402
import validate_dip_protocol as dip  # noqa: E402

HEADING_CLASSES = {"T_NaS", "T_fett", "T_ohne_NaS"}


def heading_of(top: ET.Element) -> str:
    lines, zusatz = [], []
    for p in top.findall("p"):
        klass, text = p.attrib.get("klasse", ""), dip.elem_text(p)
        if klass in HEADING_CLASSES and text:
            lines.append(text)
        elif klass == "T_ZP_NaS" and text:
            zusatz.append(text)
    return dip.clean_text(" ".join(lines or zusatz))


def is_marker(e: ET.Element) -> bool:
    return e.tag == "p" and e.get("klasse") == "redner"


def speaker(marker: ET.Element | None) -> tuple[str, str]:
    redner = marker.find("redner") if marker is not None else None
    if redner is None:
        return "", ""
    name = redner.find("name")
    parts = [dip.elem_text(name.find(t)) for t in ("vorname", "nachname") if name is not None and name.find(t) is not None]
    return redner.get("id") or "", " ".join(p for p in parts if p) or dip.clean_text(dip.elem_text(marker))


def words(e: ET.Element) -> int:
    return len(dip.clean_text(dip.elem_text(e)).split())


def main() -> None:
    store, out_path = pathlib.Path(sys.argv[1]), sys.argv[2]
    db = sqlite3.connect(f"file:{store / 'data/bundestag-pulse.sqlite'}?mode=ro&immutable=1", uri=True)
    paths = sorted((store / "data/xml").glob("plenarprotokoll-*.xml"), key=lambda p: [int(x) for x in p.stem.split("-")[1:]])
    rows = []
    for path in paths:
        sitting = path.stem.removeprefix("plenarprotokoll-").replace("-", "/")
        root = ET.fromstring(path.read_text(encoding="utf-8"))
        ordinal, run_no, sitting_rows = 0, 0, []
        for top in root.findall("./sitzungsverlauf/tagesordnungspunkt"):
            kids = list(top)
            fragestunde = speech_kinds.FRAGESTUNDE in speech_kinds.heading_formats(heading_of(top))
            current_run = None
            for i, child in enumerate(kids):
                if child.tag == "rede":
                    current_run = None
                if not is_marker(child):
                    continue
                ordinal += 1
                if fragestunde:
                    continue
                if current_run is None:
                    run_no += 1
                    current_run = run_no
                start = i
                while start > 0 and kids[start - 1].tag != "rede":
                    start -= 1
                end = i
                while end < len(kids) and kids[end].tag != "rede":
                    end += 1
                prev_rede = kids[start - 1] if start > 0 else None
                next_rede = kids[end] if end < len(kids) else None
                paragraphs, total, to_kommentar, stopped = [], 0, 0, False
                for following in kids[i + 1:]:
                    if following.tag in ("rede", "name") or is_marker(following):
                        break
                    if following.tag != "p":
                        stopped = True
                        continue
                    n = words(following)
                    total += n
                    to_kommentar += 0 if stopped else n
                    paragraphs.append(" ".join(dip.clean_text(dip.elem_text(following)).split()))
                redner_id, name = speaker(child)
                sitting_rows.append({
                    "sitting": sitting, "top": top.get("top-id"), "marker": f"M{ordinal}", "run": f"{sitting}#{current_run}",
                    "redner_id": redner_id, "speaker": name,
                    "prev_owner": speaker(prev_rede.find("p[@klasse='redner']") if prev_rede is not None else None)[1],
                    "next_owner": speaker(next_rede.find("p[@klasse='redner']") if next_rede is not None else None)[1],
                    "words": total, "words_to_first_kommentar": to_kommentar,
                    "probe": (lambda p: p[len(p) // 2 - 40: len(p) // 2 + 40] if len(p) > 100 else p)(max(paragraphs, key=len) if paragraphs else ""),
                    "first_words": " ".join((paragraphs[0] if paragraphs else "").split()[:12]),
                })
        if not sitting_rows:
            continue
        pid = db.execute("select id from protocols where document_number = ?", (sitting,)).fetchone()
        texts = []
        if pid:
            for table in ("speeches", "contributions"):
                texts += [" ".join((r[0] or "").split()) for r in db.execute(f"select text from {table} where protocol_id = ?", pid)]
        blob = "\n".join(texts)
        for row in sitting_rows:
            row["in_store"] = "yes" if row["probe"] and row.pop("probe") in blob else "no"
            row.pop("probe", None)
            rows.append(row)
    fields = ["sitting", "top", "marker", "run", "redner_id", "speaker", "prev_owner", "next_owner",
              "words", "words_to_first_kommentar", "in_store", "first_words"]
    with open(out_path, "w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} markers in {len({r['sitting'] for r in rows})} sittings, {len({r['run'] for r in rows})} runs, "
          f"{sum(r['words'] for r in rows)} words ({sum(r['words_to_first_kommentar'] for r in rows)} to the first kommentar), "
          f"{sum(r['in_store'] == 'yes' for r in rows)} probes found in the store")


if __name__ == "__main__":
    main()
