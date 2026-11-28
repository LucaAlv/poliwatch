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
import validate_dip_protocol as dip
import validate_store_gate as gate
from test_presidium_kinds import entry, parse, redner, rede, sitting, top_of

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


def own_words(rede_id, redner_id, page=''):
    return {**entry(rede_id, redner_id, 'own_words'), 'page': page}


def parse_with_pages(body, pages, entries):
    """``parse``, with an Inhaltsverzeichnis that names each ``rede`` id's page."""
    listed = ''.join(f'<ivz-eintrag><xref ref-type="rede" rid="{rid}" pnr="{page[:-1]}" div="{page[-1]}"/></ivz-eintrag>'
                     for rid, page in pages.items())
    xml = sitting(body).replace('<sitzungsverlauf>', '<vorspann><inhaltsverzeichnis><ivz-block><ivz-block-titel>T1</ivz-block-titel>'
                                f'{listed}</ivz-block></inhaltsverzeichnis></vorspann><sitzungsverlauf>', 1)
    return dip.parse_protocol_xml(xml, reviewed=list(entries))


def place(page_ref):
    return f"{page_ref['page']}{page_ref['quadrant']}"


class OwnWordsTests(unittest.TestCase):
    """A ``<rede>`` that goes on with the Rede before it (ADR 0004, amendment 2026-11-23 on split Reden)."""

    ASKED = CHAIR + '<p>Frau Kollegin, gestatten Sie eine Zwischenfrage?</p>'
    REST = '<p>Ja, gerne.</p>' + DEMASI + '<p>Ist Ihnen das bekannt?</p>' + NEXT + '<p>Ja. Und damit zum Schluss.</p>'
    ENTRY = own_words('ID2', '11000004')

    def two(self, between=''):
        return rede('ID1', NEXT, MAIN + self.ASKED) + between + rede('ID2', NEXT, self.REST) + rede('ID3', HIRTE, MAIN)

    def split(self):
        return (rede('ID1', HIRTE, MAIN + CHAIR + '<p>Das Wort hat die Kollegin Dr. Petra Sitte.</p>' + NEXT + MAIN + self.ASKED)
                + rede('ID2', NEXT, self.REST))

    # Value: protects=the two parts are one Rede under the first id, the Zwischenfrage in the second is its Beitrag, and the part
    #   joined away has a status; fails_when=the rest counts as a Rede, loses its text or its Zwischenfrage; why_new=new kind; seam=reviewed
    def test_the_rest_joins_the_rede_before_it(self):
        self.assertEqual([s['rede_id'] for s in top_of(parse(self.two()))['speeches']], ['ID1', 'ID2', 'ID3'])
        parsed = parse(self.two(), [self.ENTRY])
        self.assertEqual(kinds(parsed), (['ID1', 'ID3'], [('nested:ID1:3', 'zwischenfrage', 'ID1')]))
        self.assertEqual(top_of(parsed)['speeches'][0]['text'], MAIN[3:-4] + '\nJa, gerne.\nJa. Und damit zum Schluss.')
        self.assertEqual([(d['source_rede_id'], d['treatment'], d['target_rede_id']) for d in top_of(parsed)['xml_turn_diagnostics']
                          if d['treatment'] == 'joined_rede'], [('ID2', 'joined_rede', 'ID1')])

    # Value: protects=where the first part is one the parser split off another Rede, the Rede keeps the id the Inhaltsverzeichnis
    #   names; fails_when=it goes by the made-up id, which no other dataset has; why_new=7 of the 13; seam=reviewed
    def test_a_split_parts_rede_keeps_the_listed_id(self):
        self.assertEqual([s['rede_id'] for s in top_of(parse(self.split()))['speeches']], ['ID1', 'ID1:2', 'ID2'])
        parsed = parse_with_pages(self.split(), {'ID1': '10B', 'ID2': '13C'}, [own_words('ID2', '11000004', '12A')])
        self.assertEqual([s['rede_id'] for s in top_of(parsed)['speeches']], ['ID1', 'ID2'])
        self.assertEqual(top_of(parsed)['speeches'][1]['text'], MAIN[3:-4] + '\nJa, gerne.\nJa. Und damit zum Schluss.')

    # Value: protects=a joined Rede begins where its first part does, and the TOP still reaches the rest's page; fails_when=the
    #   Rede takes the page the Inhaltsverzeichnis gives its rest (18/98), or the TOP ends before it (18/88); why_new=review; seam=reviewed
    def test_the_rede_begins_where_its_first_part_does(self):
        top = top_of(parse_with_pages(self.split(), {'ID1': '10B', 'ID2': '13C'}, [own_words('ID2', '11000004', '12A')]))
        self.assertEqual([place(s['source_page']) for s in top['speeches']], ['10B', '12A'])
        self.assertEqual([place(top['page_range'][end]) for end in ('start', 'end')], ['10B', '13C'])
        top = top_of(parse_with_pages(self.two(), {'ID1': '10B', 'ID2': '13C', 'ID3': '13A'}, [self.ENTRY]))
        self.assertEqual([place(s['source_page']) for s in top['speeches']], ['10B', '13A'])
        self.assertEqual([place(top['page_range'][end]) for end in ('start', 'end')], ['10B', '13C'])

    # Value: protects=the page is given exactly where the source has none, and lies between the two it has; fails_when=a typed page
    #   is stored unread; why_new=new key; seam=reviewed
    def test_a_page_that_does_not_fit_stops_the_run(self):
        for case, body, page in (('missing on a split part', self.split(), ''), ('given where the first part has its own', self.two(), '12A'),
                                 ('before the Rede it was split off', self.split(), '10A'), ('after the rest', self.split(), '13D')):
            with self.subTest(case), self.assertRaises(reviewed_units.ReviewedUnitsError):
                parse_with_pages(body, {'ID1': '10B', 'ID2': '13C'}, [own_words('ID2', '11000004', page)])
        # Codex (ship, 2026-11-24): a bound the Inhaltsverzeichnis does not give is not dropped; all 7 held entries have both.
        for case, pages in (('no page of the Rede split off', {'ID2': '13C'}), ('no page of the rest', {'ID1': '10B'}), ('neither', {})):
            with self.subTest(case), self.assertRaisesRegex(reviewed_units.ReviewedUnitsError, 'Inhaltsverzeichnis'):
                parse_with_pages(self.split(), pages, [own_words('ID2', '11000004', '12A')])
        for case, bad in (('no page key', entry('ID2', '11000004', 'own_words')), ('no quadrant', own_words('ID2', '11000004', '12')),
                          ('page on another kind', {**entry('ID2', '11000004', 'rede'), 'page': '12A'}),
                          ('number', {**own_words('ID2', '11000004'), 'page': 12}),
                          ('page 0', own_words('ID2', '11000004', '0A')), ('quadrant beyond D', own_words('ID2', '11000004', '12E'))):
            with self.subTest(case), self.assertRaises(reviewed_units.ReviewedUnitsError):
                reviewed_units._check({'entries': [bad]}, Path('list.json'))

    # Value: protects=no words move to another person, over another turn, or on a stale entry; fails_when=a guard is dropped;
    #   why_new=new kind; seam=reviewed
    def test_an_entry_that_does_not_fit_stops_the_run(self):
        for case, body, listed in (
                ('another owner', self.two(), own_words('ID2', '11000001')),
                ('another speaker before', self.two(), own_words('ID3', '11000001')),
                ('nothing before', self.two(), own_words('ID1', '11000004')),
                ('text between', self.two('<p>Wir kommen zur Abstimmung.</p>'), self.ENTRY),
                ('another Rede between', rede('ID1', NEXT, MAIN) + rede('ID9', HIRTE, MAIN) + rede('ID2', NEXT, self.REST), self.ENTRY),
                ('no such rede', self.two(), own_words('ID7', '11000004'))):
            with self.subTest(case), self.assertRaises(reviewed_units.ReviewedUnitsError):
                parse(body, [listed])
        chair = redner('11000009', 'Pau', role='Vizepräsidentin', first='Petra', printed='Petra Pau, Vizepräsidentin:')
        with self.assertRaisesRegex(reviewed_units.ReviewedUnitsError, "ADR 0004's kinds"):
            parse(rede('ID1', chair, MAIN + self.ASKED) + rede('ID2', chair, self.REST), [own_words('ID2', '11000009')])

    # Value: protects=a first part whose id the parser made from a speaker marker (N<n>, M<n>) is refused, not kept in place of a
    #   Bundestag id; fails_when=a joined Rede is stored under a made-up id no other dataset has (TODOS item 11); why_new=code
    #   review 2026-11-24; seam=reviewed
    def test_a_made_up_first_part_is_refused(self):
        for made_up in ('M1', 'N3'):
            with self.subTest(made_up), self.assertRaisesRegex(reviewed_units.ReviewedUnitsError, 'made from a speaker marker'):
                parse(rede(made_up, NEXT, MAIN + self.ASKED) + rede('ID2', NEXT, self.REST), [self.ENTRY])


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

    # Value: protects=the architecture docs name every Kind the contributions table holds; fails_when=a new Kind ships and the docs
    #   still list the old set (erklaerung and ansprache were missing, TODOS item 10); why_new=hand-synced list; seam=none
    def test_the_architecture_docs_name_every_kind(self):
        for name in ('bundestag-puls-architecture.json', 'bundestag-puls-architecture.html'):
            text = (_support.ROOT / 'docs' / name).read_text(encoding='utf-8')
            for kind in (sk.KURZINTERVENTION, sk.ERWIDERUNG, sk.ERKLAERUNG, sk.ZWISCHENFRAGE, sk.ZU_PROTOKOLL, sk.ANSPRACHE):
                with self.subTest(name=name, kind=kind):
                    self.assertIn(kind if kind in ('zu_protokoll', 'erklaerung', 'ansprache') else kind.capitalize(), text)



