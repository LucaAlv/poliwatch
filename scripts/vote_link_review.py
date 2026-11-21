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

``--batch-protocols`` names a TSV with a ``sitting`` column (the restored
sittings, ``docs/plans/t4-acquire/restored-sittings.tsv``). Their rows carry
``--batch-name`` in the ``batch`` column (``-`` on every other row). S1 to S3
take them in full like any sitting. S4 keeps them apart: the draw above runs
over the other sittings alone, so it picks the links it picked before the
batch was fetched, and a second draw takes ``BATCH_RATE`` of the batch's plain
links, at least ``BATCH_MIN``. Both options repeat, one name per list, for
sittings fetched later still: the batches are drawn in the order given, so a
new one changes no earlier draw.

A row's key is ``(vote_id, protocol, top_id, top_occurrence)``: ``top_occurrence``
counts the TOPs of the sitting with the same ``top_id`` up to this one, in item
order (21/24 has "Tagesordnungspunkt I" twice). ``item_index`` is informative
only, since a re-parse that adds a TOP renumbers the items; the evidence is read
from the cached report's TOP with the same key.

The verdict columns are filled in from ``scripts/reviewed_vote_links.json`` by
row key wherever an entry exists, so a regenerated sheet keeps every verdict
(``--entries-file`` names another file).

``--entries SHEET SOURCE`` turns filled sheets into that file instead of writing
a sheet: every row's five verdict columns become one entry, with the TOP's
heading start and first page read from the store, merged into the file by key.
It refuses a row without a verdict and a row whose key the file holds with
another verdict, so no verdict is overwritten silently. ``SOURCE`` is
``sheet YYYY-MM-DD`` or ``plan vote-pr-c``; the option repeats.

    python3 scripts/vote_link_review.py --output-dir .context/dip-pulse-site \
        --entries docs/plans/vote-links-review.tsv "sheet 2026-11-21"

``--fixture OUT`` writes the oracle's fixture instead
(``tests/fixtures/vote_links/reviewed-sittings.json.gz``): every sitting that
holds an entry, re-read from its cached XML in memory (the cached JSON can
predate a parse field the rule reads), cut to what ``vote_links`` reads. A
refresh is a reviewed act: it freezes the rule's inputs again.

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
import math
import random
import re
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import gzip

import derive
import persist_dip_pulse_store as pulse_store
import validate_dip_protocol as dip
import vote_links
import reviewed_vote_links as reviewed
import sqlite_open
from stable_ids import source_index

STORE = Path("data") / "bundestag-pulse.sqlite"
COLUMNS = (
    "stratum", "batch", "protocol", "date", "vote_id", "vote_title", "item_index", "top_id", "top_occurrence", "top_heading",
    "basis", "shared", "announced", "tally", "other_tops", "verdict", "pattern", "action", "evidence", "reviewer",
)
#: The share of a batch's plain Drucksache links S4 draws, and the least it draws
#: (docs/plans/t4-acquire.md, step 4).
BATCH_RATE = 0.16
BATCH_MIN = 10
_BATCH_NAME_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,19}")
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


#: The head of the result table the protocol prints after the chair's
#: announcement ("Endgültiges Ergebnis Abgegebene Stimmen: 577; davon ja: 421
#: nein: 66"), up to where the tally starts. "Endgültiges" is not required:
#: 18/133 prints "En dgültiges" and 20/194 "Entgültiges".
_RESULT_TABLE_RE = re.compile(r"Ergebnis\W{0,5}Abgegebene Stimmen\D{0,5}[0-9]{1,6}\W{0,5}davon\W{0,3}\Z", re.I)
_RESULT_TABLE_CHARS = 80


