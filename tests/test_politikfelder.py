from __future__ import annotations

import contextlib
import copy
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

import _support  # noqa: F401
import build_dip_pulse_site as build
import derive
import persist_dip_pulse_store as pulse_store
import politikfelder as pf
import render_dip_pulse_html as pulse_html
import validate_dip_protocol as dip
from _support import FIXTURES

#: The 28 DIP Sachgebiete (DIP documentation, checked against /vorgang on 2026-10-04).
DIP_SACHGEBIETE = (
    "Arbeit und Beschäftigung",
    "Außenpolitik und internationale Beziehungen",
    "Außenwirtschaft",
    "Bildung und Erziehung",
    "Bundestag",
    "Deutsche Einheit / Innerdeutsche Beziehungen (bis 1990)",
    "Energie",
    "Entwicklungspolitik",
    "Europapolitik und Europäische Union",
    "Gesellschaftspolitik, soziale Gruppen",
    "Gesundheit",
    "Innere Sicherheit",
    "Kultur",
    "Landwirtschaft und Ernährung",
    "Medien, Kommunikation und Informationstechnik",
    "Migration und Aufenthaltsrecht",
    "Politisches Leben, Parteien",
    "Raumordnung, Bau- und Wohnungswesen",
    "Recht",
    "Soziale Sicherung",
    "Sport, Freizeit und Tourismus",
    "Staat und Verwaltung",
    "Umwelt",
    "Verkehr",
    "Verteidigung",
    "Wirtschaft",
    "Wissenschaft, Forschung und Technologie",
    "Öffentliche Finanzen, Steuern und Abgaben",
)

#: Every (Wahlperiode, Einzelplan) pair in the Einzelplan headings of the WP 20 and
#: 21 cache on 2026-10-04.
EINZELPLAENE_IN_THE_CACHE = (
    [("20", n) for n in "01 02 03 04 05 06 07 08 09 10 11 12 14 15 16 17 19 20 21 22 23 25 30 32 60".split()]
    + [("21", n) for n in "01 02 03 04 05 06 07 08 09 10 11 12 14 15 16 17 19 20 21 22 23 24 25 30 32 60".split()]
)


def vorgang(*sachgebiete: str, typ: str = "Gesetzgebung") -> dict[str, Any]:
    return {"sachgebiet": list(sachgebiete), "vorgangstyp": typ}


def position(vorgang_id: str, typ: str = "Antrag", *, twins: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "id": f"pos-{vorgang_id}",
        "vorgang_id": vorgang_id,
        "vorgangstyp": typ,
        "vorgangsposition": "Beschlussempfehlung",
        "titel": f"Titel {vorgang_id}",
        "mitberaten": [{"id": twin, "titel": f"Twin {twin}", "vorgangstyp": "Antrag"} for twin in twins],
    }


def item(index: int = 1, *, positions: tuple[dict[str, Any], ...] = (), heading: str = "Beratung", votes=(), numbers=()) -> dict[str, Any]:
    return {
        "index": index,
        "top_id": f"TOP {index}",
        "heading": heading,
        "api": {"positions": list(positions), "linked_drucksachen": []},
        "xml_drucksachen": [{"dokumentnummer": n} for n in numbers],
        "votes": list(votes),
    }


def cache_of(vorgaenge: dict[str, Any] | None = None, numbers: dict[str, list[str]] | None = None) -> dict[str, Any]:
    return {"version": 1, "vorgaenge": vorgaenge or {}, "dokumentnummern": numbers or {}}


