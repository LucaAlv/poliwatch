from __future__ import annotations

import json
import sqlite3
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


class PartyNameTests(unittest.TestCase):
    """DIP's person.fraktion is a list; the store must hold the plain name."""

    def test_a_list_valued_fraktion_persists_one_clean_party_row(self) -> None:
        report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
        report["sampled_people"] = [
            {
                "id": "dip-ada",
                "titel": "Ada Lovelace, MdB, SPD",
                "fraktion": ["SPD"],
                "funktion": "Mitglied",
                "wahlperiode": "20",
            },
            {
                "id": "dip-bruno",
                "titel": "Bruno Beispiel, MdB",
                "fraktion": ["DIE LINKE", "fraktionslos"],
                "funktion": "Mitglied",
                "wahlperiode": "20",
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.persist_report(conn, report)
                names = {row["name"] for row in conn.execute("SELECT name FROM parties")}
            finally:
                conn.close()

        self.assertIn("SPD", names)
        self.assertIn("Die Linke", names)
        self.assertFalse(
            [name for name in names if name.startswith("[")],
            f"a list repr reached parties.name: {sorted(names)}",
        )

    def test_unwrap_dip_faction_reads_lists_and_the_repr_the_bug_left_behind(self) -> None:
        self.assertEqual(pulse_store.unwrap_dip_faction(["CDU/CSU"]), "CDU/CSU")
        self.assertEqual(pulse_store.unwrap_dip_faction("['CDU/CSU']"), "CDU/CSU")
        self.assertEqual(pulse_store.unwrap_dip_faction("['SPD', 'AfD']"), "SPD")
        self.assertEqual(pulse_store.unwrap_dip_faction("CDU/CSU"), "CDU/CSU")
        self.assertIsNone(pulse_store.unwrap_dip_faction([]))
        self.assertIsNone(pulse_store.unwrap_dip_faction(None))
        # Not a repr, so it survives: the "[…]" shape alone does not mean list.
        self.assertEqual(pulse_store.unwrap_dip_faction("[nicht lesbar]"), "[nicht lesbar]")


class PartyMigrationTests(unittest.TestCase):
    """initialize() merges the duplicate rows the list-repr bug left in a store."""

    def _seed_dirty_store(self, conn) -> dict[str, int]:
        now = pulse_store.utc_now()
        ids = {}
        for name in ("CDU/CSU", "['CDU/CSU']", "['DIE LINKE']", "['BSW (Gruppe)']"):
            conn.execute(
                "INSERT INTO parties(name, created_at, updated_at) VALUES (?, ?, ?)",
                (name, now, now),
            )
            ids[name] = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
        for index, name in enumerate(("CDU/CSU", "['CDU/CSU']", "['DIE LINKE']", "['BSW (Gruppe)']")):
            pulse_store.upsert_mp(
                conn,
                now=now,
                display_name=f"MdB {index}",
                party_id=ids[name],
                identity_key=f"dip:seed-{index}",
            )
        conn.execute(
            "INSERT INTO votes(id, created_at, updated_at) VALUES ('v1', ?, ?)", (now, now)
        )
        for name, yes in (("CDU/CSU", 5), ("['CDU/CSU']", 3), ("['DIE LINKE']", 2)):
            conn.execute(
                """
                INSERT INTO vote_fractions(vote_id, party_id, yes_count, total_count)
                VALUES ('v1', ?, ?, ?)
                """,
                (ids[name], yes, yes),
            )
        mp_id = int(
            conn.execute("SELECT id FROM mps WHERE identity_key = 'dip:seed-1'").fetchone()["id"]
        )
        conn.execute(
            "INSERT INTO vote_members(vote_id, mp_id, party_id, vote) VALUES ('v1', ?, ?, 'yes')",
            (mp_id, ids["['CDU/CSU']"]),
        )
        return ids

    def test_migration_merges_duplicates_and_leaves_no_dangling_party_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                ids = self._seed_dirty_store(conn)

                pulse_store.initialize(conn)

                names = [row["name"] for row in conn.execute("SELECT name FROM parties ORDER BY name")]
                self.assertEqual(names, ["BSW (Gruppe)", "CDU/CSU", "Die Linke"])
                self.assertEqual(len(names), len(set(names)))

                dangling = conn.execute(
                    """
                    SELECT COUNT(*) AS n FROM mps
                     WHERE party_id IS NOT NULL
                       AND party_id NOT IN (SELECT id FROM parties)
                    """
                ).fetchone()["n"]
                self.assertEqual(dangling, 0)
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) AS n FROM mps WHERE party_id IS NULL").fetchone()["n"],
                    0,
                )

                # Both CDU/CSU MdBs now point at the surviving row.
                kept = int(conn.execute("SELECT id FROM parties WHERE name = 'CDU/CSU'").fetchone()["id"])
                self.assertEqual(kept, ids["CDU/CSU"])
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) AS n FROM mps WHERE party_id = ?", (kept,)
                    ).fetchone()["n"],
                    2,
                )

                # The duplicate's vote_fractions row was absorbed, not dropped.
                fractions = {
                    row["name"]: row["yes_count"]
                    for row in conn.execute(
                        """
                        SELECT p.name, vf.yes_count FROM vote_fractions vf
                        JOIN parties p ON p.id = vf.party_id
                        """
                    )
                }
                self.assertEqual(fractions, {"CDU/CSU": 8, "Die Linke": 2})
                self.assertEqual(
                    conn.execute(
                        "SELECT party_id FROM vote_members WHERE vote_id = 'v1'"
                    ).fetchone()["party_id"],
                    kept,
                )

                # Idempotent: a second pass over a clean store changes nothing.
                before = conn.execute("SELECT id, name FROM parties ORDER BY id").fetchall()
                pulse_store.initialize(conn)
                after = conn.execute("SELECT id, name FROM parties ORDER BY id").fetchall()
                self.assertEqual([tuple(row) for row in before], [tuple(row) for row in after])
            finally:
                conn.close()

    def test_a_merge_that_flips_the_majority_recomputes_leading_vote(self) -> None:
        # meiste-abweichler counts a member as a dissenter via
        # vm.vote <> vf.leading_vote, so a merge that changes the majority
        # without updating leading_vote would silently swap who counts as
        # loyal vs. dissenting for every vote_member row already keyed to
        # the surviving party.
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                now = pulse_store.utc_now()
                conn.execute(
                    "INSERT INTO parties(name, created_at, updated_at) VALUES ('CDU/CSU', ?, ?)",
                    (now, now),
                )
                canonical_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
                conn.execute(
                    "INSERT INTO parties(name, created_at, updated_at) VALUES (\"['CDU/CSU']\", ?, ?)",
                    (now, now),
                )
                duplicate_id = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
                conn.execute("INSERT INTO votes(id, created_at, updated_at) VALUES ('v1', ?, ?)", (now, now))
                # Canonical row: a lone "yes" (leading_vote "yes"). Duplicate:
                # ten "no" votes (leading_vote "no"). Merged majority is "no".
                conn.execute(
                    "INSERT INTO vote_fractions(vote_id, party_id, yes_count, no_count, total_count, leading_vote) "
                    "VALUES ('v1', ?, 1, 0, 1, 'yes')",
                    (canonical_id,),
                )
                conn.execute(
                    "INSERT INTO vote_fractions(vote_id, party_id, yes_count, no_count, total_count, leading_vote) "
                    "VALUES ('v1', ?, 0, 10, 10, 'no')",
                    (duplicate_id,),
                )
                conn.commit()

                pulse_store.initialize(conn)

                row = conn.execute(
                    "SELECT yes_count, no_count, total_count, leading_vote FROM vote_fractions WHERE vote_id = 'v1'"
                ).fetchone()
                self.assertEqual(dict(row), {"yes_count": 1, "no_count": 10, "total_count": 11, "leading_vote": "no"})
            finally:
                conn.close()


