"""The reviewed list's unit kinds (ADR 0002, amendment 2026-11-23): what a whole
unit is where the wording rules read it as something else, and the check of the
stored Reden against DIP's types."""

import json
import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401  (puts scripts/ on the path)

import build_dip_pulse_site as build
import reviewed_units
import speech_kinds as sk
import validate_store_gate as gate
from test_presidium_kinds import entry, parse, redner, rede, top_of

HIRTE = redner('11000001', 'Hirte', 'CDU/CSU', first='Heribert', printed='Dr. Heribert Hirte (CDU/CSU):')
DEMASI = redner('11000002', 'De Masi', 'DIE LINKE', first='Fabio', printed='Fabio De Masi (DIE LINKE):')
MAIER = redner('11000003', 'Maier', 'AfD', first='Lothar', printed='Dr. Lothar Maier (AfD):')
NEXT = redner('11000004', 'Sitte', 'DIE LINKE', first='Petra', printed='Dr. Petra Sitte (DIE LINKE):')
CHAIR = '<name>Vizepräsidentin Petra Pau: </name>'
MAIN = '<p>Frau Präsidentin! Liebe Kolleginnen und Kollegen! Eine Rede zur Sache.</p>'
REMARK = '<p>Herr Kollege, Sie haben mich angesprochen.</p>'


def body(grant='Herr De Masi, bitte.'):
    return (rede('ID1', HIRTE, MAIN + CHAIR + f'<p>{grant}</p>')
            + rede('ID2', DEMASI, REMARK + CHAIR + '<p>Sie möchten antworten?</p>')
            + rede('ID3', HIRTE, '<p>Das tue ich gerne.</p>' + CHAIR + '<p>Nächste Rednerin ist Dr. Petra Sitte.</p>')
            + rede('ID4', NEXT, MAIN))


def kinds(parsed):
    top = top_of(parsed)
    return ([s['rede_id'] for s in top['speeches']],
            [(c['rede_id'], c['kind'], c['parent_rede_id']) for c in top['contributions']])