def find_tally(text: str, yes: Any, no: Any) -> tuple[str, list[str]]:
    """``(unique|several|none, Drucksachen announced)`` for one vote: whether its
    exact tally occurs once in the sitting's text, and for a unique one the
    Drucksache numbers in the ``ANNOUNCEMENT_CHARS`` before it and in it. The
    tally inside the printed result table does not count beside another match,
    so the chair's announcement followed by its table is ``unique``."""
    if not isinstance(yes, int) or not isinstance(no, int) or isinstance(yes, bool) or isinstance(no, bool):
        return "none", []
    matches = list(tally_pattern(yes, no).finditer(text))
    if not matches:
        return "none", []
    matches = [match for match in matches
               if not _RESULT_TABLE_RE.search(text, max(0, match.start() - _RESULT_TABLE_CHARS), match.start())] or matches
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
    occurrence: dict[str, tuple[int, tuple[str, str]]] = {}
    for item_id, protocol_id, top_id in conn.execute(
        "SELECT id, protocol_id, top_id FROM agenda_items ORDER BY protocol_id, item_index"
    ):
        seen[(protocol_id, top_id)] += 1
        occurrence[item_id] = (seen[(protocol_id, top_id)], (protocol_id, top_id))
    numbers: dict[str, list[str]] = {}
    for vote_id, number in conn.execute(
        "SELECT vd.vote_id, d.document_number FROM vote_documents vd JOIN documents d ON d.id = vd.document_id ORDER BY vd.rank"
    ):
        numbers.setdefault(vote_id, []).append(number)
    return [{**dict(row), "top_occurrence": occurrence[row["agenda_item_id"]][0],
             "top_count": seen[occurrence[row["agenda_item_id"]][1]],
             "vote_numbers": numbers.get(row["vote_id"], [])} for row in rows]


def _sort_key(link: Mapping[str, Any]) -> tuple:
    wp, _, number = str(link["document_number"]).partition("/")
    vote_id = str(link["vote_id"])
    return (int(wp) if wp.isdigit() else 0, int(number) if number.isdigit() else 0,
            (int(vote_id), "") if vote_id.isdigit() else (-1, vote_id), link["item_index"])


def read_batch(path: Path) -> frozenset[str]:
    """The protocol numbers in the ``sitting`` column of a TSV."""
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if "sitting" not in (reader.fieldnames or []):
                raise ReviewInputError(f"{path} has no sitting column")
            sittings = frozenset(" ".join((row["sitting"] or "").split()) for row in reader) - {""}
    except (OSError, ValueError, csv.Error) as exc:
        raise ReviewInputError(f"the batch list {path} cannot be read: {exc}") from exc
    if not sittings:
        raise ReviewInputError(f"{path} names no sitting")
    return sittings


def batch_sample_size(pool: int) -> int:
    """How many of a batch's ``pool`` plain links S4 draws."""
    return min(pool, max(BATCH_MIN, math.ceil(pool * BATCH_RATE)))


def strata(links: list[dict[str, Any]], seed: int, sample_vorgang: int, sample_xml: int,
           batches: Sequence[frozenset[str]] = ()) -> dict[int, list[str]]:
    """Row position in ``links`` -> its strata. The links of each batch's
    sittings stay out of the two S4 draws and get a draw of their own after
    them, in the order of ``batches``."""
    per_vote = Counter(link["vote_id"] for link in links)
    per_top = Counter(link["agenda_item_id"] for link in links)
    chosen: dict[int, list[str]] = {}
    plain: dict[str, list[int]] = {"drucksache_vorgang": [], "drucksache_xml": []}
    batch_of = {sitting: index for index, batch in enumerate(batches) for sitting in batch}
    batch_plain: list[list[int]] = [[] for _ in batches]
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
            index = batch_of.get(link["document_number"])
            (plain[link["basis"]] if index is None else batch_plain[index]).append(position)
    rng = random.Random(seed)
    for basis, size in (("drucksache_vorgang", sample_vorgang), ("drucksache_xml", sample_xml)):
        pool = plain[basis]
        if size > len(pool):
            raise ReviewInputError(f"--sample-{basis.split('_')[1]} {size} exceeds the {len(pool)} plain {basis} links")
        for position in rng.sample(pool, size):
            chosen[position] = ["S4"]
    for pool in batch_plain:
        for position in rng.sample(pool, batch_sample_size(len(pool))):
            chosen[position] = ["S4"]
    return chosen


