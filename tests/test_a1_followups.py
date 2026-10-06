"""Source and cross-boundary contracts for A1 T1–T8 (D1/D3/D4)."""
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import _support
import _facts_fixture
import build_dip_pulse_site as build
import facts
import persist_dip_pulse_store as store
import render_dip_pulse_html as html
import speech_kinds as sk
import validate_dip_protocol as dip
from stable_ids import contribution_occurrence_id


def source(name):
    return (_support.FIXTURES / name).read_text()


def report(parsed, number='18/100'):
    return {'protocol': {'id': number, 'dokumentnummer': number, 'datum': '2015-04-23',
                         'pdf_url': 'https://dserver.bundestag.de/btp/18/18100.pdf'},
            'agenda_items': [dict(index=t['index'], **dip.xml_top_fields(t)) for t in parsed['agenda_items']],
            'xml_contributions': parsed.get('sitting_contributions', []),
            'validation_summary': dip.contribution_summary(parsed['agenda_items'], parsed.get('sitting_contributions'))}


class SourceRecoveryTests(unittest.TestCase):
    def test_historical_opening_questions_answers_and_role_parity(self):
        for number, expected in [('18-13', (13, 91, 94)), ('18-84', (25, 51, 51))]:
            with self.subTest(number=number):
                parsed = dip.parse_protocol_xml(source(f'a1-historical-{number}.xml'))
                b, f = parsed['agenda_items']
                self.assertEqual(len(b['speeches']), 1)
                self.assertEqual(sk.kind_counts([c for c in b['contributions'] if not c['rede_id'].startswith('nested:')]), {'befragung_frage': expected[0], 'befragung_antwort': expected[0]})
                self.assertEqual(sk.kind_counts(f['contributions']), {'fragestunde_antwort': expected[1], 'fragestunde_frage': expected[2]})
                self.assertEqual(store.derive.sprechrolle(b['speeches'][0]['speaker']), 'bundesregierung')
                for c in b['contributions'] + f['contributions']:
                    if c['kind'].endswith('antwort'):
                        self.assertEqual(store.derive.sprechrolle(c['speaker']), 'bundesregierung')

    def test_recovery_is_occurrence_specific_and_conflict_refuses(self):
        historical = dip.ET.fromstring(source('a1-role-19-13.xml')).find('redner')
        self.assertEqual(sk.speaker_class(historical), sk.OFFICIAL)
        self.assertEqual(store.derive.sprechrolle(dip.parse_redner(historical)), 'bundesregierung')
        redner = dip.ET.fromstring('<redner id="1"><name><vorname>Maria</vorname><nachname>Böhmer</nachname><fraktion>CDU/CSU</fraktion></name></redner>')
        redner.tail = 'Dr. Maria Böhmer, Staatsministerin im Auswärtigen Amt:'
        self.assertEqual(sk.speaker_class(redner), sk.OFFICIAL)
        redner.tail = 'Dr. Maria Böhmer (CDU/CSU):'
        self.assertEqual(sk.speaker_class(redner), sk.MEMBER)
        dip.ET.SubElement(dip.ET.SubElement(redner.find('name'), 'rolle'), 'rolle_lang').text = 'Ministerpräsident (Hessen)'
        redner.tail = 'Maria Böhmer, Bundesministerin:'
        with self.assertRaisesRegex(ValueError, 'conflicting roles.*1'):
            dip.parse_redner(redner)

    def test_unresolved_befragung_contains_source_context(self):
        xml = '<dbtplenarprotokoll wahlperiode="18" sitzung-nr="84"><sitzungsverlauf><tagesordnungspunkt top-id="TOP1"><p klasse="T_ohne_NaS">Befragung der Bundesregierung</p><rede id="R1"><p klasse="redner"><redner id="X"><name><nachname>Unbekannt</nachname></name></redner></p><p>Text</p></rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>'
        with self.assertRaisesRegex(ValueError, '18/84 TOP1: unresolved Befragung turn R1 redner X'):
            dip.parse_protocol_xml(xml)

    def test_precise_grants_and_party_name_suffixes(self):
        self.assertFalse(sk.announces_kurzintervention('Eine Kurzintervention ist möglich. Frau Meier hat das Wort.', 'Meier'))
        self.assertFalse(sk.announces_kurzintervention('Kurzintervention von Gottschalk.', 'Ott'))
        self.assertTrue(sk.announces_kurzintervention('Zu einer Kurzintervention hat Ott das Wort.', 'Ott'))
        for suffix, party in [(' (AfD)', 'AfD'), (', CDU/CSU', 'CDU/CSU'), (' von Bündnis 90/Die Grünen', 'Bündnis 90/Die Grünen')]:
            self.assertEqual(sk.announced_asker_details('Frage 1 des Abgeordneten Dr. Gottfried Curio' + suffix + ':'), ('Dr. Gottfried Curio', party))
        self.assertIsNone(sk.announced_asker('Frage 1 von Ihnen:'))

    def test_source_pending_grant_and_later_refusal(self):
        self.assertTrue(sk.announces_kurzintervention(
            "Bevor ich den nächsten Redner aufrufe, gibt es zwei Kurzinterventionen zu der Rede von Herrn Töns. Es beginnt der fraktionslose Abgeordnete Robert Farle.",
            "Farle", "", 1000))
        self.assertFalse(sk.announces_kurzintervention(
            "Es gibt jetzt vier Wortmeldungen für Kurzinterventionen. Wir sind weit über den Zeitplan hinaus. Ich werde heute Abend nachsitzen. Aber ich werde jetzt keine Kurzintervention mehr zulassen und darf als letzte Wortmeldung Jürgen Hardt das Wort erteilen.",
            "Hardt", "CDU/CSU", 1000))

    def test_unique_silent_asker_and_ambiguous_candidates(self):
        for extra, linked in [('', True), ('<p klasse="redner"><redner id="2"><name><vorname>Ada</vorname><nachname>Test</nachname><fraktion>SPD</fraktion></name></redner></p><p>Zusatz</p>', False)]:
            xml = '<tagesordnungspunkt><p klasse="redner"><redner id="1"><name><vorname>Ada</vorname><nachname>Test</nachname><fraktion>SPD</fraktion></name></redner></p><p>Früher</p>' + extra + '<name>Präsident</name><p klasse="J">Frage 1 der Abgeordneten Ada Test (SPD):</p><p klasse="P">Schriftliche Frage?</p></tagesordnungspunkt>'
            turns, _ = sk.fragestunde_turns(dip.ET.fromstring(xml))
            question = turns[-1]
            self.assertEqual(question.redner is not None, linked)
            self.assertEqual(question.paragraphs, ['Schriftliche Frage?'])


