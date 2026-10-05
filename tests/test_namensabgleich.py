"""Zusammenführung (CONTEXT.md: Personenkennung, Namensabgleich): records join by a
shared Personenkennung, otherwise only when a name+party bucket holds exactly one
record from the roster/roll-call side and one from the protocol-speaker side. An
id found by searching a name is a guess and identifies nobody."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401
import person_registry
import build_dip_pulse_site as build
import derive
import persist_dip_pulse_store as pulse_store
import render_dip_pulse_html as html


class TrustedIdTests(unittest.TestCase):
    def test_only_an_id_looked_up_by_the_redner_id_is_a_personenkennung(self) -> None:
        self.assertEqual(derive.trusted_aw_id({"id": 5, "match": "ext_id"}), 5)
        self.assertIsNone(derive.trusted_aw_id({"id": 5, "match": "name"}))
        self.assertIsNone(derive.trusted_aw_id({"id": 5, "match": "something-new"}))
        # A cache from before the kind was kept: counts as found by name.
        self.assertIsNone(derive.trusted_aw_id({"id": 5}))
        self.assertIsNone(derive.trusted_aw_id({"match": "ext_id"}))
        self.assertIsNone(derive.trusted_aw_id(None))

    def test_the_identity_key_uses_an_aw_id_only_when_it_is_trusted(self) -> None:
        self.assertEqual(pulse_store.mp_identity(aw_politician_id=5, aw_match="ext_id", xml_redner_id="1"), "aw:5")
        self.assertEqual(pulse_store.mp_identity(aw_politician_id=5, aw_match="name", xml_redner_id="1"), "xml:1")
        self.assertEqual(pulse_store.mp_identity(aw_politician_id=5, xml_redner_id="1"), "xml:1")
        self.assertEqual(pulse_store.mp_identity(aw_politician_id=5, aw_match="name", dip_person_id="d"), "dip:d")


class ZusammenfuehrungTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.conn = pulse_store.connect(Path(self._tmp.name) / "store.sqlite")
        self.addCleanup(self.conn.close)
        pulse_store.initialize(self.conn)
        self.now = pulse_store.utc_now()

    def party(self, name: str = "SPD") -> int:
        return pulse_store.upsert_party(self.conn, name, self.now)

    def speaker(
        self, name: str, xml_id: str, *, aw: int | None = None, match: str | None = None, party: str = "SPD",
        separate: bool = False, page: bool = False,
    ) -> int:
        """A record a Plenarprotokoll named as a Redner. ``separate`` keys it by
        its Redner-ID even when it carries a trusted aw id (which would name the
        same identity as another record's), to give the join something to do;
        ``page`` gives it a page."""
        identity = "xml:" + xml_id if separate else pulse_store.mp_identity(aw_politician_id=aw, aw_match=match, xml_redner_id=xml_id)
        return pulse_store.upsert_mp(
            self.conn, now=self.now, display_name=name, party_id=self.party(party), identity_key=identity,
            xml_redner_id=xml_id, aw_politician_id=aw, aw_match=match, is_mdb=page,
        )

    def roster(
        self, name: str, dip_id: str, *, party: str = "SPD", aw: int | None = None, match: str | None = None,
        separate: bool = False,
    ) -> int:
        """A DIP person (roster side)."""
        identity = "dip:" + dip_id if separate else pulse_store.mp_identity(aw_politician_id=aw, aw_match=match, dip_person_id=dip_id)
        return pulse_store.upsert_mp(
            self.conn, now=self.now, display_name=name, party_id=self.party(party), identity_key=identity,
            dip_person_id=dip_id, aw_politician_id=aw, aw_match=match, is_mdb=True,
        )

    def collect(self):
        totals = person_registry.reconcile(self.conn)
        mps, lookup = build.collect_abgeordnete(self.conn)
        canonical = {row["id"]: row["person_id"] for row in self.conn.execute("SELECT id, person_id FROM mps")}
        stats = {f"merges_{kind}": totals[kind] for kind in ("ext_id", "corroborated_name", "unique_name")}
        stats.update(buckets_split_namesakes=totals["buckets_split_namesakes"], buckets_split_3plus=totals["buckets_split_3plus"])
        return mps, lookup, canonical, stats

    def test_queued_name_matches_cannot_bridge_conflicting_roster_ids(self) -> None:
        # One speaker has two party spellings across source records. Each
        # spelling matches a different roster person before either join runs.
        for identity, party in (("speaker-old", "SPD"), ("speaker-new", "CDU/CSU")):
            pulse_store.upsert_mp(
                self.conn, now=self.now, display_name="Ada Example", party_id=self.party(party),
                identity_key=identity, xml_redner_id="11",
            )
        first = self.roster("Ada Example", "d1", party="SPD")
        second = self.roster("Ada Example", "d2", party="CDU/CSU")

        _, _, canonical, stats = self.collect()

        self.assertNotEqual(canonical[first], canonical[second])
        self.assertEqual(stats["merges_unique_name"], 1)
        self.assertEqual(stats["buckets_split_namesakes"], 1)

    def test_a_name_found_id_shared_by_two_records_does_not_join_them(self) -> None:
        a = self.speaker("Peter Müller", "11", aw=99, match="name")
        b = self.speaker("Peter Müller", "22", aw=99, match="name")
        mps, lookup, canonical, stats = self.collect()
        self.assertNotEqual(canonical[a], canonical[b])
        self.assertEqual(len(mps), 2)
        # ...and the guessed id links no page.
        self.assertNotIn("aw:99", lookup)
        self.assertEqual(stats["merges_ext_id"], 0)
        self.assertEqual(stats["merges_unique_name"], 0)

    def test_an_id_with_no_recorded_match_kind_counts_as_found_by_name(self) -> None:
        a = self.speaker("Ada Lovelace", "11", aw=5, match=None)
        b = self.speaker("Ada Lovelace", "22", aw=5, match=None)
        _, lookup, canonical, _ = self.collect()
        self.assertNotEqual(canonical[a], canonical[b])
        self.assertNotIn("aw:5", lookup)

    def test_a_shared_personenkennung_joins_and_is_recorded_as_ext_id(self) -> None:
        a = self.roster("Ada Lovelace", "dip-1", aw=5, match="ext_id", separate=True)
        b = self.speaker("Ada Lovelace", "11", aw=5, match="ext_id", separate=True)
        self.assertNotEqual(a, b)
        mps, lookup, canonical, stats = self.collect()
        self.assertEqual(canonical[a], canonical[b])
        self.assertEqual(len(mps), 1)
        self.assertEqual(lookup["aw:5"], canonical[a])
        self.assertEqual((stats["merges_ext_id"], stats["merges_unique_name"]), (1, 0))

    def test_one_record_on_each_side_with_the_same_name_and_party_join_as_unique_name(self) -> None:
        roster = self.roster("Dr. Erika Beispiel, MdB, SPD", "dip-7")
        speaker = self.speaker("Erika Beispiel", "77")
        mps, lookup, canonical, stats = self.collect()
        self.assertEqual(canonical[roster], canonical[speaker])
        self.assertEqual(len(mps), 1)
        # Both records' keys reach the one page, so a speaker link resolves.
        self.assertEqual(lookup["dip:dip-7"], lookup["xml:77"])
        self.assertEqual(stats["merges_unique_name"], 1)

    def test_academic_titles_are_left_out_of_the_name_on_both_sides(self) -> None:
        roster = self.roster("Prof. Dr. Karl Lauterbach, MdB, SPD", "dip-9")
        speaker = self.speaker("Dr. Karl Lauterbach", "99")
        _, _, canonical, _ = self.collect()
        self.assertEqual(canonical[roster], canonical[speaker])

    def test_namesakes_on_one_side_stay_split_even_with_a_record_on_the_other_side(self) -> None:
        # Two Redner named Peter Müller (SPD) and one DIP person of that name: a
        # bucket of three cannot say who is who.
        a = self.speaker("Peter Müller", "11")
        b = self.speaker("Peter Müller", "22")
        c = self.roster("Peter Müller", "dip-3")
        mps, _, canonical, stats = self.collect()
        self.assertEqual(len({canonical[a], canonical[b], canonical[c]}), 3)
        self.assertEqual(len(mps), 3)
        self.assertEqual(stats["buckets_split_3plus"], 1)
        self.assertEqual(stats["merges_unique_name"], 0)

    def test_duplicate_roster_rows_and_one_speaker_stay_split(self) -> None:
        # E13: a bucket of 3+ (two roster rows for one name, one Redner) is not unique.
        roster_a = self.roster("Anna Schmidt", "dip-1")
        roster_b = self.roster("Anna Schmidt", "dip-2")
        speaker = self.speaker("Anna Schmidt", "31")
        _, _, canonical, stats = self.collect()
        self.assertEqual(len({canonical[roster_a], canonical[roster_b], canonical[speaker]}), 3)
        self.assertEqual(stats["buckets_split_3plus"], 1)

    def test_two_records_on_the_same_side_stay_split(self) -> None:
        a = self.speaker("Peter Müller", "11")
        b = self.speaker("Peter Müller", "22")
        _, _, canonical, stats = self.collect()
        self.assertNotEqual(canonical[a], canonical[b])
        self.assertEqual(stats["buckets_split_namesakes"], 1)

    def test_a_contradicting_personenkennung_blocks_the_name_match(self) -> None:
        roster = self.roster("Ada Lovelace", "dip-1", aw=6, match="ext_id")
        speaker = self.speaker("Ada Lovelace", "11", aw=5, match="ext_id")
        _, _, canonical, stats = self.collect()
        self.assertNotEqual(canonical[roster], canonical[speaker])
        self.assertEqual(stats["buckets_split_namesakes"], 1)

    def test_a_second_redner_id_with_a_corroborating_name_found_id_rejoins_the_person(self) -> None:
        # Nancy Faeser: an MdB Redner-ID (aw found by ext_id) and a 99999xxxx id for
        # her Reden as Ministerin, whose name search returned the same profile.
        mdb = self.speaker("Nancy Faeser", "11005452", aw=135391, match="ext_id", page=True)
        minister = self.speaker("Nancy Faeser", "999990119", aw=135391, match="name", party="Regierung", separate=True, page=True)
        mps, lookup, canonical, stats = self.collect()
        self.assertEqual(canonical[mdb], canonical[minister])
        self.assertEqual(len(mps), 1)
        self.assertEqual(stats["merges_corroborated_name"], 1)
        # Both Redner-IDs reach the one page.
        self.assertEqual(lookup["xml:11005452"], lookup["xml:999990119"])

    def test_a_namesakes_profile_is_no_corroboration(self) -> None:
        # Sonja Lemke's name search returned Steffi Lemke's profile: the names differ.
        steffi = self.speaker("Steffi Lemke", "11002720", aw=175323, match="ext_id", party="BÜNDNIS 90/DIE GRÜNEN")
        sonja = self.speaker("Sonja Lemke", "11005518", aw=175323, match="name", party="Die Linke", separate=True)
        mps, _, canonical, stats = self.collect()
        self.assertNotEqual(canonical[steffi], canonical[sonja])
        self.assertEqual(stats["merges_corroborated_name"], 0)

    def test_a_name_found_id_nobody_holds_as_a_personenkennung_corroborates_nothing(self) -> None:
        a = self.speaker("Peter Müller", "11", aw=99, match="name", separate=True)
        b = self.speaker("Peter Müller", "22", aw=99, match="name", separate=True)
        _, _, canonical, stats = self.collect()
        self.assertNotEqual(canonical[a], canonical[b])
        self.assertEqual(stats["merges_corroborated_name"], 0)

    def test_a_contradicting_dip_id_blocks_the_corroboration(self) -> None:
        trusted = self.roster("Ada Lovelace", "dip-1", aw=5, match="ext_id", separate=True)
        named = pulse_store.upsert_mp(
            self.conn, now=self.now, display_name="Ada Lovelace", party_id=self.party("SPD"), identity_key="xml:9",
            xml_redner_id="9", dip_person_id="dip-2", aw_politician_id=5, aw_match="name",
        )
        _, _, canonical, stats = self.collect()
        self.assertNotEqual(canonical[trusted], canonical[named])
        self.assertEqual(stats["merges_corroborated_name"], 0)

    def test_a_different_party_is_not_the_same_person(self) -> None:
        roster = self.roster("Ada Lovelace", "dip-1", party="SPD")
        speaker = self.speaker("Ada Lovelace", "11", party="CDU/CSU")
        _, _, canonical, _ = self.collect()
        self.assertNotEqual(canonical[roster], canonical[speaker])

    def test_each_namesake_speaker_links_to_their_own_page(self) -> None:
        # Both Redner were resolved by name to the same abgeordnetenwatch profile.
        self.speaker("Peter Müller", "11", aw=99, match="name", page=True)
        self.speaker("Peter Müller", "22", aw=99, match="name", page=True)
        _, lookup, _, _ = self.collect()
        first = {"xml_redner_id": "11", "abgeordnetenwatch": {"id": 99, "match": "name"}}
        second = {"xml_redner_id": "22", "abgeordnetenwatch": {"id": 99, "match": "name"}}
        # A speaker without a trusted id links through the Redner-ID, never through the guess.
        href_first = html.mp_page_href(first, lookup)
        href_second = html.mp_page_href(second, lookup)
        self.assertIsNotNone(href_first)
        self.assertIsNotNone(href_second)
        self.assertNotEqual(href_first, href_second)
        # A trusted id does link through the profile.
        trusted = {"xml_redner_id": "unknown", "abgeordnetenwatch": {"id": 99, "match": "ext_id"}}
        self.assertIsNone(html.mp_page_href(trusted, lookup))

    # Value: protects=a trusted external id held by two separate persons selects no page while each person's own keys still link; fails_when=the key_owners filter in collect_abgeordnete is dropped; why_new=only name-found ids were tested, which never reach the lookup; seam=none
    def test_a_trusted_id_shared_by_two_persons_links_no_page(self) -> None:
        a = self.speaker("Ada Lovelace", "11", aw=5, match="ext_id", separate=True, page=True)
        b = self.speaker("Bea Babbage", "22", aw=5, match="ext_id", separate=True, page=True)
        mps, lookup = build.collect_abgeordnete(self.conn)  # no reconcile: two persons keep the id
        canonical = {row["id"]: row["person_id"] for row in self.conn.execute("SELECT id, person_id FROM mps")}
        self.assertNotEqual(canonical[a], canonical[b])
        self.assertEqual(len(mps), 2)
        self.assertNotIn("aw:5", lookup)
        self.assertEqual(lookup["xml:11"], canonical[a])
        self.assertEqual(lookup["xml:22"], canonical[b])
        self.assertIsNone(html.mp_page_href({"xml_redner_id": "unknown", "abgeordnetenwatch": {"id": 5, "match": "ext_id"}}, lookup))

    # Value: protects=mp_page_href tries occurrence_id, person_id, trusted aw id, Redner-ID, DIP id in that order and returns None when none is known; fails_when=a candidate is dropped or reordered; why_new=only Redner-ID and aw links were asserted; seam=none
    def test_mp_page_href_candidates_resolve_in_documented_order(self) -> None:
        lookup = {"occ-1": "p-occ", "p-own": "p-own", "aw:7": "p-aw", "xml:11": "p-xml", "dip:d1": "p-dip"}
        trusted = {"id": 7, "match": "ext_id"}
        cases = [
            ("occurrence_id beats everything", {"occurrence_id": "occ-1", "person_id": "p-own", "abgeordnetenwatch": trusted, "xml_redner_id": "11", "dip_person_id": "d1"}, "abgeordnete/p-occ.html"),
            ("person_id beats external ids", {"person_id": "p-own", "abgeordnetenwatch": trusted, "xml_redner_id": "11", "dip_person_id": "d1"}, "abgeordnete/p-own.html"),
            ("unknown occurrence falls through to person_id", {"occurrence_id": "occ-x", "person_id": "p-own"}, "abgeordnete/p-own.html"),
            ("trusted aw id beats Redner-ID", {"abgeordnetenwatch": trusted, "xml_redner_id": "11", "dip_person_id": "d1"}, "abgeordnete/p-aw.html"),
            ("name-found aw id is skipped for the Redner-ID", {"abgeordnetenwatch": {"id": 7, "match": "name"}, "xml_redner_id": "11", "dip_person_id": "d1"}, "abgeordnete/p-xml.html"),
            ("Redner-ID beats DIP id", {"xml_redner_id": "11", "dip_person_id": "d1"}, "abgeordnete/p-xml.html"),
            ("DIP id alone", {"dip_person_id": "d1"}, "abgeordnete/p-dip.html"),
            ("nothing known", {"occurrence_id": "occ-x", "person_id": "p-x", "xml_redner_id": "99"}, None),
        ]
        for label, speaker, expected in cases:
            with self.subTest(label):
                self.assertEqual(html.mp_page_href(speaker, lookup), expected)
        self.assertEqual(html.mp_page_href({"person_id": "p-own"}, lookup, "../abgeordnete/"), "../abgeordnete/p-own.html")


class PersonMetricsTests(unittest.TestCase):
    """erste-reden counts Persons, not Redner-IDs."""

    def test_a_person_with_two_redner_ids_debuts_once(self) -> None:
        import facts

        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "store.sqlite")
            try:
                report = {
                    "validation_summary": {"speech_kinds_version": pulse_store.speech_kinds.VERSION},
            "protocol": {"id": "p1", "dokumentnummer": "21/1", "datum": "2026-01-01"},
                    "agenda_items": [
                        {
                            "index": 1, "top_id": "T1", "heading": "TOP",
                            "xml_speakers": [
                                {"rede_id": "R1", "speaker": {"xml_redner_id": "999990119", "display_name": "Nancy Faeser", "role": "Bundesministerin des Innern und für Heimat"},
                                 "char_count": 5, "text": "Hallo", "snippet": "Hallo"},
                                {"rede_id": "R2", "speaker": {"xml_redner_id": "11005452", "display_name": "Nancy Faeser", "fraktion": "SPD"},
                                 "char_count": 5, "text": "Hallo", "snippet": "Hallo"},
                            ],
                        }
                    ],
                }
                pulse_store.persist_report(conn, report)
                sql = facts.REGISTRY_BY_ID["erste-reden"]["sql"]
                # Without a map the two Redner-IDs are two Persons...
                facts.ensure_canonical(conn)
                self.assertEqual(len(conn.execute(sql).fetchall()), 2)
                # ...with an explicit persisted merge they are one Person.
                persons = [row["person_id"] for row in conn.execute("SELECT person_id FROM mps")]
                person_registry.merge(conn, persons)
                facts.ensure_canonical(conn)
                rows = conn.execute(sql).fetchall()
                self.assertEqual([row["rede_id"] for row in rows], ["R1"])
            finally:
                conn.close()


class DebutOrderTests(unittest.TestCase):
    # Value: protects=erste-reden cites the Rede that comes first in the sitting (agenda item, then position in it) even when a later item holds a lower position number; fails_when=the debut ORDER BY puts sequence before item_index or falls back to the key hash; why_new=every debut test seeds one agenda item per sitting; seam=none
    def test_the_debut_rede_is_the_first_in_the_sitting_across_agenda_items(self) -> None:
        import facts

        def speech(rede_id, name="Ada Example"):
            return {"rede_id": rede_id, "speaker": {"xml_redner_id": "1" if name == "Ada Example" else "2", "display_name": name, "fraktion": "SPD"},
                    "char_count": 5, "text": "Hallo", "snippet": "Hallo"}

        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "store.sqlite")
            try:
                report = {
                    "validation_summary": {"speech_kinds_version": pulse_store.speech_kinds.VERSION},
            "protocol": {"id": "p1", "dokumentnummer": "21/1", "datum": "2026-01-01"},
                    "agenda_items": [
                        {"index": 1, "top_id": "T1", "heading": "TOP 1", "xml_speakers": [speech("other-first-place", "Other Person"), speech("A-first-item-second-place")]},
                        {"index": 2, "top_id": "T2", "heading": "TOP 2", "xml_speakers": [speech("B-second-item-first-place")]},
                    ],
                }
                pulse_store.persist_report(conn, report)
                facts.ensure_canonical(conn)
                rows = conn.execute(facts.REGISTRY_BY_ID["erste-reden"]["sql"]).fetchall()
                self.assertEqual(sorted(row["rede_id"] for row in rows), ["A-first-item-second-place", "other-first-place"])
            finally:
                conn.close()


class PersistTests(unittest.TestCase):
    def report(self, *speakers: dict) -> dict:
        return {
            "validation_summary": {"speech_kinds_version": pulse_store.speech_kinds.VERSION},
            "protocol": {"id": "p1", "dokumentnummer": "21/1", "datum": "2026-01-01"},
            "agenda_items": [
                {
                    "index": 1,
                    "top_id": "T1",
                    "heading": "TOP 1",
                    "xml_speakers": [
                        {"rede_id": f"R{i}", "speaker": speaker, "paragraph_count": 1, "char_count": 5, "text": "Hallo", "snippet": "Hallo"}
                        for i, speaker in enumerate(speakers, start=1)
                    ],
                }
            ],
        }

    def test_a_name_found_id_is_stored_with_its_kind_and_names_no_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "store.sqlite")
            try:
                pulse_store.persist_report(
                    conn,
                    self.report(
                        {"xml_redner_id": "11", "display_name": "Peter Müller", "fraktion": "SPD",
                         "abgeordnetenwatch": {"id": 99, "match": "name", "url": "https://www.abgeordnetenwatch.de/profile/pm"}},
                        {"xml_redner_id": "22", "display_name": "Peter Müller", "fraktion": "SPD",
                         "abgeordnetenwatch": {"id": 99, "match": "name", "url": "https://www.abgeordnetenwatch.de/profile/pm"}},
                        {"xml_redner_id": "33", "display_name": "Eva Ext", "fraktion": "SPD",
                         "abgeordnetenwatch": {"id": 7, "match": "ext_id", "url": "https://www.abgeordnetenwatch.de/profile/ee"}},
                    ),
                )
                rows = {
                    row["display_name"] + row["xml_redner_id"]: (row["identity_key"], row["aw_politician_id"], row["aw_match"])
                    for row in conn.execute("SELECT * FROM mps")
                }
            finally:
                conn.close()
        self.assertEqual(rows, {
            "Peter Müller11": ("xml:11", 99, "name"),
            "Peter Müller22": ("xml:22", 99, "name"),
            "Eva Ext33": ("aw:7", 7, "ext_id"),
        })

    def test_a_preserved_roster_row_is_keyed_by_todays_rule(self) -> None:
        # A roster row written when a name-found aw id still named identity
        # ("aw:77") must not fold into a speaker row whose identity is aw:77.
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "store.sqlite"
            conn = pulse_store.connect(database)
            now = pulse_store.utc_now()
            pulse_store.initialize(conn)
            with conn:
                pulse_store.upsert_mp(
                    conn, now=now, display_name="Ada Lovelace", party_id=pulse_store.upsert_party(conn, "SPD", now),
                    identity_key="aw:77", dip_person_id="dip-ada", aw_politician_id=77, is_mdb=True,
                )
            conn.close()
            entry = {
                "report": self.report(
                    {"xml_redner_id": "11", "display_name": "Ada Lovelace", "fraktion": "SPD",
                     "abgeordnetenwatch": {"id": 77, "match": "ext_id"}}
                ),
                "report_path": Path(tmp) / "r.json",
            }
            build.rebuild_database_from_entries(database, [entry])
            conn = pulse_store.connect(database)
            try:
                keys = sorted(row["identity_key"] for row in conn.execute("SELECT identity_key FROM mps"))
            finally:
                conn.close()
        self.assertEqual(keys, ["aw:77", "dip:dip-ada"])

    def test_preserved_roster_cannot_reintroduce_a_namesakes_speaker_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            database = Path(tmp) / "store.sqlite"
            conn = pulse_store.connect(database)
            pulse_store.initialize(conn)
            now = pulse_store.utc_now()
            with conn:
                # Old identity rules merged a name-found speaker into this
                # roster row, leaving the other person's XML identifier behind.
                pulse_store.upsert_mp(
                    conn, now=now, display_name="Steffi Lemke",
                    party_id=pulse_store.upsert_party(conn, "BÜNDNIS 90/DIE GRÜNEN", now),
                    identity_key="aw:175323", dip_person_id="steffi", xml_redner_id="11005518",
                    aw_politician_id=175323, is_mdb=True,
                )
            conn.close()
            entry = {
                "report": self.report(
                    {"xml_redner_id": "11005518", "display_name": "Sonja Lemke", "fraktion": "Die Linke",
                     "abgeordnetenwatch": {"id": 175323, "match": "name"}}
                ),
                "report_path": Path(tmp) / "r.json",
            }
            build.rebuild_database_from_entries(database, [entry])
            conn = pulse_store.connect(database)
            try:
                rows = {row["identity_key"]: dict(row) for row in conn.execute("SELECT * FROM mps")}
                person_registry.reconcile(conn)
                _, _ = build.collect_abgeordnete(conn)
                canonical = {row["id"]: row["person_id"] for row in conn.execute("SELECT id, person_id FROM mps")}
                roster, speaker = rows["dip:steffi"], rows["xml:11005518"]
                self.assertIsNone(roster["xml_redner_id"])
                self.assertNotEqual(canonical[roster["id"]], canonical[speaker["id"]])
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
