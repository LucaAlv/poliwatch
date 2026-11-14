"""The vote outcome and the Abweichler figures are persisted (plan
docs/plans/vote-links-and-figures.md, part 2): ``votes.application_result``,
``votes.abweichler_count`` and ``vote_members.abweichung`` are written at persist
by the derive functions, so every SQL reader (recipe r3, the Fakten metric, the
archive, the store gate) counts one definition."""

from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any

import _support  # noqa: F401
import _site_store_fixture
import build_dip_pulse_site as build
import derive
import facts
import persist_dip_pulse_store as pulse_store
import validate_store_gate as gate
from _support import FIXTURES


def member(name: str, faction: Any, vote: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "faction": faction, "vote": vote, **extra}


def fraction(name: Any, yes: int = 0, no: int = 0, abstain: int = 0, absent: int = 0) -> dict[str, Any]:
    return {"name": name, "counts": {"yes": yes, "no": no, "abstain": abstain, "absent": absent},
            "total": yes + no + abstain + absent}


def make_vote(fractions: list[dict[str, Any]], members: list[dict[str, Any]], **fields: Any) -> dict[str, Any]:
    """A vote of the fixture report with these rows; its total is the sum of the rows."""
    total = {key: sum(row["counts"][key] for row in fractions) for key in derive.VOTE_COUNT_KEYS}
    return {"id": "12345", "date": "2024-05-15", "title": "Abstimmung zur Drucksache 20/123",
            "document_numbers": ["20/123"], "total": total, "fractions": fractions, "members": members,
            "result_raw": "accepted", "result_source": "official", "result_scope": "proposition", **fields}


def report_with(vote: dict[str, Any]) -> dict[str, Any]:
    report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
    report["agenda_items"][0]["votes"] = [vote]
    return report


#: Complete groups, one SPD member votes Nein against a Ja Mehrheitsvotum.
ONE_DEVIATOR = make_vote(
    [fraction("SPD", yes=2, no=1), fraction("CDU/CSU", no=2)],
    [member("Anna A", "SPD", "yes"), member("Ben B", "SPD", "yes"), member("Cem C", "SPD", "no"),
     member("Dora D", "CDU/CSU", "no"), member("Emil E", "CDU/CSU", "no")],
)


