"""Durable issued person keys, source records, occurrence bindings and corrections."""
from __future__ import annotations

import itertools
import json
import fcntl
from contextlib import contextmanager
from functools import lru_cache
from collections.abc import Iterator
import re
import sqlite3
from pathlib import Path
from typing import Any
import derive
import abgeordnetenwatch as aw
from stable_ids import stable_key

CORRECTIONS_PATH = Path(__file__).with_name("person_corrections.json")
REGISTRY_TABLES = ("persons", "person_aliases", "person_records", "person_bindings")
#: A person key is a page file name: URL-safe, never starting with a dot.
PERSON_KEY_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
#: File stems under abgeordnete/ that belong to the site, not to a person.
RESERVED_PERSON_KEYS = frozenset({"index"})
#: Partition prefix of a record a reviewed assignment or split placed on a person.
REVIEWED_PREFIX = "correction:"
#: Identity-key prefix of a record an occurrence assignment created.
ASSIGNMENT_PREFIX = "assignment:"
#: aw_match value of a record whose profile must not link it to anything.
PARTITIONED = "partitioned"

class RegistryError(ValueError):
    pass

@contextmanager
def writer_lock(database_path: Path) -> Iterator[None]:
    """Kernel releases this nonblocking lock even when a writer crashes."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    path = database_path.with_suffix(database_path.suffix + ".writer.lock")
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RegistryError(f"Another writer holds {path}; retry after that rebuild finishes") from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS persons (
      id TEXT PRIMARY KEY NOT NULL, ordinal INTEGER NOT NULL UNIQUE);
    CREATE TABLE IF NOT EXISTS person_aliases (
      id TEXT PRIMARY KEY NOT NULL REFERENCES persons(id),
      person_id TEXT NOT NULL REFERENCES persons(id));
    -- home_person_id is the durable owner (issued key, hard-ID and reviewed
    -- merges through its aliases); person_id is the current person, which
    -- reconcile may move to a namesake's person by a guess it recomputes.
    CREATE TABLE IF NOT EXISTS person_records (
      id TEXT PRIMARY KEY NOT NULL, identity_key TEXT NOT NULL UNIQUE,
      person_id TEXT NOT NULL REFERENCES persons(id), evidence_json TEXT NOT NULL,
      partition TEXT, home_person_id TEXT NOT NULL REFERENCES persons(id));
    CREATE TABLE IF NOT EXISTS person_bindings (
      id TEXT PRIMARY KEY NOT NULL,
      record_id TEXT NOT NULL REFERENCES person_records(id),
      person_id TEXT NOT NULL REFERENCES persons(id));
    CREATE INDEX IF NOT EXISTS idx_persons_folded ON persons(lower(id));
    CREATE INDEX IF NOT EXISTS idx_person_records_person ON person_records(person_id);
    CREATE INDEX IF NOT EXISTS idx_person_bindings_record ON person_bindings(record_id);
    CREATE INDEX IF NOT EXISTS idx_person_bindings_person ON person_bindings(person_id);
    """)

def corrections() -> dict[str, Any]:
    try:
        stat = CORRECTIONS_PATH.stat()
    except OSError as exc:
        raise RegistryError(f"Unreadable person corrections {CORRECTIONS_PATH}: {exc}") from exc
    return _load_corrections(CORRECTIONS_PATH, stat.st_ino, stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=8)
