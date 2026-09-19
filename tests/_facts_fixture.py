"""Parametric fixture store for the Fakt der Woche tests (plan D8).

seed_weeks(path, weeks=[...]) creates the live-store schema through
persist_dip_pulse_store.initialize and one protocol per listed week spec.
Each spec is a dict:

  document_number  "21/91" (required; the Wahlperiode is derived from it)
  date             "2026-09-08" (required; decides the ISO week)
  longest          char_count of the longest attributed speech (default 1000);
                   a second attributed speech at half that length is always
                   seeded so the max is a choice, not the only row
  speaker          display name of the longest speech's MP (default
                   "Ada Lovelace"); party via ``party`` (default "SPD")
  speeches         optional explicit list of (char_count, speaker_or_None,
                   rede_id_or_None) replacing the two default speeches; a None
                   speaker seeds a NULL mp_id row, a None rede_id a synthetic
                   "<protocol_id>:<agenda_item_id>:<sequence>" id
  closest          optional (yes, no) tuple: one roll-call vote that week
  votes            optional explicit list of (yes, no, title) replacing it
  unlinked_votes   optional list of (yes, no, title) votes without an agenda
                   link (they must never count for the week)
  complete         optional {"votes": bool, "speeches": bool} overrides

Returns the ids a test asserts against: protocol ids, speech ids and vote
ids per document number, and the completeness map keyed by document number
that facts.compute takes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import _support  # noqa: F401
import persist_dip_pulse_store as pulse_store


DEFAULT_SPEAKER = "Ada Lovelace"
DEFAULT_PARTY = "SPD"


def seed_weeks(path: Path, weeks: list[dict[str, Any]]) -> dict[str, Any]:
    conn = pulse_store.connect(path)
    try:
        pulse_store.initialize(conn)
        now = pulse_store.utc_now()
        result: dict[str, Any] = {
            "protocol_ids": {},
            "speech_ids": {},
            "vote_ids": {},
            "completeness": {},
        }
        parties: dict[str, int] = {}
        mps: dict[str, int] = {}

        def party_id(name: str) -> int:
            if name not in parties:
                parties[name] = pulse_store.upsert_party(conn, name, now)
            return parties[name]

        def mp_id(name: str, party: str) -> int:
            if name not in mps:
                mps[name] = pulse_store.upsert_mp(
                    conn,
                    now=now,
                    display_name=name,
                    party_id=party_id(party),
                    identity_key=pulse_store.mp_identity(xml_redner_id=f"x-{name}"),
                    xml_redner_id=f"x-{name}",
                )
            return mps[name]

        with conn:
            for index, spec in enumerate(weeks):
                document_number = spec["document_number"]
                protocol_id = f"p{index + 1}"
                conn.execute(
                    """
                    INSERT INTO protocols(id, document_number, date, title, pdf_url, xml_header_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, '{}', ?, ?)
                    """,
                    (
                        protocol_id,
                        document_number,
                        spec["date"],
                        f"Sitzung {document_number}",
                        f"https://example.test/{protocol_id}.pdf",
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO agenda_items(protocol_id, item_index, top_id, heading, created_at, updated_at)
                    VALUES (?, 1, 'T1', 'TOP 1', ?, ?)
                    """,
                    (protocol_id, now, now),
                )
                agenda_item_id = conn.execute(
                    "SELECT id FROM agenda_items WHERE protocol_id = ?", (protocol_id,)
                ).fetchone()["id"]

                speaker = spec.get("speaker", DEFAULT_SPEAKER)
                party = spec.get("party", DEFAULT_PARTY)
                longest = int(spec.get("longest", 1000))
                speeches = spec.get("speeches")
                if speeches is None:
                    speeches = [
                        (longest, speaker, f"ID{index + 1}00100"),
                        (longest // 2, "Karl Marx", f"ID{index + 1}00200"),
                    ]
                speech_ids = []
                for sequence, (char_count, name, rede_id) in enumerate(speeches, start=1):
                    resolved_rede_id = rede_id or f"{protocol_id}:{agenda_item_id}:{sequence}"
                    cursor = conn.execute(
                        """
                        INSERT INTO speeches(
                          protocol_id, agenda_item_id, rede_id, sequence, mp_id, page, page_quadrant,
                          paragraph_count, char_count, text, paragraphs_json, snippet, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, '[]', ?, ?, ?)
                        """,
                        (
                            protocol_id,
                            agenda_item_id,
                            resolved_rede_id,
                            sequence,
                            mp_id(name, party) if name else None,
                            1000 + sequence,
                            "B",
                            int(char_count),
                            f"Rede {sequence}",
                            f"Rede {sequence}",
                            now,
                            now,
                        ),
                    )
                    speech_ids.append(cursor.lastrowid)

                votes = spec.get("votes")
                if votes is None and spec.get("closest") is not None:
                    yes, no = spec["closest"]
                    votes = [(yes, no, f"Abstimmung {document_number}")]
                vote_ids = []
                for offset, (yes, no, title) in enumerate(votes or []):
                    vote_id = f"v{index + 1}{offset}"
                    _insert_vote(conn, vote_id, spec["date"], title, yes, no, now)
                    conn.execute(
                        "INSERT INTO agenda_item_votes(agenda_item_id, vote_id) VALUES (?, ?)",
                        (agenda_item_id, vote_id),
                    )
                    vote_ids.append(vote_id)
                for offset, (yes, no, title) in enumerate(spec.get("unlinked_votes") or []):
                    vote_id = f"u{index + 1}{offset}"
                    _insert_vote(conn, vote_id, spec["date"], title, yes, no, now)
                    vote_ids.append(vote_id)

                complete = {"votes": True, "speeches": True}
                complete.update(spec.get("complete") or {})
                result["protocol_ids"][document_number] = protocol_id
                result["speech_ids"][document_number] = speech_ids
                result["vote_ids"][document_number] = vote_ids
                result["completeness"][document_number] = complete
        return result
    finally:
        conn.close()


def _insert_vote(
    conn: Any, vote_id: str, date: str, title: str, yes: int, no: int, now: str
) -> None:
    conn.execute(
        """
        INSERT INTO votes(id, date, topic, title, description, detail_url,
                           yes_count, no_count, abstain_count, absent_count, created_at, updated_at)
        VALUES (?, ?, ?, ?, '', ?, ?, ?, 0, 0, ?, ?)
        """,
        (
            vote_id,
            date,
            title,
            title,
            f"https://example.test/abstimmung/{vote_id}",
            int(yes),
            int(no),
            now,
            now,
        ),
    )
