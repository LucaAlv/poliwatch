#!/usr/bin/env python3
"""Withhold one Rede per TOP and check that nothing else moves (D6, ADR 0005).

For every Plenarprotokoll XML given, this parses the sitting once as it is, then
again with one Rede per agenda item forced onto the reviewed list, for each of
three pick sets:

- ``middle``: the Rede in the middle of each TOP's stored Reden;
- ``exchange``: a Kurzintervention, and separately the Erwiderung that answers
  one, where a TOP has such a pair;
- ``resumed``: the Rede a resumed Rede gave its words back to, and separately
  the resumed Rede itself, where a TOP has one.

One parse withholds one Rede in every TOP at once: withholding writes no state
another TOP reads. Every other unit must come out unchanged: speeches and
Rede-based Beiträge by id, sequence, speaker, kind and text; nested and
Zu-Protokoll Beiträge by id, speaker, kind and text (their sequence may shift,
D3); Fragestunde turns whole; and the TOP's diagnostics except the withheld
Rede's own same-asker merges. The withheld Rede must be the one picked.

Usage:
  python3 scripts/check_withhold_one.py XML_DIR [--wahlperiode 18 --wahlperiode 19] [--output result.json]

Exit code 0 when every check passes, 1 otherwise. Run before shipping a change
to the parser; it takes minutes, not seconds, so it is not in the unit suite.
"""

from __future__ import annotations

if __name__ == "__main__":
    from python_version_guard import require_supported_python

    require_supported_python()

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import derive
import speech_kinds
import validate_dip_protocol as dip

PICK_SETS = ("middle", "exchange-kurzintervention", "exchange-erwiderung", "resumed-target", "resumed")


def _speaker_key(speaker: dict[str, Any] | None) -> tuple[Any, ...]:
    speaker = speaker or {}
    return (speaker.get("xml_redner_id"), speaker.get("display_name"), speaker.get("fraktion"), speaker.get("role"))


