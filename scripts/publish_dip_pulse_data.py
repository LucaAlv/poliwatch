#!/usr/bin/env python3
"""Build an immutable, versioned data release from an existing Daten export.

Typical use (see scripts/publish_dip_pulse_data.sh for the wrapper):

    scripts/publish_dip_pulse_data.sh --next-version        # e.g. 2026.11.01
    python scripts/build_dip_pulse_site.py ... --data-tag 2026.11.01   # builds the export
    scripts/publish_dip_pulse_data.sh --exports-dir <site>/data/exports \
        --output-dir release --base-url https://host/path/ --initial

The default is a dry run: it checks the export, writes the release directory
(``<output-dir>/data-<version>/``) and prints the ``gh release create`` command it
would run. ``--publish`` creates the release through ``gh`` and refuses unless
LICENSE-DATA.md exists at the repository root (ADR 0003). This script never
pushes, tags or uploads by itself; the only remote command is the one printed.

The release is refused unless its export was built with a release tag, from a
clean commit that exists in this repository (the manifest's, not HEAD), from the
authored inputs that commit holds, and every file matches the manifest.
"""

from __future__ import annotations

if __name__ == "__main__":
    from python_version_guard import require_supported_python

    require_supported_python()

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Callable

import build_revision
import release_changes
import release_version

REPO_ROOT = Path(__file__).resolve().parents[1]
LICENSE_FILE = "LICENSE-DATA.md"
ADR = "docs/adr/0003-licences-and-impressum.md"


class ReleaseError(RuntimeError):
    """A release is refused; the message says why."""


def _site():
    # build_dip_pulse_site is large; only a release build needs its manifest validator.
    import build_dip_pulse_site

    return build_dip_pulse_site


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, what: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"cannot read {what} {path}: {exc}") from exc


def local_versions(repo_root: Path, run: Callable[..., Any]) -> set[str]:
    """Versions of the data-* tags this clone knows (a clone that has not fetched misses remote ones)."""
    result = run(["git", "tag", "--list", f"{release_version.TAG_PREFIX}*"], cwd=repo_root, env=build_revision.clean_env(), capture_output=True, text=True)
    if result.returncode != 0:
        raise ReleaseError(f"git tag --list failed: {result.stderr.strip()}")
    return {version for tag in result.stdout.split() if (version := release_version.version_of(tag))}


def remote_versions(repo_root: Path, run: Callable[..., Any]) -> set[str]:
    result = run(["gh", "release", "list", "--json", "tagName", "--limit", "1000"], cwd=repo_root, capture_output=True, text=True)
    if result.returncode != 0:
        raise ReleaseError(f"cannot ask gh for existing releases (gh release list failed: {result.stderr.strip() or 'no message'}); not publishing blind")
    try:
        names = [entry["tagName"] for entry in json.loads(result.stdout)]
    except (ValueError, KeyError, TypeError) as exc:
        raise ReleaseError(f"gh release list returned something unreadable: {exc}") from exc
    return {version for tag in names if (version := release_version.version_of(tag))}


