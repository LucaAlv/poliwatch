"""The vote-link review sheet (scripts/vote_link_review.py): strata, keys,
evidence columns, and refusals."""

from __future__ import annotations

import contextlib
import copy
import csv
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

import _support  # noqa: F401
import _site_store_fixture
import vote_link_review as review
import vote_links
from _support import FIXTURES

XML = """<?xml version="1.0" encoding="UTF-8"?>
<dbtplenarprotokoll><sitzungsverlauf><p>Ich gebe das Ergebnis der namentlichen Abstimmung über die
Beschlussempfehlung auf Drucksache 20/123 bekannt: abgegebene Stimmen 17. Mit Ja haben gestimmt 10,
mit Nein haben gestimmt 5, Enthaltungen 2.</p></sitzungsverlauf></dbtplenarprotokoll>"""


def sitting() -> dict[str, Any]:
    """The fixture sitting with one vote per stratum, placed by the rule:
    12345 (printed 20/123) and v2 (DIP 20/456) share TOP 1 (S2); v4 links TOP 3
    and TOP 4 (S1); v3 is a title link (S3); v5 and v6 are plain (S4)."""
    report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
    base = report["agenda_items"][0]["votes"][0]
    template = report["agenda_items"][1]

    def top(index: int, heading: str, printed: list[str] = (), linked: list[str] = ()) -> dict:
        new = copy.deepcopy(template)
        new.update(index=index, top_id=f"T{index}", heading=heading, votes=[], xml_speakers=[],
                   xml_drucksachen=[{"dokumentnummer": n} for n in printed],
                   api={"linked_drucksachen": [{"dokumentnummer": n, "herausgeber": "BT", "drucksachetyp": "Antrag",
                                                "vorgang_id": f"vg-{n}"} for n in linked]})
        return new

    report["agenda_items"] += [top(3, "TOP 3 Erste Lesung", printed=["20/777"]), top(4, "TOP 4 Zweite Lesung", linked=["20/888"]),
                               top(5, "TOP 5 Mandat", printed=["20/555"]), top(6, "TOP 6 Haushalt", linked=["20/666"])]

    def copy_of(vote_id: str, numbers: list[str], title: str) -> dict:
        return {**copy.deepcopy(base), "id": vote_id, "document_numbers": numbers, "title": title,
                "total": {"yes": 1, "no": 0, "abstain": 0, "absent": 0}}

    votes = [base, copy_of("v2", ["20/456", "20/999"], "Testgesetz"), copy_of("v3", [], "Fragestunde"),
             copy_of("v4", ["20/777", "20/888"], "Lesungen"), copy_of("v5", ["20/555"], "Mandat"), copy_of("v6", ["20/666"], "Haushalt")]
    report["agenda_items"][0]["votes"] = []
    report["api_records"] = {"roll_call_vote_candidates": votes, "matched_roll_call_votes": votes}
    return vote_links.attribute_votes(report)


class SheetTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.site = Path(tmp.name) / "site"
        report = _site_store_fixture.persistable([{"report": sitting()}])[0]["report"]
        _site_store_fixture.build_site_store(self.site, [{"report": report}])
        (self.site / "data" / "plenarprotokoll-20-999.json").write_text(json.dumps(report), encoding="utf-8")
        (self.site / "data" / "xml").mkdir(parents=True, exist_ok=True)
        (self.site / "data" / "xml" / "plenarprotokoll-20-999.xml").write_text(XML, encoding="utf-8")

    def run_sheet(self, *extra: str) -> tuple[int, str, str]:
        out = self.site.parent / "review.tsv"
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = review.main(["--output-dir", str(self.site), "--out", str(out), "--sample-vorgang", "1",
                                "--sample-xml", "1", *extra])
        return code, out.read_text(encoding="utf-8") if out.exists() else "", stderr.getvalue()

    def rows(self, text: str) -> list[dict[str, str]]:
        return list(csv.DictReader((line for line in text.splitlines() if not line.startswith("#")), delimiter="\t"))

    def test_every_stratum_and_its_evidence(self) -> None:
        code, text, _ = self.run_sheet()
        self.assertEqual(code, 0)
        rows = {(row["vote_id"], row["top_id"]): row for row in self.rows(text)}
        self.assertEqual({key: row["stratum"] for key, row in rows.items()}, {
            ("12345", "T1"): "S2", ("v2", "T1"): "S2", ("v3", "T2"): "S3",
            ("v4", "T3"): "S1", ("v4", "T4"): "S1", ("v5", "T5"): "S4", ("v6", "T6"): "S4",
        })
        self.assertEqual(rows[("12345", "T1")]["basis"], "drucksache_xml")
        self.assertEqual(rows[("12345", "T1")]["shared"], "20/123:xml:-")
        self.assertEqual((rows[("12345", "T1")]["tally"], rows[("12345", "T1")]["announced"]), ("unique", "20/123"))
        self.assertEqual(rows[("v2", "T1")]["shared"], "20/456:Beschlussempfehlung:vorgang-1")
        self.assertEqual(rows[("v4", "T3")]["other_tops"], "T4#1")
        self.assertEqual(rows[("v3", "T2")]["shared"], "-")
        self.assertEqual({row["top_occurrence"] for row in rows.values()}, {"1"})
        self.assertEqual({row["verdict"] + row["pattern"] + row["action"] + row["evidence"] + row["reviewer"]
                          for row in rows.values()}, {""})
        self.assertIn("# units: 5", text)
        self.assertIn("# seed: 20261114", text)

    def test_the_same_seed_writes_the_same_sheet(self) -> None:
        self.assertEqual(self.run_sheet()[1], self.run_sheet()[1])

    def test_bad_inputs_are_refused_with_a_message(self) -> None:
        code, _, err = self.run_sheet("--sample-xml", "5")
        self.assertEqual((code, "exceeds the 1 plain drucksache_xml links" in err), (2, True))
        code, _, err = self.run_sheet("--sample-xml", "-1")
        self.assertEqual((code, "cannot be negative" in err), (2, True))
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = review.main(["--output-dir", str(self.site.parent / "nowhere"), "--out", str(self.site.parent / "x.tsv")])
        self.assertEqual((code, "no store at" in err.getvalue()), (2, True))
        (self.site / "data" / "xml" / "plenarprotokoll-20-999.xml").write_text("<dbtplenarprotokoll>", encoding="utf-8")
        code, _, err = self.run_sheet()
        self.assertEqual((code, "not well-formed XML" in err), (2, True))


class TallyTests(unittest.TestCase):
    def test_unique_several_and_none(self) -> None:
        text = "über Drucksache 21/5 ... Mit Ja haben gestimmt 380, mit Nein haben gestimmt 270, Enthaltungen 2."
        self.assertEqual(review.find_tally(text, 380, 270), ("unique", ["21/5"]))
        self.assertEqual(review.find_tally(text + " davon ja: 380, nein: 270", 380, 270)[0], "several")
        # A tally inside a longer number is no tally.
        self.assertEqual(review.find_tally(text, 38, 27), ("none", []))
        self.assertEqual(review.find_tally(text, None, 270), ("none", []))
        self.assertEqual(review.find_tally(text, True, 270), ("none", []))

    # Value: protects=the tally scan stays linear on hostile text (checklist class 8); fails_when=an unbounded gap backtracks; why_new=new regex over source text; seam=none
    def test_long_runs_stay_fast(self) -> None:
        hostile = "ja " + "9" * 200_000 + " nein " + "x" * 200_000 + " ja " * 20_000
        started = time.monotonic()
        self.assertEqual(review.find_tally(hostile, 380, 270), ("none", []))
        self.assertLess(time.monotonic() - started, 2.0)


if __name__ == "__main__":
    unittest.main()
