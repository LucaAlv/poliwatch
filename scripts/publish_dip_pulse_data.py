#!/usr/bin/env python3
"""Build an immutable, versioned data release from an existing Daten export.

Typical use (see scripts/publish_dip_pulse_data.sh for the wrapper):

    scripts/publish_dip_pulse_data.sh --next-version        # e.g. 2026.11.01
    python scripts/build_dip_pulse_site.py ... --data-tag 2026.11.01   # builds the export
    scripts/publish_dip_pulse_data.sh --exports-dir <site>/data/exports \
        --output-dir release --base-url https://host/path/ --initial

The default is a dry run: it checks the export, writes the release directory
(``<output-dir>/data-<version>/``) and prints the ``gh release create`` command it
would run. A later run reuses an existing release directory only when its files
are exactly the ones it builds (``--publish`` after a dry run the same day, or
after a failed ``gh`` call); otherwise it refuses and never overwrites. ``--publish`` creates the release through ``gh`` and refuses unless
the export's licence string is the short string of its commit's LICENSE-DATA.md (ADR 0003), every exclusion on its record
is final, ``source_defect`` or ``not_narrowable`` (ADR 0005, "Coverage and the
bar"), every v1 sitting DIP lists with XML is in the export or on its
exclusion record (read from the catalog the build left next to the exports
directory, or ``--catalog``), and every contested vote link of the export is
reviewed (``scripts/reviewed_vote_links.json`` as the export's commit holds it;
docs/plans/vote-pr-c.md, section 5). This script never pushes, tags or uploads by itself; the only remote
command is the one printed.

The release is refused unless its export was built with a release tag, from a
clean commit that exists in this repository (the manifest's, not HEAD), from the
authored inputs that commit holds, with the MdB-Stammdaten loaded, every
file matches the manifest, and the manifest's withheld_reden list matches the
exported withheld_units rows. The export's LICENSE-DATA.md is one of those files:
non-empty and equal to the one that commit holds. The staged copy is checked
against the verified manifest again before it becomes the release directory.
A follow-up release's ``--previous-manifest`` must be the latest release tag on
origin, and ``--publish`` refuses a tag that already exists on origin.
"""

from __future__ import annotations

if __name__ == "__main__":
    from python_version_guard import require_supported_python

    require_supported_python()

import argparse
import csv
import gzip
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
import reviewed_vote_links

REPO_ROOT = Path(__file__).resolve().parents[1]
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
    return _read_json_bytes(path, what)[0]


def _read_json_bytes(path: Path, what: str) -> tuple[Any, bytes]:
    """The parsed file and the bytes it was parsed from (read once)."""
    try:
        raw = path.read_bytes()
        return json.loads(raw.decode("utf-8")), raw
    # ValueError covers JSONDecodeError, UnicodeDecodeError and an integer past
    # the 4300-digit limit; RecursionError a nesting deeper than the parser's stack.
    except (OSError, ValueError, RecursionError) as exc:
        raise ReleaseError(f"cannot read {what} {path}: {exc}") from exc


def previous_manifest_problem(previous: Any) -> str | None:
    """Why a --previous-manifest cannot head the changelog, or None. Not the
    site's validate_manifest: that refuses every export format but the current
    one, and the release after a format bump is the one whose changelog must
    report it. This checks the fields release_changes reads."""
    if not isinstance(previous, dict):
        return "is not a datenstand.json (a JSON object)"
    problems = [f"missing {field}" for field in release_changes.SCHEMA_FIELDS if field not in previous]
    for key, fields in (("protocols", ("count",)), ("votes", ("count", "members"))):
        if not isinstance(previous.get(key), dict) or not all(field in previous[key] for field in fields):
            problems.append(f"{key} needs {'/'.join(fields)}")
    if type(previous.get("total_rows")) is not int:
        problems.append("total_rows is not an integer")
    if "export_format" in previous and type(previous["export_format"]) is not int:
        # It decides whether the previous withheld list may be absent (release_changes.WITHHELD_LIST_FORMAT).
        problems.append("export_format is not an integer")
    return f"is not a usable datenstand.json: {'; '.join(problems)}" if problems else None


