"""ADR 0004 kinds: Ansprache, Sitzungsleitung and procedural <rede>s
(docs/plans/adr-0004-presidium-kinds.md, tests T1-T23)."""
import csv
import json
import tempfile
import time
import unittest.mock
import unittest
from pathlib import Path

import _support
import derive
import speech_kinds as sk
import validate_dip_protocol as dip


def redner(rid, last, fraktion=None, role=None, first=None, title=None, printed=None):
    parts = []
    if title:
        parts.append(f'<titel>{title}</titel>')
    if first:
        parts.append(f'<vorname>{first}</vorname>')
    parts.append(f'<nachname>{last}</nachname>')
    if role:
        parts.append(f'<rolle><rolle_lang>{role}</rolle_lang></rolle>')
    if fraktion:
        parts.append(f'<fraktion>{fraktion}</fraktion>')
    label = printed or f'{last}:'
    return f'<p klasse="redner"><redner id="{rid}"><name>{"".join(parts)}</name></redner>{label}</p>'


def rede(rid, owner, body):
    return f'<rede id="{rid}">{owner}{body}</rede>'


def sitting(body, wp=19, nr=1, heading='Eröffnung der Sitzung'):
    return (f'<dbtplenarprotokoll wahlperiode="{wp}" sitzung-nr="{nr}"><sitzungsverlauf>'
            f'<tagesordnungspunkt top-id="T1"><p klasse="T_NaS">{heading}</p>{body}</tagesordnungspunkt>'
            f'</sitzungsverlauf></dbtplenarprotokoll>')


def entry(rede_id, redner_id, kind, sitting_='19/1', reason='reviewed in the census'):
    return {'sitting': sitting_, 'rede_id': rede_id, 'redner_id': redner_id, 'kind': kind, 'reason': reason}


def parse(body, entries=(), **kwargs):
    sk.use_reviewed_units(list(entries))
    try:
        return dip.parse_protocol_xml(sitting(body, **kwargs))
    finally:
        sk.use_reviewed_units([])


def top_of(parsed):
    return parsed['agenda_items'][0]


SCHAEUBLE = redner('11001938', 'Schäuble', 'CDU/CSU', 'Präsident', first='Wolfgang', title='Dr.')
SOLMS = redner('11002190', 'Solms', 'FDP', 'Alterspräsident', first='Hermann Otto', title='Dr.')
MEMBER_A = redner('11000001', 'Meier', 'SPD', first='Anna')
MEMBER_B = redner('11000002', 'Gast', 'CDU/CSU', first='Bernd')
DEBATE = '<p>Sehr geehrte Frau Präsidentin! Liebe Kolleginnen und Kollegen! Eine Rede zur Sache mit Inhalt.</p>'


class AnspracheTests(unittest.TestCase):
    def test_a_listed_ansprache_is_one_beitrag_and_no_rede(self):
        # T1 (19/1 ID19101300, 18/245 ID1824501400 shapes).
        for owner, rid, redner_id in [(SCHAEUBLE, 'ID19101300', '11001938'),
                                      (redner('11000258', 'Bulmahn', role='Vizepräsidentin', first='Edelgard'),
                                       'ID1824501400', '11000258')]:
            with self.subTest(rede=rid):
                parsed = parse(rede(rid, owner, '<p>Liebe Kolleginnen und Kollegen, ich danke Ihnen.</p>'),
                               [entry(rid, redner_id, 'ansprache')])
                top = top_of(parsed)
                self.assertEqual(top['speeches'], [])
                [contribution] = top['contributions']
                self.assertEqual(contribution['kind'], sk.ANSPRACHE)
                self.assertEqual(contribution['rede_id'], rid)
                self.assertIsNone(contribution['parent_rede_id'])
                self.assertEqual(contribution['text'], 'Liebe Kolleginnen und Kollegen, ich danke Ihnen.')
                self.assertIn(contribution['speaker']['role'], ('Präsident', 'Vizepräsidentin'))
                self.assertEqual(top['xml_turn_diagnostics'], [])

    def test_a_listed_ansprache_keeps_the_rede_count_of_the_debate_around_it(self):
        parsed = parse(rede('ID1', SCHAEUBLE, '<p>Gedenkworte.</p><name>Präsident Dr. Wolfgang Schäuble:</name>'
                            '<p>Das Wort hat die Kollegin Meier.</p>')
                       + rede('ID2', MEMBER_A, DEBATE),
                       [entry('ID1', '11001938', 'ansprache')])
        top = top_of(parsed)
        self.assertEqual([s['rede_id'] for s in top['speeches']], ['ID2'])
        self.assertEqual([c['kind'] for c in top['contributions']], [sk.ANSPRACHE])


