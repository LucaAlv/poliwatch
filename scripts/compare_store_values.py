#!/usr/bin/env python3
"""Compare two site output directories on the values a data correction moves.

    python3 scripts/compare_store_values.py OLD_DIR NEW_DIR [--cohort shared|all]

OLD_DIR and NEW_DIR are output directories of the site build (the ones holding
``data/bundestag-pulse.sqlite`` and the generated pages), the baseline first.
Every commit that changes a stored value quotes this script's output, so a
reader can see the old value, the new value and the delta without re-deriving
them (CLAUDE.md, "When a fix moves a number, report the old and new values").

Two modes, chosen with ``--cohort``:

* ``shared`` (default), the fixed cohort: quantities that come from parsed
  protocols (speech characters, Redeanteil, votes, Mehrheitsvotum) are
  compared on the protocols present in both stores, so a newly acquired
  sitting cannot blur the delta of a value fix.
* ``all``, whole-store coverage: the same quantities over every protocol of
  each store, which is what shows what a rebuild added or lost.

Quantities that only exist store-wide (row counts, parties, the stored facts,
generated pages) are labelled ``[whole store]`` in both modes. A quantity with
no evidence in a store (a column the older schema does not have, a page
directory that was not built) prints ``unavailable``, never 0.

The script only reads: both databases are opened with ``mode=ro`` and no
migration runs.

Exit codes: 0 compared (whether or not anything changed), 2 an input is not a
readable output directory.
"""

from __future__ import annotations

if __name__ == "__main__":
    from python_version_guard import require_supported_python

    require_supported_python()

import argparse
import gzip
import re
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence, TextIO

import facts

UNAVAILABLE = "unavailable"
STORE_RELATIVE = Path("data") / "bundestag-pulse.sqlite"
#: Per-protocol tables print at most this many changed protocols.
PER_PROTOCOL_LIMIT = 15
#: A list of changed periods prints at most this many lines.
LIST_LIMIT = 25
NO_GROUP = "(ohne Zuordnung)"
PARTY_MDBS_NOTE = "MdB per row of parties"


class CompareError(Exception):
    """An input directory that cannot be compared (exit code 2)."""


@dataclass
class Store:
    """One side of the comparison: everything read from an output directory."""

    directory: Path
    conn: sqlite3.Connection
    _columns: dict[str, set[str] | None] = field(default_factory=dict)

    def columns(self, table: str) -> set[str] | None:
        """The table's columns, or None when the table does not exist."""
        if table not in self._columns:
            rows = self.conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            self._columns[table] = {row[1] for row in rows} or None
        return self._columns[table]

    def has(self, table: str, *columns: str) -> bool:
        present = self.columns(table)
        return present is not None and all(column in present for column in columns)

    def close(self) -> None:
        self.conn.close()


def open_store(directory: Path) -> Store:
    path = directory / STORE_RELATIVE
    if not path.is_file():
        raise CompareError(f"{directory}: no {STORE_RELATIVE} (pass the site output directory)")
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")
    except sqlite3.Error as error:
        raise CompareError(f"{path}: not a readable SQLite store ({error})") from error
    return Store(directory=directory, conn=conn)


# ---------------------------------------------------------------- measurement


