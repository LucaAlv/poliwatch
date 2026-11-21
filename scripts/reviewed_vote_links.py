"""The reviewed vote links (``scripts/reviewed_vote_links.json``, vote PR C).

One entry per reviewed link between a namentliche Abstimmung and a TOP of its
sitting, keyed ``(protocol, vote_id, top_id, top_occurrence)``: ``top_id`` as
persist stores it (``derive.clean_text``), ``top_occurrence`` counting the TOPs of
the sitting with that ``top_id`` in item order, as the review sheet
(``scripts/vote_link_review.py``) counts them. ``heading_starts`` (the first
``HEADING_CHARS`` characters of the cleaned heading, compared as a prefix) and
``page_start`` (the TOP's first page) tell a shifted TOP from the reviewed one.

``verdict`` is ``right`` or ``wrong``; ``pattern`` ``A`` to ``D`` (a cause the
rule handles) or ``-``; ``action``:

- ``none``: a right link; the rule must make it.
- ``rule``: a wrong link a pattern of the rule removes; the rule must not make it.
- ``drop`` and ``flag``: one-off entries that act on the data (owner decision 2).
  They act from vote PR C2 on; until then the loader refuses them, so no entry
  is ever read as acting while nothing applies it.

The entries apply after the rule and never stand in for a pattern. Three readers
check them: the CI oracle (``tests/test_vote_link_oracle.py``), the store gate
(``validate_store_gate.py``) and the release (``publish_dip_pulse_data.run_release``).
A malformed file raises ``ReviewedVoteLinksError``. Whether an entry still holds
is ``problems``' answer for one sitting (``Sitting``), never a refusal of the run:
a regression of a checked link fails the oracle, the store gate and the release.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

import derive
import vote_links
from stable_ids import document_sort_key

PATH = Path(__file__).resolve().with_name("reviewed_vote_links.json")
HEADING_CHARS = 40
VERDICTS = ("right", "wrong")
PATTERNS = ("A", "B", "C", "D", "-")
ACTIONS = ("none", "rule", "drop", "flag")
#: The actions vote PR C1 applies: none of them changes the data.
APPLIED_ACTIONS = ("none", "rule")
ENTRY_KEYS = frozenset({
    "protocol", "vote_id", "top_id", "top_occurrence", "heading_starts", "page_start",
    "verdict", "pattern", "action", "note", "evidence", "reviewer", "source",
})
_PROTOCOL_RE = re.compile(r"\d{2}/\d{1,3}")
_SOURCE_RE = re.compile(r"(?:sheet \d{4}-\d{2}-\d{2}|plan vote-pr-c)")
_TEXT_LIMIT = 4000


class ReviewedVoteLinksError(Exception):
    """The reviewed vote links file is missing or malformed. Names the entry; stops the run."""


LinkKey = tuple[str, str, str, int]


@dataclass(frozen=True)
class Entry:
    protocol: str
    vote_id: str
    top_id: str
    top_occurrence: int
    heading_starts: str
    page_start: int | None
    verdict: str
    pattern: str
    action: str
    note: str
    evidence: str
    reviewer: str
    source: str

    @property
    def key(self) -> LinkKey:
        return (self.protocol, self.vote_id, self.top_id, self.top_occurrence)

    @property
    def label(self) -> str:
        return f"{self.protocol} vote {self.vote_id} {self.top_id} #{self.top_occurrence}"

    def as_json(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in (
            "protocol", "vote_id", "top_id", "top_occurrence", "heading_starts", "page_start",
            "verdict", "pattern", "action", "note", "evidence", "reviewer", "source")}


def heading_start(heading: Any) -> str:
    """What an entry keeps of a TOP heading: its first ``HEADING_CHARS`` characters, cleaned."""
    return derive.clean_text(heading)[:HEADING_CHARS].rstrip()


def _text(entry: Mapping[str, Any], name: str, label: str, *, empty: bool = True) -> str:
    value = entry[name]
    if not isinstance(value, str) or len(value) > _TEXT_LIMIT:
        raise ReviewedVoteLinksError(f"{label}: {name} must be a string of at most {_TEXT_LIMIT} characters")
    if value != derive.clean_text(value):
        raise ReviewedVoteLinksError(f"{label}: {name} {value!r} has leading, trailing or repeated whitespace")
    if not empty and not value:
        raise ReviewedVoteLinksError(f"{label}: {name} must not be empty")
    return value


def check(data: Any, where: str = PATH.name) -> list[Entry]:
    """The entries of a parsed file, in file order; refuses anything malformed
    (``ReviewedVoteLinksError``)."""
    if not isinstance(data, dict) or set(data) != {"entries"} or not isinstance(data["entries"], list):
        raise ReviewedVoteLinksError(f'{where} must be an object with exactly one key, "entries", an array')
    entries: list[Entry] = []
    seen: set[LinkKey] = set()
    for position, raw in enumerate(data["entries"], 1):
        label = f"{where} entry {position}"
        if not isinstance(raw, dict) or set(raw) != ENTRY_KEYS:
            raise ReviewedVoteLinksError(f"{label} must have exactly the keys {', '.join(sorted(ENTRY_KEYS))}")
        protocol = _text(raw, "protocol", label, empty=False)
        if not _PROTOCOL_RE.fullmatch(protocol):
            raise ReviewedVoteLinksError(f"{label}: protocol {protocol!r} is not WP/NR, e.g. 21/45")
        vote_id = _text(raw, "vote_id", label, empty=False)
        top_id = _text(raw, "top_id", label, empty=False)
        occurrence = raw["top_occurrence"]
        if not isinstance(occurrence, int) or isinstance(occurrence, bool) or not 1 <= occurrence <= 99:
            raise ReviewedVoteLinksError(f"{label}: top_occurrence must be a whole number from 1 to 99")
        heading = _text(raw, "heading_starts", label)
        if len(heading) > HEADING_CHARS:
            raise ReviewedVoteLinksError(f"{label}: heading_starts holds more than {HEADING_CHARS} characters")
        page = raw["page_start"]
        if page is not None and (not isinstance(page, int) or isinstance(page, bool) or not 0 < page < 10**6):
            raise ReviewedVoteLinksError(f"{label}: page_start must be a page number or null")
        verdict, pattern, action = (_text(raw, name, label) for name in ("verdict", "pattern", "action"))
        if verdict not in VERDICTS:
            raise ReviewedVoteLinksError(f"{label}: verdict {verdict!r} is not one of {', '.join(VERDICTS)}")
        if pattern not in PATTERNS:
            raise ReviewedVoteLinksError(f"{label}: pattern {pattern!r} is not one of {', '.join(PATTERNS)}")
        if action not in ACTIONS:
            raise ReviewedVoteLinksError(f"{label}: action {action!r} is not one of {', '.join(ACTIONS)}")
        if (verdict, action) not in {("right", "none"), ("wrong", "rule"), ("wrong", "drop"), ("right", "flag"), ("wrong", "flag")}:
            raise ReviewedVoteLinksError(f"{label}: a {verdict} link cannot have action {action}")
        if (action == "rule") != (pattern != "-"):
            raise ReviewedVoteLinksError(f"{label}: action rule needs a pattern A to D, and only it has one")
        note = _text(raw, "note", label, empty=action not in ("drop", "flag"))
        if action not in APPLIED_ACTIONS:
            raise ReviewedVoteLinksError(
                f"{label}: action {action} acts on the data, which vote PR C2 builds; until then no entry may drop or flag")
        source = _text(raw, "source", label, empty=False)
        if not _SOURCE_RE.fullmatch(source):
            raise ReviewedVoteLinksError(f"{label}: source {source!r} is neither 'sheet YYYY-MM-DD' nor 'plan vote-pr-c'")
        entry = Entry(protocol, vote_id, top_id, occurrence, heading, page, verdict, pattern, action, note,
                      _text(raw, "evidence", label), _text(raw, "reviewer", label), source)
        if entry.key in seen:
            raise ReviewedVoteLinksError(f"{label}: {entry.label} is listed twice")
        seen.add(entry.key)
        entries.append(entry)
    return entries


def parse(text: str, where: str = PATH.name) -> list[Entry]:
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise ReviewedVoteLinksError(f"{where} is not valid JSON ({exc})") from exc
    return check(data, where)


def load(path: Path = PATH) -> list[Entry]:
    """Every entry of the file, checked whole."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ReviewedVoteLinksError(f"{path} is missing; it is checked in, restore it "
                                     "(git checkout -- scripts/reviewed_vote_links.json)") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ReviewedVoteLinksError(f"{path} cannot be read ({exc})") from exc
    return parse(text, path.name)