class SitzungsleitungTests(unittest.TestCase):
    def test_a_listed_sitzungsleitung_rede_stores_nothing_and_leaves_one_diagnostic_per_own_turn(self):
        # T2 (19/1 ID19101900, 18/245 ID1824502300 shapes).
        body = rede('ID19101900', SCHAEUBLE,
                    '<p>Wir kommen zur Wahl der Vizepräsidenten.</p>'
                    '<kommentar>(Beifall)</kommentar>'
                    + SCHAEUBLE.replace('Präsident</rolle_lang>', 'Präsident</rolle_lang>')
                    + '<p>Ich gebe das Ergebnis bekannt.</p>')
        top = top_of(parse(body, [entry('ID19101900', '11001938', 'sitzungsleitung', reason='chairs the election')]))
        self.assertEqual(top['speeches'], [])
        self.assertEqual(top['contributions'], [])
        self.assertEqual([(d['marker_ordinal'], d['treatment'], d['evidence']) for d in top['xml_turn_diagnostics']],
                         [(1, 'procedural', 'Sitzungsleitung (reviewed): chairs the election'),
                          (2, 'procedural', 'Sitzungsleitung (reviewed): chairs the election')])
        self.assertEqual(top['xml_turn_diagnostics'][0]['text'], 'Wir kommen zur Wahl der Vizepräsidenten.')

    def test_an_empty_listed_rede_stores_nothing(self):
        # H2: 19/1 ID19100200 is an empty <rede> of Solms: no turn with words, so
        # no diagnostic; the reconciliation still gives it the status procedural.
        top = top_of(parse(rede('ID19100200', SOLMS, ''), [entry('ID19100200', '11002190', 'sitzungsleitung')]))
        self.assertEqual((top['speeches'], top['contributions'], top['xml_turn_diagnostics']), ([], [], []))


class UnreviewedPresidiumTests(unittest.TestCase):
    def test_an_unlisted_presidium_rede_refuses_located(self):
        # T3, T4: whatever the Fraktion.
        for owner in [SCHAEUBLE, SOLMS, redner('3', 'Bulmahn', role='Vizepräsidentin')]:
            with self.subTest(owner=owner[:60]):
                with self.assertRaises(dip.UnreviewedUnitError) as caught:
                    parse(rede('ID7', owner, '<p>Ansprache.</p>'))
                self.assertEqual(caught.exception.rede_id, 'ID7')
                self.assertIn('19/1 T1: presidium Rede at ID7 has no reviewed kind', str(caught.exception))

    def test_a_role_printed_with_the_name_is_the_presidium(self):
        # T22: 18/178 prints "Präsident Dr. Norbert Lammert" as rolle_lang.
        lammert = redner('11001274', 'Lammert', role='Präsident Dr. Norbert Lammert', first='Norbert', title='Dr.')
        with self.assertRaisesRegex(dip.UnreviewedUnitError, 'presidium Rede at ID1 has no reviewed kind'):
            parse(rede('ID1', lammert, '<p>Gedenkworte.</p>'), wp=18, nr=178)
        top = top_of(parse(rede('ID1', lammert, '<p>Gedenkworte.</p>'),
                           [entry('ID1', '11001274', 'ansprache', '18/178')], wp=18, nr=178))
        self.assertEqual([c['kind'] for c in top['contributions']], [sk.ANSPRACHE])

    def test_a_guest_role_is_not_the_presidium(self):
        # T22: "Präsidentin des Bundesrates" is a guest, left to check_sprechrollen.
        for role in ['Präsidentin des Bundesrates', 'Präsident der Assemblée nationale', 'Bundespräsident']:
            with self.subTest(role=role):
                self.assertFalse(sk.presidium_role(role))
                top = top_of(parse(rede('ID1', redner('9', 'Dreyer', role=role, first='Malu'), '<p>Ansprache.</p>'),
                                   wp=18, nr=223))
                [speech] = top['speeches']
                with self.assertRaises(derive.SprechrolleError):
                    derive.sprechrolle(speech['speaker'])

    def test_the_presidium_role_test(self):
        for role, name, expected in [('Präsident', None, True), ('Vizepräsident in', None, True),
                                     ('Alterspräsidentin', None, True),
                                     ('Präsident Dr. Wolfgang Schäuble', ('Dr.', 'Wolfgang', 'Schäuble'), True),
                                     ('Präsident Dr. Wolfgang Schäuble', None, False),
                                     ('Ministerpräsidentin (Mecklenburg-Vorpommern)', None, False),
                                     ('', None, False)]:
            with self.subTest(role=role, name=name):
                element = None
                if name:
                    element = dip.ET.fromstring(f'<redner id="1"><name><titel>{name[0]}</titel><vorname>{name[1]}</vorname>'
                                                f'<nachname>{name[2]}</nachname></name></redner>')
                self.assertEqual(sk.presidium_role(role, element), expected)


class VizepraesidentTests(unittest.TestCase):
    def test_an_unlisted_vizepraesidentin_with_a_fraktion_is_her_fraktions_rede_and_a_listed_one_an_ansprache(self):
        # T5.
        pau = redner('11001667', 'Pau', 'DIE LINKE', 'Vizepräsidentin', first='Petra')
        top = top_of(parse(rede('ID1', pau, DEBATE), wp=18, nr=46))
        [speech] = top['speeches']
        self.assertIsNone(speech['speaker']['role'])
        top = top_of(parse(rede('ID1', pau, '<p>Abschied.</p>'), [entry('ID1', '11001667', 'ansprache', '18/46')], wp=18, nr=46))
        [contribution] = top['contributions']
        self.assertEqual((contribution['kind'], contribution['speaker']['role'], contribution['speaker']['fraktion']),
                         (sk.ANSPRACHE, 'Vizepräsidentin', 'DIE LINKE'))


