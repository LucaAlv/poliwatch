"""Speaker markers outside any <rede> in a TOP that is not a Fragestunde (ADR 0004,
docs/plans/loose-speaker-markers.md): each is placed as the
reviewed list says, and an unlisted one refuses its sitting."""

import unittest
import xml.etree.ElementTree as ET

import _support  # noqa: F401  (puts scripts/ on the path)

import reviewed_units
import validate_dip_protocol as dip
from test_presidium_kinds import entry, redner, rede

ANNEN = redner('11000001', 'Annen', 'SPD', first='Niels', printed='Niels Annen (SPD):')
STROEBELE = redner('11000002', 'Ströbele', 'BÜNDNIS 90/DIE GRÜNEN', first='Hans-Christian',
                   printed='Hans-Christian Ströbele (BÜNDNIS 90/DIE GRÜNEN):')
BEYER = redner('11000003', 'Beyer', 'CDU/CSU', first='Peter', printed='Peter Beyer (CDU/CSU):')
LINDNER = redner('11000004', 'Lindner', 'BÜNDNIS 90/DIE GRÜNEN', first='Tobias', printed='Tobias Lindner (BÜNDNIS 90/DIE GRÜNEN):')
CHAIR = '<name>Vizepräsidentin Petra Pau: </name>'
SPEECH = '<p>Frau Präsidentin! Liebe Kolleginnen und Kollegen! Eine Rede zur Sache mit Inhalt.</p>'


def loose(rede_id, redner_id, kind, attach):
    return {**entry(rede_id, redner_id, kind, '18/10'), 'attach': attach}


def document(body, heading='Beratung des Antrags zur Außenpolitik'):
    return ('<dbtplenarprotokoll wahlperiode="18" sitzung-nr="10"><sitzungsverlauf>'
            f'<tagesordnungspunkt top-id="T1"><p klasse="T_NaS">{heading}</p>{body}</tagesordnungspunkt>'
            '</sitzungsverlauf></dbtplenarprotokoll>')


def parse(body, entries=()):
    reviewed_units.use(list(entries))
    try:
        return dip.parse_protocol_xml(document(body))
    finally:
        reviewed_units.use([])


def top(parsed):
    return parsed['agenda_items'][0]


def speeches(parsed):
    return [(s['rede_id'], s['speaker']['xml_redner_id'], s['text']) for s in top(parsed)['speeches']]


# A TOP whose first two Reden the source prints without <rede>, as 18/10 TOP 3 does.
OPENING = (CHAIR + '<p>Ich eröffne die Aussprache. Das Wort hat der Kollege Niels Annen.</p>'
           + ANNEN + SPEECH
           + CHAIR + '<p>Herr Kollege Annen, erlauben Sie eine Zwischenfrage des Kollegen Ströbele?</p>'
           + ANNEN + '<p>Das tue ich gerne.</p>'
           + STROEBELE + '<p>Herr Kollege, warum hat die Bundesregierung dazu nichts gesagt?</p>'
           + ANNEN + '<p>Weil die Bundesregierung das im Ausschuss erklärt hat.</p>'
           + CHAIR + '<p>Nächster Redner ist der Kollege Peter Beyer.</p>'
           + BEYER + '<p>Frau Präsidentin! Meine Damen und Herren! Die zweite Rede.</p>'
           + CHAIR + '<p>Vielen Dank. Ich gebe das Ergebnis der namentlichen Abstimmung bekannt.</p>'
           + rede('ID1', LINDNER, SPEECH))
OPENING_ENTRIES = [loose('M1', '11000001', 'loose_rede', 'wrap'), loose('M2', '11000001', 'loose_own_words', 'wrap'),
                   loose('M3', '11000002', 'loose_zwischenfrage', 'wrap'), loose('M4', '11000001', 'loose_own_words', 'wrap'),
                   loose('M5', '11000003', 'loose_rede', 'wrap')]


