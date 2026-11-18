"""Guards for repository files that keep operator data and shipped bytes right."""
from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
