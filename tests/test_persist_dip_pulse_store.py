from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401
import persist_dip_pulse_store as pulse_store
from _support import FIXTURES


class PersistReportTests(unittest.TestCase):
    def test_persist_report_writes_expected_graph_and_is_idempotent(self) -> None:
        report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.persist_report(conn, report)
                first_counts = self._counts(conn)

                self.assertEqual(first_counts["protocols"], 1)
                self.assertEqual(first_counts["agenda_items"], 2)
                self.assertEqual(first_counts["speeches"], 3)
                self.assertEqual(first_counts["votes"], 1)
                self.assertEqual(first_counts["vote_members"], 2)
                self.assertEqual(first_counts["vote_fractions"], 2)
                self.assertEqual(first_counts["parties"], 3)
                self.assertEqual(first_counts["documents"], 2)
                self.assertEqual(first_counts["mps"], 6)

                row = conn.execute(
                    """
                    SELECT s.rede_id, m.display_name, p.name AS party
                    FROM speeches s
                    JOIN mps m ON s.mp_id = m.id
                    LEFT JOIN parties p ON m.party_id = p.id
                    WHERE s.rede_id = 'R1'
                    """
                ).fetchone()
                self.assertEqual(dict(row), {"rede_id": "R1", "display_name": "Ada Lovelace", "party": "SPD"})

                votes = {
                    row["display_name"]: row["vote"]
                    for row in conn.execute(
                        """
                        SELECT m.display_name, vm.vote
                        FROM vote_members vm
                        JOIN mps m ON vm.mp_id = m.id
                        ORDER BY m.display_name
                        """
                    )
                }
                self.assertEqual(votes, {"Ada Lovelace": "yes", "Bruno Beispiel": "no"})

                pulse_store.persist_report(conn, report)
                self.assertEqual(self._counts(conn), first_counts)
            finally:
                conn.close()

    def _counts(self, conn) -> dict[str, int]:
        tables = [
            "protocols",
            "agenda_items",
            "speeches",
            "votes",
            "vote_members",
            "vote_fractions",
            "parties",
            "documents",
            "mps",
        ]
        return {
            table: int(conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"])
            for table in tables
        }


if __name__ == "__main__":
    unittest.main()
