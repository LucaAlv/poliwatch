"""Writes the votes archive page tests/votes_archive_browser_check.js runs against.

Usage: python3 tests/votes_archive_browser_fixture.py <out-dir>   (writes <out-dir>/index.html)

Not a ``test_*.py`` module, so unittest discovery skips it. The rows come from
``build.collect_votes_archive``, so ``data-fraktion-positions`` and
``data-politikfelder`` are the real ones, not hand-made attributes. Four votes in
two months (see ``VOTES``); the browser check addresses them by their row order.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import sys
from pathlib import Path
from typing import Any

import _support  # noqa: F401
import build_dip_pulse_site as build
import politikfelder
from _support import FIXTURES

# Counts per Fraktion: SPD is "Fraktion A", CDU/CSU "Fraktion B" of the check.
YES_MAJORITY = {"yes": 8, "no": 0, "abstain": 1, "absent": 0}
NO_MAJORITY = {"yes": 0, "no": 6, "abstain": 1, "absent": 0}
TIE = {"yes": 4, "no": 4, "abstain": 0, "absent": 0}

#: (vote id, date, title, SPD counts, CDU/CSU counts, inverted, Sachgebiete of its Vorgang).
#: 1: A yes, B no. 2: A no, B yes. 3: an inverted vote A supports with a Nein majority
#: ("für den Antrag"), two Politikfelder. 4: A tie, B yes, no Politikfeld.
VOTES: list[tuple[str, str, str, dict[str, int], dict[str, int], bool, tuple[str, ...]]] = [
    ("901", "2024-05-15", "Abstimmung eins", YES_MAJORITY, NO_MAJORITY, False, ("Verkehr",)),
    ("902", "2024-05-14", "Abstimmung zwei", NO_MAJORITY, YES_MAJORITY, False, ("Gesundheit",)),
    ("903", "2024-04-18", "Abstimmung drei", NO_MAJORITY, YES_MAJORITY, True, ("Verkehr", "Gesundheit")),
    ("904", "2024-04-17", "Abstimmung vier", TIE, YES_MAJORITY, False, ()),
]


def fixture_report() -> dict[str, Any]:
    return json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))


def build_rows() -> list[dict[str, Any]]:
    report = fixture_report()
    template = report["agenda_items"][0]
    items = []
    vorgaenge: dict[str, Any] = {}
    numbers: dict[str, list[str]] = {}
    for number, (vote_id, date_iso, title, spd, cdu, inverted, sachgebiete) in enumerate(VOTES, start=1):
        top = copy.deepcopy(template)
        top["index"] = number
        top["top_id"] = f"TOP {number}"
        top["heading"] = f"TOP {number} Beratung Testgesetz {number}"
        for speech_number, speech in enumerate(top["xml_speakers"]):
            speech["rede_id"] = f"r{number}-{speech_number}"
        vote = top["votes"][0]
        vote.update(
            id=vote_id,
            date=date_iso,
            title=title,
            document_numbers=[f"20/{number}00"],
            fractions=[
                {"name": "SPD", "counts": dict(spd), "total": sum(spd.values()), "leading_vote": "yes"},
                {"name": "CDU/CSU", "counts": dict(cdu), "total": sum(cdu.values()), "leading_vote": "no"},
            ],
        )
        if inverted:
            vote["inverted"] = True
        top["api"]["positions"] = []
        top["api"]["linked_drucksachen"] = []
        top["xml_drucksachen"] = []
        # DIP knows the number and names no Vorgang: an untagged vote, not an unfetched one.
        numbers[f"20/{number}00"] = []
        if sachgebiete:
            vorgang_id = f"v{number}"
            top["api"]["positions"] = [
                {
                    "id": f"pos-{vorgang_id}",
                    "vorgang_id": vorgang_id,
                    "vorgangstyp": "Gesetzgebung",
                    "vorgangsposition": "Beschlussempfehlung",
                    "titel": f"Titel {vorgang_id}",
                    "mitberaten": [],
                }
            ]
            vorgaenge[vorgang_id] = {
                "sachgebiet": list(sachgebiete),
                "vorgangstyp": "Gesetzgebung",
                "titel": "Titel",
                "abstract": "Worum es geht.",
            }
        items.append(top)
    report["agenda_items"] = items
    cache = {"version": 1, "vorgaenge": vorgaenge, "dokumentnummern": numbers}
    entry = {"report": report, "page_path": Path("plenarprotokoll-20-999.html"), "report_path": Path("x.json"), "slug": "x"}
    with contextlib.redirect_stderr(io.StringIO()):
        return build.collect_votes_archive([entry], cache)


def write_votes_archive_fixture(output: Path) -> None:
    rows = build_rows()
    # What the check below expects of the rows; fail here, not as a confusing browser error.
    assert [row["vote"]["id"] for row in rows] == ["901", "902", "903", "904"], [row["vote"]["id"] for row in rows]
    assert [row["politikfelder"] for row in rows] == [
        ["Verkehr"],
        ["Gesundheit"],
        ["Verkehr", "Gesundheit"],
        [politikfelder.UNTAGGED],
    ], [row["politikfelder"] for row in rows]
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(build.render_votes_archive_index(rows), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <out-dir>")
    write_votes_archive_fixture(Path(sys.argv[1]))
