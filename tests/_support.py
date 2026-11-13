from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


import contextlib  # noqa: E402

import speech_kinds  # noqa: E402

# Synthetic test XML reuses real sitting numbers (18/1, 20/1, 21/1, ...), which
# scripts/reviewed_units.json lists with real <rede> ids: an entry whose <rede> a
# sitting lacks refuses it. So tests parse with an empty reviewed list, and a
# test of a real listed sitting installs the shipped one (shipped_reviewed_units).
speech_kinds.use_reviewed_units([])


@contextlib.contextmanager
def shipped_reviewed_units():
    speech_kinds.load_reviewed_units()
    try:
        yield speech_kinds.reviewed_units()
    finally:
        speech_kinds.use_reviewed_units([])