class ListedUnitTests(unittest.TestCase):
    # Value: protects=a listed Kurzintervention leaves the Reden, names the Rede it answers, and the main Redner's answer to it
    #   becomes its Erwiderung although no wording grants either; fails_when=the entry is ignored, or the running main Rede moves to
    #   the Kurzintervention so the answer stays a Rede; why_new=new entry kinds; seam=reviewed
    def test_a_listed_kurzintervention_takes_its_place(self):
        self.assertEqual(kinds(parse(body())), (['ID1', 'ID2', 'ID3', 'ID4'], []))
        parsed = parse(body(), [entry('ID2', '11000002', 'kurzintervention')])
        self.assertEqual(kinds(parsed), (['ID1', 'ID4'],
                                         [('ID2', 'kurzintervention', 'ID1'), ('ID3', 'erwiderung', 'ID1')]))

    # Value: protects=an Erklärung keeps its text as a Beitrag with no parent, and a listed answer to it names the last Rede;
    #   fails_when=the Erklärung stays a Rede, loses its text, or becomes the Rede the next turn answers; why_new=new Kind; seam=reviewed
    def test_an_erklaerung_is_a_beitrag_with_its_text(self):
        parsed = parse(body(), [entry('ID2', '11000002', 'erklaerung'), entry('ID3', '11000001', 'erwiderung')])
        self.assertEqual(kinds(parsed), (['ID1', 'ID4'],
                                         [('ID2', 'erklaerung', None), ('ID3', 'erwiderung', 'ID1')]))
        self.assertEqual(top_of(parsed)['contributions'][0]['text'], 'Herr Kollege, Sie haben mich angesprochen.')

    # Value: protects=an Erwiderung after another Redner's Rede names its Redner's own Rede, and so does the Kurzintervention it answers
    #   (19/3 Buchholz, 19/61 Möller); fails_when=both point at the Rede in between; why_new=found by the replay; seam=reviewed
    def test_a_late_exchange_belongs_to_the_answering_redners_rede(self):
        text = (rede('ID1', HIRTE, MAIN) + rede('ID2', NEXT, MAIN) + rede('ID3', DEMASI, REMARK) + rede('ID4', HIRTE, REMARK)
                + rede('ID5', MAIER, MAIN))
        parsed = parse(text, [entry('ID3', '11000002', 'kurzintervention'), entry('ID4', '11000001', 'erwiderung')])
        self.assertEqual(kinds(parsed), (['ID1', 'ID2', 'ID5'],
                                         [('ID3', 'kurzintervention', 'ID1'), ('ID4', 'erwiderung', 'ID1')]))

    # Value: protects=where two Redner answer one Kurzintervention, each Erwiderung names its own Rede and the Kurzintervention the
    #   last one; fails_when=it is moved to whichever answers first (19/212); why_new=found by the replay; seam=reviewed
    def test_two_answers_leave_the_kurzintervention_at_the_last_rede(self):
        text = (rede('ID1', HIRTE, MAIN) + rede('ID2', NEXT, MAIN) + rede('ID3', DEMASI, REMARK)
                + rede('ID4', HIRTE, REMARK) + rede('ID5', NEXT, REMARK))
        parsed = parse(text, [entry('ID3', '11000002', 'kurzintervention'), entry('ID4', '11000001', 'erwiderung'),
                              entry('ID5', '11000004', 'erwiderung')])
        self.assertEqual(kinds(parsed)[1], [('ID3', 'kurzintervention', 'ID2'), ('ID4', 'erwiderung', 'ID1'),
                                            ('ID5', 'erwiderung', 'ID2')])

    # Value: protects=an Erwiderung whose Redner holds no Rede in the TOP names the Rede the Kurzintervention before it answers
    #   (18/85 Straubinger), and without one names none (20/196 Hoffmann answers an Erklärung the XML prints as chair text);
    #   fails_when=it points at a Rede nobody answered; why_new=found by the review; seam=reviewed
    def test_an_erwiderung_without_a_rede_of_its_own(self):
        text = rede('ID1', HIRTE, MAIN) + rede('ID2', DEMASI, REMARK) + rede('ID3', MAIER, REMARK) + rede('ID4', NEXT, MAIN)
        reply = entry('ID3', '11000003', 'erwiderung')
        self.assertEqual(kinds(parse(text, [entry('ID2', '11000002', 'kurzintervention'), reply]))[1],
                         [('ID2', 'kurzintervention', 'ID1'), ('ID3', 'erwiderung', 'ID1')])
        self.assertEqual(kinds(parse(text, [entry('ID2', '11000002', 'erklaerung'), reply]))[1],
                         [('ID2', 'erklaerung', None), ('ID3', 'erwiderung', None)])

    # Value: protects=an Erklärung given in a Befragung is one, and the opening report, Frage and Antwort around it keep their kinds;
    #   fails_when=19/191 Brandner's § 31 Erklärung counts as a Frage or the turns after it change; why_new=found by the review; seam=reviewed
    def test_an_erklaerung_in_a_befragung(self):
        minister = redner('11000009', 'Heil', role='Bundesminister für Arbeit und Soziales', first='Hubertus',
                          printed='Hubertus Heil, Bundesminister für Arbeit und Soziales:')
        text = (rede('ID1', minister, MAIN) + rede('ID2', HIRTE, '<p>Was tun Sie?</p>') + rede('ID3', minister, MAIN)
                + rede('ID4', DEMASI, REMARK) + rede('ID5', NEXT, '<p>Und wann?</p>'))
        frage, antwort = sk.BEFRAGUNG_FRAGE, sk.BEFRAGUNG_ANTWORT
        heading = {'heading': 'Befragung der Bundesregierung'}
        self.assertEqual(kinds(parse(text, [entry('ID4', '11000002', 'erklaerung')], **heading)),
                         (['ID1'], [('ID2', frage, None), ('ID3', antwort, None), ('ID4', 'erklaerung', None), ('ID5', frage, None)]))
        # Before the first Frage it leaves the opening reports open.
        text = rede('ID1', minister, MAIN) + rede('ID2', DEMASI, REMARK) + rede('ID3', minister, MAIN) + rede('ID4', HIRTE, '<p>Was tun Sie?</p>')
        self.assertEqual(kinds(parse(text, [entry('ID2', '11000002', 'erklaerung')], **heading)),
                         (['ID1', 'ID3'], [('ID2', 'erklaerung', None), ('ID4', frage, None)]))

    # Value: protects=a Rede zu Protokoll printed inside a TOP is stored as one, under its TOP and id; fails_when=it stays a Rede or is
    #   refused for lack of a status; why_new=owner decision 2026-11-23; seam=reviewed
    def test_a_written_rede_inside_a_top(self):
        parsed = parse(body(), [entry('ID4', '11000004', 'zu_protokoll')])
        self.assertEqual(kinds(parsed)[1], [('ID4', 'zu_protokoll', None)])

    # Value: protects=a `rede` entry overrules the wording rules; fails_when=a Rede the rules read as a Kurzintervention (19/59 Kühn)
    #   cannot be corrected; why_new=new entry kinds; seam=reviewed
    def test_a_rede_entry_overrules_the_wording(self):
        granted = body('Zu einer Kurzintervention erhält Herr De Masi das Wort.')
        self.assertEqual(kinds(parse(granted))[1], [('ID2', 'kurzintervention', 'ID1'), ('ID3', 'erwiderung', 'ID1')])
        parsed = parse(granted, [entry('ID2', '11000002', 'rede')])
        self.assertEqual(kinds(parsed), (['ID1', 'ID2', 'ID3', 'ID4'], []))

    # Value: protects=an entry that names no unit, another owner, a question format or a presidium <rede> stops the run;
    #   fails_when=a stale or misapplied entry is skipped in silence; why_new=new entry kinds; seam=reviewed
    def test_a_stale_or_misapplied_entry_stops_the_run(self):
        chair = redner('11000009', 'Pau', role='Vizepräsidentin', first='Petra', printed='Petra Pau, Vizepräsidentin:')
        for text, entries, kwargs, message in (
            (body(), [entry('ID9', '11000002', 'erklaerung')], {}, 'ID9, which names no Rede'),
            (body(), [entry('ID2', '11000001', 'erklaerung')], {}, 'owned by Redner-ID 11000002'),
            (rede('ID1', HIRTE, MAIN), [entry('ID1', '11000001', 'kurzintervention')],
             {'heading': 'Befragung der Bundesregierung'}, 'question format'),
            (rede('ID1', chair, MAIN), [entry('ID1', '11000009', 'erklaerung')], {}, "ADR 0004's kinds"),
        ):
            with self.subTest(message), self.assertRaisesRegex(reviewed_units.ReviewedUnitsError, message):
                parse(text, entries, **kwargs)

    # Value: protects=a split part can be listed by its own id; fails_when=only whole source <rede>s match, so 18/29's Groth (a part
    #   of a part) cannot be; why_new=new entry kinds; seam=reviewed
    def test_a_split_part_can_be_listed(self):
        text = rede('ID1', HIRTE, MAIN + CHAIR + '<p>Das Wort hat die Kollegin Dr. Petra Sitte.</p>' + NEXT + MAIN)
        self.assertEqual(kinds(parse(text)), (['ID1', 'ID1:2'], []))
        self.assertEqual(kinds(parse(text, [entry('ID1:2', '11000004', 'erklaerung')])),
                         (['ID1'], [('ID1:2', 'erklaerung', None)]))

    # Value: protects=one M<ordinal> can carry the marker's entry and what its Rede is, and nothing else twice; fails_when=#213's § 31
    #   Erklärungen cannot change Kind, or one unit is withheld and typed at once; why_new=new entry kinds; seam=none
    def test_a_loose_marker_and_its_unit_are_two_entries(self):
        loose = {**entry('M1', '11000001', 'loose_rede', '18/23'), 'attach': 'wrap'}
        unit = entry('M1', '11000001', 'erklaerung', '18/23')
        reviewed_units.use([loose, unit])
        reviewed_units.use([])
        for repeated in ([loose, loose], [unit, unit], [unit, entry('M1', '11000001', 'withhold', '18/23')]):
            with self.assertRaisesRegex(reviewed_units.ReviewedUnitsError, 'listed twice'):
                reviewed_units.use(repeated)

    # Value: protects=every unit kind but `rede` is a stored Kind with a status and a label; fails_when=a listed kind reaches persist
    #   or a page with no status or wording; why_new=new Kind; seam=none
    def test_every_unit_kind_has_a_status_and_a_label(self):
        for kind in reviewed_units.UNIT_KINDS - {'rede'}:
            self.assertIn(kind, sk.CONTRIBUTION_KINDS)
            self.assertIn(kind, sk.REDE_STATUS)
            self.assertIn(kind, sk.KIND_LABELS)
        self.assertLessEqual(set(sk.DIP_UNIT_KINDS.values()), reviewed_units.UNIT_KINDS)


