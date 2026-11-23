"""Speakers printed as <name> who are not the chair (ADR 0004 amendment
2026-11-22, docs/plans/name-tag-speakers.md): each is stored as the reviewed
list says, and an unlisted one is withheld or refuses its sitting."""

import json
import tempfile
import unittest
from pathlib import Path

import _support
import reviewed_units
import speech_kinds as sk
import validate_dip_protocol as dip
from test_presidium_kinds import entry, redner, rede

HOST = redner('11000001', 'Meier', 'SPD', first='Anna', printed='Anna Meier (SPD):')
OTHER = redner('11000002', 'Gast', 'CDU/CSU', first='Bernd', printed='Bernd Gast (CDU/CSU):')
CHAIR = '<name>Vizepräsidentin Edelgard Bulmahn: </name>'
SPEECH = '<p>Frau Präsidentin! Liebe Kolleginnen und Kollegen! Eine Rede zur Sache mit Inhalt.</p>'


def name(tag):
    return f'<name>{tag} : </name>\n'


def listed(rede_id, tag, kind, redner_id, sitting_='18/30'):
    return {**entry(rede_id, redner_id, kind, sitting_), 'name': tag}


def document(body, wp=18, nr=30, heading='Haushaltsgesetz 2014', beginn=''):
    return (f'<dbtplenarprotokoll wahlperiode="{wp}" sitzung-nr="{nr}"><sitzungsverlauf>'
            f'<sitzungsbeginn>{beginn}</sitzungsbeginn>'
            f'<tagesordnungspunkt top-id="T1"><p klasse="T_NaS">{heading}</p>{body}</tagesordnungspunkt>'
            f'</sitzungsverlauf></dbtplenarprotokoll>')


def parse(body, entries=(), **kwargs):
    reviewed_units.use(list(entries))
    try:
        return dip.parse_protocol_xml(document(body, **kwargs))
    finally:
        reviewed_units.use([])


def top(parsed):
    return parsed['agenda_items'][0]


def speeches(parsed):
    return [(s['rede_id'], s['speaker']['xml_redner_id'], s['text']) for s in top(parsed)['speeches']]


class RedeTests(unittest.TestCase):
    def test_a_listed_rede_inside_another_splits_off_as_the_named_speakers_rede(self):
        body = rede('ID1', HOST, SPEECH + CHAIR + '<p>Jetzt hat die Kollegin Sylvia Pantel das Wort.</p>'
                    + name('Sylvia Pantel (CDU/CSU)') + '<p>Sehr geehrte Frau Präsidentin! Meine erste Rede.</p>'
                    + CHAIR + '<p>Herzlichen Glückwunsch. Nun Frau Yüksel.</p>'
                    + name('Gülistan Yüksel (SPD)') + '<p>Danke schön. – Frau Präsidentin! Noch eine Rede.</p>')
        parsed = parse(body, [listed('ID1', 'Sylvia Pantel (CDU/CSU)', 'name_rede', '11004079'),
                              listed('ID1', 'Gülistan Yüksel (SPD)', 'name_rede', '11004461')])
        self.assertEqual([(rid, speaker) for rid, speaker, _ in speeches(parsed)],
                         [('ID1', '11000001'), ('ID1:2', '11004079'), ('ID1:2:2', '11004461')])
        pantel = top(parsed)['speeches'][1]['speaker']
        self.assertEqual((pantel['display_name'], pantel['last_name'], pantel['fraktion']), ('Sylvia Pantel', 'Pantel', 'CDU/CSU'))
        # The opening without a salutation splits too, because the entry says it is a Rede.
        self.assertEqual(speeches(parsed)[2][2], 'Danke schön. – Frau Präsidentin! Noch eine Rede.')
        self.assertEqual(top(parsed)['withheld'], [])

    def test_a_rede_outside_any_rede_is_wrapped_under_its_ordinal(self):
        body = (CHAIR + '<p>Das Wort hat Frau Bundesministerin Schwesig.</p>'
                + name('Manuela Schwesig, Bundesministerin für Familie, Senioren, Frauen und Jugend')
                + '<p>Frau Präsidentin! Meine Damen und Herren! Die Rede der Ministerin.</p>'
                + '<kommentar>(Beifall bei der SPD)</kommentar>'
                + rede('ID2', OTHER, SPEECH))
        parsed = parse(body, [listed('N2', 'Manuela Schwesig, Bundesministerin für Familie, Senioren, Frauen und Jugend',
                                     'name_rede', '999990002')])
        self.assertEqual([(rid, speaker) for rid, speaker, _ in speeches(parsed)], [('N2', '999990002'), ('ID2', '11000002')])
        schwesig = top(parsed)['speeches'][0]['speaker']
        self.assertEqual(schwesig['role'], 'Bundesministerin für Familie, Senioren, Frauen und Jugend')
        self.assertEqual(dip.derive.sprechrolle(schwesig), 'bundesregierung')

    def test_a_speaker_without_a_redner_id_is_bound_by_dip_person(self):
        body = (CHAIR + '<p>Das Wort hat Senatorin Blankau-Rosenfeldt.</p>'
                + name('Jutta Blankau-Rosenfeldt, Senatorin (Hamburg)') + SPEECH)
        parsed = parse(body, [listed('N2', 'Jutta Blankau-Rosenfeldt, Senatorin (Hamburg)', 'name_rede', 'dip:1828')])
        speaker = top(parsed)['speeches'][0]['speaker']
        self.assertEqual((speaker['xml_redner_id'], speaker['dip_person_id']), (None, '1828'))
        self.assertEqual(dip.derive.sprechrolle(speaker), 'bundesrat')