def dump(entries: Iterable[Entry]) -> str:
    """The file's text: one entry per line, sorted by sitting, vote and TOP, so a
    merge shows each changed entry as one changed line."""
    ordered = sorted(entries, key=lambda e: (*document_sort_key(e.protocol), _vote_order(e.vote_id), e.top_id, e.top_occurrence))
    lines = [json.dumps(entry.as_json(), ensure_ascii=False, separators=(", ", ": ")) for entry in ordered]
    return '{"entries": [\n' + ",\n".join(lines) + "\n]}\n"


def _vote_order(vote_id: str) -> tuple[int, str]:
    return (int(vote_id), "") if vote_id.isdigit() else (-1, vote_id)


@dataclass
class Sitting:
    """What the checks need of one sitting: its TOPs in item order as
    ``(top_id, heading, page_start)``, its votes, and its links as
    ``(vote_id, position of the TOP)`` with the deciding step per vote."""
    protocol: str
    tops: list[tuple[str, str, int | None]]
    votes: set[str]
    links: set[tuple[str, int]]
    steps: dict[str, str] = field(default_factory=dict)

    def position(self, top_id: str, occurrence: int) -> int | None:
        seen = 0
        for position, (other, _heading, _page) in enumerate(self.tops):
            if other == top_id:
                seen += 1
                if seen == occurrence:
                    return position
        return None

    def key_of(self, vote_id: str, position: int) -> LinkKey:
        top_id = self.tops[position][0]
        occurrence = sum(1 for other, _h, _p in self.tops[:position + 1] if other == top_id)
        return (self.protocol, vote_id, top_id, occurrence)


