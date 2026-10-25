"""What a roll-call vote was about, read from the chair's announcements in the
Plenarprotokoll, and one interpretation for every copy of a vote, online and on replay.

The XML fixture holds the chair's paragraphs verbatim from 20/157 (vote 906), 20/66
(votes 809-811), 20/194 (vote 926) and 21/83 (vote 1005), cached on 2026-10-23; the vote
fixture holds their roll-call listing fields. Sources, hashes and editing:
tests/fixtures/vote_interpretation_sources.json. See docs/plans/fix-vote-interpretation.md.
"""
from __future__ import annotations

import contextlib
import copy
import csv
import gzip
import hashlib
import io
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import build_dip_pulse_site as build
import derive
import speech_kinds
import validate_dip_protocol as dip
from _support import FIXTURES
from _votes_fixture import vote_summary

LEGEND = "Ja = Antrag ablehnen · Nein = Antrag annehmen"
EXCERPT_906 = (
    "Der Ausschuss empfiehlt in seiner Beschlussempfehlung auf der Drucksache 20/10433, "
    "den Antrag der Unionsfraktion auf der Drucksache 20/9143 abzulehnen."
)
PROTOCOL_XML = (FIXTURES / "vote_interpretation_protocol.xml").read_text(encoding="utf-8")
VOTES = json.loads((FIXTURES / "vote_interpretation_votes.json").read_text(encoding="utf-8"))
INTERPRETATION_KEYS = (
    "inverted", "inversion_source", "inversion_excerpt", "procedure_type",
    "result_raw", "result_source", "result_scope",
)


def vote(vote_id: str, **fields) -> dict:
    return {**copy.deepcopy(VOTES[vote_id]), **fields}


def recommendations() -> list[dict]:
    return dip.parse_vote_recommendations(dip.ET.fromstring(PROTOCOL_XML))


def interpret(votes: list[dict], records: list[dict] | None) -> list[dict]:
    dip.interpret_sitting_votes([{"votes": votes}], [], records)
    return votes


def record(direction: str, antrag: list[str], recommendation: list[str]) -> dict:
    return {"top_id": "T", "paragraph": 0, "direction": direction, "antrag_numbers": antrag,
            "recommendation_numbers": recommendation, "excerpt": f"{direction} {antrag}"}


