from __future__ import annotations

import unittest
from argparse import Namespace
from unittest import mock

import _support  # noqa: F401
import validate_dip_protocol as dip
from _support import FIXTURES


class ValidateDipProtocolHelperTests(unittest.TestCase):
    def test_build_report_fetches_protocol_when_none_is_preloaded(self) -> None:
        protocol = {
            "id": "5805",
            "dokumentnummer": "21/87",
            "fundstelle": {"xml_url": "https://example.test/protocol.xml"},
        }
        args = Namespace(
            api_key="test-key",
            sleep=0,
            protocol_id="5805",
            document_number=None,
            person_limit=0,
            vote_scan_pages=0,
            roll_call_list_id=None,
            limit_tops=None,
        )
        parsed_xml = {"xml_protocol": {}, "agenda_items": []}
        enrichment = {
            "agenda_items": [],
            "api_totals": {},
            "warnings": [],
            "sampled_people": [],
            "api_records": {},
        }

        with (
            mock.patch.object(dip, "find_protocol", return_value=protocol) as find_protocol,
            mock.patch.object(dip, "fetch_text", return_value="<xml />"),
            mock.patch.object(dip, "parse_protocol_xml", return_value=parsed_xml),
            mock.patch.object(dip, "enrich_with_api", return_value=enrichment),
            mock.patch.object(dip, "enrich_with_llm_summaries"),
        ):
            report = dip.build_report(args)

        find_protocol.assert_called_once()
        _, protocol_id, document_number = find_protocol.call_args.args
        self.assertEqual(protocol_id, "5805")
        self.assertIsNone(document_number)
        self.assertEqual(report["protocol"]["id"], "5805")

    def test_build_report_uses_preloaded_protocol_without_refetching_it(self) -> None:
        protocol = {
            "id": "5805",
            "dokumentnummer": "21/87",
            "fundstelle": {"xml_url": "https://example.test/protocol.xml"},
        }
        args = Namespace(
            api_key="test-key",
            sleep=0,
            protocol_id="5805",
            document_number=None,
            person_limit=0,
            vote_scan_pages=0,
            roll_call_list_id=None,
            limit_tops=None,
        )
        parsed_xml = {"xml_protocol": {}, "agenda_items": []}
        enrichment = {
            "agenda_items": [],
            "api_totals": {},
            "warnings": [],
            "sampled_people": [],
            "api_records": {},
        }

        with (
            mock.patch.object(dip, "find_protocol") as find_protocol,
            mock.patch.object(dip, "fetch_text", return_value="<xml />"),
            mock.patch.object(dip, "parse_protocol_xml", return_value=parsed_xml),
            mock.patch.object(dip, "enrich_with_api", return_value=enrichment),
            mock.patch.object(dip, "enrich_with_llm_summaries"),
        ):
            report = dip.build_report(args, protocol=protocol)

        find_protocol.assert_not_called()
        self.assertEqual(report["protocol"]["id"], "5805")

    def test_vote_helpers(self) -> None:
        counts = dip.vote_counts_from_csv("10, 5, 2, 1")
        self.assertEqual(counts, {"yes": 10, "no": 5, "abstain": 2, "absent": 1})
        self.assertEqual(dip.vote_total(counts), 18)
        self.assertEqual(dip.leading_vote(counts), "yes")
        self.assertEqual(dip.leading_vote({"yes": 0, "no": 0, "abstain": 0, "absent": 9}), "absent")

    def test_text_date_and_faction_helpers(self) -> None:
        self.assertEqual(dip.normalize_faction("B90/GRÜNE"), "BÜNDNIS 90/DIE GRÜNEN")
        self.assertEqual(dip.normalize_faction("LINKE"), "Die Linke")
        self.assertEqual(dip.normalize_faction("Fraktionslose"), "fraktionslos")
        self.assertEqual(dip.iso_date("15.05.2024"), "2024-05-15")
        self.assertEqual(dip.iso_date("2024-05-15"), "2024-05-15")
        self.assertIsNone(dip.iso_date("15/05/2024"))
        self.assertEqual(dip.clamp_text("  eins   zwei drei  ", 9), "eins zwe" + "\u2026")

    def test_title_and_position_matching_helpers(self) -> None:
        self.assertEqual(dip.norm_title("Test: Gesetz 20/123!"), "test gesetz 20 123")
        self.assertTrue(dip.title_matches("TOP 1 Beratung Testgesetz", "Beratung Testgesetz"))
        self.assertTrue(
            dip.title_matches(
                "Gesetz zur Modernisierung der digitalen Verwaltung und Infrastruktur",
                "Modernisierung digitale Verwaltung Infrastruktur",
            )
        )
        self.assertFalse(dip.title_matches("Haushalt", "Verkehr Infrastruktur"))

        top = {"page_range": {"start": {"page": 5}, "end": {"page": 7}}}
        self.assertTrue(dip.overlaps(top, {"fundstelle": {"anfangsseite": "7", "endseite": "8"}}))
        self.assertFalse(dip.overlaps(top, {"fundstelle": {"anfangsseite": "8", "endseite": "9"}}))
        self.assertTrue(dip.activity_in_top({"fundstelle": {"seite": "6"}}, top))
        self.assertFalse(dip.activity_in_top({"fundstelle": {"seite": "8"}}, top))


