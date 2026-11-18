"""Code rules for scripts/ that review kept having to catch by hand
(docs/agents/review-checklist.md). Each failure message says why the rule exists
and how to fix the cause.

- Class 1, sibling path: only the openers in SQLITE_OPENERS may call
  ``sqlite3.connect`` or ``sqlite3.Connection``, and no SQL may ATTACH a file.
- Class 5, absent vs zero: no new ``or 0``, and no ``= ?`` / ``!= ?`` on a store
  column that can be NULL unless tests/code_rules_baseline.json lists it with a
  reason.
- Import layers: a module imports only groups below its own (LAYERS), and the
  import graph has no cycle beyond KNOWN_CYCLES.

The rules read the source with ``ast``; they cannot see imports made through
importlib or SQL assembled with ``+``."""
from __future__ import annotations

import ast
import functools
import json
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from typing import Iterable, Iterator, Mapping, NamedTuple
from unittest import mock

import _support  # noqa: F401
import facts
import persist_dip_pulse_store as pulse_store

ROOT = _support.ROOT
SCRIPTS = _support.SCRIPTS
BASELINE_PATH = Path(__file__).with_name("code_rules_baseline.json")


class Finding(NamedTuple):
    file: str
    line: int
    function: str
    text: str


# ---------------------------------------------------------------------------
# Reading scripts/
# ---------------------------------------------------------------------------


@functools.cache
def script_modules() -> dict[str, Path]:
    """Module name -> file, for every .py under scripts/."""
    modules: dict[str, Path] = {}
    for path in sorted(SCRIPTS.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        parts = path.relative_to(SCRIPTS).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        modules[".".join(parts)] = path
    return modules


@functools.cache
def parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def walk_with_function(tree: ast.AST) -> Iterator[tuple[ast.AST, str]]:
    """Every node with the qualified name of the def or class around it
    (``<module>`` at top level)."""

    def visit(node: ast.AST, scope: tuple[str, ...]) -> Iterator[tuple[ast.AST, str]]:
        for child in ast.iter_child_nodes(node):
            yield child, ".".join(scope) or "<module>"
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                yield from visit(child, scope + (child.name,))
            else:
                yield from visit(child, scope)

    yield from visit(tree, ())


# ---------------------------------------------------------------------------
# Class 1: who may open SQLite
# ---------------------------------------------------------------------------

SQLITE_OPENERS = {
    ("sqlite_open", "open_readonly"): "reading any SQLite file",
    ("sqlite_open", "create_database"): "a new file this run writes",
    ("persist_dip_pulse_store", "connect"): "writing the build store or a staged copy of it",
    ("compare_cpp_bt", "open_export"): (
        "a published export, read-only, in the one check that imports only the standard library "
        "(tests/test_compare_cpp_bt.py)"
    ),
}


_SQLITE_MODULES = ("sqlite3", "sqlite3.dbapi2")
_OPENING_NAMES = ("connect", "Connection")
_ATTACH = re.compile(r"\bATTACH\s+(?:DATABASE\s+)?['\"?:{]", re.IGNORECASE)


def sqlite_connect_calls(tree: ast.Module) -> Iterator[tuple[int, str]]:
    """(line, enclosing function) of every call that opens a SQLite file:
    ``sqlite3.connect`` or ``sqlite3.Connection``, through any import alias,
    ``dbapi2`` included."""
    module_aliases = {"sqlite3"}
    function_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in _SQLITE_MODULES:
                    module_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module in _SQLITE_MODULES:
            for alias in node.names:
                if alias.name in _OPENING_NAMES:
                    function_aliases.add(alias.asname or alias.name)
                elif alias.name == "dbapi2":
                    module_aliases.add(alias.asname or alias.name)
    module_aliases |= {f"{alias}.dbapi2" for alias in module_aliases}
    for node, function in walk_with_function(tree):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if (
            isinstance(target, ast.Attribute)
            and target.attr in _OPENING_NAMES
            and ast.unparse(target.value) in module_aliases
        ) or (isinstance(target, ast.Name) and target.id in function_aliases):
            yield node.lineno, function


def sqlite_open_violations(modules: Mapping[str, Path]) -> list[Finding]:
    found = []
    for name, path in modules.items():
        tree = parsed(path)
        for line, function in sqlite_connect_calls(tree):
            if (name, function) not in SQLITE_OPENERS:
                found.append(Finding(relative(path), line, function, "sqlite3.connect"))
        scopes = {id(node): function for node, function in walk_with_function(tree)}
        for node, text in string_literals(tree):
            if _ATTACH.search(text):
                found.append(Finding(relative(path), node.lineno, scopes[id(node)], "ATTACH"))
    return found


def sqlite_open_message(finding: Finding) -> str:
    openers = "; ".join(f"{module}.{function} for {use}" for (module, function), use in SQLITE_OPENERS.items())
    if finding.text == "ATTACH":
        return (
            f"{finding.file}:{finding.line} ATTACHes a database in {finding.function}. ATTACH opens a second file "
            "on an existing connection and can write it without persist_dip_pulse_store.connect's refusals "
            f"(review-checklist class 1). Open each file with its own opener instead: {openers}."
        )
    return (
        f"{finding.file}:{finding.line} opens SQLite directly in {finding.function}. Open SQLite only through: {openers}. "
        "A direct connect skips the build store's refusals (a distribution copy, foreign keys off); "
        "PR #91's facts engine wrote that way (review-checklist class 1). If none of the three fits, "
        "add an opener with the refusals it needs to scripts/sqlite_open.py and list it in SQLITE_OPENERS."
    )


# ---------------------------------------------------------------------------
# Class 5: absent vs zero
# ---------------------------------------------------------------------------


def is_zero(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant)
        and type(node.value) in (int, float)
        and node.value == 0
    )