class BeitragTests(unittest.TestCase):
    ASKED = (CHAIR + '<p>Frau Kollegin, gestatten Sie eine Zwischenfrage des Kollegen Neu?</p>'
             + redner('11000001', 'Meier', 'SPD', first='Anna', printed='Anna Meier (SPD):') + '<p>Ja, bitte.</p>'
             + CHAIR + '<p>Bitte.</p>'
             + name('Dr. Alexander S. Neu (DIE LINKE)') + '<p>Frau Kollegin, ist das so?</p>'
             + redner('11000001', 'Meier', 'SPD', first='Anna', printed='Anna Meier (SPD):') + '<p>Ja, so ist es.</p>')

    def test_a_listed_zwischenfrage_is_the_named_members_beitrag(self):
        parsed = parse(rede('ID1', HOST, SPEECH + self.ASKED),
                       [listed('ID1', 'Dr. Alexander S. Neu (DIE LINKE)', 'name_zwischenfrage', '11004361')])
        nested = [(c['kind'], c['rede_id'], c['speaker']['xml_redner_id']) for c in top(parsed)['contributions']]
        self.assertEqual(nested, [(sk.ZWISCHENFRAGE, 'nested:ID1:3', '11004361')])
        self.assertNotIn('ist das so', speeches(parsed)[0][2])

    def test_a_listed_kind_the_rules_do_not_read_stops_the_run(self):
        with self.assertRaises(reviewed_units.ReviewedUnitsError) as caught:
            parse(rede('ID1', HOST, SPEECH + self.ASKED),
                  [listed('ID1', 'Dr. Alexander S. Neu (DIE LINKE)', 'name_befragung_frage', '11004361')])
        self.assertIn('listed as befragung_frage, but the rules read a zwischenfrage', str(caught.exception))

    def test_own_words_join_the_owner_and_a_wrong_owner_stops_the_run(self):
        body = rede('ID1', HOST, SPEECH + CHAIR + '<p>Sie müssen zum Schluss kommen.</p>'
                    + name('Anna Meier (SPD )') + '<p>Mein letzter Satz.</p>')
        parsed = parse(body, [listed('ID1', 'Anna Meier (SPD )', 'name_own_words', '11000001')])
        self.assertTrue(speeches(parsed)[0][2].endswith('Mein letzter Satz.'))
        with self.assertRaises(reviewed_units.ReviewedUnitsError):
            parse(body, [listed('ID1', 'Anna Meier (SPD )', 'name_own_words', '11000002')])