@dataclass
class Measured:
    """What one store yields. ``None`` marks a quantity without evidence."""

    tables: dict[str, int] = field(default_factory=dict)
    protocols: set[str] = field(default_factory=set)
    #: document_number -> characters / Reden of that protocol's speeches.
    chars_by_protocol: dict[str, int] | None = None
    unattributed_by_protocol: dict[str, int] | None = None
    #: (document_number, group label) -> Reden; the group is the Redeanteil row.
    reden_by_group: dict[tuple[str, str], int] | None = None
    #: (document_number, sprechrolle) -> Reden.
    reden_by_sprechrolle: dict[tuple[str, str], int] | None = None
    #: (document_number, "current party" | "no Zusammenschluss") -> Reden that name
    #: none in the Plenarprotokoll and are no Rede in a Sprechrolle.
    reden_without_fraktion: dict[tuple[str, str], int] | None = None
    #: (document_number or None, date, vote id) for every vote.
    votes: list[tuple[str | None, str | None, str]] | None = None
    #: (document_number or None, leading_vote or None) per vote_fractions row.
    leading: list[tuple[str | None, str | None]] | None = None
    #: name -> {"mps": rows of mps, "mdb": of them MdB, "reden": Reden naming it}
    parties: dict[str, dict[str, int]] | None = None
    has_roster: bool = False
    facts_snapshot: dict[str, list[list[Any]]] | None = None
    facts_rows: dict[tuple[str, str, str], tuple[int, int, str | None]] | None = None
    #: Zusammenführung of the store's mps rows by the rules of this tree (rows,
    #: entries, merges per provenance, name buckets left split).
    zusammenfuehrung: dict[str, int] | None = None
    bill_pages: int | None = None
    person_pages: int | None = None
    r3_rows: int | None = None


def _vote_protocols(store: Store) -> dict[str, list[str]]:
    """vote id -> the document numbers of the sittings it hangs off."""
    if not (store.has("agenda_item_votes") and store.has("agenda_items") and store.has("protocols")):
        return {}
    mapping: dict[str, list[str]] = {}
    for vote_id, number in store.conn.execute(
        "SELECT aiv.vote_id, p.document_number FROM agenda_item_votes aiv "
        "JOIN agenda_items ai ON ai.id = aiv.agenda_item_id "
        "JOIN protocols p ON p.id = ai.protocol_id"
    ):
        mapping.setdefault(str(vote_id), []).append(str(number))
    return mapping


def _count_pages(directory: Path, subdir: str, ignore: Iterable[str] = ("index.html",)) -> int | None:
    folder = directory / subdir
    if not folder.is_dir():
        return None
    pages = [path for path in folder.glob("*.html") if path.name not in set(ignore)]
    if not pages and not any(folder.iterdir()):
        return None
    return len(pages)


def _redeanteil_group_sql(store: Store) -> str:
    """The Redeanteil row a speech belongs to. Once the store carries the
    Sprechrolle, a speech by a Bundesregierung/Bundesrat/weitere speaker is its
    own row and not any Fraktion's (ADR 0001)."""
    fraktion = "COALESCE(NULLIF(s.fraktion, ''), pa.name)"
    if store.has("speeches", "sprechrolle"):
        return f"CASE WHEN s.sprechrolle IS NOT NULL THEN 'Sprechrolle ' || s.sprechrolle ELSE {fraktion} END"
    return fraktion


