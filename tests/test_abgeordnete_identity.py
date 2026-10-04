from __future__ import annotations

from contextlib import closing
import copy
import re
import tempfile
import sqlite3
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _support
import derive
import render_dip_pulse_html as render
import speech_kinds
from stable_ids import roster_occurrence_id, vote_member_occurrence_id
import build_dip_pulse_site as site  # noqa: E402
import persist_dip_pulse_store as store  # noqa: E402
import person_registry


class FakeResolver:
    def resolve(
        self,
        *,
        ext_id: Any = None,
        first_name: str | None = None,
        last_name: str | None = None,
        fraktion: Any = None,
    ) -> dict[str, Any] | None:
        if ext_id == "xml-1" or (last_name == "von Beispiel" and fraktion == "SPD"):
            return {
                "id": 42,
                "url": "https://www.abgeordnetenwatch.de/profile/erika-von-beispiel",
                "party": "SPD",
                # Looked up by the Redner-ID it is a Personenkennung; found by a
                # name (the roll-call member) it is not.
                "match": "ext_id" if ext_id == "xml-1" else "name",
            }
        return None


def memory_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    store.initialize(conn)
    return conn


def report_with_speaker_and_vote() -> dict[str, Any]:
    return {
        "protocol": {
            "id": "protocol-1",
            "dokumentnummer": "21/1",
            "datum": "2026-01-01",
            "titel": "Testprotokoll",
        },
        "agenda_items": [
            {
                "item_index": 1,
                "top_id": "TOP 1",
                "heading": "Beratung",
                "xml_speakers": [
                    {
                        "rede_id": "rede-1",
                        "speaker": {
                            "xml_redner_id": "xml-1",
                            "display_name": "Erika von Beispiel",
                            "first_name": "Erika",
                            "last_name": "von Beispiel",
                            "fraktion": "SPD",
                        },
                        "source_page": {"page": 12},
                        "char_count": 120,
                        "snippet": "Redeauszug",
                    }
                ],
                "votes": [
                    {
                        "id": "vote-1",
                        "date": "2026-01-01",
                        "title": "Namentliche Abstimmung",
                        "total": {"yes": 1, "no": 0, "abstain": 0, "absent": 0},
                        "members": [
                            {
                                "name": "Erika von Beispiel",
                                "faction": "SPD",
                                "vote": "yes",
                                "profile_url": "https://www.bundestag.de/abgeordnete/erika-von-beispiel",
                            }
                        ],
                    }
                ],
            }
        ],
    }