def _csv_rows(path: Path) -> list[dict[str, str]]:
    # A withheld Rede's text is one field and may run past csv's default 128 KiB.
    csv.field_size_limit(2**31 - 1)
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _shown(numbers: list[str]) -> str:
    return ", ".join(numbers[:12]) + (", …" if len(numbers) > 12 else "")


def _sittings(count: int) -> str:
    return f"{count} sitting" if count == 1 else f"{count} sittings"


def withheld_export_problem(manifest: dict[str, Any], generation_dir: Path) -> str | None:
    """P2 (ADR 0005): why the manifest's withheld_reden list does not match the
    exported withheld_units rows, or None. The cap and the changelog read the
    list, a reader downloads the rows; verify_export has already matched both
    files' hashes. The sqlite file of the generation comes from the same
    snapshot, so the CSV stands for it."""
    tables: dict[str, list[str]] = {}
    for entry in manifest.get("files") or []:
        if entry.get("kind") == "table_csv":
            tables.setdefault(str(entry["name"]).partition("-")[0], []).append(entry["name"])
    for table in ("withheld_units", "protocols"):
        if len(tables.get(table, [])) != 1:
            return f"the export lists {len(tables.get(table, []))} {table} tables, not one; export it again"
    try:
        numbers = {row["id"]: row["document_number"] for row in _csv_rows(generation_dir / tables["protocols"][0])}
        exported: dict[str, str] = {}
        for row in _csv_rows(generation_dir / tables["withheld_units"][0]):
            unit = {"document_number": numbers.get(row["protocol_id"]), "rede_id": row["rede_id"]}
            exported[release_changes._withheld_key(unit)] = row["reason"]
    except (OSError, EOFError, KeyError, ValueError, csv.Error) as exc:
        return f"cannot read the exported withheld_units or protocols table ({exc}); export it again"
    listed = {key: unit["reason"] for key, unit in release_changes.withheld_list(manifest, "the manifest").items()}
    problems = []
    if only := sorted(exported.keys() - listed.keys()):
        problems.append(f"only in the export: {', '.join(only)}")
    if only := sorted(listed.keys() - exported.keys()):
        problems.append(f"only in the manifest: {', '.join(only)}")
    problems.extend(
        f"{key}: reason {listed[key]} in the manifest, {exported[key]} in the export"
        for key in sorted(listed.keys() & exported.keys())
        if listed[key] != exported[key]
    )
    if problems:
        return f"the manifest's withheld_reden does not match the exported withheld_units rows ({'; '.join(problems)}); export it again"
    return None


def awaiting_exclusions(manifest: dict[str, Any]) -> list[str]:
    """The sittings the export's exclusion record keeps out on their way back
    (ADR 0005, "Coverage and the bar"): every reason outside
    FINAL_EXCLUSION_REASONS. Raises ReleaseError when the record cannot be read."""
    excluded = (manifest.get("coverage") or {}).get("excluded") if isinstance(manifest.get("coverage"), dict) else None
    if not isinstance(excluded, list):
        raise ReleaseError("the manifest carries no coverage.excluded list (ADR 0005); export it again")
    waiting = []
    for index, entry in enumerate(excluded):
        if not isinstance(entry, dict) or not all(isinstance(entry.get(field), str) and entry[field].strip() for field in ("document_number", "reason")):
            raise ReleaseError(f"coverage.excluded[{index}] needs a document_number and a reason; export it again")
        if entry["reason"] not in _site().FINAL_EXCLUSION_REASONS:
            waiting.append(entry["document_number"])
    return waiting


def awaiting_text(waiting: list[str]) -> str:
    return f"{len(waiting)} exclusions still await acquisition or a rule (ADR 0005, \"Coverage and the bar\": {_shown(waiting)})"


def _sitting_order(number: str) -> tuple[int, int, str]:
    head, _, tail = number.partition("/")
    return (int(head), int(tail), "") if head.isdigit() and tail.isdigit() else (1 << 30, 0, number)


