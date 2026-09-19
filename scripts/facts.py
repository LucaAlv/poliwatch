#!/usr/bin/env python3
"""Fakt der Woche: the facts rule over the live store.

A0 (this file): the metric registry, the rule as pure functions, a read-only
replay and sample SVG cards. Nothing here writes to the store; A1 adds
compute_and_store, the pages and the export on top of ``compute``.

The rule (plan D5/D10/D12, ~/.gstack/projects/LucaAlv-poliwatch/fakt-der-woche-plan.md):

* A sitting week is an ISO week with at least one protocol; its Wahlperiode
  comes from the protocols' ``document_number`` prefix ("21/94" -> 21).
* Each metric yields at most one observation per week (the week's max or min
  over its candidate rows; a row-level tie cites the lowest id) and only when
  the week is complete for the metric's coverage domain (votes: every sitting's
  vote acquisition is ``complete``; speeches: every sitting's XML was parsed).
  Incomplete weeks yield no observation and never enter anyone's history.
* The week's percentile is the share of *prior* weekly observations it strictly
  beats in the metric's direction (max: greater, min: smaller). Prior means
  strictly before the week, so later weeks never change an earlier row.
* The baseline is the same Wahlperiode when it holds at least
  ``min_history_weeks`` (8) prior observations, else all coverage; fewer than 8
  in all coverage makes the week ineligible ("noch nicht vergleichbar").
* The week's fact is the eligible metric with the highest percentile; equal
  percentiles go to the lower ``tie_rank`` (knappste-abstimmung before
  laengste-rede). No eligible metric, no fact.

Replay: ``python3 scripts/facts.py --replay 30 --cards DIR [--store PATH]``.
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
import textwrap
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping
from xml.sax.saxutils import escape

from render_dip_pulse_html import format_int, iso_week_key, speaker_party


class FactsError(RuntimeError):
    """A protocol or metric the rule cannot process (build-aborting)."""


MIN_HISTORY_WEEKS = 8
DEFAULT_STORE = Path(".context/dip-pulse-site/data/bundestag-pulse.sqlite")

# The registry mirrors RECIPES (build_dip_pulse_site.py). ``sql`` lists every
# candidate row with the protocol it belongs to; ``compute`` groups the rows
# into sitting weeks and applies ``direction``. ``coverage`` names the
# completeness domain a week must be complete for; ``depends_on`` the build
# component that must exist for the metric to run at all.
REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "id": "knappste-abstimmung",
        "version": 1,
        "title": "Die knappste Abstimmung der Woche",
        "unit": "Anteil der Stimmendifferenz an Ja+Nein",
        "direction": "min",
        "sql": (
            "SELECT v.id, v.title, v.date, v.yes_count, v.no_count, v.detail_url,\n"
            "       ABS(v.yes_count - v.no_count) * 1.0 / (v.yes_count + v.no_count) AS value,\n"
            "       v.yes_count + v.no_count AS denominator,\n"
            "       p.id AS protocol_id, p.document_number, MIN(p.date) AS protocol_date\n"
            "FROM votes v\n"
            "JOIN agenda_item_votes aiv ON aiv.vote_id = v.id\n"
            "JOIN agenda_items ai ON ai.id = aiv.agenda_item_id\n"
            "JOIN protocols p ON p.id = ai.protocol_id\n"
            "WHERE v.yes_count + v.no_count > 0\n"
            "GROUP BY v.id"
        ),
        "min_history_weeks": MIN_HISTORY_WEEKS,
        "tie_rank": 1,
        "depends_on": "votes",
        "coverage": "votes",
    },
    {
        "id": "laengste-rede",
        "version": 1,
        "title": "Die längste Rede der Woche",
        "unit": "Zeichen",
        "direction": "max",
        "sql": (
            "SELECT s.id, s.rede_id, s.page, s.page_quadrant, s.char_count AS value,\n"
            "       NULL AS denominator, m.display_name, pa.name AS fraktion,\n"
            "       p.id AS protocol_id, p.document_number, p.pdf_url\n"
            "FROM speeches s\n"
            "JOIN mps m ON m.id = s.mp_id\n"
            "LEFT JOIN parties pa ON pa.id = m.party_id\n"
            "JOIN protocols p ON p.id = s.protocol_id\n"
            "WHERE s.mp_id IS NOT NULL"
        ),
        "min_history_weeks": MIN_HISTORY_WEEKS,
        "tie_rank": 2,
        "depends_on": None,
        "coverage": "speeches",
    },
)
REGISTRY_BY_ID = {metric["id"]: metric for metric in REGISTRY}

MONTHS_DE = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)


# ---------------------------------------------------------------------------
# Sitting weeks and Wahlperiode
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Week:
    key: tuple[int, int]
    wahlperiode: int
    protocols: tuple[dict[str, Any], ...]

    @property
    def label(self) -> str:
        return week_label(self.key)

    @property
    def protocol_ids(self) -> tuple[str, ...]:
        return tuple(str(p["id"]) for p in self.protocols)

    @property
    def first_date(self) -> date:
        return date.fromisoformat(str(self.protocols[0]["date"])[:10])


def week_label(key: tuple[int, int]) -> str:
    return f"{key[0]}-W{key[1]:02d}"


def wahlperiode(document_number: Any) -> int:
    """"21/94" -> 21. Raises FactsError on anything else."""
    text = str(document_number or "").strip()
    head, sep, tail = text.partition("/")
    if not sep or not head.isdigit() or not tail.strip().isdigit():
        raise FactsError(f"facts: malformed protocol document_number {text!r}")
    return int(head)


def protocol_number(document_number: Any) -> int:
    return int(str(document_number).partition("/")[2].strip())


def load_protocols(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            "SELECT id, document_number, date, pdf_url FROM protocols ORDER BY date, document_number"
        ).fetchall()
    ]


def sitting_weeks(protocols: Iterable[Mapping[str, Any]]) -> list[Week]:
    """Group protocols into ISO sitting weeks, oldest first."""
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for protocol in protocols:
        number = protocol.get("document_number")
        wp = wahlperiode(number)
        key = iso_week_key(protocol.get("date"))
        if key is None:
            raise FactsError(f"facts: protocol {number} has no usable date ({protocol.get('date')!r})")
        entry = dict(protocol)
        entry["wahlperiode"] = wp
        grouped.setdefault(key, []).append(entry)
    weeks: list[Week] = []
    for key in sorted(grouped):
        rows = sorted(grouped[key], key=lambda p: (str(p["date"]), protocol_number(p["document_number"])))
        wps = {p["wahlperiode"] for p in rows}
        if len(wps) != 1:
            raise FactsError(f"facts: sitting week {week_label(key)} spans Wahlperioden {sorted(wps)}")
        weeks.append(Week(key=key, wahlperiode=wps.pop(), protocols=tuple(rows)))
    return weeks


# ---------------------------------------------------------------------------
# Completeness (D10). A0 derives it from the cached report JSON; A1 will pass
# the same map built from the in-memory entries.
# ---------------------------------------------------------------------------


def completeness_from_reports(reports: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, bool]]:
    """document_number -> {"votes": bool, "speeches": bool} per cached report.

    Speeches are complete when the XML was parsed (``xml_speech_count`` is
    present). Votes are complete when the report's vote acquisition state is
    ``complete``. A legacy report without an ``acquisition`` block (the bulk
    of the cache as of 2026-09-19) carries no signal against the votes the
    store holds and counts as complete; A1 reads the state the build writes.
    """
    result: dict[str, dict[str, bool]] = {}
    for report in reports:
        protocol = report.get("protocol") or {}
        number = protocol.get("dokumentnummer")
        if not number:
            continue
        summary = report.get("validation_summary") or {}
        speeches = summary.get("xml_speech_count") is not None
        acquisition = (report.get("acquisition") or {}).get("votes")
        if acquisition:
            votes = str(acquisition.get("acquisition_state")) == "complete"
        else:
            votes = True
        result[str(number)] = {"votes": votes, "speeches": speeches}
    return result


def load_completeness(data_dir: Path) -> dict[str, dict[str, bool]]:
    reports = []
    for path in sorted(data_dir.glob("plenarprotokoll-*.json")):
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, dict) and payload.get("protocol"):
            reports.append(payload)
    return completeness_from_reports(reports)


def week_is_complete(week: Week, completeness: Mapping[str, Mapping[str, bool]], domain: str) -> bool:
    """Every sitting of the week is complete for ``domain``; unknown sittings are not."""
    for protocol in week.protocols:
        state = completeness.get(str(protocol["document_number"]))
        if not state or not state.get(domain):
            return False
    return True


# ---------------------------------------------------------------------------
# Observation, percentile, baseline, selection, receipts (pure)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Observation:
    value: float
    denominator: int | None
    row: dict[str, Any]
    week_n: int


def _id_sort_key(value: Any) -> tuple[int, Any]:
    text = str(value)
    return (0, int(text)) if text.isdigit() else (1, text)


def candidate_rows(conn: sqlite3.Connection, metric: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Run the metric's SQL once; rows keyed by protocol id."""
    try:
        rows = conn.execute(metric["sql"]).fetchall()
    except sqlite3.Error as exc:
        raise FactsError(f"facts: metric {metric['id']} failed: {exc}") from exc
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        entry = dict(row)
        grouped.setdefault(str(entry["protocol_id"]), []).append(entry)
    return grouped