class ClosedListTests(unittest.TestCase):
    def test_every_mapped_value_is_in_the_closed_list(self) -> None:
        self.assertEqual(len(pf.POLITIKFELDER), 13)
        self.assertEqual(len(set(pf.POLITIKFELDER)), 13)
        allowed = set(pf.POLITIKFELDER) | {pf.UNTAGGED}
        self.assertLessEqual(set(pf.SACHGEBIET_TO_POLITIKFELD.values()), allowed)
        for key, fields in pf.EINZELPLAN_TO_POLITIKFELDER.items():
            self.assertTrue(fields, key)
            self.assertLessEqual(set(fields), set(pf.POLITIKFELDER), key)
        self.assertEqual(set(pf.ALLOWED_LABELS), allowed)

    def test_all_28_sachgebiete_are_mapped_and_every_field_is_reachable(self) -> None:
        self.assertEqual(len(DIP_SACHGEBIETE), 28)
        self.assertEqual(set(pf.SACHGEBIET_TO_POLITIKFELD), set(DIP_SACHGEBIETE))
        self.assertEqual(set(pf.SACHGEBIET_TO_POLITIKFELD.values()), set(pf.POLITIKFELDER))

    def test_every_einzelplan_pair_of_the_cache_is_mapped(self) -> None:
        for pair in EINZELPLAENE_IN_THE_CACHE:
            self.assertIn(pair, pf.EINZELPLAN_TO_POLITIKFELDER)

    def test_every_einzelplan_of_the_real_store_is_mapped(self) -> None:
        data = Path(__file__).resolve().parent.parent / ".context" / "dip-pulse-site" / "data"
        reports = sorted(data.glob("plenarprotokoll-2*.json"))
        if not reports:
            self.skipTest("no cached store in this checkout")
        import re

        seen = set()
        for path in reports:
            report = json.loads(path.read_text(encoding="utf-8"))
            wahlperiode = derive.report_wahlperiode(report)
            for agenda_item in report.get("agenda_items") or []:
                for match in re.finditer(r"\bEinzelplan\s+(\d{1,2})\b", str(agenda_item.get("heading") or "")):
                    seen.add((wahlperiode, match.group(1).zfill(2)))
        self.assertLessEqual(seen, set(pf.EINZELPLAN_TO_POLITIKFELDER))

    def test_an_unknown_sachgebiet_is_skipped_and_reported(self) -> None:
        self.assertEqual(pf.fields_for_sachgebiete(["Gesundheit", "Neues Gebiet", "Recht"]), ["Gesundheit", "Justiz"])
        cache = cache_of({"1": vorgang("Neues Gebiet", "Gesundheit")})
        self.assertEqual(pf.unknown_sachgebiete(cache), {"Neues Gebiet"})


