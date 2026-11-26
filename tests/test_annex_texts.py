"""Written Reden the WP 18 annexes print without a <rede> of their own
(docs/source-errors.md E17, docs/plans/e17-wp18-texts.md): each is placed as the
reviewed list's annex_rede entry says, and a structural shape no entry names
refuses its sitting."""

import unittest
from pathlib import Path

import _support

import derive
import reviewed_units
import validate_dip_protocol as dip

SITTING = '18/10'


def marker(rid, first, last, fraktion=None, role=None, printed=None, title=None):
    parts = (f'<titel>{title}</titel>' if title else '') + f'<vorname>{first}</vorname><nachname>{last}</nachname>'
    if fraktion:
        parts += f'<fraktion>{fraktion}</fraktion>'
    if role:
        parts += f'<rolle><rolle_lang>{role}</rolle_lang></rolle>'
    label = printed or f'{first} {last} ({fraktion}): '
    return f'<p klasse="redner"><redner id="{rid}"><name>{parts}</name></redner>{label}'


FABRITIUS = marker('1', 'Bernd', 'Fabritius', 'CDU/CSU')
HUBER = marker('2', 'Charles M.', 'Huber', 'CDU/CSU')
THEWS = marker('3', 'Michael', 'Thews', 'SPD')
OEZDEMIR = marker('6', 'Mahmut', 'Özdemir', 'SPD')
SCHUSTER = marker('7', 'Armin', 'Schuster', 'CDU/CSU', printed='Armin Schuster (Weil am Rhein) (CDU/CSU): ')
TOP_HEADING = '<p klasse="Anlage_3">zur Beratung des Antrags (Tagesordnungspunkt 1)</p>'


def block(body, title='Zu Protokoll gegebene Reden'):
    return f'<anlagen-text anlagen-typ="{title}">{body}</anlagen-text>'


def document(*blocks):
    annexes = ''.join(f'<anlage><anlagen-titel>Anlage {n}</anlagen-titel>{b}</anlage>' for n, b in enumerate(blocks, 1))
    return (f'<dbtplenarprotokoll wahlperiode="18" sitzung-nr="10"><sitzungsverlauf>'
            '<tagesordnungspunkt top-id="Tagesordnungspunkt 1"><p klasse="T_NaS">Beratung des Antrags</p></tagesordnungspunkt>'
            f'</sitzungsverlauf><anlagen>{annexes}</anlagen></dbtplenarprotokoll>')


def annex(rede_id, redner_id, name, label=None):
    return {'sitting': SITTING, 'rede_id': rede_id, 'redner_id': redner_id, 'kind': 'annex_rede',
            'reason': 'reviewed in the E17 census', 'name': name, 'label': label or name}


def parse(*blocks, entries=()):
    reviewed_units.use(list(entries))
    try:
        return dip.parse_protocol_xml(document(*blocks))
    finally:
        reviewed_units.use([])


def written(parsed):
    """Every zu_protokoll unit, the TOP's then the sitting's, as (id, Redner-ID, text, TOP)."""
    units = [(c, top['top_id']) for top in parsed['agenda_items'] for c in top['contributions']]
    units += [(c, None) for c in parsed['sitting_contributions']]
    return [(c['rede_id'], (c['speaker'] or {}).get('xml_redner_id'), c['text'], top)
            for c, top in units if c['kind'] == 'zu_protokoll']


def unit(parsed, rede_id):
    return next(c for c in [*parsed['sitting_contributions'], *(c for t in parsed['agenda_items'] for c in t['contributions'])]
                if c['rede_id'] == rede_id)


