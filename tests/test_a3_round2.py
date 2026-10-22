"""Speech rule 5 for WP 18/19 XML, round 2 (docs/plans/a3-rule5-wp18-19-round2.md)."""
import unittest

import _support  # noqa: F401
import derive
import validate_dip_protocol as dip


def role_redner(long='', short='', printed=''):
    rolle = f'<rolle><rolle_lang>{long}</rolle_lang><rolle_kurz>{short}</rolle_kurz></rolle>'
    redner = dip.ET.fromstring(f'<redner id="1"><name><nachname>Meister</nachname>{rolle}</name></redner>')
    redner.tail = f'Dr. Michael Meister, {printed}: ' if printed else 'Dr. Michael Meister: '
    return redner


class RoleSpellingTests(unittest.TestCase):
    """R2: one person, two spellings of the same role, reads as one side."""

    def test_ministry_abbreviation_and_long_form_are_the_government(self):
        for short, printed in [
            ('Parl. Staatssekretär BMF', 'Parl. Staatssekretär beim Bundesminister der Finanzen'),
            ('Parl. Staatssekretärin BMWi', 'Parl. Staatssekretärin beim Bundesminister für Wirtschaft und Energie'),
            ('Parl. Staatssekretär BMJV', 'Parl. Staatssekretär beim Bundesminister der Justiz und für Verbraucherschutz'),
            ('Parl. Staatssekretär BMI', 'Parl. Staatssekretär beim Bundesminister des Innern'),
            ('Parl. Staatssekretär BMI', 'Parl. Staatssekretär beim Bundesminister des Innern.'),
            ('Parl. Staatssekretär BMEL', 'Parl. Staatssekretär beim Bundesminister für Ernährung und Landwirtschaft'),
            ('Parl. Staatssekretärin BMUB',
             'Parl. Staatssekretärin bei der Bundesministerin für Umwelt, Naturschutz, Bau und Reaktorsicherheit'),
        ]:
            with self.subTest(short=short, printed=printed):
                speaker = dip.parse_redner(role_redner(short=short, printed=printed))
                self.assertEqual(speaker['role'], printed)
                self.assertEqual(speaker['role_short'], short)
                self.assertEqual(derive.sprechrolle(speaker), 'bundesregierung')

    def test_soft_hyphen_is_stripped_from_both_spellings(self):
        speaker = dip.parse_redner(role_redner(
            long='Parl. Staatssekretärin bei der Bundesministerin für Umwelt, Naturschutz, Bau und Reaktorsicherheit',
            short='Parl. Staats\xadsekretärin BMUB',
            printed='Parl. Staats\xadsekretärin bei der Bundesministerin für Umwelt, Naturschutz, Bau und Reaktorsicherheit'))
        self.assertEqual(speaker['role_short'], 'Parl. Staatssekretärin BMUB')
        self.assertEqual(derive.sprechrolle(speaker), 'bundesregierung')
        speaker = dip.parse_redner(role_redner(
            short='Parl. Staats\xadsekretärin BMUB',
            printed='Parl. Staatssekretärin bei der Bundesministerin für Umwelt, Naturschutz, Bau und Reaktorsicherheit'))
        self.assertEqual(derive.sprechrolle(speaker), 'bundesregierung')

    def test_land_suffix_wins_over_the_bare_title(self):
        for long, printed in [('Minister', 'Minister (Brandenburg)'), ('Ministerin', 'Ministerin (Thüringen)'),
                              ('Staatsminister', 'Staatsminister (Sachsen)'), ('Senator', 'Senator (Berlin)')]:
            with self.subTest(printed=printed):
                speaker = dip.parse_redner(role_redner(long=long, printed=printed))
                self.assertEqual(speaker['role'], printed)
                self.assertEqual(derive.sprechrolle(speaker), 'bundesrat')

    def test_a_real_conflict_still_raises(self):
        for kwargs in [
            {'short': 'Parl. Staatssekretär BMF', 'printed': 'Parl. Staatssekretär beim Bundesminister des Innern'},
            {'short': 'Parl. Staatssekretär BMF', 'printed': 'Staatsminister beim Bundesminister der Finanzen'},
            {'long': 'Minister', 'printed': 'Ministerpräsident (Hessen)'},
            {'long': 'Ministerpräsident (Hessen)', 'printed': 'Bundesministerin'},
        ]:
            with self.subTest(**kwargs):
                with self.assertRaisesRegex(ValueError, 'conflicting roles at redner 1'):
                    dip.parse_redner(role_redner(**kwargs))