def shared_documents(link: Mapping[str, Any], item: Mapping[str, Any] | None) -> str:
    """The vote's Drucksachen the TOP holds, as ``number:type:Vorgang id``,
    with ``:xml`` appended when the protocol also prints the number under the
    TOP, and ``number:xml:-`` for a number only the protocol prints. ``?`` when
    the cached report's TOP cannot be paired with the stored one."""
    if item is None:
        return "?"
    linked = {}
    for doc in (item.get("api") or {}).get("linked_drucksachen") or []:
        linked.setdefault(str(doc.get("dokumentnummer")), doc)
    printed = {str(doc.get("dokumentnummer")) for doc in derive.xml_drucksachen(item)}
    parts = []
    for number in link["vote_numbers"]:
        if number in linked:
            doc = linked[number]
            parts.append(f"{number}:{doc.get('drucksachetyp') or '-'}:{doc.get('vorgang_id') or '-'}"
                         + (":xml" if number in printed else ""))
        elif number in printed:
            parts.append(f"{number}:xml:-")
    return ", ".join(parts) or "-"


class CachedTops:
    """A cached report's TOPs keyed ``(top_id, top_occurrence)`` as the store
    counts them: ``top_id`` cleaned as persist writes it, occurrences in source
    index order. The key survives a replay that renumbers the store's items,
    which the cached JSON's ``index`` does not."""

    def __init__(self, items: Iterable[Mapping[str, Any]]) -> None:
        self.count: Counter[str | None] = Counter()
        self.keyed: dict[tuple[str | None, int], Mapping[str, Any]] = {}
        for item in sorted(items, key=lambda item: source_index(item.get("index"))):
            top_id = pulse_store.clean(item.get("top_id"))
            self.count[top_id] += 1
            self.keyed[(top_id, self.count[top_id])] = item

    def item_of(self, link: Mapping[str, Any]) -> Mapping[str, Any] | None:
        """The cached TOP of a stored link, or None when the store and the
        cached report hold that ``top_id`` a different number of times: a
        replay that adopted a TOP shifts the occurrences, and pairing them
        anyway would show another TOP's Drucksachen."""
        if self.count[link["top_id"]] != link["top_count"]:
            return None
        return self.keyed.get((link["top_id"], link["top_occurrence"]))


def _cell(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split())


def _strata_counts(rows: Iterable[Mapping[str, str]]) -> dict[str, int]:
    return dict(sorted(Counter(mark for row in rows for mark in row["stratum"].split("+")).items()))


#: The sheet's verdict columns, which the review fills, and the entry field each is kept in.
VERDICT_COLUMNS = {"verdict": "verdict", "pattern": "pattern", "action": "action", "evidence": "evidence", "reviewer": "reviewer"}
#: The columns ``--entries`` reads from a filled sheet.
ENTRY_COLUMNS = ("protocol", "vote_id", "top_id", "top_occurrence", *VERDICT_COLUMNS)


