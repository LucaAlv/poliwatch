"""E4: a roll-call page that files an MdB under the wrong group is corrected from
the MdB-Stammdaten, where they prove the group (TODOS.md, "Correct the WP 19/20
roll-call group misattributions (E4) from the MdB-Stammdaten")."""

from __future__ import annotations

import contextlib
import copy
import io
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import build_dip_pulse_site as build
import derive
import persist_dip_pulse_store as pulse_store
import stammdaten
from _votes_fixture import vote_summary

NOW = "2026-11-04T00:00:00+00:00"
STAND = "2026-04-29T08:03:03+00:00"


def row(name: str, party: str, valid_from: str, valid_until: str | None, *, mdb_id: str | None = None, wp: int = 19) -> dict:
    return {"mdb_id": mdb_id or f"id-{name}", "name": name, "wahlperiode": wp, "party": party,
            "valid_from": valid_from, "valid_until": valid_until}


def member(name: str, faction: str, stimme: str = "no") -> dict:
    return {"name": name, "faction": faction, "vote": stimme, "profile_url": None}


def fraction(name: str, *, yes: int = 0, no: int = 0, abstain: int = 0, absent: int = 0) -> dict:
    return {"name": name, "counts": {"yes": yes, "no": no, "abstain": abstain, "absent": absent},
            "total": yes + no + abstain + absent}


def vote(*members: dict, fractions: list[dict] | None = None, day: str = "2018-06-01", vote_id: str = "500") -> dict:
    return {"id": vote_id, "date": day, "title": "Test", "members": list(members), "fractions": fractions or [],
            "detail_url": f"https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id={vote_id}",
            "total": {"yes": 0, "no": 0, "abstain": 0, "absent": 0}}


KAMANN = [row("Uwe Kamann", "AfD", "2017-10-24", "2019-01-03"), row("Uwe Kamann", "fraktionslos", "2019-01-03", "2021-10-26")]


def source(rows: list[dict], stand: str = STAND, unrecorded: dict | None = None) -> derive.RefilingSource:
    """The lookup for hand-written rows, each standing for a recorded Fraktion or Gruppe membership unless
    ``unrecorded`` lists its days as rule-3 days, (Wahlperiode, MdB id) to (first day, end) pairs."""
    return derive.refiling_source(rows, stand, unrecorded or {})


def filed(the_vote: dict, rows: list[dict], *, wahlperiode: int = 19, stand: str = STAND) -> list[dict]:
    derive.refile_vote_members(the_vote, wahlperiode, source(rows, stand))
    return [m for m in the_vote["members"] if "refiled_to" in m]


class NameKeyTests(unittest.TestCase):
    # Value: protects=the two spellings of one MdB meet: the page's "Nachname, Titel Vorname" and the
    #   Stammdaten's "Vorname Nachname", whatever the page's titles; fails_when=titles or word order stay in the
    #   key; why_new=E4 needs a name link, no member row carries an MdB id; seam=none
    def test_the_page_spelling_and_the_stammdaten_spelling_are_one_key(self) -> None:
        for page, stammdaten_name in (
            ("Kamann, Uwe", "Uwe Kamann"),
            ("Heßenkemper, Prof. Dr. Heiko", "Heiko Heßenkemper"),
            ("Kaufmann, Prof. Dr.-Ing. habil. Michael", "Michael Kaufmann"),
            ("Michelbach, Dr. h. c. (Univ Kyiv) Hans", "Hans Michelbach"),
            ("Birkwald, Matthias W.", "Matthias W. Birkwald"),
        ):
            self.assertEqual(derive.person_name_key(page), derive.person_name_key(stammdaten_name), page)

    # Value: protects=blank and unbalanced names give no key rather than a crash, and a long run stays fast
    #   (checklist class 8); fails_when=the scan backtracks on a long "(" run; why_new=new scanner of source text; seam=none
    def test_hostile_names_end_in_no_key_quickly(self) -> None:
        self.assertEqual(derive.person_name_key(None), frozenset())
        self.assertEqual(derive.person_name_key("  ,  "), frozenset())
        self.assertEqual(derive.person_name_key("(ohne Klammerende"), frozenset({"(ohne", "klammerende"}))
        started = time.monotonic()
        derive.person_name_key("(" * 200_000 + "a" + ")" * 3)
        self.assertLess(time.monotonic() - started, 1.0)


