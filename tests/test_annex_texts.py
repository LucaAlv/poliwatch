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


def bullets(rede_id, redner_id, first, after):
    return {'sitting': SITTING, 'rede_id': rede_id, 'redner_id': redner_id, 'kind': 'annex_paragraphs',
            'reason': 'printed in the PDF after the host paragraph', 'first': first, 'after': after}


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


class DocumentOrderTests(unittest.TestCase):
    """Several entries in one place are applied in document order (E17 items 2 and 6)."""

    # Value: protects=two other writers' markers in one host each split off with their own writer and document ordinal, whichever
    #   order the list gives; fails_when=the first split carries the second marker away, so the second entry finds nothing, or
    #   the parts take ordinals by list order; why_new=code review of 2026-11-26 (E17 items 2 and 6); seam=reviewed
    def test_two_markers_of_one_host_split_in_either_order(self):
        host = (f'<rede id="ID1">{THEWS}Thews.</p>{HUBER}Huber.</p><p klasse="J">Huber weiter.</p>'
                f'{FABRITIUS}Fabritius.</p></rede>')
        entries = [annex('ID1', '2', 'Charles M. Huber (CDU/CSU)'), annex('ID1', '1', 'Bernd Fabritius (CDU/CSU)')]
        for order in (entries, entries[::-1]):
            with self.subTest([e['label'] for e in order]):
                self.assertEqual([u[:3] for u in written(parse(block(host), entries=order))], [
                    ('ID1', '3', 'Thews.'), ('ID1:2', '2', 'Huber.\nHuber weiter.'), ('ID1:3', '1', 'Fabritius.')])

    # Value: protects=where the earlier text of a host opens with a label paragraph (no marker yet), the later part still counts
    #   it, so the two parts get distinct ordinals; fails_when=a split last to first counts markers before the earlier one is
    #   made and both parts are ID1:2 (C2 of the plan review); why_new=plan review 2026-11-27; seam=reviewed
    def test_a_label_paragraph_before_a_marker_in_one_host(self):
        host = (f'<rede id="ID1">{THEWS}Thews.</p><p klasse="J">Ralph Lenkert (DIE LINKE): Elf.</p>'
                f'{HUBER}Huber.</p></rede>')
        entries = [annex('ID1', '2', 'Charles M. Huber (CDU/CSU)'), annex('ID1', '4', 'Ralph Lenkert (DIE LINKE)')]
        for order in (entries, entries[::-1]):
            with self.subTest([e['label'] for e in order]):
                self.assertEqual([u[:3] for u in written(parse(block(host), entries=order))], [
                    ('ID1', '3', 'Thews.'), ('ID1:2', '4', 'Elf.'), ('ID1:3', '2', 'Huber.')])

    # Value: protects=two texts of one block listed out of document order get distinct places, each counting the units made
    #   before it; fails_when=the later text is wrapped first and both become annex:1:1 (E17 item 6); why_new=/ship red team
    #   2026-11-26; seam=reviewed
    def test_two_block_texts_listed_out_of_order(self):
        body = (f'{SCHUSTER}Ich hoffe auch.</p><p klasse="Anlage_3">des Abgeordneten Christian Petry (SPD) zur Beratung</p>'
                '<p klasse="N_Anlage">Vor einem Jahr.</p>')
        entries = [annex('A1', '11004605', 'Christian Petry (SPD)'), annex('A1', '7', 'Armin Schuster (Weil am Rhein) (CDU/CSU)')]
        for order in (entries, entries[::-1]):
            with self.subTest([e['label'] for e in order]):
                self.assertEqual([u[:3] for u in written(parse(block(body), entries=order))], [
                    ('annex:1:1', '7', 'Ich hoffe auch.'), ('annex:1:2', '11004605', 'Vor einem Jahr.')])

    # Value: protects=two label-paragraph texts standing back to back in a block, with no <rede> or heading between, become two
    #   Beiträge whichever order the list gives; fails_when=the first wrap swallows the second text and credits it to the first
    #   writer (R4 of the plan review); why_new=Codex outside voice 2026-11-27; seam=reviewed
    def test_adjacent_label_paragraphs_in_one_block(self):
        body = ('<p klasse="J">Metin Hakverdi (SPD): Im Rahmen.</p><p klasse="J">Weiter.</p>'
                '<p klasse="J">Ralph Lenkert (DIE LINKE): Elf.</p><p klasse="J">Zwei.</p>')
        entries = [annex('A1', '11004289', 'Metin Hakverdi (SPD)'), annex('A1', '4', 'Ralph Lenkert (DIE LINKE)')]
        for order in (entries, entries[::-1]):
            with self.subTest([e['label'] for e in order]):
                self.assertEqual([u[:3] for u in written(parse(block(body), entries=order))], [
                    ('annex:1:1', '11004289', 'Im Rahmen.\nWeiter.'), ('annex:1:2', '4', 'Elf.\nZwei.')])


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

    # Value: protects=a block wrap ends at the next annex heading, so the Rede after it keeps its TOP and the heading is no
    #   writer's text; fails_when=the wrap runs on to the next <rede> and takes the heading (E17 item 7); why_new=/ship
    #   coverage audit 2026-11-26; seam=reviewed
    def test_a_wrap_ends_at_an_annex_heading(self):
        body = f'{SCHUSTER}Ich hoffe auch.</p>{TOP_HEADING}<rede id="ID2">{OEZDEMIR}Wir beraten heute.</p></rede>'
        parsed = parse(block(body), entries=[annex('A1', '7', 'Armin Schuster (Weil am Rhein) (CDU/CSU)')])
        self.assertEqual(written(parsed), [('ID2', '6', 'Wir beraten heute.', 'Tagesordnungspunkt 1'),
                                           ('annex:1:1', '7', 'Ich hoffe auch.', None)])

    # Value: protects=a label paragraph standing directly in the block after its headings becomes the writer's Beitrag
    #   (18/155 Hakverdi); fails_when=the text stays unread or keeps its label; why_new=new rule; seam=reviewed
    def test_a_label_paragraph_directly_in_the_block_wraps(self):
        body = ('<p klasse="Anlage_3">des Abgeordneten Metin Hakverdi (SPD) zur Beratung</p><p klasse="Anlage_3">sowie</p>'
                '<p klasse="J">Metin Hakverdi (SPD): Im Rahmen.</p><p klasse="J">Weiter.</p>')
        parsed = parse(block(body), entries=[annex('A1', '11004289', 'Metin Hakverdi (SPD)')])
        self.assertEqual([u[:3] for u in written(parsed)], [('annex:1:1', '11004289', 'Im Rahmen.\nWeiter.')])


