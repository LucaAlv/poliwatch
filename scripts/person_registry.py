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
#: aw_match value of a partition record: its profile is never a trusted join key.
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
    return _load_corrections(CORRECTIONS_PATH)


@lru_cache(maxsize=8)
def _load_corrections(path: Path) -> dict[str, Any]:
    """Read once per process: a build is one process, and bind() asks for the
    corrections on every occurrence. An unreadable file is not cached."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("expected a version 1 object")
        for name in ("partitions", "assignments", "merges", "splits"):
            if not isinstance(data.get(name), list):
                raise ValueError(f"{name} must be an array")
        # Records placed on another person (occurrence assignments, splits) are
        # disabled until their redesign (TODOS.md "Reviewed reassignment of a
        # source record"); a partition or a merge covers today's corrections.
        for name in ("assignments", "splits"):
            if data[name]:
                raise ValueError(f"{name} are disabled until the placed-record redesign; use a partition or a merge")
        required = {"partitions": ("xml_redner_id", "labels"), "merges": ("persons",)}
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

        partitioned_ids = set()
        for partition in data["partitions"]:
            xml_id = text(partition["xml_redner_id"], "partition xml_redner_id")
            if xml_id in partitioned_ids:
                raise ValueError(f"Redner-ID {xml_id} is partitioned twice; use one entry")
            partitioned_ids.add(xml_id)
            if not isinstance(partition["labels"], dict) or not partition["labels"]:
                raise ValueError("partition labels must be a nonempty name-to-owner object")
            owner_of_name: dict[str, str] = {}
            for label, owner in partition["labels"].items():
                text(owner, f"partition owner of {label!r}")
                name = _normalized_mp_name(label)
                if owner_of_name.setdefault(name, owner) != owner:
                    raise ValueError(f"partition labels for {name!r} name two owners")
            # Consumers read the normalised object, so null and [] are refused here.
            occurrences = partition.setdefault("occurrences", {})
            if not isinstance(occurrences, dict):
                raise ValueError("partition occurrences must be an object")
            if partition.get("profile_owner") is not None:
                if text(partition["profile_owner"], "partition profile_owner") not in owner_of_name.values():
                    raise ValueError(f"partition profile_owner {partition['profile_owner']!r} is not one of its label owners")
            for key, reviewed in occurrences.items():
                if not isinstance(reviewed, dict):
                    raise ValueError(f"partition occurrence {key!r} must be an object")
                text(reviewed.get("display_name"), f"display_name of partition occurrence {key!r}")
        for merge_ in data["merges"]:
            texts(merge_["persons"], "merge persons")
            if merge_.get("survivor") is not None:
                text(merge_["survivor"], "merge survivor")
        return data
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RegistryError(f"Unreadable person corrections {path}: {exc}") from exc

def corrected_speaker(speaker: dict[str, Any], protocol_id: Any, rede_id: Any) -> dict[str, Any]:
    speaker = dict(speaker)
    for partition in corrections()["partitions"]:
        if derive.first_redner_id(speaker.get("xml_redner_id")) == partition["xml_redner_id"]:
            reviewed = partition["occurrences"].get(f"{protocol_id}/{rede_id}")
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
        if derive.first_redner_id(evidence.get("xml_redner_id")) != partition["xml_redner_id"]:
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

def _first_touch(conn: sqlite3.Connection, record_id: str, baseline: str | None = None) -> bool:
    """Mark a record as bound on this connection (a full build's live set, read
    by reconcile); True the first time. ``baseline`` is the evidence it had
    before this build touched it, kept so later decisions about the record do not
    depend on which occurrence was persisted first. The temp table is made on
    first use."""
    insert = "INSERT OR IGNORE INTO registry_touched VALUES (?, ?)"
    try:
        return conn.execute(insert, (record_id, baseline)).rowcount == 1
    except sqlite3.OperationalError:
        conn.execute("CREATE TEMP TABLE IF NOT EXISTS registry_touched (id TEXT PRIMARY KEY NOT NULL, baseline TEXT)")
        return conn.execute(insert, (record_id, baseline)).rowcount == 1


def _touched(conn: sqlite3.Connection, record_id: str) -> tuple[bool, str | None]:
    """``(touched in this build, baseline evidence json)`` of a record."""
    try:
        row = conn.execute("SELECT baseline FROM registry_touched WHERE id = ?", (record_id,)).fetchone()
    except sqlite3.OperationalError:
        return False, None
    return (row is not None), (row[0] if row else None)


def _redner_ids(evidence: dict[str, Any]) -> set[str]:
    """Every Redner-ID a record's evidence names (one person can have several);
    old evidence has only the flat ``xml_redner_id``."""
    ids = evidence.get("xml_redner_ids")
    if ids is None:
        ids = [evidence.get("xml_redner_id")]
    return {first for first in (derive.first_redner_id(i) for i in ids) if first}


def _name_party_pairs(evidence: dict[str, Any]) -> list[list[str | None]]:
    """The (printed name, party) pairs a record's evidence holds, sorted; old
    evidence and store rows have only the flat ``display_name`` and ``party``."""
    pairs = evidence.get("pairs")
    if pairs is None:
        pairs = [[evidence.get("display_name"), evidence.get("party")]] if evidence.get("display_name") else []
    return pairs


def _hard_id_conflict(old: dict[str, Any], new: dict[str, Any]) -> bool:
    """Both sides name an official id and the new one is not among the old ones:
    the source now says a different person, which is not an enrichment of the
    bound record."""
    old_ids, new_ids = _redner_ids(old), _redner_ids(new)
    if old_ids and new_ids and not new_ids <= old_ids:
        return True
    return bool(old.get("dip_person_id") and new.get("dip_person_id") and old["dip_person_id"] != new["dip_person_id"])


def _json_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _pair_rank(pair: list[str | None]) -> tuple[Any, ...]:
    return (pair[0] == "Unbekannt", not pair[1], -len(pair[0]), pair[0], pair[1] or "")


def _representative_pair(pairs: list[list[str | None]]) -> list[str | None]:
    """The (page name, party) a record shows when its occurrences print several:
    the name of the best pair (a real name over the "Unbekannt" placeholder, one
    with a party over one without, the fullest name with titles, then
    alphabetical) and the party of the best pair that has one, so a real name
    printed without a party still shows the party its other pairs name. Binding
    has no sitting chronology, so "newest" is not available; the matching rule
    uses every pair, not this one."""
    with_party = [p for p in pairs if p[1]]
    return [min(pairs, key=_pair_rank)[0], min(with_party, key=_pair_rank)[1] if with_party else None]


#: The abgeordnetenwatch fields of a record are chosen together, never mixed.
_AW_FIELDS = ("aw_politician_id", "aw_match", "profile_url")


def _aw_choice(unit: tuple[Any, ...]) -> tuple[Any, ...]:
    """Which abgeordnetenwatch unit wins: one with a valid id, a trusted lookup, the
    fullest, then by content."""
    return (not isinstance(unit[0], int), unit[1] != derive.TRUSTED_AW_MATCH, -sum(v is not None for v in unit), _json_key(unit))


#: Biography attributes. A roster occurrence (``is_mdb``) is the authority for
#: them; a cached dossier's or a speaker's value only stands in when no roster
#: occurrence supplies one, so a stale cached value never beats the live roster.
_BIO_FIELDS = ("title", "function", "wahlperiode", "birth_year", "gender", "profession", "wahlkreis", "bundesland",
               "person_roles_json")


def _roster_bio(evidence: dict[str, Any]) -> dict[str, Any]:
    """The biography values the roster occurrences of a record supplied: kept as
    ``roster_bio`` once folded, read off the attributes of a single roster occurrence."""
    if "roster_bio" in evidence:
        return evidence["roster_bio"]
    return {f: evidence[f] for f in _BIO_FIELDS if evidence.get(f) is not None} if evidence.get("is_mdb") else {}


def _fold(base: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Fold one occurrence's evidence into a record's evidence for this build.

    Commutative, associative and idempotent, so the result depends on the set of
    occurrences and not on the order they are persisted in. Names and parties are
    kept as a set of pairs, Redner-IDs as a set; the flat ``display_name``,
    ``party`` and ``xml_redner_id`` are a representative of those sets. Booleans
    OR, the abgeordnetenwatch fields are chosen as a unit (a trusted lookup first),
    the biography attributes come from roster occurrences when there are any, and
    any other attribute that differs takes the smallest value."""
    out = dict(base)
    roster_base, roster_new = _roster_bio(base), _roster_bio(new)
    roster = {f: min((r[f] for r in (roster_base, roster_new) if f in r), key=_json_key)
              for f in _BIO_FIELDS if f in roster_base or f in roster_new}
    pairs = {tuple(p) for p in _name_party_pairs(base)} | {tuple(p) for p in _name_party_pairs(new)}
    ids = _redner_ids(base) | _redner_ids(new)
    units = [tuple(e.get(f) for f in _AW_FIELDS) for e in (base, new) if any(e.get(f) is not None for f in _AW_FIELDS)]
    for key, value in new.items():
        if value is None or key in ("pairs", "xml_redner_ids", "roster_bio", *_AW_FIELDS, *_BIO_FIELDS):
            continue
        if isinstance(value, bool) or isinstance(out.get(key), bool):
            out[key] = bool(out.get(key)) or bool(value)
        elif out.get(key) is None:
            out[key] = value
        elif out[key] != value:
            out[key] = min(out[key], value, key=_json_key)
    for field in _BIO_FIELDS:
        stand_in = [e[field] for e, r in ((base, roster_base), (new, roster_new)) if e.get(field) is not None and field not in r]
        value = roster.get(field, min(stand_in, key=_json_key) if stand_in else None)
        if value is None:
            out.pop(field, None)
        else:
            out[field] = value
    out["roster_bio"] = roster
    if units:
        for field, value in zip(_AW_FIELDS, min(units, key=_aw_choice)):
            if value is None:
                out.pop(field, None)
            else:
                out[field] = value
    if pairs:
        out["pairs"] = sorted([list(p) for p in pairs], key=_json_key)
        name, party = _representative_pair(out["pairs"])
        out["display_name"] = name
        if party is None:
            out.pop("party", None)
        else:
            out["party"] = party
    if ids:
        out["xml_redner_ids"] = sorted(ids)
        out["xml_redner_id"] = min(ids)
    return out


