"""ADR 0004 census (plan docs/plans/adr-0004-presidium-kinds.md, step 0/1).

Scratch tooling, not shipped. Read-only: scans cached Plenarprotokoll XML,
runs the current parser (``parse_protocol_xml``) on each file to record what
it does today, and reads the reference store read-only to record what is
stored. Writes one raw JSON of candidate rows; ``review.py`` joins it with
the reviewed decisions.

Usage (Python 3.11+):
  python3 census.py --store-dir <.context/dip-pulse-site> --extra-xml-dir <W1 xml dir> --out raw.json
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import derive  # noqa: E402
import speech_kinds  # noqa: E402
import validate_dip_protocol as v  # noqa: E402

# Group 4: an oath answer or an election acceptance, any wording, in a short turn.
OATH = re.compile(r"\bschwöre\b", re.IGNORECASE)
ACCEPT = re.compile(r"\bnehme\b[^.!?]{0,40}\b(?:Wahl|sie)\b[^.!?]{0,30}\ban\b|\bWahl\b[^.!?]{0,20}\bnehme ich\b[^.!?]{0,20}\ban\b", re.IGNORECASE)
# Discovery is wider than any rule: wording or prompt, in turns up to 3,000
# characters (outside-voice finding: the scan must not share the rules' caps).
SHORT_TURN = 3000
# ... or any short turn right after the chair asks for the acceptance, the oath or a nomination.
PROMPT = re.compile(r"Wahl an(?:zunehmen)?\?|die Wahl annehmen|Nehmen Sie die Wahl|Wahl annimmt|Amt anzunehmen|\bEid\b|schwören|Vorschläge zur Wahl|um Vorschläge|Wahlvorschl", re.IGNORECASE)
# Group 5: WP 20/21 constituent, chancellor-election and swearing-in items.
CEREMONY_TOP = re.compile(
    r"Wahl de[rs] (?:Bundeskanzler|Präsident|Vizepräsident|Stellvertreter)|Eidesleistung|Vereidigung|Konstituierung|"
    r"Wahl des Wehrbeauftragten|Wahl de[rs] Polizeibeauftragten|^\s*Gedenk|Gedenkstunde|Gedenkworte|^\s*Ansprache|^\s*Begrüßung|Erklärung des Präsidenten|Erklärung der Präsidentin",
    re.IGNORECASE)
NESTED_ADDRESS_CHARS = 600


def norm_role(text: str | None) -> str:
    return re.sub(r"\s+", "", text or "")


def turns_of(rede: ET.Element):
    """Raw turns of one <rede>: (marker ordinal or None for chair <name>, redner element, text)."""
    turns = []
    current = None
    marker = 0
    for child in rede:
        if child.tag == "name":
            current = {"marker": None, "redner": None, "chair_name": v.elem_text(child), "parts": []}
            turns.append(current)
            continue
        if child.tag != "p":
            continue
        if child.get("klasse") == "redner":
            marker += 1
            redner = child.find("redner")
            current = {"marker": marker, "redner": redner, "chair_name": None,
                       "parts": [v.clean_text(((redner.tail if redner is not None else "") or "").partition(":")[2])]}
            turns.append(current)
            continue
        if current is not None:
            current["parts"].append(v.elem_text(child))
    for turn in turns:
        turn["text"] = v.clean_text(" ".join(p for p in turn["parts"] if p))
    return turns


def speaker_fields(redner):
    if redner is None:
        return {}
    parsed = v.parse_redner(redner) or {}
    try:
        role = speech_kinds.effective_role(redner)[0]
    except ValueError as exc:
        role = f"<role conflict: {exc}>"
    return {"redner_id": derive.first_redner_id(redner.get("id")), "speaker": parsed.get("display_name"),
            "role": role, "fraktion": parsed.get("fraktion"),
            "sitzungsleitung_attr": redner.get("sitzungsleitung") == "1"}


def today_outcomes(xml_text: str):
    """What the current parser makes of each unit: rede id -> outcome, nested id -> outcome."""
    try:
        report = v.parse_protocol_xml(xml_text)
    except Exception as exc:  # noqa: BLE001 - recorded, not handled
        return None, f"{type(exc).__name__}: {exc}"
    out = {}
    for item in report["agenda_items"]:
        for s in item["speeches"]:
            out[s["rede_id"]] = {"unit": "Rede", "chars": s["char_count"], "top": item["top_id"]}
        for c in item["contributions"]:
            if c.get("rede_id"):
                out[c["rede_id"]] = {"unit": c["kind"], "chars": c["char_count"], "top": item["top_id"],
                                     "parent": c.get("parent_rede_id")}
        for d in item["xml_turn_diagnostics"]:
            key = f"diag:{d['source_rede_id']}:{d['marker_ordinal']}"
            out[key] = {"unit": d["treatment"], "evidence": (d.get("evidence") or "")[:160], "top": item["top_id"]}
    return out, None


def store_outcomes(conn, number: str):
    out = {}
    for rid, mp, fr, sr, chars in conn.execute(
            "select s.rede_id, m.display_name, s.fraktion, s.sprechrolle, s.char_count from speeches s "
            "join protocols p on p.id = s.protocol_id left join mps m on m.id = s.mp_id where p.document_number = ?", (number,)):
        out[rid] = {"table": "speeches", "fraktion": fr, "sprechrolle": sr, "chars": chars}
    for rid, kind, fr, sr, chars in conn.execute(
            "select c.rede_id, c.kind, c.fraktion, c.sprechrolle, c.char_count from contributions c "
            "join protocols p on p.id = c.protocol_id where p.document_number = ? and c.rede_id is not null", (number,)):
        out[rid] = {"table": "contributions", "kind": kind, "fraktion": fr, "sprechrolle": sr, "chars": chars}
    return out


def scan(path: Path, stored: bool, conn):
    xml_text = path.read_text(encoding="utf-8")
    root = ET.fromstring(xml_text)
    sitting = f"{root.get('wahlperiode')}/{root.get('sitzung-nr')}"
    wp = int(root.get("wahlperiode"))
    rows = []
    try:
        v.adopt_reden_outside_tops(root)
    except ValueError as exc:
        rows.append({"sitting": sitting, "group": "error", "note": f"adopt: {exc}"})
    before = copy.deepcopy(root)
    v.mark_presidium_fraktionsreden(root)
    v.mark_roleless_chairs(root)
    verlauf = root.find("sitzungsverlauf")
    before_by_id = {}
    for rede in before.iter("rede"):
        before_by_id.setdefault(rede.get("id"), []).append(rede)
    ids = [r.get("id") for r in verlauf.iter("rede")] if verlauf is not None else []
    duplicate_ids = {i for i in ids if ids.count(i) > 1}
    chairs = [v.elem_text(n) for n in verlauf.iter("name") if n.find("nachname") is None] if verlauf is not None else []
    tops = {}
    prompts = {}
    if verlauf is not None:
        for top in verlauf.findall("tagesordnungspunkt"):
            heading = " ".join(v.elem_text(p) for p in top.findall("p") if (p.get("klasse") or "").startswith("T_"))
            for rede in top.iter("rede"):
                tops[id(rede)] = (top.get("top-id"), heading)
            # The chair text right before each <rede>: trailing chair turns of the
            # previous <rede> plus loose paragraphs between them.
            last_chair = ""
            for child in top:
                if child.tag == "p" and not (child.get("klasse") or "").startswith("T_"):
                    last_chair += " " + v.elem_text(child)
                elif child.tag == "rede":
                    prompts[id(child)] = v.clean_text(last_chair)[-300:]
                    trailing = []
                    for t in turns_of(child):
                        is_chair = t["marker"] is None or (t["marker"] > 1 and v.presidium_marker(t["redner"]))
                        trailing = trailing + [t["text"]] if is_chair else []
                    last_chair = " ".join(trailing)
    annex_presidium = []
    in_verlauf = {id(r) for r in verlauf.iter("rede")} if verlauf is not None else set()
    for rede in root.iter("rede"):
        if id(rede) in in_verlauf:
            continue
        first = rede.find("./p[@klasse='redner']/redner")
        if first is not None and v.SITZUNGSLEITUNG_ROLE.fullmatch(norm_role(speaker_fields(first).get("role"))):
            annex_presidium.append(rede.get("id"))
    today, error = today_outcomes(xml_text)
    store = store_outcomes(conn, sitting) if stored and conn is not None else {}

    def base(rede, turn, groups, extra=None):
        rid = rede.get("id")
        sp = speaker_fields(turn["redner"]) if turn else {}
        top_id, heading = tops.get(id(rede), (None, ""))
        key = rid if (turn is None or turn["marker"] in (None, 1)) else f"diag:{rid}:{turn['marker']}"
        row = {"sitting": sitting, "stored": stored, "groups": groups, "rede_id": rid,
               "marker": None if turn is None or turn["marker"] == 1 else turn["marker"],
               "top_id": top_id, "top_heading": heading[:160], **sp,
               "chars": len(turn["text"]) if turn else None,
               "text": turn["text"] if turn else "",
               "duplicate_id": rid in duplicate_ids,
               "prompt": prompts.get(id(rede), "") if (turn is None or turn["marker"] in (None, 1)) else None,
               "parser_today": (today or {}).get(key) or ((today or {}).get(f"nested:{rid}:{turn['marker']}") if turn and turn["marker"] else None)
               or ((today or {}).get(f"{rid}:{turn['marker']}") if turn and turn["marker"] else None),
               "parser_error": error,
               "store_today": store.get(rid) if (turn is None or turn["marker"] in (None, 1)) else
               (store.get(f"nested:{rid}:{turn['marker']}") or store.get(f"{rid}:{turn['marker']}"))}
        if extra:
            row.update(extra)
        return row

    for rede in (verlauf.iter("rede") if verlauf is not None else []):
        rid = rede.get("id")
        turns = turns_of(rede)
        owner_turns = [t for t in turns if t["marker"] is not None]
        if not owner_turns:
            continue
        owner = owner_turns[0]["redner"]
        own_key = v.redner_key(owner)
        sp_after = speaker_fields(owner)
        orig = before_by_id.get(rid, [None])[0]
        sp_before = speaker_fields(orig.find("./p[@klasse='redner']/redner")) if orig is not None else sp_after
        role_before = sp_before.get("role")
        own_text = v.clean_text(" ".join(t["text"] for t in turns if t["marker"] is not None and v.redner_key(t["redner"]) == own_key))
        groups = []
        presidium = bool(v.SITZUNGSLEITUNG_ROLE.fullmatch(norm_role(role_before)))
        if presidium:
            groups.append("1")
        elif role_before and derive.side_of_role(role_before) is None:
            groups.append("2")
        if not sp_after.get("role") and not sp_after.get("fraktion"):
            groups.append("8")  # owner with neither role nor Fraktion
        roleless_chair = False
        if not sp_after.get("role") and owner.find("name") is not None:
            full = v.clean_text(f"{v.child_text(owner.find('name'), 'vorname') or ''} {v.child_text(owner.find('name'), 'nachname') or ''}")
            roleless_chair = bool(full) and any(re.search(rf"(?<![\w-]){re.escape(full)}\s*:?$", c) for c in chairs)
            if roleless_chair:
                groups.append("7")
        top_id, heading = tops.get(id(rede), (None, ""))
        if (wp >= 20 and root.get("sitzung-nr") == "1") or CEREMONY_TOP.search(heading or ""):
            groups.append("5")
        short_own = len(own_text) <= SHORT_TURN
        if short_own and (OATH.search(own_text) or ACCEPT.search(own_text) or PROMPT.search(prompts.get(id(rede), "")[-300:])):
            groups.append("4")
        if groups:
            row = base(rede, owner_turns[0], groups, {
                "role_before_mark": role_before, "vize_fraktion_rule": presidium and not sp_after.get("role"),
                "own_chars": len(own_text), "own_text": own_text, "turn_count": len(turns)})
            rows.append(row)
        # Nested turns.
        previous_chair = ""
        for t in turns:
            if t["marker"] is None or (t["marker"] > 1 and v.presidium_marker(t["redner"])):
                chair_before, previous_chair = previous_chair, t["text"]
            else:
                chair_before, previous_chair = previous_chair, ""
            if t["marker"] is None or t["marker"] == 1:
                continue
            key = v.redner_key(t["redner"])
            if key == own_key:
                continue
            ngroups = []
            pres = v.presidium_marker(t["redner"])
            if pres and len(t["text"]) > NESTED_ADDRESS_CHARS:
                ngroups.append("3")
            if not pres and len(t["text"]) <= SHORT_TURN and (
                    OATH.search(t["text"]) or ACCEPT.search(t["text"]) or PROMPT.search(chair_before[-300:])):
                ngroups.append("4")
            if not pres and any(g in groups for g in ("1", "2", "7")):
                ngroups.append("6")
            if ngroups:
                rows.append(base(rede, t, ngroups, {"nested_presidium": pres, "prompt": chair_before[-300:]}))
    return sitting, rows, error, annex_presidium


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store-dir", type=Path, required=True)
    ap.add_argument("--extra-xml-dir", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    db = args.store_dir / "data" / "bundestag-pulse.sqlite"
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    stored_numbers = {n for (n,) in conn.execute("select document_number from protocols")}
    files = {}
    for path in sorted((args.store_dir / "data" / "xml").glob("plenarprotokoll-*.xml")):
        files[path.stem.removeprefix("plenarprotokoll-").replace("-", "/")] = path
    extra = {}
    if args.extra_xml_dir:
        for path in sorted(args.extra_xml_dir.glob("plenarprotokoll-*.xml")):
            number = path.stem.removeprefix("plenarprotokoll-").replace("-", "/")
            if number not in files:
                extra[number] = path
    result = {"stored_sittings": len(stored_numbers), "store_xml": len(files), "extra_xml": sorted(extra),
              "sittings": {}, "rows": []}
    for number, path in [*files.items(), *extra.items()]:
        sitting, rows, error, annex = scan(path, number in stored_numbers, conn)
        result["sittings"][sitting] = {"stored": number in stored_numbers, "parse_error": error,
                                       "annex_presidium_reden": annex, "xml": str(path)}
        result["rows"].extend(rows)
        print(f"{sitting}: {len(rows)} rows{' (parse error)' if error else ''}", file=sys.stderr)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
