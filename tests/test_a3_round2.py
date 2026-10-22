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


class ConsentAndOfferTests(unittest.TestCase):
    """R1b: a short Redner turn after the chair's offer is consent unless it refuses.
    R1c: "Darf sie (das)?", "Mögen Sie?", "Gestatten Sie?" and "Zusatzfrage" are
    an offer when the chair's turn names the asker."""

    # 18/171: no request wording, so only the Redner's consent grants (6a).
    OFFER = 'Herr Kollege Haupt, darf die Kollegin Konrad eine Zwischenfrage stellen?'

    def body(self, offer, consent, asker='Konrad'):
        return ('<rede id="R">' + redner('A', 'Haupt', 'CDU/CSU') + '<p>Rede.</p>'
                '<name>Vizepräsidentin Petra Pau:</name><p>' + offer + '</p>'
                + redner('A', 'Haupt', 'CDU/CSU') + '<p>' + consent + '</p>'
                + redner('B', asker, 'FDP') + '<p>Ich halte das für falsch.</p>'
                + redner('A', 'Haupt', 'CDU/CSU') + '<p>Weiter.</p></rede>')

    def assert_granted(self, offer, consent):
        _top, contributions = parse(self.body(offer, consent))
        self.assertEqual(contributions, [('zwischenfrage', 'Ich halte das für falsch.')])

    def assert_refused(self, offer, consent, asker='Konrad'):
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 3'):
            parse(self.body(offer, consent, asker))

    def test_a_short_turn_after_the_offer_is_consent(self):
        for consent in ['Aber sicher.', 'Wenn es denn sein muss.', 'Von mir aus.', 'Sicherlich, Herr Kollege.',
                        'Mit dem größten Vergnügen, Frau Präsidentin.', 'Ich bitte darum.', 'Och ja.',
                        'Gerne, das verlängert meine knappe Redezeit.']:
            with self.subTest(consent=consent):
                self.assert_granted(self.OFFER, consent)

    def test_a_refusal_word_or_a_long_turn_is_not_consent(self):
        for consent in ['Nein, danke.', 'Nee.', 'Lieber nicht.', 'Jetzt nicht, Frau Präsidentin.', 'Keine Zwischenfragen.',
                        'Später gerne.',
                        'Ich würde gerne erst einmal meinen Gedanken zu Ende führen, dann sehen wir weiter, ja.']:
            with self.subTest(consent=consent):
                self.assert_refused(self.OFFER, consent)

    def test_the_asker_must_still_match_the_offer(self):
        self.assert_refused('Gestatten Sie eine Zwischenfrage der Kollegin Meier?', 'Aber sicher.')

    def test_short_offer_wordings_that_name_the_asker(self):
        for offer in ['Die Kollegin Konrad möchte Ihnen das gerne erklären. Darf sie das?',
                      'Frau Konrad würde gerne etwas sagen. Darf sie?',
                      'Frau Kollegin Konrad hat noch Gesprächsbedarf mit Ihnen. Mögen Sie?',
                      'Frau Konrad möchte etwas fragen. Gestatten Sie?',
                      'Herr Kollege Haupt, gestatten Sie eine Zusatzfrage der Kollegin Konrad?']:
            with self.subTest(offer=offer):
                self.assert_granted(offer, 'Gern.')

    def test_a_short_offer_wording_must_name_the_asker(self):
        for offer in ['Darf sie das?', 'Mögen Sie?', 'Gestatten Sie?', 'Eine Zusatzfrage?']:
            with self.subTest(offer=offer):
                self.assert_refused(offer, 'Gern.')

    def test_a_short_offer_naming_someone_else_is_a_mismatch(self):
        body = ('<rede id="R">' + redner('A', 'Haupt', 'CDU/CSU') + '<p>Rede.</p>'
                '<name>Vizepräsidentin Petra Pau:</name><p>Frau Meier möchte etwas sagen. Darf sie?</p>'
                + redner('A', 'Haupt', 'CDU/CSU') + '<p>Gern.</p>'
                + redner('B', 'Konrad', 'FDP') + '<p>Ich halte das für falsch.</p>'
                + redner('A', 'Haupt', 'CDU/CSU') + '<p>Weiter.</p>'
                + redner('C', 'Meier', 'SPD') + '<p>Das ist doch so.</p></rede>')
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 3'):
            parse(body)