class ChairAnnouncementTests(unittest.TestCase):
    # Value: protects=adjacent chair evidence without speech or TOP leakage;
    # fails_when=paragraphs lose recommendation identity or cross a speaker boundary;
    # why_new=existing fixture announcements each fit one paragraph; seam=none;
    # no_claim=fixture parsing, not current external availability.
    def test_adjacent_chair_paragraphs_share_only_uninterrupted_recommendation_evidence(self) -> None:
        announcement = '<p klasse="J">Wir stimmen über die Beschlussempfehlung auf Drucksache 20/20 ab.</p>'
        direction = '<p klasse="J">Der Ausschuss empfiehlt, den Antrag auf Drucksache 20/10 abzulehnen.</p>'
        for label, body, expected in (
            ("adjacent", announcement + direction, True),
            ("split sentence", '<p klasse="J">Der Ausschuss empfiehlt in seiner Beschlussempfehlung auf Drucksache 20/20,</p>'
             '<p klasse="J">den Antrag auf Drucksache 20/10 abzulehnen.</p>', True),
            ("speech boundary", announcement + '<rede><p klasse="redner">Abgeordneter X</p><p>Ein Redebeitrag.</p></rede>' + direction, None),
            ("TOP boundary", announcement + '</tagesordnungspunkt><tagesordnungspunkt top-id="T2">' + direction, None),
            ("negated continuation", announcement + direction.replace("abzulehnen", "nicht abzulehnen"), None),
        ):
            with self.subTest(label=label):
                xml = '<dbtplenarprotokoll><sitzungsverlauf><tagesordnungspunkt top-id="T1">' + body + '</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>'
                records = dip.parse_vote_recommendations(dip.ET.fromstring(xml))
                item = {"id": "1", "title": "Klimaschutz", "document_numbers": ["20/20", "20/10"]}
                interpret([item], records)
                self.assertIs(item["inverted"], expected)
                if expected:
                    self.assertEqual(item["inversion_source"], "bundestag-protocol")
                    self.assertEqual(records[0]["recommendation_numbers"], ["20/20"])

    def test_only_the_chairs_announcements_about_an_antrag_are_read(self) -> None:
        records = recommendations()
        self.assertEqual(
            [(r["direction"], r["antrag_numbers"], r["recommendation_numbers"]) for r in records],
            [
                ("reject", ["20/9143"], ["20/10433"]),
                ("reject", ["20/3943"], ["20/4360"]),
                ("reject", ["20/4053"], ["20/4360"]),
                # "Zusatzpunkt 3. Abstimmung ..." reads as an ordinal, not a sentence end:
                # the merged sentence still yields this one record.
                ("reject", ["21/2234"], ["21/5130"]),
            ],
        )
        # The speech and the annex repeat "lehne den Antrag ... ab" and "den Antrag ... anzunehmen";
        # the Gesetzentwurf announcements (accepted in 20/66, rejected in 20/194) name no Antrag.
        text = " ".join(r["excerpt"] for r in records)
        self.assertNotIn("lehne den Antrag", text)
        self.assertNotIn("20/11752", text)
        self.assertEqual(records[0]["excerpt"], EXCERPT_906)

    def test_the_wording_around_a_recommendation_is_read_clause_by_clause(self) -> None:
        def parse(paragraph: str) -> list[dict]:
            xml = (
                '<dbtplenarprotokoll wahlperiode="20" sitzung-nr="1"><sitzungsverlauf>'
                f'<tagesordnungspunkt top-id="T1"><p klasse="J">{paragraph}</p></tagesordnungspunkt>'
                "</sitzungsverlauf></dbtplenarprotokoll>"
            )
            return dip.parse_vote_recommendations(dip.ET.fromstring(xml))

        # Gesetzentwurf accepted and Antrag rejected in one sentence: two clauses, one record.
        both = parse(
            "Der Ausschuss empfiehlt unter Buchstabe a seiner Beschlussempfehlung auf Drucksache 20/1, den Gesetzentwurf "
            "auf Drucksache 20/2 anzunehmen, und unter Buchstabe b den Antrag der Fraktion X auf Drucksache 20/3 abzulehnen."
        )
        self.assertEqual([(r["direction"], r["antrag_numbers"], r["recommendation_numbers"]) for r in both],
                         [("reject", ["20/3"], ["20/1"])])
        # Accepting and rejecting the same Antrag, and a negation, are conflicts, never rejections.
        for paragraph in (
            "Der Ausschuss empfiehlt in seiner Beschlussempfehlung auf Drucksache 20/1, den Antrag auf Drucksache 20/3 anzunehmen und abzulehnen.",
            "Der Ausschuss empfiehlt in seiner Beschlussempfehlung auf Drucksache 20/1, den Antrag auf Drucksache 20/3 nicht abzulehnen.",
        ):
            with self.subTest(paragraph=paragraph):
                self.assertEqual([r["direction"] for r in parse(paragraph)], ["conflict"])
        # "empfiehlt" without an Antrag, or a quoted title that ends in a period, adds nothing.
        self.assertEqual(parse("Der Ausschuss empfiehlt, den Gesetzentwurf auf Drucksache 20/2 abzulehnen."), [])
        titled = parse(
            "Wir setzen fort. Der Ausschuss empfiehlt die Ablehnung des Antrags auf Drucksache 20/3 mit dem Titel „Noch mehr. Und mehr“."
        )
        self.assertEqual([r["antrag_numbers"] for r in titled], [["20/3"]])
        # The words of a quoted title are not the chair's: "Kein ..." negates nothing.
        negated_title = parse(
            "Der Ausschuss empfiehlt in seiner Beschlussempfehlung auf Drucksache 20/1 die Ablehnung des Antrags "
            "auf Drucksache 20/3 mit dem Titel „Kein Heizungsgesetz durch die Hintertür – CO2-Bepreisung nicht abschaffen“."
        )
        self.assertEqual([(r["direction"], r["antrag_numbers"]) for r in negated_title], [("reject", ["20/3"])])
        self.assertIn("Kein Heizungsgesetz", negated_title[0]["excerpt"])
        # The dative plural names Anträge too.
        plural = parse("Der Ausschuss empfiehlt in seiner Beschlussempfehlung auf Drucksache 20/1, den Anträgen auf Drucksachen 20/3 und 20/4 nicht zu folgen und sie abzulehnen.")
        self.assertEqual([(r["direction"], r["antrag_numbers"]) for r in plural], [("conflict", ["20/3", "20/4"])])

    def test_wording_the_parser_cannot_split_stays_conservative(self) -> None:
        def parse(paragraph: str) -> list[dict]:
            xml = (
                '<dbtplenarprotokoll wahlperiode="20" sitzung-nr="1"><sitzungsverlauf>'
                f'<tagesordnungspunkt top-id="T1"><p klasse="J">{paragraph}</p></tagesordnungspunkt>'
                "</sitzungsverlauf></dbtplenarprotokoll>"
            )
            return dip.parse_vote_recommendations(dip.ET.fromstring(xml))

        # Clauses split only at "unter Buchstabe" and ";": an accept and a reject joined by
        # a plain "und" stay one clause, a conflict for both Anträge, never a rejection.
        joined = parse(
            "Der Ausschuss empfiehlt in seiner Beschlussempfehlung auf Drucksache 20/1, den Antrag auf Drucksache 20/3 "
            "abzulehnen und den Antrag auf Drucksache 20/4 anzunehmen."
        )
        self.assertEqual([(r["direction"], r["antrag_numbers"]) for r in joined], [("conflict", ["20/3", "20/4"])])
        # A sentence ending in a number reads as an ordinal ("12. Der ..."): the two sentences merge,
        # the earlier Drucksache joins the recommendation's, and no vote fits the record.
        merged = parse(
            "Abgestimmt wird über Drucksache 20/9 unter Nummer 12. Der Ausschuss empfiehlt in seiner "
            "Beschlussempfehlung auf Drucksache 20/1, den Antrag auf Drucksache 20/3 abzulehnen."
        )
        self.assertEqual([r["recommendation_numbers"] for r in merged], [["20/9", "20/1"]])
        (unfit,) = interpret([{"id": "1", "title": "Beschlussempfehlung", "document_numbers": ["20/1", "20/3"]}], merged)
        self.assertIsNone(unfit["inverted"])

    def test_vote_906_is_inverted_from_the_announcement(self) -> None:
        (taurus,) = interpret([vote("906")], recommendations())
        self.assertTrue(taurus["inverted"])
        self.assertEqual(taurus["inversion_source"], "bundestag-protocol")
        self.assertEqual(taurus["inversion_excerpt"], EXCERPT_906)
        # 494 Ja, 188 Nein: the recommendation to reject was accepted, so the Antrag was rejected.
        self.assertEqual((taurus["result_raw"], taurus["result_source"]), ("accepted", "derived"))
        self.assertEqual(derive.vote_outcome(taurus), "rejected")
        panel = vote_summary({"votes": [taurus]})
        self.assertIn(LEGEND, panel)
        self.assertIn("Antrag: Abgelehnt", panel)
        self.assertNotIn("Kein Ergebnis verfügbar", panel)
        self.assertEqual(taurus["total"], VOTES["906"]["total"])
        # The groups' positions are told against the Antrag; raw counts and Abweichler are unchanged.
        self.assertIn("gegen den Antrag", panel)
        self.assertNotIn("für den Antrag", panel)  # FDP and Gruppe BSW voted for the recommendation
        self.assertIn("Kubicki", panel)
        self.assertIn("Strack-Zimmermann", panel)
        self.assertEqual(taurus["fractions"], VOTES["906"]["fractions"])

    def test_vote_1005_shows_the_antrag_outcome_instead_of_no_result(self) -> None:
        (bafoeg,) = interpret([vote("1005")], recommendations())
        self.assertEqual((bafoeg["inverted"], bafoeg["inversion_source"]), (True, "bundestag-protocol"))
        self.assertIn("Drucksache 21/5130, den Antrag der Fraktion Bündnis 90/Die Grünen auf Drucksache 21/2234", bafoeg["inversion_excerpt"])
        self.assertEqual((bafoeg["result_raw"], bafoeg["result_source"]), ("accepted", "derived"))
        panel = vote_summary({"votes": [bafoeg]})
        self.assertIn(LEGEND, panel)
        self.assertIn("Antrag: Abgelehnt", panel)
        self.assertNotIn("Kein Ergebnis verfügbar", panel)

    def test_an_announcement_proves_an_inversion_only_for_a_vote_on_the_recommendation(self) -> None:
        # The Antrag's number alone fits a vote on the Antrag itself just as well.
        unnamed = [record("reject", ["20/10"], [])]
        on_the_antrag = {"id": "1", "title": "Klimaschutz (Antrag)", "document_numbers": ["20/10"],
                         "description": "Namentliche Abstimmung über den Antrag der AfD (Drucksache 20/10)"}
        (antrag_vote,) = interpret([on_the_antrag], unnamed)
        self.assertEqual((antrag_vote["inverted"], antrag_vote["inversion_source"]), (None, None))
        self.assertEqual(antrag_vote["result_raw"], None)  # no tally in this sketch
        unknown = {"id": "2", "title": "Klimaschutz", "document_numbers": ["20/10", "20/20"]}
        self.assertEqual(dip.protocol_recommendation_evidence(unknown, unnamed, [unknown]), ("conflict", None))
        # A listing that opens with the Beschlussempfehlung (915, 958, 1001, 1002, 1004), or an
        # announcement naming its Drucksache among the vote's (1003), shows the recommendation.
        listed = {"id": "3", "title": "x", "description": "Beschlussempfehlung des Ausschusses zu dem Antrag", "document_numbers": ["20/10", "20/20"]}
        self.assertEqual(dip.protocol_recommendation_evidence(listed, unnamed, [listed])[0], "reject")
        named = [record("reject", ["20/10"], ["20/20"])]
        self.assertEqual(dip.protocol_recommendation_evidence(unknown, named, [unknown])[0], "reject")

    def test_a_described_vorlage_is_recognised_behind_the_beschreibung_prefix(self) -> None:
        for description, expected in (
            ("Beschreibung: Beschlussempfehlung des Ausschusses", "beschlussempfehlung"),
            ("Beschreibung: Antrag der Fraktion X", "vorlage"),
            ("Teile des Gesetzentwurfs der Bundesregierung", "vorlage"),
        ):
            with self.subTest(description):
                self.assertEqual(dip._abstimmungsgegenstand({"description": description}), expected)

    def test_a_bundled_announcement_is_attributed_by_its_documents(self) -> None:
        # 809-811 share Drucksache 20/4360; the announcement names the Antrag 20/4053 of 811 only.
        votes = {vote_id: vote(vote_id) for vote_id in ("809", "810", "811")}
        interpret(list(votes.values()), recommendations())
        self.assertTrue(votes["811"]["inverted"])
        self.assertIn("Buchstabe d", votes["811"]["inversion_excerpt"])
        for vote_id in ("809", "810"):
            self.assertIsNone(votes[vote_id]["inverted"], vote_id)
            self.assertIsNone(votes[vote_id]["inversion_source"], vote_id)

    def test_a_rejected_gesetzentwurf_is_not_an_inversion_even_under_a_misleading_title(self) -> None:
        control = vote("926")
        interpret([control], recommendations())
        self.assertIsNone(control["inverted"])
        # The listing names the Vorlage itself: a title or DIP text saying "Ablehnung eines Antrags" cannot override it.
        misleading = vote("926", title="Ablehnung eines Antrags")
        documents = [{"dokumentnummer": "20/13044", "titel": "Ablehnung des Antrags", "drucksachetyp": "Beschlussempfehlung"}]
        dip.interpret_vote(misleading, documents=documents)
        self.assertIsNone(misleading["inverted"])
        # The outcome is the Gesetzentwurf's, not inverted.
        self.assertEqual(derive.vote_outcome({**misleading, "result_raw": "accepted"}), "accepted")

    def test_conflicting_or_shared_announcements_leave_the_direction_unknown(self) -> None:
        numbers = ["20/10", "20/20"]
        for label, records in (
            ("accepted instead", [record("accept", ["20/10"], ["20/20"])]),
            ("rejected and accepted", [record("reject", ["20/10"], ["20/20"]), record("accept", ["20/10"], ["20/20"])]),
            ("a conflict", [record("conflict", ["20/10"], ["20/20"])]),
        ):
            with self.subTest(label):
                (single,) = interpret([{"id": "1", "title": "Beschlussempfehlung", "document_numbers": numbers}], records)
                self.assertIsNone(single["inverted"])
        # One announcement that fits two votes of the sitting belongs to neither.
        twins = interpret(
            [{"id": "1", "title": "Beschlussempfehlung", "document_numbers": numbers},
             {"id": "2", "title": "Beschlussempfehlung", "document_numbers": numbers}],
            [record("reject", ["20/10"], ["20/20"])],
        )
        self.assertEqual([twin["inverted"] for twin in twins], [None, None])
        # ...unless the other one is a vote on a Vorlage.
        votes = interpret(
            [{"id": "1", "title": "Beschlussempfehlung", "document_numbers": numbers},
             {"id": "2", "title": "x", "description": "Antrag der Fraktion X", "document_numbers": numbers}],
            [record("reject", ["20/10"], ["20/20"])],
        )
        self.assertEqual([item["inverted"] for item in votes], [True, None])

    def test_an_announcement_naming_other_documents_is_no_evidence(self) -> None:
        (single,) = interpret(
            [{"id": "1", "title": "Beschlussempfehlung", "document_numbers": ["20/10", "20/20"]}],
            [record("reject", ["20/10", "20/99"], ["20/20"]), record("reject", ["20/10"], ["20/98"])],
        )
        self.assertIsNone(single["inverted"])

    def test_the_title_evidence_is_the_fallback_and_never_overrides_the_announcement(self) -> None:
        titled = {"id": "1", "title": "Ablehnung eines Antrags", "document_numbers": ["20/10", "20/20"]}
        (without,) = interpret([copy.deepcopy(titled)], [])
        self.assertTrue(without["inverted"])
        self.assertEqual(without["inversion_source"], "bundestag-roll-call")
        (accepted,) = interpret([copy.deepcopy(titled)], [record("accept", ["20/10"], ["20/20"])])
        self.assertIsNone(accepted["inverted"])
        (rejected,) = interpret([copy.deepcopy(titled)], [record("reject", ["20/10"], ["20/20"])])
        self.assertEqual(rejected["inversion_source"], "bundestag-protocol")
        # Protocol evidence of a rejection does not outvote a DIP text that accepts the Antrag.
        contradicted = copy.deepcopy(titled)
        dip.interpret_vote(
            contradicted, documents=[{"dokumentnummer": "20/10", "titel": "Annahme des Antrags"}],
            protocol_evidence=("reject", record("reject", ["20/10"], ["20/20"])),
        )
        self.assertIsNone(contradicted["inverted"])


