"""Speech rule 5 for WP 18/19 XML: sub-rules 6a–6d (docs/plans/a3-rule5-wp18-19.md)."""
import unittest

import _support  # noqa: F401
import speech_kinds as sk
import validate_dip_protocol as dip


def redner(rid, last, fraktion='SPD', role=''):
    rolle = f'<rolle><rolle_lang>{role}</rolle_lang></rolle>' if role else ''
    return (f'<p klasse="redner"><redner id="{rid}"><name><nachname>{last}</nachname>'
            f'{rolle}<fraktion>{fraktion}</fraktion></name></redner></p>')


def sitting(body, wp=18):
    return (f'<dbtplenarprotokoll wahlperiode="{wp}" sitzung-nr="1"><sitzungsverlauf>'
            f'<tagesordnungspunkt top-id="T1">{body}</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')


def parse(body):
    top = dip.parse_protocol_xml(sitting(body))['agenda_items'][0]
    return top, [(c['kind'], c['text']) for c in top['contributions']]


class SitzungsleitungMarkerTests(unittest.TestCase):
    """6d: a nested marker whose role is the presidium is Sitzungsleitung (ADR 0004)."""

    def test_presidium_marker_inside_a_rede_is_procedural(self):
        for role in ['Präsident', 'Vizepräsidentin', 'Vizepräsident in', 'Alterspräsident']:
            with self.subTest(role=role):
                top, contributions = parse(
                    '<rede id="R">' + redner('A', 'Haupt') + '<p>Rede.</p>'
                    + redner('P', 'Lammert', 'CDU/CSU', role)
                    + '<p>Das Wort erhält nun die Kollegin Andreae.</p></rede>')
                self.assertEqual(contributions, [])
                self.assertEqual([(d['marker_ordinal'], d['treatment']) for d in top['xml_turn_diagnostics']],
                                 [(2, 'procedural')])
                self.assertEqual(top['speeches'][0]['text'], 'Rede.')

    def test_presidium_marker_text_is_read_as_the_chair_offer(self):
        top, contributions = parse(
            '<rede id="R">' + redner('A', 'Haupt') + '<p>Rede.</p>'
            + redner('P', 'Roth', 'BÜNDNIS 90/DIE GRÜNEN', 'Vizepräsidentin')
            + '<p>Gestatten Sie eine Zwischenfrage des Kollegen Gast?</p>'
            + redner('A', 'Haupt') + '<p>Ja.</p>'
            + redner('B', 'Gast', 'CDU/CSU') + '<p>Meine Bemerkung.</p></rede>')
        self.assertEqual(contributions, [(sk.ZWISCHENFRAGE, 'Meine Bemerkung.')])

    def test_ministerpraesident_is_not_the_presidium(self):
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 2'):
            parse('<rede id="R">' + redner('A', 'Haupt') + '<p>Rede.</p>'
                  + redner('M', 'Schwesig', 'SPD', 'Ministerpräsidentin (Mecklenburg-Vorpommern)') + '<p>Eine Antwort.</p></rede>')


class ElectionAcceptanceTests(unittest.TestCase):
    """6d: the elected Präsident's acceptance is part of the election procedure."""

    def body(self, turn):
        return ('<rede id="R">' + redner('S', 'Solms', 'FDP', 'Alterspräsident') + '<p>Ergebnis.</p>'
                '<p>Ich frage Sie, Herr Schäuble: Nehmen Sie die Wahl an?</p>'
                + redner('W', 'Schäuble', 'CDU/CSU') + turn
                + '<name>Alterspräsident Dr. Hermann Otto Solms:</name><p>Herzlichen Glückwunsch.</p></rede>')

    def test_the_acceptance_is_procedural(self):
        top, contributions = parse(self.body('<p>Herr Präsident, ich nehme die Wahl an.</p>'))
        self.assertEqual(contributions, [])
        self.assertEqual([(d['marker_ordinal'], d['treatment']) for d in top['xml_turn_diagnostics']],
                         [(2, 'procedural')])

    def test_more_than_the_acceptance_is_not_procedural(self):
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 2'):
            parse(self.body('<p>Herr Präsident, ich nehme die Wahl an.</p><p>Meine Antrittsrede.</p>'))

    def test_an_acceptance_without_the_chair_question_is_not_procedural(self):
        body = self.body('<p>Herr Präsident, ich nehme die Wahl an.</p>').replace(
            'Ich frage Sie, Herr Schäuble: Nehmen Sie die Wahl an?', 'Weiter.')
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 2'):
            parse(body)