class NotStoredTests(unittest.TestCase):
    def test_an_oath_answer_in_a_listed_procedural_rede_stays_procedural(self):
        minister = redner('11002000', 'Maizière', 'CDU/CSU', first='Thomas', printed='Dr. Thomas de Maizière, Bundesminister des Innern:')
        body = rede('ID1', minister, '<p>Ich schwöre es, so wahr mir Gott helfe.</p>' + CHAIR + '<p>Herr Maas.</p>'
                    + name('Heiko Maas, Bundesminister der Justiz und für Verbraucherschutz')
                    + '<p>Herr Präsident, ich schwöre es, so wahr mir Gott helfe.</p>')
        parsed = parse(body, [entry('ID1', '11002000', 'procedural', '18/30'),
                              listed('ID1', 'Heiko Maas, Bundesminister der Justiz und für Verbraucherschutz', 'name_procedural', '')],
                       heading='Eidesleistung der Bundesminister')
        self.assertEqual((top(parsed)['speeches'], top(parsed)['contributions'], top(parsed)['withheld']), ([], [], []))
        oath = [d for d in top(parsed)['xml_turn_diagnostics'] if 'Heiko Maas' in d['speaker']['display_name']]
        self.assertEqual([(d['treatment'], d['text']) for d in oath],
                         [('procedural', 'Herr Präsident, ich schwöre es, so wahr mir Gott helfe.')])

    def test_a_guests_address_in_the_opening_is_one_ansprache_without_a_redner_id(self):
        beginn = ('<name>Präsident Dr. Norbert Lammert:</name><p>Eröffnung.</p><name>Wolf Biermann:</name><p>Erster Teil.</p>'
                  '<name>Präsident Dr. Norbert Lammert:</name><p>Zwischenruf des Präsidenten.</p><name>Wolf Biermann:</name><p>Zweiter Teil.</p>'
                  '<name>Präsident Dr. Norbert Lammert:</name><p>Danke.</p>')
        parsed = parse(rede('ID1', HOST, SPEECH),
                       [listed('N2', 'Wolf Biermann', 'name_ansprache', ''), listed('N4', 'Wolf Biermann', 'name_ansprache', '')],
                       beginn=beginn)
        self.assertEqual([(c['kind'], c['rede_id'], c['speaker'], c['text']) for c in parsed['sitting_contributions']],
                         [(sk.ANSPRACHE, 'N2', {'xml_redner_id': None, 'display_name': 'Wolf Biermann'}, 'Erster Teil.\nZweiter Teil.')])

    def test_a_remark_is_stored_nowhere(self):
        body = CHAIR + '<p>Das Wort hat Bartsch.</p>' + name('Dr. Dietmar Bartsch (DIE LINKE)') + '<p>Ein Zuruf.</p>' + rede('ID1', HOST, SPEECH)
        parsed = parse(body, [listed('N2', 'Dr. Dietmar Bartsch (DIE LINKE)', 'name_remark', '')])
        self.assertEqual([rid for rid, _, _ in speeches(parsed)], ['ID1'])
        self.assertEqual(top(parsed)['contributions'], [])