class AgendaItemTests(unittest.TestCase):
    def tags(self, agenda_item: dict[str, Any], cache: dict[str, Any], wahlperiode: str = "21"):
        return pf.tags_for_agenda_item(agenda_item, cache, wahlperiode=wahlperiode)

    def test_lead_vorgang_comes_first_and_the_rest_by_frequency(self) -> None:
        cache = cache_of(
            {
                "lead": vorgang("Wirtschaft", "Umwelt"),
                "a": vorgang("Gesundheit"),
                "b": vorgang("Gesundheit", "Recht"),
                "c": vorgang("Recht"),
                "d": vorgang("Verkehr"),
            }
        )
        # The Antrag comes first in DIP order, the Gesetzgebung Vorgang leads anyway.
        top = item(positions=(position("a"), position("lead", "Gesetzgebung"), position("b"), position("c"), position("d")))
        tags, source = self.tags(top, cache)
        self.assertEqual(source, "sachgebiet")
        # Gesundheit and Recht are each carried by two other Vorgänge: the tie goes to POLITIKFELDER order.
        self.assertEqual(tags, ["Wirtschaft & Finanzen", "Energie & Klima", "Justiz"])

    def test_ties_break_in_closed_list_order_and_the_cap_is_three(self) -> None:
        cache = cache_of({"a": vorgang("Recht"), "b": vorgang("Gesundheit"), "c": vorgang("Verkehr"), "d": vorgang("Bundestag")})
        top = item(positions=(position("a"), position("b"), position("c"), position("d")))
        tags, _ = self.tags(top, cache)
        self.assertEqual(tags, ["Justiz", "Gesundheit", "Verkehr"])
        self.assertLessEqual(len(tags), pf.MAX_TAGS)

    def test_a_mitberaten_twin_counts_as_a_vorgang(self) -> None:
        cache = cache_of({"a": vorgang(), "twin": vorgang("Verteidigung")})
        top = item(positions=(position("a", twins=("twin",)),))
        self.assertEqual(self.tags(top, cache), (["Verteidigung"], "sachgebiet"))

    def test_a_vorgang_without_sachgebiet_falls_through_to_the_drucksache(self) -> None:
        cache = cache_of({"a": vorgang(), "b": vorgang("Energie")}, {"21/5": ["b"]})
        top = item(positions=(position("a"),), numbers=("21/5",))
        self.assertEqual(self.tags(top, cache), (["Energie & Klima"], "drucksache"))

    def test_no_positions_uses_the_drucksache_numbers_of_the_top(self) -> None:
        cache = cache_of({"b": vorgang("Kultur")}, {"21/7": ["b"]})
        top = item(numbers=("21/7",))
        self.assertEqual(self.tags(top, cache), (["Bildung"], "drucksache"))

    def test_heading_numbers_count_only_for_the_sittings_wahlperiode(self) -> None:
        top = item(heading="Streitsachen 10/21, 1/22, 21/9 und 20/8")
        self.assertEqual(derive.item_document_numbers(top, "21"), ["21/9"])

    def test_a_bundled_drucksache_ranks_the_vorgang_most_numbers_name(self) -> None:
        cache = cache_of(
            {"x": vorgang("Verkehr"), "y": vorgang("Gesundheit"), "z": vorgang("Recht")},
            {"21/1": ["x", "y", "z"], "21/2": ["y"], "21/3": ["y"]},
        )
        top = item(numbers=("21/1", "21/2", "21/3"))
        self.assertEqual(self.tags(top, cache)[0][0], "Gesundheit")

    def test_einzelplan_by_wahlperiode_and_number(self) -> None:
        cache = cache_of()
        # Einzelplan 12 is Digitales und Verkehr in WP 20 and Verkehr in WP 21.
        top = item(heading="Einzelplan 12 Bundesministerium für Verkehr")
        self.assertEqual(self.tags(top, cache_of(), "20"), (["Verkehr", "Digitales"], "einzelplan"))
        self.assertEqual(self.tags(top, cache, "21"), (["Verkehr"], "einzelplan"))

    def test_a_bundled_einzelplan_heading_takes_each_in_order_and_caps_at_three(self) -> None:
        top = item(heading="Einzelplan 06 Inneres b) hier: Einzelplan 07 Justiz und Einzelplan 14")
        tags, source = self.tags(top, cache_of(), "21")
        self.assertEqual(source, "einzelplan")
        self.assertEqual(tags, ["Innere Sicherheit", "Migration", "Justiz"])

    def test_an_unknown_einzelplan_pair_is_marked(self) -> None:
        top = item(heading="Einzelplan 99 Neu")
        self.assertEqual(self.tags(top, cache_of()), ([pf.UNTAGGED], "einzelplan_unknown"))
        self.assertEqual(self.tags(item(heading="Einzelplan 06"), cache_of(), "17"), ([pf.UNTAGGED], "einzelplan_unknown"))

    def test_a_fragestunde_is_untagged(self) -> None:
        self.assertEqual(self.tags(item(heading="Fragestunde"), cache_of()), ([pf.UNTAGGED], "untagged"))

    def test_a_cache_miss_is_not_fetched_and_a_fetched_empty_vorgang_is_untagged(self) -> None:
        top = item(positions=(position("a"),))
        self.assertEqual(self.tags(top, cache_of()), ([pf.UNTAGGED], "not_fetched"))
        self.assertEqual(self.tags(top, cache_of({"a": vorgang()})), ([pf.UNTAGGED], "untagged"))
        numbers = item(numbers=("21/7",))
        self.assertEqual(self.tags(numbers, cache_of()), ([pf.UNTAGGED], "not_fetched"))
        self.assertEqual(self.tags(numbers, cache_of(numbers={"21/7": []})), ([pf.UNTAGGED], "untagged"))

    def test_tags_beat_a_missing_entry(self) -> None:
        cache = cache_of({"a": vorgang("Gesundheit")})
        top = item(positions=(position("a"), position("missing")))
        self.assertEqual(self.tags(top, cache), (["Gesundheit"], "sachgebiet"))


