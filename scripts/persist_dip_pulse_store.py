#!/usr/bin/env python3
"""Persist Bundestag Pulse reports into a linked SQLite entity graph."""

from __future__ import annotations

if __name__ == "__main__":
    from python_version_guard import require_supported_python

    require_supported_python()

import ast
import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import derive
import person_registry as registry
from stable_ids import (
    contribution_occurrence_id, roster_occurrence_id, speech_occurrence_id, speech_rede_id, stable_key, vote_member_occurrence_id,
)


SCHEMA_VERSION = 3
UPGRADE_INSTRUCTION = "Run python3 scripts/build_dip_pulse_site.py --offline --repersist --output-dir <site-dir> to upgrade the build store."

def require_current_schema(conn):
    columns = {row[1]: row[2] for row in conn.execute("PRAGMA table_info(mps)")}
    if columns and (columns.get("id") != "TEXT" or "person_id" not in columns):
        raise RuntimeError("Old build-store schema. " + UPGRADE_INSTRUCTION)
    if columns:
        # A store with current mps rows must carry its whole registry:
        # require_current alone accepts a store with no registry tables at all.
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not set(registry.REGISTRY_TABLES) <= tables:
            raise registry.RegistryError("Incomplete person registry; restore the build-store backup")
        registry.require_current(conn)



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
    user_version = conn.execute("PRAGMA user_version").fetchone()[0]
    has_datenstand = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'datenstand'"
    ).fetchone()
    if user_version or has_datenstand:
        conn.close()
        raise RuntimeError(
            f"error: {db_path} is a distribution copy (user_version={user_version}); "
            "it cannot be used as the build store"
        )
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    require_current_schema(conn)
    registry.initialize(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY NOT NULL,
          applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS parties (
          id TEXT PRIMARY KEY NOT NULL,
          name TEXT NOT NULL UNIQUE,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS mps (
          id TEXT PRIMARY KEY NOT NULL,
          identity_key TEXT NOT NULL UNIQUE,
          person_id TEXT NOT NULL REFERENCES persons(id),
          dip_person_id TEXT UNIQUE,
          xml_redner_id TEXT,
          display_name TEXT NOT NULL,
          title TEXT,
          function TEXT,
          wahlperiode TEXT,
          profile_url TEXT,
          party_id TEXT REFERENCES parties(id) ON DELETE SET NULL,
          birth_year INTEGER,
          gender TEXT,
          profession TEXT,
          wahlkreis TEXT,
          bundesland TEXT,
          aw_politician_id INTEGER,
          aw_match TEXT,
          person_roles_json TEXT,
          is_mdb INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS protocols (
          id TEXT PRIMARY KEY NOT NULL,
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
          id TEXT PRIMARY KEY NOT NULL,
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
          id TEXT PRIMARY KEY NOT NULL,
          title TEXT,
          proceeding_type TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS proceeding_positions (
          id TEXT PRIMARY KEY NOT NULL,
          proceeding_id TEXT REFERENCES proceedings(id) ON DELETE CASCADE,
          agenda_item_id TEXT REFERENCES agenda_items(id) ON DELETE SET NULL,
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
          id TEXT PRIMARY KEY NOT NULL,
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
          agenda_item_id TEXT NOT NULL REFERENCES agenda_items(id) ON DELETE CASCADE,
          document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          source TEXT NOT NULL,
          proceeding_id TEXT REFERENCES proceedings(id) ON DELETE SET NULL,
          proceeding_position_id TEXT,
          PRIMARY KEY (agenda_item_id, document_id, source)
        );

        CREATE TABLE IF NOT EXISTS speeches (
          id TEXT PRIMARY KEY NOT NULL,
          protocol_id TEXT NOT NULL REFERENCES protocols(id) ON DELETE CASCADE,
          agenda_item_id TEXT NOT NULL REFERENCES agenda_items(id) ON DELETE CASCADE,
          rede_id TEXT,
          sequence INTEGER NOT NULL,
          mp_id TEXT REFERENCES mps(id) ON DELETE SET NULL,
          page INTEGER,
          page_quadrant TEXT,
          paragraph_count INTEGER NOT NULL DEFAULT 0,
          char_count INTEGER NOT NULL DEFAULT 0,
          text TEXT,
          snippet TEXT,
          fraktion TEXT,
          unattributed_char_count INTEGER,
          sprechrolle TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(protocol_id, rede_id),
          UNIQUE(agenda_item_id, sequence)
        );

        -- What is spoken in a sitting and is not a Rede (CONTEXT.md: Beitrag):
        -- Kurzintervention, Erwiderung, Frage and Antwort of a Befragung or a
        -- Fragestunde. speeches holds Reden only. A Fragestunde turn has no
        -- rede_id and no page; a question read out by the Sitzungsleitung whose
        -- asker never speaks has no mp_id and keeps the announced name.
        CREATE TABLE IF NOT EXISTS contributions (
          id TEXT PRIMARY KEY NOT NULL,
          protocol_id TEXT NOT NULL REFERENCES protocols(id) ON DELETE CASCADE,
          agenda_item_id TEXT REFERENCES agenda_items(id) ON DELETE CASCADE,
          kind TEXT NOT NULL,
          rede_id TEXT,
          parent_rede_id TEXT,
          sequence INTEGER NOT NULL,
          mp_id TEXT REFERENCES mps(id) ON DELETE SET NULL,
          speaker_name TEXT,
          fraktion TEXT,
          sprechrolle TEXT,
          page INTEGER,
          char_count INTEGER NOT NULL DEFAULT 0,
          text TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(protocol_id, rede_id),
          UNIQUE(agenda_item_id, sequence)
        );

        CREATE TABLE IF NOT EXISTS votes (
          id TEXT PRIMARY KEY NOT NULL,
          protocol_id TEXT REFERENCES protocols(id) ON DELETE SET NULL,
          date TEXT,
          topic TEXT,
          title TEXT,
          description TEXT,
          detail_url TEXT,
          yes_count INTEGER NOT NULL DEFAULT 0,
          no_count INTEGER NOT NULL DEFAULT 0,
          abstain_count INTEGER NOT NULL DEFAULT 0,
          absent_count INTEGER NOT NULL DEFAULT 0,
          result_raw TEXT,
          result_source TEXT,
          result_scope TEXT,
          procedure_type TEXT,
          inverted INTEGER CHECK (inverted IN (0, 1) OR inverted IS NULL),
          inversion_source TEXT,
          inversion_excerpt TEXT,
          xlsx_url TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agenda_item_votes (
          agenda_item_id TEXT NOT NULL REFERENCES agenda_items(id) ON DELETE CASCADE,
          vote_id TEXT NOT NULL REFERENCES votes(id) ON DELETE CASCADE,
          PRIMARY KEY (agenda_item_id, vote_id)
        );

        CREATE TABLE IF NOT EXISTS vote_documents (
          vote_id TEXT NOT NULL REFERENCES votes(id) ON DELETE CASCADE,
          document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          PRIMARY KEY (vote_id, document_id)
        );

        CREATE TABLE IF NOT EXISTS vote_fractions (
          vote_id TEXT NOT NULL REFERENCES votes(id) ON DELETE CASCADE,
          party_id TEXT NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
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
          mp_id TEXT NOT NULL REFERENCES mps(id) ON DELETE CASCADE,
          party_id TEXT REFERENCES parties(id) ON DELETE SET NULL,
          vote TEXT NOT NULL,
          PRIMARY KEY (vote_id, mp_id)
        );

        CREATE INDEX IF NOT EXISTS idx_agenda_items_protocol ON agenda_items(protocol_id);
        CREATE INDEX IF NOT EXISTS idx_mps_person ON mps(person_id);
        CREATE INDEX IF NOT EXISTS idx_speeches_mp ON speeches(mp_id);
        CREATE INDEX IF NOT EXISTS idx_speeches_agenda_item ON speeches(agenda_item_id);
        CREATE INDEX IF NOT EXISTS idx_contributions_mp ON contributions(mp_id);
        CREATE INDEX IF NOT EXISTS idx_contributions_agenda_item ON contributions(agenda_item_id);
        CREATE INDEX IF NOT EXISTS idx_positions_proceeding ON proceeding_positions(proceeding_id);
        CREATE INDEX IF NOT EXISTS idx_vote_members_mp ON vote_members(mp_id);
        CREATE INDEX IF NOT EXISTS idx_vote_members_party ON vote_members(party_id);
        CREATE INDEX IF NOT EXISTS idx_votes_detail_url ON votes(detail_url);
        """
    )
    _migrate_mps_columns(conn)
    _migrate_speeches_columns(conn)
    _migrate_speech_paragraphs(conn)
    _migrate_party_names(conn)
    now = utc_now()
    conn.execute(
        """
        INSERT OR IGNORE INTO schema_migrations(version, applied_at)
        VALUES (?, ?)
        """,
        (SCHEMA_VERSION, now),
    )


# Bio/roster columns added after the initial release. SQLite has no
# "ADD COLUMN IF NOT EXISTS", so check the live schema before each ALTER to keep
# initialize() idempotent on pre-existing databases.
_MPS_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("birth_year", "INTEGER"),
    ("gender", "TEXT"),
    ("profession", "TEXT"),
    ("wahlkreis", "TEXT"),
    ("bundesland", "TEXT"),
    ("aw_politician_id", "INTEGER"),
    ("aw_match", "TEXT"),
    ("person_roles_json", "TEXT"),
    ("is_mdb", "INTEGER NOT NULL DEFAULT 0"),
)


# The Fraktion the XML names for the speaker of this Rede, added with the Fakten
# cards (plan D13): it is the affiliation at the time of the speech, where
# mps.party_id is the affiliation as of the last build.
_SPEECHES_ADDED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("fraktion", "TEXT"),
    ("unattributed_char_count", "INTEGER"),
    ("sprechrolle", "TEXT"),
)


def _migrate_added_columns(
    conn: sqlite3.Connection, table: str, columns: tuple[tuple[str, str], ...]
) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, decl in columns:
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def _migrate_speech_paragraphs(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(speeches)")}
    if "paragraphs_json" not in columns:
        return
    if tuple(int(part) for part in sqlite3.sqlite_version.split(".")) < (3, 35, 0):
        logging.getLogger(__name__).warning(
            "Keeping legacy speeches.paragraphs_json: SQLite %s needs an upgrade to >= 3.35 to drop it",
            sqlite3.sqlite_version,
        )
        return
    conn.execute("ALTER TABLE speeches DROP COLUMN paragraphs_json")


def _migrate_mps_columns(conn: sqlite3.Connection) -> None:
    _migrate_added_columns(conn, "mps", _MPS_ADDED_COLUMNS)


def _migrate_speeches_columns(conn: sqlite3.Connection) -> None:
    _migrate_added_columns(conn, "speeches", _SPEECHES_ADDED_COLUMNS)


# Before the list-repr fix below, persist_sampled_people wrote DIP's list-valued
# person.fraktion through str(), so the live store grew a second parties row per
# Fraktion ("['CDU/CSU']" beside "CDU/CSU", 913 mps.party_id rows pointing at the
# nine repr rows on the 2026-09-19 store). The names are merged back here rather
# than at read time, because every consumer joins on parties.id.
def _migrate_party_names(conn: sqlite3.Connection) -> None:
    rows = [dict(row) for row in conn.execute("SELECT id, name FROM parties ORDER BY id")]
    by_name = {row["name"]: row["id"] for row in rows}
    plan = [
        (row["id"], row["name"], clean_name)
        for row in rows
        for clean_name in [derive.zusammenschluss(unwrap_dip_faction(row["name"]))]
        if clean_name and clean_name != row["name"]
    ]
    if not plan:
        # The normal case on every build after the first: read only, no commit,
        # so initialize() never disturbs a caller's own transaction.
        return
    for party_id, name, clean_name in plan:
        keeper = by_name.get(clean_name)
        if keeper is None or keeper == party_id:
            conn.execute("UPDATE parties SET name = ? WHERE id = ?", (clean_name, party_id))
            by_name.pop(name, None)
            by_name[clean_name] = party_id
            continue
        _repoint_party(conn, party_id, keeper)
        conn.execute("DELETE FROM parties WHERE id = ?", (party_id,))
        by_name.pop(name, None)
    conn.commit()


def _repoint_party(conn: sqlite3.Connection, old_id: str, new_id: str) -> None:
    """Move every reference off ``old_id`` so the duplicate row can be deleted."""
    conn.execute("UPDATE mps SET party_id = ? WHERE party_id = ?", (new_id, old_id))
    conn.execute("UPDATE vote_members SET party_id = ? WHERE party_id = ?", (new_id, old_id))
    # vote_fractions is keyed (vote_id, party_id): a vote that already counted the
    # clean Fraktion absorbs the duplicate's counts instead of colliding with it.
    counts = ("yes_count", "no_count", "abstain_count", "absent_count", "total_count")
    for duplicate in [
        dict(row)
        for row in conn.execute("SELECT * FROM vote_fractions WHERE party_id = ?", (old_id,))
    ]:
        existing = conn.execute(
            "SELECT * FROM vote_fractions WHERE vote_id = ? AND party_id = ?",
            (duplicate["vote_id"], new_id),
        ).fetchone()
        if existing is None:
            conn.execute(
                "UPDATE vote_fractions SET party_id = ? WHERE vote_id = ? AND party_id = ?",
                (new_id, duplicate["vote_id"], old_id),
            )
            continue
        merged = [int(existing[name] or 0) + int(duplicate[name] or 0) for name in counts]
        merged_by_name = dict(zip(counts, merged))
        # The merge changes yes/no/abstain totals, so the Mehrheitsvotum must
        # be recomputed from them - leaving the keeper row's old leading_vote
        # would let a merge silently reverse which side of a vote counts as
        # the Zusammenschluss's own for the Abweichler metrics.
        new_leading = derive.majority_vote(
            {
                "yes": merged_by_name["yes_count"],
                "no": merged_by_name["no_count"],
                "abstain": merged_by_name["abstain_count"],
            }
        )
        assignments = ", ".join(f"{name} = ?" for name in counts) + ", leading_vote = ?"
        conn.execute(
            f"UPDATE vote_fractions SET {assignments} WHERE vote_id = ? AND party_id = ?",
            (*merged, new_leading, duplicate["vote_id"], new_id),
        )
        conn.execute(
            "DELETE FROM vote_fractions WHERE vote_id = ? AND party_id = ?",
            (duplicate["vote_id"], old_id),
        )


def unwrap_dip_faction(value: Any) -> str | None:
    """DIP's person.fraktion is a list; take its first entry.

    Accepts the live list (``["CDU/CSU"]``) and the repr an earlier build wrote
    into the store (``"['CDU/CSU']"``). Anything else comes back unchanged.
    """
    if isinstance(value, (list, tuple)):
        return next((clean(item) for item in value if clean(item)), None)
    text = clean(value)
    if not text or not (text.startswith("[") and text.endswith("]")):
        return text
    try:
        parsed = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text
    if isinstance(parsed, (list, tuple)):
        return next((clean(item) for item in parsed if clean(item)), None) or text
    return text


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def upsert_party(conn: sqlite3.Connection, name: str | None, now: str) -> str | None:
    # Every name enters parties through derive.zusammenschluss, so one
    # Zusammenschluss is one row whatever spelling its source used.
    name = derive.zusammenschluss(clean(name))
    if not name:
        return None
    conn.execute(
        """
        INSERT INTO parties(id, name, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET updated_at = excluded.updated_at
        """,
        (stable_key("party", name), name, now, now),
    )
    return conn.execute("SELECT id FROM parties WHERE name = ?", (name,)).fetchone()["id"]


def speaker_party_name(speaker: dict[str, Any] | None, protocol: dict[str, Any] | None = None) -> str | None:
    if not speaker:
        return None
    # Only a Zusammenschluss is a party. A role speaker (Bundesregierung,
    # Bundesrat, weitere Sprechrolle) belongs to none: the Rede counts for its
    # side (speeches.sprechrolle), and there is no "Regierung" row.
    return derive.speech_zusammenschluss(speaker, protocol)


def mp_identity(
    *,
    aw_politician_id: Any = None,
    aw_match: Any = None,
    dip_person_id: Any = None,
    xml_redner_id: Any = None,
    profile_url: Any = None,
    display_name: Any = None,
    party_name: Any = None,
) -> str:
    # An abgeordnetenwatch id found by searching a name is a guess, not a
    # Personenkennung: it names the person only when it was looked up by their
    # Redner-ID (ext_id).
    if aw_politician_id and aw_match == derive.TRUSTED_AW_MATCH:
        return f"aw:{aw_politician_id}"
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
    party_id: str | None,
    identity_key: str,
    dip_person_id: Any = None,
    xml_redner_id: Any = None,
    title: Any = None,
    function: Any = None,
    wahlperiode: Any = None,
    profile_url: Any = None,
    birth_year: Any = None,
    gender: Any = None,
    profession: Any = None,
    wahlkreis: Any = None,
    bundesland: Any = None,
    aw_politician_id: Any = None,
    aw_match: Any = None,
    person_roles_json: Any = None,
    is_mdb: bool = False,
    occurrence_id: str | None = None,
) -> str:
    if is_mdb and dip_person_id:
        # A DIP roster row names its person by DIP id only. A Redner-ID inherited from
        # a preserved or earlier row would let the roster record collide with a speaker
        # record's hard id (and the rebind check) before any protocol says so.
        xml_redner_id = None
    evidence = dict(display_name=clean(display_name), xml_redner_id=clean(xml_redner_id),
                    dip_person_id=clean(dip_person_id), aw_politician_id=aw_politician_id,
                    aw_match=aw_match, profile_url=profile_url, is_mdb=is_mdb,
                    party=(conn.execute("SELECT name FROM parties WHERE id=?", (party_id,)).fetchone()[0] if party_id else None),
                    title=clean(title), function=clean(function), wahlperiode=clean(wahlperiode),
                    birth_year=birth_year, gender=clean(gender), profession=clean(profession),
                    wahlkreis=clean(wahlkreis), bundesland=clean(bundesland),
                    person_roles_json=clean(person_roles_json))
    record_id, person_id, identity_key, evidence = registry.bind(conn, identity_key, evidence, occurrence_id)
    aw_match = evidence.get("aw_match")
    if evidence.get("profile_blocked"):  # a partition record other than the profile owner carries no profile
        aw_politician_id = profile_url = None
    conn.execute(
        """
        INSERT INTO mps(
          id, person_id, identity_key, dip_person_id, xml_redner_id, display_name, title,
          function, wahlperiode, profile_url, party_id,
          birth_year, gender, profession, wahlkreis, bundesland,
          aw_politician_id, aw_match, person_roles_json, is_mdb,
          created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(identity_key) DO UPDATE SET
          dip_person_id = COALESCE(excluded.dip_person_id, mps.dip_person_id),
          xml_redner_id = COALESCE(excluded.xml_redner_id, mps.xml_redner_id),
          display_name = COALESCE(NULLIF(excluded.display_name, 'Unbekannt'), mps.display_name),
          title = COALESCE(excluded.title, mps.title),
          function = COALESCE(excluded.function, mps.function),
          wahlperiode = COALESCE(excluded.wahlperiode, mps.wahlperiode),
          profile_url = COALESCE(excluded.profile_url, mps.profile_url),
          party_id = COALESCE(excluded.party_id, mps.party_id),
          birth_year = COALESCE(excluded.birth_year, mps.birth_year),
          gender = COALESCE(excluded.gender, mps.gender),
          profession = COALESCE(excluded.profession, mps.profession),
          wahlkreis = COALESCE(excluded.wahlkreis, mps.wahlkreis),
          bundesland = COALESCE(excluded.bundesland, mps.bundesland),
          aw_politician_id = COALESCE(excluded.aw_politician_id, mps.aw_politician_id),
          aw_match = CASE WHEN excluded.aw_politician_id IS NOT NULL THEN excluded.aw_match ELSE mps.aw_match END,
          person_roles_json = COALESCE(excluded.person_roles_json, mps.person_roles_json),
          is_mdb = MAX(mps.is_mdb, excluded.is_mdb),
          updated_at = excluded.updated_at
        """,
        (
            record_id, person_id, identity_key,
            clean(dip_person_id),
            clean(xml_redner_id),
            clean(display_name) or "Unbekannt",
            clean(title),
            clean(function),
            clean(wahlperiode),
            clean(profile_url),
            party_id,
            birth_year if isinstance(birth_year, int) else None,
            clean(gender),
            clean(profession),
            clean(wahlkreis),
            clean(bundesland),
            aw_politician_id if isinstance(aw_politician_id, int) else None,
            clean(aw_match) if isinstance(aw_politician_id, int) else None,
            clean(person_roles_json),
            1 if is_mdb else 0,
            now,
            now,
        ),
    )
    return record_id


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
) -> str | None:
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
            return existing["id"]
    conn.execute(
        """
        INSERT INTO documents(
          id, document_number, url, document_type, date, title, origin_json, created_at, updated_at
        )
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            stable_key("document", number, normalized_url), number,
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
    return row["id"] if row else None


def replace_protocol(conn: sqlite3.Connection, report: dict[str, Any], now: str) -> None:
    protocol = report.get("protocol") or {}
    protocol_id = clean(protocol.get("id"))
    if not protocol_id:
        raise ValueError("Report has no protocol.id")

    conn.execute("DELETE FROM agenda_items WHERE protocol_id = ?", (protocol_id,))
    conn.execute("DELETE FROM contributions WHERE protocol_id = ?", (protocol_id,))
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
        fraktion = unwrap_dip_faction(person.get("fraktion"))
        party_id = upsert_party(conn, fraktion, now)
        display_name = clean(person.get("titel")) or clean(person.get("id")) or "Unbekannt"
        upsert_mp(
            conn,
            now=now,
            display_name=display_name,
            party_id=party_id,
            identity_key=mp_identity(dip_person_id=person.get("id")),
            dip_person_id=person.get("id"),
            occurrence_id=roster_occurrence_id(person.get("id")),
            title=person.get("titel"),
            function=person.get("funktion"),
            wahlperiode=person.get("wahlperiode"),
        )


def persist_agenda_item(
    conn: sqlite3.Connection,
    protocol_id: str,
    item: dict[str, Any],
    now: str,
) -> str:
    page_range = item.get("page_range") or {}
    start_page, start_quadrant = source_page_ref(page_range.get("start"))
    end_page, end_quadrant = source_page_ref(page_range.get("end"))
    item_index = int(item.get("index") or 0)
    agenda_id = stable_key("agenda", protocol_id, item_index)
    conn.execute(
        """
        INSERT INTO agenda_items(
          id, protocol_id, item_index, top_id, heading, page_start, page_start_quadrant,
          page_end, page_end_quadrant, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            agenda_id, protocol_id,
            item_index,
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
    return agenda_id


def persist_agenda_documents(
    conn: sqlite3.Connection,
    item: dict[str, Any],
    agenda_item_id: str,
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
            proceeding_id = clean(doc.get("vorgang_id"))
            # Linked Drucksachen can belong to a co-advised (mitberatener) Vorgang
            # that never appears as a matched position, so the proceedings row may
            # not exist yet. Record it as a graph node first to satisfy the FK; any
            # later position upsert enriches it via COALESCE.
            if proceeding_id:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO proceedings(id, created_at, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (proceeding_id, now, now),
                )
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
                    proceeding_id,
                    clean(doc.get("vorgangsposition_id")),
                ),
            )


def persist_positions(
    conn: sqlite3.Connection,
    item: dict[str, Any],
    agenda_item_id: str,
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


def resolve_speaker(
    conn: sqlite3.Connection,
    speaker: dict[str, Any] | None,
    now: str,
    protocol_id: str,
    rede_id: str | None,
    occurrence_id: str,
    protocol: dict[str, Any] | None = None,
) -> tuple[str | None, str | None, str | None]:
    """The store row of the person a Rede or Beitrag names: ``(mp_id,
    fraktion, sprechrolle)``, bound to the registry as ``occurrence_id``.
    ``fraktion`` is the Zusammenschluss as the protocol states it for this unit,
    normalised the same way parties.name is; NULL when the XML names none (a
    minister speaking in role, or a merged record naming two), and the reader
    then falls back to the MP's party."""
    speaker = registry.corrected_speaker(speaker or {}, protocol_id, rede_id)
    profile = speaker.get("abgeordnetenwatch") or {}
    party_name = speaker_party_name(speaker, protocol)
    party_id = upsert_party(conn, party_name, now)
    display_name = clean(derive.undouble(speaker.get("display_name"))) or "Unbekannt"
    xml_redner_id = derive.first_redner_id(speaker.get("xml_redner_id"))
    aw_politician_id = profile.get("id") if isinstance(profile.get("id"), int) else None
    mp_id = upsert_mp(
        conn,
        now=now,
        display_name=display_name,
        party_id=party_id,
        identity_key=mp_identity(
            aw_politician_id=aw_politician_id,
            aw_match=profile.get("match"),
            xml_redner_id=xml_redner_id,
            display_name=display_name,
            party_name=party_name,
        ),
        xml_redner_id=xml_redner_id,
        occurrence_id=occurrence_id,
        profile_url=profile.get("url"),
        aw_politician_id=aw_politician_id,
        aw_match=profile.get("match"),
    )
    return mp_id, derive.speech_zusammenschluss(speaker, protocol), derive.sprechrolle(speaker)


def persist_speeches(
    conn: sqlite3.Connection,
    protocol_id: str,
    item: dict[str, Any],
    agenda_item_id: str,
    now: str,
    protocol: dict[str, Any] | None = None,
) -> None:
    for sequence, speech in enumerate(item.get("xml_speakers") or [], start=1):
        rede_id = speech_rede_id(protocol_id, int(item.get("index") or 0), sequence, speech.get("rede_id"))
        speech_id = speech_occurrence_id(protocol_id, rede_id)
        mp_id, speech_fraktion, sprechrolle = resolve_speaker(
            conn, speech.get("speaker"), now, protocol_id, rede_id, speech_id, protocol
        )
        page, quadrant = source_page_ref(speech.get("source_page"))
        conn.execute(
            """
            INSERT INTO speeches(
              id, protocol_id, agenda_item_id, rede_id, sequence, mp_id, page, page_quadrant,
              paragraph_count, char_count, text, snippet, fraktion,
              unattributed_char_count, sprechrolle, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                speech_id, protocol_id,
                agenda_item_id,
                rede_id,
                sequence,
                mp_id,
                page,
                quadrant,
                int(speech.get("paragraph_count") or 0),
                int(speech.get("char_count") or 0),
                clean(speech.get("text")),
                clean(speech.get("snippet")),
                speech_fraktion,
                # NULL for a report cached before the parser measured it:
                # unknown is not zero.
                None
                if speech.get("unattributed_char_count") is None
                else int(speech["unattributed_char_count"]),
                sprechrolle,
                now,
                now,
            ),
        )


def persist_contributions(
    conn: sqlite3.Connection,
    protocol_id: str,
    item: dict[str, Any],
    agenda_item_id: str,
    now: str,
    protocol: dict[str, Any] | None = None,
) -> None:
    for contribution in item.get("xml_contributions") or []:
        speaker = contribution.get("speaker") or {}
        rede_id = clean(contribution.get("rede_id"))
        contribution_id = contribution_occurrence_id(
            protocol_id, int(item.get("index") or 0), int(contribution["sequence"]), rede_id
        )
        # A question read out by the Sitzungsleitung whose asker never speaks
        # names a person the XML has no id for: keep the announced name, no MP.
        if speaker and speaker.get("xml_redner_id"):
            mp_id, fraktion, sprechrolle = resolve_speaker(
                conn, speaker, now, protocol_id, rede_id, contribution_id, protocol
            )
        else:
            mp_id, fraktion, sprechrolle = None, None, None
        page, _quadrant = source_page_ref(contribution.get("source_page"))
        conn.execute(
            """
            INSERT INTO contributions(
              id, protocol_id, agenda_item_id, kind, rede_id, parent_rede_id, sequence, mp_id,
              speaker_name, fraktion, sprechrolle, page, char_count, text,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                contribution_id,
                protocol_id,
                agenda_item_id,
                contribution["kind"],
                rede_id,
                clean(contribution.get("parent_rede_id")),
                int(contribution["sequence"]),
                mp_id,
                clean(derive.undouble(speaker.get("display_name"))),
                fraktion,
                sprechrolle,
                page,
                int(contribution.get("char_count") or 0),
                clean(contribution.get("text")),
                now,
                now,
            ),
        )


def persist_votes(
    conn: sqlite3.Connection,
    item: dict[str, Any] | None,
    agenda_item_id: str | None,
    protocol_id: str,
    now: str,
) -> None:
    if item is None:
        return
    for vote in item.get("votes") or ([] if not item.get("vote") else [item["vote"]]):
        persist_vote(conn, vote, agenda_item_id, protocol_id, now)


def persist_vote(
    conn: sqlite3.Connection,
    vote: dict[str, Any],
    agenda_item_id: str | None,
    protocol_id: str,
    now: str,
) -> None:
    vote_id = clean(vote.get("id"))
    if not vote_id:
        return
    total = vote.get("total") or {}
    result_raw, result_source = vote.get("result_raw"), vote.get("result_source")
    conn.execute(
        """
        INSERT INTO votes(
          id, protocol_id, date, topic, title, description, detail_url, yes_count, no_count,
          abstain_count, absent_count, result_raw, result_source, result_scope, procedure_type,
          inverted, inversion_source, inversion_excerpt, xlsx_url,
          created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          protocol_id = excluded.protocol_id,
          date = excluded.date,
          topic = excluded.topic,
          title = excluded.title,
          description = excluded.description,
          detail_url = excluded.detail_url,
          yes_count = excluded.yes_count,
          no_count = excluded.no_count,
          abstain_count = excluded.abstain_count,
          absent_count = excluded.absent_count,
          result_raw = excluded.result_raw,
          result_source = excluded.result_source,
          result_scope = excluded.result_scope,
          procedure_type = excluded.procedure_type,
          inverted = excluded.inverted,
          inversion_source = excluded.inversion_source,
          inversion_excerpt = excluded.inversion_excerpt,
          -- A copy of the vote without a link (e.g. the same vote attached to
          -- a second agenda item) never erases one already stored, so a
          -- missing link normally falls back to COALESCE. Two cases must
          -- NOT fall back, though: an explicit ambiguous-match refusal
          -- (xlsx_ambiguous) - COALESCE alone can't tell "no fresh data
          -- this copy" from "fresh data explicitly rejected this match"
          -- (Codex structured review, 2026-09-27) - and a changed date or
          -- title, the same guard carry_forward_vote_provenance already
          -- applies at the report layer: an old link was matched by
          -- (date, title), so once either changes it no longer vouches
          -- for this row (coverage audit, 2026-09-27). Across builds the
          -- store is rebuilt, so ordinary carry-forward happens in the
          -- report (build_dip_pulse_site.carry_forward_vote_provenance).
          xlsx_url = CASE
            WHEN ? THEN NULL
            WHEN excluded.date IS NOT votes.date OR excluded.title IS NOT votes.title THEN excluded.xlsx_url
            ELSE COALESCE(excluded.xlsx_url, votes.xlsx_url)
          END,
          updated_at = excluded.updated_at
        """,
        (
            vote_id,
            protocol_id,
            clean(vote.get("date")),
            clean(vote.get("topic")),
            clean(vote.get("title")),
            clean(vote.get("description")),
            clean(vote.get("detail_url")),
            int(total.get("yes") or 0),
            int(total.get("no") or 0),
            int(total.get("abstain") or 0),
            int(total.get("absent") or 0),
            clean(result_raw),
            clean(result_source),
            clean(vote.get("result_scope")),
            clean(vote.get("procedure_type")),
            None if vote.get("inverted") is None else int(bool(vote.get("inverted"))),
            clean(vote.get("inversion_source")),
            clean(vote.get("inversion_excerpt")),
            clean(vote.get("xlsx_url")),
            now,
            now,
            bool(vote.get("xlsx_ambiguous")),
        ),
    )
    if agenda_item_id is not None:
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

    # Rows of one vote that name the same Zusammenschluss under two
    # spellings ("Gruppe BSW", "BSW (Gruppe)") are one row: their counts add.
    for merged in derive.merge_fractions(vote.get("fractions")):
        party_name = merged["name"]
        party_id = upsert_party(conn, party_name, now)
        if party_id is None:
            continue
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
                merged["counts"]["yes"],
                merged["counts"]["no"],
                merged["counts"]["abstain"],
                merged["counts"]["absent"],
                merged["total"],
                # Derived from the counts: a cached report's own
                # leading_vote is ignored, so a rule change applies on
                # re-persist (plan F1/E2).
                derive.majority_vote(merged["counts"]),
            ),
        )

    for member in vote.get("members") or []:
        party_name = derive.zusammenschluss(member.get("faction")) or "Unbekannt"
        party_id = upsert_party(conn, party_name, now)
        profile = member.get("abgeordnetenwatch") or {}
        aw_politician_id = profile.get("id") if isinstance(profile.get("id"), int) else None
        profile_url = profile.get("url") or member.get("profile_url")
        mp_id = upsert_mp(
            conn,
            now=now,
            display_name=clean(member.get("name")) or "Unbekannt",
            party_id=party_id,
            identity_key=mp_identity(
                aw_politician_id=aw_politician_id,
                aw_match=profile.get("match"),
                profile_url=profile_url,
                display_name=member.get("name"),
                party_name=party_name,
            ),
            occurrence_id=vote_member_occurrence_id(vote_id, clean(member.get("name")), party_name),
            profile_url=profile_url,
            aw_politician_id=aw_politician_id,
            aw_match=profile.get("match"),
        )
        conn.execute(
            """
            INSERT INTO vote_members(vote_id, mp_id, party_id, vote)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(vote_id, mp_id) DO UPDATE SET
              party_id = excluded.party_id,
              vote = excluded.vote
            """,
            (vote_id, mp_id, party_id, clean(member.get("vote")) or "unknown"),
        )

def _warn_merged_redner_ids(report: dict[str, Any]) -> None:
    """A ``<redner id>`` with two ids is a merged record in the Bundestag XML;
    the first is used. Say where, so the source can be checked."""
    number = clean((report.get("protocol") or {}).get("dokumentnummer")) or "?"
    for item in report.get("agenda_items") or []:
        for speech in item.get("xml_speakers") or []:
            raw = (speech.get("speaker") or {}).get("xml_redner_id")
            ids = derive.redner_ids(raw)
            if len(ids) > 1:
                print(
                    f"warning: [redner-id] {number} Rede {speech.get('rede_id') or '?'}: the Redner id \"{raw}\" "
                    f"names {len(ids)} ids (a merged record in the Bundestag XML); using the first, {ids[0]}.",
                    file=sys.stderr,
                )


def persist_report(conn: sqlite3.Connection, report: dict[str, Any]) -> None:
    now = utc_now()
    initialize(conn)
    protocol = report.get("protocol") or {}
    protocol_id = clean(protocol.get("id"))
    if not protocol_id:
        raise ValueError("Report has no protocol.id")

    derive.check_sprechrollen([report])
    _warn_merged_redner_ids(report)
    with conn:
        replace_protocol(conn, report, now)
        persist_sampled_people(conn, report, now)
        # The report is a complete snapshot for this sitting. Remove old votes
        # from the sitting that disappeared from the refreshed report; linked
        # data is cascaded with them.
        report_vote_pairs = list(derive.iter_report_votes(report))
        current_vote_ids = {
            clean(vote.get("id")) for _, vote in report_vote_pairs if clean(vote.get("id"))
        }
        old_vote_ids = [
            row["id"] for row in conn.execute("SELECT id FROM votes WHERE protocol_id = ?", (protocol_id,))
            if row["id"] not in current_vote_ids
        ]
        for old_vote_id in old_vote_ids:
            conn.execute("DELETE FROM votes WHERE id = ?", (old_vote_id,))
        agenda_ids: dict[int, str] = {}
        for item in report.get("agenda_items") or []:
            agenda_item_id = persist_agenda_item(conn, protocol_id, item, now)
            agenda_ids[int(item.get("index") or 0)] = agenda_item_id
            persist_positions(conn, item, agenda_item_id, now)
            persist_agenda_documents(conn, item, agenda_item_id, now)
            persist_speeches(conn, protocol_id, item, agenda_item_id, now, protocol)
            persist_contributions(conn, protocol_id, item, agenda_item_id, now, protocol)
        for item, vote in report_vote_pairs:
            agenda_item_id = None
            if item is not None:
                agenda_item_id = agenda_ids.get(int(item.get("index") or 0))
            persist_vote(conn, vote, agenda_item_id, protocol_id, now)
        # iter_report_votes deliberately yields one row per vote. A vote may
        # still be cited under more than one TOP, so restore every source link.
        for item in report.get("agenda_items") or []:
            agenda_item_id = agenda_ids.get(int(item.get("index") or 0))
            if agenda_item_id is None:
                continue
            for vote in item.get("votes") or ([item["vote"]] if item.get("vote") else []):
                vote_id = clean(vote.get("id"))
                if vote_id:
                    conn.execute(
                        "INSERT OR IGNORE INTO agenda_item_votes(agenda_item_id, vote_id) VALUES (?, ?)",
                        (agenda_item_id, vote_id),
                    )


def main() -> int:
    # Writing one report straight into a carried store bypassed the staged rebuild:
    # it committed before the registry was reconciled and re-read each touched
    # person record from that one report. Every write now goes through the build.
    print("error: persisting a single report is not supported. Run python3 scripts/build_dip_pulse_site.py "
          "--offline --repersist --output-dir <site-dir> to persist every cached report.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