class RefileRuleTests(unittest.TestCase):
    # Value: protects=the E4 shape: a page listing Kamann as fraktionslos while the Stammdaten say AfD files him
    #   under the AfD, keeps what the page printed, and moves his Stimme between the two groups' counts;
    #   fails_when=the page's faction or fractions are overwritten, or the counts stay; why_new=E4; seam=none
    def test_a_member_the_stammdaten_place_elsewhere_moves_with_his_stimme(self) -> None:
        the_vote = vote(member("Kamann, Uwe", "fraktionslos", "yes"), member("Müller, Max", "AfD"),
                        fractions=[fraction("AfD", no=90), fraction("fraktionslos", yes=2, no=1)])
        before = copy.deepcopy(the_vote["fractions"])
        moved = filed(the_vote, KAMANN)
        self.assertEqual([(m["name"], m["faction"], m["refiled_to"]) for m in moved], [("Kamann, Uwe", "fraktionslos", "AfD")])
        self.assertEqual(the_vote["fractions"], before)
        self.assertEqual(derive.member_group(the_vote["members"][0]), "AfD")
        self.assertEqual(derive.filed_fractions(the_vote), [
            {"name": "AfD", "counts": {"yes": 1, "no": 90, "abstain": 0, "absent": 0}, "total": 91},
            {"name": "fraktionslos", "counts": {"yes": 1, "no": 1, "abstain": 0, "absent": 0}, "total": 2},
        ])

    # Value: protects=occurrence ids and identity keys stay what the page gives, so a correction creates no new
    #   person binding (checklist class 3); fails_when=the rule writes into faction; why_new=vote_member_key
    #   hashes the faction; seam=none
    def test_the_occurrence_key_does_not_move(self) -> None:
        the_vote = vote(member("Kamann, Uwe", "fraktionslos"), fractions=[fraction("AfD", no=1), fraction("fraktionslos", no=1)])
        key, identity = derive.vote_member_key("500", the_vote["members"][0]), derive.vote_member_identity(the_vote["members"][0])
        self.assertEqual(len(filed(the_vote, KAMANN)), 1)
        self.assertEqual(derive.vote_member_key("500", the_vote["members"][0]), key)
        self.assertEqual(derive.vote_member_identity(the_vote["members"][0]), identity)

    # Value: protects=a group the page does not list at all gets a row, and one left with nobody loses its row;
    #   the vote's counts still add up; fails_when=a zero row or a lost Stimme; why_new=the Pasemann direction; seam=none
    def test_rows_appear_and_disappear_with_their_last_member(self) -> None:
        rows = [row("Frank Pasemann", "fraktionslos", "2020-11-15", "2021-10-26")]
        the_vote = vote(member("Pasemann, Frank", "AfD"), fractions=[fraction("AfD", no=1), fraction("SPD", yes=5)], day="2020-12-01")
        self.assertEqual(len(filed(the_vote, rows)), 1)
        self.assertEqual([(r["name"], r["total"]) for r in derive.filed_fractions(the_vote)], [("SPD", 5), ("fraktionslos", 1)])

    # Value: protects=the 111 rows of 2024-02-02: the Gruppen start that day, the day alone cannot say whether the
    #   vote came first, so the page stands (C1 cause change_on_vote_day); fails_when=a change on the vote's day
    #   counts as proof; why_new=the naive rule moves votes 897, 898 and 912; seam=none
    def test_a_change_on_the_day_of_the_vote_keeps_the_page(self) -> None:
        rows = [row("Heidi Reichinnek", "fraktionslos", "2023-12-06", "2024-02-02", wp=20),
                row("Heidi Reichinnek", "Gruppe Die Linke", "2024-02-02", "2025-03-25", wp=20)]
        the_vote = vote(member("Reichinnek, Heidi", "fraktionslos"),
                        fractions=[fraction("fraktionslos", no=1), fraction("Gruppe Die Linke", no=1)], day="2024-02-02")
        self.assertEqual(filed(the_vote, rows, wahlperiode=20), [])
        # A membership that ended on the vote's day is the same case.
        the_vote["date"] = "2023-12-06"
        self.assertEqual(filed(the_vote, [row("Heidi Reichinnek", "Gruppe Die Linke", "2021-10-26", "2023-12-06", wp=20), *rows], wahlperiode=20), [])

    # Value: protects=a vote in the 90 days before the Stand, or after it, keeps the page: the file may not record a
    #   change yet, and its open row is only carried forward (TODOS E4 deferred item 2; checklist class 2);
    #   fails_when=the window is off by one, or the Stand day itself still proves; why_new=the window replaces the
    #   Stand-day guard; seam=refile_vote_members
    def test_only_a_vote_more_than_90_days_before_the_stand_moves(self) -> None:
        rows = [row("Ada Muster", "AfD", "2025-03-25", None, wp=21)]
        for day, moves in (("2026-01-28", True), ("2026-01-29", True), ("2026-01-30", False),
                           ("2026-04-29", False), ("2026-06-25", False)):
            the_vote = vote(member("Muster, Ada", "fraktionslos"), fractions=[fraction("AfD", no=1), fraction("fraktionslos", no=1)], day=day)
            self.assertEqual(len(filed(the_vote, rows, wahlperiode=21)), int(moves), day)

    # Value: protects=no proof, no move: namesakes in one Wahlperiode, a name the Stammdaten lack, another
    #   Wahlperiode's row, a day no row covers, no date or an unreadable one, a member listed twice; fails_when=any of
    #   them binds the neighbour (checklist class 7); why_new=the link is a name; seam=none
    def test_without_proof_the_page_stands(self) -> None:
        fractions = [fraction("AfD", no=2), fraction("fraktionslos", no=2)]
        namesakes = [row("Max Muster", "AfD", "2017-10-24", None, mdb_id="a"), row("Max Muster", "SPD", "2017-10-24", None, mdb_id="b")]
        one = member("Muster, Max", "fraktionslos")
        self.assertEqual(filed(vote(one, fractions=fractions), namesakes), [])
        self.assertEqual(filed(vote(member("Unbekannt, Niemand", "fraktionslos"), fractions=fractions), KAMANN), [])
        self.assertEqual(filed(vote(member("Kamann, Uwe", "fraktionslos"), fractions=fractions), KAMANN, wahlperiode=20), [])
        self.assertEqual(filed(vote(member("Kamann, Uwe", "fraktionslos"), fractions=fractions, day="2017-01-01"), KAMANN), [])
        self.assertEqual(filed(vote(member("Kamann, Uwe", "fraktionslos"), fractions=fractions, day=""), KAMANN), [])
        self.assertEqual(filed(vote(member("Kamann, Uwe", "fraktionslos"), fractions=fractions, day="1.6.2018"), KAMANN), [])
        self.assertEqual(filed(vote(member("Kamann, Uwe", "fraktionslos"), member("Kamann, Uwe", "fraktionslos"), fractions=fractions), KAMANN), [])
        self.assertEqual(filed(vote(member("Kamann, Uwe", "fraktionslos"), fractions=fractions), KAMANN, wahlperiode=None), [])

    # Value: protects=a vote whose counts cannot absorb the moves is left as the page has it, whole, and says so;
    #   fails_when=negative counts, or half a vote re-filed; why_new=the page's rows and member list can disagree;
    #   no_claim=which side of such a page is right; seam=none
    # Value (extension): protects=a vote whose second move cannot be absorbed has none of its members marked, and
    #   refile_vote_members says False; fails_when=a member is marked inside the checking loop, before all moves
    #   fit; why_new=every earlier case failed on its first move; seam=none
    def test_counts_that_cannot_absorb_the_move_leave_the_vote_alone(self) -> None:
        for the_vote in (
            vote(member("Kamann, Uwe", "fraktionslos", "no"), fractions=[fraction("AfD", no=1), fraction("fraktionslos", yes=1)]),
            vote(member("Kamann, Uwe", "fraktionslos", "unknown"), fractions=[fraction("AfD", no=1), fraction("fraktionslos", no=1)]),
            vote(member("Kamann, Uwe", "fraktionslos", "no"), fractions=[]),
        ):
            self.assertEqual(filed(the_vote, KAMANN), [], the_vote["members"])
            self.assertEqual(derive.filed_fractions(the_vote), derive.merge_fractions(the_vote["fractions"]))
        # Two moves out of one group: the first fits, the second cannot, and the vote stays whole, the first member unmarked.
        the_vote = vote(member("Kamann, Uwe", "fraktionslos", "no"), member("Muster, Max", "fraktionslos", "no"),
                        fractions=[fraction("AfD", no=2), fraction("fraktionslos", no=1)])
        two = [*KAMANN, row("Max Muster", "AfD", "2017-10-24", None)]
        self.assertFalse(derive.refile_vote_members(the_vote, 19, source(two)))
        self.assertEqual([m.get("refiled_to") for m in the_vote["members"]], [None, None])
        self.assertEqual(derive.filed_fractions(the_vote), derive.merge_fractions(the_vote["fractions"]))

    # Value: protects=the correction is worked out from what the page printed on every run: applying it twice
    #   moves nothing twice, and without the Stammdaten or with a file that no longer says so the page returns;
    #   fails_when=a stale refiled_to survives (checklist classes 2 and 3); why_new=write_report_files writes the mark
    #   into the cached report; seam=none
    def test_the_mark_is_recomputed_from_the_page_every_time(self) -> None:
        the_vote = vote(member("Kamann, Uwe", "fraktionslos"), fractions=[fraction("AfD", no=1), fraction("fraktionslos", no=1)])
        filed(the_vote, KAMANN)
        once = derive.filed_fractions(the_vote)
        self.assertEqual(len(filed(the_vote, KAMANN)), 1)
        self.assertEqual(derive.filed_fractions(the_vote), once)
        derive.refile_vote_members(the_vote, 19, None)
        self.assertNotIn("refiled_to", the_vote["members"][0])
        self.assertEqual(derive.filed_fractions(the_vote), derive.merge_fractions(the_vote["fractions"]))
        filed(the_vote, KAMANN)
        self.assertEqual(filed(the_vote, [row("Uwe Kamann", "fraktionslos", "2017-10-24", "2021-10-26")]), [])

    # Value: protects=the Abweichler read the corrected group: Kamann is counted against the AfD's Mehrheitsvotum,
    #   and the groups still add up to the vote (R3, the panel, the archive); fails_when=vote_abweichler or
    #   vote_groups_cover_total read the page's fields; why_new=E4 names them as affected; seam=none
    # Value (extension): protects=Kamann (Ja) is the AfD's one Abweichler against three Nein, not a tie in a group;
    #   fails_when=vote_abweichler reads the page's faction or rows; why_new=the first fixture is a tie, so reverting
    #   passed; seam=none; no_claim=vote_groups_cover_total, which a move cannot change (sums stay)
    def test_abweichler_and_the_vote_total_read_the_filed_groups(self) -> None:
        the_vote = vote(member("Kamann, Uwe", "fraktionslos", "yes"), member("Müller, Max", "AfD", "no"),
                        fractions=[fraction("AfD", no=1), fraction("fraktionslos", yes=1)])
        the_vote["total"] = {"yes": 1, "no": 1, "abstain": 0, "absent": 0}
        filed(the_vote, KAMANN)
        groups = derive.vote_abweichler(the_vote)
        self.assertEqual([m["name"] for m in groups["AfD"]["members"]], [])  # one Ja, one Nein: a tie has no Mehrheitsvotum
        self.assertEqual(groups["AfD"]["state"], "complete")
        self.assertTrue(derive.vote_groups_cover_total(the_vote))
        self.assertEqual(derive.vote_abweichler_count(the_vote), 0)
        # No tie: three AfD Nein and Kamann's Ja. Under the page's group (fraktionslos) he dissents from no one.
        the_vote = vote(member("Kamann, Uwe", "fraktionslos", "yes"), *(member(f"Müller{i}, Max", "AfD", "no") for i in range(3)),
                        fractions=[fraction("AfD", no=3), fraction("fraktionslos", yes=1)])
        the_vote["total"] = {"yes": 1, "no": 3, "abstain": 0, "absent": 0}
        filed(the_vote, KAMANN)
        groups = derive.vote_abweichler(the_vote)
        self.assertEqual([m["name"] for m in groups["AfD"]["members"]], ["Kamann, Uwe"])
        self.assertEqual(derive.vote_abweichler_count(the_vote), 1)
        self.assertTrue(derive.vote_groups_cover_total(the_vote))


