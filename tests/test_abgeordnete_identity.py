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

        mps, lookup = site.collect_abgeordnete(conn)
        matches = [mp for mp in mps if mp["name"] == "Dr. Erika Beispiel"]

        self.assertEqual(len(matches), 1)
        self.assertTrue(matches[0]["is_mdb"])
        self.assertEqual(matches[0]["birth_year"], 1980)
        self.assertEqual(matches[0]["speech_count"], 1)
        self.assertEqual(lookup["dip:dip-1"], matches[0]["id"])
        self.assertEqual(lookup["xml:xml-1"], matches[0]["id"])

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

        mps, _lookup = site.collect_abgeordnete(conn)
        matches = [mp for mp in mps if mp["name"] == "Alex Beispiel" and mp["party"] == "SPD"]

        self.assertEqual(len(matches), 2)


if __name__ == "__main__":
    unittest.main()