class SplitTests(unittest.TestCase):
    # Value: protects=a second writer's marker inside another writer's annex <rede> becomes a Beitrag of its own, with its page;
    #   fails_when=the second writer's words stay dropped as a nested segment or stay with the first writer;
    #   why_new=new rule (E17, 18/17 Huber); seam=reviewed
    def test_a_second_writers_marker_splits_off(self):
        host = (f'<rede id="ID1801712700">{FABRITIUS}Erster Absatz.</p><p klasse="J">Zweiter Absatz.'
                f'<a typ="druckseitennummer" id="S1365" name="S1365"/></p>{HUBER}Hubers Text.</p><p klasse="J">Mehr.</p></rede>')
        parsed = parse(block(TOP_HEADING + host),
                       entries=[annex('ID1801712700', '2', 'Charles M. Huber (CDU/CSU)')])
        self.assertEqual(written(parsed), [
            ('ID1801712700', '1', 'Erster Absatz.\nZweiter Absatz.', 'Tagesordnungspunkt 1'),
            ('ID1801712700:2', '2', 'Hubers Text.\nMehr.', 'Tagesordnungspunkt 1'),
        ])
        self.assertEqual(unit(parsed, 'ID1801712700:2')['source_page']['page'], 1365)

    # Value: protects=a second writer's text printed as a plain paragraph that opens with their label leaves the first writer's
    #   Beitrag and becomes the second writer's; fails_when=it stays credited to the first writer (18/23 Thews/Lenkert);
    #   why_new=new rule; seam=reviewed
    def test_a_label_paragraph_inside_another_rede_splits_off(self):
        host = (f'<rede id="ID1802308800">{THEWS}Thews spricht.</p><p klasse="J">Thews schließt.</p>'
                '<p klasse="J_Abstand">Ralph Lenkert (DIE LINKE): Elf Duale Systeme.</p><p klasse="J">Zweitens.</p></rede>')
        parsed = parse(block(TOP_HEADING + host), entries=[annex('ID1802308800', '4', 'Ralph Lenkert (DIE LINKE)')])
        self.assertEqual(written(parsed), [
            ('ID1802308800', '3', 'Thews spricht.\nThews schließt.', 'Tagesordnungspunkt 1'),
            ('ID1802308800:2', '4', 'Elf Duale Systeme.\nZweitens.', 'Tagesordnungspunkt 1'),
        ])
        speaker = unit(parsed, 'ID1802308800:2')['speaker']
        self.assertEqual((speaker['display_name'], speaker['last_name'], speaker['fraktion']), ('Ralph Lenkert', 'Lenkert', 'DIE LINKE'))

    # Value: protects=a label printed with a space before its colon ("Michaela Engelmeier (SPD) :", 18/63) is read too;
    #   fails_when=the label match requires the colon right after the parenthesis; why_new=new rule; seam=reviewed
    def test_a_label_with_a_space_before_its_colon(self):
        host = (f'<rede id="ID1806311300">{THEWS}Eigener Text.</p>'
                '<p klasse="N_Anlage">Michaela Engelmeier (SPD) : Wir beraten heute.</p></rede>')
        parsed = parse(block(host), entries=[annex('ID1806311300', '5', 'Michaela Engelmeier (SPD)')])
        self.assertEqual([u[:3] for u in written(parsed)],
                         [('ID1806311300', '3', 'Eigener Text.'), ('ID1806311300:2', '5', 'Wir beraten heute.')])


class OwnerlessRedeTests(unittest.TestCase):
    # Value: protects=an annex <rede> that opens with its writer's label but no marker gets that writer and its text, under its
    #   own id; fails_when=the row keeps no speaker and no text (18/63 Freudenstein); why_new=new rule; seam=reviewed
    def test_a_rede_without_a_marker_gets_its_writer(self):
        rede = ('<rede id="ID1806309700"><p klasse="N_Anlage">Astrid Freudenstein (CDU/CSU) : Wir haben uns vorgenommen.</p>'
                '<p klasse="J">Erstens.</p></rede>')
        parsed = parse(block(rede), entries=[annex('ID1806309700', '11004277', 'Dr. Astrid Freudenstein (CDU/CSU)',
                                                   'Astrid Freudenstein (CDU/CSU)')])
        self.assertEqual([u[:3] for u in written(parsed)], [('ID1806309700', '11004277', 'Wir haben uns vorgenommen.\nErstens.')])
        self.assertEqual(unit(parsed, 'ID1806309700')['unattributed_char_count'], 0)
        self.assertEqual(unit(parsed, 'ID1806309700')['speaker']['display_name'], 'Dr. Astrid Freudenstein')

    # Value: protects=a member of the government printed with a short role in parentheses counts for the Bundesregierung by the
    #   role the entry's name gives (18/76 Böhmer); fails_when=the parenthesised role is read as a Fraktion or the side is lost;
    #   why_new=new rule; seam=reviewed
    def test_a_government_writer_counts_for_the_government(self):
        rede = ('<rede id="ID1807611000"><p klasse="N_Anlage">Dr. Maria Böhmer (Staatsministerin AA) : Lassen Sie mich beginnen.</p>'
                '</rede>')
        parsed = parse(block(rede), entries=[annex('ID1807611000', '11002630', 'Dr. Maria Böhmer, Staatsministerin im Auswärtigen Amt',
                                                   'Dr. Maria Böhmer (Staatsministerin AA)')])
        speaker = unit(parsed, 'ID1807611000')['speaker']
        self.assertEqual((speaker['display_name'], speaker['fraktion'], derive.sprechrolle(speaker)),
                         ('Dr. Maria Böhmer', None, 'bundesregierung'))
        self.assertEqual(unit(parsed, 'ID1807611000')['text'], 'Lassen Sie mich beginnen.')


