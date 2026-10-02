"""Mehrheitsvotum (CONTEXT.md): the Stimme most MdBs of a Zusammenschluss gave
among Ja, Nein and Enthaltung; none on a tie or when nobody voted. Derived from
the counts at persist and render time, never read from a cached report (E2)."""

from __future__ import annotations

import copy
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401
import build_dip_pulse_site as build
import derive
import persist_dip_pulse_store as pulse_store
from _support import FIXTURES
from features import votes as votes_feature


class MajorityVoteTests(unittest.TestCase):
    def test_plurality_among_ja_nein_enthaltung(self) -> None:
        # C6: 40 Ja / 35 Nein / 25 Enthaltung is Ja, the plurality (CONTEXT.md,
        # "Mehrheitsvotum"), even though Ja is below half of the votes cast.
        self.assertEqual(derive.majority_vote({"yes": 40, "no": 35, "abstain": 25}), "yes")
        self.assertEqual(derive.majority_vote({"yes": 3, "no": 9, "abstain": 1}), "no")
        self.assertEqual(derive.majority_vote({"yes": 0, "no": 0, "abstain": 4}), "abstain")

    def test_a_shared_top_count_has_none(self) -> None:
        self.assertIsNone(derive.majority_vote({"yes": 5, "no": 5, "abstain": 1}))
        self.assertIsNone(derive.majority_vote({"yes": 3, "no": 3, "abstain": 3}))
        self.assertIsNone(derive.majority_vote({"yes": 1, "no": 4, "abstain": 4}))

    def test_a_tie_below_the_top_does_not_matter(self) -> None:
        self.assertEqual(derive.majority_vote({"yes": 7, "no": 2, "abstain": 2}), "yes")

    def test_nobody_voted_has_none_and_nicht_abgegeben_is_no_stimme(self) -> None:
        self.assertIsNone(derive.majority_vote({"yes": 0, "no": 0, "abstain": 0}))
        self.assertIsNone(derive.majority_vote({"yes": 0, "no": 0, "abstain": 0, "absent": 9}))
        # Twelve MdBs did not vote; the one Ja is still the Mehrheitsvotum.
        self.assertEqual(derive.majority_vote({"yes": 1, "no": 0, "abstain": 0, "absent": 12}), "yes")

    def test_missing_keys_and_no_counts(self) -> None:
        self.assertEqual(derive.majority_vote({"yes": 2}), "yes")
        self.assertIsNone(derive.majority_vote({}))
        self.assertIsNone(derive.majority_vote(None))
        self.assertEqual(derive.majority_vote({"yes": "3", "no": None}), "yes")


def stale_report() -> dict:
    """The fixture report with a cached leading_vote that contradicts the counts
    in every way an old parser got it wrong."""
    report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
    vote = report["agenda_items"][0]["votes"][0]
    vote["fractions"] = [
        # A tie: max() used to pick "yes".
        {"name": "SPD", "counts": {"yes": 5, "no": 5, "abstain": 0, "absent": 0}, "total": 10, "leading_vote": "yes"},
        # Nobody voted: used to be "absent".
        {"name": "CDU/CSU", "counts": {"yes": 0, "no": 0, "abstain": 0, "absent": 9}, "total": 9, "leading_vote": "absent"},
        # A plurality below half: Ja, though the cached value says otherwise.
        {"name": "FDP", "counts": {"yes": 40, "no": 35, "abstain": 25, "absent": 0}, "total": 100, "leading_vote": "no"},
    ]
    return report