def build_sheet(output_dir: Path, seed: int, sample_vorgang: int, sample_xml: int,
                batches: Mapping[str, frozenset[str]] | None = None,
                entries: Iterable[reviewed.Entry] = ()) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """The sheet's rows and its counts. ``batches``: name -> sittings, in draw
    order. ``entries``: reviewed links whose verdicts fill their rows."""
    verdicts = {entry.key: entry for entry in entries}
    batches = dict(batches or {})
    batch_name = {sitting: name for name, sittings in batches.items() for sitting in sittings}
    database = output_dir / STORE
    if not database.is_file():
        raise ReviewInputError(f"no store at {database}")
    conn = sqlite_open.open_readonly(database)
    conn.row_factory = sqlite3.Row
    try:
        pulse_store.require_current_schema(conn)
        links = sorted(stored_links(conn), key=_sort_key)
        unknown = set(batch_name) - {row[0] for row in conn.execute("SELECT document_number FROM protocols")}
        # Votes of one sitting that ended with the same tally: the text cannot
        # say whose announcement a match is.
        twins = {tuple(row) for row in conn.execute(
            "SELECT p.document_number, v.yes_count, v.no_count FROM votes v JOIN protocols p ON p.id = v.protocol_id "
            "WHERE v.yes_count IS NOT NULL AND v.no_count IS NOT NULL GROUP BY 1, 2, 3 HAVING COUNT(*) > 1")}
    finally:
        conn.close()
    if unknown:
        raise ReviewInputError(f"the batch list names {len(unknown)} sittings the store does not hold: "
                               + ", ".join(sorted(unknown)[:5]))
    chosen = strata(links, seed, sample_vorgang, sample_xml, list(batches.values()))
    tops_of_vote: dict[str, list[str]] = {}
    for link in links:
        tops_of_vote.setdefault(link["vote_id"], []).append(f"{link['top_id']}#{link['top_occurrence']}")
    reports: dict[str, CachedTops] = {}
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
                reports[number] = CachedTops(report.get("agenda_items") or [])
            except (OSError, ValueError, AttributeError) as exc:
                raise ReviewInputError(f"the cached report {path} cannot be read: {exc}") from exc
            texts[number] = protocol_text(output_dir / "data" / "xml" / f"plenarprotokoll-{slug(number)}.xml")
        tally, announced = find_tally(texts[number], link["yes_count"], link["no_count"])
        if tally == "unique" and (number, link["yes_count"], link["no_count"]) in twins:
            tally, announced = "several", []
        own = f"{link['top_id']}#{link['top_occurrence']}"
        rows.append({
            "stratum": "+".join(chosen[position]),
            "batch": batch_name.get(number, "-"),
            "protocol": number,
            "date": _cell(link["date"]),
            "vote_id": _cell(link["vote_id"]),
            "vote_title": _cell(link["title"]),
            "item_index": str(link["item_index"]),
            "top_id": _cell(link["top_id"]),
            "top_occurrence": str(link["top_occurrence"]),
            "top_heading": _cell(link["heading"])[:HEADING_CHARS],
            "basis": link["basis"],
            "shared": shared_documents(link, reports[number].item_of(link)),
            "announced": ", ".join(announced) or "-",
            "tally": tally,
            "other_tops": "; ".join(top for top in tops_of_vote[link["vote_id"]] if top != own) or "-",
            **_verdict_cells(verdicts.get((number, _cell(link["vote_id"]), _cell(link["top_id"]), link["top_occurrence"]))),
        })
    summary = {
        "links": len(links),
        "rows": len(rows),
        "strata": _strata_counts(rows),
        "batches": {name: {"links": sum(1 for link in links if link["document_number"] in sittings),
                           "strata": _strata_counts(row for row in rows if row["batch"] == name),
                           "rows": sum(1 for row in rows if row["batch"] == name)}
                    for name, sittings in batches.items()},
        # A unit is one vote of S1, one TOP of S2, or one row of S3 or S4 in no other stratum.
        "units": len({row["vote_id"] for row in rows if "S1" in row["stratum"]})
        + len({(row["protocol"], row["top_id"], row["top_occurrence"]) for row in rows if "S2" in row["stratum"]})
        + sum(1 for row in rows if row["stratum"] in {"S3", "S4"}),
    }
    return rows, summary


def _verdict_cells(entry: reviewed.Entry | None) -> dict[str, str]:
    return {column: getattr(entry, name) if entry else "" for column, name in VERDICT_COLUMNS.items()}


def read_filled_sheet(path: Path) -> list[dict[str, str]]:
    """The rows of a filled sheet (``#`` lines skipped), each with the
    ``ENTRY_COLUMNS``, whitespace collapsed."""
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader((line for line in handle if not line.startswith("#")), delimiter="\t")
            missing = [column for column in ENTRY_COLUMNS if column not in (reader.fieldnames or [])]
            if missing:
                raise ReviewInputError(f"{path} lacks the column(s) {', '.join(missing)}")
            return [{column: _cell(row[column]) for column in ENTRY_COLUMNS} for row in reader]
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise ReviewInputError(f"the sheet {path} cannot be read: {exc}") from exc