class Store:
    """A store holding one persisted report."""

    def __init__(self, report: dict[str, Any]) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = pulse_store.connect(Path(self.tmp.name) / "pulse.sqlite")
        pulse_store.initialize(self.conn)
        with self.conn:
            pulse_store.persist_report(self.conn, report)

    def close(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def vote_row(self) -> dict[str, Any]:
        return dict(self.conn.execute("SELECT application_result, abweichler_count FROM votes").fetchone())

    def flags(self) -> dict[str, Any]:
        """Member display name -> vote_members.abweichung."""
        return {row[0]: row[1] for row in self.conn.execute(
            "SELECT m.display_name, vm.abweichung FROM vote_members vm JOIN mps m ON m.id = vm.mp_id")}


def persisted(vote: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    store = Store(report_with(copy.deepcopy(vote)))
    try:
        return store.vote_row(), store.flags()
    finally:
        store.close()


class PersistedColumnsEqualDeriveTests(unittest.TestCase):
    """Each column equals the derive function it is written from."""

    def assert_matches_derive(self, vote: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        row, flags = persisted(vote)
        self.assertEqual(row["application_result"], derive.vote_outcome(vote))
        self.assertEqual(row["abweichler_count"], derive.vote_abweichler_count(vote))
        if row["abweichler_count"] is not None:
            self.assertEqual(sum(flag for flag in flags.values() if flag), row["abweichler_count"])
        return row, flags

    def test_complete_groups_with_one_deviator(self) -> None:
        row, flags = self.assert_matches_derive(ONE_DEVIATOR)
        self.assertEqual(row, {"application_result": "accepted", "abweichler_count": 1})
        self.assertEqual(flags, {"Anna A": 0, "Ben B": 0, "Cem C": 1, "Dora D": 0, "Emil E": 0})

    def test_a_partial_group_names_nobody_in_it(self) -> None:
        # The SPD counts three Stimmen, the member list holds two: nobody in the
        # SPD can be named, and the vote-wide count is unknown.
        vote = make_vote(
            [fraction("SPD", yes=2, no=1), fraction("CDU/CSU", yes=1, no=2)],
            [member("Anna A", "SPD", "yes"), member("Cem C", "SPD", "no"),
             member("Dora D", "CDU/CSU", "no"), member("Emil E", "CDU/CSU", "no"), member("Fritz F", "CDU/CSU", "yes")],
        )
        row, flags = self.assert_matches_derive(vote)
        self.assertIsNone(row["abweichler_count"])
        self.assertEqual(flags, {"Anna A": None, "Cem C": None, "Dora D": 0, "Emil E": 0, "Fritz F": 1})

    def test_an_unbekannt_member_with_a_fraction_row_is_never_an_abweichung(self) -> None:
        vote = make_vote(
            [fraction("SPD", yes=2), fraction(None, yes=2, no=1)],
            [member("Anna A", "SPD", "yes"), member("Ben B", "SPD", "yes"),
             member("Ulla U", None, "yes"), member("Uwe U", None, "yes"), member("Ute U", None, "no")],
        )
        row, flags = self.assert_matches_derive(vote)
        self.assertEqual(row["abweichler_count"], 0)
        self.assertEqual(flags, {"Anna A": 0, "Ben B": 0, "Ulla U": None, "Uwe U": None, "Ute U": None})

    def test_a_fraktionslos_member_is_never_an_abweichung(self) -> None:
        vote = make_vote(
            [fraction("SPD", yes=2), fraction("fraktionslos", yes=2, no=1)],
            [member("Anna A", "SPD", "yes"), member("Ben B", "SPD", "yes"),
             member("Fia F", "fraktionslos", "yes"), member("Finn F", "fraktionslos", "yes"),
             member("Fred F", "fraktionslos", "no")],
        )
        row, flags = self.assert_matches_derive(vote)
        self.assertEqual(row["abweichler_count"], 0)
        self.assertEqual({name: flag for name, flag in flags.items() if name.startswith("F")},
                         {"Fia F": None, "Finn F": None, "Fred F": None})

    def test_no_mehrheitsvotum_and_enthaltung_are_zero(self) -> None:
        # A tie and an Enthaltung Mehrheitsvotum: no Stimme is an Abweichung
        # (CONTEXT.md), so the flags are 0, not unknown.
        vote = make_vote(
            [fraction("SPD", yes=1, no=1), fraction("FDP", yes=1, abstain=2)],
            [member("Anna A", "SPD", "yes"), member("Cem C", "SPD", "no"),
             member("Gus G", "FDP", "yes"), member("Hanna H", "FDP", "abstain"), member("Ida I", "FDP", "abstain")],
        )
        row, flags = self.assert_matches_derive(vote)
        self.assertEqual(row["abweichler_count"], 0)
        self.assertEqual(set(flags.values()), {0})

    def test_no_fraction_rows_names_nobody(self) -> None:
        vote = make_vote([], [member("Anna A", "SPD", "yes")])
        vote["total"] = {"yes": 1, "no": 0, "abstain": 0, "absent": 0}
        row, flags = self.assert_matches_derive(vote)
        self.assertIsNone(row["abweichler_count"])
        self.assertEqual(flags, {"Anna A": None})

    def test_the_outcome_follows_inversion_and_scope(self) -> None:
        cases = [
            ({"inverted": True, "result_scope": "proposition"}, "rejected"),
            ({"inverted": True, "result_scope": "application"}, "accepted"),
            ({"inverted": None}, "accepted"),
            ({"result_raw": "rejected", "inverted": True, "result_scope": "proposition"}, "accepted"),
            ({"result_raw": None, "result_source": None}, None),
        ]
        for fields, expected in cases:
            with self.subTest(fields=fields):
                vote = {**copy.deepcopy(ONE_DEVIATOR), **fields}
                row, _flags = self.assert_matches_derive(vote)
                self.assertEqual(row["application_result"], expected)

    def test_a_refiled_member_counts_against_the_group_it_is_filed_to(self) -> None:
        # The page lists Cem C under the SPD; the Stammdaten file him to the
        # CDU/CSU, whose Mehrheitsvotum is Nein like his Stimme.
        vote = copy.deepcopy(ONE_DEVIATOR)
        vote["members"][2]["refiled_to"] = "CDU/CSU"
        row, flags = self.assert_matches_derive(vote)
        self.assertEqual(row["abweichler_count"], 0)
        self.assertEqual(flags["Cem C"], 0)

    def test_a_member_listed_twice_takes_the_last_rows_flag(self) -> None:
        vote = copy.deepcopy(ONE_DEVIATOR)
        vote["members"].append(member("Cem C", "SPD", "yes"))
        vote["fractions"][0] = fraction("SPD", yes=3)
        vote["total"]["yes"], vote["total"]["no"] = 3, 2
        row, flags = self.assert_matches_derive(vote)
        self.assertEqual(row["abweichler_count"], 0)
        self.assertEqual(flags["Cem C"], 0)


class MergeRecomputesTests(unittest.TestCase):
    def test_a_vote_fractions_merge_rewrites_the_figures(self) -> None:
        # Persisted with the FDP apart, nobody deviates. A store whose FDP row
        # turns out to be an old spelling of the CDU/CSU merges the two rows on
        # the next initialize: CDU/CSU then has a Ja Mehrheitsvotum (3:2), and
        # its two Nein Stimmen are Abweichungen.
        vote = make_vote(
            [fraction("SPD", yes=3), fraction("CDU/CSU", no=2), fraction("FDP", yes=3)],
            [member("Anna A", "SPD", "yes"), member("Ben B", "SPD", "yes"), member("Cem C", "SPD", "yes"),
             member("Dora D", "CDU/CSU", "no"), member("Emil E", "CDU/CSU", "no"),
             member("Gus G", "FDP", "yes"), member("Hanna H", "FDP", "yes"), member("Ida I", "FDP", "yes")],
        )
        store = Store(report_with(vote))
        try:
            self.assertEqual(store.vote_row()["abweichler_count"], 0)
            store.conn.execute("UPDATE parties SET name = ? WHERE name = 'FDP'", ("['CDU/CSU']",))
            store.conn.commit()
            pulse_store.initialize(store.conn)
            self.assertEqual(store.vote_row(), {"application_result": "accepted", "abweichler_count": 2})
            flags = store.flags()
            self.assertEqual({name for name, flag in flags.items() if flag == 1}, {"Dora D", "Emil E"})
            self.assertEqual({flag for name, flag in flags.items() if name not in {"Dora D", "Emil E"}}, {0})
        finally:
            store.close()


class ReadersUseTheColumnsTests(unittest.TestCase):
    R3 = next(recipe for recipe in build.RECIPES if recipe["id"] == "r3-abweichler")

    def r3_rows(self, conn: sqlite3.Connection) -> list[tuple]:
        conn.execute("DROP TABLE IF EXISTS temp.mp_canonical")
        conn.execute("CREATE TEMP TABLE mp_canonical AS SELECT id AS mp_id, person_id AS canonical_id, 1 AS has_page FROM mps")
        return [tuple(row)[2:] for row in conn.execute(self.R3["sql"].rstrip().removesuffix("LIMIT 5;"))]

    def test_r3_counts_the_persisted_abweichungen(self) -> None:
        store = Store(report_with(copy.deepcopy(ONE_DEVIATOR)))
        try:
            self.assertEqual(self.r3_rows(store.conn), [("Cem C", "SPD", 1)])
        finally:
            store.close()

    def test_r3_counts_nobody_in_a_partial_group_or_unbekannt(self) -> None:
        # The SQL before the column counted Cem C (a partial group) and Ute U
        # (Unbekannt with a fraction row); neither is an Abweichung now.
        vote = make_vote(
            [fraction("SPD", yes=2, no=1), fraction(None, yes=2, no=1)],
            [member("Anna A", "SPD", "yes"), member("Cem C", "SPD", "no"),
             member("Ulla U", None, "yes"), member("Uwe U", None, "yes"), member("Ute U", None, "no")],
        )
        store = Store(report_with(vote))
        try:
            self.assertEqual(self.r3_rows(store.conn), [])
        finally:
            store.close()

    def test_the_fakten_metric_reads_the_vote_count(self) -> None:
        metric = facts.REGISTRY_BY_ID["meiste-abweichler"]
        store = Store(report_with(copy.deepcopy(ONE_DEVIATOR)))
        try:
            rows = [dict(row) for row in store.conn.execute(metric["sql"])]
            self.assertEqual([row["value"] for row in rows], [1])
            store.conn.execute("UPDATE votes SET abweichler_count = NULL")
            self.assertEqual([row["value"] for row in store.conn.execute(metric["sql"])], [None])
        finally:
            store.close()

    def test_the_archive_reads_the_count_and_the_outcome_from_the_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _site_store_fixture.build_site_store(
                Path(tmp) / "site", _site_store_fixture.persistable([{"report": report_with(copy.deepcopy(ONE_DEVIATOR))}]))
            conn = sqlite3.connect(path)
            try:
                # Values no derive function would give for these rows: the
                # archive shows what the store holds.
                conn.execute("UPDATE votes SET abweichler_count = 7, application_result = 'rejected'")
                conn.commit()
            finally:
                conn.close()
            rows = build.votes_archive_rows(path)
        self.assertEqual(rows[0]["abweichler"], 7)
        markup = build.render_votes_archive_index(rows)
        self.assertIn('<span class="vote-result vote-result-rejected"', markup)
        self.assertNotIn('<span class="vote-result vote-result-accepted"', markup)

    def test_the_gate_finds_a_count_that_differs_from_its_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _site_store_fixture.build_site_store(
                Path(tmp) / "site", _site_store_fixture.persistable([{"report": report_with(copy.deepcopy(ONE_DEVIATOR))}]))
            self.assertEqual(gate.abweichler_count_mismatches(path), [])
            conn = sqlite3.connect(path)
            try:
                conn.execute("UPDATE votes SET abweichler_count = 2")
                conn.commit()
            finally:
                conn.close()
            self.assertEqual(gate.abweichler_count_mismatches(path), ["12345 abweichler_count 2, SUM(abweichung) 1"])


class SchemaTests(unittest.TestCase):
    def test_a_store_without_the_figure_columns_is_refused(self) -> None:
        for table, column in (("votes", "abweichler_count"), ("votes", "application_result"), ("vote_members", "abweichung")):
            with self.subTest(column=f"{table}.{column}"), tempfile.TemporaryDirectory() as tmp:
                conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
                try:
                    pulse_store.initialize(conn)
                    conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
                    with self.assertRaisesRegex(RuntimeError, "Old build-store schema"):
                        pulse_store.require_current_schema(conn)
                finally:
                    conn.close()


if __name__ == "__main__":
    unittest.main()