class CallerTests(unittest.TestCase):
    """The callers that parse an annex: online, offline and the D6 check."""

    # Value: protects=a sitting refused for an unlisted annex text names the reviewed-list fix online and on an offline
    #   re-parse; fails_when=it reads as corrupt XML ("--fetch-xml"), whose re-fetch returns the same XML (E17 item 7);
    #   why_new=/ship coverage audit 2026-11-26; seam=fetch_text stubbed
    def test_a_refused_sitting_names_the_reviewed_list(self):
        import json
        import tempfile
        from types import SimpleNamespace
        from unittest.mock import patch
        import build_dip_pulse_site as build
        xml = document(block(f'{SCHUSTER}Ich hoffe auch.</p>'))
        protocol = {'id': 'p1', 'dokumentnummer': SITTING, 'fundstelle': {'xml_url': 'https://dserver.bundestag.de/btp/18/18010.xml'}}
        reviewed_units.use([])
        with patch.object(dip, 'fetch_text', return_value=xml), patch.object(dip, 'enrich_with_api'), \
                self.assertRaises(dip.DipError) as online:
            dip.build_report(SimpleNamespace(api_key='test', sleep=0), protocol)
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            (output_dir / 'data' / 'xml').mkdir(parents=True)
            (output_dir / 'data' / 'xml' / 'plenarprotokoll-18-10.xml').write_text(xml, encoding='utf-8')
            report = {'protocol': {'id': 'p1', 'dokumentnummer': SITTING}, 'agenda_items': []}
            (output_dir / 'data' / 'plenarprotokoll-18-10.json').write_text(json.dumps(report), encoding='utf-8')
            entries = build.load_existing_detail_entries(output_dir, [{'dokumentnummer': SITTING}])
            with self.assertRaises(build.CachedReportError) as replay:
                build.reparse_cached_xml(output_dir, entries)
        self.assertTrue(online.exception.source_rejected)
        self.assertIn('scripts/reviewed_units.json with kind annex_rede', str(online.exception))
        printed_replay = f'{replay.exception}. {build.cached_report_fix(replay.exception)}'
        self.assertIn('scripts/reviewed_units.json with kind annex_rede', printed_replay)
        self.assertNotIn('--fetch-xml', printed_replay)

    # Value: protects=the D6 check (check_withhold_one) applies a sitting's annex entries in both its parses, so a sitting
    #   whose annex text only an entry places is checked rather than refused; fails_when=check_sitting drops the annex kinds
    #   and every such sitting fails its base parse (E17 item 7); why_new=/ship coverage audit 2026-11-26; seam=reviewed
    def test_check_withhold_one_reads_annex_entries(self):
        import check_withhold_one
        spoken = ''.join(f'<rede id="S{n}">{THEWS}Gesprochen {n}.</p></rede>' for n in (1, 2, 3))
        xml = document(block(f'{SCHUSTER}Ich hoffe auch.</p>')).replace(
            '<p klasse="T_NaS">Beratung des Antrags</p>', f'<p klasse="T_NaS">Beratung des Antrags</p>{spoken}')
        reviewed_units.use([annex('A1', '7', 'Armin Schuster (Weil am Rhein) (CDU/CSU)')])
        try:
            result = check_withhold_one.check_sitting(xml)
        finally:
            reviewed_units.use([])
        self.assertEqual(result['middle'], {'withheld': 1, 'problems': []})


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

    # Value: protects=a marker that names nobody (no, an empty or a blank id) beside a real writer's marker refuses the sitting
    #   with the guard's own error, and markers with a missing and an empty id are two unknown writers, not one; fails_when=the
    #   message's sorted() raises TypeError, or the two unidentified markers pass as one writer (E17 item 5, Codex on 185a33a);
    #   why_new=code review of 2026-11-26; seam=reviewed
    def test_unidentified_markers_refuse(self):
        def unidentified(attribute):
            return f'<p klasse="redner"><redner{attribute}><name><vorname>X</vorname><nachname>Y</nachname></name></redner>X Y: '
        shapes = {
            'no id beside a real one': f'<rede id="R1">{FABRITIUS}Erster.</p>{unidentified("")}Zweiter.</p></rede>',
            'an empty id beside a real one': f'<rede id="R1">{FABRITIUS}Erster.</p>{unidentified(" id=\"\"")}Zweiter.</p></rede>',
            'a blank id beside a real one': f'<rede id="R1">{FABRITIUS}Erster.</p>{unidentified(" id=\" \"")}Zweiter.</p></rede>',
            'no id and an empty id': f'<rede id="R1">{unidentified("")}Erster.</p>{unidentified(" id=\"\"")}Zweiter.</p></rede>',
        }
        for shape, body in shapes.items():
            with self.subTest(shape), self.assertRaisesRegex(dip.UnlistedAnnexTextError, 'markers of 2 Redner-IDs'):
                parse(block(body))