class NestedRedeTests(unittest.TestCase):
    """6c: a whole Rede the chair gives the floor to, printed inside the previous one."""

    def body(self, floor='Danke schön. – Als nächste Rednerin spricht die Kollegin Binder.',
             opening='Sehr geehrte Frau Präsidentin! Liebe Kolleginnen und Kollegen! Rede B.'):
        return ('<rede id="R">' + redner('A', 'Rief', 'CDU/CSU') + '<p>Frau Präsidentin! Rede A.</p>'
                '<name>Vizepräsidentin Claudia Roth:</name><p>' + floor + '</p>'
                + redner('B', 'Binder', 'DIE LINKE') + '<p>' + opening + '</p>'
                '<name>Vizepräsidentin Claudia Roth:</name>'
                '<p>Frau Kollegin Binder, erlauben Sie eine Zwischenfrage des Kollegen Gast?</p>'
                + redner('B', 'Binder', 'DIE LINKE') + '<p>Gerne.</p>'
                + redner('C', 'Gast', 'SPD') + '<p>Ist Ihnen das bekannt?</p>'
                + redner('B', 'Binder', 'DIE LINKE') + '<p>Ja. Ende.</p></rede>')

    def test_the_nested_rede_becomes_a_rede_of_its_own(self):
        for floor in ['Danke schön. – Als nächste Rednerin spricht die Kollegin Binder.',
                      'Ich schließe die Aussprache nicht. Jetzt gebe ich das Wort an Karin Binder für die Linke.',
                      'Das Wort hat die Kollegin Binder.']:
            with self.subTest(floor=floor):
                top, contributions = parse(self.body(floor=floor))
                self.assertEqual([(s['rede_id'], s['speaker']['xml_redner_id'], s['text']) for s in top['speeches']],
                                 [('R', 'A', 'Frau Präsidentin! Rede A.'),
                                  ('R:2', 'B', 'Sehr geehrte Frau Präsidentin! Liebe Kolleginnen und Kollegen! Rede B. Gerne. Ja. Ende.')])
                self.assertEqual([(c['kind'], c['rede_id'], c['parent_rede_id']) for c in top['contributions']],
                                 [(sk.ZWISCHENFRAGE, 'nested:R:2:3', 'R:2')])

    def test_a_salutation_without_the_floor_is_not_a_rede(self):
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 2'):
            parse(self.body(floor='Danke schön.'))

    def test_the_floor_to_someone_else_is_not_this_rede(self):
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 2'):
            parse(self.body(floor='Als nächste Rednerin spricht die Kollegin Müller.'))

    def test_the_floor_for_a_question_is_not_a_rede(self):
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 2'):
            parse(self.body(floor='Das Wort zu einer Kurzintervention hat die Kollegin Binder.',
                            opening='Sehr geehrte Frau Präsidentin! Eine Bemerkung.'))

    def test_the_floor_without_a_salutation_is_not_a_rede(self):
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 2'):
            parse(self.body(opening='Rede B.'))


class GrantEvidenceTests(unittest.TestCase):
    """6a: the Redner's short consent after an offer, or the asker's opening thanks."""

    def body(self, offer, consent, turn='Meine Bemerkung.'):
        return ('<rede id="R">' + redner('A', 'Haupt') + '<p>Rede.</p>'
                '<name>Vizepräsidentin Petra Pau:</name><p>' + offer + '</p>'
                + redner('A', 'Haupt') + '<p>' + consent + '</p>'
                + redner('B', 'Gast', 'CDU/CSU') + '<p>' + turn + '</p>'
                + redner('A', 'Haupt') + '<p>Weiter.</p></rede>')

    def test_a_short_consent_after_the_offer_grants(self):
        offer = 'Frau Kollegin, darf Ihnen der Kollege Gast eine Zwischenfrage stellen?'
        for consent in ['Aber ja.', 'Aber gern.', 'Immer gerne.', 'Die will ich erlauben, ja.', 'Das schaffe ich.',
                        'Ja, selbstverständlich.']:
            with self.subTest(consent=consent):
                _, contributions = parse(self.body(offer, consent))
                self.assertEqual(contributions, [(sk.ZWISCHENFRAGE, 'Meine Bemerkung.')])

    def test_a_consent_without_an_offer_does_not_grant(self):
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 3'):
            parse(self.body('Weiter geht es.', 'Ja.'))

    def test_a_long_or_mixed_answer_is_not_a_consent(self):
        offer = 'Frau Kollegin, darf Ihnen der Kollege Gast eine Zwischenfrage stellen?'
        for consent in ['Ja, wenn ich danach noch etwas länger über das Thema reden darf.', 'Ja. Nein, doch nicht.']:
            with self.subTest(consent=consent):
                with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 3'):
                    parse(self.body(offer, consent))

    def test_opening_thanks_for_being_allowed_grants_over_a_carried_refusal(self):
        refused = ('<rede id="R">' + redner('A', 'Haupt') + '<p>Rede.</p>'
                   '<name>Vizepräsidentin Claudia Roth:</name><p>Gestatten Sie eine Zwischenfrage?</p>'
                   + redner('A', 'Haupt') + '<p>Nein. Ich rede weiter.</p>'
                   '<name>Vizepräsidentin Claudia Roth:</name><p>Gut. Jetzt ist Herr Gast dran.</p>'
                   + redner('B', 'Gast', 'CDU/CSU') + '<p>{turn}</p>'
                   + redner('A', 'Haupt') + '<p>Weiter.</p></rede>')
        for turn in ['Vielen Dank, dass Sie die Zwischenbemerkung zulassen. Meine Bemerkung.',
                     'Vielen Dank für die Möglichkeit einer Zwischenfrage. Meine Bemerkung.',
                     'Es zeichnet Sie aus, dass Sie die Zwischenfrage zulassen. Meine Bemerkung.']:
            with self.subTest(turn=turn):
                _, contributions = parse(refused.format(turn=turn))
                self.assertEqual(contributions, [(sk.ZWISCHENFRAGE, turn)])
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 3'):
            parse(refused.format(turn='Schade, dass Sie die Zwischenbemerkung nicht zulassen. Meine Bemerkung.'))


