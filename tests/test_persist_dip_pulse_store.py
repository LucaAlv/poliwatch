from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import _support  # noqa: F401
import persist_dip_pulse_store as pulse_store
from _support import FIXTURES


class ParagraphMigrationTests(unittest.TestCase):
    def test_initialize_omits_paragraphs_and_accepts_already_absent_column(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        with conn:
            pulse_store.initialize(conn)
            pulse_store.initialize(conn)
        self.assertNotIn("paragraphs_json", {r["name"] for r in conn.execute("PRAGMA table_info(speeches)")})
        conn.close()

    def test_initialize_migrates_existing_speeches_without_changing_other_data(self):
        report = json.loads((FIXTURES / "report.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "store.sqlite")
            pulse_store.persist_report(conn, report)
            if "paragraphs_json" not in {r["name"] for r in conn.execute("PRAGMA table_info(speeches)")}:
                conn.execute("ALTER TABLE speeches ADD COLUMN paragraphs_json TEXT NOT NULL DEFAULT '[]'")
            columns = [r["name"] for r in conn.execute("PRAGMA table_info(speeches)") if r["name"] != "paragraphs_json"]
            query = "SELECT " + ", ".join(columns) + " FROM speeches ORDER BY id"
            before = [tuple(r) for r in conn.execute(query)]
            with conn:
                pulse_store.initialize(conn)
            self.assertNotIn("paragraphs_json", {r["name"] for r in conn.execute("PRAGMA table_info(speeches)")})
            self.assertEqual(before, [tuple(r) for r in conn.execute(query)])
            self.assertEqual([], list(conn.execute("PRAGMA foreign_key_check")))
            conn.close()

    def test_old_sqlite_warns_and_keeps_legacy_column(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        pulse_store.initialize(conn)
        if "paragraphs_json" not in {r["name"] for r in conn.execute("PRAGMA table_info(speeches)")}:
            conn.execute("ALTER TABLE speeches ADD COLUMN paragraphs_json TEXT NOT NULL DEFAULT '[]'")
        with mock.patch.object(sqlite3, "sqlite_version", "3.34.1"):
            with self.assertLogs(pulse_store.__name__, level="WARNING") as logs:
                pulse_store.initialize(conn)
        self.assertIn("3.35", logs.output[0])
        self.assertIn("paragraphs_json", {r["name"] for r in conn.execute("PRAGMA table_info(speeches)")})
        conn.close()


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

    # Value: protects=a Beitrag shares its speaker's mps row with that Person's Rede; a silent asker keeps the announced name with no mp; re-persist adds no rows;
    #   fails_when=persist_contributions makes a second mps row, invents an mp for an id-less asker, or a second persist duplicates contributions/mps;
    #   why_new=test_repersist asserts only counts by kind and that mp_id is set, not identity with the Rede's row, the NULL-asker branch or a same-store second persist; seam=none
    def test_contributions_share_the_speakers_mp_and_a_silent_asker_has_none(self) -> None:
        report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
        item = report["agenda_items"][0]
        ada = item["xml_speakers"][0]["speaker"]
        item["xml_contributions"] = [
            {
                "kind": "kurzintervention",
                "rede_id": "K1",
                "parent_rede_id": "R1",
                "sequence": 1,
                "source_page": {"page": 102, "quadrant": "B"},
                "speaker": json.loads(json.dumps(ada)),
                "char_count": 12,
                "text": "Kurz gesagt.",
            },
            {
                "kind": "fragestunde_frage",
                "rede_id": None,
                "parent_rede_id": None,
                "sequence": 2,
                "source_page": None,
                "speaker": {"xml_redner_id": None, "display_name": "Jan Köstering"},
                "char_count": 4,
                "text": "Wie?",
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.persist_report(conn, report)
                mps_before = conn.execute("SELECT COUNT(*) FROM mps").fetchone()[0]
                rede_mp = conn.execute("SELECT mp_id FROM speeches WHERE rede_id = 'R1'").fetchone()["mp_id"]
                kurz, frage = conn.execute(
                    "SELECT kind, rede_id, parent_rede_id, mp_id, speaker_name, fraktion, sprechrolle, page "
                    "FROM contributions ORDER BY sequence"
                ).fetchall()
                self.assertEqual((kurz["mp_id"], kurz["parent_rede_id"], kurz["page"]), (rede_mp, "R1", 102))
                self.assertEqual(kurz["fraktion"], "SPD")
                self.assertEqual(
                    (frage["mp_id"], frage["speaker_name"], frage["fraktion"], frage["sprechrolle"], frage["rede_id"], frage["page"]),
                    (None, "Jan Köstering", None, None, None, None),
                )
                # The announced name makes no mps row.
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM mps WHERE display_name = 'Jan Köstering'").fetchone()[0], 0)

                pulse_store.persist_report(conn, report)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM contributions").fetchone()[0], 2)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM mps").fetchone()[0], mps_before)
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
                # "BSW (Gruppe)" is the Gruppe BSW: one Zusammenschluss, one row.
                self.assertEqual(names, ["CDU/CSU", "Die Linke", "Gruppe BSW"])
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
                    row["rede_id"]: (row["fraktion"], row["party"], row["sprechrolle"])
                    for row in conn.execute(
                        """
                        SELECT s.rede_id, s.fraktion, p.name AS party, s.sprechrolle
                        FROM speeches s
                        LEFT JOIN mps m ON m.id = s.mp_id
                        LEFT JOIN parties p ON p.id = m.party_id
                        """
                    )
                }
                party_names = {row["name"] for row in conn.execute("SELECT name FROM parties")}
            finally:
                conn.close()

        # Normalised the same way parties.name is.
        self.assertEqual(rows["R1"], ("BÜNDNIS 90/DIE GRÜNEN", "BÜNDNIS 90/DIE GRÜNEN", None))
        # No Fraktion in the XML but a role: the Rede counts for the Bundesregierung
        # and the speaker belongs to no Zusammenschluss, so there is no party row
        # for "Regierung" (ADR 0001).
        self.assertEqual(rows["R2"], (None, None, "bundesregierung"))
        self.assertNotIn("Regierung", party_names)

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


class VoteResultColumnsTests(unittest.TestCase):
    def test_initialize_adds_result_and_xlsx_columns(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        with conn:
            pulse_store.initialize(conn)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(votes)")}
        self.assertTrue({"result_raw", "result_source", "xlsx_url"} <= columns)
        conn.close()

    def test_persist_votes_writes_result_and_xlsx_url_and_updates_on_conflict(self) -> None:
        report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
        vote = report["agenda_items"][0]["votes"][0]
        vote["result_raw"] = "accepted"
        vote["result_source"] = "official"
        vote["xlsx_url"] = "https://www.bundestag.de/resource/blob/1/vote_xls.xlsx"

        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.persist_report(conn, report)
                row = conn.execute(
                    "SELECT result_raw, result_source, xlsx_url FROM votes WHERE id = ?", (vote["id"],)
                ).fetchone()
                self.assertEqual(tuple(row), ("accepted", "official", vote["xlsx_url"]))

                # A rebuild that resolves a different result overwrites it, but a
                # run that found no XLSX link keeps the stored one.
                vote["result_raw"] = "rejected"
                vote["result_source"] = "derived"
                vote["xlsx_url"] = None
                pulse_store.persist_report(conn, report)
                row = conn.execute(
                    "SELECT result_raw, result_source, xlsx_url FROM votes WHERE id = ?", (vote["id"],)
                ).fetchone()
                self.assertEqual(tuple(row), ("rejected", "derived", "https://www.bundestag.de/resource/blob/1/vote_xls.xlsx"))

                # A newly found link still replaces the stored one.
                vote["xlsx_url"] = "https://www.bundestag.de/resource/blob/2/vote_xls.xlsx"
                pulse_store.persist_report(conn, report)
                row = conn.execute("SELECT xlsx_url FROM votes WHERE id = ?", (vote["id"],)).fetchone()
                self.assertEqual(row[0], vote["xlsx_url"])
            finally:
                conn.close()

    def test_persist_votes_clears_the_link_on_an_explicit_ambiguous_refusal(self) -> None:
        # xlsx_ambiguous=True means the scraper found 2+ distinct XLSX files
        # for this vote's (date, title) and explicitly refused to guess - that
        # refusal must win over the old stored link, unlike a plain missing
        # xlsx_url (e.g. a duplicate attachment of the same vote), which
        # COALESCE is meant to preserve (Codex structured review, 2026-09-27).
        report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
        vote = report["agenda_items"][0]["votes"][0]
        vote["xlsx_url"] = "https://www.bundestag.de/resource/blob/1/vote_xls.xlsx"

        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.persist_report(conn, report)
                row = conn.execute("SELECT xlsx_url FROM votes WHERE id = ?", (vote["id"],)).fetchone()
                self.assertEqual(row[0], vote["xlsx_url"])

                vote["xlsx_url"] = None
                vote["xlsx_ambiguous"] = True
                pulse_store.persist_report(conn, report)
                row = conn.execute("SELECT xlsx_url FROM votes WHERE id = ?", (vote["id"],)).fetchone()
                self.assertIsNone(row[0])
            finally:
                conn.close()

    def test_persist_votes_drops_the_link_once_the_title_changed(self) -> None:
        # The stored xlsx_url was matched by (date, title); the same guard
        # carry_forward_vote_provenance applies at the report layer must also
        # hold at the SQL layer, or a title correction between builds would
        # leave a no-longer-matching link stuck on the row forever (coverage
        # audit, 2026-09-27).
        report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
        vote = report["agenda_items"][0]["votes"][0]
        vote["xlsx_url"] = "https://www.bundestag.de/resource/blob/1/vote_xls.xlsx"

        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.persist_report(conn, report)
                row = conn.execute("SELECT xlsx_url FROM votes WHERE id = ?", (vote["id"],)).fetchone()
                self.assertEqual(row[0], vote["xlsx_url"])

                vote["title"] = f"{vote['title']} (korrigiert)"
                vote["xlsx_url"] = None
                pulse_store.persist_report(conn, report)
                row = conn.execute("SELECT xlsx_url FROM votes WHERE id = ?", (vote["id"],)).fetchone()
                self.assertIsNone(row[0])
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