class ReportTests(unittest.TestCase):
    # Value: protects=every copy of a vote in a report is marked, the TOP's and the sitting's, since the panel
    #   renders each copy and persist keeps the last; fails_when=only iter_report_votes' first copy is marked;
    #   why_new=a vote can sit under two TOPs; seam=none
    def test_every_copy_of_a_vote_is_marked(self) -> None:
        fractions = [fraction("AfD", no=1), fraction("fraktionslos", no=1)]
        report = {
            "protocol": {"dokumentnummer": "19/30"},
            "agenda_items": [{"votes": [vote(member("Kamann, Uwe", "fraktionslos"), fractions=fractions)]},
                             {"votes": [vote(member("Kamann, Uwe", "fraktionslos"), fractions=fractions)]}],
            "sitting_votes": [vote(member("Kamann, Uwe", "fraktionslos"), fractions=fractions, vote_id="501")],
        }
        derive.refile_report_votes(report, source(KAMANN))
        copies = [*report["agenda_items"][0]["votes"], *report["agenda_items"][1]["votes"], *report["sitting_votes"]]
        self.assertEqual([c["members"][0].get("refiled_to") for c in copies], ["AfD", "AfD", "AfD"])


class PersistTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.conn = pulse_store.connect(Path(self._tmp.name) / "s.sqlite")
        self.addCleanup(self.conn.close)
        pulse_store.initialize(self.conn)

    def persisted(self, the_vote: dict) -> None:
        with self.conn:
            pulse_store.persist_vote(self.conn, the_vote, protocol_id=None, now=NOW, top_link_step="none")

    def rows(self, sql: str) -> list[tuple]:
        return [tuple(row) for row in self.conn.execute(sql)]

    # Value: protects=the store holds the corrected group and counts with the Mehrheitsvotum computed from them, and
    #   the page's group beside the Stimme; a member the page has right has no second group; fails_when=vote_fractions
    #   keeps the page's counts or leading_vote stays stale (checklist class 6); why_new=E4 and its second column; seam=none
    def test_the_store_holds_the_corrected_figures_and_the_pages_group(self) -> None:
        the_vote = vote(member("Kamann, Uwe", "fraktionslos", "yes"), member("Müller, Max", "fraktionslos", "no"),
                        fractions=[fraction("AfD", no=1), fraction("fraktionslos", yes=1, no=1)])
        filed(the_vote, KAMANN)
        self.persisted(the_vote)
        self.assertEqual(self.rows(
            """SELECT m.display_name, p.name, l.name, vm.vote FROM vote_members vm
               JOIN mps m ON m.id = vm.mp_id JOIN parties p ON p.id = vm.party_id LEFT JOIN parties l ON l.id = vm.listed_party_id
               ORDER BY m.display_name"""),
            [("Kamann, Uwe", "AfD", "fraktionslos", "yes"), ("Müller, Max", "fraktionslos", None, "no")])
        self.assertEqual(self.rows(
            """SELECT p.name, yes_count, no_count, total_count, leading_vote FROM vote_fractions vf
               JOIN parties p ON p.id = vf.party_id ORDER BY vf.rank"""),
            [("AfD", 1, 1, 2, None), ("fraktionslos", 0, 1, 1, "no")])

    # Value: protects=the person record keeps the page's group: the identity registry reads mps.party_id as name-and-party
    #   evidence, so a correction of one vote must not move or split a person; fails_when=upsert_mp gets the corrected
    #   group; why_new=the first replay moved Heßenkemper's page and split Pasemann's Reden from his Stimmen; seam=persist_vote
    def test_the_person_record_keeps_the_pages_group(self) -> None:
        the_vote = vote(member("Kamann, Uwe", "fraktionslos", "yes"), fractions=[fraction("AfD", no=1), fraction("fraktionslos", yes=1)])
        filed(the_vote, KAMANN)
        self.persisted(the_vote)
        self.assertEqual(self.rows("SELECT p.name FROM mps m JOIN parties p ON p.id = m.party_id"), [("fraktionslos",)])

    # Value: protects=the page's own totals stay available from the store: the documented formula gives back each
    #   group's printed count; fails_when=listed_party_id is not kept or the moved Stimme is lost; why_new=E4 "done
    #   when the page's totals stay available as the source's own figures"; seam=none
    def test_the_pages_totals_can_be_read_back(self) -> None:
        the_vote = vote(member("Kamann, Uwe", "fraktionslos", "yes"), fractions=[fraction("AfD", no=1), fraction("fraktionslos", yes=1, no=1)])
        filed(the_vote, KAMANN)
        self.persisted(the_vote)
        self.assertEqual(self.rows(
            """SELECT p.name, vf.yes_count
                 - (SELECT COUNT(*) FROM vote_members vm WHERE vm.vote_id = vf.vote_id AND vm.party_id = vf.party_id
                    AND vm.listed_party_id IS NOT NULL AND vm.vote = 'yes')
                 + (SELECT COUNT(*) FROM vote_members vm WHERE vm.vote_id = vf.vote_id AND vm.listed_party_id = vf.party_id
                    AND vm.vote = 'yes')
               FROM vote_fractions vf JOIN parties p ON p.id = vf.party_id ORDER BY vf.rank"""),
            [("AfD", 0), ("fraktionslos", 1)])

    # Value: protects=folding a duplicate parties row moves the page's group too, so no row is lost to ON DELETE SET
    #   NULL; fails_when=_repoint_party forgets the new column (checklist class 6); why_new=second reference to parties; seam=none
    def test_folding_a_party_keeps_the_pages_group(self) -> None:
        the_vote = vote(member("Kamann, Uwe", "fraktionslos"), fractions=[fraction("AfD", no=1), fraction("fraktionslos", no=1)])
        filed(the_vote, KAMANN)
        self.persisted(the_vote)
        old = self.conn.execute("SELECT id FROM parties WHERE name = 'fraktionslos'").fetchone()[0]
        new = pulse_store.upsert_party(self.conn, "SPD", NOW)
        pulse_store._repoint_party(self.conn, old, new)
        self.assertEqual(self.rows("SELECT listed_party_id FROM vote_members"), [(new,)])