def activity(art, name, page):
    return {'aktivitaetsart': art, 'titel': f'{name}, MdB, SPD', 'fundstelle': {'seite': page}}


def speech(rede_id, last, page=100, quadrant='A'):
    return {'rede_id': rede_id, 'speaker': {'last_name': last, 'display_name': last},
            'source_page': {'page': page, 'quadrant': quadrant}}


def report(activities, speeches, number='21/900'):
    return {'protocol': {'dokumentnummer': number}, 'api_records': {'aktivitaeten': activities},
            'agenda_items': [{'xml_speakers': speeches}]}


class DipTypedRedenTests(unittest.TestCase):
    # Value: protects=a stored Rede DIP types as a Kurzintervention, Erwiderung or Erklärung at its place is named, through a Wahlkreis
    #   in brackets and a dropped accent; fails_when=the match misses it (18/203 Dağdelen); why_new=new guard; seam=none
    def test_names_a_rede_dip_types_otherwise(self):
        for art, kind in sk.DIP_UNIT_KINDS.items():
            [row] = sk.dip_typed_reden(report([activity(art, 'Sevim Dagdelen (Bochum)', '100A')], [speech('ID1', 'Dağdelen')]))
            self.assertEqual((row['rede_id'], row['page'], row['dip']), ('ID1', '100A', [kind]))

    # Value: protects=no false alarm where DIP also lists the Rede, where person, page or quadrant differ, where DIP's type stays a Rede,
    #   where the list says Rede, or where the page is missing; fails_when=a release stops on a correct store; why_new=new guard; seam=none
    def test_stays_silent_where_dip_explains_the_rede(self):
        kurz = activity('Kurzintervention', 'Petra Sitte', '100A')
        for name, activities, speeches, listed in (
            ('DIP lists the Rede too', [kurz, activity('Rede', 'Petra Sitte', '100A')], [speech('ID1', 'Sitte')], ()),
            ('another person', [kurz], [speech('ID1', 'Pau')], ()),
            ('another page', [kurz], [speech('ID1', 'Sitte', 101)], ()),
            ('another quadrant', [kurz], [speech('ID1', 'Sitte', 100, 'B')], ()),
            ('Geschäftsordnung stays a Rede', [activity('Zur Geschäftsordnung BT', 'Petra Sitte', '100A')], [speech('ID1', 'Sitte')], ()),
            ('listed as a Rede', [kurz], [speech('ID1', 'Sitte')], {'ID1'}),
            ('no page', [kurz], [speech('ID1', 'Sitte', None, None)], ()),
            ('no activities', None, [speech('ID1', 'Sitte')], ()),
        ):
            with self.subTest(name):
                self.assertEqual(sk.dip_typed_reden(report(activities, speeches), listed), [])

    # Value: protects=two stored Reden of one person at one place, of which DIP explains one, are both named; fails_when=the extra one
    #   hides behind the other; why_new=new guard; seam=none
    def test_names_both_candidates_of_one_place(self):
        rows = sk.dip_typed_reden(report(
            [activity('Rede', 'Petra Sitte', '100A'), activity('Kurzintervention', 'Petra Sitte', '100A')],
            [speech('ID1', 'Sitte'), speech('ID2', 'Sitte')]))
        self.assertEqual([row['rede_id'] for row in rows], ['ID1', 'ID2'])

    # Value: protects=a tagged export refuses such a Rede naming it, a local build does not, and a `rede` entry clears it;
    #   fails_when=a release ships a Kurzintervention counted as a Rede; why_new=new guard; seam=reviewed
    def test_a_release_export_refuses_and_a_rede_entry_clears(self):
        entries = [{'report': report([activity('Erwiderung', 'Petra Sitte', '100A')], [speech('ID1', 'Sitte')])}]
        with self.assertRaisesRegex(RuntimeError, r'21/900 ID1 \(erwiderung\)'):
            build.refuse_release_with_unlisted_dip_typed_reden('2026.12.01', entries)
        build.refuse_release_with_unlisted_dip_typed_reden('local', entries)
        reviewed_units.use([entry('ID1', '11000004', 'rede', '21/900')])
        try:
            build.refuse_release_with_unlisted_dip_typed_reden('2026.12.01', entries)
        finally:
            reviewed_units.use([])

    # Value: protects=the diagnostics file and the store gate name the same rows from the cached reports; fails_when=either reads
    #   something else or skips a report; why_new=new guard; seam=none
    def test_diagnostics_and_gate_name_the_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / 'data'
            data.mkdir()
            found = report([activity('Erwiderung', 'Petra Sitte', '100A')], [speech('ID1', 'Sitte')])
            (data / 'plenarprotokoll-21-900.json').write_text(json.dumps(found), encoding='utf-8')
            (data / 'plenarprotokoll-catalog.json').write_text('{}', encoding='utf-8')
            audit = build.write_classification_diagnostics(Path(tmp), [{'report': found}])
            self.assertEqual([row['rede_id'] for row in audit['reden_dip_types_otherwise']], ['ID1'])
            self.assertEqual(gate.dip_typed_reden(Path(tmp)), audit['reden_dip_types_otherwise'])