class VoteTests(unittest.TestCase):
    def test_own_drucksache_comes_before_the_tops_tags(self) -> None:
        cache = cache_of({"mine": vorgang("Gesundheit")}, {"21/1": ["mine"]})
        vote = {"id": "v", "document_numbers": ["21/1"]}
        top_tags = [(["Verkehr", "Recht"], "sachgebiet")]
        self.assertEqual(pf.tags_for_vote(vote, top_tags, cache), (["Gesundheit"], "drucksache"))

    def test_a_beschlussempfehlung_ranks_its_own_vorgang_among_a_bundle(self) -> None:
        cache = cache_of(
            {"main": vorgang("Verkehr"), "other": vorgang("Recht")},
            {"21/1": ["main"], "21/2": ["main"], "21/3": ["other", "main"]},
        )
        vote = {"document_numbers": ["21/3", "21/1", "21/2"]}
        self.assertEqual(pf.tags_for_vote(vote, [], cache), (["Verkehr", "Justiz"], "drucksache"))

    def test_without_a_resolvable_drucksache_the_votes_tops_decide(self) -> None:
        cache = cache_of({"x": vorgang()}, {"21/1": ["x"]})
        vote = {"document_numbers": ["21/1"]}
        union = pf.tags_for_vote(vote, [(["Verkehr", "Recht"], "sachgebiet"), (["Recht", "Bildung"], "einzelplan")], cache)
        self.assertEqual(union, (["Verkehr", "Recht", "Bildung"], "top"))

    def test_untagged_tops_give_an_untagged_vote_and_a_miss_gives_not_fetched(self) -> None:
        vote = {"document_numbers": []}
        self.assertEqual(pf.tags_for_vote(vote, [([pf.UNTAGGED], "untagged")], cache_of()), ([pf.UNTAGGED], "untagged"))
        self.assertEqual(pf.tags_for_vote(vote, [], cache_of()), ([pf.UNTAGGED], "untagged"))
        self.assertEqual(pf.tags_for_vote(vote, [([pf.UNTAGGED], "not_fetched")], cache_of()), ([pf.UNTAGGED], "not_fetched"))
        self.assertEqual(pf.tags_for_vote({"document_numbers": ["21/9"]}, [], cache_of()), ([pf.UNTAGGED], "not_fetched"))

    def test_a_vote_under_two_tops_takes_the_union_over_both(self) -> None:
        cache = cache_of({"a": vorgang("Verkehr"), "b": vorgang("Recht")})
        shared = {"id": "v1", "title": "Geteilt", "date": "2026-01-01"}
        report = {
            "protocol": {"dokumentnummer": "21/5"},
            "agenda_items": [
                item(1, positions=(position("a"),), votes=(shared,)),
                item(2, positions=(position("b"),), votes=(shared,)),
            ],
        }
        _, vote_tags = pf.report_politikfelder(report, cache)
        self.assertEqual(vote_tags["v1"], (["Verkehr", "Justiz"], "top"))

    def test_sitting_votes_without_a_top_use_their_own_drucksache(self) -> None:
        cache = cache_of({"a": vorgang("Energie")}, {"21/1": ["a"]})
        report = {"protocol": {"dokumentnummer": "21/5"}, "agenda_items": [], "sitting_votes": [{"id": "s", "document_numbers": ["21/1"]}]}
        _, vote_tags = pf.report_politikfelder(report, cache)
        self.assertEqual(vote_tags["s"], (["Energie & Klima"], "drucksache"))


class CacheFileTests(unittest.TestCase):
    def test_absent_file_is_an_empty_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(pf.load_cache(tmp), pf.empty_cache())

    def test_corrupt_or_misshapen_json_warns_and_is_treated_as_empty(self) -> None:
        for text in ("{not json", json.dumps({"vorgaenge": []}), json.dumps({"vorgaenge": {}}), "[]"):
            with tempfile.TemporaryDirectory() as tmp:
                path = pf.cache_path(tmp)
                path.parent.mkdir(parents=True)
                path.write_text(text, encoding="utf-8")
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    cache = pf.load_cache(tmp)
                self.assertEqual(cache, pf.empty_cache(), text)
                self.assertIn("warning", err.getvalue())

    def test_save_then_load_round_trips(self) -> None:
        cache = cache_of({"1": vorgang("Recht")}, {"21/1": ["1"]})
        with tempfile.TemporaryDirectory() as tmp:
            pf.save_cache(tmp, cache)
            self.assertEqual(pf.load_cache(tmp), cache)