class PanelTests(unittest.TestCase):
    # Value: protects=the dossier panel shows the same groups as the store, Kamann under the AfD, and says where it
    #   differs from the linked Bundestag page; fails_when=the panel reads the page's fields, or a reader checking the
    #   source finds an unexplained difference; why_new=the panel renders from the report; seam=vote_summary
    # Value (extension): protects=the panel's group rows are the filed ones: the AfD row gains the Ja, an emptied group
    #   has no row; fails_when=render_vote_summary builds rows with merge_fractions; why_new=the member grid was
    #   asserted, the tally rows never; seam=vote_summary
    def test_the_panel_shows_the_filed_groups_and_names_the_difference(self) -> None:
        the_vote = vote(member("Kamann, Uwe", "fraktionslos", "yes"), member("Müller, Max", "fraktionslos", "no"),
                        fractions=[fraction("AfD", no=1), fraction("fraktionslos", yes=1, no=1)])
        filed(the_vote, KAMANN)
        rendered = vote_summary({"index": 1, "votes": [the_vote]}, {"acquisition_state": "complete"})
        self.assertIn("Kamann, Uwe</strong>", rendered.split("<h4>AfD</h4>")[1].split("</section>")[0])
        self.assertNotIn("Kamann, Uwe", rendered.split("<h4>fraktionslos</h4>")[1])
        self.assertIn("Kamann, Uwe bei AfD (dort fraktionslos)", rendered)
        self.assertIn("MdB-Stammdaten", rendered)
        # The group rows are the filed ones too: the AfD gains his Ja, and fraktionslos, left with nobody, has no row.
        sole = vote(member("Kamann, Uwe", "fraktionslos", "yes"), member("Müller, Max", "AfD", "no"),
                    fractions=[fraction("AfD", no=1), fraction("fraktionslos", yes=1)])
        filed(sole, KAMANN)
        rows = vote_summary({"index": 1, "votes": [sole]}, {"acquisition_state": "complete"}).split('<div class="vote-fractions">')[1].split('<p class="vote-state-note">')[0]
        self.assertIn("<strong>AfD</strong>", rows)
        self.assertIn('title="ja: 1"', rows)
        self.assertNotIn("<strong>fraktionslos</strong>", rows)

    # Value: protects=a vote with nothing moved has no such line; fails_when=the note renders unconditionally;
    #   why_new=the note is new; seam=vote_summary
    def test_no_note_without_a_move(self) -> None:
        the_vote = vote(member("Müller, Max", "fraktionslos", "no"), fractions=[fraction("fraktionslos", no=1)])
        rendered = vote_summary({"index": 1, "votes": [the_vote]}, {"acquisition_state": "complete"})
        self.assertNotIn("MdB-Stammdaten", rendered)


class CachedStammdatenTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.database = Path(self._tmp.name) / "data" / "s.sqlite"

    def records(self) -> stammdaten.Stammdaten:
        kamann = {"ID": "11004700", "NAMEN": [{"VORNAME": "Uwe", "NACHNAME": "Kamann", "HISTORIE_VON": "24.10.2017"}],
                  "WAHLPERIODEN": [{"WP": "19", "MDBWP_VON": "24.10.2017", "MDBWP_BIS": "26.10.2021", "INSTITUTIONEN": [
                      {"INSART_LANG": "Fraktion/Gruppe", "INS_LANG": "Fraktion Alternative für Deutschland",
                       "MDBINS_VON": "24.10.2017", "MDBINS_BIS": "02.01.2019"}]}]}
        return stammdaten.Stammdaten(records=[kamann], stand=STAND, sha256="ab" * 32)

    def entry(self) -> dict:
        return {"report": {"protocol": {"dokumentnummer": "19/30"}, "agenda_items": [{"votes": [
            vote(member("Kamann, Uwe", "fraktionslos"), fractions=[fraction("AfD", no=1), fraction("fraktionslos", no=1)])]}]}}

    # Value: protects=the build's one entry point reads the private cache and marks the entries; no file clears
    #   marks an old cached report still carries; fails_when=it reads the store's tables (empty before the rebuild's
    #   seat step) or leaves a stale mark; why_new=E4 runs on every rebuild and render; seam=refile_entry_votes
    #   with read_cached_stammdaten patched
    def test_entries_follow_the_cached_file(self) -> None:
        entry = self.entry()
        with mock.patch.object(build, "read_cached_stammdaten", return_value=self.records()):
            build.refile_entry_votes([entry], self.database)
        members = entry["report"]["agenda_items"][0]["votes"][0]["members"]
        self.assertEqual(members[0]["refiled_to"], "AfD")
        with mock.patch.object(build, "read_cached_stammdaten", return_value=None):
            build.refile_entry_votes([entry], self.database)
        self.assertNotIn("refiled_to", members[0])

    @staticmethod
    def filed_from(records: list[dict], the_vote: dict) -> list[tuple[str, str]]:
        derive.refile_vote_members(the_vote, 19, derive.stammdaten_refiling_source(records, STAND, since_wahlperiode=18))
        return [(m["name"], m["refiled_to"]) for m in the_vote["members"] if "refiled_to" in m]

    @staticmethod
    def mdb(institutionen: list[dict], *, von: str = "24.10.2017") -> dict:
        return {"ID": "11009990", "NAMEN": [{"VORNAME": "Ada", "NACHNAME": "Muster", "HISTORIE_VON": von}],
                "WAHLPERIODEN": [{"WP": "19", "MDBWP_VON": von, "MDBWP_BIS": "26.10.2021", "INSTITUTIONEN": institutionen}]}

    @staticmethod
    def record(ins_lang: str, von: str, bis: str | None = None) -> dict:
        return {"INSART_LANG": "Fraktion/Gruppe", "INS_LANG": ins_lang, "MDBINS_VON": von, "MDBINS_BIS": bis}

    # Value: protects=a Mandat the file lists before any Fraktion or Gruppe record is no proof of fraktionslos: the
    #   page's SPD row stands (TODOS E4 deferred item 2); fails_when=_proved_group treats an uncovered Mandat
    #   stretch with no record in the Wahlperiode as fraktionslos; why_new=a refreshed file can enter a Mandat before
    #   its Fraktion; seam=stammdaten_refiling_source
    # Value (extension): protects=the same holds for the days before an MdB's first record when the record comes in
    #   later (Mandat from 24.10.2017, SPD entered from 01.12.2017); fails_when=only a Wahlperiode with no record at
    #   all is guarded; why_new=a late entry is the same lag
    def test_a_mandat_with_no_record_yet_is_no_proof_of_fraktionslos(self) -> None:
        spd = "Fraktion der Sozialdemokratischen Partei Deutschlands"
        page = lambda day: vote(member("Muster, Ada", "SPD"), fractions=[fraction("SPD", no=1)], day=day)  # noqa: E731
        self.assertEqual(self.filed_from([self.mdb([])], page("2018-06-01")), [])
        self.assertEqual(self.filed_from([self.mdb([self.record(spd, "01.12.2017")])], page("2017-11-21")), [])
        # The record proves SPD from its first day on.
        page_fraktionslos = vote(member("Muster, Ada", "fraktionslos"), fractions=[fraction("fraktionslos", no=1)], day="2018-06-01")
        self.assertEqual(self.filed_from([self.mdb([self.record(spd, "01.12.2017")])], page_fraktionslos), [("Muster, Ada", "SPD")])

    # Value: protects=fraktionslos stays provable from an explicit Fraktionslos record (Petry, Mieruch from the
    #   Mandat's first day), but the days after a Fraktion record ends with no record after it prove nothing: the
    #   file may not have entered the next one yet (TODOS E4 deferred item 9, tail); fails_when=the guard drops every
    #   fraktionslos row, or a rule-3 tail moves a page's AfD row; why_new=rule 2 of the window decision;
    #   seam=stammdaten_refiling_source
    def test_a_fraktionslos_record_proves_fraktionslos_and_an_uncovered_tail_does_not(self) -> None:
        afd = lambda day: vote(member("Muster, Ada", "AfD"), fractions=[fraction("AfD", no=1)], day=day)  # noqa: E731
        self.assertEqual(self.filed_from([self.mdb([self.record("Fraktionslos", "24.10.2017")])], afd("2018-06-01")),
                         [("Muster, Ada", "fraktionslos")])
        left = [self.record("Fraktion Alternative für Deutschland", "24.10.2017", "02.01.2019")]
        self.assertEqual(self.filed_from([self.mdb(left)], afd("2019-06-01")), [])
        # The record itself still proves its own days.
        fraktionslos = vote(member("Muster, Ada", "fraktionslos"), fractions=[fraction("fraktionslos", no=1)], day="2018-06-01")
        self.assertEqual(self.filed_from([self.mdb(left)], fraktionslos), [("Muster, Ada", "AfD")])

    # Value: protects=a gap between two records (A ends 31.03.2019, B starts 01.05.2019) proves nothing for its days,
    #   while both records prove theirs, and the same gap entered as Fraktionslos does prove fraktionslos (TODOS E4
    #   deferred item 9, gap); fails_when=a rule-3 gap day moves a page row, or the guard reaches the records around
    #   it; why_new=rule 2 of the window decision; seam=stammdaten_refiling_source
    def test_a_gap_between_two_records_proves_nothing_for_its_days(self) -> None:
        afd, spd = "Fraktion Alternative für Deutschland", "Fraktion der Sozialdemokratischen Partei Deutschlands"
        page = lambda group, day: vote(member("Muster, Ada", group), fractions=[fraction(group, no=1)], day=day)  # noqa: E731
        gap = [self.record(afd, "24.10.2017", "31.03.2019"), self.record(spd, "01.05.2019")]
        self.assertEqual(self.filed_from([self.mdb(gap)], page("SPD", "2019-04-15")), [])
        self.assertEqual(self.filed_from([self.mdb(gap)], page("AfD", "2019-06-01")), [("Muster, Ada", "SPD")])
        entered = [*gap, self.record("Fraktionslos", "01.04.2019", "30.04.2019")]
        self.assertEqual(self.filed_from([self.mdb(entered)], page("SPD", "2019-04-15")), [("Muster, Ada", "fraktionslos")])

    # Value: protects=the lead-in of a second Mandat in the Wahlperiode, before its record, proves nothing, and the
    #   record proves its days (TODOS E4 deferred item 9, re-entry); fails_when=the guard is keyed to the first record
    #   of the Wahlperiode, which the first Mandat already passed; why_new=rule 2 of the window decision;
    #   seam=stammdaten_refiling_source
    def test_a_re_entry_mandat_before_its_record_proves_nothing(self) -> None:
        spd = "Fraktion der Sozialdemokratischen Partei Deutschlands"
        mdb = self.mdb([])
        mdb["WAHLPERIODEN"] = [
            {"WP": "19", "MDBWP_VON": "24.10.2017", "MDBWP_BIS": "31.12.2019", "INSTITUTIONEN": [self.record(spd, "24.10.2017", "31.12.2019")]},
            {"WP": "19", "MDBWP_VON": "01.06.2020", "MDBWP_BIS": "26.10.2021", "INSTITUTIONEN": [self.record(spd, "01.09.2020")]},
        ]
        page = lambda group, day: vote(member("Muster, Ada", group), fractions=[fraction(group, no=1)], day=day)  # noqa: E731
        self.assertEqual(self.filed_from([mdb], page("SPD", "2020-07-01")), [])
        self.assertEqual(self.filed_from([mdb], page("fraktionslos", "2020-10-01")), [("Muster, Ada", "SPD")])

    # Value: protects=the day an explicit Fraktionslos record takes over from rule-3 days is a change day and proves
    #   nothing, though the seat rows merge the two into one fraktionslos row that hides the boundary; the day after
    #   proves fraktionslos; fails_when=_proved_group reads only the merged seat rows; why_new=Codex plan review
    #   finding 6; seam=stammdaten_refiling_source
    def test_the_day_a_record_takes_over_from_uncovered_days_proves_nothing(self) -> None:
        records = [self.record("Fraktion Alternative für Deutschland", "24.10.2017", "31.12.2018"), self.record("Fraktionslos", "01.02.2019")]
        afd = lambda day: vote(member("Muster, Ada", "AfD"), fractions=[fraction("AfD", no=1)], day=day)  # noqa: E731
        self.assertEqual(self.filed_from([self.mdb(records)], afd("2019-01-15")), [])
        self.assertEqual(self.filed_from([self.mdb(records)], afd("2019-02-01")), [])
        self.assertEqual(self.filed_from([self.mdb(records)], afd("2019-02-02")), [("Muster, Ada", "fraktionslos")])

    # Value: protects=the seat rows do not change with the refiling guard: rule-3 days still count as fraktionslos
    #   seats and merge with an adjacent Fraktionslos record; fails_when=the evidence split leaks into
    #   mdb_zugehoerigkeiten or party_seats; why_new=_mandate_stretches now tags its stretches; seam=mdb_zugehoerigkeiten
    def test_the_seat_rows_are_unchanged_by_the_guard(self) -> None:
        afd, spd = "Fraktion Alternative für Deutschland", "Fraktion der Sozialdemokratischen Partei Deutschlands"
        spans = lambda records: [(r["party"], r["valid_from"], r["valid_until"])  # noqa: E731
                                 for r in derive.mdb_zugehoerigkeiten([self.mdb(records)], since_wahlperiode=18)]
        self.assertEqual(spans([self.record(afd, "24.10.2017", "31.03.2019"), self.record(spd, "01.05.2019")]), [
            ("AfD", "2017-10-24", "2019-04-01"), ("fraktionslos", "2019-04-01", "2019-05-01"), ("SPD", "2019-05-01", "2021-10-27")])
        self.assertEqual(spans([self.record(afd, "24.10.2017", "31.12.2018"), self.record("Fraktionslos", "01.02.2019")]), [
            ("AfD", "2017-10-24", "2019-01-01"), ("fraktionslos", "2019-01-01", "2021-10-27")])
        self.assertEqual(spans([self.record(afd, "24.10.2017", "02.01.2019")]), [
            ("AfD", "2017-10-24", "2019-01-03"), ("fraktionslos", "2019-01-03", "2021-10-27")])
        self.assertEqual(derive.party_seats(derive.mdb_zugehoerigkeiten([self.mdb([])], since_wahlperiode=18)), [
            {"party": "fraktionslos", "wahlperiode": 19, "valid_from": "2017-10-24", "valid_until": "2021-10-27", "seats": 1}])

    # Value: protects=an MdB with two Mandate in one Wahlperiode (left and came back) keeps the proof of the first
    #   one: a page row on a day of the first Mandat is still re-filed, in either element order; fails_when=
    #   the later Mandat's lead-in or record hides the earlier Mandat's days; why_new=Codex reproduced it in the ship review; seam=refile_entry_votes
    def test_a_second_mandat_in_the_wahlperiode_keeps_the_first_mandats_proof(self) -> None:
        spd = "Fraktion der Sozialdemokratischen Partei Deutschlands"
        first = {"WP": "19", "MDBWP_VON": "24.10.2017", "MDBWP_BIS": "31.12.2019",
                 "INSTITUTIONEN": [self.record(spd, "24.10.2017", "31.12.2019")]}
        second = {"WP": "19", "MDBWP_VON": "01.06.2020", "MDBWP_BIS": "26.10.2021",
                  "INSTITUTIONEN": [self.record(spd, "01.06.2020")]}
        for periods in ([first, second], [second, first]):
            mdb = self.mdb([])
            mdb["WAHLPERIODEN"] = periods
            page = vote(member("Muster, Ada", "fraktionslos"), fractions=[fraction("fraktionslos", no=1)], day="2018-06-01")
            self.assertEqual(self.filed_from([mdb], page), [("Muster, Ada", "SPD")])

    # Value: protects=an unreadable cached file stops a rebuild as DatabaseRebuildError with the store untouched,
    #   as the seat step does; fails_when=StammdatenError escapes the CLI's handler; why_new=this read comes before the
    #   seat step's; seam=refile_entry_votes
    def test_an_unreadable_file_is_a_rebuild_error(self) -> None:
        with mock.patch.object(build, "read_cached_stammdaten", side_effect=derive.StammdatenError("kaputt")):
            with self.assertRaises(build.DatabaseRebuildError):
                build.refile_entry_votes([self.entry()], self.database)

    # Value: protects=a rebuild from cached reports files the Stimmen from the cached Stammdaten into the store, a vote
    #   whose counts cannot absorb the move stays as the page has it, and stderr names it; fails_when=the rebuild
    #   skips refile_entry_votes, or drops the refused warning; why_new=only refile_entry_votes was called directly;
    #   seam=rebuild_database_from_entries, read_cached_stammdaten patched and seat counts skipped (one MdB, no legal size)
    def test_a_rebuild_files_the_votes_and_names_a_refused_one(self) -> None:
        good = vote(member("Kamann, Uwe", "fraktionslos", "yes"), member("Müller, Max", "AfD", "no"),
                    fractions=[fraction("AfD", no=1), fraction("fraktionslos", yes=1)], vote_id="501")
        refused = vote(member("Kamann, Uwe", "fraktionslos", "no"), fractions=[fraction("AfD", no=1), fraction("fraktionslos", yes=1)],
                       vote_id="502")
        report = {"validation_summary": {"speech_kinds_version": pulse_store.speech_kinds.VERSION},
                  "protocol": {"id": "p19-30", "dokumentnummer": "19/30", "datum": "2018-06-01"},
                  "agenda_items": [{"index": 1, "heading": "Test", "votes": [good, refused]}]}
        entries = [{"report": report, "report_path": Path(self._tmp.name) / "plenarprotokoll-19-30.json"}]
        self.database.parent.mkdir(parents=True)
        err = io.StringIO()
        with mock.patch.object(build, "read_cached_stammdaten", return_value=self.records()), \
                mock.patch.object(build, "rebuild_seat_counts"), contextlib.redirect_stderr(err):
            build.rebuild_database_from_entries(self.database, entries, preserve_roster=False)
        conn = sqlite3.connect(self.database)
        self.addCleanup(conn.close)
        self.assertEqual(
            conn.execute("""SELECT substr(v.detail_url, -3), p.name, l.name FROM vote_members vm JOIN votes v ON v.id = vm.vote_id
                            JOIN mps m ON m.id = vm.mp_id JOIN parties p ON p.id = vm.party_id
                            LEFT JOIN parties l ON l.id = vm.listed_party_id
                            WHERE m.display_name = 'Kamann, Uwe' ORDER BY 1""").fetchall(),
            [("501", "AfD", "fraktionslos"), ("502", "fraktionslos", None)])
        self.assertIn("refile: 1 Stimmen in 1 Abstimmungen", err.getvalue())
        self.assertRegex(err.getvalue(), r"warning: \[refile\] the fraction rows of 1 votes cannot absorb the moves.*502")


class StoreSchemaTests(unittest.TestCase):
    # Value: protects=a store from before the column is refused with the upgrade instruction rather than read;
    #   fails_when=require_current_schema does not look for it; why_new=schema 11; seam=require_current_schema
    def test_a_store_without_the_column_is_old(self) -> None:
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute("CREATE TABLE vote_members (vote_id TEXT, mp_id TEXT, party_id TEXT, vote TEXT)")
        with self.assertRaisesRegex(RuntimeError, "Old build-store schema"):
            pulse_store.require_current_schema(conn)


if __name__ == "__main__":
    unittest.main()