class ContributionTests(unittest.TestCase):
    def test_source_refusals_need_and_accept_fresh_explicit_authorization(self):
        for sitting, rid, marker in [('20-127', 'ID2012711500', 3), ('20-58', 'ID205803400', 3),
                                     ('20-120', 'ID2012006500', 3), ('20-37', 'ID203711500', 4),
                                     ('21-36', 'ID213613700', 7), ('21-43', 'ID214305400', 4),
                                     ('21-56', 'ID215600500', 3), ('21-90', 'ID219002200', 4)]:
            with self.subTest(sitting=sitting):
                parsed = dip.parse_protocol_xml(source(f'offline-v5-renewed/{sitting}.xml'))
                unit = next(c for t in parsed['agenda_items'] for c in t['contributions']
                            if c['rede_id'] == f'nested:{rid}:{marker}')
                self.assertEqual(unit['kind'], sk.ZWISCHENFRAGE)

    def test_an_addressed_bystander_before_the_question_is_not_a_named_asker(self):
        xml = ('<dbtplenarprotokoll><sitzungsverlauf><tagesordnungspunkt><rede id="R">'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname><fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
               '<name>Präsident</name><p>Herr Neben, bitte Ruhe. Herr Haupt, gestatten Sie eine Frage des Kollegen Gast?</p>'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname><fraktion>SPD</fraktion></name></redner></p><p>Gerne.</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Neben</nachname><fraktion>SPD</fraktion></name></redner></p><p>Meine Frage?</p>'
               '</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        for placement in (xml, xml.replace('Herr Neben, bitte Ruhe. ', '').replace('Gast?</p>', 'Gast? Herr Neben, bitte Ruhe.</p>')):
            with self.assertRaisesRegex(ValueError, 'R marker 3'):
                dip.parse_protocol_xml(placement)

    def test_reviewed_faction_permissions_reject_an_unrelated_recipient(self):
        xml = source('offline-v5/plenarprotokoll-20-44.xml')
        root = dip.ET.fromstring(xml)
        rede = root.find(".//rede[@id='ID204403100']")
        marker = rede.findall("./p[@klasse='redner']")[2]
        marker.find('redner/name/fraktion').text = 'SPD'
        with self.assertRaisesRegex(ValueError, 'ID204403100 marker 3'):
            dip.parse_protocol_xml(dip.ET.tostring(root, encoding='unicode'))
        self.assertEqual(dip.nested_grant_names('Zwischenfrage vom Kollegen der Grünen'), None)

    def test_new_named_and_mixed_grants_reject_unrelated_recipients(self):
        for sitting, rid, marker, surname, faction in [
            ('21-47', 'ID214708400', 3, 'Andere', 'AfD'),
            ('21-47', 'ID214708400', 5, 'Andere', 'AfD'),
            ('20-57', 'ID205710600', 3, 'Andere', 'AfD'),
            ('20-208', 'ID2020801600', 3, 'Andere', 'SPD'),
            ('21-93', 'ID219311800', 5, 'Andere', 'AfD'),
        ]:
            root = dip.ET.fromstring(source(f'offline-v5/plenarprotokoll-{sitting}.xml'))
            rede = root.find(f".//rede[@id='{rid}']")
            name = rede.findall("./p[@klasse='redner']")[marker - 1].find('redner/name')
            name.find('nachname').text = surname
            name.find('fraktion').text = faction
            with self.subTest(sitting=sitting, marker=marker), self.assertRaisesRegex(ValueError, f'{rid} marker {marker}'):
                dip.parse_protocol_xml(dip.ET.tostring(root, encoding='unicode'))

    def test_question_addressee_is_not_its_asker(self):
        xml = ('<dbtplenarprotokoll><sitzungsverlauf><tagesordnungspunkt><rede id="R">'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname><fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
               '<name>Präsident</name><p>Der Abgeordnete Gast hat die Möglichkeit zu einer Zwischenfrage an den Abgeordneten Neben. – Bitte schön.</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Neben</nachname><fraktion>SPD</fraktion></name></redner></p><p>Meine Frage?</p>'
               '</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        with self.assertRaisesRegex(ValueError, 'R marker 2'):
            dip.parse_protocol_xml(xml)
        allowed = xml.replace('<nachname>Neben</nachname>', '<nachname>Gast</nachname>')
        self.assertEqual(dip.parse_protocol_xml(allowed)['agenda_items'][0]['contributions'][0]['speaker']['last_name'], 'Gast')

    def test_actual_refusal_after_acceptance_cancels_but_proven_banter_does_not(self):
        xml = source('offline-v5/plenarprotokoll-21-56.xml')
        self.assertTrue(dip.parse_protocol_xml(xml)['agenda_items'])
        for mutation in ('banter', 'neutral_chair', 'explicit'):
            root = dip.ET.fromstring(xml)
            rede = root.find(".//rede[@id='ID215612200']")
            for p in rede.findall('p'):
                if mutation in {'banter', 'neutral_chair'} and 'Hoffnungen nicht enttäuschen' in dip.elem_text(p):
                    p.text = 'Möchten Sie die Zwischenfrage wirklich zulassen?' if mutation == 'banter' else 'Vielen Dank.'
                elif mutation == 'explicit' and dip.elem_text(p) == 'Nein. Genau.':
                    p.text = 'Nein, ich lasse keine Zwischenfrage zu.'
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'ID215612200 marker 4'):
                dip.parse_protocol_xml(dip.ET.tostring(root, encoding='unicode'))

    def test_fresh_faction_authorization_requires_new_consent_after_refusal(self):
        xml = source('offline-v5/plenarprotokoll-20-51.xml')
        root = dip.ET.fromstring(xml)
        rede = root.find(".//rede[@id='ID205104600']")
        for p in rede.findall('p'):
            if dip.elem_text(p) == 'Von der CDU/CSU? – Ja.':
                p.text = 'Vielen Dank.'
        with self.assertRaisesRegex(ValueError, 'ID205104600 marker 4'):
            dip.parse_protocol_xml(dip.ET.tostring(root, encoding='unicode'))

    def test_named_exchange_after_refusal_requires_the_chair_floor(self):
        root = dip.ET.fromstring(source('offline-v5/plenarprotokoll-20-57.xml'))
        rede = root.find(".//rede[@id='ID205710600']")
        for p in rede.findall('p'):
            if 'Es sind noch fünf Sekunden. Aber bitte schön.' == dip.elem_text(p):
                p.text = 'Es sind noch fünf Sekunden.'
        with self.assertRaisesRegex(ValueError, 'ID205710600 marker 3'):
            dip.parse_protocol_xml(dip.ET.tostring(root, encoding='unicode'))

    def test_delegated_procedural_reply_requires_proven_identity_and_adjacent_target(self):
        xml = source('offline-v5/plenarprotokoll-20-191.xml')
        for mutation in ('requester', 'target', 'consent', 'boundary', 'duplicate'):
            root = dip.ET.fromstring(xml)
            rede = root.find(".//rede[@id='ID2019101000']")
            target = root.find(".//rede[@id='ID2019101100']")
            top = next(t for t in root.findall('.//tagesordnungspunkt') if rede in list(t))
            if mutation == 'requester':
                rede.findall("./p[@klasse='redner']")[1].find('redner').set('id', 'UNRELATED')
            elif mutation == 'target':
                target.find("./p[@klasse='redner']/redner/name/nachname").text = 'Andere'
            elif mutation == 'consent':
                for p in rede.findall('p'):
                    if 'Sind Sie einverstanden' in dip.elem_text(p):
                        p.text = 'Vielen Dank.'
            elif mutation == 'duplicate':
                top.append(copy.deepcopy(target))
            else:
                top.remove(target)
                dip.ET.SubElement(root.find('sitzungsverlauf'), 'tagesordnungspunkt').append(target)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'ID2019101000 marker 2'):
                dip.parse_protocol_xml(dip.ET.tostring(root, encoding='unicode'))

    def test_shortened_source_surname_requires_unique_local_candidate(self):
        for duplicate_name in ('Cademartori Andere', 'Cademartori Dujisin'):
            root = dip.ET.fromstring(source('offline-v5/plenarprotokoll-20-208.xml'))
            rede = root.find(".//rede[@id='ID2020801600']")
            clone = copy.deepcopy(rede.findall("./p[@klasse='redner']")[2])
            clone.find('redner').set('id', 'OTHER')
            clone.find('redner/name/nachname').text = duplicate_name
            rede.append(clone)  # even an empty source marker makes the alias ambiguous
            with self.subTest(name=duplicate_name), self.assertRaisesRegex(ValueError, 'ID2020801600 marker 3'):
                dip.parse_protocol_xml(dip.ET.tostring(root, encoding='unicode'))

    def test_interrupted_request_needs_acceptance_and_chair_floor_grant(self):
        xml = source('offline-v5/plenarprotokoll-20-207.xml')
        for missing in ('Ja, gerne.', 'Bitte schön.'):
            root = dip.ET.fromstring(xml)
            rede = root.find(".//rede[@id='ID2020707400']")
            for child in rede.findall('p'):
                if dip.elem_text(child) == missing:
                    child.text = ''
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, 'ID2020707400 marker 5'):
                dip.parse_protocol_xml(dip.ET.tostring(root, encoding='unicode'))

    def test_reply_attachment_requires_evidence_matching_identity_and_unique_same_top_target(self):
        xml = source('offline-v5/plenarprotokoll-21-35.xml')
        for mutation in ('evidence', 'identity', 'duplicate', 'top_boundary'):
            root = dip.ET.fromstring(xml)
            container = root.find(".//rede[@id='ID213505100']")
            target = root.find(".//rede[@id='ID213505200']")
            top = next(t for t in root.findall('.//tagesordnungspunkt') if target in list(t))
            if mutation == 'evidence':
                for p in container.findall('p'):
                    if 'Möchten Sie erwidern' in dip.elem_text(p):
                        p.text = 'Vielen Dank.'
            elif mutation == 'identity':
                target.find("./p[@klasse='redner']/redner").set('id', 'unrelated')
            elif mutation == 'duplicate':
                top.append(copy.deepcopy(target))
            else:
                top.remove(target)
                other = dip.ET.SubElement(root.find('sitzungsverlauf'), 'tagesordnungspunkt', {'top-id': 'other'})
                other.append(target)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'ID213505100 marker 2'):
                dip.parse_protocol_xml(dip.ET.tostring(root, encoding='unicode'))

    def test_resumption_cannot_attach_to_an_unrelated_original_speaker(self):
        root = dip.ET.fromstring(source('offline-v5/plenarprotokoll-21-43.xml'))
        original = root.find(".//rede[@id='ID214301600']")
        original.find("./p[@klasse='redner']/redner").set('id', 'unrelated')
        container = root.find(".//rede[@id='ID214301700']")
        for p in list(container):
            if p.tag == 'p' and dip.elem_text(p) == 'Alles gut.':
                container.remove(p)
        with self.assertRaisesRegex(ValueError, 'ID214301700 marker 4'):
            dip.parse_protocol_xml(dip.ET.tostring(root, encoding='unicode'))

    def test_short_reply_outside_a_proven_exchange_remains_unresolved(self):
        xml = ('<dbtplenarprotokoll><sitzungsverlauf><tagesordnungspunkt><rede id="R">'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname><fraktion>SPD</fraktion></name></redner></p>'
               '<p>Rede.</p><name>Präsident</name><p>Möchten Sie antworten?</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname><fraktion>SPD</fraktion></name></redner></p>'
               '<p>Ja.</p></rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        with self.assertRaisesRegex(ValueError, 'R marker 2'):
            dip.parse_protocol_xml(xml)

    def test_nested_remark_keeps_grant_across_same_speaker_resumption(self):
        xml = ('<dbtplenarprotokoll wahlperiode="21" sitzung-nr="1"><sitzungsverlauf>'
               '<tagesordnungspunkt top-id="T1"><rede id="R">'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
               '<name>Präsident:</name><p>Gestatten Sie eine Zwischenfrage von Gast?</p>'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Gerne.</p>'
               '<name>Präsident:</name><p>Herr Kollege.</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
               '<fraktion>Grüne</fraktion></name></redner></p><p>Ich möchte anmerken, dass ...</p>'
               '</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        parsed = dip.parse_protocol_xml(xml)
        self.assertEqual(parsed['agenda_items'][0]['contributions'][0]['kind'], 'zwischenfrage')
        self.assertEqual(parsed['agenda_items'][0]['contributions'][0]['speaker']['last_name'], 'Gast')

    def test_main_speaker_grant_after_generic_chair_question_is_evidence(self):
        xml = ('<dbtplenarprotokoll wahlperiode="21" sitzung-nr="1"><sitzungsverlauf>'
               '<tagesordnungspunkt top-id="T1"><rede id="R">'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
               '<name>Präsident:</name><p>Gestatten Sie eine Frage oder Bemerkung von Gast?</p>'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Ja, ich lasse die Zwischenfrage sehr gerne zu.</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
               '<fraktion>Grüne</fraktion></name></redner></p><p>Meine Frage ohne Satzzeichen</p>'
               '</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        parsed = dip.parse_protocol_xml(xml)
        self.assertEqual(parsed['agenda_items'][0]['contributions'][0]['speaker']['last_name'], 'Gast')

    def test_nested_speaker_acknowledgement_is_grant_evidence(self):
        xml = ('<dbtplenarprotokoll wahlperiode="21" sitzung-nr="1"><sitzungsverlauf>'
               '<tagesordnungspunkt top-id="T1"><rede id="R">'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
               '<fraktion>Grüne</fraktion></name></redner></p>'
               '<p>Herzlichen Dank, dass Sie die Frage zulassen. Ich wollte Sie fragen, ob ...</p>'
               '</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        parsed = dip.parse_protocol_xml(xml)
        self.assertEqual(parsed['agenda_items'][0]['contributions'][0]['kind'], 'zwischenfrage')
        refused = xml.replace('die Frage zulassen', 'die Frage nicht zulassen')
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 2'):
            dip.parse_protocol_xml(refused)

    def test_explicit_refusal_is_not_a_main_speaker_grant(self):
        xml = ('<dbtplenarprotokoll wahlperiode="21" sitzung-nr="1"><sitzungsverlauf>'
               '<tagesordnungspunkt top-id="T1"><rede id="R">'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Ich lasse keine Zwischenfrage zu.</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
               '<fraktion>Grüne</fraktion></name></redner></p><p>Eine Bemerkung.</p>'
               '</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 3'):
            dip.parse_protocol_xml(xml)
        for pending in [
            '<name>Präsident:</name><p>Gestatten Sie eine Zwischenfrage von Gast?</p>',
            '<p>Ich lasse die Zwischenfrage zu.</p>',
        ]:
            with self.subTest(pending=pending):
                refused = xml.replace('<p>Rede.</p>', '<p>Rede.</p>' + pending)
                with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 3'):
                    dip.parse_protocol_xml(refused)

    def test_multi_speaker_grant_applies_only_to_named_askers(self):
        xml = ('<dbtplenarprotokoll wahlperiode="21" sitzung-nr="1"><sitzungsverlauf>'
               '<tagesordnungspunkt top-id="T1"><rede id="R">'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
               '<name>Präsident:</name><p>Gestatten Sie eine Zwischenfrage des Kollegen Erster und der Kollegin Zweite?</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Erster</nachname>'
               '<fraktion>Grüne</fraktion></name></redner></p><p>Eine Bemerkung.</p>'
               '<name>Präsident:</name><p>Jetzt die Kollegin Zweite.</p>'
               '<p klasse="redner"><redner id="C"><name><nachname>Zweite</nachname>'
               '<fraktion>FDP</fraktion></name></redner></p><p>Eine weitere Bemerkung.</p>'
               '</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        parsed = dip.parse_protocol_xml(xml)
        self.assertEqual([c['speaker']['last_name'] for c in parsed['agenda_items'][0]['contributions']],
                         ['Erster', 'Zweite'])
        # Value: protects=named grants reject unrelated askers; fails_when=chair text bypasses the name guard; why_new=existing case names both granted askers; seam=none
        unrelated = xml.replace('<nachname>Erster</nachname>', '<nachname>Andere</nachname>')
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 2'):
            dip.parse_protocol_xml(unrelated)

    def test_named_grant_survives_main_resumption_without_authorizing_another_speaker(self):
        xml = ('<dbtplenarprotokoll wahlperiode="21" sitzung-nr="1"><sitzungsverlauf>'
               '<tagesordnungspunkt top-id="T1"><rede id="R">'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
               '<name>Präsident:</name><p>Gestatten Sie eine Zwischenfrage von Gast?</p>'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Gerne.</p>'
               '<p klasse="redner"><redner id="C"><name><nachname>Andere</nachname>'
               '<fraktion>FDP</fraktion></name></redner></p><p>Eine Bemerkung ohne Fragezeichen.</p>'
               '</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 3'):
            dip.parse_protocol_xml(xml)

    def test_three_named_askers_include_first_name_before_grammatical_genitives(self):
        xml = ('<dbtplenarprotokoll wahlperiode="21" sitzung-nr="1"><sitzungsverlauf>'
               '<tagesordnungspunkt top-id="T1"><rede id="R">'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
               '<name>Präsident:</name><p>Gestatten Sie eine Zwischenfrage des Kollegen Müller, des Kollegen Schmidt und der Kollegin Weber?</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Müller</nachname>'
               '<fraktion>Grüne</fraktion></name></redner></p><p>Eine Bemerkung.</p>'
               '<name>Präsident:</name><p>Jetzt Kollege Schmidt.</p>'
               '<p klasse="redner"><redner id="C"><name><nachname>Schmidt</nachname>'
               '<fraktion>FDP</fraktion></name></redner></p><p>Eine weitere Bemerkung.</p>'
               '<name>Präsident:</name><p>Jetzt Kollegin Weber.</p>'
               '<p klasse="redner"><redner id="D"><name><nachname>Weber</nachname>'
               '<fraktion>CDU/CSU</fraktion></name></redner></p><p>Noch eine Bemerkung.</p>'
               '</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        parsed = dip.parse_protocol_xml(xml)
        self.assertEqual([c['speaker']['last_name'] for c in parsed['agenda_items'][0]['contributions']],
                         ['Müller', 'Schmidt', 'Weber'])

    def test_explicit_refusal_clears_remembered_nested_speaker(self):
        xml = ('<dbtplenarprotokoll wahlperiode="21" sitzung-nr="1"><sitzungsverlauf>'
               '<tagesordnungspunkt top-id="T1"><rede id="R">'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
               '<name>Präsident:</name><p>Gestatten Sie eine Zwischenfrage von Gast?</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
               '<fraktion>Grüne</fraktion></name></redner></p><p>Eine Frage?</p>'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Ich lasse keine weitere Zwischenfrage zu.</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
               '<fraktion>Grüne</fraktion></name></redner></p><p>Eine weitere Bemerkung.</p>'
               '</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 4'):
            dip.parse_protocol_xml(xml)
        for authorization, continuation in [
            ('', 'Eine weitere Frage?'),
            ('<p>Ich lasse die Zwischenfrage zu.</p>', 'Eine weitere Bemerkung.'),
            ('<name>Präsident:</name><p>Gestatten Sie eine weitere Zwischenfrage von Gast?</p>'
             '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
             '<fraktion>SPD</fraktion></name></redner></p><p>Gerne.</p>',
             'Eine weitere Bemerkung.'),
        ]:
            with self.subTest(authorization=authorization):
                renewed = xml.replace(
                    '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
                    '<fraktion>Grüne</fraktion></name></redner></p><p>Eine weitere Bemerkung.</p>',
                    authorization + '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
                    '<fraktion>Grüne</fraktion></name></redner></p><p>' + continuation + '</p>')
                if not authorization:
                    with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 4'):
                        dip.parse_protocol_xml(renewed)
                else:
                    parsed = dip.parse_protocol_xml(renewed)
                    self.assertEqual(parsed['agenda_items'][0]['contributions'][-1]['speaker']['last_name'], 'Gast')

    def test_grant_does_not_authorize_a_second_unrelated_nested_speaker(self):
        xml = ('<dbtplenarprotokoll wahlperiode="21" sitzung-nr="1"><sitzungsverlauf>'
               '<tagesordnungspunkt top-id="T1"><rede id="R">'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
               '<name>Präsident:</name><p>Gestatten Sie eine Zwischenfrage von Gast?</p>'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Gerne.</p>'
               '<name>Präsident:</name><p>Herr Kollege.</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
               '<fraktion>Grüne</fraktion></name></redner></p><p>Ich möchte anmerken.</p>'
               '<p klasse="redner"><redner id="C"><name><nachname>Andere</nachname>'
               '<fraktion>FDP</fraktion></name></redner></p><p>Eine Mitteilung.</p>'
               '</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R marker 4'):
            dip.parse_protocol_xml(xml)

    def test_same_nested_speaker_can_resume_after_the_main_speaker_replies(self):
        xml = ('<dbtplenarprotokoll wahlperiode="20" sitzung-nr="101"><sitzungsverlauf>'
               '<tagesordnungspunkt top-id="T1"><rede id="R">'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>CDU/CSU</fraktion></name></redner></p><p>Rede.</p>'
               '<name>Präsident:</name><p>Herr Haupt, lassen Sie eine Zwischenfrage zu?</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
               '<fraktion>Grüne</fraktion></name></redner></p><p>Eine Bemerkung ohne Fragezeichen.</p>'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>CDU/CSU</fraktion></name></redner></p><p>Was meinen Sie?</p>'
               '<name>Präsident:</name><p>Kommen Sie bitte zum Schluss Ihrer Frage.</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
               '<fraktion>Grüne</fraktion></name></redner></p><p>Erklären Sie uns doch mal.</p>'
               '</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        parsed = dip.parse_protocol_xml(xml)
        nested = parsed['agenda_items'][0]['contributions']
        self.assertEqual([c['rede_id'] for c in nested], ['nested:R:2', 'nested:R:4'])

    def test_question_mark_evidence_carries_through_chair_interruption(self):
        xml = ('<dbtplenarprotokoll wahlperiode="21" sitzung-nr="1"><sitzungsverlauf>'
               '<tagesordnungspunkt top-id="T1"><rede id="R">'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
               '<fraktion>Grüne</fraktion></name></redner></p><p>Was meinen Sie?</p>'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Ich antworte darauf.</p>'
               '<name>Präsident:</name><p>Kommen Sie bitte zum Schluss Ihrer Frage.</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
               '<fraktion>Grüne</fraktion></name></redner></p><p>Das war der Punkt.</p>'
               '</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        parsed = dip.parse_protocol_xml(xml)
        self.assertEqual([c['rede_id'] for c in parsed['agenda_items'][0]['contributions']],
                         ['nested:R:2', 'nested:R:4'])

    def test_nested_grant_does_not_cross_rede_boundary(self):
        xml = ('<dbtplenarprotokoll wahlperiode="21" sitzung-nr="1"><sitzungsverlauf>'
               '<tagesordnungspunkt top-id="T1">'
               '<rede id="R1"><p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
               '<fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
               '<name>Präsident:</name><p>Gestatten Sie eine Zwischenfrage von Gast?</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
               '<fraktion>Grüne</fraktion></name></redner></p><p>Bemerkung.</p></rede>'
               '<rede id="R2"><p klasse="redner"><redner id="C"><name><nachname>Andere</nachname>'
               '<fraktion>FDP</fraktion></name></redner></p><p>Neue Rede.</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
               '<fraktion>Grüne</fraktion></name></redner></p><p>Weitere Bemerkung.</p></rede>'
               '</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        with self.assertRaisesRegex(ValueError, 'unresolved nested contribution at R2 marker 2'):
            dip.parse_protocol_xml(xml)

    def test_nested_non_questions_reject_instead_of_becoming_zwischenfragen(self):
        for role, text in [
            ('<rolle><rolle_lang>Bundesminister</rolle_lang></rolle>', 'Meine Antwort.'),
            ('<rolle><rolle_lang>Bundesminister</rolle_lang></rolle>', 'Meine Antwort, richtig?'),
            ('<fraktion>SPD</fraktion>', 'Eine andere Mitteilung.'),
            ('', 'Eine Frage?'),
        ]:
            with self.subTest(role=role, text=text):
                xml = ('<dbtplenarprotokoll wahlperiode="21" sitzung-nr="1"><sitzungsverlauf>'
                       '<tagesordnungspunkt top-id="T1"><rede id="R">'
                       '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
                       '<fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
                       '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
                       + role + '</name></redner></p><p>' + text + '</p></rede>'
                       '</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
                with self.assertRaisesRegex(ValueError, '21/1 T1: unresolved nested contribution at R marker 2'):
                    dip.parse_protocol_xml(xml)

    def test_nested_member_question_or_announced_remark_is_a_zwischenfrage(self):
        for announcement, text in [('', 'Meine Frage?'), ('Eine Zwischenbemerkung, bitte.', 'Meine Bemerkung.')]:
            with self.subTest(announcement=announcement):
                xml = ('<dbtplenarprotokoll><sitzungsverlauf><tagesordnungspunkt><rede id="R">'
                       '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname>'
                       '<fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
                       '<name>Präsident</name><p>' + announcement + '</p>'
                       '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname>'
                       '<fraktion>SPD</fraktion></name></redner></p><p>' + text + '</p></rede>'
                       '</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
                contributions = dip.parse_protocol_xml(xml)['agenda_items'][0]['contributions']
                self.assertEqual([(c['kind'], c['text']) for c in contributions], [(sk.ZWISCHENFRAGE, text)])

    def test_multiple_nested_questions_keep_own_text_and_stable_container(self):
        xml = source('rede-interjections.xml')
        parsed = dip.parse_protocol_xml(xml)
        questions = [c for t in parsed['agenda_items'] for c in t['contributions']]
        self.assertTrue(questions)
        self.assertTrue(all(c['kind'] == sk.ZWISCHENFRAGE for c in questions))
        for t in parsed['agenda_items']:
            ids = [contribution_occurrence_id('p', t['index'], c['sequence'], c['rede_id']) for c in t['contributions']]
            self.assertEqual(len(ids), len(set(ids)))
            for c in t['contributions']:
                self.assertTrue(c['rede_id'].startswith('nested:' + c['parent_rede_id'] + ':'))
                own = next(s for s in t['speeches'] if s['rede_id'] == c['parent_rede_id'])
                self.assertNotIn(c['text'], own['text'])
                self.assertNotIn('kommentar', c['text'])

    def test_written_submission_keeps_inline_text_without_rede_inflation(self):
        parsed = dip.parse_protocol_xml(source('a1-written-18-100.xml'))
        contributions = parsed['sitting_contributions'] + [c for t in parsed['agenda_items'] for c in t['contributions']]
        self.assertEqual(len(contributions), 1)
        c = contributions[0]
        self.assertEqual(c['kind'], sk.ZU_PROTOKOLL)
        self.assertIn('Nahezu täglich erhalten wir Nachrichten', c['text'])
        self.assertEqual(c['speaker']['display_name'], 'Clemens Binninger')
        self.assertEqual(dip.contribution_summary(parsed['agenda_items'], parsed['sitting_contributions'])['xml_speech_count'], 0)

    def test_unassigned_annex_persists_links_exports_and_replays_identically(self):
        xml = source('a1-written-18-100.xml').replace('(Tagesordnungspunkt 15)', '(Tagesordnungspunkt 999)')
        parsed = dip.parse_protocol_xml(xml)
        self.assertEqual(len(parsed['sitting_contributions']), 1)
        r = report(parsed)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'store.sqlite'
            entries = [{'report': r}]
            self.assertTrue(build.rebuild_database_from_entries(path, entries))
            original = path.read_bytes()
            self.assertFalse(build.rebuild_database_from_entries(path, entries, keep_if_unchanged=True))
            self.assertEqual(path.read_bytes(), original)
            conn = store.connect(path)
            self.addCleanup(conn.close)
            c = conn.execute('SELECT * FROM contributions').fetchone()
            self.assertIsNone(c['agenda_item_id'])
            self.assertIsNone(c['page'])
            self.assertIsNotNone(c['mp_id'])
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(), [])
            people, lookup = build.collect_abgeordnete(conn)
            self.assertTrue(any(p['has_page'] for p in people))
            rendered = html.render_html(r, mp_lookup=lookup)
            self.assertIn('Schriftliche Beiträge ohne gesicherte TOP-Zuordnung', rendered)
            self.assertIn('Nahezu täglich', rendered)
            self.assertIn('../abgeordnete/', rendered)
            conn.close()
            manifest = build.export_distribution_data(database_path=path, exports_dir=Path(tmp)/'exports', mp_lookup=lookup)
            self.assertTrue(manifest)


class ReplayAndGuardTests(unittest.TestCase):
    def test_read_only_audit_exposes_later_rejected_markers_without_editing_source(self):
        import audit_offline_turns
        xml = ('<dbtplenarprotokoll><sitzungsverlauf><tagesordnungspunkt><rede id="R">'
               '<p klasse="redner"><redner id="A"><name><nachname>Haupt</nachname><fraktion>SPD</fraktion></name></redner></p><p>Rede.</p>'
               '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname><fraktion>SPD</fraktion></name></redner></p><p>Ungeklärt.</p>'
               '<p klasse="redner"><redner id="C"><name><nachname>Andere</nachname><fraktion>SPD</fraktion></name></redner></p><p>Ebenfalls ungeklärt.</p>'
               '</rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'source.xml'
            path.write_text(xml)
            result = audit_offline_turns.audit(dip, path)
            self.assertFalse(result['accepted'])
            self.assertEqual([u['marker_ordinal'] for u in result['unresolved']], [2, 3])
            self.assertEqual(result['counts'], {'rede': 1})
            self.assertEqual(path.read_text(), xml)
            with self.assertRaisesRegex(ValueError, 'R marker 2'):
                dip.parse_protocol_xml(path.read_text())

    def test_reordered_unique_tops_keep_enrichment_and_refresh_heading(self):
        parsed = dip.parse_protocol_xml(source('speech-kinds-befragung-fragestunde.xml'))
        r = report(parsed, '21/6')
        r['agenda_items'][0]['votes'] = [{'id': 'v1'}]
        r['agenda_items'][0]['heading'] = 'Old heading'
        parsed['agenda_items'].reverse()
        dip.reparse_report_xml(r, parsed)
        self.assertEqual(r['agenda_items'][0]['votes'], [{'id': 'v1'}])
        self.assertEqual(r['agenda_items'][0]['heading'], 'Befragung der Bundesregierung')

    def test_ambiguous_or_changed_tops_fail_before_report_mutation(self):
        parsed = dip.parse_protocol_xml(source('speech-kinds-befragung-fragestunde.xml'))
        r = report(parsed, '21/6')
        for t in parsed['agenda_items']:
            t['top_id'] = 'different'
        before = copy.deepcopy(r)
        with self.assertRaisesRegex(ValueError, 'source TOP'):
            dip.reparse_report_xml(r, parsed)
        self.assertEqual(r, before)

    def test_missing_and_stale_provenance_refuse_facts_and_export_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'store.sqlite'
            parsed = dip.parse_protocol_xml(source('a1-written-18-100.xml'))
            r = report(parsed)
            conn = store.connect(path)
            store.persist_report(conn, r)
            self.assertEqual(sk.VERSION, 5)
            self.assertEqual(store.SCHEMA_VERSION, 3)
            store.require_current_speech_rules(conn)
            for version in [None, 4]:
                conn.execute('UPDATE speech_rule_inputs SET version=?', (version,)); conn.commit()
                with self.assertRaisesRegex(RuntimeError, '--offline --repersist'):
                    facts.compute(conn, facts.REGISTRY, {}, catalog=None)
                target = Path(tmp)/'exports'
                with self.assertRaisesRegex(RuntimeError, '--offline --repersist'):
                    build.export_distribution_data(database_path=path, exports_dir=target)
                self.assertFalse(target.exists())
            conn.close()

    def test_bad_kind_and_fetch_inputs_fail_with_context(self):
        with self.assertRaisesRegex(ValueError, 'Unknown contribution kind'):
            html.render_top_contributions({'xml_contributions': [{'kind': 'bad'}]})
        with tempfile.TemporaryDirectory() as tmp, patch.object(dip, 'fetch_text') as fetch:
            entries = [{'report': {'protocol': {'dokumentnummer': '21/6', 'xml_url': 'file:///etc/passwd'}}}, {'report': {'protocol': {}}}]
            self.assertEqual(build.fetch_missing_xml(Path(tmp), entries, pause=0), (0, 2))
            fetch.assert_not_called()

    # Value: protects=cached classification diagnostics stay sorted and versioned while unknown stored kinds are refused; fails_when=rows become unstable or validate_cached_kinds accepts an obsolete kind; why_new=no existing test inspects the diagnostic artifact or cached-kind guard; seam=none
    def test_cached_classification_diagnostics_are_sorted_and_validate_kinds(self):
        entries = [
            {'report': {'protocol': {'dokumentnummer': '21/2'}, 'validation_summary': {
                'contribution_dip_mismatches': [{'kind': sk.ZU_PROTOKOLL, 'xml': 1, 'dip': 0},
                                                {'kind': sk.KURZINTERVENTION, 'xml': 2, 'dip': 1}]}}},
            {'report': {'protocol': {'dokumentnummer': '21/1'}, 'validation_summary': {
                'contribution_dip_mismatches': [{'kind': sk.ERWIDERUNG, 'xml': 1, 'dip': 2}]}}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / 'data').mkdir()
            audit = build.write_classification_diagnostics(output, entries)
            saved = json.loads((output / 'data' / 'a1-classification-diagnostics.json').read_text())
            self.assertEqual(audit, saved)
            self.assertEqual(audit['speech_kinds_version'], sk.VERSION)
            self.assertEqual([(row['document_number'], row['kind']) for row in audit['mismatches']],
                             [('21/1', sk.ERWIDERUNG), ('21/2', sk.KURZINTERVENTION), ('21/2', sk.ZU_PROTOKOLL)])

        stale = {'report': {'protocol': {'dokumentnummer': '21/1'}, 'xml_contributions': [{'kind': 'removed_kind'}]}}
        with self.assertRaisesRegex(build.CachedReportError, 'Unknown contribution kind'):
            build.validate_cached_kinds([stale])

    def test_vote_receipt_uses_one_authoritative_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'store.sqlite'
            seeded = _facts_fixture.seed_weeks(path, [
                {'document_number':'21/9','date':'2025-01-15','closest':(30,20)},
                {'document_number':'21/10','date':'2025-01-22','closest':(40,20)}])
            conn = store.connect(path)
            self.addCleanup(conn.close)
            vote = seeded["vote_ids"]["21/9"][0]
            conn.execute("UPDATE votes SET protocol_id=? WHERE id=?", (seeded["protocol_ids"]["21/9"], vote))
            other = conn.execute('SELECT id FROM agenda_items WHERE protocol_id=?', (seeded['protocol_ids']['21/10'],)).fetchone()[0]
            conn.execute('INSERT INTO agenda_item_votes VALUES (?,?)',(other,vote))
            receipt_metrics = [metric for metric in facts.REGISTRY if 'AS protocol_date' in metric['sql']]
            self.assertEqual(len(receipt_metrics), 2)
            for metric in receipt_metrics:
                row = next(row for row in conn.execute(metric['sql']) if row['id']==vote)
                self.assertEqual((row['protocol_id'],row['document_number'],row['protocol_date']), (seeded['protocol_ids']['21/9'],'21/9','2025-01-15'))
            conn.execute('UPDATE votes SET protocol_id=NULL WHERE id=?',(vote,))
            for metric in receipt_metrics:
                row = next(row for row in conn.execute(metric['sql']) if row['id']==vote)
                chosen = conn.execute('SELECT document_number,date FROM protocols WHERE id=?',(row['protocol_id'],)).fetchone()
                self.assertEqual((row['document_number'],row['protocol_date']),tuple(chosen))
            conn.commit()
            conn.execute('PRAGMA foreign_keys=OFF')
            conn.execute("UPDATE votes SET protocol_id='missing' WHERE id=?", (vote,))
            for metric in receipt_metrics:
                row = next(row for row in conn.execute(metric['sql']) if row['id']==vote)
                self.assertIsNotNone(row['protocol_id'])
                self.assertNotEqual(row['protocol_id'], 'missing')

class AcceptanceFailuresTests(unittest.TestCase):
    def test_xml_pair_digest_rejects_an_interrupted_pair_before_mutation(self):
        xml = source('speech-kinds-befragung-fragestunde.xml')
        lf = dip.parse_protocol_xml(xml)
        crlf = dip.parse_protocol_xml(xml.replace('\n', '\r\n'))
        self.assertEqual(lf['xml_sha256'], crlf['xml_sha256'])
        dip.reparse_report_xml(report(crlf, '21/6'), lf)
        parsed = dip.parse_protocol_xml(source('speech-kinds-befragung-fragestunde.xml'))
        r = report(parsed, '21/6')
        dip.reparse_report_xml(r, parsed)
        before = copy.deepcopy(r)
        changed = dip.parse_protocol_xml(source('speech-kinds-befragung-fragestunde.xml') + '\n')
        with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
            dip.reparse_report_xml(r, changed)
        self.assertEqual(r, before)

    def test_stale_report_cannot_certify_or_replace_a_current_store(self):
        parsed = dip.parse_protocol_xml(source('a1-written-18-100.xml'))
        r = report(parsed)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'store.sqlite'
            build.rebuild_database_from_entries(path, [{'report':r}])
            before = path.read_bytes()
            r['validation_summary']['speech_kinds_version'] = sk.VERSION - 1
            with self.assertRaisesRegex(build.DatabaseRebuildError, 'persisted speech rules'):
                build.rebuild_database_from_entries(path, [{'report':r}])
            self.assertEqual(path.read_bytes(), before)

    def test_fresh_source_refusal_prevents_report_acceptance(self):
        protocol = {'id':'p1','dokumentnummer':'18/84','fundstelle':{'xml_url':'https://dserver.bundestag.de/btp/18/18084.xml'}}
        xml = '<dbtplenarprotokoll wahlperiode="18" sitzung-nr="84"><sitzungsverlauf><tagesordnungspunkt top-id="T1"><p klasse="T_ohne_NaS">Befragung der Bundesregierung</p><rede id="R"><p klasse="redner"><redner id="X"><name><nachname>Unknown</nachname></name></redner></p><p>Text</p></rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>'
        from types import SimpleNamespace
        args = SimpleNamespace(api_key='test',sleep=0)
        with patch.object(dip,'fetch_text',return_value=xml), self.assertRaises(dip.DipError) as raised:
            dip.build_report(args,protocol)
        self.assertTrue(raised.exception.source_rejected)
        self.assertIn('18/84 T1',str(raised.exception))

    def test_unresolved_nested_question_format_speaker_rejects_source(self):
        xml = '<dbtplenarprotokoll wahlperiode="18" sitzung-nr="84"><sitzungsverlauf><tagesordnungspunkt top-id="T1"><p klasse="T_ohne_NaS">Befragung der Bundesregierung</p><rede id="R"><p klasse="redner"><redner id="A"><name><nachname>Minister</nachname><rolle><rolle_lang>Bundesminister</rolle_lang></rolle></name></redner></p><p>Report</p><p klasse="redner"><redner id="X"><name><nachname>Unknown</nachname></name></redner></p><p>Question</p></rede></tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>'
        with self.assertRaisesRegex(ValueError, '18/84 T1: unresolved nested.*R marker 2'):
            dip.parse_protocol_xml(xml)

    def test_repeated_tops_require_unique_heading_context_or_source_unit(self):
        parsed = dip.parse_protocol_xml(source('speech-kinds-befragung-fragestunde.xml'))
        r = report(parsed,'21/6')
        for item in r['agenda_items']:
            item.update(top_id='repeat',heading='same',xml_speakers=[],xml_contributions=[])
        for top in parsed['agenda_items']:
            top.update(top_id='repeat',heading='same',speeches=[],contributions=[])
        # Distinct source neighbors can still prove these boundary positions.
        dip.reparse_report_xml(r,parsed)
        # Four consecutive identical groups have indistinguishable interior context.
        parsed['agenda_items'] = [dict(copy.deepcopy(parsed['agenda_items'][0]),index=i+1) for i in range(4)]
        r['agenda_items'] = [dict(copy.deepcopy(r['agenda_items'][0]),index=i+1) for i in range(4)]
        before = copy.deepcopy(r)
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            dip.reparse_report_xml(r,parsed)
        self.assertEqual(r,before)

    def test_contribution_person_panel_links_back_to_source_anchor(self):
        parsed = dip.parse_protocol_xml(source('a1-written-18-100.xml'))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'s.sqlite'
            build.rebuild_database_from_entries(path,[{'report':report(parsed)}])
            conn = store.connect(path)
            people, _lookup = build.collect_abgeordnete(conn)
            conn.close()
            self.assertTrue(people[0]['contribution_links'])
            panel = build.render_contributions_panel(people[0])
            self.assertIn('plenarprotokoll-18-100.html#contribution-',panel)