class AddressedMemberTests(unittest.TestCase):
    """6b: the chair gives the floor to an MdB the Redner addressed; no question is asked."""

    def body(self, turn, chair='<name>Vizepräsidentin Claudia Roth:</name><p>Herr Kollege.</p>'):
        return ('<rede id="R">' + redner('A', 'Haupt') + '<p>Rede über Herrn Gast.</p>' + chair
                + redner('B', 'Gast', 'DIE LINKE') + '<p>' + turn + '</p>'
                + redner('A', 'Haupt') + '<p>Weiter.</p></rede>')

    def test_an_addressed_member_given_the_floor_makes_a_zwischenbemerkung(self):
        for turn in ['Vielen Dank. – Sie haben mich jetzt gerade direkt angesprochen, darum ein paar Anmerkungen.',
                     'Darauf muss ich eingehen, weil Sie mich ja indirekt angesprochen haben. – Das trifft nicht zu.',
                     'Ich wollte es nur korrigieren, weil Sie, lieber Kollege, es hier falsch zitiert haben.']:
            with self.subTest(turn=turn):
                _, contributions = parse(self.body(turn))
                self.assertEqual(contributions, [(sk.ZWISCHENFRAGE, turn)])

    def test_a_floor_for_a_kurzintervention_is_not_a_zwischenbemerkung(self):
        chair = ('<name>Vizepräsidentin Edelgard Bulmahn:</name>'
                 '<p>Jetzt erhält der Kollege Gast das Wort zu einer Kurzintervention.</p>')
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 2'):
            parse(self.body('Sehr geehrte Kollegin, Sie hatten mich direkt angesprochen.', chair=chair))

    def test_a_turn_that_does_not_say_it_was_addressed_stays_refused(self):
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 2'):
            parse(self.body('Das trifft nicht zu.'))

    def test_without_the_chair_giving_the_floor_it_stays_refused(self):
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 2'):
            parse(self.body('Sie haben mich angesprochen. Das trifft nicht zu.', chair=''))


class SourceBlockerTests(unittest.TestCase):
    """Trimmed WP 18/19 blockers (provenance in fixtures/a1-source-manifest.json)."""

    def parse_source(self, stem):
        top = dip.parse_protocol_xml((_support.FIXTURES / f'a3-rule5/{stem}.xml').read_text())['agenda_items'][0]
        return top

    def test_18_100_lammert_giving_the_floor_is_sitzungsleitung(self):
        top = self.parse_source('18-100')
        self.assertEqual(top['contributions'], [])
        self.assertEqual([(d['marker_ordinal'], d['treatment']) for d in top['xml_turn_diagnostics']], [(3, 'procedural')])

    def test_18_71_aber_ja_after_the_chair_offer_grants_burkert(self):
        top = self.parse_source('18-71')
        self.assertEqual([(c['kind'], c['rede_id'], c['speaker']['display_name']) for c in top['contributions']],
                         [(sk.ZWISCHENFRAGE, 'nested:ID1807101000:3', 'Martin Burkert')])

    def test_18_70_binder_rede_printed_inside_rief_rede_is_its_own(self):
        top = self.parse_source('18-70')
        self.assertEqual([(s['rede_id'], s['speaker']['display_name']) for s in top['speeches']],
                         [('ID1807005100', 'Josef Rief'), ('ID1807005100:2', 'Karin Binder')])
        self.assertEqual([(c['kind'], c['rede_id'], c['speaker']['display_name']) for c in top['contributions']],
                         [(sk.ZWISCHENFRAGE, 'nested:ID1807005100:2:3', 'Dr. Wilhelm Priesmeier')])


if __name__ == '__main__':
    unittest.main()