def catalog_v1_sittings(path: Path) -> dict[str, bool]:
    """Every sitting of V1_FIRST_WAHLPERIODE on that the build's DIP catalog
    lists, and whether DIP gives its XML. Only a catalog fetched in full
    (``"authoritative": true``, as the build writes it) can show what is missing."""
    site = _site()
    try:
        payload = _read_json(path, "catalog")
    except ReleaseError as exc:
        raise ReleaseError(f"{exc}; an online build writes it next to the exports directory, or name another with --catalog") from exc
    if not isinstance(payload, dict) or payload.get("authoritative") is not True or not isinstance(payload.get("protocols"), list):
        raise ReleaseError(
            f"the catalog {path} is not a complete DIP catalog (an object with \"authoritative\": true and a protocols list); "
            "an online build writes it next to the exports directory, or name another with --catalog"
        )
    sittings: dict[str, bool] = {}
    for protocol in payload["protocols"]:
        if not isinstance(protocol, dict):
            continue
        number = site.normalized_document_number(protocol.get("dokumentnummer"))
        wahlperiode = site.wahlperiode_of(protocol)
        if wahlperiode is None or wahlperiode < site.V1_FIRST_WAHLPERIODE:
            continue
        has_xml = isinstance(protocol.get("fundstelle") or {}, dict) and bool(site.protocol_xml_url(protocol))
        sittings[number] = sittings.get(number, False) or has_xml
    return sittings


def unreleased_sittings_problem(manifest: dict[str, Any], generation_dir: Path, catalog_path: Path) -> str | None:
    """Owner decision 6 (docs/plans/t4-acquire.md): why the export leaves out a
    v1 sitting DIP lists with XML that is not on its exclusion record, or None.
    A sitting DIP lists without XML yet (incomplete_sitting_protocols' waiting)
    is not missing. A catalog that lacks a sitting the export holds is older
    than the export and cannot vouch for it. Call after awaiting_exclusions and
    withheld_export_problem, which check the record and the protocols table."""
    catalog = catalog_v1_sittings(catalog_path)
    site = _site()
    (table,) = [entry["name"] for entry in manifest["files"] if entry.get("kind") == "table_csv" and str(entry["name"]).partition("-")[0] == "protocols"]
    try:
        stored = {site.normalized_document_number(row["document_number"]) for row in _csv_rows(generation_dir / table)}
    except (OSError, EOFError, KeyError, ValueError, csv.Error) as exc:
        raise ReleaseError(f"cannot read the exported protocols table ({exc}); export it again") from exc
    excluded = {entry["document_number"].strip() for entry in manifest["coverage"]["excluded"]}
    v1_stored = {
        number for number in stored
        if (wahlperiode := site.wahlperiode_of({"dokumentnummer": number})) is not None and wahlperiode >= site.V1_FIRST_WAHLPERIODE
    }
    stale = sorted(v1_stored - catalog.keys(), key=_sitting_order)
    if stale:
        return (f"the catalog {catalog_path} lacks {_sittings(len(stale))} the export holds ({_shown(stale)}), so it is older "
                "than the export and cannot show which sittings are missing; refresh it with an online build")
    missing = sorted((number for number, has_xml in catalog.items() if has_xml and number not in stored | excluded), key=_sitting_order)
    if missing:
        verb = "is" if len(missing) == 1 else "are"
        return (f"{len(missing)} v1 {'sitting' if len(missing) == 1 else 'sittings'} DIP lists with XML {verb} neither in the export "
                f"nor on its exclusion record ({_shown(missing)}); acquire them, or record why they stay out, and export again")
    return None


#: The exported tables the vote-link review gate reads, with the columns it needs.
_VOTE_LINK_TABLES = {
    "protocols": ("id", "document_number"),
    "agenda_items": ("id", "protocol_id", "item_index", "top_id", "heading", "page_start"),
    "votes": ("id", "protocol_id", "top_link_step"),
    "agenda_item_votes": ("agenda_item_id", "vote_id"),
}


