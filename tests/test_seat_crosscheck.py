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
from unittest import mock

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
        self.conn.execute("INSERT INTO votes(id, protocol_id, date, top_link_step, created_at, updated_at) VALUES (?, ?, ?, 'none', ?, ?)",
                          (vote_id, protocol_id, day, NOW, NOW))
        for party, total in totals.items():
            party_id = pulse_store.upsert_party(self.conn, PARTY.get(party, party), NOW)
            self.conn.execute("INSERT INTO vote_fractions(vote_id, party_id, total_count, rank) VALUES (?, ?, ?, 1)",
                              (vote_id, party_id, total))

    def refiled_vote(self, vote_id: str, day: str, page: dict[str, int], moves: list[tuple[str, str, str]]) -> None:
        """A roll-call persisted as the build persists it: the page's group counts ``page`` (all Nein), and the
        members ``moves`` names, (name, the page's group, the group the Stammdaten prove), re-filed."""
        members = [{"name": name, "faction": listed, "vote": "no", "profile_url": None, "refiled_to": filed}
                   for name, listed, filed in moves]
        fractions = [{"name": party, "counts": {"yes": 0, "no": count, "abstain": 0, "absent": 0}, "total": count}
                     for party, count in page.items()]
        the_vote = {"id": vote_id, "date": day, "title": "Test", "members": members, "fractions": fractions,
                    "detail_url": f"https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id={vote_id}",
                    "total": {"yes": 0, "no": sum(page.values()), "abstain": 0, "absent": 0}}
        with self.conn:
            pulse_store.persist_vote(self.conn, the_vote, protocol_id=None, now=NOW, top_link_step="none")

    def causes(self, result: stammdaten.CrossCheck) -> list[tuple]:
        return [(row["vote_id"], row["party"], row["stammdaten_seats"], row["roll_call_total"], row["filed_total"], row["cause"])
                for row in result.disagreements]


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
            {"vote_id": "1001", "date": "2025-06-26", "wahlperiode": 21, "party": "SPD", "stammdaten_seats": 3,
             "roll_call_total": 2, "filed_total": 2, "page_difference": -1, "filed_difference": -1, "cause": "roll_call_short"},
        ])
        self.assertEqual(result.refiled, [])

    # Value: protects=a roll-call that files members under another group than the
    #   Stammdaten (the E4 shape: the totals agree, the groups do not) is one roll-call
    #   with a row per group, filed as a shift; fails_when=a net-zero difference is read
    #   as members missing or as unexplained, or one side's row is dropped; why_new=C1
    #   step 5; seam=stammdaten.crosscheck
    def test_members_filed_under_another_group_are_a_shift(self) -> None:
        self.stammdaten(bundestag(AfD=3, SPD=2, fraktionslos=1))
        self.vote("1002", "2025-06-26", AfD=2, SPD=2, fraktionslos=2)
        result = stammdaten.crosscheck(self.conn)
        self.assertEqual([(row["party"], row["filed_difference"], row["cause"]) for row in result.disagreements],
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
        self.assertEqual([(row["vote_id"], row["party"], row["filed_difference"], row["cause"]) for row in result.disagreements], [
            ("1003", "Gruppe BSW", -3, "change_on_vote_day"), ("1003", "fraktionslos", 3, "change_on_vote_day"),
            ("1004", "AfD", -1, "shift_between_groups"), ("1004", "fraktionslos", 1, "shift_between_groups"),
        ])

    # Value: protects=D6: a roll-call in the 90 days before the Stammdaten's Stand, or after it, that disagrees is
    #   near the Stand, filed as such whatever its shape (it warns and never fails the gate), while one 90 days
    #   before is still judged by its shape: the same boundary as the refiling (TODOS E4 deferred item 2);
    #   fails_when=the cross-check and the refiling use different boundaries, or the shape test runs first;
    #   why_new=C1 step 5, window from E4 item 2; seam=stammdaten.crosscheck
    def test_a_disagreement_in_the_90_days_before_the_stand_is_near_the_stand(self) -> None:
        self.stammdaten(bundestag(SPD=3, AfD=1), stand="2025-08-01T08:03:03+00:00")
        self.vote("1005", "2025-05-03", SPD=2, AfD=1)
        self.vote("1006", "2025-05-04", SPD=2, AfD=2)
        self.vote("1007", "2025-08-02", SPD=2, AfD=1)
        result = stammdaten.crosscheck(self.conn)
        self.assertEqual([(row["vote_id"], row["party"], row["cause"]) for row in result.disagreements], [
            ("1005", "SPD", "roll_call_short"), ("1006", "AfD", "near_stand"), ("1006", "SPD", "near_stand"),
            ("1007", "SPD", "near_stand"),
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

    # Value: protects=a roll-call whose page files a member under another group than the Stammdaten, re-filed by
    #   E4, is reported with the page's count beside the filed one and filed as re-filed, and the move is listed
    #   (TODOS E4 deferred item 4); fails_when=the check compares only the filed counts, which come from the same
    #   file as the seats, so the page's disagreement disappears; why_new=item 4; seam=stammdaten.crosscheck
    def test_a_roll_call_the_stammdaten_re_filed_is_filed_as_refiled(self) -> None:
        self.stammdaten(bundestag(AfD=87, fraktionslos=9))
        self.refiled_vote("1101", "2025-06-26", {"AfD": 86, "fraktionslos": 10}, [("Kamann, Uwe", "fraktionslos", "AfD")])
        result = stammdaten.crosscheck(self.conn)
        self.assertEqual(result.disagreements, [
            {"vote_id": "1101", "date": "2025-06-26", "wahlperiode": 21, "party": "AfD", "stammdaten_seats": 87,
             "roll_call_total": 86, "filed_total": 87, "page_difference": -1, "filed_difference": 0, "cause": "refiled"},
            {"vote_id": "1101", "date": "2025-06-26", "wahlperiode": 21, "party": "fraktionslos", "stammdaten_seats": 9,
             "roll_call_total": 10, "filed_total": 9, "page_difference": 1, "filed_difference": 0, "cause": "refiled"},
        ])
        self.assertEqual(result.refiled, [{"vote_id": "1101", "date": "2025-06-26", "member": "Kamann, Uwe",
                                           "listed": "fraktionslos", "filed": "AfD"}])

    # Value: protects=a re-filed roll-call whose filed counts still disagree with the seats is filed by the shape
    #   of the filed differences, with the page's count in its rows and the move in the list; a move that breaks an
    #   agreement the page had is filed by shape too, never as re-filed; fails_when=any roll-call with a move counts
    #   as explained; why_new=item 4; seam=stammdaten.crosscheck
    def test_a_residual_beside_a_move_is_filed_by_its_shape(self) -> None:
        self.stammdaten(bundestag(AfD=88, fraktionslos=8))
        self.refiled_vote("1102", "2025-06-26", {"AfD": 86, "fraktionslos": 10}, [("Kamann, Uwe", "fraktionslos", "AfD")])
        self.refiled_vote("1103", "2025-06-26", {"AfD": 88, "fraktionslos": 8}, [("Muster, Ada", "AfD", "fraktionslos")])
        result = stammdaten.crosscheck(self.conn)
        self.assertEqual(self.causes(result), [
            ("1102", "AfD", 88, 86, 87, "shift_between_groups"), ("1102", "fraktionslos", 8, 10, 9, "shift_between_groups"),
            ("1103", "AfD", 88, 88, 87, "shift_between_groups"), ("1103", "fraktionslos", 8, 8, 9, "shift_between_groups"),
        ])
        self.assertEqual([(move["vote_id"], move["member"]) for move in result.refiled], [("1102", "Kamann, Uwe"), ("1103", "Muster, Ada")])

    # Value: protects=two opposite moves in one roll-call cancel in the totals, so nothing disagrees, but both stay in
    #   the list; fails_when=the list is built from the disagreements; why_new=Codex plan review finding 2;
    #   seam=stammdaten.crosscheck
    def test_opposite_moves_that_cancel_are_still_listed(self) -> None:
        self.stammdaten(bundestag(AfD=87, fraktionslos=9))
        self.refiled_vote("1104", "2025-06-26", {"AfD": 87, "fraktionslos": 9},
                          [("Kamann, Uwe", "fraktionslos", "AfD"), ("Muster, Ada", "AfD", "fraktionslos")])
        result = stammdaten.crosscheck(self.conn)
        self.assertEqual((result.compared, result.disagreements), (1, []))
        self.assertEqual([move["member"] for move in result.refiled], ["Kamann, Uwe", "Muster, Ada"])

    # Value: protects=a group every member of which the Stammdaten moved has no vote_fractions row, and its page count
    #   comes back from the moves; fails_when=the page counts are taken over the filed groups only; why_new=Codex plan
    #   review finding 3; seam=stammdaten.crosscheck
    def test_a_group_its_members_all_left_gets_its_page_count_back(self) -> None:
        self.stammdaten(bundestag(AfD=87))
        self.refiled_vote("1105", "2025-06-26", {"AfD": 86, "fraktionslos": 1}, [("Kamann, Uwe", "fraktionslos", "AfD")])
        result = stammdaten.crosscheck(self.conn)
        self.assertEqual(self.causes(result), [("1105", "AfD", 87, 86, 87, "refiled"), ("1105", "fraktionslos", 0, 1, 0, "refiled")])

    # Value: protects=moves that would put a page count below zero (the moves and vote_fractions disagree, as when two
    #   page entries share one member row) make the roll-call not comparable instead of a made-up figure; fails_when=a
    #   negative page count is compared; why_new=Codex plan review finding 3; seam=stammdaten.crosscheck
    def test_moves_the_group_totals_cannot_hold_are_not_compared(self) -> None:
        self.stammdaten(bundestag(AfD=87, fraktionslos=9))
        self.refiled_vote("1106", "2025-06-26", {"AfD": 86, "fraktionslos": 10}, [("Kamann, Uwe", "fraktionslos", "AfD")])
        self.conn.execute("UPDATE vote_fractions SET total_count = 0 WHERE party_id = (SELECT id FROM parties WHERE name = 'AfD')")
        result = stammdaten.crosscheck(self.conn)
        self.assertEqual((result.compared, result.disagreements, result.moves_inconsistent), (0, [], ["1106"]))
        self.assertEqual(len(result.refiled), 1)

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
    #   cause in one summary line, and warns for disagreements near the Stand (D6) and for a
    #   disagreement in no known shape, without failing; the report holds no build time,
    #   so an unchanged store gives the same file; fails_when=the report is published,
    #   lost, stamped, or an unexplained roll-call passes silently; why_new=C1 step 5;
    #   seam=build.log_seat_crosscheck
    def test_the_report_lists_every_disagreement_and_the_summary_counts_causes(self) -> None:
        self.stammdaten(bundestag(SPD=3, AfD=1), stand="2025-08-01T08:03:03+00:00")
        self.vote("1020", "2025-04-26", SPD=3, AfD=1)
        self.vote("1021", "2025-04-26", SPD=3, AfD=2)
        self.vote("1022", "2025-08-02", SPD=2, AfD=1)
        self.vote("1023", "2025-04-26", SPD=3, Unbekannt=1)
        err, path = self.log()
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {
            "stand": "2025-08-01T08:03:03+00:00", "sha256": "0" * 64,
            "compared": 3, "agree": 1,
            "roll_calls_by_cause": {"near_stand": ["1022"], "refiled": [], "change_on_vote_day": [], "shift_between_groups": [],
                                    "roll_call_short": [], "unexplained": ["1021"]},
            "not_compared": {"without_seat_count": [], "without_totals": [], "with_unbekannt": ["1023"], "moves_inconsistent": []},
            "disagreements": [
                {"vote_id": "1021", "date": "2025-04-26", "wahlperiode": 21, "party": "AfD", "stammdaten_seats": 1,
                 "roll_call_total": 2, "filed_total": 2, "page_difference": 1, "filed_difference": 1, "cause": "unexplained"},
                {"vote_id": "1022", "date": "2025-08-02", "wahlperiode": 21, "party": "SPD", "stammdaten_seats": 3,
                 "roll_call_total": 2, "filed_total": 2, "page_difference": -1, "filed_difference": -1, "cause": "near_stand"},
            ],
            "refiled": [],
        })
        self.assertIn("stammdaten: cross-check of 3 roll-calls against the seat counts: 1 agree, 2 disagree "
                      "(1 near the Stand, 1 unexplained); 1 not compared", err)
        self.assertIn("warning: [stammdaten] disagreement with the seat counts in no known shape, 1 roll-call: 1021", err)
        self.assertIn("warning: [stammdaten] disagreement after 03.05.2025, 90 days before the Stand (01.08.2025): the "
                      "file may not record a change yet, 1 roll-call: 1022", err)
        self.assertIn("warning: [stammdaten] not compared, a group named Unbekannt, 1 roll-call: 1023", err)
        first = path.read_bytes()
        self.log()
        self.assertEqual(path.read_bytes(), first)

    # Value: protects=the report lists every re-filed Stimme and the summary line counts them and the re-filed
    #   roll-calls without a warning, while moves the totals cannot hold are warned about as not compared (TODOS E4
    #   deferred item 4); fails_when=the moves are dropped from the report, or 87 explained roll-calls warn on every
    #   build; why_new=item 4; seam=build.log_seat_crosscheck
    def test_the_report_lists_the_moves_and_the_summary_counts_them(self) -> None:
        self.stammdaten(bundestag(AfD=87, fraktionslos=9))
        self.refiled_vote("1050", "2025-04-26", {"AfD": 86, "fraktionslos": 10}, [("Kamann, Uwe", "fraktionslos", "AfD")])
        self.refiled_vote("1051", "2025-04-26", {"AfD": 87, "fraktionslos": 9},
                          [("Kamann, Uwe", "fraktionslos", "AfD"), ("Muster, Ada", "AfD", "fraktionslos")])
        self.refiled_vote("1052", "2025-04-26", {"AfD": 86, "fraktionslos": 10}, [("Kamann, Uwe", "fraktionslos", "AfD")])
        self.conn.execute("UPDATE vote_fractions SET total_count = 0 WHERE vote_id = '1052' AND party_id = "
                          "(SELECT id FROM parties WHERE name = 'AfD')")
        err, path = self.log()
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(report["roll_calls_by_cause"]["refiled"], ["1050"])
        self.assertEqual(report["not_compared"]["moves_inconsistent"], ["1052"])
        self.assertEqual([(move["vote_id"], move["member"], move["listed"], move["filed"]) for move in report["refiled"]], [
            ("1050", "Kamann, Uwe", "fraktionslos", "AfD"), ("1051", "Kamann, Uwe", "fraktionslos", "AfD"),
            ("1051", "Muster, Ada", "AfD", "fraktionslos"), ("1052", "Kamann, Uwe", "fraktionslos", "AfD")])
        self.assertIn("cross-check of 2 roll-calls against the seat counts: 1 agree, 1 disagree (1 re-filed); "
                      "4 Stimmen re-filed in 3 roll-calls; 1 not compared", err)
        self.assertIn("warning: [stammdaten] not compared, the re-filed Stimmen and the group totals disagree, 1 roll-call: 1052", err)
        self.assertNotIn("1050", "".join(line for line in err.splitlines() if line.startswith("warning:")))

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
        self.assertEqual(report["not_compared"], {"without_seat_count": ["1030"], "without_totals": ["1031"], "with_unbekannt": [],
                                                  "moves_inconsistent": []})
        self.assertIn("cross-check of 1 roll-call against the seat counts: 1 agree, 0 disagree; 2 not compared", err)
        self.assertIn("warning: [stammdaten] not compared, no seat count on the date, 1 roll-call: 1030", err)
        self.assertIn("warning: [stammdaten] not compared, no group totals, 1 roll-call: 1031", err)

    # Value: protects=a store the cross-check cannot read (missing file, not a database) ends in one
    #   note on stderr and no report, never an exception, so a routine update is not stopped; fails_when=
    #   the sqlite3.Error from opening or querying escapes log_seat_crosscheck; why_new=TODOS C1 deferred
    #   item 18 (the unreadable-store branch has no test); seam=none (log_seat_crosscheck is production code);
    #   no_claim=an OSError while writing the report (the next two tests)
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

    # Value: protects=the report is written or removed only in a private directory that is a real
    #   directory, never through a symlink planted at the private directory's place, so neither the
    #   write nor the unlink of an earlier report reaches a file elsewhere; the build still goes on
    #   with a note; fails_when=log_seat_crosscheck mkdirs and writes or unlinks without
    #   registry.ensure_private_dir; why_new=TODOS C1 deferred item 33 (and 8); seam=build.log_seat_crosscheck
    def test_a_symlinked_private_directory_is_refused_for_the_write_and_the_unlink(self) -> None:
        for label, with_stammdaten in (("report written", True), ("old report removed", False)):
            with self.subTest(label):
                self.setUp()
                elsewhere = Path(self._tmp.name) / "elsewhere"
                elsewhere.mkdir()
                victim = Path(self._tmp.name) / "victim.json"
                victim.write_text("keep", encoding="utf-8")
                (elsewhere / "seat-crosscheck.json").symlink_to(victim)
                registry.private_dir(self.path).symlink_to(elsewhere)
                self.vote("1040", "2025-06-26", SPD=3, AfD=1)
                if with_stammdaten:
                    self.stammdaten(bundestag(SPD=3, AfD=1))
                err, _ = self.log()
                self.assertEqual(victim.read_text(encoding="utf-8"), "keep")
                self.assertTrue((elsewhere / "seat-crosscheck.json").is_symlink())
                self.assertIn("note: [stammdaten] the cross-check report could not be", err)
                self.assertIn("symbolic link", err)
                self.assertNotIn("report:", err)

    # Value: protects=an OSError from writing the report (full disk, permissions) ends in a note and
    #   the summary lines, never an exception that leaves main() after the store swap and before the
    #   site and export, as the docstring promises; fails_when=the OSError escapes, or the summary is
    #   skipped with the report; why_new=TODOS C1 deferred item 12; seam=build.log_seat_crosscheck with
    #   write_text_atomic failing
    def test_a_report_that_cannot_be_written_gives_a_note_and_the_summary(self) -> None:
        self.stammdaten(bundestag(SPD=3, AfD=1))
        self.vote("1041", "2025-06-26", SPD=3, AfD=1)
        with mock.patch.object(build.dip, "write_text_atomic", side_effect=OSError(28, "No space left on device")):
            err, path = self.log()
        self.assertFalse(path.exists())
        self.assertIn("note: [stammdaten] the cross-check report could not be written: [Errno 28] No space left on device", err)
        self.assertIn("stammdaten: cross-check of 1 roll-call against the seat counts: 1 agree, 0 disagree", err)
        self.assertNotIn("report:", err)


if __name__ == "__main__":
    unittest.main()
