"""Person-registry operator contracts: staged roster ingestion, rejected
corrections, the shipped Föhr/Mende partition and the
shared writer lock on the direct persistence paths.

Kept apart from test_stable_ids.py on purpose; that file holds the A.2
identity tests."""
from __future__ import annotations
import contextlib
import io
import json
import sqlite3
import subprocess
import sys
import unittest
from unittest import mock
import _support  # noqa: F401
import build_dip_pulse_site as build
import persist_dip_pulse_store as store
import person_registry as registry
from _registry_fixture import RegistryFixture
from stable_ids import stable_key


def report(pid="s1", names=("Ada Example",), rede_ids=None):
    speakers = [
        {"rede_id": (rede_ids or {}).get(name, f"{pid}-r{index}"),
         "speaker": {"display_name": name, "xml_redner_id": str(index + 1), "fraktion": "SPD"},
         "char_count": 20, "text": "Ein geprüfter Text."}
        for index, name in enumerate(names)
    ]
    return {"protocol": {"id": pid, "dokumentnummer": f"21/{pid[-1]}", "datum": "2026-06-10"},
            "agenda_items": [{"index": 1, "heading": "Debatte", "xml_speakers": speakers}]}


class RegistryContractTests(RegistryFixture, unittest.TestCase):
    def rebuild(self, reports, **kwargs):
        entries = [{"report": r, "report_path": self.root / f'{r["protocol"]["id"]}.json'} for r in reports]
        with contextlib.redirect_stderr(io.StringIO()):
            return build.rebuild_database_from_entries(self.db, entries, **kwargs)

    def rows(self, table):
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY 1")]

    @contextlib.contextmanager
    def held_lock(self):
        lock = self.db.with_suffix(".sqlite.writer.lock")
        proc = subprocess.Popen(
            [sys.executable, "-c", 'import fcntl,sys,time; f=open(sys.argv[1],"a"); fcntl.flock(f,fcntl.LOCK_EX); print("locked",flush=True); time.sleep(30)', str(lock)],
            stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(), "locked")
            yield
        finally:
            proc.terminate()
            proc.wait()
            proc.stdout.close()

    # Value: protects=online roster ingestion inside the staged rebuild binds roster and speaker to one stable person; fails_when=roster_ingest is skipped, bound under another key, or a failure replaces the store; why_new=no test passes roster_ingest or calls ingest_mdb_roster; seam=none
    def test_staged_roster_ingestion_binds_with_speaker_and_failure_keeps_store(self):
        roster = [
            {"id": "dip-7", "titel": "Ada Example", "vorname": "Ada", "nachname": "Example",
             "fraktion": ["SPD"], "funktion": ["MdB"], "wahlperiode": 21},
            {"id": "dip-8", "titel": "Bea Minister", "vorname": "Bea", "nachname": "Minister",
             "fraktion": ["SPD"], "funktion": ["Bundesminister"], "wahlperiode": 21},
        ]
        client = mock.Mock()
        client.list_all.return_value = roster
        stats = []
        def ingest(staged):
            stats.append(build.ingest_mdb_roster(client, staged, wahlperiode=21))
        r = report()
        self.rebuild([r], preserve_roster=False, roster_ingest=ingest)
        self.assertEqual((stats[0]["fetched"], stats[0]["mdb"]), (2, 1))
        bindings = {b["id"]: b["person_id"] for b in self.rows("person_bindings")}
        roster_binding = stable_key("roster", "dip-7")
        self.assertIn(roster_binding, bindings)
        self.assertNotIn(stable_key("roster", "dip-8"), bindings)
        speech_binding = stable_key("speech", "s1", "s1-r0")
        self.assertEqual(bindings[roster_binding], bindings[speech_binding])
        self.assertEqual(len(self.rows("mps")), 2)
        self.assertEqual(len({m["person_id"] for m in self.rows("mps")}), 1)
        # A name-based guess moves the current person but retires no key.
        self.assertEqual(len(self.rows("person_aliases")), 0)
        persons = self.rows("persons")
        self.rebuild([r], preserve_roster=False, roster_ingest=ingest)
        self.assertEqual(self.rows("persons"), persons)
        before = self.db.read_bytes()
        with self.assertRaisesRegex(build.DatabaseRebuildError, "Abgeordnetenkader could not be fetched: roster down"):
            self.rebuild([r], preserve_roster=False, roster_ingest=mock.Mock(side_effect=RuntimeError("roster down")))
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual(list(self.root.glob(".store.sqlite.*.tmp")), [])

    # Value: protects=a member the refreshed roster no longer lists keeps one page with biography and speeches; fails_when=a stale roster record takes part in no match, or collect_abgeordnete skips its evidence once it shares a current person; why_new=staged roster tests always list the same members; seam=none
    def test_member_dropped_from_roster_keeps_one_page_with_biography_and_speeches(self):
        ada = {"id": "dip-7", "titel": "Ada Example", "vorname": "Ada", "nachname": "Example",
               "fraktion": ["SPD"], "funktion": ["MdB"], "wahlperiode": 21}
        bea = {"id": "dip-9", "titel": "Bea Other", "vorname": "Bea", "nachname": "Other",
               "fraktion": ["SPD"], "funktion": ["MdB"], "wahlperiode": 21}
        def ingest_with(persons):
            client = mock.Mock()
            client.list_all.return_value = persons
            return lambda staged: build.ingest_mdb_roster(client, staged, wahlperiode=21)
        r = report()
        self.rebuild([r], preserve_roster=False, roster_ingest=ingest_with([ada, bea]))
        speech = stable_key("speech", "s1", "s1-r0")
        person = {b["id"]: b["person_id"] for b in self.rows("person_bindings")}[speech]
        self.rebuild([r], preserve_roster=False, roster_ingest=ingest_with([bea]))
        bindings = {b["id"]: b["person_id"] for b in self.rows("person_bindings")}
        self.assertEqual(bindings[speech], person)
        self.assertEqual(bindings[stable_key("roster", "dip-7")], person)
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            mps, lookup = build.collect_abgeordnete(conn)
        adas = [mp for mp in mps if mp["name"] == "Ada Example"]
        self.assertEqual(len(adas), 1)
        self.assertEqual((adas[0]["id"], adas[0]["speech_count"], adas[0]["wahlperioden"]), (person, 1, [21]))
        self.assertEqual(lookup["dip:dip-7"], person)

    # Value: protects=malformed or unresolvable corrections abort the rebuild before replacement; fails_when=a validation guard is dropped so a bad file is applied or partially applied; why_new=only unknown merge persons were tested; seam=none
    def test_invalid_corrections_abort_without_replacing_store(self):
        r = report(names=("Ada Example", "Bea Example"))
        self.rebuild([r])
        people = [p["id"] for p in self.rows("persons")]
        records = [m["id"] for m in self.rows("mps")]
        first_speech = stable_key("speech", "s1", "s1-r0")
        cases = [
            ("wrong version", {"version": 2}, "version 1 object"),
            ("field not an array", {"merges": {}}, "merges must be an array"),
            ("missing required field", {"partitions": [{"labels": {"a": "b"}}]}, "requires xml_redner_id"),
            ("empty partition labels", {"partitions": [{"xml_redner_id": "9", "labels": {}}]}, "nonempty name-to-owner"),
            # Records placed on another person wait for their redesign (TODOS.md).
            ("assignments disabled", {"assignments": [{"occurrence_id": first_speech, "person_id": people[0]}]}, "assignments are disabled"),
            ("splits disabled", {"splits": [{"person_id": people[0], "retain_records": [records[0]], "new_records": [records[1]]}]}, "splits are disabled"),
            ("survivor outside the merge", {"merges": [{"persons": [people[0]], "survivor": people[1]}]}, "not a member"),
            ("partition occurrences not an object", {"partitions": [{"xml_redner_id": "9", "labels": {"a": "b"}, "occurrences": ["x"]}]}, "occurrences must be an object"),
            ("merge persons not an array", {"merges": [{"persons": "abc"}]}, "merge persons must be a nonempty array"),
            ("redner id not a string", {"partitions": [{"xml_redner_id": 11005304, "labels": {"a": "b"}}]}, "xml_redner_id must be a nonempty string"),
            # Value: protects=every nested corrections field is type-checked and a bad file aborts before any write; fails_when=any text()/texts() guard is dropped; why_new=only top-level shapes and a few nested ones were tabled; seam=none
            ("occurrence entry not an object", {"partitions": [{"xml_redner_id": "9", "labels": {"a": "b"}, "occurrences": {"k": ["x"]}}]}, "partition occurrence 'k' must be an object"),
            ("occurrence without display_name", {"partitions": [{"xml_redner_id": "9", "labels": {"a": "b"}, "occurrences": {"k": {}}}]}, "display_name of partition occurrence 'k' must be a nonempty string"),
            ("profile_owner not a string", {"partitions": [{"xml_redner_id": "9", "labels": {"a": "b"}, "profile_owner": 5}]}, "partition profile_owner must be a nonempty string"),
            ("partition owner not a string", {"partitions": [{"xml_redner_id": "9", "labels": {"a": 5}}]}, "partition owner of 'a' must be a nonempty string"),
            ("merge survivor not a string", {"merges": [{"persons": [people[0]], "survivor": 5}]}, "merge survivor must be a nonempty string"),
            ("merge person not a string", {"merges": [{"persons": [5]}]}, "merge persons must be a nonempty string"),
            # Value: protects=a partition the consumers cannot read (null or [] occurrences, a profile owner outside its labels, a Redner-ID partitioned twice, one printed name for two owners) aborts the rebuild instead of crashing later or being silently ignored; fails_when=the loader accepts the shape and corrected_speaker/partition_identity misread it; why_new=only well-typed partitions were tabled; seam=none
            ("null occurrences", {"partitions": [{"xml_redner_id": "9", "labels": {"a": "b"}, "occurrences": None}]}, "occurrences must be an object"),
            ("empty-array occurrences", {"partitions": [{"xml_redner_id": "9", "labels": {"a": "b"}, "occurrences": []}]}, "occurrences must be an object"),
            ("profile_owner outside labels", {"partitions": [{"xml_redner_id": "9", "labels": {"a": "b"}, "profile_owner": "c"}]}, "profile_owner 'c' is not one of its label owners"),
            ("redner id partitioned twice", {"partitions": [{"xml_redner_id": "9", "labels": {"a": "b"}}, {"xml_redner_id": "9", "labels": {"c": "d"}}]}, "Redner-ID 9 is partitioned twice"),
            ("one name for two owners", {"partitions": [{"xml_redner_id": "9", "labels": {"Ada Example": "ada-a", "Dr. Ada Example": "ada-b"}}]}, "labels for 'ada example' name two owners"),
        ]
        before = self.db.read_bytes()
        for label, data, diagnostic in cases:
            with self.subTest(label), self.correction_file(data):
                with self.assertRaisesRegex(build.DatabaseRebuildError, diagnostic):
                    self.rebuild([r])
                self.assertEqual(before, self.db.read_bytes())

    # Value: protects=a missing or unparseable corrections file aborts the rebuild with a registry error before any write; fails_when=the loader treats an unreadable file as empty or lets the OSError/JSON error escape unwrapped; why_new=the corrections table only varied well-formed JSON; seam=none
    def test_an_unreadable_corrections_file_aborts_without_replacing_store(self):
        r = report()
        self.rebuild([r])
        before = self.db.read_bytes()
        broken = self.root / "broken.json"
        broken.write_text("{not json")
        for label, path in (("missing file", self.root / "absent.json"), ("invalid JSON", broken)):
            with self.subTest(label), mock.patch.object(registry, "CORRECTIONS_PATH", path):
                with self.assertRaisesRegex(build.DatabaseRebuildError, "Unreadable person corrections"):
                    self.rebuild([r])
                self.assertEqual(before, self.db.read_bytes())

    # Value: protects=the shipped Föhr/Mende partition applies reviewed occurrences and rejects unreviewed names; fails_when=reviewed rename is ignored or an unlabelled shared-ID name is silently persisted; why_new=existing test uses clean names and fake protocol ids; seam=none
    def test_shipped_partition_renames_reviewed_occurrence_and_rejects_unreviewed_name(self):
        # 5570/ID2010305900 is a reviewed occurrence printed as Alexander Föhr.
        reviewed = report("5570", names=("Garbled Name",), rede_ids={"Garbled Name": "ID2010305900"})
        reviewed["agenda_items"][0]["xml_speakers"][0]["speaker"]["xml_redner_id"] = "11005304"
        self.rebuild([reviewed])
        self.assertEqual([m["display_name"] for m in self.rows("mps")], ["Alexander Föhr"])
        self.assertEqual([r["partition"] for r in self.rows("person_records")], ["foehr"])
        unreviewed = report("5571", names=("Garbled Name",))
        unreviewed["agenda_items"][0]["xml_speakers"][0]["speaker"]["xml_redner_id"] = "11005304"
        before = self.db.read_bytes()
        with self.assertRaisesRegex(build.DatabaseRebuildError, "Shared Redner-ID 11005304"):
            self.rebuild([reviewed, unreviewed])
        self.assertEqual(before, self.db.read_bytes())

    # Value: protects=standalone fact computation honours the writer lock, and the standalone persist command refuses to write a single report outside the staged rebuild; fails_when=run_facts_engine skips the lock, or persist_dip_pulse_store main() writes into the store again; why_new=only rebuild_database_from_entries was tested under lock contention, and the removed single-report path half-updated stores; seam=none
    def test_facts_share_the_writer_lock_and_single_report_persist_is_refused(self):
        r = report()
        path = self.root / "report.json"
        path.write_text(json.dumps(r))
        with self.held_lock():
            with self.assertRaisesRegex(registry.RegistryError, "Another writer"):
                build.run_facts_engine(self.db, [{"report": r, "report_path": path}], None)
        stderr = io.StringIO()
        with mock.patch.object(sys, "argv", ["persist_dip_pulse_store.py", str(path)]), contextlib.redirect_stderr(stderr):
            self.assertEqual(store.main(), 2)
        self.assertIn("--offline --repersist", stderr.getvalue())
        self.assertFalse(self.db.exists())

    # Value: protects=a DIP roster row without a person id binds no occurrence, so two such rows never share one roster binding key; fails_when=roster_occurrence_id hashes a missing id, giving every id-less row the key of None; why_new=every roster fixture carried a DIP id; seam=none
    def test_a_roster_row_without_a_dip_id_binds_no_occurrence(self):
        from stable_ids import roster_occurrence_id
        self.assertIsNone(roster_occurrence_id(None))
        self.assertIsNone(roster_occurrence_id(""))
        conn = self.open_store()
        now = store.utc_now()
        store.persist_sampled_people(conn, {"sampled_people": [{"titel": "Ada Example"}, {"titel": "Bea Example"}]}, now)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM person_bindings").fetchone()[0], 0)

    # Value: protects=the dossier page prints the reviewed name of a shared-Redner-ID occurrence, not the garbled printed one; fails_when=render_html stops applying registry.corrected_speaker so the page shows a name the store has corrected; why_new=the shipped-partition test only checks the store rows; seam=none
    def test_render_prints_the_reviewed_name_of_a_partitioned_occurrence(self):
        import render_dip_pulse_html as render
        reviewed = report("5570", names=("Garbled Name",), rede_ids={"Garbled Name": "ID2010305900"})
        reviewed["agenda_items"][0]["xml_speakers"][0]["speaker"]["xml_redner_id"] = "11005304"
        markup = render.render_html(reviewed)
        self.assertIn("Alexander Föhr", markup)
        self.assertNotIn("Garbled Name", markup)

    # Value: protects=the cached dossier JSON keeps the printed speaker after its page was rendered, so a second write (the online build writes every dossier twice) never turns the reviewed name and blanked profile into source evidence; fails_when=render_html writes the corrected speaker or occurrence_id back into the report it was given; why_new=the render test only checked the markup; seam=none
    def test_writing_a_dossier_twice_keeps_the_printed_speaker_in_its_json(self):
        reviewed = report("5560", names=("Garbled Name",), rede_ids={"Garbled Name": "ID209407600"})
        speaker = reviewed["agenda_items"][0]["xml_speakers"][0]["speaker"]
        speaker.update(xml_redner_id="11005304", abgeordnetenwatch={"id": 5, "match": "ext_id", "url": "https://aw.example/5"})
        pristine = json.dumps(reviewed, sort_keys=True)
        for folder in ("data", "protocols"):
            (self.root / folder).mkdir(exist_ok=True)
        first = build.write_report_files(reviewed, self.root, {})
        written = first["report_path"].read_text(encoding="utf-8")
        self.assertIn("Dirk-Ulrich Mende", first["page_path"].read_text(encoding="utf-8"))  # the page shows the review
        build.write_report_files(reviewed, self.root, {})
        self.assertEqual(json.dumps(reviewed, sort_keys=True), pristine)
        self.assertEqual(first["report_path"].read_text(encoding="utf-8"), written)
        self.assertIn("Garbled Name", written)
        self.assertNotIn("occurrence_id", written)

    # Value: protects=a rebuild issues the same persons to the same names whatever order the cached reports arrive in; fails_when=the newest-first sort of the entries is dropped so name-only persons take p-NNNNNN ordinals in input order; why_new=the reordering tests use Redner-ID persons whose keys are content hashes and never touch ordinals; seam=none
    def test_a_rebuild_issues_the_same_persons_whatever_the_report_order(self):
        def named(pid, name):
            r = report(pid, names=(name,))
            del r["agenda_items"][0]["xml_speakers"][0]["speaker"]["xml_redner_id"]
            r["protocol"]["datum"] = f"2026-06-1{pid[-1]}"
            return r
        reports = [named("s1", "Ada Example"), named("s2", "Bea Example"), named("s3", "Cy Example")]
        issued = []
        for order in (reports, list(reversed(reports))):
            self.db = self.root / f"order-{len(issued)}.sqlite"
            self.rebuild(order)
            issued.append({m["display_name"]: m["person_id"] for m in self.rows("mps")})
        self.assertEqual(issued[0], issued[1])

    # Value: protects=records of two different partitions never merge into one person, by shared id or by name+party; fails_when=the partition-union guard in match_rows is removed; why_new=tests cover partition naming and rebuilds, never the union step; seam=none
    def test_match_rows_never_unions_records_of_different_partitions(self):
        def row(rid, partition, **fields):
            return {"id": rid, "display_name": fields.pop("display_name", "Alexander Föhr"), "party": "CDU/CSU",
                    "partition": partition, "aw_politician_id": None, "aw_match": None,
                    "dip_person_id": None, "xml_redner_id": None, **fields}
        shared = {"aw_politician_id": 5, "aw_match": "ext_id", "dip_person_id": "dip-1"}
        with self.subTest("shared trusted aw and dip id"):
            components, totals = registry.match_rows([
                row("foehr", "foehr", xml_redner_id="11005304", **shared),
                row("mende", "mende", xml_redner_id="11005304", display_name="Erik Mende", **shared)])
            self.assertEqual(sorted(map(len, components.values())), [1, 1])
            self.assertEqual(totals["ext_id"], 0)
        with self.subTest("same name and party on opposite sides"):
            components, totals = registry.match_rows([
                row("speaker", "foehr", xml_redner_id="11005304"),
                row("roster", "mende", dip_person_id="dip-9")])
            self.assertEqual(sorted(map(len, components.values())), [1, 1])
            self.assertEqual(totals["unique_name"], 0)
        with self.subTest("control: one partition still joins by shared id"):
            components, totals = registry.match_rows([
                row("a", "foehr", xml_redner_id="11005304", **shared), row("b", "foehr", **shared)])
            self.assertEqual(sorted(map(len, components.values())), [2])
            self.assertEqual(totals["ext_id"], 1)

    # Value: protects=a build-store backup with an incomplete registry, bad person key, unreadable evidence or FK violation aborts replay untouched; fails_when=a validate or copy_previous guard is dropped; why_new=only corrections-file errors were tested, never a damaged previous store; seam=none
    def test_damaged_previous_registry_aborts_replay_and_leaves_store_unchanged(self):
        r = report()
        self.rebuild([r])
        pristine = self.db.read_bytes()
        cases = [
            ("registry table missing", "DROP TABLE person_bindings", "Incomplete person registry"),
            ("person key not URL-safe", "UPDATE persons SET id = 'bad key/1'", "Invalid registry person key"),
            ("evidence is not an object", "UPDATE person_records SET evidence_json = '[]'", "Unreadable registry evidence"),
            ("record points at unknown person", "UPDATE person_records SET person_id = 'ghost'", "foreign-key violations"),
            ("every registry table missing", "DROP TABLE person_bindings; DROP TABLE person_records; DROP TABLE person_aliases; DROP TABLE persons", "Incomplete person registry"),
            ("registry from an unreleased A.2 draft", "ALTER TABLE person_records RENAME COLUMN home_person_id TO draft_person_id", "unreleased A.2 draft"),
        ]
        for label, damage, diagnostic in cases:
            with self.subTest(label):
                self.db.write_bytes(pristine)
                with contextlib.closing(sqlite3.connect(self.db)) as conn:
                    conn.execute("PRAGMA foreign_keys = OFF")
                    conn.executescript(damage)
                    conn.commit()
                damaged = self.db.read_bytes()
                with self.assertRaisesRegex(build.DatabaseRebuildError, diagnostic):
                    self.rebuild([r])
                self.assertEqual(damaged, self.db.read_bytes())
                self.assertEqual(list(self.root.glob(".store.sqlite.*.tmp")), [])
        # Value: protects=initialize refuses a store whose registry tables vanished instead of minting an empty registry; fails_when=require_current_schema skips the registry-tables check; why_new=copy_previous guards replay only, not a direct initialize of the build store; seam=none
        with self.subTest("direct initialize without registry tables"):
            self.db.write_bytes(pristine)
            with contextlib.closing(sqlite3.connect(self.db)) as conn:
                conn.execute("PRAGMA foreign_keys = OFF")
                conn.executescript("; ".join(f"DROP TABLE {table}" for table in registry.REGISTRY_TABLES))
                conn.commit()
            with contextlib.closing(store.connect(self.db)) as conn:
                with self.assertRaisesRegex(registry.RegistryError, "Incomplete person registry"):
                    store.initialize(conn)
                names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertFalse(names & set(registry.REGISTRY_TABLES))


    # Value: protects=a source that now names a different Redner-ID or DIP id moves the occurrence to that identity's record while enrichment keeps the pin; fails_when=bind keeps the bound record on a hard-ID conflict (Berta's data lands on Anna) or moves it on a name/party change; why_new=only partition moves were tested; seam=none
    def test_a_changed_hard_id_rebinds_the_occurrence_but_enrichment_keeps_it(self):
        conn = self.open_store()
        anna = self.up(conn, "occ-1", "xml:1", "Anna Alt", xml="1")
        self.assertEqual(self.up(conn, "occ-1", "xml:1", "Anna Alt-Meyer", xml="1", party="SPD"), anna)
        berta = self.up(conn, "occ-1", "xml:2", "Berta Neu", xml="2")
        self.assertNotEqual(berta, anna)
        persons = self.person_of_records(conn)
        self.assertNotEqual(persons[anna], persons[berta])
        self.assertEqual(conn.execute("SELECT record_id FROM person_bindings WHERE id='occ-1'").fetchone()[0], berta)
        row = conn.execute("SELECT xml_redner_id, identity_key FROM mps WHERE id=?", (anna,)).fetchone()
        self.assertEqual(tuple(row), ("1", "xml:1"))  # the earlier record is kept, not overwritten

    # Value: protects=an aw id the source stopped supplying cannot keep linking records in a later build; fails_when=bind overlays new evidence onto the old build's evidence so a removed id survives; why_new=no test re-persisted a record with less evidence than the carried registry holds; seam=none
    def test_a_removed_aw_id_does_not_link_records_in_the_next_build(self):
        first = self.open_store("first.sqlite")
        self.up(first, "occ-s", "xml:7", "Anna Sprecher", xml="7", aw=123, match="ext_id")
        registry.reconcile(first)
        second = self.next_build(first)
        self.up(second, "occ-s", "xml:7", "Anna Sprecher", xml="7")
        self.up(second, "roster:9", "dip:9", "Berta Roster", dip="9", aw=123, match="ext_id", mdb=True)
        registry.reconcile(second)
        self.assertEqual(len(set(self.person_of_records(second).values())), 2)

    # Value: protects=name-based guess merges are recomputed per reconcile, leave no alias and give the same persons whatever order records arrived in; fails_when=a unique-name merge is written as an alias so a later namesake cannot undo it; why_new=tests only built each store once, never an incremental versus fresh replay; seam=none
    def test_name_guess_merges_leave_no_alias_and_do_not_depend_on_arrival_order(self):
        def add_speaker_and_roster(conn):
            self.up(conn, "occ-s", "xml:10", "Max Muster", xml="10", party="CDU/CSU")
            self.up(conn, "roster:5", "dip:5", "Max Muster", dip="5", mdb=True, party="CDU/CSU")

        def add_namesake(conn):
            self.up(conn, "roster:6", "dip:6", "Max Muster", dip="6", mdb=True, party="CDU/CSU")

        first = self.open_store("first.sqlite")
        add_speaker_and_roster(first)
        registry.reconcile(first)
        self.assertEqual(len(set(self.person_of_records(first).values())), 1)
        self.assertEqual(first.execute("SELECT COUNT(*) FROM person_aliases").fetchone()[0], 0)
        second = self.next_build(first)
        add_speaker_and_roster(second)
        add_namesake(second)
        registry.reconcile(second)
        fresh = self.open_store("fresh.sqlite")
        add_speaker_and_roster(fresh)
        add_namesake(fresh)
        registry.reconcile(fresh)
        self.assertEqual(self.grouping(second), self.grouping(fresh))
        self.assertEqual(len(self.grouping(second)), 3)

    # Value: protects=a partition correction added after a store exists moves the occurrences to new persons, keeps the old record and person, and a further replay changes nothing; fails_when=bind keeps the pre-partition binding or replay mints new keys each time; why_new=the shipped Foehr/Mende test only built from an empty store; seam=none
    def test_a_partition_added_to_an_existing_store_splits_it_and_replays_stably(self):
        r = report(names=("Alexander Föhr", "Dirk-Ulrich Mende"))
        for speech in r["agenda_items"][0]["xml_speakers"]:
            speech["speaker"]["xml_redner_id"] = "11005304"
        with self.correction_file({}):  # the shipped file already partitions this Redner-ID
            self.rebuild([r])
        before = self.rows("persons")
        self.assertEqual(len(before), 1)
        partition = {"partitions": [{"xml_redner_id": "11005304", "labels": {"Alexander Föhr": "foehr", "Dirk-Ulrich Mende": "mende"}}]}
        with self.correction_file(partition):
            self.rebuild([r])
            persons = self.rows("persons")
            bound = {b["id"]: b["person_id"] for b in self.rows("person_bindings")}
            speeches = [stable_key("speech", "s1", "s1-r0"), stable_key("speech", "s1", "s1-r1")]
            self.assertNotEqual(bound[speeches[0]], bound[speeches[1]])
            self.assertEqual(len(persons), 3)  # the old person stays issued
            self.assertEqual(len(self.rows("person_records")), 3)
            self.rebuild([r])
            self.assertEqual(self.rows("persons"), persons)

    # Value: protects=only the --offline --repersist replay upgrades an old-schema store; fails_when=an online rebuild accepts the schema 2 store and silently mints a fresh registry; why_new=only the offline render and the export were gated; seam=none
    def test_only_the_upgrade_rebuild_accepts_an_old_schema_store(self):
        with sqlite3.connect(self.db) as conn:
            conn.executescript("CREATE TABLE parties(id INTEGER PRIMARY KEY,name TEXT); CREATE TABLE mps(id INTEGER PRIMARY KEY,display_name TEXT); CREATE TABLE protocols(id TEXT PRIMARY KEY,document_number TEXT);")
            conn.execute("INSERT INTO protocols VALUES ('s1','21/1')")
        before = self.db.read_bytes()
        with self.assertRaisesRegex(build.DatabaseRebuildError, "--offline --repersist"):
            self.rebuild([report()])
        self.assertEqual(self.db.read_bytes(), before)
        self.assertTrue(self.rebuild([report()], upgrade=True))
        self.assertEqual(len(self.rows("persons")), 1)

    # Value: protects=a merged XML record's combined Redner-ID ("11005304 999990074") still meets its partition and reviewed name; fails_when=corrected_speaker or partition_identity compares the raw attribute instead of its first id; why_new=partition tests used single ids only; seam=none
    def test_a_combined_redner_id_meets_its_partition(self):
        combined = "11005304 999990074"
        speaker = registry.corrected_speaker({"display_name": "Dirk-UlrichAlexander Mende Föhr", "xml_redner_id": combined}, 5560, "ID209407600")
        self.assertEqual(speaker["display_name"], "Dirk-Ulrich Mende")
        evidence = {"display_name": "Dirk-Ulrich Mende", "xml_redner_id": combined}
        self.assertEqual(registry.partition_identity("xml:11005304", evidence), "partition:11005304:mende")
        self.assertEqual(evidence["partition"], "mende")

    # Value: protects=the Foehr/Mende shared ext-ID profile belongs to the profile owner only; fails_when=corrected_speaker or bind stops blanking the shared profile so the other partition gets aw id and profile link; why_new=the shipped test asserted two persons and links, which the partition guard alone already guarantees; seam=none
    def test_the_shared_profile_stays_with_its_owner_only(self):
        r = report(names=("Alexander Föhr", "Dirk-Ulrich Mende"))
        for speech in r["agenda_items"][0]["xml_speakers"]:
            speech["speaker"].update(xml_redner_id="11005304", abgeordnetenwatch={"id": 123, "match": "ext_id", "url": "https://example.test/foehr"})
        self.rebuild([r])
        rows = {m["display_name"]: m for m in self.rows("mps")}
        self.assertEqual(rows["Alexander Föhr"]["aw_politician_id"], 123)
        self.assertIsNone(rows["Dirk-Ulrich Mende"]["aw_politician_id"])
        self.assertIsNone(rows["Dirk-Ulrich Mende"]["profile_url"])
        evidence = {rec["partition"]: json.loads(rec["evidence_json"]) for rec in self.rows("person_records")}
        self.assertEqual(evidence["mende"]["aw_match"], "partitioned")
        self.assertTrue(evidence["mende"]["profile_blocked"])
        self.assertEqual(evidence["foehr"]["aw_politician_id"], 123)
        # Value: protects=a non-owner partition record never holds the shared aw id or profile even when corrected_speaker is bypassed; fails_when=bind infers profile_blocked from a missing aw id instead of profile_owner; why_new=corrected_speaker blanks the id first, so the report path never reaches bind with it; seam=none
        conn = self.open_store("direct.sqlite")
        store.upsert_mp(conn, now=store.utc_now(), party_id=None, display_name="Dirk-Ulrich Mende", identity_key="xml:11005304", xml_redner_id="11005304",
                        aw_politician_id=123, aw_match="ext_id", profile_url="https://example.test/foehr", occurrence_id="occ-mende")
        mende = conn.execute("SELECT aw_politician_id, profile_url FROM mps").fetchone()
        self.assertEqual(tuple(mende), (None, None))
        recorded = json.loads(conn.execute("SELECT evidence_json FROM person_records").fetchone()[0])
        self.assertTrue(recorded["profile_blocked"])
        self.assertIsNone(recorded.get("aw_politician_id"))
        self.assertIsNone(recorded.get("profile_url"))
        # Value: protects=a partition without profile_owner leaves no record that links the contaminated shared profile; fails_when=a missing profile_owner is read as no restriction, in corrected_speaker or in the record's profile_blocked; why_new=only the shipped file, which names an owner, was tested; seam=none
        self.db = self.root / "ownerless.sqlite"
        ownerless = {"partitions": [{"xml_redner_id": "11005304", "labels": {"Alexander Föhr": "foehr", "Dirk-Ulrich Mende": "mende"}}]}
        with self.subTest("partition without profile_owner"), self.correction_file(ownerless):
            self.rebuild([r])
            self.assertEqual(len(self.rows("person_records")), 2)
            for mp in self.rows("mps"):
                self.assertIsNone(mp["aw_politician_id"], mp["display_name"])
                self.assertIsNone(mp["profile_url"], mp["display_name"])
            for rec in self.rows("person_records"):
                evidence = json.loads(rec["evidence_json"])
                self.assertTrue(evidence["profile_blocked"], rec["partition"])
                self.assertIsNone(evidence.get("aw_politician_id"), rec["partition"])
                self.assertIsNone(evidence.get("profile_url"), rec["partition"])

    # Value: protects=a person key may not be a reserved page name or differ only by case from an issued key; fails_when=allocate or validate accepts index or Foehr beside foehr so one page file overwrites another; why_new=the key regex was only tested for URL-unsafe characters; seam=none
    def test_reserved_and_case_colliding_person_keys_are_refused(self):
        conn = self.open_store()
        registry.allocate(conn, "foehr")
        for key, diagnostic in (("index", "reserved page name"), ("Foehr", "differs only by case")):
            with self.subTest(key), self.assertRaisesRegex(registry.RegistryError, diagnostic):
                registry.allocate(conn, key)
        conn.execute("INSERT INTO persons VALUES ('Foehr', 99)")
        with self.assertRaisesRegex(registry.RegistryError, "differ only by case"):
            registry.validate(conn)

    # Value: protects=a replay sweeps temp store copies a crash left behind and the replacement keeps the store's file mode; fails_when=stale .tmp copies pile up beside published data or the swap silently makes the store 0600; why_new=tests checked only that no temp file is left by the run itself; seam=none
    def test_replay_sweeps_stale_temp_copies_and_keeps_the_store_mode(self):
        self.rebuild([report()])
        self.assertEqual(self.db.stat().st_mode & 0o777, 0o644)  # a first store is readable by the site's server
        self.db.chmod(0o640)
        stale = self.root / ".store.sqlite.crashed.tmp"
        stale.write_bytes(b"half-written store with speech text")
        self.rebuild([report(), report(pid="s2")])
        self.assertFalse(stale.exists())
        self.assertEqual(self.db.stat().st_mode & 0o777, 0o640)

    # Value: protects=person pages are only collected for filename-safe person keys even if a store was edited after validation; fails_when=collect_abgeordnete writes a key like a/b into a page path; why_new=key validation only ran at rebuild, never on the offline page-collection path; seam=none
    def test_page_collection_refuses_an_unsafe_person_key(self):
        self.rebuild([report()])
        with contextlib.closing(sqlite3.connect(self.db)) as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            old = conn.execute("SELECT id FROM persons").fetchone()[0]
            for table, column in (("persons", "id"), ("person_records", "person_id"), ("person_bindings", "person_id"), ("mps", "person_id")):
                conn.execute(f"UPDATE {table} SET {column} = 'a/b' WHERE {column} = ?", (old,))
            conn.commit()
        with contextlib.closing(store.connect(self.db)) as conn:
            with self.assertRaisesRegex(registry.RegistryError, "Invalid person key"):
                build.collect_abgeordnete(conn)


    # Value: protects=a name guess about one record moves its whole person, so a reviewed merge is never torn apart; fails_when=the guess pass assigns single records so the merged partner is left on a different person than the record it was merged with; why_new=guesses were only tested on single-record persons; seam=none
    def test_a_guess_cannot_tear_apart_a_reviewed_merge(self):
        conn = self.open_store()
        self.up(conn, "occ-c", "xml:3", "Anna Alpha", xml="3", party="SPD")
        a = self.up(conn, "roster:1", "dip:1", "Anna Alpha", dip="1", mdb=True, party="SPD")
        b = self.up(conn, "roster:2", "dip:2", "Bea Beta", dip="2", mdb=True, party="SPD")
        persons = self.person_of_records(conn)
        with self.correction_file({"merges": [{"persons": [persons[a], persons[b]]}]}):
            registry.reconcile(conn)
        after = self.person_of_records(conn)
        self.assertEqual(after[a], after[b])

    # Value: protects=the key of a person a name guess moved elsewhere still resolves to the survivor's page; fails_when=collect_abgeordnete lists only durable aliases so the loser's published page is deleted without a redirect; why_new=page tests only covered hard merges with an alias row; seam=none
    def test_a_guess_merged_key_keeps_a_redirect_page(self):
        conn = self.open_store()
        self.up(conn, "occ-s", "xml:10", "Max Muster", xml="10", party="CDU/CSU")
        self.up(conn, "roster:5", "dip:5", "Max Muster", dip="5", mdb=True, party="CDU/CSU")
        registry.reconcile(conn)
        conn.commit()
        homes = {row[0] for row in conn.execute("SELECT home_person_id FROM person_records")}
        mps, _ = build.collect_abgeordnete(conn)
        (mp,) = [m for m in mps if m["has_page"]]
        (loser,) = homes - {mp["id"]}
        self.assertIn(loser, mp["aliases"])
        # Value: protects=the page key a name guess keeps is the earlier issued person key, so the public URL does not depend on which record the guess names first; fails_when=the guess pass elects the later issued key (min ordinal becomes max); why_new=the test checked only that the other key redirects, not which key is the page; seam=none
        ordinals = dict(conn.execute("SELECT id, ordinal FROM persons"))
        self.assertEqual(mp["id"], min(homes, key=ordinals.get))
        for folder in ("data", "protocols"):
            (self.root / folder).mkdir(exist_ok=True)
        build.write_abgeordnete_pages(self.root, mps)
        self.assertIn(mp["id"], (self.root / "abgeordnete" / f"{loser}.html").read_text(encoding="utf-8"))

    # Value: protects=a guess-merged pair that is not re-touched in the next build is split again when a namesake arrives; fails_when=reconcile stops resetting every record to its durable home before recomputing guesses; why_new=the arrival-order test re-persisted every record in the second build; seam=none
    def test_a_carried_guess_that_stops_holding_is_undone_for_untouched_records(self):
        first = self.open_store("first.sqlite")
        self.up(first, "occ-s", "xml:10", "Max Muster", xml="10", party="CDU/CSU")
        self.up(first, "roster:5", "dip:5", "Max Muster", dip="5", mdb=True, party="CDU/CSU")
        registry.reconcile(first)
        self.assertEqual(len(self.grouping(first)), 1)
        second = self.next_build(first)
        self.up(second, "roster:6", "dip:6", "Max Muster", dip="6", mdb=True, party="CDU/CSU")
        registry.reconcile(second)
        self.assertEqual(len(self.grouping(second)), 3)

    # Value: protects=a different DIP person id for the same occurrence rebinds it like a different Redner-ID; fails_when=_hard_id_conflict drops the dip_person_id pair so a roster occurrence keeps the old record; why_new=the rebind test only drove the Redner-ID pair; seam=none
    def test_a_changed_dip_id_rebinds_the_occurrence(self):
        conn = self.open_store()
        anna = self.up(conn, "occ-1", "dip:1", "Anna", dip="1", mdb=True)
        berta = self.up(conn, "occ-1", "dip:2", "Berta", dip="2", mdb=True)
        self.assertNotEqual(anna, berta)
        self.assertEqual(conn.execute("SELECT record_id FROM person_bindings WHERE id='occ-1'").fetchone()[0], berta)

    # Value: protects=an alias key that is not filename-safe is refused before a redirect page is written; fails_when=the unsafe-key guard stops covering aliases; why_new=the unsafe-key test only renamed a page person; seam=none
    def test_page_collection_refuses_an_unsafe_alias_key(self):
        self.rebuild([report()])
        with contextlib.closing(sqlite3.connect(self.db)) as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            person = conn.execute("SELECT id FROM persons").fetchone()[0]
            conn.execute("INSERT INTO persons VALUES ('a/b', 99)")
            conn.execute("INSERT INTO person_aliases VALUES ('a/b', ?)", (person,))
            conn.commit()
        with contextlib.closing(store.connect(self.db)) as conn:
            with self.assertRaisesRegex(registry.RegistryError, "Invalid person key"):
                build.collect_abgeordnete(conn)
        # Value: protects=collect_abgeordnete never writes index.html as a person, folds case collisions and lets a redirect overwrite no live page; fails_when=the reserved-name, casefold or page_ids guard is removed; why_new=only an unsafe-character key was tested; seam=none
        def edited(damage, names=("Ada Example",)):
            self.db.unlink()
            self.rebuild([report(names=names)])
            with contextlib.closing(sqlite3.connect(self.db)) as conn:
                conn.execute("PRAGMA foreign_keys = OFF")
                people = [row[0] for row in conn.execute("SELECT id FROM persons ORDER BY ordinal")]
                damage(conn, *people)
                conn.commit()
            return people

        def rename(new):
            def apply(conn, old):
                for table, column in (("persons", "id"), ("person_records", "person_id"), ("person_records", "home_person_id"), ("person_bindings", "person_id"), ("mps", "person_id")):
                    conn.execute(f"UPDATE {table} SET {column} = ? WHERE {column} = ?", (new, old))
            return apply

        def aliased(*keys):
            def apply(conn, person):
                for number, key in enumerate(keys):
                    conn.execute("INSERT INTO persons VALUES (?, ?)", (key, 90 + number))
                    conn.execute("INSERT INTO person_aliases VALUES (?, ?)", (key, person))
            return apply

        for label, damage, diagnostic in (
            ("a person keyed index", rename("index"), "Invalid person key 'index'"),
            ("an alias keyed index", aliased("index"), "Invalid person key 'index'"),
            ("two aliases differing only by case", aliased("Old1", "old1"), "differ only by case"),
        ):
            with self.subTest(label):
                edited(damage)
                with contextlib.closing(store.connect(self.db)) as conn:
                    with self.assertRaisesRegex(registry.RegistryError, diagnostic):
                        build.collect_abgeordnete(conn)
        with self.subTest("an alias keyed like a live page"):
            def retire_ada_into_bea(conn, ada, bea):
                conn.execute("INSERT INTO person_aliases VALUES (?, ?)", (ada, bea))
            ada, bea = edited(retire_ada_into_bea, names=("Ada Example", "Bea Example"))
            with contextlib.closing(store.connect(self.db)) as conn:
                mps, _ = build.collect_abgeordnete(conn)
            self.assertEqual({mp["id"] for mp in mps if mp["has_page"]}, {ada, bea})
            self.assertTrue(all(ada not in mp["aliases"] for mp in mps))

    # Value: protects=--offline on a store with a damaged registry exits 1 with an error line instead of a traceback; fails_when=main catches only RuntimeError so a RegistryError escapes; why_new=only the old-schema rejection was tested through the CLI; seam=none
    def test_offline_cli_reports_an_incomplete_registry_without_a_traceback(self):
        site = self.root / "site"
        data = site / "data"
        data.mkdir(parents=True)
        r = report()
        (data / "plenarprotokoll-21-1.json").write_text(json.dumps(r))
        self.db = data / "bundestag-pulse.sqlite"
        self.rebuild([r])
        with contextlib.closing(sqlite3.connect(self.db)) as conn:
            conn.execute("DROP TABLE person_bindings")
            conn.commit()
        done = subprocess.run([sys.executable, str(_support.ROOT / "scripts/build_dip_pulse_site.py"), "--offline", "--output-dir", str(site)],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 1)
        self.assertNotIn("Traceback", done.stderr)
        self.assertIn("Incomplete person registry", done.stderr)
        # Value: protects=--offline on a store that is not a database exits 1 with an error line, and --offline --no-persist renders without reading the store at all; fails_when=the precheck lets sqlite3.Error escape as a traceback or runs although --no-persist never opens the store; why_new=only a damaged registry inside a valid database was tested; seam=none
        self.db.write_bytes(b"not a database, " * 64)
        script = [sys.executable, str(_support.ROOT / "scripts/build_dip_pulse_site.py"), "--offline", "--output-dir", str(site)]
        corrupt = subprocess.run(script, capture_output=True, text=True)
        self.assertEqual(corrupt.returncode, 1)
        self.assertNotIn("Traceback", corrupt.stderr)
        rendered = subprocess.run([*script, "--no-persist"], capture_output=True, text=True)
        self.assertEqual(rendered.returncode, 0, rendered.stderr)


    # Value: protects=a durable alias whose survivor a name guess moved elsewhere still redirects to the current person's page; fails_when=aliases are resolved only through the durable chain so the retired key matches no page and its published file is deleted; why_new=the guess redirect test had no retired key behind the moved survivor; seam=none
    def test_a_retired_key_behind_a_guess_moved_survivor_keeps_its_redirect(self):
        conn = self.open_store()
        self.up(conn, "roster:7", "dip:7", "Max Muster", dip="7", mdb=True, party="SPD")
        first = self.up(conn, "occ-100", "xml:100", "Max Muster", xml="100", aw=7, match="ext_id", party="SPD")
        second = self.up(conn, "occ-101", "xml:101", "Max Muster", xml="101", aw=7, match="ext_id", party="SPD")
        registry.reconcile(conn)
        conn.commit()
        retired = {row[0] for row in conn.execute("SELECT id FROM person_aliases")}
        self.assertEqual(len(retired), 1)
        mps, _ = build.collect_abgeordnete(conn)
        (mp,) = [m for m in mps if m["has_page"]]
        homes = {row[0] for row in conn.execute("SELECT home_person_id FROM person_records")}
        self.assertEqual(set(mp["aliases"]), homes - {mp["id"]})
        self.assertTrue(retired <= set(mp["aliases"]))

    # Value: protects=a guess chained through a person that holds both Foehr and Mende records never joins the two reviewed partitions; fails_when=the person-level guess group ignores partitions that are not correction: owners; why_new=only correction: owners were checked at the person level; seam=none
    def test_a_guess_chain_never_joins_the_foehr_and_mende_partitions(self):
        first = self.open_store("first.sqlite")
        self.up(first, "roster:Z1", "dip:Z1", "Alexander Föhr", dip="Z1", aw=9, match="ext_id", mdb=True, party="CDU/CSU")
        self.up(first, "vote:Z2", "dip:Z2", "Dirk-Ulrich Mende", dip="Z2", aw=9, match="ext_id", mdb=True, party="FDP")
        registry.reconcile(first)
        self.assertEqual(first.execute("SELECT COUNT(*) FROM person_aliases").fetchone()[0], 1)  # durable: shared aw id
        second = self.next_build(first)
        self.up(second, "roster:Z1", "dip:Z1", "Alexander Föhr", dip="Z1", mdb=True, party="CDU/CSU")
        self.up(second, "vote:Z2", "dip:Z2", "Dirk-Ulrich Mende", dip="Z2", mdb=True, party="FDP")
        foehr = self.up(second, "occ-f", "xml:11005304", "Alexander Föhr", xml="11005304", party="CDU/CSU")
        mende = self.up(second, "occ-m", "xml:11005304", "Dirk-Ulrich Mende", xml="11005304", party="FDP")
        registry.reconcile(second)
        persons = self.person_of_records(second)
        self.assertNotEqual(persons[foehr], persons[mende])

    # Value: protects=a person once listed as MdB keeps a page in later builds even when the source no longer marks the record as MdB (a sampled-person or roll-call row touches it); fails_when=bind stops carrying ever_mdb forward so the person drops out of the pages and every speaker link to it dangles; why_new=only empty-input replays and speech-bound persons were tested for page retention; seam=none
    def test_a_former_mdb_keeps_a_page_when_a_later_build_no_longer_lists_them(self):
        first = self.open_store("first.sqlite")
        self.up(first, "roster:5", "dip:5", "Ada Example", dip="5", mdb=True, party="SPD")
        registry.reconcile(first)
        mps, _ = build.collect_abgeordnete(first)
        self.assertEqual([(m["name"], m["has_page"]) for m in mps], [("Ada Example", True)])
        second = self.next_build(first)
        self.up(second, "roster:5", "dip:5", "Ada Example", dip="5", mdb=False, party="SPD")
        registry.reconcile(second)
        mps, _ = build.collect_abgeordnete(second)
        (mp,) = mps
        self.assertFalse(mp["is_mdb"])
        self.assertEqual(mp["speech_count"], 0)
        self.assertTrue(mp["has_page"])


if __name__ == "__main__":
    unittest.main()
