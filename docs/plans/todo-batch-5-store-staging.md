# TODO batch 5: store staging and the private directory

Status: plan, not implemented. Base: `main` 69ade54 (v0.26.1.0), branch `claude/todos-batching-subagents-aa0a61`.
Source: TODOS.md, section Architektur, heading "A.2 follow-up ship review: deferred findings", items (2) to (6).
Reviews: eng review and design review results are recorded at the end of this file.

## Scope

| Item | What is wrong today | Plan |
|---|---|---|
| (2) | `_replace_store` copies the old store's mode onto the staged copy but not its group. The staged copy is created in the private directory, so it gets that directory's group (BSD/macOS semantics, or a setgid directory on Linux) or the builder's egid. A store chgrp'ed to a web-server group with mode 0640 becomes unreadable to the server after the next rebuild or facts write. | Firm: keep the group, failing early when it cannot be kept. |
| (3) | The crash sweep in `_staged_store_path` deletes every `glob(f"{escape(name)}.*.tmp*")` in the private directory. All stores in one `OUTPUT/data/` share `.OUTPUT.private/`, so the sweep also deletes a prefix-named sibling store's staged copies (`name.old.<rand>.tmp`) and the writer lock of a store literally named `name.x.tmp` (`name.x.tmp.writer.lock`). Deleting a held lock file lets a second writer flock a fresh inode, so two writers run at once on that store. | Firm: match only this store's mkstemp names and their sidecars. |
| (4) | `private_dir` treats any store whose directory is named `data` as `OUTPUT/data`. `/data/x.sqlite` gives `/..private` (the root's name is empty); `~/stores/data/x.sqlite` gives `~/.stores.private`. | Fix the filesystem-root case only; keep the path-only rule; the rest is an owner decision (D3). |
| (5) | The private directory beside OUTPUT needs a writable parent on the store's file system. OUTPUT as a mount point (container bind mount, CI volume) or under a read-only parent fails every rebuild, facts write and export, with a bare `OSError` or the `st_dev` message. | A clearer error only; any override is an owner decision (D4). |
| (6) | The private directory and its `exports/` are created with `mkdir(mode=0o700, exist_ok=True)`, which silently accepts an existing symlink to a directory or a directory another user owns. The rebuild sweep then unlinks matching files there, and the export sweep (`_sweep_stale_work`) deletes everything in `exports/` except `.lock`, `rmtree` included. In a shared `/tmp` another user can plant `/tmp/.site.private -> /home/victim/...`. | Firm: refuse a symlink, a non-directory or a foreign owner, and repair group/other write bits on the builder's own directory (refuse if they cannot be removed), before anything is created, written or swept there. |

No item moves a stored figure, row or export file. (2) and (6) change only file metadata and refusals; (3) changes which leftover files are deleted; (4) moves the lock and staging location only for a store directly under `/data/` (none in the project layout). Measurement: see "Verification".

## Invariant kept: one store, one lock

`private_dir` stays a pure function of the resolved store path. Every process that writes a store (rebuild, standalone facts write) must compute the same writer-lock path for it, whatever `--output-dir` it was started with. An OUTPUT-aware derivation ("beside OUTPUT if the store is inside the OUTPUT this run was given, else beside the store") breaks that: `--database-path /srv/site/data/x.sqlite` run once with `--output-dir /srv/site` and once with `--output-dir /tmp/other` would take two different locks and could rebuild concurrently. It would also need `output_dir` threaded through `rebuild_database_from_entries`, `run_facts_engine`, `export_distribution_data` and their callers, which A3 edits. So (4) and (5) get no OUTPUT-aware derivation in this batch (D3, D4).

## Changes

### 1. `person_registry.py`

**1a. `private_dir` (main lines 37-47), item (4).** Add the filesystem-root guard:

```python
store = database_path.resolve()
if store.parent.name == "data":
    root = store.parent.parent
    if root.parent != root:          # OUTPUT/data, OUTPUT not the filesystem root
        return root.parent / f".{root.name}.private"
return store.parent / f".{store.name}.private"
```

`/data/x.sqlite` now gives `/data/.x.sqlite.private`: on the store's own volume, where a container's `/data` mount needs it. Every other input is unchanged. Update the docstring to say the `data` rule is a path convention, not a check that the parent is an OUTPUT (D3).

**1b. New `ensure_private_dir(path: Path) -> Path`, items (5) and (6).** Placed right after `private_dir`. It:

1. `os.lstat(path)` first. If the path does not exist (`FileNotFoundError`), create the parents with `path.parent.mkdir(parents=True, exist_ok=True)` and the leaf with `os.mkdir(path, 0o700)` (a concurrent creator's `FileExistsError` is fine), then `lstat` again. Checking before creating keeps a dangling symlink or a regular file at the path from being reported as a mkdir failure (outside voice O6). An `OSError` from the creation is re-raised as `OSError(exc.errno, hint)` from `exc`, keeping the errno (EACCES, EROFS, ENOSPC; eng review E1), so every caller's existing `OSError` path still applies. Hint for (5): `"{path}: the private directory for staged stores and the writer lock could not be created ({exc.strerror}); its parent must be writable and on the store's file system (docs/stable-ids.md)"`.
2. From the `lstat` result, raise `PermissionError` naming the path and the reason when it is a symlink (`S_ISLNK`), not a directory, or owned by a uid other than `_euid()` (a one-line module helper wrapping `os.geteuid()`, so a test can patch it without patching the global `os` module; outside voice O7).
3. If it is this user's directory but has group or other write bits (`st_mode & 0o022`), `os.chmod(path, 0o700)` and `lstat` again; refuse with `PermissionError` only when the bits are still there (a file system that does not keep POSIX modes, D6). Repairing instead of refusing is needed because a directory this code made itself can carry those bits: `pathlib.mkdir(parents=True)` creates intermediate directories with `0o777 & ~umask`, so `export_distribution_data`'s `work_dir.mkdir(mode=0o700, parents=True, ...)` (main line 3714, left untouched) creates `.OUTPUT.private` as 0775 under a umask of 002 (Debian/Ubuntu per-user groups, many CI images), and a refusal would stop every export there (outside voice O1). Entries another group member may have planted before the repair stay harmless: the sweeps unlink symlinks without following them and `_sweep_stale_work` never `rmtree`s through a symlink.
4. returns `path`.

Why `OSError` and `PermissionError`: `writer_lock` is inside `rebuild_database_from_entries`'s `except (..., OSError, ...)` (main line 1214, becomes `DatabaseRebuildError`); `run_facts_engine` and the export reach `PIPELINE_ERRORS` (`OSError` is in it); `politikfelder.write_atomic` and `preserve_corrupt` already fall back to the cache's own directory on `OSError`. No caller needs a new except clause.

Residual race, accepted: between `lstat` and use, only someone who can rename entries in the private directory's parent can swap the directory. In a sticky `/tmp` only the owner can do that; for a parent writable by another user the build is already compromised.

**1c. `writer_lock` (main lines 54-68), item (6).** Replace `path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)` with `ensure_private_dir(path.parent)`. The lock file is then opened inside a directory only this user can write, so it cannot be a planted symlink. `writer_lock_path` stays as it is.

### 2. `build_dip_pulse_site.py`

**2a. `_staged_store_path` (main lines 1218-1235), items (3), (6) and the early half of (2).**

- `staging = registry.ensure_private_dir(registry.private_dir(database_path))` (defence in depth; the lock holder already checked it in `writer_lock`).
- The sweep becomes an exact match:

  ```python
  #: A staged copy is mkstemp's ``<store>.<random>.tmp`` (the random part never
  #: holds a dot), plus SQLite's sidecars of a crashed run.
  def _is_staged_copy(store_name: str, candidate: str) -> bool:
      return re.fullmatch(re.escape(store_name) + r"\.[^.]+\.tmp(?:-journal|-wal|-shm)?", candidate) is not None
  ```

  The sweep iterates `staging.iterdir()` and calls `unlink(missing_ok=True)` on every entry whose name passes `_is_staged_copy(name, entry.name)`. `unlink` on a symlink removes the link, never its target. `iterdir` + `fullmatch` instead of `glob` avoids glob's platform case rules; `re.escape` keeps store names with glob characters working (`a[1].sqlite`). The module-level helper sits directly above `_staged_store_path`. This was the only use of the `glob` module in the file; leave `import glob` (main line 74) in place rather than edit the import block, which A3 touches at 265e407 lines 93 and 106. A later cleanup can drop it.
  The middle segment is "one or more non-dot characters", not mkstemp's private 8-character alphabet, so the code does not pin a CPython detail; a test pins that a name `_staged_store_path` really produces passes the predicate. The existing fixtures `store.sqlite.crashed.tmp` and `a[1].sqlite.crashed.tmp-journal` still match, so no existing test changes.
- After `mkstemp`, apply the store's group to the fresh empty file (`_keep_store_group(temporary, database_path)`, 2b). On failure, unlink the temp file and raise `DatabaseRebuildError` before any persisting starts, so a group that cannot be kept costs no multi-minute rebuild. SQLite writes the staged store into this inode (`sqlite3.connect` on the existing file, and `backup()` in the facts path), so the group stays on it.
- The `st_dev` message gets the (5) hint: `"... could not replace it atomically; OUTPUT's parent must be on the store's file system (an OUTPUT that is a mount point is not supported yet, docs/stable-ids.md)"`.

The call `temp_path = _staged_store_path(database_path)` at main line 1305 is not touched.

**2b. New `_keep_store_group(temp_path, database_path)` and `_replace_store` (main lines 1238-1242), item (2).**

```python
def _keep_store_group(temp_path: Path, database_path: Path) -> None:
    """Give the staged copy the group of the store it will replace (D1, D2)."""
    if not database_path.exists():
        return                         # D2: a first store keeps the group it was created with
    gid = database_path.stat().st_gid
    if temp_path.stat().st_gid != gid:
        try:
            os.chown(temp_path, -1, gid)
        except PermissionError as exc:   # D1: refuse, the store stays as it is
            raise DatabaseRebuildError(
                f"{database_path} belongs to group {gid}, which this user cannot give the rebuilt store; "
                "add the builder to that group or chgrp the store, then rerun"
            ) from exc
```

`_replace_store` calls `_keep_store_group` again (the operator may chgrp the store during a build; a no-op otherwise), then the existing `os.chmod`, then `replace`. It also unlinks `temp_path` on any exception before re-raising: today the rebuild path calls `_replace_store` outside its `try`, so a failing swap leaves the staged copy (full speech text) until the next sweep. `_write_facts_staged` already unlinks; a second `unlink(missing_ok=True)` is harmless. Docstring: "the store keeps the file mode and group it had".

The function bodies change; their call sites (main 1403 and 12835) do not.

**2c. `_export_lock` (main lines 3204-3206), item (6).** Replace `work_dir.mkdir(mode=0o700, parents=True, exist_ok=True)` with `registry.ensure_private_dir(work_dir.parent)` then `registry.ensure_private_dir(work_dir)`. `_export_lock` runs before `_sweep_stale_work`, so a symlinked or foreign `exports/` is refused before anything in it is deleted. `export_distribution_data`'s own `work_dir.mkdir(...)` and `st_dev` check (main 3714-3716) are left alone (they sit between two A3 hunks): through a symlinked private directory that mkdir can create one empty `exports/` directory in the link's target before `_export_lock` refuses. Accepted: no file is written or deleted there, and in a normal build `writer_lock` (rebuild or facts) refuses the same directory first.

**2d. Scope addition, if D5 = fold in: `_write_csv` (main lines 3285-3320).** Every table CSV of a published export generation is mode 0600, because `_write_csv` writes through `mkstemp` and renames the file in unchanged. Measured on main 2026-11-01 with the `ExportDistributionDataTests` fixture: all 24 `<table>-local.csv.gz` files are 0600; `datenstand.json`, `DATA.md`, the recipe CSVs and the SQLite `.gz` are 0644; the generation directory is 0755. A web server running as another user serves the table downloads as 403. Fix: `os.fchmod(fd, 0o644)` right after `mkstemp` (a fixed mode that ignores the umask, as the precedent does; eng review E3), matching `politikfelder.write_atomic`'s `chmod(0o644)` ("the published caches are world-readable") and `_replace_store`'s first-store 0o644. This does not change a file's bytes, hashes or the manifest.

### 3. `politikfelder.py`, item (6)

`preserve_corrupt` (main 231-253) and `write_atomic` (main 270-320) replace `private.mkdir(mode=0o700, parents=True, exist_ok=True)` / `directory.mkdir(...)` with `registry.ensure_private_dir(...)`. Both already catch `OSError` and fall back to the cache's own directory, so a refused private directory now falls back instead of staging or sweeping through a symlink. In `preserve_corrupt` the fallback directory (`path.parent`) is not a private directory and keeps its plain `mkdir`: call `ensure_private_dir` only for the first candidate.

### 4. Docs

`docs/stable-ids.md`, the "nonblocking kernel writer lock" paragraph (main line 74): the replacement keeps the store's mode and group, and a group the builder cannot set stops the build before it persists; the crash sweep takes only this store's staged copies; the private directory must be a real directory owned by the builder, or the build stops, and group/other write bits on it are removed (a file system that cannot keep them, such as some bind mounts, is refused); a store directly under `/data/` keeps its private directory in its own directory; the private directory needs a writable parent on the store's file system, so an OUTPUT that is a mount point is not supported yet. No README or DATA.md sentence is wrong after the change (README line 266 names `.OUTPUT.private/`, still true). If D5 is folded in, nothing in DATA.md names file modes.

TODOS.md, VERSION and CHANGELOG are left to the implementing session / ship run: there, mark (2), (3), (6) done, (4) partly done (root case) and (5) as "clear error; override waits on hosting", and record D3/D4 outcomes.

## Tests

All new tests go in a new file `tests/test_private_staging.py` (no A3 overlap). It imports `RegistryFixture` from `tests/_registry_fixture.py` and `report` from `tests/test_registry_contracts.py` (a function, so no test class is collected twice), and defines its own `rebuild` helper (three lines, as in `RegistryContractTests.rebuild`). Each test carries the repo's `# Value: protects=...; fails_when=...; why_new=...; seam=...` comment.

Item (2):
- `test_a_rebuild_and_a_facts_write_keep_the_store_group`: pick the first gid from `os.getgroups()` other than the store's for which `os.chown` on a scratch file succeeds (macOS lists groups such as `everyone` that a chown may refuse; eng review E2); skip with a reason when none works, `os.chown(db, -1, gid)` and `chmod 0640`, rebuild: gid and mode kept; then a facts write through `build.run_facts_engine` with a changed snapshot (or `_write_facts_staged` directly): gid and mode kept.
- `test_a_group_the_builder_cannot_set_stops_before_persisting`: patch `build.os.chown` to raise `PermissionError` and make the staged copy's gid differ (patch `_keep_store_group`'s `stat` read, or chown the store to a supplementary group first, skip as above). Expect `DatabaseRebuildError` naming the group, the previous store byte-identical, no `_is_staged_copy` leftovers, and `pulse_store.persist_report` never called (mock with `wraps`).
- `test_a_failing_swap_removes_the_staged_copy`: patch `Path.replace` for the staged path to raise `OSError`; expect `DatabaseRebuildError`, store unchanged, private directory without staged copies.

Item (3):
- `test_the_sweep_takes_only_this_stores_staged_copies`: two stores `data/name.sqlite` and `data/name.sqlite.old` in one OUTPUT (shared private directory). Plant `name.sqlite.old.abcd1234.tmp` (sibling's staged copy), create a store literally named `name.sqlite.x.tmp` and take/release its writer lock once (its lock file `name.sqlite.x.tmp.writer.lock`), plant `name.sqlite.crashd01.tmp` + `-wal`. Rebuild `name.sqlite`: own leftovers gone; sibling copy and the other lock file still there, lock inode unchanged (`st_ino` before/after).
- `test_a_real_staged_name_passes_the_sweep_predicate`: `_staged_store_path` under the writer lock; its name and `name + "-journal"` pass `_is_staged_copy`; `name.sqlite.writer.lock`, `name.sqlite.old.abcd1234.tmp` and `exports` do not. Pins the coupling to mkstemp's naming.
- Existing `test_crash_sweep_escapes_the_store_name_and_takes_every_sidecar` and `test_replay_sweeps_stale_temp_copies_and_keeps_the_store_mode` keep passing unchanged (their 7-letter `crashed` segment has no dot).

Item (4):
- `test_private_dir_for_each_input_shape`: under one temp OUTPUT, the store `OUTPUT/data/bundestag-pulse.sqlite`, `politikfelder.cache_path(OUTPUT)`, `antrag_text.cache_path(OUTPUT)` and `OUTPUT/data/exports` all map to `.OUTPUT.private` beside OUTPUT; `X/store.sqlite` maps to `X/.store.sqlite.private`. For the root case, assert on the pure path computation for `Path("/data/x.sqlite")` (no filesystem write): `/data/.x.sqlite.private`, not `/..private`. `resolve()` of a nonexistent absolute path is fine on macOS and Linux; if `/data` is a symlink on the runner the test resolves it the same way the code does, so compare against `private_dir`'s own resolution of the parent.

Items (5) and (6):
- `test_a_symlinked_private_dir_is_refused_before_the_sweep`: replace `.site.private` by a symlink to a decoy directory holding `bundestag-pulse.sqlite.decoy01.tmp`; a rebuild raises `DatabaseRebuildError` mentioning "symbolic link"; the decoy file is still there; the store is unchanged.
- `test_a_symlinked_exports_dir_is_refused_before_the_export_sweep`: a real private directory whose `exports` entry is a symlink to a decoy directory with a file and a subdirectory; `export_distribution_data` raises; decoy contents intact.
- `test_a_foreign_private_dir_is_refused_and_a_group_writable_one_repaired`: seam: patch `person_registry._euid` to return another uid, and `ensure_private_dir` raises `PermissionError`; separately `chmod 0o775` an own directory, and `ensure_private_dir` returns it with mode 0700. A third case patches `os.chmod` in `person_registry` to a no-op (a file system that ignores modes) and expects the refusal. A fourth puts a regular file, and a fifth a dangling symlink, at the path: both are refused as "not a directory" / "symbolic link", not reported as a mkdir failure.
- `test_an_export_under_umask_002_creates_a_usable_private_dir`: under `os.umask(0o002)` (restored in cleanup), run the export on a fresh OUTPUT before any `writer_lock` has created `.OUTPUT.private`; it succeeds and the private directory and `exports/` end at 0700. Fails if step 3 above refuses instead of repairing (outside voice O1).
- `test_the_vorgang_cache_falls_back_when_the_private_dir_is_refused`: symlinked private directory; `politikfelder.save_cache` writes the cache via the cache's own directory; the decoy target receives no temp file. (Mirrors the existing `test_save_falls_back_when_the_private_directory_is_not_writable`.)
- `test_an_unwritable_private_dir_parent_names_the_requirement`: an OUTPUT whose parent is `chmod 0o555` (skip when running as root); a rebuild raises `DatabaseRebuildError` whose text contains "parent must be writable" and "docs/stable-ids.md". The cross-file-system branch stays untested (needs two file systems), as today.

D5 (if folded in):
- `test_every_published_export_file_is_world_readable`: with the `ExportDistributionDataTests`-style fixture, every file in the published generation and `datenstand.json` has `mode & 0o044 == 0o044`. Fails today on the 24 table CSVs.

Regression contract (eng review E5): these existing tests cover behaviour this plan touches and must pass unchanged, without edits:
- `test_registry_contracts.py`: `test_replay_sweeps_stale_temp_copies_and_keeps_the_store_mode` (sweep + mode), `test_crash_sweep_escapes_the_store_name_and_takes_every_sidecar` (glob characters, sidecars, bystander kept), `test_staging_and_lock_stay_outside_the_published_tree` (`.site.private` location for the default layout), `test_equivalent_store_paths_share_one_writer_lock` (symlink and `..` spellings share one lock; the private directory itself is real, so the new `lstat` check passes), the two `_damage_after_facts` / integrity tests (no staged leftovers).
- `test_politikfelder.py`: `test_save_falls_back_when_the_private_directory_is_not_writable` (a 0500 private directory has no write bits, passes the new check, then the write fails and falls back as before) and the read-only-parent case (mkdir fails, `OSError`, fallback).
- `test_daten_export.py`: the `export_work_dir(...).iterdir() == []` assertions and the `.lock` tests.
Intended differences: none of these change. The only intended behaviour changes are the ones the new tests pin.

Run: the new file, then the full suite (`python3 -m unittest discover -s tests`, about 70 s), with local python3 and with uv 3.13.12 (memory note "Local Python vs CI").

## Verification (pre-release rule: old vs new)

No figure is expected to move. To show it on real data, on the reference replay cache (`~/agent-runs`, copied, never in place):

1. On `main`: `--offline --repersist` into a copy; record the store's `_content_digests` (as `compare_store_values` computes them), `stat` mode/gid, `registry.writer_lock_path(store)` and the private directory listing after the run.
2. Same on the branch.
3. Expect: equal content digests, equal mode and lock path, no staged leftovers. If D5 is folded in, also run the export on both with `--force-export`: identical file hashes and manifest `files[].sha256`; only the table CSV modes change, 0600 to 0644. Without the force, `_manifest_reusable` (main lines 3739-3741) keeps the previous generation, because file modes are not part of `inputs_hash`, and a generation already published at 0600 is not rewritten until the inputs change (outside voice O2). Nothing is published yet, so no repair path for old generations is planned; the D5 test runs a fresh export.

Report the numbers in the commit message; per the pre-release rule a moved figure would need old/new values and a reason, and none is expected.

## Conflict surface vs A3

Checked 2026-11-01 with `git diff main...worktree-a3-plan -- <file>` (A3 tip 50e7dfd). That diff runs from the merge base 265e407 (v0.26.0.0), not from main, so A3's hunk numbers are 265e407 line numbers. Main matches them up to about line 1260 of `build_dip_pulse_site.py` and is 41 lines further down near `export_distribution_data` (3629 at 265e407, 3670 on main) and 44 near the facts write (12775 vs 12819).

Semantic check: A3's added lines (`^+`) contain no new call of `private_dir`, `ensure_private_dir`, `writer_lock`, `_staged_store_path`, `_replace_store`, `export_work_dir`, `_export_lock`, `_sweep_stale_work`, `write_atomic` or `preserve_corrupt`, and no `mkstemp`, `.private`, `os.chown` or `st_gid` in `scripts/`. So no A3 code path relies on the old behaviour, and no new caller would miss the new checks.

| File | This plan touches (main lines) | Nearest A3 hunks (265e407 numbering) | Clearance |
|---|---|---|---|
| `scripts/build_dip_pulse_site.py` | `_staged_store_path` + new `_is_staged_copy` (1218-1235), new `_keep_store_group` and `_replace_store` (1238-1242 plus about 20 new lines) | `@@ -1125,9` (`_read_roster_rows`, ends 1134); `@@ -1280,7` (`_rebuild_database_from_entries`, drops `roster_rows` at 1283) | about 80 lines before, about 38 lines after. New lines are inserted between 1236 and 1243, so A3's 1280 hunk only shifts. Not touched: the `_staged_store_path` call at 1305 (between A3's -1280 and -1318 hunks) and the `_replace_store` call at 1403 |
| `scripts/build_dip_pulse_site.py` | `_export_lock` (3204-3206) | `@@ -3090,6` (`_inputs_hash`, ends about 3096); `@@ -3640,7` (`export_distribution_data` signature) | about 108 lines after, about 430 lines before (main numbering 3681). The body of `export_distribution_data` (A3 hunks at main about 3681, 3733, 3762) is deliberately not touched |
| `scripts/build_dip_pulse_site.py` | `_write_csv` `fchmod` (3293), only if D5 | `@@ -3090,6` and `@@ -3640,7` | about 200 lines either side |
| `scripts/person_registry.py` | `private_dir` (37-47), new `ensure_private_dir` (after 47), `writer_lock` (54-68) | `@@ -11,6` (context lines 11-16, `import sqlite3` to `from stable_ids`, adds one line); `@@ -576,8` onward | The import hunk is the risk: this plan adds `import os` and `import stat`. Put them right after `import fcntl` (line 6), so at least three unchanged lines separate them from A3's hunk. The code edits are about 500 lines before A3's 576 hunk |
| `scripts/politikfelder.py` | `preserve_corrupt` (235-237), `write_atomic` (281-283) | `@@ -98,9` (closed list, about 98-106) | about 130 lines |
| `docs/stable-ids.md` | paragraph at line 74 | `@@ -1,6` and `@@ -45,7` (single long lines) | about 28 lines; one paragraph per line, so a different line |
| `tests/test_private_staging.py` | new file | none | none |
| `tests/test_registry_contracts.py`, `tests/test_daten_export.py`, `tests/test_politikfelder.py` | not edited | A3 edits each | none |

The same-file risk is in `build_dip_pulse_site.py` and `person_registry.py` only, and in both the nearest A3 hunk is at least 38 lines away from any edited line. Whichever branch lands second rebases with no textual conflict expected; the implementer re-runs `git diff main...worktree-a3-plan` before committing in case A3 moved.

## Open owner decisions

The implementer takes each recommendation unless the owner says otherwise. Each is the owner's call because it fixes a deployment assumption, adds or rejects a knob, or changes scope.

- **D1. The store's group cannot be set (item 2).** Refuse before persisting, store untouched (recommended), or warn and swap anyway. Why refuse: a swapped-in store the web server cannot read breaks the public download silently; the operator fixes the cause once (add the builder to the group, or chgrp the store). Cost: a host where the old store's group came from BSD directory inheritance and the builder is not a member now fails every rebuild until fixed. That configuration worked before v0.19.0.0, when the staged copy was created in `data/` and inherited the group. The refusal is early (in `_staged_store_path`), so it also stops an `--offline --repersist` that would have changed nothing (`keep_if_unchanged=True`, main line 1949) and a facts write; on such a host no swap can keep the group, so failing every write the same way is the consistent rule (eng review E6). Two limits (outside voice O5): the store has been losing its group silently since v0.19.0.0, so on an affected host this turns a silent, figure-neutral metadata loss into a hard stop of every write until the operator acts; and the second `_keep_store_group` call in `_replace_store` can still refuse after a full persist, but only when someone chgrp'ed the store during the build. A chown refused with an errno other than EPERM is not swallowed; it propagates as an `OSError` and also stops the write. If the owner prefers warn-and-swap, the change is to print a warning instead of raising in `_keep_store_group`.
- **D2. Group of a first store.** Leave it as created (recommended): a first store is 0644, so its group grants nothing extra. Alternative: chown it to `data/`'s group, best effort.
- **D3. Store under a directory named `data` that is not `OUTPUT/data` (item 4).** Recommended: keep the path-only rule, fix only the filesystem-root case, and document the rule as a naming convention (`~/stores/data/x.sqlite` stages in `~/.stores.private`, which is outside any published tree and so is surprising but not harmful). Rejected for now: deriving from the run's OUTPUT, which breaks "one store, one lock". Be clear about how little this delivers (outside voice O3): the root guard helps only a store directly under `/data/` (a container volume mounted there); `/srv/data/x.sqlite` or `/app/data/x.sqlite` still stage in `/.srv.private` or `/.app.private`, which fails for a non-root builder and fails the `st_dev` check for a mounted `data/`. Second option: drop the root guard as well and defer all of (4) with no code change; it costs nothing to add later. Recommended stays "fix the root case", because `/..private` is a plainly wrong path, the change is three lines, and only `/data/*` stores (none in the project layout) move their lock. Alternative for the hosting session: a marker check (for example `OUTPUT/protocols/` exists), or decoupling the lock from the staging directory by flocking the store's directory inode (tested 2026-11-01 on macOS: a second fd's nonblocking flock on a directory is refused), after which the staging directory could follow OUTPUT freely.
- **D4. OUTPUT as a mount point or under a read-only parent (item 5).** Recommended: no override in this batch, only the clearer errors; decide with hosting. Every same-file-system fallback lies inside OUTPUT, that is in the published tree (`OUTPUT/.private/` is served unless the deploy excludes dotfiles), which A.2 05 removed on purpose. If a knob is wanted later, prefer one environment variable (for example `POLIWATCH_PRIVATE_DIR`, an absolute directory on the store's file system) over a CLI flag: it reaches every caller of `private_dir` (rebuild, facts write, export, the two caches) without threading a parameter through A3-edited signatures, and every process of one deployment sees the same value, which keeps one lock per store. Not added now: a new env var is a deployment contract.
- **D5. Scope: export table CSVs published at mode 0600 (found while planning, not in items 2-6).** Recommended: fold into this batch as change 2d plus its test. It is the same failure as (2) (a published file the web server cannot read), one line, about 200 lines from any A3 hunk, and changes no byte or hash. Alternative: file it in TODOS.md under the same heading and leave it.
- **D6. Private directory ownership rule (item 6).** Recommended: owner must be the builder's euid; group/other write bits are removed by `chmod 0o700`, refused only when they cannot be removed. This refuses a private directory shared by a team of builders with different uids. Pre-release there is one builder; revisit with hosting if a shared build account is not used. It also refuses root (a container build running as root) over a private directory a normal user created, which is deliberate: root following a directory another user controls is the classic attack (eng review E4). Third limit (outside voice O4): file systems that do not keep POSIX owners or modes (Docker Desktop virtiofs bind mounts, CIFS, NFS with root squash, vfat) can report a fixed 0777 mode or a mapped uid; step 3's repair then has no effect and every write there is refused. Those are exactly the mount layouts of item (5), so the refusal text names this case and docs/stable-ids.md states it; any relaxation (for example an explicit opt-out) is a knob for the hosting session, with D4.

## Review log

### Eng review (`gstack-plan-eng-review`, 2026-11-01, target: this file)

How it ran: the planner ran it as a subagent. No AskUserQuestion tool was available, so every decision took the recommended option and is logged here; the owner's real calls are D1-D6 above. Skipped: the gstack upgrade prompt (offered 1.91.176.0 to 1.91.379.0, needs network), the /office-hours prerequisite offer (a small TODO batch), and the Codex outside voice (it would go online, which this run was told not to do). The native fallback (a Claude subagent, read-only) ran instead. Did not persist: gstack's state directory `~/.gstack/` is not writable from this sandbox (`touch: ... Operation not permitted`), so the required review log, the test-plan artifact and the task JSONL were not written there. Their content is in this file.

**Step 0, Scope Challenge:** scope accepted as-is. 5 files (3 scripts, 1 doc, 1 new test file), 0 new classes, so the complexity gate did not trip. What exists already: `politikfelder.write_atomic` sets 0644 and falls back on `OSError` (precedent for 2d and 1b); `_export_lock` already runs before `_sweep_stale_work`; `writer_lock` is the first creator of the private directory. Nothing in TODOS.md blocks this plan. `git log main --since=2026-10-18` shows no change to the staging code since v0.19.0.0 (fe7143f), and no branch has `ensure_private_dir`, `_is_staged_copy` or a chown, so none of this is done yet.

Reality rows:
- REALITY: premise-table pass. The premises are the five TODO defects, read in the code: `private_dir` (person_registry.py:37-47), the sweep glob (build_dip_pulse_site.py:1231), `_replace_store` mode-only (1238-1242), and the bare mkdirs (person_registry.py:59, build_dip_pulse_site.py:3205, politikfelder.py:237/283). Export CSV 0600 was measured. unverified=0.
- REALITY: already-done pass. No commit since fe7143f touches these functions (local `git log`; no fetch, offline run).
- REALITY: surface-check pass. No new CLI flag or env var. The test command `python3 -m unittest discover -s tests` matches CONTRIBUTING.md:8 and ci.yml:28.
- REALITY: binding-decisions pass. `gstack-decision-search --scope branch` returns nothing. The A.2 05 decision (nothing private in the published tree) is kept: D4 rejects an in-OUTPUT fallback.
- REALITY: numbers pass. 24 table CSVs at 0600 [measured: ExportDistributionDataTests fixture, main 69ade54]. The mkstemp alphabet and length 8 [measured: python3 3.13.2]. Replay about 245 s [estimated: memory note a2-07].
- REALITY: deferred-asks pass. No linked issue. Parts of TODO items (4) and (5) are deferred as D3/D4 with reasons.
- REALITY: pr-count pass. No `.gstack/ship-policy.json`, so one PR.

**Findings (four sections)**

| ID | Section | Finding | Severity / confidence | Disposition |
|---|---|---|---|---|
| E1 | Code quality | Re-raising every mkdir `OSError` as `PermissionError` lost the errno (EROFS, ENOSPC) | P2 / 8 | accepted (auto, recommended): keep the errno, 1b step 1 |
| E2 | Tests | `os.getgroups()` can list groups a chown refuses (macOS `everyone`) | P2 / 7 | accepted: probe chown on a scratch file, skip when none works |
| E3 | Code quality | 2d's fixed 0644 ignores the umask, while DATA.md and others follow it | P3 / 7 | accepted as a note: same as the `write_atomic` precedent |
| E4 | Architecture | The owner check refuses root over a user-created private directory (container as root) | P2 / 8 | accepted as a note in D6 |
| E5 | Tests | Regression contract for the existing tests the plan touches was not stated | P2 / 8 | accepted: list added under Tests |
| E6 | Architecture | The early group refusal also stops no-op `--repersist` (`keep_if_unchanged=True`, 1949) and facts writes | P2 / 8 | accepted as a note in D1 |

Performance: no issues. The sweep lists one small directory, plus one `lstat` and at most one `chown`/`chmod` per write.

**Code paths and coverage (planned tests)**

```
CODE PATHS
[+] person_registry.private_dir
  ├── data/ store, normal OUTPUT  ──── [★★ TESTED] test_staging_and_lock_stay_outside_the_published_tree + new input-shape test
  ├── data/ directly under /       ─── [GAP→NEW] test_private_dir_for_each_input_shape (pure path)
  └── other store                  ─── [★★ TESTED] existing + new input-shape test
[+] person_registry.ensure_private_dir
  ├── absent → create (0700 leaf)  ─── [★★ TESTED] every rebuild test
  ├── create fails (EACCES/EROFS)  ─── [GAP→NEW] test_an_unwritable_private_dir_parent_names_the_requirement
  ├── symlink                      ─── [GAP→NEW] symlinked private dir / exports tests
  ├── not a directory              ─── [GAP→NEW] add a row to the foreign-owner test (regular file at the path)
  ├── foreign uid                  ─── [GAP→NEW] _euid patched
  ├── own + write bits → chmod     ─── [GAP→NEW] 0775 repaired; umask-002 export test
  └── chmod has no effect → refuse ─── [GAP→NEW] os.chmod no-op case
[+] _staged_store_path
  ├── st_dev differs               ─── [GAP] untestable without two file systems (as today)
  ├── sweep: own copies + sidecars ─── [★★★ TESTED] existing crash-sweep tests
  ├── sweep: sibling / foreign lock ── [GAP→NEW] test_the_sweep_takes_only_this_stores_staged_copies
  └── group kept / refused early   ─── [GAP→NEW] the two group tests
[+] _replace_store
  ├── mode kept                    ─── [★★ TESTED] existing
  ├── group kept                   ─── [GAP→NEW]
  └── swap fails → temp removed    ─── [GAP→NEW] test_a_failing_swap_removes_the_staged_copy
[+] _export_lock → _sweep_stale_work
  └── symlinked exports/ refused   ─── [GAP→NEW]
[+] politikfelder.write_atomic / preserve_corrupt
  ├── refused private dir → fallback ─ [GAP→NEW] vorgang-cache fallback test
  └── unwritable 0500 private dir  ─── [★★ TESTED] existing
[+] _write_csv (D5)
  └── published mode 0644          ─── [GAP→NEW] test_every_published_export_file_is_world_readable
USER FLOWS (operator): rebuild, facts write, export, cache save; each error path ends in "error: ..." and exit 1 (PIPELINE_ERRORS / DatabaseRebuildError), never a traceback
```

Test gaps found: 14, all with a planned test, except `st_dev` (untestable, unchanged). Tests made obsolete: none.

**Failure modes:** a group the builder cannot set gives a clear error and leaves the store untouched. A refused private directory gives a clear error with the reason; the caches fall back silently, which is the existing and intended behaviour. The cross-file-system case gives a clear error. Critical gaps (untested, unhandled and silent): 0.

**Outside voice:** Codex was skipped (it needs network, which this run forbids). Native fallback: a Claude subagent (Plan type, sonnet, read-only) reported before the five-minute timer. Strictly, its report came back as a direct hand-back message, so under the skill's rule it earns no outside-coverage credit. Its findings were still used:

| ID | Finding | Severity | Disposition |
|---|---|---|---|
| O1 | A refusal of group-writable bits breaks exports under umask 002, because `pathlib.mkdir(parents=True)` creates `.OUTPUT.private` at `0777 & ~umask` (main line 3714) | High | accepted: repair with `chmod 0o700`, refuse only if it does not take; umask test added |
| O2 | D5 does not rewrite a reused 0600 generation (`_manifest_reusable`; mode is not in `inputs_hash`) | Medium | accepted: verification uses `--force-export`; no repair path, since nothing is published |
| O3 | The (4) root guard helps only `/data/*`; `/srv/data` still fails | Medium | accepted as a note: D3 now offers "defer all of (4)" as the second option; the recommendation is unchanged |
| O4 | File systems without POSIX modes or owners (virtiofs, CIFS, NFS root squash) would always be refused | Medium | accepted as a note: D6 and the docs/error text; relaxation goes with D4 |
| O5 | D1 hardens a silent degradation into a hard stop; a late refusal is still possible | Medium | accepted as a note in D1; the owner's call |
| O6 | Rewrapping `FileExistsError` gives the wrong hint for a dangling link or regular file | Low | accepted: `lstat` before mkdir |
| O7 | Patching `person_registry.os.geteuid` patches the global `os` | Low | accepted: `_euid()` helper |

The subagent also confirmed the A3 conflict analysis, the `report` import surviving A3, and the sweep regex.

**TODO proposals** (TODOS.md not edited by this planner; the implementer records them): (a) the D3/D4 leftovers: an OUTPUT-aware or override-based private directory, or the directory-inode flock, for the hosting session; (b) if D5 is deferred, the 0600 table CSVs; (c) remove the now-unused `import glob` after A3 lands. Auto-decision: A) add each to TODOS.md at implementation time.

**NOT in scope:** an OUTPUT-aware private directory and a `POLIWATCH_PRIVATE_DIR` override (D3, D4: they break one lock per store or add a deployment contract); repairing already published 0600 generations (nothing is published); a TOCTOU-free `dir_fd` implementation (the sticky `/tmp` makes `lstat` sufficient); TODO items (7) to (13) of the same heading.

**Parallelization:** sequential implementation, no parallelization opportunity (one module family, shared test file).

## Implementation Tasks

- [ ] **T1 (P2, human: ~1h / CC: ~10 min)**: person_registry: `ensure_private_dir`, `_euid`, the `private_dir` root guard, and `writer_lock` using the new helper. Surfaced by items (4) and (6), E1, O1, O6, O7. Files: scripts/person_registry.py. Verify: new tests in tests/test_private_staging.py.
- [ ] **T2 (P2, human: ~1h / CC: ~10 min)**: build: `_is_staged_copy`, `_staged_store_path` (ensure, exact sweep, early group, hint), `_keep_store_group`, `_replace_store` (group plus cleanup), and `_export_lock` using the new helper. Surfaced by items (2), (3) and (6). Files: scripts/build_dip_pulse_site.py.
- [ ] **T3 (P2, human: ~20 min / CC: ~5 min)**: politikfelder fallbacks use `ensure_private_dir`. Surfaced by item (6). Files: scripts/politikfelder.py.
- [ ] **T4 (P2, human: ~2h / CC: ~20 min)**: tests/test_private_staging.py with all planned tests, then the full suite on python3 and uv 3.13.12. Surfaced by E2, E5, O1.
- [ ] **T5 (P3, human: ~20 min / CC: ~5 min)**: docs/stable-ids.md paragraph. Surfaced by the Docs section.
- [ ] **T6 (P2, only if D5, human: ~15 min / CC: ~3 min)**: `_write_csv` fchmod plus test. Surfaced by D5 and O2.
- [ ] **T7 (P2, human: ~30 min / CC: ~10 min, mostly replay wait)**: verification on the reference replay cache, old vs new. Surfaced by the pre-release rule.

**Completion summary**
- Step 0: Scope Challenge: scope accepted as-is
- Reality rows: 7/7 emitted, 0 unverified premises
- Architecture Review: 2 issues found (E4, E6)
- Code Quality Review: 2 issues found (E1, E3)
- Test Review: diagram produced, 14 gaps identified, all planned (plus E2 and E5)
- Performance Review: 0 issues found
- NOT in scope: written
- What already exists: written
- TODOS.md updates: 3 items proposed (auto: add at implementation)
- Failure modes: 0 critical gaps flagged
- Unresolved decisions: 0 in this review's ledger (owner decisions D1-D6 are recorded above with recommendations)
- Outside voice: Codex skipped (no network allowed); native Claude subagent completed, 7 findings, all folded in
- Parallelization: 1 lane, sequential
- Lake Score: N/A (no completeness-scored question was asked)

Review log fields, not persisted (sandbox denied `~/.gstack/`). For the caller to run:
PERSIST: ~/.claude/skills/gstack/bin/gstack-review-log '{"skill":"plan-eng-review","timestamp":"2026-11-01T00:00:00Z","status":"issues_open","unresolved":0,"critical_gaps":0,"issues_found":18,"mode":"FULL_REVIEW","commit":"69ade54"}'

### Design review (`gstack-plan-design-review`)

No UI scope, so the review was not applicable and stopped at UI scope detection (2026-11-01). The plan changes no page, component, interaction or design token. It changes only store staging, the private directory, file modes and operator error messages. The one user-visible effect is that, under D5, Daten table downloads become readable to a web server running as another user.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | not run | — |
| Outside Review | Codex skipped (needs network); native Claude subagent (Plan, sonnet) | Independent 2nd opinion | 1 | unavailable (native fallback completed, no outside credit) | 7 findings (1 High, 4 Medium, 2 Low), all folded in |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 (not persisted: `~/.gstack/` write denied by sandbox) | ISSUES OPEN (resolved in plan) | 18 issues (2 architecture + 2 code quality + 0 performance + 14 test gaps, all planned), 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | not applicable | no UI scope |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run | — |

- **OUTSIDE COVERAGE:** Codex plan review: skipped, because this run was not allowed to go online. Native in-host fallback: completed. It is no outside coverage.
- **VERDICT:** no review CLEAR. Eng review findings are folded into the plan, and the owner decisions D1-D6 above are open for the owner. The eng review log was not persisted: run the `PERSIST:` line in the eng review section to record it. eng review required

**UNRESOLVED DECISIONS:**
- D1-D6 (Open owner decisions above): each has a recommendation the implementer takes unless the owner overrides it. None was answered by the owner during this review.