class WrapTests(unittest.TestCase):
    # Value: protects=a writer's marker and paragraphs standing directly in the block become a <rede> of their own up to the next
    #   <rede>, which keeps its own words (18/46 Schuster); fails_when=the text stays unread or runs into the next writer's;
    #   why_new=new rule; seam=reviewed
    def test_a_marker_directly_in_the_block_wraps_up_to_the_next_rede(self):
        body = (TOP_HEADING + f'{SCHUSTER}Ich hoffe auch.</p><p klasse="J">IT-Systeme.</p>'
                f'<rede id="ID1804618000">{OEZDEMIR}Wir beraten heute.</p></rede>')
        parsed = parse(block(body), entries=[annex('A1', '7', 'Armin Schuster (Weil am Rhein) (CDU/CSU)')])
        self.assertEqual(written(parsed), [
            ('annex:1:1', '7', 'Ich hoffe auch.\nIT-Systeme.', 'Tagesordnungspunkt 1'),
            ('ID1804618000', '6', 'Wir beraten heute.', 'Tagesordnungspunkt 1'),
        ])

    # Value: protects=a text whose writer only the block heading names becomes their Beitrag, from the first paragraph after the
    #   heading, on the page of the last anchor before the block; the block is counted among all annex blocks (18/34 Petry);
    #   fails_when=the text stays unread, the heading is read as text, the page is lost or taken from an anchor inside the text,
    #   or the block index skips other annexes; why_new=new rule; seam=reviewed
    def test_a_text_named_by_the_heading_wraps_to_the_block_end(self):
        # The page anchor stands in the block before: the text begins on that page.
        absentees = block('<p klasse="Anlage_2">Liste der entschuldigten Abgeordneten</p>'
                          '<p klasse="J"><a typ="druckseitennummer" id="S2931" name="S2931"/>Abgeordnete(r)</p>',
                          title='Liste der entschuldigten Abgeordneten')
        body = ('<p klasse="Anlage_2">Zu Protokoll gegebene Rede</p>'
                '<p klasse="Anlage_3">des Abgeordneten Christian Petry (SPD) zur Beratung des Entwurfs (33. Sitzung, '
                'Tagesordnungspunkt 17)</p>'
                '<p klasse="N_Anlage">Vor einem Jahr.</p><p klasse="J">Für mich.<a typ="druckseitennummer" id="S2932" name="S2932"/></p>')
        parsed = parse(absentees, block(body, title='Zu Protokoll gegebene Rede'),
                       entries=[annex('A2', '11004605', 'Christian Petry (SPD)')])
        self.assertEqual(written(parsed), [('annex:2:1', '11004605', 'Vor einem Jahr.\nFür mich.', None)])
        self.assertEqual(unit(parsed, 'annex:2:1')['source_page']['page'], 2931)

    # Value: protects=a label paragraph standing directly in the block after its headings becomes the writer's Beitrag
    #   (18/155 Hakverdi); fails_when=the text stays unread or keeps its label; why_new=new rule; seam=reviewed
    def test_a_label_paragraph_directly_in_the_block_wraps(self):
        body = ('<p klasse="Anlage_3">des Abgeordneten Metin Hakverdi (SPD) zur Beratung</p><p klasse="Anlage_3">sowie</p>'
                '<p klasse="J">Metin Hakverdi (SPD): Im Rahmen.</p><p klasse="J">Weiter.</p>')
        parsed = parse(block(body), entries=[annex('A1', '11004289', 'Metin Hakverdi (SPD)')])
        self.assertEqual([u[:3] for u in written(parsed)], [('annex:1:1', '11004289', 'Im Rahmen.\nWeiter.')])


