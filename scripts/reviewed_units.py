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
- ``name_*`` (ADR 0004 amendment 2026-11-22): a speaker the source prints
  under a ``<name>`` element, the chair's element, although they are not the
  chair (``docs/plans/name-tag-speakers.md``). The entry adds ``name``, the
  printed tag without its colon. ``rede_id`` names the source ``<rede>`` that
  holds the tag, read before any split, or ``N<ordinal>`` for a tag outside any
  ``<rede>``: its 1-based position among the Sitzungsverlauf's ``<name>``
  elements (``validate_dip_protocol.name_tags``). ``redner_id`` may be
  ``dip:<n>``, a DIP Personenkennung, for a speaker the Bundestag gave no
  Redner-ID, and is empty for ``name_procedural``, ``name_ansprache`` and
  ``name_remark``.
- ``loose_*`` (ADR 0004, amendment "speaker markers outside any ``<rede>``",
  2026-11-22): a speaker marker that stands directly in a Tagesordnungspunkt
  that is not a Fragestunde, outside any ``<rede>``
  (``docs/plans/loose-speaker-markers.md``). ``rede_id`` is
  ``M<ordinal>``: the marker's 1-based position among all speaker markers
  standing directly in the sitting's TOPs, Fragestunde TOPs included, in the
  source XML (``validate_dip_protocol.loose_marker_ordinals``). ``redner_id``
  is the marker's printed Redner-ID. The entry adds ``attach``: ``wrap`` (into
  the Rede a ``loose_rede`` marker of the same run opens), ``prev`` or
  ``next`` (into the ``<rede>`` just before or after the run), or ``none``.
