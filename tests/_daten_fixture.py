"""Shared fixture store for the Daten export/page tests (F6.1).

seed_store(path) builds a small SQLite store covering every recipe, a
consolidated MP pair, a vote-only person who never gets a page, a NULL
mp_id speech, a synthetic rede_id, a dash-leading speech (CSV formula-cell
taste decision), a roll-call vote with a deviating member, and one bill
procedure. It returns the ids a test needs to assert against without
re-deriving them from the seeded rows.

A literal lone surrogate cannot be stored as SQLite TEXT through the
sqlite3 module (it must encode to valid UTF-8), so the CSV replacement-count
path (F2.2) is covered separately, against a mocked connection, in
test_daten_export.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import _support  # noqa: F401
import persist_dip_pulse_store as pulse_store


def seed_store(path: Path) -> dict[str, Any]:
    conn = pulse_store.connect(path)
    try:
        pulse_store.initialize(conn)
        now = pulse_store.utc_now()
        with conn:
            party_spd = pulse_store.upsert_party(conn, "SPD", now)
            party_cdu = pulse_store.upsert_party(conn, "CDU/CSU", now)

            # Duplicate pair: the DIP roster row (biography) and the protocol
            # speaker row (speeches), merged by the shared abgeordnetenwatch id.
            roster_mp = pulse_store.upsert_mp(
                conn,
                now=now,
                display_name="Ada Lovelace, MdB, SPD",
                party_id=party_spd,
                identity_key=pulse_store.mp_identity(dip_person_id="ada"),
                dip_person_id="ada",
                aw_politician_id=77,
                is_mdb=True,
            )
            speaker_mp = pulse_store.upsert_mp(
                conn,
                now=now,
                display_name="Ada Lovelace",
                party_id=party_spd,
                identity_key=pulse_store.mp_identity(xml_redner_id="11001"),
                xml_redner_id="11001",
                aw_politician_id=77,
            )
            # A second MdB with their own speeches (R1's #2 row, R5).
            other_mp = pulse_store.upsert_mp(
                conn,
                now=now,
                display_name="Karl Marx, MdB, CDU/CSU",
                party_id=party_cdu,
                identity_key=pulse_store.mp_identity(dip_person_id="karl"),
                dip_person_id="karl",
                is_mdb=True,
            )
            # A vote-only person: never a speaker, never on the roster, so the
            # page-eligibility gate in collect_abgeordnete excludes them from
            # the link lookup - but mp_canonical still carries their row
            # (eng:T3), and R3 must still count their deviation.
            vote_only_mp = pulse_store.upsert_mp(
                conn,
                now=now,
                display_name="Vera Stimme",
                party_id=party_cdu,
                identity_key=pulse_store.mp_identity(profile_url="https://example.test/vera"),
                profile_url="https://example.test/vera",
                is_mdb=False,
            )
            # A Fraktionswechsel: currently CDU/CSU (mps.party_id), but their
            # seeded speech carries speeches.fraktion = 'SPD', the Fraktion the
            # XML named for them at the time of that Rede. R2 must group the
            # Rede under the speech-time value, not the current party (D18/T8).
            switcher_mp = pulse_store.upsert_mp(
                conn,
                now=now,
                display_name="Petra Wechsel, MdB, CDU/CSU",
                party_id=party_cdu,
                identity_key=pulse_store.mp_identity(dip_person_id="petra"),
                dip_person_id="petra",
                is_mdb=True,
            )

            conn.execute(
                """
                INSERT INTO protocols(id, document_number, date, title, xml_header_json, created_at, updated_at)
                VALUES ('5801', '20/100', '2024-05-15', 'Erste Sitzung', '{}', ?, ?)
                """,
                (now, now),
            )
            conn.execute(
                """
                INSERT INTO protocols(id, document_number, date, title, xml_header_json, created_at, updated_at)
                VALUES ('5802', '20/101', '2024-05-22', 'Zweite Sitzung', '{}', ?, ?)
                """,
                (now, now),
            )
            conn.execute(
                """
                INSERT INTO agenda_items(protocol_id, item_index, top_id, heading, created_at, updated_at)
                VALUES ('5801', 1, 'T1', 'TOP 1 Haushalt', ?, ?)
                """,
                (now, now),
            )
            conn.execute(
                """
                INSERT INTO agenda_items(protocol_id, item_index, top_id, heading, created_at, updated_at)
                VALUES ('5802', 1, 'T1', 'TOP 1 Zweite Sitzung', ?, ?)
                """,
                (now, now),
            )
            agenda_item_1 = conn.execute(
                "SELECT id FROM agenda_items WHERE protocol_id = '5801'"
            ).fetchone()["id"]
            agenda_item_2 = conn.execute(
                "SELECT id FROM agenda_items WHERE protocol_id = '5802'"
            ).fetchone()["id"]

            # Seven speeches: speaker_mp (2, one with a synthetic rede_id and a
            # dash-leading snippet), other_mp (3, one more on the second
            # sitting for R5's sitzungen>1), a NULL mp_id row, and switcher_mp
            # (whose speeches.fraktion is 'SPD', not their current CDU/CSU).
            speech_rows = [
                ("5801", agenda_item_1, "R1", 1, speaker_mp, 240, "Redetext eins", None),
                ("5801", agenda_item_1, None, 2, other_mp, 100, "-beginnt mit Bindestrich", None),
                ("5801", agenda_item_1, "R3", 3, None, 80, "Rede ohne Redner", None),
                ("5801", agenda_item_1, "R4", 4, other_mp, 150, "Redetext vier", None),
                ("5802", agenda_item_2, "R5", 1, speaker_mp, 90, "Redetext fünf", None),
                ("5802", agenda_item_2, "R6", 2, other_mp, 60, "Redetext sechs", None),
                ("5802", agenda_item_2, "R7", 3, switcher_mp, 70, "Redetext sieben", "SPD"),
            ]
            for index, (protocol_id, agenda_item_id, rede_id, sequence, mp_id, char_count, snippet, fraktion) in enumerate(
                speech_rows
            ):
                resolved_rede_id = rede_id or pulse_store.synthetic_rede_id(protocol_id, agenda_item_id, sequence)
                conn.execute(
                    """
                    INSERT INTO speeches(
                      protocol_id, agenda_item_id, rede_id, sequence, mp_id, page,
                      paragraph_count, char_count, text, snippet, fraktion,
                      created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        protocol_id,
                        agenda_item_id,
                        resolved_rede_id,
                        sequence,
                        mp_id,
                        100 + index,
                        char_count,
                        snippet,
                        snippet,
                        fraktion,
                        now,
                        now,
                    ),
                )

            # Two roll-call votes: v1 has speaker_mp voting against their own
            # Fraktion's leading vote (the "Abweichler" R3 needs); v2 is a
            # closer 6:5 count so R4's ordering has two rows to sort.
            conn.execute(
                """
                INSERT INTO votes(id, date, topic, title, description, detail_url,
                                   yes_count, no_count, abstain_count, absent_count, created_at, updated_at)
                VALUES ('v1', '2024-05-15', 'Topic 1', 'Erste Abstimmung', 'desc',
                        'https://example.test/v1', 10, 8, 0, 0, ?, ?)
                """,
                (now, now),
            )
            conn.execute(
                """
                INSERT INTO votes(id, date, topic, title, description, detail_url,
                                   yes_count, no_count, abstain_count, absent_count, created_at, updated_at)
                VALUES ('v2', '2024-05-22', 'Topic 2', 'Zweite Abstimmung', 'desc',
                        'https://example.test/v2', 6, 5, 0, 0, ?, ?)
                """,
                (now, now),
            )
            conn.execute("INSERT INTO agenda_item_votes(agenda_item_id, vote_id) VALUES (?, 'v1')", (agenda_item_1,))
            conn.execute("INSERT INTO agenda_item_votes(agenda_item_id, vote_id) VALUES (?, 'v2')", (agenda_item_2,))
            conn.execute(
                """
                INSERT INTO vote_fractions(vote_id, party_id, yes_count, no_count, abstain_count, absent_count, total_count, leading_vote)
                VALUES ('v1', ?, 9, 1, 0, 0, 10, 'yes')
                """,
                (party_spd,),
            )
            conn.execute(
                """
                INSERT INTO vote_fractions(vote_id, party_id, yes_count, no_count, abstain_count, absent_count, total_count, leading_vote)
                VALUES ('v1', ?, 1, 7, 0, 0, 8, 'no')
                """,
                (party_cdu,),
            )
            conn.execute(
                """
                INSERT INTO vote_fractions(vote_id, party_id, yes_count, no_count, abstain_count, absent_count, total_count, leading_vote)
                VALUES ('v2', ?, 6, 5, 0, 0, 11, 'yes')
                """,
                (party_cdu,),
            )
            # speaker_mp (SPD) votes 'no' while their Fraktion's leading vote is
            # 'yes': one deviation. vote_only_mp (CDU/CSU) also deviates on v2.
            conn.execute(
                "INSERT INTO vote_members(vote_id, mp_id, party_id, vote) VALUES ('v1', ?, ?, 'no')",
                (speaker_mp, party_spd),
            )
            conn.execute(
                "INSERT INTO vote_members(vote_id, mp_id, party_id, vote) VALUES ('v2', ?, ?, 'no')",
                (vote_only_mp, party_cdu),
            )

            # One legislative procedure covering both agenda items, for R5 and
            # for the mp_id -> bill link key resolution tests.
            conn.execute(
                """
                INSERT INTO proceedings(id, title, proceeding_type, created_at, updated_at)
                VALUES ('vg-1', 'Gesetzentwurf zur Testbarkeit', 'Gesetzgebung', ?, ?)
                """,
                (now, now),
            )
            conn.execute(
                """
                INSERT INTO proceeding_positions(
                  id, proceeding_id, agenda_item_id, position_type, proceeding_type, title,
                  document_kind, activity_count, document_number, created_at, updated_at
                )
                VALUES ('pos-1', 'vg-1', ?, 'Beratung', 'Gesetzgebung', 'Erste Beratung',
                        'Drucksache', 1, '20/100', ?, ?)
                """,
                (agenda_item_1, now, now),
            )
            conn.execute(
                """
                INSERT INTO proceeding_positions(
                  id, proceeding_id, agenda_item_id, position_type, proceeding_type, title,
                  document_kind, activity_count, document_number, created_at, updated_at
                )
                VALUES ('pos-2', 'vg-1', ?, 'Beratung', 'Gesetzgebung', 'Zweite Beratung',
                        'Drucksache', 1, '20/101', ?, ?)
                """,
                (agenda_item_2, now, now),
            )
    finally:
        conn.close()

    return {
        "roster_mp": roster_mp,
        "speaker_mp": speaker_mp,
        "other_mp": other_mp,
        "vote_only_mp": vote_only_mp,
        "switcher_mp": switcher_mp,
        "protocols": ["20/100", "20/101"],
        "proceeding_id": "vg-1",
        "vote_ids": ["v1", "v2"],
    }
