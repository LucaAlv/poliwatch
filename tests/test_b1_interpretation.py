"""B1 regression evidence: vote 1002, official page retrieved 2026-09-30.

The JSON fixture preserves the heading and chart counts, with a shortened description.
"""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import _support
import derive
import validate_dip_protocol as dip
from features import votes


class InterpretationTests(unittest.TestCase):
    def test_official_1002_fixture(self):
        vote = json.loads((Path(__file__).parent / 'fixtures/roll_call_1002.json').read_text())
        raw = copy.deepcopy(vote['total'])
        dip.interpret_vote(vote)
        self.assertTrue(vote['inverted'])
        self.assertEqual(vote['result_raw'], 'accepted')
        self.assertEqual(derive.vote_outcome(vote), 'rejected')
        self.assertEqual(vote['total'], raw)
        panel = votes.render_vote_summary({'votes': [vote]})
        self.assertIn('Ja = Antrag ablehnen · Nein = Antrag annehmen', panel)
        self.assertIn('Antrag: Abgelehnt', panel)
        self.assertIn('gegen den Antrag', panel)
        self.assertIn('für den Antrag', panel)

    def test_unknown_and_mixed_evidence(self):
        for title in ('Beschlussempfehlung zum Antrag', 'Antrag zur Ablehnung einer Steuer'):
            self.assertIsNone(dip.recommendation_inversion({'title': title})[0])
        vote = {'title': 'Beschlussempfehlung', 'document_numbers': ['21/123']}
        for document in (
            {'dokumentnummer': '21/999', 'titel': 'Den Antrag abzulehnen'},
            {'dokumentnummer': '21/123', 'titel': 'Den Antrag 21/999 abzulehnen'},
            {'dokumentnummer': '21/123', 'titel': 'Den Antrag abzulehnen und den Antrag anzunehmen'},
        ):
            self.assertIsNone(dip.recommendation_inversion(vote, [document])[0])
        self.assertTrue(dip.recommendation_inversion(vote, [{'dokumentnummer': '21/123', 'titel': 'Den Antrag 21/123 abzulehnen'}])[0])

    def test_official_application_not_inverted_twice(self):
        vote = {'title': 'Ablehnung eines Antrags', 'total': {'yes': 449, 'no': 136},
                'official_result': 'rejected', 'result_scope': 'application'}
        for _ in range(2):
            dip.interpret_vote(vote)
            self.assertEqual(vote['result_raw'], 'accepted')
            self.assertEqual(derive.vote_outcome(vote), 'rejected')
            self.assertEqual(vote['result_scope'], 'proposition')

    def test_conflicting_matched_documents_stay_unknown_in_either_order(self):
        vote = {'title': 'Beschlussempfehlung', 'document_numbers': ['20/100', '20/200']}
        documents = [
            {'dokumentnummer': '20/100', 'titel': 'Beschlussempfehlung zur Ablehnung des Antrags'},
            {'dokumentnummer': '20/200', 'titel': 'Beschlussempfehlung zur Annahme des Antrags'},
        ]
        for ordered in (documents, list(reversed(documents))):
            self.assertEqual(dip.recommendation_inversion(vote, ordered), (None, None, None))

    def test_conflicting_vote_fields_and_mixed_document_stay_unknown(self):
        self.assertEqual(dip.recommendation_inversion({
            'title': 'Ablehnung des Antrags', 'description': 'Den Antrag anzunehmen'
        }), (None, None, None))
        self.assertEqual(dip.recommendation_inversion(
            {'document_numbers': ['20/100', '20/200']},
            [
                {'dokumentnummer': '20/100', 'titel': 'Den Antrag abzulehnen'},
                {'dokumentnummer': '20/200', 'titel': 'Den Antrag abzulehnen und den Antrag anzunehmen'},
            ],
        ), (None, None, None))

    def test_negated_rejection_evidence_stays_unknown(self):
        for text in ('Den Antrag nicht abzulehnen', 'Keine Ablehnung des Antrags',
                     'Den Antrag keinesfalls abzulehnen'):
            with self.subTest(text=text):
                self.assertEqual(dip.recommendation_inversion({'description': text}), (None, None, None))
                self.assertEqual(dip.recommendation_inversion(
                    {'document_numbers': ['20/100']},
                    [{'dokumentnummer': '20/100', 'titel': text}],
                ), (None, None, None))

    def test_consistent_rejection_evidence_keeps_source_and_excerpt(self):
        title = 'Ablehnung des Antrags'
        self.assertEqual(dip.recommendation_inversion(
            {'title': title, 'document_numbers': ['20/100']},
            [{'dokumentnummer': '20/100', 'titel': 'Den Antrag abzulehnen'}],
        ), (True, 'bundestag-roll-call', title))

    def test_derived_result_uses_proposition_scope_when_official_text_is_unusable(self):
        vote = {'title': 'Ablehnung des Antrags', 'total': {'yes': 60, 'no': 40},
                'official_result': None, 'result_scope': 'application'}
        dip.interpret_vote(vote)
        self.assertEqual(vote['result_source'], 'derived')
        self.assertEqual(vote['result_raw'], 'accepted')
        self.assertEqual(vote['result_scope'], 'proposition')
        self.assertEqual(derive.vote_outcome(vote), 'rejected')

    def test_special_procedures_always_unknown_without_official(self):
        for title in ('Gesetz zur Änderung des Grundgesetzes', 'Vertrauensfrage',
                      'Konstruktives Misstrauensvotum', 'Wahl des Bundeskanzlers'):
            for yes, no in ((400, 200), (200, 400), (200, 200), (0, 0)):
                self.assertEqual(dip.vote_result(official=None, yes_count=yes, no_count=no, procedure_context={'titel': title}), (None, None))
                self.assertEqual(dip.vote_result(official='accepted', yes_count=yes, no_count=no, title=title), ('accepted', 'official'))
                self.assertEqual(dip.vote_result(official='rejected', yes_count=yes, no_count=no, title=title), ('rejected', 'official'))
        for title in ('Antrag zur Beachtung des Grundgesetzes', 'Antrag zur Änderung des Grundgesetzes', 'Gesetz über die Beachtung des Grundgesetzes'):
            self.assertEqual(dip.vote_result(official=None, yes_count=400, no_count=200, title=title), ('accepted', 'derived'))
        self.assertEqual(dip.vote_result(official=None, yes_count=200, no_count=200), ('rejected', 'derived'))
        self.assertEqual(dip.vote_result(official=None, yes_count=0, no_count=0), (None, None))

    def test_positions(self):
        for counts, expected in (({'yes': 4}, 'gegen den Antrag'), ({'no': 4}, 'für den Antrag'),
                                  ({'abstain': 4}, 'Enthaltung'), ({'yes': 4, 'no': 4}, 'geteilt'), ({'absent': 4}, None)):
            self.assertEqual(derive.fraction_position(counts, True), expected)

    def test_deduplicated_iteration(self):
        vote = {'id': '1'}
        report = {'agenda_items': [{'votes': [vote]}], 'sitting_votes': [vote, {'id': '2'}]}
        self.assertEqual([v['id'] for _, v in derive.iter_report_votes(report)], ['1', '2'])
