"""E1 of the withholding build (docs/plans/v1-scope-review.md, decision D8).

Fetch the Plenarprotokoll XML of the sittings on the exclusion list and run the
offline turn audit on it, before PR 2 is built. For each sitting it records
whether the parser refuses it for a reason withholding cannot narrow, or would
accept it once its located refusals are withheld, and how many words that
withholds (the Rede as it stands after split_nested_reden, decision D4).

Usage:
  python3 -I fetch_and_audit.py <repo_scripts_dir> <store_dir> <work_dir> [--no-fetch] [--only 18/1,19/25]

<repo_scripts_dir>  the parser to audit with; use the Reden fix's scripts/ once it has landed
<store_dir>         its data/coverage-exclusions.json names the sittings (the A3 store)
<work_dir>          the XML goes to <work_dir>/xml/, the result to <work_dir>/preflight.json

Fetching needs the network: one request per sitting to dserver.bundestag.de, no
DIP key, paced like a backfill (50 at 2 s, then a 60-minute pause). A rerun skips
XML already fetched. The audit's counts cannot certify a store; they size PR 2.
"""
import argparse
import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
cli.add_argument("scripts_dir", type=Path)
cli.add_argument("store_dir", type=Path)
cli.add_argument("work_dir", type=Path)
cli.add_argument("--no-fetch", action="store_true", help="audit only the XML already in <work_dir>/xml/")
cli.add_argument("--only", help="comma-separated document numbers instead of the whole exclusion list")
args = cli.parse_args()
sys.path.insert(0, str(args.scripts_dir.resolve()))

import audit_offline_turns  # noqa: E402
import publication_state as publication  # noqa: E402
import validate_dip_protocol as dip  # noqa: E402

WORD = re.compile(r"\S+")
MOVES_OUT = {"merged_rede", "merged_erwiderung"}


def words(paragraphs):
    return sum(len(WORD.findall(p)) for p in paragraphs)


def xml_url(number):
    wahlperiode, _, sitzung = number.partition("/")
    return f"https://dserver.bundestag.de/btp/{wahlperiode}/{wahlperiode}{int(sitzung):03d}.xml"


def xml_path(number):
    return args.work_dir / "xml" / f"plenarprotokoll-{number.replace('/', '-')}.xml"


def fetch(number, pacer):
    """Fetch and check one sitting's XML. Returns None, or why it failed."""
    try:
        url = publication.validate_external_url(xml_url(number), "bundestag-xml")
        text = pacer.fetch(url)
        root = dip.ET.fromstring(text)
        wahlperiode, _, sitzung = number.partition("/")
        found = (root.tag, root.attrib.get("wahlperiode"), root.attrib.get("sitzung-nr"))
        if found != ("dbtplenarprotokoll", wahlperiode, sitzung):
            return f"not the XML of {number}: root {found}"
    except (dip.DipError, dip.ET.ParseError, ValueError, publication.PublicationStateError) as exc:
        return str(exc)
    path = xml_path(number)
    path.parent.mkdir(parents=True, exist_ok=True)
    dip.write_text_atomic(path, text)
    return None


def edited_tree(source):
    """The Reden as the per-Rede loop sees them: role-less chairs marked, nested Reden split."""
    root = dip.ET.fromstring(source)
    dip.mark_roleless_chairs(root)
    for top in root.iter("tagesordnungspunkt"):
        dip.split_nested_reden(top)
    return root


def rede_words(rede):
    own, nested = dip.speech_segments(rede)
    return words(own.paragraphs) + sum(words(segment["paragraphs"]) for segment in nested)


def measure(number):
    path = xml_path(number)
    source = path.read_text(encoding="utf-8")
    root = edited_tree(source)
    total = sum(rede_words(rede) for rede in root.findall("./sitzungsverlauf//rede"))
    row = {"date": root.attrib.get("sitzung-datum"), "words_in_reden": total,
           "xml_sha256": dip.xml_source_sha256(source)}
    try:
        result = audit_offline_turns.audit(dip, path)
    except Exception as exc:  # noqa: BLE001 - every failure is a finding here
        return {**row, "status": "refused, not narrowable", "error": f"{type(exc).__name__}: {exc}"}
    withheld = {}
    for unit in result["unresolved"]:
        rid = unit["source_rede_id"]
        if rid in withheld:
            withheld[rid]["markers"].append(unit["marker_ordinal"])
            continue
        rede = root.find(f".//rede[@id='{rid}']")
        speaker = dip.parse_redner(rede.find("./p[@klasse='redner']/redner")) if rede is not None else None
        withheld[rid] = {"markers": [unit["marker_ordinal"]], "words": rede_words(rede) if rede is not None else None,
                         "speaker": (speaker or {}).get("display_name"), "fraktion": (speaker or {}).get("fraktion"),
                         "locator": unit["locator"]}
    moves = [d for d in result["diagnostics"] if d.get("source_rede_id") in withheld and d.get("treatment") in MOVES_OUT]
    withheld_words = sum(w["words"] or 0 for w in withheld.values())
    return {**row, "status": "parses once withheld" if withheld else "parses, no refusal",
            "withheld_reden": withheld, "withheld_words": withheld_words,
            "withheld_share": round(withheld_words / total, 4) if total else None,
            "moves_out_of_withheld": [{k: d.get(k) for k in ("source_rede_id", "treatment", "target_rede_id")} for d in moves],
            "counts": result["counts"]}


def summary(sittings):
    status = Counter(row["status"] for row in sittings.values())
    accepted = [row for row in sittings.values() if row["status"] == "parses once withheld"]
    by_year, by_fraktion = Counter(), Counter()
    for row in accepted:
        for rede in row["withheld_reden"].values():
            by_year[(row["date"] or "")[-4:]] += rede["words"] or 0
            by_fraktion[rede["fraktion"] or "(keine)"] += rede["words"] or 0
    shares = [row["withheld_share"] for row in accepted if row["withheld_share"] is not None]
    return {"status": dict(status),
            "withheld_reden": sum(len(row["withheld_reden"]) for row in accepted),
            "withheld_words": sum(row["withheld_words"] for row in accepted),
            "withheld_words_by_year": dict(sorted(by_year.items())),
            "withheld_words_by_fraktion": dict(by_fraktion.most_common()),
            "withheld_share_median": statistics.median(shares) if shares else None,
            "withheld_share_max": max(shares) if shares else None,
            "sittings_with_moves_out": sorted(n for n, row in sittings.items() if row.get("moves_out_of_withheld"))}


def main():
    if args.only:
        numbers = [n.strip() for n in args.only.split(",") if n.strip()]
    else:
        listed = json.loads((args.store_dir / "data" / "coverage-exclusions.json").read_text(encoding="utf-8"))
        numbers = [entry["document_number"] for entry in listed["exclusions"]]
    pacer = dip.XmlPacer()
    sittings = {}
    for index, number in enumerate(numbers, 1):
        print(f"[{index}/{len(numbers)}] {number}", file=sys.stderr, flush=True)
        if not xml_path(number).exists():
            failure = "not fetched (--no-fetch)" if args.no_fetch else fetch(number, pacer)
            if failure:
                sittings[number] = {"status": "fetch failed", "error": failure}
                continue
        sittings[number] = measure(number)
    parser = Path(dip.__file__)
    report = {"parser": str(parser), "parser_sha256": hashlib.sha256(parser.read_bytes()).hexdigest(),
              "speech_rule_version": dip.speech_kinds.VERSION,
              "summary": summary(sittings), "sittings": sittings}
    out = args.work_dir / "preflight.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"written: {out}", file=sys.stderr)


main()
