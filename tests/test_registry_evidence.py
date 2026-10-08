"""Registry evidence is a function of the build's input, not of persist order.

A source record can be printed under several names, parties and Redner-IDs (a
Fraktion switcher; two Redner-IDs sharing one trusted abgeordnetenwatch id). The
evidence the registry keeps for it, the grouping it yields and the biography
the store shows must be identical for every order the occurrences are persisted
in, within one build and across an incremental and a fresh one."""
from __future__ import annotations
import copy
import functools
import itertools
import json
import random
import unittest
import _support  # noqa: F401
from _registry_fixture import RegistryFixture
import person_registry as registry
from stable_ids import roster_occurrence_id, speech_occurrence_id


def speech(name):
    return speech_occurrence_id("p1", name)


def occ(key, identity, name, **kw):
    return dict(occurrence=speech(key) if kw.pop("speech", True) else roster_occurrence_id(key), identity=identity, name=name, **kw)


class EvidenceHelpers(RegistryFixture):
    def build(self, occurrences, order, name, previous=None):
        conn = self.next_build(previous) if previous is not None else self.open_store(name)
        for index in order:
            item = dict(occurrences[index])
            self.up(conn, item.pop("occurrence"), item.pop("identity"), item.pop("name"), **item)
        registry.reconcile(conn, full_build=True)
        return conn

    def snapshot(self, conn):
        """Everything order could leak into: evidence bytes, the mps biography row, the grouping."""
        evidence = {row["identity_key"]: row["evidence_json"] for row in conn.execute("SELECT * FROM person_records")}
        mps = {row["identity_key"]: tuple(row) for row in conn.execute(
            "SELECT m.identity_key, m.display_name, p.name AS party, m.xml_redner_id, m.dip_person_id, m.aw_politician_id, m.aw_match, m.profile_url, m.is_mdb,"
            " m.title, m.function, m.wahlperiode, m.birth_year, m.gender, m.profession, m.wahlkreis, m.bundesland, m.person_roles_json"
            " FROM mps m LEFT JOIN parties p ON p.id = m.party_id")}
        return evidence, mps, self.grouping(conn)

    def assert_order_independent(self, occurrences, *, expect_grouping=None, tag=""):
        indexes = range(len(occurrences))
        reference = None
        for order in itertools.permutations(indexes):
            with self.subTest(order=order):
                conn = self.build(occurrences, order, f"fresh{tag}-{'-'.join(map(str, order))}.sqlite")
                snap = self.snapshot(conn)
                conn.close()
                reference = reference or snap
                self.assertEqual(snap[0], reference[0], "evidence differs by persist order")
                self.assertEqual(snap[1], reference[1], "mps biography row differs by persist order")
                self.assertEqual(snap[2], reference[2], "grouping differs by persist order")
        if expect_grouping is not None:
            self.assertEqual(reference[2], {frozenset(group) for group in expect_grouping})
        return reference