def vote_link_review_refusals(manifest: dict[str, Any], generation_dir: Path, repo_root: Path, full_commit: str) -> list[str]:
    """Owner decision 6, amended 2026-11-21 (docs/plans/vote-pr-c.md, section 5):
    every link of a contested vote (two or more TOPs, or decided by a step after
    the plain match) needs a reviewed entry with verdict right, and no entry of
    an exported sitting may have stopped holding. The entries are those of
    ``scripts/reviewed_vote_links.json`` at the export's commit, a codebook
    input verify_export has matched; the links are the exported CSV rows."""
    relative = "scripts/reviewed_vote_links.json"
    text = build_revision.blob_text(repo_root, full_commit, relative)
    if text is None:
        return [f"the export's commit {full_commit[:12]} holds no {relative}; export from a commit that has it"]
    try:
        entries = reviewed_vote_links.parse(text, f"{relative} at commit {full_commit[:12]}")
    except reviewed_vote_links.ReviewedVoteLinksError as exc:
        raise ReleaseError(str(exc)) from exc
    names: dict[str, list[str]] = {}
    for entry in manifest.get("files") or []:
        if entry.get("kind") == "table_csv":
            names.setdefault(str(entry["name"]).partition("-")[0], []).append(entry["name"])
    rows: dict[str, list[tuple]] = {}
    for table, columns in _VOTE_LINK_TABLES.items():
        if len(names.get(table, [])) != 1:
            raise ReleaseError(f"the export lists {len(names.get(table, []))} {table} tables, not one; export it again")
        try:
            rows[table] = [tuple(row[column] for column in columns) for row in _csv_rows(generation_dir / names[table][0])]
        except (OSError, EOFError, KeyError, ValueError, csv.Error) as exc:
            raise ReleaseError(f"cannot read the exported {table} table ({exc}); export it again") from exc
    try:
        sittings = reviewed_vote_links.sittings_of_rows(rows["protocols"], rows["agenda_items"], rows["votes"], rows["agenda_item_votes"])
    except (KeyError, ValueError) as exc:
        raise ReleaseError(f"the exported vote links do not fit their agenda items ({exc}); export it again") from exc
    return reviewed_vote_links.gate(entries, sittings)["refusals"]


def vote_link_review_text(refusals: list[str]) -> str:
    return (f"{len(refusals)} vote link(s) need a review before release (docs/plans/vote-pr-c.md, section 5: "
            "every link of a contested vote has a right entry in scripts/reviewed_vote_links.json, and no entry stops holding)")


def withheld_cap_problem(changes: dict[str, Any], confirmed: list[str]) -> str | None:
    """D9 (ADR 0005): why a release that adds more than ``WITHHELD_CAP`` newly
    withheld Reden may not go out, or None. A pile-up is parser drift until the
    owner has read each one and names it (``WP/NR:REDE_ID``); the initial
    release has no previous one to drift from."""
    added = changes["withheld_reden_added"]
    if changes["initial_release"] or len(added) <= release_changes.WITHHELD_CAP:
        return None
    named = {value.replace(":", " ", 1).strip() for value in confirmed}
    missing = [f"{unit['document_number']}:{unit['rede_id']}" for unit in added
               if f"{unit['document_number']} {unit['rede_id']}" not in named]
    if not missing:
        return None
    return (f"this release adds {len(added)} newly withheld Reden, more than {release_changes.WITHHELD_CAP} (ADR 0005): "
            f"read each in withheld_units, then confirm with --confirm-withheld for: {', '.join(missing)}")


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