class CopiesAndReplayTests(unittest.TestCase):
    # Value: protects=one evidence-based interpretation for every duplicate vote;
    # fails_when=a sparse first copy hides later document evidence or conflicting text;
    # why_new=existing duplicates differed only in official-result fields; seam=none;
    # no_claim=report interpretation on local fixtures, not live acquisition.
    def test_later_copy_evidence_is_shared_without_ignoring_conflicts(self) -> None:
        for label, later_fields, expected in (
            ("complete later copy", {}, True),
            ("conflicting title", {"title": "Annahme des Antrags"}, None),
            ("direct Vorlage", {"description": "Antrag der Fraktion X"}, None),
        ):
            with self.subTest(label=label):
                first = vote("906", document_numbers=[], description="Eine namentliche Abstimmung")
                later = vote("906", **later_fields)
                before_counts = copy.deepcopy([first["total"], later["total"]])
                interpret([first, later], recommendations())
                self.assertIs(first["inverted"], expected)
                self.assertIs(later["inverted"], expected)
                self.assertEqual({key: first.get(key) for key in INTERPRETATION_KEYS},
                                 {key: later.get(key) for key in INTERPRETATION_KEYS})
                self.assertEqual([first["total"], later["total"]], before_counts)

    def test_every_copy_of_a_vote_gets_one_interpretation_and_a_second_pass_changes_nothing(self) -> None:
        official = vote("996", official_result="rejected", result_scope="application")
        bare = vote("996")  # a copy after JSON reload that lost the official fields
        elsewhere = vote("906")
        dip.interpret_sitting_votes(
            [{"votes": [bare]}, {"votes": [official, elsewhere]}], [copy.deepcopy(bare)], recommendations()
        )
        first = [{key: item.get(key) for key in (*INTERPRETATION_KEYS, "official_result")} for item in (bare, official)]
        self.assertEqual(first[0], first[1])
        self.assertEqual(first[0]["result_source"], "official")
        self.assertEqual(first[0]["result_scope"], "application")
        self.assertEqual(derive.vote_outcome(bare), "rejected")
        self.assertTrue(bare["inverted"])  # 996's title: "Ablehnung eines Antrags ..."
        before = copy.deepcopy([bare, official, elsewhere])
        dip.interpret_sitting_votes(
            [{"votes": [bare]}, {"votes": [official, elsewhere]}], [], recommendations()
        )
        self.assertEqual([bare, official, elsewhere], before)

    def test_without_the_xml_a_protocol_inversion_is_kept_and_a_present_xml_decides_again(self) -> None:
        stored = interpret([vote("906")], recommendations())[0]
        self.assertTrue(stored["inverted"])
        # A report whose XML is gone is read again from what it holds: the inversion stays.
        interpret([stored], None)
        self.assertTrue(stored["inverted"])
        self.assertEqual(stored["inversion_source"], "bundestag-protocol")
        self.assertEqual(derive.vote_outcome(stored), "rejected")
        # ...also over a title that would invert it on its own (1005: "Ablehnung eines Antrags ...").
        bafoeg = interpret([vote("1005")], recommendations())[0]
        interpret([bafoeg], None)
        self.assertEqual((bafoeg["inverted"], bafoeg["inversion_source"]), (True, "bundestag-protocol"))
        self.assertIn("21/5130", bafoeg["inversion_excerpt"])
        # A present XML is the source: one that now accepts the Antrag, or announces nothing
        # attributable, decides on its own. The plan's "missing source evidence must not silently
        # clear" is the missing XML above (docs/plans/fix-vote-interpretation.md, step 4).
        for label, records in (("accepts", [record("accept", ["20/9143"], ["20/10433"])]), ("silent", [])):
            with self.subTest(label):
                again = copy.deepcopy(stored)
                interpret([again], records)
                self.assertIsNone(again["inverted"])
                self.assertIsNone(again["inversion_source"])

    def test_special_majority_votes_stay_unknown_without_an_official_result(self) -> None:
        amendment = {"id": "9", "title": "Beschlussempfehlung", "document_numbers": ["20/1"], "total": {"yes": 400, "no": 200}}
        interpret([amendment], [])
        self.assertEqual((amendment["result_raw"], amendment["result_source"]), ("accepted", "derived"))
        item = {
            "votes": [amendment],
            "api": {
                "linked_drucksachen": [{"vorgang_id": "V", "dokumentnummer": "20/1", "titel": "Antrag", "drucksachetyp": "Antrag"}],
                "raw": {"positions": [{"vorgang_id": "V", "titel": "Entwurf eines Gesetzes zur Änderung des Grundgesetzes", "vorgangstyp": "Gesetzgebung"}]},
            },
        }
        dip.interpret_sitting_votes([item], [], [])
        self.assertEqual(amendment["procedure_type"], "constitutional_amendment")
        self.assertEqual((amendment["result_raw"], amendment["result_source"]), (None, None))


