"""The cited build revision, against real git in temporary repositories."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import build_revision as rev


def git(repo: Path, *args: str) -> str:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True, text=True).stdout.strip()


def make_repo(files: dict[str, str]) -> Path:
    repo = Path(tempfile.mkdtemp())
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.org")
    git(repo, "config", "user.name", "t")
    for name, text in files.items():
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "init")
    return repo


class ResolveCommitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = make_repo({"a.txt": "one\ntwo\nthree\n", "docs/b.md": "text\n"})
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    # Value: protects=a clean tree is cited by the first 12 hex digits of HEAD, whatever core.abbrev says; fails_when=the length floats with git config or an ambiguous short id; why_new=--short=12 can return more than 12 digits; seam=resolve_commit; no_claim=dirty trees
    def test_clean_tree_is_the_twelve_digit_head_prefix(self) -> None:
        head = git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(rev.resolve_commit(self.repo), head[:12])
        git(self.repo, "config", "core.abbrev", "4")
        self.assertEqual(rev.resolve_commit(self.repo), head[:12])

    # Value: protects=touching a tracked file without changing it does not make the revision dirty; fails_when=diff-index reports stat-dirty files; why_new=plumbing diff-index skips porcelain's stat refresh; seam=resolve_commit; no_claim=content changes
    def test_touched_but_unchanged_file_is_clean(self) -> None:
        os.utime(self.repo / "a.txt", (1, 1))
        self.assertRegex(rev.resolve_commit(self.repo), r"^[0-9a-f]{12}$")

    # Value: protects=the same edit gives the same revision whatever the reader's git config or inherited GIT_* variables say; fails_when=colour, prefix, abbrev, algorithm, external-diff settings or GIT_DIR/GIT_INDEX_FILE change the hash; why_new=resolve_commit hashed the bytes of a porcelain diff; seam=resolve_commit; no_claim=the hash value itself
    def test_same_edit_same_revision_under_hostile_git_config(self) -> None:
        (self.repo / "a.txt").write_text("one\nTWO\nthree\n", encoding="utf-8")
        baseline = rev.resolve_commit(self.repo)
        self.assertRegex(baseline, r"^[0-9a-f]{12}-dirty-[0-9a-f]{8}$")
        other = make_repo({"x": "elsewhere\n"})
        self.addCleanup(shutil.rmtree, other, ignore_errors=True)
        for key, value in (
            ("color.ui", "always"),
            ("diff.noprefix", "true"),
            ("diff.mnemonicPrefix", "true"),
            ("core.abbrev", "4"),
            ("diff.algorithm", "patience"),
            ("diff.context", "9"),
            ("diff.external", "false"),
            ("diff.renames", "copies"),
        ):
            git(self.repo, "config", key, value)
        hostile_env = {"GIT_DIR": str(other / ".git"), "GIT_WORK_TREE": str(other), "GIT_INDEX_FILE": str(other / "no-such-index")}
        with mock.patch.dict(os.environ, hostile_env):
            self.assertEqual(rev.resolve_commit(self.repo), baseline)

    # Value: protects=different edits give different revisions, and a staged edit counts as an edit; fails_when=two edits share a suffix or the index hides one; why_new=the cache key and DATA.md cite this suffix; seam=resolve_commit; no_claim=untracked files
    def test_different_edits_give_different_revisions(self) -> None:
        (self.repo / "a.txt").write_text("one\nTWO\nthree\n", encoding="utf-8")
        first = rev.resolve_commit(self.repo)
        (self.repo / "a.txt").write_text("one\ntwo\nTHREE\n", encoding="utf-8")
        second = rev.resolve_commit(self.repo)
        self.assertNotEqual(first, second)
        git(self.repo, "add", "a.txt")
        self.assertEqual(rev.resolve_commit(self.repo), second)

    # Value: protects=a diff git cannot produce in time still gives a revision that moves with edits, and never one a release accepts; fails_when=the fallback is a constant or passes the release gate; why_new=a timeout gave the constant -unverified; seam=resolve_commit; no_claim=timeout length
    def test_timeout_fallback_moves_with_edits_and_is_not_a_release_revision(self) -> None:
        real_run = subprocess.run

        def slow_diff(command, *args, **kwargs):
            if "diff-index" in command:
                raise subprocess.TimeoutExpired(command, 30)
            return real_run(command, *args, **kwargs)

        with mock.patch.object(rev.subprocess, "run", side_effect=slow_diff):
            clean = rev.resolve_commit(self.repo)
            (self.repo / "a.txt").write_text("one\nTWO\nthree\n", encoding="utf-8")
            first = rev.resolve_commit(self.repo)
            (self.repo / "a.txt").write_text("one\ntwo\nTHREE!\n", encoding="utf-8")
            second = rev.resolve_commit(self.repo)
        for value in (clean, first, second):
            self.assertRegex(value, r"^[0-9a-f]{12}-unverified-[0-9a-f]{8}$")
            self.assertFalse(rev.is_release_revision(value))
        self.assertNotEqual(first, second)
        self.assertNotEqual(clean, first)

    # Value: protects=no usable git means no revision, not a crash; fails_when=a non-repository directory or a missing git binary raises; why_new=local builds run from source archives; seam=resolve_commit; no_claim=message text
    def test_no_repository_or_no_git_gives_none(self) -> None:
        plain = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, plain, ignore_errors=True)
        with mock.patch.dict(os.environ, {"GIT_CEILING_DIRECTORIES": str(plain.parent)}):
            self.assertIsNone(rev.resolve_commit(plain))
        with mock.patch.object(rev.subprocess, "run", side_effect=FileNotFoundError("git")):
            self.assertIsNone(rev.resolve_commit(self.repo))

    # Value: protects=only a bare 12-digit id passes the release gate; fails_when=a dirty, unverified, short, long, upper-case or empty revision is accepted; why_new=the gate looked only for a hyphen; seam=is_release_revision; no_claim=whether the id exists
    def test_release_gate_accepts_only_a_bare_twelve_digit_id(self) -> None:
        self.assertTrue(rev.is_release_revision("0123456789ab"))
        for bad in (None, "", "abc123", "0123456789abc", "0123456789AB", "0123456789ab-dirty-01234567", "0123456789ab-unverified", "0123456789ab\n"):
            with self.subTest(bad=bad):
                self.assertFalse(rev.is_release_revision(bad))


class CommitLookupTests(unittest.TestCase):
    # Value: protects=a release names its commit in full and checks file content as that commit holds it; fails_when=a short id that names no commit, a non-hex string or a missing path is accepted; why_new=the release script targets the manifest's commit, not HEAD; seam=full_commit and blob_sha256; no_claim=ambiguous prefixes
    def test_full_commit_and_blob_hash(self) -> None:
        import hashlib

        repo = make_repo({"a.txt": "one\n"})
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        head = git(repo, "rev-parse", "HEAD")
        (repo / "a.txt").write_text("two\n", encoding="utf-8")  # the working file moves on; the commit does not
        self.assertEqual(rev.full_commit(repo, head[:12]), head)
        self.assertIsNone(rev.full_commit(repo, "0123456789ab"))
        self.assertIsNone(rev.full_commit(repo, "HEAD"))
        self.assertIsNone(rev.full_commit(repo, head[:12] + "-dirty-01234567"))
        self.assertEqual(rev.blob_sha256(repo, head, "a.txt"), hashlib.sha256(b"one\n").hexdigest())
        self.assertIsNone(rev.blob_sha256(repo, head, "missing.txt"))


class AuthoredInputsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = make_repo({"docs/m.md": "m\n", "d.json": "{}\n"})
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.paths = ("docs/m.md", "d.json")

    # Value: protects=a release export is refused while an authored input is untracked, edited or staged-but-uncommitted; fails_when=the gate passes an input the commit does not contain; why_new=the revision ignores untracked files; seam=authored_inputs_problem; no_claim=message wording beyond the path
    def test_inputs_must_be_tracked_and_unmodified(self) -> None:
        self.assertIsNone(rev.authored_inputs_problem(self.repo, self.paths))
        (self.repo / "docs/m.md").write_text("changed\n", encoding="utf-8")
        self.assertIn("docs/m.md", rev.authored_inputs_problem(self.repo, self.paths))
        git(self.repo, "checkout", "--", "docs/m.md")
        (self.repo / "new.md").write_text("new\n", encoding="utf-8")
        self.assertIn("new.md", rev.authored_inputs_problem(self.repo, (*self.paths, "new.md")))
        git(self.repo, "add", "new.md")
        self.assertIn("new.md", rev.authored_inputs_problem(self.repo, (*self.paths, "new.md")))
        self.assertIn("missing.md", rev.authored_inputs_problem(self.repo, (*self.paths, "missing.md")))

    # Value: protects=a checkout or rebase that only touches an authored input does not block a release the revision calls clean; fails_when=the input check reports stat-dirty files that resolve_commit treats as clean; why_new=plumbing diff-index --name-only does not compare content; seam=authored_inputs_problem; no_claim=content edits
    def test_a_touched_but_unchanged_input_is_not_a_problem(self) -> None:
        os.utime(self.repo / "docs/m.md", (1, 1))
        self.assertIsNone(rev.authored_inputs_problem(self.repo, self.paths))
        self.assertRegex(rev.resolve_commit(self.repo), r"^[0-9a-f]{12}$")

    # Value: protects=unrelated tracked edits do not block a release by themselves (the revision gate covers them) and no git blocks it; fails_when=an edit to another file trips the input check or git failure passes it; why_new=the two gates are separate; seam=authored_inputs_problem; no_claim=revision gate
    def test_other_edits_are_not_this_gates_business_but_missing_git_is(self) -> None:
        (self.repo / "other.txt").write_text("x\n", encoding="utf-8")
        self.assertIsNone(rev.authored_inputs_problem(self.repo, self.paths))
        with mock.patch.object(rev.subprocess, "run", side_effect=FileNotFoundError("git")):
            self.assertIn("git", rev.authored_inputs_problem(self.repo, self.paths))


if __name__ == "__main__":
    unittest.main()