def or_zero_findings(path: Path, tree: ast.Module) -> list[Finding]:
    return [
        Finding(relative(path), node.lineno, function, ast.unparse(node))
        for node, function in walk_with_function(tree)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and is_zero(node.values[-1])
    ]


def or_zero_message(finding: Finding) -> str:
    return (
        f"{finding.file}:{finding.line} `{finding.text}` in {finding.function}: `or 0` turns a missing value "
        "(None, and also '' or False) into a real zero, so an unknown figure is published as 0 "
        "(review-checklist class 5, absent vs zero). Decide what absence means here. Not measured: keep None "
        "and let the page say so. A source that leaves zero counts out: `mapping.get(key, 0)`, which still fails "
        "loudly on an explicit null. Checked that None means zero: write `0 if value is None else value`, so the "
        "decision is visible in the code. Do not add entries to tests/code_rules_baseline.json; it only shrinks."
    )


_COMPARISON = re.compile(r"(?:\b([A-Za-z_]\w*)\.)?\b([A-Za-z_]\w*)\s*(!=|<>|==|=)\s*\?")
_CLAUSE = re.compile(r"\b(SET|WHERE|AND|OR|ON|HAVING|WHEN|NOT)\b", re.IGNORECASE)
_NOT_ALIAS = (
    "WHERE|SET|ON|USING|LEFT|RIGHT|INNER|OUTER|CROSS|FULL|JOIN|NATURAL|GROUP|ORDER|LIMIT|VALUES|SELECT|"
    "UNION|EXCEPT|INTERSECT|HAVING|WINDOW|DEFAULT|AND|OR|AS|DO|RETURNING"
)
_TABLE_REF = re.compile(
    rf"\b(?:FROM|JOIN|UPDATE|INTO)\s+([A-Za-z_]\w*)(?:\s+(?:AS\s+)?(?!(?:{_NOT_ALIAS})\b)([A-Za-z_]\w*))?",
    re.IGNORECASE,
)


@functools.cache
def store_schema() -> dict[str, dict[str, bool]]:
    """table -> column -> nullable, from an empty store the build itself creates."""
    with tempfile.TemporaryDirectory() as scratch:
        conn = pulse_store.connect(Path(scratch) / "store.sqlite")
        try:
            pulse_store.initialize(conn)
            facts.ensure_tables(conn)
            tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
            return {
                table: {
                    row["name"]: not row["notnull"] and not row["pk"]
                    for row in conn.execute("SELECT * FROM pragma_table_info(?)", (table,))
                }
                for table in tables
            }
        finally:
            conn.close()


