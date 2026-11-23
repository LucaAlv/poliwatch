#!/usr/bin/env python3
"""Census of stored Reden that DIP types as another kind of contribution.

Read-only. For each sitting it matches every stored Rede, Kurzintervention and
Erwiderung to DIP's Aktivitäten (kept in the cached report) by surname, page and
page quadrant, and prints one TSV row per disagreement with the evidence a
reader needs: what the Sitzungsleitung said just before, how the turn opens, and
who spoke before it. DIP is a lead, not the verdict.

Usage: census.py <site output dir> > docs/plans/beitraege-as-reden.tsv
"""

from __future__ import annotations

import collections
import csv
import json
import re
import sqlite3
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

DIP_KIND = {
    "Kurzintervention": "kurzintervention",
    "Erwiderung": "erwiderung",
    "Erklärung zur Aussprache gem. § 30 Geschäftsordnung BT": "erklaerung_30",
    "Mündliche Erklärung gem. § 31 Geschäftsordnung BT": "erklaerung_31",
    "Persönliche Erklärung gem. § 32 Geschäftsordnung BT": "erklaerung_32",
    "Rede (zu Protokoll gegeben)": "zu_protokoll",
    "Zur Geschäftsordnung BT": "geschaeftsordnung",
    "Erklärung zum Vermittlungsverfahren (§ 90 GO-BT, § 10 GO-VermA)": "vermittlungsverfahren",
    "Berichterstattung": "berichterstattung",
    "Erklärung zum Plenarprotokoll": "erklaerung_plenarprotokoll",
    "Wortbeitrag": "wortbeitrag",
    "Zwischenfrage": "zwischenfrage",
    "Rede": "rede",
}
SALUTATION = re.compile(
    r"^(?:Vielen Dank[^.!–]*[.!–]\s*[–-]?\s*)?(?:Sehr |Meine |Liebe |Verehrte|Werte|Hochverehrte|Geehrte)?"
    r"(?:geehrte[rs]? |verehrte[rs]? |sehr )*(?:Herr|Frau|Damen|Kolleg)\w*", re.IGNORECASE)
#: The chair's words that grant each kind. Used to confirm DIP, and to find the
#: turns DIP calls a Rede or does not list.
WORDING = {
    "kurzintervention": re.compile(r"Kurzintervention|Zwischenintervention|\bIntervention\b"),
    "erwiderung": re.compile(r"Erwiderung|erwidern|zu reagieren|(?:zu |Sie |möchten )antworten|zur Antwort|zum Antworten|Ihre Antwort"),
    "erklaerung_30": re.compile(r"§\s*30\b|Erklärung zur Aussprache|persönliche[nr]? Erklärung"),
    "erklaerung_31": re.compile(r"§\s*31\b|Erklärung zur Abstimmung"),
    "erklaerung_32": re.compile(r"§\s*32\b"),
}
#: Decisions 1 to 3 of 2026-11-23; the other DIP kinds wait for the owner.
DECIDED = {"kurzintervention": "kurzintervention", "erwiderung": "erwiderung", "erklaerung_30": "erklaerung",
           "erklaerung_31": "erklaerung", "erklaerung_32": "erklaerung", "zu_protokoll": "zu_protokoll"}
NEXT_SPEAKER = re.compile(r"[Nn]ächste[rn]? (?:Redner|hat)|ersten Rede|als Nächste")
SHORT = 2600
COLUMNS = ["sitting", "rede_id", "redner_id", "stored", "dip", "match", "chars", "proposed", "read", "page", "speaker",
           "previous", "chair_before", "opens"]


def proposal(unit: dict, dip: str, chair: str, previous: str) -> tuple[str, str]:
    """The proposed kind and why a person must read the row (empty: no reason)."""
    worded = [kind for kind, wording in WORDING.items() if wording.search(chair)]
    reasons = []
    if unit["stored"] != "rede":
        return "", "stored as a Beitrag, DIP disagrees"
    if dip in ("", "rede"):
        return DECIDED[worded[0]], "wording only, DIP does not confirm"
    if dip not in DECIDED:
        return "", "no decided kind"
    if unit["match"] == "near":
        reasons.append("page differs by one or quadrant differs")
    if dip in ("kurzintervention", "erwiderung") and unit["chars"] > SHORT:
        reasons.append("long")
    if fold(previous) and fold(previous) == surname(unit["speaker"]):
        reasons.append("same speaker before: own words printed as a new <rede>?")
    if dip != "zu_protokoll" and NEXT_SPEAKER.search(chair):
        reasons.append("announced as the next speaker")
    if dip != "zu_protokoll" and worded and dip not in worded:
        reasons.append("the chair's wording names " + ", ".join(worded))
    if dip == "zu_protokoll" and re.match(r"(?:Sehr (?:geehrte|verehrte)|Herr Präsident|Frau Präsidentin|Vielen Dank)", unit["text"] or ""):
        reasons.append("opens with a salutation")
    return DECIDED[dip], "; ".join(reasons)


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()


def fold(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower().replace("ß", "ss"))
    return re.sub(r"[^a-z]", "", value.encode("ascii", "ignore").decode())


def surname(name: str | None) -> str:
    words = re.sub(r"\(.*?\)", "", name or "").split(",")[0].split()
    return fold(words[-1]) if words else ""


