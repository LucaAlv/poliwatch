"""Zugehörigkeit stretches and seat counts derived from the MdB-Stammdaten
(C1 step 2, docs/plans/c1-seat-counts.md "Interval rules")."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import derive
import stammdaten

CDU = "Fraktion der Christlich Demokratischen Union/Christlich - Sozialen Union"
AFD = "Fraktion Alternative für Deutschland"


def name(vorname: str, nachname: str, von: str = "", bis: str = "", **parts: str) -> dict[str, str]:
    return {
        "NACHNAME": nachname, "VORNAME": vorname, "ORTSZUSATZ": parts.get("ortszusatz", ""),
        "ADEL": parts.get("adel", ""), "PRAEFIX": parts.get("praefix", ""), "ANREDE_TITEL": "",
        "AKAD_TITEL": "", "HISTORIE_VON": von, "HISTORIE_BIS": bis,
    }


def institution(ins_lang: str, von: str, bis: str = "", art: str = "Fraktion/Gruppe", funktion: str = "") -> dict[str, str]:
    return {"INSART_LANG": art, "INS_LANG": ins_lang, "MDBINS_VON": von, "MDBINS_BIS": bis, "FKT_LANG": funktion}


def wahlperiode(wp: int, von: str, bis: str = "", *institutions: dict[str, str], land: str = "NW") -> dict[str, object]:
    return {"WP": str(wp), "MDBWP_VON": von, "MDBWP_BIS": bis, "WKR_LAND": land, "INSTITUTIONEN": list(institutions)}


def mdb(mdb_id: str, *wahlperioden: dict[str, object], names: list[dict[str, str]] | None = None) -> dict[str, object]:
    return {"ID": mdb_id, "NAMEN": names or [name("Ada", "Muster", "01.01.1990")], "WAHLPERIODEN": list(wahlperioden)}


def row(party: str, valid_from: str, valid_until: str | None, wp: int = 21, mdb_id: str = "11000001", display: str = "Ada Muster") -> dict[str, object]:
    return {"mdb_id": mdb_id, "name": display, "wahlperiode": wp, "party": party, "valid_from": valid_from, "valid_until": valid_until}


def stretches(*mdbs: dict[str, object], since: int = 18) -> list[dict[str, object]]:
    return derive.mdb_zugehoerigkeiten(list(mdbs), since_wahlperiode=since)


class ZugehoerigkeitTests(unittest.TestCase):
    def test_an_open_membership_in_an_open_mandate_stays_open(self) -> None:
        self.assertEqual(
            stretches(mdb("11000001", wahlperiode(21, "25.03.2025", "", institution(CDU, "25.03.2025")))),
            [row("CDU/CSU", "2025-03-25", None)],
        )

    def test_one_row_per_fraktion_function_is_one_membership(self) -> None:
        mandate = wahlperiode(
            21, "25.03.2025", "",
            institution(CDU, "25.03.2025", funktion="Vorsitzende"),
            institution(CDU, "25.03.2025", funktion="Mitglied"),
        )
        self.assertEqual(stretches(mdb("11000001", mandate)), [row("CDU/CSU", "2025-03-25", None)])

    def test_a_leaver_is_counted_through_the_last_day_of_the_membership(self) -> None:
        mandate = wahlperiode(18, "22.10.2013", "03.06.2016", institution(CDU, "22.10.2013", "03.06.2016"))
        self.assertEqual(stretches(mdb("11000001", mandate)), [row("CDU/CSU", "2013-10-22", "2016-06-04", wp=18)])

    def test_the_handover_day_belongs_to_the_new_group(self) -> None:
        # Nüßlein: CDU/CSU until 07.03.2021, Fraktionslos from 07.03.2021.
        mandate = wahlperiode(
            19, "24.10.2017", "26.10.2021",
            institution(CDU, "24.10.2017", "07.03.2021"),
            institution("Fraktionslos", "07.03.2021", "26.10.2021"),
        )
        self.assertEqual(stretches(mdb("11000001", mandate)), [
            row("CDU/CSU", "2017-10-24", "2021-03-07", wp=19),
            row("fraktionslos", "2021-03-07", "2021-10-27", wp=19),
        ])

    def test_a_membership_dated_before_the_mandate_starts_with_the_mandate(self) -> None:
        # A successor whose membership the Stammdaten dates from the Fraktion's founding.
        mandate = wahlperiode(19, "15.03.2019", "26.10.2021", institution(AFD, "24.10.2017", "26.10.2021"))
        self.assertEqual(stretches(mdb("11000001", mandate)), [row("AfD", "2019-03-15", "2021-10-27", wp=19)])

    def test_an_open_membership_ends_with_its_mandate(self) -> None:
        mandate = wahlperiode(18, "22.10.2013", "24.10.2017", institution(CDU, "22.10.2013"))
        self.assertEqual(stretches(mdb("11000001", mandate)), [row("CDU/CSU", "2013-10-22", "2017-10-25", wp=18)])

    def test_mandate_days_no_membership_covers_are_fraktionslos(self) -> None:
        mandate = wahlperiode(
            19, "24.10.2017", "26.10.2021",
            institution(AFD, "01.11.2017", "31.12.2019"),
            institution(AFD, "01.03.2020", "26.10.2021"),
        )
        self.assertEqual(stretches(mdb("11000001", mandate)), [
            row("fraktionslos", "2017-10-24", "2017-11-01", wp=19),
            row("AfD", "2017-11-01", "2020-01-01", wp=19),
            row("fraktionslos", "2020-01-01", "2020-03-01", wp=19),
            row("AfD", "2020-03-01", "2021-10-27", wp=19),
        ])

    def test_a_rejoin_after_an_unbroken_fraktionslos_stretch(self) -> None:
        # Heßenkemper-shaped: out of the AfD, fraktionslos (first undated, then
        # recorded), back in the AfD on 24.08.2021. The fraktionslos days are
        # one unbroken stretch, so one row.
        mandate = wahlperiode(
            19, "24.10.2017", "26.10.2021",
            institution(AFD, "24.10.2017", "15.05.2021"),
            institution("Fraktionslos", "20.05.2021", "24.08.2021"),
            institution(AFD, "24.08.2021", "26.10.2021"),
        )
        self.assertEqual(stretches(mdb("11000001", mandate)), [
            row("AfD", "2017-10-24", "2021-05-16", wp=19),
            row("fraktionslos", "2021-05-16", "2021-08-24", wp=19),
            row("AfD", "2021-08-24", "2021-10-27", wp=19),
        ])

    def test_two_memberships_on_the_same_day_fail_by_name(self) -> None:
        mandate = wahlperiode(
            19, "24.10.2017", "26.10.2021",
            institution(AFD, "24.10.2017", "30.06.2021"),
            institution("Fraktionslos", "01.06.2021", "26.10.2021"),
        )
        with self.assertRaises(derive.StammdatenError) as raised:
            stretches(mdb("11000042", mandate))
        message = str(raised.exception)
        for part in ("11000042", "WP 19", AFD, "Fraktionslos", "01.06.2021"):
            self.assertIn(part, message)

    def test_an_open_membership_followed_by_another_is_an_overlap(self) -> None:
        mandate = wahlperiode(21, "25.03.2025", "", institution(AFD, "25.03.2025"), institution("Fraktionslos", "01.06.2025"))
        with self.assertRaises(derive.StammdatenError):
            stretches(mdb("11000042", mandate))

    # Value: protects=every Zusammenschluss the closed Stammdaten map names is spelled as derive.zusammenschluss
    #   spells it for speeches and roll-call totals, so seat rows land on the parties row the other tables use
    #   (R2 joins the seat share to the speech share by that name); fails_when=a map value is a variant spelling
    #   ("DIE LINKE", "Bündnis 90/Die Grünen") that zusammenschluss rewrites, which would leave the group's
    #   sitzanteil_prozent empty and its cross-check rows unmatched; why_new=no test ties the map values to the
    #   spelling table, the map tests use CDU only; seam=none; no_claim=the spellings the live sources use
    def test_every_mapped_group_is_spelled_as_the_other_tables_spell_it(self) -> None:
        for fraktion, group in derive.STAMMDATEN_ZUSAMMENSCHLUESSE.items():
            with self.subTest(fraktion):
                self.assertEqual(derive.zusammenschluss(group), group)

    def test_a_group_name_outside_the_closed_map_fails_by_name(self) -> None:
        mandate = wahlperiode(22, "20.10.2029", "", institution("Fraktion Neue Partei", "20.10.2029"))
        with self.assertRaises(derive.StammdatenError) as raised:
            stretches(mdb("11000042", mandate))
        for part in ("11000042", "WP 22", "Fraktion Neue Partei"):
            self.assertIn(part, str(raised.exception))

    def test_a_malformed_date_fails_by_name(self) -> None:
        mandate = wahlperiode(21, "2025-03-25", "", institution(CDU, "25.03.2025"))
        with self.assertRaises(derive.StammdatenError) as raised:
            stretches(mdb("11000042", mandate))
        for part in ("11000042", "2025-03-25"):
            self.assertIn(part, str(raised.exception))

    def test_an_undated_membership_or_mandate_fails_by_name(self) -> None:
        for mandate in (
            wahlperiode(21, "25.03.2025", "", institution(CDU, "")),
            wahlperiode(21, "", "", institution(CDU, "25.03.2025")),
        ):
            with self.subTest(mandate=mandate), self.assertRaises(derive.StammdatenError) as raised:
                stretches(mdb("11000042", mandate))
            self.assertIn("11000042", str(raised.exception))

    def test_institutions_other_than_fraktion_or_gruppe_are_not_memberships(self) -> None:
        mandate = wahlperiode(
            21, "25.03.2025", "",
            institution(CDU, "25.03.2025"),
            institution("Ausschuss für Arbeit und Soziales", "15.05.2025", art="Ausschuss"),
        )
        self.assertEqual(stretches(mdb("11000001", mandate)), [row("CDU/CSU", "2025-03-25", None)])

    def test_wahlperioden_before_the_first_one_are_left_out_unread(self) -> None:
        # A WP 17 name outside the closed map must not fail a v1 build.
        record = mdb(
            "11000001",
            wahlperiode(17, "27.10.2009", "22.10.2013", institution("Fraktion der CDU/CSU", "27.10.2009")),
            wahlperiode(18, "22.10.2013", "24.10.2017", institution(CDU, "22.10.2013")),
        )
        self.assertEqual(stretches(record, since=18), [row("CDU/CSU", "2013-10-22", "2017-10-25", wp=18)])

    def test_each_stretch_carries_the_name_valid_on_its_first_day(self) -> None:
        names = [name("Eva-Maria", "Bulling", "10.11.1994", "31.12.2018"), name("Eva", "Bulling-Schröter", "01.01.2019")]
        mandate = wahlperiode(
            19, "24.10.2017", "26.10.2021",
            institution(AFD, "24.10.2017", "31.05.2019"),
            institution("Fraktionslos", "01.06.2019", "26.10.2021"),
        )
        self.assertEqual(stretches(mdb("11000001", mandate, names=names)), [
            row("AfD", "2017-10-24", "2019-06-01", wp=19, display="Eva-Maria Bulling"),
            row("fraktionslos", "2019-06-01", "2021-10-27", wp=19, display="Eva Bulling-Schröter"),
        ])

    def test_the_name_joins_its_parts_and_falls_back_to_the_earliest(self) -> None:
        # The name history starts after the Mandat: no name covers its first day.
        names = [name("Dirk", "Fischer", "01.01.2014", adel="Freiherr", praefix="von", ortszusatz="(Hamburg)")]
        mandate = wahlperiode(18, "22.10.2013", "24.10.2017", institution(CDU, "22.10.2013"))
        self.assertEqual(
            stretches(mdb("11000001", mandate, names=names)),
            [row("CDU/CSU", "2013-10-22", "2017-10-25", wp=18, display="Dirk Freiherr von Fischer (Hamburg)")],
        )

    # Value: protects=a membership that covers no day of its Mandat is refused by name, so the file never
    #   reaches party_seats as valid_until < valid_from (seats=-1, which check_seat_totals cannot see);
    #   fails_when=Rule 2 clips only the endpoints again and an inverted stretch passes; why_new=TODOS C1
    #   deferred item 9; seam=derive.mdb_zugehoerigkeiten; no_claim=the live file (it has no such membership)
    def test_a_membership_wholly_outside_its_mandate_is_refused_by_name(self) -> None:
        for label, mandate in {
            "before the Mandat": wahlperiode(19, "15.03.2019", "26.10.2021", institution(AFD, "24.10.2017", "01.03.2019")),
            "after the Mandat": wahlperiode(19, "24.10.2017", "01.03.2019", institution(AFD, "15.03.2019", "26.10.2021")),
            "open-ended, after the Mandat": wahlperiode(19, "24.10.2017", "01.03.2019", institution(AFD, "15.03.2019")),
        }.items():
            with self.subTest(label), self.assertRaises(derive.StammdatenError) as raised:
                stretches(mdb("11000042", mandate))
            for part in ("11000042", "WP 19", AFD):
                self.assertIn(part, str(raised.exception))

    # Value: protects=a one-day membership on a handover day (MDBINS_VON == MDBINS_BIS, the next membership
    #   starting that day) gives one outcome whatever the hash seed: a refusal naming the zero-length
    #   membership, where the unsorted ties gave a zero-length row under some seeds and "two memberships on
    #   the same day" under others; fails_when=the stretches are built in set order again, or a zero-length
    #   stretch is dropped or emitted; why_new=TODOS C1 deferred item 9; seam=derive.mdb_zugehoerigkeiten in
    #   a subprocess per PYTHONHASHSEED; no_claim=the live file (it has no such membership)
    def test_a_one_day_membership_on_a_handover_day_is_refused_the_same_under_every_hash_seed(self) -> None:
        script = (
            "import sys; sys.path.insert(0, sys.argv[1])\n"
            "import derive\n"
            "def inst(name, von, bis):\n"
            "    return {'INSART_LANG': 'Fraktion/Gruppe', 'INS_LANG': name, 'MDBINS_VON': von, 'MDBINS_BIS': bis}\n"
            "mdb = {'ID': '11000042', 'NAMEN': [], 'WAHLPERIODEN': [{'WP': '19', 'MDBWP_VON': '24.10.2017', "
            "'MDBWP_BIS': '26.10.2021', 'INSTITUTIONEN': [\n"
            f"    inst({CDU!r}, '24.10.2017', '07.03.2021'), inst({AFD!r}, '07.03.2021', '07.03.2021'), "
            "inst('Fraktionslos', '07.03.2021', '26.10.2021')]}]}\n"
            "try:\n"
            "    print(derive.mdb_zugehoerigkeiten([mdb], since_wahlperiode=18))\n"
            "except derive.StammdatenError as exc:\n"
            "    print('refused:', exc)\n"
        )
        outcomes = set()
        for seed in range(6):
            result = subprocess.run(
                [sys.executable, "-c", script, str(Path(derive.__file__).parent)],
                env={**os.environ, "PYTHONHASHSEED": str(seed)}, capture_output=True, text=True, check=True,
            )
            outcomes.add(result.stdout)
        self.assertEqual(len(outcomes), 1, outcomes)
        [outcome] = outcomes
        self.assertTrue(outcome.startswith("refused: "), outcome)
        for part in ("11000042", "WP 19", AFD, "07.03.2021"):
            self.assertIn(part, outcome)



def seat(party: str, valid_from: str, valid_until: str | None, seats: int, wp: int = 21) -> dict[str, object]:
    return {"party": party, "wahlperiode": wp, "valid_from": valid_from, "valid_until": valid_until, "seats": seats}


def seats_of(*mdbs: dict[str, object]) -> list[dict[str, object]]:
    return derive.party_seats(stretches(*mdbs))


class PartySeatsTests(unittest.TestCase):
    def test_members_of_one_group_on_the_same_days_are_one_row(self) -> None:
        self.assertEqual(
            seats_of(
                mdb("11000001", wahlperiode(21, "25.03.2025", "", institution(CDU, "25.03.2025"))),
                mdb("11000002", wahlperiode(21, "25.03.2025", "", institution(CDU, "25.03.2025"))),
                mdb("11000003", wahlperiode(21, "25.03.2025", "", institution(AFD, "25.03.2025"))),
            ),
            [seat("AfD", "2025-03-25", None, 1), seat("CDU/CSU", "2025-03-25", None, 2)],
        )

    def test_a_vacancy_lowers_the_count_until_the_successor_starts(self) -> None:
        self.assertEqual(
            seats_of(
                mdb("11000001", wahlperiode(18, "22.10.2013", "24.10.2017", institution(CDU, "22.10.2013"))),
                mdb("11000002", wahlperiode(18, "22.10.2013", "03.06.2016", institution(CDU, "22.10.2013"))),
                mdb("11000003", wahlperiode(18, "10.06.2016", "24.10.2017", institution(CDU, "10.06.2016"))),
            ),
            [
                seat("CDU/CSU", "2013-10-22", "2016-06-04", 2, wp=18),
                seat("CDU/CSU", "2016-06-04", "2016-06-10", 1, wp=18),
                seat("CDU/CSU", "2016-06-10", "2017-10-25", 2, wp=18),
            ],
        )

    def test_a_successor_starting_the_next_day_leaves_the_count_unbroken(self) -> None:
        self.assertEqual(
            seats_of(
                mdb("11000002", wahlperiode(18, "22.10.2013", "03.06.2016", institution(CDU, "22.10.2013"))),
                mdb("11000003", wahlperiode(18, "04.06.2016", "24.10.2017", institution(CDU, "04.06.2016"))),
            ),
            [seat("CDU/CSU", "2013-10-22", "2017-10-25", 1, wp=18)],
        )

    def test_a_successor_starting_on_the_leavers_last_day_takes_that_day(self) -> None:
        # Lambsdorff's Mandat ends 07.08.2023, his Nachrückerin Willkomm's starts
        # 07.08.2023: the day is hers, as a handover day between two groups
        # belongs to the new one.
        fdp = "Fraktion der Freien Demokratischen Partei"
        rows = stretches(
            mdb("11004798", wahlperiode(20, "26.10.2021", "07.08.2023", institution(fdp, "26.10.2021", "07.08.2023"))),
            mdb("11004783", wahlperiode(20, "07.08.2023", "25.03.2025", institution(fdp, "07.08.2023"))),
        )
        self.assertEqual(
            [(r["mdb_id"], r["valid_from"], r["valid_until"]) for r in rows],
            [("11004798", "2021-10-26", "2023-08-07"), ("11004783", "2023-08-07", "2025-03-26")],
        )
        self.assertEqual(derive.party_seats(rows), [seat("FDP", "2021-10-26", "2025-03-26", 1, wp=20)])

    def test_a_seat_moving_to_another_lands_list_is_a_handover_too(self) -> None:
        # Berlin repeat election: Stahr (Berlin list) ends 04.03.2024 and the
        # Grünen seat goes to Krumwiede-Steiner (NRW list) from 04.03.2024.
        rows = stretches(
            mdb("11005227", wahlperiode(20, "26.10.2021", "04.03.2024", institution("Fraktion BÜNDNIS 90/DIE GRÜNEN", "26.10.2021", "04.03.2024"), land="BE")),
            mdb("11005312", wahlperiode(20, "04.03.2024", "25.03.2025", institution("Fraktion BÜNDNIS 90/DIE GRÜNEN", "04.03.2024"), land="NW")),
        )
        self.assertEqual(rows[0]["valid_until"], "2024-03-04")

    def test_a_mandate_of_another_group_starting_on_a_last_day_is_no_handover(self) -> None:
        fdp = "Fraktion der Freien Demokratischen Partei"
        rows = stretches(
            mdb("11000001", wahlperiode(20, "26.10.2021", "07.08.2023", institution(fdp, "26.10.2021", "07.08.2023"))),
            mdb("11000003", wahlperiode(20, "07.08.2023", "25.03.2025", institution(AFD, "07.08.2023"))),
        )
        self.assertEqual(rows[0]["valid_until"], "2023-08-08")

    def test_one_successor_takes_the_last_day_of_one_leaver_only(self) -> None:
        fdp = "Fraktion der Freien Demokratischen Partei"
        rows = stretches(
            mdb("11000001", wahlperiode(20, "26.10.2021", "07.08.2023", institution(fdp, "26.10.2021", "07.08.2023"))),
            mdb("11000002", wahlperiode(20, "26.10.2021", "07.08.2023", institution(fdp, "26.10.2021", "07.08.2023"))),
            mdb("11000003", wahlperiode(20, "07.08.2023", "25.03.2025", institution(fdp, "07.08.2023"))),
        )
        self.assertEqual(sorted(r["valid_until"] for r in rows[:2]), ["2023-08-07", "2023-08-08"])

    def test_which_leaver_a_successor_relieves_does_not_depend_on_input_order(self) -> None:
        fdp = "Fraktion der Freien Demokratischen Partei"
        records = [
            mdb("11000002", wahlperiode(20, "26.10.2021", "07.08.2023", institution(fdp, "26.10.2021", "07.08.2023"))),
            mdb("11000001", wahlperiode(20, "26.10.2021", "07.08.2023", institution(fdp, "26.10.2021", "07.08.2023"))),
            mdb("11000003", wahlperiode(20, "07.08.2023", "25.03.2025", institution(fdp, "07.08.2023"))),
        ]
        ends = lambda rows: sorted((r["mdb_id"], r["valid_until"]) for r in rows)
        self.assertEqual(ends(stretches(*records)), ends(stretches(*reversed(records))))

    def test_the_linke_split_ends_the_fraktion_before_the_gruppen_start(self) -> None:
        # Textarchiv: the Fraktion ended on 06.12.2023; the Gruppen were
        # recognised on 02.02.2024 (C1 plan F4, S3).
        def linke(mdb_id: str, gruppe: str) -> dict[str, object]:
            return mdb(mdb_id, wahlperiode(
                20, "26.10.2021", "25.03.2025",
                institution("Fraktion DIE LINKE.", "26.10.2021", "06.12.2023"),
                institution("Fraktionslos", "06.12.2023", "02.02.2024"),
                institution(gruppe, "02.02.2024", "25.03.2025"),
            ))

        bsw = "Gruppe BSW - Bündnis Sahra Wagenknecht - Vernunft und Gerechtigkeit"
        self.assertEqual(
            seats_of(linke("11000001", "Gruppe Die Linke"), linke("11000002", "Gruppe Die Linke"), linke("11000003", bsw)),
            [
                seat("Die Linke", "2021-10-26", "2023-12-06", 3, wp=20),
                seat("Gruppe BSW", "2024-02-02", "2025-03-26", 1, wp=20),
                seat("Gruppe Die Linke", "2024-02-02", "2025-03-26", 2, wp=20),
                seat("fraktionslos", "2023-12-06", "2024-02-02", 3, wp=20),
            ],
        )

    def test_the_last_day_of_a_wahlperiode_counts_in_both(self) -> None:
        self.assertEqual(
            seats_of(
                mdb("11000001",
                    wahlperiode(18, "22.10.2013", "24.10.2017", institution(CDU, "22.10.2013")),
                    wahlperiode(19, "24.10.2017", "26.10.2021", institution(CDU, "24.10.2017"))),
            ),
            [seat("CDU/CSU", "2013-10-22", "2017-10-25", 1, wp=18), seat("CDU/CSU", "2017-10-24", "2021-10-27", 1, wp=19)],
        )



class SeatRowsGateTests(unittest.TestCase):
    """``stammdaten.seat_rows`` is the gate ``refresh`` caches a file through,
    so it refuses what ``persist_seat_counts`` would fail on later."""

    def gate(self, *mdbs: dict[str, object]) -> None:
        stammdaten.seat_rows(list(mdbs), since_wahlperiode=18)

    # Value: protects=party_seats refuses a negative count by name instead of emitting seats=-1 (the table's
    #   CHECK (seats > 0) would fail every later rebuild); fails_when=`if count:` is true for -1 again;
    #   why_new=TODOS C1 deferred item 9; seam=derive.party_seats
    def test_an_inverted_row_is_refused_not_counted_as_minus_one_seat(self) -> None:
        with self.assertRaises(derive.StammdatenError) as raised:
            derive.party_seats([row("AfD", "2025-06-02", "2025-06-01")])
        for part in ("WP 21", "AfD", "-1", "2025-06-01"):
            self.assertIn(part, str(raised.exception))

    # Value: protects=a file whose rows the store cannot hold (an empty or inverted Zugehörigkeit, a seat count
    #   of zero or less, a repeated primary key) is refused at the gate, so refresh never caches it and no
    #   later rebuild dies with a raw sqlite3.IntegrityError; fails_when=seat_rows checks only the size rule
    #   again; why_new=TODOS C1 deferred item 9 (the ship's adversarial pass); seam=stammdaten.seat_rows
    #   with the derivation patched for the shapes it no longer produces, a real duplicate MdB for the key
    def test_rows_the_store_cannot_hold_are_refused_at_the_gate(self) -> None:
        good = [row("CDU/CSU", "2025-03-25", None)]
        for label, patched, message in (
            ("empty Zugehörigkeit", (good + [row("AfD", "2025-06-01", "2025-06-01")], []), "ends on"),
            ("inverted Zugehörigkeit", (good + [row("AfD", "2025-06-02", "2025-06-01")], []), "ends on"),
            ("zero seats", (good, [seat("CDU/CSU", "2025-03-25", None, 0)]), "seats"),
            ("negative seats", (good, [seat("CDU/CSU", "2025-03-25", None, -1)]), "seats"),
            ("repeated Zugehörigkeit key", (good + good, []), "twice"),
            ("repeated seat key", (good, [seat("CDU/CSU", "2025-03-25", None, 1), seat("CDU/CSU", "2025-03-25", "2025-04-01", 2)]), "twice"),
        ):
            with self.subTest(label), \
                    mock.patch.object(derive, "mdb_zugehoerigkeiten", return_value=patched[0]), \
                    mock.patch.object(derive, "party_seats", return_value=patched[1]), \
                    mock.patch.object(derive, "check_seat_totals"), \
                    self.assertRaisesRegex(derive.StammdatenError, message):
                stammdaten.seat_rows([], since_wahlperiode=18)

    def test_a_mdb_listed_twice_is_refused_by_the_repeated_key(self) -> None:
        record = mdb("11000001", wahlperiode(21, "25.03.2025", "", institution(CDU, "25.03.2025")))
        with self.assertRaisesRegex(derive.StammdatenError, "11000001.*twice"):
            self.gate(record, record)


class SeatTotalsTests(unittest.TestCase):
    def test_the_legal_sizes_are_the_four_bundestage(self) -> None:
        self.assertEqual(derive.BUNDESTAG_SIZES, {18: 631, 19: 709, 20: 736, 21: 630})

    def test_totals_that_reach_but_never_pass_the_size_pass(self) -> None:
        derive.check_seat_totals(
            [seat("CDU/CSU", "2025-03-25", None, 2), seat("AfD", "2025-03-25", "2025-06-01", 1), seat("AfD", "2025-06-10", None, 1)],
            sizes={21: 3},
        )

    def test_a_day_over_the_size_fails_by_wahlperiode_and_day(self) -> None:
        with self.assertRaises(derive.StammdatenError) as raised:
            derive.check_seat_totals(
                [seat("CDU/CSU", "2025-03-25", None, 2), seat("AfD", "2025-03-25", "2025-06-01", 1), seat("SPD", "2025-05-01", None, 1)],
                sizes={21: 3},
            )
        for part in ("WP 21", "2025-05-01", "4", "3"):
            self.assertIn(part, str(raised.exception))

    def test_a_wahlperiode_that_never_reaches_its_size_fails(self) -> None:
        with self.assertRaises(derive.StammdatenError) as raised:
            derive.check_seat_totals([seat("CDU/CSU", "2025-03-25", None, 2)], sizes={21: 3})
        self.assertIn("WP 21", str(raised.exception))

    def test_a_wahlperiode_without_a_legal_size_fails(self) -> None:
        with self.assertRaises(derive.StammdatenError) as raised:
            derive.check_seat_totals([seat("CDU/CSU", "2029-10-20", None, 3, wp=22)], sizes={21: 3})
        self.assertIn("WP 22", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