class StaleEntryTests(unittest.TestCase):
    def test_a_stale_entry_refuses_the_sitting_naming_it(self):
        # T6.
        body = rede('ID1', SCHAEUBLE, '<p>Ansprache.</p>')
        annex = ('<dbtplenarprotokoll wahlperiode="19" sitzung-nr="1"><sitzungsverlauf>'
                 '<tagesordnungspunkt top-id="T1"><p klasse="T_NaS">Eröffnung</p>' + rede('ID1', MEMBER_A, DEBATE)
                 + '</tagesordnungspunkt></sitzungsverlauf><anlagen><anlage><anlagen-text anlagen-typ="Anlage">'
                 + rede('ID9', SCHAEUBLE, '<p>Zu Protokoll.</p>') + '</anlagen-text></anlage></anlagen></dbtplenarprotokoll>')
        for name, xml, entries, message in [
            ('missing rede', sitting(body), [entry('ID1', '11001938', 'ansprache'), entry('ID2', '11001938', 'ansprache')],
             'reviewed unit ID2 .*prints this <rede> 0 times'),
            ('wrong redner', sitting(body), [entry('ID1', '11002190', 'ansprache')],
             'reviewed unit ID1 .*owned by Redner-ID 11001938, the entry says 11002190'),
            ('annex only', annex, [entry('ID9', '11001938', 'ansprache')], 'reviewed unit ID9 .*prints this <rede> 0 times'),
        ]:
            with self.subTest(name):
                sk.use_reviewed_units(entries)
                try:
                    with self.assertRaisesRegex(ValueError, '^19/1: ' + message):
                        dip.parse_protocol_xml(xml)
                finally:
                    sk.use_reviewed_units([])

    def test_an_id_printed_twice_refuses(self):
        xml = sitting(rede('ID1', SCHAEUBLE, '<p>A.</p>') + rede('ID1', SCHAEUBLE, '<p>B.</p>'))
        sk.use_reviewed_units([entry('ID1', '11001938', 'ansprache')])
        try:
            with self.assertRaisesRegex(ValueError, 'ID1'):
                dip.parse_protocol_xml(xml)
        finally:
            sk.use_reviewed_units([])

    def test_an_entry_for_another_sitting_is_not_applied(self):
        # T8.
        with self.assertRaisesRegex(dip.UnreviewedUnitError, 'presidium Rede at ID1'):
            parse(rede('ID1', SCHAEUBLE, '<p>Ansprache.</p>'), [entry('ID1', '11001938', 'ansprache', '19/2')])


class LoaderTests(unittest.TestCase):
    """T7: a malformed list stops the run with ReviewedUnitsError, never as a
    protocol refusal (a ValueError)."""

    def test_malformed_lists_refuse_with_a_named_entry(self):
        good = entry('ID1', '1', 'ansprache')
        cases = {
            'null': None,
            'list': [good],
            'unknown top key': {'entries': [good], 'version': 1},
            'entries not a list': {'entries': {}},
            'entry not an object': {'entries': ['x']},
            'unknown key': {'entries': [{**good, 'marker': 3}]},
            'missing key': {'entries': [{k: v for k, v in good.items() if k != 'reason'}]},
            'unknown kind': {'entries': [{**good, 'kind': 'withhold'}]},
            'number value': {'entries': [{**good, 'redner_id': 11001938}]},
            'blank sitting': {'entries': [{**good, 'sitting': ''}]},
            'path sitting': {'entries': [{**good, 'sitting': '../1'}]},
            'blank reason': {'entries': [{**good, 'reason': '  '}]},
            'rede id not an id': {'entries': [{**good, 'rede_id': 'ID1:3'}]},
            'redner id not digits': {'entries': [{**good, 'redner_id': '11001938 '}]},
            'duplicate entry': {'entries': [good, good]},
            'one rede under two kinds': {'entries': [good, {**good, 'kind': 'procedural'}]},
        }
        for name, data in cases.items():
            with self.subTest(name):
                with self.assertRaises(sk.ReviewedUnitsError) as caught:
                    sk.validate_reviewed_units(data, 'list.json')
                self.assertNotIsInstance(caught.exception, ValueError)
                self.assertTrue(str(caught.exception).startswith('list.json'))
        self.assertEqual(len(sk.validate_reviewed_units({'entries': [good]})), 1)

    def test_an_unreadable_file_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'reviewed_units.json'
            for content in ['', '{', '{"entries": [}']:
                with self.subTest(content=content):
                    path.write_text(content, encoding='utf-8')
                    with self.assertRaises(sk.ReviewedUnitsError):
                        sk.load_reviewed_units(path)
            with self.assertRaises(sk.ReviewedUnitsError):
                sk.load_reviewed_units(Path(tmp) / 'absent.json')
        sk.use_reviewed_units([])

    def test_the_shipped_list_loads(self):
        with _support.shipped_reviewed_units() as units:
            kinds = [e['kind'] for e in units.values()]
        self.assertEqual((kinds.count('procedural'), kinds.count('ansprache'), kinds.count('sitzungsleitung')),
                         (113, 14, 9))

    def test_a_broken_list_stops_the_entry_points_before_any_work(self):
        import build_dip_pulse_site as build
        import extract_demo_fixture
        original = sk.REVIEWED_UNITS_PATH
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / 'reviewed_units.json'
            broken.write_text('{"entries": [{"sitting": "19/1"}]}', encoding='utf-8')
            for name, main, argv in [('build', build.main, ['build', '--offline', '--output-dir', tmp]),
                                     ('validate', dip.main, ['validate', '--document-number', '19/1']),
                                     ('fixture', extract_demo_fixture.main, ['x', '--xml', 'x.xml', '--output', f'{tmp}/o.json'])]:
                with self.subTest(name):
                    sk.REVIEWED_UNITS_PATH = broken
                    sk._reviewed = None
                    try:
                        with unittest.mock.patch('sys.argv', argv), unittest.mock.patch('sys.stderr') as stderr:
                            self.assertEqual(main(), 1)
                        written = ''.join(call.args[0] for call in stderr.write.call_args_list)
                        self.assertIn('ERROR [reviewed-units]', written)
                    finally:
                        sk.REVIEWED_UNITS_PATH = original
                        sk.use_reviewed_units([])