def verify_export(exports_dir: Path, repo_root: Path) -> tuple[dict[str, Any], str, str]:
    """The manifest, the release version and the full commit of an export that may be released."""
    site = _site()
    manifest_path = exports_dir / "datenstand.json"
    manifest = site.validate_manifest(_read_json(manifest_path, "manifest"), str(manifest_path), subject=str(manifest_path))
    version = manifest.get("tag")
    if not release_version.is_version(version):
        raise ReleaseError(
            f"the export's tag {version!r} is not a release version; build the export with --data-tag <version> "
            "(scripts/publish_dip_pulse_data.sh --next-version prints it)"
        )
    commit = manifest.get("commit")
    if not build_revision.is_release_revision(commit):
        raise ReleaseError(f"release {version} needs a clean, known build revision (the export cites {commit or 'none'}); rebuild from a clean commit")
    full = build_revision.full_commit(repo_root, commit)
    if full is None:
        raise ReleaseError(f"the export's commit {commit} is not a commit of this repository")
    inputs = manifest.get("codebook_inputs")
    if not isinstance(inputs, dict) or set(inputs) != set(site.CODEBOOK_INPUT_FILES.values()):
        raise ReleaseError("the manifest does not name the authored codebook inputs")
    for relative, digest in sorted(inputs.items()):
        if build_revision.blob_sha256(repo_root, full, relative) != digest:
            raise ReleaseError(f"the authored input {relative} of the export differs from commit {commit}; rebuild from that commit")
    generation = exports_dir / manifest["generation"]
    listed = {entry["name"]: entry for entry in manifest["files"]}
    present = {path.name for path in generation.iterdir()} if generation.is_dir() else set()
    if present != set(listed):
        problems = [f"extra file {name}" for name in sorted(present - set(listed))] + [f"missing file {name}" for name in sorted(set(listed) - present)]
        raise ReleaseError(f"{generation} does not match the manifest: {', '.join(problems)}")
    for name, entry in sorted(listed.items()):
        path = generation / name
        if path.stat().st_size != entry["bytes"] or _sha256(path) != entry.get("sha256"):
            raise ReleaseError(f"{path} does not match the manifest (size or sha256)")
    return manifest, version, full


def _link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, target)  # exports are replaced as a whole, never edited in place
    except OSError:
        shutil.copy2(source, target)


