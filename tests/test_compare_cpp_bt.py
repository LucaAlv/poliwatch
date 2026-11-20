"""scripts/compare_cpp_bt.py: the release review's comparison with CPP-BT's speech metadata."""

from __future__ import annotations

import ast
import contextlib
import csv
import gzip
import io
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import _support  # noqa: F401
from _support import ROOT

import compare_cpp_bt as cmp  # noqa: E402
import validate_dip_protocol  # noqa: E402

HEADER = ["doc_id", "protokoll_nr", "rede_id", "redner_nachname", "redner_fraktion", "redner_rolle_kurz", "tokens"]

XML_18_1 = """<?xml version="1.0" encoding="UTF-8"?>
<dbtplenarprotokoll>
  <sitzungsverlauf>
    <tagesordnungspunkt top-id="Tagesordnungspunkt 1">
      <rede id="ID1800100100"><p klasse="redner">A</p></rede>
      <rede id="ID1800100200"><p klasse="redner">B</p></rede>
      <rede id="ID1800100300"><p klasse="redner">Präsident</p></rede>
    </tagesordnungspunkt>
    <rede id="ID1800100900"><p klasse="redner">outside</p></rede>
  </sitzungsverlauf>
  <anlagen>
    <anlage>
      <anlagen-text anlagen-typ="Erklärung nach § 31 GO des Abgeordneten X">
        <rede id="ID1800101000"><p klasse="redner">X</p></rede>
      </anlagen-text>
      <anlagen-text anlagen-typ="Zu Protokoll gegebene Rede">
        <rede id="ID1800101100"><p klasse="redner">Y</p></rede>
      </anlagen-text>
    </anlage>
  </anlagen>
</dbtplenarprotokoll>
"""


def words(count: int) -> str:
    return " ".join(["wort"] * count)