class SplitTests(unittest.TestCase):
    def test_6c_inside_listed_rede(self):
        # T9: a debate Rede printed inside a listed Sitzungsleitung <rede> splits
        # off with the owner's text as chair text; the split part is no listed unit.
        body = rede('ID1', SCHAEUBLE, '<p>Wir beginnen die Aussprache. Das Wort hat die Kollegin Meier.</p>'
                    + MEMBER_A + DEBATE)
        top = top_of(parse(body, [entry('ID1', '11001938', 'sitzungsleitung')]))
        self.assertEqual([(s['rede_id'], s['speaker']['last_name']) for s in top['speeches']], [('ID1:2', 'Meier')])
        self.assertEqual([d['marker_ordinal'] for d in top['xml_turn_diagnostics']], [1])
        # In a listed Ansprache the owner's words are not the chair's: no split, and
        # the other speaker's turn follows the existing nested rules.
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at ID1 marker 2'):
            parse(body, [entry('ID1', '11001938', 'ansprache')])


class RunningStateTests(unittest.TestCase):
    """T10: a listed or unlisted presidium <rede> leaves classify_reden's state alone."""

    def labels(self, body, entries, formats=frozenset()):
        sk.use_reviewed_units(list(entries))
        try:
            root = dip.ET.fromstring(sitting(body))
            dip.mark_reviewed_units(root)
            return [tuple(l) for l in sk.classify_reden(root.find('.//tagesordnungspunkt'), formats)]
        finally:
            sk.use_reviewed_units([])

    def test_a_kurzintervention_announced_inside_a_sitzungsleitung_rede_answers_the_last_rede(self):
        body = (rede('ID1', MEMBER_A, DEBATE)
                + rede('ID2', SCHAEUBLE, '<p>Zu einer Kurzintervention erteile ich dem Kollegen Gast das Wort.</p>')
                + rede('ID3', MEMBER_B, '<p>Frau Kollegin, Sie irren.</p>'))
        self.assertEqual(self.labels(body, [entry('ID2', '11001938', 'sitzungsleitung')]),
                         [(None, None), (sk.SITZUNGSLEITUNG, None), (sk.KURZINTERVENTION, 'ID1')])

    def test_an_erwiderung_after_a_listed_rede_still_pairs(self):
        for kind, label in [('procedural', sk.PROCEDURAL), ('ansprache', sk.ANSPRACHE), ('sitzungsleitung', sk.SITZUNGSLEITUNG)]:
            with self.subTest(kind=kind):
                body = (rede('ID1', MEMBER_A, DEBATE + '<name>Präsident Dr. Wolfgang Schäuble:</name>'
                             '<p>Zu einer Kurzintervention hat der Kollege Gast das Wort.</p>')
                        + rede('ID2', MEMBER_B, '<p>Frau Kollegin, Sie irren.</p>')
                        + rede('ID3', SCHAEUBLE, '<p>Kurz.</p>')
                        + rede('ID4', MEMBER_A, '<p>Ich erwidere.</p>'))
                self.assertEqual(self.labels(body, [entry('ID3', '11001938', kind)]),
                                 [(None, None), (sk.KURZINTERVENTION, 'ID1'), (label, None), (sk.ERWIDERUNG, 'ID1')])

    def test_a_listed_rede_in_a_befragung_does_not_end_the_opening_reports(self):
        minister = redner('11000003', 'Ministerin', role='Bundesministerin für Bildung', first='Eva')
        body = (rede('ID1', minister, '<p>Bericht.</p>') + rede('ID2', SCHAEUBLE, '<p>Hinweis.</p>')
                + rede('ID3', minister, '<p>Weiterer Bericht.</p>') + rede('ID4', MEMBER_A, '<p>Frage?</p>'))
        self.assertEqual(self.labels(body, [entry('ID2', '11001938', 'procedural')], frozenset({sk.BEFRAGUNG})),
                         [(None, None), (sk.PROCEDURAL, None), (None, None), (sk.BEFRAGUNG_FRAGE, None)])


class NestedInListedTests(unittest.TestCase):
    def test_another_members_turn_in_a_listed_procedural_rede_refuses_unless_6d_covers_it(self):
        # T11.
        body = rede('ID1', MEMBER_A, '<p>Ich nehme die Wahl an.</p>' + MEMBER_B + '<p>Was ist mit uns?</p>')
        for kind in ('procedural', 'sitzungsleitung'):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at ID1 marker 2 inside a reviewed'):
                    parse(body, [entry('ID1', '11000001', kind)])
        # 6d: a nested presidium marker in it is chair text.
        body = rede('ID1', MEMBER_A, '<p>Ich nehme die Wahl an.</p>' + SCHAEUBLE + '<p>Herzlichen Glückwunsch.</p>')
        top = top_of(parse(body, [entry('ID1', '11000001', 'procedural')]))
        self.assertEqual((top['speeches'], top['contributions']), ([], []))
        self.assertEqual([d['marker_ordinal'] for d in top['xml_turn_diagnostics']], [1, 2])


