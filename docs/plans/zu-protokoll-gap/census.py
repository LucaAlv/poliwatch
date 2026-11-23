#!/usr/bin/env python3
"""Census: Reden zu Protokoll DIP lists and the store lacks, per sitting, and
the sittings whose Protokoll XML stops before the sitting ends.

Read-only. Usage, from a data directory of a replay:

    uv run --no-project --python 3.13 python -I census.py DATA_DIR > per-sitting.tsv

DATA_DIR holds `bundestag-pulse.sqlite`, `plenarprotokoll-*.json` and
`xml/plenarprotokoll-*.xml`. A row is printed for each sitting whose DIP and
stored count of Reden zu Protokoll differ or whose XML prints the notice of a
first edition ("Der gesamte und damit endgültige Stenografische Bericht der N.
Sitzung wird am … veröffentlicht."). Totals and the sittings where DIP lists a
Rede past the XML's last `<rede>` without the notice go to stderr.

The cut is the page and quadrant of the last `<rede>` outside the annexes, as the
XML's own Inhaltsverzeichnis gives it (20/210: as DIP gives it). DIP positions after it are in the part the
XML does not print. A turn that starts in the cut's own quadrant is not counted
after it, so the numbers "after the cut" are lower bounds. The Fragen and Antworten
of a Fragestunde stand outside any `<rede>` and can fall after the last one in a
complete file too; they are left out.
"""

from __future__ import annotations

import collections
import json
import re
import sqlite3
import sys
from pathlib import Path

NOTICE = re.compile(r"gesamte und damit endgültige Stenografische Bericht")
NOTICE_DATE = re.compile(r"Sitzung wird am (\d+\.\s*\w+ \d{4})")
XREF = re.compile(r'<xref[^>]*\bref-type="rede"[^>]*>', re.S)
SPOKEN = {
    "Rede", "Kurzintervention", "Erwiderung", "Zwischenfrage", "Frage", "Antwort", "Zusatzfrage",
    "Zur Geschäftsordnung BT", "Einleitende Ausführungen und Beantwortung", "Berichterstattung",
    "Berichterstattung und Beantwortung", "Erklärung zur Aussprache gem. § 30 Geschäftsordnung BT",
    "Mündliche Erklärung gem. § 31 Geschäftsordnung BT", "Persönliche Erklärung gem. § 32 Geschäftsordnung BT",
    "Erklärung zum Vermittlungsverfahren (§ 90 GO-BT, § 10 GO-VermA)", "Wortbeitrag",
}
ZP = "Rede (zu Protokoll gegeben)"
TURNS = {"Zwischenfrage", "Kurzintervention", "Erwiderung"}
#: 20/210 prints its Inhaltsverzeichnis without page numbers. The place is DIP's for
#: its last `<rede>` (ID2021013400, Christiane Schenderlein).
CUT_FROM_DIP = {"20/210": (27367, "B")}


def place(text: str | None) -> tuple[int, str]:
    match = re.match(r"(\d+)\s*([A-D]?)", text or "")
    return (int(match[1]), match[2]) if match else (0, "")


def xml_cut(xml: str) -> tuple[int, str]:
    body = xml[xml.find("<sitzungsverlauf") : xml.find("</sitzungsverlauf>")]
    ids = set(re.findall(r'<rede id="([^"]+)"', body))
    toc = xml[: xml.find("<sitzungsverlauf")]
    places = []
    for tag in XREF.findall(toc):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', tag))
        if attrs.get("rid") in ids and attrs.get("pnr", "").isdigit():
            places.append((int(attrs["pnr"]), attrs.get("div", "")))
    return max(places, default=(0, ""))


