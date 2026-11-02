"""A store for tests that render (A4 R1).

The site renders from a store, so a test that runs a build builds one from its
entries through the production rebuild path (``rebuild_database_from_entries``),
never by seeding tables by hand.
"""
from __future__ import annotations

import contextlib
import io
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import _support  # noqa: F401
import build_dip_pulse_site as site
import facts


def store_path(output_dir: Path) -> Path:
    """Where a build keeps OUTPUT_DIR's store."""
    return output_dir / "data" / "bundestag-pulse.sqlite"


def build_site_store(
    output_dir: Path,
    entries: list[dict[str, Any]],
    *,
    today: date = date(2026, 9, 15),
    vorgang_cache: dict[str, Any] | None = None,
    catalog: facts.SittingCatalog | None = None,
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
            path, entries, preserve_roster=True, today=today, vorgang_cache=vorgang_cache, catalog=catalog
        )
    return path


def store_people(database_path: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """``(abg_mps, mp_lookup)`` read out of the store, as a build reads them."""
    conn = facts.open_readonly(database_path)
    try:
        return site.collect_abgeordnete(conn)
    finally:
        conn.close()