def page_of(value: object) -> tuple[int | None, str]:
    found = re.match(r"(\d+)\s*([A-D]?)", str(value or ""))
    return (int(found.group(1)), found.group(2)) if found else (None, "")


def stored_units(db: sqlite3.Connection) -> dict[str, list[dict]]:
    units = collections.defaultdict(list)
    for row in db.execute(
        "select p.document_number sitting, s.rede_id, s.page, s.page_quadrant quadrant, s.char_count chars, "
        "m.display_name speaker, m.xml_redner_id redner_id, 'rede' stored, s.text "
        "from speeches s join protocols p on p.id = s.protocol_id left join mps m on m.id = s.mp_id "
        "union all select p.document_number, c.rede_id, c.page, null, c.char_count, "
        "coalesce(m.display_name, c.speaker_name), m.xml_redner_id, c.kind, c.text "
        "from contributions c join protocols p on p.id = c.protocol_id left join mps m on m.id = c.mp_id "
        "where c.kind in ('kurzintervention', 'erwiderung')"):
        units[row["sitting"]].append(dict(row))
    return units


def chair_context(xml: Path) -> dict[str, tuple[str, str]]:
    """Per ``<rede>``: the chair's words just before it and who spoke before."""
    context, before, previous = {}, "", ""
    body = ET.parse(xml).getroot().find("sitzungsverlauf")
    for elem in body.iter() if body is not None else ():
        if elem.tag == "tagesordnungspunkt":
            before, previous = "", ""
            in_rede = set(elem.findall(".//rede/p"))
            loose = [p for p in elem.findall("p") if p.get("klasse") != "redner" and p not in in_rede]
            before = " ".join(clean("".join(p.itertext())) for p in loose[:3])
        if elem.tag != "rede":
            continue
        context[elem.get("id", "")] = (before[-400:], previous)
        chair, words = False, []
        for child in elem:
            if child.tag == "name":
                chair, words = True, []
            elif child.tag == "p" and child.get("klasse") == "redner":
                chair, words = False, []
                previous = surname_of_marker(child) or previous
            elif chair and child.tag == "p":
                words.append(clean("".join(child.itertext())))
        before = " ".join(words) if chair else ""
    return context


def surname_of_marker(marker: ET.Element) -> str:
    return clean(marker.findtext("redner/name/nachname"))


def main(output: Path) -> None:
    data = output / "data"
    db = sqlite3.connect(f"file:{data / 'bundestag-pulse.sqlite'}?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    units = stored_units(db)
    writer = csv.DictWriter(sys.stdout, COLUMNS, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    totals: collections.Counter = collections.Counter()
    for sitting in sorted(units, key=lambda s: tuple(map(int, s.split("/")))):
        report = json.loads((data / f"plenarprotokoll-{sitting.replace('/', '-')}.json").read_text(encoding="utf-8"))
        context = chair_context(data / "xml" / f"plenarprotokoll-{sitting.replace('/', '-')}.xml")
        acts = []
        for act in report["api_records"]["aktivitaeten"]:
            kind = DIP_KIND.get(act["aktivitaetsart"])
            if kind:
                acts.append({"kind": kind, "surname": surname(act["titel"]), "used": False,
                             "page": page_of(act["fundstelle"].get("seite"))})
        # An exact page and quadrant first; then, for what is left over on both
        # sides, the same person within one page.
        for wide in (False, True):
            for unit in units[sitting]:
                if unit.get("act") or unit["page"] is None:
                    continue
                hits = [a for a in acts if not a["used"] and a["surname"] == surname(unit["speaker"])
                        and a["page"][0] is not None
                        and (abs(a["page"][0] - unit["page"]) <= 1 if wide else a["page"][0] == unit["page"])
                        and (wide or not unit["quadrant"] or not a["page"][1] or a["page"][1] == unit["quadrant"])]
                same = [a for a in hits if a["kind"] == unit["stored"]]
                hit = (same or (hits if not wide or len(hits) == 1 else []) or [None])[0]
                if hit is not None:
                    hit["used"], unit["act"], unit["match"] = True, hit, "near" if wide else "exact"
        for unit in units[sitting]:
            dip = unit["act"]["kind"] if unit.get("act") else ""
            totals[(unit["stored"], dip or "-")] += 1
            chair, previous = context.get(unit["rede_id"], ("", ""))
            if dip == unit["stored"] or not dip:
                # DIP sees nothing here; the chair's last words may.
                if unit["stored"] != "rede" or unit["chars"] > SHORT or NEXT_SPEAKER.search(chair[-260:]) \
                        or not any(w.search(chair[-160:]) for w in WORDING.values()):
                    continue
                dip = dip or ""
            proposed, read = proposal(unit, dip, chair[-260:], previous)
            if not proposed and not read:
                continue
            writer.writerow({
                "sitting": sitting, "rede_id": unit["rede_id"], "redner_id": unit["redner_id"] or "",
                "stored": unit["stored"], "dip": dip, "match": unit.get("match", ""), "chars": unit["chars"],
                "proposed": proposed, "read": read,
                "page": f"{unit['page']}{unit['quadrant'] or ''}", "speaker": unit["speaker"], "previous": previous,
                "chair_before": chair[-260:], "opens": clean(unit["text"])[:110]})
    for (stored, dip), count in sorted(totals.items(), key=lambda item: -item[1]):
        print(f"{count:6} stored {stored}, DIP {dip}", file=sys.stderr)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
