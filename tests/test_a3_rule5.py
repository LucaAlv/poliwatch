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


if __name__ == '__main__':
    unittest.main()