class RefusalTests(unittest.TestCase):
    def test_an_unlisted_speaker_inside_a_rede_withholds_that_rede_and_keeps_the_sitting(self):
        body = rede('ID1', HOST, SPEECH + CHAIR + '<p>Frau Pantel.</p>' + name('Sylvia Pantel (CDU/CSU)') + SPEECH) + rede('ID2', OTHER, SPEECH)
        parsed = parse(body)
        self.assertEqual([(w['rede_id'], w['reason']) for w in top(parsed)['withheld']], [('ID1', 'unreviewed_name_speaker')])
        self.assertEqual([rid for rid, _, _ in speeches(parsed)], ['ID2'])
        self.assertIn('unreviewed_name_speaker', sk.WITHHELD_REASONS)

    def test_an_unlisted_speaker_outside_any_rede_refuses_the_sitting(self):
        with self.assertRaisesRegex(dip.UnlistedNameSpeakerError, r'outside any <rede> has no entry') as caught:
            parse(CHAIR + '<p>Frau Pantel.</p>' + name('Sylvia Pantel (CDU/CSU)') + SPEECH)
        self.assertIsInstance(caught.exception, ValueError)
        self.assertNotIsInstance(caught.exception, reviewed_units.ReviewedUnitsError)

    # Value: protects=a sitting refused for an unlisted outside speaker names the reviewed-list fix, online and on replay;
    #   fails_when=it reads as corrupt XML ("--fetch-xml", "re-fetch"), whose re-fetch returns the same XML;
    #   why_new=code review of claude/name-speakers-build; seam=fetch_text stubbed
    def test_a_sitting_refused_for_an_unlisted_outside_speaker_names_the_reviewed_list(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import build_dip_pulse_site as build
        xml = document(CHAIR + '<p>Frau Pantel.</p>' + name('Sylvia Pantel (CDU/CSU)') + SPEECH)
        protocol = {"id": "p1", "dokumentnummer": "18/30", "fundstelle": {"xml_url": "https://dserver.bundestag.de/btp/18/18030.xml"}}
        reviewed_units.use([])
        try:
            with patch.object(dip, "fetch_text", return_value=xml), patch.object(dip, "enrich_with_api") as enrich, \
                    self.assertRaises(dip.DipError) as online:
                dip.build_report(SimpleNamespace(api_key="test", sleep=0), protocol)
            enrich.assert_not_called()
            with tempfile.TemporaryDirectory() as tmp:
                output_dir = Path(tmp)
                (output_dir / "data" / "xml").mkdir(parents=True)
                (output_dir / "data" / "xml" / "plenarprotokoll-18-30.xml").write_text(xml, encoding="utf-8")
                report = {"protocol": {"id": "p1", "dokumentnummer": "18/30"}, "agenda_items": []}
                (output_dir / "data" / "plenarprotokoll-18-30.json").write_text(json.dumps(report), encoding="utf-8")
                entries = build.load_existing_detail_entries(output_dir, [{"dokumentnummer": "18/30"}])
                with self.assertRaises(build.CachedReportError) as replay:
                    build.reparse_cached_xml(output_dir, entries)
        finally:
            reviewed_units.use([])
        self.assertTrue(online.exception.source_rejected)
        self.assertIn("scripts/reviewed_units.json with a name_* kind", str(online.exception))
        printed_replay = f"{replay.exception}. {build.cached_report_fix(replay.exception)}"
        self.assertIn("scripts/reviewed_units.json with a name_* kind", printed_replay)
        self.assertNotIn("not the Plenarprotokoll XML", printed_replay)
        self.assertNotIn("--fetch-xml", printed_replay)

    def test_a_stale_entry_stops_the_run(self):
        with self.assertRaisesRegex(reviewed_units.ReviewedUnitsError, r'ID1 <name>Sylvia Pantel \(CDU/CSU\)</name>'):
            parse(rede('ID1', HOST, SPEECH), [listed('ID1', 'Sylvia Pantel (CDU/CSU)', 'name_rede', '11004079')])

    def test_a_kind_that_cannot_stand_there_stops_the_run(self):
        body = rede('ID1', HOST, SPEECH + CHAIR + '<p>Bitte.</p>' + name('Sylvia Pantel (CDU/CSU)') + SPEECH)
        with self.assertRaisesRegex(reviewed_units.ReviewedUnitsError, r'cannot stand inside a <rede>'):
            parse(body, [listed('ID1', 'Sylvia Pantel (CDU/CSU)', 'name_ansprache', '')])

    def test_chair_forms_are_never_read_as_speakers(self):
        body = rede('ID1', HOST, SPEECH
                    + '<name>Vizepräsident Wolfgang Kubicki:</name><p>Bitte schön.</p>'
                    + '<name>Wolfgang Kubicki:</name><p>Herr Kollege, Ihre Zeit.</p>'
                    + '<name>Alterspräsident Dr. Hermann Otto Solms:</name><p>Weiter.</p>'
                    + HOST + '<p>Ich komme zum Schluss.</p>'
                    + '<name>(Vizepräsident Wolfgang Kubicki räuspert sich)</name>'
                    + '<p>Mein Schluss.</p>')
        parsed = parse(body)
        self.assertEqual(top(parsed)['withheld'], [])
        self.assertTrue(speeches(parsed)[0][2].endswith('Mein Schluss.'))


class MarkerTests(unittest.TestCase):
    def fields(self, tag):
        marker = dip.name_tag_marker(tag, '1', None)
        speaker = dip.parse_redner(marker.find('redner'))
        return speaker['display_name'], speaker['last_name'], speaker['fraktion'], speaker['role']

    def test_the_tag_gives_the_name_fields(self):
        self.assertEqual(self.fields('Christian Kühn ( Tübingen) (BÜNDNIS 90/DIE GRÜNEN)'),
                         ('Christian Kühn', 'Kühn', 'BÜNDNIS 90/DIE GRÜNEN', None))
        self.assertEqual(self.fields('Dr. Alexander S. Neu (DIE LINKE)'), ('Dr. Alexander S. Neu', 'Neu', 'DIE LINKE', None))
        self.assertEqual(self.fields('Bodo Ramelow, Ministerpräsident (Thüringen)'),
                         ('Bodo Ramelow', 'Ramelow', None, 'Ministerpräsident (Thüringen)'))

    def test_every_tag_of_the_shipped_list_reads_as_a_person_with_a_side(self):
        for item in (e for entries in reviewed_units.load().values() for e in entries
                     if e['kind'] in reviewed_units.NAME_KINDS and e['redner_id']):
            with self.subTest(item['sitting'], tag=item['name']):
                speaker = dip.parse_redner(dip.name_tag_marker(item['name'], item['redner_id'], None).find('redner'))
                self.assertTrue(speaker['last_name'])
                self.assertTrue(speaker['fraktion'] or dip.derive.sprechrolle(speaker), item['name'])



class MakeEntriesTests(unittest.TestCase):
    """The script that wrote the 145 entries reads the plan TSV's proposed ids
    as the owner decided (docs/plans/name-tag-speakers.md, section 4)."""

    def test_proposed_ids_become_redner_ids(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            'make_entries', _support.ROOT / 'docs/plans/name-tag-speakers/make_entries.py')
        make = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(make)
        cases = [
            ('rede', '999990003 (of 999990003, 999990030: the id of her 2014 sittings)', '999990003'),
            ('rede', '11003836 (her MdB-Stammdaten id, mdb_zugehoerigkeiten; no WP 18 XML prints one)', '11003836'),
            ('rede', 'none: bind by DIP person 1828', 'dip:1828'),
            ('own_words', "host owner's", '11000001'),
            ('oath_answer', '- (not stored)', ''),
            ('ansprache', 'none (guest; Ansprache)', ''),
            ('remark', '- (not stored)', ''),
        ]
        for kind, proposed, expected in cases:
            with self.subTest(proposed):
                row = {'kind': kind, 'proposed_redner_id': proposed, 'sitting': '18/30', 'name_tag': 'X'}
                self.assertEqual(make.redner_id(row, '11000001'), expected)
        with self.assertRaises(SystemExit):
            make.redner_id({'kind': 'rede', 'proposed_redner_id': 'unknown', 'sitting': '18/30', 'name_tag': 'X'}, None)

class LoaderTests(unittest.TestCase):
    def test_name_entries_are_checked(self):
        good = listed('ID1', 'Sylvia Pantel (CDU/CSU)', 'name_rede', '11004079')
        cases = {
            'no name': {k: v for k, v in good.items() if k != 'name'},
            'name on another kind': {**good, 'kind': 'withhold'},
            'tag with colon': {**good, 'name': 'Sylvia Pantel (CDU/CSU):'},
            'split part': {**good, 'rede_id': 'ID1:2'},
            'speaker on a remark': {**good, 'kind': 'name_remark'},
            'no speaker on a rede': {**good, 'redner_id': ''},
            'bad dip id': {**good, 'redner_id': 'dip:x'},
        }
        with tempfile.TemporaryDirectory() as tmp:
            for index, (label, data) in enumerate(cases.items()):
                with self.subTest(label):
                    path = Path(tmp) / f'case{index}.json'
                    path.write_text(json.dumps({'entries': [data]}), encoding='utf-8')
                    with self.assertRaises(reviewed_units.ReviewedUnitsError):
                        reviewed_units.load(path)
            path = Path(tmp) / 'good.json'
            two = [good, {**good, 'name': 'Gülistan Yüksel (SPD)', 'redner_id': 'dip:1828'},
                   entry('ID1', '11000001', 'procedural', '18/30'), listed('N3', 'Wolf Biermann', 'name_ansprache', '')]
            path.write_text(json.dumps({'entries': two}), encoding='utf-8')
            self.assertEqual(len(reviewed_units.load(path)['18/30']), 4)


if __name__ == '__main__':
    unittest.main()
