"""Fakt der Woche: the rule as pure functions, the six metrics, the engine
that writes the three tables, the replay and the SVG card.

One test per rule and per edge in the plan's "Failure modes" table
(~/.gstack/projects/LucaAlv-poliwatch/fakt-der-woche-plan.md, D1-D28).
"""

from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import _support  # noqa: F401
import _facts_fixture
import facts


REAL_STORE = _support.ROOT / ".context" / "dip-pulse-site" / "data" / "bundestag-pulse.sqlite"

def quiet() -> io.StringIO:
    """The engine's progress lines go to stderr in a build; tests keep them."""
    return io.StringIO()


KNAPPSTE = "knappste-abstimmung"
ABWEICHLER = "meiste-abweichler"
DEBATTE = "laengste-debatte"
LAENGSTE = "laengste-rede"
SITZUNG = "laengste-sitzung"
ERSTE = "erste-reden"


def week_specs(count: int, *, start_number: int = 1, wp: int = 21, year: int = 2025, **extra):
    """count consecutive ISO weeks in ``wp``; the longest speech grows with the
    week (1000, 1100, ...) so every week beats all prior ones by default. Only
    the three metrics that need no extra seeding observe on these specs."""
    specs = []
    for index in range(count):
        # Wednesdays from the 3rd ISO week of ``year`` (all on distinct weeks).
        day = facts.date.fromisocalendar(year, 3 + index, 3)
        spec = {
            "document_number": f"{wp}/{start_number + index}",
            "date": day.isoformat(),
            "longest": 1000 + 100 * index,
            "closest": (300 + index, 200),
            # A named topic, the way a real agenda item has one: without it
            # laengste-debatte withholds its card (requires_topic).
            "items": [{"heading": "TOP 1", "proceeding_title": "Haushaltsbegleitgesetz 2027"}],
        }
        spec.update(extra)
        specs.append(spec)
    return specs


class StoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "store.sqlite"

    def seed(self, weeks, **kwargs):
        self.seeded = _facts_fixture.seed_weeks(self.path, weeks, **kwargs)
        self.conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        return self.seeded

    def writable(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        self.addCleanup(conn.close)
        return conn

    def compute(self, built=("votes",), registry=facts.REGISTRY, **kwargs):
        return facts.compute(
            self.conn, registry, self.seeded["completeness"], built=set(built), **kwargs
        )

    @staticmethod
    def rows_for(rows, metric_id):
        return [row for row in rows if row["metric_id"] == metric_id]

    def one(self, metric_id, index=0, **kwargs):
        return self.rows_for(self.compute(**kwargs), metric_id)[index]


class RegistryTests(unittest.TestCase):
    def test_the_six_metrics_are_registered_in_tie_rank_order(self) -> None:
        self.assertEqual(
            [metric["id"] for metric in facts.REGISTRY],
            [KNAPPSTE, ABWEICHLER, DEBATTE, LAENGSTE, SITZUNG, ERSTE],
        )
        self.assertEqual([metric["tie_rank"] for metric in facts.REGISTRY], [1, 2, 3, 4, 5, 6])
        facts.validate_registry()

    def test_required_caveats_are_registry_data(self) -> None:
        # D27: these two metrics are misread without their caveat.
        for metric_id in facts.REQUIRED_CAVEATS:
            with self.subTest(metric=metric_id):
                caveat = facts.REGISTRY_BY_ID[metric_id]["caveat"]
                self.assertTrue(caveat and caveat.strip())
        self.assertIn("Gewissensfragen", facts.REGISTRY_BY_ID[ABWEICHLER]["caveat"])
        self.assertIn("seit Januar 2022", facts.REGISTRY_BY_ID[ERSTE]["caveat"])

    def test_a_metric_without_its_required_caveat_is_rejected(self) -> None:
        stripped = tuple(
            {**metric, "caveat": None} if metric["id"] == ABWEICHLER else metric
            for metric in facts.REGISTRY
        )
        with self.assertRaises(facts.FactsError) as ctx:
            facts.validate_registry(stripped)
        self.assertIn(ABWEICHLER, str(ctx.exception))

    def test_sql_sha256_tracks_the_statement(self) -> None:
        metric = facts.REGISTRY_BY_ID[LAENGSTE]
        changed = {**metric, "sql": metric["sql"] + "\nORDER BY s.id"}
        self.assertNotEqual(facts.sql_sha256(metric), facts.sql_sha256(changed))


class SittingWeekTests(StoreCase):
    def test_wahlperiode_from_document_number(self) -> None:
        self.assertEqual(facts.wahlperiode("21/94"), 21)
        self.assertEqual(facts.wahlperiode("20/14"), 20)

    def test_two_protocols_in_one_iso_week_form_one_week(self) -> None:
        self.seed(
            [
                {"document_number": "21/91", "date": "2026-09-08", "longest": 500},
                {"document_number": "21/92", "date": "2026-09-09", "longest": 900},
            ]
        )
        weeks = facts.sitting_weeks(facts.load_protocols(self.conn))
        self.assertEqual(len(weeks), 1)
        self.assertEqual(weeks[0].key, (2026, 37))
        self.assertEqual(weeks[0].wahlperiode, 21)
        self.assertEqual(weeks[0].period_kind, "week")
        self.assertEqual(weeks[0].period_key, "2026-W37")
        self.assertEqual([p["document_number"] for p in weeks[0].protocols], ["21/91", "21/92"])

    def test_malformed_document_number_names_the_protocol(self) -> None:
        with self.assertRaises(facts.FactsError) as ctx:
            facts.sitting_weeks([{"id": "p1", "document_number": "Plenarprotokoll 21", "date": "2026-09-08"}])
        self.assertIn("Plenarprotokoll 21", str(ctx.exception))

    def test_every_row_carries_its_period(self) -> None:
        self.seed(week_specs(2))
        for row in self.compute():
            self.assertEqual(row["period_kind"], "week")
            self.assertEqual(row["period_key"], f"{row['iso_year']}-W{row['iso_week']:02d}")


# ---------------------------------------------------------------------------
# T10: one test per metric, pinning its observation and its receipt.
# ---------------------------------------------------------------------------


class KnappsteAbstimmungTests(StoreCase):
    def test_observation_and_receipt(self) -> None:
        seeded = self.seed(
            [
                {
                    "document_number": "21/1",
                    "date": "2025-03-25",
                    "votes": [(300, 200, "weit"), (251, 249, "knapp")],
                }
            ]
        )
        row = self.one(KNAPPSTE)
        self.assertAlmostEqual(row["value"], 2 / 500)
        self.assertEqual(row["denominator"], 500)
        self.assertEqual(row["week_n"], 2)
        self.assertEqual(row["citation"]["title"], "knapp")
        self.assertEqual(
            [(r["entity_kind"], r["document_number"], r["official_url"], r["position"]) for r in row["receipts"]],
            [("vote", "21/1", f"https://example.test/abstimmung/{seeded['vote_ids']['21/1'][1]}", 0)],
        )

    def test_week_without_a_vote_yields_no_observation(self) -> None:
        self.seed(
            [{"document_number": "21/1", "date": "2025-03-25", "unlinked_votes": [(300, 299, "lose")]}]
        )
        row = self.one(KNAPPSTE)
        self.assertIsNone(row["value"])
        self.assertEqual(row["week_n"], 0)
        self.assertEqual(row["eligible"], 0)

    def test_vote_with_zero_denominator_is_excluded(self) -> None:
        self.seed(
            [{"document_number": "21/1", "date": "2025-03-25", "votes": [(0, 0, "leer"), (300, 200, "voll")]}]
        )
        row = self.one(KNAPPSTE)
        self.assertEqual(row["week_n"], 1)
        self.assertAlmostEqual(row["value"], 100 / 500)


class MeisteAbweichlerTests(StoreCase):
    VOTE = {
        "yes": 3,
        "no": 3,
        "title": "Gewissensfrage",
        "leading": {"SPD": "no", "CDU/CSU": "yes", "fraktionslos": "no"},
        "members": [
            ("Treue Sozialdemokratin", "SPD", "no"),
            ("Abweichender Sozialdemokrat", "SPD", "yes"),
            ("Enthaltende Sozialdemokratin", "SPD", "abstain"),
            ("Fehlender Sozialdemokrat", "SPD", "absent"),
            ("Abweichende Christdemokratin", "CDU/CSU", "no"),
            ("Fraktionslose Abgeordnete", "fraktionslos", "yes"),
        ],
    }

    def test_observation_counts_only_counter_votes_inside_a_fraktion(self) -> None:
        seeded = self.seed(
            [{"document_number": "21/1", "date": "2025-03-25", "votes": [self.VOTE]}]
        )
        row = self.one(ABWEICHLER)
        # Two counter-votes. The Enthaltung and the Abwesenheit are not a
        # counter-vote, and "fraktionslos" has no Fraktionslinie to break.
        self.assertEqual(row["value"], 2)
        # Denominator: the members who cast a yes or a no.
        self.assertEqual(row["denominator"], 4)
        self.assertEqual(row["citation"]["title"], "Gewissensfrage")
        self.assertEqual(
            [(r["entity_kind"], r["document_number"], r["position"]) for r in row["receipts"]],
            [("vote", "21/1", 0)],
        )
        self.assertEqual(seeded["vote_ids"]["21/1"], [row["citation"]["id"]])

    def test_vote_without_member_rows_yields_no_observation(self) -> None:
        self.seed([{"document_number": "21/1", "date": "2025-03-25", "closest": (300, 200)}])
        row = self.one(ABWEICHLER)
        self.assertIsNone(row["value"])
        self.assertEqual(row["week_n"], 0)


class LaengsteDebatteTests(StoreCase):
    def test_observation_sums_one_agenda_item_and_cites_the_proceeding_title(self) -> None:
        seeded = self.seed(
            [
                {
                    "document_number": "21/1",
                    "date": "2025-03-25",
                    "items": [
                        {"heading": "TOP 1", "proceeding_title": "Haushaltsbegleitgesetz 2027"},
                        {"heading": "TOP 2"},
                    ],
                    "speeches": [
                        {"char_count": 300, "speaker": "Ada Lovelace", "rede_id": "IDA", "item": 0},
                        {"char_count": 600, "speaker": "Karl Marx", "rede_id": "IDB", "item": 0},
                        {"char_count": 500, "speaker": "Ada Lovelace", "rede_id": "IDC", "item": 1},
                    ],
                }
            ]
        )
        row = self.one(DEBATTE)
        self.assertEqual(row["value"], 900)
        self.assertEqual(row["denominator"], 2)
        self.assertEqual(row["week_n"], 2)
        self.assertEqual(row["citation"]["id"], seeded["agenda_item_ids"]["21/1"][0])
        self.assertEqual(row["citation"]["topic"], "Haushaltsbegleitgesetz 2027")
        self.assertEqual(
            [(r["entity_kind"], r["document_number"], r["page"], r["page_quadrant"]) for r in row["receipts"]],
            [("agenda_item", "21/1", 2001, "A")],
        )

    def test_topic_falls_back_to_the_stripped_heading(self) -> None:
        self.seed(
            [
                {
                    "document_number": "21/1",
                    "date": "2025-03-25",
                    "items": [{"heading": "Beratung des Antrags der Fraktion der SPD Bezahlbares Wohnen"}],
                    "speeches": [{"char_count": 400, "speaker": "Ada Lovelace", "rede_id": "IDA"}],
                }
            ]
        )
        citation = self.one(DEBATTE)["citation"]
        self.assertTrue(citation["topic"])
        self.assertNotIn("Beratung des Antrags", citation["topic"])

    def test_an_item_without_a_topic_says_so(self) -> None:
        self.seed(
            [
                {
                    "document_number": "21/1",
                    "date": "2025-03-25",
                    "items": [{"heading": None}],
                    "speeches": [{"char_count": 400, "speaker": "Ada Lovelace", "rede_id": "IDA"}],
                }
            ]
        )
        self.assertIsNone(self.one(DEBATTE)["citation"]["topic"])


class LaengsteRedeTests(StoreCase):
    def test_observation_receipt_and_topic(self) -> None:
        seeded = self.seed(
            [
                {
                    "document_number": "21/1",
                    "date": "2025-03-25",
                    "items": [{"heading": "TOP 1", "proceeding_title": "Gesetz über die Feststellung"}],
                    "speeches": [(900, "Ada Lovelace", "ID2100100"), (100, "Karl Marx", "ID2100200")],
                }
            ]
        )
        row = self.one(LAENGSTE)
        self.assertEqual(row["value"], 900)
        self.assertEqual(row["citation"]["display_name"], "Ada Lovelace")
        self.assertEqual(row["citation"]["fraktion"], "SPD")
        self.assertEqual(row["citation"]["topic"], "Gesetz über die Feststellung")
        self.assertEqual(row["citation"]["id"], seeded["speech_ids"]["21/1"][0])
        self.assertEqual(
            [(r["entity_kind"], r["document_number"], r["rede_id"], r["page"], r["page_quadrant"]) for r in row["receipts"]],
            [("speech", "21/1", "ID2100100", None, None)],
        )

    def test_synthetic_rede_id_falls_back_to_the_page_anchor(self) -> None:
        self.seed(
            [
                {
                    "document_number": "21/2",
                    "date": "2025-04-02",
                    "speeches": [(950, "Ada Lovelace", None), (100, "Karl Marx", "ID2200200")],
                }
            ]
        )
        self.assertEqual(
            [(r["rede_id"], r["page"], r["page_quadrant"]) for r in self.one(LAENGSTE)["receipts"]],
            [(None, 1001, "B")],
        )

    def test_null_mp_id_speech_is_excluded(self) -> None:
        self.seed(
            [
                {
                    "document_number": "21/1",
                    "date": "2025-03-25",
                    "speeches": [(9000, None, "IDNULL"), (400, "Ada Lovelace", "IDADA")],
                }
            ]
        )
        row = self.one(LAENGSTE)
        self.assertEqual(row["value"], 400)
        self.assertEqual(row["week_n"], 1)

    def test_row_level_tie_cites_the_lowest_id(self) -> None:
        seeded = self.seed(
            [
                {
                    "document_number": "21/1",
                    "date": "2025-03-25",
                    "speeches": [(700, "Ada Lovelace", "IDA"), (700, "Karl Marx", "IDB")],
                    "votes": [(300, 200, "erste"), (300, 200, "zweite")],
                }
            ]
        )
        rows = self.compute()
        self.assertEqual(self.rows_for(rows, LAENGSTE)[0]["citation"]["id"], seeded["speech_ids"]["21/1"][0])
        self.assertEqual(self.rows_for(rows, KNAPPSTE)[0]["citation"]["id"], seeded["vote_ids"]["21/1"][0])


class LaengsteSitzungTests(StoreCase):
    def test_observation_wraps_past_midnight_and_cites_the_protocol(self) -> None:
        self.seed(
            [
                # 9:00 to 01:30 the next morning, single-digit hour as the store
                # spells it for 2022's protocols: 16 h 30 min.
                {"document_number": "21/1", "date": "2025-03-25", "sitzung": ("9:00", "01:30")},
                {"document_number": "21/2", "date": "2025-03-26", "sitzung": ("09:00", "14:08")},
            ]
        )
        row = self.one(SITZUNG)
        self.assertEqual(row["value"], 990)
        self.assertEqual(row["week_n"], 2)
        self.assertEqual(row["citation"]["document_number"], "21/1")
        self.assertEqual(row["citation"]["sitzung_end"], "01:30")
        self.assertEqual(
            [(r["entity_kind"], r["document_number"], r["official_url"], r["position"]) for r in row["receipts"]],
            [("protocol", "21/1", "https://example.test/p1.pdf", 0)],
        )

    def test_protocol_without_times_yields_no_observation(self) -> None:
        self.seed([{"document_number": "21/1", "date": "2025-03-25"}])
        row = self.one(SITZUNG)
        self.assertIsNone(row["value"])
        self.assertEqual(row["week_n"], 0)


class ErsteRedenTests(StoreCase):
    # The live store splits one person across an "aw:" and an "xml:" mps row
    # that share their xml_redner_id (D25's assumption re-checked on the
    # 2026-09-19 store: 314 display names are split). Grouping by mps.id would
    # make the second row look like a debutant.
    PEOPLE = {
        "wiese-aw": {
            "display_name": "Dirk Wiese",
            "party": "SPD",
            "identity_key": "aw:78913",
            "xml_redner_id": "11004444",
        },
        "wiese-xml": {
            "display_name": "Dirk Wiese",
            "party": "SPD",
            "identity_key": "xml:11004444",
            "xml_redner_id": "11004444",
        },
    }

    def seed_two_weeks(self):
        return self.seed(
            [
                {
                    "document_number": "21/1",
                    "date": "2025-03-25",
                    "speeches": [(500, "wiese-aw", "IDW1"), (100, "Karl Marx", "IDK1")],
                },
                {
                    "document_number": "21/2",
                    "date": "2025-04-02",
                    "speeches": [(400, "wiese-xml", "IDW2")],
                },
            ],
            people=self.PEOPLE,
        )

    def test_counts_debutants_and_cites_every_first_speech(self) -> None:
        seeded = self.seed_two_weeks()
        first, second = self.rows_for(self.compute(), ERSTE)
        self.assertEqual(first["value"], 2)
        self.assertEqual(first["week_n"], 2)
        self.assertEqual(first["citation"]["speakers"], ["Dirk Wiese", "Karl Marx"])
        self.assertEqual(
            [(r["entity_kind"], r["document_number"], r["rede_id"], r["position"]) for r in first["receipts"]],
            [("speech", "21/1", "IDW1", 0), ("speech", "21/1", "IDK1", 1)],
        )
        self.assertEqual(seeded["speech_ids"]["21/1"][0], first["citation"]["id"])
        # Week 2 has no debutant: the second mps row is the same person.
        self.assertIsNone(second["value"])
        self.assertEqual(second["week_n"], 0)

    def test_grouping_by_mps_id_would_double_count_the_split_person(self) -> None:
        self.seed_two_weeks()
        split = self.conn.execute(
            "SELECT COUNT(*) FROM mps WHERE xml_redner_id = '11004444'"
        ).fetchone()[0]
        self.assertEqual(split, 2)


class ObserveTests(StoreCase):
    def test_depends_on_skips_an_unbuilt_metric(self) -> None:
        self.seed(week_specs(2))
        rows = self.compute(built=())
        self.assertEqual(self.rows_for(rows, KNAPPSTE), [])
        self.assertEqual(self.rows_for(rows, ABWEICHLER), [])
        self.assertEqual(len(self.rows_for(rows, LAENGSTE)), 2)

    def test_a_metric_whose_sql_raises_names_the_metric(self) -> None:
        self.seed(week_specs(2))
        broken = tuple(
            {**metric, "sql": "SELECT * FROM speeches_does_not_exist"} if metric["id"] == DEBATTE else metric
            for metric in facts.REGISTRY
        )
        with self.assertRaises(facts.FactsError) as ctx:
            self.compute(registry=broken)
        self.assertIn(DEBATTE, str(ctx.exception))


class PercentileTests(unittest.TestCase):
    def test_percentile_counts_strictly_beaten_in_the_metric_direction(self) -> None:
        self.assertEqual(facts.percentile(5, [1, 2, 3, 4], "max"), 1.0)
        self.assertEqual(facts.percentile(3, [1, 2, 3, 4], "max"), 0.5)
        self.assertEqual(facts.percentile(0.01, [0.02, 0.03, 0.005, 0.04], "min"), 0.75)

    def test_empty_prior_is_not_comparable(self) -> None:
        self.assertIsNone(facts.percentile(5, [], "max"))

    def test_tie_with_the_record_never_reads_100_percent(self) -> None:
        self.assertEqual(facts.percentile(4, [1, 2, 3, 4], "max"), 0.75)
        self.assertEqual(facts.percentile(0.02, [0.02, 0.05], "min"), 0.5)
        self.assertEqual(facts.format_percentile(0.996), "99")

    def test_all_equal_prior_reads_zero(self) -> None:
        self.assertEqual(facts.percentile(3, [3, 3, 3], "max"), 0.0)


class BaselineTests(StoreCase):
    def test_wp_baseline_when_enough_prior_weeks_else_all_coverage(self) -> None:
        specs = week_specs(9, wp=20, start_number=14, year=2022) + week_specs(
            5, wp=21, start_number=1, year=2025
        )
        self.seed(specs)
        rows = self.rows_for(self.compute(), LAENGSTE)
        wp20_last = rows[8]
        self.assertEqual(wp20_last["baseline_kind"], "wp")
        self.assertEqual(wp20_last["baseline_count"], 8)
        self.assertEqual(wp20_last["eligible"], 1)
        wp21_fifth = rows[13]
        self.assertEqual(wp21_fifth["baseline_kind"], "all")
        self.assertEqual(wp21_fifth["baseline_count"], 13)
        self.assertEqual(wp21_fifth["eligible"], 1)

    def test_baseline_phrase_names_wp_start_only_from_protocol_one(self) -> None:
        specs = week_specs(9, wp=20, start_number=14, year=2022) + week_specs(
            9, wp=21, start_number=1, year=2025
        )
        self.seed(specs)
        rows = self.rows_for(self.compute(), LAENGSTE)
        self.assertEqual(rows[8]["baseline_kind"], "wp")
        self.assertEqual(rows[8]["baseline_label"], "seit Januar 2022")
        self.assertEqual(rows[17]["baseline_kind"], "wp")
        self.assertEqual(rows[17]["baseline_label"], "seit Beginn der 21. Wahlperiode")

    def test_ineligible_below_eight_prior_weeks(self) -> None:
        self.seed(week_specs(9))
        rows = self.rows_for(self.compute(), LAENGSTE)
        self.assertEqual([row["eligible"] for row in rows], [0] * 8 + [1])
        # The percentile over a too-small population is kept for the replay
        # table; the row is ineligible and its clause says so.
        self.assertEqual(rows[7]["baseline_count"], 7)
        self.assertEqual(facts.comparison_clause(rows[7]), "noch nicht vergleichbar")
        self.assertEqual(rows[8]["percentile"], 1.0)

    def test_history_is_strictly_before_the_week(self) -> None:
        specs = week_specs(10)
        specs[9]["longest"] = 99_999
        self.seed(specs)
        rows = self.rows_for(self.compute(), LAENGSTE)
        self.assertEqual(rows[8]["percentile"], 1.0)
        self.assertEqual(rows[8]["baseline_count"], 8)
        self.assertEqual(rows[8]["baseline_to"], "2025-W10")


class PublishableTests(StoreCase):
    def test_the_floor_keeps_an_unusual_fact_and_drops_an_ordinary_one(self) -> None:
        # Nine growing weeks, then a week whose longest speech is the shortest
        # of them all: eligible, percentile 0, below the floor.
        specs = week_specs(10)
        specs[9]["longest"] = 1
        self.seed(specs)
        rows = self.rows_for(self.compute(), LAENGSTE)
        self.assertEqual(rows[8]["percentile"], 1.0)
        self.assertEqual(rows[8]["publishable"], 1)
        self.assertEqual(rows[9]["eligible"], 1)
        self.assertEqual(rows[9]["percentile"], 0.0)
        self.assertEqual(rows[9]["publishable"], 0)
        self.assertIsNone(rows[9]["rank"])
        self.assertEqual(facts.comparison_clause(rows[9]), "nicht ungewöhnlich genug")

    def test_the_floor_is_inclusive_at_fifty_percent(self) -> None:
        def row(**kwargs):
            return {"metric_id": LAENGSTE, "value": 100, "eligible": 1, **kwargs}

        self.assertTrue(facts.is_publishable(row(percentile=0.5)))
        self.assertFalse(facts.is_publishable(row(percentile=0.499)))
        self.assertFalse(facts.is_publishable(row(eligible=0, percentile=1.0)))
        self.assertFalse(facts.is_publishable(row(percentile=None)))
        self.assertFalse(facts.is_publishable(row(value=None, percentile=1.0)))

    def test_the_withheld_reason_names_the_gate_that_applied(self) -> None:
        def row(**kwargs):
            return {"metric_id": LAENGSTE, "value": 100, "eligible": 1, "percentile": 1.0, **kwargs}

        self.assertIsNone(facts.withheld_reason(row()))
        self.assertEqual(facts.withheld_reason(row(value=None)), facts.WITHHELD_NO_OBSERVATION)
        self.assertEqual(facts.withheld_reason(row(eligible=0)), facts.WITHHELD_NOT_COMPARABLE)
        self.assertEqual(facts.withheld_reason(row(percentile=0.1)), facts.WITHHELD_BELOW_FLOOR)
        # Every reason has a clause the archive can print.
        self.assertEqual(set(facts.WITHHELD_CLAUSES), {
            facts.WITHHELD_NO_OBSERVATION, facts.WITHHELD_NOT_COMPARABLE,
            facts.WITHHELD_BELOW_MIN_VALUE, facts.WITHHELD_NO_TOPIC,
            facts.WITHHELD_BELOW_FLOOR,
        })

    def test_a_thin_count_is_withheld_by_min_value(self) -> None:
        # meiste-abweichler is zero-inflated, so one Abweichlerin beats two
        # thirds of the weeks. A floor of three keeps that off a card.
        loyal = [("Treue Sozialdemokratin", "SPD", "no")]
        specs = []
        for index in range(10):
            day = facts.date.fromisocalendar(2025, 3 + index, 3)
            members = list(loyal)
            # The last week has one deviation, the earlier ones none.
            if index == 9:
                members.append(("Abweichender Sozialdemokrat", "SPD", "yes"))
            specs.append(
                {
                    "document_number": f"21/{index + 1}",
                    "date": day.isoformat(),
                    "votes": [
                        {
                            "yes": 1,
                            "no": 1,
                            "title": f"Abstimmung {index}",
                            "leading": {"SPD": "no"},
                            "members": members,
                        }
                    ],
                }
            )
        self.seed(specs)
        last = self.rows_for(self.compute(), ABWEICHLER)[9]
        self.assertEqual(last["value"], 1)
        self.assertEqual(last["eligible"], 1)
        self.assertEqual(last["percentile"], 1.0)
        self.assertEqual(last["withheld"], facts.WITHHELD_BELOW_MIN_VALUE)
        self.assertEqual(last["publishable"], 0)
        self.assertEqual(
            facts.comparison_clause(last), "zu wenige, um daraus einen Fakt zu machen"
        )

    def test_a_debate_without_a_topic_is_withheld(self) -> None:
        # The topic is this card's subject; 6 of the 48 cards the metric would
        # post over the real store's coverage have none.
        specs = week_specs(9)
        specs[8]["items"] = [{"heading": None}]
        self.seed(specs)
        rows = self.rows_for(self.compute(), DEBATTE)
        self.assertEqual(rows[8]["percentile"], 1.0)
        self.assertEqual(rows[8]["withheld"], facts.WITHHELD_NO_TOPIC)
        self.assertEqual(rows[8]["publishable"], 0)
        self.assertEqual(facts.comparison_clause(rows[8]), "Thema der Debatte nicht bestimmbar")
        # The longest *speech* of the same week still posts: its subject is the
        # speaker, not the topic.
        self.assertEqual(self.rows_for(self.compute(), LAENGSTE)[8]["publishable"], 1)

    def test_an_absolute_gate_is_registry_data_not_a_rule_change(self) -> None:
        relaxed = tuple(
            {**metric, "min_value": None} if metric["id"] == ABWEICHLER else metric
            for metric in facts.REGISTRY
        )
        row = {"metric_id": ABWEICHLER, "value": 1, "eligible": 1, "percentile": 1.0}
        self.assertEqual(facts.withheld_reason(row), facts.WITHHELD_BELOW_MIN_VALUE)
        self.assertIsNone(facts.withheld_reason(row, facts.REGISTRY_BY_ID[LAENGSTE]))
        facts.validate_registry(relaxed)

    def test_min_value_on_a_min_direction_metric_is_rejected(self) -> None:
        wrong = tuple(
            {**metric, "min_value": 3} if metric["id"] == KNAPPSTE else metric
            for metric in facts.REGISTRY
        )
        with self.assertRaises(facts.FactsError) as ctx:
            facts.validate_registry(wrong)
        self.assertIn(KNAPPSTE, str(ctx.exception))

    def test_an_ineligible_row_is_never_publishable(self) -> None:
        self.seed(week_specs(9))
        for row in self.compute():
            if not row["eligible"]:
                self.assertEqual(row["publishable"], 0)


class RankTests(StoreCase):
    def test_every_publishable_fact_is_posted_in_percentile_then_tie_rank_order(self) -> None:
        # Week 9 is the closest vote and the longest speech and the longest
        # debate so far: three cards, not one, and knappste-abstimmung leads
        # the tie on tie_rank 1.
        specs = week_specs(9)
        specs[8]["closest"] = (250, 249)
        self.seed(specs)
        rows = self.compute()
        posted = sorted(
            (row for row in rows if row["publishable"] and row["iso_week"] == 11),
            key=lambda row: row["rank"],
        )
        self.assertEqual([row["metric_id"] for row in posted], [KNAPPSTE, DEBATTE, LAENGSTE])
        self.assertEqual([row["rank"] for row in posted], [1, 2, 3])
        self.assertEqual({row["percentile"] for row in posted}, {1.0})

    def test_a_higher_percentile_outranks_a_lower_tie_rank(self) -> None:
        rows = [
            {"metric_id": LAENGSTE, "value": 9, "eligible": 1, "percentile": 0.95, "tie_rank": 4},
            {"metric_id": KNAPPSTE, "value": 0.1, "eligible": 1, "percentile": 0.9, "tie_rank": 1},
        ]
        self.assertEqual([row["metric_id"] for row in facts.rank_period(rows)], [LAENGSTE, KNAPPSTE])
        self.assertEqual([row["rank"] for row in rows], [1, 2])

    def test_a_week_below_the_floor_posts_nothing(self) -> None:
        self.seed(week_specs(3))
        rows = self.compute()
        self.assertFalse(any(row["publishable"] for row in rows))
        with tempfile.TemporaryDirectory() as cards:
            self.assertEqual(facts.write_cards(rows, Path(cards)), [])

    def test_ranks_are_contiguous_per_period(self) -> None:
        self.seed(week_specs(12))
        rows = self.compute()
        per_period: dict[tuple[str, str], list[int]] = {}
        for row in rows:
            if row["publishable"]:
                per_period.setdefault((row["period_kind"], row["period_key"]), []).append(row["rank"])
        self.assertTrue(per_period)
        for ranks in per_period.values():
            self.assertEqual(sorted(ranks), list(range(1, len(ranks) + 1)))


class CompletenessTests(StoreCase):
    def test_incomplete_week_is_excluded_from_facts_and_history(self) -> None:
        specs = week_specs(10)
        specs[4]["longest"] = 99_999
        specs[4]["complete"] = {"speeches": False}
        self.seed(specs)
        rows = self.rows_for(self.compute(), LAENGSTE)
        self.assertEqual(rows[4]["complete"], 0)
        self.assertIsNone(rows[4]["value"])
        self.assertEqual(rows[4]["eligible"], 0)
        # Week 6 (index 5) sees 4 prior complete weeks, not 5, and the 99 999
        # from the incomplete week never enters anyone's baseline.
        self.assertEqual(rows[5]["baseline_count"], 4)
        self.assertEqual(rows[9]["percentile"], 1.0)
        self.assertEqual(rows[9]["baseline_count"], 8)
        # Votes are untouched by a speech-side gap.
        self.assertEqual(self.rows_for(self.compute(), KNAPPSTE)[4]["complete"], 1)

    def test_completeness_map_from_cached_reports(self) -> None:
        reports = [
            {
                "protocol": {"dokumentnummer": "21/91"},
                "validation_summary": {"xml_speech_count": 10, "roll_call_vote_candidate_count": 0},
                "acquisition": {"votes": {"acquisition_state": "not_requested"}},
            },
            {
                "protocol": {"dokumentnummer": "21/90"},
                "validation_summary": {"xml_speech_count": 10, "roll_call_vote_candidate_count": 0},
                "acquisition": {"votes": {"acquisition_state": "complete"}},
            },
            {
                # Legacy report without an acquisition block (282 of 290 cached
                # reports on 2026-09-19): the cache carries no signal against
                # the votes the store holds, so votes count as complete.
                "protocol": {"dokumentnummer": "20/100"},
                "validation_summary": {"xml_speech_count": 10, "roll_call_vote_candidate_count": 3},
            },
            {
                "protocol": {"dokumentnummer": "20/99"},
                "validation_summary": {},
                "acquisition": {"votes": {"acquisition_state": "failed"}},
            },
        ]
        completeness = facts.completeness_from_reports(reports)
        self.assertEqual(completeness["21/91"], {"votes": False, "speeches": True})
        self.assertEqual(completeness["21/90"], {"votes": True, "speeches": True})
        self.assertEqual(completeness["20/100"], {"votes": True, "speeches": True})
        self.assertEqual(completeness["20/99"], {"votes": False, "speeches": False})

    def test_the_build_and_the_replay_derive_the_same_map(self) -> None:
        # D10: one function, fed the build's in-memory entries or the same
        # reports read back from data/plenarprotokoll-*.json.
        reports = [
            {
                "protocol": {"dokumentnummer": "21/90"},
                "validation_summary": {"xml_speech_count": 10},
                "acquisition": {"votes": {"acquisition_state": "complete"}},
            }
        ]
        entries = [{"report": reports[0], "report_path": "ignored"}]
        self.assertEqual(
            facts.completeness_from_entries(entries),
            facts.completeness_from_reports(reports),
        )

    def test_an_entry_without_a_report_is_skipped(self) -> None:
        self.assertEqual(facts.completeness_from_entries([{"report": None}, {}]), {})


# ---------------------------------------------------------------------------
# T5: the engine in the build.
# ---------------------------------------------------------------------------


class EngineTests(StoreCase):
    def store_all(self, specs=None, **kwargs):
        self.seed(specs or week_specs(12))
        conn = self.writable()
        report = facts.compute_and_store(
            conn, facts.REGISTRY, self.seeded["completeness"], out=quiet(), **kwargs
        )
        return conn, report

    def test_the_engine_writes_the_three_tables(self) -> None:
        conn, report = self.store_all()
        self.assertTrue(report["written"])
        metrics = facts.load_metrics(conn)
        self.assertEqual([m["id"] for m in metrics], [m["id"] for m in facts.REGISTRY])
        self.assertEqual(
            metrics[0]["sql_sha256"], facts.sql_sha256(facts.REGISTRY_BY_ID[metrics[0]["id"]])
        )
        stored = facts.load_facts(conn)
        self.assertEqual(len(stored), len(report["rows"]))
        posted = [row for row in stored if row["publishable"]]
        self.assertTrue(posted)
        self.assertEqual({row["period_kind"] for row in stored}, {"week"})
        for row in posted:
            self.assertGreaterEqual(row["rank"], 1)
            self.assertTrue(row["receipts"])

    def test_receipts_round_trip_with_their_fact(self) -> None:
        conn, _ = self.store_all()
        stored = {
            (row["period_key"], row["metric_id"]): row for row in facts.load_facts(conn)
        }
        computed = {
            (row["period_key"], row["metric_id"]): row for row in self.compute()
        }
        for key, row in computed.items():
            with self.subTest(fact=key):
                self.assertEqual(
                    [r["entity_kind"] for r in stored[key]["receipts"]],
                    [r["entity_kind"] for r in row["receipts"]],
                )
                self.assertEqual(
                    [r["rede_id"] for r in stored[key]["receipts"]],
                    [r["rede_id"] for r in row["receipts"]],
                )

    def test_a_second_run_on_an_unchanged_store_writes_nothing(self) -> None:
        conn, _ = self.store_all()
        conn.close()
        before = self.path.stat().st_mtime_ns
        again = sqlite3.connect(self.path)
        again.row_factory = sqlite3.Row
        try:
            report = facts.compute_and_store(
                again, facts.REGISTRY, self.seeded["completeness"], out=quiet()
            )
        finally:
            again.close()
        self.assertFalse(report["written"])
        self.assertEqual(self.path.stat().st_mtime_ns, before)

    def test_a_changed_value_rewrites_even_when_the_posted_facts_are_the_same(self) -> None:
        conn, _ = self.store_all()
        before = {
            (row["period_key"], row["metric_id"]): row["value"] for row in facts.load_facts(conn)
        }
        # Lengthen the runner-up speech of the last week: the same metric still
        # wins the same rank, but laengste-debatte's value moves.
        with conn:
            conn.execute(
                "UPDATE speeches SET char_count = char_count + 7 "
                "WHERE protocol_id = 'p12' AND rede_id = 'ID1200200'"
            )
        report = facts.compute_and_store(
            conn, facts.REGISTRY, self.seeded["completeness"], out=quiet()
        )
        self.assertTrue(report["written"])
        after = {
            (row["period_key"], row["metric_id"]): row["value"] for row in facts.load_facts(conn)
        }
        changed = {key for key in before if before[key] != after[key]}
        self.assertEqual(changed, {("2025-W14", DEBATTE)})
        # D11: the report names a week whose posted metric *or* value moved,
        # so a silent value correction still shows up in the build log.
        self.assertEqual(len(report["changed_winners"]), 1)
        self.assertIn("(3150)", report["changed_winners"][0])
        self.assertIn("(3157)", report["changed_winners"][0])

    def test_a_changed_posted_fact_is_reported(self) -> None:
        conn, _ = self.store_all()
        with conn:
            # A data correction that pushes the last week's longest speech
            # below every prior week: its card disappears.
            conn.execute("UPDATE speeches SET char_count = 1 WHERE protocol_id = 'p12'")
        report = facts.compute_and_store(
            conn, facts.REGISTRY, self.seeded["completeness"], out=quiet()
        )
        self.assertTrue(report["written"])
        self.assertEqual(len(report["changed_winners"]), 1)
        line = report["changed_winners"][0]
        self.assertTrue(line.startswith("2025-W14: "))
        self.assertIn(LAENGSTE, line)

    def test_a_crash_mid_write_leaves_the_previous_rows_intact(self) -> None:
        conn, _ = self.store_all()
        good = facts.read_snapshot(conn)
        broken = {key: list(values) for key, values in good.items()}
        # A duplicate (metric_id, period_kind, period_key) trips the UNIQUE
        # constraint after every earlier row has already been inserted.
        broken["facts"] = broken["facts"] + [broken["facts"][0]]
        with self.assertRaises(sqlite3.IntegrityError):
            facts.write_snapshot(conn, broken)
        self.assertEqual(facts.read_snapshot(conn), good)

    def test_no_persist_computes_without_writing(self) -> None:
        self.seed(week_specs(12))
        conn = self.writable()
        conn.close()
        before = self.path.stat().st_mtime_ns
        again = sqlite3.connect(self.path)
        again.row_factory = sqlite3.Row
        try:
            report = facts.compute_and_store(
                again,
                facts.REGISTRY,
                self.seeded["completeness"],
                no_persist=True,
                out=quiet(),
            )
            self.assertFalse(facts.tables_exist(again))
            self.assertEqual(facts.load_facts(again), [])
        finally:
            again.close()
        self.assertTrue(report["rows"])
        self.assertFalse(report["written"])
        self.assertEqual(self.path.stat().st_mtime_ns, before)

    def test_reading_a_store_without_the_tables_yields_an_empty_archive(self) -> None:
        self.seed(week_specs(2))
        self.assertIsNone(facts.read_snapshot(self.conn))
        self.assertEqual(facts.load_facts(self.conn), [])
        self.assertEqual(facts.load_metrics(self.conn), [])

    def test_a_metric_whose_sql_raises_aborts_the_engine_naming_the_metric(self) -> None:
        self.seed(week_specs(2))
        conn = self.writable()
        broken = tuple(
            {**metric, "sql": "SELECT * FROM nope"} if metric["id"] == SITZUNG else metric
            for metric in facts.REGISTRY
        )
        with self.assertRaises(facts.FactsError) as ctx:
            facts.compute_and_store(
                conn, broken, self.seeded["completeness"], out=quiet()
            )
        self.assertIn(SITZUNG, str(ctx.exception))
        self.assertFalse(facts.tables_exist(conn))

    def test_a_changed_metric_sql_rewrites_the_three_tables(self) -> None:
        conn, _ = self.store_all()
        relabelled = tuple(
            {**metric, "title": "Die allerlängste Rede der Woche"} if metric["id"] == LAENGSTE else metric
            for metric in facts.REGISTRY
        )
        report = facts.compute_and_store(
            conn, relabelled, self.seeded["completeness"], out=quiet()
        )
        self.assertTrue(report["written"])
        stored = {metric["id"]: metric for metric in facts.load_metrics(conn)}
        self.assertEqual(stored[LAENGSTE]["title"], "Die allerlängste Rede der Woche")

    def test_a_store_written_by_an_older_schema_is_rebuilt_not_read(self) -> None:
        # The engine owns these tables and rewrites all three as one unit, so a
        # leftover table from an earlier registry revision is dropped rather
        # than migrated. Without this a build against such a store would fail
        # with "no such column".
        conn, _ = self.store_all()
        with conn:
            conn.execute("ALTER TABLE facts DROP COLUMN withheld")
        self.assertFalse(facts.tables_exist(conn))
        self.assertIsNone(facts.read_snapshot(conn))
        self.assertEqual(facts.load_facts(conn), [])
        report = facts.compute_and_store(
            conn, facts.REGISTRY, self.seeded["completeness"], out=quiet()
        )
        self.assertTrue(report["written"])
        self.assertTrue(facts.tables_exist(conn))
        self.assertEqual(len(facts.load_facts(conn)), len(report["rows"]))

    def test_a_snapshot_round_trips_through_the_store(self) -> None:
        conn, _ = self.store_all()
        snapshot = facts.read_snapshot(conn)
        self.assertEqual(
            snapshot, facts.snapshot_from_rows(facts.REGISTRY, self.compute())
        )


# ---------------------------------------------------------------------------
# Card copy and the SVG card.
# ---------------------------------------------------------------------------


class CardTests(StoreCase):
    LONG_TITLE = (
        "Entschließungsantrag der Fraktionen SPD, CDU/CSU und BÜNDNIS 90/DIE GRÜNEN zu der "
        "Abgabe einer Regierungserklärung durch den Bundeskanzler zum Europäischen Rat"
    )

    def test_wrap_lines_caps_at_three_lines_with_a_word_boundary_ellipsis(self) -> None:
        words = [f"Wort{i}" for i in range(60)]
        lines = facts.wrap_lines(" ".join(words), width=30, max_lines=3)
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[-1].endswith("…"))
        kept = " ".join(lines)[:-1].split()
        self.assertEqual(kept, words[: len(kept)])
        self.assertTrue(all(len(line) <= 30 for line in lines))
        self.assertEqual(facts.wrap_lines("kurz", width=30, max_lines=3), ["kurz"])

    def test_card_wraps_the_longest_title_to_three_lines(self) -> None:
        self.assertGreaterEqual(len(self.LONG_TITLE), 140)
        specs = week_specs(9)
        specs[8]["votes"] = [(250, 249, self.LONG_TITLE)]
        self.seed(specs)
        winner = next(
            row for row in self.compute() if row["publishable"] and row["metric_id"] == KNAPPSTE
        )
        svg = facts.render_card(winner)
        root = ET.fromstring(svg)
        ns = {"svg": "http://www.w3.org/2000/svg"}
        title = root.find(".//svg:text[@class='title']", ns)
        spans = [span.text for span in title.findall("svg:tspan", ns)]
        self.assertLessEqual(len(spans), 3)
        self.assertTrue(spans[-1].endswith("…"))
        headline = root.find(".//svg:text[@class='headline']", ns)
        self.assertEqual("".join(headline.itertext()).strip(), "250 : 249")
        self.assertIn('font-family="Helvetica Neue, Arial, sans-serif"', svg)
        self.assertNotIn("<filter", svg)
        self.assertNotIn("Gradient", svg)

    def test_every_metric_renders_a_sentence_naming_its_population(self) -> None:
        specs = week_specs(9, speaker="Friedrich Merz", party="CDU/CSU")
        # Week 9's vote has to be the closest so far, or the min-direction
        # metric reads 0 % and its clause says so instead.
        specs[8]["closest"] = (250, 249)
        self.seed(specs)
        rows = self.compute()
        speech = self.rows_for(rows, LAENGSTE)[8]
        self.assertEqual(
            facts.card_sentence(speech),
            "Die längste Rede der Woche: 1.800 Zeichen von Friedrich Merz (CDU/CSU) "
            "zum Thema „Haushaltsbegleitgesetz 2027“, länger als 100 % der wöchentlichen "
            "Spitzenreden seit Beginn der 21. Wahlperiode.",
        )
        vote = self.rows_for(rows, KNAPPSTE)[8]
        self.assertTrue(
            facts.card_sentence(vote).startswith(
                "Die knappste Abstimmung der Woche: 250 zu 249 zu „Abstimmung 21/9“, knapper als "
            )
        )
        self.assertIn(
            "der wöchentlich knappsten Abstimmungen seit Beginn der 21. Wahlperiode.",
            facts.card_sentence(vote),
        )
        debate = self.rows_for(rows, DEBATTE)[8]
        self.assertIn("der wöchentlichen Spitzendebatten", facts.card_sentence(debate))
        # Every registered metric has its own population phrase.
        self.assertEqual(set(facts.POPULATION_PHRASES), set(facts.REGISTRY_BY_ID))

    def test_the_card_names_the_topic_of_the_speech(self) -> None:
        specs = week_specs(9)
        specs[8]["items"] = [{"heading": "TOP 1", "proceeding_title": "Bundeshaushalt 2027"}]
        self.seed(specs)
        speech = self.rows_for(self.compute(), LAENGSTE)[8]
        self.assertIn("zum Thema „Bundeshaushalt 2027“", facts.card_sentence(speech))

    def test_a_metric_caveat_renders_on_its_card(self) -> None:
        self.seed(
            [
                {
                    "document_number": "21/1",
                    "date": "2025-03-25",
                    "votes": [MeisteAbweichlerTests.VOTE],
                }
            ]
        )
        row = self.one(ABWEICHLER)
        self.assertEqual(facts.card_caveat(row), facts.REGISTRY_BY_ID[ABWEICHLER]["caveat"])
        svg = facts.render_card(row)
        root = ET.fromstring(svg)
        ns = {"svg": "http://www.w3.org/2000/svg"}
        caveat = root.find(".//svg:text[@class='caveat']", ns)
        self.assertIn("Gewissensfragen", "".join(caveat.itertext()))
        # laengste-rede states no caveat; the two vote metrics and erste-reden do.
        self.assertIsNone(facts.card_caveat({"metric_id": LAENGSTE}))
        self.assertEqual(
            {metric["id"] for metric in facts.REGISTRY if metric["caveat"]},
            set(facts.REQUIRED_CAVEATS),
        )

    def test_one_svg_per_posted_fact_byte_identical_on_rerun(self) -> None:
        self.seed(week_specs(12))
        rows = self.compute()
        with tempfile.TemporaryDirectory() as cards:
            first = facts.write_cards(rows, Path(cards))
            self.assertGreaterEqual(len(first), 1)
            bytes_first = {path.name: path.read_bytes() for path in first}
            second = facts.write_cards(rows, Path(cards))
            bytes_second = {path.name: path.read_bytes() for path in second}
        self.assertEqual(bytes_first, bytes_second)
        # D21: one card per posted fact, named <period_key>-<metric_id>.svg.
        self.assertEqual(
            sorted(bytes_first),
            sorted(
                f"2025-W{week:02d}-{metric}.svg"
                for week in range(11, 15)
                for metric in (DEBATTE, LAENGSTE)
            ),
        )