def load_census():
    import importlib.util
    path = _support.ROOT / 'docs' / 'plans' / 'beitraege-as-reden' / 'census.py'
    spec = importlib.util.spec_from_file_location('beitraege_census', path)
    census = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(census)
    return census


class CensusTests(unittest.TestCase):
    # Value: protects=a person shown under a later name or listed under a second DIP id is matched, another person of the surname is not;
    #   fails_when=a name change hides a turn again (18/46 Jantz, 21/10 dos Santos-Wintz), or two persons of one surname are paired
    #   (18/17 Wiese, 20/79 Hahn without a stored id); why_new=found by the ship review and on PR 214; seam=none
    def test_the_same_person_is_matched_and_a_namesake_is_not(self):
        census = load_census()
        for dip_ids, shown, printed, person_id, titel, expected in (
                ({'1691'}, 'Christina Jantz-Herrmann', 'Christina Jantz', '1691', 'Christina Anders, MdB, SPD', True),
                (set(), 'Christina Jantz-Herrmann', 'Christina Jantz', '', 'Christina Jantz, MdB, SPD', True),
                ({'615'}, 'Henning Otte', 'Henning Otte', '8226', 'Henning Otte, MdB, CDU/CSU', True),
                (set(), 'Matthias W. Birkwald', 'Matthias W. Birkwald', '', 'Matthias W. Birkwald, MdB, DIE LINKE', True),
                ({'1792'}, 'Dirk Wiese', 'Dirk Wiese', '1651', 'Heinz Wiese (Ehingen), MdB, CDU/CSU', False),
                (set(), 'Florian Hahn', 'Florian Hahn', '7811', 'Dr. André Hahn, MdB, DIE LINKE', False),
                ({'7471'}, 'Dr. Till Steffen', 'Dr. Till Steffen', '8188', 'Dr. Thomas Steffen, Staatssekr.', False),
                (set(), '', '', '', '', False)):
            with self.subTest(shown=shown, titel=titel):
                unit = {'dip_ids': dip_ids, 'names': {census.full_name(shown), census.full_name(printed)}}
                act = {'person_id': person_id, 'name': census.full_name(titel)}
                self.assertEqual(census.same_person(unit, act), expected)

    # Value: protects=the census proposes DIP's decided kind, flags a row a reader must read, and proposes nothing for a kind the owner left
    #   a Rede; fails_when=a later census (a new sitting) lists doubtful rows as clear; why_new=new script; seam=none
    def test_the_proposal_flags_what_must_be_read(self):
        census = load_census()
        unit = {'stored': 'rede', 'match': 'exact', 'chars': 900, 'speaker': 'Petra Sitte', 'text': 'Herr Kollege, nein.'}
        grant = 'Zu einer Kurzintervention hat Frau Sitte das Wort.'
        self.assertEqual(census.proposal(unit, 'kurzintervention', grant, 'Hirte'), ('kurzintervention', ''))
        self.assertEqual(census.proposal(unit, 'erklaerung_31', 'Eine Erklärung nach § 31.', 'Hirte'), ('erklaerung', ''))
        for changed, chair, previous, reason in (({'match': 'near'}, grant, 'Hirte', 'page'), ({'chars': 9000}, grant, 'Hirte', 'long'),
                                                 ({}, grant, 'Sitte', 'same speaker'), ({}, 'Nächste Rednerin ist Frau Sitte.', 'Hirte', 'next speaker'),
                                                 ({}, 'Eine Erklärung zur Aussprache.', 'Hirte', 'erklaerung_30')):
            with self.subTest(reason):
                kind, read = census.proposal({**unit, **changed}, 'kurzintervention', chair, previous)
                self.assertEqual(kind, 'kurzintervention')
                self.assertIn(reason, read)
        self.assertEqual(census.proposal(unit, 'geschaeftsordnung', '', 'Hirte')[0], '')


if __name__ == '__main__':
    unittest.main()