def observe(metric: Mapping[str, Any], rows: Iterable[Mapping[str, Any]]) -> Observation | None:
    """The week's max/min row; ties cite the lowest id; no rows, no observation."""
    candidates = [dict(row) for row in rows if row.get("value") is not None]
    if not candidates:
        return None
    sign = -1 if metric["direction"] == "max" else 1
    best = min(candidates, key=lambda row: (sign * float(row["value"]), _id_sort_key(row["id"])))
    denominator = best.get("denominator")
    return Observation(
        value=float(best["value"]),
        denominator=int(denominator) if denominator is not None else None,
        row=best,
        week_n=len(candidates),
    )


def percentile(value: float, prior: Iterable[float], direction: str) -> float | None:
    """Share of prior values strictly beaten in ``direction``; None without prior."""
    values = list(prior)
    if not values:
        return None
    if direction == "max":
        beaten = sum(1 for other in values if value > other)
    else:
        beaten = sum(1 for other in values if value < other)
    return beaten / len(values)


def format_percentile(value: float) -> str:
    """Floor to whole percent so a value short of the record never reads 100."""
    return str(int(math.floor(value * 100 + 1e-9)))


@dataclass(frozen=True)
class Baseline:
    kind: str
    entries: tuple[tuple[Week, float], ...]

    @property
    def values(self) -> list[float]:
        return [value for _, value in self.entries]

    @property
    def count(self) -> int:
        return len(self.entries)

    @property
    def from_week(self) -> Week | None:
        return self.entries[0][0] if self.entries else None

    @property
    def to_week(self) -> Week | None:
        return self.entries[-1][0] if self.entries else None