def sheet_entries(rows: Iterable[Mapping[str, str]], source: str, sittings: Mapping[str, reviewed.Sitting],
                  where: str) -> list[reviewed.Entry]:
    """One entry per filled row, its TOP's heading start and first page read
    from ``sittings`` (the store). Refuses a row without a verdict, and one
    whose sitting or TOP the store lacks."""
    raw = []
    for number, row in enumerate(rows, 1):
        label = f"{where} row {number} ({row['protocol']} vote {row['vote_id']} {row['top_id']} #{row['top_occurrence']})"
        if not row["verdict"]:
            raise ReviewInputError(f"{label} has no verdict; fill it, or leave the row out")
        sitting = sittings.get(row["protocol"])
        if not row["top_occurrence"].isdigit() or sitting is None:
            raise ReviewInputError(f"{label}: the store holds no such sitting, or top_occurrence is not a number")
        position = sitting.position(row["top_id"], int(row["top_occurrence"]))
        if position is None:
            raise ReviewInputError(f"{label}: the store's sitting holds no such TOP")
        _top_id, heading, page = sitting.tops[position]
        raw.append({"protocol": row["protocol"], "vote_id": row["vote_id"], "top_id": row["top_id"],
                    "top_occurrence": int(row["top_occurrence"]), "heading_starts": reviewed.heading_start(heading),
                    "page_start": page, "verdict": row["verdict"], "pattern": row["pattern"], "action": row["action"],
                    "note": "", "evidence": row["evidence"], "reviewer": row["reviewer"], "source": source})
    try:
        return reviewed.check({"entries": raw}, where)
    except reviewed.ReviewedVoteLinksError as exc:
        raise ReviewInputError(str(exc)) from exc


def merge_entries(existing: Iterable[reviewed.Entry], new: Iterable[reviewed.Entry]) -> list[reviewed.Entry]:
    """``existing`` with ``new`` merged in by key. A key both hold with another
    verdict is refused: a verdict changes only by editing the file itself."""
    merged = {entry.key: entry for entry in existing}
    for entry in new:
        old = merged.get(entry.key)
        if old is not None and old.verdict != entry.verdict:
            raise ReviewInputError(f"{entry.label}: the entries file holds verdict {old.verdict}, the sheet {entry.verdict}; "
                                   "change the file by hand if the verdict really changed")
        merged[entry.key] = entry
    return list(merged.values())


def write_entries(output_dir: Path, sheets: Sequence[tuple[str, str]], entries_file: Path) -> int:
    """``--entries``: merge the filled ``sheets`` (path, source) into ``entries_file``. Returns how many entries it holds."""
    database = output_dir / STORE
    if not database.is_file():
        raise ReviewInputError(f"no store at {database}")
    conn = sqlite_open.open_readonly(database)
    try:
        pulse_store.require_current_schema(conn)
        sittings = reviewed.sittings_of_store(conn)
    finally:
        conn.close()
    try:
        existing = reviewed.load(entries_file) if entries_file.exists() else []
    except reviewed.ReviewedVoteLinksError as exc:
        raise ReviewInputError(str(exc)) from exc
    new: list[reviewed.Entry] = []
    for path, source in sheets:
        new += sheet_entries(read_filled_sheet(Path(path)), source, sittings, Path(path).name)
    merged = merge_entries(existing, new)
    try:
        text = reviewed.dump(reviewed.check(json.loads(reviewed.dump(merged)), entries_file.name))
    except reviewed.ReviewedVoteLinksError as exc:
        raise ReviewInputError(str(exc)) from exc
    partial = entries_file.with_name(entries_file.name + ".partial")
    partial.write_text(text, encoding="utf-8")
    partial.replace(entries_file)
    return len(merged)


