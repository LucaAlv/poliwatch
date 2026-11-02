"""Drift guard for the GitHub issue forms and the documented pre-fill URL.

Text match only: PyYAML is not a dependency, so this cannot validate the form
schema. Schema validity is the owner's manual check on GitHub.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import _support  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / ".github" / "ISSUE_TEMPLATE"
FORMS = ("datenfehler.yml", "seitenfehler.yml")
ID_LINE = re.compile(r"^\s*id:\s*(\S+)\s*$", re.MULTILINE)
PLACEHOLDER = re.compile(r"PLATZHALTER|TODO|example\.invalid|\[B\d")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _documented_prefill_url() -> str:
    for line in _read(ROOT / "docs" / "project-documentation.md").splitlines():
        if line.startswith("| `--data-issues-url"):
            match = re.search(r"https://github\.com/[^\s`]+/issues/new\?[^\s`]+", line)
            if match:
                return match.group(0)
    raise AssertionError("no issues/new?… URL in the --data-issues-url row of docs/project-documentation.md")


def _triage_label() -> str:
    for line in _read(ROOT / "docs" / "agents" / "triage-labels.md").splitlines():
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] == "needs-triage":
            return cells[1]
    raise AssertionError("no needs-triage row in docs/agents/triage-labels.md")


class IssueFormTests(unittest.TestCase):
    # Value: protects=the --data-issues-url value documented for the public build opens an existing form and fills only fields that exist in it; fails_when=a form or field id is renamed without the documented URL, or the URL carries labels=; why_new=the pre-fill contract lived only in prose; seam=none; no_claim=does not validate the form schema (no YAML parser), the owner checks it on GitHub
    def test_documented_prefill_url_matches_the_form(self) -> None:
        parts = urlsplit(_documented_prefill_url())
        query = parse_qsl(parts.query, keep_blank_values=True)
        keys = dict(query)
        self.assertIn("template", keys)
        form = TEMPLATES / keys["template"]
        self.assertTrue(form.is_file(), f"{form} does not exist")
        ids = ID_LINE.findall(_read(form))
        for key, _ in query:
            if key == "template":
                continue
            self.assertNotEqual("labels", key)
            self.assertIn(key, ids, f"pre-fill field {key!r} is not an id in {form.name}")

    # Value: protects=every field id in a form is a legal, unique GitHub field id; fails_when=an id has a space or accent, or two fields share one; why_new=no form existed; seam=none
    def test_field_ids_are_legal_and_unique(self) -> None:
        for name in FORMS:
            with self.subTest(form=name):
                ids = ID_LINE.findall(_read(TEMPLATES / name))
                self.assertTrue(ids)
                for value in ids:
                    self.assertRegex(value, r"^[A-Za-z0-9_-]+$")
                self.assertEqual(len(ids), len(set(ids)))

    # Value: protects=both forms apply the triage label the label table names, so a rename there fails here instead of filing unlabelled issues; fails_when=a form drops needs-triage or docs/agents/triage-labels.md renames it; why_new=no form existed; seam=none
    def test_forms_apply_the_triage_label(self) -> None:
        label = _triage_label()
        for name in FORMS:
            with self.subTest(form=name):
                lines = [l for l in _read(TEMPLATES / name).splitlines() if l.startswith("labels:")]
                self.assertEqual(1, len(lines))
                self.assertIn(f'"{label}"', lines[0])

    # Value: protects=blank issues stay off so a report can only come in through a form; fails_when=config.yml loses or flips blank_issues_enabled; why_new=no config existed; seam=none
    def test_blank_issues_are_disabled(self) -> None:
        self.assertIn("\nblank_issues_enabled: false\n", "\n" + _read(TEMPLATES / "config.yml"))

    # Value: protects=every plain (unquoted) `key: value` line in the forms and config is valid YAML, so GitHub can load them; fails_when=an unquoted value contains ": " or " #" or starts with a YAML indicator character (YAML then reads a nested mapping or a comment, and GitHub rejects the template); why_new=both forms shipped with an unquoted ": " in a description and no parser is available to catch it; seam=none; no_claim=a line-based approximation, not a YAML parser: multi-line plain scalars and flow collections are not checked
    def test_plain_scalar_values_are_valid_yaml(self) -> None:
        key_line = re.compile(r"^(\s*)(?:- )?[A-Za-z_][A-Za-z0-9_-]*:\s+(\S.*?)\s*$")
        block_header = re.compile(r"^(\s*)(?:- )?[A-Za-z_][A-Za-z0-9_-]*:\s+[|>][+-]?\d?\s*$")
        indicators = "!&*|>%@`,[]{}#'\"?-:"
        checked = 0
        for path in sorted(TEMPLATES.glob("*.yml")):
            block_indent: int | None = None
            for number, line in enumerate(_read(path).splitlines(), 1):
                if block_indent is not None:
                    if not line.strip() or len(line) - len(line.lstrip()) > block_indent:
                        continue
                    block_indent = None
                header = block_header.match(line)
                if header:
                    block_indent = len(header.group(1))
                    continue
                match = key_line.match(line)
                if not match:
                    continue
                value = match.group(2)
                if value[0] in "\"'[{":
                    continue  # quoted scalar or flow collection
                checked += 1
                where = f"{path.name}:{number}: {line.strip()}"
                self.assertNotIn(": ", value, where)
                self.assertNotIn(" #", value, where)
                self.assertNotIn(value[0], indicators, where)
        self.assertGreater(checked, 15)

    # Value: protects=no placeholder marker survives in public text that is live the moment the repository is public; fails_when=a PLATZHALTER, TODO, example.invalid or [B<digit> marker is committed in a form, config, SECURITY.md or CODE_OF_CONDUCT.md; why_new=the private-matters link was deliberately left out rather than stubbed; seam=none
    def test_no_placeholder_markers_in_public_text(self) -> None:
        paths = sorted(TEMPLATES.iterdir()) + [ROOT / "SECURITY.md", ROOT / "CODE_OF_CONDUCT.md"]
        self.assertGreaterEqual(len(paths), 5)
        for path in paths:
            with self.subTest(path=path.name):
                self.assertIsNone(PLACEHOLDER.search(_read(path)))


if __name__ == "__main__":
    unittest.main()