def _write_checksums(directory: Path) -> None:
    lines = [
        f"{_sha256(path)}  {path.relative_to(directory).as_posix()}"
        for path in sorted(directory.rglob("*"), key=lambda p: p.relative_to(directory).as_posix())
        if path.is_file() and path.name != "SHA256SUMS"
    ]
    (directory / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_release_directory(
    *, exports_dir: Path, manifest: dict[str, Any], version: str, changes: dict[str, Any], output_dir: Path, license_file: Path | None
) -> Path:
    release_dir = output_dir / release_version.tag_for(version)
    if release_dir.exists():
        raise ReleaseError(f"{release_dir} already exists; a release directory is never overwritten")
    output_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=output_dir, prefix=".building-"))
    try:
        shutil.copyfile(exports_dir / "datenstand.json", staging / "datenstand.json")
        for entry in manifest["files"]:
            _link_or_copy(exports_dir / manifest["generation"] / entry["name"], staging / manifest["generation"] / entry["name"])
        (staging / "changes.json").write_text(json.dumps(changes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (staging / "CHANGES.md").write_text(release_changes.render_markdown(changes), encoding="utf-8")
        if license_file is not None:
            shutil.copyfile(license_file, staging / LICENSE_FILE)
        _write_checksums(staging)
        staging.rename(release_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return release_dir


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an immutable, versioned data release from an existing export (dry run by default).")
    parser.add_argument("--next-version", action="store_true", help="Print the version for a release made today and exit; build the export with --data-tag <version>.")
    parser.add_argument("--exports-dir", type=Path, help="The export to release: the directory holding datenstand.json and the g-<hash> generation.")
    parser.add_argument("--output-dir", type=Path, help="Where the release directory data-<version>/ is written (never overwritten).")
    parser.add_argument("--base-url", help="Public URL under which the release directory's contents will be served (printed as --data-base-url).")
    parser.add_argument("--initial", action="store_true", help="This is the first data release.")
    parser.add_argument("--previous-manifest", type=Path, help="datenstand.json of the previous release (for the changelog).")
    parser.add_argument("--changes", type=Path, help="Authored changes file (docs/data-changelog.md); required for every release but the first.")
    parser.add_argument("--publish", action="store_true", help=f"Create the release through gh. Refuses unless {LICENSE_FILE} exists at the repository root (ADR 0003).")
    return parser.parse_args(argv)


def run_release(args: argparse.Namespace, *, repo_root: Path, run: Callable[..., Any], out: Callable[[str], None], today: date) -> None:
    if not (args.exports_dir and args.output_dir):
        raise ReleaseError("--exports-dir and --output-dir are required")
    if args.initial == bool(args.previous_manifest):
        raise ReleaseError("say which release this is: --initial (the first) or --previous-manifest <datenstand.json> (not both)")
    license_file = repo_root / LICENSE_FILE
    if args.publish and not license_file.is_file():
        raise ReleaseError(
            f"--publish refused: {LICENSE_FILE} does not exist at the repository root. ADR 0003 ({ADR}) is not implemented yet, "
            "and a release must carry its data licence. A dry run (without --publish) still works."
        )
    data_base_url = None
    if args.base_url:
        try:
            data_base_url = _site().resolve_data_base_url(args.base_url)
        except ValueError as exc:
            raise ReleaseError(str(exc)) from exc
    manifest, version, full_commit = verify_export(args.exports_dir, repo_root)
    if args.publish and not str(manifest.get("license") or "").strip():
        raise ReleaseError(
            "--publish refused: the export carries no licence string (manifest field license). Rebuild it with --data-license "
            f"(the short string of {ADR}) or $BUNDESTAG_PULSE_DATA_LICENSE."
        )
    tag = release_version.tag_for(version)
    known = local_versions(repo_root, run)
    if args.publish:
        known |= remote_versions(repo_root, run)
    if version in known:
        raise ReleaseError(f"release {tag} already exists; releases are immutable, build a new version (--next-version)")
    if args.initial and known:
        raise ReleaseError(f"--initial, but data releases already exist ({', '.join(sorted(known, key=release_version.version_key))}); give --previous-manifest instead")
    previous = _read_json(args.previous_manifest, "previous manifest") if args.previous_manifest else None
    authored = release_changes.load_authored(args.changes) if args.changes else None
    changes = release_changes.assemble(version=version, released=today, manifest=manifest, previous_manifest=previous, authored=authored)
    release_dir = build_release_directory(
        exports_dir=args.exports_dir, manifest=manifest, version=version, changes=changes, output_dir=args.output_dir,
        license_file=license_file if license_file.is_file() else None,
    )
    files = sorted((path for path in release_dir.rglob("*") if path.is_file()), key=lambda p: p.relative_to(release_dir).as_posix())
    command = [
        "gh", "release", "create", tag, *map(str, files),
        "--title", f"Daten {version}", "--notes-file", str(release_dir / "CHANGES.md"), "--target", full_commit,
    ]
    out(f"version: {version}")
    out(f"tag: {tag}")
    out(f"export format: {manifest['export_format']}" + (" (schema change, see CHANGES.md)" if changes["schema_changed"] else ""))
    out(f"commit: {full_commit}")
    out(f"release directory: {release_dir}")
    out("site build: --offline --data-manifest " + f"{release_dir / 'datenstand.json'} --data-base-url {data_base_url or '<where the release directory is served>'}")
    if not args.publish:
        out("dry run: nothing was published. The command --publish would run:")
        out(shlex.join(command))
        out("immutability check: local tags only (best effort); --publish also asks gh for existing releases.")
        out(
            "hosting: GitHub release assets are flat, but the site links <base><generation>/<file>; "
            "a GitHub release URL as --base-url does not resolve until the site's link scheme or the host changes "
            "(TODOS: Site hosting plan). Use a host that keeps the directory layout of the release directory."
        )
        if not license_file.is_file():
            out(f"{LICENSE_FILE}: missing at the repository root; --publish refuses until ADR 0003 is implemented.")
        if not str(manifest.get("license") or "").strip():
            out("licence string: empty in the export; --publish refuses until the export is rebuilt with --data-license.")
        return
    result = run(command, cwd=repo_root, capture_output=True, text=True)
    if result.returncode != 0:
        raise ReleaseError(f"gh release create failed: {result.stderr.strip() or 'no message'} (the release directory {release_dir} is kept)")
    out(f"published: {result.stdout.strip()}")


def main(argv: list[str] | None = None, *, repo_root: Path = REPO_ROOT, run: Callable[..., Any] = subprocess.run, today: date | None = None) -> int:
    args = parse_args(argv)
    today = today or date.today()
    try:
        if args.next_version:
            print(release_version.next_version(today, local_versions(repo_root, run)))
            return 0
        run_release(args, repo_root=repo_root, run=run, out=print, today=today)
    except (ReleaseError, release_changes.ChangesError, RuntimeError) as exc:
        message = str(exc)
        print(message if message.startswith("error: ") else f"error: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