class WrapTests(unittest.TestCase):
    # Value: protects=a TOP printed without <rede> yields one Rede per listed rede marker, with the speaker's later turns
    #   and the Zwischenfrage inside it; fails_when=the turns stay unread, split wrongly, or the Zwischenfrage becomes a Rede;
    #   why_new=new rule; seam=reviewed
    def test_a_loose_opening_becomes_reden_with_their_zwischenfrage(self):
        parsed = parse(OPENING, OPENING_ENTRIES)
        self.assertEqual([(rid, speaker) for rid, speaker, _ in speeches(parsed)],
                         [('M1', '11000001'), ('M5', '11000003'), ('ID1', '11000004')])
        self.assertEqual(speeches(parsed)[0][2], 'Frau Präsidentin! Liebe Kolleginnen und Kollegen! Eine Rede zur Sache mit '
                         'Inhalt. Das tue ich gerne. Weil die Bundesregierung das im Ausschuss erklärt hat.')
        [question] = top(parsed)['contributions']
        self.assertEqual((question['kind'], question['parent_rede_id'], question['speaker']['xml_redner_id']),
                         ('zwischenfrage', 'M1', '11000002'))
        self.assertEqual(top(parsed)['withheld'], [])

    # Value: protects=the last wrapped Rede ends after its last listed turn, so the chair text after it stays in the TOP;
    #   fails_when=the wrap runs on to the next <rede> and swallows the chair's roll-call result; why_new=new rule; seam=none
    def test_the_last_wrapped_rede_ends_after_its_turn(self):
        root = ET.fromstring(document(OPENING))
        topelement = root.find('./sitzungsverlauf/tagesordnungspunkt')
        created = set()
        dip.mark_loose_markers(topelement, frozenset(), dip.loose_marker_ordinals(root),
                               {e['rede_id']: e for e in OPENING_ENTRIES}, set(), '18/10', created)
        self.assertEqual(created, {'M1', 'M5'})
        self.assertEqual([child.tag for child in topelement][-3:], ['name', 'p', 'rede'])
        self.assertIn('namentlichen Abstimmung', dip.elem_text(list(topelement)[-2]))


class MoveTests(unittest.TestCase):
    # Value: protects=own words before the speaker's <rede> open that Rede, and the chair text between stays in the TOP;
    #   fails_when=the words are lost, or the chair's announcement moves into the Rede (20/9 read a Kurzintervention
    #   as a Rede that way); why_new=new rule; seam=reviewed
    def test_words_before_the_own_rede_open_it(self):
        body = (CHAIR + '<p>Nächster Redner ist der Kollege Lindner.</p>' + LINDNER + '<p>Genau.</p>'
                + CHAIR + '<p>Bitte schön, Sie haben das Wort.</p>' + rede('ID1', LINDNER, SPEECH))
        parsed = parse(body, [loose('M1', '11000004', 'loose_own_words', 'next')])
        self.assertEqual(speeches(parsed), [('ID1', '11000004', 'Genau. ' + SPEECH[3:-4])])

    # Value: protects=own words after the speaker's <rede> close it; fails_when=Kühne's last 407 words (19/62) stay
    #   unread; why_new=new rule; seam=reviewed
    def test_words_after_the_own_rede_close_it(self):
        body = (rede('ID1', LINDNER, SPEECH) + CHAIR + '<p>Da haben Sie was ausgelöst.</p>'
                + LINDNER + '<p>Ja, genau. Und weiter in der Sache.</p>')
        parsed = parse(body, [loose('M1', '11000004', 'loose_own_words', 'prev')])
        self.assertEqual(speeches(parsed), [('ID1', '11000004', SPEECH[3:-4] + ' Ja, genau. Und weiter in der Sache.')])

    # Value: protects=a procedural turn becomes a diagnostic, a remark and Sitzungsleitung are stored nowhere, and none
    #   of them moves with a run; fails_when=an acceptance of an election is counted, or refuses the sitting; why_new=new rule; seam=reviewed
    def test_kinds_that_go_nowhere_store_nothing(self):
        body = (CHAIR + '<p>Nehmen Sie die Wahl an?</p>' + BEYER + '<p>Jawohl, ich nehme die Wahl an.</p>'
                + ANNEN + '<p>Nein.</p>' + CHAIR + '<p>Dann fahren wir fort.</p>' + rede('ID1', LINDNER, SPEECH))
        parsed = parse(body, [loose('M1', '11000003', 'loose_procedural', 'none'), loose('M2', '11000001', 'loose_remark', 'none')])
        self.assertEqual([rid for rid, _, _ in speeches(parsed)], ['ID1'])
        self.assertEqual(top(parsed)['contributions'], [])
        procedural = [d for d in top(parsed)['xml_turn_diagnostics'] if d['treatment'] == 'procedural']
        self.assertEqual([(d['speaker']['xml_redner_id'], d['text']) for d in procedural],
                         [('11000003', 'Jawohl, ich nehme die Wahl an.')])


