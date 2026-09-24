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
  items            optional list of {"heading":..., "proceeding_title":...,
                   "proceeding_id":..., "proceeding_type":...}, one agenda
                   item each (default a single item with neither, so a card
                   carries no topic clause unless the spec asks for one); a
                   speech or vote names its item by index. proceeding_id lets
                   two items (even in different protocols/months) name the
                   same Vorgang, default unique per item; proceeding_type
                   defaults to "Gesetzgebung"
  speeches         optional explicit list replacing the two default speeches.
                   An entry is (char_count, speaker_or_None, rede_id_or_None)
                   or a dict with those keys plus "item"; a None speaker seeds
                   a NULL mp_id row, a None rede_id a synthetic
                   "<protocol_id>:<agenda_item_id>:<sequence>" id
  closest          optional (yes, no) tuple: one roll-call vote that week
  votes            optional explicit list replacing it. An entry is
                   (yes, no, title) or a dict with those keys plus "item",
                   "leading" ({party: "yes"|"no"|"abstain"}) and "members"
                   ([(name, party, vote), ...]) for the deviation metric
  unlinked_votes   optional list of (yes, no, title) votes without an agenda
                   link (they must never count for the week)
  sitzung          optional (start, end) as "09:00"/"14:08" strings, written
                   into protocols.xml_header_json
  complete         optional {"votes": bool, "speeches": bool} overrides

