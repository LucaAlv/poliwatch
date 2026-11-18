from __future__ import annotations

import contextlib
import hashlib
import io
import os
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import compare_store_values as compare
import facts
import persist_dip_pulse_store as pulse_store

NOW = "2026-01-01T00:00:00Z"
METRIC = facts.REGISTRY[0]["id"]


def _fact_row(url: str | None, *, value: float = 5.0, complete: int = 1, publishable: int = 1, withheld=None):
    row = {
        "metric_id": METRIC, "metric_version": 1, "period_kind": "week", "period_key": "2026-W10",
        "iso_year": 2026, "iso_week": 10, "wahlperiode": 21, "complete": complete, "week_n": 9,
        "value": value, "denominator": None, "baseline_kind": None, "baseline_count": None,
        "baseline_from": None, "baseline_to": None, "baseline_label": None, "percentile": 0.9,
        "eligible": 1, "withheld": withheld, "publishable": publishable, "rank": 1,
        "receipts": [],
    }
    if url is not None:
        row["receipts"] = [{
            "entity_kind": "vote", "document_number": "21/1", "rede_id": None, "page": None,
            "page_quadrant": None, "official_url": url, "position": 0,
        }]
    return row


def make_output(
    root: Path,
    *,
    protocols: dict[str, list[tuple[str, str | None, int, str | None]]],
    votes: list[tuple[str, str, str, str | None, str]] = (),
    sprechrolle: bool = False,
    contributions: list[tuple[str, str]] | None = (),
    fact: dict | None = None,
    bills: int | None = None,
    roster: bool = True,
) -> Path:
    """An output directory with a tiny store.

    ``protocols``: document number -> speeches as (rede_id, fraktion, chars,
    sprechrolle). ``votes``: (vote id, date, document number, leading_vote,
    party) rows, one vote_fractions row each. ``contributions``: (document
    number, kind) rows; ``None`` is an older schema: the store predates the table.
    """
    (root / "data").mkdir(parents=True)
    conn = pulse_store.connect(root / "data" / "bundestag-pulse.sqlite")
    try:
        pulse_store.initialize(conn)
        if not sprechrolle:
            # An older schema: the store predates the column.
            conn.execute("ALTER TABLE speeches DROP COLUMN sprechrolle")
        if contributions is None:
            conn.execute("DROP TABLE contributions")
        party_ids: dict[str, int] = {}

        def party(name: str) -> int:
            if name not in party_ids:
                party_ids[name] = f"party-{name}"
                conn.execute("INSERT INTO parties(id, name, created_at, updated_at) VALUES (?, ?, ?, ?)", (party_ids[name], name, NOW, NOW))
            return party_ids[name]

        items: dict[str, int] = {}
        for number, speeches in protocols.items():
            protocol_id = f"p-{number}"
            conn.execute(
                "INSERT INTO protocols(id, document_number, date, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (protocol_id, number, "2026-03-04", NOW, NOW),
            )
            items[number] = pulse_store.persist_agenda_item(conn, protocol_id, {"index": 0}, NOW)
            for sequence, (rede_id, fraktion, chars, role) in enumerate(speeches):
                mp = pulse_store.upsert_mp(conn, now=NOW, identity_key=f"mp-{rede_id}", occurrence_id=f"fixture:mp-{rede_id}", display_name=f"MdB {rede_id}", party_id=party(fraktion or "SPD"), is_mdb=roster)
                conn.execute(
                    "INSERT INTO speeches(id, protocol_id, agenda_item_id, rede_id, sequence, mp_id, char_count, "
                    "fraktion, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"speech-{protocol_id}-{rede_id}", protocol_id, items[number], rede_id, sequence, mp, chars, fraktion, NOW, NOW),
                )
                if sprechrolle:
                    conn.execute("UPDATE speeches SET sprechrolle = ? WHERE rede_id = ?", (role, rede_id))
        for sequence, (number, kind) in enumerate(contributions or ()):
            conn.execute(
                "INSERT INTO contributions(id, protocol_id, agenda_item_id, kind, rede_id, sequence, created_at, "
                "updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (f"contribution-p-{number}-C{sequence}", f"p-{number}", items[number], kind, f"C{sequence}", sequence, NOW, NOW),
            )
        for vote_id, date, number, leading, party_name in votes:
            if not conn.execute("SELECT 1 FROM votes WHERE id = ?", (vote_id,)).fetchone():
                conn.execute(
                    "INSERT INTO votes(id, date, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (vote_id, date, NOW, NOW),
                )
                conn.execute(
                    "INSERT INTO agenda_item_votes(agenda_item_id, vote_id, basis) VALUES (?, ?, 'drucksache_xml')", (items[number], vote_id)
                )
            conn.execute(
                "INSERT INTO vote_fractions(vote_id, party_id, leading_vote, rank) VALUES (?, ?, ?, 1)",
                (vote_id, party(party_name), leading),
            )
        if fact is not None:
            facts.write_snapshot(conn, facts.snapshot_from_rows(facts.REGISTRY, [fact]))
        conn.commit()
    finally:
        conn.close()
    if bills is not None:
        (root / "bills").mkdir()
        (root / "bills" / "index.html").write_text("index")
        for number in range(bills):
            (root / "bills" / f"bill-{number}.html").write_text("bill")
    return root


