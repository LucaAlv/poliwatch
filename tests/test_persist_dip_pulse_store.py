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


class SchemaGuardTests(unittest.TestCase):
    # Value: protects=a store from before schema 5 (proceedings without sachgebiet) is refused with the repersist instruction instead of being stamped version 5 with empty tag tables; fails_when=require_current_schema stops checking proceedings.sachgebiet, so a plain --offline build exports empty Politikfeld tables and later persists fail; why_new=no test opened a store from before the Politikfeld columns; seam=none
    def test_a_store_without_proceedings_sachgebiet_is_refused(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE proceedings (id TEXT PRIMARY KEY, title TEXT)")
        with self.assertRaisesRegex(RuntimeError, "Old build-store schema"):
            pulse_store.initialize(conn)
        self.assertNotIn("agenda_item_politikfelder", {r[0] for r in conn.execute("SELECT name FROM sqlite_master")})
        conn.close()

    # Value: protects=a schema 5 store (sachgebiet present, no proceedings.abstract) is refused with the repersist instruction instead of being stamped 6 with an empty vote_proceedings and NULL context states; fails_when=require_current_schema stops checking proceedings.abstract, so a plain --offline build exports a format 7 copy without any vote context; why_new=B4 bumps the schema to 6; seam=none
    def test_a_schema_5_store_without_proceedings_abstract_is_refused(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE proceedings (id TEXT PRIMARY KEY, title TEXT, sachgebiet TEXT)")
        with self.assertRaisesRegex(RuntimeError, "Old build-store schema.*--offline --repersist"):
            pulse_store.initialize(conn)
        self.assertNotIn("vote_proceedings", {r[0] for r in conn.execute("SELECT name FROM sqlite_master")})
        conn.close()


    # Value: protects=a store written by this branch before the v0.19 merge (tag tables and sachgebiet present, documents keyed by URL) is refused with the repersist instruction and left unchanged; fails_when=the documents check is reordered or loosened, since it is the only guard that catches this shape; why_new=the guard tests used a bare proceedings table or the v0.19 shape; seam=none
    def test_a_pre_merge_politikfeld_store_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "store.sqlite"
            conn = pulse_store.connect(path)
            pulse_store.initialize(conn)
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("DROP TABLE documents")
            conn.execute("CREATE TABLE documents (id TEXT PRIMARY KEY, url TEXT)")
            conn.commit()
            conn.close()
            before = path.read_bytes()
            conn = sqlite3.connect(path)
            try:
                self.assertIn("agenda_item_politikfelder", {r[0] for r in conn.execute("SELECT name FROM sqlite_master")})
                with self.assertRaisesRegex(RuntimeError, "documents keyed by URL"):
                    pulse_store.initialize(conn)
            finally:
                conn.close()
            self.assertEqual(before, path.read_bytes())


def _context_cache(numbers: dict, vorgaenge: dict) -> dict:
    return {"version": 1, "vorgaenge": vorgaenge, "dokumentnummern": numbers}


class VoteContextPersistTests(unittest.TestCase):
    """B4 schema 6: proceedings.abstract and title, vote_proceedings, votes.context_state."""

    def persisted(self, cache, report=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = pulse_store.connect(Path(tmp.name) / "store.sqlite")
        self.addCleanup(conn.close)
        report = report or json.loads((FIXTURES / "report.json").read_text())
        pulse_store.persist_report(conn, report, cache)
        return conn

    def rows(self, conn, sql):
        return [tuple(r) for r in conn.execute(sql)]

    # Value: protects=a vote's context Vorgänge reach the store with their sanitised abstract and cached titel, ranked, with state resolved, and a vote-only Vorgang gets a proceedings row; fails_when=persist skips vote_proceedings, stores raw HTML, or leaves vote-only Vorgänge without a row (FK) or title (D12); why_new=schema 6 is new; seam=none
    def test_a_resolved_vote_stores_its_vorgaenge_abstracts_and_titles(self):
        cache = _context_cache(
            {"20/123": ["vote-only", "vorgang-1"]},
            {
                "vote-only": {"sachgebiet": ["Energie"], "titel": "Gesetz X", "vorgangstyp": "Antrag",
                              "abstract": "Erster<br />\r\n<br />\r\n<strong>Zweiter</strong>"},
                "vorgang-1": {"sachgebiet": ["Recht"], "titel": "Cache-Titel", "vorgangstyp": "Gesetzgebung", "abstract": "&bdquo;TOP&ldquo;"},
            },
        )
        report = json.loads((FIXTURES / "report.json").read_text())
        report["agenda_items"][0]["api"]["positions"] = []  # the TOP has no Vorgang: nothing narrows the vote's
        conn = self.persisted(cache, report)
        self.assertEqual(self.rows(conn, "SELECT vote_id, proceeding_id, rank FROM vote_proceedings ORDER BY rank"),
                         [("12345", "vote-only", 1), ("12345", "vorgang-1", 2)])
        self.assertEqual(self.rows(conn, "SELECT context_state FROM votes"), [("resolved",)])
        self.assertEqual(
            self.rows(conn, "SELECT id, title, proceeding_type, abstract, sachgebiet FROM proceedings ORDER BY id"),
            [("vorgang-1", "Cache-Titel", None, "„TOP“", None),
             ("vote-only", "Gesetz X", None, "Erster\n\nZweiter", None)],
        )

    # Value: protects=the vote path fills a proceedings title only where it is empty and never its type, so a TOP-linked Vorgang keeps its position title, in either persist order, and still gets its abstract; fails_when=the vote upsert lets the cache titel overwrite the position title, moving an existing proceedings cell (D10); why_new=the vote path writes proceedings for the first time; seam=none
    def test_a_top_vorgang_keeps_its_position_title_and_gets_its_abstract(self):
        cache = _context_cache(
            {"20/123": ["vorgang-1"]},
            {"vorgang-1": {"sachgebiet": ["Recht"], "titel": "Cache-Titel", "vorgangstyp": "Antrag", "abstract": "Kurz."}},
        )
        conn = self.persisted(cache)
        report = json.loads((FIXTURES / "report.json").read_text())
        pulse_store.persist_report(conn, report, cache)
        self.assertEqual(self.rows(conn, "SELECT id, title, proceeding_type, abstract FROM proceedings"),
                         [("vorgang-1", "Testgesetz", "Gesetzgebung", "Kurz.")])
        self.assertEqual(self.rows(conn, "SELECT proceeding_id, rank FROM vote_proceedings"), [("vorgang-1", 1)])

    # Value: protects=the store separates "no Vorgang" from "not fetched" (D7) and a vote never ends with a NULL state; fails_when=both collapse to no row, or a cache miss is stored as none; why_new=votes.context_state is new; seam=none
    def test_none_and_not_fetched_are_stored_apart_without_rows(self):
        for cache, state in ((None, "not_fetched"), (_context_cache({"20/123": []}, {}), "none")):
            with self.subTest(state=state):
                conn = self.persisted(cache)
                self.assertEqual(self.rows(conn, "SELECT context_state FROM votes"), [(state,)])
                self.assertEqual(self.rows(conn, "SELECT * FROM vote_proceedings"), [])
                self.assertEqual(self.rows(conn, "SELECT abstract FROM proceedings"), [(None,)])
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute("UPDATE votes SET context_state = 'geraten'")

    # Value: protects=D7: a resolved Vorgang without a cached record keeps its row but is not_fetched; fails_when=the state reads resolved over a missing abstract, or the row is dropped; why_new=review fix E2; seam=none
    def test_a_resolved_vorgang_without_a_record_is_written_and_not_fetched(self):
        conn = self.persisted(_context_cache({"20/123": ["vorgang-1"]}, {}))
        self.assertEqual(self.rows(conn, "SELECT proceeding_id, rank FROM vote_proceedings"), [("vorgang-1", 1)])
        self.assertEqual(self.rows(conn, "SELECT context_state FROM votes"), [("not_fetched",)])

    # Value: protects=a re-persist replaces a vote's vote_proceedings rows and state with the current resolution; fails_when=rows are only inserted, so a Vorgang the cache no longer names stays linked; why_new=vote_proceedings is new; seam=none
    def test_persisting_again_replaces_the_rows(self):
        first = _context_cache({"20/123": ["a"]}, {"a": {"sachgebiet": [], "titel": "A", "abstract": "A."}})
        conn = self.persisted(first)
        report = json.loads((FIXTURES / "report.json").read_text())
        pulse_store.persist_report(conn, report, _context_cache({"20/123": []}, {}))
        self.assertEqual(self.rows(conn, "SELECT * FROM vote_proceedings"), [])
        self.assertEqual(self.rows(conn, "SELECT context_state FROM votes"), [("none",)])

    # Value: protects=persist refuses a roll-call vote without a usable id and rolls the whole report back, instead of skipping the vote as before B4; fails_when=persist stops calling derive.require_vote_shape and skips the vote, so the store lacks a vote the archive and export count, or the failed write leaves a half-replaced sitting; why_new=the old skip test was dropped with the legacy shapes and nothing asserts the refusal; seam=none
    def test_a_vote_without_a_usable_id_is_refused_and_the_store_stays_as_it_was(self):
        cache = _context_cache({"20/123": []}, {})
        conn = self.persisted(cache)
        before = self.rows(conn, "SELECT id, protocol_id, context_state FROM votes")
        self.assertEqual(len(before), 1)
        for bad_id in (None, "", "  "):
            with self.subTest(vote_id=bad_id):
                report = json.loads((FIXTURES / "report.json").read_text())
                report["agenda_items"][0]["votes"][0]["id"] = bad_id
                with self.assertRaisesRegex(ValueError, "a roll-call vote has no id"):
                    pulse_store.persist_report(conn, report, cache)
                self.assertEqual(self.rows(conn, "SELECT id, protocol_id, context_state FROM votes"), before)

    # Value: protects=two vote ids equal after cleaning inside one report are one vote and the FIRST copy is stored (before the B4 edge fixes persist kept the last), for TOP votes and sitting_votes, in both orders; fails_when=iter_report_votes dedupes on the raw id again or persist writes every copy; why_new=review of the vote-identity cleaning rule (2026-10-31); seam=none
    def test_ids_equal_after_cleaning_store_the_first_copy(self):
        cache = _context_cache({"20/123": []}, {})
        for where in ("top", "sitting"):
            for first_raw, second_raw in ((" v1 ", "v1"), ("v1", " v1 ")):
                with self.subTest(where=where, order=(first_raw, second_raw)):
                    conn = self.persisted(cache)
                    report = json.loads((FIXTURES / "report.json").read_text())
                    template = report["agenda_items"][0]["votes"][0]
                    copies = [{**template, "id": first_raw, "title": "erste"}, {**template, "id": second_raw, "title": "zweite"}]
                    if where == "top":
                        report["agenda_items"][0]["votes"] = copies
                    else:
                        report["agenda_items"][0]["votes"] = []
                        report["sitting_votes"] = copies
                    pulse_store.persist_report(conn, report, cache)
                    self.assertEqual(self.rows(conn, "SELECT id, title FROM votes"), [("v1", "erste")])

    # Value: protects=a library caller handing persist a report with a TOP's singular "vote" is refused before any write; fails_when=persist reads the TOP as voteless and deletes the sitting's stored vote; why_new=only report loading refused the shape (B4 ship review 2026-10-22); seam=none
    def test_a_singular_vote_is_refused_and_the_store_stays_as_it_was(self):
        cache = _context_cache({"20/123": []}, {})
        conn = self.persisted(cache)
        before = self.rows(conn, "SELECT id, protocol_id, context_state FROM votes")
        self.assertEqual(len(before), 1)
        report = json.loads((FIXTURES / "report.json").read_text())
        report["agenda_items"][0]["vote"] = report["agenda_items"][0].pop("votes")[0]
        with self.assertRaisesRegex(ValueError, 'singular "vote"'):
            pulse_store.persist_report(conn, report, cache)
        self.assertEqual(self.rows(conn, "SELECT id, protocol_id, context_state FROM votes"), before)


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

    # Value: protects=two MPs whose member cards link back to the Abstimmung stay two vote_members rows; fails_when=the Abstimmung URL serves as a profile identity and folds them into one mp (63 rows lost on the reference store); why_new=found while keying the Abweichler dedupe on identity (2026-10-22); seam=derive.vote_member_identity
    def test_members_linked_to_the_abstimmung_page_stay_two_mps(self) -> None:
        report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
        vote = report["agenda_items"][0]["votes"][0]
        for member in vote["members"]:
            member["profile_url"] = vote["detail_url"]
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.persist_report(conn, report)
                rows = conn.execute(
                    "SELECT m.display_name, m.profile_url FROM vote_members vm JOIN mps m ON vm.mp_id = m.id ORDER BY 1"
                ).fetchall()
                self.assertEqual([tuple(row) for row in rows], [("Ada Lovelace", None), ("Bruno Beispiel", None)])
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
                "INSERT INTO parties(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (name, name, now, now),
            )
            ids[name] = name
        for index, name in enumerate(("CDU/CSU", "['CDU/CSU']", "['DIE LINKE']", "['BSW (Gruppe)']")):
            pulse_store.upsert_mp(
                conn,
                now=now,
                display_name=f"MdB {index}",
                party_id=ids[name],
                identity_key=f"dip:seed-{index}",
                occurrence_id=f"fixture:dip:seed-{index}",
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
        mp_id = conn.execute("SELECT id FROM mps WHERE identity_key = 'dip:seed-1'").fetchone()["id"]
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
                kept = conn.execute("SELECT id FROM parties WHERE name = 'CDU/CSU'").fetchone()["id"]
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
                    "INSERT INTO parties(id, name, created_at, updated_at) VALUES ('clean', 'CDU/CSU', ?, ?)",
                    (now, now),
                )
                canonical_id = "clean"
                conn.execute(
                    "INSERT INTO parties(id, name, created_at, updated_at) VALUES ('dirty', \"['CDU/CSU']\", ?, ?)",
                    (now, now),
                )
                duplicate_id = "dirty"
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



class DocumentUrlRankTests(unittest.TestCase):
    # Value: protects=a Drucksache number with non-ASCII digits is treated as encoding no checkable path instead of crashing the persist; fails_when=_encodes_document_number goes back to str.isdigit, which accepts '²' and int() raises; why_new=every URL-rank case used ASCII numbers; seam=none
    def test_non_ascii_digits_encode_no_checkable_path(self) -> None:
        for issuer, number in (("BT", "2²/1"), ("BR", "٢٣/١")):
            with self.subTest(number=number):
                self.assertFalse(pulse_store._encodes_document_number(issuer, number, "/btd/2/000/200001.pdf"))
        self.assertTrue(pulse_store._encodes_document_number("BT", "20/8601", "/btd/20/086/2008601.pdf"))


if __name__ == "__main__":
    unittest.main()
