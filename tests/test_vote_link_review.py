"""The vote-link review sheet (scripts/vote_link_review.py): strata, keys,
evidence columns, and refusals."""

from __future__ import annotations

import contextlib
import copy
import csv
import io
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any

import _support  # noqa: F401
import _site_store_fixture
import vote_link_review as review
import gzip

import reviewed_vote_links
import validate_dip_protocol as dip
import vote_links
from _support import FIXTURES

XML = """<?xml version="1.0" encoding="UTF-8"?>
<dbtplenarprotokoll><sitzungsverlauf><p>Ich gebe das Ergebnis der namentlichen Abstimmung über die
Beschlussempfehlung auf Drucksache 20/123 bekannt: abgegebene Stimmen 17. Mit Ja haben gestimmt 10,
mit Nein haben gestimmt 5, Enthaltungen 2.</p></sitzungsverlauf></dbtplenarprotokoll>"""


def sitting(repeated: bool = False) -> dict[str, Any]:
    """The fixture sitting with one vote per stratum, placed by the rule:
    12345 (printed 20/123) and v2 (DIP 20/456) share TOP 1 (S2); v4 links TOP 3
    and TOP 4 (S1); v3 is a title link (S3); v5 and v6 are plain (S4).
    ``repeated`` adds two TOPs with the same ``top_id`` "TR": v7 under the first
    (printed 20/701), v8 under the second (20/702 printed and DIP-linked)."""
    report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
    base = report["agenda_items"][0]["votes"][0]
    template = report["agenda_items"][1]

    def top(index: int, heading: str, printed: list[str] = (), linked: list[str] = (), top_id: str = "") -> dict:
        new = copy.deepcopy(template)
        new.update(index=index, top_id=top_id or f"T{index}", heading=heading, votes=[], xml_speakers=[],
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
    if repeated:
        report["agenda_items"] += [top(7, "TOP R Erste Beratung", printed=["20/701"], top_id="TR"),
                                   top(8, "TOP R Zweite Beratung", printed=["20/702"], linked=["20/702"], top_id="TR")]
        votes += [copy_of("v7", ["20/701"], "Erste Beratung"), copy_of("v8", ["20/702"], "Zweite Beratung")]
    report["agenda_items"][0]["votes"] = []
    report["api_records"] = {"roll_call_vote_candidates": votes, "matched_roll_call_votes": votes}
    return vote_links.attribute_votes(report)


class SiteCase(unittest.TestCase):
    """A site directory with the fixture sitting persisted and cached."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.site = Path(tmp.name) / "site"
        self.report = self.make_site(sitting())

    def make_site(self, built: dict[str, Any]) -> dict[str, Any]:
        """Persist ``built`` into a fresh store under ``self.site`` and cache it
        beside the store as the replay would; returns the persisted report."""
        report = _site_store_fixture.persistable([{"report": built}])[0]["report"]
        _site_store_fixture.build_site_store(self.site, [{"report": report}])
        self.write_cached(report)
        (self.site / "data" / "xml").mkdir(parents=True, exist_ok=True)
        (self.site / "data" / "xml" / "plenarprotokoll-20-999.xml").write_text(XML, encoding="utf-8")
        return report

    def write_cached(self, report: dict[str, Any]) -> None:
        (self.site / "data" / "plenarprotokoll-20-999.json").write_text(json.dumps(report), encoding="utf-8")

    def run_sheet(self, *extra: str, vorgang: str = "1", xml: str = "1") -> tuple[int, str, str]:
        out = self.site.parent / "review.tsv"
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = review.main(["--output-dir", str(self.site), "--out", str(out), "--sample-vorgang", vorgang,
                                "--sample-xml", xml, *extra])
        return code, out.read_text(encoding="utf-8") if out.exists() else "", stderr.getvalue()

    def rows(self, text: str) -> list[dict[str, str]]:
        return list(csv.DictReader((line for line in text.splitlines() if not line.startswith("#")), delimiter="\t"))


class SheetTests(SiteCase):

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

    def test_a_repeated_top_id_reads_each_occurrence_and_marks_printed_numbers(self) -> None:
        shutil.rmtree(self.site)
        self.make_site(sitting(repeated=True))
        code, text, _ = self.run_sheet(xml="3")
        self.assertEqual(code, 0)
        rows = {row["vote_id"]: row for row in self.rows(text)}
        self.assertEqual((rows["v7"]["top_id"], rows["v7"]["top_occurrence"]), ("TR", "1"))
        self.assertEqual((rows["v8"]["top_id"], rows["v8"]["top_occurrence"]), ("TR", "2"))
        self.assertEqual(rows["v7"]["shared"], "20/701:xml:-")
        # A number printed under the TOP and linked to its Vorgang shows both.
        self.assertEqual(rows["v8"]["shared"], "20/702:Antrag:vg-20/702:xml")
        self.assertEqual(rows["v8"]["basis"], "drucksache_xml")

    def test_evidence_is_read_by_top_id_and_occurrence_not_item_index(self) -> None:
        # A replay that adopts a TOP renumbers the store but not the cached
        # JSON: here the cached indices of T5 and T6 are swapped.
        cached = copy.deepcopy(self.report)
        by_top = {item["top_id"]: item for item in cached["agenda_items"]}
        by_top["T5"]["index"], by_top["T6"]["index"] = by_top["T6"]["index"], by_top["T5"]["index"]
        self.write_cached(cached)
        code, text, _ = self.run_sheet()
        self.assertEqual(code, 0)
        rows = {row["vote_id"]: row for row in self.rows(text)}
        self.assertEqual(rows["v5"]["shared"], "20/555:xml:-")
        self.assertEqual(rows["v6"]["shared"], "20/666:Antrag:vg-20/666")

    def test_a_repeated_top_id_the_cached_report_holds_fewer_times_shows_unknown(self) -> None:
        # The store holds "TR" twice, the cached report once: the occurrences
        # cannot be paired, so neither row borrows the other TOP's evidence.
        shutil.rmtree(self.site)
        report = self.make_site(sitting(repeated=True))
        cached = copy.deepcopy(report)
        cached["agenda_items"] = [item for item in cached["agenda_items"] if item["heading"] != "TOP R Erste Beratung"]
        self.write_cached(cached)
        code, text, _ = self.run_sheet(xml="3")
        self.assertEqual(code, 0)
        shared = {row["vote_id"]: row["shared"] for row in self.rows(text)}
        self.assertEqual((shared["v7"], shared["v8"]), ("?", "?"))
        self.assertEqual(shared["v5"], "20/555:xml:-")

    def test_a_malformed_cached_index_is_refused_with_a_message(self) -> None:
        cached = copy.deepcopy(self.report)
        cached["agenda_items"][0]["index"] = "erste"
        self.write_cached(cached)
        code, _, err = self.run_sheet()
        self.assertEqual((code, "cannot be read" in err), (2, True))

    def test_a_top_missing_from_the_cached_report_shows_unknown(self) -> None:
        cached = copy.deepcopy(self.report)
        cached["agenda_items"] = [item for item in cached["agenda_items"] if item["top_id"] != "T5"]
        self.write_cached(cached)
        code, text, _ = self.run_sheet()
        self.assertEqual(code, 0)
        self.assertEqual({row["vote_id"]: row["shared"] for row in self.rows(text)}["v5"], "?")

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


    def test_two_votes_with_one_tally_do_not_share_an_announcement(self) -> None:
        # v2 gets the tally the XML announces for 12345 (10 Ja, 5 Nein): the
        # one match could be either vote's, so neither row shows it.
        built = sitting()
        tallies = {vote["id"]: vote["total"] for item in built["agenda_items"] for vote in item.get("votes") or []}
        for item in built["agenda_items"]:
            for vote in item.get("votes") or []:
                if vote["id"] == "v2":
                    vote["total"] = dict(tallies["12345"])
        shutil.rmtree(self.site)
        self.make_site(built)
        rows = {row["vote_id"]: row for row in self.rows(self.run_sheet()[1])}
        self.assertEqual([(rows[vote]["tally"], rows[vote]["announced"]) for vote in ("12345", "v2")], [("several", "-")] * 2)

    def batch_file(self, text: str) -> str:
        path = self.site.parent / "batch.tsv"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_a_batch_sitting_is_marked_and_sampled_apart(self) -> None:
        # The fixture sitting is the batch: the first draw has no pool left, and
        # the batch draw takes both plain links (fewer than BATCH_MIN).
        code, text, _ = self.run_sheet("--batch-protocols", self.batch_file("sitting\tdate\n20/999\t2024-01-01\n"),
                                       vorgang="0", xml="0")
        self.assertEqual(code, 0)
        rows = self.rows(text)
        self.assertEqual({row["batch"] for row in rows}, {"t4"})
        self.assertEqual(sorted(row["vote_id"] for row in rows if row["stratum"] == "S4"), ["v5", "v6"])
        self.assertIn("# batch t4: 1 sittings of ", text)
        self.assertIn("7 links in store, 7 rows: S1 2, S2 2, S3 1, S4 2", text)
        code, _, err = self.run_sheet("--batch-protocols", self.batch_file("sitting\n20/999\n"))
        self.assertEqual((code, "exceeds the 0 plain drucksache_vorgang links" in err), (2, True))

    def test_without_a_batch_every_row_reads_a_dash(self) -> None:
        self.assertEqual({row["batch"] for row in self.rows(self.run_sheet()[1])}, {"-"})

    def test_bad_batch_inputs_are_refused_with_a_message(self) -> None:
        for content, message in (("protocol\n20/999\n", "has no sitting column"), ("sitting\n\n", "names no sitting"),
                                 ("sitting\n20/999\n20/998\n", "1 sittings the store does not hold: 20/998"),
                                 ("", "has no sitting column")):
            code, _, err = self.run_sheet("--batch-protocols", self.batch_file(content))
            self.assertEqual((code, message in err), (2, True), err)
        code, _, err = self.run_sheet("--batch-protocols", str(self.site.parent / "nowhere.tsv"))
        self.assertEqual((code, "cannot be read" in err), (2, True))
        (self.site.parent / "latin.tsv").write_bytes(b"sitting\n\xff\n")
        code, _, err = self.run_sheet("--batch-protocols", str(self.site.parent / "latin.tsv"))
        self.assertEqual((code, "cannot be read" in err), (2, True))
        code, _, err = self.run_sheet("--batch-protocols", self.batch_file("sitting\n20/999\n"), "--batch-name", "T 4")
        self.assertEqual((code, "--batch-name takes" in err), (2, True))

    def test_two_batches_need_a_name_each_and_share_no_sitting(self) -> None:
        one = self.batch_file("sitting\n20/999\n")
        code, _, err = self.run_sheet("--batch-protocols", one, "--batch-protocols", one, "--batch-name", "t4")
        self.assertEqual((code, "one --batch-name for each --batch-protocols" in err), (2, True), err)
        code, _, err = self.run_sheet("--batch-protocols", one, "--batch-protocols", one,
                                      "--batch-name", "t4", "--batch-name", "t4")
        self.assertEqual((code, "two batches are named t4" in err), (2, True), err)
        code, _, err = self.run_sheet("--batch-protocols", one, "--batch-protocols", one,
                                      "--batch-name", "t4", "--batch-name", "later")
        self.assertEqual((code, "20/999 is in the batches t4 and later" in err), (2, True), err)


class EntriesTests(SiteCase):
    """``--entries`` turns filled sheets into scripts/reviewed_vote_links.json, and the sheet keeps them (item 15)."""

    HEAD = "protocol\tvote_id\ttop_id\ttop_occurrence\tverdict\tpattern\taction\tevidence\treviewer\n"

    def filled(self, *rows: str) -> Path:
        path = self.site.parent / f"filled-{len(list(self.site.parent.glob('filled-*')))}.tsv"
        path.write_text("# a comment line\n" + self.HEAD + "".join(row + "\n" for row in rows), encoding="utf-8")
        return path

    def run_entries(self, *sheets: tuple[Path, str]) -> tuple[int, str]:
        argv = ["--output-dir", str(self.site), "--entries-file", str(self.entries_file)]
        for path, source in sheets:
            argv += ["--entries", str(path), source]
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = review.main(argv)
        return code, stderr.getvalue()

    def setUp(self) -> None:
        super().setUp()
        self.entries_file = self.site.parent / "reviewed_vote_links.json"

    def test_filled_rows_become_entries_with_heading_and_page_from_the_store(self) -> None:
        sheet = self.filled("20/999\t12345\tT1\t1\tright\t-\tnone\tthe chair calls it  here\tB01",
                            "20/999\tv4\tT4\t1\twrong\tA\trule\tumbrella\tB02")
        code, err = self.run_entries((sheet, "sheet 2026-11-21"))
        self.assertEqual(code, 0, err)
        entries = {entry.vote_id: entry for entry in reviewed_vote_links.load(self.entries_file)}
        self.assertEqual((entries["12345"].heading_starts, entries["12345"].page_start), ("TOP 1 Beratung Testgesetz", 101))
        self.assertEqual(entries["12345"].evidence, "the chair calls it here")
        self.assertEqual((entries["v4"].verdict, entries["v4"].pattern, entries["v4"].source), ("wrong", "A", "sheet 2026-11-21"))
        # Merging the same verdicts again changes nothing; another source's rows add to them.
        before = self.entries_file.read_bytes()
        self.assertEqual(self.run_entries((sheet, "sheet 2026-11-21"))[0], 0)
        self.assertEqual(self.entries_file.read_bytes(), before)
        more = self.filled("20/999\tv5\tT5\t1\tright\t-\tnone\tread\tplan")
        self.assertEqual(self.run_entries((more, "plan vote-pr-c"))[0], 0)
        self.assertEqual(len(reviewed_vote_links.load(self.entries_file)), 3)

    # Value: protects=no verdict is overwritten silently and no row without a verdict becomes an entry (plan section 4); fails_when=--entries merges by key without comparing verdicts, or reads an empty verdict as a value; why_new=PR C makes the entries file the record; seam=main
    def test_a_changed_or_missing_verdict_is_refused_and_nothing_is_written(self) -> None:
        self.assertEqual(self.run_entries((self.filled("20/999\t12345\tT1\t1\tright\t-\tnone\tok\tB01"), "sheet 2026-11-21"))[0], 0)
        before = self.entries_file.read_bytes()
        cases = [
            (self.filled("20/999\t12345\tT1\t1\twrong\tA\trule\tumbrella\tB09"), "holds verdict right, the sheet wrong"),
            (self.filled("20/999\tv5\tT5\t1\t\t\t\t\t"), "has no verdict"),
            (self.filled("20/999\tv5\tT9\t1\tright\t-\tnone\tok\tB01"), "holds no such TOP"),
            (self.filled("20/999\tv5\tT5\t1\tright\tA\tnone\tok\tB01"), "needs a pattern A to D"),
        ]
        for sheet, message in cases:
            with self.subTest(message=message):
                code, err = self.run_entries((sheet, "sheet 2026-11-21"))
                self.assertEqual(code, 2)
                self.assertIn(message, err)
                self.assertEqual(self.entries_file.read_bytes(), before)
        code, err = self.run_entries((self.filled("20/999\tv5\tT5\t1\tright\t-\tnone\tok\tB01"), "by hand"))
        self.assertEqual(code, 2)
        self.assertIn("source 'by hand'", err)

    # Value: protects=a regenerated sheet keeps every verdict the entries file holds (TODOS "Check that vote links are right" item 15); fails_when=build_sheet writes the verdict columns empty; why_new=a later batch regenerates the sheet; seam=main
    def test_a_regenerated_sheet_keeps_the_verdicts(self) -> None:
        self.run_entries((self.filled("20/999\t12345\tT1\t1\tright\t-\tnone\tthe chair calls it\tB01"), "sheet 2026-11-21"))
        code, text, _ = self.run_sheet("--entries-file", str(self.entries_file))
        self.assertEqual(code, 0)
        rows = {(row["vote_id"], row["top_id"]): row for row in self.rows(text)}
        self.assertEqual([rows[("12345", "T1")][column] for column in ("verdict", "pattern", "action", "evidence", "reviewer")],
                         ["right", "-", "none", "the chair calls it", "B01"])
        self.assertEqual(rows[("v2", "T1")]["verdict"], "")

    # Value: protects=the oracle fixture holds what the rule reads, re-read from the XML, also for a cached report whose JSON predates called_drucksachen (plan section 6); fails_when=--fixture copies the cached JSON as it is; why_new=PR C adds the fixture; seam=main
    def test_the_fixture_rereads_a_report_whose_json_predates_the_field(self) -> None:
        report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
        self.assertNotIn("called_drucksachen", report["agenda_items"][1])
        xml = (FIXTURES / "protocol.xml").read_text(encoding="utf-8")
        start, end = xml.index('<tagesordnungspunkt top-id="T2">'), xml.index("</tagesordnungspunkt>", xml.index('top-id="T2"'))
        xml = xml[:start] + '<tagesordnungspunkt top-id="T2"><p klasse="J">Abstimmung über Drucksache 20/123.</p>' + xml[end:]
        (self.site / "data" / "plenarprotokoll-20-999.json").write_text(json.dumps(report), encoding="utf-8")
        (self.site / "data" / "xml" / "plenarprotokoll-20-999.xml").write_text(xml, encoding="utf-8")
        self.entries_file.write_text(reviewed_vote_links.dump(reviewed_vote_links.check({"entries": [{
            "protocol": "20/999", "vote_id": "12345", "top_id": "T2", "top_occurrence": 1, "heading_starts": "", "page_start": None,
            "verdict": "right", "pattern": "-", "action": "none", "note": "", "evidence": "", "reviewer": "", "source": "plan vote-pr-c"}]})),
            encoding="utf-8")
        out = self.site.parent / "fixture.json.gz"
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(review.main(["--output-dir", str(self.site), "--entries-file", str(self.entries_file), "--fixture", str(out)]), 0)
        [sitting] = json.loads(gzip.decompress(out.read_bytes()))["sittings"]
        self.assertEqual([item["called_drucksachen"] for item in sitting["agenda_items"]], [[], ["20/123"]])
        self.assertEqual(vote_links.links(sitting)["12345"], ({1: "drucksache_call"}, "call"))
        first = out.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            review.main(["--output-dir", str(self.site), "--entries-file", str(self.entries_file), "--fixture", str(out)])
        self.assertEqual(out.read_bytes(), first)


class BatchDrawTests(unittest.TestCase):
    def links(self, protocols: list[str]) -> list[dict[str, Any]]:
        return [{"vote_id": f"{protocol}-{n}", "agenda_item_id": f"{protocol}-{n}", "document_number": protocol,
                 "basis": "drucksache_vorgang" if n % 3 else "drucksache_xml"}
                for protocol in protocols for n in range(20)]

    def test_a_batch_leaves_the_first_draw_as_it_was(self) -> None:
        before = review.strata(self.links(["20/1", "20/2"]), 7, 5, 3)
        after = review.strata(self.links(["20/1", "20/2", "18/1", "18/2", "18/3", "18/4"]), 7, 5, 3,
                              [frozenset({"18/1", "18/2", "18/3", "18/4"})])
        self.assertEqual({position for position in after if position < 40}, set(before))
        # 80 plain batch links: 16% is 12.8, drawn as 13.
        self.assertEqual(len([position for position in after if position >= 40]), 13)

    def test_a_second_batch_leaves_the_earlier_draws_as_they_were(self) -> None:
        first = frozenset({"18/1", "18/2", "18/3", "18/4"})
        one = review.strata(self.links(["20/1", "20/2", "18/1", "18/2", "18/3", "18/4"]), 7, 5, 3, [first])
        two = review.strata(self.links(["20/1", "20/2", "18/1", "18/2", "18/3", "18/4", "21/1"]), 7, 5, 3,
                            [first, frozenset({"21/1"})])
        self.assertEqual({position for position in two if position < 120}, set(one))
        # 20 plain links in the second batch: the minimum of 10 is drawn.
        self.assertEqual(len([position for position in two if position >= 120]), 10)

    def test_the_batch_sample_size(self) -> None:
        self.assertEqual([review.batch_sample_size(pool) for pool in (0, 3, 51, 62, 63, 100)], [0, 3, 10, 10, 11, 16])


class SharedDocumentsTests(unittest.TestCase):
    def test_a_number_read_off_a_news_site_url_is_not_printed(self) -> None:
        top = {"xml_drucksachen": [{"dokumentnummer": "21/5", "url": "https://euronews.com/x/21/5"}],
               "api": {"linked_drucksachen": [{"dokumentnummer": "21/6", "drucksachetyp": "Antrag", "vorgang_id": "7"}]}}
        link = {"vote_numbers": ["21/5", "21/6"]}
        self.assertEqual(review.shared_documents(link, top), "21/6:Antrag:7")


class TallyTests(unittest.TestCase):
    def test_unique_several_and_none(self) -> None:
        text = "über Drucksache 21/5 ... Mit Ja haben gestimmt 380, mit Nein haben gestimmt 270, Enthaltungen 2."
        self.assertEqual(review.find_tally(text, 380, 270), ("unique", ["21/5"]))
        self.assertEqual(review.find_tally(text + " davon ja: 380, nein: 270", 380, 270)[0], "several")
        # The result table printed after the announcement is no second tally,
        # also under a misprinted heading; two announcements stay several, and
        # a tally found only in the table is still found.
        table = " Die Beschlussempfehlung ist angenommen. Endgültiges Ergebnis Abgegebene Stimmen: 652; davon ja: 380 nein: 270 enthalten: 2"
        self.assertEqual(review.find_tally(text + table, 380, 270), ("unique", ["21/5"]))
        self.assertEqual(review.find_tally(text + table.replace("Endgültiges", "En dgültiges"), 380, 270)[0], "unique")
        self.assertEqual(review.find_tally(text + table + " " + text + table, 380, 270)[0], "several")
        self.assertEqual(review.find_tally("Drucksache 21/7." + table, 380, 270), ("unique", ["21/7"]))
        # A tally inside a longer number is no tally.
        self.assertEqual(review.find_tally(text, 38, 27), ("none", []))
        self.assertEqual(review.find_tally(text, None, 270), ("none", []))
        self.assertEqual(review.find_tally(text, True, 270), ("none", []))

    # Value: protects=the tally scan stays linear on hostile text (checklist class 8); fails_when=an unbounded gap backtracks; why_new=new regex over source text; seam=none
    def test_long_runs_stay_fast(self) -> None:
        hostile = "ja " + "9" * 200_000 + " nein " + "x" * 200_000 + " ja " * 20_000
        started = time.monotonic()
        self.assertEqual(review.find_tally(hostile, 380, 270), ("none", []))
        tables = "Ergebnis Abgegebene Stimmen: 1; davon ja: 380 nein: 270 " * 20_000
        self.assertEqual(review.find_tally(tables, 380, 270)[0], "several")
        self.assertLess(time.monotonic() - started, 2.0)  # gstack-timing-ok: checklist class 8 times hostile text; the linear scan of 600 kB takes milliseconds, a backtracking one far longer


if __name__ == "__main__":
    unittest.main()