class AcceptanceTests(unittest.TestCase):
    """T12: P4's <rede> form."""

    def test_listed_acceptances_are_procedural_and_unlisted_ones_refuse(self):
        for text in ['Herr Präsident, ich nehme die Wahl an und bedanke mich für das Vertrauen.',
                     'Ich nehme die Wahl an. – Danke schön.',
                     'Frau Alterspräsidentin, ich nehme die Wahl sehr gerne an.',
                     'Ich nehme sie mit großer Freude an.',
                     'Ja, ich nehme die Wahl an.']:
            with self.subTest(text=text):
                body = rede('ID1', MEMBER_A, f'<p>{text}</p>')
                top = top_of(parse(body, [entry('ID1', '11000001', 'procedural', reason='acceptance')]))
                self.assertEqual((top['speeches'], top['contributions']), ([], []))
                self.assertEqual([(d['treatment'], d['evidence']) for d in top['xml_turn_diagnostics']],
                                 [('procedural', 'procedural (reviewed): acceptance')])
                with self.assertRaises(dip.UnreviewedUnitError) as caught:
                    parse(body)
                self.assertIn('election acceptance at ID1 has no reviewed kind', str(caught.exception))
                self.assertEqual(caught.exception.rede_id, 'ID1')

    def test_ja_under_an_election_is_a_candidate(self):
        # 20/5 Scholz: "Ja." under "Wahl des Bundeskanzlers".
        with self.assertRaisesRegex(dip.UnreviewedUnitError, 'election acceptance at ID1'):
            parse(rede('ID1', MEMBER_A, '<p>Ja.</p>'), heading='Wahl des Bundeskanzlers')
        top = top_of(parse(rede('ID1', MEMBER_A, '<p>Ja.</p>'), heading='Vereinbarte Debatte'))
        self.assertEqual(len(top['speeches']), 1)

    def test_no_candidate(self):
        for text in ['Ich nehme an, dass Sie das wissen.',  # 18/90
                     'Ich nehme die Wahl an. Meine Antrittsrede. ' + 'Ich danke allen, die mich gewählt haben. ' * 5,
                     'Sehr geehrte Damen und Herren, wir nehmen die Wahl der Mittel ernst.']:
            with self.subTest(text=text[:40]):
                top = top_of(parse(rede('ID1', MEMBER_A, f'<p>{text}</p>')))
                self.assertEqual(len(top['speeches']), 1)


class OathTests(unittest.TestCase):
    """T13: P5, one subTest per form."""

    MERZ = ('Ich schwöre, dass ich meine Kraft dem Wohle des deutschen Volkes widmen, seinen Nutzen mehren, '
            'Schaden von ihm wenden, das Grundgesetz und die Gesetze des Bundes wahren und verteidigen, meine '
            'Pflichten gewissenhaft erfüllen und Gerechtigkeit gegen jedermann üben werde. So wahr mir Gott helfe.')

    def test_each_listed_form_is_procedural_and_refuses_unlisted(self):
        minister = redner('11000003', 'Ministerin', role='Bundesministerin für Bildung', first='Eva')
        for form, text in [('short', 'Ich schwöre es.'),
                           ('with God', 'Ich schwöre, so wahr mir Gott helfe.'),
                           ('thanks after it', 'Ich schwöre es, so wahr mir Gott helfe. – Vielen Dank.'),
                           ('full Art. 56 formula', self.MERZ),
                           ('Amtseid', 'Ich leiste den Amtseid ohne religiöse Beteuerung.'),
                           ('Eidesformel', 'Ich spreche die Eidesformel nach.'),
                           ('yes', 'Ja, ich schwöre.')]:
            with self.subTest(form=form):
                self.assertLessEqual(len(text), dip.OATH_MAX_CHARS)
                body = rede('ID1', minister, f'<p>{text}</p>')
                top = top_of(parse(body, [entry('ID1', '11000003', 'procedural', '21/2')], wp=21, nr=2))
                self.assertEqual((top['speeches'], top['contributions']), ([], []))
                with self.assertRaisesRegex(dip.UnreviewedUnitError, '21/2 T1: oath answer at ID1 has no reviewed kind'):
                    parse(body, wp=21, nr=2)

    def test_no_candidate(self):
        quote = 'Sehr geehrte Frau Präsidentin! Wir alle haben geschworen, dem Wohle des Volkes zu dienen. ' * 6
        for form, text in [('oath quoted in a long Rede', quote),
                           ('Eidgenossenschaft', 'Die Eidgenossenschaft und die Leidenschaft.'),
                           ('beschwören', 'Wir beschwören die Schwierigkeiten nicht.')]:
            with self.subTest(form=form):
                self.assertEqual(len(top_of(parse(rede('ID1', MEMBER_A, f'<p>{text}</p>')))['speeches']), 1)

    def test_a_befragung_frage_saying_unter_eid_is_no_candidate(self):
        # 19/94 ID199400400: no Rede, so never a candidate.
        minister = redner('11000003', 'Merkel', role='Bundeskanzlerin', first='Angela')
        body = (rede('ID1', minister, '<p>Bericht.</p>')
                + rede('ID2', MEMBER_A, '<p>Würden Sie auch unter Eid bestreiten, dass es so war?</p>'))
        top = top_of(parse(body, heading='Befragung der Bundesregierung', wp=19, nr=94))
        self.assertEqual([c['kind'] for c in top['contributions']], [sk.BEFRAGUNG_FRAGE])

    def test_the_bundespraesidents_oath_inside_a_listed_address_stays_in_it(self):
        gauck = redner('9', 'Gauck', role='Bundespräsident', first='Joachim')
        text = 'Ich schwöre es. ' + 'Meine Damen und Herren, ' * 30
        top = top_of(parse(rede('ID1', gauck, f'<p>{text}</p>'), [entry('ID1', '9', 'ansprache', '18/223')], wp=18, nr=223))
        [contribution] = top['contributions']
        self.assertEqual(contribution['kind'], sk.ANSPRACHE)
        self.assertIn('Ich schwöre es.', contribution['text'])

    def test_hostile_text_is_fast(self):
        # Checklist class 8: long runs and unbalanced quotes, under the caps and over.
        for text in ['„' * 10000, 'nehme ' * 2000, 'Eid' * 4000, 'schw' * 3000, 'Ja.' * 5000]:
            with self.subTest(text=text[:10]):
                start = time.perf_counter()
                dip.procedural_candidate(text, 'Wahl', 'nehmen Sie die Wahl an')
                dip.procedural_candidate(text[:150], 'Wahl', '')
                self.assertLess(time.perf_counter() - start, 0.5)  # gstack-timing-ok: checklist class 8 times hostile text; the bound is the contract