class OnlineAndReplayAgreeTests(unittest.TestCase):
    """The votes an online enrichment interprets and the same report replayed from its
    saved JSON and cached XML end up with identical interpretation. Only the page fetch
    is faked: the detail fetch reads 996's real Beschluss section."""

    def setUp(self) -> None:
        positions = [{
            "id": "p1", "vorgang_id": "V1", "vorgangstyp": "Antrag", "titel": "Antrag der Fraktion der CDU/CSU Taurus",
            "vorgangsposition": "Beschlussempfehlung", "dokumentart": "Drucksache", "fundstelle": {"seite": "20084"},
            "mitberaten": [{"id": "V2", "titel": "Entwurf eines Gesetzes zur Änderung des Grundgesetzes", "vorgangstyp": "Gesetzgebung"}],
        }]
        documents = {
            "V1": [self.document("V1", "20/10433", "Beschlussempfehlung und Bericht", "Beschlussempfehlung"),
                   self.document("V1", "20/9143", "Antrag", "Antrag")],
            "V2": [self.document("V2", "20/7777", "Gesetzentwurf", "Gesetzentwurf")],
        }

        class FakeClient:
            def list_all(self, path: str, params: dict[str, str]) -> list:
                if path == "/vorgangsposition" and "f.vorgang" in params:
                    return documents[params["f.vorgang"]]
                return positions if path == "/vorgangsposition" else []

        self.client = FakeClient()
        taurus = vote("906")
        amendment = {"id": "9001", "date": "2024-03-14", "title": "Grundgesetz", "description": "Beschlussempfehlung zum Gesetzentwurf",
                     "document_numbers": ["20/7777"], "total": {"yes": 500, "no": 100, "abstain": 0, "absent": 0}}
        # 996 names no Drucksache of this sitting's TOPs: a sitting-level vote.
        einbuergerung = {key: value for key, value in vote("996", date="2024-03-14").items() if key not in ("fractions", "members")}
        self.candidates = [taurus, amendment, einbuergerung]
        self.page_996 = (FIXTURES / "roll_call_detail_996.html").read_text(encoding="utf-8")

    @staticmethod
    def document(vorgang: str, number: str, kind: str, position: str) -> dict:
        return {"id": f"{vorgang}-{number}", "vorgang_id": vorgang, "dokumentart": "Drucksache", "vorgangsposition": position,
                "titel": f"{kind} {number}", "fundstelle": {"dokumentnummer": number, "drucksachetyp": kind, "herausgeber": "BT"}}

    def enrich(self, parsed: dict) -> dict:
        def fetch_html(url: str) -> str:
            # The detail page of 996; every other page (details, member and Namenslisten) is empty.
            return self.page_996 if url == dip.roll_call_vote_url("996") else ""

        fetch = dip.RollCallCandidateFetch(self.candidates, True, 3, False, scan_end="date_passed")
        dip._namenslisten_entries = None
        self.addCleanup(setattr, dip, "_namenslisten_entries", None)
        with contextlib.redirect_stderr(io.StringIO()), \
                mock.patch.object(dip, "fetch_roll_call_vote_candidates", return_value=fetch), \
                mock.patch.object(dip, "fetch_html", side_effect=fetch_html), \
                mock.patch.object(dip, "overlaps", return_value=True):
            return dip.enrich_with_api(
                self.client, {"id": "157", "dokumentnummer": "20/157", "datum": "2024-03-14"},  # type: ignore[arg-type]
                parsed, person_limit=0, vote_scan_pages=1,
            )

    def test_a_replay_of_the_saved_report_interprets_every_vote_as_the_online_build_did(self) -> None:
        parsed = dip.parse_protocol_xml(PROTOCOL_XML)
        online = self.enrich(parsed)

        def copies(report: dict) -> list[dict]:
            records = report["api_records"]
            return [*(v for item in report["agenda_items"] for v in item["votes"]), *report["sitting_votes"],
                    *records["sitting_votes"], *records["matched_roll_call_votes"]]

        self.assertEqual({v["id"] for item in online["agenda_items"] for v in item["votes"]}, {"906", "9001"})
        self.assertEqual([v["id"] for v in online["sitting_votes"]], ["996"])
        online_values = {v["id"]: {key: v.get(key) for key in INTERPRETATION_KEYS} for v in copies(online)}
        # Every online copy of a vote holds the same interpretation, the matched list's too.
        for vote_ in copies(online):
            self.assertEqual({key: vote_.get(key) for key in INTERPRETATION_KEYS}, online_values[vote_["id"]], vote_["id"])
        self.assertTrue(online_values["906"]["inverted"])
        self.assertEqual(online_values["9001"]["procedure_type"], "constitutional_amendment")
        # 996: the page's own Antrag outcome, scoped to the Antrag, not inverted a second time.
        self.assertEqual({key: online_values["996"][key] for key in ("inverted", "result_raw", "result_source", "result_scope")},
                         {"inverted": True, "result_raw": "rejected", "result_source": "official", "result_scope": "application"})
        saved = json.loads(json.dumps({key: online[key] for key in ("agenda_items", "sitting_votes", "api_records")}))
        # A replay starts from what an older build stored: no interpretation at all, except the
        # official result of the page, which a replay cannot fetch again.
        for vote_ in copies(saved):
            for key in INTERPRETATION_KEYS:
                if not (vote_["id"] == "996" and key in ("result_raw", "result_source", "result_scope")):
                    vote_.pop(key, None)
            vote_.pop("official_result", None)
        dip.interpret_report_votes(saved, parsed["vote_recommendations"])
        for vote_ in copies(saved):
            self.assertEqual({key: vote_.get(key) for key in INTERPRETATION_KEYS}, online_values[vote_["id"]], vote_["id"])