class LooseParagraphTests(unittest.TestCase):
    """Bullet points printed loose after their <rede> go back in at the printed place (annex_paragraphs)."""

    HOST = (f'<rede id="ID1">{THEWS}Thews eröffnet.</p><p klasse="J">Zwei Punkte sind wichtig:</p>'
            '<p klasse="J">Danach geht es weiter.</p></rede>')
    NEXT = f'<rede id="ID2">{OEZDEMIR}Wir beraten heute.</p></rede>'
    LOOSE = '<p klasse="J">– Punkt eins.</p><p klasse="J">– Punkt zwei.</p>'
    ENTRY = bullets('ID1', '3', '– Punkt eins', 'Zwei Punkte sind wichtig:')

    # Value: protects=a run of loose bullets goes in right after the host paragraph that opens it, before the paragraph printed
    #   next, and up to the next <rede>, which keeps its own words (18/136 Strebl and Kapschack, 18/209, 18/243, 19/104);
    #   fails_when=the bullets stay unread, land at the Rede's end or run into the next Rede; why_new=TODOS "Bullet points of
    #   written Reden"; seam=reviewed
    def test_bullets_go_in_after_the_paragraph_that_opens_them(self):
        parsed = parse(block(TOP_HEADING + self.HOST + self.LOOSE + self.NEXT), entries=[self.ENTRY])
        self.assertEqual([u[:3] for u in written(parsed)], [
            ('ID1', '3', 'Thews eröffnet.\nZwei Punkte sind wichtig:\n– Punkt eins.\n– Punkt zwei.\nDanach geht es weiter.'),
            ('ID2', '6', 'Wir beraten heute.')])
        self.assertEqual(unit(parsed, 'ID1')['paragraph_count'], 5)

    # Value: protects=a run opened by the marker paragraph itself goes in after it, and a run at the block's end ends there
    #   (18/206 Binding); fails_when=the marker paragraph is not searched or the run needs a following <rede>; why_new=TODOS
    #   "Bullet points of written Reden"; seam=reviewed
    def test_bullets_after_the_marker_paragraph_at_the_block_end(self):
        host = (f'<rede id="ID1">{THEWS}Drei Themen hätten es verdient:</p><p klasse="J">Die Umsetzung.</p></rede>'
                '<p klasse="J">Bekämpfung von Gewinnkürzungen</p><p klasse="J">Entlastung</p>')
        parsed = parse(block(host), entries=[bullets('ID1', '3', 'Bekämpfung', 'hätten es verdient:')])
        self.assertEqual([u[:3] for u in written(parsed)], [
            ('ID1', '3', 'Drei Themen hätten es verdient:\nBekämpfung von Gewinnkürzungen\nEntlastung\nDie Umsetzung.')])

    # Value: protects=a run stops at the first paragraph that is no text, so a page scrap stays out of the writer's words, and
    #   text left behind the scrap still refuses the sitting (R3 of the plan review); fails_when=a page number or notice is
    #   stored as an MdB's written words, or text after it is dropped silently; why_new=Codex outside voice 2026-11-27;
    #   seam=reviewed
    def test_a_page_scrap_ends_the_run(self):
        scrap = '<p klasse="Standard">-12409</p>'
        parsed = parse(block(self.HOST + self.LOOSE + scrap + self.NEXT), entries=[self.ENTRY])
        self.assertNotIn('12409', unit(parsed, 'ID1')['text'])
        self.assertIn('– Punkt zwei.\nDanach', unit(parsed, 'ID1')['text'])
        with self.assertRaisesRegex(dip.UnlistedAnnexTextError, 'Punkt drei'):
            parse(block(self.HOST + self.LOOSE + scrap + '<p klasse="J">– Punkt drei.</p>' + self.NEXT), entries=[self.ENTRY])

    # Value: protects=one host can hold two runs, each ending where the next entry's run begins, each at its own place;
    #   fails_when=the first run swallows the second or the second entry is refused; why_new=new kind; seam=reviewed
    def test_two_runs_of_one_host(self):
        host = (f'<rede id="ID1">{THEWS}Erstens:</p><p klasse="J">Zweitens:</p><p klasse="J">Schluss.</p></rede>'
                '<p klasse="J">– a</p><p klasse="J">– b</p><p klasse="J">– c</p>')
        entries = [bullets('ID1', '3', '– c', 'Zweitens:'), bullets('ID1', '3', '– a', 'Erstens:')]
        self.assertEqual([u[2] for u in written(parse(block(host), entries=entries))],
                         ['Erstens:\n– a\n– b\nZweitens:\n– c\nSchluss.'])

    # Value: protects=bullets of a host that an annex_rede entry splits go to the unit holding the paragraph they follow, and
    #   redner_id is checked against that unit's writer (R5 of the plan review); fails_when=bullets after the split point are
    #   credited to the host's writer, or an entry naming the wrong writer passes; why_new=Codex outside voice 2026-11-27;
    #   seam=reviewed
    def test_bullets_of_a_split_host_go_to_the_unit_that_holds_their_place(self):
        host = (f'<rede id="ID1">{THEWS}Thews nennt:</p>{HUBER}Huber nennt:</p><p klasse="J">Huber Schluss.</p></rede>'
                '<p klasse="J">– Punkt.</p>')
        split = annex('ID1', '2', 'Charles M. Huber (CDU/CSU)')
        self.assertEqual([u[:3] for u in written(parse(block(host), entries=[split, bullets('ID1', '2', '– Punkt', 'Huber nennt:')]))],
                         [('ID1', '3', 'Thews nennt:'), ('ID1:2', '2', 'Huber nennt:\n– Punkt.\nHuber Schluss.')])
        self.assertEqual([u[:3] for u in written(parse(block(host), entries=[split, bullets('ID1', '3', '– Punkt', 'Thews nennt:')]))],
                         [('ID1', '3', 'Thews nennt:\n– Punkt.'), ('ID1:2', '2', 'Huber nennt:\nHuber Schluss.')])
        with self.assertRaisesRegex(reviewed_units.ReviewedUnitsError, 'owner carries Redner-ID 2, not 3'):
            parse(block(host), entries=[split, bullets('ID1', '3', '– Punkt', 'Huber nennt:')])

    # Value: protects=each way an annex_paragraphs entry can miss its place stops the run with the entry named; fails_when=a
    #   stale entry is skipped, a scrap is moved, or the run goes to a paragraph that ends the same way twice; why_new=new kind;
    #   seam=reviewed
    def test_entries_that_do_not_match_stop_the_run(self):
        body = self.HOST + self.LOOSE + self.NEXT
        cases = [
            (bullets('ID9', '3', '– Punkt eins', 'wichtig:'), 'names no <rede>'),
            (bullets('ID1', '3', '– Punkt neun', 'wichtig:'), 'first paragraph is found nowhere'),
            (bullets('ID1', '3', '– Punkt eins', 'unwichtig:'), 'is found nowhere in ID1'),
            (bullets('ID1', '3', '– Punkt eins', '.'), 'is found 2 times in ID1'),
            (bullets('ID1', '6', '– Punkt eins', 'wichtig:'), 'owner carries Redner-ID 3, not 6'),
            (bullets('ID2', '6', '– Punkt eins', 'heute.'), 'first paragraph is found nowhere'),
        ]
        for entry, message in cases:
            with self.subTest(message, entry=entry), self.assertRaisesRegex(reviewed_units.ReviewedUnitsError, message):
                parse(block(body), entries=[entry])
        scrap = self.HOST + '<p klasse="Standard">– Punkt eins.</p>' + self.NEXT
        with self.subTest('a scrap'), self.assertRaisesRegex(reviewed_units.ReviewedUnitsError, 'first paragraph is found nowhere'):
            parse(block(scrap), entries=[self.ENTRY])
        with self.subTest('one place twice'), self.assertRaisesRegex(reviewed_units.ReviewedUnitsError, 'names the place'):
            parse(block(body), entries=[self.ENTRY, bullets('ID1', '3', '– Punkt zwei', 'Zwei Punkte sind wichtig:')])

    # Value: protects=the D6 check applies annex_paragraphs entries in both its parses; fails_when=check_sitting drops the kind
    #   and the guard refuses each of the five sittings; why_new=new kind (C3 of the plan review); seam=reviewed
    def test_check_withhold_one_reads_the_kind(self):
        import check_withhold_one
        spoken = ''.join(f'<rede id="S{n}">{THEWS}Gesprochen {n}.</p></rede>' for n in (1, 2, 3))
        xml = document(block(self.HOST + self.LOOSE)).replace(
            '<p klasse="T_NaS">Beratung des Antrags</p>', f'<p klasse="T_NaS">Beratung des Antrags</p>{spoken}')
        reviewed_units.use([self.ENTRY])
        try:
            self.assertEqual(check_withhold_one.check_sitting(xml)['middle'], {'withheld': 1, 'problems': []})
        finally:
            reviewed_units.use([])


