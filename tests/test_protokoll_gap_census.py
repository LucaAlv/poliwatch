"""docs/plans/zu-protokoll-gap/census.py: what DIP lists after the last printed
<rede> of a sitting whose Protokoll XML is a first edition."""

import contextlib
import csv
import importlib.util
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _support

GAP = _support.ROOT / 'docs' / 'plans' / 'zu-protokoll-gap'
NOTICE = ('Der gesamte und damit end­gültige Stenografische Bericht der 99. Sitzung wird am '
          '13.Oktober 2026 veröffentlicht.')


def load_census():
    spec = importlib.util.spec_from_file_location('protokoll_gap_census', GAP / 'census.py')
    census = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(census)
    return census


def xref(rede_id, page, quadrant):
    return f'<xref ref-type="rede" rid="{rede_id}" pnr="{page}" div="{quadrant}"/>'


def protocol_xml(notice=NOTICE):
    """Two Reden in the Sitzungsverlauf, one in an annex printed on a later page."""
    return (f'<dbtplenarprotokoll sitzung-ende-uhrzeit="01:07"><vorspann>{xref("ID1", 10, "A")}{xref("ID2", 12, "B")}'
            f'{xref("ID9", 90, "C")}</vorspann><sitzungsverlauf><rede id="ID1"/><rede id="ID2"/><p>{notice}</p>'
            '</sitzungsverlauf><anlagen><rede id="ID9"/></anlagen></dbtplenarprotokoll>')


def activity(kind, title, seite):
    return {'aktivitaetsart': kind, 'titel': title, 'fundstelle': {'seite': seite}}


ACTIVITIES = [
    activity('Rede', 'Anna Alt, MdB, SPD', '10A'),
    activity('Rede', 'Bernd Berg, MdB, AfD', '12B'),
    activity('Rede', 'Carla Cut, MdB, SPD', '12B'),
    activity('Rede', 'Dora Dreher, MdB, Die Linke', '12C'),
    activity('Rede', 'Emil Esch, MdB, CDU/CSU', '13A'),
    activity('Rede', 'Petra Pau, Bundestagsvizepräs.', '13B'),
    activity('Kurzintervention', 'Anna Alt, MdB, SPD', '13C'),
    activity('Frage', 'Anna Alt, MdB, SPD', '14A'),
    activity('Rede (zu Protokoll gegeben)', 'Emil Esch, MdB, CDU/CSU', '90C'),
    activity('Rede (zu Protokoll gegeben)', 'Dora Dreher, MdB, Die Linke', '91A'),
]


def data_dir(root, number, xml, activities=ACTIVITIES, positions=()):
    """A data directory as a replay leaves it, with the tables the census reads."""
    name = number.replace('/', '-')
    (root / 'xml').mkdir()
    (root / 'xml' / f'plenarprotokoll-{name}.xml').write_text(xml, encoding='utf-8')
    (root / f'plenarprotokoll-{name}.json').write_text(json.dumps({
        'protocol': {'dokumentnummer': number, 'datum': '2026-10-08'},
        'api_records': {'aktivitaeten': activities, 'vorgangspositionen': list(positions)},
    }), encoding='utf-8')
    conn = sqlite3.connect(root / 'bundestag-pulse.sqlite')
    conn.executescript('''
        CREATE TABLE protocols (id, document_number);
        CREATE TABLE contributions (protocol_id, kind);
        CREATE TABLE speeches (protocol_id);
        CREATE TABLE agenda_items (protocol_id);
        CREATE TABLE withheld_units (protocol_id);
        CREATE TABLE votes (id, protocol_id);
        CREATE TABLE agenda_item_votes (vote_id);
        INSERT INTO speeches VALUES ('p'), ('p');
        INSERT INTO contributions VALUES ('p', 'zu_protokoll');
        INSERT INTO votes VALUES ('v1', 'p'), ('v2', 'p');
        INSERT INTO agenda_item_votes VALUES ('v1');
    ''')
    conn.execute("INSERT INTO protocols VALUES ('p', ?)", (number,))
    conn.commit()
    conn.close()


def census_row(xml, **data):
    """The one row of a census over 21/99 with ``xml`` as its file."""
    census = load_census()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data_dir(root, '21/99', xml, **data)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            census.main(root)
    [row] = csv.DictReader(io.StringIO(out.getvalue()), delimiter='\t')
    return row