def measure(store: Store, *, recipes: bool = True) -> Measured:
    conn = store.conn
    measured = Measured()
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"):
        if name.startswith("sqlite_"):
            continue
        measured.tables[name] = int(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])

    if store.has("protocols", "document_number"):
        measured.protocols = {str(n) for (n,) in conn.execute("SELECT document_number FROM protocols")}

    if store.has("speeches", "char_count") and store.has("protocols", "document_number"):
        measured.chars_by_protocol = {
            str(number): int(chars or 0)
            for number, chars in conn.execute(
                "SELECT p.document_number, SUM(s.char_count) FROM speeches s "
                "JOIN protocols p ON p.id = s.protocol_id GROUP BY p.document_number"
            )
        }
    if store.has("speeches", "unattributed_char_count") and store.has("protocols", "document_number"):
        # NULL means the report predates the measurement: no evidence, not 0.
        measured.unattributed_by_protocol = {
            str(number): int(chars)
            for number, chars in conn.execute(
                "SELECT p.document_number, SUM(s.unattributed_char_count) FROM speeches s "
                "JOIN protocols p ON p.id = s.protocol_id GROUP BY p.document_number"
            )
            if chars is not None
        } or None
    if store.has("speeches", "fraktion") and store.has("mps", "party_id") and store.has("parties", "name"):
        group = _redeanteil_group_sql(store)
        measured.reden_by_group = {
            (str(number), str(label) if label else NO_GROUP): int(count)
            for number, label, count in conn.execute(
                f"SELECT p.document_number, {group}, COUNT(*) FROM speeches s "
                "JOIN protocols p ON p.id = s.protocol_id "
                "LEFT JOIN mps m ON m.id = s.mp_id "
                "LEFT JOIN parties pa ON pa.id = m.party_id "
                "GROUP BY p.document_number, 2"
            )
        }
    if store.has("speeches", "sprechrolle"):
        measured.reden_by_sprechrolle = {
            (str(number), str(role)): int(count)
            for number, role, count in conn.execute(
                "SELECT p.document_number, COALESCE(s.sprechrolle, 'keine'), COUNT(*) FROM speeches s "
                "JOIN protocols p ON p.id = s.protocol_id GROUP BY p.document_number, 2"
            )
        }

    if store.has("speeches", "sprechrolle", "fraktion") and store.has("mps", "party_id"):
        # ADR 0001: a Rede whose protocol names no Zusammenschluss counts for the
        # speaker's party as the store holds it (an approximation of the
        # Zugehörigkeit on the day); with no party either it counts for none.
        measured.reden_without_fraktion = {
            (str(number), "current party" if party else "no Zusammenschluss"): int(count)
            for number, party, count in conn.execute(
                "SELECT p.document_number, pa.name, COUNT(*) FROM speeches s "
                "JOIN protocols p ON p.id = s.protocol_id "
                "LEFT JOIN mps m ON m.id = s.mp_id LEFT JOIN parties pa ON pa.id = m.party_id "
                "WHERE s.sprechrolle IS NULL AND (s.fraktion IS NULL OR s.fraktion = '') "
                "GROUP BY p.document_number, pa.name IS NOT NULL"
            )
        }

    if store.has("votes", "id", "date"):
        by_vote = _vote_protocols(store)
        measured.votes = []
        for vote_id, date in conn.execute("SELECT id, date FROM votes"):
            for number in by_vote.get(str(vote_id)) or [None]:
                measured.votes.append((number, date, str(vote_id)))
        if store.has("vote_fractions", "vote_id", "leading_vote"):
            measured.leading = []
            for vote_id, leading in conn.execute("SELECT vote_id, leading_vote FROM vote_fractions"):
                for number in by_vote.get(str(vote_id)) or [None]:
                    measured.leading.append((number, leading))

    if store.has("parties", "id", "name") and store.has("mps", "party_id", "is_mdb"):
        measured.parties = {
            str(name): {"mps": int(mps), "mdb": int(mdb or 0), "reden": 0}
            for name, mps, mdb in conn.execute(
                "SELECT pa.name, COUNT(m.id), SUM(m.is_mdb = 1) FROM parties pa "
                "LEFT JOIN mps m ON m.party_id = pa.id GROUP BY pa.id"
            )
        }
        # No MdB roster in the store (an update without --enrich mp-roster): the
        # MdB counts say nothing, not "0".
        measured.has_roster = bool(conn.execute("SELECT 1 FROM mps WHERE is_mdb = 1 LIMIT 1").fetchone())
        if store.has("speeches", "fraktion"):
            for name, reden in conn.execute(
                "SELECT fraktion, COUNT(*) FROM speeches WHERE fraktion IS NOT NULL AND fraktion <> '' GROUP BY fraktion"
            ):
                measured.parties.setdefault(str(name), {"mps": 0, "mdb": 0, "reden": 0})["reden"] = int(reden)

    try:
        measured.facts_snapshot = facts.read_snapshot(conn)
    except sqlite3.Error:
        measured.facts_snapshot = None
    if store.has("facts", "metric_id", "period_kind", "period_key", "complete", "publishable", "withheld"):
        measured.facts_rows = {
            (str(kind), str(key), str(metric)): (int(complete), int(publishable), withheld)
            for kind, key, metric, complete, publishable, withheld in conn.execute(
                "SELECT period_kind, period_key, metric_id, complete, publishable, withheld FROM facts"
            )
        }

    measured.zusammenfuehrung = _zusammenfuehrung(store)
    measured.bill_pages = _count_pages(store.directory, "bills")
    measured.person_pages = _count_pages(store.directory, "abgeordnete")
    if recipes:
        measured.r3_rows = _recipe_rows(store, "r3-abweichler")
    return measured


