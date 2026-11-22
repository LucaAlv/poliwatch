"""Guards for repository files that keep operator data and shipped bytes right."""
from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

import _support  # noqa: F401
import build_dip_pulse_site as b

ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)


class RepoHygieneTests(unittest.TestCase):
    # Value: protects=the three authored codebook inputs are checked out with LF on every machine, so the exported LICENSE-DATA.md (LF-normalised) is byte-identical to the file the release commit holds; fails_when=a codebook input loses its eol=lf attribute in .gitattributes; why_new=a CRLF checkout made the shipped LICENSE-DATA.md differ from "the one that commit holds" (TODOS "Impressum/licence branch: deferred /gstack-review findings" item 10); seam=git check-attr
    def test_codebook_inputs_are_checked_out_with_lf(self) -> None:
        for path in b.CODEBOOK_INPUT_FILES.values():
            with self.subTest(path=path):
                result = _git("check-attr", "eol", "--", path)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertTrue(result.stdout.strip().endswith(": eol: lf"), result.stdout)

    # Value: protects=the conventional operator-file names stay out of git, so a name and postal address in a local operator.json is never committed by "git add ."; fails_when=.gitignore loses the operator.json entry; why_new=nothing kept the operator file out of git (TODOS "Impressum/licence branch: deferred /gstack-review findings" item 6); seam=git check-ignore; no_claim=an operator file under another name or a path inside the work tree is still the owner's care
    def test_the_conventional_operator_file_names_are_ignored(self) -> None:
        for name in ("operator.json", "operator.local.json", "site/operator.json"):
            with self.subTest(name=name):
                result = _git("check-ignore", "--no-index", "-q", "--", name)
                self.assertEqual(0, result.returncode, f"{name} is not ignored")

    # Value: protects=LICENSE-DATA.md passes DIP clause 5 on as the source's notice (not a term the project imposes) and says the wording that documents.forderung and votes.inversion_excerpt quote stays under the source's layer, with vote_passages named as pointing to it; fails_when=the sentence "continue to apply to any reuse" returns, the notice stops saying it adds no term of ours, or a quoting column drops out of the sentence; why_new=ADR 0003 research question 2 (docs/research/adr-0003-legal-questions-2026-11.md) found the old sentence read like a term and the three quoting columns unplaced; seam=LICENSE-DATA.md text; no_claim=legal sufficiency
    def test_license_data_passes_clause_5_on_as_a_notice_and_places_the_quoted_wording(self) -> None:
        text = (ROOT / "LICENSE-DATA.md").read_text(encoding="utf-8")
        self.assertNotIn("continue to apply to any reuse", text)
        self.assertIn("the source's notice", text)
        self.assertIn("not a term this file adds", text)
        self.assertIn("carries no such condition", text)
        quoted = next(p for p in text.split("\n\n") if "`documents.forderung`" in p and "`votes.inversion_excerpt`" in p)
        self.assertIn("`vote_passages`", quoted)
        self.assertIn("stays under the DIP layer", quoted)
        # The short string is the default --data-license and is copied verbatim into DATA.md: this change leaves it alone.
        self.assertIn("(Nutzungsbedingungen DIP)", b.default_license_text())

    # Value: protects=LICENSE-DATA.md names the stored Reden (and the one Beitrag) that keep "(Beifall" printed inline in a paragraph, so its sentence that speeches.text holds only the speaker's own words does not stand without its exceptions; fails_when=the list loses a Rede, gains one the store does not carry, or the notice drops the Beitrag; why_new=review of the owner-decisions PR (TODOS "ADR 0003 legal questions", item b); seam=LICENSE-DATA.md text; no_claim=that the list matches a later store (the query is recorded in TODOS)
    def test_license_data_names_the_reden_that_keep_inline_beifall(self) -> None:
        text = (ROOT / "LICENSE-DATA.md").read_text(encoding="utf-8")
        reden = {
            "18/92": "ID1809200100", "18/122": "ID1812201600", "18/124": "ID1812400200", "18/127": "ID1812705400",
            "18/174": "ID1817401100", "19/89": "ID198905400", "19/110": "ID1911000200", "19/130": "ID1913005300",
            "19/137": "ID1913713700", "19/146": "ID1914613800", "19/155": "ID1915509200", "20/45": "ID204504800",
            "20/163": "ID2016309300",
        }
        paragraph = next(p for p in text.split("\n") if "13 Reden" in p)
        for protocol, rede_id in reden.items():
            with self.subTest(protocol=protocol):
                self.assertIn(f"{protocol} {rede_id}", paragraph)
        self.assertEqual(13, len(re.findall(r"\b\d{2}/\d+ ID\d+", paragraph.split("and the Beitrag")[0])))
        self.assertIn("21/49 ID214902800", paragraph)
        # The dictionary entries of both text columns carry the exception and point to the list.
        tables = json.loads((ROOT / "scripts" / "data_dictionary.json").read_text(encoding="utf-8"))["tables"]
        for table in ("speeches", "contributions"):
            with self.subTest(table=table):
                meaning = tables[table]["columns"]["text"]["meaning"]
                self.assertIn("„(Beifall …)“", meaning)
                self.assertIn("LICENSE-DATA.md", meaning)


if __name__ == "__main__":
    unittest.main()
