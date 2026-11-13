"""E1 of the withholding build (docs/plans/v1-scope-review.md, decision D8).

Fetch the Plenarprotokoll XML of the sittings on the exclusion list and run the
offline turn audit on it, before PR 2 is built. For each sitting it records
whether the parser refuses it for a reason withholding cannot narrow, or would
accept it once its located refusals are withheld, and how many words that
withholds (the Rede as it stands after split_nested_reden, decision D4).

Usage:
  python3 -I fetch_and_audit.py <repo_scripts_dir> <store_dir> <work_dir> [--no-fetch]
                                [--only 18/1,19/25 | --only-file sittings.txt]

<repo_scripts_dir>  the parser to audit with; use the Reden fix's scripts/ once it has landed
<store_dir>         its data/coverage-exclusions.json names the sittings (the A3 store); not read with --only/--only-file
<work_dir>          the XML goes to <work_dir>/xml/, the result to <work_dir>/preflight.json

Each sitting gets a refusal_class from a fixed map, and its located refusals are
compared with a3-wp18-19-round2-blockers.tsv (the round 2 audit's list).

Fetching needs the network: one request per sitting to dserver.bundestag.de, no
DIP key, paced like a backfill (50 at 2 s, then a 60-minute pause). A rerun skips
XML already fetched. The audit's counts cannot certify a store; they size PR 2.
"""
import argparse
import csv
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
cli.add_argument("--only-file", type=Path, help="a file with one document number (WP/NR) per line, instead of --only")
args = cli.parse_args()
if args.only_file and not args.only_file.is_file():
    cli.error(f"--only-file {args.only_file}: no such file")
sys.path.insert(0, str(args.scripts_dir.resolve()))

import audit_offline_turns  # noqa: E402
import publication_state as publication  # noqa: E402
import validate_dip_protocol as dip  # noqa: E402

WORD = re.compile(r"\S+")
MOVES_OUT = {"merged_rede", "merged_erwiderung"}
LOCATED = re.compile(r"at (\S+) marker (\d+)$")  # audit()'s own test for a refusal it can withhold
REFUSAL_CLASSES = [  # (text in the error, class); the first match wins
    ("audit could not isolate", "other"),
    ("unresolved nested question-format speaker at", "located_nested_question_speaker"),
    ("unresolved nested contribution at", "located_nested_contribution"),
    ("unresolved Befragung turn", "befragung"),
    ("unresolved Fragestunde marker", "fragestunde_marker"),
    ("conflicting roles at redner", "conflicting_roles"),
    ("nested contribution needs a source rede id", "nested_needs_source_id"),
    ("stands outside any TOP", "outside_top"),
]
BLOCKERS = Path(__file__).resolve().parent.parent / "a3-wp18-19-round2-blockers.tsv"
FLAGGED = {  # listed, but in no group of the T3 review's finding 8 (a3-wp18-19-round2-result.md:211)
    number: "not in the blockers file: its role conflict was fixed in round 2, then it refused at a turn "
            "(\"unresolved nested contribution\") and stayed listed"
    for number in ("18/124", "18/173")}


def refusal_class(error):
    return next((cls for text, cls in REFUSAL_CLASSES if text in error), "other")


class Recorder:
    """dip as audit() uses it, keeping each located refusal it meets: audit() drops
    its list when an unnarrowable refusal follows, and the report keeps it."""

    def __init__(self):
        self.located = []

    def __getattr__(self, name):
        return getattr(dip, name)

    def parse_protocol_xml(self, source):
        try:
            return dip.parse_protocol_xml(source)
        except ValueError as exc:
            if LOCATED.search(str(exc)) and str(exc) not in self.located:
                self.located.append(str(exc))
            raise


def read_blockers():
    """The round 2 audit's located refusals, per sitting, as "<rede id> marker <n>"."""
    expected = {}
    with BLOCKERS.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            expected.setdefault(row["sitting"].replace("-", "/"), []).append(f"{row['rede']} marker {row['marker']}")
    return expected


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


