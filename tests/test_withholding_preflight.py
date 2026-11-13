"""W1's preflight tool (docs/plans/withholding-preflight/fetch_and_audit.py) and its committed result.

The tool and these tests go in PR 2 (v1-scope-review.md, TD1).
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import _support

PREFLIGHT = _support.ROOT / "docs/plans/withholding-preflight"
TOOL = PREFLIGHT / "fetch_and_audit.py"
GUEST = '<p klasse="redner"><redner id="99999999"><name><vorname>Test</vorname><nachname>Gast</nachname></name></redner>Test Gast:</p>'


def replace_line_after(text, anchor, expected, new):
    lines = text.split("\n")
    at = next(i for i, line in enumerate(lines) if anchor in line) + 1
    assert expected in lines[at], lines[at]
    lines[at] = new
    return "\n".join(lines)


def variants():
    """Real fixtures, edited into one shape each; keyed by the document number they are run under."""
    f150 = (_support.FIXTURES / "a3-wp18-18-150.xml").read_text(encoding="utf-8")
    f49 = (_support.FIXTURES / "reden-outside-tops/18-49.xml").read_text(encoding="utf-8")
    # Künast's second marker becomes a guest with no Fraktion: a located refusal at ID1815002700 marker 2.
    located = replace_line_after(f150, "Frau Kollegin Künast, ich glaube", 'redner id="11003576"', GUEST)
    # A role printed against its structured role refuses the whole sitting while the tree is built.
    conflict = located.replace("<nachname>Gast</nachname></name></redner>Test Gast:",
                               "<nachname>Gast</nachname><rolle><rolle_lang>Ministerpräsident (Hessen)</rolle_lang></rolle>"
                               "</name></redner>Test Gast, Bundesministerin:")
    # After the located refusal, a Rede in an annex no rule covers, as 19/36 prints a Zu-Protokoll Rede under
    # "Liste der entschuldigten Abgeordneten": the reconciliation refuses it once the walk is done, and
    # withholding cannot narrow that.
    then_other = located.replace("</sitzungsverlauf>", "</sitzungsverlauf>\n  <anlagen><anlage><anlagen-titel>Anlage 1</anlagen-titel>"
                                 '<anlagen-text anlagen-typ="Liste der entschuldigten Abgeordneten"><rede id="ID1815099900">'
                                 f'{GUEST}<p klasse="J">Zu Protokoll gegeben.</p></rede></anlagen-text></anlage></anlagen>')
    # A nested Rede split out of ID1804900200, which stands outside any TOP, holding a refused guest marker.
    lines = f49.split("\n")
    start = lines.index('      <rede id="ID1804900200">')
    end = next(i for i in range(start, len(lines)) if lines[i].strip() == "</rede>")
    lines[end:end] = [
        "<name>Präsident Dr. Norbert Lammert:</name>", '<p klasse="J_1">Nächster Redner ist Kai Gehring.</p>',
        '<p klasse="redner"><redner id="11009999"><name><vorname>Kai</vorname><nachname>Gehring</nachname>'
        "<fraktion>BÜNDNIS 90/DIE GRÜNEN</fraktion></name></redner>Kai Gehring (BÜNDNIS 90/DIE GRÜNEN):</p>",
        '<p klasse="J_1">Sehr geehrter Herr Präsident! Liebe Kolleginnen und Kollegen! Rede B mit einigen Worten mehr.</p>',
        "<name>Präsident Dr. Norbert Lammert:</name>", '<p klasse="J_1">Bitte.</p>', GUEST,
        '<p klasse="J_1">Eine Bemerkung ohne Frage.</p>']
    return {"18/150": f150, "18/10": located, "18/124": located, "18/2": conflict, "18/3": then_other,
            "18/49": "\n".join(lines)}


class PreflightToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / "xml").mkdir()
            for number, text in variants().items():
                (work / "xml" / f"plenarprotokoll-{number.replace('/', '-')}.xml").write_text(text, encoding="utf-8")
            listed = work / "sittings.txt"
            listed.write_text("18/150\n18/10\n\n18/124\n18/2\n18/3\n18/49\n18/20\n", encoding="utf-8")
            subprocess.run([sys.executable, "-I", str(TOOL), str(_support.SCRIPTS), str(work / "no-store"), str(work),
                            "--no-fetch", "--only-file", str(listed)], capture_output=True, text=True, check=True)
            cls.report = json.loads((work / "preflight.json").read_text(encoding="utf-8"))
        cls.rows = cls.report["sittings"]

    # Value: protects=--only-file reads one number per line in order; fails_when=blank lines or order are mishandled; why_new=the flag is new; seam=none
    def test_only_file_lists_the_sittings_in_order(self):
        self.assertEqual(list(self.rows), ["18/150", "18/10", "18/124", "18/2", "18/3", "18/49", "18/20"])
        self.assertEqual(self.rows["18/150"]["status"], "parses, no refusal")
        self.assertEqual(self.rows["18/20"]["refusal_class"], "fetch_rejected")

    # Value: protects=a missing --only-file is a clear refusal; fails_when=the path check is dropped and a traceback returns; why_new=QA capture 002 hit the traceback; seam=none
    def test_missing_only_file_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, "-I", str(TOOL), str(_support.SCRIPTS), tmp, tmp, "--no-fetch",
                                     "--only-file", str(Path(tmp) / "missing.txt")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("no such file", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    # Value: protects=B3, a sitting-wide refusal while the tree is built is a row, not the end of the run; fails_when=tree building leaves the try; why_new=it aborted the run before; seam=none
    def test_sitting_wide_refusal_is_recorded(self):
        row = self.rows["18/2"]
        self.assertEqual((row["status"], row["refusal_class"]), ("refused, not narrowable", "conflicting_roles"))
        self.assertIsNone(row["words_in_reden"])

    # Value: protects=located refusals survive an unnarrowable refusal after them; fails_when=the located list is replaced by the error; why_new=audit() drops it on raise; seam=none
    def test_located_refusals_kept_when_an_unnarrowable_one_follows(self):
        row = self.rows["18/3"]
        self.assertEqual(row["refusal_class"], "rede_reconciliation")
        self.assertIn("ID1815099900 (annex \"Liste der entschuldigten Abgeordneten\") has no status", row["error"])
        self.assertEqual(list(row["located_before_refusal"]), ["ID1815002700"])
        self.assertEqual(row["located_before_refusal"]["ID1815002700"]["refusal_class"], "located_nested_contribution")

    # Value: protects=B2, a split part of a Rede outside a TOP is found and its words counted; fails_when=Reden outside a TOP are not adopted first; why_new=its words counted as 0 before; seam=none
    def test_split_part_outside_a_top_counts_its_words(self):
        rede = self.rows["18/49"]["withheld_reden"]["ID1804900200:2"]
        self.assertEqual(rede["speaker"], "Kai Gehring")
        self.assertGreater(rede["words"], 0)
        self.assertEqual(self.rows["18/49"]["withheld_words"], rede["words"])

    # Value: protects=the comparison with the blockers file and the two flags; fails_when=missing or unlisted markers are misreported; why_new=both are new; seam=none
    def test_blockers_comparison_and_flags(self):
        self.assertEqual(self.rows["18/10"]["blockers"], {"expected": 1, "found": 1, "missing": ["ID1801002600:2 marker 4"],
                                                          "not_listed": ["ID1815002700 marker 2"]})
        self.assertIn("flag", self.rows["18/124"])
        self.assertNotIn("flag", self.rows["18/10"])
        self.assertEqual(self.report["summary"]["blockers_file"]["distinct_rede_ids"], 86)
        self.assertEqual(self.report["summary"]["blockers_file"]["rede_ids_under_two_sittings"], ["ID1802102900"])


class CommittedResultTests(unittest.TestCase):
    # Value: protects=the committed run covers exactly the 85 listed sittings and its summary matches its rows; fails_when=preflight.json or sittings-85.txt is edited by hand or truncated; why_new=both files are new; seam=none
    def test_result_matches_its_list_and_rows(self):
        numbers = (PREFLIGHT / "sittings-85.txt").read_text(encoding="utf-8").split()
        self.assertEqual(len(numbers), 85)
        self.assertEqual(len(set(numbers)), 85)
        report = json.loads((PREFLIGHT / "preflight.json").read_text(encoding="utf-8"))
        rows = report["sittings"]
        self.assertEqual(list(rows), numbers)
        summary = report["summary"]
        statuses = {}
        for row in rows.values():
            statuses[row["status"]] = statuses.get(row["status"], 0) + 1
        self.assertEqual(summary["status"], statuses)
        accepted = [row for row in rows.values() if row["status"] == "parses once withheld"]
        self.assertEqual(summary["withheld_reden"], sum(len(row["withheld_reden"]) for row in accepted))
        self.assertEqual(summary["withheld_words"], sum(row["withheld_words"] for row in accepted))


if __name__ == "__main__":
    unittest.main()