- ``rede``, ``kurzintervention``, ``erwiderung``, ``erklaerung``,
  ``zu_protokoll`` (ADR 0002, amendment 2026-11-23): what a whole unit is,
  where the wording rules of ``speech_kinds.classify_reden`` would read it as
  something else (``docs/plans/beitraege-as-reden.md``). Like ``withhold`` it
  names a unit as the parser emits it: a ``<rede>`` id, a split part
  ``<id>:<marker>``, or the ``N<ordinal>`` or ``M<ordinal>`` a ``name_rede`` or
  ``loose_rede`` entry makes a Rede of. ``rede`` says that a unit DIP types as
  one of the others is a Rede after all.

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
#: A speaker printed as ``<name>`` (ADR 0004 amendment 2026-11-22). A ``rede``
#: entry becomes a Rede of that speaker; a Beitrag kind becomes a speaker marker
#: the existing rules classify, and the parse must give it that kind; own words
#: join the host's owner; ``procedural`` is an oath answer (a diagnostic, never
#: stored); ``ansprache`` an invited guest's address with no Redner-ID; a
#: ``remark`` is stored nowhere.
NAME_KINDS = frozenset({
    "name_rede", "name_zwischenfrage", "name_befragung_frage", "name_befragung_antwort",
    "name_fragestunde_frage", "name_own_words", "name_procedural", "name_ansprache", "name_remark",
})
#: A speaker marker outside any ``<rede>`` in a TOP that is not a Fragestunde
#: (ADR 0004, amendment of 2026-11-22 on markers outside any ``<rede>``). A
#: ``rede`` opens a Rede of its own; own words join a Rede of the same speaker;
#: a Beitrag kind joins a Rede as a speaker marker the existing rules must give
#: that kind; ``procedural`` is a diagnostic; ``sitzungsleitung`` and ``remark``
#: are stored nowhere.
LOOSE_KINDS = frozenset({
    "loose_rede", "loose_own_words", "loose_zwischenfrage", "loose_befragung_frage", "loose_befragung_antwort",
    "loose_procedural", "loose_sitzungsleitung", "loose_remark",
})
#: Where each loose kind's turn may go.
LOOSE_ATTACH = {
    "loose_rede": frozenset({"wrap"}),
    "loose_own_words": frozenset({"wrap", "prev", "next"}),
    "loose_zwischenfrage": frozenset({"wrap", "prev", "next"}),
    "loose_befragung_frage": frozenset({"wrap", "prev", "next"}),
    "loose_befragung_antwort": frozenset({"wrap", "prev", "next"}),
    "loose_procedural": frozenset({"none"}),
    "loose_sitzungsleitung": frozenset({"none"}),
    "loose_remark": frozenset({"none"}),
}
#: Name kinds that bind no speaker: their ``redner_id`` is empty.
NAME_KINDS_WITHOUT_SPEAKER = frozenset({"name_procedural", "name_ansprache", "name_remark"})
#: What a whole unit as emitted is (ADR 0002, amendment 2026-11-23); every one
#: but ``rede`` is a ``speech_kinds.CONTRIBUTION_KINDS`` value.
UNIT_KINDS = frozenset({"rede", "kurzintervention", "erwiderung", "erklaerung", "zu_protokoll"})
KINDS = frozenset({WITHHOLD}) | PRESIDIUM_KINDS | NAME_KINDS | LOOSE_KINDS | UNIT_KINDS
ENTRY_KEYS = frozenset({"sitting", "rede_id", "redner_id", "kind", "reason"})
NAME_ENTRY_KEYS = ENTRY_KEYS | {"name"}
LOOSE_ENTRY_KEYS = ENTRY_KEYS | {"attach"}
SITTING_RE = re.compile(r"^\d{2}/\d{1,3}$")
REDE_ID_RE = re.compile(r"^[A-Za-z0-9]+(?::\d+)*$")
WHOLE_REDE_ID_RE = re.compile(r"^[A-Za-z0-9]+$")
REDNER_ID_RE = re.compile(r"^\d+$")
NAME_REDNER_ID_RE = re.compile(r"^(?:\d+|dip:[1-9]\d*)$")
NAME_REDE_ID_RE = re.compile(r"^(?:[A-Za-z0-9]+|N[1-9]\d*)$")
LOOSE_REDE_ID_RE = re.compile(r"^M[1-9]\d*$")

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
    seen: set[tuple[str, ...]] = set()
    for position, entry in enumerate(data["entries"], 1):
        label = f"{where} entry {position}"
        name_kind = isinstance(entry, dict) and entry.get("kind") in NAME_KINDS
        loose_kind = isinstance(entry, dict) and entry.get("kind") in LOOSE_KINDS
        keys = NAME_ENTRY_KEYS if name_kind else LOOSE_ENTRY_KEYS if loose_kind else ENTRY_KEYS
        if not isinstance(entry, dict) or set(entry) != keys:
            raise ReviewedUnitsError(f"{label} must have exactly the keys {', '.join(sorted(keys))}")
        for key in keys:
            if not isinstance(entry[key], str):
                raise ReviewedUnitsError(f"{label}: {key} must be a string")
            if not entry[key].strip() and not (key == "redner_id" and entry["kind"] in NAME_KINDS_WITHOUT_SPEAKER):
                raise ReviewedUnitsError(f"{label}: {key} must be a nonempty string")
        if not SITTING_RE.fullmatch(entry["sitting"]):
            raise ReviewedUnitsError(f"{label}: sitting {entry['sitting']!r} is not WP/NR, e.g. 18/2")
        if loose_kind:
            if not LOOSE_REDE_ID_RE.fullmatch(entry["rede_id"]):
                raise ReviewedUnitsError(f"{label}: a {entry['kind']} entry names a marker as M<ordinal>, not {entry['rede_id']!r}")
            if entry["attach"] not in LOOSE_ATTACH[entry["kind"]]:
                raise ReviewedUnitsError(f"{label}: {entry['attach']!r} is no place for a {entry['kind']} entry; "
                                         f"its attach must be one of {', '.join(sorted(LOOSE_ATTACH[entry['kind']]))}")
        elif not REDE_ID_RE.fullmatch(entry["rede_id"]) and not (name_kind and NAME_REDE_ID_RE.fullmatch(entry["rede_id"])):
            raise ReviewedUnitsError(f"{label}: rede_id {entry['rede_id']!r} is not a <rede> id or a split part <id>:<n>")
        if entry["kind"] not in KINDS:
            raise ReviewedUnitsError(f"{label}: kind {entry['kind']!r} is not one of {', '.join(sorted(KINDS))}")
        if entry["kind"] in NAME_KINDS_WITHOUT_SPEAKER:
            if entry["redner_id"]:
                raise ReviewedUnitsError(f"{label}: a {entry['kind']} entry binds no speaker; its redner_id must be empty")
        elif not (NAME_REDNER_ID_RE if name_kind else REDNER_ID_RE).fullmatch(entry["redner_id"]):
            raise ReviewedUnitsError(f"{label}: redner_id {entry['redner_id']!r} is not a Redner-ID, digits only"
                                     + (", or dip:<n>" if name_kind else ""))
        if entry["kind"] in PRESIDIUM_KINDS and not WHOLE_REDE_ID_RE.fullmatch(entry["rede_id"]):
            raise ReviewedUnitsError(f"{label}: a {entry['kind']} entry names a whole source <rede>, not the split part {entry['rede_id']!r}")
        if name_kind and not NAME_REDE_ID_RE.fullmatch(entry["rede_id"]):
            raise ReviewedUnitsError(f"{label}: a {entry['kind']} entry names a whole source <rede> or N<ordinal>, not {entry['rede_id']!r}")
        if name_kind and entry["name"] != entry["name"].strip(" :"):
            raise ReviewedUnitsError(f"{label}: name {entry['name']!r} is the printed tag without its colon or outer spaces")
        # One source <rede> can hold several speakers printed as <name>, and
        # carry a reviewed kind or a withhold entry of its own besides. A loose
        # marker's entry says where it goes; what the Rede it opens is, or that
        # it is withheld, is a second entry under the same M<ordinal>.
        key = ((entry["sitting"], entry["rede_id"], entry["name"]) if name_kind
               else (entry["sitting"], entry["rede_id"], "loose marker") if loose_kind
               else (entry["sitting"], entry["rede_id"]))
        if key in seen:
            raise ReviewedUnitsError(f"{label}: {' '.join(key)} is listed twice")
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
        except FileNotFoundError as exc:
            # The file is checked in. Read as empty, a deleted or renamed list
            # would release every reviewed Rede on the next repersist (P3c).
            raise ReviewedUnitsError(
                f"{path} is missing; it is checked in, restore it (git checkout -- scripts/reviewed_units.json)"
            ) from exc
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
    canonical = sorted((dict(sorted(entry.items())) for entry in entries), key=lambda e: (e["rede_id"], e["kind"], e.get("name", "")))
    return hashlib.sha256(json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def sitting_digest(sitting: str, path: Path = PATH) -> str:
    return digest(for_sitting(sitting, path))