def run(old: Path, new: Path, *args: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = compare.main([str(old), str(new), "--no-recipes", *args])
    return code, out.getvalue(), err.getvalue()


def line_of(text: str, label: str, section: str | None = None) -> str:
    """The first output line starting with ``label`` (after ``section``'s heading)."""
    body = text if section is None else text.split(f"== {section}", 1)[1]
    for line in body.splitlines():
        if line.strip().startswith(label):
            return re.sub(r"\s+", " ", line.strip())
    raise AssertionError(f"no line for {label!r} in {section or 'output'}:\n{text}")


class CompareStoreValuesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def stores(self) -> tuple[Path, Path]:
        old = make_output(
            self.tmp / "old",
            protocols={
                "21/1": [("R1", "SPD", 100, None), ("R2", "SPD", 200, None), ("R3", "Regierung", 300, None)],
            },
            votes=[("v1", "2026-03-04", "21/1", "yes", "SPD"), ("v2", "2026-03-04", "21/1", "no", "SPD")],
            fact=_fact_row("https://example.test/vote/1"),
        )
        new = make_output(
            self.tmp / "new",
            protocols={
                "21/1": [("R1", "SPD", 100, None), ("R2", "SPD", 150, None), ("R3", "Regierung", 300, "bundesregierung")],
                "21/2": [("R4", "SPD", 1000, None)],
            },
            votes=[
                ("v1", "2026-03-04", "21/1", None, "SPD"),
                ("v2", "2026-03-04", "21/1", "no", "SPD"),
                ("v3", "2026-04-01", "21/2", "yes", "SPD"),
            ],
            sprechrolle=True,
            fact=_fact_row("https://example.test/vote/2"),
            bills=3,
        )
        return old, new

    # Value: protects=the comparison diagnostic keeps same-roll-call namesakes split; fails_when=vote_members stop populating vote_ids on rows passed to match_rows; why_new=identity integration tests cover production reconciliation but not this separate comparison path; seam=none
    # Value: protects=the replay report names every vote whose total moved, with old and new values, and counts the NULL totals schema 10 stores where the source gave none; fails_when=the section is dropped or a 0 that became NULL reads as unchanged; why_new=A4 slice 1 moves missing totals from 0 to NULL; seam=none
    def test_vote_totals_list_each_moved_vote_and_count_null_totals(self) -> None:
        old, new = self.stores()
        for root, totals in ((old, {"v1": (0, 0, 0, 0), "v2": (5, 3, 1, 0)}), (new, {"v1": (None, None, None, None), "v2": (5, 3, 1, 0)})):
            conn = sqlite3.connect(root / "data" / "bundestag-pulse.sqlite")
            try:
                for vote_id, (yes, no, abstain, absent) in totals.items():
                    conn.execute(
                        "UPDATE votes SET yes_count = ?, no_count = ?, abstain_count = ?, absent_count = ? WHERE id = ?",
                        (yes, no, abstain, absent, vote_id),
                    )
                conn.commit()
            finally:
                conn.close()
        code, out, _ = run(old, new)
        self.assertEqual(code, 0)
        section = "vote totals"
        self.assertEqual(line_of(out, "votes with a NULL count", section), "votes with a NULL count 0 -> 1 +1")
        self.assertIn("1 votes in both stores changed their total", out)
        self.assertEqual(line_of(out, "v1", section), "v1 0/0/0/0 -> NULL/NULL/NULL/NULL")

    # Value: protects=the replay report shows each vote whose persisted outcome, Abweichler count or member Abweichung moved, old and new; fails_when=the section is dropped or a member flag change on an unchanged count reads as unchanged; why_new=schema 13 persists the three figures and the README recipe "Validate a data correction" must show them moving; seam=none
    def test_vote_outcome_abweichler_count_and_member_abweichung_are_listed_per_vote(self) -> None:
        old, new = self.stores()
        figures = {
            old: {"v1": ("accepted", 0, {"mp-R1": 0, "mp-R2": 0}), "v2": ("rejected", None, {"mp-R1": None})},
            new: {"v1": ("rejected", 1, {"mp-R1": 1, "mp-R2": 0}), "v2": ("rejected", None, {"mp-R1": None}),
                  "v3": ("accepted", 0, {})},
        }
        for root, votes in figures.items():
            conn = sqlite3.connect(root / "data" / "bundestag-pulse.sqlite")
            try:
                for vote_id, (result, count, members) in votes.items():
                    conn.execute("UPDATE votes SET application_result = ?, abweichler_count = ? WHERE id = ?", (result, count, vote_id))
                    for key, flag in members.items():
                        mp_id = conn.execute("SELECT id FROM mps WHERE identity_key = ?", (key,)).fetchone()[0]
                        conn.execute(
                            "INSERT INTO vote_members(vote_id, mp_id, vote, abweichung) VALUES (?, ?, 'yes', ?)",
                            (vote_id, mp_id, flag),
                        )
                conn.commit()
            finally:
                conn.close()
        code, out, _ = run(old, new)
        self.assertEqual(code, 0)
        section = "vote outcome and Abweichler"
        # The fixed cohort leaves out v3 of the new sitting 21/2.
        self.assertEqual(line_of(out, "application_result accepted", section), "application_result accepted 1 -> 0 -1")
        self.assertEqual(line_of(out, "application_result rejected", section), "application_result rejected 1 -> 2 +1")
        self.assertEqual(line_of(out, "abweichler_count sum", section), "abweichler_count sum 0 -> 1 +1")
        self.assertEqual(line_of(out, "votes with a NULL abweichler_count", section), "votes with a NULL abweichler_count 1 -> 1 =")
        self.assertEqual(line_of(out, "vote_members.abweichung = 1", section), "vote_members.abweichung = 1 0 -> 1 +1")
        self.assertEqual(line_of(out, "vote_members.abweichung = 0", section), "vote_members.abweichung = 0 2 -> 1 -1")
        self.assertEqual(line_of(out, "vote_members.abweichung NULL", section), "vote_members.abweichung NULL 1 -> 1 =")
        self.assertIn("1 votes in both stores changed their outcome, Abweichler count or Abweichungen", out)
        self.assertEqual(
            line_of(out, "v1:", section),
            "v1: application_result accepted -> rejected; abweichler_count 0 -> 1; abweichung moved for 1 members",
        )
        self.assertEqual(line_of(out, "MdB R1", section), "MdB R1 (mp-R1) 0 -> 1")
        self.assertNotIn("v2:", out.split(f"== {section}", 1)[1].split("\n== ", 1)[0])

        _, whole, _ = run(old, new, "--cohort", "all")
        self.assertEqual(line_of(whole, "application_result accepted", section), "application_result accepted 1 -> 1 =")

    # Value: protects=the r3 row count is taken from the distribution copy datenstand.json names, so a --data-tag export is counted, not unavailable; fails_when=the copy is found by a fixed file name again; why_new=a tagged export names its copy bundestag-pulse-<tag>.sqlite.gz; seam=build.RECIPES_BY_ID (a one-line recipe stands in for r3, whose SQL needs the export's derived tables)
    def test_recipe_rows_run_on_the_copy_a_tagged_export_names(self) -> None:
        import gzip
        import json

        import build_dip_pulse_site as build

        old, new = self.stores()
        generation = new / "data" / "exports" / "g-0123456789ab"
        generation.mkdir(parents=True)
        name = "bundestag-pulse-v1.2.0.sqlite.gz"
        with (new / "data" / "bundestag-pulse.sqlite").open("rb") as source, gzip.open(generation / name, "wb") as target:
            target.write(source.read())
        (new / "data" / "exports" / "datenstand.json").write_text(
            json.dumps({"generation": generation.name, "files": [{"name": name}]}), encoding="utf-8"
        )
        out = io.StringIO()
        with mock.patch.dict(build.RECIPES_BY_ID, {"r3-abweichler": {"sql": "SELECT id FROM votes LIMIT 1;"}}):
            compare.compare(old, new, out=out)
        # old has no export: unavailable; new's tagged copy holds three votes (the LIMIT is dropped).
        self.assertEqual(
            line_of(out.getvalue(), "rows without LIMIT", "Daten recipe"),
            "rows without LIMIT (recipe of this tree) unavailable -> 3",
        )

    # Value: protects=a store from before schema 13 reads "unavailable" in the vote figure rows and the list of moved votes is skipped, never a crash or a 0; fails_when=the figure columns are read without the has() guard or a missing side counts as zero; why_new=the new test fills both stores, so the older-store branches are unexercised; seam=none
    def test_an_older_store_without_the_vote_figure_columns_is_unavailable(self) -> None:
        old, new = self.stores()
        conn = sqlite3.connect(old / "data" / "bundestag-pulse.sqlite")
        try:
            conn.execute("ALTER TABLE votes DROP COLUMN application_result")
            conn.execute("ALTER TABLE votes DROP COLUMN abweichler_count")
            conn.execute("ALTER TABLE vote_members DROP COLUMN abweichung")
            conn.commit()
        finally:
            conn.close()
        code, out, _ = run(old, new)
        self.assertEqual(code, 0)
        section = "vote outcome and Abweichler"
        self.assertEqual(line_of(out, "abweichler_count sum", section), "abweichler_count sum unavailable -> 0")
        self.assertEqual(line_of(out, "vote_members.abweichung = 1", section), "vote_members.abweichung = 1 unavailable -> 0")
        self.assertNotIn("changed their outcome", out)

    # Value: protects=a NULL outcome reads NULL, and long member and vote lists are cut with a count of the rest; fails_when=the no-row marker, the NULL text or the MEMBER_LIMIT/LIST_LIMIT truncation line is dropped; why_new=the first figure test stays within the limits and has every member on both sides; seam=none
    def test_vote_figure_changes_mark_missing_members_and_truncate_long_lists(self) -> None:
        old, new = self.stores()
        rows = {
            old: {"v1": (None, 0, {"mp-R1": 0, "mp-R2": 0}), "v2": ("rejected", 0, {})},
            new: {"v1": ("accepted", 0, {"mp-R1": 1, "mp-R2": 1}), "v2": ("accepted", 0, {})},
        }
        for root, votes in rows.items():
            conn = sqlite3.connect(root / "data" / "bundestag-pulse.sqlite")
            try:
                for vote_id, (result, count, members) in votes.items():
                    conn.execute("UPDATE votes SET application_result = ?, abweichler_count = ? WHERE id = ?", (result, count, vote_id))
                    for key, flag in members.items():
                        mp_id = conn.execute("SELECT id FROM mps WHERE identity_key = ?", (key,)).fetchone()[0]
                        conn.execute(
                            "INSERT INTO vote_members(vote_id, mp_id, vote, abweichung) VALUES (?, ?, 'yes', ?)", (vote_id, mp_id, flag)
                        )
                conn.commit()
            finally:
                conn.close()
        with mock.patch.object(compare, "MEMBER_LIMIT", 1), mock.patch.object(compare, "LIST_LIMIT", 1):
            code, out, _ = run(old, new)
        self.assertEqual(code, 0)
        section = "vote outcome and Abweichler"
        self.assertIn("2 votes in both stores changed their outcome, Abweichler count or Abweichungen", out)
        self.assertEqual(
            line_of(out, "v1:", section),
            "v1: application_result NULL -> accepted; abweichler_count 0 -> 0; abweichung moved for 2 members",
        )
        self.assertEqual(line_of(out, "MdB R1", section), "MdB R1 (mp-R1) 0 -> 1")
        self.assertEqual(line_of(out, "... 1 more members", section), "... 1 more members")
        self.assertEqual(line_of(out, "... 1 more votes", section), "... 1 more votes")

    # Value: protects=a missing or unusable datenstand.json, or one naming an absent copy, leaves the recipe rows unavailable instead of raising or guessing a file; fails_when=a manifest error escapes or the old glob fallback returns; why_new=the tagged-export test covers only the manifest that resolves; seam=none
    def test_distribution_copy_is_none_unless_the_manifest_names_an_existing_file(self) -> None:
        import json

        exports = self.tmp / "dist" / "data" / "exports"
        (exports / "g").mkdir(parents=True)
        directory = self.tmp / "dist"
        self.assertIsNone(compare._distribution_copy(directory))  # no manifest
        manifest = exports / "datenstand.json"
        for text in ("not json", json.dumps({"generation": "g"}), json.dumps({"generation": "g", "files": []}),
                     json.dumps({"generation": "g", "files": [{"name": "absent.sqlite.gz"}]})):
            manifest.write_text(text, encoding="utf-8")
            self.assertIsNone(compare._distribution_copy(directory), text)
        (exports / "g" / "copy.sqlite.gz").write_bytes(b"x")
        manifest.write_text(json.dumps({"generation": "g", "files": [{"name": "copy.sqlite.gz"}]}), encoding="utf-8")
        self.assertEqual(compare._distribution_copy(directory), exports / "g" / "copy.sqlite.gz")

    def test_reconciliation_diagnostic_keeps_same_vote_namesakes_split(self) -> None:
        root = make_output(
            self.tmp / "diagnostic",
            protocols={"21/1": [("R1", "SPD", 100, None)]},
            votes=[("v1", "2026-03-04", "21/1", "yes", "SPD")],
            roster=False,
        )
        path = root / "data" / "bundestag-pulse.sqlite"
        conn = pulse_store.connect(path)
        try:
            conn.row_factory = sqlite3.Row
            speaker = conn.execute("SELECT id, party_id FROM mps").fetchone()
            conn.execute("UPDATE mps SET display_name='Alex Beispiel', xml_redner_id='xml-1' WHERE id=?", (speaker["id"],))
            voter = pulse_store.upsert_mp(
                conn,
                now=NOW,
                display_name="Alex Beispiel",
                party_id=speaker["party_id"],
                identity_key="vote-only:alex",
                occurrence_id="fixture:vote-only:alex",
            )
            conn.execute("INSERT INTO vote_members(vote_id, mp_id, party_id, vote) VALUES ('v1', ?, ?, 'yes')", (speaker["id"], speaker["party_id"]))
            conn.execute("INSERT INTO vote_members(vote_id, mp_id, party_id, vote) VALUES ('v1', ?, ?, 'no')", (voter, speaker["party_id"]))
            conn.commit()
        finally:
            conn.close()

        store = compare.open_store(root)
        try:
            result = compare._zusammenfuehrung(store)
            self.assertEqual(result["entries"], 2)
            self.assertEqual(result["merges_unique_name"], 0)
        finally:
            store.close()

    # Value: protects=the Zusammenführung diagnostic reports each statistic of this tree's matching under its own label: rows, persons, merges per provenance and name buckets left split; fails_when=_zusammenfuehrung maps a totals key to the wrong field, miscounts rows, or the report prints a value under another label; why_new=A.2 test follow-ups: only entries and unique_name were asserted, on a case where every merge count is 0; seam=none
    def test_zusammenfuehrung_reports_every_statistic_under_its_label(self) -> None:
        root = make_output(self.tmp / "zusammen", protocols={"21/1": []}, roster=False)
        conn = pulse_store.connect(root / "data" / "bundestag-pulse.sqlite")
        try:
            def mp(name, identity, *, party="SPD", **fields):
                return pulse_store.upsert_mp(conn, now=NOW, display_name=name, party_id=pulse_store.upsert_party(conn, party, NOW),
                                             identity_key=identity, occurrence_id=f"fixture:{identity}", **fields)
            for n in (1, 2):  # a shared Personenkennung (ext_id): 2 merges
                mp(f"Ext Person{n}", f"dip:e{n}", dip_person_id=f"e{n}", aw_politician_id=100 + n, aw_match="ext_id", is_mdb=True)
                mp(f"Ext Person{n}", f"xml:e{n}", xml_redner_id=f"9{n}", aw_politician_id=100 + n, aw_match="ext_id")
            # a second Redner-ID whose name-found profile corroborates the first: 1 merge
            mp("Nancy Faeser", "xml:11005452", xml_redner_id="11005452", aw_politician_id=135391, aw_match="ext_id", is_mdb=True)
            mp("Nancy Faeser", "xml:999990119", party="Regierung", xml_redner_id="999990119", aw_politician_id=135391, aw_match="name", is_mdb=True)
            for n in (1, 2, 3):  # one record on each side with one name and party: 3 merges
                mp(f"Uniq Name{n}", f"dip:u{n}", dip_person_id=f"u{n}", is_mdb=True)
                mp(f"Uniq Name{n}", f"xml:u{n}", xml_redner_id=f"7{n}")
            for n in (1, 2, 3, 4):  # two Redner of one name: 4 buckets left split
                mp(f"Max Muster{n}", f"xml:m{n}a", xml_redner_id=f"m{n}a")
                mp(f"Max Muster{n}", f"xml:m{n}b", xml_redner_id=f"m{n}b")
            for n in (1, 2):  # two Redner and a DIP person of one name: 2 buckets of 3+
                mp(f"Peter Mueller{n}", f"xml:p{n}a", xml_redner_id=f"p{n}a")
                mp(f"Peter Mueller{n}", f"xml:p{n}b", xml_redner_id=f"p{n}b")
                mp(f"Peter Mueller{n}", f"dip:p{n}", dip_person_id=f"p{n}", is_mdb=True)
            conn.commit()
        finally:
            conn.close()
        expected = {"rows": 26, "entries": 20, "merges_ext_id": 2, "merges_corroborated_name": 1, "merges_unique_name": 3,
                    "buckets_split_namesakes": 4, "buckets_split_3plus": 2}
        store = compare.open_store(root)
        try:
            self.assertEqual(compare._zusammenfuehrung(store), expected)
        finally:
            store.close()
        code, out, _ = run(root, root)
        self.assertEqual(code, 0)
        section = "Zusammenführung of the mps rows"
        for label, key in (("mps rows", "rows"), ("Personen after Zusammenführung", "entries"),
                           ("merges by Personenkennung (ext_id)", "merges_ext_id"),
                           ("merges by corroborated name-found id", "merges_corroborated_name"),
                           ("merges by unique name + party", "merges_unique_name"),
                           ("name buckets left split: two on one side", "buckets_split_namesakes"),
                           ("name buckets left split: 3+ records", "buckets_split_3plus")):
            with self.subTest(label):
                self.assertTrue(line_of(out, label, section).endswith(f" {expected[key]} -> {expected[key]} ="))

    def test_fixed_cohort_prints_old_new_and_delta_on_shared_protocols_only(self) -> None:
        old, new = self.stores()
        code, out, _ = run(old, new)
        self.assertEqual(code, 0)
        self.assertIn("cohort: shared (1 protocols in both; 0 only in old, 1 only in new)", out)
        # 21/2 exists only in the new store, so the fixed cohort ignores its 1000 characters.
        self.assertEqual(line_of(out, "sum over protocols", "speeches.char_count sum"), "sum over protocols 600 -> 550 -50")
        self.assertEqual(line_of(out, "yes", "vote_fractions.leading_vote"), "yes 1 -> 0 -1")
        self.assertEqual(line_of(out, "NULL", "vote_fractions.leading_vote"), "NULL 0 -> 1 +1")
        self.assertEqual(line_of(out, "votes", "votes [shared]"), "votes 2 -> 2 =")

    def test_whole_store_mode_shows_what_the_new_store_added(self) -> None:
        old, new = self.stores()
        code, out, _ = run(old, new, "--cohort", "all")
        self.assertEqual(code, 0)
        self.assertEqual(line_of(out, "sum over protocols", "speeches.char_count sum"), "sum over protocols 600 -> 1.550 +950")
        self.assertEqual(line_of(out, "votes", "votes [all]"), "votes 2 -> 3 +1")
        self.assertEqual(line_of(out, "newest vote date", "votes [all]"), "newest vote date 2026-03-04 -> 2026-04-01")

    # Value: protects=the Personenseiten count leaves out alias redirect files of merged persons and the index; fails_when=the person_aliases subtraction in measure is removed; why_new=no test writes abgeordnete/ pages or person_aliases rows; seam=none
    def test_person_pages_exclude_alias_redirects_and_the_index(self) -> None:
        old, new = self.stores()
        for root, pages in ((old, ["p-1", "p-2"]), (new, ["p-1", "p-2", "p-gone"])):
            (root / "abgeordnete").mkdir()
            (root / "abgeordnete" / "index.html").write_text("index")
            for page in pages:
                (root / "abgeordnete" / f"{page}.html").write_text("page")
        conn = pulse_store.connect(new / "data" / "bundestag-pulse.sqlite")
        try:
            conn.executemany("INSERT INTO persons(id, ordinal) VALUES (?, ?)", [("p-1", 901), ("p-gone", 902)])
            conn.execute("INSERT INTO person_aliases(id, person_id) VALUES ('p-gone', 'p-1')")
            conn.commit()
        finally:
            conn.close()
        _, out, _ = run(old, new)
        self.assertEqual(line_of(out, "abgeordnete/ pages", "generated pages"), "abgeordnete/ pages (Personenseiten) 2 -> 2 =")

    # Value: protects=the Personenseiten count also leaves out redirect files of keys a name guess moved to another person (no alias row); fails_when=the home_person_id subtraction in measure is removed so guess redirects are counted as persons; why_new=the alias test never wrote a record whose home person differs from its current person; seam=none
    def test_person_pages_exclude_redirects_of_guess_moved_keys(self) -> None:
        old, new = self.stores()
        for root, pages in ((old, ["p-1"]), (new, ["p-1", "p-moved"])):
            (root / "abgeordnete").mkdir()
            for page in pages:
                (root / "abgeordnete" / f"{page}.html").write_text("page")
        conn = pulse_store.connect(new / "data" / "bundestag-pulse.sqlite")
        try:
            conn.executemany("INSERT INTO persons(id, ordinal) VALUES (?, ?)", [("p-1", 901), ("p-moved", 902)])
            conn.executemany(
                "INSERT INTO person_records(id, identity_key, person_id, evidence_json, partition, home_person_id) VALUES (?, ?, 'p-1', '{}', NULL, ?)",
                [("r1", "k1", "p-1"), ("r2", "k2", "p-moved")],
            )
            conn.commit()
        finally:
            conn.close()
        _, out, _ = run(old, new)
        self.assertEqual(line_of(out, "abgeordnete/ pages", "generated pages"), "abgeordnete/ pages (Personenseiten) 1 -> 1 =")

    def test_a_quantity_without_evidence_is_unavailable_never_zero(self) -> None:
        old, new = self.stores()
        _, out, _ = run(old, new)
        # The old store has no sprechrolle column and no bills/ directory; the new
        # store's figures show against "unavailable", not against 0.
        self.assertEqual(line_of(out, "bundesregierung", "speeches per Sprechrolle"), "bundesregierung unavailable -> 1")
        self.assertEqual(line_of(out, "bills/ pages", "generated pages"), "bills/ pages unavailable -> 3")
        self.assertEqual(
            line_of(out, "sum over protocols", "unattributed characters per protocol"),
            "sum over protocols unavailable -> unavailable",
        )

    def test_a_protocol_with_a_speech_lacking_the_measurement_has_no_unattributed_total(self) -> None:
        # SUM skips NULL: 21/1 would report 7 as its total though one of its two
        # speeches was never measured. 21/2 is fully measured and keeps its figure.
        root = make_output(
            self.tmp / "s",
            protocols={"21/1": [("r1", "SPD", 10, None), ("r2", "SPD", 10, None)], "21/2": [("r3", "SPD", 10, None)]},
        )
        conn = pulse_store.connect(root / "data" / "bundestag-pulse.sqlite")
        try:
            conn.execute("UPDATE speeches SET unattributed_char_count = 7 WHERE rede_id IN ('r1', 'r3')")
            conn.commit()
        finally:
            conn.close()
        store = compare.open_store(root)
        try:
            measured = compare.measure(store, recipes=False)
        finally:
            store.conn.close()
        self.assertEqual(measured.unattributed_by_protocol, {"21/2": 7})

    def test_redeanteil_moves_a_role_speaker_out_of_the_fraktion_rows(self) -> None:
        old, new = self.stores()
        _, out, _ = run(old, new)
        section = "Redeanteil"
        self.assertEqual(line_of(out, "Regierung (Reden)", section), "Regierung (Reden) 1 -> 0 -1")
        self.assertEqual(line_of(out, "Sprechrolle bundesregierung (Reden)", section), "Sprechrolle bundesregierung (Reden) 0 -> 1 +1")

    # Value: protects=the comparison lists each withheld Rede a new store adds, releases or re-words, and says "unavailable" for a store before schema 12;  # pregate-literal: SCHEMA_VERSION=12 the schema that added withheld_units, on purpose
    #   fails_when=measure() drops withheld_units or the per-reason and per-Rede sections stop printing old -> new; why_new=withheld tables are new in schema 12
    #   and no compare test touched them; seam=none; no_claim=the real store (tiny fixture stores)
    def test_withheld_reden_are_compared_per_reason_and_per_rede(self) -> None:
        protocols = {"21/1": [("R1", "SPD", 100, None)]}
        old = make_output(self.tmp / "o", protocols=protocols)
        new = make_output(self.tmp / "n", protocols=protocols)
        for root, rows in ((old, [("R9", "reviewed", 50)]), (new, [("R9", "reviewed", 70), ("R8", "refused_nested_contribution", 30)])):
            conn = sqlite3.connect(root / "data" / "bundestag-pulse.sqlite")
            try:
                item = conn.execute("SELECT id FROM agenda_items").fetchone()[0]
                for sequence, (rede_id, reason, words) in enumerate(rows, start=5):
                    conn.execute(
                        "INSERT INTO withheld_units(id, protocol_id, agenda_item_id, rede_id, sequence, reason, reason_detail, word_count, "
                        "created_at, updated_at) VALUES (?, 'p-21/1', ?, ?, ?, ?, 'x', ?, ?, ?)",
                        (f"w-{rede_id}", item, rede_id, sequence, reason, words, NOW, NOW))
                conn.commit()
            finally:
                conn.close()
        _, out, _ = run(old, new)
        reasons = out.split("== withheld Reden (ADR 0005, outside every count) per reason", 1)[1].split("\n== ", 1)[0]
        self.assertIn("refused_nested_contribution 0 -> 1 +1", re.sub(r"[ \t]+", " ", reasons))
        units = out.split("== withheld Reden added, released or changed", 1)[1].split("\n== ", 1)[0]
        self.assertIn("21/1 R9: reviewed, 50 words -> reviewed, 70 words", units)
        self.assertIn("21/1 R8: not withheld -> refused_nested_contribution, 30 words", units)
        # Unchanged withheld Reden are not listed.
        _, same, _ = run(new, new)
        self.assertIn("(none changed)", same)

    # Value: protects=the per-kind Beiträge section reports old->new counts on the cohort and shows an older store without the table as unavailable; fails_when=measure or the section drops contributions; why_new=no test read the contributions table; seam=none
    def test_contributions_per_kind_are_compared_and_an_older_store_is_unavailable(self) -> None:
        heading = "== contributions (Beiträge that are no Rede) per kind"

        def section(text: str) -> list[str]:
            body = text.split(heading, 1)[1].split("\n== ", 1)[0]
            return [re.sub(r"\s+", " ", line.strip()) for line in body.splitlines()[1:] if line.strip()]

        protocols = {"21/1": [("R1", "SPD", 100, None)], "21/2": [("R2", "SPD", 100, None)]}
        older = make_output(self.tmp / "o", protocols={"21/1": [("R1", "SPD", 100, None)]}, contributions=None)
        old = make_output(
            self.tmp / "p", protocols={"21/1": [("R1", "SPD", 100, None)]}, contributions=[("21/1", "kurzintervention")]
        )
        new = make_output(
            self.tmp / "n",
            protocols=protocols,
            contributions=[
                ("21/1", "kurzintervention"), ("21/1", "kurzintervention"), ("21/1", "erwiderung"),
                ("21/2", "kurzintervention"),
            ],
        )
        # No contributions table in the old store: the new figures show against "unavailable", not 0.
        _, out, _ = run(older, new)
        self.assertIn(f"{heading} [shared]", out)
        self.assertEqual(section(out), ["erwiderung unavailable -> 1", "kurzintervention unavailable -> 2"])
        _, out, _ = run(older, older)
        self.assertEqual(section(out), ["(all) unavailable -> unavailable"])
        # Both stores have the table: old -> new per kind; the shared cohort ignores 21/2.
        _, out, _ = run(old, new)
        self.assertEqual(section(out), ["erwiderung 0 -> 1 +1", "kurzintervention 1 -> 2 +1"])
        _, out, _ = run(old, new, "--cohort", "all")
        self.assertEqual(section(out), ["erwiderung 0 -> 1 +1", "kurzintervention 1 -> 3 +2"])

    def test_a_changed_winner_with_equal_value_is_reported_with_both_vote_identities(self) -> None:
        old, new = self.stores()
        _, out, _ = run(old, new)
        self.assertIn("changed winners: 1", out)
        self.assertIn("https://example.test/vote/1", out)
        self.assertIn("https://example.test/vote/2", out)

    def test_a_period_that_stops_being_complete_is_listed_with_its_reason(self) -> None:
        old = make_output(self.tmp / "o", protocols={"21/1": []}, fact=_fact_row("u"))
        new = make_output(
            self.tmp / "n",
            protocols={"21/1": []},
            fact=_fact_row("u", complete=0, publishable=0, withheld="Sitzung 21/2 fehlt"),
        )
        _, out, _ = run(old, new)
        self.assertIn("1 periods newly incomplete", out)
        self.assertIn("week 2026-W10: Sitzung 21/2 fehlt", out)
        self.assertEqual(line_of(out, "publishable weeks", "stored facts"), "publishable weeks 1 -> 0 -1")

    # Value (D6): protects=the old/new report for Fakt values a backfill moves behind an
    # unchanged winner (CLAUDE.md "report the old and new values"); fails_when=a moved
    # value, denominator or percentile of a shared period goes unlisted; seam=compare.main.
    def test_moved_fakt_values_are_listed_per_period_and_metric(self) -> None:
        old_row = {**_fact_row("u", value=5.0), "denominator": 20, "percentile": 0.9}
        new_row = {**_fact_row("u", value=6.0), "denominator": 24, "percentile": 0.75}
        old = make_output(self.tmp / "o", protocols={"21/1": []}, fact=old_row)
        new = make_output(self.tmp / "n", protocols={"21/1": []}, fact=new_row)
        _, out, _ = run(old, new)
        self.assertIn("fakt values moved: 1 of 1 shared (period, metric)", out)
        self.assertIn(f"week 2026-W10 {METRIC}: value 5 -> 6 +1; denominator 20 -> 24 +4; percentile 0.9 -> 0.75 -0.15", out)
        _, same, _ = run(old, make_output(self.tmp / "s", protocols={"21/1": []}, fact=old_row))
        self.assertIn("fakt values moved: 0 of 1 shared (period, metric)", same)

    def test_a_parties_name_that_disappears_is_listed_and_a_missing_roster_is_unavailable(self) -> None:
        old = make_output(
            self.tmp / "o", protocols={"21/1": [("R1", "SPDSPD", 5, None), ("R2", "SPD", 5, None)]}, roster=False
        )
        new = make_output(
            self.tmp / "n", protocols={"21/1": [("R1", "SPD", 5, None), ("R2", "SPD", 5, None)]}, roster=True
        )
        _, out, _ = run(old, new)
        section = "parties [whole store]"
        # A spelling fix removes a row; the figures alone (mps 1 -> none) would not say so.
        self.assertEqual(line_of(out, "SPDSPD: mps rows", section), "SPDSPD: mps rows 1 -> no row")
        self.assertEqual(line_of(out, "SPDSPD: Reden", section), "SPDSPD: Reden 1 -> no row")
        self.assertEqual(line_of(out, "SPD: mps rows", section), "SPD: mps rows 1 -> 2 +1")
        self.assertEqual(line_of(out, "SPD: Reden", section), "SPD: Reden 1 -> 2 +1")
        # The old store has no MdB roster: unavailable, not 0.
        self.assertEqual(line_of(out, "SPD: MdB", section), "SPD: MdB unavailable -> 2")

    def test_reden_without_a_zusammenschluss_are_counted_per_fallback(self) -> None:
        old = make_output(
            self.tmp / "o", protocols={"21/1": [("R1", None, 5, None), ("R2", None, 5, None), ("R3", "SPD", 5, None)]},
            sprechrolle=False,
        )
        new = make_output(
            self.tmp / "n",
            protocols={"21/1": [("R1", None, 5, None), ("R2", None, 5, "bundesregierung"), ("R3", "SPD", 5, None)]},
            sprechrolle=True,
        )
        _, out, _ = run(old, new)
        section = "Reden with no Zusammenschluss in the Plenarprotokoll"
        # An older store cannot tell a role speaker from one without a Fraktion.
        self.assertEqual(line_of(out, "current party", section), "current party unavailable -> 1")
        newer = make_output(
            self.tmp / "n2",
            protocols={"21/1": [("R1", None, 5, None), ("R2", None, 5, None), ("R3", "SPD", 5, None)]},
            sprechrolle=True,
        )
        _, out, _ = run(newer, new)
        # R1 has no party either? make_output gives every speaker an SPD row, so each
        # of the two is counted for that current party; the role speaker no longer is.
        self.assertEqual(line_of(out, "current party", section), "current party 2 -> 1 -1")

    def _add_members(self, root: Path, rows: list[tuple]) -> None:
        """rows: (vote id, mp identity key or None for an orphan mp_id, abweichung, party, listed party)."""
        conn = sqlite3.connect(root / "data" / "bundestag-pulse.sqlite")
        try:
            for vote_id, key, flag, party, listed in rows:
                mp_id = "orphan-" + vote_id if key is None else conn.execute("SELECT id FROM mps WHERE identity_key = ?", (key,)).fetchone()[0]
                ids = [None if name is None else conn.execute("SELECT id FROM parties WHERE name = ?", (name,)).fetchone()[0] for name in (party, listed)]
                conn.execute(
                    "INSERT INTO vote_members(vote_id, mp_id, party_id, listed_party_id, vote, abweichung) VALUES (?, ?, ?, ?, 'yes', ?)",
                    (vote_id, mp_id, ids[0], ids[1], flag),
                )
            conn.commit()
        finally:
            conn.close()

    def _figures(self, root: Path) -> None:
        conn = sqlite3.connect(root / "data" / "bundestag-pulse.sqlite")
        try:
            conn.execute("UPDATE votes SET application_result = 'accepted', abweichler_count = 0")
            conn.commit()
        finally:
            conn.close()

    # Value: protects=a vote only one store holds is named (or counted) in the vote outcome section, old-only and new-only, with a LIST_LIMIT tail; fails_when=the one-sided count line, the ids or the tail are dropped, or only the new side is named; why_new=the per-vote list covers votes both stores hold only; seam=none; no_claim=none beyond protects
    def test_votes_only_one_store_holds_are_named(self) -> None:
        old, new = self.stores()
        for root in (old, new):
            self._figures(root)
        code, out, _ = run(old, new, "--cohort", "all")
        self.assertEqual(code, 0)
        section = "vote outcome and Abweichler"
        self.assertEqual(line_of(out, "votes only in old", section), "votes only in old: 0; only in new: 1")
        self.assertEqual(line_of(out, "only in new:", section), "only in new: v3")
        # Votes only the old store holds are named too, and a long list is cut with a count.
        conn = sqlite3.connect(old / "data" / "bundestag-pulse.sqlite")
        try:
            item = conn.execute("SELECT agenda_item_id FROM agenda_item_votes WHERE vote_id = 'v1'").fetchone()[0]
            for vote_id in ("v8", "v9"):
                conn.execute(
                    "INSERT INTO votes(id, date, application_result, abweichler_count, created_at, updated_at) VALUES (?, '2026-03-04', 'accepted', 0, ?, ?)",
                    (vote_id, NOW, NOW),
                )
                conn.execute("INSERT INTO agenda_item_votes(agenda_item_id, vote_id, basis) VALUES (?, ?, 'drucksache_xml')", (item, vote_id))
            conn.commit()
        finally:
            conn.close()
        _, out, _ = run(old, new, "--cohort", "all")
        self.assertEqual(line_of(out, "votes only in old", section), "votes only in old: 2; only in new: 1")
        self.assertEqual(line_of(out, "only in old:", section), "only in old: v8, v9")
        with mock.patch.object(compare, "LIST_LIMIT", 1):
            _, out, _ = run(old, new, "--cohort", "all")
        self.assertEqual(line_of(out, "only in old:", section), "only in old: v8 ... 1 more")

    # Value: protects=a manifest whose generation or file name is not a plain name finds no copy, so the read cannot leave the export directory; fails_when=the Path(x).name check is dropped; why_new=the names were joined unchecked; seam=none
    def test_distribution_copy_refuses_names_that_are_not_plain_file_names(self) -> None:
        import json

        directory = self.tmp / "dist"
        exports = directory / "data" / "exports"
        (exports / "g").mkdir(parents=True)
        (exports / "outside.gz").write_bytes(b"x")
        (exports / "g" / "copy.gz").write_bytes(b"x")
        for generation, name in (("g", "../outside.gz"), ("..", "outside.gz"), ("g/", "copy.gz"), ("g", "/etc/hosts"), ("", "copy.gz"), (".", "g")):
            (exports / "datenstand.json").write_text(json.dumps({"generation": generation, "files": [{"name": name}]}), encoding="utf-8")
            self.assertIsNone(compare._distribution_copy(directory), (generation, name))

    # Value: protects=a truncated or corrupt .gz Verteilkopie reads unavailable instead of a traceback; fails_when=OSError, EOFError or zlib.error escape _recipe_rows; why_new=only sqlite3.Error was caught; seam=build.RECIPES_BY_ID
    def test_a_corrupt_distribution_copy_reads_unavailable(self) -> None:
        import gzip
        import json

        import build_dip_pulse_site as build

        old, _ = self.stores()
        generation = old / "data" / "exports" / "g-0123456789ab"
        generation.mkdir(parents=True)
        good = gzip.compress(b"x" * 100000)
        for name, payload in (("truncated.sqlite.gz", good[: len(good) // 2]), ("garbage.sqlite.gz", b"\x1f\x8b\x08\x00" + b"\xff" * 64), ("plain.sqlite.gz", b"not gzip at all")):
            (generation / name).write_bytes(payload)
            (old / "data" / "exports" / "datenstand.json").write_text(json.dumps({"generation": generation.name, "files": [{"name": name}]}), encoding="utf-8")
            store = compare.open_store(old)
            try:
                with mock.patch.dict(build.RECIPES_BY_ID, {"r3-abweichler": {"sql": "SELECT id FROM votes"}}):
                    self.assertIsNone(compare._recipe_rows(store, "r3-abweichler"), name)
            finally:
                store.close()

    # Value: protects=the first store's connection is closed when the second fails to open (exit 2 prints no ResourceWarning); fails_when=compare opens both in one expression again; why_new=the first connection leaked; seam=compare.open_store wrapped
    def test_the_first_store_is_closed_when_the_second_fails_to_open(self) -> None:
        old, _ = self.stores()
        opened = []
        real = compare.open_store

        def spy(directory):
            store = real(directory)
            opened.append(store)
            return store

        with mock.patch.object(compare, "open_store", spy), self.assertRaises(compare.CompareError):
            compare.compare(old, self.tmp / "missing", out=io.StringIO())
        self.assertEqual(len(opened), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            opened[0].conn.execute("SELECT 1")

    # Value: protects=a member row on one side only is listed under its own label and is no Abweichung move, while a both-sided flag move still is; fails_when=one-sided rows count in the "abweichung moved" header or the vote line again; why_new=a registry fold that adds a row with abweichung 0 read as an Abweichung change; seam=none
    def test_member_list_changes_are_not_counted_as_abweichung_moves(self) -> None:
        old, new = self.stores()
        for root in (old, new):
            self._figures(root)
        self._add_members(old, [("v1", "mp-R1", 0, "SPD", None), ("v1", "mp-R2", 0, "SPD", None), ("v2", "mp-R1", 0, "SPD", None)])
        self._add_members(new, [("v1", "mp-R1", 1, "SPD", None), ("v2", "mp-R1", 0, "SPD", None), ("v2", "mp-R2", 0, "SPD", None)])
        code, out, _ = run(old, new)
        self.assertEqual(code, 0)
        section = "vote outcome and Abweichler"
        self.assertIn("1 votes in both stores changed their outcome, Abweichler count or Abweichungen", out)
        self.assertEqual(line_of(out, "v1: application_result", section), "v1: application_result accepted -> accepted; abweichler_count 0 -> 0; abweichung moved for 1 members")
        body = out.split(f"== {section}", 1)[1].split("\n== ", 1)[0]
        self.assertNotIn("v2: application_result", body)
        self.assertEqual(line_of(out, "member rows on one side only (", section), "member rows on one side only (the member list changed, no Abweichung moved): 2 rows in 2 votes")
        self.assertEqual(line_of(out, "MdB R2 (mp-R2) only in old", section), "MdB R2 (mp-R2) only in old, abweichung 0")
        self.assertEqual(line_of(out, "MdB R2 (mp-R2) only in new", section), "MdB R2 (mp-R2) only in new, abweichung 0")

    # Value: protects=a vote_members row whose mp_id has no mps row is counted in the flag counts and keyed by its mp_id; fails_when=the join to mps is an inner join again; why_new=orphan rows dropped out silently; seam=none
    def test_orphan_member_rows_are_counted_and_keyed_by_mp_id(self) -> None:
        old, new = self.stores()
        for root in (old, new):
            self._figures(root)
        self._add_members(old, [("v1", "mp-R1", 0, "SPD", None)])
        self._add_members(new, [("v1", "mp-R1", 0, "SPD", None), ("v1", None, 1, "SPD", None)])
        code, out, _ = run(old, new)
        self.assertEqual(code, 0)
        section = "vote outcome and Abweichler"
        self.assertEqual(line_of(out, "vote_members.abweichung = 1", section), "vote_members.abweichung = 1 0 -> 1 +1")
        self.assertEqual(line_of(out, "(no mps row) (orphan-v1)", section), "(no mps row) (orphan-v1) only in new, abweichung 1")

    # Value: protects=a re-filing that flips no Mehrheitsvotum and no Abweichler still shows, per (vote, group) counts and per member party_id and listed_party_id, and identical stores show no change; fails_when=the vote groups section is dropped or compares less; why_new=E4 deferred item 8: the comparison read neither vote_fractions counts nor party_id columns; seam=none
    def test_a_refiling_that_flips_no_outcome_shows_in_the_group_comparison(self) -> None:
        old, new = self.stores()
        for root in (old, new):
            self._figures(root)
        members = [("v1", "mp-R1", None, "SPD", None), ("v1", "mp-R2", None, "SPD", None)]
        self._add_members(old, members)
        self._add_members(new, members)
        section = "vote groups"
        _, same, _ = run(old, new)
        self.assertIn("0 of 2 shared votes changed a group's vote_fractions counts", same)
        self.assertIn("0 of 2 shared votes changed a member's party_id or listed_party_id", same)

        conn = sqlite3.connect(new / "data" / "bundestag-pulse.sqlite")
        try:
            conn.execute(
                "INSERT INTO parties(id, name, created_at, updated_at) VALUES ('party-AfD', 'AfD', ?, ?)", (NOW, NOW)
            )
            conn.execute("UPDATE vote_fractions SET yes_count = 3, total_count = 3 WHERE vote_id = 'v1'")
            conn.execute(
                "UPDATE vote_members SET party_id = 'party-AfD', listed_party_id = (SELECT id FROM parties WHERE name = 'SPD') "
                "WHERE vote_id = 'v1' AND mp_id = (SELECT id FROM mps WHERE identity_key = 'mp-R2')"
            )
            conn.commit()
        finally:
            conn.close()
        _, out, _ = run(old, new)
        self.assertIn("1 of 2 shared votes changed a group's vote_fractions counts", out)
        self.assertEqual(line_of(out, "v1: SPD", section), "v1: SPD 0/0/0/0/0 -> 3/0/0/0/3")
        self.assertIn("1 of 2 shared votes changed a member's party_id or listed_party_id", out)
        self.assertEqual(line_of(out, "MdB R2 (mp-R2)", section), "MdB R2 (mp-R2) group SPD -> AfD, listed NULL -> SPD")
        # The outcome and Abweichler lines stay unmoved: only the new section shows it.
        self.assertIn("0 votes in both stores changed their outcome", out)

    def _sql(self, root: Path, *statements: str) -> None:
        conn = sqlite3.connect(root / "data" / "bundestag-pulse.sqlite")
        try:
            for statement in statements:
                conn.execute(statement)
            conn.commit()
        finally:
            conn.close()

    # Value: protects=a group present in one store only prints "no row" and counts as a move, and a vote outside the cohort is skipped by default but compared under --cohort all; fails_when=a one-sided group is dropped, or the cohort scope is not applied to the group rows; why_new=the group test moves counts of a group both stores hold on in-cohort votes only; seam=none; no_claim=none beyond protects
    def test_a_group_in_one_store_only_is_a_move_and_votes_outside_the_cohort_are_skipped(self) -> None:
        old = make_output(
            self.tmp / "old",
            protocols={"21/1": [("R1", "SPD", 10, None)], "21/3": [("R3", "SPD", 10, None)]},
            votes=[("v1", "2026-03-04", "21/1", None, "SPD"), ("v1", "2026-03-04", "21/1", None, "AfD"), ("v3", "2026-03-04", "21/3", None, "SPD")],
        )
        new = make_output(
            self.tmp / "new",
            protocols={"21/1": [("R1", "SPD", 10, None)], "21/2": [("R4", "SPD", 10, None)]},
            votes=[("v1", "2026-03-04", "21/1", None, "SPD"), ("v1", "2026-03-04", "21/1", None, "Grüne"), ("v3", "2026-03-04", "21/2", None, "SPD")],
        )
        for root in (old, new):
            self._figures(root)
        self._sql(new, "UPDATE vote_fractions SET yes_count = 4, total_count = 4 WHERE vote_id = 'v3'")
        section = "vote groups"
        _, out, _ = run(old, new)
        self.assertIn("1 of 1 shared votes changed a group's vote_fractions counts", out)
        self.assertEqual(line_of(out, "v1:", section), "v1: AfD 0/0/0/0/0 -> no row; Grüne no row -> 0/0/0/0/0")
        self.assertNotIn("v3: SPD", out)
        _, out, _ = run(old, new, "--cohort", "all")
        self.assertIn("2 of 2 shared votes changed a group's vote_fractions counts", out)
        self.assertEqual(line_of(out, "v3:", section), "v3: SPD 0/0/0/0/0 -> 4/0/0/0/4")

    # Value: protects=a store without the vote_fractions count columns reads unavailable in the group section and the run goes on; fails_when=the count columns are read without the has() guard or a missing side counts as zero; why_new=the group test fills both stores completely; seam=none; no_claim=none beyond protects
    def test_a_store_without_vote_fractions_count_columns_reads_unavailable_in_the_group_section(self) -> None:
        old, new = self.stores()
        for root in (old, new):
            self._figures(root)
        self._sql(old, *(f"ALTER TABLE vote_fractions DROP COLUMN {column}" for column in ("yes_count", "no_count", "abstain_count", "absent_count", "total_count")))
        code, out, _ = run(old, new)
        self.assertEqual(code, 0)
        self.assertEqual(line_of(out, "(all)", "vote groups"), "(all) unavailable -> present")
        self.assertNotIn("changed a group's vote_fractions counts", out)

    # Value: protects=a store without vote_members.party_id or listed_party_id reads unavailable in its own row while the count comparison still runs; fails_when=the member columns are read without the has() guard or the early return skips the count lines; why_new=the group test has both member columns on both sides; seam=none; no_claim=none beyond protects
    def test_a_store_without_the_member_party_columns_reads_unavailable_after_the_count_lines(self) -> None:
        old, new = self.stores()
        for root in (old, new):
            self._figures(root)
        self._sql(new, "DROP INDEX idx_vote_members_party", "ALTER TABLE vote_members DROP COLUMN party_id", "ALTER TABLE vote_members DROP COLUMN listed_party_id")
        code, out, _ = run(old, new)
        self.assertEqual(code, 0)
        section = "vote groups"
        self.assertIn("0 of 2 shared votes changed a group's vote_fractions counts", out)
        self.assertEqual(line_of(out, "vote_members party_id / listed_party_id", section), "vote_members party_id / listed_party_id present -> unavailable")
        self.assertNotIn("changed a member's party_id", out)

    # Value: protects=long group, member and vote lists in the vote groups section are cut with a count of the rest; fails_when=a MEMBER_LIMIT or LIST_LIMIT tail line is dropped or cuts at the wrong item; why_new=the group tests stay within the limits; seam=none; no_claim=none beyond protects
    def test_vote_group_lists_are_cut_with_a_count_of_the_rest(self) -> None:
        old, new = self.stores()
        for root in (old, new):
            self._figures(root)
        members = [(vote, key, None, "SPD", None) for vote in ("v1", "v2") for key in ("mp-R1", "mp-R2")]
        self._add_members(old, members)
        self._add_members(new, members)
        self._sql(
            new,
            "INSERT INTO parties(id, name, created_at, updated_at) VALUES ('party-AfD', 'AfD', '%s', '%s')" % (NOW, NOW),
            "INSERT INTO vote_fractions(vote_id, party_id, leading_vote, rank) VALUES ('v1', 'party-AfD', NULL, 2)",
            "UPDATE vote_fractions SET yes_count = 2, total_count = 2 WHERE party_id = 'party-SPD'",
            "UPDATE vote_members SET party_id = 'party-AfD'",
        )
        with mock.patch.object(compare, "MEMBER_LIMIT", 1), mock.patch.object(compare, "LIST_LIMIT", 1):
            code, out, _ = run(old, new)
        self.assertEqual(code, 0)
        section = "vote groups"
        body = out.split(f"== {section}", 1)[1].split("\n== ", 1)[0]
        self.assertIn("2 of 2 shared votes changed a group's vote_fractions counts", body)
        self.assertEqual(line_of(out, "v1: AfD", section), "v1: AfD no row -> 0/0/0/0/0; ... 1 more groups")
        self.assertNotIn("v2: ", body.split("changed a member's")[0])
        self.assertEqual(line_of(out, "v1: 2 members", section), "v1: 2 members")
        self.assertEqual(line_of(out, "MdB R1", section), "MdB R1 (mp-R1) group SPD -> AfD, listed NULL -> NULL")
        self.assertEqual(line_of(out, "... 1 more members", section), "... 1 more members")
        self.assertEqual(body.count("... 1 more votes"), 2)

    def test_it_only_reads(self) -> None:
        old, new = self.stores()
        paths = [old / "data" / "bundestag-pulse.sqlite", new / "data" / "bundestag-pulse.sqlite"]
        before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
        run(old, new)
        self.assertEqual(before, [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths])
        self.assertEqual([], sorted(p.name for d in (old, new) for p in (d / "data").iterdir() if p.suffix != ".sqlite"))

    def test_an_input_that_is_not_an_output_directory_exits_2(self) -> None:
        old, _ = self.stores()
        code, out, err = run(old, self.tmp / "missing")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("ERROR [compare]:", err)
        self.assertIn("missing", err)

    def test_help_documents_argument_order_cohort_default_and_exit_codes(self) -> None:
        # argparse wraps to $COLUMNS and can break "Read-only" at its hyphen in a
        # narrow terminal; pin the width so the test does not depend on it.
        with mock.patch.dict(os.environ, {"COLUMNS": "200"}):
            text = compare.build_parser().format_help()
        for needle in ("old_dir", "new_dir", "shared (default)", "Exit codes: 0", "2 an input", "Read-only"):
            self.assertIn(needle, " ".join(text.split()))


if __name__ == "__main__":
    unittest.main()