class AbgeordneteIdentityTests(unittest.TestCase):
    def test_roster_speaker_and_messy_vote_rows_share_a_page_after_rebuild(self) -> None:
        report = report_with_speaker_and_vote()
        report["validation_summary"] = {"speech_kinds_version": speech_kinds.VERSION}
        item = report["agenda_items"][0]
        item["index"] = 1
        speaker = item["xml_speakers"][0]["speaker"]
        speaker.update(display_name="Erika Maria von Beispiel", first_name="Erika Maria", fraktion="Grüne")
        member = item["votes"][0]["members"][0]
        member.update(name="von Beispiel,\xa0Erika  Maria", faction="BÜNDNIS 90/DIE GRÜNEN")
        item["votes"][0]["detail_url"] = "https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id=1"
        sitting_vote = copy.deepcopy(item["votes"][0])
        sitting_vote.update(id="vote-2", title="Zweite Abstimmung")
        report["sitting_votes"] = [sitting_vote]

        def roster(conn):
            now = store.utc_now()
            store.upsert_mp(
                conn, now=now, display_name="Dr. Erika Maria von Beispiel, MdB, Grüne",
                party_id=store.upsert_party(conn, "Grüne", now), identity_key="dip:dip-1",
                dip_person_id="dip-1", is_mdb=True, occurrence_id=roster_occurrence_id("dip-1"),
            )

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "store.sqlite"
            entries = [{"report": report, "report_path": Path(tmp) / "report.json"}]
            site.rebuild_database_from_entries(db, entries, roster_ingest=roster)
            with closing(store.connect(db)) as conn:
                mps, lookup = site.collect_abgeordnete(conn)
                page_id = lookup["xml:xml-1"]
                self.assertEqual(lookup["dip:dip-1"], page_id)
                for vote in [item["votes"][0], sitting_vote]:
                    # Pin persist's pre-helper key; render must normalize the same inputs.
                    old_key = vote_member_occurrence_id(store.clean(vote["id"]), store.clean(member["name"]),
                                                        derive.zusammenschluss(member["faction"]) or "Unbekannt")
                    self.assertEqual(lookup[old_key], page_id)
                person = next(mp for mp in mps if mp["id"] == page_id)
                self.assertEqual({v["vote_id"] for v in person["votes"]}, {"vote-1", "vote-2"})
                profile_markup = site.render_abgeordnete_detail(person)
                self.assertIn("Bundestag-Profil ↗</a>", profile_markup)
                self.assertNotIn("abgeordnetenwatch.de-Profil ↗</a>", profile_markup)
            markup = render.render_html(report, mp_lookup=lookup)
            rows = re.findall(r'<li class="member-vote-row">(.*?)</li>', markup, re.S)
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertIn(f'href="../abgeordnete/{page_id}.html"', row)
            # Name guesses keep the occurrence keys and their target on replay.
            site.rebuild_database_from_entries(db, entries, roster_ingest=roster)
            with closing(store.connect(db)) as conn:
                _, replay_lookup = site.collect_abgeordnete(conn)
                self.assertEqual(replay_lookup, lookup)

    def test_vote_records_join_one_speaker_across_bundestag_profile_versions(self) -> None:
        report = report_with_speaker_and_vote()
        member = report["agenda_items"][0]["votes"][0]["members"][0]
        member["name"] = "von Beispiel, Erika"
        second = copy.deepcopy(report["agenda_items"][0]["votes"][0])
        second["id"] = "vote-2"
        second["members"][0]["profile_url"] += "-new"
        report["sitting_votes"] = [second]
        conn = memory_conn()
        self.addCleanup(conn.close)
        store.persist_report(conn, report)
        person_registry.reconcile(conn)
        mps, lookup = site.collect_abgeordnete(conn)
        self.assertEqual(len(mps), 1)
        self.assertEqual(len(mps[0]["votes"]), 2)
        self.assertEqual(mps[0]["name"], "Erika von Beispiel")
        self.assertEqual(len({r[0] for r in conn.execute("SELECT person_id FROM mps")}), 1)
        self.assertIn("xml:xml-1", lookup)

    def test_vote_record_joins_unique_roster_person_without_a_speech(self) -> None:
        conn = memory_conn()
        self.addCleanup(conn.close)
        now = store.utc_now()
        store.upsert_mp(conn, now=now, display_name="Erika von Beispiel, MdB, SPD", is_mdb=True,
                        party_id=store.upsert_party(conn, "SPD", now), identity_key="dip:d1",
                        dip_person_id="d1", occurrence_id=roster_occurrence_id("d1"))
        report = report_with_speaker_and_vote()
        report["agenda_items"][0]["xml_speakers"] = []
        member = report["agenda_items"][0]["votes"][0]["members"][0]
        member["name"] = "von Beispiel, Erika"
        store.persist_report(conn, report)
        person_registry.reconcile(conn)
        mps, lookup = site.collect_abgeordnete(conn)
        key = vote_member_occurrence_id("vote-1", member["name"], "SPD")
        self.assertEqual(lookup[key], lookup["dip:d1"])
        self.assertEqual(len(mps), 1)
        self.assertEqual((mps[0]["speech_count"], len(mps[0]["votes"])), (0, 1))

    def test_vote_guess_is_recomputed_when_a_namesake_appears(self) -> None:
        report = report_with_speaker_and_vote()
        report["validation_summary"] = {"speech_kinds_version": speech_kinds.VERSION}
        report["agenda_items"][0]["votes"][0]["members"][0]["name"] = "von Beispiel, Erika"
        ambiguous = copy.deepcopy(report)
        other = copy.deepcopy(ambiguous["agenda_items"][0]["xml_speakers"][0])
        other["rede_id"] = "rede-2"
        other["speaker"]["xml_redner_id"] = "xml-2"
        ambiguous["agenda_items"][0]["xml_speakers"].append(other)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            incremental, fresh = root / "incremental.sqlite", root / "fresh.sqlite"

            def rebuild(db, payload):
                site.rebuild_database_from_entries(db, [{"report": payload, "report_path": root / "report.json"}])

            def groups(db):
                with closing(store.connect(db)) as conn:
                    result = {}
                    for row in conn.execute("SELECT person_id, identity_key FROM person_records"):
                        result.setdefault(row["person_id"], set()).add(row["identity_key"])
                    return {frozenset(group) for group in result.values()}

            rebuild(incremental, report)
            self.assertEqual(len(groups(incremental)), 1)
            rebuild(incremental, ambiguous)
            rebuild(fresh, ambiguous)
            self.assertEqual(len(groups(incremental)), 3)
            self.assertEqual(groups(incremental), groups(fresh))
            before = groups(incremental)
            rebuild(incremental, ambiguous)
            self.assertEqual(groups(incremental), before)

    def test_vote_name_guesses_refuse_ambiguous_or_conflicting_people(self) -> None:
        for case in ("two speakers", "two roster persons", "trusted id conflict", "same vote namesakes", "different party"):
            with self.subTest(case=case):
                conn = memory_conn()
                self.addCleanup(conn.close)
                report = report_with_speaker_and_vote()
                item = report["agenda_items"][0]
                member = item["votes"][0]["members"][0]
                member["name"] = "von Beispiel, Erika"
                if case == "two speakers":
                    second = copy.deepcopy(item["xml_speakers"][0])
                    second["rede_id"] = "rede-2"
                    second["speaker"]["xml_redner_id"] = "xml-2"
                    item["xml_speakers"].append(second)
                elif case == "two roster persons":
                    now = store.utc_now()
                    for dip_id in ("d1", "d2"):
                        store.upsert_mp(conn, now=now, display_name="Erika von Beispiel", is_mdb=True,
                                        party_id=store.upsert_party(conn, "SPD", now), identity_key="dip:"+dip_id,
                                        dip_person_id=dip_id, occurrence_id=roster_occurrence_id(dip_id))
                elif case == "trusted id conflict":
                    item["xml_speakers"][0]["speaker"]["abgeordnetenwatch"] = {"id": 42, "match": "ext_id"}
                    member["abgeordnetenwatch"] = {"id": 99, "match": "ext_id"}
                elif case == "same vote namesakes":
                    other = {**member, "name": "Dr. Erika von Beispiel", "profile_url": member["profile_url"]+"-other"}
                    item["votes"][0]["members"].append(other)
                else:
                    member["faction"] = "FDP"
                store.persist_report(conn, report)
                person_registry.reconcile(conn)
                _, lookup = site.collect_abgeordnete(conn)
                key = vote_member_occurrence_id("vote-1", store.clean(member["name"]), member["faction"])
                self.assertNotIn(key, lookup)
                speaker_person = lookup["xml:xml-1"]
                vote_person = conn.execute("SELECT person_id FROM person_bindings WHERE id=?", (key,)).fetchone()[0]
                self.assertNotEqual(vote_person, speaker_person)

    def test_speaker_and_vote_member_merge_with_vote_tally(self) -> None:
        report = report_with_speaker_and_vote()
        site.enrich_report_with_profiles(report, FakeResolver())

        member = report["agenda_items"][0]["votes"][0]["members"][0]
        self.assertEqual(member["abgeordnetenwatch"]["id"], 42)

        conn = memory_conn()
        store.persist_report(conn, report)

        person_registry.reconcile(conn)
        mps, lookup = site.collect_abgeordnete(conn)
        matches = [mp for mp in mps if mp["name"] == "Erika von Beispiel"]

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["speech_count"], 1)
        self.assertEqual(len(matches[0]["votes"]), 1)
        self.assertEqual(matches[0]["vote_tally"], {"yes": 1, "no": 0, "abstain": 0, "absent": 0})
        self.assertEqual(lookup["aw:42"], matches[0]["id"])

    def test_roster_and_speaker_merge_without_abgeordnetenwatch(self) -> None:
        conn = memory_conn()
        now = store.utc_now()
        party_id = store.upsert_party(conn, "SPD", now)
        store.upsert_mp(
            conn,
            now=now,
            display_name="Dr. Erika Beispiel, MdB, SPD",
            party_id=party_id,
            identity_key=store.mp_identity(dip_person_id="dip-1"),
            dip_person_id="dip-1",
            title="Dr. Erika Beispiel, MdB, SPD",
            birth_year=1980,
            is_mdb=True,
        )

        report = report_with_speaker_and_vote()
        item = report["agenda_items"][0]
        item["xml_speakers"][0]["speaker"] = {
            "xml_redner_id": "xml-1",
            "display_name": "Dr. Erika Beispiel",
            "first_name": "Erika",
            "last_name": "Beispiel",
            "fraktion": "SPD",
        }
        item["votes"] = []
        store.persist_report(conn, report)

        person_registry.reconcile(conn)
        mps, lookup = site.collect_abgeordnete(conn)
        matches = [mp for mp in mps if mp["name"] == "Dr. Erika Beispiel"]

        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0]["is_mdb"])
        self.assertEqual(matches[0]["birth_year"], 1980)
        self.assertEqual(matches[0]["speech_count"], 1)
        self.assertEqual(lookup["dip:dip-1"], matches[0]["id"])
        self.assertEqual(lookup["xml:xml-1"], matches[0]["id"])

    # Value: protects=a Person's Beiträge resolve to the same profile as their Reden and count beside them on one Abgeordnete row; a Beitrag-only Person keeps a page;
    #   fails_when=xml_contributions are skipped by profile enrichment, an id-less asker is resolved, or collect_abgeordnete folds Beiträge into speech_count;
    #   why_new=no test runs enrich_report_with_profiles or collect_abgeordnete over xml_contributions; the render tests feed hand-made contribution_counts; seam=none
    def test_a_persons_beitraege_share_their_identity_and_count_apart_from_reden(self) -> None:
        report = report_with_speaker_and_vote()
        erika = report["agenda_items"][0]["xml_speakers"][0]["speaker"]
        report["agenda_items"][0]["xml_contributions"] = [
            {
                "kind": "kurzintervention",
                "rede_id": "kurz-1",
                "parent_rede_id": "rede-1",
                "sequence": 1,
                "source_page": {"page": 13},
                "speaker": {**erika, "xml_redner_id": "xml-1"},
                "char_count": 40,
                "text": "Kurz.",
            },
            {
                "kind": "befragung_frage",
                "rede_id": "frage-1",
                "parent_rede_id": None,
                "sequence": 2,
                "source_page": {"page": 14},
                "speaker": {
                    "xml_redner_id": "xml-9",
                    "display_name": "Hans Frager",
                    "first_name": "Hans",
                    "last_name": "Frager",
                    "fraktion": "AfD",
                },
                "char_count": 20,
                "text": "Frage?",
            },
            {
                "kind": "fragestunde_frage",
                "rede_id": None,
                "parent_rede_id": None,
                "sequence": 3,
                "source_page": None,
                "speaker": {"xml_redner_id": None, "display_name": "Stille Fragerin"},
                "char_count": 6,
                "text": "Warum?",
            },
        ]
        site.enrich_report_with_profiles(report, FakeResolver())
        first, second, silent = report["agenda_items"][0]["xml_contributions"]
        self.assertEqual(first["speaker"]["abgeordnetenwatch"]["id"], 42)
        self.assertIsNone(second["speaker"]["abgeordnetenwatch"])
        self.assertNotIn("abgeordnetenwatch", silent["speaker"])

        conn = memory_conn()
        store.persist_report(conn, report)

        person_registry.reconcile(conn)
        mps, lookup = site.collect_abgeordnete(conn)
        by_name = {mp["name"]: mp for mp in mps}

        erika_row = by_name["Erika von Beispiel"]
        self.assertEqual(len(mps), 2)
        self.assertEqual((erika_row["speech_count"], erika_row["contribution_count"]), (1, 1))
        self.assertEqual(erika_row["contribution_counts"], {"kurzintervention": 1})
        # Hans Frager only asked: no Reden, but a page and a link target.
        hans = by_name["Hans Frager"]
        self.assertEqual((hans["speech_count"], hans["contribution_counts"]), (0, {"befragung_frage": 1}))
        self.assertTrue(site.has_abgeordnete_page(hans))
        self.assertEqual(lookup["xml:xml-9"], hans["id"])
        self.assertNotIn("Stille Fragerin", by_name)

    def test_same_name_same_party_conflicting_external_ids_do_not_merge(self) -> None:
        conn = memory_conn()
        now = store.utc_now()
        party_id = store.upsert_party(conn, "SPD", now)
        for dip_id in ("dip-1", "dip-2"):
            store.upsert_mp(
                conn,
                now=now,
                display_name="Alex Beispiel",
                party_id=party_id,
                identity_key=store.mp_identity(dip_person_id=dip_id),
                dip_person_id=dip_id,
                is_mdb=True,
            )

        person_registry.reconcile(conn)
        mps, _lookup = site.collect_abgeordnete(conn)
        matches = [mp for mp in mps if mp["name"] == "Alex Beispiel" and mp["party"] == "SPD"]

        self.assertEqual(len(matches), 2)


if __name__ == "__main__":
    unittest.main()
