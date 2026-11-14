#!/usr/bin/env python3
"""Write the vote-link review sheet (docs/plans/vote-links-and-figures.md, "The review").

    python3 scripts/vote_link_review.py --output-dir .context/dip-pulse-site \\
        --out docs/plans/vote-links-review.tsv

Read-only: it opens the store of a site directory with ``mode=ro`` and reads the
cached reports and Plenarprotokoll XML beside it. It writes one TSV row per
sampled link of ``agenda_item_votes`` with every column filled in but the
verdict columns (``verdict``, ``pattern``, ``action``, ``evidence``,
``reviewer``), which the review fills.

The sample:

- S1: every link of a vote linked to two or more TOPs;
- S2: every link of a TOP linked to two or more votes;
- S3: every title link (``basis = title``);
- S4: plain links (one vote, one TOP) resting on a Drucksache, drawn with
  ``--seed``: ``--sample-vorgang`` of the ``drucksache_vorgang`` ones and
  ``--sample-xml`` of the ``drucksache_xml`` ones.

A row's key is ``(vote_id, protocol, top_id, top_occurrence)``: ``top_occurrence``
counts the TOPs of the sitting with the same ``top_id`` up to this one, in item
order (21/24 has "Tagesordnungspunkt I" twice). ``item_index`` is informative
only, since a re-parse that adds a TOP renumbers the items.

Exit codes: 0 written, 2 an input is missing or malformed.
"""

from __future__ import annotations

if __name__ == "__main__":
    from python_version_guard import require_supported_python

    require_supported_python()

import argparse
import csv
import io
import json
import random
import re
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import persist_dip_pulse_store as pulse_store
from stable_ids import source_index

STORE = Path("data") / "bundestag-pulse.sqlite"
COLUMNS = (
    "stratum", "protocol", "date", "vote_id", "vote_title", "item_index", "top_id", "top_occurrence", "top_heading",
    "basis", "shared", "announced", "tally", "other_tops", "verdict", "pattern", "action", "evidence", "reviewer",
)
#: How much of a TOP heading the sheet shows.
HEADING_CHARS = 120
#: How far before a tally the announcement's Drucksachen are read.
ANNOUNCEMENT_CHARS = 800
#: A Drucksache number of WP 10 to 99, as the chair reads it out.
_DRUCKSACHE_RE = re.compile(r"\b[1-9][0-9]/[0-9]{1,6}\b")


class ReviewInputError(Exception):
    """An input the sheet cannot be built from; the message says which."""


def slug(document_number: str) -> str:
    return document_number.replace("/", "-")


def tally_pattern(yes: int, no: int) -> re.Pattern[str]:
    """The chair's announcement of exactly this Ja/Nein tally ("mit Ja haben
    gestimmt 380, mit Nein haben gestimmt 270"; "davon ja: 380, nein: 270").
    The gaps are bounded, so a long run of text or digits costs linear time."""
    return re.compile(
        rf"\bja\b[^0-9]{{0,60}}(?<![0-9]){yes}(?![0-9])[^0-9]{{0,120}}\bnein\b[^0-9]{{0,60}}(?<![0-9]){no}(?![0-9])",
        re.I,
    )


def find_tally(text: str, yes: Any, no: Any) -> tuple[str, list[str]]:
    """``(unique|several|none, Drucksachen announced)`` for one vote: whether its
    exact tally occurs once in the sitting's text, and for a unique one the
    Drucksache numbers in the ``ANNOUNCEMENT_CHARS`` before it and in it."""
    if not isinstance(yes, int) or not isinstance(no, int) or isinstance(yes, bool) or isinstance(no, bool):
        return "none", []
    matches = list(tally_pattern(yes, no).finditer(text))
    if not matches:
        return "none", []
    if len(matches) > 1:
        return "several", []
    match = matches[0]
    window = text[max(0, match.start() - ANNOUNCEMENT_CHARS):match.end()]
    return "unique", list(dict.fromkeys(_DRUCKSACHE_RE.findall(window)))


def protocol_text(path: Path) -> str:
    """The whole text of a cached Plenarprotokoll XML, whitespace collapsed; ""
    without a file."""
    if not path.is_file():
        return ""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ReviewInputError(f"{path} is not well-formed XML: {exc}") from exc
    return " ".join(" ".join(root.itertext()).split())