def page_of(page: Any) -> int | None:
    """A TOP's first page as persist stores it (``agenda_items.page_start``)."""
    if not isinstance(page, Mapping) or page.get("page") is None:
        return None
    try:
        return int(page["page"])
    except (TypeError, ValueError):
        return None


def sitting_of_report(report: Mapping[str, Any], links: Mapping[str, Any]) -> Sitting:
    """A cached or replayed report as a ``Sitting``; ``links`` is ``vote_links.links(report)``."""
    protocol = derive.clean_text((report.get("protocol") or {}).get("dokumentnummer"))
    tops = [(derive.clean_text(item.get("top_id")), derive.clean_text(item.get("heading")),
             page_of((item.get("page_range") or {}).get("start")))
            for item in report.get("agenda_items") or []]
    return Sitting(protocol, tops, set(links),
                   {(vote_id, position) for vote_id, link in links.items() for position in link.tops},
                   {vote_id: link.step for vote_id, link in links.items()})


def sittings_of_rows(protocols: Iterable[tuple], agenda_items: Iterable[tuple], votes: Iterable[tuple],
                     links: Iterable[tuple]) -> dict[str, Sitting]:
    """Every sitting of a store or an export, by document number, from its rows:
    ``protocols`` (id, document_number), ``agenda_items`` (id, protocol_id,
    item_index, top_id, heading, page_start), ``votes`` (id, protocol_id,
    top_link_step) and ``agenda_item_votes`` (agenda_item_id, vote_id). Numbers
    may come as text (an exported CSV)."""
    def number(value: Any) -> int | None:
        return None if value is None or value == "" else int(value)

    sittings: dict[str, Sitting] = {}
    by_protocol: dict[str, Sitting] = {}
    for protocol_id, document_number in protocols:
        sitting = Sitting(derive.clean_text(document_number), [], set(), set())
        sittings[sitting.protocol] = by_protocol[str(protocol_id)] = sitting
    positions: dict[str, tuple[Sitting, int]] = {}
    ordered = sorted(agenda_items, key=lambda row: (str(row[1]), number(row[2])))
    for item_id, protocol_id, _index, top_id, heading, page in ordered:
        sitting = by_protocol[str(protocol_id)]
        positions[str(item_id)] = (sitting, len(sitting.tops))
        sitting.tops.append((derive.clean_text(top_id), derive.clean_text(heading), number(page)))
    for vote_id, protocol_id, step in votes:
        sitting = by_protocol.get(str(protocol_id))
        if sitting is not None:
            sitting.votes.add(str(vote_id))
            sitting.steps[str(vote_id)] = step
    for item_id, vote_id in links:
        sitting, position = positions[str(item_id)]
        sitting.links.add((str(vote_id), position))
    return sittings