class StaleCachedReportTests(unittest.TestCase):
    """F1/E2: a cached report whose leading_vote is wrong gives the same,
    correct value in the database and in the pages."""

    def test_the_database_row_is_derived_from_the_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                pulse_store.persist_report(conn, stale_report())
                rows = {
                    row["name"]: row["leading_vote"]
                    for row in conn.execute(
                        "SELECT p.name, vf.leading_vote FROM vote_fractions vf JOIN parties p ON p.id = vf.party_id"
                    )
                }
            finally:
                conn.close()
        self.assertEqual(rows, {"SPD": None, "CDU/CSU": None, "FDP": "yes"})

    def test_the_vote_panel_shows_no_pill_for_a_tie_or_nobody_voting(self) -> None:
        report = stale_report()
        markup = votes_feature.render_vote_summary(report["agenda_items"][0])
        rows = {
            re.search(r"<strong>([^<]+)</strong>", block).group(1): block
            for block in markup.split('<div class="vote-fraction-row">')[1:]
        }
        self.assertEqual(set(rows), {"SPD", "CDU/CSU", "FDP"})
        self.assertNotIn('<em class="vote-pill', rows["SPD"])
        self.assertNotIn('<em class="vote-pill', rows["CDU/CSU"])
        self.assertIn('<em class="vote-pill vote-yes">ja</em>', rows["FDP"])
        # "nicht abgegeben" is a Stimme count, never a Mehrheitsvotum pill.
        self.assertNotIn("vote-absent", "".join(re.findall(r'<em class="vote-pill[^>]*>', markup)))

    def test_the_votes_archive_gives_them_no_position(self) -> None:
        report = stale_report()
        entry = {"report": report, "page_path": Path("plenarprotokoll-20-999.html")}
        rows = build.collect_votes_archive([entry])
        # SPD (tie) and CDU/CSU (nobody voted) have none; FDP's Ja is a plurality
        # below half of the votes, which the chip's stricter Ja-Mehrheit rejects.
        self.assertEqual(rows[0]["fraction_positions"], {"FDP": "tie"})
        markup = build.render_votes_archive_index(rows)
        self.assertNotIn('data-fraktion-chip="SPD"', markup)
        self.assertNotIn('data-fraktion-chip="CDU/CSU"', markup)

    def test_a_party_merge_that_ends_in_a_tie_stores_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                now = pulse_store.utc_now()
                keeper = conn.execute(
                    "INSERT INTO parties(id, name, created_at, updated_at) VALUES ('clean', 'CDU/CSU', ?, ?)", (now, now)
                )
                keeper = "clean"
                duplicate = conn.execute(
                    "INSERT INTO parties(id, name, created_at, updated_at) VALUES ('dirty', \"['CDU/CSU']\", ?, ?)", (now, now)
                )
                duplicate = "dirty"
                conn.execute("INSERT INTO votes(id, created_at, updated_at) VALUES ('v1', ?, ?)", (now, now))
                for party_id, yes, no in ((keeper, 6, 0), (duplicate, 0, 6)):
                    conn.execute(
                        "INSERT INTO vote_fractions(vote_id, party_id, yes_count, no_count, total_count, leading_vote) "
                        "VALUES ('v1', ?, ?, ?, ?, ?)",
                        (party_id, yes, no, yes + no, "yes" if yes else "no"),
                    )
                conn.commit()
                pulse_store.initialize(conn)
                row = conn.execute("SELECT yes_count, no_count, leading_vote FROM vote_fractions").fetchone()
            finally:
                conn.close()
        self.assertEqual(dict(row), {"yes_count": 6, "no_count": 6, "leading_vote": None})