def _rede_units(top: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The TOP's units that stand for a whole <rede>: speeches and Rede-based Beiträge."""
    units = {s["rede_id"]: s for s in top["speeches"]}
    for c in top["contributions"]:
        if c.get("rede_id") and not str(c["rede_id"]).startswith("nested:") and c["kind"] != speech_kinds.ZU_PROTOKOLL:
            units[c["rede_id"]] = c
    return units


def picks(top: dict[str, Any], pick_set: str) -> str | None:
    """The rede id to withhold in this TOP for one pick set, or None."""
    speeches = sorted(top["speeches"], key=lambda s: s["sequence"])
    contributions = [c for c in top["contributions"] if c.get("rede_id") and not str(c["rede_id"]).startswith("nested:")]
    if pick_set == "middle":
        return speeches[len(speeches) // 2]["rede_id"] if speeches else None
    if pick_set == "exchange-kurzintervention":
        return next((c["rede_id"] for c in contributions if c["kind"] == speech_kinds.KURZINTERVENTION), None)
    if pick_set == "exchange-erwiderung":
        return next((c["rede_id"] for c in contributions if c["kind"] == speech_kinds.ERWIDERUNG), None)
    resumed = [d for d in top["xml_turn_diagnostics"] if d["treatment"] == "merged_rede"]
    if pick_set == "resumed-target":
        return resumed[0]["target_rede_id"] if resumed else None
    if pick_set == "resumed":
        return resumed[0]["source_rede_id"] if resumed else None
    raise ValueError(pick_set)


def _owner(xml_root, base_top: dict[str, Any], rid: str) -> str | None:
    """The first Redner-ID of the picked Rede's owner: from its stored unit, or
    for a Rede stored as no unit (a resumed one) from the source <rede>."""
    unit = _rede_units(base_top).get(rid)
    if unit is not None:
        return derive.first_redner_id((unit.get("speaker") or {}).get("xml_redner_id"))
    rede = next((r for r in xml_root.iter("rede") if r.get("id") == rid), None)
    redner = rede.find("./p[@klasse='redner']/redner") if rede is not None else None
    return derive.first_redner_id(redner.get("id")) if redner is not None else None


def compare(base: dict[str, Any], forced: dict[str, Any], withheld: dict[int, str]) -> list[str]:
    """Every difference between the two parses that withholding ``withheld``
    (TOP index -> rede id) does not explain. Empty when the check passes."""
    problems = []
    forced_tops = {top["index"]: top for top in forced["agenda_items"]}
    if len(forced_tops) != len(base["agenda_items"]):
        return [f"TOP count {len(base['agenda_items'])} -> {len(forced_tops)}"]
    for top in base["agenda_items"]:
        index, label = top["index"], top["top_id"]
        other = forced_tops[index]
        rid = withheld.get(index)
        got = [w["rede_id"] for w in other["withheld"]]
        if got != ([rid] if rid else []):
            problems.append(f"{label}: withheld {got}, picked {rid}")
        before, after = _rede_units(top), _rede_units(other)
        expected = {key: unit for key, unit in before.items() if key != rid}
        for key in sorted(set(expected) | set(after)):
            a, b = expected.get(key), after.get(key)
            if a is None or b is None:
                problems.append(f"{label} {key}: {'appeared' if a is None else 'vanished'}")
                continue
            for field in ("sequence", "kind", "text", "parent_rede_id"):
                if a.get(field) != b.get(field):
                    problems.append(f"{label} {key}: {field} changed")
            if _speaker_key(a.get("speaker")) != _speaker_key(b.get("speaker")):
                problems.append(f"{label} {key}: speaker changed")
        nested_before = {c["rede_id"]: c for c in top["contributions"]
                         if str(c.get("rede_id") or "").startswith("nested:") or c["kind"] == speech_kinds.ZU_PROTOKOLL}
        nested_after = {c["rede_id"]: c for c in other["contributions"]
                        if str(c.get("rede_id") or "").startswith("nested:") or c["kind"] == speech_kinds.ZU_PROTOKOLL}
        nested_expected = {key: unit for key, unit in nested_before.items() if not (rid and unit.get("parent_rede_id") == rid
                                                                                  and str(key).startswith("nested:"))}
        if set(nested_expected) != set(nested_after):
            problems.append(f"{label}: nested/Zu-Protokoll ids {sorted(set(nested_expected) ^ set(nested_after))[:5]} differ")
        for key in set(nested_expected) & set(nested_after):
            a, b = nested_expected[key], nested_after[key]
            if (a["kind"], a["text"], _speaker_key(a.get("speaker"))) != (b["kind"], b["text"], _speaker_key(b.get("speaker"))):
                problems.append(f"{label} {key}: nested unit changed")
        turns_before = [c for c in top["contributions"] if c.get("rede_id") is None]
        turns_after = [c for c in other["contributions"] if c.get("rede_id") is None]
        if turns_before != turns_after:
            problems.append(f"{label}: Fragestunde turns changed")
        diagnostics_expected = [d for d in top["xml_turn_diagnostics"]
                                if not (d["source_rede_id"] == rid and d["treatment"] == "merged_zwischenfrage")]
        if diagnostics_expected != other["xml_turn_diagnostics"]:
            problems.append(f"{label}: diagnostics changed")
    if base.get("sitting_contributions") != forced.get("sitting_contributions"):
        problems.append("sitting-level Zu-Protokoll Beiträge changed")
    return problems


def check_sitting(xml_text: str) -> dict[str, Any]:
    """All pick sets for one sitting: {pick set: {"withheld": n, "problems": [...]}}."""
    root = dip.ET.fromstring(xml_text)
    sitting = f"{root.get('wahlperiode')}/{root.get('sitzung-nr')}"
    base = dip.parse_protocol_xml(xml_text, reviewed=[])
    result = {}
    for pick_set in PICK_SETS:
        chosen = {top["index"]: picks(top, pick_set) for top in base["agenda_items"]}
        chosen = {index: rid for index, rid in chosen.items() if rid}
        if not chosen:
            continue
        tops = {top["index"]: top for top in base["agenda_items"]}
        entries = [{"sitting": sitting, "rede_id": rid, "redner_id": _owner(root, tops[index], rid), "kind": "withhold",
                    "reason": f"check_withhold_one {pick_set}"} for index, rid in chosen.items()]
        try:
            forced = dip.parse_protocol_xml(xml_text, reviewed=entries)
        except Exception as exc:  # a crash is a failed check, reported with the sitting
            result[pick_set] = {"withheld": len(chosen), "problems": [f"parse failed: {type(exc).__name__}: {exc}"]}
            continue
        result[pick_set] = {"withheld": len(chosen), "problems": compare(base, forced, chosen)}
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xml_dir", type=Path)
    parser.add_argument("--wahlperiode", action="append", default=[], help="only these Wahlperioden (repeatable)")
    parser.add_argument("--output", type=Path, help="write the full result as JSON")
    args = parser.parse_args(argv)
    paths = sorted(args.xml_dir.glob("plenarprotokoll-*.xml"))
    if args.wahlperiode:
        paths = [p for p in paths if p.stem.split("-")[1] in set(args.wahlperiode)]
    results, failed, totals = {}, 0, {name: 0 for name in PICK_SETS}
    for path in paths:
        try:
            outcome = check_sitting(path.read_text(encoding="utf-8"))
        except Exception as exc:
            outcome = {"base": {"withheld": 0, "problems": [f"base parse failed: {type(exc).__name__}: {exc}"]}}
        results[path.name] = outcome
        for name, row in outcome.items():
            totals[name] = totals.get(name, 0) + row["withheld"]
            if row["problems"]:
                failed += 1
                print(f"{path.name} {name}: {row['problems'][:3]}", file=sys.stderr)
    summary = {"sittings": len(paths), "withheld_per_pick_set": totals, "failed_checks": failed}
    print(json.dumps(summary, ensure_ascii=False))
    if args.output:
        args.output.write_text(json.dumps({"summary": summary, "sittings": results}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
