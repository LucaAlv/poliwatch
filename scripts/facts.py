#!/usr/bin/env python3
"""Fakt der Woche: the facts rule over the live store.

The metric registry, the rule as pure functions, the persistence engine
(``compute_and_store``) the build calls before the Daten export, and a
read-only replay that writes sample SVG cards. This module renders no pages:
it writes the rows ``scripts/features/facts.py`` (T6) will read.

The rule (plan D5/D10/D12/D20/D21/D24,
~/.gstack/projects/LucaAlv-poliwatch/fakt-der-woche-plan.md):

* A period is an ISO sitting week (``period_kind`` "week", ``period_key``
  "2026-W37"); its Wahlperiode comes from the protocols' ``document_number``
  prefix ("21/94" -> 21). D24 reserves "month" for T11; only weeks are built.
* Each metric yields at most one observation per period -- the period's max or
  min over its candidate rows, or their count for a counting metric -- and only
  when the period is complete for the metric's coverage domain (votes: every
  sitting's vote acquisition is ``complete``; speeches: every sitting's XML was
  parsed). Incomplete periods yield no observation and never enter anyone's
  history.
* The percentile is the share of *prior* observations the value strictly beats
  in the metric's direction (max: greater, min: smaller). Prior means strictly
  before the period, so later periods never change an earlier row.
* The baseline is the same Wahlperiode when it holds at least
  ``min_history_weeks`` (8) prior observations, else all coverage; fewer than 8
  in all coverage makes the period ineligible ("noch nicht vergleichbar").
* A fact is **publishable** when it is eligible and its percentile reaches
  ``PUBLICATION_FLOOR`` (0,50): more unusual than half its comparison
  population (D20). Every publishable fact is posted, no cap (D21); ``rank``
  orders the period's publishable rows by percentile desc, then ``tie_rank``
  asc. A period with no publishable fact gets no card.

Replay: ``python3 scripts/facts.py --replay 30 --cards DIR [--store PATH]``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
import textwrap
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Sequence
from xml.sax.saxutils import escape

from render_dip_pulse_html import agenda_topic, format_int, iso_week_key, speaker_party


class FactsError(RuntimeError):
    """A protocol or metric the rule cannot process (build-aborting)."""


MIN_HISTORY_WEEKS = 8
# D20: a fact is posted only when it is more unusual than half its comparison
# population. Measured on the A0 replay (30 weeks): 50 keeps 20 weeks, 25 keeps
# 25, 75 keeps 12. The human rejected the two 0 % cards outright.
PUBLICATION_FLOOR = 0.50
DEFAULT_STORE = Path(".context/dip-pulse-site/data/bundestag-pulse.sqlite")

# A metric may not be read without its caveat, so the registry carries it and
# validate_registry() refuses to run without one. D27 named the first two; the
# two vote metrics were added on 2026-09-22 after the replay measured an
# opportunity-count effect on both of them (see their caveat text).
REQUIRED_CAVEATS = (
    "knappste-abstimmung",
    "meiste-abweichler",
    "erste-reden",
)

# Why a period has no card for a metric, in the order the engine decides it.
# Stored in ``facts.withheld`` (NULL when the fact is posted) so the archive
# can say which of them applies instead of lumping everything into "kein Fakt".
WITHHELD_NO_OBSERVATION = "no_observation"
WITHHELD_NOT_COMPARABLE = "not_comparable"
WITHHELD_BELOW_MIN_VALUE = "below_min_value"
WITHHELD_NO_TOPIC = "no_topic"
WITHHELD_BELOW_FLOOR = "below_floor"

# The lead proceeding of an agenda item, by the same rule topic_identity uses:
# a Gesetzgebung position first, then the lowest proceeding_positions.id. Shared
# verbatim by the two metrics that name a topic; each metric's ``sql`` stays a
# complete, runnable statement because it is what the week page shows.
_LEAD_POSITION_CTE = (
    "WITH ranked_positions AS (\n"
    "  SELECT pp.agenda_item_id AS agenda_item_id, pp.title AS title,\n"
    "         (CASE WHEN pp.proceeding_type = 'Gesetzgebung' THEN 0 ELSE 1 END) * 100000000000\n"
    "           + CAST(pp.id AS INTEGER) AS ord\n"
    "  FROM proceeding_positions pp\n"
    "  WHERE pp.agenda_item_id IS NOT NULL AND TRIM(COALESCE(pp.title, '')) <> ''\n"
    "),\n"
    "lead_position AS (\n"
    "  SELECT agenda_item_id, title, MIN(ord) AS ord FROM ranked_positions GROUP BY agenda_item_id\n"
    ")\n"
)

# "09:00" and "9:00" both occur in xml_header_json; a sitting that runs past
# midnight ends before it starts (13 of 290 protocols on 2026-09-19), so the
# difference wraps through +1440 minutes.
def _minutes_of(expression: str) -> str:
    return (
        f"CAST(substr({expression}, 1, instr({expression}, ':') - 1) AS INTEGER) * 60\n"
        f"           + CAST(substr({expression}, instr({expression}, ':') + 1) AS INTEGER)"
    )


_SITZUNG_START = "json_extract(p.xml_header_json, '$.sitzung_start')"
_SITZUNG_END = "json_extract(p.xml_header_json, '$.sitzung_end')"

# The registry mirrors RECIPES (build_dip_pulse_site.py). ``sql`` lists every
# candidate row with the protocol it belongs to; ``compute`` groups the rows
# into periods and applies ``direction`` (or ``aggregation`` "count", which
# observes how many rows the period has). ``coverage`` names the completeness
# domain a period must be complete for; ``depends_on`` the build component that
# must exist for the metric to run at all; ``receipt`` the fact_sources shape.
REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "id": "knappste-abstimmung",
        "version": 1,
        "title": "Die knappste Abstimmung der Woche",
        "unit": "Anteil der Stimmendifferenz an Ja+Nein",
        "direction": "min",
        "aggregation": "extreme",
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
        "receipt": "vote",
        "min_value": None,
        "requires_topic": False,
        "caveat": (
            "Verglichen werden nur die namentlichen Abstimmungen. Je mehr eine Woche davon "
            "hat, desto knapper fällt die knappste im Schnitt aus (gemessen über 58 "
            "vergleichbare Wochen), ein hoher Prozentwert sagt also auch etwas über die "
            "Zahl der Abstimmungen."
        ),
    },
    {
        "id": "meiste-abweichler",
        "version": 1,
        "title": "Die meisten Abweichler der Woche",
        "unit": "Abgeordnete gegen die Linie ihrer Fraktion",
        "direction": "max",
        "aggregation": "extreme",
        # An abweichlerin votes the opposite way of her Fraktion's
        # leading_vote. Enthaltung and Abwesenheit are not a counter-vote and
        # do not count (the Suizidhilfe vote reads 179 this way, 202 with
        # Enthaltungen); fraktionslose Abgeordnete have no Fraktionslinie to
        # break, so the pseudo-Fraktion "fraktionslos" is excluded (151 of its
        # members' votes would otherwise count as deviations).
        "sql": (
            "SELECT v.id, v.title, v.date, v.detail_url,\n"
            "       CASE WHEN EXISTS (SELECT 1 FROM vote_members vm0 WHERE vm0.vote_id = v.id) THEN (\n"
            "         SELECT COUNT(*) FROM vote_members vm\n"
            "         JOIN vote_fractions vf ON vf.vote_id = vm.vote_id AND vf.party_id = vm.party_id\n"
            "         JOIN parties pa ON pa.id = vm.party_id\n"
            "         WHERE vm.vote_id = v.id\n"
            "           AND vm.vote IN ('yes', 'no') AND vf.leading_vote IN ('yes', 'no')\n"
            "           AND vm.vote <> vf.leading_vote AND pa.name <> 'fraktionslos'\n"
            "       ) END AS value,\n"
            "       (SELECT COUNT(*) FROM vote_members vm3\n"
            "         WHERE vm3.vote_id = v.id AND vm3.vote IN ('yes', 'no')) AS denominator,\n"
            "       p.id AS protocol_id, p.document_number, MIN(p.date) AS protocol_date\n"
            "FROM votes v\n"
            "JOIN agenda_item_votes aiv ON aiv.vote_id = v.id\n"
            "JOIN agenda_items ai ON ai.id = aiv.agenda_item_id\n"
            "JOIN protocols p ON p.id = ai.protocol_id\n"
            "GROUP BY v.id"
        ),
        "min_history_weeks": MIN_HISTORY_WEEKS,
        "tie_rank": 2,
        "depends_on": "votes",
        "coverage": "votes",
        "receipt": "vote",
        # The metric is zero-inflated: 21 of the 66 observed weeks read 0, so a
        # single Abweichlerin already beats two thirds of them. Two of the 19
        # cards this metric would post read "1 Abgeordnete", which is an
        # anecdote, not a fact; a floor of three drops exactly those two and
        # keeps the other 17 (values 3 to 179).
        "min_value": 3,
        "requires_topic": False,
        "caveat": (
            "Bei Gewissensfragen gibt es keine Fraktionslinie. Gezählt wird, wer anders "
            "stimmt als die Mehrheit der eigenen Fraktion; Enthaltungen und Abwesenheit "
            "zählen nicht, fraktionslose Abgeordnete bleiben außen vor. Je mehr "
            "namentliche Abstimmungen eine Woche hat, desto mehr Abweichungen sind zu "
            "erwarten."
        ),
    },
    {
        "id": "laengste-debatte",
        "version": 1,
        "title": "Die längste Debatte der Woche",
        "unit": "Zeichen",
        "direction": "max",
        "aggregation": "extreme",
        "sql": (
            _LEAD_POSITION_CTE
            + "SELECT ai.id, ai.heading, ai.page_start AS page,\n"
            "       ai.page_start_quadrant AS page_quadrant,\n"
            "       SUM(s.char_count) AS value, COUNT(*) AS denominator,\n"
            "       lp.title AS proceeding_title,\n"
            "       p.id AS protocol_id, p.document_number, p.pdf_url\n"
            "FROM agenda_items ai\n"
            "JOIN speeches s ON s.agenda_item_id = ai.id\n"
            "JOIN protocols p ON p.id = ai.protocol_id\n"
            "LEFT JOIN lead_position lp ON lp.agenda_item_id = ai.id\n"
            "GROUP BY ai.id\n"
            "HAVING SUM(s.char_count) > 0"
        ),
        "min_history_weeks": MIN_HISTORY_WEEKS,
        "tie_rank": 3,
        "depends_on": None,
        "coverage": "speeches",
        "receipt": "agenda_item",
        "min_value": None,
        # The topic *is* this card's subject: without it the card says only
        # that some Tagesordnungspunkt was long, which is not a fact a reader
        # can do anything with. 6 of the 48 cards this metric would post have
        # no topic (2026-W37, 2025-W39, 2025-W28, 2024-W37, 2023-W36,
        # 2022-W36); they are withheld rather than published nameless.
        "requires_topic": True,
        "caveat": None,
    },
    {
        "id": "laengste-rede",
        "version": 1,
        "title": "Die längste Rede der Woche",
        "unit": "Zeichen",
        "direction": "max",
        "aggregation": "extreme",
        "sql": (
            _LEAD_POSITION_CTE
            + "SELECT s.id, s.rede_id, s.page, s.page_quadrant, s.char_count AS value,\n"
            "       NULL AS denominator, m.display_name, pa.name AS fraktion,\n"
            "       ai.heading, lp.title AS proceeding_title,\n"
            "       p.id AS protocol_id, p.document_number, p.pdf_url\n"
            "FROM speeches s\n"
            "JOIN mps m ON m.id = s.mp_id\n"
            "LEFT JOIN parties pa ON pa.id = m.party_id\n"
            "JOIN protocols p ON p.id = s.protocol_id\n"
            "LEFT JOIN agenda_items ai ON ai.id = s.agenda_item_id\n"
            "LEFT JOIN lead_position lp ON lp.agenda_item_id = s.agenda_item_id\n"
            "WHERE s.mp_id IS NOT NULL"
        ),
        "min_history_weeks": MIN_HISTORY_WEEKS,
        "tie_rank": 4,
        "depends_on": None,
        "coverage": "speeches",
        "receipt": "speech",
        "min_value": None,
        "requires_topic": False,
        "caveat": None,
    },
    {
        "id": "laengste-sitzung",
        "version": 1,
        "title": "Die längste Sitzung der Woche",
        "unit": "Minuten",
        "direction": "max",
        "aggregation": "extreme",
        "sql": (
            "SELECT p.id, p.document_number, p.date, p.pdf_url, p.id AS protocol_id,\n"
            f"       {_SITZUNG_START} AS sitzung_start,\n"
            f"       {_SITZUNG_END} AS sitzung_end,\n"
            f"       CASE WHEN {_SITZUNG_START} LIKE '_%:__' AND {_SITZUNG_END} LIKE '_%:__'\n"
            f"         THEN (({_minutes_of(_SITZUNG_END)})\n"
            f"               - ({_minutes_of(_SITZUNG_START)}) + 1440) % 1440\n"
            "       END AS value,\n"
            "       NULL AS denominator\n"
            "FROM protocols p"
        ),
        "min_history_weeks": MIN_HISTORY_WEEKS,
        "tie_rank": 5,
        "depends_on": None,
        "coverage": "speeches",
        "receipt": "protocol",
        "min_value": None,
        "requires_topic": False,
        "caveat": None,
    },
    {
        "id": "erste-reden",
        "version": 1,
        "title": "Die meisten ersten Reden der Woche",
        "unit": "Abgeordnete mit ihrer ersten Rede",
        "direction": "max",
        "aggregation": "count",
        # Grouped by the XML speaker id, not by mps.id: the live store splits
        # one person across an "aw:" and an "xml:" mps row that share their
        # xml_redner_id (314 display names on the 2026-09-19 store), and
        # grouping by mps.id turned 4 debutants in 2026-W37 into 233. Every
        # mps row that carries a speech has an xml_redner_id (0 without).
        "sql": (
            "WITH speaker AS (\n"
            "  SELECT s.id AS speech_id, p.date AS day,\n"
            "         COALESCE(NULLIF(m.xml_redner_id, ''), 'mp#' || m.id) AS person_key\n"
            "  FROM speeches s\n"
            "  JOIN mps m ON m.id = s.mp_id\n"
            "  JOIN protocols p ON p.id = s.protocol_id\n"
            "  WHERE s.mp_id IS NOT NULL\n"
            "),\n"
            "first_day AS (\n"
            "  SELECT person_key, MIN(day) AS day FROM speaker GROUP BY person_key\n"
            "),\n"
            "first_speech AS (\n"
            "  SELECT sp.person_key AS person_key, MIN(sp.speech_id) AS speech_id\n"
            "  FROM speaker sp\n"
            "  JOIN first_day fd ON fd.person_key = sp.person_key AND fd.day = sp.day\n"
            "  GROUP BY sp.person_key\n"
            ")\n"
            "SELECT s.id, s.rede_id, s.page, s.page_quadrant, 1 AS value,\n"
            "       NULL AS denominator, m.display_name, pa.name AS fraktion,\n"
            "       p.id AS protocol_id, p.document_number, p.pdf_url\n"
            "FROM first_speech fs\n"
            "JOIN speeches s ON s.id = fs.speech_id\n"
            "JOIN mps m ON m.id = s.mp_id\n"
            "LEFT JOIN parties pa ON pa.id = m.party_id\n"
            "JOIN protocols p ON p.id = s.protocol_id"
        ),
        "min_history_weeks": MIN_HISTORY_WEEKS,
        "tie_rank": 6,
        "depends_on": None,
        "coverage": "speeches",
        "receipt": "speeches",
        # Every card this metric posts already reads 3 or more (3..60), so an
        # absolute floor would be a claim with nothing behind it.
        "min_value": None,
        "requires_topic": False,
        "caveat": (
            "Erste Rede in unserer Abdeckung seit Januar 2022, nicht zwingend die erste "
            "Rede im Bundestag."
        ),
    },
)
REGISTRY_BY_ID = {metric["id"]: metric for metric in REGISTRY}

MONTHS_DE = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)


def sql_sha256(metric: Mapping[str, Any]) -> str:
    """The metric's SQL fingerprint (D14): a changed statement changes the
    fact_metrics row, which changes the snapshot, which rewrites all three
    tables."""
    return hashlib.sha256(str(metric["sql"]).encode("utf-8")).hexdigest()


def validate_registry(registry: Iterable[Mapping[str, Any]] = REGISTRY) -> None:
    """Refuse to run a registry the rule cannot honour (D27)."""
    seen_ids: set[str] = set()
    seen_ranks: set[int] = set()
    for metric in registry:
        metric_id = str(metric.get("id") or "")
        if not metric_id or metric_id in seen_ids:
            raise FactsError(f"facts: duplicate or missing metric id {metric_id!r}")
        seen_ids.add(metric_id)
        rank = int(metric["tie_rank"])
        if rank in seen_ranks:
            raise FactsError(f"facts: metric {metric_id} repeats tie_rank {rank}")
        seen_ranks.add(rank)
        if metric.get("direction") not in ("max", "min"):
            raise FactsError(f"facts: metric {metric_id} has no direction")
        if metric.get("aggregation") not in ("extreme", "count"):
            raise FactsError(f"facts: metric {metric_id} has no aggregation")
        if metric.get("coverage") not in ("votes", "speeches"):
            raise FactsError(f"facts: metric {metric_id} has no coverage domain")
        if metric.get("min_value") is not None and metric["direction"] != "max":
            raise FactsError(
                f"facts: metric {metric_id} sets min_value on a min-direction metric, "
                "where a floor on the value would cut off the interesting end"
            )
        if metric.get("requires_topic") and metric.get("receipt") not in ("agenda_item", "speech"):
            raise FactsError(
                f"facts: metric {metric_id} requires a topic but its receipt names no agenda item"
            )
        if metric_id in REQUIRED_CAVEATS and not str(metric.get("caveat") or "").strip():
            raise FactsError(f"facts: metric {metric_id} must carry a caveat (D27)")

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

    # D24: facts carry a period, not a bare (iso_year, iso_week) pair. A
    # sitting week is the only period kind A1 step 2 builds; T11 adds "month"
    # with the identical rule over prior months.
    period_kind = "week"

    @property
    def period_key(self) -> str:
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


def completeness_from_entries(entries: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, bool]]:
    """The build's completeness map, from the in-memory dossier entries (D10).

    The build and the replay must agree on which weeks have a fact, so both
    derive the map with ``completeness_from_reports``: the build hands it the
    reports it is holding, the replay the same reports read back from
    ``data/plenarprotokoll-*.json``.
    """
    return completeness_from_reports(entry.get("report") or {} for entry in entries)


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
    #: Every row the observation rests on, lowest id first. An extreme metric
    #: cites one row; a counting metric (erste-reden) cites all of them.
    rows: tuple[dict[str, Any], ...] = ()


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
    """The period's observation, or None when it has no candidate row.

    ``aggregation`` "extreme" takes the max or min row and a row-level tie
    cites the lowest id; "count" takes how many rows the period has and cites
    every one of them.
    """
    candidates = [dict(row) for row in rows if row.get("value") is not None]
    if not candidates:
        return None
    ordered = sorted(candidates, key=lambda row: _id_sort_key(row["id"]))
    if metric.get("aggregation") == "count":
        return Observation(
            value=float(len(ordered)),
            denominator=None,
            row=ordered[0],
            week_n=len(ordered),
            rows=tuple(ordered),
        )
    sign = -1 if metric["direction"] == "max" else 1
    best = min(ordered, key=lambda row: (sign * float(row["value"]), _id_sort_key(row["id"])))
    denominator = best.get("denominator")
    return Observation(
        value=float(best["value"]),
        denominator=int(denominator) if denominator is not None else None,
        row=best,
        week_n=len(candidates),
        rows=(best,),
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


def withheld_reason(
    row: Mapping[str, Any],
    metric: Mapping[str, Any] | None = None,
    floor: float = PUBLICATION_FLOOR,
) -> str | None:
    """Why this fact is not posted, or None when it is.

    The relative floor (D20) is only the last gate. A metric may also set an
    absolute one: ``min_value``, below which the observation is an anecdote
    rather than a fact, and ``requires_topic``, for a card whose subject *is*
    the topic. Both were added on 2026-09-22 from the replay; both are registry
    data, so changing either is a one-line edit, not a rule change.
    """
    if row.get("value") is None:
        return WITHHELD_NO_OBSERVATION
    if not row.get("eligible") or row.get("percentile") is None:
        return WITHHELD_NOT_COMPARABLE
    if metric is None:
        metric = REGISTRY_BY_ID.get(str(row.get("metric_id")))
    if metric is not None:
        minimum = metric.get("min_value")
        if minimum is not None and float(row["value"]) < float(minimum):
            return WITHHELD_BELOW_MIN_VALUE
        if metric.get("requires_topic") and not (row.get("citation") or {}).get("topic"):
            return WITHHELD_NO_TOPIC
    if float(row["percentile"]) < floor:
        return WITHHELD_BELOW_FLOOR
    return None


def is_publishable(row: Mapping[str, Any], floor: float = PUBLICATION_FLOOR) -> bool:
    return withheld_reason(row, floor=floor) is None


def rank_period(
    rows: Iterable[MutableMapping[str, Any]],
    floor: float = PUBLICATION_FLOOR,
    metrics: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[MutableMapping[str, Any]]:
    """Set ``withheld``, ``publishable`` and ``rank`` on one period's rows in
    place (D21).

    Every publishable fact is posted; ``rank`` runs 1..n over them by
    percentile desc, then ``tie_rank`` asc. A withheld row keeps ``rank`` None
    and carries the reason, so the archive can say which gate applied instead
    of lumping every empty week into one "kein Fakt".
    """
    period_rows = list(rows)
    lookup = REGISTRY_BY_ID if metrics is None else metrics
    publishable: list[MutableMapping[str, Any]] = []
    for row in period_rows:
        reason = withheld_reason(row, lookup.get(str(row.get("metric_id"))), floor)
        row["withheld"] = reason
        row["publishable"] = int(reason is None)
        row["rank"] = None
        if row["publishable"]:
            publishable.append(row)
    publishable.sort(key=lambda row: (-float(row["percentile"]), int(row["tie_rank"])))
    for position, row in enumerate(publishable, start=1):
        row["rank"] = position
    return publishable


def is_synthetic_rede_id(rede_id: Any, protocol_id: Any) -> bool:
    """persist_dip_pulse_store fills "<protocol_id>:<agenda_item_id>:<sequence>"
    when the XML carries no rede id."""
    return not rede_id or str(rede_id).startswith(f"{protocol_id}:")


def _receipt(
    entity_kind: str,
    row: Mapping[str, Any],
    *,
    position: int,
    rede_id: Any = None,
    page: Any = None,
    page_quadrant: Any = None,
    official_url: Any = None,
) -> dict[str, Any]:
    return {
        "entity_kind": entity_kind,
        "document_number": row["document_number"],
        "rede_id": rede_id,
        "page": page,
        "page_quadrant": page_quadrant,
        "official_url": official_url,
        "position": position,
    }


def _speech_receipt(row: Mapping[str, Any], position: int) -> dict[str, Any]:
    """(document_number, rede_id), or the page anchor
    (document_number, page, page_quadrant) for a synthetic id (D14)."""
    synthetic = is_synthetic_rede_id(row.get("rede_id"), row.get("protocol_id"))
    return _receipt(
        "speech",
        row,
        position=position,
        rede_id=None if synthetic else row["rede_id"],
        page=row.get("page") if synthetic else None,
        page_quadrant=row.get("page_quadrant") if synthetic else None,
        official_url=row.get("pdf_url"),
    )


def receipts(
    metric: Mapping[str, Any],
    observation: Observation,
    documents: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """The fact's fact_sources rows, in ``position`` order.

    Every receipt cites a stable key, never a store row id, so a rebuilt store
    keeps pointing at the same primary source (D14). ``position`` 0 is the
    subject; anything after it is supporting material (a vote's Drucksachen,
    ordered by the lowest ``documents.id`` first).
    """
    kind = metric["receipt"]
    row = observation.row
    if kind == "speech":
        return [_speech_receipt(row, 0)]
    if kind == "speeches":
        return [_speech_receipt(entry, position) for position, entry in enumerate(observation.rows)]
    if kind == "agenda_item":
        return [
            _receipt(
                "agenda_item",
                row,
                position=0,
                page=row.get("page"),
                page_quadrant=row.get("page_quadrant"),
                official_url=row.get("pdf_url"),
            )
        ]
    if kind == "protocol":
        return [_receipt("protocol", row, position=0, official_url=row.get("pdf_url"))]
    if kind != "vote":
        raise FactsError(f"facts: metric {metric['id']} has unknown receipt kind {kind!r}")
    result = [_receipt("vote", row, position=0, official_url=row.get("detail_url"))]
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


def _citation(metric: Mapping[str, Any], observation: Observation) -> dict[str, Any]:
    """What the fact is *about*, for the replay and the sample cards.

    In-memory only: the store keeps the stable receipt keys (D2A/D14) and T6
    resolves the name, the Fraktion and the link at render time, so a rebuilt
    store never carries a stale display name.
    """
    row = observation.row
    citation: dict[str, Any] = {
        "id": row["id"],
        "document_number": row["document_number"],
    }
    kind = metric["receipt"]
    if kind in ("speech", "speeches"):
        citation.update(
            {
                "rede_id": row.get("rede_id"),
                "display_name": row.get("display_name"),
                "fraktion": speaker_party({"fraktion": row.get("fraktion")}),
                "topic": agenda_topic(row.get("proceeding_title"), row.get("heading")),
            }
        )
        if kind == "speeches":
            citation["speakers"] = [
                str(entry.get("display_name") or "Unbekannt") for entry in observation.rows
            ]
    elif kind == "agenda_item":
        citation.update(
            {
                "topic": agenda_topic(row.get("proceeding_title"), row.get("heading")),
                "heading": row.get("heading"),
                "speech_count": int(row.get("denominator") or 0),
            }
        )
    elif kind == "protocol":
        citation.update(
            {
                "date": row.get("date"),
                "sitzung_start": row.get("sitzung_start"),
                "sitzung_end": row.get("sitzung_end"),
            }
        )
    else:
        citation.update(
            {
                "title": row.get("title"),
                "date": row.get("date"),
                "yes_count": int(row.get("yes_count") or 0),
                "no_count": int(row.get("no_count") or 0),
                "denominator": int(row["denominator"]) if row.get("denominator") is not None else None,
            }
        )
    return citation


def compute(
    conn: sqlite3.Connection,
    registry: Iterable[Mapping[str, Any]],
    completeness: Mapping[str, Mapping[str, bool]],
    *,
    built: Iterable[str] = ("votes",),
    force_all: bool = False,
    floor: float = PUBLICATION_FLOOR,
) -> list[dict[str, Any]]:
    """All fact rows, oldest period first, metrics in tie_rank order.

    ``force_all`` replays the rule with the all-coverage baseline everywhere
    (the A0 wp-vs-all comparison) and ``floor`` moves the publication floor;
    neither applies in a real build.
    """
    registry = tuple(registry)
    validate_registry(registry)
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
                "period_kind": week.period_kind,
                "period_key": week.period_key,
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
                "withheld": WITHHELD_NO_OBSERVATION,
                "publishable": 0,
                "rank": None,
                "citation": None,
                "receipts": [],
            }
            if complete:
                week_rows = [r for pid in week.protocol_ids for r in candidates.get(pid, [])]
                observation = observe(metric, week_rows)
                # D12: how many observations the period's value was chosen
                # from. A candidate row whose value is NULL (a vote with no
                # member rows, a protocol whose XML names no sitting times)
                # is not an observation and does not count.
                row["week_n"] = observation.week_n if observation is not None else 0
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
                            "citation": _citation(metric, observation),
                        }
                    )
                    documents = (
                        vote_documents(conn, observation.row["id"])
                        if metric["receipt"] == "vote"
                        else ()
                    )
                    row["receipts"] = receipts(metric, observation, documents)
                    history.append((week, observation.value))
            rows.append(row)

    by_period: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        by_period.setdefault((row["period_kind"], row["period_key"]), []).append(row)
    metrics_by_id = {str(metric["id"]): metric for metric in registry}
    for period_rows in by_period.values():
        rank_period(period_rows, floor, metrics_by_id)
    rows.sort(key=lambda r: (r["period_kind"], r["iso_year"], r["iso_week"], r["tie_rank"]))
    return rows


# ---------------------------------------------------------------------------
# Persistence (T5): the three tables, the snapshot diff, the single-transaction
# replace and the changed-winners report.
#
# D1A/D14: the engine computes every row in memory on every build and writes
# only when the three-table snapshot differs. That no-write guarantee is what
# keeps an --offline rebuild from re-hashing a 291 MB store and re-exporting
# 19 CSVs for nothing. The three tables change as one unit: any difference
# replaces all three inside one transaction, so a crash mid-write leaves the
# previous rows intact.
# ---------------------------------------------------------------------------


FACTS_TABLES = ("fact_metrics", "facts", "fact_sources")

# D3A: the engine owns this schema. Nothing else creates these tables, and
# nothing has been persisted yet, so there is no migration path - only
# CREATE TABLE IF NOT EXISTS. "rank" is quoted because it doubles as a window
# function name.
FACTS_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS fact_metrics (
      id TEXT PRIMARY KEY,
      version INTEGER NOT NULL,
      title TEXT NOT NULL,
      unit TEXT NOT NULL,
      direction TEXT NOT NULL,
      aggregation TEXT NOT NULL,
      sql TEXT NOT NULL,
      sql_sha256 TEXT NOT NULL,
      min_history_weeks INTEGER NOT NULL,
      tie_rank INTEGER NOT NULL,
      depends_on TEXT,
      caveat TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS facts (
      id INTEGER PRIMARY KEY,
      metric_id TEXT NOT NULL REFERENCES fact_metrics(id) ON DELETE CASCADE,
      metric_version INTEGER NOT NULL,
      period_kind TEXT NOT NULL,
      period_key TEXT NOT NULL,
      iso_year INTEGER,
      iso_week INTEGER,
      wahlperiode INTEGER NOT NULL,
      complete INTEGER NOT NULL,
      week_n INTEGER,
      value REAL,
      denominator INTEGER,
      baseline_kind TEXT,
      baseline_count INTEGER,
      baseline_from TEXT,
      baseline_to TEXT,
      baseline_label TEXT,
      percentile REAL,
      eligible INTEGER NOT NULL,
      withheld TEXT,
      publishable INTEGER NOT NULL,
      "rank" INTEGER,
      UNIQUE(metric_id, period_kind, period_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fact_sources (
      fact_id INTEGER NOT NULL REFERENCES facts(id) ON DELETE CASCADE,
      entity_kind TEXT NOT NULL,
      document_number TEXT,
      rede_id TEXT,
      page INTEGER,
      page_quadrant TEXT,
      official_url TEXT,
      position INTEGER NOT NULL,
      PRIMARY KEY (fact_id, position)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_facts_period ON facts(period_kind, period_key)",
    "CREATE INDEX IF NOT EXISTS idx_facts_publishable ON facts(publishable, period_key)",
)

_METRIC_COLUMNS = (
    "id", "version", "title", "unit", "direction", "aggregation", "sql",
    "sql_sha256", "min_history_weeks", "tie_rank", "depends_on", "caveat",
)
_FACT_COLUMNS = (
    "metric_id", "metric_version", "period_kind", "period_key", "iso_year", "iso_week",
    "wahlperiode", "complete", "week_n", "value", "denominator", "baseline_kind",
    "baseline_count", "baseline_from", "baseline_to", "baseline_label", "percentile",
    "eligible", "withheld", "publishable", "rank",
)
_SOURCE_COLUMNS = (
    "entity_kind", "document_number", "rede_id", "page", "page_quadrant",
    "official_url", "position",
)


def _quoted(columns: Sequence[str]) -> str:
    """Column list for a statement; "rank" needs the quotes."""
    return ", ".join(f'"{column}"' for column in columns)


#: The columns each table must have for the engine to read or write it.
_EXPECTED_COLUMNS = {
    "fact_metrics": _METRIC_COLUMNS,
    "facts": ("id",) + _FACT_COLUMNS,
    "fact_sources": ("fact_id",) + _SOURCE_COLUMNS,
}


def _columns_of(conn: sqlite3.Connection, table: str) -> set[str] | None:
    """The table's column names, or None when it does not exist."""
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone():
        return None
    return {str(list(row)[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def ensure_tables(conn: sqlite3.Connection) -> None:
    """Create the three tables, dropping any left over from an older schema.

    The engine is the only writer and rewrites all three as one unit, so a
    table whose columns no longer match is worth nothing: dropping it is
    cheaper and safer than a migration, and the next write refills it. This is
    what keeps a store built by an earlier revision of the registry from
    failing the build with "no such column".
    """
    for table, expected in _EXPECTED_COLUMNS.items():
        columns = _columns_of(conn, table)
        if columns is not None and columns != set(expected):
            conn.execute(f"DROP TABLE {table}")
    for statement in FACTS_SCHEMA:
        conn.execute(statement)


def tables_exist(conn: sqlite3.Connection) -> bool:
    """True when all three tables exist *with the current schema*. A store
    written by an older registry reads as empty, so the engine rewrites it
    instead of reading columns that are no longer there."""
    return all(
        _columns_of(conn, table) == set(expected)
        for table, expected in _EXPECTED_COLUMNS.items()
    )


def metric_row(metric: Mapping[str, Any]) -> list[Any]:
    return [
        str(metric["id"]),
        int(metric["version"]),
        str(metric["title"]),
        str(metric["unit"]),
        str(metric["direction"]),
        str(metric["aggregation"]),
        str(metric["sql"]),
        sql_sha256(metric),
        int(metric["min_history_weeks"]),
        int(metric["tie_rank"]),
        metric.get("depends_on"),
        metric.get("caveat"),
    ]


def _fact_values(row: Mapping[str, Any]) -> list[Any]:
    values: list[Any] = []
    for column in _FACT_COLUMNS:
        value = row.get(column)
        if column in ("value", "percentile"):
            values.append(None if value is None else float(value))
        elif column in ("metric_version", "iso_year", "iso_week", "wahlperiode", "complete",
                        "week_n", "denominator", "baseline_count", "eligible", "publishable", "rank"):
            values.append(None if value is None else int(value))
        else:
            values.append(None if value is None else str(value))
    return values


def _source_values(receipt: Mapping[str, Any]) -> list[Any]:
    return [
        str(receipt["entity_kind"]),
        None if receipt.get("document_number") is None else str(receipt["document_number"]),
        None if receipt.get("rede_id") is None else str(receipt["rede_id"]),
        None if receipt.get("page") is None else int(receipt["page"]),
        None if receipt.get("page_quadrant") is None else str(receipt["page_quadrant"]),
        None if receipt.get("official_url") is None else str(receipt["official_url"]),
        int(receipt["position"]),
    ]


def snapshot_from_rows(
    registry: Iterable[Mapping[str, Any]], rows: Iterable[Mapping[str, Any]]
) -> dict[str, list[list[Any]]]:
    """The three tables as one comparable value.

    ``fact_sources`` is keyed by the fact's natural key rather than by the
    surrogate ``fact_id``, so a snapshot read back from the store compares
    equal to one built in memory even though the row ids differ.
    """
    facts_rows: list[list[Any]] = []
    source_rows: list[list[Any]] = []
    # One fixed order on both sides of the diff: an in-memory snapshot and one
    # read back from the store have to compare equal row for row.
    for row in sorted(rows, key=lambda r: (r["period_kind"], r["period_key"], str(r["metric_id"]))):
        key = [str(row["period_kind"]), str(row["period_key"]), str(row["metric_id"])]
        facts_rows.append(_fact_values(row))
        for receipt in sorted(row.get("receipts") or [], key=lambda r: int(r["position"])):
            source_rows.append(key + _source_values(receipt))
    return {
        "fact_metrics": [metric_row(metric) for metric in sorted(registry, key=lambda m: str(m["id"]))],
        "facts": facts_rows,
        "fact_sources": source_rows,
    }


def read_snapshot(conn: sqlite3.Connection) -> dict[str, list[list[Any]]] | None:
    """The stored snapshot in the same shape, or None when the tables are
    missing (a fresh store, or one rebuilt by an online build)."""
    if not tables_exist(conn):
        return None
    metrics = [
        list(row)
        for row in conn.execute(
            f"SELECT {_quoted(_METRIC_COLUMNS)} FROM fact_metrics ORDER BY id"
        ).fetchall()
    ]
    metric_id_at = _FACT_COLUMNS.index("metric_id")
    kind_at = _FACT_COLUMNS.index("period_kind")
    key_at = _FACT_COLUMNS.index("period_key")
    facts_rows: list[list[Any]] = []
    keys: dict[int, list[Any]] = {}
    for row in conn.execute(f"SELECT id, {_quoted(_FACT_COLUMNS)} FROM facts").fetchall():
        values = list(row)[1:]
        facts_rows.append(values)
        keys[int(list(row)[0])] = [
            str(values[kind_at]), str(values[key_at]), str(values[metric_id_at])
        ]
    source_rows = [
        keys[int(list(row)[0])] + list(row)[1:]
        for row in conn.execute(
            f"SELECT fact_id, {_quoted(_SOURCE_COLUMNS)} FROM fact_sources"
        ).fetchall()
        if int(list(row)[0]) in keys
    ]
    facts_rows.sort(key=lambda values: (values[kind_at], values[key_at], str(values[metric_id_at])))
    source_rows.sort(key=lambda values: (values[0], values[1], values[2], int(values[-1])))
    return {"fact_metrics": metrics, "facts": facts_rows, "fact_sources": source_rows}


def _comparable(snapshot: Mapping[str, list[list[Any]]] | None) -> str | None:
    if snapshot is None:
        return None
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str)


def write_snapshot(conn: sqlite3.Connection, snapshot: Mapping[str, list[list[Any]]]) -> None:
    """Replace all three tables in one transaction (D14).

    The tables are created first, outside the transaction, because SQLite's
    Python driver does not enrol DDL in the implicit one; every row the site
    reads is written inside it, so a crash leaves the previous rows intact.
    """
    ensure_tables(conn)
    metric_sql = (
        f"INSERT INTO fact_metrics({_quoted(_METRIC_COLUMNS)}) "
        f"VALUES ({', '.join('?' * len(_METRIC_COLUMNS))})"
    )
    fact_sql = (
        f"INSERT INTO facts({_quoted(_FACT_COLUMNS)}) "
        f"VALUES ({', '.join('?' * len(_FACT_COLUMNS))})"
    )
    source_sql = (
        f"INSERT INTO fact_sources(fact_id, {_quoted(_SOURCE_COLUMNS)}) "
        f"VALUES ({', '.join('?' * (len(_SOURCE_COLUMNS) + 1))})"
    )
    metric_id_at = _FACT_COLUMNS.index("metric_id")
    kind_at = _FACT_COLUMNS.index("period_kind")
    key_at = _FACT_COLUMNS.index("period_key")
    sources_by_key: dict[tuple[str, str, str], list[list[Any]]] = {}
    for values in snapshot["fact_sources"]:
        sources_by_key.setdefault(
            (str(values[0]), str(values[1]), str(values[2])), []
        ).append(values[3:])
    with conn:
        conn.execute("DELETE FROM fact_sources")
        conn.execute("DELETE FROM facts")
        conn.execute("DELETE FROM fact_metrics")
        conn.executemany(metric_sql, snapshot["fact_metrics"])
        for values in snapshot["facts"]:
            cursor = conn.execute(fact_sql, values)
            fact_id = cursor.lastrowid
            key = (str(values[kind_at]), str(values[key_at]), str(values[metric_id_at]))
            for source in sources_by_key.get(key, []):
                conn.execute(source_sql, [fact_id] + source)


def load_facts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Every stored fact with its receipts, oldest period first.

    Returns [] when the tables do not exist, so a ``--no-persist`` render of a
    store that has never seen the engine shows an empty archive instead of
    crashing (D3A).
    """
    if not tables_exist(conn):
        return []
    rows = [
        dict(row)
        for row in conn.execute(
            f"SELECT id, {_quoted(_FACT_COLUMNS)} FROM facts "
            'ORDER BY period_kind, iso_year, iso_week, period_key, "rank" IS NULL, "rank", metric_id'
        ).fetchall()
    ]
    by_id = {int(row["id"]): row for row in rows}
    for row in rows:
        row["receipts"] = []
    for source in conn.execute(
        f"SELECT fact_id, {_quoted(_SOURCE_COLUMNS)} FROM fact_sources ORDER BY fact_id, position"
    ).fetchall():
        parent = by_id.get(int(source["fact_id"]))
        if parent is not None:
            parent["receipts"].append({key: source[key] for key in _SOURCE_COLUMNS})
    return rows


def load_metrics(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if not tables_exist(conn):
        return []
    return [
        dict(row)
        for row in conn.execute(
            f"SELECT {_quoted(_METRIC_COLUMNS)} FROM fact_metrics ORDER BY tie_rank"
        ).fetchall()
    ]


def _posted(snapshot: Mapping[str, list[list[Any]]]) -> dict[tuple[str, str], list[tuple[Any, ...]]]:
    """period -> its posted facts as (metric_id, rank, value), rank order."""
    index = {column: position for position, column in enumerate(_FACT_COLUMNS)}
    posted: dict[tuple[str, str], list[tuple[Any, ...]]] = {}
    for values in snapshot["facts"]:
        if not values[index["publishable"]]:
            continue
        key = (str(values[index["period_kind"]]), str(values[index["period_key"]]))
        posted.setdefault(key, []).append(
            (values[index["rank"]], str(values[index["metric_id"]]), values[index["value"]])
        )
    for entries in posted.values():
        entries.sort()
    return posted


def changed_winners(
    previous: Mapping[str, list[list[Any]]] | None,
    current: Mapping[str, list[list[Any]]],
) -> list[str]:
    """Periods whose posted facts differ from the stored ones (D11).

    "Spätere Wochen ändern frühere Karten nicht; Datenkorrekturen können es" is
    the guarantee the Methodik page states, and this is the line in the build
    log that proves it when a correction does.
    """
    if previous is None:
        return []
    before = _posted(previous)
    after = _posted(current)
    lines: list[str] = []
    for key in sorted(set(before) | set(after)):
        was, now = before.get(key, []), after.get(key, [])
        if was == now:
            continue
        lines.append(
            f"{key[1]}: {_posted_text(was)} -> {_posted_text(now)}"
        )
    return lines


def _posted_text(entries: Sequence[tuple[Any, ...]]) -> str:
    if not entries:
        return "kein Fakt"
    return ", ".join(f"{metric_id} ({value:g})" for _, metric_id, value in entries)


def compute_and_store(
    conn: sqlite3.Connection,
    registry: Iterable[Mapping[str, Any]] = REGISTRY,
    completeness: Mapping[str, Mapping[str, bool]] | None = None,
    *,
    built: Iterable[str] = ("votes",),
    no_persist: bool = False,
    out=sys.stderr,
) -> dict[str, Any]:
    """Compute every fact and write the three tables when they changed.

    Writes nothing when the snapshot is unchanged (the store's mtime stays put
    and the Daten export's skip rule holds) and nothing at all under
    ``no_persist``. A metric whose SQL raises aborts the build naming the
    metric, via FactsError.
    """
    registry = tuple(registry)
    rows = compute(conn, registry, completeness if completeness is not None else {}, built=built)
    snapshot = snapshot_from_rows(registry, rows)
    posted = sum(1 for row in rows if row["publishable"])
    periods = {(row["period_kind"], row["period_key"]) for row in rows}
    report: dict[str, Any] = {
        "rows": rows,
        "periods": len(periods),
        "posted": posted,
        "periods_with_a_fact": len({(r["period_kind"], r["period_key"]) for r in rows if r["publishable"]}),
        "written": False,
        "changed_winners": [],
    }
    if no_persist:
        print("facts: --no-persist, nothing written", file=out)
        return report
    previous = read_snapshot(conn)
    if _comparable(previous) == _comparable(snapshot):
        print(f"facts: unchanged ({posted} Fakten in {len(periods)} Perioden), store untouched", file=out)
        return report
    report["changed_winners"] = changed_winners(previous, snapshot)
    write_snapshot(conn, snapshot)
    report["written"] = True
    print(
        f"facts: wrote {len(snapshot['facts'])} rows, {posted} Fakten in "
        f"{report['periods_with_a_fact']} von {len(periods)} Perioden",
        file=out,
    )
    for line in report["changed_winners"]:
        print(f"facts: changed winner {line}", file=out)
    return report

# ---------------------------------------------------------------------------
# Card copy (D12) and the SVG card (D7)
#
# The sample cards the replay writes; T6 owns the site's own copy. Each metric
# contributes a headline number, the subject line and the phrase that names its
# comparison population - "wöchentlich knappsten Abstimmungen" is not the same
# population as "wöchentlichen Spitzenreden", and saying so is D12.
# ---------------------------------------------------------------------------


#: metric_id -> the plural noun the percentile is measured against (D12).
POPULATION_PHRASES = {
    "knappste-abstimmung": ("knapper als", "der wöchentlich knappsten Abstimmungen"),
    "meiste-abweichler": ("mehr als bei", "der wöchentlich abweichungsreichsten Abstimmungen"),
    "laengste-debatte": ("länger als", "der wöchentlichen Spitzendebatten"),
    "laengste-rede": ("länger als", "der wöchentlichen Spitzenreden"),
    "laengste-sitzung": ("länger als", "der wöchentlich längsten Sitzungen"),
    "erste-reden": ("mehr als in", "der Sitzungswochen"),
}


def _topic_clause(citation: Mapping[str, Any]) -> str:
    """" zum Thema X", or "" when the agenda item names no topic (D22)."""
    topic = citation.get("topic")
    return f" zum Thema „{topic}“" if topic else ""


def headline(row: Mapping[str, Any]) -> str:
    citation = row["citation"] or {}
    metric_id = row["metric_id"]
    if metric_id == "knappste-abstimmung":
        return f"{format_int(citation['yes_count'])} : {format_int(citation['no_count'])}"
    if metric_id == "meiste-abweichler":
        return f"{format_int(int(row['value']))} Abweichler"
    if metric_id == "laengste-sitzung":
        minutes = int(row["value"])
        return f"{minutes // 60} h {minutes % 60:02d} min"
    if metric_id == "erste-reden":
        return f"{format_int(int(row['value']))} erste Reden"
    return f"{format_int(int(row['value']))} Zeichen"


def card_title(row: Mapping[str, Any]) -> str:
    citation = row["citation"] or {}
    metric_id = row["metric_id"]
    if metric_id in ("knappste-abstimmung", "meiste-abweichler"):
        return f"„{citation.get('title') or 'ohne Titel'}“"
    if metric_id == "laengste-debatte":
        return citation.get("topic") or f"Tagesordnungspunkt in {citation.get('document_number')}"
    if metric_id == "laengste-sitzung":
        return f"Plenarprotokoll {citation.get('document_number')}"
    if metric_id == "erste-reden":
        speakers = citation.get("speakers") or []
        head = ", ".join(speakers[:3])
        return f"{head} und weitere" if len(speakers) > 3 else (head or "Unbekannt")
    return f"{citation.get('display_name') or 'Unbekannt'} ({citation.get('fraktion') or 'Unbekannt'})"


#: The archive's reason line per withheld reason. T6 owns the page copy; this
#: is the one sentence the replay's sample cards and the week page share.
WITHHELD_CLAUSES = {
    WITHHELD_NO_OBSERVATION: "diese Woche nicht messbar",
    WITHHELD_NOT_COMPARABLE: "noch nicht vergleichbar",
    WITHHELD_BELOW_MIN_VALUE: "zu wenige, um daraus einen Fakt zu machen",
    WITHHELD_NO_TOPIC: "Thema der Debatte nicht bestimmbar",
    WITHHELD_BELOW_FLOOR: "nicht ungewöhnlich genug",
}


def comparison_clause(row: Mapping[str, Any]) -> str:
    reason = row["withheld"] if "withheld" in row else withheld_reason(row)
    if reason is not None:
        return WITHHELD_CLAUSES[reason]
    pct = format_percentile(float(row["percentile"]))
    comparative, population = POPULATION_PHRASES[row["metric_id"]]
    label = row.get("baseline_label") or ""
    return f"{comparative} {pct} % {population} {label}".rstrip()


def card_lead(row: Mapping[str, Any]) -> str:
    """The sentence up to the comparison clause."""
    citation = row["citation"] or {}
    metric_id = row["metric_id"]
    title = REGISTRY_BY_ID[metric_id]["title"]
    if metric_id == "knappste-abstimmung":
        return (
            f"{title}: {format_int(citation['yes_count'])} zu "
            f"{format_int(citation['no_count'])} zu {card_title(row)}"
        )
    if metric_id == "meiste-abweichler":
        return (
            f"{title}: {format_int(int(row['value']))} Abgeordnete stimmten gegen die Linie "
            f"ihrer Fraktion, bei {card_title(row)}"
        )
    if metric_id == "laengste-debatte":
        return (
            f"{title}: {format_int(int(row['value']))} Zeichen in "
            f"{format_int(int(citation.get('speech_count') or 0))} Reden über {card_title(row)}"
        )
    if metric_id == "laengste-sitzung":
        return f"{title}: {headline(row)} im {card_title(row)}"
    if metric_id == "erste-reden":
        return (
            f"{title}: {format_int(int(row['value']))} Abgeordnete hielten ihre erste Rede "
            f"({card_title(row)})"
        )
    return (
        f"{title}: {format_int(int(row['value']))} Zeichen von {card_title(row)}"
        f"{_topic_clause(citation)}"
    )


def card_sentence(row: Mapping[str, Any]) -> str:
    return f"{card_lead(row)}, {comparison_clause(row)}."


def card_caveat(row: Mapping[str, Any]) -> str | None:
    """The metric's caveat, registry data since D27; rendered on every card and
    week page that shows the metric."""
    return REGISTRY_BY_ID[row["metric_id"]].get("caveat")


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
    caveat_lines = wrap_lines(card_caveat(row) or "", width=76, max_lines=2)
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
        _text_block(caveat_lines, x=x, y=870, size=24, line_height=32, fill=CARD_MUTED, css_class="caveat"),
        _text_block([footer], x=x, y=960, size=26, line_height=0, fill=CARD_MUTED, css_class="footer"),
        f'<text class="site" x="{CARD_SIZE - x}" y="1000" font-size="30" font-weight="bold" '
        f'fill="{CARD_BLUE}" text-anchor="end">Bundestag-Puls</text>',
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def card_filename(row: Mapping[str, Any]) -> str:
    """D21: one card per posted fact, not one per week."""
    return f"{row['period_key']}-{row['metric_id']}.svg"


def write_cards(rows: Iterable[Mapping[str, Any]], cards_dir: Path) -> list[Path]:
    """One SVG per publishable row (D21); returns the written paths (sorted)."""
    cards_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for row in rows:
        if not row.get("publishable"):
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
    floors: Sequence[float] = (0.25, 0.50, 0.75),
) -> dict[str, Any]:
    """The 15A criteria plus the D20 floor numbers over the replayed weeks.

    Criterion 1 is reported, not enforced: D28 waived it. ``posted_per_metric``
    and ``floor_table`` are what the human reads to decide whether T6 starts.
    """
    posted = [row for week in week_reports for row in week["posted"]]
    speakers = Counter(
        (row["citation"] or {}).get("display_name")
        for row in posted
        if row["metric_id"] == "laengste-rede"
    )
    wins = Counter(row["metric_id"] for row in posted)
    wins["kein Fakt"] = sum(1 for week in week_reports if not week["posted"])

    changed = 0
    compared = 0
    for rule_week, all_week in zip(week_reports, all_week_reports):
        rule_ids = [row["metric_id"] for row in rule_week["posted"]]
        all_ids = [row["metric_id"] for row in all_week["posted"]]
        if not rule_ids and not all_ids:
            continue
        compared += 1
        if rule_ids != all_ids:
            changed += 1

    # How the publication floor trades weeks for cards (D20): at each floor,
    # how many of the replayed weeks still post something and how many cards
    # they post in total.
    floor_table: list[dict[str, Any]] = []
    for floor in floors:
        eligible_rows = [
            row
            for week in week_reports
            for row in week["metrics"].values()
            if row["eligible"] and row["percentile"] is not None
        ]
        kept = [row for row in eligible_rows if withheld_reason(row, floor=floor) is None]
        weeks_with = {(row["period_kind"], row["period_key"]) for row in kept}
        floor_table.append(
            {
                "floor": floor,
                "weeks": len(weeks_with),
                "cards": len(kept),
                "per_metric": dict(Counter(row["metric_id"] for row in kept).most_common()),
            }
        )

    vs_week_n: dict[str, Any] = {}
    for metric in REGISTRY:
        observed = [
            week["metrics"][metric["id"]]
            for week in week_reports
            if metric["id"] in week["metrics"] and week["metrics"][metric["id"]]["value"] is not None
        ]
        eligible = [row for row in observed if row["eligible"]]
        xs = [float(row["week_n"]) for row in eligible]
        ys = [float(row["percentile"]) for row in eligible]
        # Criterion 4 asks whether a period scores high merely because it had
        # more chances to. For a counting metric the value *is* week_n, so the
        # correlation is 1 by construction and says nothing; reporting a number
        # there would read as a red flag where there is no finding.
        counts_its_chances = metric.get("aggregation") == "count"
        entry: dict[str, Any] = {
            "weeks_observed": len(observed),
            "weeks_eligible": len(eligible),
            "weeks_posted": sum(1 for row in eligible if row["publishable"]),
            "pearson_week_n_vs_percentile": None if counts_its_chances else _pearson(xs, ys),
            "value_is_week_n": counts_its_chances,
        }
        if eligible:
            median = _median(xs)
            above = [row for row in eligible if row["week_n"] > median]
            below = [row for row in eligible if row["week_n"] <= median]
            entry["median_week_n"] = median
            entry["won_above_median"] = (sum(1 for r in above if r["publishable"]), len(above))
            entry["won_at_or_below_median"] = (sum(1 for r in below if r["publishable"]), len(below))
        vs_week_n[metric["id"]] = entry

    recent_cards = [
        card_sentence(row)
        for week in reversed(week_reports)
        for row in week["posted"]
    ][:recent]
    return {
        "max_cards_per_speaker": max(speakers.values()) if speakers else 0,
        "cards_per_speaker": dict(speakers.most_common()),
        "posted_per_metric": dict(wins),
        "weeks_with_a_fact": sum(1 for week in week_reports if week["posted"]),
        "cards_total": len(posted),
        "floor_table": floor_table,
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
            {
                "key": key,
                "label": row["period_key"],
                "period_kind": row["period_kind"],
                "wahlperiode": row["wahlperiode"],
                "metrics": {},
                "posted": [],
            },
        )
        entry["metrics"][row["metric_id"]] = row
    for entry in by_week.values():
        entry["posted"] = sorted(
            (row for row in entry["metrics"].values() if row["publishable"]),
            key=lambda row: int(row["rank"]),
        )
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
    """Compute every week read-only, write the last ``weeks``' posted facts as
    SVGs and return the replay table plus the gate numbers."""
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
        written = write_cards(
            [row for week in week_reports for row in week["posted"]], cards_dir
        )
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
    document = citation.get("document_number")
    kind = REGISTRY_BY_ID[row["metric_id"]]["receipt"]
    if kind == "vote":
        title = str(citation.get("title") or "")
        return f"{document} Abstimmung {citation.get('id')} {title[:50]}"
    if kind == "agenda_item":
        return f"{document} TOP {citation.get('id')} {str(citation.get('topic') or '')[:50]}"
    if kind == "protocol":
        return f"{document} {citation.get('sitzung_start')}-{citation.get('sitzung_end')}"
    if kind == "speeches":
        return f"{document} {', '.join((citation.get('speakers') or [])[:3])}"
    return f"{document} {citation.get('rede_id')} {citation.get('display_name')} ({citation.get('fraktion')})"


#: One character per withheld reason for the replay table's pct column.
_WITHHELD_MARK = {
    WITHHELD_NOT_COMPARABLE: "*",
    WITHHELD_BELOW_FLOOR: "-",
    WITHHELD_BELOW_MIN_VALUE: "!",
    WITHHELD_NO_TOPIC: "?",
}


#: Column tags for the replay table, short enough to stay readable at six metrics.
_SHORT_METRIC = {
    "knappste-abstimmung": "knapp",
    "meiste-abweichler": "abw",
    "laengste-debatte": "deb",
    "laengste-rede": "rede",
    "laengste-sitzung": "sitz",
    "erste-reden": "erst",
}


def print_report(report: dict[str, Any], out=sys.stdout) -> None:
    metrics = [m["id"] for m in sorted(REGISTRY, key=lambda m: int(m["tie_rank"]))]
    header = ["week", "WP", "compl(v/s)"]
    for metric_id in metrics:
        header += [f"{_SHORT_METRIC[metric_id]}_value", f"{_SHORT_METRIC[metric_id]}_pct"]
    header += ["posted", "cited (rank 1)"]
    lines = [" | ".join(header)]
    for week in report["weeks"]:
        votes_flag = week["metrics"].get("knappste-abstimmung", {}).get("complete", "-")
        speech_flag = week["metrics"].get("laengste-rede", {}).get("complete", "-")
        cells = [week["label"], str(week["wahlperiode"]), f"{votes_flag}/{speech_flag}"]
        for metric_id in metrics:
            row = week["metrics"].get(metric_id)
            if row is None:
                cells += ["-", "-"]
                continue
            if row["percentile"] is None:
                pct = "-"
            else:
                pct = format_percentile(row["percentile"]) + _WITHHELD_MARK.get(row["withheld"], "")
            cells += [_fmt_value(row), pct]
        posted = week["posted"]
        cells += [
            ",".join(_SHORT_METRIC[row["metric_id"]] for row in posted) or "-",
            _fmt_cited(posted[0]) if posted else "-",
        ]
        lines.append(" | ".join(cells))
    print("\n".join(lines), file=out)
    print(file=out)
    print(
        f"store: {report['store']}  (read-only; {report['weeks_total']} sitting weeks; "
        f"built: {', '.join(report['built']) or 'none'})",
        file=out,
    )
    print(f"unlinked votes (no agenda link, excluded): {report['unlinked_votes']}", file=out)
    print(
        "pct suffix: * noch nicht vergleichbar, - unter 50 %, ! zu wenige, ? kein Thema",
        file=out,
    )
    print(file=out)
    gate = report["gate"]
    weeks_total = len(report["weeks"])
    print(f"Gate (15A) and floor (D20) over {weeks_total} weeks:", file=out)
    print(
        f"  0. floor {PUBLICATION_FLOOR:.2f}: {gate['weeks_with_a_fact']} of {weeks_total} weeks "
        f"post a fact, {gate['cards_total']} cards in total",
        file=out,
    )
    for entry in gate["floor_table"]:
        print(
            f"     floor {entry['floor']:.2f}: {entry['weeks']} weeks, {entry['cards']} cards "
            f"{entry['per_metric']}",
            file=out,
        )
    print(f"  1. max cards per speaker: {gate['max_cards_per_speaker']}  {gate['cards_per_speaker']}  (waived, D28)", file=out)
    print(f"  2. cards per metric: {gate['posted_per_metric']}", file=out)
    changed, compared = gate["changed_wp_vs_all"]
    share = f"{changed / compared:.2f}" if compared else "n/a"
    print(f"  3. posted facts changed wp -> all: {changed} of {compared} ({share})", file=out)
    print("  4. posted vs week_n:", file=out)
    for metric_id, entry in gate["winners_vs_week_n"].items():
        r = entry.get("pearson_week_n_vs_percentile")
        if entry.get("value_is_week_n"):
            r_text = "n/a (value is week_n)"
        else:
            r_text = "n/a" if r is None else f"{r:+.2f}"
        contingency = ""
        if "median_week_n" in entry:
            above = entry["won_above_median"]
            below = entry["won_at_or_below_median"]
            contingency = (
                f"; median week_n {entry['median_week_n']:g}: posted {above[0]}/{above[1]} above, "
                f"{below[0]}/{below[1]} at or below"
            )
        print(
            f"     {metric_id}: {entry['weeks_observed']} observed, {entry['weeks_eligible']} eligible, "
            f"{entry['weeks_posted']} posted, pearson(week_n, percentile) = {r_text}{contingency}",
            file=out,
        )
    print("  5. the 10 most recent cards (newest first):", file=out)
    for index, sentence in enumerate(gate["recent_cards"], start=1):
        print(f"     {index:2d}. {sentence}", file=out)
    if report["cards"]:
        print(file=out)
        print(f"cards: {len(report['cards'])} SVGs in {Path(report['cards'][0]).parent}", file=out)

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fakt der Woche: read-only replay.")
    parser.add_argument("--replay", type=int, metavar="N", required=True, help="print the last N sitting weeks")
    parser.add_argument("--cards", type=Path, metavar="DIR", help="write the replayed weeks' posted facts as SVG cards here")
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