class ReplayTests(StoreCase):
    def test_replay_is_read_only_and_reports_the_gate_and_floor_numbers(self) -> None:
        self.seed(week_specs(12))
        self.conn.close()
        before = self.path.stat().st_mtime_ns
        with tempfile.TemporaryDirectory() as cards:
            report = facts.replay(
                self.path,
                weeks=5,
                cards_dir=Path(cards),
                completeness=self.seeded["completeness"],
            )
            self.assertEqual(len(list(Path(cards).glob("*.svg"))), 8)
        self.assertEqual(self.path.stat().st_mtime_ns, before)
        self.assertEqual(len(report["weeks"]), 5)
        gate = report["gate"]
        self.assertEqual(gate["weeks_with_a_fact"], 4)
        self.assertEqual(gate["cards_total"], 8)
        self.assertEqual({entry["floor"] for entry in gate["floor_table"]}, {0.25, 0.50, 0.75})
        for entry in gate["floor_table"]:
            self.assertLessEqual(entry["weeks"], len(report["weeks"]))
        self.assertIn("max_cards_per_speaker", gate)
        self.assertIn("posted_per_metric", gate)
        self.assertIn("changed_wp_vs_all", gate)
        self.assertEqual(len(gate["recent_cards"]), 8)

    def test_print_report_renders_every_metric_column(self) -> None:
        self.seed(week_specs(12))
        self.conn.close()
        report = facts.replay(
            self.path, weeks=3, cards_dir=None, completeness=self.seeded["completeness"]
        )
        out = io.StringIO()
        facts.print_report(report, out=out)
        text = out.getvalue()
        for tag in facts._SHORT_METRIC.values():
            self.assertIn(f"{tag}_value", text)
        self.assertIn("floor 0.50", text)

    @unittest.skipUnless(REAL_STORE.exists(), "real store not present")
    def test_real_store_replay(self) -> None:
        with tempfile.TemporaryDirectory() as cards:
            report = facts.replay(REAL_STORE, weeks=5, cards_dir=Path(cards))
        self.assertEqual(len(report["weeks"]), 5)


if __name__ == "__main__":
    unittest.main()