def baseline(
    history: Iterable[tuple[Week, float]],
    week: Week,
    min_history: int = MIN_HISTORY_WEEKS,
    *,
    force_all: bool = False,
) -> Baseline:
    """Prior observations of the same Wahlperiode, else all coverage (D5)."""
    prior = [(w, value) for w, value in history if w.key < week.key]
    same = [(w, value) for w, value in prior if w.wahlperiode == week.wahlperiode]
    if not force_all and len(same) >= min_history:
        return Baseline(kind="wp", entries=tuple(same))
    return Baseline(kind="all", entries=tuple(prior))


def coverage_starts(weeks: Iterable[Week]) -> dict[int, tuple[int, date]]:
    """Wahlperiode -> (lowest protocol number covered, first sitting date)."""
    starts: dict[int, tuple[int, date]] = {}
    for week in weeks:
        for protocol in week.protocols:
            number = protocol_number(protocol["document_number"])
            day = date.fromisoformat(str(protocol["date"])[:10])
            current = starts.get(week.wahlperiode)
            if current is None or (number, day) < current:
                starts[week.wahlperiode] = (number, day)
    return starts


def baseline_label(base: Baseline, week: Week, starts: Mapping[int, tuple[int, date]]) -> str:
    """"seit Beginn der 21. Wahlperiode" when the population's Wahlperiode is
    covered from its protocol 1, else "seit <Monat Jahr>" of the coverage
    start (WP20 starts at 20/14: "seit Januar 2022"). A ``wp`` baseline
    names the week's Wahlperiode, an ``all`` baseline the earliest covered
    one (D12)."""
    if not starts:
        return ""
    wp = week.wahlperiode if base.kind == "wp" else min(starts)
    number, day = starts[wp]
    if number == 1:
        return f"seit Beginn der {wp}. Wahlperiode"
    return f"seit {MONTHS_DE[day.month - 1]} {day.year}"


