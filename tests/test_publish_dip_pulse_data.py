"""The release script, against a temporary git repository, a real fixture export
and a recorded command runner. No test calls gh, pushes, tags or uploads."""

from __future__ import annotations

import contextlib
import fnmatch
import hashlib
import io
import json
import shlex
import shutil
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import _support  # noqa: F401
import _daten_fixture
import build_dip_pulse_site as b
import persist_dip_pulse_store as pulse_store
import publish_dip_pulse_data as publish

VERSION = "2026.11.01"
TODAY = date(2026, 11, 1)
READINESS = {"votes": "ready", "aw-profiles": "unavailable", "mp-roster": "ready"}
BASE_URL = "https://data.example.org/poliwatch/"


def git(repo: Path, *args: str) -> str:
    import os

    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True, text=True).stdout.strip()


class Runner:
    """Runs git for real in the temporary repository, answers gh from a script, and records everything."""

    def __init__(self, gh_tags=(), gh_list_fails=False, gh_view_exists=(), gh_list_stdout=None, gh_create_fails=False, git_tag_fails=False, missing=(), remote_tags=(), ls_remote_fails=False, ls_remote_stdout=None):
        self.calls: list[list[str]] = []
        self.missing = tuple(missing)
        self.gh_tags = list(gh_tags)
        self.gh_list_fails = gh_list_fails
        self.gh_list_stdout = gh_list_stdout
        self.gh_create_fails = gh_create_fails
        self.git_tag_fails = git_tag_fails
        self.remote_tags = list(remote_tags)
        self.ls_remote_fails = ls_remote_fails
        self.ls_remote_stdout = ls_remote_stdout

    def __call__(self, command, **kwargs):
        self.calls.append(list(command))
        if command[0] in self.missing:
            raise FileNotFoundError(2, "No such file or directory", command[0])
        if command[0] == "gh":
            if command[1:3] == ["release", "list"]:
                if self.gh_list_fails:
                    return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 401")
                stdout = self.gh_list_stdout if self.gh_list_stdout is not None else json.dumps([{"tagName": tag} for tag in self.gh_tags])
                return SimpleNamespace(returncode=0, stdout=stdout, stderr="")
            if command[1:3] == ["release", "create"]:
                if self.gh_create_fails:
                    return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 422: Validation Failed")
                return SimpleNamespace(returncode=0, stdout="https://example.invalid/release", stderr="")
            raise AssertionError(f"unexpected gh call {command}")
        if command[:2] == ["git", "ls-remote"]:
            # The temporary repository has no remote; answer as origin would.
            if self.ls_remote_fails:
                return SimpleNamespace(returncode=128, stdout="", stderr="fatal: 'origin' does not appear to be a git repository")
            if self.ls_remote_stdout is not None:
                return SimpleNamespace(returncode=0, stdout=self.ls_remote_stdout, stderr="")
            asked = command[-1]
            lines = [f"{'0' * 40}\t{ref}" for ref in (f"refs/tags/{tag}" for tag in self.remote_tags) if fnmatch.fnmatchcase(ref, asked)]
            return SimpleNamespace(returncode=0, stdout="".join(line + "\n" for line in lines), stderr="")
        if self.git_tag_fails and command[:2] == ["git", "tag"]:
            return SimpleNamespace(returncode=128, stdout="", stderr="fatal: not a git repository")
        return subprocess.run(command, **{**kwargs, "capture_output": True, "text": True})

    def gh(self, *prefix):
        return [call for call in self.calls if call[0] == "gh" and call[1 : 1 + len(prefix)] == list(prefix)]


class ReleaseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(tempfile.mkdtemp()).resolve()
        cls.repo = cls.root / "repo"
        cls.repo.mkdir()
        git(cls.repo, "init", "-q")
        git(cls.repo, "config", "user.email", "t@example.org")
        git(cls.repo, "config", "user.name", "t")
        for relative in b.CODEBOOK_INPUT_FILES.values():
            target = cls.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(b.REPO_ROOT / relative, target)
        git(cls.repo, "add", "-A")
        git(cls.repo, "commit", "-qm", "inputs")
        cls.head = git(cls.repo, "rev-parse", "HEAD")
        db_path = cls.root / "pulse.sqlite"
        _daten_fixture.seed_store(db_path)
        conn = pulse_store.connect(db_path)
        try:
            # Three withheld Reden in 18/7 (ADR 0005), so the export carries real
            # withheld_units rows for the manifest's list to match.
            import test_withholding as tw

            parsed = b.dip.parse_protocol_xml(
                tw.sitting(tw.rede("R0"), *(tw.rede(f"R{i}", name, tw.REFUSED) for i, name in ((1, "Eins"), (2, "Zwei"), (3, "Drei")))),
                reviewed=[],
            )
            pulse_store.persist_report(conn, tw.report(parsed))
            _mps, lookup = b.collect_abgeordnete(conn)
        finally:
            conn.close()
        cls.exports = cls.root / "exports"
        with mock.patch.object(b.build_revision, "authored_inputs_problem", return_value=None):
            cls.manifest = b.export_distribution_data(
                db_path, cls.exports, mp_lookup=lookup, readiness=READINESS, catalog_count=2, dossier_count=2, tag=VERSION, commit=cls.head[:12], license_text="Quelldaten: DIP; eigene Auswertungen: CC BY 4.0"
            )
        (protocols,) = [entry["name"] for entry in cls.manifest["files"] if entry["name"].startswith("protocols-")]
        cls.stored = sorted((row["document_number"], row["date"]) for row in publish._csv_rows(cls.exports / cls.manifest["generation"] / protocols))

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.root, ignore_errors=True)

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp()).resolve()  # the script resolves its directories
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)
        self.out = self.work / "out"
        self.exports_copy = self.work / "exports"
        shutil.copytree(self.exports, self.exports_copy)
        self.runner = Runner()
        self.write_catalog()

    def write_catalog(self, extra=(), *, payload=None, path=None) -> Path:
        """The DIP catalog an online build leaves next to the exports directory:
        every stored sitting with its XML, a WP 17 sitting (before v1) and a
        Sonderdruck nobody stores, plus ``extra`` (number, date, has_xml)."""
        def protocol(number, day, xml=True):
            fundstelle = {"pdf_url": "https://dserver.bundestag.de/btp/x.pdf"}
            if xml:
                fundstelle["xml_url"] = f"https://dserver.bundestag.de/btp/{number.replace('/', '')}.xml"
            return {"dokumentnummer": number, "datum": day, "fundstelle": fundstelle}

        if payload is None:
            protocols = [protocol(number, day) for number, day in self.stored]
            protocols += [protocol("17/250", "2013-09-03"), {"dokumentnummer": "SDr 1981", "datum": "1981-01-01"}]
            protocols += [protocol(*row) for row in extra]
            payload = {"authoritative": True, "fetched_at": "2026-11-01T08:00:00Z", "protocols": protocols}
        path = path or self.work / "plenarprotokoll-catalog.json"
        path.write_text(json.dumps(payload) if not isinstance(payload, str) else payload, encoding="utf-8")
        return path

    def run_script(self, *args, runner=None, repo_root=None, exports=None):
        argv = ["--exports-dir", str(exports or self.exports_copy), "--output-dir", str(self.out), "--base-url", BASE_URL, *args]
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = publish.main(argv, repo_root=repo_root or self.repo, run=runner or self.runner, today=TODAY)
        return code, stdout.getvalue(), stderr.getvalue()

    def edit_manifest(self, **changes):
        path = self.exports_copy / "datenstand.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest.update(changes)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def assert_refused(self, code, stderr, *fragments):
        self.assertEqual(code, 1, stderr)
        for fragment in fragments:
            self.assertIn(fragment, stderr)
        self.assertFalse((self.out / f"data-{VERSION}").exists(), "a refused release leaves no directory")

    def assert_nothing_dangerous_ran(self):
        for call in self.runner.calls:
            self.assertNotEqual(call[:2], ["git", "push"], call)
            self.assertFalse(call[:2] == ["git", "tag"] and "--list" not in call and "-l" not in call, call)
            self.assertNotIn(call[:3], (["gh", "release", "create"], ["gh", "release", "upload"], ["gh", "release", "edit"]), call)
            self.assertNotEqual(call[:2], ["gh", "api"], call)