FIELDS = ("inverted", "inversion_source", "inversion_excerpt", "result_raw", "result_source", "result_scope")


class RepairedReportsTests(unittest.TestCase):
    """A report cached before votes were interpreted, replayed with ``--offline --repersist``:
    the saved JSON, the store, the export and the panels agree, vote by vote."""

    @classmethod
    def legacy_report(cls) -> dict:
        def legacy(vote_id: str, **fields) -> dict:
            return {key: value for key, value in vote(vote_id, **fields).items()
                    if key not in (*INTERPRETATION_KEYS, "official_result")}

        def top(index: int, top_id: str, votes: list[dict]) -> dict:
            return {"index": index, "top_id": top_id, "heading": top_id, "votes": votes}

        recorded = legacy("996")  # an official Antrag result an earlier targeted refresh stored
        recorded.update(official_result="rejected", result_raw="rejected", result_source="official", result_scope="application")
        return {
            "protocol": {"id": "pp-157", "dokumentnummer": "20/157", "datum": "2024-03-14", "titel": "Plenarprotokoll 20/157"},
            "sampled_people": [],
            "agenda_items": [
                top(1, "Tagesordnungspunkt 7", [legacy("906")]),
                top(2, "Tagesordnungspunkt 10", [legacy("811"), legacy("810")]),
                top(3, "Tagesordnungspunkt 8", [legacy("1005")]),
                top(4, "Tagesordnungspunkt 12", [legacy("811"), legacy("926")]),  # 811 under a second TOP too
            ],
            "api_records": {"sitting_votes": [recorded]},
        }

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.output_dir = Path(self._tmp.name) / "site"
        (self.output_dir / "data" / "xml").mkdir(parents=True)
        (self.output_dir / "protocols").mkdir()
        self.database = self.output_dir / "data" / "bundestag-pulse.sqlite"
        (self.output_dir / "data" / "xml" / "plenarprotokoll-20-157.xml").write_text(PROTOCOL_XML, encoding="utf-8")
        self.report_path = self.output_dir / "data" / "plenarprotokoll-20-157.json"
        self.report_path.write_text(json.dumps(self.legacy_report()), encoding="utf-8")

    def repersist(self) -> tuple[list[dict], object]:
        protocols = build.load_cached_protocols(self.output_dir)
        with contextlib.redirect_stderr(io.StringIO()):
            entries, rebuilt = build.repersist_cached_reports(self.output_dir, self.database, protocols)
            build.rebuild_cached_detail_pages(self.output_dir, protocols, cached_entries=entries)
        return entries, rebuilt

    def stored_votes(self) -> dict[str, dict]:
        conn = sqlite3.connect(self.database)
        conn.row_factory = sqlite3.Row
        try:
            return {row["id"]: dict(row) for row in conn.execute(f"SELECT id, {', '.join(FIELDS)}, yes_count, no_count FROM votes")}
        finally:
            conn.close()

    def saved_votes(self) -> dict[str, list[dict]]:
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        found: dict[str, list[dict]] = {}
        for item in report["agenda_items"]:
            for saved in item["votes"]:
                found.setdefault(saved["id"], []).append(saved)
        for saved in report.get("sitting_votes") or []:
            found.setdefault(saved["id"], []).append(saved)
        return found

    def test_a_legacy_report_the_store_the_export_and_the_panels_agree(self) -> None:
        self.assertFalse(self.database.exists())
        entries, _ = self.repersist()
        saved = self.saved_votes()
        stored = self.stored_votes()
        self.assertEqual(set(saved), {"906", "811", "810", "926", "996", "1005"})
        self.assertEqual(len(saved["811"]), 2)
        # Every copy of a vote in the saved JSON holds the same interpretation, and the store holds it too.
        for vote_id, copies in saved.items():
            values = [{field: copy_.get(field) for field in FIELDS} for copy_ in copies]
            self.assertTrue(all(value == values[0] for value in values), vote_id)
            expected = {**values[0], "inverted": None if values[0]["inverted"] is None else int(values[0]["inverted"])}
            self.assertEqual({field: stored[vote_id][field] for field in FIELDS}, expected, vote_id)
        by_id = {vote_id: copies[0] for vote_id, copies in saved.items()}
        # The announcements recover 906, 811 and 1005; the Gesetzentwürfe 810 and 926 stay uninverted.
        self.assertEqual({vote_id for vote_id, item in by_id.items() if item["inverted"]}, {"906", "811", "996", "1005"})
        for vote_id in ("906", "811", "1005"):
            self.assertEqual(by_id[vote_id]["inversion_source"], "bundestag-protocol", vote_id)
        self.assertEqual(by_id["906"]["inversion_excerpt"], EXCERPT_906)
        self.assertTrue(by_id["811"]["inversion_excerpt"].startswith("Der Ausschuss empfiehlt unter Buchstabe d"))
        self.assertEqual(by_id["996"]["inversion_source"], "bundestag-roll-call")  # no announcement in the cached XML
        # A derived result stays derived; the recorded official Antrag result and its scope survive.
        self.assertEqual((by_id["906"]["result_raw"], by_id["906"]["result_source"], by_id["906"]["result_scope"]),
                         ("accepted", "derived", "proposition"))
        self.assertEqual((by_id["996"]["result_raw"], by_id["996"]["result_source"], by_id["996"]["result_scope"]),
                         ("rejected", "official", "application"))
        # Final counts are untouched, the groups' and the members' too.
        self.assertEqual({vote_id: (row["yes_count"], row["no_count"]) for vote_id, row in stored.items()}, {
            vote_id: (VOTES[vote_id]["total"]["yes"], VOTES[vote_id]["total"]["no"]) for vote_id in stored})
        conn = sqlite3.connect(self.database)
        try:
            fraction_counts = sorted(conn.execute(
                "SELECT yes_count, no_count, abstain_count, absent_count FROM vote_fractions WHERE vote_id = '906'"))
            member_votes = sorted(row[0] for row in conn.execute("SELECT vote FROM vote_members WHERE vote_id = '906'"))
        finally:
            conn.close()
        self.assertEqual(fraction_counts, sorted(
            (f["counts"]["yes"], f["counts"]["no"], f["counts"]["abstain"], f["counts"]["absent"]) for f in VOTES["906"]["fractions"]))
        self.assertEqual(member_votes, sorted(member["vote"] for member in VOTES["906"]["members"]))
        # The downloadable distribution carries the same values: the SQLite copy and the votes CSV.
        with contextlib.redirect_stderr(io.StringIO()):
            manifest = build.export_distribution_data(
                self.database, self.output_dir / "exports", mp_lookup={}, readiness={"votes": "ready"},
                catalog_count=1, dossier_count=1, license_text="", commit="test",
            )
        generation = self.output_dir / "exports" / manifest["generation"]
        sqlite_gz = next(f["name"] for f in manifest["files"] if f["name"].endswith(".sqlite.gz"))
        unpacked = Path(self._tmp.name) / "distribution.sqlite"
        with gzip.open(generation / sqlite_gz, "rb") as source:
            unpacked.write_bytes(source.read())
        conn = sqlite3.connect(unpacked)
        try:
            distributed = {row[0]: row[1:] for row in conn.execute(f"SELECT id, {', '.join(FIELDS)} FROM votes")}
        finally:
            conn.close()
        csv_name = next(f["name"] for f in manifest["files"] if f["name"].startswith("votes-") and f["name"].endswith(".csv.gz"))
        with gzip.open(generation / csv_name, "rt", encoding="utf-8", newline="") as handle:
            exported = {row["id"]: row for row in csv.DictReader(handle)}
        for vote_id, row in stored.items():
            self.assertEqual(distributed[vote_id], tuple(row[field] for field in FIELDS), vote_id)
            for field in FIELDS:
                self.assertEqual(exported[vote_id][field], "" if row[field] is None else str(row[field]), (vote_id, field))
        # The dossier panels show the legend and the Antrag's outcome in every occurrence of an inverted vote only...
        page = (self.output_dir / "protocols" / "plenarprotokoll-20-157.html").read_text(encoding="utf-8")
        inverted_occurrences = sum(len(copies) for vote_id, copies in saved.items() if by_id[vote_id]["inverted"])
        self.assertEqual(page.count(LEGEND), inverted_occurrences)
        self.assertEqual(page.count("Antrag: Abgelehnt"), inverted_occurrences)
        self.assertNotIn("Kein Ergebnis verfügbar", page)
        # 906's groups are told against the Antrag, with FDP's two Abweichler named.
        self.assertEqual(page.count(">gegen den Antrag<"), 2)
        self.assertIn("Kubicki", page)
        self.assertIn("Strack-Zimmermann", page)
        # ...and so do the archive rows, where a computed result stays marked.
        archive = build.render_votes_archive_index(build.collect_votes_archive(entries))

        def badge(vote_id: str) -> str:
            row = re.search(rf'#vote-{vote_id}">.*?</h3>', archive, re.S).group(0)
            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row.split("</a>", 1)[1])).strip()

        self.assertEqual(badge("906"), "Antrag: Abgelehnt (berechnet)")
        self.assertEqual(badge("811"), "Antrag: Abgelehnt (berechnet)")
        self.assertEqual(badge("1005"), "Antrag: Abgelehnt (berechnet)")
        self.assertEqual(badge("996"), "Antrag: Abgelehnt")
        self.assertEqual(badge("810"), "Angenommen (berechnet)")
        self.assertEqual(badge("926"), "Abgelehnt (berechnet)")

    def test_a_second_repair_changes_nothing(self) -> None:
        self.repersist()
        first = {"saved": self.saved_votes(), "stored": self.stored_votes(), "report": self.report_path.read_bytes()}
        _, rebuilt = self.repersist()
        self.assertFalse(rebuilt.replaced)
        self.assertEqual({"saved": self.saved_votes(), "stored": self.stored_votes(), "report": self.report_path.read_bytes()}, first)

    def test_a_report_without_cached_xml_keeps_what_the_announcement_gave_it(self) -> None:
        self.repersist()
        (self.output_dir / "data" / "xml" / "plenarprotokoll-20-157.xml").unlink()
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        report["validation_summary"] = {"speech_kinds_version": speech_kinds.VERSION}
        self.report_path.write_text(json.dumps(report), encoding="utf-8")
        before = self.stored_votes()
        self.repersist()
        self.assertEqual(self.stored_votes(), before)
        self.assertEqual(before["906"]["inversion_source"], "bundestag-protocol")

    def test_a_cached_xml_of_another_sitting_stops_the_repair_and_leaves_the_store_alone(self) -> None:
        self.repersist()
        stored = self.stored_votes()
        digest = hashlib.sha256(self.database.read_bytes()).hexdigest()
        saved = self.report_path.read_bytes()
        xml = self.output_dir / "data" / "xml" / "plenarprotokoll-20-157.xml"
        xml.write_text(PROTOCOL_XML.replace('sitzung-nr="157"', 'sitzung-nr="158"'), encoding="utf-8")
        with self.assertRaises(build.CachedReportError), contextlib.redirect_stderr(io.StringIO()):
            build.repersist_cached_reports(self.output_dir, self.database, build.load_cached_protocols(self.output_dir))
        self.assertEqual(hashlib.sha256(self.database.read_bytes()).hexdigest(), digest)
        self.assertEqual(self.stored_votes(), stored)
        self.assertEqual(self.report_path.read_bytes(), saved)


if __name__ == "__main__":
    unittest.main()
