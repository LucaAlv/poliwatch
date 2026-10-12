"""Shared store helpers for the person-registry tests (mixed into a TestCase)."""
from __future__ import annotations
import json
import tempfile
from pathlib import Path
from unittest import mock
import _support  # noqa: F401
import persist_dip_pulse_store as store
import person_registry as registry


class RegistryFixture:
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "store.sqlite"
        self.corrections_written = 0
        self.builds = 0

    def correction_file(self, data):
        # A distinct filename per call: corrections() reads each path once per process.
        self.corrections_written += 1
        path = self.root / f"corrections-{self.corrections_written}.json"
        path.write_text(json.dumps({"version": 1, "partitions": [], "assignments": [], "merges": [], "splits": [], **data}))
        return mock.patch.object(registry, "CORRECTIONS_PATH", path)

    def open_store(self, name="s.sqlite"):
        conn = store.connect(self.root / name)
        store.initialize(conn)
        self.addCleanup(conn.close)
        return conn

    def next_build(self, previous):
        """A fresh store that starts from the previous store's registry, as a replay does."""
        previous.commit()
        self.builds += 1
        target = self.open_store(f"build-{self.builds}.sqlite")
        registry.copy_previous(previous, target)
        return target

    def up(self, conn, occurrence, identity, name, *, xml=None, dip=None, aw=None, match=None, mdb=False, party=None, **biography):
        now = store.utc_now()
        party_id = store.upsert_party(conn, party, now) if party else None
        return store.upsert_mp(conn, now=now, display_name=name, party_id=party_id, identity_key=identity,
                               xml_redner_id=xml, dip_person_id=dip, aw_politician_id=aw, aw_match=match,
                               is_mdb=mdb, occurrence_id=occurrence, **biography)

    def person_of_records(self, conn):
        return {row["id"]: row["person_id"] for row in conn.execute("SELECT id, person_id FROM person_records")}

    def grouping(self, conn):
        """The partition of records into persons, independent of which key a person got."""
        groups = {}
        for row in conn.execute("SELECT person_id, identity_key FROM person_records"):
            groups.setdefault(row[0], set()).add(row[1])
        return {frozenset(members) for members in groups.values()}

    def occurrence_groups(self, conn):
        """The partition of bound occurrences into persons, independent of person keys."""
        groups = {}
        for row in conn.execute("SELECT id, person_id FROM person_bindings"):
            groups.setdefault(row["person_id"], set()).add(row["id"])
        return {frozenset(members) for members in groups.values()}
