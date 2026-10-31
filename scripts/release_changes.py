"""The public changelog of a data release: ``changes.json`` and ``CHANGES.md``.

A release's changes are assembled from two sources. What the two manifests say
is derived here (the previous version, the export format, store schema, key
version and schema hash that moved, the change of the protocol, vote and row
counts), so it cannot be forgotten or mistyped. What only a person knows is
authored in a small JSON file (summary, which schema changes were made and why,
which coverage was added, every correction with old value, new value and reason)
and is type-checked. A schema change the manifests detect but the authored file
does not describe refuses the release. The first release needs no authored file.
Format: docs/data-changelog.md.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import release_version

CHANGES_FORMAT = 1
INITIAL_SUMMARY = "Erste Veröffentlichung."
SCHEMA_CHANGE_KINDS = ("added", "removed", "renamed", "retyped", "meaning", "table-added", "table-removed", "other")
# Manifest fields whose change is a schema change a reader must be told about.
SCHEMA_FIELDS = ("export_format", "store_schema", "key_version", "schema_hash")
_AUTHORED_KEYS = {"summary", "schema_changes", "coverage_added", "corrections", "notes"}
_CORRECTION_KEYS = {"table", "key", "column", "old", "new", "reason"}
_SCALAR = (str, int, float, bool, type(None))


class ChangesError(RuntimeError):
    """The changelog of a release cannot be assembled."""


def load_authored(path: Path) -> dict[str, Any]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ChangesError(f"cannot read the changes file {path}: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ChangesError(f"the changes file {path} is not valid JSON: {exc}") from exc


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ChangesError(f"changes file: {where} must be non-empty text")
    return value.strip()


def _list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise ChangesError(f"changes file: {where} must be a list")
    return value


def _object(value: Any, where: str, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ChangesError(f"changes file: {where} must be an object")
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ChangesError(f"changes file: {where} has unknown fields {', '.join(unknown)}")
    return value


def _check_authored(authored: Any) -> dict[str, Any]:
    authored = _object(authored, "the file", _AUTHORED_KEYS)
    checked: dict[str, Any] = {"summary": _text(authored.get("summary"), "summary")}
    schema_changes = []
    for index, entry in enumerate(_list(authored.get("schema_changes", []), "schema_changes")):
        where = f"schema_changes[{index}]"
        entry = _object(entry, where, {"table", "column", "change", "description"})
        if entry.get("change") not in SCHEMA_CHANGE_KINDS:
            raise ChangesError(f"changes file: {where}.change must be one of {', '.join(SCHEMA_CHANGE_KINDS)}")
        column = entry.get("column")
        if column is not None:
            column = _text(column, f"{where}.column")
        schema_changes.append(
            {"table": _text(entry.get("table"), f"{where}.table"), "column": column, "change": entry["change"], "description": _text(entry.get("description"), f"{where}.description")}
        )
    checked["schema_changes"] = schema_changes
    coverage_added = []
    for index, entry in enumerate(_list(authored.get("coverage_added", []), "coverage_added")):
        entry = _object(entry, f"coverage_added[{index}]", {"description"})
        coverage_added.append({"description": _text(entry.get("description"), f"coverage_added[{index}].description")})
    checked["coverage_added"] = coverage_added
    corrections = []
    for index, entry in enumerate(_list(authored.get("corrections", []), "corrections")):
        where = f"corrections[{index}]"
        entry = _object(entry, where, _CORRECTION_KEYS)
        for field in ("old", "new"):
            if field not in entry:
                raise ChangesError(f"changes file: {where} needs {field} (use null for a missing value)")
            if not isinstance(entry[field], _SCALAR):
                raise ChangesError(f"changes file: {where}.{field} must be a text, number, true/false or null")
        if entry["old"] == entry["new"] and type(entry["old"]) is type(entry["new"]):
            raise ChangesError(f"changes file: {where} changes nothing (old equals new)")
        # The row is named by table, key and column, in that order.
        correction = {name: _text(entry.get(name), f"{where}.{name}") for name in ("table", "key", "column")}
        correction.update(old=entry["old"], new=entry["new"], reason=_text(entry.get("reason"), f"{where}.reason"))
        corrections.append(correction)
    checked["corrections"] = corrections
    checked["notes"] = [_text(note, f"notes[{index}]") for index, note in enumerate(_list(authored.get("notes", []), "notes"))]
    return checked


def _delta(previous: dict[str, Any] | None, current: dict[str, Any], *path: str) -> dict[str, Any]:
    def dig(source: Any) -> Any:
        for key in path:
            source = source.get(key) if isinstance(source, dict) else None
        return source

    return {"old": dig(previous) if previous is not None else None, "new": dig(current)}


def assemble(
    *,
    version: str,
    released: date,
    manifest: dict[str, Any],
    previous_manifest: dict[str, Any] | None,
    authored: Any,
) -> dict[str, Any]:
    """The changes of release ``version`` (machine-readable); raises ChangesError."""
    if not release_version.is_version(version):
        raise ChangesError(f"{version!r} is not a release version")
    initial = previous_manifest is None
    previous_version = None
    if not initial:
        previous_version = previous_manifest.get("tag")
        if not release_version.is_version(previous_version):
            raise ChangesError(f"the previous manifest's tag {previous_version!r} is not a release version")
        if release_version.version_key(previous_version) >= release_version.version_key(version):
            raise ChangesError(f"the previous version {previous_version} is not earlier than {version}")
    if authored is None:
        if not initial:
            raise ChangesError(f"release {version} follows {previous_version} and needs a changes file (--changes)")
        checked: dict[str, Any] = {"summary": INITIAL_SUMMARY, "schema_changes": [], "coverage_added": [], "corrections": [], "notes": []}
    else:
        checked = _check_authored(authored)
        if initial and (checked["corrections"] or checked["schema_changes"]):
            raise ChangesError("an initial release has nothing to correct or migrate: drop corrections and schema_changes from the changes file")
    detected = {}
    if not initial:
        for field in SCHEMA_FIELDS:
            if previous_manifest.get(field) != manifest.get(field):
                detected[field] = {"old": previous_manifest.get(field), "new": manifest.get(field)}
    if detected and not checked["schema_changes"]:
        raise ChangesError(
            f"the schema changed since {previous_version} ({', '.join(detected)}) but the changes file lists no schema_changes: describe them"
        )
    coverage = {
        "protocols": _delta(previous_manifest, manifest, "protocols", "count"),
        "first_protocol": _delta(previous_manifest, manifest, "protocols", "first"),
        "last_protocol": _delta(previous_manifest, manifest, "protocols", "last"),
        "last_protocol_date": _delta(previous_manifest, manifest, "protocols", "to"),
        "votes": _delta(previous_manifest, manifest, "votes", "count"),
        "vote_members": _delta(previous_manifest, manifest, "votes", "members"),
        "total_rows": _delta(previous_manifest, manifest, "total_rows"),
    }
    return {
        "changes_format": CHANGES_FORMAT,
        "version": version,
        "tag": release_version.tag_for(version),
        "released": released.isoformat(),
        "previous_version": previous_version,
        "initial_release": initial,
        "export_format": manifest.get("export_format"),
        "store_schema": manifest.get("store_schema"),
        "key_version": manifest.get("key_version"),
        "schema_hash": manifest.get("schema_hash"),
        "summary": checked["summary"],
        "schema_changed": bool(detected),
        "detected": detected,
        "schema_changes": checked["schema_changes"],
        "coverage": coverage,
        "coverage_added": checked["coverage_added"],
        "corrections": checked["corrections"],
        "notes": checked["notes"],
    }


def _cell(value: Any) -> str:
    text = "leer" if value is None else str(value)
    return " ".join(text.replace("|", "\\|").split())


def _change(delta: dict[str, Any]) -> str:
    old, new = delta["old"], delta["new"]
    return f"{_cell(new)}" if old is None else (f"{_cell(old)} → {_cell(new)}" if old != new else f"{_cell(new)} (unverändert)")


def render_markdown(changes: dict[str, Any]) -> str:
    lines = [
        f"# Änderungen in Version {changes['version']}",
        "",
        f"Veröffentlicht am {changes['released']} · Tag `{changes['tag']}` · Exportformat {changes['export_format']} · "
        f"Store-Schema {changes['store_schema']} · Schlüsselversion {changes['key_version']}",
        "",
    ]
    if changes["previous_version"]:
        lines += [f"Vorherige Version: {changes['previous_version']}", ""]
    lines += [changes["summary"], ""]
    lines += ["## Schemaänderungen", ""]
    if changes["schema_changes"]:
        for entry in changes["schema_changes"]:
            target = f"`{entry['table']}.{entry['column']}`" if entry["column"] else f"`{entry['table']}`"
            lines.append(f"- {target} ({entry['change']}): {_cell(entry['description'])}")
        lines += ["", "Geändert laut Manifest: " + ", ".join(f"{name} ({_change(delta)})" for name, delta in changes["detected"].items()) + "."]
    else:
        lines.append("Keine Schemaänderungen.")
    lines += ["", "## Abdeckung", ""]
    coverage = changes["coverage"]
    for label, key in (
        ("Plenarprotokolle", "protocols"),
        ("Letztes Protokoll", "last_protocol"),
        ("Letztes Sitzungsdatum", "last_protocol_date"),
        ("Namentliche Abstimmungen", "votes"),
        ("Einzelstimmen", "vote_members"),
        ("Zeilen insgesamt", "total_rows"),
    ):
        lines.append(f"- {label}: {_change(coverage[key])}")
    if changes["coverage_added"]:
        lines += ["", "Neu erfasst:", ""] + [f"- {_cell(entry['description'])}" for entry in changes["coverage_added"]]
    lines += ["", "## Korrekturen", ""]
    if changes["corrections"]:
        lines += ["| Tabelle | Schlüssel | Spalte | Alter Wert | Neuer Wert | Grund |", "|---|---|---|---|---|---|"]
        for entry in changes["corrections"]:
            lines.append("| " + " | ".join(_cell(entry[name]) for name in ("table", "key", "column", "old", "new", "reason")) + " |")
    else:
        lines.append("Keine Korrekturen veröffentlichter Werte.")
    if changes["notes"]:
        lines += ["", "## Hinweise", ""] + [f"- {_cell(note)}" for note in changes["notes"]]
    return "\n".join(lines) + "\n"