class FakeClient:
    """An ApiClient stand-in that answers ``/vorgang`` from a dict and records the calls."""

    def __init__(self, records: dict[str, dict[str, Any]], numbers: dict[str, list[str]] | None = None, fail: bool = False):
        self.records = records
        self.numbers = numbers or {}
        self.fail = fail
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list_all(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self.calls.append((path, dict(params or {})))
        if self.fail:
            raise dip.DipError("boom")
        if "f.id" in params:
            return [{"id": i, **self.records[i]} for i in params["f.id"] if i in self.records]
        return [{"id": i, **self.records[i]} for i in self.numbers.get(params["f.dokumentnummer"], [])]


def raw(*sachgebiete: str) -> dict[str, Any]:
    return {"sachgebiet": list(sachgebiete), "abstract": "A", "vorgangstyp": "Antrag", "aktualisiert": "2026-01-01",
            "deskriptor": [{"name": "Wolf", "typ": "Sachbegriffe"}, {"name": "Bund", "typ": "Geografisch"}]}


class FetchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entries = [
            {
                "report": {
                    "protocol": {"dokumentnummer": "21/5"},
                    "agenda_items": [
                        item(1, positions=(position("a"), position("b"))),
                        item(2, heading="Beratung", numbers=("21/7",)),
                        item(3, heading="Fragestunde"),
                    ],
                    "sitting_votes": [{"id": "s", "document_numbers": ["21/8"]}],
                }
            }
        ]

    def run_refresh(self, client: FakeClient, cache: dict[str, Any]):
        self.enterContext(mock.patch.object(build, "NUMBER_LOOKUP_PAUSE", 0))
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()) as err:
            stats = build.refresh_vorgang_cache(client, self.entries, cache, Path(tmp))
            saved = pf.load_cache(tmp)
        return stats, saved, err.getvalue()

    def test_only_missing_vorgaenge_and_numbers_are_fetched_and_the_cache_is_saved(self) -> None:
        client = FakeClient(
            {"a": raw("Gesundheit"), "b": raw("Recht"), "c": raw("Kultur"), "d": raw("Energie")},
            {"21/7": ["c"], "21/8": ["d"]},
        )
        cache = cache_of({"a": pf.__dict__["empty_cache"]() and dip.vorgang_cache_record(raw("Gesundheit"))})
        stats, saved, _ = self.run_refresh(client, cache)
        id_calls = [params["f.id"] for path, params in client.calls if "f.id" in params]
        self.assertEqual(id_calls, [["b"]])  # a was complete, so it stays cached
        number_calls = [params["f.dokumentnummer"] for _, params in client.calls if "f.dokumentnummer" in params]
        self.assertEqual(number_calls, ["21/7", "21/8"])  # the Fragestunde names none
        self.assertEqual(stats["nummern"], 2)
        self.assertEqual(saved["dokumentnummern"], {"21/7": ["c"], "21/8": ["d"]})
        self.assertEqual(saved["vorgaenge"]["c"]["sachgebiet"], ["Kultur"])
        self.assertEqual(saved["vorgaenge"]["c"]["deskriptor_sachbegriffe"], ["Wolf"])
        self.assertEqual(saved["vorgaenge"]["c"]["abstract"], "A")

    def test_a_cached_vorgang_without_sachgebiet_is_refetched_and_a_second_run_fetches_nothing(self) -> None:
        records = {"a": raw("Gesundheit"), "b": raw("Recht")}
        cache = cache_of({"a": dip.vorgang_cache_record(raw()), "b": dip.vorgang_cache_record(raw("Recht"))}, {"21/7": [], "21/8": []})
        client = FakeClient(records)
        self.run_refresh(client, cache)
        self.assertEqual([p["f.id"] for _, p in client.calls], [["a"]])
        self.assertEqual(cache["vorgaenge"]["a"]["sachgebiet"], ["Gesundheit"])
        again = FakeClient(records)
        self.run_refresh(again, cache)
        self.assertEqual(again.calls, [])

    def test_ids_are_batched_by_the_batch_size(self) -> None:
        ids = [str(i) for i in range(dip.VORGANG_BATCH * 2 + 5)]
        client = FakeClient({i: raw("Recht") for i in ids})
        found = dip.fetch_vorgaenge(client, ids)
        self.assertEqual([len(p["f.id"]) for _, p in client.calls], [dip.VORGANG_BATCH, dip.VORGANG_BATCH, 5])
        self.assertEqual(len(found), len(ids))

    def test_an_id_dip_does_not_return_is_recorded_as_empty(self) -> None:
        self.assertEqual(dip.fetch_vorgaenge(FakeClient({}), ["gone"])["gone"]["sachgebiet"], [])

    def test_a_failed_fetch_warns_leaves_a_cache_miss_and_does_not_abort(self) -> None:
        stats, saved, err = self.run_refresh(FakeClient({}, fail=True), pf.empty_cache())
        self.assertIn("warning", err)
        self.assertEqual(saved["vorgaenge"], {})
        self.assertGreater(stats["vorgaenge_failed"], 0)
        self.assertGreater(stats["nummern_failed"], 0)
        top_tags, vote_tags = pf.report_politikfelder(self.entries[0]["report"], saved)
        self.assertEqual(top_tags[0], ([pf.UNTAGGED], "not_fetched"))
        self.assertEqual(top_tags[2], ([pf.UNTAGGED], "untagged"))
        self.assertEqual(vote_tags["s"], ([pf.UNTAGGED], "not_fetched"))

    def test_fetch_targets_asks_for_nothing_when_the_cache_is_complete(self) -> None:
        reports = [self.entries[0]["report"]]
        cache = cache_of(
            {"a": vorgang("Recht"), "b": vorgang("Recht"), "c": vorgang("Kultur"), "d": vorgang("Energie")},
            {"21/7": ["c"], "21/8": ["d"]},
        )
        self.assertEqual(pf.fetch_targets(reports, cache), ([], []))