class LooseTextGuardTests(unittest.TestCase):
    # Value: protects=a paragraph of Rede text standing loose in a zu-Protokoll block after a <rede> (the shape of the 24 WP 18/19
    #   bullet points), in any of the text classes or with none, refuses its sitting unless an annex_paragraphs entry places it;
    #   fails_when=those words are stored nowhere without a sign; why_new=TODOS "Bullet points of written Reden" (R1 of the
    #   plan review adds the paragraph without klasse); seam=reviewed
    def test_loose_text_after_a_rede_refuses(self):
        for klasse in ('J', 'J_1', 'J-Strich', 'J_Abstand', 'N_Anlage', 'O', 'Z', None):
            attribute = f' klasse="{klasse}"' if klasse else ''
            body = f'<rede id="ID1">{THEWS}Thews.</p></rede><p{attribute}>– Ein Punkt.</p>'
            with self.subTest(klasse), self.assertRaisesRegex(dip.UnlistedAnnexTextError, 'stands loose after annex <rede> ID1'):
                parse(block(body))

    # Value: protects=what the guard leaves alone: loose text after an annex heading (a TOP line before the first <rede>, 18/158),
    #   page scraps (Standard) and first-edition notices (Ende, p) after a <rede>; fails_when=a held sitting is refused over
    #   markup no entry can fix; why_new=census of the 806 files 2026-11-27; seam=reviewed
    def test_loose_text_after_a_heading_and_scraps_after_a_rede_pass(self):
        body = (f'{TOP_HEADING}<p klasse="J">Tagesordnungspunkt 1: Antrag.</p><rede id="ID1">{THEWS}Thews.</p></rede>'
                '<p klasse="Standard">-12409</p><p klasse="Ende">Vorabfassung</p><p klasse="p">Hinweis</p>'
                f'<p klasse="Anlage_3">zur Beratung</p><p klasse="J">Zeile nach der Überschrift.</p>')
        self.assertEqual([u[:3] for u in written(parse(block(body)))], [('ID1', '3', 'Thews.')])

    # Value: protects=the guard reads only zu-Protokoll blocks; fails_when=loose text in another annex (an absentee list) refuses
    #   a sitting; why_new=new guard; seam=none
    def test_another_annex_is_not_guarded(self):
        body = f'<rede id="ID1">{THEWS}Thews.</p></rede><p klasse="J">Abgeordnete(r)</p>'
        self.assertEqual(written(parse(block(body, title='Erklärungen nach § 31 GO'))), [])


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
        petry = '<p klasse="Anlage_3">des Abgeordneten Christian Petry (SPD)</p>'
        self.refuses(petry, annex('A1', '11004605', 'Christian Petry (SPD)'), 'no text paragraph follows the heading')
        self.refuses(petry + f'{SCHUSTER}Ich hoffe auch.</p>', annex('A1', '11004605', 'Christian Petry (SPD)'),
                     'no text paragraph follows the heading')

    # Value: protects=both entry checks read a merged record's ids ("2 999990001") as their first, as the guard does: the
    #   printed marker's Redner-ID and the host owner's; fails_when=a merged id fails the marker check, or a host owner with a
    #   merged id lets an entry split off the owner's own words; why_new=E17 item 5 (Codex on 185a33a); seam=reviewed
    def test_both_entry_checks_read_a_merged_id_as_its_first(self):
        merged_huber = marker('2 999990001', 'Charles M.', 'Huber', 'CDU/CSU')
        host = f'<rede id="ID1">{FABRITIUS}Erster.</p>{merged_huber}Zweiter.</p></rede>'
        self.assertEqual([u[:2] for u in written(parse(block(host), entries=[annex('ID1', '2', 'Charles M. Huber (CDU/CSU)')]))],
                         [('ID1', '1'), ('ID1:2', '2 999990001')])
        merged_owner = marker('3 999990002', 'Michael', 'Thews', 'SPD', printed='Thews (SPD): ')
        self.refuses(f'<rede id="ID1">{merged_owner}Eigener Text.</p><p klasse="J">Michael Thews (SPD): Weiter.</p></rede>',
                     annex('ID1', '3', 'Michael Thews (SPD)'), "writer of the <rede> itself")

    # Value: protects=an entry may not name a <rede> outside a zu-Protokoll annex; fails_when=an entry splits a spoken Rede or a
    #   § 31 Erklärung; why_new=new rule; seam=reviewed
    def test_an_entry_for_another_annex_stops_the_run(self):
        self.refuses(self.HOST.replace('ID1', 'ID2'), annex('ID1', '4', 'Ralph Lenkert (DIE LINKE)'), 'names no <rede>')
        with self.assertRaises(reviewed_units.ReviewedUnitsError):
            parse(block(self.HOST, title='Erklärungen nach § 31 GO'), entries=[annex('ID1', '4', 'Ralph Lenkert (DIE LINKE)')])

    # Value: protects=a unit inserted before an annex <rede> without an id would shift that <rede>'s key annex:<block>:<n>, so
    #   the entry stops the run and names the key instead of the reconciliation refusing the sitting (E17 item 1, answered
    #   "refuse"); fails_when=the new unit takes or shifts the key and the sitting fails reconciliation with no pointer to the
    #   entry; why_new=code review of 2026-11-26; seam=reviewed
    def test_an_entry_before_an_annex_rede_without_id_stops_the_run(self):
        idless = f'<rede>{OEZDEMIR}Wir beraten heute.</p></rede>'
        self.refuses(f'{SCHUSTER}Ich hoffe auch.</p>{idless}', annex('A1', '7', 'Armin Schuster (Weil am Rhein) (CDU/CSU)'),
                     'annex:1:1 after it has no id')
        self.refuses(f'{self.HOST}{idless}', annex('ID1', '4', 'Ralph Lenkert (DIE LINKE)'), 'annex:1:2 after it has no id')

    # Value: protects=two entries that locate one place (a heading naming two writers) stop the run instead of one wrap holding
    #   both texts under one writer; fails_when=the second entry finds its place inside the first's unit or silently wins;
    #   why_new=E17 item 6 (locate before apply); seam=reviewed
    def test_two_entries_of_one_place_stop_the_run(self):
        body = ('<p klasse="Anlage_3">der Abgeordneten Christian Petry (SPD) und Metin Hakverdi (SPD)</p>'
                '<p klasse="N_Anlage">Vor einem Jahr.</p>')
        with self.assertRaisesRegex(reviewed_units.ReviewedUnitsError, 'names the place of the entry'):
            parse(block(body), entries=[annex('A1', '11004605', 'Christian Petry (SPD)'),
                                        annex('A1', '11004289', 'Metin Hakverdi (SPD)')])


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

    # Value: protects=two written Reden in one place (a host <rede> or an A<n> block) are listed by their labels, and one label
    #   listed twice is refused; fails_when=the second text of a place cannot be listed, so its sitting stays refused (E17
    #   item 2); why_new=code review of 2026-11-26; seam=reviewed
    def test_two_labels_of_one_place_are_two_entries(self):
        for place in ('ID1', 'A2'):
            with self.subTest(place):
                reviewed_units.use([annex(place, '2', 'Charles M. Huber (CDU/CSU)'), annex(place, '1', 'Bernd Fabritius (CDU/CSU)')])
                with self.assertRaisesRegex(reviewed_units.ReviewedUnitsError, 'listed twice'):
                    reviewed_units.use([annex(place, '2', 'Charles M. Huber (CDU/CSU)'), annex(place, '9', 'X Y (SPD)',
                                                                                              'Charles M. Huber (CDU/CSU)')])
        reviewed_units.use([])

    # Value: protects=the list accepts an annex_paragraphs entry with first and after and refuses a malformed one, and keys it by
    #   its first words, so one host can hold two runs; fails_when=a block id, a missing key, words with outer spaces or a run
    #   listed twice pass the check; why_new=new kind; seam=none
    def test_the_paragraphs_kind_is_checked(self):
        good = bullets('ID1813611300', '11002940', '– Beschäftigte mit', 'auf zwei Personengruppen richten wollen:')
        reviewed_units.use([good, {**good, 'first': '– Arbeitnehmerinnen'}])
        self.assertIn('annex_paragraphs', reviewed_units.ANNEX_KINDS)
        self.assertIn('annex_rede', reviewed_units.ANNEX_KINDS)
        bad = [
            {**good, 'rede_id': 'A6'},
            {**good, 'rede_id': 'ID1:2'},
            {**good, 'first': ' – Beschäftigte'},
            {**good, 'after': 'wollen: '},
            {**good, 'after': ''},
            {**good, 'redner_id': 'dip:5'},
            {key: value for key, value in good.items() if key != 'after'},
            {**good, 'label': 'X'},
        ]
        for entry in bad:
            with self.subTest(entry=entry), self.assertRaises(reviewed_units.ReviewedUnitsError):
                reviewed_units.use([entry])
        with self.assertRaisesRegex(reviewed_units.ReviewedUnitsError, 'listed twice'):
            reviewed_units.use([good, {**good, 'after': 'Andere Stelle:'}])
        reviewed_units.use([])

    # Value: protects=the reviewed digest ignores the file order of entries that tie on rede_id, kind and name, and the shipped
    #   digests stay as they were (21/84's demo fixture); fails_when=reordering two entries of one host forces a needless replay,
    #   or the tie-break changes every multi-entry digest; why_new=Codex outside voice on the annex-bullets plan (R6); seam=none
    def test_tied_entries_give_one_digest_in_either_order(self):
        import json
        first = annex('ID1', '2', 'Charles M. Huber (CDU/CSU)', 'Charles M. Huber')
        second = annex('ID1', '2', 'Charles M. Huber (CDU/CSU)', 'Huber')
        self.assertEqual(reviewed_units.digest([first, second]), reviewed_units.digest([second, first]))
        fixture = json.loads((_support.FIXTURES / 'demo-report-21-84.json').read_text(encoding='utf-8'))
        self.assertEqual(fixture['protocol']['reviewed_digest'], _support.shipped_digest('21/84'))

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