class ReadersSkipANullMehrheitsvotumTests(unittest.TestCase):
    """Every reader of vote_fractions.leading_vote filters on yes/no, so a NULL
    row is skipped, not counted."""

    def store(self, tmp: str) -> sqlite3.Connection:
        conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
        pulse_store.initialize(conn)
        report = stale_report()
        # A Mitglied of every Fraktion, each voting Ja.
        vote = report["agenda_items"][0]["votes"][0]
        vote["members"] = [
            {"name": f"Mitglied {party}", "faction": party, "vote": "yes"} for party in ("SPD", "CDU/CSU", "FDP")
        ] + [{"name": "Frieda Frei", "faction": "fraktionslos", "vote": "no"}]
        vote["fractions"].append(
            {"name": "fraktionslos", "counts": {"yes": 0, "no": 1, "abstain": 0, "absent": 0}, "total": 1}
        )
        with conn:
            pulse_store.persist_report(conn, report)
        return conn

    RECIPE = next(r for r in build.RECIPES if r["id"] == "r3-abweichler")

    def r3_rows(self, conn: sqlite3.Connection) -> list[tuple]:
        conn.execute("DROP TABLE IF EXISTS temp.mp_canonical")
        conn.execute("CREATE TEMP TABLE mp_canonical AS SELECT id AS mp_id, person_id AS canonical_id, 1 AS has_page FROM mps")
        sql = self.RECIPE["sql"].rstrip().removesuffix("LIMIT 5;")
        return [tuple(row) for row in conn.execute(sql)]

    def test_r3_abweichler_skips_a_null_mehrheitsvotum_and_excludes_fraktionslos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = self.store(tmp)
            try:
                # SPD and CDU/CSU have none (tie / nobody voted), FDP's is Ja
                # and its member voted Ja, fraktionslos has Nein and its member
                # voted Nein: nobody deviates.
                self.assertEqual(self.r3_rows(conn), [])
                # A fraktionslos MdB voting against the pseudo-Fraktion's own
                # "Mehrheitsvotum" is no Abweichung: no Zusammenschluss.
                conn.execute(
                    "UPDATE vote_members SET vote = 'yes' WHERE party_id = "
                    "(SELECT id FROM parties WHERE name = 'fraktionslos')"
                )
                self.assertEqual(self.r3_rows(conn), [])
                # ...whereas the same deviation in a real Fraktion counts.
                conn.execute(
                    "UPDATE vote_members SET vote = 'no' WHERE party_id = (SELECT id FROM parties WHERE name = 'FDP')"
                )
                self.assertEqual([row[2:] for row in self.r3_rows(conn)], [("FDP", 1)])
            finally:
                conn.close()

    def test_r3_title_and_metric_wording_say_anders_als_die_mehrheit(self) -> None:
        self.assertIn("anders als die Mehrheit der eigenen Fraktion oder Gruppe", self.RECIPE["title"])
        import facts

        metric = facts.REGISTRY_BY_ID["meiste-abweichler"]
        self.assertIn("anders stimmten als die Mehrheit ihrer Fraktion oder Gruppe", metric["unit"])
        self.assertNotIn("Fraktionslinie", metric["caveat"])
        self.assertNotIn("gegen die Linie", metric["unit"])

    def test_meiste_abweichler_skips_a_null_mehrheitsvotum(self) -> None:
        import facts

        metric = facts.REGISTRY_BY_ID["meiste-abweichler"]
        with tempfile.TemporaryDirectory() as tmp:
            conn = self.store(tmp)
            try:
                # Everyone in a real Fraktion with a NULL leading_vote is
                # ignored; FDP's members agree with Ja.
                rows = conn.execute(metric["sql"]).fetchall()
                self.assertEqual([row["value"] for row in rows], [0])
                conn.execute(
                    "UPDATE vote_members SET vote = 'no' WHERE party_id = (SELECT id FROM parties WHERE name = 'SPD')"
                )
                # SPD has no Mehrheitsvotum (tie): its Nein-voter is no Abweichler.
                self.assertEqual([row["value"] for row in conn.execute(metric["sql"]).fetchall()], [0])
                conn.execute(
                    "UPDATE vote_members SET vote = 'no' WHERE party_id = (SELECT id FROM parties WHERE name = 'FDP')"
                )
                self.assertEqual([row["value"] for row in conn.execute(metric["sql"]).fetchall()], [1])
            finally:
                conn.close()


class LabelTests(unittest.TestCase):
    def test_an_uncast_stimme_is_labelled_nicht_abgegeben_everywhere(self) -> None:
        import render_dip_pulse_html as html

        self.assertEqual(html.VOTE_LABELS["absent"], "nicht abgegeben")
        page = build.render_abgeordnete_detail(
            {
                "id": 1, "name": "Ada", "party": "SPD", "profile_url": "https://www.abgeordnetenwatch.de/profile/ada",
                "wahlperioden": [], "function": [], "person_roles": [], "speeches": [], "speech_count": 0,
                "total_chars": 0,
                "votes": [{"vote": "absent", "title": "T", "date": "2026-01-01"}],
            },
            None,
            None,
        )
        self.assertIn("nicht abgegeben", page)
        self.assertNotIn("Abwesend", page)


if __name__ == "__main__":
    unittest.main()
