"""Drift guard for the GitHub issue forms and the documented pre-fill URL.

Line-based checks only: PyYAML is not a dependency, so this cannot validate the
form schema. ``form_problems``, ``config_problems`` and ``plain_scalar_problems``
approximate the parts of it a typo breaks, and the negative-control tests below
prove each one fires on the break it names. Schema validity is the owner's manual
check on GitHub.
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
# A field's id sits at the indentation of a body item's keys (four spaces under
# "  - type:"). A line "id: x" inside a markdown block is indented deeper.
ID_LINE = re.compile(r"^ {4}id:\s*(\S+)\s*$", re.MULTILINE)
FIELD_TYPES = ("markdown", "input", "textarea", "dropdown", "checkboxes")
TOP_KEYS = ("name", "description", "title", "labels", "body")
ITEM_KEYS = ("id", "attributes", "validations")
ATTRIBUTE_KEYS = ("label", "description", "placeholder", "value", "options", "render", "multiple")
BLOCK_HEADER = re.compile(r"^(\s*)(?:- )?[A-Za-z_][A-Za-z0-9_-]*:\s+[|>][+-]?\d?\s*$")
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


def _structure_lines(text: str):
    """(number, line) of every line that is not inside a block scalar, with
    blank lines and comments left out."""
    block_indent: int | None = None
    for number, line in enumerate(text.splitlines(), 1):
        if block_indent is not None:
            if not line.strip() or len(line) - len(line.lstrip()) > block_indent:
                continue
            block_indent = None
        header = BLOCK_HEADER.match(line)
        if header:
            block_indent = len(header.group(1))
        if line.strip() and not line.lstrip().startswith("#"):
            yield number, line


def form_problems(text: str) -> list[str]:
    """What is structurally wrong with an issue form: a missing top-level key, a
    body that is not the list GitHub reads, an unknown field type, a field
    without id or label, a misspelt key, a duplicate label."""
    problems: list[str] = []
    lines = list(_structure_lines(text))
    tops = [line.split(":")[0] for _, line in lines if re.match(r"^[A-Za-z_]", line)]
    for key in TOP_KEYS:
        if tops.count(key) != 1:
            problems.append(f"top-level key {key!r} appears {tops.count(key)} times")
    for number, line in lines:
        if "\t" in line[: len(line) - len(line.lstrip())]:
            problems.append(f"{number}: tab indentation")
    in_body = False
    item_type: str | None = None
    item_key: str | None = None
    seen: dict[str, set[str]] = {"id": set(), "label": set()}
    for number, line in lines:
        where = f"{number}: {line.strip()}"
        if re.match(r"^[A-Za-z_]", line):
            in_body = line == "body:"
            continue
        if not in_body:
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 2:
            item = re.match(r"^  - type: (\S+)$", line)
            if not item:
                problems.append(f"{where}: not a body item")
                item_type = None
                continue
            item_type = item.group(1)
            item_key = None
            if item_type not in FIELD_TYPES:
                problems.append(f"{where}: unknown type {item_type!r}")
        elif item_type is None:
            problems.append(f"{where}: outside a body item")
        elif indent == 4:
            key = re.match(r"^    ([A-Za-z_]+):(?:\s|$)", line)
            if not key or key.group(1) not in ITEM_KEYS:
                problems.append(f"{where}: unknown item key")
                continue
            item_key = key.group(1)
            if item_key == "id":
                value = line.split(":", 1)[1].strip()
                if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
                    problems.append(f"{where}: illegal id")
                elif value in seen["id"]:
                    problems.append(f"{where}: duplicate id")
                seen["id"].add(value)
        elif indent == 6 and item_key == "attributes":
            key = re.match(r"^      ([A-Za-z_]+):(?:\s|$)", line)
            if not key or key.group(1) not in ATTRIBUTE_KEYS:
                problems.append(f"{where}: unknown attribute key")
            elif key.group(1) == "label":
                label = line.split(":", 1)[1].strip()
                if not label:
                    problems.append(f"{where}: empty label")
                elif label in seen["label"]:
                    problems.append(f"{where}: duplicate label")
                seen["label"].add(label)
        elif indent == 6 and item_key == "validations":
            if not re.match(r"^      required: (true|false)$", line):
                problems.append(f"{where}: unknown validation")
        elif indent not in (8, 10, 12) and item_key != "attributes":
            problems.append(f"{where}: unexpected indentation")
    # Per-item completeness, from a second pass over the raw text.
    for block in re.split(r"(?m)^  - type: ", text.split("\nbody:\n", 1)[1] if "\nbody:\n" in text else ""):
        if not block.strip():
            continue
        kind = block.split("\n", 1)[0].strip()
        if kind == "markdown":
            if not re.search(r"(?m)^      value:", block):
                problems.append("a markdown item has no value")
        elif kind in FIELD_TYPES:
            if not re.search(r"(?m)^    id: \S", block):
                problems.append(f"a {kind} item has no id")
            if not re.search(r"(?m)^      label: \S", block):
                problems.append(f"a {kind} item has no label")
    return problems


def config_problems(text: str) -> list[str]:
    """What is wrong with config.yml's shape: the two top-level keys, and every
    contact link a two-space "- name:" with url and about at four spaces."""
    problems: list[str] = []
    lines = list(_structure_lines(text))
    for number, line in lines:
        where = f"{number}: {line.strip()}"
        if re.match(r"^[A-Za-z_]", line):
            if not re.match(r"^(blank_issues_enabled: (true|false)|contact_links:)$", line):
                problems.append(f"{where}: unknown top-level line")
        elif re.match(r"^  - name: \S", line) or re.match(r"^    (url|about): \S", line):
            continue
        else:
            problems.append(f"{where}: unexpected indentation or key")
    if not any(line == "contact_links:" for _, line in lines):
        problems.append("no contact_links")
    return problems


def plain_scalar_problems(text: str) -> tuple[int, list[str]]:
    """(plain scalars checked, what YAML would reject in them): ": " or " #"
    inside, a trailing ":" (Psych reads a mapping key there and rejects it), or
    a leading indicator character. Quoted scalars, flow collections and block
    scalars are skipped; a line-based approximation, not a YAML parser."""
    key_line = re.compile(r"^(\s*)(?:- )?[A-Za-z_][A-Za-z0-9_-]*:\s+(\S.*?)\s*$")
    indicators = "!&*|>%@`,[]{}#'\"?-:"
    problems: list[str] = []
    checked = 0
    for number, line in _structure_lines(text):
        if BLOCK_HEADER.match(line):
            continue
        match = key_line.match(line)
        if not match:
            continue
        value = match.group(2)
        if value[0] in "\"'[{":
            continue  # quoted scalar or flow collection
        checked += 1
        where = f"{number}: {line.strip()}"
        if ": " in value or " #" in value or value.endswith(":"):
            problems.append(f"{where}: a plain scalar YAML rejects")
        elif value[0] in indicators:
            problems.append(f"{where}: starts with an indicator character")
    return checked, problems


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
        checked = 0
        for path in sorted(TEMPLATES.glob("*.yml")):
            with self.subTest(path=path.name):
                count, problems = plain_scalar_problems(_read(path))
                self.assertEqual([], problems)
                checked += count
        self.assertGreater(checked, 15)

    # Value: protects=no placeholder marker survives in public text that is live the moment the repository is public; fails_when=a PLATZHALTER, TODO, example.invalid or [B<digit> marker is committed in a form, config, SECURITY.md or CODE_OF_CONDUCT.md; why_new=the private-matters link was deliberately left out rather than stubbed; seam=none
    def test_no_placeholder_markers_in_public_text(self) -> None:
        paths = sorted(TEMPLATES.iterdir()) + [ROOT / "SECURITY.md", ROOT / "CODE_OF_CONDUCT.md"]
        self.assertGreaterEqual(len(paths), 5)
        for path in paths:
            with self.subTest(path=path.name):
                self.assertIsNone(PLACEHOLDER.search(_read(path)))


class NegativeControlTests(unittest.TestCase):
    """Each break below passed the id, label, quoting and URL checks; the shape
    checks now name it. The unbroken files are clean, or the controls prove
    nothing."""

    # Value: protects=the structural checks pass on the committed forms and config, so every negative control below is a real change from a clean state; fails_when=a form or config.yml gains a malformed line, a duplicate id or label, an unknown field type or a trailing-colon plain scalar; why_new=only ids, labels, quoting and URL drift were checked; seam=none; no_claim=not a YAML parser, the owner checks the schema on GitHub
    def test_the_committed_files_are_clean(self) -> None:
        for name in FORMS:
            with self.subTest(form=name):
                self.assertEqual([], form_problems(_read(TEMPLATES / name)))
        self.assertEqual([], config_problems(_read(TEMPLATES / "config.yml")))

    # Value: protects=a form with a field that has no label, an unknown field type, a renamed body key, a misspelt label key or a duplicate field label is flagged; fails_when=form_problems stops naming one of them; why_new=the review's negative controls (missing label, type: textfield, body: renamed, label typo, duplicate label) all passed the old checks; seam=none; no_claim=line-based, not the GitHub schema
    def test_form_breaks_are_flagged(self) -> None:
        text = _read(TEMPLATES / "datenfehler.yml")
        breaks = {
            "missing label": ("      label: Seite\n", ""),
            "unknown field type": ("  - type: input\n", "  - type: textfield\n"),
            "body renamed": ("\nbody:\n", "\nbodies:\n"),
            "label typo": ("      label: Seite\n", "      lable: Seite\n"),
            "duplicate label": ("label: Was steht in der Quelle?", "label: Was steht auf der Seite?"),
            "duplicate id": ("    id: quelle\n", "    id: seite\n"),
            "tab indentation": ("    id: seite\n", "\tid: seite\n"),
            "missing id": ("    id: seite\n", ""),
            "markdown without value": ("      value: |\n", "      valu: |\n"),
        }
        for name, (old, new) in breaks.items():
            with self.subTest(broken=name):
                self.assertIn(old, text)
                self.assertTrue(form_problems(text.replace(old, new, 1)), name)

    # Value: protects=a config.yml with broken indentation, a lost top-level key or an unknown key is flagged; fails_when=config_problems stops naming one of them; why_new=a mis-indented contact link passed the old checks; seam=none; no_claim=line-based, not the GitHub schema
    def test_config_breaks_are_flagged(self) -> None:
        text = _read(TEMPLATES / "config.yml")
        breaks = {
            "link indented by one": ("  - name:", " - name:"),
            "url indented by three": ("    url:", "   url:"),
            "about indented by six": ("    about:", "      about:"),
            "contact_links renamed": ("contact_links:", "contacts:"),
            "unknown top-level key": ("blank_issues_enabled:", "blank_issue_enabled:"),
        }
        for name, (old, new) in breaks.items():
            with self.subTest(broken=name):
                self.assertIn(old, text)
                self.assertTrue(config_problems(text.replace(old, new, 1)), name)

    # Value: protects=a plain scalar ending in ":" (which Psych rejects) is flagged, with the ": " and " #" cases; fails_when=plain_scalar_problems drops the trailing-colon rule; why_new=the check covered ": " inside a value but not at its end; seam=none; no_claim=line-based, not a YAML parser
    def test_a_plain_scalar_ending_in_a_colon_is_flagged(self) -> None:
        for value in ("Datenfehler:", "Ein Satz: mit Doppelpunkt", "Text # Kommentar", "- listet"):
            with self.subTest(value=value):
                self.assertTrue(plain_scalar_problems(f"title: {value}\n")[1], value)
        self.assertEqual((1, []), plain_scalar_problems("title: Ein Satz ohne Doppelpunkt\n"))
        self.assertEqual((0, []), plain_scalar_problems('title: "Datenfehler: "\n'))

    # Value: protects=ID_LINE reads only field ids (four spaces), so an "id:" line inside a markdown block neither joins the id list nor makes a pre-fill key valid; fails_when=ID_LINE matches at any indentation again; why_new=ID_LINE was ^\s*id: and matched inside a block; seam=none
    def test_id_line_ignores_a_line_inside_a_markdown_block(self) -> None:
        text = (
            "body:\n"
            "  - type: markdown\n"
            "    attributes:\n"
            "      value: |\n"
            "        Beispiel:\n"
            "        id: im-markdown\n"
            "  - type: input\n"
            "    id: seite\n"
        )
        self.assertEqual(["seite"], ID_LINE.findall(text))


if __name__ == "__main__":
    unittest.main()