def _load_corrections(path: Path, inode: int, mtime_ns: int, size: int) -> dict[str, Any]:
    """Cache only a specific file revision; a corrected file is read afresh."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("expected a version 1 object")
        for name in ("partitions", "assignments", "merges", "splits"):
            if not isinstance(data.get(name), list):
                raise ValueError(f"{name} must be an array")
        required = {"partitions": ("xml_redner_id", "labels"), "assignments": ("occurrence_id", "person_id"), "merges": ("persons",), "splits": ("person_id", "retain_records", "new_records")}
        for kind, fields in required.items():
            for index, item in enumerate(data[kind]):
                if not isinstance(item, dict) or any(field not in item for field in fields):
                    raise ValueError(f"{kind}[{index}] requires {', '.join(fields)}")
        def text(value, what):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{what} must be a nonempty string")
            return value

        def texts(value, what):
            if not isinstance(value, list) or not value:
                raise ValueError(f"{what} must be a nonempty array of strings")
            for item in value:
                text(item, what)

        for partition in data["partitions"]:
            text(partition["xml_redner_id"], "partition xml_redner_id")
            if not isinstance(partition["labels"], dict) or not partition["labels"]:
                raise ValueError("partition labels must be a nonempty name-to-owner object")
            for label, owner in partition["labels"].items():
                text(owner, f"partition owner of {label!r}")
            occurrences = partition.get("occurrences") or {}
            if not isinstance(occurrences, dict):
                raise ValueError("partition occurrences must be an object")
            if partition.get("profile_owner") is not None:
                text(partition["profile_owner"], "partition profile_owner")
            for key, reviewed in occurrences.items():
                if not isinstance(reviewed, dict):
                    raise ValueError(f"partition occurrence {key!r} must be an object")
                text(reviewed.get("display_name"), f"display_name of partition occurrence {key!r}")
        for merge_ in data["merges"]:
            texts(merge_["persons"], "merge persons")
            if merge_.get("survivor") is not None:
                text(merge_["survivor"], "merge survivor")
        for split in data["splits"]:
            text(split["person_id"], "split person_id")
            texts(split["retain_records"], "split retain_records")
            texts(split["new_records"], "split new_records")
            if split.get("new_person_id") is not None:
                text(split["new_person_id"], "split new_person_id")
        assigned = {}
        for assignment in data["assignments"]:
            occurrence, owner = text(assignment["occurrence_id"], "assignment occurrence_id"), text(assignment["person_id"], "assignment person_id")
            if occurrence in assigned and assigned[occurrence] != owner:
                raise ValueError(f"contradictory assignments for occurrence {occurrence}")
            assigned[occurrence] = owner
        data["assignment_of"] = assigned  # occurrence id -> owner, for bind()
        return data
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RegistryError(f"Unreadable person corrections {CORRECTIONS_PATH}: {exc}") from exc

def corrected_speaker(speaker: dict[str, Any], protocol_id: Any, rede_id: Any) -> dict[str, Any]:
    speaker = dict(speaker)
    for partition in corrections()["partitions"]:
        if str(speaker.get("xml_redner_id")) == partition["xml_redner_id"]:
            reviewed = partition.get("occurrences", {}).get(f"{protocol_id}/{rede_id}")
            if reviewed:
                speaker["display_name"] = reviewed["display_name"]
            name = _normalized_mp_name(speaker.get("display_name"))
            owner = next((owner for label, owner in partition["labels"].items() if _normalized_mp_name(label) == name), None)
            profile = speaker.get("abgeordnetenwatch") or {}
            if owner and partition.get("profile_owner") != owner and profile.get("match") == derive.TRUSTED_AW_MATCH:
                speaker["abgeordnetenwatch"] = {}
    return speaker

def partition_identity(identity: str, evidence: dict[str, Any]) -> str:
    for partition in corrections()["partitions"]:
        if str(evidence.get("xml_redner_id")) != partition["xml_redner_id"]:
            continue
        name = _normalized_mp_name(evidence.get("display_name"))
        choices = {owner for part, owner in partition["labels"].items() if _normalized_mp_name(part) == name}
        if len(choices) != 1:
            raise RegistryError(f"Shared Redner-ID {partition['xml_redner_id']}: review printed label {name!r} in {CORRECTIONS_PATH}")
        owner = next(iter(choices))
        # The contaminated ext_id profile cannot bridge these two partitions.
        evidence["aw_match"] = PARTITIONED
        evidence["partition"] = owner
        # Only the profile owner's partition keeps the shared profile (the same rule
        # corrected_speaker applies), whatever one occurrence happens to carry.
        evidence["profile_blocked"] = owner != partition.get("profile_owner")
        return f"partition:{partition['xml_redner_id']}:{owner}"
    return identity

def resolve(conn: sqlite3.Connection, person_id: str) -> str:
    seen = set()
    while True:
        if person_id in seen:
            raise RegistryError(f"Alias cycle at {person_id}")
        seen.add(person_id)
        row = conn.execute("SELECT person_id FROM person_aliases WHERE id = ?", (person_id,)).fetchone()
        if row is None:
            return person_id
        person_id = row[0]

def allocate(conn: sqlite3.Connection, preferred: str | None = None) -> str:
    if preferred is not None:
        if not isinstance(preferred, str) or not PERSON_KEY_RE.fullmatch(preferred) or preferred.casefold() in RESERVED_PERSON_KEYS:
            raise RegistryError(f"Invalid person key {preferred!r}; use a URL-safe filename key that is not a reserved page name")
        clash = conn.execute("SELECT id FROM persons WHERE lower(id) = lower(?) AND id != ?", (preferred, preferred)).fetchone()
        if clash:
            raise RegistryError(f"Person key {preferred!r} differs only by case from {clash[0]!r}; case-insensitive file systems would merge their pages")
    ordinal = conn.execute("SELECT COALESCE(MAX(ordinal), 0) + 1 FROM persons").fetchone()[0]
    key = preferred or f"p-{ordinal:06d}"
    while conn.execute("SELECT 1 FROM persons WHERE id = ?", (key,)).fetchone():
        if preferred:
            return resolve(conn, key)
        ordinal += 1
        key = f"p-{ordinal:06d}"
    conn.execute("INSERT INTO persons VALUES (?, ?)", (key, ordinal))
    return key

def is_placed_identity(identity_key: Any) -> bool:
    """True for the identity of a record an occurrence assignment created."""
    return str(identity_key or "").startswith(ASSIGNMENT_PREFIX)


def _hard_id_conflict(old: dict[str, Any], new: dict[str, Any]) -> bool:
    """Both sides name an official id and the ids differ: the source now says a
    different person, which is not an enrichment of the bound record."""
    pairs = (
        (derive.first_redner_id(old.get("xml_redner_id")), derive.first_redner_id(new.get("xml_redner_id"))),
        (old.get("dip_person_id"), new.get("dip_person_id")),
    )
    return any(a and b and a != b for a, b in pairs)


def bind(
    conn: sqlite3.Connection, identity: str, evidence: dict[str, Any],
    occurrence: str | None = None,
) -> tuple[str, str, str, dict[str, Any]]:
    """Bind one source occurrence to a source record and its home person.

    Returns ``(record_id, home_person_id, identity_key, evidence)``. An occurrence
    that is already bound keeps its record while the source only enriches it; it
    moves to the record of the new identity on a reviewed assignment, a changed
    partition or a different official id. Evidence is re-read from the source on
    a record's first touch in this connection; only registry-owned evidence
    survives from the earlier build."""
    evidence["ever_mdb"] = bool(evidence.get("is_mdb"))
    identity = partition_identity(identity, evidence)
    assignment = corrections()["assignment_of"].get(occurrence)
    if assignment:
        # Reports arrive newest first, so the owner may not be issued yet; reconcile
        # rejects an owner that is still unknown once every report is bound.
        identity = f"{ASSIGNMENT_PREFIX}{identity}:{assignment}"
        evidence["partition"] = f"{REVIEWED_PREFIX}{assignment}"
        evidence["aw_match"] = PARTITIONED
    row = conn.execute("SELECT * FROM person_records WHERE identity_key = ?", (identity,)).fetchone()
    bound = conn.execute("SELECT record_id FROM person_bindings WHERE id = ?", (occurrence,)).fetchone() if occurrence else None
    if bound:
        previous = conn.execute("SELECT * FROM person_records WHERE id = ?", (bound[0],)).fetchone()
        # A reviewed partition or occurrence correction, or a source that now
        # names a different official id, moves a binding; otherwise the
        # established source record wins over changing attributes.
        moved = (
            assignment
            or (evidence.get("partition") and evidence.get("partition") != previous["partition"])
            or _hard_id_conflict(json.loads(previous["evidence_json"]), evidence)
        )
        if not moved:
            row = previous
            identity = row["identity_key"]
    # An assignment record carries the printed speaker's profile, not its owner's, so
    # it links nothing (also after the assignment leaves the file: the record stays).
    if assignment or (row and is_placed_identity(row["identity_key"])):
        evidence["profile_blocked"] = True
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS registry_touched (id TEXT PRIMARY KEY NOT NULL)")
    if row:
        record_id, home = row["id"], resolve(conn, row["home_person_id"])
        previous = json.loads(row["evidence_json"])
        was_mdb = bool(previous.get("ever_mdb") or previous.get("is_mdb"))
        if not conn.execute("SELECT 1 FROM registry_touched WHERE id = ?", (record_id,)).fetchone():
            # First touch in this build: the source speaks again, so nothing but the
            # registry's own ever_mdb (re-derived below) survives from the earlier
            # build; an id the source stopped supplying cannot keep linking records.
            previous = {}
        evidence["ever_mdb"] = bool(evidence.get("ever_mdb") or was_mdb)
        previous.update({k:v for k,v in evidence.items() if v is not None})
        previous.pop("vacated", None)
        evidence = previous
    else:
        record_id = stable_key("mp", identity)
        xml = evidence.get("xml_redner_id")
        dip = evidence.get("dip_person_id")
        preferred = stable_key("person", "xml", xml) if xml and not evidence.get("partition") else stable_key("person", "dip", dip) if dip else None
        owner_issued = assignment and conn.execute("SELECT 1 FROM persons WHERE id=?", (assignment,)).fetchone()
        home = resolve(conn, assignment) if owner_issued else allocate(conn, preferred)
        evidence = {k: v for k, v in evidence.items() if v is not None}
    if evidence.get("profile_blocked"):
        evidence.update(aw_politician_id=None, aw_match=PARTITIONED, profile_url=None)
    conn.execute("INSERT OR IGNORE INTO registry_touched VALUES (?)", (record_id,))
    if bound and bound[0] != record_id:
        # The occurrence left its old record; once nothing is bound to it any more
        # that record is stale evidence, which reconcile no longer matches on.
        old = conn.execute("SELECT evidence_json FROM person_records WHERE id=?", (bound[0],)).fetchone()
        conn.execute("UPDATE person_records SET evidence_json=? WHERE id=?",
                     (json.dumps({**json.loads(old[0]), "vacated": True}, ensure_ascii=False, sort_keys=True), bound[0]))
    # The current person restarts from the durable home on every touch; reconcile
    # recomputes any guess merge.
    conn.execute("INSERT INTO person_records VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET evidence_json=excluded.evidence_json, person_id=excluded.person_id",
                 (record_id, identity, home, json.dumps(evidence, ensure_ascii=False, sort_keys=True), evidence.get("partition"), home))
    if occurrence:
        conn.execute("INSERT INTO person_bindings VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET record_id=excluded.record_id, person_id=excluded.person_id", (occurrence, record_id, home))
    return record_id, home, identity, evidence

def merge(conn: sqlite3.Connection, keys: list[str], survivor: str | None = None) -> str:
    keys = {resolve(conn, key) for key in keys}
    placeholders = ",".join("?" for _ in keys)
    ordinals = {row[0]:row[1] for row in conn.execute(f"SELECT id, ordinal FROM persons WHERE id IN ({placeholders})", sorted(keys))}
    if not keys or not keys <= ordinals.keys():
        raise RegistryError(f"Merge refers to unknown persons: {sorted(keys - ordinals.keys())}")
    if survivor:
        if resolve(conn, survivor) not in keys or not conn.execute("SELECT 1 FROM persons WHERE id=?", (survivor,)).fetchone():
            raise RegistryError(f"Merge survivor {survivor} is not a member")
        conn.execute("DELETE FROM person_aliases WHERE id=?", (survivor,))
        keys.add(survivor)
    else:
        survivor = min(keys, key=ordinals.get)
    for retired in keys - {survivor}:
        conn.execute("INSERT INTO person_aliases VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET person_id=excluded.person_id", (retired, survivor))
        for table in ("person_records", "person_bindings", "mps"):
            conn.execute(f"UPDATE {table} SET person_id=? WHERE person_id=?", (survivor, retired))
    return survivor

def mp_keys(row: dict[str, Any]) -> list[str]:
    """Personenkennungen of an MP row, used to link rows that describe the same
    person across sources (DIP roster vs. protocol speaker). An abgeordnetenwatch
    id counts only when it was looked up by the Redner-ID (match kind ext_id); one
    found by searching a name is a Namensabgleich and links nothing."""
    keys: list[str] = []
    if derive.trusted_aw_id({"id": row.get("aw_politician_id")}, row.get("aw_match")) is not None:
        keys.append(f"aw:{row['aw_politician_id']}")
    if row.get("dip_person_id"):
        keys.append(f"dip:{row['dip_person_id']}:{row['partition']}" if row.get("partition") else f"dip:{row['dip_person_id']}")
    xml_id = derive.first_redner_id(row.get("xml_redner_id"))
    if xml_id:
        keys.append(f"xml:{xml_id}:{row['partition']}" if row.get("partition") else f"xml:{xml_id}")
    return keys


# The external ids a row carries, bucketed by kind. Two rows may only be merged
# by name+party when their id buckets do not contradict each other.
def _mp_external_ids(row: dict[str, Any]) -> dict[str, set[str]]:
    ids: dict[str, set[str]] = {"aw": set(), "dip": set(), "xml": set(), "profile": set()}
    if derive.trusted_aw_id({"id": row.get("aw_politician_id")}, row.get("aw_match")) is not None:
        ids["aw"].add(str(row["aw_politician_id"]))
    if row.get("dip_person_id"):
        ids["dip"].add(str(row["dip_person_id"]))
    xml_id = derive.first_redner_id(row.get("xml_redner_id"))
    if xml_id:
        ids["xml"].add(xml_id)
    if row.get("profile_url"):
        ids["profile"].add(str(row["profile_url"]))
    return ids


# Union of the id buckets across all rows already merged into one person.
def _merge_external_ids(rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    merged: dict[str, set[str]] = {"aw": set(), "dip": set(), "xml": set(), "profile": set()}
    for row in rows:
        for kind, values in _mp_external_ids(row).items():
            merged[kind].update(values)
    return merged


# True when both sides carry ids of the same kind and none of them overlap -
# that is positive evidence of two different people, so no merge.
def _external_ids_conflict(left: dict[str, set[str]], right: dict[str, set[str]]) -> bool:
    for kind in left:
        if left[kind] and right[kind] and not (left[kind] & right[kind]):
            return True
    return False


def clean_mp_name(name: Any) -> str:
    # Roster display names are the verbose DIP "titel" ("Dr. Carolin Wagner, MdB,
    # SPD"); trim the ", MdB…" tail for a clean profile heading. Speaker names
    # (plain) pass through unchanged.
    text = str(name or "").strip()
    return text.split(", MdB")[0].strip() or text


# Academic titles are written on one side and left off on the other ("Dr. Janosch
# Dahmen" in a Redner line, "Janosch Dahmen" in a vote list), so they are not part of
# the name a bucket is keyed by. Only leading ones go, and never the last two words.
_MP_TITLE_WORDS = frozenset(
    {"dr", "prof", "dipl", "ing", "med", "jur", "rer", "nat", "phil", "h", "c", "habil", "mult", "univ", "mag"}
)


# Casefolded, whitespace-collapsed, title-free name used as a merge bucket key.
def _normalized_mp_name(name: Any) -> str:
    words = re.sub(r"\s+", " ", clean_mp_name(name).casefold()).strip().split(" ")
    while len(words) > 2 and words[0].rstrip(".") in _MP_TITLE_WORDS:
        words.pop(0)
    return " ".join(word for word in words if word)


# Party names differ in spelling between sources ("BÜNDNIS 90/DIE GRÜNEN" vs
# "Grüne"), so compare the normalised token set instead of the raw string.
def _normalized_mp_party(party: Any) -> str:
    text = str(party or "").strip()
    if not text:
        return ""
    normalized = derive.zusammenschluss(text)
    if not normalized:
        return ""
    tokens = sorted(aw._party_tokens(normalized))
    return "|".join(tokens) if tokens else normalized.casefold()



def match_rows(rows: list[dict[str, Any]], *, guesses: bool = True) -> tuple[dict, dict]:
    """Group rows into persons. ``guesses=False`` stops after the passes that rest
    on a shared Personenkennung; the name-based passes only ever propose."""
    # Union-find: link rows that share any external id into one person.
    parent = {row["id"]: row["id"] for row in rows}
    totals = {"ext_id": 0, "corroborated_name": 0, "unique_name": 0, "buckets_split_namesakes": 0, "buckets_split_3plus": 0}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    members_by_root = {row["id"]: [row] for row in rows}
    by_id = {row["id"]: row for row in rows}

    def union(a: str, b: str, kind: str) -> bool:
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        partitions = {member.get("partition") for member in members_by_root[ra] + members_by_root[rb] if member.get("partition")}
        if len(partitions) > 1:
            return False
        parent[ra] = rb
        members_by_root[rb].extend(members_by_root.pop(ra))
        totals[kind] += 1
        return True

    # Pass 1: merge rows that share a Personenkennung (a Redner-ID, a DIP
    # person id, an abgeordnetenwatch id looked up by Redner-ID).
    first_for_key: dict[str, str] = {}
    for row in rows:
        for key in mp_keys(row):
            if key in first_for_key:
                union(row["id"], first_for_key[key], "ext_id")
            else:
                first_for_key[key] = row["id"]

    if not guesses:
        durable: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            durable.setdefault(find(row["id"]), []).append(row)
        return durable, totals

    # Pass 1b: a record whose abgeordnetenwatch id was found by name joins the
    # record that holds the same id as a Personenkennung when both carry the same
    # name (titles aside). This is how a Person with two Redner-IDs (an MdB id and
    # one for a government role) is put back together: the name search returned
    # the profile the Redner-ID lookup found for the other record. A different
    # name is no corroboration (a namesake's profile), and a contradicting DIP or
    # abgeordnetenwatch Personenkennung blocks it. Redner-IDs are not compared:
    # two of them for one Person is exactly the case.
    def strong_ids(root: str) -> dict[str, set[str]]:
        ids = _merge_external_ids(members_by_root[root])
        return {kind: ids[kind] for kind in ("aw", "dip")}

    for row in rows:
        aw_id = row.get("aw_politician_id")
        # A partitioned or reviewed record carries its profile only as an
        # attribute: it must not rejoin the record that holds the same id.
        if aw_id is None or row.get("partition") or derive.trusted_aw_id({"id": aw_id}, row.get("aw_match")) is not None:
            continue
        other = first_for_key.get(f"aw:{aw_id}")
        name = _normalized_mp_name(row.get("display_name"))
        if other is None or not name or find(other) == find(row["id"]):
            continue
        other_name = _normalized_mp_name(by_id[other].get("display_name"))
        if name == other_name and not _external_ids_conflict(strong_ids(find(row["id"])), strong_ids(find(other))):
            union(row["id"], other, "corroborated_name")

    rows_of: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        rows_of.setdefault(find(row["id"]), []).append(row)

    def sides(root: str) -> set[str]:
        # "speaker": a Plenarprotokoll named this record as a Redner. "roster":
        # everything else (a DIP person, a roll-call member).
        return {"speaker" if member.get("xml_redner_id") else "roster" for member in rows_of[root]}

    # Pass 2: Namensabgleich on the records pass 1 left. A name+party bucket
    # merges only when it holds exactly two records, one on each side, and no
    # Personenkennung of one contradicts one of the other. It is a guess, so
    # any other shape stays split. Buckets are judged on the records passes 1 and 1b left and
    # the unions applied afterwards.
    buckets: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        name_key = _normalized_mp_name(row.get("display_name"))
        party_key = _normalized_mp_party(row.get("party"))
        if name_key and party_key:
            buckets.setdefault((name_key, party_key), set()).add(find(row["id"]))

    pending: list[tuple[str, str]] = []
    for records in buckets.values():
        if len(records) < 2:
            continue
        ordered = sorted(records)
        speaker = [root for root in ordered if "speaker" in sides(root)]
        roster = [root for root in ordered if "roster" in sides(root)]
        if (
            len(ordered) == 2
            and len(speaker) == 1
            and len(roster) == 1
            and speaker[0] != roster[0]
            and not _external_ids_conflict(
                _merge_external_ids(rows_of[speaker[0]]), _merge_external_ids(rows_of[roster[0]])
            )
        ):
            pending.append((speaker[0], roster[0]))
        elif len(ordered) >= 3:
            totals["buckets_split_3plus"] += 1
        else:
            totals["buckets_split_namesakes"] += 1
    for left, right in pending:
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            continue
        # Earlier queued joins can add identifiers to either component. Check
        # the current components so aliases cannot bridge two different people.
        if _external_ids_conflict(
            _merge_external_ids(rows_of[left_root]), _merge_external_ids(rows_of[right_root])
        ):
            totals["buckets_split_namesakes"] += 1
            continue
        if union(left, right, "unique_name"):
            rows_of[right_root].extend(rows_of.pop(left_root))

    # Group the merged rows back into one bucket per person.
    components: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        components.setdefault(find(row["id"]), []).append(row)

    return components, totals

def _load_rows(conn: sqlite3.Connection, touched: set[str] | None = None) -> list[dict[str, Any]]:
    """Every record's evidence with its current person, its partition (a reviewed
    owner resolved through the alias chain, so a merged owner compares equal to
    its survivor) and whether it is live. In a full build a record is live when
    this build touched it (``touched``); otherwise when it is bound, or was never
    vacated by an occurrence moving to another record. A record that is not live
    is stale evidence: it keeps its person but takes part in no match."""
    bound = set() if touched is not None else {row[0] for row in conn.execute("SELECT DISTINCT record_id FROM person_bindings")}
    rows = []
    for record in conn.execute("SELECT * FROM person_records ORDER BY id"):
        evidence = json.loads(record["evidence_json"])
        partition = record["partition"]
        if partition and partition.startswith(REVIEWED_PREFIX):
            partition = REVIEWED_PREFIX + resolve(conn, partition[len(REVIEWED_PREFIX):])
            evidence["aw_match"] = PARTITIONED  # a reviewed record's profile links nothing, as at bind time
        live = record["id"] in touched if touched is not None else record["id"] in bound or not evidence.get("vacated")
        evidence.update(id=record["id"], person_id=record["person_id"], partition=partition, live=live)
        rows.append(evidence)
    return rows


def _block_profile(conn: sqlite3.Connection, record: str) -> None:
    """Strip the profile of a record an assignment placed on another person."""
    evidence = json.loads(conn.execute("SELECT evidence_json FROM person_records WHERE id=?", (record,)).fetchone()[0])
    evidence.update(profile_blocked=True, aw_politician_id=None, aw_match=PARTITIONED, profile_url=None)
    conn.execute("UPDATE person_records SET evidence_json=? WHERE id=?", (json.dumps(evidence, ensure_ascii=False, sort_keys=True), record))
    conn.execute("UPDATE mps SET aw_politician_id=NULL, aw_match=NULL, profile_url=NULL WHERE id=?", (record,))


def _is_reviewed(row: dict[str, Any]) -> bool:
    return str(row.get("partition") or "").startswith(REVIEWED_PREFIX)


def _assign(conn: sqlite3.Connection, record: str, person: str, *, home: bool = False, partition: str | None = None) -> None:
    """Point a record, its occurrence bindings and its mps row at a person."""
    conn.execute("UPDATE person_records SET person_id=? WHERE id=? AND person_id != ?", (person, record, person))
    if home:
        conn.execute("UPDATE person_records SET home_person_id=? WHERE id=?", (person, record))
    if partition is not None:
        conn.execute("UPDATE person_records SET partition=? WHERE id=?", (partition, record))
    conn.execute("UPDATE mps SET person_id=? WHERE id=? AND person_id != ?", (person, record, person))
    conn.execute("UPDATE person_bindings SET person_id=? WHERE record_id=? AND person_id != ?", (person, record, person))


def _guess_merges(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> dict[str, int]:
    """Apply the name-based guesses to the current persons, from the rows alone.

    A pure function of ``rows``: it reads no earlier guess, so a replay, an
    incremental build and a fresh build agree. Only live, unreviewed records are
    matched (a reviewed record is an explicit decision, a vacated one is stale
    evidence), but whole persons move, so a guess can never tear a durable or
    reviewed merge apart. A group that would join two reviewed owners, two
    partitions, or persons whose official ids contradict stays split; a reviewed
    owner keeps its key when a group has exactly one."""
    components, totals = match_rows([row for row in rows if row["live"] and not _is_reviewed(row)])
    parent: dict[str, str] = {}

    def find(person: str) -> str:
        parent.setdefault(person, person)
        while parent[person] != person:
            parent[person] = parent[parent[person]]
            person = parent[person]
        return person

    for members in components.values():
        first = find(members[0]["person_id"])
        for row in members[1:]:
            parent[find(row["person_id"])] = first
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(find(row["person_id"]), []).append(row)
    live = [row for row in rows if row["live"]]
    reviewed_persons = {row["person_id"] for row in live if _is_reviewed(row)}
    ordinals = {row[0]: row[1] for row in conn.execute("SELECT id, ordinal FROM persons")}
    for members in groups.values():
        persons = {row["person_id"] for row in members}
        reviewed = persons & reviewed_persons
        partitions = {row["partition"] for row in members if row["live"] and row.get("partition")}
        if len(persons) < 2 or len(partitions) > 1:  # a reviewed owner has its own partition, so two of them never join
            continue
        by_person: dict[str, list[dict[str, Any]]] = {}
        for row in members:
            if row["live"]:
                by_person.setdefault(row["person_id"], []).append(row)
        # Redner-IDs are left out: one person can hold two of them (match_rows, pass 1b).
        known = {person: {kind: ids[kind] for kind in ("aw", "dip")}
                 for person, ids in ((person, _merge_external_ids(rows_of)) for person, rows_of in by_person.items())}
        if any(_external_ids_conflict(known[a], known[b]) for a, b in itertools.combinations(known, 2)):
            continue
        survivor = next(iter(reviewed)) if reviewed else min(persons, key=ordinals.get)
        for row in members:
            if row["person_id"] != survivor:
                _assign(conn, row["id"], survivor)
    return totals


def reconcile(conn: sqlite3.Connection, *, full_build: bool = False) -> dict[str, int]:
    """Settle which person every record belongs to.

    Durable: the issued home key, reviewed corrections, and merges that rest on a
    shared Personenkennung (retired keys stay as aliases). Recomputed on every run: the name-based guesses
    (``_guess_merges``), which move a record's current person without retiring any
    key, so a guess that stops holding, or arrives in another order, leaves no trace.

    ``full_build``: every live occurrence was bound again on this connection (the
    staged rebuild), so a record nothing touched is stale and is ignored by every
    match; a direct single-report persist leaves it False."""
    validate(conn)
    data = corrections()
    touched = None
    if full_build:
        touched = set()
        if conn.execute("SELECT 1 FROM sqlite_temp_master WHERE name='registry_touched'").fetchone():
            touched = {row[0] for row in conn.execute("SELECT id FROM temp.registry_touched")}
    # Every record restarts from its durable home.
    for record in conn.execute("SELECT id, home_person_id FROM person_records").fetchall():
        _assign(conn, record["id"], resolve(conn, record["home_person_id"]))
    rows = _load_rows(conn, touched)
    # Explicit assignments/splits block automatic reconciliation across owners.
    by_id = {row["id"]:row for row in rows}
    assigned = {}
    placed_records = set()  # records an occurrence assignment placed (their profile links nothing)
    for assignment in data["assignments"]:
        occurrence, owner = assignment["occurrence_id"], assignment["person_id"]
        binding = conn.execute("SELECT record_id FROM person_bindings WHERE id=?", (occurrence,)).fetchone()
        if binding is None:
            raise RegistryError(f"Unknown occurrence {occurrence}")
        record = binding[0]
        placed_records.add(record)
        if not conn.execute("SELECT 1 FROM persons WHERE id=?", (owner,)).fetchone():
            raise RegistryError(f"Unknown assignment person {owner}")
        owner = resolve(conn, owner)
        if record in assigned and assigned[record] != owner:
            raise RegistryError(f"Contradictory assignments for {record}; partition the source identity first")
        assigned[record] = owner
    for split in data["splits"]:
        original, retained = split["person_id"], split["retain_records"]
        moved = split["new_records"]
        if not retained or not moved or set(retained) & set(moved):
            raise RegistryError("Split must designate disjoint retained and new records")
        if any(record not in by_id for record in retained + moved):
            raise RegistryError(f"Split of {original} names unknown records")
        if not conn.execute("SELECT 1 FROM persons WHERE id=?", (original,)).fetchone():
            raise RegistryError(f"Split owner {original} is unknown")
        # A shared Personenkennung may have merged the original into another
        # person since the split was written; the retained records follow it.
        current = resolve(conn, original)
        new_id = allocate(conn, split.get("new_person_id") or stable_key("person-split", original, sorted(moved)))
        if new_id in (original, current):
            raise RegistryError(f"Split of {original} must issue a different person key")
        for record in retained + moved:
            owner = current if record in retained else new_id
            if record in assigned and assigned[record] != owner:
                raise RegistryError(f"Contradictory split assignment for {record}")
            assigned[record] = owner
    for record, owner in assigned.items():
        _assign(conn, record, owner, home=True, partition=f"{REVIEWED_PREFIX}{owner}")
    for record in placed_records:
        _block_profile(conn, record)
    # Durable merges: records that share a Personenkennung, then reviewed merges.
    # A person that holds a reviewed record keeps its key when it is merged.
    rows = _load_rows(conn, touched)
    reviewed_persons = {row["person_id"] for row in rows if _is_reviewed(row)}
    for members in match_rows([row for row in rows if row["live"]], guesses=False)[0].values():
        persons = {resolve(conn, row["person_id"]) for row in members}
        owners = {resolve(conn, person) for person in persons & reviewed_persons}
        merge(conn, sorted(persons), next(iter(owners)) if len(owners) == 1 else None)
    for correction in data["merges"]:
        merge(conn, correction["persons"], correction.get("survivor"))
    totals = _guess_merges(conn, _load_rows(conn, touched))
    validate(conn)
    return totals


def validate(conn: sqlite3.Connection) -> None:
    seen: dict[str, str] = {}
    for row in conn.execute("SELECT id FROM persons"):
        if not PERSON_KEY_RE.fullmatch(row[0]) or row[0].casefold() in RESERVED_PERSON_KEYS:
            raise RegistryError(f"Invalid registry person key {row[0]!r}; restore the build-store backup")
        if seen.setdefault(row[0].casefold(), row[0]) != row[0]:
            raise RegistryError(f"Registry person keys {seen[row[0].casefold()]!r} and {row[0]!r} differ only by case; restore the build-store backup")
    for row in conn.execute("SELECT id FROM person_aliases"):
        resolve(conn, row[0])
    for row in conn.execute("SELECT id, evidence_json FROM person_records"):
        try:
            if not isinstance(json.loads(row[1]), dict):
                raise ValueError("expected object")
        except ValueError as exc:
            raise RegistryError(f"Unreadable registry evidence {row[0]}: {exc}") from exc
    failures = conn.execute("PRAGMA foreign_key_check").fetchall()
    if failures:
        raise RegistryError(f"Registry foreign-key violations: {failures[:3]}")


def require_current(conn: sqlite3.Connection) -> None:
    """A registry that exists must be complete and of this layout."""
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not tables.intersection(REGISTRY_TABLES):
        return
    if not set(REGISTRY_TABLES) <= tables:
        raise RegistryError("Incomplete person registry; restore the build-store backup")
    if "home_person_id" not in {row[1] for row in conn.execute("PRAGMA table_info(person_records)")}:
        raise RegistryError("Person registry from an unreleased A.2 draft cannot be carried forward; re-mint it by running --offline --repersist on a schema 2 build-store backup")


def copy_previous(previous: sqlite3.Connection, target: sqlite3.Connection) -> None:
    require_current(previous)
    tables = {row[0] for row in previous.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not tables.intersection(REGISTRY_TABLES):
        if "mps" in tables and "person_id" in {row[1] for row in previous.execute("PRAGMA table_info(mps)")}:
            raise RegistryError("Incomplete person registry; restore the build-store backup")
        return
    validate(previous)
    for table in REGISTRY_TABLES:
        columns = [row[1] for row in previous.execute(f"PRAGMA table_info({table})")]
        placeholders = ','.join('?' for _ in columns)
        target.executemany(f"INSERT INTO {table} VALUES ({placeholders})", [tuple(row) for row in previous.execute(f"SELECT * FROM {table}")])
    target.commit()