def string_literals(tree: ast.Module) -> Iterator[tuple[ast.AST, str]]:
    """Every string constant, and every f-string with its fields as ``{}``."""
    inside_fstring: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            inside_fstring |= {id(value) for value in node.values}
    for node, function in walk_with_function(tree):
        if isinstance(node, ast.JoinedStr):
            text = "".join(value.value if isinstance(value, ast.Constant) else "{}" for value in node.values)
            yield node, text
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in inside_fstring:
            yield node, node.value


def table_references(sql: str) -> tuple[dict[str, str], list[str]]:
    """(alias -> table, tables in order) named after FROM, JOIN, UPDATE or INTO."""
    aliases: dict[str, str] = {}
    tables: list[str] = []
    for match in _TABLE_REF.finditer(sql):
        table = match.group(1)
        tables.append(table)
        aliases[table] = table
        if match.group(2):
            aliases[match.group(2)] = table
    return aliases, tables


def is_comparison(sql: str, match: re.Match[str]) -> bool:
    """A ``col = ?`` is a comparison after WHERE, AND, ON and the like, and an
    assignment after SET. A fragment that starts with it counts as a comparison
    only when AND or OR follows; a bare ``col = ?`` or a comma list stays unknown."""
    before = _CLAUSE.findall(sql, 0, match.start())
    if before:
        return before[-1].upper() != "SET"
    after = _CLAUSE.search(sql, match.end())
    return after is not None and after.group(1).upper() in ("AND", "OR")


def nullable_comparisons(sql: str, schema: Mapping[str, Mapping[str, bool]], context: str = "") -> list[str]:
    """``table.column op ?`` for each comparison with a bound value on a column
    that can be NULL. A fragment that names no table takes its tables from
    ``context``, the other literals of its function; a statement whose tables
    are not in the schema is skipped."""
    aliases, tables = table_references(sql)
    if not tables and context:
        aliases, tables = table_references(context)
    found = []
    for match in _COMPARISON.finditer(sql):
        if not is_comparison(sql, match):
            continue
        qualifier, column, operator = match.groups()
        if qualifier:
            owners = [aliases.get(qualifier, qualifier)]
        else:
            owners = list(dict.fromkeys(tables))
        nullable = [table for table in owners if schema.get(table, {}).get(column)]
        if nullable:
            found.append(f"{nullable[0]}.{column} {operator} ?")
    return found


def nullable_comparison_findings(path: Path, tree: ast.Module, schema: Mapping[str, Mapping[str, bool]]) -> list[Finding]:
    scopes = {id(node): function for node, function in walk_with_function(tree)}
    literals = [(node, text, scopes[id(node)]) for node, text in string_literals(tree)]
    context: dict[str, list[str]] = {}
    for _, text, function in literals:
        context.setdefault(function, []).append(text)
    return [
        Finding(relative(path), node.lineno, function, comparison)
        for node, text, function in literals
        for comparison in nullable_comparisons(text, schema, "\n".join(context[function]))
    ]


def nullable_comparison_message(finding: Finding) -> str:
    column = finding.text.split(" ", 1)[0]
    return (
        f"{finding.file}:{finding.line} `{finding.text}` in {finding.function}: {column} can be NULL. "
        "`= ?` never matches a NULL row, even when the bound value is None, and `!= ?` silently drops "
        "NULL rows (review-checklist class 5, absent vs zero). Use `IS ?` / `IS NOT ?` when None can be "
        "bound or NULL rows must count. If the bound value can never be None and leaving NULL rows out "
        "is intended, list the comparison under nullable_comparisons in tests/code_rules_baseline.json "
        "with that reason."
    )


def counted_or_zero(findings: Iterable[Finding]) -> Counter[tuple[str, str, str]]:
    return Counter((finding.file, finding.function, finding.text) for finding in findings)


# ---------------------------------------------------------------------------
# Import layers
# ---------------------------------------------------------------------------