def edit_tree(root):
    """The Reden as the per-Rede loop sees them, in parse_protocol_xml's order: Reden
    outside a TOP adopted, role-less chairs marked, nested Reden split. Can refuse
    the whole sitting ("outside any TOP", "conflicting roles")."""
    dip.adopt_reden_outside_tops(root)
    dip.mark_roleless_chairs(root)
    for top in root.iter("tagesordnungspunkt"):
        dip.split_nested_reden(top)


def rede_words(rede):
    own, nested = dip.speech_segments(rede)
    return words(own.paragraphs) + sum(words(segment["paragraphs"]) for segment in nested)


def withheld_reden(root, located):
    """The Reden of the edited tree that hold the located refusals, with their words."""
    withheld = {}
    for locator in located:
        rid, ordinal = LOCATED.search(locator).group(1), int(LOCATED.search(locator).group(2))
        if rid in withheld:
            withheld[rid]["markers"].append(ordinal)
            continue
        rede = root.find(f".//rede[@id='{rid}']")
        speaker = dip.parse_redner(rede.find("./p[@klasse='redner']/redner")) if rede is not None else None
        withheld[rid] = {"markers": [ordinal], "words": rede_words(rede) if rede is not None else None,
                         "speaker": (speaker or {}).get("display_name"), "fraktion": (speaker or {}).get("fraktion"),
                         "refusal_class": refusal_class(locator), "locator": locator}
    return withheld


def compare(withheld, expected):
    """Located refusals found here against those the blockers file lists for the sitting."""
    found = [f"{rid} marker {m}" for rid, rede in withheld.items() for m in rede["markers"]]
    return {"expected": len(expected), "found": len(found),
            "missing": [b for b in expected if b not in found], "not_listed": [b for b in found if b not in expected]}


def measure(number, expected):
    path = xml_path(number)
    source = path.read_text(encoding="utf-8")
    root = dip.ET.fromstring(source)
    row = {"date": root.attrib.get("sitzung-datum"), "words_in_reden": None,
           "xml_sha256": dip.xml_source_sha256(source)}
    if number in FLAGGED:
        row["flag"] = FLAGGED[number]
    recorder = Recorder()
    try:
        edit_tree(root)  # inside the try: a sitting-wide refusal is a finding, not the end of the run
        row["words_in_reden"] = sum(rede_words(rede) for rede in root.findall("./sitzungsverlauf//rede"))
        result = audit_offline_turns.audit(recorder, path)
    except Exception as exc:  # noqa: BLE001 - every failure is a finding here
        error = f"{type(exc).__name__}: {exc}"
        withheld = withheld_reden(root, recorder.located)
        return {**row, "status": "refused, not narrowable", "refusal_class": refusal_class(error), "error": error,
                "located_before_refusal": withheld, "blockers": compare(withheld, expected)}
    withheld = withheld_reden(root, [unit["locator"] for unit in result["unresolved"]])
    classes = {rede["refusal_class"] for rede in withheld.values()}
    moves = [d for d in result["diagnostics"] if d.get("source_rede_id") in withheld and d.get("treatment") in MOVES_OUT]
    withheld_words = sum(w["words"] or 0 for w in withheld.values())
    total = row["words_in_reden"]
    return {**row, "status": "parses once withheld" if withheld else "parses, no refusal",
            "refusal_class": min(classes) if classes else None,  # located_nested_contribution when both occur
            "withheld_reden": withheld, "withheld_words": withheld_words,
            "withheld_share": round(withheld_words / total, 4) if total else None,
            "moves_out_of_withheld": [{k: d.get(k) for k in ("source_rede_id", "treatment", "target_rede_id")} for d in moves],
            "blockers": compare(withheld, expected), "counts": result["counts"]}