def main(data: Path) -> None:
    con = sqlite3.connect(f"file:{data}/bundestag-pulse.sqlite?mode=ro", uri=True)
    stored: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for number, kind, count in con.execute(
        "SELECT p.document_number, c.kind, COUNT(*) FROM contributions c JOIN protocols p ON p.id = c.protocol_id GROUP BY 1, 2"
    ):
        stored[number][kind] = count
    for table in ("speeches", "agenda_items", "withheld_units"):
        for number, count in con.execute(
            f"SELECT p.document_number, COUNT(*) FROM {table} t JOIN protocols p ON p.id = t.protocol_id GROUP BY 1"
        ):
            stored[number][table] = count
    votes = dict(con.execute("SELECT p.document_number, COUNT(*) FROM votes v JOIN protocols p ON p.id = v.protocol_id GROUP BY 1"))
    unlinked = dict(con.execute(
        "SELECT p.document_number, COUNT(*) FROM votes v JOIN protocols p ON p.id = v.protocol_id"
        " WHERE NOT EXISTS (SELECT 1 FROM agenda_item_votes a WHERE a.vote_id = v.id) GROUP BY 1"
    ))
    columns = (
        "sitzung datum teilausgabe endgueltig_am dip_zu_protokoll gespeichert_zu_protokoll fehlend_zu_protokoll "
        "dip_reden gespeichert_reden xml_letzte_rede dip_letzter_beitrag_gesprochen dip_reden_danach "
        "dip_zwischenfragen_kurzinterventionen_erwiderungen_danach dip_schriftl_par31 dip_vorgangspositionen_danach "
        "abstimmungen abstimmungen_ohne_top xml_sitzungsende"
    ).split()
    print("\t".join(columns))
    totals: dict[tuple[str, str], collections.Counter] = collections.defaultdict(collections.Counter)
    reports = [json.loads(path.read_text()) for path in data.glob("plenarprotokoll-*-*.json")]
    reports.sort(key=lambda r: [int(x) for x in r["protocol"]["dokumentnummer"].split("/")])
    for report in reports:
        number = report["protocol"]["dokumentnummer"]
        xml = (data / "xml" / f"plenarprotokoll-{number.replace('/', '-')}.xml").read_text()
        flat = re.sub(r"[­]", "", xml)
        notice = bool(NOTICE.search(flat))
        acts = report["api_records"]["aktivitaeten"]
        kinds = collections.Counter(a["aktivitaetsart"] for a in acts)
        cut = CUT_FROM_DIP.get(number) or xml_cut(xml)
        spoken = [(place(a["fundstelle"].get("seite")), a["aktivitaetsart"]) for a in acts if a["aktivitaetsart"] in SPOKEN]
        after = [kind for where, kind in spoken if cut[0] and where > cut]
        reden_after = after.count("Rede")
        last = max((where for where, _ in spoken), default=(0, ""))
        zp_missing = kinds[ZP] - stored[number]["zu_protokoll"]
        positions = {
            (p["id"])
            for p in report["api_records"]["vorgangspositionen"]
            if cut[0] and (p["fundstelle"].get("anfangsseite") or 0, p["fundstelle"].get("anfangsquadrant") or "") > cut
        }
        wp = number.split("/")[0]
        group = "first edition" if notice and (reden_after or zp_missing > 0) else "notice only" if notice else "other"
        total = totals[(group, wp)]
        total["sittings"] += 1
        total["dip_zp"] += kinds[ZP]
        total["stored_zp"] += stored[number]["zu_protokoll"]
        total["dip_reden"] += kinds["Rede"]
        total["stored_reden"] += stored[number]["speeches"]
        total["reden_after"] += reden_after
        total["turns_after"] += sum(kind in TURNS for kind in after)
        total["votes"] += votes.get(number, 0)
        total["unlinked"] += unlinked.get(number, 0)
        if not notice and reden_after:
            print(f"no notice, DIP Rede after the cut: {number} cut {cut} Reden {reden_after}", file=sys.stderr)
        if not cut[0]:
            print(f"no page in the Inhaltsverzeichnis: {number}", file=sys.stderr)
        if not (notice or zp_missing):
            continue
        end = re.findall(r'sitzung-ende-uhrzeit="([^"]*)"', xml)
        date = NOTICE_DATE.search(flat)
        print("\t".join(str(x) for x in (
            number, report["protocol"]["datum"], "ja" if notice else "nein",
            re.sub(r"\.(?=\S)", ". ", date[1]) if date else "", kinds[ZP], stored[number]["zu_protokoll"], zp_missing,
            kinds["Rede"], stored[number]["speeches"], f"{cut[0]}{cut[1]}", f"{last[0]}{last[1]}", reden_after,
            sum(kind in TURNS for kind in after), kinds["Schriftliche Erklärung gem. § 31 Geschäftsordnung BT"], len(positions),
            votes.get(number, 0), unlinked.get(number, 0), end[0] if end else "",
        )))
    for key in sorted(totals):
        print(key, dict(totals[key]), file=sys.stderr)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
