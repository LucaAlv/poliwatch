"""How scripts open SQLite files.

``sqlite3.connect`` is called only here, in
``persist_dip_pulse_store.connect``, the build store's writer, and in the
read-only ``compare_cpp_bt.open_export``, which may import only the standard
library (tests/test_code_rules.py SQLITE_OPENERS; the rule also refuses
``sqlite3.Connection`` and ATTACH). Writing to an existing database file
therefore goes through ``persist_dip_pulse_store.connect``: it refuses a
distribution copy and turns on foreign keys, and a write path that opened the
store any other way would skip both (review-checklist class 1, PR #91)."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def open_readonly(path: Path) -> sqlite3.Connection:
    """A read-only connection to an existing SQLite file: the build store, a
    staged or published copy, or an export. It cannot write, so it needs none
    of the build store's refusals. Raises ``sqlite3.OperationalError`` when the
    file does not exist."""
    return sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)


def create_database(path: Path) -> sqlite3.Connection:
    """A writable connection to a database file this run creates. ``path`` must
    be absent or empty: an existing database is written only through
    ``persist_dip_pulse_store.connect``."""
    path = Path(path)
    if path.exists() and path.stat().st_size > 0:
        raise FileExistsError(
            f"{path} already holds data; create_database only opens a new file. "
            "Write to an existing store with persist_dip_pulse_store.connect, "
            "or read it with sqlite_open.open_readonly."
        )
    return sqlite3.connect(path)