class EvidenceOrderTests(EvidenceHelpers, unittest.TestCase):
    # Value: protects=a Fraktion switcher joins the roster record of the party it is listed under, whichever occurrence is persisted last; fails_when=bind keeps only the last occurrence's name and party so the name+party bucket depends on persist order; why_new=no test persists one record under two parties; seam=none
    def test_a_fraktion_switcher_groups_the_same_in_every_order(self):
        occurrences = [
            occ("a", "xml:1", "Ada Example", xml="1", party="SPD"),
            occ("b", "xml:1", "Ada Example", xml="1", party="CDU/CSU"),
            occ("d", "dip:d1", "Ada Example", dip="d1", mdb=True, party="CDU/CSU", speech=False),
        ]
        self.assert_order_independent(occurrences, expect_grouping=[{"xml:1", "dip:d1"}])

    # Value: protects=two Redner-IDs on one trusted aw id link the xml-keyed record of either id (both, not just the smaller) in every order, and show one biography name; fails_when=bind keeps only the last occurrence's Redner-ID or name; why_new=the shared aw id case was only reproduced by hand; seam=none
    def test_two_redner_ids_sharing_an_aw_id_group_the_same_in_every_order(self):
        occurrences = [
            occ("a", "aw:5", "Ada Example", xml="1", aw=5, match="ext_id", party="SPD"),
            occ("b", "aw:5", "Dr. Ada Example", xml="2", aw=5, match="ext_id", party="SPD"),
            occ("c", "xml:1", "Ada Example", xml="1", party="SPD"),
            occ("d", "xml:2", "Dr. Ada Example", xml="2", party="SPD"),
        ]
        self.assert_order_independent(occurrences, expect_grouping=[{"aw:5", "xml:1", "xml:2"}])

    # Value: protects=an incremental build and a fresh one agree on evidence and grouping for a multi-name record in any persist order; fails_when=evidence from an earlier build or insertion order survives the first touch; why_new=the randomized invariants persist one name per record; seam=none
    def test_incremental_and_fresh_builds_agree_for_multi_name_records(self):
        occurrences = [
            occ("a", "xml:1", "Ada Example", xml="1", party="SPD"),
            occ("b", "xml:1", "Ada Example", xml="1", party="CDU/CSU"),
            occ("d", "dip:d1", "Ada Example", dip="d1", mdb=True, party="CDU/CSU", speech=False),
        ]
        fresh = self.snapshot(self.build(occurrences, (0, 1, 2), "fresh.sqlite"))
        for first_order, second_order in itertools.product(itertools.permutations(range(3)), repeat=2):
            with self.subTest(first=first_order, second=second_order):
                first = self.build(occurrences, first_order, f"i1-{first_order}-{second_order}.sqlite")
                second = self.build(occurrences, second_order, "", previous=first)
                snap = self.snapshot(second)
                self.assertEqual(snap[0], fresh[0])
                self.assertEqual(snap[1], fresh[1])
                self.assertEqual(snap[2], fresh[2])
                fresh_second = self.build(occurrences, second_order, f"f-{first_order}-{second_order}.sqlite")
                self.assertEqual(self.occurrence_groups(second), self.occurrence_groups(fresh_second))
                for conn in (first, second, fresh_second):
                    conn.close()

    # Value: protects=replay is a fixed point once evidence has its folded shape: a third build over the same input changes no byte; fails_when=evidence carries insertion-order state between builds; why_new=the fixed-point invariant never covered multi-name records; seam=none
    def test_replaying_the_same_input_is_a_fixed_point(self):
        occurrences = [
            occ("a", "xml:1", "Ada Example", xml="1", party="SPD"),
            occ("b", "xml:1", "Ada Example", xml="1", party="CDU/CSU"),
            occ("d", "dip:d1", "Ada Example", dip="d1", mdb=True, party="CDU/CSU", speech=False),
        ]
        first = self.build(occurrences, (0, 1, 2), "one.sqlite")
        second = self.build(occurrences, (2, 1, 0), "", previous=first)
        third = self.build(occurrences, (1, 0, 2), "", previous=second)
        self.assertEqual(self.snapshot(second), self.snapshot(third))
        self.assertEqual(self.snapshot(first)[2], self.snapshot(third)[2])

    # Value: protects=an attribute the source stopped supplying leaves the record's evidence when the input returns without it, and a vanished occurrence leaves no trace of its name; fails_when=first-touch reset is skipped so earlier names or Redner-IDs keep matching; why_new=vanished attributes were only tested for ids; seam=none
    def test_vanished_attributes_leave_evidence_and_reappear_with_input(self):
        both = [
            occ("a", "xml:1", "Ada Example", xml="1", party="SPD"),
            occ("b", "xml:1", "Ada Example", xml="1", party="CDU/CSU"),
        ]
        first = self.build(both, (0, 1), "one.sqlite")
        only_spd = self.build(both[:1], (0,), "", previous=first)
        evidence = json.loads(only_spd.execute("SELECT evidence_json FROM person_records WHERE identity_key='xml:1'").fetchone()[0])
        self.assertEqual(evidence["party"], "SPD")
        self.assertNotIn("CDU/CSU", json.dumps(evidence))
        back = self.build(both, (1, 0), "", previous=only_spd)
        self.assertEqual(self.snapshot(back), self.snapshot(first))

    # Value: protects=a union of a record's name/party pairs never bridges two partitions or contradicting hard ids; fails_when=pair-set matching ignores the partition guard or the id re-check; why_new=pair sets give a record several buckets; seam=none
    def test_pair_sets_do_not_bridge_contradicting_ids(self):
        occurrences = [
            occ("a", "xml:1", "Ada Example", xml="1", party="SPD"),
            occ("b", "xml:1", "Ada Example", xml="1", party="CDU/CSU"),
            occ("d1", "dip:d1", "Ada Example", dip="d1", mdb=True, party="SPD", speech=False),
            occ("d2", "dip:d2", "Ada Example", dip="d2", mdb=True, party="CDU/CSU", speech=False),
        ]
        snap = self.assert_order_independent(occurrences)
        groups = snap[2]
        # The switcher is ambiguous between two roster records: it joins neither, and the two DIP ids stay apart.
        self.assertIn(frozenset({"xml:1"}), groups)
        self.assertIn(frozenset({"dip:d1"}), groups)
        self.assertIn(frozenset({"dip:d2"}), groups)


