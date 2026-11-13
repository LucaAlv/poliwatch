"""ADR 0004 census: join the raw scan with the reviewed decisions.

Scratch tooling, not shipped. Reads the raw JSON ``census.py`` wrote and
writes:
  docs/plans/adr-0004-census.tsv                 every candidate row with its proposed kind
  docs/plans/adr-0004-reviewed-units.draft.json  the draft of scripts/reviewed_units.json
                                                 (moved there by the code PR)

Each proposed kind comes from a rule below or from an explicit entry in
DECISIONS, which records what the reviewer read. A row no rule or entry
covers is written as UNREVIEWED and makes the script exit 1.

Usage: python3 review.py raw.json
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
# The P4/P5 detector predicates exactly as the plan states them (P4, P5). They
# find candidates; a candidate leaves the counts only through a list entry, and an
# unlisted candidate refuses (located). No prompt test: the census showed the
# chair's question printed in too many shapes ("Nehmen Sie die Wahl an, Frau
# Kollegin?", "ob er die Wahl annimmt", inside the previous Redner's text).
OATH_TEXT = re.compile(r"\b[Ii]ch schwöre\b")
OATH_CAP = 400
# "sie" lower-case only: "Ich nehme an, dass Sie …" (18/90) is no acceptance.
ACCEPT_TEXT = re.compile(r"\b[Nn]ehme\b[^.!?]{0,40}\b(?:[Ww]ahl|sie)\b[^.!?]{0,30}\ban\b")
ACCEPT_PROMPT = re.compile(r"Wahl an(?:zunehmen)?\b[^.!?]{0,30}\?|die Wahl annehmen|Wahl annimmt|Amt anzunehmen", re.IGNORECASE)
ELECTION_HEADING = re.compile(r"Wahl de[rs]|Wahl eine[rs]", re.IGNORECASE)
ACCEPT_CAP = 200


def p5(text, prompt, heading):
    return len(text) <= OATH_CAP and bool(OATH_TEXT.search(text))


def p4(text, prompt, heading):
    # A bare "Ja." needs the chair's question or an election heading; it is too
    # common a word to be a candidate on its own.
    if re.fullmatch(r"Ja\.", text):
        return bool(ACCEPT_PROMPT.search(prompt) or ELECTION_HEADING.search(heading))
    return len(text) <= ACCEPT_CAP and bool(ACCEPT_TEXT.search(text))

# (sitting, rede_id, marker or None) -> (kind, hard, reason). The reason names
# what was read; "hard" rows go to the owner with the options in the plan.
DECISIONS: dict[tuple[str, str, int | None], tuple[str, bool, str]] = {
    # --- presidium-owned <rede>s without a Fraktion, or Präsident ---
    ("18/178", "ID1817804400", None): ("ansprache", False,
        "Lammert opens the vereinbarte Debatte on the 75th anniversary of the invasion of the Soviet Union with "
        "Gedenkworte on behalf of the Bundestag; no floor-giving in the turn. Role printed as rolle_lang "
        "'Präsident Dr. Norbert Lammert', which SITZUNGSLEITUNG_ROLE does not fullmatch: P2 must test the role "
        "by prefix or the entry must carry it"),
    ("18/223", "ID1822300100", None): ("ansprache", False,
        "Lammert opens the joint sitting of Bundestag and Bundesrat (Bundespräsident's oath): welcome, address on "
        "Gauck's term, then gives the floor to Dreyer in the last sentence. Address with one chair sentence (O2 grain)"),
    ("18/223", "ID1822300200", None): ("ansprache", False,
        "Malu Dreyer, Präsidentin des Bundesrates: address at the joint sitting; guest role, not an MdB"),
    ("18/223", "ID1822300300", None): ("ansprache", False,
        "Joachim Gauck, Bundespräsident a. D.: farewell address at the joint sitting; guest, not an MdB"),
    ("18/223", "ID1822300400", None): ("ansprache", False,
        "Frank-Walter Steinmeier, Bundespräsident: address after taking the oath at the joint sitting; "
        "the oath formula is part of the address text (P5 leaves it inside)"),
    ("18/193", "ID1819300700", None): ("ansprache", False,
        "Lammert's farewell to Peer Steinbrück on behalf of the Bundestag, ending with the floor to the next "
        "Redner (one chair sentence, O2 grain). Not in the plan's list: new case (18/193 is excluded for an "
        "unrelated refusal)"),
    ("18/215", "ID1821504000", None): ("ansprache", False,
        "Bulmahn (Vizepräsidentin, no Fraktion printed) thanks Außenminister Steinmeier after his last speech, "
        "on behalf of the Bundestag. The plan's '18/215 presidium owner marker'"),
    ("18/173", "ID1817301900", None): ("ansprache", True,
        "Lammert's statement opening the Armenia resolution debate: welcomes the Armenian and Turkish embassies, "
        "states the Bundestag's position on threats against MdBs, then opens the Aussprache. An address on "
        "behalf of the Bundestag inside a debate item, with political content and chair text. Options: "
        "ansprache (proposed) / sitzungsleitung. New case, not in the plan (18/173 is excluded for an unrelated refusal)"),
    # --- the seven sittings waiting on this item: 18/245, 19/1, 19/9, 19/19, 19/73 (18/178, 18/223 above) ---
    ("18/245", "ID1824501400", None): ("ansprache", False,
        "Bulmahn (Vizepräsidentin, no Fraktion) asks to say a few words in her last sitting: farewell address "
        "(5,226 characters), ending with one chair sentence giving the floor to Barley (O2 grain)"),
    ("18/245", "ID1824502300", None): ("ansprache", True,
        "Singhammer (Vizepräsident, no Fraktion): reopens the sitting and announces the result of the "
        "Verfassungsrichter election (about 600 characters of Sitzungsleitung), then the closing address of the "
        "18th Wahlperiode (names the deceased members, thanks, 'Möge Gott unser Vaterland behüten') and closes the "
        "sitting. The plan proposed Sitzungsleitung; the larger part is an address on behalf of the Bundestag. "
        "Options: ansprache (proposed) / sitzungsleitung; no figure moves either way"),
    ("19/1", "ID19100100", None): ("sitzungsleitung", False,
        "Solms (Alterspräsident): welcome, the GO rule for the constituent sitting, the vote on the AfD's motion "
        "19/2, the seniority check, then calls TOP 1. Chair work; the plan's guess 'opening address' does not hold"),
    ("19/1", "ID19100200", None): ("sitzungsleitung", True,
        "An empty <rede> (the Alterspräsident's marker, no paragraph). Solms's opening address follows as loose "
        "<p> elements directly under the TOP (about 14,000 characters: welcome of the Bundespräsident, the "
        "Schriftführer, then the address), which the parser reads as chair text. Counted today as a Rede of "
        "0 characters. Options: sitzungsleitung for the empty <rede> and the address stays unshown (proposed, a "
        "display gap like WP 20/21's constituent addresses) / a new tree rule that adopts the loose paragraphs "
        "into an Ansprache (O7)"),
    ("19/1", "ID19101000", None): ("sitzungsleitung", False,
        "Solms: 'Der Kollege Dr. Wolfgang Schäuble ist vorgeschlagen. – Ich darf Sie fragen: Sind Sie bereit, zu kandidieren?'"),
    ("19/1", "ID19100900", None): ("nomination", True,
        "Kauder nominates Schäuble for Präsident (71 characters). Options as 20/1 ID20100700"),
    ("19/1", "ID19101100", None): ("procedural", False,
        "Schäuble's 'Ja, Herr Präsident.' answering 'Sind Sie bereit, zu kandidieren?': the candidate's consent, "
        "part of the election procedure like the acceptance. No P4 text test reads it, so a list entry"),
    ("19/1", "ID19101200", None): ("sitzungsleitung", False,
        "Solms: the election procedure (3,007 characters of voting instructions), the result, Schäuble's nested "
        "acceptance (marker 2, procedural by 6d), congratulations and the hand-over"),
    ("19/1", "ID19101300", None): ("ansprache", True,
        "Schäuble's inaugural address as Präsident (15,343 characters). Ansprache is clear; hard because the "
        "<redner id> printed on it is 11002190, Solms's id, not Schäuble's 11001938 (the name says Schäuble): the "
        "list's redner_id proof would bind the Ansprache to Solms. Options: entry with redner_id 11002190 and a "
        "person_corrections.json fix of the binding (proposed) / correct the id in the entry, which the P1 check "
        "would then refuse as a mismatch"),
    ("19/1", "ID19101900", None): ("sitzungsleitung", True,
        "Schäuble chairs the third ballot of the Vizepräsidenten election (result, procedure). Sitzungsleitung is "
        "clear; hard only because it carries Solms's redner id 11002190 like ID19101300 (no unit is stored, so "
        "nothing is bound)"),
    ("19/9", "ID19900100", None): ("ansprache", False,
        "Schäuble opens the joint debate with the Assemblée nationale on 55 years of the Élysée Treaty: address "
        "to both parliaments. Role printed 'Präsident Dr. Wolfgang Schäuble' (name in the role, as 18/178)"),
    ("19/9", "ID19900200", None): ("ansprache", False,
        "François de Rugy, Präsident der Assemblée nationale: guest address, not an MdB"),
    ("19/19", "ID191900100", None): ("sitzungsleitung", False,
        "Schäuble reopens the sitting and announces the result of the chancellor election"),
    ("19/19", "ID191900300", None): ("sitzungsleitung", False,
        "Schäuble reads the Bundespräsident's letter appointing Merkel and calls her to take the oath"),
    ("19/19", "ID191900500", None): ("sitzungsleitung", False,
        "Schäuble reads the Bundespräsident's letter on the formation of the government (TOP 'Bekanntgabe der "
        "Bildung der Bundesregierung'): an official communication in exercise of the chair"),
    ("19/19", "ID191900600", None): ("sitzungsleitung", False,
        "Schäuble reads the oath formula and calls the Minister one by one"),
    ("19/73", "ID197300100", None): ("ansprache", False,
        "Schäuble opens the first sitting of 2019 with a statement on the attack on Frank Magnitz and on "
        "violence and language in politics, on behalf of the Bundestag (4,616 characters), ending with a birthday "
        "greeting. Role printed 'Präsident Dr. Wolfgang Schäuble'"),
    # --- nested presidium turns longer than 600 characters (group 3) ---
    ("18/113", "ID1811302500", 3): ("deferred", True,
        "Pau, printed Vizepräsidentin, speaks 1,897 characters as the Antrag's author inside another Redner's "
        "<rede> (a debate contribution, not chair text). 6d reads every nested presidium marker as Sitzungsleitung, "
        "so it is dropped. Same class as 18/96 and 18/109 (plan, Deferred): needs its own rule; 18/113 is excluded "
        "for an unrelated refusal (TOP 32 recipients)"),
    # --- 18/1 acceptances no rule reads ---
    ("18/1", "ID1800100600", None): ("procedural", True,
        "Hintze's own <rede>: 'Ich bedanke mich. Ich nehme die Wahl an.' followed by the chair's announcement of "
        "Singhammer's result and the acceptance question, printed under Hintze with no <name> chair element "
        "(source misattribution: Lammert chairs, ID1800100700 follows with Singhammer's acceptance). Options: "
        "list as procedural with the chair text dropped (proposed; check the PDF page) / split at the chair sentence"),
    ("18/1", "ID1800101100", None): ("procedural", False,
        "Claudia Roth answers Lammert's 'ob Sie sich ernsthaft entschließen könnten, dieses Amt anzunehmen' with "
        "'Ich freue mich, Ihnen antworten zu dürfen ...': an acceptance without the words, so a list entry"),
    # --- discovery rows (wording or prompt in turns up to 3,000 characters) that are Reden ---
    ("20/44", "ID204406300", None): ("unchanged", False,
        "Brandner's GO statement on the AfD's Wahlvorschlag (603 characters): a contribution, not a nomination"),
    ("20/57", "ID205707100", None): ("unchanged", False, "debate Rede quoting the Amtseid (2,962 characters)"),
    ("20/131", "ID2013115000", None): ("unchanged", False, "debate Rede quoting the soldiers' oath (2,750 characters)"),
    ("21/52", "ID215212900", None): ("unchanged", False, "Erwiderung ending 'Ich schwöre.' as an expression (1,129 characters, over the cap)"),
    ("21/62", "ID216212100", None): ("unchanged", False, "debate Rede opening with the soldiers' oath (2,607 characters)"),
    ("18/90", "ID1809000900", None): ("unchanged", False,
        "Steinmeier in the Fragestunde: 'Ich nehme an, dass Sie …' is no acceptance (18/90 is excluded)"),
    # --- false positives of the loose group-4 scan ---
    ("20/154", "ID2015403800", None): ("unchanged", False,
        "Kurzintervention: 'ich nehme an, Sie haben ...' is not an election acceptance"),
    # --- nominations (Wahlvorschläge) printed as <rede>: outside ADR 0004, hard ---
    ("20/1", "ID20100700", None): ("nomination", True,
        "Mützenich nominates Bärbel Bas for Präsidentin (99 characters). Counted today as an SPD Rede. Not a "
        "presidium turn, acceptance or oath: options keep as Rede (status quo) / procedural like the acceptance"),
    ("21/1", "ID21101200", None): ("nomination", True,
        "Merz nominates Julia Klöckner for Präsidentin (179 characters). Counted today as a CDU/CSU Rede. Options "
        "as 20/1 ID20100700"),
    ("18/1", "ID1800100100", None): ("nomination", True,
        "Kauder nominates Lammert for Präsident (125 characters); 18/1 is excluded. Options as 20/1 ID20100700"),
}


# The plan's P4/P5 regexes as written (full match of the turn), to measure their recall.
NESTED_P4 = re.compile(r"(?:(?:Herr|Frau) (?:Alters)?[Pp]räsident(?:in)?(?:, [^.!?]{1,60})?, )?[Ii]ch nehme die Wahl (?:sehr )?(?:gerne? )?an\.")
PLAN_P4 = re.compile(r"(?:(?:Herr|Frau) (?:Alters)?Präsident(?:in)?(?:, [^.!?]{1,60})?, )?[Ii]ch nehme die Wahl (?:sehr )?(?:gerne )?an\.")
PLAN_P5 = re.compile(r"(?:Ja, )?Ich schwöre es(?:, so wahr mir Gott helfe)?\.")


def classify(r):
    key = (r["sitting"], r["rede_id"], r["marker"])
    if key in DECISIONS:
        kind, hard, reason = DECISIONS[key]
        return kind, "reviewed entry", hard, reason
    groups = set(r["groups"])
    text = r.get("own_text") or r.get("text") or ""
    prompt = r.get("prompt") or ""
    heading = r.get("top_heading") or ""
    if "1" in groups and r.get("vize_fraktion_rule"):
        unit = (r.get("parser_today") or {}).get("unit") or "unit of a refused sitting"
        return ("fraktionsrede", "existing rule mark_presidium_fraktionsreden (round 2 decision 2)", False,
                f"Vizepräsident(in) printed with a Fraktion; today {unit}; reviewed in round 2 result-vp-owned.tsv")
    if p5(text, prompt, heading):
        return ("procedural", "P5 oath answer", False,
                "the sworn person's answer to the chair's oath prompt" + (" (full Art. 56 formula)" if "Wohle des deutschen Volkes" in text else ""))
    if r["marker"] and NESTED_P4.fullmatch(text):
        # The nested form stays 6d's owner-approved full match, widened by the
        # salutation clause, "gerne" and the lower-case p of "Alterspräsident".
        return ("procedural", "6d nested acceptance (widened)", False, "nested acceptance after the chair's question; no list entry")
    if p4(text, prompt, heading):
        return ("procedural", "P4 election acceptance", False,
                ("'Ja.' answering 'Nehmen Sie die Wahl an?'" if text == "Ja." else "acceptance of an election just announced")
                + (" (nested)" if r["marker"] else " (<rede> form)"))
    if "6" in groups:
        unit = (r.get("parser_today") or {}).get("unit")
        return ("unchanged", "group 6 listing", False, f"nested turn of another speaker; parser today: {unit}")
    if "7" in groups and "1" not in groups:
        return ("unchanged", "group 7 review", False,
                "role-less chair speaking as an MdB: debate contribution (salutation and debate content), counts for the Fraktion")
    if groups <= {"5"}:
        return ("unchanged", "group 5 listing", False, "debate or GO Rede in a ceremony item")
    return ("UNREVIEWED", "", True, "")


def main():
    raw = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out_rows = []
    entries = []
    unreviewed = 0
    for r in raw["rows"]:
        if "groups" not in r:
            continue
        kind, rule, hard, reason = classify(r)
        unreviewed += kind == "UNREVIEWED"
        pt = r.get("parser_today") or {}
        st = r.get("store_today") or {}
        text = r.get("own_text") or r.get("text") or ""
        out_rows.append({
            "sitting": r["sitting"], "stored": "kept" if r["stored"] else "excluded",
            "groups": ",".join(r["groups"]), "rede_id": r["rede_id"], "marker": r["marker"] or "",
            "redner_id": r.get("redner_id") or "", "speaker": r.get("speaker") or "",
            "role": r.get("role_before_mark") or r.get("role") or "", "fraktion": r.get("fraktion") or "",
            "chars": len(text), "top_id": r.get("top_id") or "",
            "parser_today": pt.get("unit") or ("sitting refused" if r.get("parser_error") else ""),
            "store_today": (f"{st['table']}" + (f"/{st['kind']}" if st.get("kind") else "") +
                            (f"/{st['sprechrolle']}" if st.get("sprechrolle") else "")) if st else "",
            "proposed_kind": kind, "rule": rule, "hard": "yes" if hard else "",
            "reason": reason, "first_200": text[:200].replace("\t", " "),
            "top_heading": (r.get("top_heading") or "")[:120].replace("\t", " "),
            "prompt_tail": (r.get("prompt") or "")[-160:].replace("\t", " "),
        })
        # Every unit that leaves the counts is a list entry (P1, revised P4/P5): the
        # detector only finds candidates, the list decides. Hard rows wait in the
        # TSV for the owner; the draft holds the proposed kind with the loader's keys only.
        if kind in ("ansprache", "sitzungsleitung", "procedural") and not rule.startswith("6d"):
            entry = {"sitting": r["sitting"], "rede_id": r["rede_id"]}
            if r["marker"]:
                entry["marker"] = r["marker"]
            entry.update({"redner_id": r.get("redner_id"), "kind": kind, "reason": reason.split(". ")[0]})
            entries.append(entry)
    def order(row):
        wp, nr = row["sitting"].split("/")
        return (int(wp), int(nr), row["rede_id"], int(row["marker"] or 0))
    out_rows.sort(key=order)
    entries.sort(key=lambda e: (*map(int, e["sitting"].split("/")), e["rede_id"], e.get("marker", 0)))
    tsv = ROOT / "docs" / "plans" / "adr-0004-census.tsv"
    with tsv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(out_rows[0]), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)
    draft = ROOT / "docs" / "plans" / "adr-0004-reviewed-units.draft.json"
    draft.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(out_rows)} rows, {len(entries)} list entries, {unreviewed} unreviewed")
    for rule, pattern in (("P4 election acceptance", PLAN_P4), ("P5 oath answer", PLAN_P5)):
        hits = [r for r in raw["rows"] if "groups" in r and classify(r)[1] == rule]
        full = [r for r in hits if pattern.fullmatch(r.get("own_text") or r.get("text") or "")]
        print(f"plan regex for {rule}: full-matches {len(full)} of {len(hits)} census turns")
    for row in out_rows:
        if row["proposed_kind"] == "UNREVIEWED":
            print("UNREVIEWED", row["sitting"], row["rede_id"], row["marker"], row["speaker"], row["role"], row["first_200"][:100])
    return 1 if unreviewed else 0


if __name__ == "__main__":
    sys.exit(main())
