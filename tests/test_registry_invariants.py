"""Invariants of person_registry.reconcile that review passes kept breaking: a
guess never joins persons whose official ids contradict, a replay is a fixed
point, and an incremental build groups occurrences exactly like a fresh one. Named
regressions first, then a seeded randomized check over two-build sequences."""
from __future__ import annotations
import json
import random
import unittest
import _support  # noqa: F401
from _registry_fixture import RegistryFixture
import person_registry as registry
from stable_ids import roster_occurrence_id, speech_occurrence_id


def speech(name):
    return speech_occurrence_id("p1", name)


class RegistryInvariantTests(RegistryFixture, unittest.TestCase):
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

    # Value: protects=reconcile is a fixed point, keeps a reviewed merge and never puts two DIP ids on one person; fails_when=any guess or merge step reads state it has already changed or a guess tears a reviewed merge apart; why_new=hand-written merge cases cover single shapes, not their combination with guesses; seam=none
    def test_reviewed_merges_hold_and_replay_is_a_fixed_point(self):
        for seed in range(24):
            with self.subTest(seed=seed):
                rng = random.Random(1000 + seed)
                people = self.world(rng)
                first = self.open_store(f"first-{seed}.sqlite")
                self.persist(first, people, {})
                registry.reconcile(first)
                homes = sorted({row[0] for row in first.execute("SELECT home_person_id FROM person_records")})
                corrections = {"merges": [{"persons": rng.sample(homes, 2)}] if len(homes) > 1 and rng.random() < 0.6 else []}
                second = self.next_build(first)
                self.persist(second, people, {})
                with self.correction_file(corrections):
                    registry.reconcile(second)
                    state = self.person_of_records(second)
                    registry.reconcile(second)
                    self.assertEqual(self.person_of_records(second), state)
                    for merge in corrections["merges"]:
                        self.assertEqual(len({registry.resolve(second, person) for person in merge["persons"]}), 1)
                    if not corrections["merges"]:
                        for person in set(state.values()):
                            ids = {json.loads(row["evidence_json"]).get("dip_person_id") for row in second.execute(
                                "SELECT evidence_json FROM person_records WHERE person_id=?", (person,))} - {None}
                            self.assertLessEqual(len(ids), 1, ids)

if __name__ == "__main__":
    unittest.main()