def person(rid, first, last, fraktion='SPD'):
    return (f'<p klasse="redner"><redner id="{rid}"><name><vorname>{first}</vorname><nachname>{last}</nachname>'
            f'<fraktion>{fraktion}</fraktion></name></redner>{first} {last} ({fraktion}):</p>')


class RolelessChairTests(unittest.TestCase):
    """A role-less marker of the sitting's chair, saying chair text, is Sitzungsleitung (like 6d)."""

    # The person chairs this sitting: a <name> chair element names her elsewhere.
    OPENING = ('<rede id="R0">' + person('Z', 'Uwe', 'Zahl') + '<p>Erste Rede.</p>'
               '<name>Vizepräsidentin Josephine Ortleb:</name><p>Danke schön.</p></rede>')

    def test_the_chairs_offer_is_sitzungsleitung(self):
        top, contributions = parse(self.OPENING + '<rede id="R">' + person('A', 'Martin', 'Renner', 'AfD') + '<p>Rede.</p>'
                                   + person('O', 'Josephine', 'Ortleb')
                                   + '<p>Herr Kollege Renner, erlauben Sie eine Zwischenfrage der Kollegin Gast?</p>'
                                   + person('A', 'Martin', 'Renner', 'AfD') + '<p>Ja.</p>'
                                   + person('B', 'Anna', 'Gast', 'AfD') + '<p>Meine Bemerkung.</p></rede>')
        self.assertEqual(contributions, [('zwischenfrage', 'Meine Bemerkung.')])
        self.assertEqual([(d['marker_ordinal'], d['treatment']) for d in top['xml_turn_diagnostics']],
                         [(2, 'procedural')])

    def test_the_chairs_floor_starts_a_nested_rede(self):
        top, contributions = parse(self.OPENING + '<rede id="R">' + person('A', 'Frank', 'Tempel', 'DIE LINKE') + '<p>Rede.</p>'
                                   + person('O', 'Josephine', 'Ortleb')
                                   + '<p>Für die SPD hat jetzt der Kollege Burkhard Blienert das Wort.</p>'
                                   + person('B', 'Burkhard', 'Blienert')
                                   + '<p>Sehr geehrte Frau Präsidentin! Rede B.</p></rede>')
        self.assertEqual([s['rede_id'] for s in top['speeches']], ['R0', 'R', 'R:3'])
        self.assertEqual(contributions, [])

    def test_the_chair_asking_as_a_member_is_her_zwischenfrage(self):
        _top, contributions = parse(self.OPENING + '<rede id="R">' + person('A', 'Martin', 'Renner', 'AfD') + '<p>Rede.</p>'
                                    + person('O', 'Josephine', 'Ortleb')
                                    + '<p>Herr Renner, habe ich Sie richtig verstanden, dass Sie zustimmen würden?</p></rede>')
        self.assertEqual(contributions, [('zwischenfrage', 'Herr Renner, habe ich Sie richtig verstanden, dass Sie zustimmen würden?')])

    def test_a_namesake_of_the_chair_is_not_the_chair(self):
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 2'):
            parse(self.OPENING + '<rede id="R">' + person('A', 'Martin', 'Renner', 'AfD') + '<p>Rede.</p>'
                  + person('O', 'Dagmar', 'Ortleb')
                  + '<p>Herr Kollege Renner, erlauben Sie eine Zwischenfrage der Kollegin Gast.</p></rede>')


if __name__ == '__main__':
    unittest.main()
