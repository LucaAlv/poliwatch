"""The public data changelog of a release: changes.json and CHANGES.md."""

from __future__ import annotations

import copy
import json
import unittest
from datetime import date

import _support  # noqa: F401
import release_changes as rc


def manifest(**overrides):
    base = {
        "export_format": 10,
        "store_schema": 12,
        "key_version": 3,
        "schema_hash": "a" * 64,
        "total_rows": 1000,
        "protocols": {"count": 285, "first": "18/1", "last": "21/84", "from": "2013-10-22", "to": "2025-11-06"},
        "votes": {"count": 400, "members": 250000},
    }
    base.update(overrides)
    return base


AUTHORED = {
    "summary": "Sitzungen 21/85 bis 21/90 ergänzt; zwei Abstimmungsergebnisse korrigiert.",
    "schema_changes": [],
    "coverage_added": [{"description": "Plenarprotokolle 21/85 bis 21/90 der 21. Wahlperiode"}],
    "corrections": [
        {"table": "votes", "key": "v-4711", "column": "yes_count", "old": 301, "new": 310, "reason": "Endgültiges Ergebnis statt vorläufigem Ergebnis"}
    ],
    "notes": ["Hinweis"],
}


class InitialReleaseTests(unittest.TestCase):
    # Value: protects=the first release says it is the first and names no corrections or deltas; fails_when=an initial changelog carries a previous version, old values or an empty summary; why_new=no changelog existed; seam=assemble; no_claim=Markdown layout
    def test_initial_release_changes(self) -> None:
        changes = rc.assemble(version="2026.11.01", released=date(2026, 11, 1), manifest=manifest(), previous_manifest=None, authored=None)
        self.assertEqual(changes["changes_format"], rc.CHANGES_FORMAT)
        self.assertEqual(changes["version"], "2026.11.01")
        self.assertEqual(changes["tag"], "data-2026.11.01")
        self.assertEqual(changes["released"], "2026-11-01")
        self.assertTrue(changes["initial_release"])
        self.assertIsNone(changes["previous_version"])
        self.assertEqual(changes["summary"], "Erste Veröffentlichung.")
        self.assertEqual((changes["schema_changed"], changes["schema_changes"], changes["corrections"], changes["coverage_added"]), (False, [], [], []))
        self.assertEqual(changes["coverage"]["protocols"], {"old": None, "new": 285})
        self.assertEqual(changes["export_format"], 10)
        self.assertEqual(json.loads(json.dumps(changes)), changes)

    def test_an_initial_release_has_nothing_to_correct_or_migrate(self) -> None:
        for key, value in (("corrections", AUTHORED["corrections"]), ("schema_changes", [{"table": "t", "column": None, "change": "added", "description": "d"}])):
            with self.subTest(key=key), self.assertRaisesRegex(rc.ChangesError, "initial release"):
                rc.assemble(version="2026.11.01", released=date(2026, 11, 1), manifest=manifest(), previous_manifest=None, authored={"summary": "x", key: value})

    def test_an_initial_release_may_carry_its_own_summary(self) -> None:
        changes = rc.assemble(version="2026.11.01", released=date(2026, 11, 1), manifest=manifest(), previous_manifest=None, authored={"summary": "Erste Veröffentlichung mit WP 18 bis 21."})
        self.assertEqual(changes["summary"], "Erste Veröffentlichung mit WP 18 bis 21.")