def _zusammenfuehrung(store: Store) -> dict[str, int] | None:
    """Run this tree's Zusammenführung over the store's mps rows and return its
    statistics. A store from before ``aw_match`` was kept counts every
    abgeordnetenwatch id as found by name (the rule for an unrecorded kind)."""
    if not (store.has("mps", "id", "display_name") and store.has("speeches") and store.has("vote_members")):
        return None
    import build_dip_pulse_site as build

    conn = store.conn
    conn.row_factory = sqlite3.Row
    stats: dict[str, int] = {}
    try:
        build.collect_abgeordnete(conn, stats)
    except sqlite3.Error:
        return None
    finally:
        conn.row_factory = None
    return stats


def _recipe_rows(store: Store, recipe_id: str) -> int | None:
    """Row count of a Daten recipe (without its LIMIT) run on the store's own
    Verteilkopie, the copy that carries the derived ``mp_canonical`` table. The
    SQL is the recipe as this tree defines it."""
    exports = store.directory / "data" / "exports"
    copies = sorted(
        exports.glob("*/bundestag-pulse-local.sqlite.gz") if exports.is_dir() else [],
        key=lambda path: path.stat().st_mtime,
    )
    if not copies:
        return None
    import build_dip_pulse_site as build

    recipe = build.RECIPES_BY_ID.get(recipe_id)
    if recipe is None:
        return None
    sql = re.sub(r"\s+LIMIT\s+\d+\s*;?\s*$", "", str(recipe["sql"]).strip(), flags=re.IGNORECASE)
    with tempfile.TemporaryDirectory() as scratch:
        unpacked = Path(scratch) / "copy.sqlite"
        with gzip.open(copies[-1], "rb") as source, unpacked.open("wb") as target:
            shutil.copyfileobj(source, target)
        conn = sqlite3.connect(f"file:{unpacked}?mode=ro", uri=True)
        try:
            return len(conn.execute(sql).fetchall())
        except sqlite3.Error:
            return None
        finally:
            conn.close()


# --------------------------------------------------------------------- report


def _shared(old: Measured, new: Measured) -> set[str]:
    return old.protocols & new.protocols


def _in(cohort: set[str] | None, number: str | None) -> bool:
    if cohort is None:
        return True
    return number is not None and number in cohort


def _fmt(value: Any) -> str:
    if value is None:
        return UNAVAILABLE
    if isinstance(value, float):
        return f"{value:.1f}"
    if isinstance(value, int):
        return f"{value:,}".replace(",", ".")
    return str(value)


def _delta(old: Any, new: Any) -> str:
    if old is None or new is None or isinstance(old, str) or isinstance(new, str):
        return ""
    change = new - old
    if change == 0:
        return "="
    return f"{change:+,}".replace(",", ".") if isinstance(change, int) else f"{change:+.1f}"


class Report:
    def __init__(self, out: TextIO) -> None:
        self.out = out

    def heading(self, title: str) -> None:
        print(f"\n== {title}", file=self.out)

    def row(self, label: str, old: Any, new: Any, *, indent: int = 2) -> None:
        delta = _delta(old, new)
        print(
            f"{' ' * indent}{label:<44} {_fmt(old):>14} -> {_fmt(new):<14} {delta}".rstrip(),
            file=self.out,
        )

    def line(self, text: str) -> None:
        print(f"  {text}", file=self.out)