def select_winner(rows: Iterable[Mapping[str, Any]]) -> str | None:
    """Highest percentile among eligible rows; ties to the lowest tie_rank."""
    eligible = [row for row in rows if row.get("eligible") and row.get("percentile") is not None]
    if not eligible:
        return None
    best = min(eligible, key=lambda row: (-float(row["percentile"]), int(row["tie_rank"])))
    return str(best["metric_id"])


def is_synthetic_rede_id(rede_id: Any, protocol_id: Any) -> bool:
    """persist_dip_pulse_store fills "<protocol_id>:<agenda_item_id>:<sequence>"
    when the XML carries no rede id."""
    return not rede_id or str(rede_id).startswith(f"{protocol_id}:")


def receipts(
    metric: Mapping[str, Any],
    observation: Observation,
    documents: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """fact_sources rows keyed (document_number, rede_id), or the page anchor
    (document_number, page, page_quadrant) for synthetic ids (D14)."""
    row = observation.row
    if metric["coverage"] == "speeches":
        synthetic = is_synthetic_rede_id(row.get("rede_id"), row.get("protocol_id"))
        return [
            {
                "entity_kind": "speech",
                "document_number": row["document_number"],
                "rede_id": None if synthetic else row["rede_id"],
                "page": row.get("page") if synthetic else None,
                "page_quadrant": row.get("page_quadrant") if synthetic else None,
                "official_url": row.get("pdf_url"),
                "position": 0,
            }
        ]
    result = [
        {
            "entity_kind": "vote",
            "document_number": row["document_number"],
            "rede_id": None,
            "page": None,
            "page_quadrant": None,
            "official_url": row.get("detail_url"),
            "position": 0,
        }
    ]
    ordered = sorted(documents, key=lambda doc: int(doc["id"]))
    for position, doc in enumerate(ordered, start=1):
        result.append(
            {
                "entity_kind": "document",
                "document_number": doc["document_number"],
                "rede_id": None,
                "page": None,
                "page_quadrant": None,
                "official_url": doc.get("url") or None,
                "position": position,
            }
        )
    return result


def vote_documents(conn: sqlite3.Connection, vote_id: Any) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            "SELECT d.id, d.document_number, d.url FROM vote_documents vd "
            "JOIN documents d ON d.id = vd.document_id WHERE vd.vote_id = ? ORDER BY d.id",
            (str(vote_id),),
        ).fetchall()
    ]


# ---------------------------------------------------------------------------
# The engine core: one row per metric per sitting week
# ---------------------------------------------------------------------------