class SpeechFraktionTests(unittest.TestCase):
    def test_speeches_carry_the_fraktion_the_protocol_names(self) -> None:
        report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
        speakers = report["agenda_items"][0]["xml_speakers"]
        speakers[0]["speaker"]["fraktion"] = "B90/GRÜNE"
        speakers[1]["speaker"].pop("fraktion", None)
        speakers[1]["speaker"]["role"] = "Bundesminister für Gesundheit"

        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.persist_report(conn, report)
                rows = {
                    row["rede_id"]: (row["fraktion"], row["party"])
                    for row in conn.execute(
                        """
                        SELECT s.rede_id, s.fraktion, p.name AS party
                        FROM speeches s
                        LEFT JOIN mps m ON m.id = s.mp_id
                        LEFT JOIN parties p ON p.id = m.party_id
                        """
                    )
                }
            finally:
                conn.close()

        # Normalised the same way parties.name is.
        self.assertEqual(rows["R1"][0], "BÜNDNIS 90/DIE GRÜNEN")
        # No Fraktion in the XML: NULL, and the reader falls back to the party.
        self.assertIsNone(rows["R2"][0])
        self.assertEqual(rows["R2"][1], "Regierung")

    @unittest.skipUnless(
        sqlite3.sqlite_version_info >= (3, 35),
        "ALTER TABLE ... DROP COLUMN needs SQLite 3.35+ to stage the old schema",
    )
    def test_the_column_is_added_to_a_store_that_predates_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pulse.sqlite"
            conn = pulse_store.connect(path)
            try:
                pulse_store.initialize(conn)
                conn.execute("ALTER TABLE speeches DROP COLUMN fraktion")
                self.assertNotIn(
                    "fraktion",
                    {row["name"] for row in conn.execute("PRAGMA table_info(speeches)")},
                )

                pulse_store.initialize(conn)

                self.assertIn(
                    "fraktion",
                    {row["name"] for row in conn.execute("PRAGMA table_info(speeches)")},
                )
            finally:
                conn.close()


class ConnectGuardTests(unittest.TestCase):
    def test_connect_refuses_a_store_with_a_nonzero_user_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "distribution.sqlite"
            conn = pulse_store.connect(db_path)
            conn.execute("PRAGMA user_version = 1")
            conn.close()

            with self.assertRaises(RuntimeError) as ctx:
                pulse_store.connect(db_path)
            self.assertIn("distribution copy", str(ctx.exception))

    def test_connect_refuses_a_store_with_a_datenstand_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "distribution.sqlite"
            conn = pulse_store.connect(db_path)
            conn.execute("CREATE TABLE datenstand (tag TEXT)")
            conn.close()

            with self.assertRaises(RuntimeError):
                pulse_store.connect(db_path)

    def test_connect_accepts_an_ordinary_build_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "pulse.sqlite"
            conn = pulse_store.connect(db_path)
            pulse_store.initialize(conn)
            conn.close()
            # Reconnecting to a normal, already-initialized store must not raise.
            conn = pulse_store.connect(db_path)
            conn.close()


if __name__ == "__main__":
    unittest.main()