def _compare_maps(
    report: Report,
    old: Mapping[str, Any] | None,
    new: Mapping[str, Any] | None,
    *,
    only_changed: bool = False,
    limit: int | None = None,
    order: Callable[[str], Any] | None = None,
) -> None:
    if old is None and new is None:
        report.row("(all)", None, None)
        return
    # A side without evidence still shows the other side's figures, against
    # "unavailable", so a new quantity reads as what it is, not as a jump from 0.
    keys = sorted(set(old or {}) | set(new or {}), key=order) if order else sorted(set(old or {}) | set(new or {}))
    rows = [
        (key, None if old is None else old.get(key, 0), None if new is None else new.get(key, 0)) for key in keys
    ]
    if only_changed:
        rows = [row for row in rows if row[1] != row[2]]
    if limit is not None and len(rows) > limit:
        rows.sort(key=lambda row: -abs((row[2] or 0) - (row[1] or 0)))
        rest = len(rows) - limit
        rows = rows[:limit]
    else:
        rest = 0
    for key, was, now in rows:
        report.row(key, was, now)
    if rest:
        report.line(f"... {rest} more changed")


def _filter_by_protocol(
    mapping: dict[Any, int] | None, cohort: set[str] | None, position: int = 0
) -> dict[Any, int] | None:
    if mapping is None:
        return None
    return {key: value for key, value in mapping.items() if _in(cohort, key[position] if isinstance(key, tuple) else key)}


def _collapse(mapping: dict[tuple[str, str], int] | None, cohort: set[str] | None) -> dict[str, int] | None:
    if mapping is None:
        return None
    total: Counter[str] = Counter()
    for (number, label), count in mapping.items():
        if _in(cohort, number):
            total[label] += count
    return dict(total)


def _share_rows(report: Report, old: dict[str, int] | None, new: dict[str, int] | None) -> None:
    if old is None and new is None:
        report.row("(all)", None, None)
        return
    old_total = sum(old.values()) or 1 if old is not None else 1
    new_total = sum(new.values()) or 1 if new is not None else 1
    labels = set(old or {}) | set(new or {})
    for label in sorted(labels, key=lambda name: -((new or {}).get(name, 0) + (old or {}).get(name, 0))):
        report.row(
            f"{label} (Reden)",
            None if old is None else old.get(label, 0),
            None if new is None else new.get(label, 0),
        )
        report.row(
            f"{label} (Anteil %)",
            None if old is None else round(100 * old.get(label, 0) / old_total, 1),
            None if new is None else round(100 * new.get(label, 0) / new_total, 1),
            indent=4,
        )


