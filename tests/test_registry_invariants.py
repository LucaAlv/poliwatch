"""Invariants of person_registry.reconcile that three review passes kept breaking:
a reviewed record is never overridden by a name guess, a replay is a fixed point,
and an incremental build groups occurrences exactly like a fresh one. Named
regressions first, then a seeded randomized check over two-build sequences."""
from __future__ import annotations
import json
import random
import unittest
import _support  # noqa: F401
from _registry_fixture import RegistryFixture
import person_registry as registry
from stable_ids import roster_occurrence_id, speech_occurrence_id, stable_key


def speech(name):
    return speech_occurrence_id("p1", name)


class ReviewedRecordTests(RegistryFixture, unittest.TestCase):
    def record_of(self, conn, identity):
        return conn.execute("SELECT id FROM person_records WHERE identity_key=?", (identity,)).fetchone()[0]

    # Value: protects=a record a reviewed assignment placed on a person is never pulled onto a roster namesake by the name guess, and the namesake keeps its own person; fails_when=reconcile feeds correction: records to the guess or drops the reviewed-owner survivor; why_new=the assignment tests carried an aw id, so pass 1b's partition skip hid the unguarded name guess; seam=none
    def test_a_reviewed_assignment_is_not_overridden_by_a_name_guess(self):
        bea = stable_key("person", "xml", "2")
        with self.correction_file({"assignments": [{"occurrence_id": speech("r1"), "person_id": bea}]}):
            conn = self.open_store()
            self.up(conn, speech("r2"), "xml:2", "Bea Minister", xml="2", party="SPD")
            assigned = self.up(conn, speech("r1"), "xml:1", "Ada Example", xml="1", party="SPD")
            roster = self.up(conn, roster_occurrence_id("dip-7"), "dip:dip-7", "Ada Example", dip="dip-7", mdb=True, party="SPD")
            registry.reconcile(conn)
            persons = self.person_of_records(conn)
            self.assertEqual(persons[assigned], bea)
            self.assertNotEqual(persons[roster], bea)

    # Value: protects=a name guess that would join two persons whose official ids contradict is skipped even through a chain of reviewed merge plus guess; fails_when=the person-level dip/aw conflict guard in _guess_merges is removed; why_new=pass 1b's partition skip made every earlier test pass without this guard; seam=none
    def test_a_guess_cannot_join_persons_with_contradicting_official_ids(self):
        conn = self.open_store()
        speaker = self.up(conn, speech("a"), "xml:3", "Max Muster", xml="3", party="CDU/CSU")
        first = self.up(conn, roster_occurrence_id("dip-1"), "dip:dip-1", "Max Muster", dip="dip-1", mdb=True, party="CDU/CSU")
        second = self.up(conn, roster_occurrence_id("dip-2"), "dip:dip-2", "Bea Beta", dip="dip-2", mdb=True, party="SPD")
        persons = self.person_of_records(conn)
        with self.correction_file({"merges": [{"persons": [persons[speaker], persons[second]]}]}):
            registry.reconcile(conn)
        after = self.person_of_records(conn)
        self.assertEqual(after[speaker], after[second])
        self.assertNotEqual(after[first], after[speaker])

    # Value: protects=a person's reviewed split keeps working when a shared Personenkennung later merges its owner into another person; fails_when=the split loop raises on a retired owner again or the durable merge retires the reviewed owner's key; why_new=no test merged a split owner away, so the registry committed a state the next build rejected; seam=none
    def test_a_split_survives_a_durable_merge_of_its_owner(self):
        conn = self.open_store()
        kept = self.up(conn, speech("a"), "xml:1", "Ada A", xml="1", party="SPD")
        moved = self.up(conn, speech("m"), "xml:2", "Moe M", xml="2", party="SPD")
        self.up(conn, speech("v"), "aw:5", "Vera V", xml="4", aw=5, match="ext_id", party="SPD")
        unlisted = self.up(conn, speech("u"), "xml:3", "Uli U", xml="3", aw=5, match="ext_id", party="SPD")
        owner = self.person_of_records(conn)[unlisted]
        split = {"splits": [{"person_id": owner, "retain_records": [kept], "new_records": [moved], "new_person_id": "moe-split"}]}
        with self.correction_file(split):
            registry.reconcile(conn)
            first = self.person_of_records(conn)
            registry.reconcile(conn)
            self.assertEqual(self.person_of_records(conn), first)
        self.assertEqual(first[moved], "moe-split")
        self.assertEqual(first[kept], owner)
        self.assertEqual(first[kept], first[unlisted])

    # Value: protects=a name guess never joins two persons that each hold a reviewed record, even when unreviewed namesakes on both sides bridge them; fails_when=the partition guard in _guess_merges is removed so the guess merges two reviewed owners; why_new=the named cases have one reviewed owner per group and the random seeds never put two reviewed persons in one bucket; seam=none
    def test_a_guess_never_joins_two_reviewed_owners(self):
        conn = self.open_store()
        speaker = self.up(conn, speech("a"), "xml:1", "Max Muster", xml="1", party="CDU/CSU")
        roster = self.up(conn, roster_occurrence_id("dip-2"), "dip:dip-2", "Max Muster", dip="dip-2", mdb=True, party="CDU/CSU")
        first = self.up(conn, speech("x"), "xml:5", "Zed Zero", xml="5", party="SPD")
        second = self.up(conn, speech("y"), "xml:6", "Yan Yoo", xml="6", party="SPD")
        persons = self.person_of_records(conn)
        assignments = [{"occurrence_id": speech("x"), "person_id": persons[speaker]}, {"occurrence_id": speech("y"), "person_id": persons[roster]}]
        with self.correction_file({"assignments": assignments}):
            registry.reconcile(conn)
            after = self.person_of_records(conn)
        self.assertEqual((after[first], after[second]), (persons[speaker], persons[roster]))
        self.assertNotEqual(after[speaker], after[roster])

    # Value: protects=reconcile gives the same grouping when run twice even after two reviewed owners are merged; fails_when=the guess guard compares partition strings stamped before the reviewed merge instead of current persons; why_new=every earlier test reconciled once; seam=none
    def test_reconcile_is_a_fixed_point_when_two_reviewed_owners_merge(self):
        bea, cy = stable_key("person", "xml", "2"), stable_key("person", "xml", "5")
        corrections = {"assignments": [{"occurrence_id": speech("r1"), "person_id": bea}, {"occurrence_id": speech("r3"), "person_id": cy}],
                       "merges": [{"persons": [bea, cy]}]}
        with self.correction_file(corrections):
            conn = self.open_store()
            self.up(conn, speech("r2"), "xml:2", "Bea Minister", xml="2", party="SPD")
            self.up(conn, speech("r4"), "xml:5", "Cy Minister", xml="5", party="SPD")
            self.up(conn, speech("r1"), "xml:1", "Ada Example", xml="1", party="SPD")
            self.up(conn, speech("r3"), "xml:3", "Dora Example", xml="3", party="SPD")
            self.up(conn, roster_occurrence_id("dip-7"), "dip:dip-7", "Ada Example", dip="dip-7", mdb=True, party="SPD")
            namesake = self.up(conn, roster_occurrence_id("dip-9"), "dip:dip-9", "Bea Minister", dip="dip-9", mdb=True, party="SPD")
            registry.reconcile(conn)
            first = self.person_of_records(conn)
            registry.reconcile(conn)
            self.assertEqual(self.person_of_records(conn), first)
            # Bea's own speaker record and her roster namesake still join under the merged owners.
            self.assertEqual(first[namesake], first[self.record_of(conn, "xml:2")])

    # Value: protects=a split whose owner a reviewed merge later retires still applies on the next replay and keeps its retained records with the merged person; fails_when=the split loop raises on a retired owner instead of following its alias; why_new=the earlier test only merged the owner by a shared id, which now keeps the owner's key; seam=none
    def test_a_split_follows_its_owner_after_a_reviewed_merge(self):
        conn = self.open_store()
        kept = self.up(conn, speech("a"), "xml:1", "Ada A", xml="1", party="SPD")
        moved = self.up(conn, speech("m"), "xml:2", "Moe M", xml="2", party="SPD")
        otto = self.up(conn, speech("o"), "xml:3", "Otto O", xml="3", party="SPD")
        persons = self.person_of_records(conn)
        owner, other = persons[kept], persons[otto]
        corrections = {"merges": [{"persons": [owner, other], "survivor": other}],
                       "splits": [{"person_id": owner, "retain_records": [kept], "new_records": [moved], "new_person_id": "moe-split"}]}
        with self.correction_file(corrections):
            registry.reconcile(conn)
            first = self.person_of_records(conn)
            registry.reconcile(conn)
            self.assertEqual(self.person_of_records(conn), first)
        self.assertEqual(first[kept], other)
        self.assertEqual(first[moved], "moe-split")

    # Value: protects=a reviewed assignment applied at reconcile time to a record that still carries a trusted abgeordnetenwatch id does not drag that id's roster record onto the owner; fails_when=_load_rows keeps the aw trust of a reviewed record so the shared id merges two different people; why_new=only the randomized check reached this, via a correction file that changed after the records were bound; seam=none
    def test_a_reviewed_record_does_not_link_its_roster_record_by_aw_id(self):
        conn = self.open_store()
        ada = self.up(conn, roster_occurrence_id("dip-1"), "dip:dip-1", "Ada Example", dip="dip-1", mdb=True, party="CDU/CSU")
        speaker = self.up(conn, speech("cy"), "xml:4", "Cy Muster", xml="4", aw=103, match="ext_id", party="CDU/CSU")
        cy_roster = self.up(conn, roster_occurrence_id("dip-3"), "dip:dip-3", "Cy Muster", dip="dip-3", aw=103, match="ext_id", mdb=True, party="CDU/CSU")
        owner = self.person_of_records(conn)[ada]
        with self.correction_file({"assignments": [{"occurrence_id": speech("cy"), "person_id": owner}]}):
            registry.reconcile(conn)
            persons = self.person_of_records(conn)
        self.assertEqual(persons[speaker], owner)
        self.assertNotEqual(persons[cy_roster], owner)

    # Value: protects=a record whose occurrence vanished from the source (a corrected Rede-ID) no longer feeds the name guess or the shared-id merge, in a full build and in a direct persist; fails_when=liveness stops following the build's touched set / vacated mark so a stale record blocks the join or durably aliases a roster person into it; why_new=the randomized check compares bound occurrences only and never drops an occurrence; seam=none
    def test_a_stale_record_neither_blocks_a_guess_nor_aliases_a_new_roster_person(self):
        for full_build in (False, True):
            with self.subTest(full_build=full_build):
                # A full build sees every live occurrence again, so a vanished one is stale; a direct persist only
                # knows an occurrence moved off a record when the same occurrence is bound to another one.
                old_speech = speech(f"old{full_build}")
                new_speech = speech(f"new{full_build}") if full_build else old_speech
                roster = roster_occurrence_id(f"dip-{full_build}")
                first = self.open_store(f"first-{full_build}.sqlite")
                self.up(first, old_speech, "xml:1", "Ada Example", xml="1", aw=5, match="ext_id", party="SPD")
                registry.reconcile(first)
                second = self.next_build(first)
                # the speech's Rede-ID was corrected upstream: the old occurrence is gone, a new one names Redner-ID 9 (no aw id)
                new_record = self.up(second, new_speech, "xml:9", "Ada Example", xml="9", party="SPD")
                roster_record = self.up(second, roster, f"dip:dip-{full_build}", "Ada Example", dip=f"dip-{full_build}", aw=5, match="ext_id", mdb=True, party="SPD")
                registry.reconcile(second, full_build=full_build)
                persons = self.person_of_records(second)
                self.assertEqual(second.execute("SELECT COUNT(*) FROM person_aliases").fetchone()[0], 0)
                self.assertEqual(persons[new_record], persons[roster_record])
                stale = second.execute("SELECT id FROM person_records WHERE identity_key='xml:1'").fetchone()[0]
                self.assertNotEqual(persons[stale], persons[roster_record])

    # Value: protects=a record an assignment placed on another person carries none of the printed speaker's profile, so the owner's page shows neither the profile link nor the aw id, also after the assignment leaves the file; fails_when=bind keeps the aw profile of an assignment record or collect_abgeordnete heads the page with the placed record; why_new=the assignment tests never looked at the owner's page fields; seam=none
    def test_an_assigned_record_leaks_no_profile_onto_its_owner(self):
        import build_dip_pulse_site as build
        import persist_dip_pulse_store as store
        bea = stable_key("person", "xml", "2")
        profile = "https://www.abgeordnetenwatch.de/profile/ada-example"
        def persist(conn):
            now = store.utc_now()
            store.upsert_mp(conn, now=now, party_id=None, display_name="Bea Minister", identity_key="xml:2", xml_redner_id="2", occurrence_id=speech("b"))
            store.upsert_mp(conn, now=now, party_id=None, display_name="Ada Example", identity_key="aw:5", xml_redner_id="1", aw_politician_id=5,
                            aw_match="ext_id", profile_url=profile, occurrence_id=speech("a"))
        with self.correction_file({"assignments": [{"occurrence_id": speech("a"), "person_id": bea}]}):
            conn = self.open_store("with.sqlite")
            persist(conn)
            registry.reconcile(conn)
            pages, lookup = build.collect_abgeordnete(conn)
        owner = next(mp for mp in pages if mp["id"] == bea)
        self.assertIsNone(owner["profile_url"])
        self.assertIsNone(owner["aw_politician_id"])
        self.assertNotIn("aw:5", lookup)
        with self.correction_file({}):  # the assignment is removed: the placed record stays blocked
            again = self.next_build(conn)
            persist(again)
            registry.reconcile(again, full_build=True)
            pages, lookup = build.collect_abgeordnete(again)
        self.assertIsNone(next(mp for mp in pages if mp["id"] == bea)["aw_politician_id"])

    # Value: protects=a reviewed assignment that was later pointed at another owner leaves no reviewed marker on its old owner, so the old owner does not win a guess group by that stale marker; fails_when=_guess_merges takes reviewed owners and partitions from stale rows; why_new=no test changed an assignment between builds; seam=none
    def test_a_changed_assignment_leaves_no_stale_reviewed_marker(self):
        roster = roster_occurrence_id("dip-c")
        first = self.open_store("first.sqlite")
        c = self.up(first, roster, "dip:dip-c", "Max Muster", dip="dip-c", mdb=True, party="CDU/CSU")  # issued first: lowest ordinal
        a = self.up(first, speech("a"), "xml:3", "Max Muster", xml="3", party="CDU/CSU")
        b = self.up(first, speech("b"), "xml:7", "Bob Berg", xml="7", party="SPD")
        self.up(first, speech("s"), "xml:5", "Zed Zero", xml="5", party="SPD")
        persons = self.person_of_records(first)
        def persist(conn):
            self.up(conn, roster, "dip:dip-c", "Max Muster", dip="dip-c", mdb=True, party="CDU/CSU")
            self.up(conn, speech("a"), "xml:3", "Max Muster", xml="3", party="CDU/CSU")
            self.up(conn, speech("b"), "xml:7", "Bob Berg", xml="7", party="SPD")
            self.up(conn, speech("s"), "xml:5", "Zed Zero", xml="5", party="SPD")
        with self.correction_file({"assignments": [{"occurrence_id": speech("s"), "person_id": persons[a]}]}):
            persist(first)
            registry.reconcile(first, full_build=True)
        second = self.next_build(first)
        with self.correction_file({"assignments": [{"occurrence_id": speech("s"), "person_id": persons[b]}]}):
            persist(second)
            registry.reconcile(second, full_build=True)
        after = self.person_of_records(second)
        # the speaker and the roster namesake join; the lowest ordinal (the roster person) keeps its key
        self.assertEqual(after[a], after[c])
        self.assertEqual(after[c], persons[c])

    # Value: protects=an owner page keeps its own name when an assignment placed another speaker's record on it, whatever the content hashes of the record ids are; fails_when=the assignment-last heading sort reads a key the rows never carry (identity_key) so the hash order of the ids decides the page heading; why_new=the profile test asserted only profile fields and one id pair; seam=none
    def test_an_owner_page_is_headed_by_its_own_record_not_the_assigned_one(self):
        import build_dip_pulse_site as build
        bea = stable_key("person", "xml", "2")
        for xml in ("1", "13", "20", "31", "47", "58"):  # different record hashes: some order the placed record first
            with self.subTest(xml=xml), self.correction_file({"assignments": [{"occurrence_id": speech("a"), "person_id": bea}]}):
                conn = self.open_store(f"head-{xml}.sqlite")
                self.up(conn, speech("b"), "xml:2", "Bea Minister", xml="2")
                self.up(conn, speech("a"), f"xml:{xml}", "Ada Example", xml=xml)
                registry.reconcile(conn)
                pages, _lookup = build.collect_abgeordnete(conn)
                self.assertEqual(next(mp for mp in pages if mp["id"] == bea)["name"], "Bea Minister")

    # Value: protects=the shipped profile owner of a shared Redner-ID keeps the shared aw id and profile in registry evidence and in mps whichever occurrence is persisted first, even if one occurrence carries no aw id; fails_when=bind blocks the profile of a partition record as soon as one occurrence lacks an aw id (sticky, order dependent); why_new=the shared-profile test persists one occurrence per partition; seam=none
    def test_the_profile_owner_keeps_its_profile_whatever_the_occurrence_order(self):
        import json as _json
        results = []
        for order in ("aw first", "no aw first"):
            conn = self.open_store(f"{order.replace(' ', '-')}.sqlite")
            enriched = dict(display_name="Alexander Föhr", identity_key="xml:11005304", xml="11005304", aw=123, match="ext_id")
            plain = dict(display_name="Alexander Föhr", identity_key="xml:11005304", xml="11005304")
            for occurrence, kwargs in ((speech("1"), enriched), (speech("2"), plain)) if order == "aw first" else ((speech("2"), plain), (speech("1"), enriched)):
                import persist_dip_pulse_store as store
                store.upsert_mp(conn, now=store.utc_now(), party_id=None, display_name=kwargs["display_name"], identity_key=kwargs["identity_key"],
                                xml_redner_id=kwargs["xml"], aw_politician_id=kwargs.get("aw"), aw_match=kwargs.get("match"),
                                profile_url="https://www.abgeordnetenwatch.de/profile/foehr" if kwargs.get("aw") else None, occurrence_id=occurrence)
            registry.reconcile(conn)
            row = conn.execute("SELECT m.aw_politician_id, m.profile_url, r.evidence_json FROM mps m JOIN person_records r ON r.id = m.id").fetchone()
            results.append((row["aw_politician_id"], row["profile_url"], _json.loads(row["evidence_json"]).get("aw_politician_id")))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], 123)

    # Value: protects=a person bound only to roll-call vote-member occurrences, and never a speaker or MdB, gets no page; fails_when=_prefix_range loses its upper bound or the prefix, so the vote-member keys that sort after speech-v1- count as speeches; why_new=no test had a vote-only person who is not an MdB; seam=none
    def test_a_vote_only_person_has_no_page_and_the_speech_prefix_range_is_tight(self):
        import build_dip_pulse_site as build
        from stable_ids import vote_member_occurrence_id
        low, high = build._prefix_range("speech-v1-")
        self.assertTrue(low <= "speech-v1-abc" < high)
        self.assertFalse(low <= "vote-member-v1-abc" < high)
        self.assertFalse(low <= "roster-v1-abc" < high)
        conn = self.open_store()
        self.up(conn, vote_member_occurrence_id("v1", "Vera Vote", "SPD"), "name-party:Vera Vote|SPD", "Vera Vote", party="SPD")
        self.up(conn, speech("s"), "xml:1", "Sam Speaker", xml="1", party="SPD")
        registry.reconcile(conn)
        pages, _lookup = build.collect_abgeordnete(conn)
        self.assertEqual({mp["name"]: mp["has_page"] for mp in pages}, {"Vera Vote": False, "Sam Speaker": True})

    # Value: protects=the person-level aw arm of the guess conflict guard: two roster persons with different trusted aw ids are never joined by a name guess chain; fails_when=_guess_merges compares only dip ids; why_new=only the dip arm was exercised; seam=none
    def test_a_guess_cannot_join_persons_with_contradicting_aw_ids(self):
        conn = self.open_store()
        speaker = self.up(conn, speech("a"), "xml:3", "Max Muster", xml="3", party="CDU/CSU")
        # no DIP ids: only the aw arm of the guard can see the contradiction
        first = self.up(conn, roster_occurrence_id("r1"), "aw:41", "Max Muster", aw=41, match="ext_id", mdb=True, party="CDU/CSU")
        second = self.up(conn, roster_occurrence_id("r2"), "aw:42", "Bea Beta", aw=42, match="ext_id", mdb=True, party="SPD")
        persons = self.person_of_records(conn)
        with self.correction_file({"merges": [{"persons": [persons[speaker], persons[second]]}]}):
            registry.reconcile(conn)
        after = self.person_of_records(conn)
        self.assertEqual(after[speaker], after[second])
        self.assertNotEqual(after[first], after[speaker])

    # Value: protects=an assignment whose owner is first issued by a report processed later still binds, so a fresh or re-minted registry does not depend on report order; fails_when=bind raises for an owner that is not issued yet; why_new=tests persisted the owner's own record first; seam=none
    def test_an_assignment_binds_before_its_owner_is_issued(self):
        bea = stable_key("person", "xml", "2")
        with self.correction_file({"assignments": [{"occurrence_id": speech("r1"), "person_id": bea}]}):
            conn = self.open_store()
            assigned = self.up(conn, speech("r1"), "xml:1", "Ada Example", xml="1", party="SPD")
            self.up(conn, speech("r2"), "xml:2", "Bea Minister", xml="2", party="SPD")
            registry.reconcile(conn)
            self.assertEqual(self.person_of_records(conn)[assigned], bea)

    # Value: protects=a record no occurrence is bound to any more (a corrected Redner-ID) no longer feeds the name guess, so the incremental build groups like a fresh one; fails_when=_load_rows stops marking a vacated record as not live; why_new=no test changed the source id of an already bound occurrence and compared with a fresh build; seam=none
    def test_a_vacated_record_does_not_split_the_guess_of_an_incremental_build(self):
        speaker, roster = speech("r1"), roster_occurrence_id("dip-7")
        first = self.open_store("first.sqlite")
        self.up(first, speaker, "xml:1", "Ada Example", xml="1", party="SPD")
        self.up(first, roster, "dip:dip-7", "Ada Example", dip="dip-7", mdb=True, party="SPD")
        registry.reconcile(first)
        self.assertEqual(len(self.grouping(first)), 1)
        incremental = self.next_build(first)
        self.up(incremental, speaker, "xml:9", "Ada Example", xml="9", party="SPD")
        self.up(incremental, roster, "dip:dip-7", "Ada Example", dip="dip-7", mdb=True, party="SPD")
        registry.reconcile(incremental)
        fresh = self.open_store("fresh.sqlite")
        self.up(fresh, speaker, "xml:9", "Ada Example", xml="9", party="SPD")
        self.up(fresh, roster, "dip:dip-7", "Ada Example", dip="dip-7", mdb=True, party="SPD")
        registry.reconcile(fresh)
        self.assertEqual(self.occurrence_groups(incremental), self.occurrence_groups(fresh))
        self.assertEqual(len(self.occurrence_groups(fresh)), 1)