class GuardTests(unittest.TestCase):
    # Value: protects=a structural shape that would drop a writer's words or store an empty row refuses its sitting unless the
    #   list places it; fails_when=such text is dropped or credited to nobody without a sign; why_new=new guard; seam=reviewed
    def test_unlisted_shapes_refuse(self):
        shapes = {
            'two writers in one rede': f'<rede id="R1">{FABRITIUS}Erster.</p>{HUBER}Zweiter.</p></rede>',
            'a rede without a marker': '<rede id="R1"><p klasse="N_Anlage">Astrid Freudenstein (CDU/CSU) : Text.</p></rede>',
            'a marker outside any rede': f'{SCHUSTER}Ich hoffe auch.</p>',
        }
        for shape, body in shapes.items():
            with self.subTest(shape), self.assertRaises(dip.UnlistedAnnexTextError):
                parse(block(body))

    # Value: protects=the guard reads only zu-Protokoll blocks, so a § 31 annex's <rede> without a marker (18/46, 18/117, 18/118)
    #   still parses; fails_when=the guard reads every annex; why_new=new guard; seam=none
    def test_a_paragraph_31_annex_is_not_guarded(self):
        body = '<rede id="R1"><p klasse="N_Anlage">Karl-Heinz Brunner (SPD) : Mit diesem Gesetz.</p></rede>'
        self.assertEqual(written(parse(block(body, title='Erklärungen nach § 31 GO'))), [])

    # Value: protects=a writer's marker printed again in their own <rede> is no second writer; fails_when=the guard counts markers
    #   instead of Redner-IDs; why_new=new guard; seam=none
    def test_one_writers_repeated_marker_is_not_refused(self):
        body = f'<rede id="R1">{FABRITIUS}Erster.</p>{FABRITIUS}Weiter.</p></rede>'
        self.assertEqual([u[:2] for u in written(parse(block(body)))], [('R1', '1')])

    # Value: protects=a merged record's ids ("1 999990001") name their first, as redner_key reads them, so the same writer's
    #   markers with and without the merged id are one writer; fails_when=the guard compares whole id attributes and refuses the
    #   sitting (Codex, /ship 2026-11-26); why_new=new guard; seam=none
    def test_a_merged_record_id_is_the_same_writer(self):
        merged = marker('1 999990001', 'Bernd', 'Fabritius', 'CDU/CSU')
        body = f'<rede id="R1">{FABRITIUS}Erster.</p>{merged}Weiter.</p></rede>'
        self.assertEqual([u[:2] for u in written(parse(block(body)))], [('R1', '1')])


