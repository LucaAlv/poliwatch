from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


import contextlib  # noqa: E402

import reviewed_units  # noqa: E402

# Synthetic test XML reuses real sitting numbers (18/1, 20/1, 21/1, ...), which
# scripts/reviewed_units.json lists with real <rede> ids: an entry whose <rede> a
# sitting lacks refuses it. So tests parse with an empty reviewed list, and a
# test of a real listed sitting installs the shipped one (shipped_reviewed_units).
reviewed_units.use([])


@contextlib.contextmanager
def shipped_reviewed_units():
    reviewed_units.use(None)
    try:
        yield reviewed_units.load()
    finally:
        reviewed_units.use([])


def stamp_reviewed(report: dict) -> dict:
    """Give a hand-built report the reviewed digest a parse under the active list
    would record for its sitting, and the vote-link inputs version every parse
    records, unless it has them. Without them the report reads as stale
    (build_dip_pulse_site.stale_causes, P3b and "votes")."""
    import vote_links

    protocol = report.setdefault("protocol", {})
    number = str(protocol.get("dokumentnummer") or "").strip()
    protocol.setdefault("reviewed_digest", reviewed_units.sitting_digest(number))
    report.setdefault("validation_summary", {}).setdefault("vote_inputs_version", vote_links.INPUTS_VERSION)
    return report


def shipped_digest(number: str) -> str:
    """The reviewed digest of ``number`` under scripts/reviewed_units.json, what a
    CLI run in a subprocess compares a cached report against."""
    with shipped_reviewed_units():
        return reviewed_units.sitting_digest(number)