class WithholdOneTests(unittest.TestCase):
    """The D6 check (scripts/check_withhold_one.py) parses with every reviewed entry of the sitting."""

    def check(self, text, entries):
        import check_withhold_one
        reviewed_units.use(list(entries))
        try:
            return check_withhold_one.check_sitting(sitting(text))
        finally:
            reviewed_units.use([])

    # Value: protects=the exchange picks reach a listed Kurzintervention and the Erwiderung it makes, and withholding a listed unit
    #   leaves the rest as it was; fails_when=the check parses without unit entries and never withholds a listed one (TODOS item 10);
    #   why_new=TODOS items 10 and 11; seam=reviewed
    def test_the_exchange_picks_reach_listed_units(self):
        result = self.check(body(), [entry('ID2', '11000002', 'kurzintervention')])
        self.assertEqual(result['exchange-kurzintervention'], {'withheld': 1, 'problems': []})
        self.assertEqual(result['exchange-erwiderung'], {'withheld': 1, 'problems': []})

    # Value: protects=a Rede joined from two printed parts is withheld whole, its joined-away part appearing nowhere; fails_when=the
    #   check withholds the parts singly and never a joined one (TODOS item 11); why_new=plan review R2; seam=reviewed
    def test_a_joined_rede_is_withheld_whole(self):
        result = self.check(OwnWordsTests().two(), [OwnWordsTests.ENTRY])
        self.assertEqual(result['joined-target'], {'withheld': 1, 'problems': []})