``people`` names MPs the specs refer to by alias, so a test can seed two mps
rows for one person (the live store's "aw:"/"xml:" split) or pin an
xml_redner_id: {alias: {"display_name":..., "party":..., "identity_key":...,
"xml_redner_id":...}}.

Returns the ids a test asserts against: protocol ids, agenda item ids, speech
ids and vote ids per document number, the mps ids per alias or name, and the
completeness map keyed by document number that facts.compute takes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import _support  # noqa: F401
import persist_dip_pulse_store as pulse_store


DEFAULT_SPEAKER = "Ada Lovelace"
DEFAULT_PARTY = "SPD"


def _speech_spec(entry: Any) -> dict[str, Any]:
    if isinstance(entry, dict):
        return {
            "char_count": entry["char_count"],
            "speaker": entry.get("speaker"),
            "rede_id": entry.get("rede_id"),
            "item": int(entry.get("item", 0)),
        }
    char_count, speaker, rede_id = entry
    return {"char_count": char_count, "speaker": speaker, "rede_id": rede_id, "item": 0}


def _vote_spec(entry: Any) -> dict[str, Any]:
    if isinstance(entry, dict):
        return {
            "yes": entry["yes"],
            "no": entry["no"],
            "title": entry.get("title", "Abstimmung"),
            "item": int(entry.get("item", 0)),
            "leading": entry.get("leading") or {},
            "members": entry.get("members") or [],
        }
    yes, no, title = entry
    return {"yes": yes, "no": no, "title": title, "item": 0, "leading": {}, "members": []}


def seed_weeks(
    path: Path, weeks: list[dict[str, Any]], *, people: dict[str, dict[str, Any]] | None = None
) -> dict[str, Any]:
    people = people or {}
    conn = pulse_store.connect(path)
    try:
        pulse_store.initialize(conn)
        now = pulse_store.utc_now()
        result: dict[str, Any] = {
            "protocol_ids": {},
            "agenda_item_ids": {},
            "speech_ids": {},
            "vote_ids": {},
            "mp_ids": {},
            "completeness": {},
        }
        parties: dict[str, int] = {}
        mps: dict[str, int] = {}

        def party_id(name: str) -> int:
            if name not in parties:
                parties[name] = pulse_store.upsert_party(conn, name, now)
            return parties[name]

        def mp_id(name: str, party: str) -> int:
            if name in mps:
                return mps[name]
            person = people.get(name)
            if person is not None:
                mps[name] = pulse_store.upsert_mp(
                    conn,
                    now=now,
                    display_name=person.get("display_name", name),
                    party_id=party_id(person.get("party", party)),
                    identity_key=person["identity_key"],
                    xml_redner_id=person.get("xml_redner_id"),
                )
            else:
                mps[name] = pulse_store.upsert_mp(
                    conn,
                    now=now,
                    display_name=name,
                    party_id=party_id(party),
                    identity_key=pulse_store.mp_identity(xml_redner_id=f"x-{name}"),
                    xml_redner_id=f"x-{name}",
                )
            result["mp_ids"][name] = mps[name]
            return mps[name]

        with conn:
            for index, spec in enumerate(weeks):
                document_number = spec["document_number"]
                protocol_id = f"p{index + 1}"
                header: dict[str, Any] = {"wahlperiode": document_number.partition("/")[0]}
                if spec.get("sitzung"):
                    header["sitzung_start"], header["sitzung_end"] = spec["sitzung"]
                conn.execute(
                    """
                    INSERT INTO protocols(id, document_number, date, title, pdf_url, xml_header_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        protocol_id,
                        document_number,
                        spec["date"],
                        f"Sitzung {document_number}",
                        f"https://example.test/{protocol_id}.pdf",
                        json.dumps(header, ensure_ascii=False, sort_keys=True),
                        now,
                        now,
                    ),
                )

                items = spec.get("items") or [{}]
                agenda_item_ids: list[int] = []
                for item_index, item in enumerate(items, start=1):
                    cursor = conn.execute(
                        """
                        INSERT INTO agenda_items(protocol_id, item_index, top_id, heading,
                                                 page_start, page_start_quadrant, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, 'A', ?, ?)
                        """,
                        (
                            protocol_id,
                            item_index,
                            f"T{item_index}",
                            item.get("heading"),
                            2000 + item_index,
                            now,
                            now,
                        ),
                    )
                    agenda_item_id = cursor.lastrowid
                    agenda_item_ids.append(agenda_item_id)
                    if item.get("proceeding_title"):
                        # "proceeding_id" lets two items in different protocols
                        # (even different months) name the same Vorgang, the
                        # way meistdiskutierter-vorgang sums a proceeding's
                        # speeches across every protocol it recurs in that
                        # month; the default is unique per item, as before.
                        proceeding_id = item.get("proceeding_id") or f"{protocol_id}-v{item_index}"
                        proceeding_type = item.get("proceeding_type", "Gesetzgebung")
                        conn.execute(
                            "INSERT OR IGNORE INTO proceedings(id, title, proceeding_type, created_at, updated_at) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (proceeding_id, item["proceeding_title"], proceeding_type, now, now),
                        )
                        conn.execute(
                            """
                            INSERT INTO proceeding_positions(id, proceeding_id, agenda_item_id,
                                                             proceeding_type, title, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                str(900000 + index * 100 + item_index),
                                proceeding_id,
                                agenda_item_id,
                                proceeding_type,
                                item["proceeding_title"],
                                now,
                                now,
                            ),
                        )

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
                sequence_by_item: dict[int, int] = {}
                for entry in speeches:
                    speech = _speech_spec(entry)
                    agenda_item_id = agenda_item_ids[speech["item"]]
                    sequence = sequence_by_item.get(agenda_item_id, 0) + 1
                    sequence_by_item[agenda_item_id] = sequence
                    resolved_rede_id = speech["rede_id"] or pulse_store.synthetic_rede_id(
                        protocol_id, agenda_item_id, sequence
                    )
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
                            mp_id(speech["speaker"], party) if speech["speaker"] else None,
                            1000 + len(speech_ids) + 1,
                            "B",
                            int(speech["char_count"]),
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
                for offset, entry in enumerate(votes or []):
                    vote = _vote_spec(entry)
                    vote_id = f"v{index + 1}{offset}"
                    _insert_vote(conn, vote_id, spec["date"], vote["title"], vote["yes"], vote["no"], now)
                    conn.execute(
                        "INSERT INTO agenda_item_votes(agenda_item_id, vote_id) VALUES (?, ?)",
                        (agenda_item_ids[vote["item"]], vote_id),
                    )
                    for fraction, leading in (vote["leading"] or {}).items():
                        conn.execute(
                            "INSERT INTO vote_fractions(vote_id, party_id, leading_vote) VALUES (?, ?, ?)",
                            (vote_id, party_id(fraction), leading),
                        )
                    for name, member_party, cast in vote["members"]:
                        conn.execute(
                            "INSERT INTO vote_members(vote_id, mp_id, party_id, vote) VALUES (?, ?, ?, ?)",
                            (vote_id, mp_id(name, member_party), party_id(member_party), cast),
                        )
                    vote_ids.append(vote_id)
                for offset, (yes, no, title) in enumerate(spec.get("unlinked_votes") or []):
                    vote_id = f"u{index + 1}{offset}"
                    _insert_vote(conn, vote_id, spec["date"], title, yes, no, now)
                    vote_ids.append(vote_id)

                complete = {"votes": True, "speeches": True}
                complete.update(spec.get("complete") or {})
                result["protocol_ids"][document_number] = protocol_id
                result["agenda_item_ids"][document_number] = agenda_item_ids
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