def origin_versions(repo_root: Path, run: Callable[..., Any]) -> set[str]:
    """Versions of the data-* tags origin holds (owner decision 2026-11-17: the
    latest release a --previous-manifest must be is origin's, not this clone's)."""
    prefix = "refs/tags/"
    result = run(
        ["git", "ls-remote", "--tags", "origin", f"{prefix}{release_version.TAG_PREFIX}*"],
        cwd=repo_root, env=build_revision.clean_env(), capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise ReleaseError(
            f"cannot ask origin for its release tags (git ls-remote failed: {result.stderr.strip() or 'no message'}); "
            "a --previous-manifest must be the latest of them"
        )
    refs = (line.rpartition("\t")[2].removesuffix("^{}") for line in result.stdout.splitlines())
    return {version for ref in refs if ref.startswith(prefix) and (version := release_version.version_of(ref[len(prefix):]))}


def remote_tag_exists(repo_root: Path, run: Callable[..., Any], tag: str) -> bool:
    """Whether origin holds refs/tags/<tag>. gh release create attaches to an
    existing tag and ignores --target, so a tag a failed run left must not be reused."""
    ref = f"refs/tags/{tag}"
    result = run(["git", "ls-remote", "--tags", "origin", ref], cwd=repo_root, env=build_revision.clean_env(), capture_output=True, text=True)
    if result.returncode != 0:
        raise ReleaseError(f"cannot ask origin for tag {tag} (git ls-remote failed: {result.stderr.strip() or 'no message'}); not publishing blind")
    return any(line.rpartition("\t")[2] in (ref, ref + "^{}") for line in result.stdout.splitlines())


def verify_export(exports_dir: Path, repo_root: Path) -> tuple[dict[str, Any], str, str, str]:
    """The manifest, the release version, the full commit of an export that may
    be released, and the sha256 of the datenstand.json bytes that were checked."""
    site = _site()
    manifest_path = exports_dir / "datenstand.json"
    parsed, raw = _read_json_bytes(manifest_path, "manifest")
    manifest = site.validate_manifest(parsed, str(manifest_path), subject=str(manifest_path))
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
    if not manifest.get("stammdaten"):
        raise ReleaseError(f"release {version} needs the MdB-Stammdaten (the manifest's stammdaten is null): rebuild the store with them, then export again")
    inputs = manifest.get("codebook_inputs")
    if not isinstance(inputs, dict) or set(inputs) != set(site.CODEBOOK_INPUT_FILES.values()):
        raise ReleaseError("the manifest does not name the authored codebook inputs")
    for relative, digest in sorted(inputs.items()):
        if build_revision.blob_sha256(repo_root, full, relative) != digest:
            raise ReleaseError(f"the authored input {relative} of the export differs from commit {commit}; rebuild from that commit")
    # validate_manifest admits exactly one licence file; it must be the bytes
    # the commit holds (hashed as a codebook input), and the manifest's licence
    # string must be that blob's short string.
    (licence,) = [entry for entry in manifest["files"] if entry["kind"] == "license"]
    license_file = site.CODEBOOK_INPUT_FILES["license"]
    if licence["sha256"] != inputs.get(license_file):
        raise ReleaseError(f"the export's {licence['name']} is not the {license_file} of commit {commit}; rebuild the export")
    try:
        short = site.license_short_string(build_revision.blob_text(repo_root, full, license_file) or "", f"{license_file} at commit {commit}")
    except RuntimeError as exc:
        raise ReleaseError(str(exc)) from exc
    if manifest.get("license") != short:
        raise ReleaseError(
            f"the export's licence string {manifest.get('license')!r} is not the short string of {license_file} at commit {commit}; "
            "rebuild the export without --data-license and without $BUNDESTAG_PULSE_DATA_LICENSE"
        )
    generation = exports_dir / manifest["generation"]
    listed = {entry["name"]: entry for entry in manifest["files"]}
    present = {path.name for path in generation.iterdir()} if generation.is_dir() else set()
    if present != set(listed):
        problems = [f"extra file {name}" for name in sorted(present - set(listed))] + [f"missing file {name}" for name in sorted(set(listed) - present)]
        raise ReleaseError(f"{generation} does not match the manifest: {', '.join(problems)}")
    for name, entry in sorted(listed.items()):
        path = generation / name
        if not path.is_file():
            raise ReleaseError(f"{path} is not a regular file")
        if path.stat().st_size != entry["bytes"] or _sha256(path) != entry.get("sha256"):
            raise ReleaseError(f"{path} does not match the manifest (size or sha256)")
    return manifest, version, full, hashlib.sha256(raw).hexdigest()


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


def staging_problem(staging: Path, manifest: dict[str, Any], manifest_sha256: str) -> str | None:
    """Why the staged copy is not the export verify_export checked, or None.
    The export may be replaced between the check and the copy (release item 5)."""
    changed = []
    if _sha256(staging / "datenstand.json") != manifest_sha256:
        changed.append("datenstand.json")
    for entry in manifest["files"]:
        path = staging / manifest["generation"] / entry["name"]
        if not path.is_file() or path.stat().st_size != entry["bytes"] or _sha256(path) != entry["sha256"]:
            changed.append(entry["name"])
    if not changed:
        return None
    return f"the export's {', '.join(changed)} changed after it was verified; let a running export finish, then export it again"


def _file_digests(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): (_sha256(path) if path.is_file() and not path.is_symlink() else "not a regular file")
        for path in directory.rglob("*")
        if not path.is_dir() or path.is_symlink()
    }