class ValidateDipProtocolParserTests(unittest.TestCase):
    def test_parse_protocol_xml_extracts_agenda_speeches_and_pages(self) -> None:
        parsed = dip.parse_protocol_xml((FIXTURES / "protocol.xml").read_text(encoding="utf-8"))

        self.assertEqual(parsed["xml_protocol"]["wahlperiode"], "20")
        self.assertEqual(len(parsed["agenda_items"]), 2)

        first = parsed["agenda_items"][0]
        self.assertEqual(first["top_id"], "T1")
        self.assertEqual(first["heading"], "TOP 1 Beratung Testgesetz")
        self.assertEqual(first["page_range"]["start"], {"page": 101, "quadrant": "A"})
        self.assertEqual(first["page_range"]["end"], {"page": 102, "quadrant": "C"})
        self.assertEqual(len(first["speeches"]), 2)
        self.assertEqual(first["speeches"][0]["speaker"]["display_name"], "Dr. Ada Lovelace")
        self.assertEqual(first["speeches"][0]["paragraph_count"], 2)
        self.assertIn("Zweiter Absatz", first["speeches"][0]["text"])

        second = parsed["agenda_items"][1]
        self.assertEqual(second["page_range"]["start"], {"page": 103, "quadrant": "B"})
        self.assertEqual(second["speeches"][0]["speaker"]["last_name"], "Kontrolle")

    def test_parse_roll_call_list_page(self) -> None:
        entries = dip.parse_roll_call_list_page((FIXTURES / "roll_call_list.html").read_text(encoding="utf-8"))

        self.assertEqual(len(entries), 1)
        vote = entries[0]
        self.assertEqual(vote["id"], "12345")
        self.assertEqual(vote["date"], "2024-05-15")
        self.assertEqual(vote["document_numbers"], ["20/123", "20/456"])
        self.assertEqual(vote["total"], {"yes": 10, "no": 5, "abstain": 2, "absent": 1})

    def test_parse_member_votes_maps_vote_keys(self) -> None:
        members = dip.parse_member_votes((FIXTURES / "member_votes.html").read_text(encoding="utf-8"))

        self.assertEqual(
            {member["name"]: member["vote"] for member in members},
            {
                "Ada Lovelace": "yes",
                "Bruno Beispiel": "no",
                "Clara Kontrolle": "abstain",
                "Dora Abwesend": "absent",
            },
        )
        self.assertEqual(members[0]["faction"], "SPD")
        self.assertTrue(members[0]["profile_url"].endswith("/abgeordnete/ada-lovelace"))


if __name__ == "__main__":
    unittest.main()