#: (sitting, host, paragraphs the host holds in the source, index of the paragraph the run follows, paragraphs moved, words
#: moved, start of the first moved paragraph, start of the paragraph printed after the run). Placed against the PDFs.
BULLETS = [
    ('18/136', 'ID1813611300', 9, 6, 2, 16, '– Beschäftigte mit einem geringeren', 'Ebenso dürfen wir auch nicht'),
    ('18/136', 'ID1813611400', 12, 8, 4, 45, '– Die Verringerung der Unverfallbarkeitsfristen', 'Ein Wort noch zu dem Vorschlag'),
    ('18/206', 'ID1820612300', 20, 0, 3, 18, 'Bekämpfung von Gewinnkürzungen', 'Die Umsetzung der Änderungen'),
    ('18/209', 'ID1820916300', 17, 12, 8, 126, '– Die vielfältigen Einsatzmöglichkeiten', 'Mit dem heute vorliegenden Antrag'),
    ('18/243', 'ID1824313700', 7, 5, 4, 158, '– Erst einmal mehr Kinderschutz', 'In der nächsten Wahlperiode'),
    ('19/104', 'ID1910418500', 7, 5, 3, 186, '1. Statt das Problem wirklich', 'Generell ist diese Große Koalition'),
]


@unittest.skipUnless(STORE_XML.is_dir(), 'reference store XML not present')
class RealBulletTests(unittest.TestCase):
    # Value: protects=the shipped list puts the 24 loose bullet paragraphs of six written Reden back at the printed place, 549
    #   words in all, and the sittings parse past the new guard; fails_when=a run lands elsewhere, takes a paragraph too many or
    #   too few, or a sitting is refused; why_new=TODOS "Bullet points of written Reden"; seam=reviewed
    def test_the_six_hosts_of_the_shipped_list(self):
        with _support.shipped_reviewed_units():
            for number in sorted({row[0] for row in BULLETS}, key=lambda s: tuple(map(int, s.split('/')))):
                wp, nr = number.split('/')
                parsed = dip.parse_protocol_xml((STORE_XML / f'plenarprotokoll-{wp}-{nr}.xml').read_text(encoding='utf-8'))
                for _, host, held, after, moved, words, first, following in (row for row in BULLETS if row[0] == number):
                    with self.subTest(number, host=host):
                        paragraphs = unit(parsed, host)['text'].split('\n')
                        self.assertEqual(len(paragraphs), held + moved)
                        run = paragraphs[after + 1:after + 1 + moved]
                        self.assertTrue(run[0].startswith(first), run[0][:60])
                        self.assertTrue(paragraphs[after + 1 + moved].startswith(following), paragraphs[after + 1 + moved][:60])
                        self.assertEqual(sum(len(p.split()) for p in run), words)
        self.assertEqual(sum(row[5] for row in BULLETS), 549)


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


if __name__ == '__main__':
    unittest.main()
