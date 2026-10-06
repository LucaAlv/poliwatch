"""Read-only cached-XML audit; rejected turns stay rejected in the real parser.

For counting comparisons only, blank each rejected segment in an in-memory XML
copy and continue, exposing later blockers. These partial counts cannot certify
or replace a report/database. --baseline-parser loads a local historical parser.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

import validate_dip_protocol as current


def audit(parser, path):
    source = path.read_text(encoding="utf-8")
    source_sha256 = current.xml_source_sha256(source)
    root = ET.fromstring(source)
    unresolved = []
    while True:
        try:
            parsed = parser.parse_protocol_xml(source)
            break
        except ValueError as exc:
            locator = re.search(r"at (\S+) marker (\d+)$", str(exc))
            if not locator:
                raise
            if any(u["locator"] == str(exc) for u in unresolved):
                raise RuntimeError(f"audit could not isolate {exc}") from exc
            rid, ordinal = locator.group(1), int(locator.group(2))
            rede = root.find(f".//rede[@id='{rid}']")
            segment = next(s for s in parser.speech_segments(rede)[1] if s["marker"] == ordinal)
            unresolved.append({"locator": str(exc), "source_rede_id": rid, "marker_ordinal": ordinal,
                               "speaker": segment["speaker"], "text": " ".join(segment["paragraphs"]),
                               "evidence": segment["announcement"]})
            marker = 0
            for child in list(rede):
                if child.tag == "p" and child.get("klasse") == "redner":
                    marker += 1
                    if marker == ordinal:
                        redner = child.find("redner")
                        if redner is not None:
                            redner.tail = (redner.tail or "").partition(":")[0] + ":"
                elif child.tag == "name" and marker == ordinal:
                    break
                elif child.tag == "p" and marker == ordinal:
                    rede.remove(child)
            source = ET.tostring(root, encoding="unicode")
    counts = Counter()
    turns = []
    diagnostics = []
    for top in parsed["agenda_items"]:
        counts["rede"] += len(top["speeches"])
        counts.update(c["kind"] for c in top["contributions"])
        diagnostics.extend(dict(top_id=top["top_id"], **d) for d in top.get("xml_turn_diagnostics", []))
        units = {u["rede_id"]: u for u in top["speeches"] + top["contributions"] if u["rede_id"]}
        for rede in root.findall("./sitzungsverlauf/tagesordnungspunkt/rede"):
            rid = rede.get("id")
            if rid not in units and not any(d["source_rede_id"] == rid for d in top.get("xml_turn_diagnostics", [])):
                continue
            for segment in parser.speech_segments(rede)[1]:
                key = f"nested:{rid}:{segment['marker']}"
                diagnostic = next((d for d in top.get("xml_turn_diagnostics", [])
                                   if d["source_rede_id"] == rid and d["marker_ordinal"] == segment["marker"]), None)
                owner = units.get(key) or (units.get(diagnostic.get("target_rede_id")) if diagnostic else None)
                text = " ".join(segment["paragraphs"])
                if diagnostic:
                    assert diagnostic["text"] == text, key
                if owner:
                    assert text in owner["text"], key
                    assert owner["speaker"]["xml_redner_id"] == segment["speaker"]["xml_redner_id"], key
                else:
                    assert diagnostic and diagnostic["treatment"] == "procedural", key
                turns.append({"source_rede_id": rid, "marker_ordinal": segment["marker"],
                              "speaker_id": segment["speaker"].get("xml_redner_id"),
                              "treatment": diagnostic["treatment"] if diagnostic else owner["kind"],
                              "target_rede_id": owner["rede_id"] if owner else None,
                              "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "char_count": len(text)})
    counts.update(c["kind"] for c in parsed.get("sitting_contributions", []))
    return {"source_sha256": source_sha256,
            "accepted": not unresolved, "counts": dict(sorted(counts.items())),
            "unresolved": unresolved, "turns": turns, "diagnostics": diagnostics}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("xml_dir", type=Path)
    cli.add_argument("--baseline-parser", type=Path)
    cli.add_argument("--baseline-speech-kinds", type=Path, help="Matching historical native-turn classifier")
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    if bool(args.baseline_parser) != bool(args.baseline_speech_kinds):
        cli.error("--baseline-parser and --baseline-speech-kinds must be supplied together")
    parser_sha256 = hashlib.sha256(Path(current.__file__).read_bytes()).hexdigest()
    speech_kinds_sha256 = hashlib.sha256(Path(current.speech_kinds.__file__).read_bytes()).hexdigest()
    baseline = None
    if args.baseline_parser:
        spec = importlib.util.spec_from_file_location("offline_baseline", args.baseline_parser)
        baseline = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = baseline
        spec.loader.exec_module(baseline)
        if args.baseline_speech_kinds:
            kind_spec = importlib.util.spec_from_file_location("offline_baseline_kinds", args.baseline_speech_kinds)
            baseline.speech_kinds = importlib.util.module_from_spec(kind_spec)
            sys.modules[kind_spec.name] = baseline.speech_kinds
            kind_spec.loader.exec_module(baseline.speech_kinds)
    sittings = {}
    for index, path in enumerate(sorted(args.xml_dir.glob("*.xml")), 1):
        print(f"[{index}] {path.stem}", file=sys.stderr, flush=True)
        result = audit(current, path)
        if baseline:
            old = audit(baseline, path)
            kinds = old["counts"].keys() | result["counts"].keys()
            result["count_changes"] = {k: result["counts"].get(k, 0) - old["counts"].get(k, 0)
                                       for k in sorted(kinds) if result["counts"].get(k, 0) != old["counts"].get(k, 0)}
            result["baseline_accepted"] = old["accepted"]
            result["baseline_unresolved"] = old["unresolved"]
        sittings[path.stem] = result
    counts = Counter()
    changes = Counter()
    for result in sittings.values():
        counts.update(result["counts"])
        changes.update(result.get("count_changes", {}))
    report = {"rule_version": current.speech_kinds.VERSION,
              "parser_sha256": parser_sha256,
              "baseline_parser_sha256": hashlib.sha256(args.baseline_parser.read_bytes()).hexdigest() if args.baseline_parser else None,
              "baseline_speech_kinds_sha256": hashlib.sha256(args.baseline_speech_kinds.read_bytes()).hexdigest() if args.baseline_speech_kinds else None,
              "speech_kinds_sha256": speech_kinds_sha256,
              "files": len(sittings),
              "accepted": sum(r["accepted"] for r in sittings.values()),
              "rejected": sum(not r["accepted"] for r in sittings.values()),
              "unresolved_markers": sum(len(r["unresolved"]) for r in sittings.values()),
              "baseline_rule_version": baseline.speech_kinds.VERSION if baseline else None,
              "baseline_accepted": sum(r["baseline_accepted"] for r in sittings.values()) if baseline else None,
              "baseline_rejected": sum(not r["baseline_accepted"] for r in sittings.values()) if baseline else None,
              "count_scope": "All files; unresolved segments omitted only from in-memory audit copies. Partial counts do not certify rejected sittings.",
              "counts": dict(sorted(counts.items())), "count_changes": dict(sorted(changes.items())), "sittings": sittings}
    assert hashlib.sha256(Path(current.speech_kinds.__file__).read_bytes()).hexdigest() == report["speech_kinds_sha256"], "classifier changed during audit; rerun"
    assert hashlib.sha256(Path(current.__file__).read_bytes()).hexdigest() == parser_sha256, "parser changed during audit; rerun"
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "sittings"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