def redner(rid, last, fraktion='SPD'):
    return (f'<p klasse="redner"><redner id="{rid}"><name><nachname>{last}</nachname>'
            f'<fraktion>{fraktion}</fraktion></name></redner></p>')


def parse(body, wp=18):
    xml = (f'<dbtplenarprotokoll wahlperiode="{wp}" sitzung-nr="1"><sitzungsverlauf>'
           f'<tagesordnungspunkt top-id="T1">{body}</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
    top = dip.parse_protocol_xml(xml)['agenda_items'][0]
    return top, [(c['kind'], c['text']) for c in top['contributions']]


class MiddleInitialTests(unittest.TestCase):
    """R4: the chair names "Birkwald"; WP 18/19 prints <nachname>W. Birkwald</nachname>."""

    def body(self, asker):
        return ('<rede id="R">' + redner('A', 'Haupt', 'CDU/CSU') + '<p>Rede.</p>'
                '<name>Vizepräsidentin Petra Pau:</name>'
                '<p>Gestatten Sie eine Zwischenfrage des Kollegen Birkwald?</p>'
                + redner('A', 'Haupt', 'CDU/CSU') + '<p>Ja.</p>'
                + redner('B', asker, 'DIE LINKE') + '<p>Meine Frage an Sie.</p></rede>')

    def test_named_asker_matches_the_surname_after_its_initial(self):
        _top, contributions = parse(self.body('W. Birkwald'))
        self.assertEqual(contributions, [('zwischenfrage', 'Meine Frage an Sie.')])

    def test_the_stored_last_name_keeps_the_initial(self):
        top, _contributions = parse(self.body('W. Birkwald'))
        self.assertEqual(top['contributions'][0]['speaker']['last_name'], 'W. Birkwald')

    def test_another_surname_is_still_a_mismatch(self):
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 3'):
            parse(self.body('W. Birkholz'))


class NestedRedeFloorWordingTests(unittest.TestCase):
    """R3: the WP 18 chair's other ways of giving the next Redner the floor (6c)."""

    def body(self, floor, opening='Sehr geehrte Frau Präsidentin! Liebe Kolleginnen und Kollegen! Rede B?'):
        return ('<rede id="R">' + redner('A', 'Rief', 'CDU/CSU') + '<p>Frau Präsidentin! Rede A.</p>'
                '<name>Vizepräsidentin Claudia Roth:</name><p>' + floor + '</p>'
                + redner('B', 'Gehring', 'BÜNDNIS 90/DIE GRÜNEN') + '<p>' + opening + '</p></rede>')

    def test_each_floor_form_splits_the_nested_rede(self):
        for floor in ['Nächster Redner ist Kai Gehring.',
                      'Nächster Redner: Kai Gehring.',
                      'Nächster Redner in der Debatte: Kai Gehring.',
                      'Der nächste Redner ist Kai Gehring.',
                      'Kai Gehring ist der nächste Redner.',
                      'Für Bündnis 90/Die Grünen spricht jetzt Kai Gehring.',
                      'Jetzt spricht nun Kai Gehring.',
                      'Kai Gehring hat für die Fraktion Bündnis 90/Die Grünen das Wort.',
                      'Jetzt hat Kai Gehring das Wort.',
                      'Als Nächstes hat das Wort Kai Gehring.',
                      'Als nächstem Redner erteile ich Kai Gehring das Wort.',
                      'Letzter Redner in dieser Debatte ist Kai Gehring.',
                      'Abschließender Redner in dieser Aussprache ist Kai Gehring.']:
            with self.subTest(floor=floor):
                top, contributions = parse(self.body(floor))
                self.assertEqual([s['rede_id'] for s in top['speeches']], ['R', 'R:2'])
                self.assertEqual(contributions, [])

    def test_sehr_verehrte_opens_a_rede(self):
        top, contributions = parse(self.body('Nächster Redner ist Kai Gehring.',
                                             opening='Sehr verehrte Frau Präsidentin! Meine Damen und Herren! Rede B?'))
        self.assertEqual([s['rede_id'] for s in top['speeches']], ['R', 'R:2'])
        self.assertEqual(contributions, [])

    def test_a_floor_form_naming_a_question_is_not_a_rede(self):
        top, contributions = parse(self.body('Jetzt hat Kai Gehring das Wort zu einer Zwischenfrage.'))
        self.assertEqual([s['rede_id'] for s in top['speeches']], ['R'])


if __name__ == '__main__':
    unittest.main()