class ReconciliationTests(unittest.TestCase):
    def test_statuses(self):
        # T20: #147's reconciliation counts a listed procedural or Sitzungsleitung
        # <rede> as procedural and an Ansprache as a Beitrag.
        body = (rede('ID1', SCHAEUBLE, '<p>Gedenkworte.</p>') + rede('ID2', SOLMS, '<p>Wahlgang.</p>')
                + rede('ID3', MEMBER_A, '<p>Ich nehme die Wahl an.</p>') + rede('ID4', MEMBER_B, DEBATE))
        statuses = {}
        original = dip.reconcile_reden

        def capture(sitting_, inventory, recorded, split_parts):
            statuses.update(recorded)
            return original(sitting_, inventory, recorded, split_parts)

        with unittest.mock.patch.object(dip, 'reconcile_reden', capture):
            parse(body, [entry('ID1', '11001938', 'ansprache'), entry('ID2', '11002190', 'sitzungsleitung'),
                         entry('ID3', '11000001', 'procedural')])
        self.assertEqual(statuses, {'ID1': 'beitrag', 'ID2': 'procedural', 'ID3': 'procedural', 'ID4': 'speech'})
        self.assertEqual(sk.REDE_STATUS[sk.ANSPRACHE], 'beitrag')
        for internal in (sk.SITZUNGSLEITUNG, sk.PROCEDURAL, sk.UNREVIEWED_PRESIDIUM):
            self.assertNotIn(internal, sk.CONTRIBUTION_KINDS)
            with self.assertRaises(ValueError):
                sk.validate_kind(internal)


def store_report(number, speakers, contributions=()):
    from test_sprechrolle import report
    data = report(number, *speakers)
    data['agenda_items'][0]['xml_contributions'] = [
        {'kind': kind, 'rede_id': f'IDC{index}', 'parent_rede_id': None, 'sequence': 100 + index,
         'speaker': speaker, 'paragraph_count': 1, 'char_count': 50, 'text': 'Ansprache', 'snippet': 'Ansprache'}
        for index, (kind, speaker) in enumerate(contributions, 1)]
    return data


LAMMERT = {'xml_redner_id': '11001274', 'display_name': 'Dr. Norbert Lammert', 'first_name': 'Norbert',
           'last_name': 'Lammert', 'fraktion': 'CDU/CSU', 'role': 'Präsident'}
DREYER = {'xml_redner_id': '11009999', 'display_name': 'Malu Dreyer', 'role': 'Präsidentin des Bundesrates'}
ADA = {'xml_redner_id': '5', 'display_name': 'Ada Lovelace', 'fraktion': 'SPD'}


class RoleCheckTests(unittest.TestCase):
    def test_a_listed_guest_or_presidium_ansprache_passes_and_an_unlisted_guest_role_still_fails(self):
        # T14.
        self.assertEqual(derive.find_unmapped_sprechrollen(
            [store_report('18/223', [ADA], [('ansprache', DREYER), ('ansprache', LAMMERT)])]), {})
        derive.check_sprechrollen([store_report('18/223', [ADA], [('ansprache', DREYER)])])
        self.assertEqual(derive.find_unmapped_sprechrollen([store_report('18/223', [DREYER])]),
                         {'Präsidentin des Bundesrates': ['18/223 ID1822301']})
        self.assertEqual(derive.find_unmapped_sprechrollen([store_report('18/223', [ADA], [('kurzintervention', DREYER)])]),
                         {'Präsidentin des Bundesrates': ['18/223 IDC1']})

    def test_a_presidium_role_on_a_rede_raises_the_adr_0004_error(self):
        # T15, with the role printed with the name (18/178).
        for speaker in [LAMMERT, {**LAMMERT, 'role': 'Präsident Dr. Norbert Lammert'},
                        {**LAMMERT, 'role': 'Vizepräsident in'}]:
            with self.subTest(role=speaker['role']):
                with self.assertRaises(derive.PresidiumRoleError) as caught:
                    derive.check_sprechrollen([store_report('18/178', [ADA, speaker])])
                self.assertIn('18/178 ID1817802', str(caught.exception))
                self.assertIn('ADR 0004', str(caught.exception))
                self.assertIsInstance(caught.exception, derive.SprechrolleError)


