"""C1 step 5: the Stammdaten seat counts checked against the roll-call totals
(``vote_fractions.total_count``), one roll-call at a time
(docs/plans/c1-seat-counts.md, "Cross-check against the roll-call totals")."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401
import build_dip_pulse_site as build
import derive
import person_registry as registry
import persist_dip_pulse_store as pulse_store
import stammdaten

NOW = "2026-11-01T00:00:00+00:00"
STAND = "2026-04-29T08:03:03+00:00"
#: Keyword spellings of the group names that are no identifiers.
PARTY = {"CDU_CSU": "CDU/CSU", "Gruppe_BSW": "Gruppe BSW"}


def member(mdb_id: str, party: str, valid_from: str, valid_until: str | None = None, wp: int = 21) -> dict:
    return {"mdb_id": mdb_id, "name": f"MdB {mdb_id}", "wahlperiode": wp, "party": party,
            "valid_from": valid_from, "valid_until": valid_until}


def bundestag(**groups: int) -> list[dict]:
    """A WP 21 Bundestag from its first day, ``groups`` seats each (keyword
    ``fraktionslos`` included), with no change."""
    rows, number = [], 0
    for party, seats in groups.items():
        for _ in range(seats):
            number += 1
            rows.append(member(f"110{number:05d}", PARTY.get(party, party), "2025-03-25"))
    return rows


class StoreFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "s.sqlite"
        self.conn = pulse_store.connect(self.path)
        self.addCleanup(self.conn.close)
        pulse_store.initialize(self.conn)
        self.sittings = 0

    def stammdaten(self, rows: list[dict], *, stand: str = STAND) -> None:
        pulse_store.persist_seat_counts(self.conn, rows, derive.party_seats(rows), stand=stand, sha256="0" * 64, now=NOW)

    def vote(self, vote_id: str, day: str, *, wp: int | None = 21, **totals: int) -> None:
        protocol_id = None
        if wp is not None:
            self.sittings += 1
            protocol_id = f"protocol-{self.sittings}"
            self.conn.execute(
                "INSERT INTO protocols(id, document_number, date, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (protocol_id, f"{wp}/{self.sittings}", day, NOW, NOW))
        self.conn.execute("INSERT INTO votes(id, protocol_id, date, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                          (vote_id, protocol_id, day, NOW, NOW))
        for party, total in totals.items():
            party_id = pulse_store.upsert_party(self.conn, PARTY.get(party, party), NOW)
            self.conn.execute("INSERT INTO vote_fractions(vote_id, party_id, total_count, rank) VALUES (?, ?, ?, 1)",
                              (vote_id, party_id, total))


class CrossCheckTests(StoreFixture):
    # Value: protects=a roll-call that lists one member fewer than the Stammdaten seat
    #   count is reported with both figures and filed as the roll-call being short (the
    #   E5 / one-seat shape); fails_when=the comparison is skipped, the sign of the
    #   difference flips, or the group's row is lost; why_new=C1 step 5;
    #   seam=stammdaten.crosscheck
    def test_a_roll_call_one_member_short_is_reported(self) -> None:
        self.stammdaten(bundestag(SPD=3, CDU_CSU=2, fraktionslos=1))
        self.vote("1001", "2025-06-26", SPD=2, CDU_CSU=2, fraktionslos=1)
        result = stammdaten.crosscheck(self.conn)
        self.assertEqual(result.compared, 1)
        self.assertEqual(result.disagreements, [
            {"vote_id": "1001", "date": "2025-06-26", "wahlperiode": 21, "party": "SPD",
             "stammdaten_seats": 3, "roll_call_total": 2, "difference": -1, "cause": "roll_call_short"},
        ])

    # Value: protects=a roll-call that files members under another group than the
    #   Stammdaten (the E4 shape: the totals agree, the groups do not) is one roll-call
    #   with a row per group, filed as a shift; fails_when=a net-zero difference is read
    #   as members missing or as unexplained, or one side's row is dropped; why_new=C1
    #   step 5; seam=stammdaten.crosscheck
    def test_members_filed_under_another_group_are_a_shift(self) -> None:
        self.stammdaten(bundestag(AfD=3, SPD=2, fraktionslos=1))
        self.vote("1002", "2025-06-26", AfD=2, SPD=2, fraktionslos=2)
        result = stammdaten.crosscheck(self.conn)
        self.assertEqual([(row["party"], row["difference"], row["cause"]) for row in result.disagreements],
                         [("AfD", -1, "shift_between_groups"), ("fraktionslos", 1, "shift_between_groups")])

    # Value: protects=a roll-call on the day members change group, listing them under
    #   the old one, is filed as a change on the vote's day even though its differences
    #   net to zero (the 2024-02-02 Gruppen votes), but only when that day's changes of
    #   the disagreeing groups cover the difference: an unrelated Nachrücker that day
    #   explains nothing; fails_when=the shift test runs first, or any change that day
    #   counts; why_new=C1 step 5; seam=stammdaten.crosscheck
    def test_a_change_on_the_vote_day_explains_only_its_own_groups(self) -> None:
        switchers = [row for number in (1, 2, 3) for row in (
            member(f"1109000{number}", "fraktionslos", "2025-03-25", "2025-07-01"),
            member(f"1109000{number}", "Gruppe BSW", "2025-07-01"))]
        nachruecker = [member("11090010", "SPD", "2025-03-25", "2025-09-01"), member("11090011", "SPD", "2025-09-01")]
        self.stammdaten(bundestag(AfD=3, SPD=1) + switchers + nachruecker)
        self.vote("1003", "2025-07-01", AfD=3, SPD=2, fraktionslos=3)
        self.vote("1004", "2025-09-01", AfD=2, SPD=2, fraktionslos=1, Gruppe_BSW=3)
        result = stammdaten.crosscheck(self.conn)
        self.assertEqual([(row["vote_id"], row["party"], row["difference"], row["cause"]) for row in result.disagreements], [
            ("1003", "Gruppe BSW", -3, "change_on_vote_day"), ("1003", "fraktionslos", 3, "change_on_vote_day"),
            ("1004", "AfD", -1, "shift_between_groups"), ("1004", "fraktionslos", 1, "shift_between_groups"),
        ])

    # Value: protects=D6: a roll-call dated after the Stammdaten's Stand that disagrees is
    #   drift, filed as such whatever its shape (it warns and never fails the gate), while
    #   a roll-call on the Stand day itself is still judged by its shape; fails_when=the
    #   Stand is compared as a timestamp string against a date, or the shape test runs
    #   first; why_new=C1 step 5; seam=stammdaten.crosscheck
    def test_a_disagreement_after_the_stand_is_drift(self) -> None:
        self.stammdaten(bundestag(SPD=3, AfD=1), stand="2025-08-01T08:03:03+00:00")
        self.vote("1005", "2025-08-01", SPD=2, AfD=1)
        self.vote("1006", "2025-08-02", SPD=2, AfD=2)
        result = stammdaten.crosscheck(self.conn)
        self.assertEqual([(row["vote_id"], row["party"], row["cause"]) for row in result.disagreements], [
            ("1005", "SPD", "roll_call_short"), ("1006", "AfD", "after_stand"), ("1006", "SPD", "after_stand"),
        ])

    # Value: protects=absent is not zero: a roll-call dated where no seat count exists, one
    #   with no group totals, and one with an Unbekannt group (F3) are listed as not
    #   compared instead of turning every group into a disagreement, and a group missing
    #   on one side counts 0 only on a date with seat rows; fails_when=a missing side is
    #   read as 0 seats or 0 members; why_new=C1 step 5; seam=stammdaten.crosscheck
    def test_roll_calls_without_a_side_to_compare_are_listed_not_counted(self) -> None:
        self.stammdaten(bundestag(SPD=3, AfD=1))
        self.vote("1007", "2025-03-24", SPD=3, AfD=1)
        self.vote("1008", "2025-06-26")
        self.vote("1009", "2025-06-26", SPD=3, Unbekannt=1)
        self.vote("1010", "2025-06-26", SPD=3)
        result = stammdaten.crosscheck(self.conn)
        self.assertEqual((result.compared, result.without_seat_count, result.without_totals, result.with_unbekannt),
                         (1, ["1007"], ["1008"], ["1009"]))
        self.assertEqual([(row["vote_id"], row["party"], row["stammdaten_seats"], row["roll_call_total"])
                          for row in result.disagreements], [("1010", "AfD", 1, 0)])

    # Value: protects=the vote's Wahlperiode comes from its protocol, so a day both an
    #   ending and a starting Bundestag have seat rows for is compared with the vote's
    #   own one; without a protocol such a day has no seat count; fails_when=the seat
    #   rows of two Wahlperioden are mixed into one comparison; why_new=C1 step 5;
    #   seam=stammdaten.crosscheck
    def test_the_vote_is_compared_with_its_own_wahlperiode(self) -> None:
        old = [member(f"1108000{n}", "SPD", "2021-10-26", "2025-03-26", wp=20) for n in range(4)]
        self.stammdaten(old + bundestag(SPD=2, AfD=1))
        self.vote("1011", "2025-03-25", SPD=2, AfD=1)
        self.vote("1012", "2025-03-25", wp=None, SPD=2, AfD=1)
        result = stammdaten.crosscheck(self.conn)
        self.assertEqual((result.compared, result.disagreements, result.without_seat_count), (1, [], ["1012"]))

    # Value: protects=a store without Stammdaten has nothing to check against, which the
    #   cross-check says as None instead of reporting every roll-call; fails_when=an empty
    #   seat table yields a disagreement per group; why_new=C1 step 5;
    #   seam=stammdaten.crosscheck
    def test_no_stammdaten_means_no_cross_check(self) -> None:
        self.vote("1013", "2025-06-26", SPD=3)
        self.assertIsNone(stammdaten.crosscheck(self.conn))



class ReportTests(StoreFixture):
    def log(self) -> tuple[str, Path]:
        self.conn.commit()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            build.log_seat_crosscheck(self.path)
        return err.getvalue(), registry.private_dir(self.path) / "seat-crosscheck.json"

    # Value: protects=the build writes every disagreement with its cause to a report in
    #   the store's private directory (D9: never published), counts the roll-calls by
    #   cause in one summary line, and warns for drift after the Stand (D6) and for a
    #   disagreement in no known shape, without failing; the report holds no build time,
    #   so an unchanged store gives the same file; fails_when=the report is published,
    #   lost, stamped, or an unexplained roll-call passes silently; why_new=C1 step 5;
    #   seam=build.log_seat_crosscheck
    def test_the_report_lists_every_disagreement_and_the_summary_counts_causes(self) -> None:
        self.stammdaten(bundestag(SPD=3, AfD=1), stand="2025-08-01T08:03:03+00:00")
        self.vote("1020", "2025-06-26", SPD=3, AfD=1)
        self.vote("1021", "2025-06-26", SPD=3, AfD=2)
        self.vote("1022", "2025-08-02", SPD=2, AfD=1)
        self.vote("1023", "2025-06-26", SPD=3, Unbekannt=1)
        err, path = self.log()
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {
            "stand": "2025-08-01T08:03:03+00:00", "sha256": "0" * 64,
            "compared": 3, "agree": 1,
            "roll_calls_by_cause": {"after_stand": ["1022"], "change_on_vote_day": [], "shift_between_groups": [],
                                    "roll_call_short": [], "unexplained": ["1021"]},
            "not_compared": {"without_seat_count": [], "without_totals": [], "with_unbekannt": ["1023"]},
            "disagreements": [
                {"vote_id": "1021", "date": "2025-06-26", "wahlperiode": 21, "party": "AfD",
                 "stammdaten_seats": 1, "roll_call_total": 2, "difference": 1, "cause": "unexplained"},
                {"vote_id": "1022", "date": "2025-08-02", "wahlperiode": 21, "party": "SPD",
                 "stammdaten_seats": 3, "roll_call_total": 2, "difference": -1, "cause": "after_stand"},
            ],
        })
        self.assertIn("stammdaten: cross-check of 3 roll-calls against the seat counts: 1 agree, 2 disagree "
                      "(1 after the Stand, 1 unexplained); 1 not compared", err)
        self.assertIn("warning: [stammdaten] disagreement with the seat counts in no known shape, 1 roll-call: 1021", err)
        self.assertIn("warning: [stammdaten] disagreement after the Stand (01.08.2025) with the carried-forward seat "
                      "counts (drift), 1 roll-call: 1022", err)
        self.assertIn("warning: [stammdaten] not compared, a group named Unbekannt, 1 roll-call: 1023", err)
        first = path.read_bytes()
        self.log()
        self.assertEqual(path.read_bytes(), first)

    # Value: protects=roll-calls the cross-check cannot compare (no seat count on their date, no group
    #   totals) are named in a warning each and counted as not compared in the summary, never as agreeing
    #   or as disagreeing; fails_when=the two warning lines or the not-compared count are dropped, or an
    #   uncomparable roll-call is counted in "agree"; why_new=TODOS C1 deferred item 18 (these two branches
    #   have no test; the Unbekannt one does); seam=none (log_seat_crosscheck is production code); no_claim=none beyond protects
    def test_roll_calls_without_a_seat_count_or_totals_are_warned_about_and_not_counted(self) -> None:
        self.stammdaten(bundestag(SPD=3, AfD=1))
        self.vote("1030", "2025-03-24", SPD=3, AfD=1)
        self.vote("1031", "2025-06-26")
        self.vote("1032", "2025-06-26", SPD=3, AfD=1)
        err, path = self.log()
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual((report["compared"], report["agree"]), (1, 1))
        self.assertEqual(report["not_compared"], {"without_seat_count": ["1030"], "without_totals": ["1031"], "with_unbekannt": []})
        self.assertIn("cross-check of 1 roll-call against the seat counts: 1 agree, 0 disagree; 2 not compared", err)
        self.assertIn("warning: [stammdaten] not compared, no seat count on the date, 1 roll-call: 1030", err)
        self.assertIn("warning: [stammdaten] not compared, no group totals, 1 roll-call: 1031", err)

    # Value: protects=a store the cross-check cannot read (missing file, not a database) ends in one
    #   note on stderr and no report, never an exception, so a routine update is not stopped; fails_when=
    #   the sqlite3.Error from opening or querying escapes log_seat_crosscheck; why_new=TODOS C1 deferred
    #   item 18 (the unreadable-store branch has no test); seam=none (log_seat_crosscheck is production code);
    #   no_claim=an OSError while writing the report (deferred item 12 says that one still escapes)
    def test_a_store_that_cannot_be_read_gives_a_note_not_an_exception(self) -> None:
        garbage = Path(self._tmp.name) / "garbage.sqlite"
        garbage.write_bytes(b"this is not a database" * 100)
        for label, database in {"missing": Path(self._tmp.name) / "missing.sqlite", "not a database": garbage}.items():
            with self.subTest(label):
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    build.log_seat_crosscheck(database)
                self.assertIn("note: [stammdaten] no cross-check, the store could not be read:", err.getvalue())
                self.assertFalse(stammdaten.crosscheck_path(database).exists())

    # Value: protects=without Stammdaten the build says once that there is no cross-check
    #   and removes the report of an earlier build, which would describe seat counts the
    #   store no longer holds; fails_when=a stale report survives, or every roll-call is
    #   reported; why_new=C1 step 5; seam=build.log_seat_crosscheck
    def test_no_stammdaten_removes_the_old_report(self) -> None:
        self.vote("1024", "2025-06-26", SPD=3)
        stale = registry.private_dir(self.path) / "seat-crosscheck.json"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("{}", encoding="utf-8")
        err, path = self.log()
        self.assertFalse(path.exists())
        self.assertEqual(err.strip().splitlines(), ["stammdaten: no cross-check, MdB-Stammdaten nicht geladen"])


if __name__ == "__main__":
    unittest.main()
