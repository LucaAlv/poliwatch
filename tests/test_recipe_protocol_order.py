"""Recipes pick "the first sitting" by protocol number, not by its text: Plenarprotokoll
21/99 comes before 21/100 (TODOS.md "Recipe SQL disagrees with the site's own counting
rules in edge cases", item 1)."""

from __future__ import annotations

import sqlite3
import unittest

import _support  # noqa: F401
import build_dip_pulse_site as build
import persist_dip_pulse_store as pulse_store

STAMP = "2026-11-04T00:00:00Z"


def store() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    pulse_store.initialize(conn)
    return conn


def add_sitting(conn: sqlite3.Connection, number: str, *agenda_items: str) -> None:
    """A Plenarprotokoll `number` with one agenda item per id in `agenda_items`."""
    conn.execute(
        "INSERT INTO protocols (id, document_number, date, created_at, updated_at) VALUES (?, ?, '2026-01-01', ?, ?)",
        (f"p{number}", number, STAMP, STAMP),
    )
    for index, item_id in enumerate(agenda_items, 1):
        conn.execute(
            "INSERT INTO agenda_items (id, protocol_id, item_index, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (item_id, f"p{number}", index, STAMP, STAMP),
        )


def add_vote(conn: sqlite3.Connection, vote_id: str, *agenda_items: str) -> None:
    conn.execute(
        "INSERT INTO votes (id, date, title, yes_count, no_count, created_at, updated_at) VALUES (?, '2026-01-01', 'V', 5, 4, ?, ?)",
        (vote_id, STAMP, STAMP),
    )
    for item_id in agenda_items:
        conn.execute("INSERT INTO agenda_item_votes (agenda_item_id, vote_id) VALUES (?, ?)", (item_id, vote_id))


class RecipeProtocolOrderTests(unittest.TestCase):
    def test_a_vote_in_two_sittings_belongs_to_the_numerically_first_one(self) -> None:
        conn = store()
        self.addCleanup(conn.close)
        # 21/100 < 21/99 as text; the sitting that came first is 21/99.
        add_sitting(conn, "21/100", "a100")
        add_sitting(conn, "21/99", "a99")
        add_vote(conn, "v1", "a100", "a99")
        row = conn.execute(build.RECIPES_BY_ID["r4-knappste-abstimmungen"]["sql"]).fetchone()
        self.assertEqual(row["document_number"], "21/99")

    def test_the_wahlperiode_decides_before_the_sitting_number(self) -> None:
        conn = store()
        self.addCleanup(conn.close)
        add_sitting(conn, "20/200", "a20")
        add_sitting(conn, "21/5", "a21")
        add_vote(conn, "v1", "a21", "a20")
        row = conn.execute(build.RECIPES_BY_ID["r4-knappste-abstimmungen"]["sql"]).fetchone()
        self.assertEqual((row["document_number"], row["wahlperiode"]), ("20/200", 20))

    def test_a_vote_in_one_sitting_still_belongs_to_it(self) -> None:
        conn = store()
        self.addCleanup(conn.close)
        add_sitting(conn, "21/100", "a100")
        add_vote(conn, "v1", "a100")
        row = conn.execute(build.RECIPES_BY_ID["r4-knappste-abstimmungen"]["sql"]).fetchone()
        self.assertEqual(row["document_number"], "21/100")

    def test_a_proceeding_names_its_numerically_first_sitting(self) -> None:
        conn = store()
        self.addCleanup(conn.close)
        add_sitting(conn, "21/100", "a100")
        add_sitting(conn, "21/99", "a99")
        conn.execute("INSERT INTO proceedings (id, title, created_at, updated_at) VALUES ('pr1', 'T', ?, ?)", (STAMP, STAMP))
        for item_id in ("a100", "a99"):
            conn.execute(
                "INSERT INTO proceeding_positions (id, proceeding_id, agenda_item_id, created_at, updated_at) VALUES (?, 'pr1', ?, ?, ?)",
                (f"pp-{item_id}", item_id, STAMP, STAMP),
            )
            conn.execute(
                "INSERT INTO speeches (id, protocol_id, agenda_item_id, sequence, created_at, updated_at) "
                "VALUES (?, ?, ?, 1, ?, ?)",
                (f"s-{item_id}", "p" + ("21/100" if item_id == "a100" else "21/99"), item_id, STAMP, STAMP),
            )
        row = conn.execute(build.RECIPES_BY_ID["r5-vorgaenge-meiste-reden"]["sql"]).fetchone()
        self.assertEqual((row["erste_drucksache"], row["sitzungen"]), ("21/99", 2))


if __name__ == "__main__":
    unittest.main()