class PersistTests(unittest.TestCase):
    def test_an_ansprache_row(self):
        # T16: sprechrolle NULL, fraktion as printed, the person bound; no Reden figure moves.
        import persist_dip_pulse_store as pulse_store
        conn = pulse_store.connect(Path(tempfile.mkdtemp()) / 'store.sqlite')
        self.addCleanup(conn.close)
        pulse_store.persist_report(conn, store_report('18/178', [ADA], [('ansprache', LAMMERT), ('ansprache', DREYER)]))
        rows = {row[0]: row[1:] for row in conn.execute(
            'SELECT m.display_name, c.kind, c.fraktion, c.sprechrolle, c.mp_id IS NOT NULL '
            'FROM contributions c JOIN mps m ON m.id = c.mp_id')}
        self.assertEqual(rows, {'Dr. Norbert Lammert': ('ansprache', 'CDU/CSU', None, 1),
                                'Malu Dreyer': ('ansprache', None, None, 1)})
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM speeches').fetchone()[0], 1)
        recipe = __import__('build_dip_pulse_site').RECIPES_BY_ID['r2-textanteil-fraktion']
        self.assertEqual([(r['fraktion'], r['reden']) for r in conn.execute(recipe['sql'])], [('SPD', 1)])


def site_report(xml, entries, number):
    sk.use_reviewed_units(list(entries))
    try:
        parsed = dip.parse_protocol_xml(xml)
    finally:
        sk.use_reviewed_units([])
    return {'protocol': {'id': number, 'dokumentnummer': number, 'datum': '2025-05-06',
                         'pdf_url': 'https://dserver.bundestag.de/btp/21/21002.pdf'},
            'agenda_items': [dict(index=t['index'], **dip.xml_top_fields(t)) for t in parsed['agenda_items']],
            'xml_contributions': parsed.get('sitting_contributions', []),
            'validation_summary': dip.contribution_summary(parsed['agenda_items'], parsed.get('sitting_contributions'))}


class SiteTests(unittest.TestCase):
    def build(self, report):
        import build_dip_pulse_site as build
        import persist_dip_pulse_store as pulse_store
        import render_dip_pulse_html as html
        tmp = Path(tempfile.mkdtemp())
        path = tmp / 'store.sqlite'
        self.assertTrue(build.rebuild_database_from_entries(path, [{'report': report}]).replaced)
        conn = pulse_store.connect(path)
        self.addCleanup(conn.close)
        people, lookup = build.collect_abgeordnete(conn)
        return conn, people, html.render_html(report, mp_lookup=lookup)

    def test_the_dossier_and_the_person_page_show_an_ansprache(self):
        # T17.
        import build_dip_pulse_site as build
        xml = sitting(rede('ID1', SCHAEUBLE, '<p>Liebe Kolleginnen und Kollegen, ich danke Ihnen.</p>'
                           '<name>Präsident Dr. Wolfgang Schäuble:</name><p>Das Wort hat die Kollegin Meier.</p>')
                      + rede('ID2', MEMBER_A, DEBATE), wp=19, nr=73)
        conn, people, page = self.build(site_report(xml, [entry('ID1', '11001938', 'ansprache', '19/73')], '19/73'))
        self.assertIn('Weitere Beiträge, keine Reden und nicht mitgezählt: 1 Ansprache.', page)
        self.assertIn('<em>Ansprache · Präsident</em>', page)
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM speeches').fetchone()[0], 1)
        schaeuble = next(p for p in people if (p.get('contribution_counts') or {}).get('ansprache'))
        panel = build.render_contributions_panel(schaeuble)
        self.assertIn('<span>Ansprachen</span><strong>1</strong>', panel)
        self.assertIn('Erwiderungen, Ansprachen sowie Fragen und Antworten zählen gesondert.', panel)
        # The role printed with the name (18/178) is shown without it.
        import render_dip_pulse_html as html
        card = html.render_contribution_details({'index': 1, 'xml_contributions': [{
            'kind': 'ansprache', 'sequence': 1, 'rede_id': 'ID1', 'text': 'Gedenkworte.',
            'speaker': {'display_name': 'Dr. Norbert Lammert', 'first_name': 'Norbert', 'last_name': 'Lammert',
                        'role': 'Präsident Dr. Norbert Lammert'}}]}, {'id': '18/178'})
        self.assertIn('<em>Ansprache · Präsident</em>', card)

    def test_a_sitting_whose_every_rede_is_procedural(self):
        # T21: 18/4, 20/5, 21/2's shape. 0 Reden is a real zero, not an extraction gap.
        import build_dip_pulse_site as build
        minister = redner('11000003', 'Ministerin', role='Bundesministerin für Bildung', first='Eva')
        xml = sitting(rede('ID1', MEMBER_A, '<p>Ich nehme die Wahl an.</p>')
                      + rede('ID2', minister, '<p>Ich schwöre es, so wahr mir Gott helfe.</p>'),
                      wp=21, nr=2, heading='Wahl des Bundeskanzlers')
        report = site_report(xml, [entry('ID1', '11000001', 'procedural', '21/2', 'acceptance'),
                                   entry('ID2', '11000003', 'procedural', '21/2', 'oath answer')], '21/2')
        conn, _people, page = self.build(report)
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM speeches').fetchone()[0], 0)
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM contributions').fetchone()[0], 0)
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM protocols').fetchone()[0], 1)
        self.assertNotIn('Keine Reden im XML', page)
        self.assertNotIn('0 von 0', page)
        self.assertNotIn('Redeanteil <strong>', page)
        self.assertIn('Keine Reden in dieser Sitzung: Was das Protokoll als Rede druckt, sind Verfahrensschritte '
                      '(Annahme einer Wahl, Eid, Sitzungsleitung) – kein Ranking möglich.', page)
        self.assertIn('Keine Reden in dieser Sitzung, daher kein Rede- und kein Textanteil.', page)
        self.assertIn('Keine Reden: Was das Protokoll hier als Rede druckt, sind Verfahrensschritte '
                      '(Annahme einer Wahl, Eid, Sitzungsleitung), die nicht als Rede zählen.', page)
        for recipe_id in ('r2-textanteil-fraktion', 'r5-vorgaenge-meiste-reden'):  # r1 needs the export's mp_canonical
            recipe = build.RECIPES_BY_ID[recipe_id]
            with self.subTest(recipe=recipe_id):
                self.assertEqual(conn.execute(recipe['sql']).fetchall(), [])