class DryRunTests(ReleaseTestCase):
    # Value: protects=a dry run writes the complete release directory and prints the exact commands without creating a release; fails_when=a file of the manifest, DATA.md, the changelog or SHA256SUMS is missing, a checksum is wrong, or any gh create/upload, git push or git tag runs; why_new=the release script did not exist; seam=main; no_claim=publish path
    def test_dry_run_writes_the_release_directory_and_runs_nothing_dangerous(self) -> None:
        code, stdout, stderr = self.run_script("--initial")
        self.assertEqual(code, 0, stderr)
        release = self.out / f"data-{VERSION}"
        generation = release / self.manifest["generation"]
        names = {path.relative_to(release).as_posix() for path in release.rglob("*") if path.is_file()}
        expected = {f"{self.manifest['generation']}/{file['name']}" for file in self.manifest["files"]}
        expected |= {"datenstand.json", "CHANGES.md", "changes.json", "SHA256SUMS"}
        self.assertEqual(names, expected)
        self.assertIn("DATA.md", {path.name for path in generation.iterdir()})
        self.assertEqual((release / "datenstand.json").read_bytes(), (self.exports_copy / "datenstand.json").read_bytes())
        sums = (release / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        self.assertEqual(sums, sorted(sums, key=lambda line: line.split("  ", 1)[1]))
        listed = {line.split("  ", 1)[1]: line.split("  ", 1)[0] for line in sums}
        self.assertEqual(set(listed), expected - {"SHA256SUMS"})
        for name, digest in listed.items():
            self.assertEqual(hashlib.sha256((release / name).read_bytes()).hexdigest(), digest, name)
        changes = json.loads((release / "changes.json").read_text(encoding="utf-8"))
        self.assertTrue(changes["initial_release"])
        self.assertEqual(changes["version"], VERSION)
        self.assertIn("Erste Veröffentlichung", (release / "CHANGES.md").read_text(encoding="utf-8"))
        self.assert_nothing_dangerous_ran()
        self.assertEqual(self.runner.gh(), [])
        self.assertIn("dry run", stdout)

    # Value: protects=the printed instructions name the version, tag, export format, the full site-build flags and the exact gh command with the manifest's commit as target; fails_when=the base URL is printed without --offline/--data-manifest, the target is HEAD or a short id, or the hosting and immutability caveats are missing; why_new=the site build must use this release's manifest or every link 404s; seam=main; no_claim=gh behaviour
    def test_dry_run_prints_site_flags_the_gh_command_and_its_caveats(self) -> None:
        code, stdout, _ = self.run_script("--initial")
        self.assertEqual(code, 0)
        release = self.out / f"data-{VERSION}"
        self.assertIn(f"version: {VERSION}", stdout)
        self.assertIn(f"tag: data-{VERSION}", stdout)
        self.assertIn(f"export format: {self.manifest['export_format']}", stdout)
        self.assertIn(f"--offline --data-manifest {release / 'datenstand.json'} --data-base-url {BASE_URL}", stdout)
        create = next(line for line in stdout.splitlines() if line.startswith("gh release create"))
        words = shlex.split(create)
        self.assertEqual(words[:4], ["gh", "release", "create", f"data-{VERSION}"])
        self.assertEqual(words[words.index("--target") + 1], self.head)
        self.assertEqual(words[words.index("--notes-file") + 1], str(release / "CHANGES.md"))
        uploaded = words[4 : words.index("--title")]
        self.assertIn(str(release / self.manifest["generation"] / self.manifest["files"][0]["name"]), uploaded)
        self.assertIn(str(release / "SHA256SUMS"), uploaded)
        self.assertIn("best effort", stdout)
        self.assertIn("flat", stdout)
        self.assertIn("LICENSE-DATA.md", stdout)

    # Value: protects=the next version is computed from existing data-* tags before the export, so the export can be built with --data-tag; fails_when=an existing tag is ignored or a non-release tag counts; why_new=the export has to be built with the version as its tag; seam=main --next-version; no_claim=remote tags
    def test_next_version_uses_the_local_release_tags(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(publish.main(["--next-version"], repo_root=self.repo, run=self.runner, today=TODAY), 0)
        self.assertEqual(stdout.getvalue().strip(), VERSION)
        git(self.repo, "tag", f"data-{VERSION}")
        git(self.repo, "tag", "v0.1")
        self.addCleanup(git, self.repo, "tag", "-d", f"data-{VERSION}")
        self.addCleanup(git, self.repo, "tag", "-d", "v0.1")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            publish.main(["--next-version"], repo_root=self.repo, run=self.runner, today=TODAY)
        self.assertEqual(stdout.getvalue().strip(), f"{VERSION}.2")


class WrapperTests(unittest.TestCase):
    # Value: protects=the shell wrapper reaches the Python script and passes its arguments through; fails_when=the wrapper is not executable or drops arguments; why_new=the TODO names scripts/publish_dip_pulse_data.sh; seam=the wrapper; no_claim=release logic
    def test_the_shell_wrapper_runs_the_script(self) -> None:
        import os
        import sys

        wrapper = b.REPO_ROOT / "scripts" / "publish_dip_pulse_data.sh"
        self.assertTrue(os.access(wrapper, os.X_OK))
        result = subprocess.run([str(wrapper), "--help"], env={**os.environ, "PYTHON": sys.executable}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--publish", result.stdout)
        self.assertIn("ADR 0003", result.stdout)


class RefusalTests(ReleaseTestCase):
    # Value: protects=a release is refused unless it is the initial one or says what it follows; fails_when=missing --initial/--previous-manifest is guessed as initial; why_new=release 2 from a fresh clone sees no local tags and would be labelled initial; seam=main; no_claim=changelog content
    def test_initial_or_previous_manifest_is_required(self) -> None:
        code, _, stderr = self.run_script()
        self.assert_refused(code, stderr, "--initial", "--previous-manifest")
        code, _, stderr = self.run_script("--initial", "--previous-manifest", str(self.exports_copy / "datenstand.json"))
        self.assert_refused(code, stderr, "not both")

    # Value: protects=a release whose export was not built with a release tag, a clean commit that exists, authored inputs of that commit and intact files is refused naming the problem; fails_when=a local export, dirty or unverified revision, unknown commit, inputs differing from the commit, a flipped byte, or an extra or missing file passes; why_new=the script is the release gate; seam=main; no_claim=every manifest rule (validate_manifest does that)
    def test_a_release_is_refused_unless_the_export_is_exactly_the_clean_commit(self) -> None:
        generation = self.exports_copy / self.manifest["generation"]
        sqlite_name = self.manifest["files"][0]["name"]

        def flip():
            data = bytearray((generation / sqlite_name).read_bytes())
            data[-1] ^= 1
            (generation / sqlite_name).write_bytes(bytes(data))

        cases = {
            "local tag": (lambda: self.edit_manifest(tag="local"), "release version"),
            "dirty revision": (lambda: self.edit_manifest(commit=self.head[:12] + "-dirty-01234567"), "clean"),
            "unverified revision": (lambda: self.edit_manifest(commit=self.head[:12] + "-unverified"), "clean"),
            "no revision": (lambda: self.edit_manifest(commit=None), "clean"),
            "unknown commit": (lambda: self.edit_manifest(commit="0123456789ab"), "not a commit of this repository"),
            "inputs differ from the commit": (lambda: self.edit_manifest(codebook_inputs={**self.manifest["codebook_inputs"], "docs/data-methods.md": "0" * 64}), "docs/data-methods.md"),
            "flipped byte": (flip, "sha256"),
            "extra file": (lambda: (generation / "extra.txt").write_text("x"), "extra.txt"),
            "missing file": (lambda: (generation / self.manifest["files"][-1]["name"]).unlink(), self.manifest["files"][-1]["name"]),
            "unusable manifest": (lambda: self.edit_manifest(files=[]), "not a usable"),
            "no Stammdaten": (lambda: self.edit_manifest(stammdaten=None), "MdB-Stammdaten"),
        }
        for label, (tamper, fragment) in cases.items():
            with self.subTest(label):
                shutil.rmtree(self.exports_copy)
                shutil.copytree(self.exports, self.exports_copy)
                tamper()
                code, _, stderr = self.run_script("--initial")
                self.assert_refused(code, stderr, fragment)
        self.assert_nothing_dangerous_ran()

    # Value: protects=a version that already exists as a tag is never reused, and an existing output directory is never overwritten; fails_when=an existing local data-<version> tag or output directory is accepted; why_new=releases are immutable; seam=main; no_claim=remote tags (see the publish tests)
    def test_an_existing_tag_or_output_directory_is_refused(self) -> None:
        git(self.repo, "tag", f"data-{VERSION}")
        try:
            code, _, stderr = self.run_script("--initial")
            self.assert_refused(code, stderr, f"data-{VERSION}", "already exists")
        finally:
            git(self.repo, "tag", "-d", f"data-{VERSION}")
        release = self.out / f"data-{VERSION}"
        release.mkdir(parents=True)
        (release / "x").write_text("x")
        code, _, stderr = self.run_script("--initial")
        self.assertEqual(code, 1)
        self.assertIn("already exists and differs from this release", stderr)
        self.assertIn("remove it or use a fresh --output-dir", stderr)
        self.assertEqual([path.name for path in release.iterdir()], ["x"], "an existing release directory is left untouched")
        self.assertEqual([path.name for path in self.out.iterdir()], [f"data-{VERSION}"], "no staging directory is left behind")

    # Value: protects=--initial is refused while data releases exist locally; fails_when=a clone with release tags can label a release initial; why_new=the initial flag is explicit but must still be true; seam=main; no_claim=remote releases (publish tests)
    def test_initial_is_refused_when_release_tags_exist(self) -> None:
        git(self.repo, "tag", "data-2026.10.01")
        try:
            code, _, stderr = self.run_script("--initial")
        finally:
            git(self.repo, "tag", "-d", "data-2026.10.01")
        self.assert_refused(code, stderr, "--initial", "2026.10.01")


    # Value: protects=missing arguments, a bad base URL, an unreadable manifest or previous manifest, and a failing git tag listing each refuse with exit 1 and one message, leaving no release directory and running no gh call; fails_when=any of them is read as an empty value, raises a traceback, or lets the release continue; why_new=the existing refusals cover the export's content, not the script's own inputs; seam=main (git tag via a recorded runner); no_claim=message wording beyond the quoted fragment
    def test_unusable_script_inputs_are_refused_cleanly(self) -> None:
        manifest_path = self.exports_copy / "datenstand.json"
        previous_missing = str(self.work / "no-such-previous.json")
        garbage = self.work / "garbage.json"
        garbage.write_text("{nope", encoding="utf-8")
        not_an_object = self.work / "list.json"
        not_an_object.write_text("[1, 2]", encoding="utf-8")
        # Item 10a: JSON null read as None labelled a follow-up release the first one.
        null_previous = self.work / "null.json"
        null_previous.write_text("null", encoding="utf-8")
        number_previous = self.work / "number.json"
        number_previous.write_text("7", encoding="utf-8")
        # Ship findings item 15: an integer past 4300 digits or a deep nesting ended in a traceback.
        huge_int_previous = self.work / "huge-int.json"
        huge_int_previous.write_text('{"tag": ' + "9" * 5000 + "}", encoding="utf-8")
        deep_previous = self.work / "deep.json"
        deep_previous.write_text("[" * 100_000, encoding="utf-8")
        shapeless_previous = self.work / "shapeless.json"
        shapeless_previous.write_text(json.dumps({"tag": "2026.10.01", "protocols": [], "votes": {"count": 1}}), encoding="utf-8")

        def directory_in_place_of_a_file() -> None:
            listed = json.loads(manifest_path.read_text(encoding="utf-8"))
            target = self.exports_copy / listed["generation"] / listed["files"][0]["name"]
            target.unlink()
            target.mkdir()

        cases = [
            ("missing --exports-dir", lambda: None, ["--initial"], "--exports-dir and --output-dir are required", None, True),
            ("unsupported base-url scheme", lambda: None, ["--initial", "--base-url", "ftp://host/x/"], "unsupported scheme", None, False),
            ("manifest absent", manifest_path.unlink, ["--initial"], "cannot read manifest", None, False),
            ("manifest not JSON", lambda: manifest_path.write_text("{nope", encoding="utf-8"), ["--initial"], "cannot read manifest", None, False),
            ("previous manifest absent", lambda: None, ["--previous-manifest", previous_missing], "cannot read previous manifest", None, False),
            ("previous manifest not JSON", lambda: None, ["--previous-manifest", str(garbage)], "cannot read previous manifest", None, False),
            ("manifest with an integer past 4300 digits", lambda: manifest_path.write_text('{"total_rows": ' + "9" * 5000 + "}", encoding="utf-8"), ["--initial"], "cannot read manifest", None, False),
            ("previous manifest with an integer past 4300 digits", lambda: None, ["--previous-manifest", str(huge_int_previous)], "cannot read previous manifest", None, False),
            ("previous manifest nested too deep", lambda: None, ["--previous-manifest", str(deep_previous)], "cannot read previous manifest", None, False),
            ("git tag listing fails", lambda: None, ["--initial"], "git tag --list failed", Runner(git_tag_fails=True), False),
            # /ship review 2026-10-31: these three ended in a traceback.
            ("previous manifest not an object", lambda: None, ["--previous-manifest", str(not_an_object)], "previous manifest", None, False),
            ("previous manifest null", lambda: None, ["--previous-manifest", str(null_previous)], "is not a datenstand.json (a JSON object)", None, False),
            ("previous manifest a number", lambda: None, ["--previous-manifest", str(number_previous)], "is not a datenstand.json (a JSON object)", None, False),
            ("previous manifest without the changelog fields", lambda: None, ["--previous-manifest", str(shapeless_previous)], "missing export_format", None, False),
            ("a directory where a listed file belongs", directory_in_place_of_a_file, ["--initial"], "is not a regular file", None, False),
            ("git not installed", lambda: None, ["--initial"], "git", Runner(missing=("git",)), False),
        ]
        for label, tamper, extra, fragment, runner, no_dirs in cases:
            with self.subTest(label):
                shutil.rmtree(self.exports_copy)
                shutil.copytree(self.exports, self.exports_copy)
                shutil.rmtree(self.out, ignore_errors=True)
                tamper()
                runner = runner or Runner()
                argv = list(extra) if no_dirs else ["--exports-dir", str(self.exports_copy), "--output-dir", str(self.out), *extra]
                if not no_dirs and "--base-url" not in extra:
                    argv += ["--base-url", BASE_URL]
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    code = publish.main(argv, repo_root=self.repo, run=runner, today=TODAY)
                err = stderr.getvalue()
                self.assert_refused(code, err, fragment)
                self.assertTrue(err.startswith("error: ") and "error: error:" not in err, err)
                self.assertEqual(runner.gh(), [])

    # Value: protects=a release build that fails part-way (here: writing CHANGES.md) exits 1 with one "error:" line, leaves no .building-* staging directory and no data-<version> directory, and the same command succeeds afterwards; fails_when=the staging directory or a half-written release stays behind, the OS error escapes as a traceback, or blocks the retry as "already exists"; why_new=build_release_directory's rollback was never triggered; seam=main with release_changes.render_markdown failing; no_claim=other failure points or a killed process
    def test_a_failed_release_build_leaves_nothing_behind(self) -> None:
        stderr = io.StringIO()
        with mock.patch.object(publish.release_changes, "render_markdown", side_effect=OSError("disk full")):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
                code = publish.main(["--exports-dir", str(self.exports_copy), "--output-dir", str(self.out), "--initial"], repo_root=self.repo, run=self.runner, today=TODAY)
        self.assertEqual(code, 1)
        self.assertTrue(stderr.getvalue().startswith("error: ") and "disk full" in stderr.getvalue(), stderr.getvalue())
        self.assertEqual(list(self.out.iterdir()), [])
        code, _, stderr = self.run_script("--initial")
        self.assertEqual(code, 0, stderr)
        self.assertEqual([path.name for path in self.out.iterdir()], [f"data-{VERSION}"])


    # Value: protects=an export file or datenstand.json replaced after verify_export checked it never reaches the release directory: the staging copy is checked against the verified manifest bytes and every file's size and sha256 before the rename; fails_when=build_release_directory re-reads and links whatever the export holds by then (release item 5, TOCTOU); why_new=release item 5; seam=main with verify_export wrapped to swap a file after it returns; no_claim=a swap during the final rename
    def test_a_file_swapped_after_verification_is_refused_before_the_rename(self) -> None:
        real_verify = publish.verify_export

        def swap_manifest(exports_dir: Path) -> None:
            path = exports_dir / "datenstand.json"
            path.write_text(path.read_text(encoding="utf-8").replace('"total_rows":', '"total_rows" :', 1), encoding="utf-8")

        def swap_data_md(exports_dir: Path) -> None:
            target = exports_dir / self.manifest["generation"] / "DATA.md"
            content = target.read_bytes() + b"\nnachtraeglich\n"
            target.unlink()  # a new file, as an export that is replaced writes it
            target.write_bytes(content)

        for label, swap, fragment in (
            ("datenstand.json", swap_manifest, "datenstand.json changed after it was verified"),
            ("a generation file", swap_data_md, "DATA.md changed after it was verified"),
        ):
            with self.subTest(label):
                shutil.rmtree(self.exports_copy)
                shutil.copytree(self.exports, self.exports_copy)
                shutil.rmtree(self.out, ignore_errors=True)

                def verify_then_swap(exports_dir, repo_root, swap=swap):
                    result = real_verify(exports_dir, repo_root)
                    swap(exports_dir)
                    return result

                with mock.patch.object(publish, "verify_export", side_effect=verify_then_swap):
                    code, _, stderr = self.run_script("--initial")
                self.assert_refused(code, stderr, fragment, "export it again")
                self.assertEqual(list(self.out.iterdir()), [], "no staging directory is left behind")

    # Value: protects=relative --output-dir/--exports-dir run from outside the repository reach gh as absolute paths, and an output path with "#" is refused before anything is written; fails_when=gh (run with cwd=repo_root) is handed a relative asset path that resolves elsewhere, or "#" splits a path into an asset label; why_new=release item 10b (P1), reachable once --publish opens; seam=main from another cwd; no_claim=gh's own path handling (mocked)
    def test_relative_directories_reach_gh_as_absolute_paths_and_a_hash_is_refused(self) -> None:
        import os

        previous_cwd = os.getcwd()
        os.chdir(self.work)
        self.addCleanup(os.chdir, previous_cwd)
        argv = ["--exports-dir", "exports", "--output-dir", "out", "--base-url", BASE_URL, "--initial"]
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = publish.main(argv, repo_root=self.repo, run=self.runner, today=TODAY)
        self.assertEqual(code, 0, stderr.getvalue())
        create = shlex.split(next(line for line in stdout.getvalue().splitlines() if line.startswith("gh release create")))
        paths = create[4 : create.index("--title")] + [create[create.index("--notes-file") + 1]]
        release = (self.work / "out" / f"data-{VERSION}").resolve()
        for path in paths:
            self.assertTrue(Path(path).is_absolute(), path)
            self.assertTrue(Path(path).is_relative_to(release), path)
        hashed = self.work / "rel#1"
        argv = ["--exports-dir", str(self.exports_copy), "--output-dir", str(hashed), "--base-url", BASE_URL, "--initial"]
        stderr = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            code = publish.main(argv, repo_root=self.repo, run=Runner(), today=TODAY)
        self.assertEqual(code, 1)
        self.assertIn("'#'", stderr.getvalue())
        self.assertFalse(hashed.exists())


class LineEndingTests(unittest.TestCase):
    # Value: protects=a core.autocrlf=true checkout (CRLF working tree, LF commit) hashes its authored inputs exactly as the release script hashes the committed blobs; fails_when=the exporter hashes CRLF bytes, so a clean checkout builds an export the release script refuses as "differs from commit"; why_new=release item 10d (P1); seam=_read_codebook_inputs vs build_revision.blob_sha256; no_claim=other git filters (eol attributes, smudge)
    def test_autocrlf_checkout_hashes_the_inputs_like_the_committed_blobs(self) -> None:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        repo = root / "repo"
        repo.mkdir()
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "t@example.org")
        git(repo, "config", "user.name", "t")
        git(repo, "config", "core.autocrlf", "true")
        for relative in b.CODEBOOK_INPUT_FILES.values():
            target = repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(b.REPO_ROOT / relative, target)
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "inputs")
        for relative in b.CODEBOOK_INPUT_FILES.values():
            (repo / relative).unlink()
        git(repo, "checkout", "--", ".")
        head = git(repo, "rev-parse", "HEAD")
        some = repo / b.CODEBOOK_INPUT_FILES["methods"]
        self.assertIn(b"\r\n", some.read_bytes(), "the checkout must hold CRLF for this test to mean anything")
        with mock.patch.object(b, "REPO_ROOT", repo):
            inputs = b._read_codebook_inputs()
        self.assertEqual(inputs.sha256, {relative: b.build_revision.blob_sha256(repo, head, relative) for relative in b.CODEBOOK_INPUT_FILES.values()})
        self.assertNotIn("\r", inputs.methods)


class PublishTests(ReleaseTestCase):
    # Value: protects=a release refuses an export whose manifest lists no LICENSE-DATA.md, an empty one, or one that is not the file the manifest commit holds, before any gh call and before writing anything; fails_when=a release can be created without the data licence, with an empty one (deferred item 6), or with bytes that differ from the commit; why_new=the licence file moved from a working-tree copy into every export (O3); seam=main; no_claim=licence content
    def test_a_release_refuses_a_missing_empty_or_foreign_licence_file(self) -> None:
        manifest = json.loads((self.exports_copy / "datenstand.json").read_text(encoding="utf-8"))
        generation = self.exports_copy / manifest["generation"]
        (licence,) = [entry for entry in manifest["files"] if entry["kind"] == "license"]

        def drop_entry() -> None:
            (generation / "LICENSE-DATA.md").unlink()
            self.edit_manifest(files=[entry for entry in manifest["files"] if entry["kind"] != "license"])

        def rewrite(content: bytes) -> None:
            (generation / "LICENSE-DATA.md").write_bytes(content)
            self.edit_manifest(files=[
                {**entry, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()} if entry is licence else entry
                for entry in manifest["files"]
            ])

        cases = [
            ("not listed", drop_entry, "license needs exactly one typed LICENSE-DATA.md"),
            ("empty", lambda: rewrite(b""), "is empty or not the LICENSE-DATA.md of commit"),
            ("not the commit's", lambda: rewrite(b"# Andere Lizenz\n\n## Short string\n\n> frei\n"), "is empty or not the LICENSE-DATA.md of commit"),
        ]
        for label, tamper, fragment in cases:
            with self.subTest(label):
                shutil.rmtree(self.exports_copy)
                shutil.copytree(self.exports, self.exports_copy)
                runner = Runner()
                tamper()
                code, _, stderr = self.run_script("--initial", "--publish", runner=runner)
                self.assert_refused(code, stderr, fragment)
                self.assertFalse(self.out.exists())
                self.assertEqual(runner.gh("release", "create"), [])

    # Value: protects=the release's LICENSE-DATA.md is the export's (the bytes the manifest commit holds), not a copy of the working tree; fails_when=an edited, uncommitted LICENSE-DATA.md in the checkout reaches the release (deferred item 6); why_new=the release script copied the file from the repository root; seam=main; no_claim=the export's own copy (tested in test_daten_export)
    def test_the_release_licence_comes_from_the_export_not_the_working_tree(self) -> None:
        repo = self.work / "edited"
        shutil.copytree(self.repo, repo)
        (repo / "LICENSE-DATA.md").write_text("# Uncommitted edit\n", encoding="utf-8")
        code, _, stderr = self.run_script("--initial", "--publish", repo_root=repo)
        self.assertEqual(code, 0, stderr)
        release = self.out / f"data-{VERSION}"
        self.assertEqual([path.relative_to(release).as_posix() for path in release.rglob("LICENSE-DATA.md")], [f"{self.manifest['generation']}/LICENSE-DATA.md"])
        self.assertEqual((release / self.manifest["generation"] / "LICENSE-DATA.md").read_bytes(), (b.REPO_ROOT / "LICENSE-DATA.md").read_bytes().replace(b"\r\n", b"\n"))

    # Value: protects=with the licence file present --publish checks the remote for existing releases, ships LICENSE-DATA.md in the directory and in SHA256SUMS, and calls gh release create exactly once with exact arguments; fails_when=the licence file is not shipped or checksummed, the gh check is skipped, or the create arguments differ; why_new=the one real-upload path; seam=main with a recorded gh; no_claim=gh's behaviour (mocked)
    def test_publish_with_the_licence_file_creates_the_release_through_gh(self) -> None:
        code, stdout, stderr = self.run_script("--initial", "--publish")
        self.assertEqual(code, 0, stderr)
        release = self.out / f"data-{VERSION}"
        self.assertTrue((release / self.manifest["generation"] / "LICENSE-DATA.md").is_file())
        self.assertIn(f"{self.manifest['generation']}/LICENSE-DATA.md", (release / "SHA256SUMS").read_text(encoding="utf-8"))
        self.assertEqual(len(self.runner.gh("release", "list")), 1)
        (create,) = self.runner.gh("release", "create")
        files = sorted(
            [str(path) for path in release.rglob("*") if path.is_file()],
            key=lambda value: (Path(value).name,),
        )
        self.assertEqual(create[:4], ["gh", "release", "create", f"data-{VERSION}"])
        self.assertEqual(sorted(create[4 : create.index("--title")]), sorted(files))
        tail = create[create.index("--title") :]
        self.assertEqual(tail, ["--title", f"Daten {VERSION}", "--notes-file", str(release / "CHANGES.md"), "--target", self.head])
        self.assertNotIn("dry run", stdout)
        for call in self.runner.calls:
            self.assertNotEqual(call[:2], ["git", "push"])

    # Value: protects=a failing gh release create exits 1 with gh's message and names the recovery step (check origin for a left-behind tag or release), keeps the finished directory, and the retry publishes that same directory; fails_when=the failure is reported as success, the directory is deleted or half-written, the message leaves the reader at a dead end, or the retry is refused as "already exists" (release item 1); why_new=the retry used to be refused with no way forward; seam=main with a recorded gh; no_claim=gh's real failure modes (mocked)
    def test_a_failed_gh_create_names_the_recovery_and_the_retry_reuses_the_directory(self) -> None:
        runner = Runner(gh_create_fails=True)
        code, stdout, stderr = self.run_script("--initial", "--publish", runner=runner)
        self.assertEqual(code, 1)
        self.assertIn("gh release create failed", stderr)
        self.assertIn("HTTP 422", stderr)
        self.assertIn(f"git ls-remote --tags origin refs/tags/data-{VERSION}", stderr)
        self.assertIn(f"gh release view data-{VERSION}", stderr)
        self.assertIn(f"git tag -d data-{VERSION}", stderr)
        self.assertNotIn("published:", stdout)
        release = self.out / f"data-{VERSION}"
        self.assertIn(str(release), stderr)
        self.assertTrue((release / "SHA256SUMS").is_file() and (release / self.manifest["generation"] / "LICENSE-DATA.md").is_file())
        self.assertEqual(len(runner.gh("release", "create")), 1)
        before = {path.relative_to(release).as_posix(): path.read_bytes() for path in release.rglob("*") if path.is_file()}
        retry = Runner()
        code, stdout, stderr = self.run_script("--initial", "--publish", runner=retry)
        self.assertEqual(code, 0, stderr)
        self.assertIn("published:", stdout)
        self.assertEqual({path.relative_to(release).as_posix(): path.read_bytes() for path in release.rglob("*") if path.is_file()}, before)
        (create,) = retry.gh("release", "create")
        self.assertEqual(sorted(create[4 : create.index("--title")]), sorted(str(release / name) for name in before))
        self.assertEqual([path.name for path in self.out.iterdir()], [f"data-{VERSION}"], "no staging directory is left behind")

    # Value: protects=the documented flow, a dry run followed by --publish into the same --output-dir, publishes the rehearsed directory, while a dry run from another day (a different changes.json) is refused naming the differing file and the recovery; fails_when=--publish refuses the rehearsed directory as "already exists" (release item 1), or silently publishes a directory whose files differ from this run's release; why_new=release item 1; seam=main with a recorded gh; no_claim=gh behaviour (mocked)
    def test_publish_after_a_dry_run_reuses_a_matching_directory_only(self) -> None:
        code, _, stderr = self.run_script("--initial")
        self.assertEqual(code, 0, stderr)
        code, stdout, stderr = self.run_script("--initial", "--publish")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(len(self.runner.gh("release", "create")), 1)
        self.assertIn("reusing", stdout)
        shutil.rmtree(self.out)
        code, _, stderr = self.run_script("--initial")
        self.assertEqual(code, 0, stderr)
        release = self.out / f"data-{VERSION}"
        before = sorted(path.relative_to(release).as_posix() for path in release.rglob("*") if path.is_file())
        runner = Runner()
        stderr = io.StringIO()
        argv = ["--exports-dir", str(self.exports_copy), "--output-dir", str(self.out), "--base-url", BASE_URL, "--initial", "--publish"]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            code = publish.main(argv, repo_root=self.repo, run=runner, today=date(2026, 11, 2))
        self.assertEqual(code, 1)
        self.assertIn("already exists and differs from this release", stderr.getvalue())
        self.assertIn("changes.json", stderr.getvalue())
        self.assertIn("remove it or use a fresh --output-dir", stderr.getvalue())
        self.assertEqual(runner.gh("release", "create"), [])
        self.assertEqual(sorted(path.relative_to(release).as_posix() for path in release.rglob("*") if path.is_file()), before)
        self.assertEqual([path.name for path in self.out.iterdir()], [f"data-{VERSION}"])

    # Value: protects=--publish asks origin for the release tag before gh and refuses when it already exists or origin cannot be asked; fails_when=gh release create attaches to a left-behind remote tag and ignores --target (release item 2), or a failed ls-remote reads as "no tag"; why_new=release item 2; seam=main with a recorded git ls-remote and gh; no_claim=the real remote (mocked)
    def test_publish_refuses_a_tag_that_already_exists_on_origin(self) -> None:
        for label, runner, fragments in (
            ("tag on origin", Runner(remote_tags=[f"data-{VERSION}"]), ("already exists on origin", "ignores --target", f"git push origin :refs/tags/data-{VERSION}")),
            ("origin cannot be asked", Runner(ls_remote_fails=True), ("git ls-remote", "not publishing blind")),
        ):
            with self.subTest(label):
                code, _, stderr = self.run_script("--initial", "--publish", runner=runner)
                self.assert_refused(code, stderr, *fragments)
                self.assertEqual(runner.gh("release", "create"), [])
                shutil.rmtree(self.out, ignore_errors=True)
        runner = Runner(remote_tags=["data-2026.10.01"])
        code, _, stderr = self.run_script("--initial", "--publish", runner=runner)
        self.assertEqual(code, 0, stderr)
        ls_remote = [i for i, call in enumerate(runner.calls) if call[:2] == ["git", "ls-remote"]]
        create = [i for i, call in enumerate(runner.calls) if call[:3] == ["gh", "release", "create"]]
        self.assertEqual(len(ls_remote), 1)
        self.assertEqual(runner.calls[ls_remote[0]][-1], f"refs/tags/data-{VERSION}")
        self.assertLess(ls_remote[0], create[0])
        self.assertEqual([call for call in self.runner.calls if call[:2] == ["git", "ls-remote"]], [], "a dry run asks no remote")

    # Value: protects=only a tag whose ref is exactly refs/tags/<tag> (or its peeled ^{} line) counts as already on origin; fails_when=ls-remote lines for other refs are read as the tag (substring match refuses a good release) or the peeled line of an annotated tag is missed; why_new=the origin test's mock only ever answers with the asked ref; seam=main with a scripted git ls-remote; no_claim=the real remote (scripted output)
    def test_origin_tag_match_is_exact_and_sees_peeled_annotated_tags(self) -> None:
        tag = f"refs/tags/data-{VERSION}"
        decoys = f"{'1' * 40}\trefs/tags/data-{VERSION}-rc\n{'2' * 40}\trefs/tags/old/data-{VERSION}\n"
        runner = Runner(ls_remote_stdout=decoys)
        code, _, stderr = self.run_script("--initial", "--publish", runner=runner)
        self.assertEqual(code, 0, stderr)
        shutil.rmtree(self.out)
        runner = Runner(ls_remote_stdout=decoys + f"{'3' * 40}\t{tag}^{{}}\n")
        code, _, stderr = self.run_script("--initial", "--publish", runner=runner)
        self.assert_refused(code, stderr, "already exists on origin")
        self.assertEqual(runner.gh("release", "create"), [])

    # Value: protects=an existing release directory is reused only when every built file is present as a regular file with equal bytes; fails_when=a missing file, a symlink standing in for a file, or a plain file in place of the directory is accepted as the rehearsed release; why_new=the existing refusal tests cover an extra file and different changes.json only; seam=main; no_claim=more than 6 differences (message truncation)
    def test_an_existing_directory_with_a_missing_file_a_symlink_or_no_directory_is_refused(self) -> None:
        code, _, stderr = self.run_script("--initial")
        self.assertEqual(code, 0, stderr)
        release = self.out / f"data-{VERSION}"
        original = (release / "CHANGES.md").read_bytes()
        (release / "CHANGES.md").unlink()
        mutations = {"missing CHANGES.md": "missing CHANGES.md"}
        for label, fragment in mutations.items():
            with self.subTest(label):
                code, _, stderr = self.run_script("--initial", "--publish")
                self.assertEqual(code, 1, stderr)
                self.assertIn("already exists and differs from this release", stderr)
                self.assertIn(fragment, stderr)
        (release / "CHANGES.md").write_bytes(original)
        (release / "SHA256SUMS").unlink()
        (release / "SHA256SUMS").symlink_to(release / "changes.json")
        with self.subTest("symlinked SHA256SUMS"):
            code, _, stderr = self.run_script("--initial", "--publish")
            self.assertEqual(code, 1, stderr)
            self.assertIn("different SHA256SUMS", stderr)
        shutil.rmtree(release)
        release.write_text("not a directory", encoding="utf-8")
        code, _, stderr = self.run_script("--initial", "--publish")
        self.assertEqual(code, 1, stderr)
        self.assertIn("not a directory", stderr)
        self.assertEqual(release.read_text(encoding="utf-8"), "not a directory")

    # Value: protects=--publish refuses an export built without a licence string even though it carries LICENSE-DATA.md; fails_when=an empty manifest licence passes; why_new=the project documentation promises the publish step refuses on an empty string; seam=main; no_claim=string content
    def test_publish_refuses_an_export_without_a_licence_string(self) -> None:
        self.edit_manifest(license="")
        code, _, stderr = self.run_script("--initial", "--publish")
        self.assert_refused(code, stderr, "licence string")
        self.assertEqual(self.runner.gh("release", "create"), [])

    # Value: protects=--publish refuses when gh already lists the version, lists any release for --initial, or cannot be asked; fails_when=the remote check is skipped or its failure is read as "no releases"; why_new=local tags miss releases of a clone that has not fetched; seam=main with a recorded gh; no_claim=gh behaviour (mocked)
    def test_publish_checks_the_remote_for_existing_releases(self) -> None:
        cases = {
            "version exists": (Runner(gh_tags=[f"data-{VERSION}"]), "already exists"),
            "initial but releases exist": (Runner(gh_tags=["data-2026.10.01"]), "--initial"),
            "gh fails": (Runner(gh_list_fails=True), "gh release list"),
            "gh output unreadable": (Runner(gh_list_stdout="<html>rate limited</html>"), "unreadable"),
            "gh output not a list of releases": (Runner(gh_list_stdout='{"tagName": "data-2026.10.01"}'), "unreadable"),
        }
        for label, (runner, fragment) in cases.items():
            with self.subTest(label):
                self.runner = runner
                code, _, stderr = self.run_script("--initial", "--publish", runner=runner)
                self.assert_refused(code, stderr, fragment)
                self.assertEqual(runner.gh("release", "create"), [])
                shutil.rmtree(self.out, ignore_errors=True)

    def set_exclusions(self, excluded) -> None:
        manifest = json.loads((self.exports_copy / "datenstand.json").read_text(encoding="utf-8"))
        self.edit_manifest(coverage={**manifest["coverage"], "excluded": excluded})

    # Value: protects=ADR 0005's bar: --publish refuses while any exclusion still reads awaiting_rule or awaiting_acquisition, the first release included (D6, owner 2026-11-14); fails_when=a release goes out with sittings on their way back; why_new=nothing read coverage.excluded[].reason outside the codebook; seam=main
    def test_publish_refuses_while_an_exclusion_awaits(self) -> None:
        final = [{"document_number": "18/20", "reason": "source_defect", "reason_detail": "Datei hält Sitzung 21."},
                 {"document_number": "18/90", "reason": "not_narrowable", "reason_detail": "x"}]
        waiting = [{"document_number": "18/62", "reason": "awaiting_rule", "reason_detail": "x"},
                   *({"document_number": f"18/{n}", "reason": "awaiting_acquisition", "reason_detail": "x"} for n in range(100, 113))]
        self.set_exclusions(final + waiting)
        code, _, stderr = self.run_script("--initial", "--publish")
        self.assert_refused(code, stderr, "--publish refused: 14 exclusions still await acquisition or a rule (ADR 0005",
                            "18/62, 18/100, 18/101", "18/110, …")
        self.assertEqual(self.runner.gh("release", "create"), [])
        # A dry run still builds the directory and says what --publish would do.
        code, stdout, stderr = self.run_script("--initial")
        self.assertEqual(code, 0, stderr)
        self.assertIn("--publish would refuse: 14 exclusions still await acquisition or a rule (ADR 0005", stdout)
        shutil.rmtree(self.out)
        self.set_exclusions(final)
        code, stdout, stderr = self.run_script("--initial", "--publish")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(len(self.runner.gh("release", "create")), 1)

    # Value: protects=an exclusion record the bar cannot read is refused, never read as none (class 9); fails_when=a missing or malformed coverage.excluded lets --publish through; why_new=D6; seam=main
    def test_an_unreadable_exclusion_record_is_refused(self) -> None:
        manifest = json.loads((self.exports_copy / "datenstand.json").read_text(encoding="utf-8"))
        coverage = {k: v for k, v in manifest["coverage"].items() if k != "excluded"}
        for label, edit in (
            ("absent", coverage),
            ("null", {**coverage, "excluded": None}),
            ("an entry without a reason", {**coverage, "excluded": [{"document_number": "18/20"}]}),
            ("an entry that is no object", {**coverage, "excluded": ["18/20"]}),
        ):
            with self.subTest(label):
                self.edit_manifest(coverage=edit)
                code, _, stderr = self.run_script("--initial", "--publish")
                self.assert_refused(code, stderr, "coverage.excluded")


class MissingSittingTests(ReleaseTestCase):
    """Owner decision 6 of docs/plans/t4-acquire.md: --publish refuses while a v1
    catalog sitting with XML is neither in the export nor on its exclusion record."""

    def set_exclusions(self, excluded) -> None:
        manifest = json.loads((self.exports_copy / "datenstand.json").read_text(encoding="utf-8"))
        self.edit_manifest(coverage={**manifest["coverage"], "excluded": excluded})

    # Value: protects=a v1 sitting DIP lists with XML that is neither stored nor excluded blocks --publish, named, while a dry run still builds and says so, and an exclusion record entry for it lifts the refusal; fails_when=a T4 run DIP stopped partway (update_coverage_exclusions dropped the sitting from the record without storing it) or a sitting DIP added after the build goes out unnoticed; why_new=run_release read coverage.excluded only; seam=main with the build's catalog file; no_claim=whether the catalog is current at release time (the release reads the one the build left)
    def test_publish_refuses_a_v1_sitting_neither_stored_nor_excluded(self) -> None:
        self.write_catalog([("21/107", "2026-11-11", True)])
        code, _, stderr = self.run_script("--initial", "--publish")
        self.assert_refused(code, stderr, "--publish refused: 1 v1 sitting DIP lists with XML is neither in the export nor on its exclusion record (21/107)")
        self.assertEqual(self.runner.gh("release", "create"), [])
        code, stdout, stderr = self.run_script("--initial")
        self.assertEqual(code, 0, stderr)
        self.assertIn("--publish would refuse: 1 v1 sitting DIP lists with XML is neither in the export nor on its exclusion record (21/107)", stdout)
        shutil.rmtree(self.out)
        self.set_exclusions([{"document_number": "21/107", "reason": "source_defect", "reason_detail": "XML leer."}])
        code, _, stderr = self.run_script("--initial", "--publish")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(len(self.runner.gh("release", "create")), 1)

    # Value: protects=the refusal names many missing sittings in sitting order and cuts the list after twelve; fails_when=a long list floods the message or sorts 21/9 after 21/10; why_new=new refusal; seam=main
    def test_many_missing_sittings_are_counted_and_shown_in_order(self) -> None:
        self.write_catalog([(f"21/{n}", "2026-10-01", True) for n in range(20, 4, -1)])
        code, _, stderr = self.run_script("--initial", "--publish")
        self.assert_refused(code, stderr, "16 v1 sittings DIP lists with XML are neither", "(21/5, 21/6, 21/7, 21/8, 21/9, 21/10,", "21/16, …)")

    # Value: protects=a sitting DIP lists without XML yet (incomplete_sitting_protocols' "waiting") and a sitting before WP 18 never block --publish; fails_when=the release waits for an XML DIP has not published or for sittings outside v1; why_new=new refusal; seam=main
    def test_a_sitting_without_xml_or_before_wp_18_is_not_refused(self) -> None:
        self.write_catalog([("21/108", "2026-11-12", False), ("17/251", "2013-09-04", True)])
        code, stdout, stderr = self.run_script("--initial", "--publish")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(len(self.runner.gh("release", "create")), 1)

    # Value: protects=a catalog entry that is not an object, or whose fundstelle is not an object, is skipped or read as "no XML" instead of crashing or blocking; fails_when=the isinstance guards in catalog_v1_sittings are dropped (AttributeError traceback on --publish); why_new=the other catalog tests carry only well-formed entries; seam=main
    def test_a_malformed_catalog_entry_is_skipped_not_a_crash(self) -> None:
        path = self.write_catalog([("21/108", "2026-11-12", False)])
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["protocols"] += ["21/109", None, {"dokumentnummer": "21/110", "datum": "2026-11-13", "fundstelle": "kein Objekt"}]
        self.write_catalog(payload=payload)
        code, _, stderr = self.run_script("--initial", "--publish")
        self.assertEqual(code, 0, stderr)
        self.assertEqual(len(self.runner.gh("release", "create")), 1)

    # Value: protects=a sitting DIP lists twice, once without XML and once with, counts as having XML and is named once; fails_when=the later duplicate overwrites the XML flag so the sitting is read as waiting, or it is listed twice; why_new=the other catalog tests list each sitting once; seam=main
    def test_a_sitting_listed_twice_counts_as_having_xml_once(self) -> None:
        self.write_catalog([("21/107", "2026-11-11", True), ("21/107", "2026-11-11", False)])
        code, _, stderr = self.run_script("--initial", "--publish")
        self.assert_refused(code, stderr, "1 v1 sitting DIP lists with XML is neither in the export nor on its exclusion record (21/107)")

    # Value: protects=a catalog the check cannot read, one not fetched in full, or one older than the export is never read as "nothing missing" (class 9); fails_when=a missing or narrowed catalog file lets --publish through; why_new=new input; seam=main
    def test_an_unreadable_partial_or_stale_catalog_is_refused(self) -> None:
        stale = {"authoritative": True, "protocols": [{"dokumentnummer": n, "datum": d, "fundstelle": {"xml_url": "x"}} for n, d in self.stored[1:]]}
        cases = (
            ("absent", None, "cannot read catalog"),
            ("not JSON", "{nope", "cannot read catalog"),
            ("null", "null", "not a complete DIP catalog"),
            ("not authoritative", {"authoritative": False, "protocols": []}, "not a complete DIP catalog"),
            ("protocols not a list", {"authoritative": True, "protocols": {}}, "not a complete DIP catalog"),
        )
        for label, payload, fragment in cases:
            with self.subTest(label):
                shutil.rmtree(self.out, ignore_errors=True)
                catalog = self.work / "plenarprotokoll-catalog.json"
                if payload is None:
                    catalog.unlink()
                else:
                    self.write_catalog(payload=payload)
                # Every run reads it, the dry run included: it is the release's input.
                code, _, stderr = self.run_script("--initial")
                self.assert_refused(code, stderr, fragment, "--catalog")
        self.write_catalog(payload=stale)
        code, _, stderr = self.run_script("--initial", "--publish")
        self.assert_refused(code, stderr, f"lacks 1 sitting the export holds ({self.stored[0][0]})", "older than the export")
        self.assertEqual(self.runner.gh("release", "create"), [])
        code, stdout, stderr = self.run_script("--initial")
        self.assertEqual(code, 0, stderr)
        self.assertIn("--publish would refuse: the catalog", stdout)

    # Value: protects=--catalog names the catalog file when it is not next to the exports directory, and the default location is then not read; fails_when=the flag is ignored; why_new=new flag; seam=main
    def test_the_catalog_flag_names_another_file(self) -> None:
        elsewhere = self.write_catalog([("21/107", "2026-11-11", True)], path=self.work / "elsewhere.json")
        (self.work / "plenarprotokoll-catalog.json").unlink()
        code, _, stderr = self.run_script("--initial", "--publish", "--catalog", str(elsewhere))
        self.assert_refused(code, stderr, "(21/107)")


class FollowUpReleaseTests(ReleaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        # The previous manifests below are release 2026.10.01's, so this clone and origin know that release.
        git(self.repo, "tag", "data-2026.10.01")
        self.addCleanup(git, self.repo, "tag", "-d", "data-2026.10.01")
        self.runner = Runner(remote_tags=["data-2026.10.01"])

    # Value: protects=--previous-manifest must be the latest release on origin (git ls-remote --tags, owner decision 2026-11-17), in a dry run too, and is refused when origin holds no release tag or cannot be asked; fails_when=an older previous manifest gives false deltas and can hide a schema change from the authored schema_changes guard (release item 4), a clone that has not fetched (or holds an unpushed tag) decides which release is latest, or a follow-up release is assembled against a release nobody published; why_new=release item 4 took the latest from local tags; seam=main with local tags and a recorded origin; no_claim=whether the previous manifest's bytes are the published asset's (item 12b)
    def test_the_previous_manifest_must_be_the_latest_release_on_origin(self) -> None:
        previous = self.work / "previous.json"
        previous.write_text(json.dumps({**self.manifest, "tag": "2026.10.01"}), encoding="utf-8")
        args = ("--previous-manifest", str(previous), "--changes", self.write_changes({"summary": "x"}))
        for label, runner in (
            ("dry run", Runner(remote_tags=["data-2026.10.01", "data-2026.10.20"])),
            ("--publish", Runner(remote_tags=["data-2026.10.01", "data-2026.10.20"], gh_tags=["data-2026.10.01"])),
        ):
            with self.subTest(label):
                extra = ("--publish",) if label == "--publish" else ()
                code, _, stderr = self.run_script(*args, *extra, runner=runner)
                self.assert_refused(code, stderr, "is release 2026.10.01, but the latest release on origin is 2026.10.20", "datenstand.json of 2026.10.20")
                self.assertEqual(runner.gh("release", "create"), [])
                self.assertIn(["git", "ls-remote", "--tags", "origin", "refs/tags/data-*"], runner.calls)
        # A local tag origin does not hold (not pushed, or a fetch from elsewhere) does not decide the latest release.
        git(self.repo, "tag", "data-2026.10.15")
        try:
            code, _, stderr = self.run_script(*args, runner=Runner(remote_tags=["data-2026.10.01"]))
        finally:
            git(self.repo, "tag", "-d", "data-2026.10.15")
        self.assertEqual(code, 0, stderr)
        shutil.rmtree(self.out)
        # A peeled annotated tag and a non-release tag on origin are read as one release and none.
        stdout = f"{'1' * 40}\trefs/tags/data-2026.10.01\n{'2' * 40}\trefs/tags/data-2026.10.01^{{}}\n{'3' * 40}\trefs/tags/data-latest\n"
        code, _, stderr = self.run_script(*args, runner=Runner(ls_remote_stdout=stdout))
        self.assertEqual(code, 0, stderr)
        shutil.rmtree(self.out)
        # The clone knows the release, origin does not: no release has been published.
        code, _, stderr = self.run_script(*args, runner=Runner())
        self.assert_refused(code, stderr, "origin holds no data release tag", "--initial")
        code, _, stderr = self.run_script(*args, runner=Runner(ls_remote_fails=True))
        self.assert_refused(code, stderr, "cannot ask origin for its release tags", "git ls-remote failed")

    # Value: protects=a follow-up --publish whose tag a failed gh run left on origin (no release behind it) is refused with remote_tag_exists' message naming how to delete the tag; fails_when=origin's tags count as existing releases, so the message falsely says the release exists and drops the recovery step; why_new=code review of the origin-tag change (owner decision 4b); seam=main with a recorded origin; no_claim=gh behaviour (mocked)
    def test_a_follow_up_tag_left_on_origin_names_its_recovery(self) -> None:
        previous = self.work / "previous.json"
        previous.write_text(json.dumps({**self.manifest, "tag": "2026.10.01"}), encoding="utf-8")
        runner = Runner(gh_tags=["data-2026.10.01"], remote_tags=["data-2026.10.01", f"data-{VERSION}"])
        code, _, stderr = self.run_script("--previous-manifest", str(previous), "--changes", self.write_changes({"summary": "x"}), "--publish", runner=runner)
        self.assert_refused(code, stderr, f"tag data-{VERSION} already exists on origin but has no release", f"git push origin :refs/tags/data-{VERSION}")
        self.assertNotIn("releases are immutable", stderr)
        self.assertEqual(runner.gh("release", "create"), [])

    # Value: protects=an export whose version is older than the latest known release is refused, local tag or gh release; fails_when=a stale export goes out after a newer release and its changelog is computed backwards from that release's manifest; why_new=code-review of release item 4 (the latest-release check assumed the export is newer); seam=main; no_claim=clock skew between machines
    def test_an_export_older_than_the_latest_release_is_refused(self) -> None:
        previous = self.work / "previous.json"
        previous.write_text(json.dumps({**self.manifest, "tag": "2026.11.05"}), encoding="utf-8")
        args = ("--previous-manifest", str(previous), "--changes", self.write_changes({"summary": "x"}))
        git(self.repo, "tag", "data-2026.11.05")
        try:
            code, _, stderr = self.run_script(*args)
        finally:
            git(self.repo, "tag", "-d", "data-2026.11.05")
        self.assert_refused(code, stderr, f"release {VERSION} is older than the latest known release 2026.11.05")
        runner = Runner(gh_tags=["data-2026.10.01", "data-2026.11.05"], remote_tags=["data-2026.10.01", "data-2026.11.05"])
        code, _, stderr = self.run_script(*args, "--publish", runner=runner)
        self.assert_refused(code, stderr, "older than the latest known release 2026.11.05")
        self.assertEqual(runner.gh("release", "create"), [])

    # Value: protects=a later release assembles its changelog from the previous manifest and the authored file and is refused without them; fails_when=a missing --changes passes, the previous version is not recorded, or the corrections do not reach changes.json and CHANGES.md; why_new=a researcher must be able to check a cited figure against the release before; seam=main; no_claim=changelog rules (tested in test_release_changes)
    def test_a_later_release_needs_and_uses_the_changes_file(self) -> None:
        previous = self.work / "previous.json"
        previous.write_text(json.dumps({**self.manifest, "tag": "2026.10.01", "protocols": {**self.manifest["protocols"], "count": 1}}), encoding="utf-8")
        code, _, stderr = self.run_script("--previous-manifest", str(previous))
        self.assert_refused(code, stderr, "changes file")
        changes = self.work / "changes-source.json"
        changes.write_text(
            json.dumps({"summary": "Zwei Sitzungen ergänzt.", "corrections": [{"table": "votes", "key": "v1", "column": "yes_count", "old": 1, "new": 2, "reason": "Endergebnis"}]}),
            encoding="utf-8",
        )
        # An integer past 4300 digits or a deep nesting in the changes file is refused, not a traceback.
        for label, text in (("huge integer", '{"summary": ' + "9" * 5000 + "}"), ("deep nesting", "[" * 100_000)):
            with self.subTest(label):
                broken = self.work / "broken-changes.json"
                broken.write_text(text, encoding="utf-8")
                code, _, stderr = self.run_script("--previous-manifest", str(previous), "--changes", str(broken))
                self.assert_refused(code, stderr, "is not valid JSON")
        code, _, stderr = self.run_script("--previous-manifest", str(previous), "--changes", str(changes))
        self.assertEqual(code, 0, stderr)
        release = self.out / f"data-{VERSION}"
        result = json.loads((release / "changes.json").read_text(encoding="utf-8"))
        self.assertEqual(result["previous_version"], "2026.10.01")
        self.assertEqual(result["corrections"][0]["new"], 2)
        self.assertEqual(result["coverage"]["protocols"]["old"], 1)
        self.assertIn("Endergebnis", (release / "CHANGES.md").read_text(encoding="utf-8"))
        self.assert_nothing_dangerous_ran()

    # Value: protects=D9 at the entry point: a follow-up release adding more newly withheld Reden than the cap is refused naming each, and --confirm-withheld lets it through; fails_when=run_release skips the cap or the flag is not read; why_new=the cap function is tested alone, not through main; seam=main; no_claim=which Reden are worth releasing
    def test_a_release_with_too_many_new_withheld_reden_needs_each_confirmed(self) -> None:
        self.assertEqual([u["rede_id"] for u in self.manifest["withheld_reden"]], ["R1", "R2", "R3"])
        previous = self.work / "previous.json"
        previous.write_text(json.dumps({**self.manifest, "tag": "2026.10.01", "withheld_reden": []}), encoding="utf-8")
        changes = self.work / "changes-source.json"
        changes.write_text(json.dumps({"summary": "Drei Reden zurückgehalten."}), encoding="utf-8")
        args = ("--previous-manifest", str(previous), "--changes", str(changes))
        code, _, stderr = self.run_script(*args)
        self.assert_refused(code, stderr, "--confirm-withheld", "18/7:R1, 18/7:R2, 18/7:R3")
        code, _, stderr = self.run_script(*args, "--confirm-withheld", "18/7:R1", "--confirm-withheld", "18/7:R2", "--confirm-withheld", "18/7:R3")
        self.assertEqual(code, 0, stderr)
        added = json.loads((self.out / f"data-{VERSION}" / "changes.json").read_text(encoding="utf-8"))["withheld_reden_added"]
        self.assertEqual([unit["rede_id"] for unit in added], ["R1", "R2", "R3"])

    # Value: protects=the manifest's withheld list matches the withheld_units rows a reader downloads (P2); fails_when=a hand-edited list (rows removed, added or re-reasoned) passes the cap and the changelog; why_new=Codex's repro at PR 2's ship; seam=main
    def test_the_withheld_list_must_match_the_exported_rows(self) -> None:
        git(self.repo, "tag", "-d", "data-2026.10.01")  # these runs are --initial
        self.addCleanup(git, self.repo, "tag", "data-2026.10.01")
        listed = self.manifest["withheld_reden"]
        cases = (
            ("every row removed", [], "only in the export: 18/7 R1, 18/7 R2, 18/7 R3"),
            ("one row missing", listed[:2], "only in the export: 18/7 R3"),
            ("an extra row", [*listed, {"document_number": "18/7", "rede_id": "R9", "reason": "reviewed"}], "only in the manifest: 18/7 R9"),
            ("a changed reason", [{**listed[0], "reason": "reviewed"}, *listed[1:]],
             "18/7 R1: reason reviewed in the manifest, refused_nested_contribution in the export"),
        )
        for label, units, fragment in cases:
            with self.subTest(label):
                self.edit_manifest(withheld_reden=units)
                code, _, stderr = self.run_script("--initial")
                self.assert_refused(code, stderr, "withheld_reden does not match", fragment)
        self.edit_manifest(withheld_reden=listed)
        code, _, stderr = self.run_script("--initial")
        self.assertEqual(code, 0, stderr)

    # Value: protects=a withheld-list check that cannot read the export is refused with its own message, never passed as "nothing to compare" (class 9); fails_when=withheld_export_problem returns None when a table is missing, listed twice, or unreadable; why_new=the mismatch test only reaches the row comparison of a well-formed export; seam=none; no_claim=verify_export's hash check, which runs first in a release
    def test_an_unreadable_withheld_export_is_refused(self) -> None:
        manifest = json.loads((self.exports_copy / "datenstand.json").read_text(encoding="utf-8"))
        tables = [entry for entry in manifest["files"] if entry["kind"] == "table_csv"]
        withheld = next(e for e in tables if e["name"].startswith("withheld_units"))
        protocols = next(e for e in tables if e["name"].startswith("protocols"))
        generation = self.exports_copy / manifest["generation"]
        cases = (
            ("no protocols table", {**manifest, "files": [e for e in manifest["files"] if e is not protocols and e["name"] != protocols["name"]]},
             "lists 0 protocols tables, not one"),
            ("two withheld tables", {**manifest, "files": [*manifest["files"], {**withheld, "name": "withheld_units-other.csv.gz"}]},
             "lists 2 withheld_units tables, not one"),
        )
        for label, edited, fragment in cases:
            with self.subTest(label):
                problem = publish.withheld_export_problem(edited, generation)
                self.assertIsNotNone(problem)
                self.assertIn(fragment, problem)
        with self.subTest("a table that is no gzip"), tempfile.TemporaryDirectory() as tmp:
            for entry in (withheld, protocols):
                (Path(tmp) / entry["name"]).write_bytes(b"not gzip")
            problem = publish.withheld_export_problem(manifest, Path(tmp))
            self.assertIn("cannot read the exported withheld_units or protocols table", problem or "")

    # Value: protects=a previous manifest whose export_format is not an integer is refused (class 9); fails_when=previous_manifest_problem only checks the field is present, so "17" decides whether the withheld list may be absent; why_new=P2; seam=main
    def test_a_previous_manifest_needs_an_integer_export_format(self) -> None:
        for value in ("17", None, True, 17.0):
            with self.subTest(value=value):
                previous = self.work / "previous.json"
                previous.write_text(json.dumps({**self.manifest, "tag": "2026.10.01", "export_format": value}), encoding="utf-8")
                code, _, stderr = self.run_script("--previous-manifest", str(previous), "--changes", self.write_changes({"summary": "x"}))
                self.assert_refused(code, stderr, "export_format is not an integer")

    # Value: protects=a follow-up release published through gh is not blocked by the previous release's own tag, which gh lists, and creates exactly one release for the new version; fails_when=the remote check counts any listed release as blocking (the --initial rule leaks into follow-ups) or --publish drops the previous version from changes.json; why_new=every other --publish test passes --initial, so the follow-up x --publish cell had no test; seam=main with a recorded gh; no_claim=changelog rules (tested in test_release_changes)
    def test_a_follow_up_release_is_published_although_gh_lists_the_previous_tag(self) -> None:
        previous = self.work / "previous.json"
        previous.write_text(json.dumps({**self.manifest, "tag": "2026.10.01"}), encoding="utf-8")
        runner = Runner(gh_tags=[publish.release_version.tag_for("2026.10.01")], remote_tags=[publish.release_version.tag_for("2026.10.01")])
        code, stdout, stderr = self.run_script("--previous-manifest", str(previous), "--changes", self.write_changes({"summary": "Zwei Sitzungen ergänzt."}), "--publish", runner=runner)
        self.assertEqual(code, 0, stderr)
        self.assertEqual(len(runner.gh("release", "list")), 1)
        (create,) = runner.gh("release", "create")
        self.assertEqual(create[:4], ["gh", "release", "create", f"data-{VERSION}"])
        result = json.loads((self.out / f"data-{VERSION}" / "changes.json").read_text(encoding="utf-8"))
        self.assertEqual(result["previous_version"], "2026.10.01")
        self.assertNotIn("dry run", stdout)

    # Value: protects=the release that follows an export-format bump accepts the older previous manifest and reports the format change in its changelog, while a previous manifest with unusable counts is refused naming the field; fails_when=previous_manifest_problem demands the current export format (the first release after any bump is refused), lets a boolean or text total_rows through, or lets a votes block without members through; why_new=the shapeless-file row only pins the first message of a manifest that is wrong everywhere; seam=main with a previous datenstand.json file; no_claim=changelog rules (tested in test_release_changes)
    def test_an_older_format_previous_manifest_is_usable_and_unusable_counts_are_named(self) -> None:
        def previous_with(**changes) -> str:
            path = self.work / "previous-variant.json"
            path.write_text(json.dumps({**self.manifest, "tag": "2026.10.01", **changes}), encoding="utf-8")
            return str(path)

        refusals = (
            ("protocols without count", {"protocols": {"first": "21/1"}}, "protocols needs count"),
            ("votes without members", {"votes": {"count": 1}}, "votes needs count/members"),
            ("boolean total_rows", {"total_rows": True}, "total_rows is not an integer"),
            ("text total_rows", {"total_rows": "12"}, "total_rows is not an integer"),
        )
        for label, changes, fragment in refusals:
            with self.subTest(label):
                code, _, stderr = self.run_script("--previous-manifest", previous_with(**changes), "--changes", str(self.work / "unused.json"))
                self.assert_refused(code, stderr, "is not a usable datenstand.json", fragment)
        older = previous_with(export_format=self.manifest["export_format"] - 1, schema_hash="0" * 64)
        code, _, stderr = self.run_script("--previous-manifest", older, "--changes", self.write_changes({"summary": "Formatwechsel."}))
        self.assert_refused(code, stderr, "the schema changed since 2026.10.01", "export_format")
        changes = {"summary": "Formatwechsel.", "schema_changes": [{"table": "votes", "column": None, "change": "added", "description": "Neue Tabelle."}]}
        code, _, stderr = self.run_script("--previous-manifest", older, "--changes", self.write_changes(changes))
        self.assertEqual(code, 0, stderr)
        result = json.loads((self.out / f"data-{VERSION}" / "changes.json").read_text(encoding="utf-8"))
        self.assertEqual(result["previous_version"], "2026.10.01")
        self.assertEqual(result["schema_changes"][0]["description"], "Neue Tabelle.")

    def write_changes(self, content: dict) -> str:
        path = self.work / "changes-variant.json"
        path.write_text(json.dumps(content), encoding="utf-8")
        return str(path)


if __name__ == "__main__":
    unittest.main()