def compare(
    old_dir: Path, new_dir: Path, *, cohort: str = "shared", out: TextIO | None = None, recipes: bool = True
) -> None:
    out = out or sys.stdout
    old_store, new_store = open_store(old_dir), open_store(new_dir)
    try:
        old = measure(old_store, recipes=recipes)
        new = measure(new_store, recipes=recipes)
    finally:
        old_store.close()
        new_store.close()

    shared = _shared(old, new)
    scope: set[str] | None = shared if cohort == "shared" else None
    report = Report(out)
    print(f"compare_store_values: old={old_dir} new={new_dir}", file=out)
    only_old, only_new = len(old.protocols - new.protocols), len(new.protocols - old.protocols)
    if cohort == "shared":
        print(
            f"cohort: shared ({len(shared)} protocols in both; {only_old} only in old, {only_new} only in new)",
            file=out,
        )
    else:
        print(
            f"cohort: all (whole-store coverage; {len(old.protocols)} old, {len(new.protocols)} new protocols)",
            file=out,
        )

    report.heading("Row counts per table [whole store]")
    for table in sorted(set(old.tables) | set(new.tables)):
        report.row(table, old.tables.get(table), new.tables.get(table))

    report.heading("parties [whole store]: mps rows, MdB, Reden naming it")
    _party_rows(report, old, new)

    report.heading(f"vote_fractions.leading_vote [{cohort}]")
    if old.leading is None or new.leading is None:
        report.row("(all)", None if old.leading is None else "present", None if new.leading is None else "present")
    else:
        was = Counter(value or "NULL" for number, value in old.leading if _in(scope, number))
        now = Counter(value or "NULL" for number, value in new.leading if _in(scope, number))
        _compare_maps(report, dict(was), dict(now))

    report.heading(f"votes [{cohort}]")
    _vote_rows(report, old, new, scope)

    report.heading(f"speeches.char_count sum [{cohort}]")
    old_chars = _filter_by_protocol(old.chars_by_protocol, scope)
    new_chars = _filter_by_protocol(new.chars_by_protocol, scope)
    report.row(
        "sum over protocols",
        None if old_chars is None else sum(old_chars.values()),
        None if new_chars is None else sum(new_chars.values()),
    )
    if old_chars is not None and new_chars is not None:
        changed = sum(1 for key in set(old_chars) | set(new_chars) if old_chars.get(key) != new_chars.get(key))
        report.line(f"{changed} protocols changed; largest moves:")
        _compare_maps(report, old_chars, new_chars, only_changed=True, limit=PER_PROTOCOL_LIMIT)

    report.heading(f"unattributed characters per protocol [{cohort}]")
    old_un = _filter_by_protocol(old.unattributed_by_protocol, scope)
    new_un = _filter_by_protocol(new.unattributed_by_protocol, scope)
    report.row(
        "sum over protocols",
        None if old_un is None else sum(old_un.values()),
        None if new_un is None else sum(new_un.values()),
    )
    if old_un is not None and new_un is not None:
        _compare_maps(report, old_un, new_un, only_changed=True, limit=PER_PROTOCOL_LIMIT)

    report.heading(f"speeches per Sprechrolle [{cohort}]")
    _compare_maps(
        report,
        _collapse(old.reden_by_sprechrolle, scope),
        _collapse(new.reden_by_sprechrolle, scope),
    )

    report.heading(f"Redeanteil: Reden and share per Zusammenschluss and Sprechrolle [{cohort}]")
    _share_rows(report, _collapse(old.reden_by_group, scope), _collapse(new.reden_by_group, scope))

    report.heading(f"Reden with no Zusammenschluss in the Plenarprotokoll, no Sprechrolle [{cohort}]")
    _compare_maps(
        report,
        _collapse(old.reden_without_fraktion, scope),
        _collapse(new.reden_without_fraktion, scope),
    )

    report.heading("Daten recipe r3-abweichler [whole store]")
    report.row("rows without LIMIT (recipe of this tree)", old.r3_rows, new.r3_rows)

    report.heading("Zusammenführung of the mps rows, by the rules of this tree [whole store]")
    labels = (
        ("rows", "mps rows"),
        ("entries", "Personen after Zusammenführung"),
        ("merges_ext_id", "merges by Personenkennung (ext_id)"),
        ("merges_corroborated_name", "merges by corroborated name-found id (corroborated_name)"),
        ("merges_unique_name", "merges by unique name + party (unique_name)"),
        ("buckets_split_namesakes", "name buckets left split: two on one side"),
        ("buckets_split_3plus", "name buckets left split: 3+ records"),
    )
    for key, label in labels:
        report.row(
            label,
            None if old.zusammenfuehrung is None else old.zusammenfuehrung.get(key),
            None if new.zusammenfuehrung is None else new.zusammenfuehrung.get(key),
        )

    report.heading("generated pages [whole store]")
    report.row("bills/ pages", old.bill_pages, new.bill_pages)
    report.row("abgeordnete/ pages (Personenseiten)", old.person_pages, new.person_pages)

    report.heading("stored facts [whole store]")
    _facts_rows(report, old, new)


def _party_rows(report: Report, old: Measured, new: Measured) -> None:
    """Every parties name that is on one side only or whose figures moved. A
    name that disappears (SPDSPD) or appears is exactly what a spelling fix
    changes, so it is listed even when its counts would be equal."""
    if old.parties is None or new.parties is None:
        report.row("(all)", None if old.parties is None else "present", None if new.parties is None else "present")
        return
    shown = False
    for name in sorted(set(old.parties) | set(new.parties)):
        was, now = old.parties.get(name), new.parties.get(name)
        for key, label in (("mps", "mps rows"), ("mdb", "MdB"), ("reden", "Reden")):
            before = None if was is None else was[key]
            after = None if now is None else now[key]
            if key == "mdb":
                before = before if old.has_roster else None
                after = after if new.has_roster else None
            if was is not None and now is not None and before == after:
                continue
            shown = True
            report.row(
                f"{name}: {label}",
                "no row" if was is None else before,
                "no row" if now is None else after,
            )
    if not shown:
        report.line("(no parties name or count changed)")