class EntryErrorTests(unittest.TestCase):
    """An entry the source does not match stops the run: the list needs correcting."""

    HOST = f'<rede id="ID1">{THEWS}Eigener Text.</p><p klasse="J">Ralph Lenkert (DIE LINKE): Elf.</p></rede>'

    def refuses(self, body, entry, message):
        with self.assertRaises(reviewed_units.ReviewedUnitsError) as caught:
            parse(block(body), entries=[entry])
        self.assertIn(message, str(caught.exception))

    # Value: protects=each way an entry can miss its place stops the run with the entry named; fails_when=a stale entry is skipped
    #   and the text silently stays where it was; why_new=new rule; seam=reviewed
    def test_entries_that_do_not_match_stop_the_run(self):
        self.refuses(self.HOST, annex('ID1', '4', 'Klaus Ernst (DIE LINKE)'), 'found nowhere')
        twice = self.HOST.replace('</rede>', '<p klasse="J">Ralph Lenkert (DIE LINKE): Nochmal.</p></rede>')
        self.refuses(twice, annex('ID1', '4', 'Ralph Lenkert (DIE LINKE)'), 'found 2 times')
        huber = f'<rede id="ID1">{FABRITIUS}Erster.</p>{HUBER}Zweiter.</p></rede>'
        self.refuses(huber, annex('ID1', '9', 'Charles M. Huber (CDU/CSU)'), 'Redner-ID 2')
        self.refuses(huber, annex('ID1', '2', 'Charles Huber (CDU/CSU)', 'Charles M. Huber (CDU/CSU)'), 'must equal')
        self.refuses(self.HOST, annex('ID9', '4', 'Ralph Lenkert (DIE LINKE)'), 'names no <rede>')
        self.refuses(self.HOST, annex('A2', '4', 'Ralph Lenkert (DIE LINKE)'), 'names no zu-Protokoll block')
        own = f'<rede id="ID1">{THEWS}Eigener Text.</p></rede>'
        self.refuses(own, annex('ID1', '3', 'Michael Thews (SPD)'), "writer of the <rede> itself")

    # Value: protects=an entry may not name a <rede> outside a zu-Protokoll annex; fails_when=an entry splits a spoken Rede or a
    #   § 31 Erklärung; why_new=new rule; seam=reviewed
    def test_an_entry_for_another_annex_stops_the_run(self):
        self.refuses(self.HOST.replace('ID1', 'ID2'), annex('ID1', '4', 'Ralph Lenkert (DIE LINKE)'), 'names no <rede>')
        with self.assertRaises(reviewed_units.ReviewedUnitsError):
            parse(block(self.HOST, title='Erklärungen nach § 31 GO'), entries=[annex('ID1', '4', 'Ralph Lenkert (DIE LINKE)')])


class ListFormatTests(unittest.TestCase):
    # Value: protects=the list accepts an annex_rede entry with its two extra keys and refuses a malformed one; fails_when=a bad
    #   rede_id, a missing label or a name with its colon passes the check; why_new=new kind; seam=none
    def test_the_kind_is_checked(self):
        reviewed_units.use([annex('A3', '11004605', 'Christian Petry (SPD)'), annex('ID1802308800', '1', 'Ralph Lenkert (DIE LINKE)')])
        reviewed_units.use([])
        bad = [
            annex('A0', '1', 'X Y (SPD)'),
            annex('nested:ID1:2', '1', 'X Y (SPD)'),
            annex('ID1:2', '1', 'X Y (SPD)'),
            annex('ID1', '1', 'X Y (SPD):'),
            annex('ID1', '1', 'X Y (SPD)', ' X Y (SPD)'),
            annex('ID1', 'dip:5', 'X Y (SPD)'),
            {key: value for key, value in annex('ID1', '1', 'X Y (SPD)').items() if key != 'label'},
        ]
        for entry in bad:
            with self.subTest(entry=entry), self.assertRaises(reviewed_units.ReviewedUnitsError):
                reviewed_units.use([entry])
        reviewed_units.use([])

    # Value: protects=every shipped annex_rede name reads as a person with a Fraktion or a side, so each Beitrag counts for someone;
    #   fails_when=a name's role or Fraktion maps to nothing; why_new=new kind; seam=reviewed
    def test_every_shipped_name_reads_as_a_person_with_a_side(self):
        items = [e for entries in reviewed_units.load().values() for e in entries if e['kind'] == 'annex_rede']
        self.assertEqual(len(items), 12)
        for item in items:
            with self.subTest(item['sitting'], name=item['name']):
                speaker = dip.parse_redner(dip.name_tag_marker(item['name'], item['redner_id'], None).find('redner'))
                self.assertTrue(speaker['last_name'])
                self.assertTrue(speaker['fraktion'] or derive.sprechrolle(speaker), item['name'])


STORE_XML = Path('/Users/luca/Projects/poliwatch/.context/dip-pulse-site/data/xml')

