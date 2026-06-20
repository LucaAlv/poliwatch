#!/usr/bin/env python3
"""Persist Bundestag Pulse reports into a linked SQLite entity graph."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def clean(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).replace("\xa0", " ").split())
    return text or None


def page_number(page: dict[str, Any] | None) -> int | None:
    if not page or page.get("page") is None:
        return None
    try:
        return int(page["page"])
    except (TypeError, ValueError):
        return None


def source_page_ref(page: dict[str, Any] | None) -> tuple[int | None, str | None]:
    if not page:
        return None, None
    return page_number(page), clean(page.get("quadrant"))


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS parties (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mps (
          id INTEGER PRIMARY KEY,
          identity_key TEXT NOT NULL UNIQUE,
          dip_person_id TEXT UNIQUE,
          xml_redner_id TEXT,
          display_name TEXT NOT NULL,
          title TEXT,
          function TEXT,
          wahlperiode TEXT,
          profile_url TEXT,
          party_id INTEGER REFERENCES parties(id) ON DELETE SET NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS protocols (
          id TEXT PRIMARY KEY,
          document_number TEXT NOT NULL UNIQUE,
          date TEXT,
          title TEXT,
          verteildatum TEXT,
          pdf_url TEXT,
          xml_url TEXT,
          xml_header_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agenda_items (
          id INTEGER PRIMARY KEY,
          protocol_id TEXT NOT NULL REFERENCES protocols(id) ON DELETE CASCADE,
          item_index INTEGER NOT NULL,
          top_id TEXT,
          heading TEXT,
          page_start INTEGER,
          page_start_quadrant TEXT,
          page_end INTEGER,
          page_end_quadrant TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(protocol_id, item_index)
        );

        CREATE TABLE IF NOT EXISTS proceedings (
          id TEXT PRIMARY KEY,
          title TEXT,
          proceeding_type TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS proceeding_positions (
          id TEXT PRIMARY KEY,
          proceeding_id TEXT REFERENCES proceedings(id) ON DELETE CASCADE,
          agenda_item_id INTEGER REFERENCES agenda_items(id) ON DELETE SET NULL,
          position_type TEXT,
          proceeding_type TEXT,
          title TEXT,
          document_kind TEXT,
          activity_count INTEGER,
          document_number TEXT,
          page TEXT,
          page_start TEXT,
          page_end TEXT,
          pdf_url TEXT,
          xml_url TEXT,
          mitberaten_json TEXT NOT NULL DEFAULT '[]',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS documents (
          id INTEGER PRIMARY KEY,
          document_number TEXT NOT NULL,
          url TEXT NOT NULL DEFAULT '',
          document_type TEXT,
          date TEXT,
          title TEXT,
          origin_json TEXT NOT NULL DEFAULT '[]',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(document_number, url)
        );

        CREATE TABLE IF NOT EXISTS agenda_item_documents (
          agenda_item_id INTEGER NOT NULL REFERENCES agenda_items(id) ON DELETE CASCADE,
          document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          source TEXT NOT NULL,
          proceeding_id TEXT REFERENCES proceedings(id) ON DELETE SET NULL,
          proceeding_position_id TEXT,
          PRIMARY KEY (agenda_item_id, document_id, source)
        );

        CREATE TABLE IF NOT EXISTS speeches (
          id INTEGER PRIMARY KEY,
          protocol_id TEXT NOT NULL REFERENCES protocols(id) ON DELETE CASCADE,
          agenda_item_id INTEGER NOT NULL REFERENCES agenda_items(id) ON DELETE CASCADE,
          rede_id TEXT,
          sequence INTEGER NOT NULL,
          mp_id INTEGER REFERENCES mps(id) ON DELETE SET NULL,
          page INTEGER,
          page_quadrant TEXT,
          paragraph_count INTEGER NOT NULL DEFAULT 0,
          char_count INTEGER NOT NULL DEFAULT 0,
          text TEXT,
          paragraphs_json TEXT NOT NULL DEFAULT '[]',
          snippet TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(protocol_id, rede_id),
          UNIQUE(agenda_item_id, sequence)
        );

        CREATE TABLE IF NOT EXISTS votes (
          id TEXT PRIMARY KEY,
          date TEXT,
          topic TEXT,
          title TEXT,
          description TEXT,
          detail_url TEXT,
          yes_count INTEGER NOT NULL DEFAULT 0,
          no_count INTEGER NOT NULL DEFAULT 0,
          abstain_count INTEGER NOT NULL DEFAULT 0,
          absent_count INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agenda_item_votes (
          agenda_item_id INTEGER NOT NULL REFERENCES agenda_items(id) ON DELETE CASCADE,
          vote_id TEXT NOT NULL REFERENCES votes(id) ON DELETE CASCADE,
          PRIMARY KEY (agenda_item_id, vote_id)
        );

        CREATE TABLE IF NOT EXISTS vote_documents (
          vote_id TEXT NOT NULL REFERENCES votes(id) ON DELETE CASCADE,
          document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          PRIMARY KEY (vote_id, document_id)
        );

        CREATE TABLE IF NOT EXISTS vote_fractions (
          vote_id TEXT NOT NULL REFERENCES votes(id) ON DELETE CASCADE,
          party_id INTEGER NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
          yes_count INTEGER NOT NULL DEFAULT 0,
          no_count INTEGER NOT NULL DEFAULT 0,
          abstain_count INTEGER NOT NULL DEFAULT 0,
          absent_count INTEGER NOT NULL DEFAULT 0,
          total_count INTEGER NOT NULL DEFAULT 0,
          leading_vote TEXT,
          PRIMARY KEY (vote_id, party_id)
        );

        CREATE TABLE IF NOT EXISTS vote_members (
          vote_id TEXT NOT NULL REFERENCES votes(id) ON DELETE CASCADE,
          mp_id INTEGER NOT NULL REFERENCES mps(id) ON DELETE CASCADE,
          party_id INTEGER REFERENCES parties(id) ON DELETE SET NULL,
          vote TEXT NOT NULL,
          PRIMARY KEY (vote_id, mp_id)
        );

        CREATE INDEX IF NOT EXISTS idx_agenda_items_protocol ON agenda_items(protocol_id);
        CREATE INDEX IF NOT EXISTS idx_speeches_mp ON speeches(mp_id);
        CREATE INDEX IF NOT EXISTS idx_speeches_agenda_item ON speeches(agenda_item_id);
        CREATE INDEX IF NOT EXISTS idx_positions_proceeding ON proceeding_positions(proceeding_id);
        CREATE INDEX IF NOT EXISTS idx_vote_members_mp ON vote_members(mp_id);
        CREATE INDEX IF NOT EXISTS idx_vote_members_party ON vote_members(party_id);
        """
    )
    now = utc_now()
    conn.execute(
        """
        INSERT OR IGNORE INTO schema_migrations(version, applied_at)
        VALUES (?, ?)
        """,
        (SCHEMA_VERSION, now),
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def upsert_party(conn: sqlite3.Connection, name: str | None, now: str) -> int | None:
    name = clean(name)
    if not name:
        return None
    conn.execute(
        """
        INSERT INTO parties(name, created_at, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET updated_at = excluded.updated_at
        """,
        (name, now, now),
    )
    return int(conn.execute("SELECT id FROM parties WHERE name = ?", (name,)).fetchone()["id"])


def speaker_party_name(speaker: dict[str, Any] | None) -> str | None:
    if not speaker:
        return None
    if speaker.get("fraktion"):
        return clean(speaker.get("fraktion"))
    if speaker.get("role") or speaker.get("role_short"):
        return "Regierung"
    return None


def mp_identity(
    *,
    dip_person_id: Any = None,
    xml_redner_id: Any = None,
    profile_url: Any = None,
    display_name: Any = None,
    party_name: Any = None,
) -> str:
    if dip_person_id:
        return f"dip:{dip_person_id}"
    if xml_redner_id:
        return f"xml:{xml_redner_id}"
    if profile_url:
        return f"profile:{profile_url}"
    return f"name-party:{clean(display_name) or 'Unbekannt'}|{clean(party_name) or 'Unbekannt'}"


def upsert_mp(
    conn: sqlite3.Connection,
    *,
    now: str,
    display_name: str | None,
    party_id: int | None,
    identity_key: str,
    dip_person_id: Any = None,
    xml_redner_id: Any = None,
    title: Any = None,
    function: Any = None,
    wahlperiode: Any = None,
    profile_url: Any = None,
) -> int:
    conn.execute(
        """
        INSERT INTO mps(
          identity_key, dip_person_id, xml_redner_id, display_name, title,
          function, wahlperiode, profile_url, party_id, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(identity_key) DO UPDATE SET
          dip_person_id = COALESCE(excluded.dip_person_id, mps.dip_person_id),
          xml_redner_id = COALESCE(excluded.xml_redner_id, mps.xml_redner_id),
          display_name = COALESCE(NULLIF(excluded.display_name, 'Unbekannt'), mps.display_name),
          title = COALESCE(excluded.title, mps.title),
          function = COALESCE(excluded.function, mps.function),
          wahlperiode = COALESCE(excluded.wahlperiode, mps.wahlperiode),
          profile_url = COALESCE(excluded.profile_url, mps.profile_url),
          party_id = COALESCE(excluded.party_id, mps.party_id),
          updated_at = excluded.updated_at
        """,
        (
            identity_key,
            clean(dip_person_id),
            clean(xml_redner_id),
            clean(display_name) or "Unbekannt",
            clean(title),
            clean(function),
            clean(wahlperiode),
            clean(profile_url),
            party_id,
            now,
            now,
        ),
    )
    return int(conn.execute("SELECT id FROM mps WHERE identity_key = ?", (identity_key,)).fetchone()["id"])


def upsert_document(
    conn: sqlite3.Connection,
    *,
    now: str,
    document_number: Any,
    url: Any = None,
    document_type: Any = None,
    date: Any = None,
    title: Any = None,
    origin: Any = None,
) -> int | None:
    number = clean(document_number)
    if not number:
        return None
    normalized_url = clean(url) or ""
    if not normalized_url:
        existing = conn.execute(
            """
            SELECT id FROM documents
            WHERE document_number = ?
            ORDER BY CASE WHEN url = '' THEN 1 ELSE 0 END, id
            LIMIT 1
            """,
            (number,),
        ).fetchone()
        if existing:
            return int(existing["id"])
    conn.execute(
        """
        INSERT INTO documents(
          document_number, url, document_type, date, title, origin_json, created_at, updated_at
        )
          VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(document_number, url) DO UPDATE SET
          document_type = COALESCE(excluded.document_type, documents.document_type),
          date = COALESCE(excluded.date, documents.date),
          title = COALESCE(excluded.title, documents.title),
          origin_json = CASE
            WHEN excluded.origin_json != '[]' THEN excluded.origin_json
            ELSE documents.origin_json
          END,
          updated_at = excluded.updated_at
        """,
        (
            number,
            normalized_url,
            clean(document_type),
            clean(date),
            clean(title),
            dumps(origin or []),
            now,
            now,
        ),
    )
    row = conn.execute(
        """
        SELECT id FROM documents
          WHERE document_number = ? AND url = ?
        """,
        (number, normalized_url),
    ).fetchone()
    return int(row["id"]) if row else None


def replace_protocol(conn: sqlite3.Connection, report: dict[str, Any], now: str) -> None:
    protocol = report.get("protocol") or {}
    protocol_id = clean(protocol.get("id"))
    if not protocol_id:
        raise ValueError("Report has no protocol.id")

    conn.execute("DELETE FROM agenda_items WHERE protocol_id = ?", (protocol_id,))
    conn.execute(
        """
        INSERT INTO protocols(
          id, document_number, date, title, verteildatum, pdf_url, xml_url,
          xml_header_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          document_number = excluded.document_number,
          date = excluded.date,
          title = excluded.title,
          verteildatum = excluded.verteildatum,
          pdf_url = excluded.pdf_url,
          xml_url = excluded.xml_url,
          xml_header_json = excluded.xml_header_json,
          updated_at = excluded.updated_at
        """,
        (
            protocol_id,
            clean(protocol.get("dokumentnummer")) or protocol_id,
            clean(protocol.get("datum")),
            clean(protocol.get("titel")),
            clean(protocol.get("verteildatum")),
            clean(protocol.get("pdf_url")),
            clean(protocol.get("xml_url")),
            dumps(protocol.get("xml_header") or {}),
            now,
            now,
        ),
    )


def persist_sampled_people(conn: sqlite3.Connection, report: dict[str, Any], now: str) -> None:
    for person in report.get("sampled_people") or []:
        party_id = upsert_party(conn, clean(person.get("fraktion")), now)
        display_name = clean(person.get("titel")) or clean(person.get("id")) or "Unbekannt"
        upsert_mp(
            conn,
            now=now,
            display_name=display_name,
            party_id=party_id,
            identity_key=mp_identity(dip_person_id=person.get("id")),
            dip_person_id=person.get("id"),
            title=person.get("titel"),
            function=person.get("funktion"),
            wahlperiode=person.get("wahlperiode"),
        )


def persist_agenda_item(
    conn: sqlite3.Connection,
    protocol_id: str,
    item: dict[str, Any],
    now: str,
) -> int:
    page_range = item.get("page_range") or {}
    start_page, start_quadrant = source_page_ref(page_range.get("start"))
    end_page, end_quadrant = source_page_ref(page_range.get("end"))
    conn.execute(
        """
        INSERT INTO agenda_items(
          protocol_id, item_index, top_id, heading, page_start, page_start_quadrant,
          page_end, page_end_quadrant, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            protocol_id,
            int(item.get("index") or 0),
            clean(item.get("top_id")),
            clean(item.get("heading")),
            start_page,
            start_quadrant,
            end_page,
            end_quadrant,
            now,
            now,
        ),
    )
    return int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])


def persist_agenda_documents(
    conn: sqlite3.Connection,
    item: dict[str, Any],
    agenda_item_id: int,
    now: str,
) -> None:
    for doc in item.get("xml_drucksachen") or []:
        document_id = upsert_document(
            conn,
            now=now,
            document_number=doc.get("dokumentnummer"),
            url=doc.get("url"),
        )
        if document_id:
            conn.execute(
                """
                INSERT OR IGNORE INTO agenda_item_documents(agenda_item_id, document_id, source)
                VALUES (?, ?, 'xml')
                """,
                (agenda_item_id, document_id),
            )

    for doc in (item.get("api") or {}).get("linked_drucksachen") or []:
        document_id = upsert_document(
            conn,
            now=now,
            document_number=doc.get("dokumentnummer"),
            url=doc.get("url"),
            document_type=doc.get("drucksachetyp"),
            date=doc.get("datum"),
            title=doc.get("titel"),
            origin=doc.get("urheber") or [],
        )
        if document_id:
            conn.execute(
                """
                INSERT OR IGNORE INTO agenda_item_documents(
                  agenda_item_id, document_id, source, proceeding_id, proceeding_position_id
                )
                VALUES (?, ?, 'api', ?, ?)
                """,
                (
                    agenda_item_id,
                    document_id,
                    clean(doc.get("vorgang_id")),
                    clean(doc.get("vorgangsposition_id")),
                ),
            )


def persist_positions(
    conn: sqlite3.Connection,
    item: dict[str, Any],
    agenda_item_id: int,
    now: str,
) -> None:
    for position in (item.get("api") or {}).get("positions") or []:
        proceeding_id = clean(position.get("vorgang_id"))
        position_id = clean(position.get("id"))
        if proceeding_id:
            conn.execute(
                """
                INSERT INTO proceedings(id, title, proceeding_type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  title = COALESCE(excluded.title, proceedings.title),
                  proceeding_type = COALESCE(excluded.proceeding_type, proceedings.proceeding_type),
                  updated_at = excluded.updated_at
                """,
                (
                    proceeding_id,
                    clean(position.get("titel")),
                    clean(position.get("vorgangstyp")),
                    now,
                    now,
                ),
            )
        if not position_id:
            continue
        source = position.get("source") or {}
        conn.execute(
            """
            INSERT INTO proceeding_positions(
              id, proceeding_id, agenda_item_id, position_type, proceeding_type,
              title, document_kind, activity_count, document_number, page, page_start,
              page_end, pdf_url, xml_url, mitberaten_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              proceeding_id = excluded.proceeding_id,
              agenda_item_id = excluded.agenda_item_id,
              position_type = excluded.position_type,
              proceeding_type = excluded.proceeding_type,
              title = excluded.title,
              document_kind = excluded.document_kind,
              activity_count = excluded.activity_count,
              document_number = excluded.document_number,
              page = excluded.page,
              page_start = excluded.page_start,
              page_end = excluded.page_end,
              pdf_url = excluded.pdf_url,
              xml_url = excluded.xml_url,
              mitberaten_json = excluded.mitberaten_json,
              updated_at = excluded.updated_at
            """,
            (
                position_id,
                proceeding_id,
                agenda_item_id,
                clean(position.get("vorgangsposition")),
                clean(position.get("vorgangstyp")),
                clean(position.get("titel")),
                clean(position.get("dokumentart")),
                position.get("aktivitaet_anzahl"),
                clean(source.get("dokumentnummer")),
                clean(source.get("seite")),
                clean(source.get("anfangsseite")),
                clean(source.get("endseite")),
                clean(source.get("pdf_url")),
                clean(source.get("xml_url")),
                dumps(position.get("mitberaten") or []),
                now,
                now,
            ),
        )


def persist_speeches(
    conn: sqlite3.Connection,
    protocol_id: str,
    item: dict[str, Any],
    agenda_item_id: int,
    now: str,
) -> None:
    for sequence, speech in enumerate(item.get("xml_speakers") or [], start=1):
        speaker = speech.get("speaker") or {}
        party_name = speaker_party_name(speaker)
        party_id = upsert_party(conn, party_name, now)
        display_name = clean(speaker.get("display_name")) or "Unbekannt"
        mp_id = upsert_mp(
            conn,
            now=now,
            display_name=display_name,
            party_id=party_id,
            identity_key=mp_identity(
                xml_redner_id=speaker.get("xml_redner_id"),
                display_name=display_name,
                party_name=party_name,
            ),
            xml_redner_id=speaker.get("xml_redner_id"),
        )
        page, quadrant = source_page_ref(speech.get("source_page"))
        conn.execute(
            """
            INSERT INTO speeches(
              protocol_id, agenda_item_id, rede_id, sequence, mp_id, page, page_quadrant,
              paragraph_count, char_count, text, paragraphs_json, snippet, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                protocol_id,
                agenda_item_id,
                clean(speech.get("rede_id")) or f"{protocol_id}:{agenda_item_id}:{sequence}",
                sequence,
                mp_id,
                page,
                quadrant,
                int(speech.get("paragraph_count") or 0),
                int(speech.get("char_count") or 0),
                clean(speech.get("text")),
                dumps(speech.get("paragraphs") or []),
                clean(speech.get("snippet")),
                now,
                now,
            ),
        )


def persist_votes(
    conn: sqlite3.Connection,
    item: dict[str, Any],
    agenda_item_id: int,
    now: str,
) -> None:
    for vote in item.get("votes") or ([] if not item.get("vote") else [item["vote"]]):
        vote_id = clean(vote.get("id"))
        if not vote_id:
            continue
        total = vote.get("total") or {}
        conn.execute(
            """
            INSERT INTO votes(
              id, date, topic, title, description, detail_url, yes_count, no_count,
              abstain_count, absent_count, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              date = excluded.date,
              topic = excluded.topic,
              title = excluded.title,
              description = excluded.description,
              detail_url = excluded.detail_url,
              yes_count = excluded.yes_count,
              no_count = excluded.no_count,
              abstain_count = excluded.abstain_count,
              absent_count = excluded.absent_count,
              updated_at = excluded.updated_at
            """,
            (
                vote_id,
                clean(vote.get("date")),
                clean(vote.get("topic")),
                clean(vote.get("title")),
                clean(vote.get("description")),
                clean(vote.get("detail_url")),
                int(total.get("yes") or 0),
                int(total.get("no") or 0),
                int(total.get("abstain") or 0),
                int(total.get("absent") or 0),
                now,
                now,
            ),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO agenda_item_votes(agenda_item_id, vote_id)
            VALUES (?, ?)
            """,
            (agenda_item_id, vote_id),
        )
        conn.execute("DELETE FROM vote_fractions WHERE vote_id = ?", (vote_id,))
        conn.execute("DELETE FROM vote_members WHERE vote_id = ?", (vote_id,))
        conn.execute("DELETE FROM vote_documents WHERE vote_id = ?", (vote_id,))

        for number in vote.get("document_numbers") or []:
            document_id = upsert_document(conn, now=now, document_number=number)
            if document_id:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO vote_documents(vote_id, document_id)
                    VALUES (?, ?)
                    """,
                    (vote_id, document_id),
                )

        for fraction in vote.get("fractions") or []:
            party_id = upsert_party(conn, clean(fraction.get("name")) or "Unbekannt", now)
            if party_id is None:
                continue
            counts = fraction.get("counts") or {}
            conn.execute(
                """
                INSERT INTO vote_fractions(
                  vote_id, party_id, yes_count, no_count, abstain_count, absent_count,
                  total_count, leading_vote
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vote_id,
                    party_id,
                    int(counts.get("yes") or 0),
                    int(counts.get("no") or 0),
                    int(counts.get("abstain") or 0),
                    int(counts.get("absent") or 0),
                    int(fraction.get("total") or 0),
                    clean(fraction.get("leading_vote")),
                ),
            )

        for member in vote.get("members") or []:
            party_name = clean(member.get("faction")) or "Unbekannt"
            party_id = upsert_party(conn, party_name, now)
            mp_id = upsert_mp(
                conn,
                now=now,
                display_name=clean(member.get("name")) or "Unbekannt",
                party_id=party_id,
                identity_key=mp_identity(
                    profile_url=member.get("profile_url"),
                    display_name=member.get("name"),
                    party_name=party_name,
                ),
                profile_url=member.get("profile_url"),
            )
            conn.execute(
                """
                INSERT INTO vote_members(vote_id, mp_id, party_id, vote)
                VALUES (?, ?, ?, ?)
                """,
                (vote_id, mp_id, party_id, clean(member.get("vote")) or "unknown"),
            )


def persist_report(conn: sqlite3.Connection, report: dict[str, Any]) -> None:
    now = utc_now()
    initialize(conn)
    protocol = report.get("protocol") or {}
    protocol_id = clean(protocol.get("id"))
    if not protocol_id:
        raise ValueError("Report has no protocol.id")

    with conn:
        replace_protocol(conn, report, now)
        persist_sampled_people(conn, report, now)
        for item in report.get("agenda_items") or []:
            agenda_item_id = persist_agenda_item(conn, protocol_id, item, now)
            persist_positions(conn, item, agenda_item_id, now)
            persist_agenda_documents(conn, item, agenda_item_id, now)
            persist_speeches(conn, protocol_id, item, agenda_item_id, now)
            persist_votes(conn, item, agenda_item_id, now)


def persist_report_file(db_path: Path, report_path: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    with connect(db_path) as conn:
        persist_report(conn, report)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Validation JSON produced by validate_dip_protocol.py")
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(".context/dip-pulse-site/data/bundestag-pulse.sqlite"),
        help="SQLite database path to create or update.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    persist_report_file(args.database, args.report)
    print(args.database)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