def blockers_file(blockers):
    """The file's own counts. A Rede id under two sittings is counted twice by (sitting, rede)."""
    pairs = {(number, b.partition(" ")[0]) for number, listed in blockers.items() for b in listed}
    sittings_of = Counter(rid for _number, rid in pairs)
    return {"rows": sum(len(listed) for listed in blockers.values()), "sittings": len(blockers),
            "sitting_rede_pairs": len(pairs), "distinct_rede_ids": len(sittings_of),
            "rede_ids_under_two_sittings": sorted(rid for rid, n in sittings_of.items() if n > 1)}


def summary(sittings, blockers):
    status = Counter(row["status"] for row in sittings.values())
    accepted = [row for row in sittings.values() if row["status"] == "parses once withheld"]
    by_year, by_fraktion, markers_by_class = Counter(), Counter(), Counter()
    for row in accepted:
        for rede in row["withheld_reden"].values():
            by_year[(row["date"] or "")[-4:]] += rede["words"] or 0
            by_fraktion[rede["fraktion"] or "(keine)"] += rede["words"] or 0
    for row in sittings.values():
        for rede in {**row.get("withheld_reden", {}), **row.get("located_before_refusal", {})}.values():
            markers_by_class[rede["refusal_class"]] += len(rede["markers"])
    listed = [n for n in sittings if n in blockers]
    shares = [row["withheld_share"] for row in accepted if row["withheld_share"] is not None]
    return {"status": dict(status),
            "refusal_class": dict(Counter(row["refusal_class"] for row in sittings.values() if row.get("refusal_class")).most_common()),
            "located_markers_by_class": dict(markers_by_class.most_common()),
            "blockers_file": blockers_file(blockers),
            "blockers_listed_sittings": len(listed),
            "blockers_listed_parse_once_withheld": sum(sittings[n]["status"] == "parses once withheld" for n in listed),
            "blockers_listed_exact_match": sorted(n for n in listed if sittings[n]["status"] == "parses once withheld"
                                                  and not sittings[n]["blockers"]["missing"] and not sittings[n]["blockers"]["not_listed"]),
            "blockers_listed_differ": {n: {k: sittings[n].get(k) for k in ("status", "refusal_class", "blockers")} for n in listed
                                       if sittings[n]["status"] != "parses once withheld"
                                       or sittings[n]["blockers"]["missing"] or sittings[n]["blockers"]["not_listed"]},
            "flagged": {n: {k: sittings[n].get(k) for k in ("status", "refusal_class", "error")} for n in FLAGGED if n in sittings},
            "words_in_reden_parse_once_withheld": sum(row["words_in_reden"] for row in accepted),
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
    elif args.only_file:
        numbers = [n.strip() for n in args.only_file.read_text(encoding="utf-8").splitlines() if n.strip()]
    else:
        listed = json.loads((args.store_dir / "data" / "coverage-exclusions.json").read_text(encoding="utf-8"))
        numbers = [entry["document_number"] for entry in listed["exclusions"]]
    blockers = read_blockers()
    pacer = dip.XmlPacer()
    sittings = {}
    for index, number in enumerate(numbers, 1):
        print(f"[{index}/{len(numbers)}] {number}", file=sys.stderr, flush=True)
        if not xml_path(number).exists():
            failure = "not fetched (--no-fetch)" if args.no_fetch else fetch(number, pacer)
            if failure:
                sittings[number] = {"status": "fetch failed", "refusal_class": "fetch_rejected", "error": failure,
                                    "blockers": compare({}, blockers.get(number, []))}
                continue
        sittings[number] = measure(number, blockers.get(number, []))
    parser = Path(dip.__file__)
    report = {"parser": str(parser), "parser_sha256": hashlib.sha256(parser.read_bytes()).hexdigest(),
              "speech_rule_version": dip.speech_kinds.VERSION,
              "summary": summary(sittings, blockers), "sittings": sittings}
    out = args.work_dir / "preflight.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"written: {out}", file=sys.stderr)


main()
