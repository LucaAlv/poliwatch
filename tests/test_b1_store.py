from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path

import _support  # noqa: F401
import persist_dip_pulse_store as pulse_store
from _support import FIXTURES


class SittingVotePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def tearDown(self):
        self.conn.close()

    def test_sitting_level_vote_persists_interpretation_without_agenda_link(self):
        vote = self.report["agenda_items"][0]["votes"][0]
        self.report["agenda_items"][0]["votes"] = []
        vote.update(
            inverted=True,
            inversion_source="bundestag_heading",
            inversion_excerpt="Abstimmung über die Ablehnung des Antrags",
            result_scope="proposition",
            procedure_type="ordinary",
        )
        self.report["sitting_votes"] = [vote]

        pulse_store.persist_report(self.conn, self.report)
        pulse_store.persist_report(self.conn, self.report)

        row = self.conn.execute("SELECT * FROM votes WHERE id = ?", (vote["id"],)).fetchone()
        self.assertEqual(row["protocol_id"], self.report["protocol"]["id"])
        self.assertEqual(row["inverted"], 1)
        self.assertEqual(row["inversion_source"], "bundestag_heading")
        self.assertEqual(row["inversion_excerpt"], vote["inversion_excerpt"])
        self.assertEqual(row["result_scope"], "proposition")
        self.assertEqual(row["procedure_type"], "ordinary")
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM agenda_item_votes WHERE vote_id = ?", (vote["id"],)).fetchone()[0],
            0,
        )
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0], 1)

    def test_removed_sitting_vote_is_pruned_when_report_is_replaced(self):
        vote = self.report["agenda_items"][0]["votes"][0]
        self.report["agenda_items"][0]["votes"] = []
        self.report["sitting_votes"] = [vote]
        pulse_store.persist_report(self.conn, self.report)
        self.report["sitting_votes"] = []

        pulse_store.persist_report(self.conn, self.report)

        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0], 0)

    def test_duplicate_vote_keeps_each_top_link_while_stored_once(self):
        vote = self.report["agenda_items"][0]["votes"][0]
        self.report["agenda_items"][1]["votes"] = [dict(vote)]

        pulse_store.persist_report(self.conn, self.report)

        links = self.conn.execute(
            """SELECT COUNT(*) FROM agenda_item_votes WHERE vote_id = ?""", (vote["id"],)
        ).fetchone()[0]
        self.assertEqual(links, 2)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0], 1)

    def test_initialize_does_not_infer_sitting_id_from_top_link(self):
        pulse_store.persist_report(self.conn, self.report)
        vote_id = self.report["agenda_items"][0]["votes"][0]["id"]
        self.conn.execute("UPDATE votes SET protocol_id = NULL WHERE id = ?", (vote_id,))

        pulse_store.initialize(self.conn)

        protocol_id = self.conn.execute(
            "SELECT protocol_id FROM votes WHERE id = ?", (vote_id,)
        ).fetchone()[0]
        self.assertIsNone(protocol_id)

    def test_fresh_schema_has_vote_interpretation_and_protocol_columns(self):
        pulse_store.initialize(self.conn)
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(votes)")}
        self.assertTrue(
            {
                "protocol_id",
                "inverted",
                "inversion_source",
                "inversion_excerpt",
                "result_scope",
                "procedure_type",
            }.issubset(columns)
        )

    def test_initialize_does_not_upgrade_legacy_vote_schema(self):
        # Recreate the relevant portion of schema v1, which had no sitting
        # foreign key or interpretation columns on votes.
        self.conn.executescript(
            """
            CREATE TABLE protocols (id TEXT PRIMARY KEY);
            CREATE TABLE agenda_items (
              id INTEGER PRIMARY KEY, protocol_id TEXT NOT NULL, item_index INTEGER NOT NULL
            );
            CREATE TABLE votes (
              id TEXT PRIMARY KEY, date TEXT, topic TEXT, title TEXT, description TEXT,
              detail_url TEXT, yes_count INTEGER NOT NULL DEFAULT 0,
              no_count INTEGER NOT NULL DEFAULT 0, abstain_count INTEGER NOT NULL DEFAULT 0,
              absent_count INTEGER NOT NULL DEFAULT 0, result_raw TEXT, result_source TEXT,
              xlsx_url TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE agenda_item_votes (
              agenda_item_id INTEGER NOT NULL, vote_id TEXT NOT NULL,
              PRIMARY KEY (agenda_item_id, vote_id)
            );
            INSERT INTO protocols VALUES ('legacy-protocol');
            INSERT INTO agenda_items VALUES (7, 'legacy-protocol', 1);
            INSERT INTO votes (id, title, yes_count, created_at, updated_at)
              VALUES ('legacy-vote', 'Preserved title', 42, 'old', 'old');
            INSERT INTO agenda_item_votes VALUES (7, 'legacy-vote');
            """
        )

        pulse_store.initialize(self.conn)

        row = self.conn.execute("SELECT * FROM votes WHERE id = 'legacy-vote'").fetchone()
        self.assertEqual(row["title"], "Preserved title")
        self.assertEqual(row["yes_count"], 42)
        columns = {column["name"] for column in self.conn.execute("PRAGMA table_info(votes)")}
        self.assertTrue({"protocol_id", "inverted", "result_scope"}.isdisjoint(columns))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM agenda_item_votes").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
