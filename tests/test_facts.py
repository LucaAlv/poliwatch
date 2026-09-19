"""Fakt der Woche, A0: the rule as pure functions, the replay, the SVG card.

One test per rule and per edge in the plan's "Failure modes" table
(~/.gstack/projects/LucaAlv-poliwatch/fakt-der-woche-plan.md, D1-D19).
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import _support  # noqa: F401
import _facts_fixture
import facts


REAL_STORE = _support.ROOT / ".context" / "dip-pulse-site" / "data" / "bundestag-pulse.sqlite"

KNAPPSTE = "knappste-abstimmung"
LAENGSTE = "laengste-rede"


def week_specs(count: int, *, start_number: int = 1, wp: int = 21, year: int = 2025, **extra):
    """count consecutive ISO weeks in ``wp``; the longest speech grows with the
    week (1000, 1100, ...) so every week beats all prior ones by default."""
    specs = []
    for index in range(count):
        # Wednesdays from the 3rd ISO week of ``year`` (all on distinct weeks).
        day = facts.date.fromisocalendar(year, 3 + index, 3)
        spec = {
            "document_number": f"{wp}/{start_number + index}",
            "date": day.isoformat(),
            "longest": 1000 + 100 * index,
            "closest": (300 + index, 200),
        }
        spec.update(extra)
        specs.append(spec)
    return specs


class StoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "store.sqlite"

    def seed(self, weeks):
        self.seeded = _facts_fixture.seed_weeks(self.path, weeks)
        self.conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        return self.seeded

    def compute(self, built=("votes",), registry=facts.REGISTRY):
        return facts.compute(
            self.conn, registry, self.seeded["completeness"], built=set(built)
        )

    @staticmethod
    def rows_for(rows, metric_id):
        return [row for row in rows if row["metric_id"] == metric_id]


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
        self.assertEqual([p["document_number"] for p in weeks[0].protocols], ["21/91", "21/92"])

    def test_malformed_document_number_names_the_protocol(self) -> None:
        with self.assertRaises(facts.FactsError) as ctx:
            facts.sitting_weeks([{"id": "p1", "document_number": "Plenarprotokoll 21", "date": "2026-09-08"}])
        self.assertIn("Plenarprotokoll 21", str(ctx.exception))


class ObserveTests(StoreCase):
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
        rows = self.rows_for(self.compute(), LAENGSTE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["value"], 400)
        self.assertEqual(rows[0]["week_n"], 1)

    def test_week_without_a_vote_yields_no_observation(self) -> None:
        self.seed(
            [
                {"document_number": "21/1", "date": "2025-03-25", "unlinked_votes": [(300, 299, "lose")]},
            ]
        )
        rows = self.rows_for(self.compute(), KNAPPSTE)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["value"])
        self.assertEqual(rows[0]["week_n"], 0)
        self.assertEqual(rows[0]["eligible"], 0)

    def test_vote_with_zero_denominator_is_excluded(self) -> None:
        self.seed(
            [
                {
                    "document_number": "21/1",
                    "date": "2025-03-25",
                    "votes": [(0, 0, "leer"), (300, 200, "voll")],
                }
            ]
        )
        rows = self.rows_for(self.compute(), KNAPPSTE)
        self.assertEqual(rows[0]["week_n"], 1)
        self.assertAlmostEqual(rows[0]["value"], 100 / 500)
        self.assertEqual(rows[0]["denominator"], 500)

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
        speech = self.rows_for(rows, LAENGSTE)[0]
        self.assertEqual(speech["citation"]["id"], seeded["speech_ids"]["21/1"][0])
        vote = self.rows_for(rows, KNAPPSTE)[0]
        self.assertEqual(vote["citation"]["id"], seeded["vote_ids"]["21/1"][0])

    def test_depends_on_skips_an_unbuilt_metric(self) -> None:
        self.seed(week_specs(2))
        rows = self.compute(built=())
        self.assertEqual(self.rows_for(rows, KNAPPSTE), [])
        self.assertEqual(len(self.rows_for(rows, LAENGSTE)), 2)


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


class SelectWinnerTests(StoreCase):
    def test_metric_tie_breaks_by_tie_rank(self) -> None:
        # Week 9 is both the closest vote and the longest speech so far: both
        # metrics read 100 %; knappste-abstimmung (tie_rank 1) wins.
        specs = week_specs(9)
        specs[8]["closest"] = (250, 249)
        self.seed(specs)
        rows = self.compute()
        selected = [row for row in rows if row["selected"] and row["iso_week"] == 11]
        self.assertEqual([row["metric_id"] for row in selected], [KNAPPSTE])
        self.assertEqual(facts.select_winner(
            [
                {"metric_id": LAENGSTE, "eligible": 1, "percentile": 0.9, "tie_rank": 2},
                {"metric_id": KNAPPSTE, "eligible": 1, "percentile": 0.9, "tie_rank": 1},
            ]
        ), KNAPPSTE)

    def test_higher_percentile_wins_regardless_of_tie_rank(self) -> None:
        self.assertEqual(facts.select_winner(
            [
                {"metric_id": LAENGSTE, "eligible": 1, "percentile": 0.95, "tie_rank": 2},
                {"metric_id": KNAPPSTE, "eligible": 1, "percentile": 0.9, "tie_rank": 1},
            ]
        ), LAENGSTE)

    def test_no_eligible_metric_means_no_winner(self) -> None:
        self.assertIsNone(facts.select_winner(
            [{"metric_id": LAENGSTE, "eligible": 0, "percentile": None, "tie_rank": 2}]
        ))
        self.seed(week_specs(3))
        rows = self.compute()
        self.assertFalse(any(row["selected"] for row in rows))
        with tempfile.TemporaryDirectory() as cards:
            written = facts.write_cards(rows, Path(cards))
        self.assertEqual(written, [])

    def test_selected_is_unique_per_week(self) -> None:
        self.seed(week_specs(12))
        rows = self.compute()
        per_week = {}
        for row in rows:
            if row["selected"]:
                per_week[(row["iso_year"], row["iso_week"])] = per_week.get((row["iso_year"], row["iso_week"]), 0) + 1
        self.assertTrue(per_week)
        self.assertEqual(set(per_week.values()), {1})


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


class ReceiptTests(StoreCase):
    def test_receipt_keys_document_number_and_rede_id_or_page_anchor(self) -> None:
        self.seed(
            [
                {
                    "document_number": "21/1",
                    "date": "2025-03-25",
                    "speeches": [(900, "Ada Lovelace", "ID2100100"), (100, "Karl Marx", "ID2100200")],
                    "votes": [(300, 200, "Antrag")],
                },
                {
                    "document_number": "21/2",
                    "date": "2025-04-02",
                    "speeches": [(950, "Ada Lovelace", None), (100, "Karl Marx", "ID2200200")],
                },
            ]
        )
        rows = self.compute()
        speech_rows = self.rows_for(rows, LAENGSTE)
        real = speech_rows[0]["receipts"]
        self.assertEqual(
            [(r["entity_kind"], r["document_number"], r["rede_id"], r["page"], r["page_quadrant"]) for r in real],
            [("speech", "21/1", "ID2100100", None, None)],
        )
        synthetic = speech_rows[1]["receipts"]
        self.assertEqual(
            [(r["entity_kind"], r["document_number"], r["rede_id"], r["page"], r["page_quadrant"]) for r in synthetic],
            [("speech", "21/2", None, 1001, "B")],
        )
        vote = self.rows_for(rows, KNAPPSTE)[0]["receipts"]
        self.assertEqual(vote[0]["entity_kind"], "vote")
        self.assertEqual(vote[0]["document_number"], "21/1")
        self.assertEqual(vote[0]["official_url"], "https://example.test/abstimmung/v10")
        self.assertEqual(vote[0]["position"], 0)


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
        rows = self.compute()
        winner = [row for row in rows if row["selected"]][-1]
        self.assertEqual(winner["metric_id"], KNAPPSTE)
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

    def test_card_sentence_names_its_population(self) -> None:
        specs = week_specs(9, speaker="Friedrich Merz", party="CDU/CSU")
        self.seed(specs)
        rows = self.compute()
        speech = self.rows_for(rows, LAENGSTE)[8]
        self.assertEqual(
            facts.card_sentence(speech),
            "Die längste Rede der Woche: 1.800 Zeichen von Friedrich Merz (CDU/CSU), "
            "länger als 100 % der wöchentlichen Spitzenreden seit Beginn der 21. Wahlperiode.",
        )
        vote = self.rows_for(rows, KNAPPSTE)[8]
        self.assertTrue(facts.card_sentence(vote).startswith("Die knappste Abstimmung der Woche: 308 zu 200 zu „Abstimmung 21/9“, knapper als "))
        self.assertIn("der wöchentlich knappsten Abstimmungen seit Beginn der 21. Wahlperiode.", facts.card_sentence(vote))

    def test_svg_is_byte_identical_on_rerun(self) -> None:
        self.seed(week_specs(12))
        rows = self.compute()
        with tempfile.TemporaryDirectory() as cards:
            first = facts.write_cards(rows, Path(cards))
            self.assertGreaterEqual(len(first), 1)
            bytes_first = {path.name: path.read_bytes() for path in first}
            second = facts.write_cards(rows, Path(cards))
            bytes_second = {path.name: path.read_bytes() for path in second}
        self.assertEqual(bytes_first, bytes_second)
        self.assertEqual(sorted(bytes_first), sorted(f"2025-W{w:02d}.svg" for w in range(11, 15)))


class ReplayTests(StoreCase):
    def test_replay_is_read_only_and_reports_gate_numbers(self) -> None:
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
            self.assertEqual(len(list(Path(cards).glob("*.svg"))), 4)
        self.assertEqual(self.path.stat().st_mtime_ns, before)
        self.assertEqual(len(report["weeks"]), 5)
        gate = report["gate"]
        self.assertIn("max_cards_per_speaker", gate)
        self.assertIn("wins_per_metric", gate)
        self.assertIn("changed_wp_vs_all", gate)
        self.assertIn("winners_vs_week_n", gate)
        self.assertEqual(len(gate["recent_cards"]), 4)

    @unittest.skipUnless(REAL_STORE.exists(), "real store not present")
    def test_real_store_replay(self) -> None:
        with tempfile.TemporaryDirectory() as cards:
            report = facts.replay(REAL_STORE, weeks=5, cards_dir=Path(cards))
        self.assertEqual(len(report["weeks"]), 5)


if __name__ == "__main__":
    unittest.main()