#: Group -> its modules (a package covers its submodules) and what it is for.
GROUPS: dict[str, tuple[frozenset[str], str]] = {
    "tools": (
        frozenset({
            "build_demo_site", "check_withhold_one", "compare_cpp_bt", "compare_store_values",
            "extract_demo_fixture", "measure_aw_match_share", "prefetch_dip_bulk",
            "publish_dip_pulse_data", "validate_store_gate", "vote_link_review",
        }),
        "standalone checks, comparisons and release scripts; nothing outside tools imports them",
    ),
    "build": (frozenset({"build_dip_pulse_site"}), "the site build CLI; only tools import it"),
    "facts": (frozenset({"facts"}), "the Fakt der Woche engine over the store"),
    "feeds": (frozenset({"week_radar_feed"}), "the week radar feed"),
    "store": (
        frozenset({"persist_dip_pulse_store"}),
        "writes parsed reports into the build store; it never renders pages",
    ),
    "pages": (
        frozenset({"render_dip_pulse_html", "features"}),
        "renders HTML from the rows it is given; it never opens the store writer",
    ),
    "parse": (
        frozenset({"validate_dip_protocol", "vote_links", "dip_cache", "sitzungskalender"}),
        "reads the protocol XML and DIP records into reports; no store, pages or facts",
    ),
    "domain": (
        frozenset({"derive", "person_registry", "speech_kinds", "politikfelder", "stammdaten", "antrag_text"}),
        "rules over parsed data (votes, persons, speech kinds, Politikfelder); no parser, store or pages",
    ),
    "base": (
        frozenset({
            "stable_ids", "publication_state", "python_version_guard", "reviewed_units", "dip_text",
            "release_version", "release_changes", "build_revision", "sqlite_open", "abgeordnetenwatch",
        }),
        "helpers that import only each other",
    ),
}

#: Top layer first. A group imports its own modules and groups in lower layers,
#: never a sibling group in its own layer.
LAYERS: tuple[tuple[str, ...], ...] = (
    ("tools",),
    ("build",),
    ("facts", "feeds"),
    ("store", "pages"),
    ("parse",),
    ("domain",),
    ("base",),
)

#: Import cycles that predate the rule, with why they exist.
KNOWN_CYCLES: dict[frozenset[str], str] = {
    frozenset({"validate_dip_protocol", "vote_links"}): (
        "vote_links uses validate_dip_protocol.title_matches while the parser calls vote_links "
        "(TODOS.md \"Move title_matches below the parser\")"
    ),
}


def group_of(module: str) -> str | None:
    parts = module.split(".")
    for end in range(len(parts), 0, -1):
        candidate = ".".join(parts[:end])
        for group, (members, _) in GROUPS.items():
            if candidate in members:
                return group
    return None


def layer_of(group: str) -> int:
    return next(index for index, layer in enumerate(LAYERS) if group in layer)


def imports_of(name: str, path: Path, tree: ast.Module, modules: Mapping[str, Path]) -> list[tuple[str, int]]:
    """(project module, line) for every import in the file, at any depth."""
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    found: list[tuple[str, int]] = []

    def resolve(candidate: str) -> str | None:
        while candidate:
            if candidate in modules:
                return candidate
            candidate = candidate.rpartition(".")[0]
        return None

    for node in ast.walk(tree):
        targets: list[str] = []
        if isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package
                for _ in range(node.level - 1):
                    base = base.rpartition(".")[0]
                base = f"{base}.{node.module}" if node.module else base
            else:
                base = node.module or ""
            targets = [f"{base}.{alias.name}" if f"{base}.{alias.name}" in modules else base for alias in node.names]
        for target in targets:
            module = resolve(target)
            if module is not None and module != name:
                found.append((module, node.lineno))
    return found


def import_graph(modules: Mapping[str, Path]) -> dict[str, list[tuple[str, int]]]:
    return {name: imports_of(name, path, parsed(path), modules) for name, path in modules.items()}


def layer_violations(graph: Mapping[str, list[tuple[str, int]]], modules: Mapping[str, Path]) -> list[str]:
    problems = []
    for name in graph:
        if group_of(name) is None:
            problems.append(
                f"scripts module {name} is in no group of tests/test_code_rules.py GROUPS: add it to the lowest "
                "group whose rules it keeps (each group's description says what it may not import)."
            )
    for name, edges in graph.items():
        source = group_of(name)
        if source is None:
            continue
        for target, line in edges:
            destination = group_of(target)
            if destination is None or destination == source:
                continue
            if layer_of(destination) > layer_of(source):
                continue
            relation = "a sibling group in its own layer" if layer_of(destination) == layer_of(source) else "a group above it"
            problems.append(
                f"{relative(modules[name])}:{line} imports {target}, which is in {relation}. "
                f"Group {source} may import only groups below it in LAYERS. "
                f"{source}: {GROUPS[source][1]}. {destination}: {GROUPS[destination][1]}. "
                "Move what both need down to a group both may import, or have the caller pass the value in."
            )
    return problems