PARTIES = ("SPD", "CDU/CSU")
NAMES = ("Ada Example", "Bea Minister", "Cy Muster", "Dora Dorn")


class RandomizedInvariantTests(RegistryFixture, unittest.TestCase):
    """Seeded two-build sequences. A person has a name and party from a small pool
    (so namesakes happen), a Redner-ID, a DIP id and sometimes a shared abgeordnetenwatch id."""

    def world(self, rng):
        people = []
        for index in range(rng.randint(2, 6)):
            people.append({
                "name": rng.choice(NAMES), "party": rng.choice(PARTIES), "xml": str(index + 1) if rng.random() < 0.85 else None,
                "dip": f"d{index}" if rng.random() < 0.7 else None, "aw": index + 100 if rng.random() < 0.25 else None,
            })
        return people

    def persist(self, conn, people, overrides):
        for index, person in enumerate(people):
            aw = {"aw": person["aw"], "match": "ext_id"} if person["aw"] else {}
            if person["xml"]:
                xml = overrides.get(index, person["xml"])
                self.up(conn, speech(f"s{index}"), f"xml:{xml}", person["name"], xml=xml, party=person["party"], **aw)
            if person["dip"]:
                self.up(conn, roster_occurrence_id(person["dip"]), f"dip:{person['dip']}", person["name"], dip=person["dip"], mdb=True, party=person["party"], **aw)

    # Value: protects=an incremental build groups occurrences like a fresh build of the same sources after Redner-IDs are corrected; fails_when=stale or order-dependent evidence reaches the guess; why_new=hand-written cases cover single shapes, not their combinations; seam=none
    def test_incremental_builds_group_like_fresh_builds(self):
        for seed in range(24):
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                people = self.world(rng)
                overrides = {index: str(900 + index) for index, person in enumerate(people) if person["xml"] and rng.random() < 0.4}
                first = self.open_store(f"first-{seed}.sqlite")
                self.persist(first, people, {})
                registry.reconcile(first)
                incremental = self.next_build(first)
                self.persist(incremental, people, overrides)
                registry.reconcile(incremental)
                fresh = self.open_store(f"fresh-{seed}.sqlite")
                self.persist(fresh, people, overrides)
                registry.reconcile(fresh)
                self.assertEqual(self.occurrence_groups(incremental), self.occurrence_groups(fresh))

    # Value: protects=reconcile is a fixed point, never overrides a reviewed assignment and never puts two DIP ids on one person, whatever reviewed corrections are applied; fails_when=any guess or merge step reads state it has already changed or ignores a reviewed record; why_new=the three earlier critical bugs each needed a different mix of assignments, splits and merges; seam=none
    def test_reviewed_corrections_hold_and_replay_is_a_fixed_point(self):
        for seed in range(24):
            with self.subTest(seed=seed):
                rng = random.Random(1000 + seed)
                people = self.world(rng)
                first = self.open_store(f"first-{seed}.sqlite")
                self.persist(first, people, {})
                registry.reconcile(first)
                records = {row["id"]: row["home_person_id"] for row in first.execute("SELECT id, home_person_id FROM person_records")}
                homes = sorted(set(records.values()))
                current = {row["id"]: row["person_id"] for row in first.execute("SELECT id, person_id FROM person_records")}
                speeches = [speech(f"s{index}") for index, person in enumerate(people) if person["xml"]]
                corrections = {"assignments": [], "merges": [], "splits": []}
                if speeches and rng.random() < 0.7:
                    corrections["assignments"].append({"occurrence_id": rng.choice(speeches), "person_id": rng.choice(homes)})
                if len(homes) > 1 and rng.random() < 0.4:
                    corrections["merges"].append({"persons": rng.sample(homes, 2)})
                splittable = [person for person in sorted(set(current.values())) if sum(value == person for value in current.values()) > 1]
                if splittable and rng.random() < 0.5:
                    home = rng.choice(splittable)  # a person that holds several records after the first build's guesses
                    members = sorted(record for record, value in current.items() if value == home)
                    corrections["splits"].append({"person_id": home, "retain_records": members[:1], "new_records": members[1:2], "new_person_id": f"split-{seed}"})
                second = self.next_build(first)
                self.persist(second, people, {})
                with self.correction_file(corrections):
                    try:
                        registry.reconcile(second)
                    except registry.RegistryError:
                        continue  # a contradictory random correction set is rejected up front
                    state = self.person_of_records(second)
                    registry.reconcile(second)
                    self.assertEqual(self.person_of_records(second), state)
                    for assignment in corrections["assignments"]:
                        bound = second.execute("SELECT person_id FROM person_bindings WHERE id=?", (assignment["occurrence_id"],)).fetchone()[0]
                        self.assertEqual(bound, registry.resolve(second, assignment["person_id"]))
                    if not corrections["merges"]:
                        for person in set(state.values()):
                            ids = {json.loads(row["evidence_json"]).get("dip_person_id") for row in second.execute(
                                "SELECT evidence_json FROM person_records WHERE person_id=?", (person,))} - {None}
                            self.assertLessEqual(len(ids), 1, ids)


if __name__ == "__main__":
    unittest.main()