def bind(
    conn: sqlite3.Connection, identity: str, evidence: dict[str, Any],
    occurrence: str | None = None,
) -> tuple[str, str, str, dict[str, Any]]:
    """Bind one source occurrence to a source record and its home person.

    Returns ``(record_id, home_person_id, identity_key, evidence)``. An occurrence
    that is already bound keeps its record while the source only enriches it; it
    moves to the record of the new identity on a changed reviewed partition or a
    different official id. Evidence is re-read from the source on a record's first
    touch in this connection; only registry-owned evidence survives from the
    earlier build. Every later touch folds its occurrence in with ``_fold``, and a
    record's decisions compare against its evidence from before the build, so
    neither the evidence nor the binding depends on persist order."""
    evidence["ever_mdb"] = bool(evidence.get("is_mdb"))
    identity = partition_identity(identity, evidence)
    row = conn.execute("SELECT * FROM person_records WHERE identity_key = ?", (identity,)).fetchone()
    bound = conn.execute("SELECT record_id FROM person_bindings WHERE id = ?", (occurrence,)).fetchone() if occurrence else None
    bound_touched = False
    if bound:
        previous = conn.execute("SELECT * FROM person_records WHERE id = ?", (bound[0],)).fetchone()
        bound_touched, baseline = _touched(conn, bound[0])
        # A reviewed partition, or a source that now names a different official
        # id, moves a binding; otherwise the established source record wins over
        # changing attributes.
        moved = (
            (evidence.get("partition") and evidence.get("partition") != previous["partition"])
            or _hard_id_conflict(json.loads(baseline or previous["evidence_json"]), evidence)
        )
        if not moved:
            row = previous
            identity = row["identity_key"]
    if row:
        record_id, home = row["id"], resolve(conn, row["home_person_id"])
        previous = json.loads(row["evidence_json"])
        was_mdb = bool(previous.get("ever_mdb") or previous.get("is_mdb"))
        if _first_touch(conn, record_id, row["evidence_json"]):
            # First touch in this build: the source speaks again, so nothing but the
            # registry's own ever_mdb (re-derived below) survives from the earlier
            # build; an id the source stopped supplying cannot keep linking records.
            previous = {}
        evidence["ever_mdb"] = bool(evidence.get("ever_mdb") or was_mdb)
        previous.pop("vacated", None)
        evidence = _fold(previous, evidence)
    else:
        record_id = stable_key("mp", identity)
        xml = evidence.get("xml_redner_id")
        dip = evidence.get("dip_person_id")
        preferred = stable_key("person", "xml", xml) if xml and not evidence.get("partition") else stable_key("person", "dip", dip) if dip else None
        home = allocate(conn, preferred)
        _first_touch(conn, record_id)
        evidence = _fold({}, evidence)
    if evidence.get("profile_blocked"):
        evidence.update(aw_politician_id=None, aw_match=PARTITIONED, profile_url=None)
    if bound and bound[0] != record_id and not bound_touched:
        # The occurrence left its old record; once nothing is bound to it any more
        # that record is stale evidence, which reconcile no longer matches on. A
        # record this build touched is live and is not marked, whichever order
        # its occurrences were persisted in.
        old = conn.execute("SELECT evidence_json FROM person_records WHERE id=?", (bound[0],)).fetchone()
        conn.execute("UPDATE person_records SET evidence_json=? WHERE id=?",
                     (json.dumps({**json.loads(old[0]), "vacated": True}, ensure_ascii=False, sort_keys=True), bound[0]))
    # The current person restarts from the durable home on every touch; reconcile
    # recomputes any guess merge. A repeat touch that changes nothing (most vote
    # members and speeches) skips the write.
    evidence_json = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    if not (row and row["id"] == record_id and row["evidence_json"] == evidence_json and row["person_id"] == home):
        conn.execute("INSERT INTO person_records VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET evidence_json=excluded.evidence_json, person_id=excluded.person_id",
                     (record_id, identity, home, evidence_json, evidence.get("partition"), home))
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
    for xml_id in sorted(_redner_ids(row)):
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
    ids["xml"].update(_redner_ids(row))
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