def _citation(metric: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    if metric["coverage"] == "speeches":
        return {
            "id": row["id"],
            "document_number": row["document_number"],
            "rede_id": row.get("rede_id"),
            "display_name": row.get("display_name"),
            "fraktion": speaker_party({"fraktion": row.get("fraktion")}),
        }
    return {
        "id": row["id"],
        "document_number": row["document_number"],
        "title": row.get("title"),
        "date": row.get("date"),
        "yes_count": int(row.get("yes_count") or 0),
        "no_count": int(row.get("no_count") or 0),
    }


def compute(
    conn: sqlite3.Connection,
    registry: Iterable[Mapping[str, Any]],
    completeness: Mapping[str, Mapping[str, bool]],
    *,
    built: Iterable[str] = ("votes",),
    force_all: bool = False,
) -> list[dict[str, Any]]:
    """All fact rows, oldest week first, metrics in tie_rank order.

    ``force_all`` replays the rule with the all-coverage baseline everywhere
    (the A0 wp-vs-all comparison); it never applies in a real build.
    """
    built_set = set(built)
    weeks = sitting_weeks(load_protocols(conn))
    starts = coverage_starts(weeks)

    rows: list[dict[str, Any]] = []
    for metric in sorted(registry, key=lambda m: int(m["tie_rank"])):
        if metric.get("depends_on") and metric["depends_on"] not in built_set:
            continue
        candidates = candidate_rows(conn, metric)
        history: list[tuple[Week, float]] = []
        for week in weeks:
            complete = week_is_complete(week, completeness, metric["coverage"])
            row: dict[str, Any] = {
                "metric_id": metric["id"],
                "metric_version": metric["version"],
                "tie_rank": metric["tie_rank"],
                "direction": metric["direction"],
                "iso_year": week.key[0],
                "iso_week": week.key[1],
                "week": week.label,
                "wahlperiode": week.wahlperiode,
                "complete": int(complete),
                "week_n": None,
                "value": None,
                "denominator": None,
                "baseline_kind": None,
                "baseline_count": None,
                "baseline_from": None,
                "baseline_to": None,
                "baseline_label": None,
                "percentile": None,
                "eligible": 0,
                "selected": 0,
                "citation": None,
                "receipts": [],
            }
            if complete:
                week_rows = [r for pid in week.protocol_ids for r in candidates.get(pid, [])]
                observation = observe(metric, week_rows)
                row["week_n"] = len(week_rows)
                if observation is not None:
                    base = baseline(history, week, int(metric["min_history_weeks"]), force_all=force_all)
                    pct = percentile(observation.value, base.values, metric["direction"])
                    row.update(
                        {
                            "value": observation.value,
                            "denominator": observation.denominator,
                            "baseline_kind": base.kind,
                            "baseline_count": base.count,
                            "baseline_from": base.from_week.label if base.from_week else None,
                            "baseline_to": base.to_week.label if base.to_week else None,
                            "baseline_label": baseline_label(base, week, starts),
                            "percentile": pct,
                            "eligible": int(base.count >= int(metric["min_history_weeks"])),
                            "citation": _citation(metric, observation.row),
                        }
                    )
                    documents = (
                        vote_documents(conn, observation.row["id"])
                        if metric["coverage"] == "votes"
                        else ()
                    )
                    row["receipts"] = receipts(metric, observation, documents)
                    history.append((week, observation.value))
            rows.append(row)

    by_week: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in rows:
        by_week.setdefault((row["iso_year"], row["iso_week"]), []).append(row)
    for week_rows in by_week.values():
        winner = select_winner(week_rows)
        for row in week_rows:
            row["selected"] = int(row["metric_id"] == winner) if winner else 0
    rows.sort(key=lambda r: (r["iso_year"], r["iso_week"], r["tie_rank"]))
    return rows


# ---------------------------------------------------------------------------
# Card copy (D12) and the SVG card (D7)
# ---------------------------------------------------------------------------


def headline(row: Mapping[str, Any]) -> str:
    citation = row["citation"] or {}
    if row["metric_id"] == "knappste-abstimmung":
        return f"{format_int(citation['yes_count'])} : {format_int(citation['no_count'])}"
    return f"{format_int(int(row['value']))} Zeichen"


def card_title(row: Mapping[str, Any]) -> str:
    citation = row["citation"] or {}
    if row["metric_id"] == "knappste-abstimmung":
        return f"„{citation.get('title') or 'ohne Titel'}“"
    return f"{citation.get('display_name') or 'Unbekannt'} ({citation.get('fraktion') or 'Unbekannt'})"


def comparison_clause(row: Mapping[str, Any]) -> str:
    if row.get("percentile") is None or not row.get("eligible"):
        return "noch nicht vergleichbar"
    pct = format_percentile(float(row["percentile"]))
    label = row.get("baseline_label") or ""
    if row["metric_id"] == "knappste-abstimmung":
        return f"knapper als {pct} % der wöchentlich knappsten Abstimmungen {label}".rstrip()
    return f"länger als {pct} % der wöchentlichen Spitzenreden {label}".rstrip()


def card_sentence(row: Mapping[str, Any]) -> str:
    citation = row["citation"] or {}
    if row["metric_id"] == "knappste-abstimmung":
        lead = (
            f"Die knappste Abstimmung der Woche: {format_int(citation['yes_count'])} zu "
            f"{format_int(citation['no_count'])} zu {card_title(row)}"
        )
    else:
        lead = (
            f"Die längste Rede der Woche: {format_int(int(row['value']))} Zeichen von "
            f"{card_title(row)}"
        )
    return f"{lead}, {comparison_clause(row)}."


def wrap_lines(text: str, width: int, max_lines: int) -> list[str]:
    """textwrap into at most ``max_lines`` lines; the cut ends on a word
    boundary followed by an ellipsis that still fits the width."""
    lines = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
    if len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    words = kept[-1].split()
    while words and len(" ".join(words)) + 1 > width:
        words.pop()
    kept[-1] = (" ".join(words) + "…") if words else "…"
    return kept


CARD_SIZE = 1080
CARD_MARGIN = 80
CARD_FONT = "Helvetica Neue, Arial, sans-serif"
CARD_INK = "#171a1f"
CARD_MUTED = "#606a78"
CARD_PAPER = "#f7f8fa"
CARD_BLUE = "#174ea6"


def _text_block(
    lines: list[str], *, x: int, y: int, size: int, line_height: int, fill: str, css_class: str, weight: str = "normal"
) -> str:
    spans = "".join(
        f'<tspan x="{x}" dy="{0 if index == 0 else line_height}">{escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return (
        f'<text class="{css_class}" x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}">{spans}</text>'
    )


def render_card(row: Mapping[str, Any]) -> str:
    """1080x1080 SVG: eyebrow, metric label, headline number in its own
    element, title (<=3 lines), comparison clause (<=3 lines), footer.
    Plain fills, no filters or gradients; deterministic for byte-identical
    reruns (no timestamps)."""
    metric = REGISTRY_BY_ID[row["metric_id"]]
    x = CARD_MARGIN
    eyebrow = f"FAKT DER WOCHE · KW {row['iso_week']}/{row['iso_year']}"
    title_lines = wrap_lines(card_title(row), width=36, max_lines=3)
    comparison_lines = wrap_lines(comparison_clause(row), width=44, max_lines=3)
    count = row.get("baseline_count") or 0
    footer = f"Vergleich: {format_int(count)} Sitzungswochen"
    if row.get("baseline_from") and row.get("baseline_to"):
        footer += f" ({row['baseline_from']} bis {row['baseline_to']})"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_SIZE}" height="{CARD_SIZE}" '
        f'viewBox="0 0 {CARD_SIZE} {CARD_SIZE}" font-family="{CARD_FONT}">',
        f'<rect width="{CARD_SIZE}" height="{CARD_SIZE}" fill="{CARD_PAPER}"/>',
        f'<rect x="{x}" y="{x}" width="{CARD_SIZE - 2 * x}" height="8" fill="{CARD_BLUE}"/>',
        _text_block([eyebrow], x=x, y=150, size=30, line_height=0, fill=CARD_MUTED, css_class="eyebrow", weight="bold"),
        _text_block([metric["title"]], x=x, y=215, size=40, line_height=0, fill=CARD_INK, css_class="label"),
        _text_block([headline(row)], x=x, y=380, size=110, line_height=0, fill=CARD_BLUE, css_class="headline", weight="bold"),
        _text_block(title_lines, x=x, y=470, size=46, line_height=58, fill=CARD_INK, css_class="title"),
        _text_block(comparison_lines, x=x, y=700, size=40, line_height=52, fill=CARD_INK, css_class="comparison"),
        _text_block([footer], x=x, y=940, size=26, line_height=0, fill=CARD_MUTED, css_class="footer"),
        f'<text class="site" x="{CARD_SIZE - x}" y="990" font-size="30" font-weight="bold" '
        f'fill="{CARD_BLUE}" text-anchor="end">Bundestag-Puls</text>',
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def card_filename(row: Mapping[str, Any]) -> str:
    return f"{row['iso_year']}-W{row['iso_week']:02d}.svg"