def fixture_sitting(report: Mapping[str, Any]) -> dict[str, Any]:
    """What ``vote_links.links`` and ``reviewed_vote_links.sitting_of_report``
    read of a report, and nothing else; every vote among the sitting votes,
    since the rule ignores where a report placed a vote."""
    def position(raw: Mapping[str, Any]) -> dict[str, Any]:
        source = raw.get("source") or {}
        return {"vorgang_id": raw.get("vorgang_id"), "vorgangsposition": raw.get("vorgangsposition"), "titel": raw.get("titel"),
                "source": {key: source.get(key) for key in ("seite", "anfangsseite", "endseite")},
                "mitberaten": [{"id": other.get("id"), "titel": other.get("titel")} for other in raw.get("mitberaten") or []]}

    items = []
    for item in report.get("agenda_items") or []:
        api = item.get("api") or {}
        items.append({
            "index": item.get("index"), "top_id": item.get("top_id"), "heading": item.get("heading"),
            "page_range": item.get("page_range"), "xml_speech_count": item.get("xml_speech_count"),
            "xml_drucksachen": [{"dokumentnummer": doc.get("dokumentnummer"), "url": doc.get("url")}
                                for doc in item.get("xml_drucksachen") or []],
            "called_drucksachen": list(item.get("called_drucksachen") or []),
            "api": {"positions": [position(raw) for raw in api.get("positions") or []],
                    "linked_drucksachen": [{key: doc.get(key) for key in ("dokumentnummer", "vorgang_id", "herausgeber", "url")}
                                           for doc in api.get("linked_drucksachen") or []]},
            "votes": [],
        })
    votes = [{key: vote.get(key) for key in ("id", "title", "description", "document_numbers")}
             for vote in vote_links.report_votes(report).values()]
    return {"protocol": {"dokumentnummer": (report.get("protocol") or {}).get("dokumentnummer")},
            "agenda_items": items, "sitting_votes": votes}