def cycles(graph: Mapping[str, list[tuple[str, int]]]) -> list[frozenset[str]]:
    """Strongly connected components with more than one module (Tarjan)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    found: list[frozenset[str]] = []

    def connect(node: str) -> None:
        index[node] = low[node] = len(index)
        stack.append(node)
        on_stack.add(node)
        for target, _ in graph.get(node, []):
            if target not in index:
                connect(target)
                low[node] = min(low[node], low[target])
            elif target in on_stack:
                low[node] = min(low[node], index[target])
        if low[node] == index[node]:
            component = set()
            while True:
                member = stack.pop()
                on_stack.discard(member)
                component.add(member)
                if member == node:
                    break
            if len(component) > 1:
                found.append(frozenset(component))

    for node in sorted(graph):
        if node not in index:
            connect(node)
    return found


# ---------------------------------------------------------------------------
# The rules on the real scripts/
# ---------------------------------------------------------------------------


def load_baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


class RuleTestCase(unittest.TestCase):
    def assertNoProblems(self, problems: list[str]) -> None:
        """Each problem in full, one paragraph apiece: the messages are the fix instructions."""
        if problems:
            self.fail(f"{len(problems)} problem(s):\n\n" + "\n\n".join(problems))


class SqliteOpenRuleTests(RuleTestCase):
    # Value: protects=every SQLite open in scripts/ goes through the three openers, so a write to an existing store always passes persist_dip_pulse_store.connect's refusals; fails_when=a script calls sqlite3.connect directly; why_new=PR #91 shipped a write path that skipped the distribution-copy refusal and nothing caught it until ship; seam=none
    def test_sqlite_is_opened_only_through_the_openers(self):
        found = sqlite_open_violations(script_modules())
        self.assertNoProblems([sqlite_open_message(finding) for finding in found])

    # Value: protects=create_database cannot be used to write an existing store around persist's refusals; fails_when=the non-empty check goes; why_new=the opener is new; seam=none
    def test_create_database_refuses_a_file_with_data(self):
        import sqlite_open

        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "existing.sqlite"
            conn = sqlite_open.create_database(path)
            conn.execute("CREATE TABLE t (x)")
            conn.commit()
            conn.close()
            with self.assertRaises(FileExistsError):
                sqlite_open.create_database(path)
            empty = Path(scratch) / "empty.sqlite"
            empty.touch()
            sqlite_open.create_database(empty).close()


class AbsentVersusZeroRuleTests(RuleTestCase):
    # Value: protects=no new `or 0` lands in scripts/ and fixed ones leave the baseline; fails_when=an `or 0` is added, or one is removed while its baseline entry stays; why_new=checklist class 5 was prose only and 78 sites accumulated; seam=none
    def test_no_or_zero_beyond_the_baseline(self):
        baseline = Counter({
            (entry["file"], entry["function"], entry["expression"]): entry["count"]
            for entry in load_baseline()["or_zero"]["entries"]
        })
        findings = [finding for path in script_modules().values() for finding in or_zero_findings(path, parsed(path))]
        actual = counted_or_zero(findings)
        added = actual - baseline
        new = [or_zero_message(finding) for finding in findings if added[(finding.file, finding.function, finding.text)]]
        stale = [
            f"tests/code_rules_baseline.json lists `{expression}` in {file} {function} {count} more time(s) than the "
            "code has it: lower or remove the entry (the baseline only shrinks; after renaming a function, move its "
            "entries to the new name)."
            for (file, function, expression), count in sorted((baseline - actual).items())
        ]
        self.assertNoProblems(new + stale)

    # Value: protects=no SQL comparison with a bound value on a nullable store column lands without a stated reason; fails_when=`col = ?` is added on a column that can be NULL, or a listed comparison disappears; why_new=NULL page_quadrant silently broke citations (9edb6a5) and nothing checks for the pattern; seam=none
    def test_no_unlisted_comparison_on_a_nullable_column(self):
        listed = {
            (entry["file"], entry["function"], entry["comparison"]): entry["reason"]
            for entry in load_baseline()["nullable_comparisons"]
        }
        for key, reason in listed.items():
            self.assertTrue(reason.strip(), f"{key} has no reason")
        schema = store_schema()
        findings = [
            finding
            for path in script_modules().values()
            for finding in nullable_comparison_findings(path, parsed(path), schema)
        ]
        seen = {(finding.file, finding.function, finding.text) for finding in findings}
        new = [nullable_comparison_message(finding) for finding in findings if (finding.file, finding.function, finding.text) not in listed]
        stale = [
            f"tests/code_rules_baseline.json lists `{comparison}` in {file} {function}, which the code no longer has: remove it."
            for (file, function, comparison) in sorted(set(listed) - seen)
        ]
        self.assertNoProblems(new + stale)


class ImportLayerRuleTests(RuleTestCase):
    # Value: protects=pages never import the store writer, the parser never imports store or pages, and only tools import the build CLI; fails_when=an import goes up a layer or sideways, or a new module is in no group; why_new=module boundaries were convention only; seam=none
    def test_imports_follow_the_layers(self):
        modules = script_modules()
        self.assertNoProblems(layer_violations(import_graph(modules), modules))

    # Value: protects=GROUPS names only modules that exist, so the map cannot rot; fails_when=a module is renamed or deleted and GROUPS keeps the old name; why_new=the map is new; seam=none
    def test_groups_name_only_existing_modules(self):
        modules = set(script_modules())
        listed = {member for members, _ in GROUPS.values() for member in members}
        self.assertEqual(set(), listed - modules)
        self.assertEqual(set(GROUPS), {group for layer in LAYERS for group in layer})

    # Value: protects=no new import cycle forms and a broken-up known cycle leaves KNOWN_CYCLES; fails_when=two modules start importing each other; why_new=the validate_dip_protocol/vote_links cycle went unnoticed; seam=none
    def test_no_import_cycle_beyond_the_known_ones(self):
        found = set(cycles(import_graph(script_modules())))
        self.assertNoProblems(
            [f"import cycle {sorted(cycle)}: move the shared code into a module both can import" for cycle in found - set(KNOWN_CYCLES)]
            + [f"KNOWN_CYCLES lists {sorted(cycle)}, which no longer exists: remove it" for cycle in set(KNOWN_CYCLES) - found]
        )


# ---------------------------------------------------------------------------
# The detectors on synthetic code, so a broken detector cannot pass by finding nothing
# ---------------------------------------------------------------------------


class DetectorTests(unittest.TestCase):
    # Value: protects=the connect detector sees every import spelling; fails_when=an alias form goes unseen; why_new=a detector that finds nothing passes silently; seam=parsed source, not files
    def test_connect_detector_sees_aliases(self):
        source = (
            "import sqlite3\nimport sqlite3 as db\nfrom sqlite3 import connect as c\n"
            "def a():\n    sqlite3.connect('x')\n"
            "class K:\n    def b(self):\n        db.connect('x')\n"
            "c('x')\n"
            "import sqlite3.dbapi2 as d2\nfrom sqlite3 import dbapi2, Connection\n"
            "sqlite3.Connection('x')\nd2.connect('x')\ndbapi2.connect('x')\nConnection('x')\nsqlite3.dbapi2.connect('x')\n"
        )
        self.assertEqual(
            [(5, "a"), (8, "K.b"), (9, "<module>")] + [(line, "<module>") for line in range(12, 17)],
            sorted(sqlite_connect_calls(ast.parse(source))),
        )

    # Value: protects=an ATTACH in SQL counts as opening a file; fails_when=the ATTACH pattern drifts; why_new=ATTACH can write an existing store from a create_database connection; seam=a real scripts/ module list with one probe file
    def test_attach_is_an_opening(self):
        with tempfile.TemporaryDirectory() as scratch:
            probe = Path(scratch) / "probe.py"
            probe.write_text("def f(conn, path):\n    conn.execute(\"ATTACH DATABASE ? AS s\", (path,))\n", encoding="utf-8")
            with mock.patch(f"{__name__}.relative", lambda path: path.name):
                found = sqlite_open_violations({"probe": probe})
        self.assertEqual([Finding("probe.py", 2, "f", "ATTACH")], found)

    # Value: protects=the or-0 detector flags int and float zero and leaves booleans and other defaults alone; fails_when=the zero test drifts; why_new=see above; seam=parsed source
    def test_or_zero_detector(self):
        source = "a = x or 0\nb = x or y or 0.0\nc = x or False\nd = x or 1\ne = 0 if x is None else x\n"
        found = [finding.text for finding in or_zero_findings(ROOT / "probe.py", ast.parse(source))]
        self.assertEqual(["x or 0", "x or y or 0.0"], found)

    # Value: protects=the comparison detector resolves tables and aliases, skips SET assignments and IS, and flags = and != on nullable columns only; fails_when=resolution or the clause test drifts; why_new=see above; seam=a hand-written schema
    def test_nullable_comparison_detector(self):
        schema = {"votes": {"id": False, "protocol_id": True}, "speeches": {"id": False, "mp_id": True}}
        cases = {
            "SELECT id FROM votes WHERE protocol_id = ?": ["votes.protocol_id = ?"],
            "SELECT 1 FROM votes v JOIN speeches s ON s.id = v.id WHERE s.mp_id != ? AND v.id = ?": ["speeches.mp_id != ?"],
            "UPDATE votes SET protocol_id = ? WHERE id = ?": [],
            "SELECT id FROM votes WHERE protocol_id IS ?": [],
            "SELECT id FROM votes WHERE id = ?": [],
            "SELECT id FROM unknown WHERE protocol_id = ?": [],
            "protocol_id = ?": [],
        }
        for sql, expected in cases.items():
            with self.subTest(sql=sql):
                self.assertEqual(expected, nullable_comparisons(sql, schema))
        # A WHERE fragment takes its aliases from the rest of its function; a SET list stays unknown.
        context = "SELECT s.id FROM speeches s JOIN votes v ON v.id = s.id WHERE {}"
        fragments = {
            "v.id = ? AND s.mp_id = ?": ["speeches.mp_id = ?"],
            "s.mp_id = ? AND v.id = ?": ["speeches.mp_id = ?"],
            "mp_id = ?, protocol_id = ?": [],
            "s.mp_id = ?": [],
        }
        for sql, expected in fragments.items():
            with self.subTest(fragment=sql):
                self.assertEqual(expected, nullable_comparisons(sql, schema, context))

    # Value: protects=the layer check flags upward and sideways imports and unplaced modules; fails_when=the layer order test drifts; why_new=see above; seam=a hand-built graph over real group names
    def test_layer_check(self):
        modules = {name: SCRIPTS / f"{name}.py" for name in ("derive", "persist_dip_pulse_store", "render_dip_pulse_html", "newcomer")}
        graph = {
            "derive": [("persist_dip_pulse_store", 3)],
            "render_dip_pulse_html": [("persist_dip_pulse_store", 4), ("derive", 5)],
            "persist_dip_pulse_store": [("derive", 6)],
            "newcomer": [],
        }
        problems = layer_violations(graph, modules)
        self.assertEqual(3, len(problems), problems)
        self.assertIn("newcomer is in no group", problems[0])
        self.assertIn("derive.py:3 imports persist_dip_pulse_store, which is in a group above it", problems[1])
        self.assertIn("render_dip_pulse_html.py:4 imports persist_dip_pulse_store, which is in a sibling group", problems[2])

    # Value: protects=the cycle finder reports a two-module cycle and nothing for a DAG; fails_when=Tarjan's bookkeeping breaks; why_new=see above; seam=a hand-built graph
    def test_cycle_finder(self):
        self.assertEqual([frozenset({"a", "b"})], cycles({"a": [("b", 1)], "b": [("a", 1)], "c": [("a", 1)]}))
        self.assertEqual([], cycles({"a": [("b", 1)], "b": [], "c": [("a", 1)]}))


if __name__ == "__main__":
    unittest.main()