class LaterReleaseTests(unittest.TestCase):
    def assemble(self, new=None, old=None, authored=AUTHORED, version="2026.11.08"):
        return rc.assemble(
            version=version,
            released=date(2026, 11, 8),
            manifest=new or manifest(protocols={"count": 291, "first": "18/1", "last": "21/90", "from": "2013-10-22", "to": "2025-11-20"}),
            previous_manifest={**manifest(), "tag": "2026.11.01"} if old is None else old,
            authored=copy.deepcopy(authored),
        )

    # Value: protects=a later release takes its previous version from the previous manifest and derives the coverage delta itself; fails_when=the delta is authored by hand, the old value is the new one, or the previous version is missing; why_new=a cited figure must be checkable against the release before it; seam=assemble; no_claim=authored text
    def test_coverage_delta_comes_from_the_two_manifests(self) -> None:
        changes = self.assemble()
        self.assertFalse(changes["initial_release"])
        self.assertEqual(changes["previous_version"], "2026.11.01")
        self.assertEqual(changes["coverage"]["protocols"], {"old": 285, "new": 291})
        self.assertEqual(changes["coverage"]["last_protocol"], {"old": "21/84", "new": "21/90"})
        self.assertEqual(changes["coverage"]["votes"], {"old": 400, "new": 400})
        self.assertEqual(changes["corrections"], AUTHORED["corrections"])
        self.assertFalse(changes["schema_changed"])

    # Value: protects=a schema change is detected from the manifests and the release is refused until the changelog calls it out; fails_when=a changed export_format, store_schema, key_version or schema_hash passes with an empty schema_changes; why_new=a schema change breaks every downstream reader and must be explicit; seam=assemble; no_claim=wording
    def test_a_detected_schema_change_must_be_called_out(self) -> None:
        for key, value in (("export_format", 11), ("store_schema", 13), ("key_version", 4), ("schema_hash", "b" * 64)):
            with self.subTest(key=key):
                new = manifest(**{key: value}, protocols={"count": 291, "first": "18/1", "last": "21/90", "from": "2013-10-22", "to": "2025-11-20"})
                with self.assertRaisesRegex(rc.ChangesError, f"schema.*{key}"):
                    self.assemble(new=new)
                called_out = {**AUTHORED, "schema_changes": [{"table": "votes", "column": "inverted", "change": "added", "description": "neue Spalte"}]}
                changes = self.assemble(new=new, authored=called_out)
                self.assertTrue(changes["schema_changed"])
                self.assertEqual(changes["detected"][key], {"old": manifest()[key], "new": value})

    # Value: protects=every correction states table, key, column, old value, new value and reason, and a correction that changes nothing is refused; fails_when=a correction without a reason, without old/new, with old == new or with an unknown field is accepted; why_new=the changelog is what lets a researcher check a cited figure; seam=assemble; no_claim=that the old value was ever published
    def test_corrections_are_type_checked(self) -> None:
        good = AUTHORED["corrections"][0]
        bad = {
            "no reason": {k: v for k, v in good.items() if k != "reason"},
            "empty reason": {**good, "reason": "  "},
            "no old": {k: v for k, v in good.items() if k != "old"},
            "no new": {k: v for k, v in good.items() if k != "new"},
            "unchanged": {**good, "new": good["old"]},
            "unknown field": {**good, "oops": 1},
            "table not text": {**good, "table": 5},
            "old is a list": {**good, "old": [1]},
            "not an object": "votes.yes_count",
        }
        for label, correction in bad.items():
            with self.subTest(label), self.assertRaises(rc.ChangesError):
                self.assemble(authored={**AUTHORED, "corrections": [correction]})
        self.assemble(authored={**AUTHORED, "corrections": [{**good, "old": None, "new": "x"}]})

    def test_authored_file_shape_is_checked(self) -> None:
        for label, authored in (
            ("no summary", {k: v for k, v in AUTHORED.items() if k != "summary"}),
            ("blank summary", {**AUTHORED, "summary": " "}),
            ("unknown key", {**AUTHORED, "extra": 1}),
            ("coverage_added not a list", {**AUTHORED, "coverage_added": "WP 21"}),
            ("coverage entry without description", {**AUTHORED, "coverage_added": [{}]}),
            ("notes not text", {**AUTHORED, "notes": [1]}),
            ("schema change without description", {**AUTHORED, "schema_changes": [{"table": "t", "column": None, "change": "added"}]}),
            ("unknown schema change kind", {**AUTHORED, "schema_changes": [{"table": "t", "column": None, "change": "tweaked", "description": "d"}]}),
            ("not an object", ["x"]),
        ):
            with self.subTest(label), self.assertRaises(rc.ChangesError):
                self.assemble(authored=authored)
        with self.assertRaisesRegex(rc.ChangesError, "needs a changes file"):
            self.assemble(authored=None)

    def test_the_previous_manifest_must_be_an_earlier_version(self) -> None:
        with self.assertRaisesRegex(rc.ChangesError, "not earlier"):
            self.assemble(old={**manifest(), "tag": "2026.11.08"})
        with self.assertRaisesRegex(rc.ChangesError, "not earlier"):
            self.assemble(old={**manifest(), "tag": "2026.11.09"})
        self.assemble(version="2026.11.01.2", old={**manifest(), "tag": "2026.11.01"})
        with self.assertRaisesRegex(rc.ChangesError, "release version"):
            self.assemble(old={**manifest(), "tag": "local"})


class RenderTests(unittest.TestCase):
    def changes(self):
        return rc.assemble(
            version="2026.11.08",
            released=date(2026, 11, 8),
            manifest=manifest(export_format=11, protocols={"count": 291, "first": "18/1", "last": "21/90", "from": "2013-10-22", "to": "2025-11-20"}),
            previous_manifest={**manifest(), "tag": "2026.11.01"},
            authored={
                **AUTHORED,
                "schema_changes": [{"table": "votes", "column": "inverted", "change": "added", "description": "Neue Spalte"}],
                "corrections": [{**AUTHORED["corrections"][0], "reason": "a | b\nc"}],
            },
        )

    # Value: protects=CHANGES.md shows the version, schema change, coverage delta and each correction's old value, new value and reason, and survives pipes and newlines in text; fails_when=a section is missing or a pipe breaks the correction table; why_new=the page and the release carry this text; seam=render_markdown; no_claim=exact wording
    def test_markdown_states_every_part_of_the_changelog(self) -> None:
        text = rc.render_markdown(self.changes())
        for part in ("Version 2026.11.08", "data-2026.11.08", "Vorherige Version: 2026.11.01", "Schemaänderung", "votes", "inverted", "Neue Spalte",
                     "Plenarprotokolle", "285", "291", "Korrekturen", "v-4711", "yes_count", "301", "310"):
            self.assertIn(part, text)
        self.assertIn("a \\| b c", text)
        self.assertEqual(rc.render_markdown(self.changes()), text)

    def test_initial_markdown_says_so_and_has_no_corrections_table(self) -> None:
        text = rc.render_markdown(rc.assemble(version="2026.11.01", released=date(2026, 11, 1), manifest=manifest(), previous_manifest=None, authored=None))
        self.assertIn("Erste Veröffentlichung", text)
        self.assertNotIn("| Tabelle |", text)
        self.assertIn("Keine Korrekturen", text)


class LoadAuthoredTests(unittest.TestCase):
    def test_load_authored_reports_unreadable_or_invalid_json(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "changes-source.json"
            with self.assertRaisesRegex(rc.ChangesError, "cannot read"):
                rc.load_authored(path)
            path.write_text("{nope", encoding="utf-8")
            with self.assertRaisesRegex(rc.ChangesError, "not valid JSON"):
                rc.load_authored(path)
            path.write_text(json.dumps(AUTHORED), encoding="utf-8")
            self.assertEqual(rc.load_authored(path), AUTHORED)


if __name__ == "__main__":
    unittest.main()