#: (sitting, unit id, Redner-ID, page DIP gives, start of the text, the <rede> it came out of or None).
EXPECTED = [
    ('18/17', 'ID1801712700:2', '11004308', 1365, 'Afrika hat im Moment circa 1 Milliarde Einwohner', 'ID1801712700'),
    ('18/23', 'ID1802308800:2', '11004091', 1889, 'Elf Duale Systeme, also Betreiberfirmen', 'ID1802308800'),
    ('18/34', 'annex:2:1', '11004605', 2931, 'Vor ziemlich genau einem Jahr hat das Bundesverfassungsgericht', None),
    ('18/46', 'annex:16:1', '11004149', 4325, 'Ich hoffe auch in diesem Jahr', None),
    ('18/47', 'annex:5:1', '11001186', 4412, 'Wir alle können stolz sein', None),
    ('18/63', 'ID1806311300:2', '11004266', 5949, 'Wir beraten heute also den Antrag der Linken', 'ID1806311300'),
    ('18/63', 'ID1806309700', '11004277', 5932, 'Wir haben uns als Koalition vorgenommen', None),
    ('18/66', 'ID1806614200:2', '11004402', 6317, 'Wir beraten den Entwurf eines Gesetzes', 'ID1806614200'),
    ('18/76', 'ID1807611000', '11002630', 7366, 'Lassen Sie mich persönlich beginnen', None),
    ('18/112', 'ID1811211800:2', '11004402', 10849, 'Die Union unterstützt das Anliegen', 'ID1811211800'),
    ('18/115', 'ID1811515000:2', '11004360', 11240, 'Im November 2014 wurde die ICILS-Studie', 'ID1811515000'),
    ('18/155', 'annex:2:1', '11004289', 15339, 'Im Rahmen des Gesetzgebungsverfahrens', None),
]


@unittest.skipUnless(STORE_XML.is_dir(), 'reference store XML not present')
class RealSittingTests(unittest.TestCase):
    # Value: protects=the shipped list places all twelve E17 texts in the real XML with writer, id, page and text, and the hosts
    #   no longer hold the other writer's words; fails_when=an entry misses its place, the split ends wrong, or a page is off;
    #   why_new=new rule; seam=reviewed
    def test_the_twelve_units_of_the_shipped_list(self):
        with _support.shipped_reviewed_units():
            for number in sorted({row[0] for row in EXPECTED}, key=lambda s: int(s.split('/')[1])):
                wp, nr = number.split('/')
                parsed = dip.parse_protocol_xml((STORE_XML / f'plenarprotokoll-{wp}-{nr}.xml').read_text(encoding='utf-8'))
                for _, rid, redner_id, page, start, host in (row for row in EXPECTED if row[0] == number):
                    with self.subTest(number, rid=rid):
                        written_unit = unit(parsed, rid)
                        self.assertEqual(written_unit['kind'], 'zu_protokoll')
                        self.assertEqual(written_unit['speaker']['xml_redner_id'], redner_id)
                        self.assertEqual(written_unit['source_page']['page'], page)
                        self.assertTrue(written_unit['text'].startswith(start), written_unit['text'][:80])
                        self.assertEqual(written_unit['unattributed_char_count'], 0)
                        if host:
                            self.assertNotIn(start, unit(parsed, host)['text'])


if __name__ == '__main__':
    unittest.main()


class ReplayTests(unittest.TestCase):
    # Value: protects=a store parsed before the annex page rule and the annex guard re-reads every sitting, so an incremental
    #   run fills 19/36 ID193616800's page (3543) as a fresh build does and checks every cached sitting against the guard;
    #   fails_when=the speech rule stays at 16, so only the ten sittings whose reviewed digest changed are re-read;
    #   why_new=code review of 2026-11-26 (the page rule and the guard change parses outside the listed sittings); seam=stale_causes
    def test_a_report_parsed_before_the_annex_rules_is_stale(self):
        import build_dip_pulse_site as build
        import vote_links
        protocol = {"dokumentnummer": "19/36", "xml_url": "https://example.test/19-36.xml"}
        summary = {"speech_kinds_version": 16, "vote_inputs_version": vote_links.INPUTS_VERSION}
        old = _support.stamp_reviewed({"protocol": protocol, "validation_summary": summary})
        self.assertEqual(build.stale_causes(old), ("rule",))