class RefusalTests(unittest.TestCase):
    # Value: protects=an unlisted marker outside any <rede> refuses its sitting, naming the fix; fails_when=the turn is
    #   dropped silently again (the gap this rule closes); why_new=new rule; seam=none
    def test_an_unlisted_marker_refuses_the_sitting(self):
        with self.assertRaises(dip.UnlistedLooseMarkerError) as caught:
            parse(OPENING, OPENING_ENTRIES[:-1])
        self.assertIn('M5', str(caught.exception))
        self.assertIsInstance(caught.exception, ValueError)

    # Value: protects=an entry whose marker, Redner-ID, owner or place does not fit stops the run; fails_when=a stale or
    #   misapplied entry binds the wrong speaker; why_new=new rule; seam=reviewed
    def test_an_entry_that_does_not_fit_stops_the_run(self):
        cases = {
            'stale': OPENING_ENTRIES + [loose('M9', '11000001', 'loose_rede', 'wrap')],
            'other id': [loose('M1', '11000009', 'loose_rede', 'wrap')] + OPENING_ENTRIES[1:],
            'other owner': OPENING_ENTRIES[:1] + [loose('M2', '11000002', 'loose_own_words', 'wrap')] + OPENING_ENTRIES[2:],
            'two places': OPENING_ENTRIES[:1] + [loose('M2', '11000001', 'loose_own_words', 'prev')] + OPENING_ENTRIES[2:],
            'no rede opens': [loose('M1', '11000001', 'loose_own_words', 'wrap')] + OPENING_ENTRIES[1:],
        }
        for label, entries in cases.items():
            with self.subTest(label), self.assertRaises(reviewed_units.ReviewedUnitsError):
                parse(OPENING, entries)

    # Value: protects=a moved own-words run must open with the owner of the <rede> it joins; fails_when=another speaker's
    #   words become the owner's Rede text; why_new=new rule; seam=reviewed
    def test_a_next_run_must_open_with_the_owner(self):
        body = BEYER + '<p>Genau.</p>' + rede('ID1', LINDNER, SPEECH)
        with self.assertRaises(reviewed_units.ReviewedUnitsError):
            parse(body, [loose('M1', '11000003', 'loose_own_words', 'next')])


    # Value: protects=a sitting refused for an unlisted loose marker names the reviewed-list fix, online and on replay;
    #   fails_when=it reads as corrupt XML ("--fetch-xml"), whose re-fetch returns the same XML; why_new=new error;
    #   seam=fetch_text stubbed
    def test_a_refused_sitting_names_the_reviewed_list(self):
        import json
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch
        import build_dip_pulse_site as build
        xml = document(OPENING)
        protocol = {"id": "p1", "dokumentnummer": "18/10", "fundstelle": {"xml_url": "https://dserver.bundestag.de/btp/18/18010.xml"}}
        reviewed_units.use([])
        try:
            with patch.object(dip, "fetch_text", return_value=xml), patch.object(dip, "enrich_with_api"), \
                    self.assertRaises(dip.DipError) as online:
                dip.build_report(SimpleNamespace(api_key="test", sleep=0), protocol)
            with tempfile.TemporaryDirectory() as tmp:
                output_dir = Path(tmp)
                (output_dir / "data" / "xml").mkdir(parents=True)
                (output_dir / "data" / "xml" / "plenarprotokoll-18-10.xml").write_text(xml, encoding="utf-8")
                report = {"protocol": {"id": "p1", "dokumentnummer": "18/10"}, "agenda_items": []}
                (output_dir / "data" / "plenarprotokoll-18-10.json").write_text(json.dumps(report), encoding="utf-8")
                entries = build.load_existing_detail_entries(output_dir, [{"dokumentnummer": "18/10"}])
                with self.assertRaises(build.CachedReportError) as replay:
                    build.reparse_cached_xml(output_dir, entries)
        finally:
            reviewed_units.use([])
        self.assertTrue(online.exception.source_rejected)
        self.assertIn("with a loose_* kind", str(online.exception))
        printed_replay = f"{replay.exception}. {build.cached_report_fix(replay.exception)}"
        self.assertIn("with a loose_* kind", printed_replay)
        self.assertNotIn("--fetch-xml", printed_replay)


class ListTests(unittest.TestCase):
    # Value: protects=the list refuses a loose entry with a wrong id shape, place or key set; fails_when=a typo in the
    #   list is read as a different marker or place; why_new=new kinds; seam=none
    def test_the_list_checks_loose_entries(self):
        good = loose('M1', '11000001', 'loose_rede', 'wrap')
        reviewed_units.use([good])
        reviewed_units.use([])
        for bad in ({**good, 'rede_id': 'ID1'}, {**good, 'attach': 'prev'}, {**good, 'redner_id': ''},
                    {k: v for k, v in good.items() if k != 'attach'}, {**good, 'kind': 'loose_remark'}):
            with self.subTest(bad), self.assertRaises(reviewed_units.ReviewedUnitsError):
                reviewed_units.use([bad])
        reviewed_units.use([])


if __name__ == '__main__':
    unittest.main()
