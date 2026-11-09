"""Redner-IDs the Bundestag gives to more than one person (docs/source-errors.md E7).

These tests read the shipped scripts/person_corrections.json, so they cover the
reviewed entries themselves and not a fixture of them."""
from __future__ import annotations
import itertools
import json
import unittest
from pathlib import Path
import _support  # noqa: F401
import persist_dip_pulse_store as store
import person_registry as registry
from _registry_fixture import RegistryFixture

PROTOCOL = {"id": "p1", "dokumentnummer": "19/1", "datum": "2018-01-01"}
STAATSSEKRETAERIN = "Parl. Staatssekretärin bei der Bundesministerin für Arbeit und Soziales"

#: Every printed person under the five ids, as the source prints them:
#: (Redner-ID, printed name, Fraktion, role).
SPEAKERS = [
    ("999990108", "Anette Kramme", None, STAATSSEKRETAERIN),
    ("999990108", "Maika Friemann-Jennert", "CDU/CSU", None),
    ("999990124", "Annette Widmann-Mauz", None, "Parl. Staatssekretärin beim Bundesminister für Gesundheit"),
    ("999990124", "Dr. Andreas Bovenschulte", None, "Bürgermeister (Bremen)"),
    ("999990127", "Enak Ferlemann", None, "Parl. Staatssekretär beim Bundesminister für Verkehr und digitale Infrastruktur"),
    ("999990127", "Peter Beuth", None, "Staatsminister (Hessen)"),
    ("999990141", "Dr. Mehmet Daimagüler", None, "Beauftragter der Bundesregierung gegen Antiziganismus"),
    ("999990141", "Judith Gerlach", None, "Staatsministerin (Bayern)"),
    ("10000", "Marja-Liisa Völlers", "SPD", None),
    ("10000", "Olaf in der Beek", "FDP", None),
    ("10000", "Dr. Carsten Sieling, Bürgermeister", "Bremen", "Bürgermeister (Bremen)"),
]

#: The DIP rows of the people who hold no Redner-ID of their own, as the roster prints them.
ROSTER = [
    ("7189", "Maika Friemann-Jennert, MdB, CDU/CSU", "CDU/CSU"),
    ("7131", "Dr. Andreas Bovenschulte, MdBR (Präsident des Senats), Bremen", None),
    ("1809", "Peter Beuth, Stellv. MdBR (Minister des Innern und für Sport), Hessen", None),
    ("7727", "Dr. Mehmet Daimagüler, Beauftr. d. Bundesregierung", None),
    ("7686", "Judith Gerlach, Stellv. MdBR (Staatsministerin), Bayern", None),
]


def speaker(xml_id, name, fraktion=None, role=None, **extra):
    return {"xml_redner_id": xml_id, "display_name": name, "fraktion": fraktion, "role": role, **extra}


