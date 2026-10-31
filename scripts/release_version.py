"""The version scheme of a data release, in one place.

Default scheme: a calendar version ``YYYY.MM.DD``; a second release on the same
day is ``YYYY.MM.DD.2``, a third ``.3``. The release's git tag is ``data-<version>``
and the export is built with the version as its tag (it ends every file name).
The export format is recorded beside the version in the manifest and in the
changelog, and a schema change is called out there; it does not bump the version.

The owner may still choose another scheme (semver where a schema change bumps
the major version was the alternative): change ``next_version``, ``is_version``
and ``version_key`` here, and nothing else.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Iterable

TAG_PREFIX = "data-"
_VERSION_RE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})(?:\.([2-9]|[1-9]\d+))?")


def tag_for(version: str) -> str:
    return f"{TAG_PREFIX}{version}"


def version_of(tag: str) -> str | None:
    """The version a tag names, or None for a tag that is not a release tag."""
    if tag.startswith(TAG_PREFIX) and is_version(tag[len(TAG_PREFIX):]):
        return tag[len(TAG_PREFIX):]
    return None


def is_version(value: object) -> bool:
    if not isinstance(value, str):
        return False
    match = _VERSION_RE.fullmatch(value)
    if not match:
        return False
    try:
        date(int(match[1]), int(match[2]), int(match[3]))
    except ValueError:
        return False
    return True


def version_key(version: str) -> tuple[int, int, int, int]:
    """Orders versions: later is greater. Raises ValueError for a non-version."""
    match = _VERSION_RE.fullmatch(version) if is_version(version) else None
    if not match:
        raise ValueError(f"{version!r} is not a release version")
    return (int(match[1]), int(match[2]), int(match[3]), int(match[4] or 1))


def next_version(today: date, existing: Iterable[str]) -> str:
    """The version for a release made on ``today`` given the versions that exist."""
    base = f"{today:%Y.%m.%d}"
    taken = {version_key(version)[3] for version in existing if is_version(version) and version.startswith(base)}
    if not taken:
        return base
    return f"{base}.{max(taken) + 1}"