def name_party_keys(row: dict[str, Any]) -> set[tuple[str, str]]:
    """Every normalised (name, party) a record is known under, with both parts
    present: the keys of the buckets it can join."""
    keys = {(_normalized_mp_name(name), _normalized_mp_party(party)) for name, party in _name_party_pairs(row)}
    return {key for key in keys if key[0] and key[1]}


def _names(row: dict[str, Any]) -> set[str]:
    return {name for name in (_normalized_mp_name(n) for n, _ in _name_party_pairs(row)) if name}


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
        # A partitioned record carries its profile only as an
        # attribute: it must not rejoin the record that holds the same id.
        if aw_id is None or row.get("partition") or derive.trusted_aw_id({"id": aw_id}, row.get("aw_match")) is not None:
            continue
        other = first_for_key.get(f"aw:{aw_id}")
        if other is None or find(other) == find(row["id"]):
            continue
        # Any printed name in common corroborates: a record may be printed under several.
        if _names(row) & _names(by_id[other]) and not _external_ids_conflict(strong_ids(find(row["id"])), strong_ids(find(other))):
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
    # A record printed under several names or parties sits in one bucket per
    # pair.
    buckets: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        for key in name_party_keys(row):
            buckets.setdefault(key, set()).add(find(row["id"]))

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
    # A record in two qualifying buckets (a Fraktion switcher beside two roster
    # records) has no unique partner: it joins neither.
    partners: dict[str, set[str]] = {}
    for left, right in pending:
        partners.setdefault(left, set()).add(right)
        partners.setdefault(right, set()).add(left)
    for left, right in pending:
        if len(partners[left]) > 1 or len(partners[right]) > 1:
            totals["buckets_split_namesakes"] += 1
            continue
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
    """Every record's evidence with its current person, its partition and whether
    it is live. In a full build a record is live when
    this build touched it (``touched``); otherwise when it is bound, or was never
    vacated by an occurrence moving to another record. A record that is not live
    is stale evidence: it keeps its person but takes part in no match."""
    bound = set() if touched is not None else {row[0] for row in conn.execute("SELECT DISTINCT record_id FROM person_bindings")}
    rows = []
    for record in conn.execute("SELECT * FROM person_records ORDER BY id"):
        evidence = json.loads(record["evidence_json"])
        live = record["id"] in touched if touched is not None else record["id"] in bound or not evidence.get("vacated")
        evidence.update(id=record["id"], person_id=record["person_id"], partition=record["partition"], live=live)
        rows.append(evidence)
    return rows