def sittings_of_store(conn: Any) -> dict[str, Sitting]:
    """``sittings_of_rows`` over a build store or an export's SQLite."""
    return sittings_of_rows(
        conn.execute("SELECT id, document_number FROM protocols").fetchall(),
        conn.execute("SELECT id, protocol_id, item_index, top_id, heading, page_start FROM agenda_items").fetchall(),
        conn.execute("SELECT id, protocol_id, top_link_step FROM votes").fetchall(),
        conn.execute("SELECT agenda_item_id, vote_id FROM agenda_item_votes").fetchall(),
    )


def problems(entries: Iterable[Entry], sitting: Sitting) -> list[str]:
    """Each entry of ``sitting`` that no longer holds, as a sentence: its vote
    or TOP is unknown, the TOP's heading or first page differs, a right link is
    not made, or a wrong one is."""
    found = []
    for entry in entries:
        if entry.protocol != sitting.protocol:
            continue
        if entry.vote_id not in sitting.votes:
            found.append(f"{entry.label}: the sitting holds no vote {entry.vote_id}")
            continue
        position = sitting.position(entry.top_id, entry.top_occurrence)
        if position is None:
            found.append(f"{entry.label}: the sitting holds no such TOP")
            continue
        _top_id, heading, page = sitting.tops[position]
        if not heading.startswith(entry.heading_starts):
            found.append(f"{entry.label}: the TOP's heading no longer starts {entry.heading_starts!r}")
        elif page != entry.page_start:
            found.append(f"{entry.label}: the TOP starts on page {page}, not {entry.page_start}")
        elif entry.verdict == "right" and (entry.vote_id, position) not in sitting.links:
            found.append(f"{entry.label}: reviewed right, but the rule no longer makes the link")
        elif entry.verdict == "wrong" and (entry.vote_id, position) in sitting.links:
            found.append(f"{entry.label}: reviewed wrong, but the rule makes the link")
    return found


def contested(sitting: Sitting) -> dict[str, list[int]]:
    """The votes the release gate checks, with the positions of their TOPs: a
    vote linked to two or more TOPs, or one a step after the plain match
    decided (``vote_links.CONTESTED_STEPS``)."""
    per_vote: dict[str, list[int]] = {}
    for vote_id, position in sorted(sitting.links):
        per_vote.setdefault(vote_id, []).append(position)
    return {vote_id: positions for vote_id, positions in per_vote.items()
            if len(positions) > 1 or sitting.steps.get(vote_id) in vote_links.CONTESTED_STEPS}


def gate(entries: Iterable[Entry], sittings: Mapping[str, Sitting]) -> dict[str, Any]:
    """The release condition over a store or an export: every link of every
    contested vote has a holding entry with verdict right (or a flag), and no
    made link has a wrong entry. Returns ``refusals`` (sentences), ``contested``
    (how many votes), ``reviewed`` (entries checked) and ``skipped`` (entries of
    sittings ``sittings`` does not hold)."""
    entries = list(entries)
    by_link = {entry.key: entry for entry in entries}
    by_protocol: dict[str, list[Entry]] = {}
    for entry in entries:
        by_protocol.setdefault(entry.protocol, []).append(entry)
    refusals: list[str] = []
    count = 0
    for protocol in sorted(sittings, key=document_sort_key):
        sitting = sittings[protocol]
        stale = set(problems(by_protocol.get(protocol, []), sitting))
        for vote_id, positions in contested(sitting).items():
            count += 1
            for position in positions:
                key = sitting.key_of(vote_id, position)
                entry = by_link.get(key)
                where = f"{protocol} vote {vote_id} {key[2]} #{key[3]}"
                if entry is None:
                    refusals.append(f"{where}: contested link ({sitting.steps.get(vote_id)}, {len(positions)} TOP(s)) has no reviewed entry")
                elif entry.verdict != "right" and entry.action != "flag":
                    refusals.append(f"{where}: contested link is reviewed {entry.verdict}")
        # Every entry of the sitting that no longer holds, a made wrong link included.
        refusals += sorted(stale)
    held = Counter(entry.protocol in sittings for entry in entries)
    return {"refusals": list(dict.fromkeys(refusals)), "contested": count,
            "reviewed": held[True], "skipped": held[False]}