def directory_difference(existing: Path, built: Path) -> str | None:
    """How an existing release directory differs from the one just built, or None."""
    have, want = _file_digests(existing), _file_digests(built)
    problems = [f"extra {name}" for name in sorted(have.keys() - want.keys())]
    problems += [f"missing {name}" for name in sorted(want.keys() - have.keys())]
    problems += [f"different {name}" for name in sorted(have.keys() & want.keys()) if have[name] != want[name]]
    if not problems:
        return None
    return ", ".join(problems[:6]) + (f", and {len(problems) - 6} more" if len(problems) > 6 else "")


def build_release_directory(
    *, exports_dir: Path, manifest: dict[str, Any], manifest_sha256: str, version: str, changes: dict[str, Any], output_dir: Path
) -> tuple[Path, bool]:
    """The release directory and whether it already existed. An existing one is
    reused only when its files are exactly the ones this run builds (a dry run
    of the same release on the same day, or a publish whose gh call failed)."""
    release_dir = output_dir / release_version.tag_for(version)
    output_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(dir=output_dir, prefix=".building-"))
    try:
        shutil.copyfile(exports_dir / "datenstand.json", staging / "datenstand.json")
        for entry in manifest["files"]:
            _link_or_copy(exports_dir / manifest["generation"] / entry["name"], staging / manifest["generation"] / entry["name"])
        problem = staging_problem(staging, manifest, manifest_sha256)
        if problem:
            raise ReleaseError(problem)
        (staging / "changes.json").write_text(json.dumps(changes, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        (staging / "CHANGES.md").write_text(release_changes.render_markdown(changes), encoding="utf-8")
        _write_checksums(staging)
        if release_dir.exists() or release_dir.is_symlink():
            difference = directory_difference(release_dir, staging) if release_dir.is_dir() and not release_dir.is_symlink() else "not a directory"
            if difference:
                raise ReleaseError(
                    f"{release_dir} already exists and differs from this release ({difference}); a release directory "
                    "is never overwritten: remove it or use a fresh --output-dir"
                )
            shutil.rmtree(staging)
            return release_dir, True
        staging.rename(release_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return release_dir, False


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an immutable, versioned data release from an existing export (dry run by default).")
    parser.add_argument("--next-version", action="store_true", help="Print the version for a release made today and exit; build the export with --data-tag <version>.")
    parser.add_argument("--exports-dir", type=Path, help="The export to release: the directory holding datenstand.json and the g-<hash> generation.")
    parser.add_argument("--output-dir", type=Path, help="Where the release directory data-<version>/ is written (never overwritten).")
    parser.add_argument("--base-url", help="Public URL under which the release directory's contents will be served (printed as --data-base-url).")
    parser.add_argument("--initial", action="store_true", help="This is the first data release.")
    parser.add_argument("--previous-manifest", type=Path, help="datenstand.json of the previous release (for the changelog).")
    parser.add_argument("--changes", type=Path, help="Authored changes file (docs/data-changelog.md); required for every release but the first.")
    parser.add_argument(
        "--confirm-withheld", action="append", default=[], metavar="WP/NR:REDE_ID",
        help=f"Confirm one newly withheld Rede (repeatable, e.g. 18/1:ID1800100100) after reading it: a release that adds "
             f"more than {release_changes.WITHHELD_CAP} is refused unless every one of them is confirmed (ADR 0005).",
    )
    parser.add_argument(
        "--catalog", type=Path,
        help="The DIP catalog the build wrote (default: plenarprotokoll-catalog.json next to --exports-dir); --publish refuses "
             "while a v1 sitting it lists with XML is neither in the export nor on its exclusion record.",
    )
    parser.add_argument("--publish", action="store_true", help="Create the release through gh. Refuses an export without a licence string (ADR 0003).")
    return parser.parse_args(argv)


def run_release(args: argparse.Namespace, *, repo_root: Path, run: Callable[..., Any], out: Callable[[str], None], today: date) -> None:
    if not (args.exports_dir and args.output_dir):
        raise ReleaseError("--exports-dir and --output-dir are required")
    if args.initial == bool(args.previous_manifest):
        raise ReleaseError("say which release this is: --initial (the first) or --previous-manifest <datenstand.json> (not both)")
    # gh runs with cwd=repo_root and reads "path#label" as an asset label, so
    # every path it is given must be absolute and free of "#".
    args.exports_dir, args.output_dir = args.exports_dir.resolve(), args.output_dir.resolve()
    if "#" in str(args.output_dir):
        raise ReleaseError(f"--output-dir {args.output_dir} contains '#', which gh reads as an asset label separator; choose another directory")
    data_base_url = None
    if args.base_url:
        try:
            data_base_url = _site().resolve_data_base_url(args.base_url)
        except ValueError as exc:
            raise ReleaseError(str(exc)) from exc
    manifest, version, full_commit, manifest_sha256 = verify_export(args.exports_dir, repo_root)
    problem = withheld_export_problem(manifest, args.exports_dir / manifest["generation"])
    if problem:
        raise ReleaseError(problem)
    # D6 (owner, 2026-11-14): the bar holds for every published release, the
    # first one included; a dry run still builds the directory to rehearse it.
    waiting = awaiting_exclusions(manifest)
    if args.publish and waiting:
        raise ReleaseError(f"--publish refused: {awaiting_text(waiting)}. Acquire or reclassify them first.")
    # Owner decision 6 (docs/plans/t4-acquire.md): the bar also counts a v1
    # sitting that is neither stored nor excluded, which a run DIP stopped
    # partway leaves behind; a dry run still rehearses.
    catalog_path = (args.catalog or args.exports_dir.parent / _site().facts.CATALOG_FILENAME).resolve()
    unreleased = unreleased_sittings_problem(manifest, args.exports_dir / manifest["generation"], catalog_path)
    if args.publish and unreleased:
        raise ReleaseError(f"--publish refused: {unreleased}")
    unreviewed = vote_link_review_refusals(manifest, args.exports_dir / manifest["generation"], repo_root, full_commit)
    if args.publish and unreviewed:
        shown = "; ".join(unreviewed[:12]) + ("; …" if len(unreviewed) > 12 else "")
        raise ReleaseError(f"--publish refused: {vote_link_review_text(unreviewed)}: {shown}")
    tag = release_version.tag_for(version)
    released = remote_versions(repo_root, run) if args.publish else set()
    known = local_versions(repo_root, run) | released
    if version in known:
        raise ReleaseError(f"release {tag} already exists; releases are immutable, build a new version (--next-version)")
    # Origin's tags count for "older than the latest" and the previous manifest,
    # not for "already exists": a tag without a release gets remote_tag_exists'
    # message, which names how to delete it.
    on_origin = origin_versions(repo_root, run) if args.previous_manifest else set()
    newest = max(known | on_origin, key=release_version.version_key) if known | on_origin else None
    # The latest release a --previous-manifest must be: origin's tags, and under
    # --publish also gh's releases (gh may publish to another repository than
    # origin); never a local tag (owner decision 2026-11-17).
    published = on_origin | released
    searched = "origin's tags and gh's releases" if args.publish else "origin's tags"
    if newest and release_version.version_key(version) < release_version.version_key(newest):
        # A stale export would go out after a newer release, its changelog
        # computed backwards from that newer release's manifest.
        raise ReleaseError(f"release {version} is older than the latest known release {newest}; export again with a newer --data-tag (--next-version)")
    if args.initial and known:
        raise ReleaseError(f"--initial, but data releases already exist ({', '.join(sorted(known, key=release_version.version_key))}); give --previous-manifest instead")
    if args.publish and remote_tag_exists(repo_root, run, tag):
        raise ReleaseError(
            f"tag {tag} already exists on origin but has no release: gh release create attaches to it and ignores --target {full_commit}. "
            f"If a failed run left it, delete it (git push origin :refs/tags/{tag}) and run again; otherwise build a new version (--next-version)"
        )
    previous = None
    if args.previous_manifest:
        # JSON null too: read as None it would label this release the first one.
        previous = _read_json(args.previous_manifest, "previous manifest")
        problem = previous_manifest_problem(previous)
        if problem:
            raise ReleaseError(f"the previous manifest {args.previous_manifest} {problem}")
        # An older release's manifest gives false deltas and can hide a schema
        # change from the authored schema_changes guard (release item 4). A clone
        # that has not fetched, or holds a tag it never pushed, must not decide it.
        if not published:
            raise ReleaseError(f"--previous-manifest, but no data release is published ({searched}, git ls-remote --tags origin); give --initial for the first release")
        latest = max(published, key=release_version.version_key)
        if previous.get("tag") != latest:
            raise ReleaseError(
                f"the previous manifest {args.previous_manifest} is release {previous.get('tag')}, but the latest release ({searched}) is {latest}; "
                f"give the datenstand.json of {latest}"
            )
    authored = release_changes.load_authored(args.changes) if args.changes else None
    changes = release_changes.assemble(version=version, released=today, manifest=manifest, previous_manifest=previous, authored=authored)
    problem = withheld_cap_problem(changes, args.confirm_withheld)
    if problem:
        raise ReleaseError(problem)
    release_dir, reused = build_release_directory(
        exports_dir=args.exports_dir, manifest=manifest, manifest_sha256=manifest_sha256, version=version, changes=changes, output_dir=args.output_dir,
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
    out(f"release directory: {release_dir}" + (" (reusing the existing one: its files match this release)" if reused else ""))
    out("site build: --offline --data-manifest " + f"{release_dir / 'datenstand.json'} --data-base-url {data_base_url or '<where the release directory is served>'}")
    if not args.publish:
        out("dry run: nothing was published. The command --publish would run:")
        out(shlex.join(command))
        out("immutability checks: local tags only (best effort); --publish also asks gh for existing releases and origin for the tag. "
            "A --previous-manifest is checked against origin's release tags.")
        out(
            "hosting: GitHub release assets are flat, but the site links <base><generation>/<file>; "
            "a GitHub release URL as --base-url does not resolve until the site's link scheme or the host changes "
            "(TODOS: Site hosting plan). Use a host that keeps the directory layout of the release directory."
        )
        if waiting:
            out(f"--publish would refuse: {awaiting_text(waiting)}.")
        if unreleased:
            out(f"--publish would refuse: {unreleased}.")
        if unreviewed:
            out(f"--publish would refuse: {vote_link_review_text(unreviewed)}:")
            for refusal in unreviewed:
                out(f"  {refusal}")
        return
    result = run(command, cwd=repo_root, capture_output=True, text=True)
    if result.returncode != 0:
        raise ReleaseError(
            f"gh release create failed: {result.stderr.strip() or 'no message'}. The release directory {release_dir} is kept; "
            f"the same command publishes it once the cause is fixed. gh may have left a tag or a release behind: check with "
            f"git ls-remote --tags origin refs/tags/{tag} and gh release view {tag}, and delete what this run left "
            f"(gh release delete {tag} --cleanup-tag, or git push origin :refs/tags/{tag}; and git tag -d {tag} if a fetch "
            f"brought that tag into this clone) before running it again"
        )
    out(f"published: {result.stdout.strip()}")


def main(argv: list[str] | None = None, *, repo_root: Path = REPO_ROOT, run: Callable[..., Any] = subprocess.run, today: date | None = None) -> int:
    args = parse_args(argv)
    today = today or date.today()
    try:
        if args.next_version:
            print(release_version.next_version(today, local_versions(repo_root, run)))
            return 0
        run_release(args, repo_root=repo_root, run=run, out=print, today=today)
    except (ReleaseError, release_changes.ChangesError, RuntimeError, OSError) as exc:
        # OSError: git or gh not installed, a full disk; the release directory
        # was already rolled back by build_release_directory.
        message = str(exc)
        print(message if message.startswith("error: ") else f"error: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
