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


if __name__ == '__main__':
    unittest.main()