def _vote_rows(report: Report, old: Measured, new: Measured, scope: set[str] | None) -> None:
    def summarise(measured: Measured) -> tuple[int | None, str | None]:
        if measured.votes is None:
            return None, None
        ids = {vote_id for number, _date, vote_id in measured.votes if _in(scope, number)}
        dates = [date for number, date, _id in measured.votes if _in(scope, number) and date]
        return len(ids), (max(dates) if dates else None)

    old_count, old_max = summarise(old)
    new_count, new_max = summarise(new)
    report.row("votes", old_count, new_count)
    report.row("newest vote date", old_max, new_max)


def _facts_rows(report: Report, old: Measured, new: Measured) -> None:
    if old.facts_rows is None or new.facts_rows is None:
        report.row("publishable periods", None, None)
        return
    for kind in ("week", "month"):
        def posted(rows: Mapping[tuple[str, str, str], tuple[int, int, Any]]) -> int:
            return len({(k, p) for (k, p, _m), (_c, publishable, _w) in rows.items() if publishable and k == kind})

        report.row(f"publishable {kind}s", posted(old.facts_rows), posted(new.facts_rows))
    newly_incomplete = sorted(
        (key, new.facts_rows[key][2])
        for key, (complete, _p, _w) in old.facts_rows.items()
        if complete and key in new.facts_rows and not new.facts_rows[key][0]
    )
    if newly_incomplete:
        periods: dict[tuple[str, str], str] = {}
        for (kind, period, _metric), reason in newly_incomplete:
            periods.setdefault((kind, period), str(reason or "no reason stored"))
        report.line(f"{len(periods)} periods newly incomplete:")
        for (kind, period), reason in list(periods.items())[:LIST_LIMIT]:
            report.line(f"  {kind} {period}: {reason}")
        if len(periods) > LIST_LIMIT:
            report.line(f"  ... {len(periods) - LIST_LIMIT} more")
    winners = (
        facts.changed_winners(old.facts_snapshot, new.facts_snapshot)
        if old.facts_snapshot is not None and new.facts_snapshot is not None
        else None
    )
    if winners is None:
        report.row("changed winners", None, None)
    elif not winners:
        report.line("changed winners: none")
    else:
        report.line(f"changed winners: {len(winners)}")
        for line in winners[:LIST_LIMIT]:
            report.line(f"  {line}")
        if len(winners) > LIST_LIMIT:
            report.line(f"  ... {len(winners) - LIST_LIMIT} more")


# ------------------------------------------------------------------------ cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="compare_store_values.py",
        description=(
            "Print old value, new value and delta for the quantities a data correction moves, "
            "comparing two site output directories. Read-only. "
            "Exit codes: 0 compared, 2 an input is not a readable output directory."
        ),
    )
    parser.add_argument("old_dir", type=Path, help="baseline output directory (holds data/bundestag-pulse.sqlite)")
    parser.add_argument("new_dir", type=Path, help="output directory after the change")
    parser.add_argument(
        "--cohort",
        choices=("shared", "all"),
        default="shared",
        help=(
            "shared (default): compare parsed-protocol quantities on the protocols both stores hold, "
            "so newly acquired sittings do not blur a value fix; all: whole-store coverage. "
            "Row counts, parties, generated pages and stored facts are always whole-store."
        ),
    )
    parser.add_argument(
        "--no-recipes",
        action="store_true",
        help="skip the Daten recipe row count (it unpacks each store's Verteilkopie)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        compare(args.old_dir, args.new_dir, cohort=args.cohort, recipes=not args.no_recipes)
    except CompareError as error:
        print(f"ERROR [compare]: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
