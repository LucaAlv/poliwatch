"""Stable public references and durable registry contracts across rebuilds."""
from __future__ import annotations
import contextlib
import io
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import _support
import build_dip_pulse_site as build
import persist_dip_pulse_store as store
import person_registry as registry
import render_dip_pulse_html as render
import facts
from stable_ids import stable_key


def report(pid='s1', names=('Ada Example',)):
    return {'protocol': {'id':pid,'dokumentnummer':f'21/{pid[-1]}','datum':'2026-06-10'},
            'agenda_items':[{'index':1,'heading':'Debatte','xml_speakers':[
                {'rede_id':f'{pid}-r{index}', 'speaker':{'display_name':name,'xml_redner_id':str(index+1),'fraktion':'SPD'},
                 'char_count':20,'text':'Ein geprüfter Text.'} for index,name in enumerate(names)]}]}

class StableIDsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);(self.root/"data").mkdir();self.db=self.root/'store.sqlite'

    def entries(self, reports):
        return [{'report':r,'report_path':self.root/f'{r["protocol"]["id"]}.json'} for r in reports]

    def rebuild(self, reports, **kwargs):
        with contextlib.redirect_stderr(io.StringIO()):
            return build.rebuild_database_from_entries(self.db,self.entries(reports),**kwargs)

    def rows(self, table):
        with sqlite3.connect(self.db) as conn:
            conn.row_factory=sqlite3.Row
            return [dict(r) for r in conn.execute(f'SELECT * FROM {table} ORDER BY 1')]

    def test_keys_are_namespaced_versioned_and_canonical(self):
        self.assertEqual(stable_key('x',{'a':1,'b':2}),stable_key('x',{'b':2,'a':1}))
        self.assertNotEqual(stable_key('x','1'),stable_key('x',1))
        self.assertNotEqual(stable_key('x',1),stable_key('y',1))
        self.assertRegex(stable_key('x',1),r'^x-v1-[a-f0-9]{64}$')

    # Value: protects=stable_key output is frozen for known inputs, including Unicode and the type distinction, and non-finite numbers are refused; fails_when=separators, ensure_ascii, payload shape, key version or hash change so every table key, person URL and fact id is silently re-minted; why_new=every other test computes its expectations through stable_key itself; seam=none
    def test_key_output_is_frozen_for_known_inputs(self):
        self.assertEqual(stable_key('x',1),'x-v1-3917d754158d271f418a7d083033d60dc40f1e82541c209ca972b85bfd82a35a')
        self.assertEqual(stable_key('person','xml','11005304'),'person-v1-cd689b2db95ea8e4e75f592d31361c7adf20c8a73b631060e2fba9396a92d5df')
        self.assertEqual(stable_key('party','Föhr'),'party-v1-d07fc77cfe7d1febe015d8ee917ec788ade61a037601d936c0d8770cba3314a9')
        with self.assertRaises(ValueError):stable_key('x',float('nan'))

    # Value: protects=two namesake members of different Fraktionen in one roll call get different occurrence keys; fails_when=party is dropped from vote_member_occurrence_id so they collapse into one mps row, one person and one vote_members row; why_new=the only test computed its expectation through the function itself; seam=none
    def test_vote_member_key_is_frozen_and_separates_namesakes_by_party(self):
        from stable_ids import vote_member_occurrence_id
        self.assertEqual(vote_member_occurrence_id('v1','Michael Müller','SPD'),'vote-member-v1-f65793eb91bbc3de162d308884da162b58893743ab9259460cf8fa080fa0c86d')
        self.assertEqual(vote_member_occurrence_id('v1','Michael Müller','CDU/CSU'),'vote-member-v1-89cd236d3e9f784ee39ce29e638bf5278b7f1f59553ee122960752c330a8e883')

    # Value: protects=store, renderer and bill pages derive the same rede id and occurrence key, including whitespace normalisation and the synthetic fallback; fails_when=speech_rede_id stops cleaning the id or the synthetic format changes; why_new=the shared helper had no direct test; seam=none
    def test_speech_rede_id_cleans_and_falls_back_to_the_synthetic_id(self):
        from stable_ids import speech_rede_id,speech_occurrence_id,synthetic_rede_id
        self.assertEqual(speech_rede_id('p1',3,2,'\xa0 r1 '),'r1')
        self.assertEqual(speech_rede_id('p1',3,2,None),'p1:3:2')
        self.assertEqual(speech_rede_id('p1',3,2,'  '),synthetic_rede_id('p1',3,2))
        self.assertEqual(speech_occurrence_id(7,'r1'),stable_key('speech','7','r1'))

    def test_reordering_and_new_sitting_preserve_shared_rows_and_references(self):
        r=report();self.rebuild([r]);before={t:self.rows(t) for t in ('agenda_items','speeches','mps','person_bindings')}
        self.rebuild([report('s2'),r])
        for table,rows in before.items():
            current={row['id']:row for row in self.rows(table)}
            for row in rows:
                for field,value in row.items():
                    if field not in ('created_at','updated_at'):
                        self.assertEqual(current[row['id']][field],value,(table,field))
        with sqlite3.connect(self.db) as conn:self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_synthetic_rede_uses_source_item_index(self):
        r=report();r['agenda_items'][0]['xml_speakers'][0].pop('rede_id');self.rebuild([r])
        self.assertEqual(self.rows('speeches')[0]['rede_id'],'s1:1:1')
        self.rebuild([r,report('s2')]);self.assertIn('s1:1:1',[s['rede_id'] for s in self.rows('speeches')])

    def test_occurrence_survives_attribute_and_enrichment_changes(self):
        r=report();self.rebuild([r]);before=self.rows('mps')[0]
        speaker=r['agenda_items'][0]['xml_speakers'][0]['speaker'];speaker.update(display_name='Dr. Ada Example',abgeordnetenwatch={'id':17,'match':'ext_id'})
        self.rebuild([r]);after=self.rows('mps')[0]
        self.assertEqual((before['id'],before['person_id']),(after['id'],after['person_id']))
        self.assertEqual(after['aw_politician_id'],17)

    def test_registry_survives_empty_input_and_reappearance_independent_of_roster(self):
        r=report();self.rebuild([r]);before=self.rows('persons');bindings=self.rows('person_bindings')
        # Removing source rows explicitly simulates disappearance; rebuilds refuse missing evidence for existing protocols.
        with sqlite3.connect(self.db) as conn:
            conn.execute('DELETE FROM speeches');conn.execute('DELETE FROM agenda_items');conn.execute('DELETE FROM protocols')
        self.rebuild([],preserve_roster=False)
        self.assertEqual(self.rows('persons'),before);self.assertEqual(self.rows('person_bindings'),bindings)
        conn=facts.open_readonly(self.db)
        try:
            mps,lookup=build.collect_abgeordnete(conn)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM mps').fetchone()[0],0)
            build.write_abgeordnete_pages(self.root,mps)
            self.assertTrue((self.root/'abgeordnete'/f'{before[0]["id"]}.html').exists())
        finally:conn.close()
        self.rebuild([r],preserve_roster=False);self.assertEqual(self.rows('persons'),before)

    def correction_file(self,data):
        # A distinct filename per call: corrections() caches on inode, mtime and size.
        self.corrections_written=getattr(self,'corrections_written',0)+1
        path=self.root/f'corrections-{self.corrections_written}.json';path.write_text(json.dumps({'version':1,'partitions':[],'assignments':[],'merges':[],'splits':[],**data}))
        return mock.patch.object(registry,'CORRECTIONS_PATH',path)

    def test_merge_keeps_oldest_and_emits_resolvable_alias_redirect(self):
        r=report(names=('Ada Example','Bea Example'));self.rebuild([r]);people=sorted(self.rows('persons'),key=lambda r:r['ordinal'])
        with self.correction_file({'merges':[{'persons':[p['id'] for p in people]}]}):self.rebuild([r])
        self.assertEqual(self.rows('person_aliases'),[{'id':people[1]['id'],'person_id':people[0]['id']}])
        conn=store.connect(self.db)
        try:
            mps,_=build.collect_abgeordnete(conn);build.write_abgeordnete_pages(self.root,mps)
        finally:conn.close()
        redirect=self.root/'abgeordnete'/f'{people[1]["id"]}.html'
        self.assertIn(f'{people[0]["id"]}.html',redirect.read_text())

    def test_explicit_merge_survivor_can_override_oldest_allocation(self):
        r=report(names=('Ada Example','Bea Example'));self.rebuild([r]);people=sorted(self.rows('persons'),key=lambda row:row['ordinal'])
        ids=[p['id'] for p in people]
        with self.correction_file({'merges':[{'persons':ids}]}):self.rebuild([r])
        with self.correction_file({'merges':[{'persons':ids,'survivor':ids[1]}]}):self.rebuild([r])
        self.assertEqual({m['person_id'] for m in self.rows('mps')},{ids[1]})
        self.assertEqual(self.rows('person_aliases'),[{'id':ids[0],'person_id':ids[1]}])

    def test_project_allocation_does_not_reuse_an_explicit_reserved_key(self):
        conn=store.connect(self.db)
        try:
            store.initialize(conn);first=registry.allocate(conn,'p-000002');second=registry.allocate(conn)
            self.assertNotEqual(first,second)
        finally:conn.close()

    def test_invalid_corrections_preserve_database_bytes(self):
        r=report();self.rebuild([r]);before=self.db.read_bytes()
        with self.correction_file({'merges':[{'persons':['missing']}]}):
            with self.assertRaisesRegex(build.DatabaseRebuildError,'unknown persons'):self.rebuild([r])
        self.assertEqual(before,self.db.read_bytes())

    def test_alias_cycle_and_unreadable_registry_fail_without_replacement(self):
        r=report(names=('Ada Example','Bea Example'));self.rebuild([r]);people=self.rows('persons')
        with sqlite3.connect(self.db) as conn:
            conn.executemany('INSERT INTO person_aliases VALUES (?,?)',[(people[0]['id'],people[1]['id']),(people[1]['id'],people[0]['id'])])
        before=self.db.read_bytes()
        with self.assertRaisesRegex(build.DatabaseRebuildError,'Alias cycle'):self.rebuild([r])
        self.assertEqual(before,self.db.read_bytes())
        with sqlite3.connect(self.db) as conn:
            conn.execute('DELETE FROM person_aliases');conn.execute("UPDATE person_records SET evidence_json='bad'")
        before=self.db.read_bytes()
        with self.assertRaisesRegex(build.DatabaseRebuildError,'Unreadable registry'):self.rebuild([r])
        self.assertEqual(before,self.db.read_bytes())

    def test_writer_overlap_and_crash_recovery_preserve_history(self):
        r=report();self.rebuild([r]);before=self.db.read_bytes();lock=self.db.with_suffix('.sqlite.writer.lock')
        proc=subprocess.Popen([sys.executable,'-c','import fcntl,sys,time; f=open(sys.argv[1],"a"); fcntl.flock(f,fcntl.LOCK_EX); print("locked",flush=True); time.sleep(30)',str(lock)],stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(),'locked')
            with self.assertRaisesRegex(build.DatabaseRebuildError,'Another writer'):self.rebuild([r])
            self.assertEqual(before,self.db.read_bytes())
        finally:proc.terminate();proc.wait();proc.stdout.close()
        issued=self.rows('persons');self.rebuild([r]);self.assertEqual(issued,self.rows('persons'))

    def test_failed_fact_write_and_missing_evidence_leave_store_intact(self):
        r=report();self.rebuild([r]);before=self.db.read_bytes()
        with mock.patch.object(facts,'compute_and_store',side_effect=facts.FactsError('failed metric')):
            with self.assertRaisesRegex(build.DatabaseRebuildError,'failed metric'):self.rebuild([r])
        self.assertEqual(before,self.db.read_bytes())
        with self.assertRaisesRegex(build.DatabaseRebuildError,'Missing cached evidence'):self.rebuild([])
        self.assertEqual(before,self.db.read_bytes())
        self.assertEqual(list(self.root.glob('.store.sqlite.*.tmp')),[])

    def test_foehr_mende_occurrences_persist_and_link_separately(self):
        r=report(names=('Alexander Föhr','Dirk-Ulrich Mende'))
        for s in r['agenda_items'][0]['xml_speakers']:
            s['speaker'].update(xml_redner_id='11005304',abgeordnetenwatch={'id':123,'match':'ext_id'})
        self.rebuild([r]);conn=store.connect(self.db)
        try:mps,lookup=build.collect_abgeordnete(conn)
        finally:conn.close()
        self.assertEqual(len(mps),2);self.assertEqual(len({m['person_id'] for m in self.rows('mps')}),2)
        markup=render.render_html(r,mp_lookup=lookup)
        for mp in mps:self.assertIn(f'../abgeordnete/{mp["id"]}.html',markup)

    def test_repeat_replay_keeps_semantic_store_and_export_generation(self):
        r=report();self.rebuild([r],keep_if_unchanged=True);before=self.db.stat().st_mtime_ns
        first=build.export_distribution_data(self.db,self.root/'exports')
        self.assertFalse(self.rebuild([r],keep_if_unchanged=True));self.assertEqual(before,self.db.stat().st_mtime_ns)
        second=build.export_distribution_data(self.db,self.root/'exports')
        self.assertEqual(first['generation'],second['generation'])
        for table in second['tables']:
            self.assertTrue(any(c['pk'] for c in table['columns']),table['name'])
            self.assertTrue(table['stable_keys'],table['name'])
            for column in table['columns']:
                if column['pk'] and column['type'] == 'TEXT':
                    self.assertTrue(column['notnull'],(table['name'],column['name']))

    def test_receipt_keys_survive_reordering_and_distinguish_same_page_speeches(self):
        r=report(names=('Ada Example','Bea Example'))
        for speech in r['agenda_items'][0]['xml_speakers']:
            speech.pop('rede_id');speech['source_page']={'page':10}
        self.rebuild([r]);conn=store.connect(self.db)
        try:
            speeches=[dict(row) for row in conn.execute('SELECT s.*,p.document_number FROM speeches s JOIN protocols p ON p.id=s.protocol_id ORDER BY s.id')]
            metric=facts.REGISTRY[0]
            row=dict(metric_id=metric['id'],metric_version=1,period_kind='week',period_key='2026-W24',wahlperiode=21,complete=1,eligible=1,publishable=1,rank=1,
                     receipts=[facts._speech_receipt(speech,index) for index,speech in enumerate(speeches)])
            facts.write_snapshot(conn,facts.snapshot_from_rows([metric],[row]))
            first={r['source_entity_id']:r['id'] for r in conn.execute('SELECT * FROM fact_sources')}
            self.assertEqual(set(first),{speech['id'] for speech in speeches})
            for index,receipt in enumerate(reversed(row['receipts'])):receipt['position']=index
            facts.write_snapshot(conn,facts.snapshot_from_rows([metric],[row]))
            second={r['source_entity_id']:r['id'] for r in conn.execute('SELECT * FROM fact_sources')}
            self.assertEqual(first,second)
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(),[])
        finally:conn.close()

    def test_person_page_collection_only_reads_persisted_assignments(self):
        r=report();self.rebuild([r]);before=self.db.read_bytes()
        conn=facts.open_readonly(self.db)
        try:
            with mock.patch.object(registry,'reconcile',side_effect=AssertionError('renderer must not reconcile')):
                mps,_=build.collect_abgeordnete(conn)
            self.assertEqual(len(mps),1)
            assignments=dict(conn.execute('SELECT id,person_id FROM mps'))
            facts.ensure_canonical(conn)
            self.assertEqual(dict(conn.execute('SELECT mp_id,canonical_id FROM mp_canonical')),assignments)
        finally:conn.close()
        self.assertEqual(before,self.db.read_bytes())

    def test_legacy_cli_requires_explicit_replay_then_builds_pages_facts_and_exports(self):
        site=self.root/'site';data=site/'data';data.mkdir(parents=True);db=data/'bundestag-pulse.sqlite'
        r=report();(data/'plenarprotokoll-21-1.json').write_text(json.dumps(r))
        with sqlite3.connect(db) as conn:
            conn.executescript('CREATE TABLE parties(id INTEGER PRIMARY KEY,name TEXT); CREATE TABLE mps(id INTEGER PRIMARY KEY,display_name TEXT); CREATE TABLE protocols(id TEXT PRIMARY KEY,document_number TEXT);')
            conn.execute("INSERT INTO protocols VALUES ('s1','21/1')")
        before=db.read_bytes();cmd=[sys.executable,str(_support.ROOT/'scripts/build_dip_pulse_site.py'),'--offline','--output-dir',str(site)]
        plain=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(plain.returncode,1);self.assertIn(store.UPGRADE_INSTRUCTION,plain.stderr);self.assertEqual(db.read_bytes(),before)
        with self.assertRaisesRegex(RuntimeError,'--offline --repersist'):build.export_distribution_data(db,site/'exports')
        upgraded=subprocess.run(cmd+['--repersist'],capture_output=True,text=True);self.assertEqual(upgraded.returncode,0,upgraded.stderr)
        with sqlite3.connect(db) as conn:
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(),[])
            person=conn.execute('SELECT person_id FROM mps').fetchone()[0]
            self.assertGreater(conn.execute('SELECT COUNT(*) FROM fact_metrics').fetchone()[0],0)
        self.assertTrue((site/'abgeordnete'/f'{person}.html').exists());self.assertTrue((data/'exports/datenstand.json').exists())

if __name__=='__main__':unittest.main()