def stored_links(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Every row of ``agenda_item_votes`` with its sitting, TOP and vote."""
    rows = conn.execute(
        "SELECT p.document_number, v.date, v.id AS vote_id, v.title, v.yes_count, v.no_count, ai.id AS agenda_item_id, "
        "ai.item_index, ai.top_id, ai.heading, aiv.basis FROM agenda_item_votes aiv "
        "JOIN agenda_items ai ON ai.id = aiv.agenda_item_id JOIN votes v ON v.id = aiv.vote_id "
        "JOIN protocols p ON p.id = ai.protocol_id"
    ).fetchall()
    seen: Counter[tuple[str, str]] = Counter()
    occurrence: dict[str, int] = {}
    for item_id, protocol_id, top_id in conn.execute(
        "SELECT id, protocol_id, top_id FROM agenda_items ORDER BY protocol_id, item_index"
    ):
        seen[(protocol_id, top_id)] += 1
        occurrence[item_id] = seen[(protocol_id, top_id)]
    numbers: dict[str, list[str]] = {}
    for vote_id, number in conn.execute(
        "SELECT vd.vote_id, d.document_number FROM vote_documents vd JOIN documents d ON d.id = vd.document_id ORDER BY vd.rank"
    ):
        numbers.setdefault(vote_id, []).append(number)
    return [{**dict(row), "top_occurrence": occurrence[row["agenda_item_id"]],
             "vote_numbers": numbers.get(row["vote_id"], [])} for row in rows]


def _sort_key(link: Mapping[str, Any]) -> tuple:
    wp, _, number = str(link["document_number"]).partition("/")
    vote_id = str(link["vote_id"])
    return (int(wp) if wp.isdigit() else 0, int(number) if number.isdigit() else 0,
            (int(vote_id), "") if vote_id.isdigit() else (-1, vote_id), link["item_index"])


def strata(links: list[dict[str, Any]], seed: int, sample_vorgang: int, sample_xml: int) -> dict[int, list[str]]:
    """Row position in ``links`` -> its strata."""
    per_vote = Counter(link["vote_id"] for link in links)
    per_top = Counter(link["agenda_item_id"] for link in links)
    chosen: dict[int, list[str]] = {}
    plain: dict[str, list[int]] = {"drucksache_vorgang": [], "drucksache_xml": []}
    for position, link in enumerate(links):
        marks = []
        if per_vote[link["vote_id"]] > 1:
            marks.append("S1")
        if per_top[link["agenda_item_id"]] > 1:
            marks.append("S2")
        if link["basis"] == "title":
            marks.append("S3")
        if marks:
            chosen[position] = marks
        elif link["basis"] in plain:
            plain[link["basis"]].append(position)
    rng = random.Random(seed)
    for basis, size in (("drucksache_vorgang", sample_vorgang), ("drucksache_xml", sample_xml)):
        pool = plain[basis]
        if size > len(pool):
            raise ReviewInputError(f"--sample-{basis.split('_')[1]} {size} exceeds the {len(pool)} plain {basis} links")
        for position in rng.sample(pool, size):
            chosen[position] = ["S4"]
    return chosen


def shared_documents(link: Mapping[str, Any], item: Mapping[str, Any] | None) -> str:
    """The vote's Drucksachen the TOP holds, as ``number:type:Vorgang id``
    (``xml`` and ``-`` for a number only the protocol prints)."""
    if item is None:
        return "?"
    linked = {}
    for doc in (item.get("api") or {}).get("linked_drucksachen") or []:
        linked.setdefault(str(doc.get("dokumentnummer")), doc)
    printed = {str(doc.get("dokumentnummer")) for doc in item.get("xml_drucksachen") or []}
    parts = []
    for number in link["vote_numbers"]:
        if number in linked:
            doc = linked[number]
            parts.append(f"{number}:{doc.get('drucksachetyp') or '-'}:{doc.get('vorgang_id') or '-'}")
        elif number in printed:
            parts.append(f"{number}:xml:-")
    return ", ".join(parts) or "-"


def _cell(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split())


def build_sheet(output_dir: Path, seed: int, sample_vorgang: int, sample_xml: int) -> tuple[list[dict[str, str]], dict[str, Any]]:
    database = output_dir / STORE
    if not database.is_file():
        raise ReviewInputError(f"no store at {database}")
    conn = sqlite3.connect(f"{database.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        pulse_store.require_current_schema(conn)
        links = sorted(stored_links(conn), key=_sort_key)
    finally:
        conn.close()
    chosen = strata(links, seed, sample_vorgang, sample_xml)
    tops_of_vote: dict[str, list[str]] = {}
    for link in links:
        tops_of_vote.setdefault(link["vote_id"], []).append(f"{link['top_id']}#{link['top_occurrence']}")
    reports: dict[str, dict[int, Mapping[str, Any]]] = {}
    texts: dict[str, str] = {}
    rows = []
    for position, link in enumerate(links):
        if position not in chosen:
            continue
        number = str(link["document_number"])
        if number not in reports:
            path = output_dir / "data" / f"plenarprotokoll-{slug(number)}.json"
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise ReviewInputError(f"the cached report {path} cannot be read: {exc}") from exc
            reports[number] = {source_index(item.get("index")): item for item in report.get("agenda_items") or []}
            texts[number] = protocol_text(output_dir / "data" / "xml" / f"plenarprotokoll-{slug(number)}.xml")
        tally, announced = find_tally(texts[number], link["yes_count"], link["no_count"])
        own = f"{link['top_id']}#{link['top_occurrence']}"
        rows.append({
            "stratum": "+".join(chosen[position]),
            "protocol": number,
            "date": _cell(link["date"]),
            "vote_id": _cell(link["vote_id"]),
            "vote_title": _cell(link["title"]),
            "item_index": str(link["item_index"]),
            "top_id": _cell(link["top_id"]),
            "top_occurrence": str(link["top_occurrence"]),
            "top_heading": _cell(link["heading"])[:HEADING_CHARS],
            "basis": link["basis"],
            "shared": shared_documents(link, reports[number].get(link["item_index"])),
            "announced": ", ".join(announced) or "-",
            "tally": tally,
            "other_tops": "; ".join(top for top in tops_of_vote[link["vote_id"]] if top != own) or "-",
            "verdict": "", "pattern": "", "action": "", "evidence": "", "reviewer": "",
        })
    summary = {
        "links": len(links),
        "rows": len(rows),
        "strata": dict(sorted(Counter(mark for marks in chosen.values() for mark in marks).items())),
        # A unit is one vote of S1, one TOP of S2, or one row of S3 or S4 in no other stratum.
        "units": len({row["vote_id"] for row in rows if "S1" in row["stratum"]})
        + len({(row["protocol"], row["top_id"], row["top_occurrence"]) for row in rows if "S2" in row["stratum"]})
        + sum(1 for row in rows if row["stratum"] in {"S3", "S4"}),
    }
    return rows, summary


def code_revision() -> str:
    result = subprocess.run(["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True)
    return result.stdout.strip() or "unknown"


def render_sheet(rows: Iterable[Mapping[str, str]], header: Mapping[str, Any]) -> str:
    out = io.StringIO()
    for key, value in header.items():
        out.write(f"# {key}: {value}\n")
    writer = csv.DictWriter(out, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output-dir", type=Path, required=True, help="site directory holding data/bundestag-pulse.sqlite")
    parser.add_argument("--out", type=Path, required=True, help="the TSV to write")
    parser.add_argument("--seed", type=int, default=20261114, help="seed of the S4 draw (default: 20261114)")
    parser.add_argument("--sample-vorgang", type=int, default=34, help="plain drucksache_vorgang links in S4 (default: 34)")
    parser.add_argument("--sample-xml", type=int, default=16, help="plain drucksache_xml links in S4 (default: 16)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.sample_vorgang < 0 or args.sample_xml < 0:
        print("error: a sample size cannot be negative", file=sys.stderr)
        return 2
    try:
        rows, summary = build_sheet(args.output_dir, args.seed, args.sample_vorgang, args.sample_xml)
    except (ReviewInputError, RuntimeError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    header = {"store": args.output_dir.as_posix(), "code revision": code_revision(), "seed": args.seed,
              "sample": f"S4 {args.sample_vorgang} drucksache_vorgang + {args.sample_xml} drucksache_xml",
              "links in store": summary["links"], "rows": summary["rows"], "units": summary["units"],
              "rows per stratum": ", ".join(f"{key} {value}" for key, value in summary["strata"].items())}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    # Written beside the target and renamed, so a stopped run never leaves half a sheet.
    partial = args.out.with_name(args.out.name + ".partial")
    partial.write_text(render_sheet(rows, header), encoding="utf-8")
    partial.replace(args.out)
    print(f"vote_link_review: {summary['rows']} rows ({summary['units']} units) of {summary['links']} links -> {args.out}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
