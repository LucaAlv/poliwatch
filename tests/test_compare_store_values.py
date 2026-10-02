from __future__ import annotations

import contextlib
import hashlib
import io
import re
import tempfile
import unittest
from pathlib import Path

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
    fact: dict | None = None,
    bills: int | None = None,
    roster: bool = True,
) -> Path:
    """An output directory with a tiny store.

    ``protocols``: document number -> speeches as (rede_id, fraktion, chars,
    sprechrolle). ``votes``: (vote id, date, document number, leading_vote,
    party) rows, one vote_fractions row each.
    """
    (root / "data").mkdir(parents=True)
    conn = pulse_store.connect(root / "data" / "bundestag-pulse.sqlite")
    try:
        pulse_store.initialize(conn)
        if not sprechrolle:
            # An older schema: the store predates the column.
            conn.execute("ALTER TABLE speeches DROP COLUMN sprechrolle")
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
                mp = pulse_store.upsert_mp(conn, now=NOW, identity_key=f"mp-{rede_id}", display_name=f"MdB {rede_id}", party_id=party(fraktion or "SPD"), is_mdb=roster)
                conn.execute(
                    "INSERT INTO speeches(id, protocol_id, agenda_item_id, rede_id, sequence, mp_id, char_count, "
                    "fraktion, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"speech-{protocol_id}-{rede_id}", protocol_id, items[number], rede_id, sequence, mp, chars, fraktion, NOW, NOW),
                )
                if sprechrolle:
                    conn.execute("UPDATE speeches SET sprechrolle = ? WHERE rede_id = ?", (role, rede_id))
        for vote_id, date, number, leading, party_name in votes:
            if not conn.execute("SELECT 1 FROM votes WHERE id = ?", (vote_id,)).fetchone():
                conn.execute(
                    "INSERT INTO votes(id, date, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (vote_id, date, NOW, NOW),
                )
                conn.execute(
                    "INSERT INTO agenda_item_votes(agenda_item_id, vote_id) VALUES (?, ?)", (items[number], vote_id)
                )
            conn.execute(
                "INSERT INTO vote_fractions(vote_id, party_id, leading_vote) VALUES (?, ?, ?)",
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
        text = compare.build_parser().format_help()
        for needle in ("old_dir", "new_dir", "shared (default)", "Exit codes: 0", "2 an input", "Read-only"):
            self.assertIn(needle, " ".join(text.split()))


if __name__ == "__main__":
    unittest.main()
