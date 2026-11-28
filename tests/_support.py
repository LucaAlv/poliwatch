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

import reviewed_vote_links  # noqa: E402

# Likewise for the vote-link review: a drop or flag entry of a real sitting would
# act on (or refuse) a synthetic report with that sitting's number. A test of
# the shipped entries passes them explicitly or installs them with
# reviewed_vote_links.using.
reviewed_vote_links.use([])

import reviewed_end_times  # noqa: E402

# And for the corrected end times (scripts/reviewed_end_times.json): an entry of
# a real sitting refuses a synthetic report whose head prints another end.
reviewed_end_times.use([])


@contextlib.contextmanager
def shipped_reviewed_units():
    reviewed_units.use(None)
    try:
        yield reviewed_units.load()
    finally:
        reviewed_units.use([])


def stamp_reviewed(report: dict) -> dict:
    """Give a hand-built report the reviewed digest a parse under the active list
    would record for its sitting, the vote-link inputs version and the cut rule
    (with its count of printed Reden) every parse records, unless it has them. Without them the report reads as
    stale (build_dip_pulse_site.stale_causes, P3b, "votes" and "cut")."""
    import protocol_cut
    import vote_links

    protocol = report.setdefault("protocol", {})
    number = str(protocol.get("dokumentnummer") or "").strip()
    protocol.setdefault("reviewed_digest", reviewed_units.sitting_digest(number))
    summary = report.setdefault("validation_summary", {})
    summary.setdefault("vote_inputs_version", vote_links.INPUTS_VERSION)
    # Read under the current rule for cut Protokoll files, and whole (E16).
    summary.setdefault("cut_rule_version", protocol_cut.CUT_RULE_VERSION)
    summary.setdefault("protocol_cut", None)
    # The rule's count of printed Reden, which gate rule 3 reads: a hand-built
    # report withholds nothing, so it is the stored Reden.
    summary.setdefault("printed_reden", summary.get("xml_speech_count", 0))
    return report


def shipped_digest(number: str) -> str:
    """The reviewed digest of ``number`` under scripts/reviewed_units.json, what a
    CLI run in a subprocess compares a cached report against."""
    with shipped_reviewed_units():
        return reviewed_units.sitting_digest(number)


#: The reviewed-list entries the excerpt ``fixtures/withholding/18-10-top3.xml``
#: needs. Neu's Rede is printed as <name> outside any <rede> (ADR 0004 amendment
#: 2026-11-22); its ordinal counts the excerpt's <name> elements, not the whole
#: sitting's, so the shipped entry (N39) does not apply to the excerpt. Annen's
#: and Beyer's Reden are printed as speaker markers outside any <rede> (second
#: amendment of 2026-11-22); no
#: earlier TOP of 18/10 has a speaker marker outside a <rede>, so the shipped
#: M<ordinal> entries apply to the excerpt unchanged.
NAME_ENTRIES_18_10_TOP3 = [{
    "sitting": "18/10", "rede_id": "N4", "redner_id": "11004361", "kind": "name_rede",
    "reason": "a whole Rede the chair gave the floor to, printed under <name> (name-tag-speakers.tsv entry 123)",
    "name": "Dr. Alexander S. Neu (DIE LINKE)",
}] + [entry for entry in reviewed_units.load()["18/10"] if entry["kind"] in reviewed_units.LOOSE_KINDS]
