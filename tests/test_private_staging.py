"""The store's private directory and staged copies: group kept, the crash sweep
limited to one store's own files, a private directory that cannot redirect a
sweep, and export files a web server can read.

Kept apart from test_registry_contracts.py on purpose (the same area, another
branch edits that file)."""
from __future__ import annotations
import contextlib
import gzip
import io
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import _support  # noqa: F401
import _daten_fixture
import build_dip_pulse_site as build
import persist_dip_pulse_store as pulse_store
import person_registry as registry
import politikfelder
from _registry_fixture import RegistryFixture
from test_registry_contracts import report

READINESS = {"votes": "ready", "aw-profiles": "unavailable", "mp-roster": "ready"}


def _another_group(path: Path) -> int | None:
    """A group of this user other than ``path``'s that a chown may give a file
    (macOS lists groups such as ``everyone`` that a chown refuses), or None."""
    own = path.stat().st_gid
    probe = path.parent / f".probe-{os.getpid()}"
    probe.write_bytes(b"")
    try:
        for gid in os.getgroups():
            if gid == own:
                continue
            try:
                os.chown(probe, -1, gid)
            except OSError:
                continue
            return gid
    finally:
        probe.unlink(missing_ok=True)
    return None


class PrivateStagingTests(RegistryFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.root = self.root.resolve()  # private_dir resolves symlinks (macOS /tmp)
        # The layout of a real build: the store in OUTPUT/data/, the private directory beside OUTPUT.
        self.output = self.root / "site"
        (self.output / "data").mkdir(parents=True)
        self.db = self.output / "data" / "bundestag-pulse.sqlite"
        self.private = self.root / ".site.private"

    def rebuild(self, reports, **kwargs):
        entries = [{"report": r, "report_path": self.root / f'{r["protocol"]["id"]}.json'} for r in reports]
        with contextlib.redirect_stderr(io.StringIO()):
            return build.rebuild_database_from_entries(self.db, entries, **kwargs)

    def staged_leftovers(self, name=None):
        name = name or self.db.name
        return [p.name for p in self.private.iterdir() if build._is_staged_copy(name, p.name)]

    def other_group(self):
        gid = _another_group(self.db)
        if gid is None:
            self.skipTest("this user has no second group a chown may use")
        return gid

    EMPTY_SNAPSHOT = {"fact_metrics": [], "facts": [], "fact_sources": []}

    # Value: protects=a rebuild and a facts write keep the store's group and mode, so a store chgrp'ed to the web server's group stays readable to it; fails_when=_replace_store copies only the mode, so the staged copy keeps the private directory's group or the builder's egid; why_new=the staged copy moved into the private directory in v0.19.0.0 and lost the group of data/; seam=none
    def test_a_rebuild_and_a_facts_write_keep_the_store_group(self):
        self.rebuild([report()])
        gid = self.other_group()
        os.chown(self.db, -1, gid)
        os.chmod(self.db, 0o640)
        self.rebuild([report(), report(pid="s2")])
        self.assertEqual((self.db.stat().st_gid, stat.S_IMODE(self.db.stat().st_mode)), (gid, 0o640))
        build._write_facts_staged(self.db, self.EMPTY_SNAPSHOT)
        self.assertEqual((self.db.stat().st_gid, stat.S_IMODE(self.db.stat().st_mode)), (gid, 0o640))

    # Value: protects=a group the builder cannot give the staged copy stops the write before any persisting and leaves the store and the private directory as they were; fails_when=the group is checked only at the swap, after a full multi-minute rebuild, or the failure leaves a staged copy of speech text behind; why_new=the group was never carried over, so there was no refusal; seam=os.chown in the build module refuses (a store in a group the builder is not in)
    def test_a_group_the_builder_cannot_set_stops_before_persisting(self):
        self.rebuild([report()])
        gid = self.other_group()
        os.chown(self.db, -1, gid)
        with mock.patch.object(build.pulse_store, "persist_report", wraps=build.pulse_store.persist_report) as persist:
            self.rebuild([report(), report(pid="s2")])  # control: a normal rebuild does reach persist_report
            self.assertTrue(persist.called)
            persist.reset_mock()
            before = self.db.read_bytes()
            with mock.patch.object(build.os, "chown", side_effect=PermissionError(1, "Operation not permitted")), \
                    self.assertRaisesRegex(build.DatabaseRebuildError, f"belongs to group {gid}"):
                self.rebuild([report(), report(pid="s2"), report(pid="s3")])
            with mock.patch.object(build.os, "chown", side_effect=PermissionError(1, "Operation not permitted")), \
                    self.assertRaisesRegex(build.DatabaseRebuildError, f"belongs to group {gid}"):
                build._write_facts_staged(self.db, self.EMPTY_SNAPSHOT)
        persist.assert_not_called()
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual(self.staged_leftovers(), [])

    # Value: protects=a swap that fails removes the staged copy, which holds the full speech text; fails_when=_replace_store lets the exception pass with the staged copy still in the private directory until the next sweep; why_new=the rebuild path called _replace_store outside any try; seam=Path.replace raises for the staged path
    def test_a_failing_swap_removes_the_staged_copy(self):
        self.rebuild([report()])
        before = self.db.read_bytes()
        real_replace = Path.replace

        def replace(path, target):
            if build._is_staged_copy(self.db.name, path.name):
                raise OSError(28, "No space left on device")
            return real_replace(path, target)

        with mock.patch.object(Path, "replace", replace):
            with self.assertRaisesRegex(build.DatabaseRebuildError, "No space left"):
                self.rebuild([report(), report(pid="s2")])
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual(self.staged_leftovers(), [])

    # Value: protects=the crash sweep takes only this store's staged copies: a prefix-named sibling store's copy and the writer lock of a store literally named like a staged copy stay, with the lock's inode; fails_when=the sweep pattern is name.*.tmp*, which deletes a held lock file and lets a second writer flock a fresh inode; why_new=all stores of one OUTPUT/data/ share one private directory; seam=none
    def test_the_sweep_takes_only_this_stores_staged_copies(self):
        self.rebuild([report()])
        odd_store = self.db.parent / f"{self.db.name}.x.tmp"
        with registry.writer_lock(odd_store):
            pass
        odd_lock = registry.writer_lock_path(odd_store)
        self.assertEqual(odd_lock.parent, self.private)
        inode = odd_lock.stat().st_ino
        sibling = self.private / f"{self.db.name}.old.abcd1234.tmp"
        sibling.write_bytes(b"x")
        own = [self.private / f"{self.db.name}.crashd01.tmp{suffix}" for suffix in ("", "-journal", "-wal", "-shm")]
        for path in own:
            path.write_bytes(b"x")
        self.rebuild([report(), report(pid="s2")])
        self.assertEqual([p.name for p in own if p.exists()], [])
        self.assertTrue(sibling.exists())
        self.assertEqual(odd_lock.stat().st_ino, inode)

    # Value: protects=the sweep predicate matches what _staged_store_path really creates, so the coupling to mkstemp's naming cannot drift unnoticed; fails_when=a Python release names mkstemp files with a dot, or the predicate stops matching the real name, so crashed copies pile up; why_new=the sweep changed from a glob to an exact name match; seam=none
    def test_a_real_staged_name_passes_the_sweep_predicate(self):
        self.rebuild([report()])
        with registry.writer_lock(self.db):
            staged = build._staged_store_path(self.db)
        try:
            for suffix in ("", "-journal"):
                self.assertTrue(build._is_staged_copy(self.db.name, staged.name + suffix), staged.name + suffix)
        finally:
            staged.unlink(missing_ok=True)
        for other in (f"{self.db.name}.writer.lock", f"{self.db.name}.old.abcd1234.tmp", "exports", self.db.name):
            self.assertFalse(build._is_staged_copy(self.db.name, other), other)

    # Value: protects=the private directory of each caller's input shape (store, both caches, the exports directory) is the one beside OUTPUT, and a store directly under the filesystem root gets a real path; fails_when=the root guard is missing, so /data/x.sqlite gives /..private, or a caller derives another directory; why_new=private_dir had no root guard; seam=none
    def test_private_dir_for_each_input_shape(self):
        for path in (self.db, politikfelder.cache_path(self.output), build.antrag_text.cache_path(self.output), self.output / "data" / "exports"):
            with self.subTest(path=path.name):
                self.assertEqual(registry.private_dir(path), self.private)
        plain = self.root / "stores" / "store.sqlite"
        self.assertEqual(registry.private_dir(plain), plain.parent.resolve() / ".store.sqlite.private")
        top = Path("/data/x.sqlite")
        self.assertEqual(registry.private_dir(top), top.resolve().parent / ".x.sqlite.private")
        self.assertNotEqual(registry.private_dir(top).name, ".private")
        self.assertEqual(registry.private_dir(top).parent, top.resolve().parent)

    # Value: protects=a symlink in place of the private directory is refused before the sweep, so a decoy directory's files are neither deleted nor written; fails_when=mkdir(exist_ok=True) accepts the link and the sweep unlinks matching files in its target; why_new=an attacker in a shared /tmp can plant the link; seam=none
    def test_a_symlinked_private_dir_is_refused_before_the_sweep(self):
        self.rebuild([report()])
        before = self.db.read_bytes()
        decoy = self.root / "decoy"
        decoy.mkdir()
        victim = decoy / f"{self.db.name}.decoy01.tmp"
        victim.write_bytes(b"x")
        shutil.rmtree(self.private)
        self.private.symlink_to(decoy)
        with self.assertRaisesRegex(build.DatabaseRebuildError, "symbolic link"):
            self.rebuild([report(), report(pid="s2")])
        self.assertEqual([p.name for p in decoy.iterdir()], [victim.name])
        self.assertEqual(before, self.db.read_bytes())

    # Value: protects=a symlinked exports/ in the private directory is refused before the export sweep, which would otherwise delete everything in the link's target; fails_when=_export_lock only mkdirs (exist_ok), so _sweep_stale_work empties the decoy; why_new=the export sweep deletes every entry but .lock; seam=none
    def test_a_symlinked_exports_dir_is_refused_before_the_export_sweep(self):
        db = self.root / "pulse.sqlite"
        _daten_fixture.seed_store(db)
        exports_dir = self.output / "data" / "exports"
        exports_dir.mkdir(parents=True)
        work = build.export_work_dir(exports_dir)
        self.assertEqual(work.parent, self.private)
        self.private.mkdir(mode=0o700)
        decoy = self.root / "decoy"
        (decoy / "sub").mkdir(parents=True)
        (decoy / "file.txt").write_bytes(b"x")
        (decoy / "sub" / "inner.txt").write_bytes(b"y")
        work.symlink_to(decoy)
        with mock.patch.object(build.build_revision, "authored_inputs_problem", return_value=None):
            with self.assertRaisesRegex(PermissionError, "symbolic link"):
                build.export_distribution_data(db, exports_dir, mp_lookup={}, readiness=READINESS, catalog_count=2,
                                               dossier_count=2, license_text="", commit="abc123")
        self.assertEqual(sorted(p.name for p in decoy.iterdir()), ["file.txt", "sub"])
        self.assertEqual([p.name for p in (decoy / "sub").iterdir()], ["inner.txt"])

    # Value: protects=ensure_private_dir refuses a foreign owner, a regular file and a dangling link with the real reason, repairs a group-writable directory of its own, and refuses when the repair does not hold; fails_when=a branch is dropped, so a planted directory is used, a file is reported as a mkdir failure, or a file system without POSIX modes is silently accepted; why_new=new helper; seam=person_registry._euid names another user, os.chmod is a no-op
    def test_a_foreign_private_dir_is_refused_and_a_group_writable_one_repaired(self):
        own = self.root / "own"
        own.mkdir()
        with mock.patch.object(registry, "_euid", return_value=os.geteuid() + 1):
            with self.assertRaisesRegex(PermissionError, "owned by uid"):
                registry.ensure_private_dir(own)
        own.chmod(0o775)
        self.assertEqual(registry.ensure_private_dir(own), own)
        self.assertEqual(stat.S_IMODE(own.stat().st_mode), 0o700)
        own.chmod(0o775)
        with mock.patch.object(registry.os, "chmod"):
            with self.assertRaisesRegex(PermissionError, "cannot be changed"):
                registry.ensure_private_dir(own)
        plain_file = self.root / "plain"
        plain_file.write_bytes(b"x")
        with self.assertRaisesRegex(PermissionError, "not a directory"):
            registry.ensure_private_dir(plain_file)
        dangling = self.root / "dangling"
        dangling.symlink_to(self.root / "nowhere")
        with self.assertRaisesRegex(PermissionError, "symbolic link"):
            registry.ensure_private_dir(dangling)
        self.assertFalse((self.root / "nowhere").exists())
        fresh = self.root / "deep" / "fresh"
        self.assertEqual(registry.ensure_private_dir(fresh), fresh)
        self.assertEqual(stat.S_IMODE(fresh.stat().st_mode), 0o700)

    # Value: protects=an export on a fresh OUTPUT under umask 002 (Debian per-user groups, many CI images) succeeds and leaves 0700 directories, because the helper repairs the group-writable directory pathlib's mkdir(parents=True) made; fails_when=ensure_private_dir refuses group write bits instead of repairing them, which stops every export there; why_new=export_distribution_data creates the private directory itself, before any writer_lock; seam=none
    def test_an_export_under_umask_002_creates_a_usable_private_dir(self):
        db = self.root / "pulse.sqlite"
        _daten_fixture.seed_store(db)
        exports_dir = self.output / "data" / "exports"
        old = os.umask(0o002)
        self.addCleanup(os.umask, old)
        self.assertFalse(self.private.exists())
        with mock.patch.object(build.build_revision, "authored_inputs_problem", return_value=None):
            build.export_distribution_data(db, exports_dir, mp_lookup={}, readiness=READINESS, catalog_count=2,
                                           dossier_count=2, license_text="", commit="abc123")
        for directory in (self.private, self.private / "exports"):
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700, directory)

    # Value: protects=a refused private directory makes the Vorgang cache fall back to the cache's own directory, and the stale-temp sweep never runs inside the link's target; fails_when=write_atomic accepts the symlinked private directory, so its sweep deletes an old temp file of another directory (and a staged save lands there); why_new=write_atomic now refuses a symlinked private directory; seam=os.utime ages the planted file past STALE_TEMP_SECONDS
    def test_the_vorgang_cache_falls_back_when_the_private_dir_is_refused(self):
        decoy = self.root / "decoy"
        decoy.mkdir()
        planted = decoy / ".dip-vorgang-cache.json.planted.tmp"
        planted.write_bytes(b"x")
        old = os.stat(planted).st_mtime - 2 * politikfelder.STALE_TEMP_SECONDS
        os.utime(planted, (old, old))
        self.private.symlink_to(decoy)
        politikfelder.save_cache(self.output, {"version": 1, "vorgaenge": {}, "dokumentnummern": {}})
        self.assertTrue(politikfelder.cache_path(self.output).is_file())
        self.assertEqual([p.name for p in decoy.iterdir()], [planted.name])

    # Value: protects=a private directory that cannot be created (OUTPUT's parent is read-only) fails with a message naming the requirement and the doc; fails_when=the bare OSError returns, so the operator sees only a permission error with no reason; why_new=the private directory lives beside OUTPUT, which not every deployment can write; seam=none
    def test_an_unwritable_private_dir_parent_names_the_requirement(self):
        if os.geteuid() == 0:
            self.skipTest("root can write anywhere")
        parent = self.root / "readonly"
        output = parent / "site"
        (output / "data").mkdir(parents=True)
        self.db = output / "data" / "bundestag-pulse.sqlite"
        parent.chmod(0o555)
        self.addCleanup(parent.chmod, 0o755)
        with self.assertRaises(build.DatabaseRebuildError) as caught:
            self.rebuild([report()])
        self.assertIn("parent must be writable", str(caught.exception))
        self.assertIn("docs/stable-ids.md", str(caught.exception))

    # Value: protects=every file of a published export generation, the table CSVs included, is world-readable, so a web server running as another user serves it; fails_when=_write_csv writes through mkstemp and renames the 0600 file in unchanged; why_new=24 table CSVs were published at 0600 while the manifest and recipe files were 0644; seam=none
    def test_every_published_export_file_is_world_readable(self):
        db = self.root / "pulse.sqlite"
        _daten_fixture.seed_store(db)
        exports_dir = self.output / "data" / "exports"
        with mock.patch.object(build.build_revision, "authored_inputs_problem", return_value=None):
            manifest = build.export_distribution_data(db, exports_dir, mp_lookup={}, readiness=READINESS, catalog_count=2,
                                                      dossier_count=2, license_text="", commit="abc123")
        files = [p for p in exports_dir.rglob("*") if p.is_file()]
        self.assertTrue(any(p.name.endswith("-local.csv.gz") for p in files))
        for path in files:
            self.assertEqual(path.stat().st_mode & 0o044, 0o044, f"{path.relative_to(exports_dir)} is {oct(path.stat().st_mode)}")


if __name__ == "__main__":
    unittest.main()
