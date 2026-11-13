"""The reviewed list of single units (``scripts/reviewed_units.json``).

One file holds every reviewed decision about a single unit of a sitting, each
entry with a ``kind``:

- ``withhold`` (coverage gate N7, ADR 0005): the parser withholds that unit
  with reason ``reviewed`` instead of emitting it. It names a unit as the
  parser emits it, after ``split_nested_reden``: a ``<rede>`` id, or a split
  part ``<id>:<marker>``.
- ``ansprache``, ``sitzungsleitung``, ``procedural`` (ADR 0004): what a
  presidium, guest, oath or acceptance ``<rede>`` is. They name a whole source
  ``<rede>`` of the Sitzungsverlauf, read before any split.

``redner_id`` is the first Redner-ID of that unit's owner marker; an entry whose
unit the sitting does not hold, or whose owner differs, stops the run
(``validate_dip_protocol``): the list, not the source, needs correcting.

The file is read once per process and checked whole. A malformed file, or an
entry the source does not match, raises ``ReviewedUnitsError``: not a
``ValueError``, so no caller can mistake it for a refused source XML, and the
run stops instead of skipping sittings.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

PATH = Path(__file__).resolve().with_name("reviewed_units.json")
WITHHOLD = "withhold"
#: ADR 0004's kinds of a whole ``<rede>``: an Ansprache is stored as a Beitrag;
#: Sitzungsleitung and procedural ``<rede>``s are not stored.
PRESIDIUM_KINDS = frozenset({"ansprache", "sitzungsleitung", "procedural"})
KINDS = frozenset({WITHHOLD}) | PRESIDIUM_KINDS
ENTRY_KEYS = frozenset({"sitting", "rede_id", "redner_id", "kind", "reason"})
SITTING_RE = re.compile(r"^\d{2}/\d{1,3}$")
REDE_ID_RE = re.compile(r"^[A-Za-z0-9]+(?::\d+)*$")
WHOLE_REDE_ID_RE = re.compile(r"^[A-Za-z0-9]+$")
REDNER_ID_RE = re.compile(r"^\d+$")

_cache: dict[Path, dict[str, list[dict[str, str]]]] = {}
#: Entries ``use`` installed in place of the shipped file (tests), or None.
_in_use: dict[str, list[dict[str, str]]] | None = None


class ReviewedUnitsError(Exception):
    """The reviewed list is malformed, or an entry does not match its sitting.
    Names the entry and ``scripts/reviewed_units.json``; stops the run."""


def _check(data: Any, path: Path) -> dict[str, list[dict[str, str]]]:
    where = f"{path.name}"
    if not isinstance(data, dict) or set(data) != {"entries"} or not isinstance(data["entries"], list):
        raise ReviewedUnitsError(f"{where} must be an object with exactly one key, \"entries\", an array")
    by_sitting: dict[str, list[dict[str, str]]] = {}
    seen: set[tuple[str, str]] = set()
    for position, entry in enumerate(data["entries"], 1):
        label = f"{where} entry {position}"
        if not isinstance(entry, dict) or set(entry) != ENTRY_KEYS:
            raise ReviewedUnitsError(f"{label} must have exactly the keys {', '.join(sorted(ENTRY_KEYS))}")
        for key in ENTRY_KEYS:
            if not isinstance(entry[key], str) or not entry[key].strip():
                raise ReviewedUnitsError(f"{label}: {key} must be a nonempty string")
        if not SITTING_RE.fullmatch(entry["sitting"]):
            raise ReviewedUnitsError(f"{label}: sitting {entry['sitting']!r} is not WP/NR, e.g. 18/2")
        if not REDE_ID_RE.fullmatch(entry["rede_id"]):
            raise ReviewedUnitsError(f"{label}: rede_id {entry['rede_id']!r} is not a <rede> id or a split part <id>:<n>")
        if entry["kind"] not in KINDS:
            raise ReviewedUnitsError(f"{label}: kind {entry['kind']!r} is not one of {', '.join(sorted(KINDS))}")
        if not REDNER_ID_RE.fullmatch(entry["redner_id"]):
            raise ReviewedUnitsError(f"{label}: redner_id {entry['redner_id']!r} is not a Redner-ID, digits only")
        if entry["kind"] in PRESIDIUM_KINDS and not WHOLE_REDE_ID_RE.fullmatch(entry["rede_id"]):
            raise ReviewedUnitsError(f"{label}: a {entry['kind']} entry names a whole source <rede>, not the split part {entry['rede_id']!r}")
        key = (entry["sitting"], entry["rede_id"])
        if key in seen:
            raise ReviewedUnitsError(f"{label}: {entry['sitting']} {entry['rede_id']} is listed twice")
        seen.add(key)
        by_sitting.setdefault(entry["sitting"], []).append(dict(entry))
    return by_sitting


def load(path: Path = PATH) -> dict[str, list[dict[str, str]]]:
    """Every entry, by sitting. Read and checked once per process; callers that
    must stop before any sitting is touched call this at startup."""
    path = Path(path)
    if path not in _cache:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            data = {"entries": []}
        except (OSError, ValueError, RecursionError) as exc:
            raise ReviewedUnitsError(f"{path} cannot be read ({exc})") from exc
        _cache[path] = _check(data, path)
    return _cache[path]


def use(entries: list[dict[str, str]] | None) -> None:
    """Make ``entries`` the list ``for_sitting`` reads by default, checked like
    the file; ``None`` goes back to the shipped file. For tests: synthetic XML
    reuses real sitting numbers the shipped list names."""
    global _in_use
    _in_use = None if entries is None else _check({"entries": entries}, Path("reviewed units in use"))


def for_sitting(sitting: str, path: Path = PATH) -> list[dict[str, str]]:
    """The entries of one sitting (``WP/NR``), in file order."""
    entries = _in_use if _in_use is not None and Path(path) == PATH else load(path)
    return [dict(entry) for entry in entries.get(sitting, [])]


def digest(entries: list[dict[str, str]]) -> str:
    """The SHA-256 of a sitting's entries as canonical JSON, order-independent;
    an empty list has a digest too. The store keeps it per protocol so an edit
    of the list forces a replay of exactly the sittings it touches."""
    canonical = sorted((dict(sorted(entry.items())) for entry in entries), key=lambda e: (e["rede_id"], e["kind"]))
    return hashlib.sha256(json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def sitting_digest(sitting: str, path: Path = PATH) -> str:
    return digest(for_sitting(sitting, path))