class SharedRednerIdTests(RegistryFixture, unittest.TestCase):
    def build(self, conn=None, speakers=SPEAKERS, roster=()):
        self.stores = getattr(self, "stores", 0) + 1
        conn = conn or self.open_store(f"build-store-{self.stores}.sqlite")
        registry.begin_build(conn)
        for dip, name, party in roster:
            self.up(conn, f"roster:{dip}", f"dip:{dip}", name, dip=dip, mdb=True, party=party)
        self.results = {}
        for index, entry in enumerate(speakers):
            occurrence = f"occ-{entry[1]}-{index}"
            self.results[occurrence] = store.resolve_speaker(
                conn, speaker(*entry), store.utc_now(), "p1", f"ID{index}", occurrence, PROTOCOL)
        registry.reconcile(conn)
        return conn

    def person_of(self, conn, occurrence):
        return conn.execute("SELECT person_id FROM person_bindings WHERE id=?", (occurrence,)).fetchone()[0]

    def person_of_identity(self, conn, identity):
        return conn.execute("SELECT person_id FROM person_records WHERE identity_key=?", (identity,)).fetchone()[0]

    # Value: protects=each of the five shared ids files every printed person apart and off the shared record; fails_when=an entry is dropped from person_corrections.json or a printed name stops matching its label; why_new=the store filed 43 units under the wrong person; seam=none
    def test_each_shared_id_gives_each_printed_person_their_own_record(self):
        conn = self.build(roster=ROSTER)
        for occurrence in (row[0] for row in conn.execute("SELECT id FROM person_bindings WHERE id LIKE 'occ-%'")):
            printed = occurrence.split("-", 1)[1].rsplit("-", 1)[0]
            record = conn.execute(
                "SELECT r.evidence_json FROM person_bindings b JOIN person_records r ON r.id=b.record_id WHERE b.id=?",
                (occurrence,)).fetchone()[0]
            self.assertIn(printed, [pair[0] for pair in json.loads(record)["pairs"]])
        persons = {self.person_of(conn, f"occ-{entry[1]}-{index}") for index, entry in enumerate(SPEAKERS)}
        self.assertEqual(len(persons), len(SPEAKERS))
        for xml_id in ("999990108", "999990124", "999990127", "999990141", "10000"):
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM person_records WHERE identity_key=?", (f"xml:{xml_id}",)).fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM mps WHERE xml_redner_id=?", (xml_id,)).fetchone()[0], 0)

    # Value: protects=one page per person: a role occurrence under a shared id lands on the person of the speaker's own id, not on a new page beside it; fails_when=own_ids is dropped so the partition forks a second person for Kramme, Widmann-Mauz or Ferlemann; why_new=a plain partition files the right person but on a page of its own; seam=none
    def test_people_with_their_own_redner_id_get_no_second_page(self):
        pairs = [("999990108", "Anette Kramme", None, STAATSSEKRETAERIN, "11003162", "Anette Kramme", "SPD"),
                 ("999990124", "Annette Widmann-Mauz", None, "Parl. Staatssekretärin beim Bundesminister für Gesundheit", "11003259", "Annette Widmann-Mauz", "CDU/CSU"),
                 ("999990127", "Enak Ferlemann", None, "Parl. Staatssekretär beim Bundesminister für Verkehr und digitale Infrastruktur", "11003525", "Enak Ferlemann", "CDU/CSU")]
        speakers = [entry for shared, name, fraktion, role, own, own_name, party in pairs
                    for entry in ((shared, name, fraktion, role), (own, own_name, party, None))]
        conn = self.build(speakers=speakers)
        for index, (_, name, *_rest) in enumerate(pairs):
            self.assertEqual(self.person_of(conn, f"occ-{name}-{index * 2}"), self.person_of(conn, f"occ-{name}-{index * 2 + 1}"))
        self.assertEqual(conn.execute("SELECT COUNT(DISTINCT person_id) FROM person_bindings").fetchone()[0], 3)

    # Value: protects=people with no Redner-ID of their own land on their DIP person, whose page already exists; fails_when=the dip: form of own_ids binds a separate record, or a replay keeps the occurrence on the old xml record; why_new=Beuth, Gerlach, Bovenschulte, Daimagüler and Friemann-Jennert hold only a DIP id; seam=none
    def test_people_with_only_a_dip_id_land_on_their_dip_person(self):
        conn = self.build(roster=ROSTER)
        for printed, index, dip in (("Dr. Andreas Bovenschulte", 3, "7131"), ("Peter Beuth", 5, "1809"), ("Dr. Mehmet Daimagüler", 6, "7727"), ("Judith Gerlach", 7, "7686")):
            self.assertEqual(self.person_of(conn, f"occ-{printed}-{index}"), self.person_of_identity(conn, f"dip:{dip}"), printed)
        row = conn.execute("SELECT display_name, xml_redner_id, dip_person_id FROM mps WHERE identity_key='dip:1809'").fetchone()
        self.assertEqual(tuple(row), ("Peter Beuth", None, "1809"))

    # Value: protects=each person keeps the name-found profile of their own name and gets no one else's; fails_when=the fold picks one profile for the id's speakers (Ferlemann showed Beuth's), a Redner-ID lookup under a shared id survives, or reparse copies a profile across the id; why_new=the store linked Ferlemann to peter-beuth and Daimagüler to judith-gerlach; seam=build_dip_pulse_site.py enrich_report_with_profiles
    def test_a_profile_stays_with_its_own_person(self):
        conn = self.open_store("profiles.sqlite")
        registry.begin_build(conn)
        now = store.utc_now()
        beuth = {"id": 135405, "match": "name", "url": "https://www.abgeordnetenwatch.de/profile/peter-beuth"}
        store.resolve_speaker(conn, speaker("999990127", "Peter Beuth", None, "Staatsminister (Hessen)", abgeordnetenwatch=beuth), now, "p1", "ID1", "occ-beuth", PROTOCOL)
        store.resolve_speaker(conn, speaker("999990127", "Enak Ferlemann", None, "Parl. Staatssekretär beim Bundesminister für Verkehr und digitale Infrastruktur",
                                            abgeordnetenwatch={"id": 7, "match": "ext_id", "url": "https://aw.example/7"}), now, "p1", "ID2", "occ-ferlemann", PROTOCOL)
        registry.reconcile(conn)
        rows = {row["identity_key"]: row for row in conn.execute("SELECT identity_key, aw_politician_id, profile_url FROM mps")}
        self.assertEqual(rows["dip:1809"]["aw_politician_id"], 135405)
        self.assertEqual((rows["xml:11003525"]["aw_politician_id"], rows["xml:11003525"]["profile_url"]), (None, None))
        self.assertFalse(registry.profile_follows_redner_id("999990127"))
        self.assertFalse(registry.profile_follows_redner_id("10000"))
        self.assertTrue(registry.profile_follows_redner_id("11005304"))  # the partition with a reviewed profile owner
        self.assertTrue(registry.profile_follows_redner_id("11003525"))

    # Value: protects=the garbled name of 20/82 becomes Dr. Lena Kreck on her DIP person; fails_when=the reviewed occurrence or the label is dropped; why_new=the store shows a person called "Dr. Dirk-UlrichLena Mende Kreck"; seam=none
    def test_the_garbled_kreck_record_is_lena_kreck(self):
        conn = self.open_store("kreck.sqlite")
        registry.begin_build(conn)
        store.resolve_speaker(conn, speaker("999990134", "Dr. Dirk-UlrichLena Mende Kreck", None, "Senatorin (Berlin)"), store.utc_now(), "5546", "ID208205200", "occ-kreck", PROTOCOL)
        registry.reconcile(conn)
        row = conn.execute("SELECT identity_key, display_name FROM mps").fetchone()
        self.assertEqual(tuple(row), ("dip:7642", "Dr. Lena Kreck"))

    # Value: protects=the unit keeps the Fraktion and Sprechrolle the source printed, which is why per-Fraktion counts hold; fails_when=the correction rewrites more than the id; why_new=Fraktion counts are claimed unchanged; seam=none
    def test_fraktion_and_sprechrolle_stay_as_printed(self):
        conn = self.build()
        fraktionen = {occurrence.split("-", 1)[1].rsplit("-", 1)[0]: result[1:] for occurrence, result in self.results.items()}
        self.assertEqual(fraktionen["Marja-Liisa Völlers"], ("SPD", None))
        self.assertEqual(fraktionen["Olaf in der Beek"], ("FDP", None))
        self.assertEqual(fraktionen["Maika Friemann-Jennert"], ("CDU/CSU", None))
        self.assertEqual(fraktionen["Anette Kramme"], (None, "bundesregierung"))
        self.assertEqual(fraktionen["Dr. Carsten Sieling, Bürgermeister"], ("Bremen", "bundesrat"))
        conn.close()

    # Value: protects=Völlers keeps her own units: those printed under 10000 land on the person of her own Redner-ID, away from in der Beek and Sieling, and her roster record joins; fails_when=own_ids is dropped so her 10000 units sit on a stub page and the third record in her name+party bucket keeps her roster apart; why_new=the wrong-person count alone does not show this; seam=none
    def test_voellers_keeps_her_own_units_on_her_own_person(self):
        speakers = [
            ("10000", "Marja-Liisa Völlers", "SPD", None),
            ("10000", "Marja-Liisa Völlers", "SPD", None),
            ("11004942", "Marja-Liisa Völlers", "SPD", None),
            ("10000", "Olaf in der Beek", "FDP", None),
            ("11004667", "Olaf in der Beek", "FDP", None),
            ("10000", "Dr. Carsten Sieling, Bürgermeister", "Bremen", "Bürgermeister (Bremen)"),
            ("11004157", "Dr. Carsten Sieling", "SPD", None),
        ]
        roster = [("6968", "Marja-Liisa Völlers, MdB, SPD", "SPD"), ("2064", "Olaf in der Beek, MdB, FDP", "FDP")]
        conn = self.build(speakers=speakers, roster=roster)
        voellers = {self.person_of(conn, f"occ-Marja-Liisa Völlers-{index}") for index in range(3)}
        self.assertEqual(voellers, {self.person_of_identity(conn, "dip:6968")})
        in_der_beek = {self.person_of(conn, "occ-Olaf in der Beek-3"), self.person_of(conn, "occ-Olaf in der Beek-4")}
        self.assertEqual(in_der_beek, {self.person_of_identity(conn, "dip:2064")})
        sieling = {self.person_of(conn, "occ-Dr. Carsten Sieling, Bürgermeister-5"), self.person_of(conn, "occ-Dr. Carsten Sieling-6")}
        self.assertEqual(len(sieling), 1)
        self.assertEqual(len(voellers | in_der_beek | sieling), 3)
        # The page shows the plain name and the party, not the printed role and "Bremen".
        row = conn.execute("SELECT m.display_name, p.name FROM mps m JOIN parties p ON p.id=m.party_id WHERE m.identity_key='xml:11004157'").fetchone()
        self.assertEqual(tuple(row), ("Dr. Carsten Sieling", "SPD"))

    # Value: protects=Friemann-Jennert keeps her Rede on the page of her roster record while Kramme's answers leave it; fails_when=her own id stops resolving to dip:7189; why_new=she holds no Redner-ID of her own and the shared one held 14 answers that are not hers; seam=none
    def test_friemann_jennert_keeps_her_rede_and_loses_the_answers(self):
        speakers = [("999990108", "Maika Friemann-Jennert", "CDU/CSU", None), ("999990108", "Anette Kramme", None, STAATSSEKRETAERIN)]
        conn = self.build(speakers=speakers, roster=[("7189", "Maika Friemann-Jennert, MdB, CDU/CSU", "CDU/CSU")])
        roster_person = self.person_of_identity(conn, "dip:7189")
        self.assertEqual(self.person_of(conn, "occ-Maika Friemann-Jennert-0"), roster_person)
        self.assertNotEqual(self.person_of(conn, "occ-Anette Kramme-1"), roster_person)

    # Value: protects=a name nobody reviewed under a listed id stops the build; fails_when=an unlabelled name joins one of the listed people; why_new=the five entries are new; seam=none
    def test_an_unreviewed_name_under_a_listed_id_is_refused(self):
        for xml_id in ("999990108", "999990124", "999990127", "999990141", "10000"):
            with self.subTest(xml_id):
                with self.assertRaisesRegex(registry.RegistryError, f"Shared Redner-ID {xml_id}"):
                    self.build(speakers=[(xml_id, "Erika Mustermann", "SPD", None)])

    # Value: protects=a Redner-ID found on a new person stops the build and names both; fails_when=the guard is dropped or reads only one name, and a later sitting (the 85 excluded ones were never scanned) files two people as one again; why_new=the list of shared ids was only found by a one-off scan; seam=none
    def test_an_unlisted_id_printed_for_two_people_is_refused(self):
        speakers = [("11009999", "Erika Mustermann", "SPD", None), ("11009999", "Max Beispiel", "FDP", None)]
        for order in itertools.permutations(speakers):
            with self.assertRaisesRegex(registry.RegistryError, r"11009999 \(Erika Mustermann, Max Beispiel\)"):
                self.build(speakers=list(order))

    # Value: protects=the guard stays quiet for people the Bundestag prints under two names: surname changes, a dropped given name, a particle; fails_when=the name comparison requires equal surnames, so a routine update refuses over a marriage; why_new=these are the name changes the scan of the 716 files showed; seam=none
    def test_a_name_change_is_not_a_shared_id(self):
        for left, right in (("Julia Obermeier", "Julia Bartz"), ("Ronja Schmitt", "Ronja Kemmer"), ("Katharina Willkomm", "Katharina Kloke"),
                            ("Barbara Lenk", "Barbara Benkstein"), ("Jan Köstering", "Jan Krampe"), ("Marina Kermer", "Angela Kermer"),
                            ("Ursula Leyen", "Ursula von der Leyen"), ("Uli Grötsch", "Ulrich Grötsch"), ("Heidrun Bluhm", "Heidrun Bluhm-Förster"),
                            ("Unbekannt", "Albert Weiler")):
            with self.subTest(left):
                self.build(speakers=[("11009999", left, "SPD", None), ("11009999", right, "SPD", None)])

    # Value: protects=the particle rule: "von" alone does not make two people one, and neither does a title; fails_when=particles or titles count as shared words, so two people slip past the guard; why_new=the guard's word sets; seam=none
    def test_a_particle_or_title_does_not_make_two_people_one(self):
        with self.assertRaisesRegex(registry.RegistryError, "11009999"):
            self.build(speakers=[("11009999", "Dr. Anna von Berg", "SPD", None), ("11009999", "Dr. Max von Tal", "SPD", None)])

    # Value: protects=a store built before the fix replays like a fresh build: every occurrence leaves the contaminated record, also where the new key is a dip: one that names no conflicting Redner-ID; fails_when=bind keeps a bound occurrence on xml:<shared id> because no hard id contradicts, so Beuth's Reden stay on Ferlemann's record; why_new=the replay's old bindings differ from a fresh build's; seam=none
    def test_an_old_contaminated_store_replays_like_a_fresh_build(self):
        with self.correction_file({}):
            old = self.open_store("old.sqlite")
            registry.begin_build(old)
            for index, entry in enumerate(SPEAKERS):
                occurrence = f"occ-{entry[1]}-{index}"
                store.resolve_speaker(old, speaker(*entry), store.utc_now(), "p1", f"ID{index}", occurrence, PROTOCOL)
            self.assertEqual(old.execute("SELECT COUNT(*) FROM person_records WHERE identity_key LIKE 'xml:%'").fetchone()[0], 5)
        replayed = self.build(self.next_build(old), roster=ROSTER)
        fresh = self.build(self.open_store("fresh.sqlite"), roster=ROSTER)
        self.assertEqual(self.occurrence_groups(replayed), self.occurrence_groups(fresh))
        self.assertEqual(replayed.execute("SELECT COUNT(*) FROM person_bindings b JOIN person_records r ON r.id=b.record_id WHERE r.identity_key LIKE 'xml:9999%' OR r.identity_key='xml:10000'").fetchone()[0], 0)
        self.assertEqual(replayed.execute("SELECT COUNT(*) FROM mps WHERE identity_key LIKE 'xml:9999%' OR identity_key='xml:10000'").fetchone()[0], 0)

    # Value: protects=grouping does not depend on which occurrence is persisted first; fails_when=the result reads "the name already bound to an id" as the first one seen; why_new=the guard and the partitions are new order-sensitive surfaces; seam=none
    def test_grouping_does_not_depend_on_persist_order(self):
        groups = set()
        for order in (SPEAKERS, list(reversed(SPEAKERS)), SPEAKERS[5:] + SPEAKERS[:5]):
            conn = self.build(self.open_store(f"order-{len(groups)}-{order[0][1]}.sqlite"), speakers=order)
            names = {}
            for row in conn.execute("SELECT id, person_id FROM person_bindings"):
                names.setdefault(row[1], set()).add(row[0].split("-", 1)[1].rsplit("-", 1)[0])
            groups.add(frozenset(frozenset(members) for members in names.values()))
        self.assertEqual(len(groups), 1)

    # Value: protects=a page and a store read the same corrected speaker, and the cached report is not rewritten; fails_when=corrected_speaker mutates its input or leaves the shared id; why_new=own_ids is new; seam=none
    def test_corrected_speaker_gives_the_own_id_on_a_copy(self):
        printed = speaker("10000", "Olaf in der Beek", "FDP", abgeordnetenwatch={"id": 5, "match": "ext_id"})
        corrected = registry.corrected_speaker(printed, "p1", "ID1")
        self.assertEqual((corrected["xml_redner_id"], corrected["dip_person_id"]), ("11004667", None))
        self.assertEqual(corrected["abgeordnetenwatch"], {})
        self.assertEqual(printed["xml_redner_id"], "10000")
        beuth = registry.corrected_speaker(speaker("999990127", "Peter Beuth"), "p1", "ID1")
        self.assertEqual((beuth["xml_redner_id"], beuth["dip_person_id"]), (None, "1809"))
        self.assertEqual(registry.corrected_speaker(speaker("10000", "Erika Mustermann"), "p1", "ID1")["xml_redner_id"], "10000")

    # Value: protects=these tests read the shipped corrections file, not a fixture of it; fails_when=CORRECTIONS_PATH points elsewhere, so the five entries go untested; why_new=the module docstring claims it; seam=none
    def test_reads_the_shipped_corrections_file(self):
        shipped = Path(__file__).resolve().parents[1] / "scripts/person_corrections.json"
        self.assertEqual(registry.CORRECTIONS_PATH.resolve(), shipped)

    # Value: protects=a malformed own_ids stops the build with a diagnostic; fails_when=the loader accepts a shape corrected_speaker misreads; why_new=own_ids is new; seam=none
    def test_malformed_own_ids_are_refused(self):
        base = {"xml_redner_id": "9", "labels": {"Ada Example": "ada"}}
        for own_ids, message in (
            ([], "own_ids must be an object"),
            ({"bea": "xml:1"}, "own_ids owner 'bea' is not one of its label owners"),
            ({"ada": 1}, "own id of partition owner 'ada' must be a nonempty string"),
            ({"ada": "1"}, "must read xml:<Redner-ID> or dip:<DIP id>"),
            ({"ada": "aw:1"}, "must read xml:<Redner-ID> or dip:<DIP id>"),
            ({"ada": "xml:9"}, "own id xml:9 of partition owner 'ada' is itself partitioned"),
        ):
            with self.subTest(message), self.correction_file({"partitions": [{**base, "own_ids": own_ids}]}):
                with self.assertRaisesRegex(registry.RegistryError, message):
                    registry.corrections()


if __name__ == "__main__":
    unittest.main()