def _assign(conn: sqlite3.Connection, record: str, person: str) -> None:
    """Point a record, its occurrence bindings and its mps row at a person."""
    conn.execute("UPDATE person_records SET person_id=? WHERE id=? AND person_id != ?", (person, record, person))
    conn.execute("UPDATE mps SET person_id=? WHERE id=? AND person_id != ?", (person, record, person))
    conn.execute("UPDATE person_bindings SET person_id=? WHERE record_id=? AND person_id != ?", (person, record, person))


def is_stale_roster_partner(evidence: dict[str, Any]) -> bool:
    """A former roster (DIP person) record this build did not list again: its
    biography stays published, so it may still join the speaker it belongs to.
    A vacated record is not one: the source said its evidence was someone else's."""
    return bool((evidence.get("ever_mdb") or evidence.get("is_mdb")) and not evidence.get("xml_redner_id")
                and not evidence.get("vacated"))


def _stale_roster_partners(
    rows: list[dict[str, Any]], components: dict[str, list[dict[str, Any]]],
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """Stale roster records that join a live person as a partner only.

    A stale record takes no part in ``match_rows``, so it cannot split a live
    bucket or bridge two live persons. It joins when it is the only stale roster
    record of its name+party, exactly one live person holds that name+party, that
    person has a speaker side but no live roster record of its own, and no
    official id or partition of the two contradicts."""
    live_by_key: dict[tuple[str, str], list[list[dict[str, Any]]]] = {}
    component_of_person: dict[str, int] = {}
    for members in components.values():
        for row in members:
            component_of_person.setdefault(row["person_id"], id(members))
        for k in set().union(*(name_party_keys(row) for row in members)):
            live_by_key.setdefault(k, []).append(members)
    stale_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        keys = name_party_keys(row)
        if not row["live"] and is_stale_roster_partner(row) and len(keys) == 1:
            stale_by_key.setdefault(next(iter(keys)), []).append(row)
    partners = []
    for k, stale in stale_by_key.items():
        targets = live_by_key.get(k, [])
        if len(stale) != 1 or len(targets) != 1:
            continue
        row, members = stale[0], targets[0]
        if component_of_person.get(row["person_id"], id(members)) != id(members):
            continue  # its person already lives in another live person
        if not any(member.get("xml_redner_id") for member in members):
            continue
        if any((member.get("ever_mdb") or member.get("is_mdb")) and not member.get("xml_redner_id") for member in members):
            continue  # the person was listed again under another roster record
        partitions = {member.get("partition") for member in [*members, row] if member.get("partition")}
        if len(partitions) > 1 or _external_ids_conflict(_merge_external_ids([row]), _merge_external_ids(members)):
            continue
        partners.append((row, members))
    return partners


def _guess_merges(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> dict[str, int]:
    """Apply the name-based guesses to the current persons, from the rows alone.

    A pure function of ``rows``: it reads no earlier guess, so a replay, an
    incremental build and a fresh build agree. Only live records are matched (a
    vacated one is stale evidence); a stale roster record joins afterwards as a
    partner only (``_stale_roster_partners``). Whole persons move, so a guess can never
    tear a durable merge apart. A group that would join two partitions, or
    persons whose official ids contradict, stays split; otherwise the person
    issued first keeps its key."""
    components, totals = match_rows([row for row in rows if row["live"]])
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
    partners = _stale_roster_partners(rows, components)
    for row, members in partners:
        parent[find(row["person_id"])] = find(members[0]["person_id"])
    joined = {row["id"] for row, _ in partners}
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(find(row["person_id"]), []).append(row)
    ordinals = {row[0]: row[1] for row in conn.execute("SELECT id, ordinal FROM persons")}
    for members in groups.values():
        persons = {row["person_id"] for row in members}
        matched = [row for row in members if row["live"] or row["id"] in joined]
        partitions = {row["partition"] for row in matched if row.get("partition")}
        if len(persons) < 2 or len(partitions) > 1:
            continue
        by_person: dict[str, list[dict[str, Any]]] = {}
        for row in matched:
            by_person.setdefault(row["person_id"], []).append(row)
        # Redner-IDs are left out: one person can hold two of them (match_rows, pass 1b).
        known = {person: {kind: ids[kind] for kind in ("aw", "dip")}
                 for person, ids in ((person, _merge_external_ids(rows_of)) for person, rows_of in by_person.items())}
        if any(_external_ids_conflict(known[a], known[b]) for a, b in itertools.combinations(known, 2)):
            continue
        survivor = min(persons, key=ordinals.get)
        for row in members:
            if row["person_id"] != survivor:
                _assign(conn, row["id"], survivor)
    return totals


def reconcile(conn: sqlite3.Connection, *, full_build: bool = False) -> dict[str, int]:
    """Settle which person every record belongs to.

    Durable: the issued home key, reviewed merges, and merges that rest on a
    shared Personenkennung (retired keys stay as aliases). Recomputed on every run: the name-based guesses
    (``_guess_merges``), which move a record's current person without retiring any
    key, so a guess that stops holding, or arrives in another order, leaves no trace.

    ``full_build``: every live occurrence was bound again on this connection (the
    staged rebuild), so a record nothing touched is stale and is ignored by every
    match. Without it (tests, a partial persist) liveness falls back to bound or never vacated."""
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
    # Durable merges: records that share a Personenkennung, then reviewed merges.
    rows = _load_rows(conn, touched)
    for members in match_rows([row for row in rows if row["live"]], guesses=False)[0].values():
        merge(conn, sorted({resolve(conn, row["person_id"]) for row in members}))
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
    # Only the tables that point into the registry: reconcile runs this twice per
    # build, and the whole store is checked once at the end of a rebuild.
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    failures = [row for table in (*REGISTRY_TABLES, "mps") if table in tables
                for row in conn.execute(f"PRAGMA foreign_key_check({table})").fetchall()]
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