def write_fixture(output_dir: Path, entries: Iterable[reviewed.Entry], out: Path) -> int:
    """``--fixture``: the sittings holding an entry, re-read from their cached
    XML and cut by ``fixture_sitting``, as one gzipped JSON file whose bytes
    depend only on its content. Returns how many sittings it holds."""
    def order(number: str) -> tuple[int, int]:
        wp, _, sitting = number.partition("/")
        return (int(wp), int(sitting))

    sittings = []
    for number in sorted({entry.protocol for entry in entries}, key=order):
        report_path = output_dir / "data" / f"plenarprotokoll-{slug(number)}.json"
        xml_path = output_dir / "data" / "xml" / f"plenarprotokoll-{slug(number)}.xml"
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            dip.reparse_report_xml(report, dip.parse_protocol_xml(xml_path.read_text(encoding="utf-8")))
        except (OSError, ValueError, dip.ET.ParseError) as exc:
            raise ReviewInputError(f"{number}: the cached report or XML cannot be re-read ({exc})") from exc
        sittings.append(fixture_sitting(report))
    text = json.dumps({"sittings": sittings}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(out.name + ".partial")
    with partial.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as handle:
        handle.write(text.encode("utf-8"))
    partial.replace(out)
    return len(sittings)


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
    parser.add_argument("--out", type=Path, help="the TSV to write (not with --entries)")
    parser.add_argument("--entries", nargs=2, action="append", default=[], metavar=("SHEET", "SOURCE"),
                        help="merge a filled sheet's verdicts into the entries file instead of writing a sheet; "
                        "SOURCE is 'sheet YYYY-MM-DD' or 'plan vote-pr-c' (repeatable)")
    parser.add_argument("--fixture", type=Path, metavar="OUT",
                        help="write the oracle fixture of every sitting the entries file names to OUT instead of a sheet")
    parser.add_argument("--entries-file", type=Path, default=reviewed.PATH,
                        help="the reviewed vote links file (default: scripts/reviewed_vote_links.json)")
    parser.add_argument("--seed", type=int, default=20261114, help="seed of the S4 draw (default: 20261114)")
    parser.add_argument("--sample-vorgang", type=int, default=34, help="plain drucksache_vorgang links in S4 (default: 34)")
    parser.add_argument("--sample-xml", type=int, default=16, help="plain drucksache_xml links in S4 (default: 16)")
    parser.add_argument("--batch-protocols", type=Path, action="append", default=[],
                        help="TSV with a sitting column: the sittings of a later batch, kept out of the S4 draw above "
                        "and sampled on their own (repeatable; batches are drawn in the order given)")
    parser.add_argument("--batch-name", action="append", default=[],
                        help="the batch column's value on those sittings' rows, one per --batch-protocols "
                        "(default for a single batch: t4)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.entries:
        if args.out:
            print("error: --entries writes the entries file; leave out --out", file=sys.stderr)
            return 2
        try:
            count = write_entries(args.output_dir, args.entries, args.entries_file)
        except (ReviewInputError, RuntimeError, sqlite3.Error) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"vote_link_review: {count} entries -> {args.entries_file}", file=sys.stderr)
        return 0
    if args.fixture:
        try:
            count = write_fixture(args.output_dir, reviewed.load(args.entries_file), args.fixture)
        except (ReviewInputError, reviewed.ReviewedVoteLinksError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(f"vote_link_review: {count} sittings -> {args.fixture}", file=sys.stderr)
        return 0
    if args.out is None:
        print("error: give --out (the sheet to write), --entries or --fixture", file=sys.stderr)
        return 2
    if args.sample_vorgang < 0 or args.sample_xml < 0:
        print("error: a sample size cannot be negative", file=sys.stderr)
        return 2
    names = args.batch_name or (["t4"] if len(args.batch_protocols) <= 1 else [])
    if not all(_BATCH_NAME_RE.fullmatch(name) for name in names):
        print("error: --batch-name takes up to 20 lower-case letters, digits and hyphens", file=sys.stderr)
        return 2
    if args.batch_protocols and len(names) != len(args.batch_protocols):
        print("error: give one --batch-name for each --batch-protocols", file=sys.stderr)
        return 2
    try:
        batches: dict[str, frozenset[str]] = {}
        for name, path in zip(names, args.batch_protocols):
            if name in batches:
                raise ReviewInputError(f"two batches are named {name}")
            sittings = read_batch(path)
            for other, held in batches.items():
                if sittings & held:
                    raise ReviewInputError(f"{sorted(sittings & held)[0]} is in the batches {other} and {name}")
            batches[name] = sittings
        try:
            entries = reviewed.load(args.entries_file)
        except reviewed.ReviewedVoteLinksError as exc:
            raise ReviewInputError(str(exc)) from exc
        rows, summary = build_sheet(args.output_dir, args.seed, args.sample_vorgang, args.sample_xml, batches, entries)
    except (ReviewInputError, RuntimeError, sqlite3.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    header = {"store": args.output_dir.as_posix(), "code revision": code_revision(), "seed": args.seed,
              "sample": f"S4 {args.sample_vorgang} drucksache_vorgang + {args.sample_xml} drucksache_xml",
              "links in store": summary["links"], "rows": summary["rows"], "units": summary["units"],
              "rows per stratum": ", ".join(f"{key} {value}" for key, value in summary["strata"].items())}
    if batches:
        header["sample"] += (f"; batch {', '.join(batches)} apart: {BATCH_RATE:.0%} of its plain Drucksache links, "
                             f"at least {BATCH_MIN}")
    for (name, sittings), path in zip(batches.items(), args.batch_protocols):
        counts = summary["batches"][name]
        header[f"batch {name}"] = (
            f"{len(sittings)} sittings of {path.as_posix()}, {counts['links']} links in store, "
            f"{counts['rows']} rows: " + ", ".join(f"{key} {value}" for key, value in counts["strata"].items()))
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
