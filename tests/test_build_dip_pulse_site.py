from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import build_dip_pulse_site
import persist_dip_pulse_store as pulse_store


class CollectAbgeordneteTests(unittest.TestCase):
    def test_write_report_reuses_catalog_protocol_metadata(self) -> None:
        protocol = {
            "id": "5805",
            "dokumentnummer": "21/87",
            "fundstelle": {"xml_url": "https://example.test/protocol.xml"},
        }
        report = {"protocol": {"id": "5805"}, "agenda_items": []}
        expected_entry = {"report": report}

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(build_dip_pulse_site.dip, "build_report", return_value=report) as build_report,
            mock.patch.object(
                build_dip_pulse_site,
                "write_report_files",
                return_value=expected_entry,
            ),
        ):
            entry = build_dip_pulse_site.write_report_and_page(
                protocol=protocol,
                output_dir=Path(tmp),
                api_key="test-key",
                sleep=0,
                person_limit=0,
                vote_scan_pages=0,
                roll_call_list_id=None,
                summary_mode="off",
                summary_provider="auto",
                anthropic_api_key=None,
                gemini_api_key=None,
                summary_model=None,
                existing_report=None,
            )

        self.assertIs(entry, expected_entry)
        self.assertIs(build_report.call_args.kwargs["protocol"], protocol)

    def test_collect_abgeordnete_groups_rows_sharing_external_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                now = pulse_store.utc_now()
                with conn:
                    party_id = pulse_store.upsert_party(conn, "SPD", now)
                    roster_mp_id = pulse_store.upsert_mp(
                        conn,
                        now=now,
                        display_name="Ada Lovelace, MdB, SPD",
                        party_id=party_id,
                        identity_key=pulse_store.mp_identity(dip_person_id="dip-ada"),
                        dip_person_id="dip-ada",
                        aw_politician_id=77,
                        profession="Mathematician",
                        is_mdb=True,
                    )
                    speaker_mp_id = pulse_store.upsert_mp(
                        conn,
                        now=now,
                        display_name="Ada Lovelace",
                        party_id=party_id,
                        identity_key=pulse_store.mp_identity(xml_redner_id="11001"),
                        xml_redner_id="11001",
                        aw_politician_id=77,
                    )
                    conn.execute(
                        """
                        INSERT INTO protocols(id, document_number, date, title, xml_header_json, created_at, updated_at)
                        VALUES ('pp-test', '20/999', '2024-05-15', 'Test protocol', '{}', ?, ?)
                        """,
                        (now, now),
                    )
                    conn.execute(
                        """
                        INSERT INTO agenda_items(protocol_id, item_index, top_id, heading, created_at, updated_at)
                        VALUES ('pp-test', 1, 'T1', 'TOP 1 Test', ?, ?)
                        """,
                        (now, now),
                    )
                    agenda_item_id = conn.execute("SELECT id FROM agenda_items").fetchone()["id"]
                    conn.execute(
                        """
                        INSERT INTO speeches(
                          protocol_id, agenda_item_id, rede_id, sequence, mp_id, page,
                          paragraph_count, char_count, text, paragraphs_json, snippet,
                          created_at, updated_at
                        )
                        VALUES ('pp-test', ?, 'R1', 1, ?, 101, 1, 24, 'Rede text', '[]', 'Rede text', ?, ?)
                        """,
                        (agenda_item_id, speaker_mp_id, now, now),
                    )

                mps, lookup = build_dip_pulse_site.collect_abgeordnete(conn)

                self.assertEqual(len(mps), 1)
                mp = mps[0]
                self.assertEqual(mp["id"], roster_mp_id)
                self.assertEqual(mp["name"], "Ada Lovelace")
                self.assertEqual(mp["profession"], "Mathematician")
                self.assertEqual(mp["speech_count"], 1)
                self.assertEqual(mp["speeches"][0]["rede_id"], "R1")
                self.assertEqual(lookup["aw:77"], roster_mp_id)
                self.assertEqual(lookup["dip:dip-ada"], roster_mp_id)
                self.assertEqual(lookup["xml:11001"], roster_mp_id)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
