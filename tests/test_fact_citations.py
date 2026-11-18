"""A fact's citation is found by the id its receipt carries, not by a page.

An agenda item or a speech without a printed page has a NULL page, which
"page = ?" never matches and "page IS ?" would tie across the page-less rows of
one protocol (found by tests/test_code_rules.py, class 5, 2026-11-18).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401
import build_dip_pulse_site as build
import facts
from test_facts import DEBATTE, LAENGSTE, VORGANG, StoreCase, quiet, week_specs


class CitationByIdTests(StoreCase):
    def compute_into_store(self) -> None:
        conn = self.writable()
        facts.compute_and_store(
            conn, facts.REGISTRY, self.seeded["completeness"], catalog=self.seeded["catalog"], built={"votes"}, out=quiet()
        )
        conn.close()

    def test_a_page_less_agenda_item_that_wins_a_fact_still_renders_it(self) -> None:
        weeks = week_specs(9)
        self.seed(weeks)
        conn = self.writable()
        conn.execute("UPDATE agenda_items SET page_start = NULL, page_start_quadrant = NULL")
        conn.commit()
        conn.close()
        self.compute_into_store()
        output_dir = Path(self.tmp.name) / "site"
        output_dir.mkdir()
        build.write_facts_pages(output_dir, self.path, {}, {spec["document_number"] for spec in weeks}, set())
        html = (output_dir / "fakt" / "2025-W11.html").read_text(encoding="utf-8")
        self.assertIn('<section id="laengste-debatte"', html)
        self.assertIn("Haushaltsbegleitgesetz 2027", html)
        self.assertNotIn("nicht mehr auffindbar", html)

    def test_two_page_less_items_of_one_protocol_resolve_to_their_own_rows(self) -> None:
        self.seed(
            [
                {
                    "document_number": "21/1",
                    "date": "2025-06-03",
                    "items": [
                        {"heading": "TOP 1", "proceeding_title": "Antrag A", "proceeding_id": "VA"},
                        {"heading": "TOP 2", "proceeding_title": "Gesetz C", "proceeding_id": "VC"},
                    ],
                    "speeches": [(100, "Ada Lovelace", "IDA1"), (100, "Karl Marx", "IDK1"), (100, "Ada Lovelace", "IDA2")],
                }
            ]
        )
        conn = self.writable()
        conn.execute("UPDATE agenda_items SET page_start = NULL, page_start_quadrant = NULL")
        conn.commit()
        conn.close()
        build._ensure_lead_position_tables(self.conn)
        ids = [r[0] for r in self.conn.execute("SELECT id FROM agenda_items ORDER BY id")]
        self.assertEqual(len(ids), 2)
        found = [build._fact_agenda_item_citation(self.conn, "21/1", item_id) for item_id in ids]
        self.assertEqual([row["id"] for row in found], ids)
        self.assertEqual([row["heading"] for row in found], ["TOP 1", "TOP 2"])

    def test_a_page_less_vorgang_receipt_resolves_by_the_agenda_item_id(self) -> None:
        self.seed(
            [
                {
                    "document_number": "21/1",
                    "date": "2025-06-03",
                    "items": [{"heading": "TOP 1", "proceeding_title": "Gesetz C", "proceeding_id": "VC"}],
                    "speeches": [(100, "Ada Lovelace", "IDA1"), (100, "Karl Marx", "IDK1")],
                }
            ]
        )
        conn = self.writable()
        conn.execute("UPDATE agenda_items SET page_start = NULL, page_start_quadrant = NULL")
        conn.commit()
        conn.close()
        row = self.one(VORGANG, registry=facts.MONTHLY_REGISTRY)
        receipt = row["receipts"][0]
        self.assertIsNone(receipt["page"])
        build._ensure_lead_position_tables(self.conn)
        cited = build._fact_proceeding_citation(self.conn, receipt["document_number"], receipt["source_entity_id"])
        self.assertEqual(cited["title"], "Gesetz C")

    def test_a_synthetic_rede_id_speech_without_a_page_resolves_by_the_speech_id(self) -> None:
        self.seed(
            [
                {
                    "document_number": "21/2",
                    "date": "2025-04-02",
                    "speeches": [(950, "Ada Lovelace", None), (100, "Karl Marx", "ID2200200")],
                }
            ]
        )
        conn = self.writable()
        conn.execute("UPDATE speeches SET page = NULL, page_quadrant = NULL")
        conn.commit()
        conn.close()
        receipt = self.one(LAENGSTE)["receipts"][0]
        self.assertIsNone(receipt["rede_id"])
        self.assertIsNone(receipt["page"])
        build._ensure_lead_position_tables(self.conn)
        cited = build._fact_speech_citation(self.conn, receipt["document_number"], receipt["rede_id"], receipt["source_entity_id"])
        self.assertEqual(cited["display_name"], "Ada Lovelace")
        self.assertEqual(cited["id"], receipt["source_entity_id"])

    def test_a_receipt_without_an_id_does_not_resolve(self) -> None:
        self.seed(week_specs(1))
        build._ensure_lead_position_tables(self.conn)
        self.assertIsNone(build._fact_agenda_item_citation(self.conn, "21/1", None))
        self.assertIsNone(build._fact_proceeding_citation(self.conn, "21/1", None))
        self.assertIsNone(build._fact_speech_citation(self.conn, "21/1", None, None))

    def test_an_id_from_another_protocol_does_not_resolve(self) -> None:
        self.seed(week_specs(2))
        build._ensure_lead_position_tables(self.conn)
        item_id = self.conn.execute(
            "SELECT ai.id FROM agenda_items ai JOIN protocols p ON p.id = ai.protocol_id WHERE p.document_number = '21/1'"
        ).fetchone()[0]
        self.assertIsNone(build._fact_agenda_item_citation(self.conn, "21/2", item_id))


if __name__ == "__main__":
    unittest.main()