class ProtokollGapCensusTests(unittest.TestCase):
    # Value: protects=a count the census cannot know is empty, never 0; fails_when=a rerun reads a file without page
    #   numbers (20/7, 20/97, 18/223, 19/161) as having nothing after its cut; why_new=TODOS census hygiene; seam=none
    def test_without_a_page_the_columns_that_need_one_are_empty(self):
        no_pages = protocol_xml().replace('pnr="10"', 'pnr=""').replace('pnr="12"', 'pnr=""')
        unplaced = [activity(a['aktivitaetsart'], a['titel'], None) for a in ACTIVITIES]
        row = census_row(no_pages, activities=unplaced,
                         positions=[{'id': 'v1', 'fundstelle': {'anfangsseite': 99}}])
        self.assertEqual(
            [row[key] for key in ('xml_letzte_rede', 'dip_letzter_beitrag_gesprochen', 'dip_reden_danach',
                                  'dip_zwischenfragen_kurzinterventionen_erwiderungen_danach',
                                  'dip_vorgangspositionen_danach')],
            ['', '', '', '', ''])
        self.assertEqual((row['dip_zu_protokoll'], row['fehlend_zu_protokoll']), ('2', '1'))

    # Value: protects=a Vorgangsposition whose page DIP gives as text is read as that page; fails_when=the run stops
    #   comparing text with a number, or a text that is no page counts; why_new=TODOS census hygiene; seam=none
    def test_a_position_page_given_as_text_is_read_as_a_number(self):
        positions = [{'id': name, 'fundstelle': {'anfangsseite': page, 'anfangsquadrant': 'A'}}
                     for name, page in (('after', '13'), ('number', 14), ('before', ' 11 '), ('none', 'Anlage 2'),
                                        ('absent', None), ('long', '9' * 5000))]
        self.assertEqual(census_row(protocol_xml(), positions=positions)['dip_vorgangspositionen_danach'], '2')

    # Value: protects=the place of the last <rede> is the last of the Sitzungsverlauf, never an annex's or a page the TOC leaves empty;
    #   fails_when=the cut moves and the Reden after it are counted wrongly; why_new=new script; seam=none
    def test_the_cut_is_the_last_rede_of_the_sitzungsverlauf(self):
        census = load_census()
        self.assertEqual(census.xml_cut(protocol_xml()), (12, 'B'))
        self.assertEqual(census.xml_cut(protocol_xml().replace('pnr="12" div="B"', 'pnr="" div=""')), (10, 'A'))
        self.assertEqual(census.place('26871D'), (26871, 'D'))
        self.assertEqual(census.place(None), (0, ''))

    # Value: protects=the Reden after the cut: none in the cut's own quadrant, no farewell by the chair, no Frage;
    #   fails_when=the 1,189 of DATA.md counts the 23 addresses by the chair again; why_new=new script; seam=none
    def test_a_first_edition_is_listed_with_what_dip_gives_after_the_cut(self):
        census = load_census()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir(root, '21/99', protocol_xml())
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                census.main(root)
        [row] = csv.DictReader(io.StringIO(out.getvalue()), delimiter='\t')
        self.assertEqual((row['sitzung'], row['teilausgabe'], row['endgueltig_am']), ('21/99', 'ja', '13. Oktober 2026'))
        self.assertEqual((row['xml_letzte_rede'], row['dip_letzter_beitrag_gesprochen']), ('12B', '14A'))
        self.assertEqual((row['dip_reden_danach'], row['dip_zwischenfragen_kurzinterventionen_erwiderungen_danach']), ('2', '1'))
        self.assertEqual((row['dip_zu_protokoll'], row['gespeichert_zu_protokoll'], row['fehlend_zu_protokoll']), ('2', '1', '1'))
        self.assertEqual((row['abstimmungen'], row['abstimmungen_ohne_top'], row['xml_sitzungsende']), ('2', '1', '01:07'))
        self.assertIn("'chair_after': 1", err.getvalue())

    # Value: protects=the table per Wahlperiode in docs/data-methods.md, which becomes DATA.md, against the committed census;
    #   fails_when=one of the two is changed without the other; why_new=the figures are typed by hand; seam=none
    # Value: protects=the committed census keeps the totals of E16, and data-methods types no count of cut files: DATA.md
    #   generates them from the store (cut-protocols step 8), so a cut Thursday cannot leave a stale figure there;
    #   fails_when=a hand-written per-Wahlperiode table returns, or the census drifts from 33 / 1,189 / 429; seam=docs
    def test_the_census_totals_hold_and_data_methods_types_no_count(self):
        with (GAP / 'per-sitting.tsv').open(encoding='utf-8', newline='') as handle:
            rows = [row for row in csv.DictReader(handle, delimiter='\t') if row['teilausgabe'] == 'ja' and row['sitzung'] != '19/107']
        self.assertEqual((len(rows), sum(int(row['dip_reden_danach']) for row in rows),
                          sum(int(row['fehlend_zu_protokoll']) for row in rows)), (33, 1189, 429))
        methods = (_support.ROOT / 'docs' / 'data-methods.md').read_text(encoding='utf-8')
        # Through the E17 paragraph, which reconciles the Reden zu Protokoll with DIP: its totals move with the next
        # cut sitting too (4.599 DIP, 4.174 stored, 429 on 2026-11-26).
        section = methods[methods.index('**Abgebrochene Protokolldateien.**'):methods.index('## Personen und Abstimmungen')]
        self.assertIn('In der 18. Wahlperiode druckt', section)
        self.assertNotRegex(section, r'(?m)^\|')
        self.assertNotRegex(section, r'\b(33|1\.189|429|4\.599|4\.174)\b')

if __name__ == '__main__':
    unittest.main()
