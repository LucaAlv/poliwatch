"""The build revision an export cites, and the gate a release passes.

A revision is a fixed-length commit id, ``<commit>-dirty-<hash>`` when tracked
files differ from it, or ``<commit>-unverified[-<hash>]`` when git could not
say. Only the bare 12-digit form is a release revision. The bytes that get
hashed come from git plumbing with every output-changing setting pinned and the
repository-locating ``GIT_*`` variables removed, so one edit gives one revision
on any machine; untracked files are not counted, which ``authored_inputs_problem``
covers for the files an export is built from.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import Sequence

REVISION_LENGTH = 12
_RELEASE_REVISION_RE = re.compile(r"[0-9a-f]{12}")

# Settings that change the bytes of a patch, pinned on the command line so a
# user's gitconfig cannot move the hash (command-line -c beats every config file).
_PINNED_CONFIG = (
    "core.abbrev=40",
    "core.quotepath=true",
    "color.ui=never",
    "diff.noprefix=false",
    "diff.mnemonicPrefix=false",
    "diff.algorithm=default",
    "diff.indentHeuristic=true",
    "diff.context=3",
    "diff.interHunkContext=0",
    "diff.renames=false",
    "diff.orderFile=/dev/null",
)
_DIFF_FLAGS = (
    "diff-index",
    "-p",
    "--binary",
    "--full-index",
    "--no-ext-diff",
    "--no-textconv",
    "--no-color",
    "--no-renames",
    "--unified=3",
)


def _clean_env() -> dict[str, str]:
    """The environment without GIT_*: GIT_DIR, GIT_WORK_TREE and GIT_INDEX_FILE
    would point git at another repository, and GIT_EXTERNAL_DIFF and
    GIT_DIFF_OPTS would change the patch."""
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def _git(repo_root: Path, *args: str, timeout: int) -> bytes:
    command = ["git", "--no-optional-locks"]
    for setting in _PINNED_CONFIG:
        command += ["-c", setting]
    return subprocess.run(
        [*command, *args],
        cwd=repo_root,
        env=_clean_env(),
        capture_output=True,
        timeout=timeout,
        check=True,
    ).stdout


def _stat_digest(repo_root: Path) -> str | None:
    """A hash of every tracked file's path, size and mtime: not portable, but it
    moves with every local edit, which a constant fallback would not."""
    try:
        names = _git(repo_root, "ls-files", "-z", timeout=10).split(b"\0")
    except (OSError, subprocess.SubprocessError):
        return None
    digest = hashlib.sha256()
    for raw in sorted(name for name in names if name):
        try:
            stat = (repo_root / os.fsdecode(raw)).stat()
        except OSError:
            continue  # a tracked file deleted from the tree: its absence is the edit
        digest.update(raw + b"\0" + f"{stat.st_size}:{stat.st_mtime_ns}".encode() + b"\0")
    return digest.hexdigest()[:8]


def resolve_commit(repo_root: Path) -> str | None:
    """The cited revision of the checkout at ``repo_root``, or None when it is
    no git checkout (or git is missing)."""
    try:
        head = _git(repo_root, "rev-parse", "HEAD", timeout=5).decode("ascii").strip()
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError):
        return None
    commit = head[:REVISION_LENGTH]
    if not _RELEASE_REVISION_RE.fullmatch(commit):
        return None
    try:
        diff = _git(repo_root, *_DIFF_FLAGS, "HEAD", timeout=30)
    except (OSError, subprocess.SubprocessError):
        digest = _stat_digest(repo_root)
        return f"{commit}-unverified-{digest}" if digest else f"{commit}-unverified"
    return f"{commit}-dirty-{hashlib.sha256(diff).hexdigest()[:8]}" if diff else commit


def is_release_revision(commit: str | None) -> bool:
    """Only a bare 12-digit commit id: no suffix, no other length."""
    return bool(commit) and _RELEASE_REVISION_RE.fullmatch(commit) is not None


def authored_inputs_problem(repo_root: Path, relative_paths: Sequence[str]) -> str | None:
    """Why a release cannot cite its revision for these authored files, or None.
    The revision ignores untracked files, so a release also needs each file
    tracked and equal to what HEAD holds."""
    try:
        listed = _git(repo_root, "ls-files", "-z", "--", *relative_paths, timeout=10).split(b"\0")
        tracked = {os.fsdecode(name) for name in listed if name}
        untracked = [path for path in relative_paths if path not in tracked]
        if untracked:
            return f"not tracked by git: {', '.join(untracked)}"
        names = _git(repo_root, "diff-index", "--name-only", "-z", "--no-renames", "HEAD", "--", *relative_paths, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"git could not check them: {exc}"
    changed = [os.fsdecode(name) for name in names.split(b"\0") if name]
    if changed:
        return f"differ from HEAD: {', '.join(changed)}"
    return None