def build_export(path: Path, extra_tables: bool = True) -> None:
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE protocols (id TEXT, document_number TEXT);
        CREATE TABLE mps (id TEXT, display_name TEXT);
        CREATE TABLE speeches (protocol_id TEXT, rede_id TEXT, mp_id TEXT, fraktion TEXT, text TEXT);
        CREATE TABLE contributions (protocol_id TEXT, rede_id TEXT, mp_id TEXT, speaker_name TEXT, fraktion TEXT);
        CREATE TABLE withheld_units (protocol_id TEXT, rede_id TEXT, speaker_name TEXT, fraktion TEXT);
    """)
    db.executemany("INSERT INTO protocols VALUES (?, ?)", [("1", "18/1"), ("2", "18/2")])
    db.executemany("INSERT INTO mps VALUES (?, ?)", [
        ("m1", "Dr. Anna Muster, MdB, SPD"), ("m2", "Sevim Dagdelen, MdB, DIE LINKE"), ("m3", "Karl Dritter, MdB, AfD")])
    db.executemany("INSERT INTO speeches VALUES (?, ?, ?, ?, ?)", [
        ("1", "ID1800100100", "m1", "SPD", words(100)),
        ("1", "ID1800100200", "m2", "Die Linke", words(100)),
        # one <rede> split in two parts: the words of both parts belong to the element
        ("1", "ID1800100400", "m3", "AfD", words(60)),
        ("1", "ID1800100400:1", "m1", "SPD", words(40)),
        ("1", "ID1800100500", "m1", "SPD", words(100)),
        ("2", "ID1800200100", "m1", "SPD", words(100)),
    ])
    db.executemany("INSERT INTO contributions VALUES (?, ?, ?, ?, ?)", [
        ("1", "nested:ID1800100100:1", "m2", None, None),
        ("1", None, None, "Fragesteller", None),
        ("1", "", None, "Fragesteller", None),
    ])
    db.executemany("INSERT INTO withheld_units VALUES (?, ?, ?, ?)", [("1", "ID1800100300", "Präsident", None)])
    db.commit()
    db.close()


def cpp_rows() -> list[list[str]]:
    return [
        ["a", "18/1", "ID1800100100", "Muster", "SPD", "NA", "115"],
        ["b", "18/1 (neu)", "ID1800100200", "Dağdelen", "DIE LINKE.", "NA", "115"],
        ["c", "18/1", "ID1800100300", "Präsident", "NA", "Präsident", "10"],
        ["d", "18/1", "ID1800100400", "Dritter", "AfD", "NA", "115"],
        ["e", "18/1", "ID1800100500", "Muster", "SPD", "NA", "300"],
        ["f", "18/1", "ID1800100900", "Out", "NA", "NA", "70"],
        ["g", "18/1", "ID1800101000", "Xx", "NA", "NA", "70"],
        ["h", "18/1", "ID1800101100", "Yy", "NA", "NA", "70"],
        ["i", "18/1", "ID1800109999", "Gone", "NA", "NA", "70"],
        ["j", "18/3", "ID1800300100", "Only", "SPD", "NA", "70"],
    ]


def write_cpp(path: Path, rows: list[list[str]], bom: bool = False, as_zip: bool = False) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(rows)
    data = (("﻿" if bom else "") + buffer.getvalue()).encode("utf-8")
    if as_zip:
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("CPP-BT_test.csv", data)
    else:
        path.write_bytes(data)


class CompareCppBtTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        self.export = self.dir / "export.sqlite"
        build_export(self.export)
        self.xml = self.dir / "xml"
        self.xml.mkdir()
        (self.xml / "plenarprotokoll-18-1.xml").write_text(XML_18_1, encoding="utf-8")
        self.known = self.dir / "known.tsv"
        self.known.write_text("field\trede_id\tours\ttheirs\treason\n", encoding="utf-8")
        self.out = self.dir / "out.tsv"

    def run_main(self, cpp: Path, export: Path | None = None) -> tuple[int, str]:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = cmp.main(["--export", str(export or self.export), "--xml-dir", str(self.xml), "--cpp-bt", str(cpp),
                             "--out", str(self.out), "--known-differences", str(self.known)])
        return code, stderr.getvalue()

    def sections(self) -> dict[str, list[dict[str, str]]]:
        parts: dict[str, list[dict[str, str]]] = {}
        title, header = None, None
        for line in self.out.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                title, header = line[2:].split(":")[0], None
                parts[title] = []
            elif line and header is None:
                header = line.split("\t")
            elif line and title:
                parts[title].append(dict(zip(header, line.split("\t"))))
        return parts

    # Value: protects=the script's isolation claim in its docstring: standard library only, no project module, so a bug in the project cannot hide in its own check; fails_when=an import of scripts/ code or a third-party package is added; why_new=the script did not exist; seam=none; no_claim=what it computes
    def test_imports_only_the_standard_library(self) -> None:
        tree = ast.parse((ROOT / "scripts" / "compare_cpp_bt.py").read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules.add(node.module.split(".")[0])
        self.assertEqual(sorted(modules - set(sys.stdlib_module_names) - {"__future__"}), [])

    # Value: protects=the copied annex rules classify §31, continuation and reprint blocks exactly as the parser's ANNEX_EXCLUSIONS do; fails_when=a rule is added, renamed or reworded in only one of the two lists; why_new=the script copies the list so it can import nothing; seam=none; no_claim=other annex titles
    def test_annex_rules_match_the_parsers_rule_names_and_patterns(self) -> None:
        theirs = [(name, pattern.pattern) for name, pattern, _ in validate_dip_protocol.ANNEX_EXCLUSIONS]
        ours = [(name, pattern.pattern) for name, pattern in cmp.ANNEX_RULES]
        self.assertEqual(ours, theirs)

    # Value: protects=one definition per key (review checklist class 4): the (neu) suffix, the :N suffix, nested: and empty ids; fails_when=a normaliser stops dropping the suffix or starts accepting a non-id as an id; why_new=the script did not exist; seam=none; no_claim=ids the Bundestag never issued
    def test_keys_are_normalised_in_one_place(self) -> None:
        self.assertEqual(cmp.sitting_key("18/100"), "18/100")
        self.assertEqual(cmp.sitting_key("19/50 (neu)"), "19/50")
        self.assertEqual(cmp.sitting_key("019/050"), "19/50")
        for bad in (None, "", "NA", "18-100", "18/100 (alt)", 18, "18/100\n19/1"):
            self.assertIsNone(cmp.sitting_key(bad), repr(bad))
        self.assertEqual(cmp.source_rede_id("ID1801709200:3"), "ID1801709200")
        self.assertEqual(cmp.source_rede_id("ID1801709200"), "ID1801709200")
        for skipped in (None, "", "  ", "nested:ID19202300:4", "annex:1:2", "ID12", "xID1801709200"):
            self.assertIsNone(cmp.source_rede_id(skipped), repr(skipped))

    # Value: protects=the comparison counts, the classification of ids only CPP-BT has, absent-not-zero for a sitting one side lacks, and the inputs' digests; fails_when=a count changes on the synthetic store, a class is misassigned, or a missing sitting is written as 0; why_new=the script did not exist; seam=none; no_claim=the real store
    def test_three_sitting_comparison(self) -> None:
        cpp = self.dir / "cpp.zip"
        write_cpp(cpp, cpp_rows(), as_zip=True)
        code, message = self.run_main(cpp)
        self.assertEqual(code, 0, message)
        sections = self.sections()
        by_sitting = {row["sitting"]: row for row in sections["sittings"]}
        one = by_sitting["18/1"]
        # ours: 100, 200, 400 (with its :1 part), 500 and the withheld 300 only in withheld_units
        self.assertEqual((one["ours"], one["theirs"], one["both"], one["only_ours"], one["only_theirs"]),
                         ("4", "9", "4", "0", "5"))
        for name, expected in (("withheld", "1"), ("paragraph_31", "1"), ("annex_zu_protokoll", "1"),
                               ("outside_top", "1"), ("unclassified", "1")):
            self.assertEqual(one[name], expected, name)
        # a sitting only ours holds: their side is empty, never 0
        two = by_sitting["18/2"]
        self.assertEqual((two["ours"], two["theirs"], two["both"], two["only_theirs"]), ("1", "", "", ""))
        # a sitting only theirs holds
        three = by_sitting["18/3"]
        self.assertEqual((three["ours"], three["theirs"], three["both"], three["paragraph_31"]), ("", "1", "", ""))
        summary = {row["item"]: row["value"] for row in sections["summary"]}
        self.assertEqual(summary["sittings_both"], "1")
        self.assertEqual(summary["sittings_only_ours"], "1")
        self.assertEqual(summary["sittings_only_theirs"], "1")
        self.assertEqual(summary["theirs_ids_in_sittings_we_lack"], "1")
        self.assertEqual(summary["ours_skipped:nested_id"], "1")
        self.assertEqual(summary["ours_skipped:no_bundestag_id"], "2")
        self.assertEqual(summary["wp18:sittings_ours"], "2")
        self.assertEqual(summary["wp18:sittings_theirs"], "2")
        self.assertRegex(summary["input:cpp_bt"], r"^[0-9a-f]{64}  cpp\.zip$")
        self.assertRegex(summary["input:export"], r"^[0-9a-f]{64}  export\.sqlite$")

    # Value: protects=surname and Fraktion differences are listed per Rede, a known-differences row turns a difference into "known", an unlisted one stays "read_by_hand", and label folding hides only label noise (Die Linke vs DIE LINKE.); fails_when=a diacritic difference is folded away, a known row stops matching, or a label difference passes; why_new=the script did not exist; seam=none; no_claim=who is right
    def test_surname_and_fraktion_differences_and_the_known_file(self) -> None:
        cpp = self.dir / "cpp.csv"
        rows = cpp_rows()
        rows[0][3] = "Anderer"          # surname we have not listed
        rows[3][4] = "CDU/CSU"          # Fraktion we have not listed
        write_cpp(cpp, rows)
        self.run_main(cpp)
        diffs = {(row["kind"], row["rede_id"]): row for row in self.sections()["differences"]}
        self.assertEqual(diffs[("surname", "ID1800100200")]["status"], "read_by_hand")   # Dagdelen vs Dağdelen
        self.assertEqual(diffs[("surname", "ID1800100100")]["status"], "read_by_hand")
        self.assertEqual(diffs[("fraktion", "ID1800100400")]["status"], "read_by_hand")
        self.assertNotIn(("fraktion", "ID1800100200"), diffs)                            # Die Linke = DIE LINKE.
        self.known.write_text(
            "field\trede_id\tours\ttheirs\treason\n"
            "surname\t\tsevim dagdelen\tDağdelen\tspelling\n"
            "surname\tID1800100100\tdr. anna muster\tAnderer\ta reason\n"
            "fraktion\tID1800100400\tAfD\tCDU/CSU\t\n", encoding="utf-8")
        self.run_main(cpp)
        diffs = {(row["kind"], row["rede_id"]): row for row in self.sections()["differences"]}
        self.assertEqual(diffs[("surname", "ID1800100200")]["status"], "known")
        self.assertEqual(diffs[("surname", "ID1800100100")]["status"], "known")
        self.assertEqual(diffs[("fraktion", "ID1800100400")]["status"], "read_by_hand", "a row without a reason does not count")

    # Value: protects=the token-ratio lead: a shared Rede over the token floor whose words/tokens differs from its sitting's median by more than the tolerance is listed, under the floor it is not, and a split element counts the words of all its parts; fails_when=the part words stop being summed, the floor or tolerance moves; why_new=the script did not exist; seam=none; no_claim=the calibration
    def test_token_ratio_outliers(self) -> None:
        cpp = self.dir / "cpp.csv"
        rows = cpp_rows()
        rows[1][6] = "100"   # 100 words / 100 tokens = 1.0 against a median near 0.87 -> outlier
        write_cpp(cpp, rows)
        self.run_main(cpp)
        outliers = [row for row in self.sections()["differences"] if row["kind"] == "ratio"]
        ids = {row["rede_id"] for row in outliers}
        self.assertIn("ID1800100500", ids)           # 100 words against 300 tokens
        self.assertNotIn("ID1800100400", ids)        # 60 + 40 words against 115 tokens
        self.assertNotIn("ID1800100300", ids)        # 10 tokens, under the floor

    # Value: protects=a hostile CSV (review checklist classes 8 and 9): a BOM, a 1 MB field, an unbalanced quote, a missing column and a bad zip each end in a clear exit 2 or a correct read, never a traceback; fails_when=the script crashes with a traceback or reads a BOM header wrongly; why_new=the script reads a 71 MB file it does not own; seam=none; no_claim=other malformed inputs
    def test_hostile_csv(self) -> None:
        bom = self.dir / "bom.csv"
        write_cpp(bom, cpp_rows(), bom=True)
        self.assertEqual(self.run_main(bom)[0], 0)
        big = self.dir / "big.csv"
        rows = cpp_rows()
        rows[0][3] = "M" * 1_000_000
        write_cpp(big, rows)
        self.assertEqual(self.run_main(big)[0], 0)
        unbalanced = self.dir / "unbalanced.csv"
        unbalanced.write_text('"doc_id","protokoll_nr","rede_id","redner_nachname","redner_fraktion",'
                              '"redner_rolle_kurz","tokens"\n"a","18/1","ID1800100100","Mu"ster","SPD","NA","5"\n'
                              + '"x' + "y" * (cmp.CSV_FIELD_LIMIT + 10) + "\n", encoding="utf-8")
        code, message = self.run_main(unbalanced)
        self.assertEqual(code, 2)
        self.assertIn("unreadable CSV", message)
        missing = self.dir / "missing.csv"
        missing.write_text("doc_id,protokoll_nr\nx,18/1\n", encoding="utf-8")
        code, message = self.run_main(missing)
        self.assertEqual(code, 2)
        self.assertIn("missing columns", message)
        notzip = self.dir / "notzip.zip"
        notzip.write_bytes(b"PK not really")
        self.assertEqual(self.run_main(notzip)[0], 2)
        twozips = self.dir / "two.zip"
        with zipfile.ZipFile(twozips, "w") as archive:
            archive.writestr("a.csv", "x")
            archive.writestr("b.csv", "y")
        code, message = self.run_main(twozips)
        self.assertEqual(code, 2)
        self.assertIn("exactly one", message)
        self.assertEqual(self.run_main(self.dir / "absent.csv")[0], 2)

    # Value: protects=input shape for --export and --xml-dir: a gzip export reads like the plain one, and a non-SQLite file, an export without the tables and a missing xml directory each refuse with exit 2; fails_when=a bad export produces a traceback or a half-written report; why_new=the script did not exist; seam=none; no_claim=a corrupt but valid SQLite
    def test_export_and_directory_refusals(self) -> None:
        cpp = self.dir / "cpp.csv"
        write_cpp(cpp, cpp_rows())
        gz = self.dir / "export.sqlite.gz"
        with gzip.open(gz, "wb") as handle:
            handle.write(self.export.read_bytes())
        self.assertEqual(self.run_main(cpp, export=gz)[0], 0)
        junk = self.dir / "junk.sqlite"
        junk.write_bytes(b"not a database" * 100)
        self.assertEqual(self.run_main(cpp, export=junk)[0], 2)
        bare = self.dir / "bare.sqlite"
        sqlite3.connect(bare).close()
        code, message = self.run_main(cpp, export=bare)
        self.assertEqual(code, 2)
        self.assertIn("missing tables", message)
        badgz = self.dir / "bad.sqlite.gz"
        badgz.write_bytes(b"not gzip")
        self.assertEqual(self.run_main(cpp, export=badgz)[0], 2)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = cmp.main(["--export", str(self.export), "--xml-dir", str(self.dir / "nope"), "--cpp-bt", str(cpp),
                             "--out", str(self.out)])
        self.assertEqual(code, 2)
        with contextlib.redirect_stderr(stderr):
            code = cmp.main(["--export", str(self.export), "--xml-dir", str(self.xml), "--cpp-bt", str(cpp),
                             "--out", str(self.dir / "no_such_dir" / "out.tsv")])
        self.assertEqual(code, 2)

    # Value: protects=the export is opened read-only: the script leaves the store byte for byte as it found it; fails_when=a write, a journal or a pragma changes the file; why_new=the release review runs it on the release's own SQLite; seam=none; no_claim=that nothing else is written (the report is)
    def test_export_is_not_modified(self) -> None:
        cpp = self.dir / "cpp.csv"
        write_cpp(cpp, cpp_rows())
        before = self.export.read_bytes()
        self.assertEqual(self.run_main(cpp)[0], 0)
        self.assertEqual(self.export.read_bytes(), before)
        self.assertEqual(sorted(path.name for path in self.dir.glob("export.sqlite*")), ["export.sqlite"])

    # Value: protects=an id only CPP-BT has, inside a TOP and spoken by a presidium role, is read by hand as docs/release-review.md step 4 says, never passed as classified; fails_when=in_top_presidium leaves READ_BY_HAND or the known file stops being consulted for it; why_new=the first run had no such id, so no other test reaches the class; seam=none; no_claim=which presidium words the role list holds
    def test_presidium_id_only_theirs_is_read_by_hand(self) -> None:
        (self.xml / "plenarprotokoll-18-1.xml").write_text(
            XML_18_1.replace("    </tagesordnungspunkt>", '      <rede id="ID1800100600"><p klasse="redner">Chair</p></rede>\n    </tagesordnungspunkt>'),
            encoding="utf-8")
        cpp = self.dir / "cpp.csv"
        write_cpp(cpp, cpp_rows() + [["k", "18/1", "ID1800100600", "Chair", "NA", "Präsident", "20"]])
        self.assertEqual(self.run_main(cpp)[0], 0)
        row = next(r for r in self.sections()["differences"] if r["rede_id"] == "ID1800100600")
        self.assertEqual((row["kind"], row["status"]), ("only_theirs:in_top_presidium", "read_by_hand"))
        self.known.write_text("field\trede_id\tours\ttheirs\treason\nonly_theirs\tID1800100600\t\t\tchair, reviewed\n", encoding="utf-8")
        self.run_main(cpp)
        row = next(r for r in self.sections()["differences"] if r["rede_id"] == "ID1800100600")
        self.assertEqual(row["status"], "known")

    # Value: protects=two runs on the same inputs write the same bytes and the ratio rows of a sitting come largest deviation first, which step 4's 'read the 20 largest' relies on; fails_when=ratio rows follow set order again; why_new=nothing compared two runs; seam=none; no_claim=order across sittings (sorted by sitting number)
    def test_ratio_rows_are_ordered_and_runs_repeat(self) -> None:
        cpp = self.dir / "cpp.csv"
        rows = cpp_rows()
        rows[0][6], rows[1][6], rows[4][6] = "400", "60", "300"
        write_cpp(cpp, rows)
        self.run_main(cpp)
        first = self.out.read_text(encoding="utf-8")
        self.run_main(cpp)
        self.assertEqual(self.out.read_text(encoding="utf-8"), first)
        deviations = [float(r["detail"].split("deviation ")[1]) for r in self.sections()["differences"] if r["kind"] == "ratio"]
        self.assertGreaterEqual(len(deviations), 2)
        self.assertEqual(deviations, sorted(deviations, reverse=True))

    # Value: protects=--out never overwrites an input or a directory and a refused run leaves an earlier report whole (no .part file); fails_when=--out equal to --cpp-bt, --export or --known-differences is accepted, or a half-written report replaces a good one; why_new=the review runs it on the release's own SQLite and the downloaded CPP-BT zip; seam=none; no_claim=a power cut during os.replace
    def test_out_never_overwrites_an_input(self) -> None:
        cpp = self.dir / "cpp.csv"
        write_cpp(cpp, cpp_rows())
        before = cpp.read_bytes()
        for target in (cpp, self.export, self.known, self.dir):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = cmp.main(["--export", str(self.export), "--xml-dir", str(self.xml), "--cpp-bt", str(cpp),
                                 "--out", str(target), "--known-differences", str(self.known)])
            self.assertEqual(code, 2, target)
        self.assertEqual(cpp.read_bytes(), before)
        self.out.write_text("earlier report", encoding="utf-8")
        self.assertEqual(self.run_main(self.dir / "absent.csv")[0], 2)
        self.assertEqual(self.out.read_text(encoding="utf-8"), "earlier report")
        self.assertEqual(sorted(path.name for path in self.dir.glob("*.part")), [])

    # Value: protects=a known-differences row with fewer than five fields is ignored, as its docstring says, instead of crashing; fails_when=a short row raises AttributeError; why_new=csv.DictReader fills missing fields with None; seam=none; no_claim=that the shipped file is complete
    def test_short_known_differences_row_is_ignored(self) -> None:
        path = self.dir / "short.tsv"
        path.write_text("field\trede_id\tours\ttheirs\treason\nsurname\nsurname\tID1\ta\tb\treason\n", encoding="utf-8")
        self.assertEqual(len(cmp.known_differences(path)), 1)

    # Value: protects=a known-differences row for only_theirs with no rede_id is refused, since it would mark every id only CPP-BT holds as known; fails_when=such a row is accepted again; why_new=is_known matches the empty id for every Rede; seam=none; no_claim=that surname and fraktion rows with an empty id (a pair rule) are refused
    def test_only_theirs_row_without_a_rede_id_is_refused(self) -> None:
        path = self.dir / "blanket.tsv"
        path.write_text("field\trede_id\tours\ttheirs\treason\nonly_theirs\t\t\t\tall of them\n", encoding="utf-8")
        with self.assertRaises(cmp.InputError):
            cmp.known_differences(path)
        cpp = self.dir / "cpp.csv"
        write_cpp(cpp, cpp_rows())
        self.known = path
        code, message = self.run_main(cpp)
        self.assertEqual(code, 2)
        self.assertIn("only_theirs", message)

    # Value: protects=a known-differences file that is not UTF-8 and an export gzip with a bad deflate stream end in exit 2 with a message, not a traceback; fails_when=UnicodeDecodeError or zlib.error escapes main; why_new=neither is an OSError or EOFError, which the readers caught; seam=none; no_claim=that an encrypted zip or an unwritable --out is handled
    def test_corrupt_gzip_stream_and_non_utf8_known_file_exit_2(self) -> None:
        cpp = self.dir / "cpp.csv"
        write_cpp(cpp, cpp_rows())
        packed = gzip.compress(self.export.read_bytes())
        broken = self.dir / "broken.sqlite.gz"
        broken.write_bytes(packed[:10] + b"\xff" * 20 + packed[30:])
        code, message = self.run_main(cpp, export=broken)
        self.assertEqual(code, 2)
        self.assertIn("cannot decompress", message)
        latin = self.dir / "latin.tsv"
        latin.write_bytes("field\trede_id\tours\ttheirs\treason\nsurname\tID1\tM\xfcller\tb\treason\n".encode("latin-1"))
        self.known = latin
        code, message = self.run_main(cpp)
        self.assertEqual(code, 2)
        self.assertIn("known-differences", message)

    # Value: protects=a Rede whose stored text is empty is listed as a ratio outlier against CPP-BT's tokens, not skipped as unknown; fails_when=an empty speech text drops out of the ratio again; why_new=the worst case, no text at all, was the one silent case; seam=none; no_claim=why the text is empty
    def test_empty_speech_text_is_a_ratio_outlier(self) -> None:
        db = sqlite3.connect(self.export)
        db.execute("UPDATE speeches SET text = '' WHERE rede_id = 'ID1800100500'")
        db.commit()
        db.close()
        cpp = self.dir / "cpp.csv"
        write_cpp(cpp, cpp_rows())
        self.assertEqual(self.run_main(cpp)[0], 0)
        row = next(r for r in self.sections()["differences"] if r["kind"] == "ratio" and r["rede_id"] == "ID1800100500")
        self.assertEqual(row["ours"], "0")

    # Value: protects=a sitting whose median ratio is 0 (every text empty) lists its Reden instead of dividing by zero; fails_when=ZeroDivisionError returns; why_new=the 0-word rule made a zero median possible; seam=none; no_claim=what the median means when most texts are missing
    def test_zero_median_sitting_lists_its_reden(self) -> None:
        db = sqlite3.connect(self.export)
        db.execute("UPDATE speeches SET text = ''")
        db.commit()
        db.close()
        cpp = self.dir / "cpp.csv"
        write_cpp(cpp, cpp_rows())
        self.assertEqual(self.run_main(cpp)[0], 0)
        ratios = [r for r in self.sections()["differences"] if r["kind"] == "ratio"]
        self.assertGreaterEqual(len(ratios), 3)
        self.assertTrue(all("deviation 1.000" in r["detail"] for r in ratios))

    # Value: protects=a run whose join found nothing to compare ends in exit 2 instead of a vacuous pass: unreadable CPP-BT protocol numbers, unreadable tokens; fails_when=such a run exits 0 with ids_only_ours 0; why_new=a changed CPP-BT format would satisfy the written pass rule with no sitting compared; seam=none; no_claim=other format changes
    def test_a_comparison_that_compared_nothing_is_refused(self) -> None:
        for column, value, needle in ((1, "181", "no sitting is held by both"), (6, "115.0", "token count")):
            rows = cpp_rows()
            for row in rows:
                row[column] = value
            cpp = self.dir / f"bad{column}.csv"
            write_cpp(cpp, rows)
            code, message = self.run_main(cpp)
            self.assertEqual(code, 2, message)
            self.assertIn(needle, message)

    # Value: protects=the shipped known-differences file parses with a reason on every row and only the field names the report writes; fails_when=a row loses its reason or names a field the report never emits; why_new=the file is read by the review's pass rule; seam=none; no_claim=that each reason is true
    def test_shipped_known_differences_file(self) -> None:
        path = ROOT / "scripts" / "cpp_bt_known_differences.tsv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertGreater(len(rows), 90)
        for row in rows:
            self.assertIn(row["field"], {"surname", "fraktion", "only_theirs"})
            self.assertTrue(row["reason"].strip(), row)
        self.assertEqual(len(cmp.known_differences(path)), len(rows))


if __name__ == "__main__":
    unittest.main()
