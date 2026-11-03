"""A store for tests that render (A4 R1).

The site renders from a store, so a test that runs a build builds one from its
entries through the production rebuild path (``rebuild_database_from_entries``),
never by seeding tables by hand.
"""
from __future__ import annotations

import contextlib
import copy
import io
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import _support  # noqa: F401
import build_dip_pulse_site as site
import speech_kinds

#: The build date the fixture's rebuild computes facts for.
TODAY = date(2026, 9, 15)


def store_path(output_dir: Path) -> Path:
    """Where a build keeps OUTPUT_DIR's store."""
    return output_dir / "data" / "bundestag-pulse.sqlite"


def build_site_store(
    output_dir: Path,
    entries: list[dict[str, Any]],
    *,
    vorgang_cache: dict[str, Any] | None = None,
) -> Path:
    """Rebuild OUTPUT_DIR's store from ``entries`` (``{"report": ...}`` dicts) as
    a build does and return its path. The rebuild's console lines are swallowed;
    its errors are not.

    ``output_dir`` must sit inside the test's temporary directory, never be it:
    the writer lock and staged copies go to ``.OUTPUT.private`` beside OUTPUT
    (``person_registry.private_dir``), which the temporary directory's cleanup
    removes only when OUTPUT is inside it."""
    if output_dir.resolve().parent == Path(tempfile.gettempdir()).resolve():
        raise ValueError(f"{output_dir} is a temporary directory itself; build the site in a subdirectory of it")
    path = store_path(output_dir)
    with contextlib.redirect_stderr(io.StringIO()):
        site.rebuild_database_from_entries(
            path, entries, preserve_roster=True, today=TODAY, vorgang_cache=vorgang_cache
        )
    return path


def persistable(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copies of the entries that carry a report, completed with what a cached
    report always has and a hand-written test report often leaves out: a
    protocol id (``"test-"`` plus the protocol number) and the current speech
    rule version. Nothing else is filled in, so every figure the store and the
    pages show still comes from the test's own report."""
    complete = []
    for entry in entries:
        if not (entry or {}).get("report"):
            continue
        entry = copy.deepcopy(entry)
        report = entry["report"]
        protocol = report.setdefault("protocol", {})
        protocol.setdefault("id", f"test-{protocol.get('dokumentnummer') or len(complete)}")
        report.setdefault("validation_summary", {}).setdefault("speech_kinds_version", speech_kinds.VERSION)
        complete.append(entry)
    return complete


def archive_rows(entries: list[dict[str, Any]], vorgang_cache: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """The votes archive rows a build shows for ``entries``: a store rebuilt from
    them (``persistable``) with ``vorgang_cache``, read by
    ``votes_archive_rows``. Entries without a report are left out, as the
    rebuild has nothing to persist for them."""
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp) / "site"
        return site.votes_archive_rows(build_site_store(output_dir, persistable(entries), vorgang_cache=vorgang_cache))
