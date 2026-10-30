"""Person-registry operator contracts: staged roster ingestion, rejected
corrections, the shipped Föhr/Mende partition and the
shared writer lock on the direct persistence paths.

Kept apart from test_stable_ids.py on purpose; that file holds the A.2
identity tests."""
from __future__ import annotations
import contextlib
from datetime import date
import copy
import io
import itertools
import json
import os
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock
import _support  # noqa: F401
import build_dip_pulse_site as build
import persist_dip_pulse_store as store
import person_registry as registry
from _registry_fixture import RegistryFixture
from stable_ids import roster_occurrence_id, stable_key


def report(pid="s1", names=("Ada Example",), rede_ids=None):
    speakers = [
        {"rede_id": (rede_ids or {}).get(name, f"{pid}-r{index}"),
         "speaker": {"display_name": name, "xml_redner_id": str(index + 1), "fraktion": "SPD"},
         "char_count": 20, "text": "Ein geprüfter Text."}
        for index, name in enumerate(names)
    ]
    return {"validation_summary": {"speech_kinds_version": store.speech_kinds.VERSION}, "protocol": {"id": pid, "dokumentnummer": f"21/{pid[-1]}", "datum": "2026-06-10"},
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
        lock = registry.writer_lock_path(self.db)
        lock.parent.mkdir(parents=True, exist_ok=True)
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
        self.assertEqual(list(registry.private_dir(self.db).glob(f"{self.db.name}.*.tmp*")), [])

    # Value: protects=the staged rebuild reconciles as a full build: a speaker record whose Rede the source re-keyed (its copied binding names no occurrence of this build) is stale, so it neither absorbs a roster person by its shared abgeordnetenwatch id nor keeps them apart; fails_when=_rebuild_database_from_entries calls reconcile without full_build=True, so every copied binding keeps its record live; why_new=third ship round (12): reconcile's full_build was tested directly, never through the rebuild; seam=roster_ingest adds the roster person to the staged store
    def test_the_rebuild_reconciles_as_a_full_build(self):
        aw = {"id": 5, "match": "ext_id", "url": "https://www.abgeordnetenwatch.de/profile/ada"}
        first = report()
        first["agenda_items"][0]["xml_speakers"][0]["speaker"]["abgeordnetenwatch"] = aw
        self.rebuild([first])
        second = report(rede_ids={"Ada Example": "s1-corrected"})
        second["agenda_items"][0]["xml_speakers"][0]["speaker"]["xml_redner_id"] = "9"

        def ingest(staged):
            self.up(staged, roster_occurrence_id("dip-5"), "dip:dip-5", "Ada Example", dip="dip-5", aw=5, match="ext_id", mdb=True, party="SPD")

        self.rebuild([second], preserve_roster=False, roster_ingest=ingest)
        records = {row["identity_key"]: row["person_id"] for row in self.rows("person_records")}
        self.assertEqual(len(self.rows("person_aliases")), 0)
        self.assertEqual(records["xml:9"], records["dip:dip-5"])
        (stale,) = [key for key in records if key not in ("xml:9", "dip:dip-5")]
        self.assertNotEqual(records[stale], records["dip:dip-5"])

    # Value: protects=the staged rebuild hands the facts engine the build date and the built set from the staged store (no votes persisted: votes metrics are not computed); fails_when=_rebuild_database_from_entries or its wrapper drops today, or built is a constant; why_new=third ship round (12) today forwarding and A.2 test follow-ups built forwarding: no test spied the rebuild's engine call; seam=compute_and_store wrapped by a spy
    def test_the_rebuild_hands_the_build_date_and_built_set_to_the_facts_engine(self):
        with mock.patch.object(build.facts, "compute_and_store", wraps=build.facts.compute_and_store) as engine:
            self.rebuild([report()], today=date(2026, 7, 1))
        engine.assert_called_once()
        self.assertEqual(engine.call_args.kwargs["today"], date(2026, 7, 1))
        self.assertEqual(engine.call_args.kwargs["built"], set())
        with mock.patch.object(build.facts, "compute_and_store", wraps=build.facts.compute_and_store) as engine:
            rebuilt = self.rebuild([report()])
        self.assertIsNone(engine.call_args.kwargs["today"])
        self.assertTrue({"incomplete_periods", "sitting_gaps"} <= rebuilt.facts_report.keys())

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
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            store.persist_sampled_people(conn, {"protocol": {"dokumentnummer": "21/1"}, "sampled_people": [{"titel": "Ada Example"}, {"titel": "Bea Example"}]}, now)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM person_bindings").fetchone()[0], 0)
        # Value: protects=two distinct DIP persons without an id are skipped with a diagnostic instead of collapsing into one name-party:Unbekannt record; fails_when=the id-less row is persisted with mp_identity(dip_person_id=None); why_new=third ship round (4): the collapse was only read, never pinned; seam=none
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM person_records").fetchone()[0], 0)
        self.assertIn("21/1: 2 sampled DIP persons have no id and were skipped", stderr.getvalue())
        client = mock.Mock()
        client.list_all.return_value = [
            {"titel": name, "vorname": name.split()[0], "nachname": name.split()[1], "fraktion": ["SPD"], "funktion": ["MdB"], "wahlperiode": 21}
            for name in ("Ada Example", "Bea Example")
        ] + [{"id": "dip-9", "titel": "Cem Example", "vorname": "Cem", "nachname": "Example", "fraktion": ["SPD"], "funktion": ["MdB"], "wahlperiode": 21}]
        roster = self.open_store("roster.sqlite")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            stats = build.ingest_mdb_roster(client, roster, wahlperiode=21)
        self.assertEqual((stats["mdb"], stats["skipped_no_id"]), (1, 2))
        self.assertEqual([row[0] for row in roster.execute("SELECT identity_key FROM person_records")], ["dip:dip-9"])
        self.assertIn("2 DIP persons with an MdB function have no id and were skipped", stderr.getvalue())

    # Value: protects=the roster holds exactly the MdBs of its Wahlperiode: "MdB" as an exact funktion, or a Fraktion role in that Wahlperiode, never a Bundesrat member; fails_when=the substring test lets "MdBR"/"Stellv. MdBR" in again, or an MdB whose current office is a government one is dropped; why_new=on DIP WP 21 (2026-10-30) the substring test listed 151 Bundesrat members and missed 48 MdBs, 740 listed instead of 637; seam=none
    def test_only_mdbs_of_the_wahlperiode_enter_the_roster(self):
        def person(pid, name, funktion, fraktion=(), roles=()):
            first, last = name.split()
            return {"id": pid, "titel": name, "vorname": first, "nachname": last, "fraktion": list(fraktion),
                    "funktion": [funktion], "wahlperiode": [21], "person_roles": list(roles)}
        client = mock.Mock()
        client.list_all.return_value = [
            person("dip-1", "Ada Example", "MdB", fraktion=["SPD"]),
            person("dip-2", "Bea Land", "MdBR", roles=[{"bundesland": "Bayern", "wahlperiode_nummer": [21]}]),
            person("dip-3", "Cem Land", "Stellv. MdBR"),
            person("dip-4", "Dora Staat", "Parl. Staatssekr.", roles=[{"fraktion": "CDU/CSU", "wahlperiode_nummer": [20, 21]}]),
            person("dip-5", "Emil Frueher", "Bundesmin.", roles=[{"fraktion": "SPD", "wahlperiode_nummer": [19, 20]}]),
        ]
        roster = self.open_store("roster.sqlite")
        stats = build.ingest_mdb_roster(client, roster, wahlperiode=21)
        self.assertEqual((stats["fetched"], stats["mdb"]), (5, 2))
        rows = roster.execute(
            "SELECT m.dip_person_id, p.name FROM mps m LEFT JOIN parties p ON p.id = m.party_id WHERE m.is_mdb = 1 ORDER BY 1"
        ).fetchall()
        # A Parl. Staatssekretärin's Fraktion comes from her role: DIP leaves the top-level field empty.
        self.assertEqual([tuple(row) for row in rows], [("dip-1", "SPD"), ("dip-4", "CDU/CSU")])

    # Value: protects=an offline rebuild drops preserved roster rows of Bundesrat members a store from before the exact MdB rule holds, and keeps an MdB in a government office; fails_when=_read_roster_rows carries every is_mdb row again, or filters by "MdB" in function and loses the Parl. Staatssekretärin; why_new=preserved rows survive until the roster is fetched again, so the fix would not reach an offline rebuild; seam=none
    def test_a_preserved_bundesrat_row_is_not_carried_over(self):
        def ingest(staged):
            for pid, funktion in (("dip-1", ["MdB"]), ("dip-2", ["MdBR"]), ("dip-3", ["Stellv. MdBR"]), ("dip-4", ["Parl. Staatssekr."])):
                store.upsert_mp(staged, now=store.utc_now(), display_name=f"Person {pid}", party_id=None,
                                identity_key=f"dip:{pid}", dip_person_id=pid, occurrence_id=roster_occurrence_id(pid),
                                function=funktion, is_mdb=True)
        self.rebuild([report("s1", names=("Bea Example",))], preserve_roster=False, roster_ingest=ingest)
        entries = [{"report": report("s1", names=("Bea Example",)), "report_path": self.root / "s1.json"}]
        build.rebuild_database_from_entries(self.db, entries)
        self.assertEqual(sorted(r["dip_person_id"] for r in self.rows("mps") if r["is_mdb"]), ["dip-1", "dip-4"])

    # Value: protects=a preserved roster row without a DIP id is skipped with a warning on the next rebuild instead of becoming a name-party record; fails_when=the preserved-roster replay persists it under mp_identity(display_name, party); why_new=third ship round (4): the preserved path built the identity from name and party; seam=none
    def test_a_preserved_roster_row_without_a_dip_id_is_skipped_with_a_warning(self):
        def ingest(staged):
            store.upsert_mp(staged, now=store.utc_now(), display_name="Ada Example", party_id=None, identity_key="dip:dip-7",
                            dip_person_id="dip-7", occurrence_id=stable_key("roster", "dip-7"), is_mdb=True)
        self.rebuild([report("s1", names=("Bea Example",))], preserve_roster=False, roster_ingest=ingest)
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE mps SET dip_person_id = NULL WHERE is_mdb = 1")
        stderr = io.StringIO()
        entries = [{"report": report("s1", names=("Bea Example",)), "report_path": self.root / "s1.json"}]
        with contextlib.redirect_stderr(stderr):
            build.rebuild_database_from_entries(self.db, entries)
        self.assertIn("1 preserved roster rows have no DIP id and were skipped", stderr.getvalue())
        self.assertEqual([r["identity_key"] for r in self.rows("person_records") if r["identity_key"].startswith("name-party:")], [])

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
        # Value: protects=the same, for every arrival order and for sittings on one day, which only the protocol id orders; fails_when=entry_sort_key drops its id tie-break; why_new=A.2 test follow-ups: only two orders of three dated reports were checked; seam=none
        same_day = copy.deepcopy(reports)
        for r in same_day:
            r["protocol"]["datum"] = "2026-06-10"
        for label, cohort in (("dated", reports), ("same day", same_day)):
            with self.subTest(label):
                issued = []
                for order in itertools.permutations(cohort):
                    self.db = self.root / f"order-{label}-{len(issued)}.sqlite"
                    self.rebuild(list(order))
                    issued.append({m["display_name"]: m["person_id"] for m in self.rows("mps")})
                self.assertTrue(all(key.startswith("p-") for key in issued[0].values()), issued[0])
                self.assertEqual([i for i in issued if i != issued[0]], [])

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
            # Value: protects=an mps row naming a person the registry does not hold aborts the replay before its registry is carried; fails_when=validate checks foreign keys of the registry tables only (the mps arm dropped); why_new=third ship round (12), the mps foreign-key arm; seam=none
            ("mps row points at unknown person", "UPDATE mps SET person_id = 'ghost'", "foreign-key violations"),
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
                self.assertEqual(list(registry.private_dir(self.db).glob(f"{self.db.name}.*.tmp*")), [])
        # Value: protects=an upgrade replay (--offline --repersist) of a store whose mps rows name persons but whose four registry tables are gone stops instead of re-minting every person key; fails_when=copy_previous returns silently for a store without registry tables; why_new=registry follow-ups (3): the upgrade path skips the schema pre-flight, so only copy_previous guards it; seam=none
        with self.subTest("upgrade replay with every registry table missing"):
            self.db.write_bytes(pristine)
            with contextlib.closing(sqlite3.connect(self.db)) as conn:
                conn.execute("PRAGMA foreign_keys = OFF")
                conn.executescript("; ".join(f"DROP TABLE {table}" for table in registry.REGISTRY_TABLES))
                conn.commit()
            damaged = self.db.read_bytes()
            with self.assertRaisesRegex(build.DatabaseRebuildError, "Incomplete person registry"):
                self.rebuild([r], upgrade=True)
            self.assertEqual(damaged, self.db.read_bytes())
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
        # Value: protects=a partition added to a store that showed the shared ext_id profile on one person leaves it on the profile owner's row only, and the old person keeps no occurrence; fails_when=the old record's profile survives on a bound row or the non-owner partition inherits it from the record it left; why_new=the add-partition case ran without a profile; seam=none
        self.db = self.root / "profiled.sqlite"
        shared = self.shared_id_report()
        with self.correction_file({}):
            self.rebuild([shared])
        self.assertEqual(self.profiles(), {"Dirk-Ulrich Mende": (123, "ext_id", "https://example.test/foehr")})
        old_person = self.rows("person_records")[0]["person_id"]
        with self.correction_file(self.partition(profile_owner="foehr")):
            self.rebuild([shared])
            live = {m["display_name"]: (m["aw_politician_id"], m["aw_match"], m["profile_url"])
                    for m in self.rows("mps") if m["id"] in {b["record_id"] for b in self.rows("person_bindings")}}
            self.assertEqual(live, {"Alexander Föhr": self.FOEHR_PROFILE, "Dirk-Ulrich Mende": self.NO_PROFILE})
            self.assertNotIn(old_person, {b["person_id"] for b in self.rows("person_bindings")})
            state = self.registry_state()
            self.rebuild([shared])
            self.assertEqual(self.registry_state(), state)

    def shared_id_report(self, names=("Alexander Föhr", "Dirk-Ulrich Mende")):
        """Föhr and Mende printed under one Redner-ID whose ext_id profile is Föhr's;
        the rede ids follow the name, so any order names the same occurrences."""
        r = report(names=names, rede_ids={"Alexander Föhr": "s1-r0", "Dirk-Ulrich Mende": "s1-r1"})
        for speech in r["agenda_items"][0]["xml_speakers"]:
            speech["speaker"].update(xml_redner_id="11005304", abgeordnetenwatch={"id": 123, "match": "ext_id", "url": "https://example.test/foehr"})
        return r

    def profiles(self):
        return {m["display_name"]: (m["aw_politician_id"], m["aw_match"], m["profile_url"]) for m in self.rows("mps")}

    def partition(self, labels=None, **extra):
        labels = labels or {"Alexander Föhr": "foehr", "Dirk-Ulrich Mende": "mende"}
        return {"partitions": [{"xml_redner_id": "11005304", "labels": labels, **extra}]}

    def registry_state(self, tables=("persons", "person_aliases", "person_records", "person_bindings", "mps")):
        """The registry and mps rows without their write timestamps."""
        return [[{k: v for k, v in row.items() if k not in ("created_at", "updated_at")} for row in self.rows(t)] for t in tables]

    def bound_groups(self):
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            groups = self.occurrence_groups(conn)
            profiles = {row[0]: tuple(row[1:]) for row in conn.execute(
                "SELECT b.id, m.aw_politician_id, m.profile_url FROM person_bindings b JOIN mps m ON m.id = b.record_id")}
        return groups, profiles

    FOEHR_PROFILE = (123, "partitioned", "https://example.test/foehr")
    NO_PROFILE = (None, None, None)

    # Value: protects=removing an applied partition from person_corrections.json cannot hand the shared profile back to both partitions; fails_when=a replay without the entry rebuilds the partition records from bare source evidence, so Mende's row shows Föhr's ext_id profile and the reviewed names revert; why_new=the third ship round found the removal half applied and the policy unpinned; seam=none
    def test_removing_an_applied_partition_is_refused_and_the_store_kept(self):
        r = self.shared_id_report()
        with self.correction_file(self.partition(profile_owner="foehr")):
            self.rebuild([r])
        self.assertEqual(self.profiles(), {"Alexander Föhr": self.FOEHR_PROFILE, "Dirk-Ulrich Mende": self.NO_PROFILE})
        persons = sorted(p["person_id"] for p in self.rows("person_records"))
        before = self.db.read_bytes()
        with self.correction_file({}), self.assertRaisesRegex(build.DatabaseRebuildError, r"Redner-ID 11005304 is partitioned in this registry") as caught:
            self.rebuild([r])
        for person in persons:
            self.assertIn(person, str(caught.exception))
        self.assertEqual(self.db.read_bytes(), before)
        # Value: protects=the refusal also guards a store written without the staged rebuild; fails_when=reconcile settles the removed partition instead of refusing it; why_new=reconcile is the one check every registry writer passes; seam=none
        conn = self.open_store("direct.sqlite")
        with self.correction_file(self.partition(profile_owner="foehr")):
            self.up(conn, "occ-foehr", "xml:11005304", "Alexander Föhr", xml="11005304")
            registry.reconcile(conn)
        with self.correction_file({}), self.assertRaisesRegex(registry.RegistryError, "Redner-ID 11005304 is partitioned"):
            registry.reconcile(conn)
        # Value: protects=an offline render, which applies the corrections file to the pages without a reconcile, refuses the store too; fails_when=only reconcile checks, so --offline renders reverted reviewed names beside the store's partition persons; why_new=the render-only path never reaches reconcile; seam=none
        site = self.root / "site"
        (site / "data").mkdir(parents=True)
        (site / "data" / "bundestag-pulse.sqlite").write_bytes(before)
        stderr = io.StringIO()
        with self.correction_file({}), mock.patch.object(sys, "argv", ["build", "--offline", "--output-dir", str(site)]), \
                contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(build.main(), 1)
        self.assertIn("error: Redner-ID 11005304 is partitioned in this registry", stderr.getvalue())
        self.assertEqual((site / "data" / "bundestag-pulse.sqlite").read_bytes(), before)
        # The documented way to drop a partition: a new history from the cached reports.
        self.db = self.root / "fresh.sqlite"
        with self.correction_file({}):
            self.rebuild([r])
        self.assertEqual(len({b["person_id"] for b in self.rows("person_bindings")}), 1)
        self.assertEqual(self.rows("person_aliases"), [])

    # Value: protects=label and profile-owner edits of an applied partition follow the file, move the shared profile with the owner and reach a fixed point; fails_when=profile_blocked or the binding is kept from an earlier build, or the incremental store groups or attributes differently from a fresh build of the same correction history; why_new=only adding a partition and the shipped file were tested; seam=none
    def test_partition_edits_follow_the_file_and_replay_to_a_fixed_point(self):
        r, reversed_r = self.shared_id_report(), self.shared_id_report(("Dirk-Ulrich Mende", "Alexander Föhr"))
        cached = copy.deepcopy(r)
        steps = (
            ("profile owner foehr", self.partition(profile_owner="foehr"),
             {"Alexander Föhr": self.FOEHR_PROFILE, "Dirk-Ulrich Mende": self.NO_PROFILE}, 2),
            ("profile owner moved to mende", self.partition(profile_owner="mende"),
             {"Alexander Föhr": self.NO_PROFILE, "Dirk-Ulrich Mende": (123, "partitioned", "https://example.test/foehr")}, 2),
            ("profile owner cleared", self.partition(), {"Alexander Föhr": self.NO_PROFILE, "Dirk-Ulrich Mende": self.NO_PROFILE}, 2),
            ("Mende's label moved to foehr", self.partition({"Alexander Föhr": "foehr", "Dirk-Ulrich Mende": "foehr"}, profile_owner="foehr"),
             None, 1),
        )
        for label, corrections, expected, people in steps:
            with self.subTest(label), self.correction_file(corrections):
                self.rebuild([r])
                if expected is not None:
                    self.assertEqual(self.profiles(), expected)
                bound = {b["person_id"] for b in self.rows("person_bindings")}
                self.assertEqual(len(bound), people)
                state = self.registry_state()
                self.rebuild([r])
                self.assertEqual(self.registry_state(), state)
                self.rebuild([reversed_r])
                self.assertEqual(self.registry_state(), state, "incremental replay in reversed persist order")
                incremental = self.bound_groups()
                current = self.db
                for order, source in (("same order", r), ("reversed order", reversed_r)):
                    self.db = self.root / f"fresh-{label}-{order}.sqlite"
                    self.rebuild([source])
                    self.assertEqual(self.bound_groups(), incremental, order)
                self.db = current
        self.assertEqual(r, cached)  # the cached source evidence is never rewritten
        # Value: protects=an ordinary attribute refresh of a partitioned occurrence (a changed printed Fraktion) keeps its record and person, unlike a reviewed correction change; fails_when=bind treats any changed evidence of a partition record as a move; why_new=only correction edits were replayed; seam=none
        with self.correction_file(self.partition(profile_owner="foehr")):
            self.db = self.root / "refresh.sqlite"
            self.rebuild([r])
            before = {b["id"]: (b["record_id"], b["person_id"]) for b in self.rows("person_bindings")}
            refreshed = copy.deepcopy(r)
            refreshed["agenda_items"][0]["xml_speakers"][1]["speaker"]["fraktion"] = "CDU/CSU"
            self.rebuild([refreshed])
            self.assertEqual({b["id"]: (b["record_id"], b["person_id"]) for b in self.rows("person_bindings")}, before)
            self.assertEqual(self.profiles(), {"Alexander Föhr": self.FOEHR_PROFILE, "Dirk-Ulrich Mende": self.NO_PROFILE})
        # Value: protects=removing a label that still has bound printed names aborts instead of guessing an owner; fails_when=partition_identity falls back to the bare Redner-ID identity for an unlisted name; why_new=label edits were untested; seam=none
        before = self.db.read_bytes()
        with self.correction_file(self.partition({"Alexander Föhr": "foehr"}, profile_owner="foehr")), \
                self.assertRaisesRegex(build.DatabaseRebuildError, "review printed label 'dirk-ulrich mende'"):
            self.rebuild([r])
        self.assertEqual(self.db.read_bytes(), before)

    # Value: protects=the documented undo for two partitions that are one person: a reviewed merge joins them while the shared profile stays on the owner's record; fails_when=a guess or the partition guard tears the reviewed merge apart, or the merge lets the non-owner record take the profile; why_new=the durable policy names this undo and nothing exercised it; seam=none
    def test_a_reviewed_merge_undoes_a_partition_and_keeps_the_profile_with_its_owner(self):
        r = self.shared_id_report()
        with self.correction_file(self.partition(profile_owner="foehr")):
            self.rebuild([r])
        records = {rec["partition"]: rec["home_person_id"] for rec in self.rows("person_records")}
        merged = {**self.partition(profile_owner="foehr"), "merges": [{"persons": [records["foehr"], records["mende"]], "survivor": records["foehr"]}]}
        with self.correction_file(merged):
            self.rebuild([r])
            self.assertEqual({b["person_id"] for b in self.rows("person_bindings")}, {records["foehr"]})
            self.assertEqual(self.profiles(), {"Alexander Föhr": self.FOEHR_PROFILE, "Dirk-Ulrich Mende": self.NO_PROFILE})
            state = self.registry_state()
            self.rebuild([r])
            self.assertEqual(self.registry_state(), state)

    # Value: protects=only the --offline --repersist replay upgrades an old-schema store; fails_when=an online rebuild accepts the schema 2 store and silently mints a fresh registry; why_new=only the offline render and the export were gated; seam=none
    def test_only_the_upgrade_rebuild_accepts_an_old_schema_store(self):
        with sqlite3.connect(self.db) as conn:
            conn.executescript("CREATE TABLE parties(id INTEGER PRIMARY KEY,name TEXT); CREATE TABLE mps(id INTEGER PRIMARY KEY,display_name TEXT); CREATE TABLE protocols(id TEXT PRIMARY KEY,document_number TEXT);")
            conn.execute("INSERT INTO protocols VALUES ('s1','21/1')")
        before = self.db.read_bytes()
        with self.assertRaisesRegex(build.DatabaseRebuildError, "--offline --repersist"):
            self.rebuild([report()])
        self.assertEqual(self.db.read_bytes(), before)
        self.assertTrue(self.rebuild([report()], upgrade=True).replaced)
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
        stale = registry.private_dir(self.db) / "store.sqlite.crashed.tmp"
        stale.write_bytes(b"half-written store with speech text")
        sidecar = registry.private_dir(self.db) / "store.sqlite.crashed.tmp-journal"
        sidecar.write_bytes(b"journal")
        self.rebuild([report(), report(pid="s2")])
        self.assertFalse(stale.exists())
        self.assertFalse(sidecar.exists())
        self.assertTrue(registry.writer_lock_path(self.db).exists())  # the sweep never takes the lock file
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
        self.assertEqual(rendered.returncode, 1, rendered.stderr)
        self.assertIn("file is not a database", rendered.stderr)


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
    # Value: protects=a stale record's partition (an occurrence that moved away, evidence nobody prints any more) does not veto a name guess between the live records of two persons; fails_when=_guess_merges reads partitions from every member of a group instead of the live (and partner-joined) ones; why_new=registry follow-ups (3): no stale record ever carried a partition; seam=registry._guess_merges over _load_rows with partitions set in person_records
    def test_a_stale_partition_does_not_veto_a_guess_between_live_records(self):
        conn = self.open_store()
        stale = self.up(conn, "occ-s", "xml:1", "Alexander Föhr", xml="1", party="CDU/CSU")
        speaker = self.up(conn, "occ-1", "xml:10", "Max Muster", xml="10", party="SPD")
        roster = self.up(conn, "roster:5", "dip:5", "Max Muster", dip="5", mdb=True, party="SPD")
        mende = self.up(conn, "occ-3", "xml:30", "Erik Mende", xml="30", party="CDU/CSU")
        person = dict(conn.execute("SELECT id, person_id FROM person_records"))
        registry._assign(conn, stale, person[speaker])
        registry._assign(conn, mende, person[roster])
        conn.execute("UPDATE person_records SET partition = 'foehr' WHERE id = ?", (stale,))
        conn.execute("UPDATE person_records SET partition = 'mende' WHERE id = ?", (mende,))
        live = {speaker, roster, mende}
        registry._guess_merges(conn, registry._load_rows(conn, touched=live))
        after = dict(conn.execute("SELECT id, person_id FROM person_records"))
        self.assertEqual(after[speaker], after[roster])
        # Control: the same record live is evidence, and two partitions stay split.
        for record, home in person.items():
            registry._assign(conn, record, home)
        registry._assign(conn, stale, person[speaker])
        registry._assign(conn, mende, person[roster])
        registry._guess_merges(conn, registry._load_rows(conn, touched=live | {stale}))
        after = dict(conn.execute("SELECT id, person_id FROM person_records"))
        self.assertNotEqual(after[speaker], after[roster])

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

    # Value: protects=reconcile reads liveness from the build's touched set only: a connection that started no build is refused, and a build that bound nothing reconciles with every copied record stale; fails_when=reconcile reads a missing touched table as "nothing touched" (every record silently stale) or falls back to bindings; why_new=handoff 08 removed the bound/vacated fallback; seam=none
    def test_reconcile_needs_a_build_on_its_connection(self):
        first = self.open_store("first.sqlite")
        self.up(first, "roster:5", "dip:5", "Ada Example", dip="5", mdb=True, party="SPD")
        self.up(first, "speech:1", "xml:1", "Ada Example", xml="1", party="SPD")
        registry.reconcile(first)
        first.commit()
        joined = set(self.person_of_records(first).values())
        self.assertEqual(len(joined), 1)
        reopened = self.open_store("first.sqlite")
        with self.assertRaisesRegex(registry.RegistryError, "only after a rebuild"):
            registry.reconcile(reopened)
        empty = self.next_build(first)
        registry.reconcile(empty)
        persons = self.person_of_records(empty)
        self.assertEqual(len(persons), 2)
        self.assertEqual(len(set(persons.values())), 2, "stale records take part in no guess")

    # Value: protects=a roster record left by one of its roster occurrences (two DIP persons folded on one trusted abgeordnetenwatch id, one now listed under another id) is vacated and does not rejoin its old speaker as a stale roster partner; fails_when=is_stale_roster_partner ignores the vacated mark; why_new=handoff 08 kept the mark only for this rule, which no test reached; seam=none
    def test_a_vacated_roster_record_does_not_rejoin_as_a_stale_partner(self):
        first = self.open_store("first.sqlite")
        roster = self.up(first, "roster:7", "aw:5", "Ada Example", dip="7", aw=5, match="ext_id", mdb=True, party="SPD")
        self.up(first, "roster:8", "aw:5", "Ada Example", dip="8", aw=5, match="ext_id", mdb=True, party="SPD")
        speaker = self.up(first, "speech:1", "xml:1", "Ada Example", xml="1", party="SPD")
        registry.reconcile(first)
        self.assertEqual(len(set(self.person_of_records(first).values())), 1)
        second = self.next_build(first)
        moved = self.up(second, "roster:8", "aw:6", "Ada Example", dip="8", aw=6, match="ext_id", mdb=True, party="CDU/CSU")
        self.up(second, "speech:1", "xml:1", "Ada Example", xml="1", party="SPD")
        registry.reconcile(second)
        self.assertNotEqual(moved, roster)
        self.assertTrue(json.loads(second.execute("SELECT evidence_json FROM person_records WHERE id=?", (roster,)).fetchone()[0]).get("vacated"))
        persons = self.person_of_records(second)
        self.assertNotEqual(persons[roster], persons[speaker])

    # Value: protects=a stale non-roster record (its occurrence vanished) of a person who still has current records stays off that person's page: no link key, no heading, no party from evidence the source stopped supporting; fails_when=collect_abgeordnete adds every record without an mps row as historical evidence; why_new=A.2 test follow-ups 6h: the rule held only in a code comment; seam=none
    def test_a_stale_speaker_record_stays_off_a_page_with_current_records(self):
        first = self.open_store("first.sqlite")
        self.up(first, stable_key("speech", "p1", "r1"), "xml:1", "Ada Example", xml="1", aw=7, match="ext_id", party="SPD")
        stale = self.up(first, stable_key("speech", "p1", "r0"), "xml:0", "Dr. Ada Alt", xml="0", aw=7, match="ext_id", party="Die Linke")
        registry.reconcile(first)
        self.assertEqual(len(set(self.person_of_records(first).values())), 1)
        second = self.next_build(first)
        self.up(second, stable_key("speech", "p1", "r1"), "xml:1", "Ada Example", xml="1", aw=7, match="ext_id", party="SPD")
        registry.reconcile(second)
        self.assertIsNone(second.execute("SELECT 1 FROM mps WHERE id = ?", (stale,)).fetchone())
        mps, lookup = build.collect_abgeordnete(second)
        (mp,) = mps
        self.assertEqual((mp["name"], mp["party"]), ("Ada Example", "SPD"))
        self.assertNotIn("xml:0", lookup)
        self.assertEqual(lookup["xml:1"], mp["id"])

    # Value: protects=every bind names its occurrence; fails_when=bind accepts an empty occurrence and writes a record no binding holds; why_new=handoff 08 made occurrence required; seam=none
    def test_a_bind_without_an_occurrence_is_refused(self):
        conn = self.open_store()
        for occurrence in (None, ""):
            with self.subTest(occurrence=occurrence), self.assertRaisesRegex(registry.RegistryError, "no occurrence id"):
                self.up(conn, occurrence, "xml:1", "Ada Example", xml="1", party="SPD")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM person_records").fetchone()[0], 0)

    def test_a_repeat_bind_writes_a_binding_only_when_it_changed(self):
        first = self.open_store()
        record = self.vote_up(first, "v1", "Ada Example", "SPD", "https://example.org/ada")
        second = self.next_build(first)
        occurrence = stable_key("vote-member", "v1", "Ada Example", "SPD")
        home = second.execute("SELECT home_person_id FROM person_records WHERE id=?", (record,)).fetchone()[0]
        writes = []
        second.set_trace_callback(lambda sql: writes.append(sql) if "INTO person_bindings" in sql else None)
        self.addCleanup(second.set_trace_callback, None)
        # Unchanged since the previous build: the vote member's binding is not rewritten.
        self.vote_up(second, "v1", "Ada Example", "SPD", "https://example.org/ada")
        self.assertEqual(writes, [])
        # A binding that points at another person (a guess of the previous build)
        # is pointed back at the record's home person.
        second.execute("INSERT INTO persons VALUES ('p-999999', 999999)")
        second.execute("UPDATE person_bindings SET person_id='p-999999' WHERE id=?", (occurrence,))
        self.vote_up(second, "v1", "Ada Example", "SPD", "https://example.org/ada")
        self.assertEqual(len(writes), 1)
        self.assertEqual(second.execute("SELECT record_id, person_id FROM person_bindings WHERE id=?", (occurrence,)).fetchone()[:],
                         (record, home))

    def test_a_bound_occurrence_stays_on_its_record_when_its_new_identity_has_one(self):
        first = self.open_store()
        url = "https://example.org/ada"
        profile_record = self.up(first, "o1", f"profile:{url}", "Ada Example", party="SPD", profile_url=url)
        second = self.next_build(first)
        aw_record = self.up(second, "o2", "aw:5", "Ada Example", aw=5, match="ext_id", xml="11", party="SPD")
        # o1's source now names the trusted profile: an enrichment, not another person.
        self.up(second, "o1", "aw:5", "Ada Example", aw=5, match="ext_id", party="SPD", profile_url=url)
        self.assertNotEqual(profile_record, aw_record)
        self.assertEqual(second.execute("SELECT record_id FROM person_bindings WHERE id='o1'").fetchone()[0], profile_record)


class _FlakyTouch(sqlite3.Connection):
    """A connection whose first registry_touched insert fails with an error that
    is not the missing temp table (a busy or damaged database)."""
    fired = False

    def execute(self, sql, *args):
        if sql.startswith("INSERT OR IGNORE INTO registry_touched") and not _FlakyTouch.fired:
            _FlakyTouch.fired = True
            raise sqlite3.OperationalError("disk I/O error")
        return super().execute(sql, *args)


class WriterRobustnessTests(RegistryFixture, unittest.TestCase):
    """Handoff A.2 05: store open errors, the touched table, private staging and
    the writer lock, and person page writes (TODOS "A.2 third ship round" (3),
    (6), (11), "A.2 second-round review leftovers" (4))."""

    rebuild = RegistryContractTests.rebuild

    def site(self):
        site = self.root / "site"
        (site / "data").mkdir(parents=True, exist_ok=True)
        self.db = site / "data" / "bundestag-pulse.sqlite"
        return site

    def offline(self, site, *extra):
        script = [sys.executable, str(_support.ROOT / "scripts/build_dip_pulse_site.py"), "--offline", "--output-dir", str(site), *extra]
        return subprocess.run(script, capture_output=True, text=True)

    # Value: protects=--offline and --offline --repersist over a store path that is a directory exit 1 with an error line naming the store and leave it as it was; fails_when=open_readonly sits outside the CLI's try, so the open error is a traceback; why_new=third ship round (3) was only read, the CLI tests used a file that is not a database; seam=none
    def test_a_store_path_that_is_a_directory_is_reported_without_a_traceback(self):
        site = self.site()
        r = report()
        (site / "data" / "plenarprotokoll-21-1.json").write_text(json.dumps(r))
        self.db.mkdir()
        (self.db / "keep").write_text("x")
        done = self.offline(site)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertNotIn("Traceback", done.stderr)
        self.assertIn(f"the store {self.db} cannot be read", done.stderr)
        replay = self.offline(site, "--repersist")
        self.assertEqual(replay.returncode, 1, replay.stderr)
        self.assertNotIn("Traceback", replay.stderr)
        self.assertIn(f"ERROR [repersist]: The store {self.db.resolve()} cannot be read", replay.stderr)
        self.assertEqual([p.name for p in self.db.iterdir()], ["keep"])

    # Value: protects=--offline over a store file the user cannot read exits 1 with an error line and leaves its bytes and mode; fails_when=the open error escapes as a traceback; why_new=third ship round (3); seam=none
    @unittest.skipIf(os.geteuid() == 0, "root reads a mode-000 file")
    def test_an_unreadable_store_is_reported_without_a_traceback(self):
        site = self.site()
        r = report()
        (site / "data" / "plenarprotokoll-21-1.json").write_text(json.dumps(r))
        self.rebuild([r])
        before = self.db.read_bytes()
        self.db.chmod(0)
        try:
            done = self.offline(site)
            self.assertEqual(self.db.stat().st_mode & 0o777, 0)
        finally:
            self.db.chmod(0o644)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertNotIn("Traceback", done.stderr)
        self.assertIn(f"the store {self.db} cannot be read", done.stderr)
        self.assertEqual(before, self.db.read_bytes())

    # Value: protects=a store path with URI characters (?, #, %) opens read-only as that file; fails_when=open_readonly pastes the path into a file: URI unquoted, so ?mode=ro is cut off or another file is opened; why_new=no path with URI characters was tested; seam=none
    def test_a_store_path_with_uri_characters_opens_read_only(self):
        self.db = self.root / "a?b#c%d.sqlite"
        self.rebuild([report()])
        conn = build.facts.open_readonly(self.db)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM protocols").fetchone()[0], 1)
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("DELETE FROM protocols")
        finally:
            conn.close()

    # Value: protects=_first_touch creates its temp table only for the missing-table error and lets any other OperationalError propagate; fails_when=_first_touch treats every OperationalError as initialization and retries, hiding a failed write; why_new=third ship round (6); seam=none
    def test_first_touch_propagates_an_unrelated_operational_error(self):
        conn = sqlite3.connect(":memory:")
        try:
            self.assertTrue(registry._first_touch(conn, "r1"))
            self.assertFalse(registry._first_touch(conn, "r1"))
            self.assertEqual(registry._touched(conn, "r1"), (True, None))
        finally:
            conn.close()
        self.assertEqual(registry._touched(sqlite3.connect(":memory:"), "r1"), (False, None))
        _FlakyTouch.fired = False
        flaky = sqlite3.connect(":memory:", factory=_FlakyTouch)
        try:
            with self.assertRaisesRegex(sqlite3.OperationalError, "disk I/O error"):
                registry._first_touch(flaky, "r1")
        finally:
            flaky.close()

    # Value: protects=an unexpected SQLite error at a first touch fails the staged rebuild and keeps the previous store byte for byte, leaving no staged copy; fails_when=the error is swallowed as a missing temp table and the build swaps in a store; why_new=third ship round (6); seam=sqlite3.connect is wrapped to hand the staged connection a flaky factory
    def test_an_unexpected_touch_error_keeps_the_store(self):
        r = report()
        self.rebuild([r])
        before = self.db.read_bytes()
        staging = registry.private_dir(self.db)
        real_connect = sqlite3.connect

        def connect(path, *args, **kwargs):
            if Path(str(path)).parent == staging:
                kwargs["factory"] = _FlakyTouch
            return real_connect(path, *args, **kwargs)

        _FlakyTouch.fired = False
        with mock.patch.object(store.sqlite3, "connect", connect):
            with self.assertRaisesRegex(build.DatabaseRebuildError, "disk I/O error"):
                self.rebuild([r])
        self.assertTrue(_FlakyTouch.fired)
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual(list(staging.glob(f"{self.db.name}.*.tmp*")), [])

    # Value: protects=no staged copy, sidecar or lock file enters the published output tree, during a rebuild or after a successful or failed one; fails_when=the staged copy or writer lock lives next to the store in OUTPUT/data; why_new=third ship round (11), open half; seam=roster_ingest observes the tree while the staged store is open
    def test_staging_and_lock_stay_outside_the_published_tree(self):
        site = self.site()
        self.assertEqual(registry.private_dir(self.db), (self.root / ".site.private").resolve())
        seen = []

        def observe(staged):
            seen.append(sorted(p.relative_to(site).as_posix() for p in site.rglob("*")))
            self.assertEqual(len(list(registry.private_dir(self.db).glob("bundestag-pulse.sqlite.*.tmp"))), 1)

        self.rebuild([report()], roster_ingest=observe)
        self.rebuild([report(), report(pid="s2")], roster_ingest=observe)
        with self.assertRaises(build.DatabaseRebuildError):
            self.rebuild([report()], roster_ingest=mock.Mock(side_effect=RuntimeError("roster down")))
        after = sorted(p.relative_to(site).as_posix() for p in site.rglob("*"))
        self.assertEqual(seen, [["data"], ["data", "data/bundestag-pulse.sqlite"]])
        self.assertEqual(after, ["data", "data/bundestag-pulse.sqlite"])
        self.assertTrue(registry.writer_lock_path(self.db).exists())

    # Value: protects=every spelling of one store (a symlink to it, a .. path) takes the same writer lock, for the rebuild and for the facts engine; fails_when=the lock path is derived from the unresolved store path, so a symlinked store gets its own lock and two writers run at once; why_new=lock tests used one spelling only; seam=none
    def test_equivalent_store_paths_share_one_writer_lock(self):
        r = report()
        self.rebuild([r])
        (self.root / "sub").mkdir()
        link = self.root / "alias.sqlite"
        link.symlink_to(self.db)
        dirlink = self.root / "linked"
        dirlink.symlink_to(self.root, target_is_directory=True)
        spellings = [link, self.root / "sub" / ".." / "store.sqlite", dirlink / "store.sqlite"]
        path = self.root / "report.json"
        path.write_text(json.dumps(r))
        with registry.writer_lock(self.db):
            for spelling in spellings:
                with self.subTest(spelling=str(spelling)):
                    self.assertEqual(registry.writer_lock_path(spelling), registry.writer_lock_path(self.db))
                    with self.assertRaisesRegex(registry.RegistryError, "Another writer"):
                        with registry.writer_lock(spelling):
                            pass
                    with self.assertRaisesRegex(registry.RegistryError, "Another writer"):
                        build.run_facts_engine(spelling, [{"report": r, "report_path": path}], None)
        # Value: protects=a rebuild through a symlink to the store replaces the store and keeps the link; fails_when=the swap renames the staged copy over the unresolved path, turning the link into a file and leaving the store stale; why_new=the lock was resolved, the swap target was not; seam=none
        entries = [{"report": x, "report_path": self.root / f'{x["protocol"]["id"]}.json'} for x in (r, report(pid="s2"))]
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertTrue(build.rebuild_database_from_entries(link, entries).replaced)
        self.assertTrue(link.is_symlink())
        with contextlib.closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM protocols").fetchone()[0], 2)

    # Value: protects=person and alias pages replace a symlink at their target instead of writing through it, and an invalid key is refused at the writer; fails_when=write_abgeordnete_pages trusts its caller's key check and opens the target following links; why_new=second-round review leftovers (4); seam=none
    def test_person_pages_never_write_through_a_symlink(self):
        conn = self.open_store()
        self.up(conn, "occ-s", "xml:10", "Max Muster", xml="10", party="CDU/CSU")
        self.up(conn, "roster:5", "dip:5", "Max Muster", dip="5", mdb=True, party="CDU/CSU")
        registry.reconcile(conn)
        conn.commit()
        mps, _ = build.collect_abgeordnete(conn)
        (mp,) = [m for m in mps if m["has_page"]]
        (alias,) = mp["aliases"]
        site = self.root / "site"
        for folder in ("data", "protocols", "abgeordnete"):
            (site / folder).mkdir(parents=True, exist_ok=True)
        outside = self.root / "sentinel.txt"
        outside.write_text("untouched")
        for key in (mp["id"], alias, "index"):
            (site / "abgeordnete" / f"{key}.html").symlink_to(outside)
        build.write_abgeordnete_pages(site, mps)
        self.assertEqual(outside.read_text(), "untouched")
        for key in (mp["id"], alias, "index"):
            target = site / "abgeordnete" / f"{key}.html"
            self.assertFalse(target.is_symlink(), key)
            self.assertTrue(target.is_file(), key)
        self.assertIn(mp["id"], (site / "abgeordnete" / f"{alias}.html").read_text())
        for bad in ("../escape", "index", ".hidden", "a/b"):
            with self.subTest(key=bad):
                with self.assertRaisesRegex(registry.RegistryError, "Invalid person key"):
                    build.write_abgeordnete_pages(site, [{**mp, "aliases": [bad]}])
                with self.assertRaisesRegex(registry.RegistryError, "Invalid person key"):
                    build.write_abgeordnete_pages(site, [{**mp, "id": bad, "aliases": []}])
        self.assertFalse((self.root / "escape.html").exists())
        self.assertEqual(outside.read_text(), "untouched")
        # Value: protects=an abgeordnete/ that links out of the output tree is refused before the stale-page sweep deletes anything there; fails_when=the writer checks only each page's parent against abg_dir, which a linked directory passes; why_new=second-round review leftovers (4); seam=none
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "precious.html").write_text("keep")
        linked = self.root / "linked-site"
        (linked / "data").mkdir(parents=True)
        (linked / "abgeordnete").symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaisesRegex(registry.RegistryError, "resolves outside"):
            build.write_abgeordnete_pages(linked, mps)
        self.assertEqual([p.name for p in elsewhere.iterdir()], ["precious.html"])


    # Value: protects=--offline over a store whose four registry tables were all dropped exits 1 with the incomplete-registry diagnostic, not a traceback or a generic read error; fails_when=require_current_schema stops checking that all registry tables exist (require_current returns silently when none exists); why_new=registry follow-ups (3): the CLI test dropped one table only; seam=none
    def test_offline_cli_reports_a_store_without_any_registry_table(self):
        site = self.site()
        r = report()
        (site / "data" / "plenarprotokoll-21-1.json").write_text(json.dumps(r))
        self.rebuild([r])
        with contextlib.closing(sqlite3.connect(self.db)) as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.executescript("; ".join(f"DROP TABLE {table}" for table in registry.REGISTRY_TABLES))
            conn.commit()
        before = self.db.read_bytes()
        done = self.offline(site)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertNotIn("Traceback", done.stderr)
        self.assertIn("error: Incomplete person registry; restore the build-store backup", done.stderr)
        self.assertEqual(before, self.db.read_bytes())

    # Value: protects=the crash sweep takes a stale staged copy with its -journal, -wal and -shm sidecars, for a store name with glob characters, and leaves another store's staged copy alone; fails_when=the sweep pattern is unescaped (a[1] matches a1, not itself) or ends in .tmp; why_new=registry follow-ups (3): only a -journal sidecar of a plain name was tested; seam=none
    def test_crash_sweep_escapes_the_store_name_and_takes_every_sidecar(self):
        self.db = self.root / "a[1].sqlite"
        self.rebuild([report()])
        private = registry.private_dir(self.db)
        stale = [private / f"a[1].sqlite.crashed.tmp{suffix}" for suffix in ("", "-journal", "-wal", "-shm")]
        bystander = private / "a1.sqlite.other.tmp"
        for path in (*stale, bystander):
            path.write_bytes(b"x")
        self.rebuild([report(), report(pid="s2")])
        self.assertEqual([path.name for path in stale if path.exists()], [])
        self.assertTrue(bystander.exists())

    def _damage_after_facts(self, damage):
        """Run the rebuild with ``damage(staged_connection)`` applied right after
        the facts are stored, i.e. after every registry check but before the
        final integrity and foreign-key checks."""
        real = build.facts.compute_and_store

        def compute_and_store(store_conn, *args, **kwargs):
            result = real(store_conn, *args, **kwargs)
            store_conn.commit()
            damage(store_conn)
            return result

        return mock.patch.object(build.facts, "compute_and_store", compute_and_store)

    # Value: protects=the final foreign_key_check of the staged store refuses a dangling row no registry check looks at, and the previous store stays byte for byte; fails_when=the end-of-rebuild foreign_key_check is dropped; why_new=third ship round (12), the end-of-rebuild foreign-key check; seam=compute_and_store is wrapped to insert a dangling vote_documents row into the staged store
    def test_a_dangling_row_in_the_staged_store_keeps_the_previous_store(self):
        self.rebuild([report()])
        before = self.db.read_bytes()

        def dangle(conn):
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("INSERT INTO vote_documents VALUES ('no-vote', 'no-document')")
            conn.commit()
            conn.execute("PRAGMA foreign_keys = ON")

        with self._damage_after_facts(dangle):
            with self.assertRaisesRegex(build.DatabaseRebuildError, "failed foreign_key_check"):
                self.rebuild([report(), report(pid="s2")])
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual(list(registry.private_dir(self.db).glob(f"{self.db.name}.*.tmp*")), [])

    # Value: protects=a staged store that fails PRAGMA integrity_check never replaces the previous one; fails_when=the end-of-rebuild integrity_check is dropped; why_new=no test reached that check; seam=the staged connection's factory answers integrity_check with a corruption line
    def test_a_staged_store_failing_integrity_check_keeps_the_previous_store(self):
        self.rebuild([report()])
        before = self.db.read_bytes()
        staging = registry.private_dir(self.db)
        real_connect = sqlite3.connect

        class Corrupt(sqlite3.Connection):
            def execute(self, sql, *args):
                if sql.strip() == "PRAGMA integrity_check":
                    return super().execute("SELECT 'row 1 missing from index'")
                return super().execute(sql, *args)

        def connect(path, *args, **kwargs):
            if Path(str(path)).parent == staging:
                kwargs["factory"] = Corrupt
            return real_connect(path, *args, **kwargs)

        with mock.patch.object(store.sqlite3, "connect", connect):
            with self.assertRaisesRegex(build.DatabaseRebuildError, "failed integrity_check"):
                self.rebuild([report(), report(pid="s2")])
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual(list(staging.glob(f"{self.db.name}.*.tmp*")), [])

if __name__ == "__main__":
    unittest.main()