class EvidenceDecisionTests(EvidenceHelpers, unittest.TestCase):
    # Value: protects=a record that lost one occurrence to another record but kept another carries the same evidence whichever occurrence is persisted first; fails_when=the vacated mark is set on a record this build already touched; why_new=the mark was written by whichever occurrence happened to move second; seam=none
    def test_a_record_that_lost_an_occurrence_is_not_marked_by_persist_order(self):
        before = [occ("a", "xml:1", "Ada Example", xml="1", party="SPD"), occ("b", "xml:1", "Ada Example", xml="1", party="SPD")]
        after = [occ("a", "xml:9", "Ada Example", xml="9", party="SPD"), occ("b", "xml:1", "Ada Example", xml="1", party="SPD")]
        first = self.build(before, (0, 1), "one.sqlite")
        reference = None
        for order in itertools.permutations(range(2)):
            with self.subTest(order=order):
                snap = self.snapshot(self.build(after, order, "", previous=first))
                reference = reference or snap
                self.assertEqual(snap, reference)
                self.assertNotIn("vacated", reference[0]["xml:1"])

    # Value: protects=whether an occurrence stays on its record is decided against the record's evidence from before the build, not against what other occurrences already folded in; fails_when=bind compares the bound record's current (partly rebuilt) evidence; why_new=a Redner-ID written earlier in the same build decided the move; seam=none
    def test_an_occurrence_stays_or_moves_whatever_the_persist_order(self):
        before = [occ("a", "aw:5", "Ada Example", xml="1", aw=5, match="ext_id", party="SPD"),
                  occ("b", "aw:5", "Ada Example", xml="2", aw=5, match="ext_id", party="SPD")]
        # The profile of the first occurrence vanished: its identity is now xml:1, but its Redner-ID is still one the record held.
        after = [occ("a", "xml:1", "Ada Example", xml="1", party="SPD"),
                 occ("b", "aw:5", "Ada Example", xml="2", aw=5, match="ext_id", party="SPD")]
        first = self.build(before, (0, 1), "one.sqlite")
        reference = None
        for order in itertools.permutations(range(2)):
            with self.subTest(order=order):
                conn = self.build(after, order, "", previous=first)
                snap = self.snapshot(conn)
                reference = reference or snap
                self.assertEqual(snap, reference)
                self.assertEqual(len(self.occurrence_groups(conn)), 1)

    # Value: protects=the fold of occurrence evidence is commutative, associative, idempotent; names, parties, Redner-IDs kept as sets; a trusted aw unit chosen whole; roster biography beats a smaller cached value; fails_when=any field takes the last value or an untrusted lookup wins on id order; why_new=this is the contract the order-independence rests on; seam=none
    def test_fold_is_commutative_associative_and_idempotent(self):
        items = [
            dict(display_name="Ada Example", party="SPD", xml_redner_id="2", is_mdb=False, ever_mdb=False, function="Abgeordnete", title="Dr."),
            dict(display_name="Dr. Ada Example", party="CDU/CSU", xml_redner_id="1", is_mdb=True, ever_mdb=True,
                 aw_politician_id=7, aw_match="ext_id", profile_url="https://example.test/7", function="Minister", title="Prof. Dr."),
            # The untrusted lookup has the smaller id, so only the trusted-first rule (not id order) picks the other unit.
            dict(display_name="Ada Example", xml_redner_id="1", aw_politician_id=5, aw_match="name", profile_url="https://example.test/5"),
        ]
        folded = {json.dumps(functools.reduce(registry._fold, (dict(i) for i in order), {}), sort_keys=True)
                  for order in itertools.permutations(items)}
        self.assertEqual(len(folded), 1)
        result = json.loads(next(iter(folded)))
        self.assertEqual(result["pairs"], [["Ada Example", "SPD"], ["Ada Example", None], ["Dr. Ada Example", "CDU/CSU"]])
        self.assertEqual(result["xml_redner_ids"], ["1", "2"])
        self.assertEqual(result["xml_redner_id"], "1")  # the flat id is the smallest of the set
        self.assertEqual((result["display_name"], result["party"]), ("Dr. Ada Example", "CDU/CSU"))
        self.assertEqual((result["aw_politician_id"], result["aw_match"], result["profile_url"]), (7, "ext_id", "https://example.test/7"))
        # A roster occurrence (is_mdb) is the authority for biography attributes even when a cached value is the smaller string.
        self.assertEqual((result["function"], result["title"]), ("Minister", "Prof. Dr."))
        self.assertEqual(result["roster_bio"], {"function": "Minister", "title": "Prof. Dr."})
        self.assertTrue(result["is_mdb"] and result["ever_mdb"])
        once = registry._fold({}, dict(items[0]))
        self.assertEqual(registry._fold(once, dict(items[0])), once)
        a, b, c = (registry._fold({}, dict(i)) for i in items)
        self.assertEqual(registry._fold(registry._fold(a, b), c), registry._fold(a, registry._fold(b, c)))

    # Value: protects=the name and party a record shows prefer a real name over the Unbekannt placeholder, a party over none, then the fullest name, in every fold order; fails_when=a placeholder or party-less pair wins or the tie-break reads fold order; why_new=the fold test only covers one title-versus-plain tie; seam=none
    def test_the_shown_name_and_party_follow_the_representative_rules(self):
        cases = [
            ([dict(display_name="Unbekannt", party="SPD"), dict(display_name="Bea Beta", party="CDU/CSU")], ("Bea Beta", "CDU/CSU")),
            ([dict(display_name="Ada Example", party=None), dict(display_name="Ada Example", party="SPD")], ("Ada Example", "SPD")),
            ([dict(display_name="Ada Example", party="SPD"), dict(display_name="Prof. Dr. Ada Example", party="SPD")], ("Prof. Dr. Ada Example", "SPD")),
            # The best name has no party: the party is still the best of the pairs that name one.
            ([dict(display_name="Unbekannt", party="SPD"), dict(display_name="Ada Example", party=None),
              dict(display_name="Unbekannt", party="CDU/CSU")], ("Ada Example", "CDU/CSU")),
        ]
        for items, expected in cases:
            for order in itertools.permutations(items):
                with self.subTest(expected=expected, order=order):
                    result = functools.reduce(registry._fold, (dict(i) for i in order), {})
                    self.assertEqual((result["display_name"], result.get("party")), expected)

    # Value: protects=a name-found aw profile joins the record holding that id when any one printed name of the record matches, and not when none does; fails_when=corroboration compares whole name sets or only the first name; why_new=pass 1b was only tested with one name per record; seam=none
    def test_any_shared_printed_name_corroborates_a_name_found_profile(self):
        def row(rid, pairs, **kw):
            return dict(id=rid, display_name=pairs[0][0], party=pairs[0][1], pairs=pairs, person_id=rid, live=True, **kw)
        holder = row("b", [["Ada Beispiel", "SPD"]], xml_redner_id="2", aw_politician_id=5, aw_match="ext_id")
        renamed = row("a", [["Ada Example", "SPD"], ["Ada Beispiel", "SPD"]], xml_redner_id="1", aw_politician_id=5, aw_match="name")
        components, _ = registry.match_rows([renamed, holder])
        self.assertEqual(len(components), 1)
        stranger = row("a", [["Ada Example", "SPD"], ["Ada Muster", "SPD"]], xml_redner_id="1", aw_politician_id=5, aw_match="name")
        components, _ = registry.match_rows([stranger, holder])
        self.assertEqual(len(components), 2)

    # Value: protects=a record's several name/party pairs never join records of two partitions or with contradicting hard ids; fails_when=pair-set matching skips the partition guard or the id re-check in match_rows; why_new=pair sets give one record several buckets; seam=none
    def test_pair_sets_respect_partitions_and_hard_ids(self):
        def row(rid, pairs, **kw):
            return dict(id=rid, display_name=pairs[0][0], party=pairs[0][1], pairs=pairs, person_id=rid, live=True, **kw)
        ada = [["Ada Example", "SPD"], ["Ada Example", "CDU/CSU"]]
        components, _ = registry.match_rows([
            row("a", ada, xml_redner_id="1", partition="x"),
            row("b", [["Ada Example", "SPD"]], dip_person_id="d1", is_mdb=True, partition="y"),
        ])
        self.assertEqual(len(components), 2)
        components, _ = registry.match_rows([
            row("a", ada, xml_redner_id="1"),
            row("b", [["Ada Example", "SPD"]], xml_redner_id="2", dip_person_id="d1", is_mdb=True),
        ])
        self.assertEqual(len(components), 2)  # contradicting Redner-IDs: no join
        components, _ = registry.match_rows([
            row("a", ada, xml_redner_id="1"),
            row("b", [["Ada Example", "CDU/CSU"]], dip_person_id="d1", is_mdb=True),
        ])
        self.assertEqual(len(components), 1)

    # Value: protects=a stale roster record printed under two parties joins neither live speaker its keys match, while one printed under a single party still joins its speaker; fails_when=the stale-partner pass takes one of several name+party keys and so joins whichever speaker that key reaches; why_new=staged roster tests give the stale record one name and party; seam=none
    def test_a_stale_roster_record_with_two_parties_joins_no_speaker(self):
        def groups(roster_parties):
            roster = [occ(f"d{i}", "dip:d1", "Ada Example", dip="d1", mdb=True, party=party, speech=False)
                      for i, party in enumerate(roster_parties)]
            then = [occ("s1", "xml:1", "Ada Example", xml="1", party="FDP"), occ("s2", "xml:2", "Ada Example", xml="2", party="AfD")]
            now = [occ("s1", "xml:1", "Ada Example", xml="1", party="SPD"), occ("s2", "xml:2", "Ada Example", xml="2", party="CDU/CSU")]
            first = self.build(then + roster, range(2 + len(roster)), "one.sqlite")
            self.assertEqual(len(self.grouping(first)), 3)  # nothing joins while the speakers sit in other parties
            second = self.build(now, (0, 1), "", previous=first)  # the roster no longer lists d1: stale
            return self.grouping(second)

        self.assertEqual(groups(["SPD"]), {frozenset({"xml:1", "dip:d1"}), frozenset({"xml:2"})})
        self.assertEqual(groups(["SPD", "CDU/CSU"]), {frozenset({"xml:1"}), frozenset({"xml:2"}), frozenset({"dip:d1"})})