def fixture_report() -> dict[str, Any]:
    return json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))


class PersistTests(unittest.TestCase):
    def persisted(self, cache: dict[str, Any] | None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = pulse_store.connect(Path(tmp.name) / "store.sqlite")
        self.addCleanup(conn.close)
        report = fixture_report()
        report["agenda_items"][0]["api"]["positions"] = [position("v1", "Gesetzgebung")]
        pulse_store.persist_report(conn, report, cache)
        return conn

    def test_rows_are_written_with_source_and_rank(self) -> None:
        conn = self.persisted(cache_of({"v1": vorgang("Gesundheit", "Recht")}))
        top = [tuple(r) for r in conn.execute(
            "SELECT politikfeld, rank, source FROM agenda_item_politikfelder JOIN agenda_items a ON a.id = agenda_item_id "
            "WHERE a.item_index = 1 ORDER BY rank")]
        self.assertEqual(top, [("Gesundheit", 1, "sachgebiet"), ("Justiz", 2, "sachgebiet")])
        votes = [tuple(r) for r in conn.execute("SELECT politikfeld, rank, source FROM vote_politikfelder ORDER BY rank")]
        self.assertEqual(votes, [("Gesundheit", 1, "top"), ("Justiz", 2, "top")])
        self.assertEqual(
            conn.execute("SELECT sachgebiet FROM proceedings WHERE id = 'v1'").fetchone()[0],
            json.dumps(["Gesundheit", "Recht"], ensure_ascii=False),
        )

    def test_untagged_and_not_fetched_are_stored_as_explicit_rows(self) -> None:
        conn = self.persisted(None)
        rows = {tuple(r) for r in conn.execute("SELECT politikfeld, source FROM agenda_item_politikfelder")}
        self.assertEqual(rows, {("untagged", "not_fetched"), ("untagged", "untagged")})
        self.assertEqual({tuple(r) for r in conn.execute("SELECT politikfeld, source FROM vote_politikfelder")}, {("untagged", "not_fetched")})
        self.assertIsNone(conn.execute("SELECT sachgebiet FROM proceedings WHERE id = 'v1'").fetchone()[0])

    def test_every_vote_has_at_least_one_row(self) -> None:
        for cache in (None, cache_of({"v1": vorgang("Gesundheit")})):
            conn = self.persisted(cache)
            self.assertGreater(conn.execute("SELECT count(*) FROM votes").fetchone()[0], 0)
            self.assertEqual(
                conn.execute("SELECT count(*) FROM votes WHERE id NOT IN (SELECT vote_id FROM vote_politikfelder)").fetchone()[0], 0
            )

    def test_the_check_constraint_rejects_a_label_outside_the_list(self) -> None:
        conn = self.persisted(cache_of({"v1": vorgang("Gesundheit")}))
        vote_id = conn.execute("SELECT id FROM votes").fetchone()[0]
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO vote_politikfelder VALUES (?, 'Esoterik', 9, 'sachgebiet')", (vote_id,))
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO vote_politikfelder VALUES (?, 'Recht', 9, 'sachgebiet')", (vote_id,))
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO vote_politikfelder VALUES (?, 'Justiz', 9, 'geraten')", (vote_id,))

    def test_persisting_again_replaces_the_rows(self) -> None:
        conn = self.persisted(cache_of({"v1": vorgang("Gesundheit")}))
        report = fixture_report()
        report["agenda_items"][0]["api"]["positions"] = [position("v1", "Gesetzgebung")]
        pulse_store.persist_report(conn, report, cache_of({"v1": vorgang("Verkehr")}))
        self.assertEqual(
            {r[0] for r in conn.execute("SELECT politikfeld FROM vote_politikfelder")}, {"Verkehr"}
        )


class RenderTests(unittest.TestCase):
    def report(self) -> dict[str, Any]:
        report = fixture_report()
        report["agenda_items"][0]["api"]["positions"] = [position("v1", "Gesetzgebung")]
        return report

    def test_the_dossier_shows_static_chips_and_none_for_an_untagged_top(self) -> None:
        report = self.report()
        before = copy.deepcopy(report)
        markup = pulse_html.render_html(report, vorgang_cache=cache_of({"v1": vorgang("Gesundheit", "Recht")}))
        self.assertIn('<ul class="pf-tags" aria-label="Politikfelder"><li class="pf-tag">Gesundheit</li><li class="pf-tag">Justiz</li></ul>', markup)
        self.assertEqual(markup.count('class="pf-tags"'), 1)  # the Fragestunde TOP has no chip
        self.assertNotIn("untagged", markup)
        self.assertEqual(report, before)  # nothing is written into the report

    def test_no_cache_means_no_chips(self) -> None:
        self.assertNotIn('class="pf-tags"', pulse_html.render_html(self.report()))

    def archive_rows(self, cache: dict[str, Any] | None):
        entry = {"report": self.report(), "page_path": Path("plenarprotokoll-20-999.html")}
        return build.collect_votes_archive([entry], cache)

    def test_the_archive_rows_carry_the_votes_politikfelder_and_page_has_chips_and_filter(self) -> None:
        rows = self.archive_rows(cache_of({"v1": vorgang("Gesundheit", "Recht")}))
        self.assertEqual(rows[0]["politikfelder"], ["Gesundheit", "Justiz"])
        page = build.render_votes_archive_index(rows)
        self.assertIn('data-politikfeld-chip="Gesundheit"', page)
        self.assertIn('data-politikfeld-chip="Justiz"', page)
        self.assertNotIn('data-politikfeld-chip="Verkehr"', page)  # only fields a vote carries
        self.assertNotIn('data-politikfeld-chip="untagged"', page)
        self.assertIn("data-politikfelder='[&quot;Gesundheit&quot;, &quot;Justiz&quot;]'", page)
        self.assertIn("getAll('politikfeld')", page)
        self.assertIn('<li class="pf-tag">Gesundheit</li>', page)
        # Without script every row stays visible: nothing is hidden in the markup.
        self.assertNotIn(" hidden>", page.split('data-archive>')[1].split("data-no-results")[0])

    def test_the_archive_offers_untagged_as_a_filter_but_not_as_a_label(self) -> None:
        tagged = self.archive_rows(cache_of({"v1": vorgang("Gesundheit")}))[0]
        untagged = self.archive_rows(None)[0]
        self.assertEqual(untagged["politikfelder"], [pf.UNTAGGED])
        page = build.render_votes_archive_index([tagged, untagged])
        self.assertIn('data-politikfeld-chip="untagged">Ohne Politikfeld</button>', page)
        self.assertEqual(page.count('class="pf-tag"'), 1)  # the untagged row gets no label
        # With no tag anywhere there is nothing to filter by, so no filter row.
        self.assertNotIn('data-politikfeld-chip="', build.render_votes_archive_index([untagged]))

    def test_the_week_radar_rows_carry_chips_and_a_filter(self) -> None:
        report = self.report()
        report["agenda_items"][0]["xml_speakers"] = [
            {"speaker": {"name": "A", "faction": "SPD"}, "text": "x", "text_length": 1, "rede_id": "r1"}
        ]
        entry = {"report": report, "page_path": Path("plenarprotokoll-20-999.html")}
        radar = pulse_html.week_topic_rows(
            [entry], {}, total=1, dossier_href_for=lambda e: "protocols/x.html",
            vorgang_cache=cache_of({"v1": vorgang("Verkehr")}),
        )
        if not radar["rows"]:
            self.skipTest("fixture has no ranked speech")
        row = radar["rows"][0]
        self.assertEqual(row["politikfelder"], ["Verkehr"])
        markup = build.render_radar_section(radar, {"speech_count": 1}, build.publication_selection())
        self.assertIn('data-radar-chip="Verkehr"', markup)
        self.assertIn('<li class="pf-tag">Verkehr</li>', markup)
        self.assertIn("data-politikfelder='[&quot;Verkehr&quot;]'", markup)
        self.assertIn('<ul class="radar-list">', markup)


if __name__ == "__main__":
    unittest.main()