class KindListTests(unittest.TestCase):
    def test_every_kind_has_a_label_and_is_in_contexts_beitrag_list(self):
        # T18, derived from the code: no hand-synced list.
        import re
        context = (_support.ROOT / 'CONTEXT.md').read_text(encoding='utf-8')
        beitrag = next(line for line in context.splitlines() if line.startswith('Something said in a Sitzung'))
        listed = re.search(r'Each has a Kind \(([^)]*)\)', beitrag).group(1)
        self.assertEqual(sorted(re.findall(r'`([a-z_]+)`', listed)), sorted(sk.CONTRIBUTION_KINDS))
        for kind in sk.CONTRIBUTION_KINDS:
            self.assertIn(kind, sk.KIND_LABELS)
            self.assertIn(kind, sk.REDE_STATUS.keys() | sk.NOT_REDE_KINDS)
        self.assertEqual(derive.SIDELESS_KINDS, {sk.ANSPRACHE})


CENSUS_TOOLS = ('docs/plans/adr-0004-census/census.py', 'docs/plans/adr-0004-census/review.py',
                'docs/plans/adr-0004-census/measure.py', 'docs/plans/adr-0004-census/sweep.py')


class CensusToolTests(unittest.TestCase):
    def test_the_census_tools_still_compile(self):
        # Verification 7 re-runs them before each release; a syntax error there
        # would only show at that moment. They need the store, so only compile here.
        import py_compile
        for path in CENSUS_TOOLS:
            with self.subTest(path=path):
                py_compile.compile(str(_support.ROOT / path), cfile=str(Path(tempfile.mkdtemp()) / 'x.pyc'), doraise=True)

    def test_the_shipped_list_and_entry_points_are_covered(self):
        # Files this suite exercises, named so the pre-gate maps them here:
        # scripts/reviewed_units.json, scripts/extract_demo_fixture.py, tests/_support.py.
        for path in ('scripts/reviewed_units.json', 'scripts/extract_demo_fixture.py', 'tests/_support.py'):
            self.assertTrue((_support.ROOT / path).is_file(), path)
        self.assertEqual(sk.REVIEWED_UNITS_PATH, _support.ROOT / 'scripts/reviewed_units.json')


STORE_XML = Path('/Users/luca/Projects/poliwatch/.context/dip-pulse-site/data/xml')
CENSUS = _support.ROOT / 'docs' / 'plans' / 'adr-0004-census.tsv'


@unittest.skipUnless(STORE_XML.is_dir(), 'reference store XML not present')
class CensusReplayTests(unittest.TestCase):
    """T23: every census row of a kept sitting reads as the census proposed under
    the branch parser and the shipped list."""

    def test_census_rows_of_kept_sittings(self):
        rows = [r for r in csv.DictReader(CENSUS.open(encoding='utf-8'), delimiter='\t') if r['stored'] == 'kept']
        by_sitting = {}
        for row in rows:
            by_sitting.setdefault(row['sitting'], []).append(row)
        with _support.shipped_reviewed_units():
            for number, sitting_rows in sorted(by_sitting.items()):
                wp, nr = number.split('/')
                with self.subTest(sitting=number):
                    parsed = dip.parse_protocol_xml((STORE_XML / f'plenarprotokoll-{wp}-{nr}.xml').read_text(encoding='utf-8'))
                    speeches = {s['rede_id'] for t in parsed['agenda_items'] for s in t['speeches']}
                    procedural = {d['source_rede_id'] for t in parsed['agenda_items'] for d in t['xml_turn_diagnostics']
                                  if d['evidence'].startswith(('procedural (reviewed)', 'Sitzungsleitung (reviewed)'))}
                    kinds = {c['rede_id']: c['kind'] for t in parsed['agenda_items'] for c in t['contributions']}
                    for row in sitting_rows:
                        if row['marker']:
                            continue  # a nested turn (Zwischenfrage), unchanged by this rule
                        if row['proposed_kind'] == 'procedural':
                            self.assertIn(row['rede_id'], procedural, row['rede_id'])
                            self.assertNotIn(row['rede_id'], speeches, row['rede_id'])
                        elif row['parser_today'] == 'Rede':
                            self.assertIn(row['rede_id'], speeches, row['rede_id'])
                        else:
                            self.assertEqual(kinds.get(row['rede_id']), row['parser_today'], row['rede_id'])


if __name__ == '__main__':
    unittest.main()