class RandomEvidenceTests(EvidenceHelpers, unittest.TestCase):
    # Value: protects=every mps column a record shows (party, biography attributes, abgeordnetenwatch unit) is the same whichever occurrence is persisted last; fails_when=upsert_mp COALESCEs the last occurrence's value over the folded evidence; why_new=the order tests varied only name, party and ids, never biography columns or a party-less representative; seam=none
    def test_the_mps_row_is_order_independent_for_every_column(self):
        scenarios = {
            "party-less best name": [
                occ("a", "xml:1", "Unbekannt", xml="1", party="SPD"),
                occ("b", "xml:1", "Ada Example", xml="1"),
                occ("c", "xml:1", "Unbekannt", xml="1", party="CDU/CSU"),
            ],
            "biography attributes": [
                occ("a", "xml:1", "Ada Example", xml="1", party="SPD", function="Bundesminister", wahlkreis="Köln I", title="Dr.", birth_year=1980),
                occ("b", "xml:1", "Ada Example", xml="1", party="SPD", function="Abgeordnete", profession="Juristin", birth_year=1970, gender="w"),
                occ("c", "xml:1", "Ada Example", xml="1", party="SPD", wahlkreis="Aachen", bundesland="NRW", person_roles_json='["a"]'),
                occ("d", "xml:1", "Ada Example", xml="1", party="SPD", person_roles_json='["b"]'),
            ],
            "a cached dossier's older biography beside the live roster": [
                occ("1", "dip:1", "Ada Example", dip="1", party="SPD", title="Dr.", wahlperiode="[19, 20]", function="Abgeordnete", speech=False),
                occ("2", "dip:1", "Ada Example", dip="1", party="SPD", mdb=True, title="Prof. Dr.", wahlperiode="[20, 21]", function="Bundesministerin", speech=False),
            ],
            "trusted aw unit without a profile beside a named unit with one": [
                occ("a", "xml:1", "Ada Example", xml="1", party="SPD", aw=5, match="ext_id"),
                occ("b", "xml:1", "Ada Example", xml="1", party="SPD", aw=7, match="name", profile_url="https://example.test/7"),
            ],
        }
        for index, (label, occurrences) in enumerate(scenarios.items()):
            with self.subTest(label):
                self.assert_order_independent(occurrences, tag=str(index))

    # Value: protects=the live roster's biography (title, Wahlperioden, function) is what the mps row shows, not an older value cached in a dossier's sampled people, in either persist order; fails_when=a biography value is chosen by string order or persist order instead of roster authority; why_new=the order tests only compared orders with each other, which a smallest-value rule also passes; seam=none
    def test_the_live_roster_biography_beats_an_older_cached_dossier_value(self):
        occurrences = [
            occ("1", "dip:1", "Ada Example", dip="1", party="SPD", title="Dr.", wahlperiode="[19, 20]", function="Abgeordnete", speech=False),
            occ("2", "dip:1", "Ada Example", dip="1", party="SPD", mdb=True, title="Prof. Dr.", wahlperiode="[20, 21]", speech=False),
        ]
        _, mps, _ = self.assert_order_independent(occurrences, tag="roster")
        (row,) = mps.values()
        columns = ("identity_key", "display_name", "party", "xml_redner_id", "dip_person_id", "aw_politician_id", "aw_match",
                   "profile_url", "is_mdb", "title", "function", "wahlperiode")
        shown = dict(zip(columns, row))
        self.assertEqual((shown["title"], shown["wahlperiode"]), ("Prof. Dr.", "[20, 21]"))
        self.assertEqual(shown["function"], "Abgeordnete")  # the roster supplied none, so the cached value stands in

    # Value: protects=the abgeordnetenwatch fields of a record are chosen as one unit, also when the winner lacks a profile URL or no unit has an id; fails_when=the fold keeps the loser's profile_url or lets the last occurrence win; why_new=the fold test only used units with all three fields; seam=none
    def test_fold_chooses_the_aw_fields_as_one_unit(self):
        base = dict(display_name="Ada Example", party="SPD")
        cases = {
            "winner has no url": ([dict(base, aw_politician_id=5, aw_match="ext_id"),
                                   dict(base, aw_politician_id=7, aw_match="name", profile_url="u7")], (5, "ext_id", None)),
            "no unit has an id": ([dict(base, profile_url="u1"), dict(base, profile_url="u2")], (None, None, "u1")),
            "an id beats a bare profile": ([dict(base, profile_url="u1"), dict(base, aw_politician_id=3, aw_match="name")], (3, "name", None)),
        }
        for label, (items, expected) in cases.items():
            for order in itertools.permutations(items):
                with self.subTest(label, order=[i.get("aw_politician_id") for i in order]):
                    result = functools.reduce(registry._fold, (dict(i) for i in order), {})
                    self.assertEqual((result.get("aw_politician_id"), result.get("aw_match"), result.get("profile_url")), expected)

    # Value: protects=grouping and evidence of a seeded world with multi-name, multi-party and multi-Redner-ID records are independent of persist order and of incremental versus fresh builds; fails_when=any evidence or match step reads insertion order; why_new=combinations of the hand-written shapes; seam=none
    def test_random_worlds_are_order_independent(self):
        names = ["Ada Example", "Dr. Ada Example", "Bea Beta", "Cem Gamma"]
        parties = ["SPD", "CDU/CSU", "DIE LINKE"]
        for seed in range(12):
            rng = random.Random(seed)
            occurrences = []
            for index in range(rng.randint(2, 5)):
                aw = {"aw": 100 + index, "match": "ext_id"} if rng.random() < 0.3 else {}
                for sub in range(rng.randint(1, 3)):
                    xml = str(index + 1) if rng.random() < 0.8 else str(index + 50)
                    identity = f"aw:{aw['aw']}" if aw else f"xml:{xml}"
                    occurrences.append(occ(f"s{index}-{sub}", identity, rng.choice(names), xml=xml, party=rng.choice(parties), **aw))
                if rng.random() < 0.5:
                    occurrences.append(occ(f"d{index}", f"dip:d{index}", rng.choice(names), dip=f"d{index}", mdb=True, party=rng.choice(parties), speech=False))
            reference = None
            for shuffle in range(4):
                order = list(range(len(occurrences)))
                random.Random(seed * 10 + shuffle).shuffle(order)
                first = self.build(occurrences, order, f"r{seed}-{shuffle}.sqlite")
                incremental = self.build(occurrences, list(reversed(order)), "", previous=first)
                for conn in (first, incremental):
                    snap = self.snapshot(conn)
                    reference = reference or snap
                    with self.subTest(seed=seed, shuffle=shuffle):
                        self.assertEqual(snap[0], reference[0])
                        self.assertEqual(snap[1], reference[1])
                        self.assertEqual(snap[2], reference[2])
                first.close()
                incremental.close()


if __name__ == "__main__":
    unittest.main()
