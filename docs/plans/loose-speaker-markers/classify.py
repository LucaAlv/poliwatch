"""Add the proposed kind and attachment to each row of census.py's TSV
(docs/plans/loose-speaker-markers.md, section 2).

usage: python -I docs/plans/loose-speaker-markers/classify.py <census.tsv> <out.tsv>

The table below is the review: one line per marker, read from the XML on
2026-11-22. ``attach`` says where the marker's turn goes:
- ``wrap``: into the Rede that a ``rede`` marker of the same run opens
  (the ``rede`` marker itself and the later turns inside that Rede);
- ``prev`` / ``next``: into the ``<rede>`` just before or after the run;
- ``none``: into no unit (procedural, Sitzungsleitung, remark).
"""
import csv
import sys

KINDS = {
    # sitting, marker: (kind, attach, note)
    ("18/2", "M1"): ("rede", "wrap", "asks for the floor for an Erklärung nach § 31 at the end of the sitting"),
    ("18/2", "M2"): ("own_words", "wrap", "the Erklärung nach § 31"),
    ("18/6", "M1"): ("rede", "wrap", "first Rede of the debate"),
    ("18/6", "M2"): ("rede", "wrap", ""),
    ("18/6", "M3"): ("rede", "wrap", ""),
    ("18/7", "M159"): ("rede", "wrap", "opens the Aktuelle Stunde"),
    ("18/10", "M1"): ("rede", "wrap", "first Rede of the debate"),
    ("18/10", "M2"): ("own_words", "wrap", "consents to Ströbele's Zwischenfrage"),
    ("18/10", "M3"): ("zwischenfrage", "wrap", ""),
    ("18/10", "M4"): ("own_words", "wrap", "answers the Zwischenfrage"),
    ("18/10", "M5"): ("own_words", "wrap", "continues after a chair remark"),
    ("18/10", "M6"): ("rede", "wrap", "after Neu's Rede (name_rede N39)"),
    ("18/23", "M1"): ("rede", "wrap", "Erklärung nach § 31"),
    ("18/23", "M2"): ("rede", "wrap", "Erklärung nach § 31 Abs. 1"),
    ("18/23", "M3"): ("rede", "wrap", "Erklärung zur Abstimmung nach § 31 Abs. 1"),
    ("18/23", "M4"): ("rede", "wrap", "persönliche Erklärung in the same series"),
    ("18/26", "M1"): ("rede", "wrap", "first Rede of the debate"),
    ("18/26", "M2"): ("rede", "wrap", "first Rede of the debate"),
    ("18/26", "M3"): ("rede", "wrap", "first Rede of the debate"),
    ("18/26", "M4"): ("own_words", "wrap", "continues after a chair remark"),
    ("18/33", "M1"): ("rede", "wrap", "the minister opens the debate"),
    ("18/74", "M1"): ("rede", "wrap", "first Rede of the debate"),
    ("18/76", "M1"): ("procedural", "none", "accepts the election as Wehrbeauftragter"),
    ("18/83", "M1"): ("rede", "wrap", "first Rede of the debate"),
    ("18/83", "M2"): ("rede", "wrap", "after Müller's Rede (name_rede N54)"),
    ("18/83", "M3"): ("rede", "wrap", "first Rede of the debate"),
    ("18/83", "M4"): ("rede", "wrap", ""),
    ("18/83", "M5"): ("own_words", "wrap", "consents to Lay's Zwischenfrage"),
    ("18/83", "M6"): ("zwischenfrage", "wrap", ""),
    ("18/83", "M7"): ("own_words", "wrap", "answers the Zwischenfrage"),
    ("18/91", "M1"): ("rede", "wrap", "Erklärung nach § 31"),
    ("18/91", "M2"): ("own_words", "wrap", "continues after a chair remark"),
    ("18/115", "M1"): ("rede", "wrap", "Berichterstatterin of the Petitionsausschuss"),
    ("18/115", "M2"): ("rede", "wrap", "mündliche Erklärung nach § 31"),
    ("19/14", "M1"): ("sitzungsleitung", "none", "the chair printed as a speaker marker"),
    ("19/62", "M1"): ("own_words", "prev", "continues his Rede after a chair remark"),
    ("19/114", "M1"): ("own_words", "next", "accepts the offer of a Nachfrage"),
    ("19/114", "M2"): ("own_words", "next", "accepts the chair's apology"),
    ("19/114", "M3"): ("own_words", "next", "remark before his Zusatzfrage"),
    ("19/114", "M4"): ("befragung_antwort", "next", "the minister's reply to that remark"),
    ("19/114", "M5"): ("own_words", "prev", "thanks after his own Frage"),
    ("19/114", "M6"): ("own_words", "next", "accepts the floor"),
    ("19/114", "M7"): ("remark", "none", "asks for a Zusatzfrage; the Frage is M8 (changed in the build from befragung_frage, which counted the request as a Frage of its own)"),
    ("19/114", "M8"): ("befragung_frage", "prev", "the Zusatzfrage"),
    ("19/114", "M9"): ("own_words", "prev", "the minister answers"),
    ("19/114", "M10"): ("remark", "none", "accepts the offer of a Zusatzfrage; the Frage is M11 (changed in the build from befragung_frage, as M7)"),
    ("19/114", "M11"): ("befragung_frage", "prev", "the Zusatzfrage"),
    ("19/114", "M12"): ("own_words", "prev", "the minister answers"),
    ("19/114", "M13"): ("own_words", "prev", "thanks the chair"),
    ("19/114", "M14"): ("befragung_frage", "prev", "the Zusatzfrage"),
    ("19/114", "M15"): ("own_words", "prev", "the minister answers"),
    ("19/114", "M16"): ("befragung_frage", "prev", "reply to the answer"),
    ("19/114", "M17"): ("remark", "none", "declines a Nachfrage: \"Nein.\""),
    ("19/114", "M18"): ("own_words", "next", "announces her Nachfrage"),
    ("19/201", "M1"): ("befragung_antwort", "prev", "the chancellor's reply after Rüthrich's Frage"),
    ("19/233", "M1"): ("own_words", "next", "starts before the chair's remark; her Rede follows"),
    ("20/9", "M1"): ("own_words", "next", "asks to make his Kurzintervention"),
    ("20/17", "M1"): ("own_words", "next", "asks for the floor; her Kurzintervention follows"),
    ("20/17", "M2"): ("own_words", "next", ""),
    ("20/44", "M1"): ("own_words", "next", "announces his Geschäftsordnungsantrag"),
    ("20/79", "M1"): ("procedural", "none", "thanks after the oath"),
    ("20/94", "M1"): ("own_words", "next", "\"Genau.\" before his Rede"),
    ("20/94", "M2"): ("own_words", "next", ""),
    ("20/97", "M1"): ("own_words", "next", "\"Das Wasser fehlt.\" before his Rede"),
    ("20/97", "M2"): ("own_words", "next", "opening words before the chair's remark"),
    ("20/106", "M1"): ("own_words", "next", "remark before his Rede"),
    ("20/115", "M1"): ("own_words", "next", "his Rede's first sentence, before the chair's remark"),
    ("20/115", "M2"): ("own_words", "next", ""),
    ("20/124", "M61"): ("own_words", "next", "remark before her Rede"),
    ("20/136", "M60"): ("own_words", "next", "remark before her Rede"),
    ("20/169", "M1"): ("own_words", "next", "remark before his Berichterstattung"),
    ("20/197", "M1"): ("procedural", "none", "thanks after the oath"),
    ("21/24", "M1"): ("own_words", "next", "accepts the floor for his Erwiderung"),
    ("21/27", "M1"): ("own_words", "next", "remark before his Rede"),
}


def main() -> None:
    with open(sys.argv[1], encoding="utf-8") as source:
        rows = list(csv.DictReader(source, delimiter="\t"))
    keys = {(row["sitting"], row["marker"]) for row in rows}
    if keys != set(KINDS):
        sys.exit(f"census and table differ: only census {sorted(keys - set(KINDS))}, only table {sorted(set(KINDS) - keys)}")
    for row in rows:
        row["kind"], row["attach"], row["note"] = KINDS[(row["sitting"], row["marker"])]
    fields = list(rows[0])
    with open(sys.argv[2], "w", newline="", encoding="utf-8") as out:
        writer = csv.DictWriter(out, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    summary: dict[str, list[int]] = {}
    for row in rows:
        entry = summary.setdefault(row["kind"], [0, 0])
        entry[0] += 1
        entry[1] += int(row["words"])
    for kind, (markers, words) in sorted(summary.items(), key=lambda item: -item[1][1]):
        print(f"{kind:18} {markers:3} markers {words:6} words")


if __name__ == "__main__":
    main()