def write_cards(rows: Iterable[Mapping[str, Any]], cards_dir: Path) -> list[Path]:
    """One SVG per selected row; returns the written paths (sorted)."""
    cards_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for row in rows:
        if not row.get("selected"):
            continue
        path = cards_dir / card_filename(row)
        path.write_bytes(render_card(row).encode("utf-8"))
        written.append(path)
    return sorted(written)


# ---------------------------------------------------------------------------
# Read-only replay (A0) and the 15A gate numbers
# ---------------------------------------------------------------------------


def open_readonly(store: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{store.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    return cov / math.sqrt(var_x * var_y)


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def gate_numbers(
    week_reports: list[dict[str, Any]],
    all_week_reports: list[dict[str, Any]],
    recent: int = 10,
) -> dict[str, Any]:
    """The 15A criteria over the replayed weeks."""
    winners = [w["selected_row"] for w in week_reports if w["selected_row"]]
    speakers = Counter(
        (row["citation"] or {}).get("display_name")
        for row in winners
        if row["metric_id"] == "laengste-rede"
    )
    wins = Counter(row["metric_id"] for row in winners)
    wins["kein Fakt"] = sum(1 for w in week_reports if not w["selected_row"])

    changed = 0
    compared = 0
    for rule_week, all_week in zip(week_reports, all_week_reports):
        rule_id = rule_week["selected"]
        all_id = all_week["selected"]
        if rule_id is None and all_id is None:
            continue
        compared += 1
        if rule_id != all_id:
            changed += 1

    vs_week_n: dict[str, Any] = {}
    for metric in REGISTRY:
        observed = [
            w["metrics"][metric["id"]]
            for w in week_reports
            if metric["id"] in w["metrics"] and w["metrics"][metric["id"]]["value"] is not None
        ]
        eligible = [r for r in observed if r["eligible"]]
        xs = [float(r["week_n"]) for r in eligible]
        ys = [float(r["percentile"]) for r in eligible]
        entry: dict[str, Any] = {
            "weeks_observed": len(observed),
            "weeks_eligible": len(eligible),
            "pearson_week_n_vs_percentile": _pearson(xs, ys),
        }
        if eligible:
            median = _median(xs)
            above = [r for r in eligible if r["week_n"] > median]
            below = [r for r in eligible if r["week_n"] <= median]
            entry["median_week_n"] = median
            entry["won_above_median"] = (sum(1 for r in above if r["selected"]), len(above))
            entry["won_at_or_below_median"] = (sum(1 for r in below if r["selected"]), len(below))
        vs_week_n[metric["id"]] = entry

    recent_cards = [card_sentence(row) for row in reversed(winners)][:recent]
    return {
        "max_cards_per_speaker": max(speakers.values()) if speakers else 0,
        "cards_per_speaker": dict(speakers.most_common()),
        "wins_per_metric": dict(wins),
        "changed_wp_vs_all": (changed, compared),
        "winners_vs_week_n": vs_week_n,
        "recent_cards": recent_cards,
    }


def _week_reports(rows: list[dict[str, Any]], weeks: int) -> list[dict[str, Any]]:
    by_week: dict[tuple[int, int], dict[str, Any]] = {}
    for row in rows:
        key = (row["iso_year"], row["iso_week"])
        entry = by_week.setdefault(
            key,
            {"key": key, "label": row["week"], "wahlperiode": row["wahlperiode"], "metrics": {}, "selected": None, "selected_row": None},
        )
        entry["metrics"][row["metric_id"]] = row
        if row["selected"]:
            entry["selected"] = row["metric_id"]
            entry["selected_row"] = row
    ordered = [by_week[key] for key in sorted(by_week)]
    return ordered[-weeks:] if weeks else ordered


def replay(
    store: Path,
    *,
    weeks: int,
    cards_dir: Path | None,
    completeness: Mapping[str, Mapping[str, bool]] | None = None,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    """Compute every week read-only, write the last ``weeks`` winners as SVGs
    and return the replay table plus the gate numbers."""
    if completeness is None:
        completeness = load_completeness(data_dir or store.parent)
    conn = open_readonly(store)
    try:
        built = {"votes"} if conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0] else set()
        rows = compute(conn, REGISTRY, completeness, built=built)
        rows_all = compute(conn, REGISTRY, completeness, built=built, force_all=True)
        unlinked = conn.execute(
            "SELECT COUNT(*) FROM votes v WHERE NOT EXISTS "
            "(SELECT 1 FROM agenda_item_votes aiv WHERE aiv.vote_id = v.id)"
        ).fetchone()[0]
    finally:
        conn.close()
    week_reports = _week_reports(rows, weeks)
    all_week_reports = _week_reports(rows_all, weeks)
    written: list[Path] = []
    if cards_dir is not None:
        selected = [w["selected_row"] for w in week_reports if w["selected_row"]]
        written = write_cards(selected, cards_dir)
    return {
        "store": str(store),
        "weeks": week_reports,
        "weeks_total": len({(r["iso_year"], r["iso_week"]) for r in rows}),
        "unlinked_votes": int(unlinked),
        "built": sorted(built),
        "gate": gate_numbers(week_reports, all_week_reports),
        "cards": [str(path) for path in written],
        "rows": rows,
    }


def _fmt_value(row: Mapping[str, Any]) -> str:
    if row["value"] is None:
        return "-"
    if row["metric_id"] == "knappste-abstimmung":
        citation = row["citation"] or {}
        return f"{citation.get('yes_count')}:{citation.get('no_count')} ({row['value']:.3f})"
    return format_int(int(row["value"]))


def _fmt_cited(row: Mapping[str, Any]) -> str:
    citation = row.get("citation") or {}
    if row["metric_id"] == "knappste-abstimmung":
        title = str(citation.get("title") or "")
        return f"{citation.get('document_number')} Abstimmung {citation.get('id')} {title[:60]}"
    return f"{citation.get('document_number')} {citation.get('rede_id')} {citation.get('display_name')} ({citation.get('fraktion')})"


def print_report(report: dict[str, Any], out=sys.stdout) -> None:
    metrics = [m["id"] for m in sorted(REGISTRY, key=lambda m: int(m["tie_rank"]))]
    short = {"knappste-abstimmung": "knappste", "laengste-rede": "laengste"}
    header = ["week", "WP", "compl(v/s)"]
    for metric_id in metrics:
        tag = short[metric_id]
        header += [f"{tag}_n", f"{tag}_value", f"{tag}_pct", f"{tag}_base"]
    header += ["selected", "cited"]
    lines = [" | ".join(header)]
    for week in report["weeks"]:
        complete = week["metrics"]
        votes_flag = complete.get("knappste-abstimmung", {}).get("complete", "-")
        speech_flag = complete.get("laengste-rede", {}).get("complete", "-")
        cells = [week["label"], str(week["wahlperiode"]), f"{votes_flag}/{speech_flag}"]
        for metric_id in metrics:
            row = week["metrics"].get(metric_id)
            if row is None:
                cells += ["-", "-", "-", "-"]
                continue
            pct = "-" if row["percentile"] is None else format_percentile(row["percentile"]) + ("" if row["eligible"] else "*")
            base = "-" if row["baseline_kind"] is None else f"{row['baseline_kind']}/{row['baseline_count']}"
            cells += [str(row["week_n"] if row["week_n"] is not None else "-"), _fmt_value(row), pct, base]
        selected_row = week["selected_row"]
        cells += [week["selected"] or "-", _fmt_cited(selected_row) if selected_row else "-"]
        lines.append(" | ".join(cells))
    print("\n".join(lines), file=out)
    print(file=out)
    print(f"store: {report['store']}  (read-only; {report['weeks_total']} sitting weeks; built: {', '.join(report['built']) or 'none'})", file=out)
    print(f"unlinked votes (no agenda link, excluded): {report['unlinked_votes']}", file=out)
    print("* = noch nicht vergleichbar (fewer than 8 prior weeks)", file=out)
    print(file=out)
    gate = report["gate"]
    print("Gate (15A):", file=out)
    print(f"  1. max cards per speaker: {gate['max_cards_per_speaker']}  {gate['cards_per_speaker']}", file=out)
    print(f"  2. wins per metric: {gate['wins_per_metric']}", file=out)
    changed, compared = gate["changed_wp_vs_all"]
    share = f"{changed / compared:.2f}" if compared else "n/a"
    print(f"  3. winners changed wp -> all: {changed} of {compared} ({share})", file=out)
    print("  4. winners vs week_n:", file=out)
    for metric_id, entry in gate["winners_vs_week_n"].items():
        r = entry.get("pearson_week_n_vs_percentile")
        r_text = "n/a" if r is None else f"{r:+.2f}"
        contingency = ""
        if "median_week_n" in entry:
            above = entry["won_above_median"]
            below = entry["won_at_or_below_median"]
            contingency = (
                f"; median week_n {entry['median_week_n']:g}: won {above[0]}/{above[1]} above, "
                f"{below[0]}/{below[1]} at or below"
            )
        print(
            f"     {metric_id}: {entry['weeks_observed']} observed, {entry['weeks_eligible']} eligible, "
            f"pearson(week_n, percentile) = {r_text}{contingency}",
            file=out,
        )
    print("  5. the 10 most recent cards (newest first):", file=out)
    for index, sentence in enumerate(gate["recent_cards"], start=1):
        print(f"     {index:2d}. {sentence}", file=out)
    if report["cards"]:
        print(file=out)
        print(f"cards: {len(report['cards'])} SVGs in {Path(report['cards'][0]).parent}", file=out)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fakt der Woche: read-only replay (A0).")
    parser.add_argument("--replay", type=int, metavar="N", required=True, help="print the last N sitting weeks")
    parser.add_argument("--cards", type=Path, metavar="DIR", help="write the selected weeks' SVG cards here")
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE, help=f"live store (default {DEFAULT_STORE})")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="directory with the cached plenarprotokoll-*.json (default: next to the store)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.store.exists():
        print(f"facts: store not found: {args.store}", file=sys.stderr)
        return 2
    try:
        report = replay(args.store, weeks=args.replay, cards_dir=args.cards, data_dir=args.data_dir)
    except FactsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