def activity(art, name, page):
    return {'aktivitaetsart': art, 'titel': f'{name}, MdB, SPD', 'fundstelle': {'seite': page}}


def speech(rede_id, last, page=100, quadrant='A', first=None, redner='11000004', display=None):
    return {'rede_id': rede_id, 'speaker': {'last_name': last, 'first_name': first, 'xml_redner_id': redner,
                                            'display_name': last if display is None else display},
            'source_page': {'page': page, 'quadrant': quadrant}}


def contribution(rede_id, kind, last, page=100, quadrant='A', first=None):
    return {**speech(rede_id, last, page, quadrant, first), 'kind': kind}


def report(activities, speeches, number='21/900', contributions=(), formats=()):
    return {'protocol': {'dokumentnummer': number}, 'api_records': {'aktivitaeten': activities},
            'agenda_items': [{'xml_speakers': speeches, 'xml_contributions': list(contributions),
                              'question_formats': list(formats)}]}


def named(rows):
    return [(row['rede_id'], row['problem']) for row in rows]


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
            ('nothing stored, nothing in DIP (20/5)', None, [], ()),
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

    # Value: protects=one DIP Aktivität explains one stored unit, however the person's given name is printed; fails_when=a Rede
    #   printing "Petra" and one printing no given name each take DIP's single Rede and a Kurzintervention passes; why_new=Codex
    #   (ship, 2026-11-28); seam=none
    def test_one_aktivitaet_explains_one_unit_across_name_variants(self):
        dip = [activity('Rede', 'Petra Sitte', '100A'), activity('Kurzintervention', 'Petra Sitte', '100A')]
        rows = sk.dip_typed_reden(report(dip, [speech('ID1', 'Sitte', first='Petra'), speech('ID2', 'Sitte')]))
        self.assertEqual(named(rows), [('ID1', 'dip_types_otherwise'), ('ID2', 'dip_types_otherwise')])
        # A namesake's Rede at the same place is not named for Petra's Kurzintervention.
        dip = [activity('Rede', 'Hans Sitte', '100A'), activity('Rede', 'Petra Sitte', '100A'), activity('Kurzintervention', 'Petra Sitte', '100A')]
        rows = sk.dip_typed_reden(report(dip, [speech('ID1', 'Sitte', first='Hans'), speech('ID2', 'Sitte', first='Petra'),
                                               speech('ID3', 'Sitte', first='Petra')]))
        self.assertEqual(named(rows), [('ID2', 'dip_types_otherwise'), ('ID3', 'dip_types_otherwise')])

    # Value: protects=only an oral Kind DIP gives explains a stored Kurzintervention, Erwiderung or Erklärung; fails_when=the person's
    #   Rede zu Protokoll at the place clears a Beitrag DIP types "Rede"; why_new=Codex (ship, 2026-11-28); seam=none
    def test_a_written_aktivitaet_explains_no_oral_beitrag(self):
        stored = [contribution('ID3', sk.KURZINTERVENTION, 'Sitte'), contribution('ID4', sk.ZU_PROTOKOLL, 'Sitte')]
        dip = [activity('Rede', 'Petra Sitte', '100A'), activity('Rede (zu Protokoll gegeben)', 'Petra Sitte', '100A')]
        self.assertEqual(named(sk.dip_typed_reden(report(dip, [], contributions=stored))), [('ID3', 'dip_types_rede')])

    # Value: protects=only DIP types stored as Reden explain a stored Rede; fails_when=a Zwischenfrage, Frage or written § 31
    #   Erklärung of the person at the place hides a Kurzintervention stored as a Rede; why_new=TODOS item 7 (review 2026-11-23); seam=none
    def test_only_types_stored_as_reden_explain_a_rede(self):
        for art in ('Zwischenfrage', 'Frage', 'Antwort', 'Zusatzfrage', 'Schriftliche Erklärung gem. § 31 Geschäftsordnung BT'):
            with self.subTest(art):
                rows = sk.dip_typed_reden(report([activity('Kurzintervention', 'Petra Sitte', '100A'), activity(art, 'Petra Sitte', '100A')],
                                                 [speech('ID1', 'Sitte')]))
                self.assertEqual(named(rows), [('ID1', 'dip_types_otherwise')])
        for art in ('Zur Geschäftsordnung BT', 'Einleitende Ausführungen und Beantwortung', 'Berichterstattung',
                    'Erklärung zum Vermittlungsverfahren (§ 90 GO-BT, § 10 GO-VermA)'):
            with self.subTest(art):
                self.assertEqual(sk.dip_typed_reden(report([activity('Kurzintervention', 'Petra Sitte', '100A'),
                                                            activity(art, 'Petra Sitte', '100A')], [speech('ID1', 'Sitte')])), [])

    # Value: protects=a Rede listed as `rede` uses up one explaining Aktivität and is never named, every other Rede of the place
    #   still is; fails_when=listing one silences the other, or a listed Rede lets a Kurzintervention at its place pass;
    #   why_new=TODOS item 7; seam=reviewed
    def test_a_listed_rede_uses_up_its_place(self):
        dip = [activity('Rede', 'Petra Sitte', '100A'), activity('Kurzintervention', 'Petra Sitte', '100A')]
        two = [speech('ID1', 'Sitte'), speech('ID2', 'Sitte')]
        self.assertEqual(named(sk.dip_typed_reden(report(dip, two), {'ID1'})), [('ID2', 'dip_types_otherwise')])
        self.assertEqual(sk.dip_typed_reden(report(dip, two), {'ID1', 'ID2'}), [])
        self.assertEqual(named(sk.dip_typed_reden(report(dip[1:] * 2, two), {'ID1'})), [('ID2', 'dip_types_otherwise')])

    # Value: protects=a Rede DIP gives zu Protokoll is named as zu_protokoll; fails_when=18/46's two Reden zu Protokoll go unseen;
    #   why_new=TODOS item 7 (/ship review 2026-11-23); seam=none
    def test_a_rede_dip_gives_zu_protokoll(self):
        for art in ('Rede (zu Protokoll gegeben)', 'Berichterstattung (zu Protokoll gegeben)'):
            with self.subTest(art):
                [row] = sk.dip_typed_reden(report([activity(art, 'Christina Jantz', '100A')], [speech('ID1', 'Jantz')]))
                self.assertEqual(row['dip'], ['zu_protokoll'])

    # Value: protects=a Befragung unit DIP types as an Erklärung is named, with `erklaerung` as the only entry offered, and Frage or
    #   Antwort explain it; fails_when=19/191 and 20/105 go unseen again, or the refusal offers a `rede` entry the parser refuses;
    #   why_new=TODOS item 7, plan review R3; seam=none
    def test_a_befragung_unit_dip_types_as_an_erklaerung(self):
        erklaerung = activity('Erklärung zur Aussprache gem. § 30 Geschäftsordnung BT', 'Petra Sitte', '100A')
        frage = [contribution('ID5', sk.BEFRAGUNG_FRAGE, 'Sitte')]
        other = activity('Frage', 'Hans Meier', '200A')  # the sitting is indexed
        [row] = sk.dip_typed_reden(report([erklaerung, other], [], contributions=frage, formats=['befragung']))
        self.assertEqual((row['rede_id'], row['stored'], row['dip']), ('ID5', sk.BEFRAGUNG_FRAGE, ['erklaerung']))
        self.assertIn('erklaerung', row['remedy'])
        self.assertNotIn('or as rede', row['remedy'])
        self.assertIn('no entry yet confirms', row['remedy'])
        self.assertEqual(sk.dip_typed_reden(report([erklaerung, activity('Frage', 'Petra Sitte', '100A')], [], contributions=frage,
                                                   formats=['befragung'])), [])
        self.assertEqual(sk.dip_typed_reden(report([activity('Kurzintervention', 'Petra Sitte', '100A'), other], [], contributions=frage,
                                                   formats=['befragung'])), [])
        # A Rede in a Befragung TOP takes no `rede` entry either.
        [row] = sk.dip_typed_reden(report([erklaerung], [speech('ID1', 'Sitte')], formats=['befragung']))
        self.assertIn('no entry yet confirms', row['remedy'])

    # Value: protects=a Rede whose XML prints no <nachname> is matched by its shown name, and one with no name at all by its place;
    #   fails_when=19/69 and six other Reden are skipped; why_new=TODOS item 7 (/ship review 2026-11-23); seam=none
    def test_a_rede_without_a_printed_surname(self):
        kurz = activity('Kurzintervention', 'Petra Sitte', '100A')
        shown = speech('ID1', None, display='Petra Sitte')
        self.assertEqual(named(sk.dip_typed_reden(report([kurz], [shown]))), [('ID1', 'dip_types_otherwise')])
        nameless = speech('ID1', None, display='Dr. h. c.')
        self.assertEqual(named(sk.dip_typed_reden(report([kurz], [nameless]))), [('ID1', 'dip_types_otherwise')])
        self.assertEqual(sk.dip_typed_reden(report([kurz, activity('Rede', 'Hans Meier', '100A')], [nameless])), [])

    # Value: protects=a namesake's Aktivität neither explains nor names a Rede where both print a given name, as census.py compares;
    #   fails_when=Heinz Wiese's Rede hides Dirk Wiese's Kurzintervention, or Heinz's Kurzintervention names Dirk's Rede (PR 214);
    #   why_new=TODOS item 7; seam=none
    def test_a_namesake_is_another_person(self):
        dirk = [speech('ID1', 'Wiese', first='Dirk')]
        self.assertEqual(named(sk.dip_typed_reden(report([activity('Rede', 'Heinz Wiese (Ehingen)', '100A'),
                                                          activity('Kurzintervention', 'Dirk Wiese', '100A')], dirk))),
                         [('ID1', 'dip_types_otherwise')])
        self.assertEqual(sk.dip_typed_reden(report([activity('Kurzintervention', 'Heinz Wiese', '100A')], dirk)), [])
        self.assertEqual(named(sk.dip_typed_reden(report([activity('Kurzintervention', 'Dr. Dirk Wiese', '100A')], dirk))),
                         [('ID1', 'dip_types_otherwise')])

    # Value: protects=a sitting with more stored units than DIP Aktivitäten (none at all included) is refused as unchecked, also
    #   where it holds no Rede; fails_when=a sitting DIP has not indexed passes in silence; why_new=TODOS item 7, plan review R1; seam=none
    def test_a_sitting_dip_has_not_indexed_is_unchecked(self):
        for name, activities, speeches, contributions in (
                ('no Aktivitäten', None, [speech('ID1', 'Sitte')], ()),
                ('fewer than Reden', [activity('Rede', 'Petra Sitte', '100A')], [speech('ID1', 'Sitte'), speech('ID2', 'Pau')], ()),
                ('only a Kurzintervention', [], [], [contribution('ID3', sk.KURZINTERVENTION, 'Sitte')])):
            with self.subTest(name):
                [row] = sk.dip_typed_reden(report(activities, speeches, contributions=contributions))
                self.assertEqual((row['rede_id'], row['problem']), (None, 'unchecked'))
        # DIP lists a Befragung's turns sparsely (20/140: 118 turns, 105 Aktivitäten; 20/10: 60 and 16), so its turns need one
        # Aktivität of a Befragung type, not one each.
        turns = [contribution(f'ID{n}', sk.BEFRAGUNG_FRAGE, 'Sitte', 100 + n) for n in range(3)]
        self.assertEqual(sk.dip_typed_reden(report([activity('Frage', 'Petra Sitte', '100A')], [], contributions=turns,
                                                   formats=['befragung'])), [])
        [row] = sk.dip_typed_reden(report([activity('Rede', 'Hans Meier', '200A')] * 3, [], contributions=turns, formats=['befragung']))
        self.assertEqual(row['problem'], 'unchecked')

    # Value: protects=a stored Kurzintervention, Erwiderung or Erklärung DIP types "Rede" at its place is named, and an entry of any
    #   unit kind clears it; fails_when=a Rede stored as a Beitrag loses its count unseen; why_new=TODOS item 7; seam=reviewed
    def test_a_beitrag_dip_types_as_a_rede(self):
        rede_act = activity('Rede', 'Petra Sitte', '100A')
        for kind in (sk.KURZINTERVENTION, sk.ERWIDERUNG, sk.ERKLAERUNG):
            with self.subTest(kind):
                [row] = sk.dip_typed_reden(report([rede_act], [], contributions=[contribution('ID3', kind, 'Sitte')]))
                self.assertEqual((row['rede_id'], row['problem'], row['stored'], row['dip']), ('ID3', 'dip_types_rede', kind, ['rede']))
                self.assertIn(f'or as {kind}', row['remedy'])
                self.assertEqual(sk.dip_typed_reden(report([rede_act], [], contributions=[contribution('ID3', kind, 'Sitte')]), {'ID3'}), [])
        both = [rede_act, activity('Kurzintervention', 'Petra Sitte', '100A')]
        self.assertEqual(sk.dip_typed_reden(report(both, [speech('ID1', 'Sitte')],
                                                   contributions=[contribution('ID3', sk.KURZINTERVENTION, 'Sitte')])), [])
        self.assertEqual(sk.dip_typed_reden(report([rede_act], [], contributions=[contribution('nested:ID1:2', sk.ZWISCHENFRAGE, 'Sitte')])), [])

    # Value: protects=the entry the remedy offers for a Beitrag DIP calls a Rede is one the parser accepts and leaves the Kind as it
    #   is; fails_when=confirming 19/165 Bystron's Kurzintervention stops the run or moves it; why_new=new remedy; seam=reviewed
    def test_an_entry_confirming_the_rules_kind_changes_nothing(self):
        granted = body('Zu einer Kurzintervention erhält Herr De Masi das Wort.')
        self.assertEqual(kinds(parse(granted, [entry('ID2', '11000002', 'kurzintervention'), entry('ID3', '11000001', 'erwiderung')])),
                         kinds(parse(granted)))

    # Value: protects=the refusal names each row with what an entry can say for it; fails_when=a reader is told to list a `rede`
    #   entry the parser refuses (a speaker without a Bundestag Redner-ID); why_new=TODOS item 7; seam=none
    def test_the_refusal_says_what_can_be_listed(self):
        [row] = sk.dip_typed_reden(report([activity('Kurzintervention', 'Petra Sitte', '100A')], [speech('N1', 'Sitte', redner=None)]))
        self.assertIn('no Bundestag Redner-ID', row['remedy'])
        entries = [{'report': report([activity('Kurzintervention', 'Petra Sitte', '100A')], [speech('ID1', 'Sitte')])}]
        with self.assertRaisesRegex(RuntimeError, r'21/900 ID1 \(kurzintervention\): list it as kurzintervention, or as rede'):
            build.refuse_release_with_unlisted_dip_typed_reden('2026.12.01', entries)

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
            self.assertEqual(gate.dip_typed_check(Path(tmp)), {'reports': 1, 'rows': audit['reden_dip_types_otherwise']})

    # Value: protects=the gate reads only the reports the store holds, and a run that reads none fails; fails_when=an excluded
    #   sitting's report fails the gate, or an empty directory passes check 7; why_new=TODOS item 7; seam=none
    def test_the_gate_reads_the_stored_sittings_and_fails_on_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / 'data'
            data.mkdir()
            self.assertEqual(gate.dip_typed_check(Path(tmp)), {'reports': 0, 'rows': []})
            self.assertFalse(gate.dip_typed_check_passes(gate.dip_typed_check(Path(tmp))))
            found = report([activity('Erwiderung', 'Petra Sitte', '100A')], [speech('ID1', 'Sitte')], number='18/20')
            (data / 'plenarprotokoll-18-20.json').write_text(json.dumps(found), encoding='utf-8')
            (data / 'plenarprotokoll-catalog.json').write_text('{}', encoding='utf-8')
            self.assertEqual(len(gate.dip_typed_check(Path(tmp))['rows']), 1)
            (data / 'coverage-exclusions.json').write_text(json.dumps({'exclusions': [
                {'document_number': '18/20', 'reason': 'source_defect', 'reason_detail': 'test'}]}), encoding='utf-8')
            self.assertEqual(gate.dip_typed_check(Path(tmp)), {'reports': 0, 'rows': []})
            clean = report([activity('Rede', 'Petra Sitte', '100A')], [speech('ID1', 'Sitte')], number='21/900')
            (data / 'plenarprotokoll-21-900.json').write_text(json.dumps(clean), encoding='utf-8')
            self.assertTrue(gate.dip_typed_check_passes(gate.dip_typed_check(Path(tmp))))


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
