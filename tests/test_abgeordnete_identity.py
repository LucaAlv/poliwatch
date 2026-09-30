from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import build_dip_pulse_site as site  # noqa: E402
import persist_dip_pulse_store as store  # noqa: E402


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
    def test_speaker_and_vote_member_merge_with_vote_tally(self) -> None:
        report = report_with_speaker_and_vote()
        site.enrich_report_with_profiles(report, FakeResolver())

        member = report["agenda_items"][0]["votes"][0]["members"][0]
        self.assertEqual(member["abgeordnetenwatch"]["id"], 42)

        conn = memory_conn()
        store.persist_report(conn, report)

        mps, lookup, _canonical_by_mp_id = site.collect_abgeordnete(conn)
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

        mps, lookup, _canonical_by_mp_id = site.collect_abgeordnete(conn)
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
        mps, lookup, _canonical_by_mp_id = site.collect_abgeordnete(conn)
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

        mps, _lookup, _canonical_by_mp_id = site.collect_abgeordnete(conn)
        matches = [mp for mp in mps if mp["name"] == "Alex Beispiel" and mp["party"] == "SPD"]

        self.assertEqual(len(matches), 2)


if __name__ == "__main__":
    unittest.main()
