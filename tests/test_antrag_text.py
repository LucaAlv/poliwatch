"""The quoted Antrag passage of a vote without a DIP abstract (antrag_text).

The Antrag texts below are synthetic: written in the layout of a DIP
``drucksache-text`` body (running heads, page numbers, wrapped lines, break
hyphens), not copied from a real Drucksache. Real texts replace them after the
step-0 measurement on the owner's machine (docs/plans/b4-extractive-antrag.md).
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import antrag_text
import build_dip_pulse_site as build
import persist_dip_pulse_store as pulse_store
import politikfelder
import speech_kinds
from _support import FIXTURES
from _votes_fixture import vote_summary


ANTRAG = """Deutscher Bundestag Drucksache 20/123
20. Wahlperiode 10.01.2024
Antrag
der Fraktion der CDU/CSU
Testantrag
Der Bundestag wolle beschließen:
I. Der Deutsche Bundestag stellt fest:
Die Lage ist ernst und erfordert ein Han-
deln.
II. Der Deutsche Bundestag fordert die Bundesre-
gierung auf,
1. die Bedarfssätze zum Wintersemester an-
zuheben und die Bundes-
und Landesförderung abzustimmen;
Drucksache 20/123 – 2 – Deutscher Bundestag – 20. Wahlperiode
2. die E-
Mobilität für Studierende zu fördern;
– 3 –
3. dem Bundestag jährlich zu berichten.
Berlin, den 9. Januar 2024
Friedrich Merz, Alexander Dobrindt und Fraktion
Begründung
Die Begründung wird nie zitiert.
"""

OPENING = "Der Deutsche Bundestag fordert die Bundesregierung auf,"
DEMANDS = (
    "1. die Bedarfssätze zum Wintersemester anzuheben und die Bundes- und Landesförderung abzustimmen;",
    "2. die E-Mobilität für Studierende zu fördern;",
    "3. dem Bundestag jährlich zu berichten.",
)


def drucksache(number="20/123", drucksache_id="D1", typ="Antrag", vorgang_ids=("vorgang-1",), **extra):
    return {
        "id": drucksache_id, "dokumentnummer": number, "herausgeber": "BT", "drucksachetyp": typ,
        "titel": "Testantrag", "datum": "2024-01-10", "urheber": ["Fraktion der CDU/CSU"],
        "vorgang_ids": list(vorgang_ids), "pdf_url": "https://dserver.bundestag.de/btd/20/001/2000123.pdf",
        "aktualisiert": None, **extra,
    }


def cache(abstract="", nummern=None, texte=None):
    """A Vorgang cache in which the fixture report's vote 12345 (Drucksache 20/123)
    is about vorgang-1, with the Drucksache cache riding along."""
    return {
        "version": 1,
        "vorgaenge": {"vorgang-1": {"sachgebiet": ["Recht"], "titel": "Testgesetz", "abstract": abstract}},
        "dokumentnummern": {"20/123": ["vorgang-1"]},
        antrag_text.CACHE_KEY: {
            "version": 1,
            "nummern": {"20/123": [drucksache()]} if nummern is None else nummern,
            "texte": {"D1": {"text": ANTRAG}} if texte is None else texte,
        },
    }


def report():
    return json.loads((FIXTURES / "report.json").read_text())


def answer(vorgang_cache):
    rep = report()
    return antrag_text.report_vote_passages(rep, vorgang_cache)[politikfelder.vote_key(rep["agenda_items"][0]["votes"][0])]


class ExtractionTests(unittest.TestCase):
    # Value: protects=the quote is the Antrag's operative part word for word, with only layout undone; fails_when=a running head or page number lands inside a demand, a break hyphen stays, a truncated compound loses its hyphen, section I or the Begründung is quoted; why_new=antrag_text is new; seam=none
    def test_the_operative_part_is_quoted_with_layout_undone(self) -> None:
        forderung = antrag_text.extract_forderung(ANTRAG)
        self.assertEqual(forderung, antrag_text.Forderung(OPENING, DEMANDS))

    # Value: protects=an Antrag without the anchor, an empty text and an oversized one give no quote; fails_when=the extractor guesses a passage; why_new=antrag_text is new; seam=none
    def test_no_anchor_no_quote(self) -> None:
        for text in ("", None, "Der Deutsche Bundestag stellt fest: alles gut.", "x" * (antrag_text.MAX_TEXT_CHARS + 1)):
            with self.subTest(text=str(text)[:30]):
                self.assertIsNone(antrag_text.extract_forderung(text))

    # Value: protects=the older frame and an anchor wrapped across lines are found, and the passage ends at the next section; fails_when=the anchor needs one line or "Deutsche"; why_new=antrag_text is new; seam=none
    def test_anchor_variants(self) -> None:
        text = "Der Bundestag wolle beschließen:\nDer Bundestag fordert die\nBundesregierung daher auf, das Gesetz zurückzunehmen.\nIII. Weiteres\nNicht zitiert."
        self.assertEqual(
            antrag_text.extract_forderung(text),
            antrag_text.Forderung("Der Bundestag fordert die Bundesregierung daher auf, das Gesetz zurückzunehmen.", ()),
        )

    # Value: protects=the teaser never cuts a demand and always shows the first; fails_when=a long first demand is cut or dropped; why_new=R5; seam=none
    def test_the_teaser_keeps_whole_demands(self) -> None:
        long_demand = "1. " + "sehr " * 100 + "lange Forderung;"
        shown, rest = antrag_text.forderung_teaser(antrag_text.Forderung(OPENING, (long_demand, "2. kurz.")))
        self.assertEqual((shown, rest), ([OPENING, long_demand], ["2. kurz."]))


class SelectionTests(unittest.TestCase):
    # Value: protects=a vote whose Vorgang has no abstract quotes the Antrag DIP links to that Vorgang; fails_when=selection reads the wrong number or state; why_new=antrag_text is new; seam=none
    def test_an_abstractless_vorgang_quotes_its_antrag(self) -> None:
        result = answer(cache())
        self.assertEqual(result.state, "extracted")
        [passage] = result.by_vorgang["vorgang-1"]
        self.assertEqual((passage.number, passage.drucksache_id, passage.forderung.demands), ("20/123", "D1", DEMANDS))

    # Value: protects=the quote is a fallback: an abstract wins (D1); fails_when=both are shown; why_new=antrag_text is new; seam=none
    def test_an_abstract_wins(self) -> None:
        self.assertEqual(answer(cache(abstract="Kurz.")), antrag_text.VotePassages({}, "not_applicable"))

    # Value: protects=a bundled Beschlussempfehlung never quotes a neighbouring Antrag, a Gesetzentwurf is not quoted, a Bundesrat record does not count; fails_when=selection drops the Vorgang, type or issuer check; why_new=antrag_text is new; seam=none
    def test_only_an_antrag_of_the_votes_vorgang_counts(self) -> None:
        for name, record in (
            ("other Vorgang", drucksache(vorgang_ids=("neighbour",))),
            ("Gesetzentwurf", drucksache(typ="Gesetzentwurf")),
            ("Bundesrat", drucksache(herausgeber="BR")),
        ):
            with self.subTest(name):
                self.assertEqual(answer(cache(nummern={"20/123": [record]})).state, "not_applicable")

    # Value: protects=a missing metadata entry or text is not_fetched, a fetched text without the part is no_passage; fails_when=a cache miss is shown as "no description"; why_new=antrag_text is new; seam=none
    def test_states_tell_a_miss_from_no_passage(self) -> None:
        self.assertEqual(answer(cache(nummern={})).state, "not_fetched")
        self.assertEqual(answer(cache(texte={})).state, "not_fetched")
        self.assertEqual(answer(cache(texte={"D1": {"text": "Nur Feststellungen."}})).state, "no_passage")

    # Value: protects=a reprint of one number resolves to its latest record; fails_when=persist order picks the record; why_new=antrag_text is new; seam=none
    def test_a_reprint_resolves_to_the_latest_record(self) -> None:
        records = [drucksache(drucksache_id="D0", datum="2024-01-09"), drucksache()]
        result = answer(cache(nummern={"20/123": list(reversed(records))}, texte={"D1": {"text": ANTRAG}}))
        self.assertEqual(result.by_vorgang["vorgang-1"][0].drucksache_id, "D1")

    # Value: protects=an online build asks for metadata first and only then for the Anträge's texts, and asks nothing once cached; fails_when=texts of every number are fetched (R1) or cached entries are asked again; why_new=antrag_text is new; seam=none
    def test_fetch_targets_are_metadata_then_texts_then_nothing(self) -> None:
        self.assertEqual(antrag_text.fetch_targets([report()], cache(nummern={}, texte={})), (["20/123"], []))
        self.assertEqual(antrag_text.fetch_targets([report()], cache(texte={})), ([], ["D1"]))
        self.assertEqual(antrag_text.fetch_targets([report()], cache()), ([], []))
        self.assertEqual(antrag_text.fetch_targets([report()], cache(abstract="Kurz.", nummern={})), ([], []))


class CacheFileTests(unittest.TestCase):
    # Value: protects=the cache round-trips and an unchanged save is byte-identical (A3's unchanged-replay gate, R2), and the Vorgang cache file never carries the texts; fails_when=gzip writes a timestamp or the texts leak into dip-vorgang-cache.json; why_new=antrag_text is new; seam=none
    def test_round_trip_and_stable_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            texts = cache()[antrag_text.CACHE_KEY]
            antrag_text.save_cache(tmp, texts)
            first = antrag_text.cache_path(tmp).read_bytes()
            loaded = antrag_text.load_cache(tmp)
            with mock.patch("time.time", return_value=4_000_000_000):
                antrag_text.save_cache(tmp, loaded)
            self.assertEqual(antrag_text.cache_path(tmp).read_bytes(), first)
            self.assertEqual(loaded["texte"], {"D1": {"text": ANTRAG}})
            politikfelder.save_cache(tmp, cache())
            self.assertNotIn(antrag_text.CACHE_KEY, json.loads(politikfelder.cache_path(tmp).read_text()))

    # Value: protects=a corrupt file reads as empty with a warning, never a crash; fails_when=load raises; why_new=antrag_text is new; seam=none
    def test_a_corrupt_file_reads_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            antrag_text.cache_path(tmp).parent.mkdir(parents=True)
            antrag_text.cache_path(tmp).write_bytes(b"not gzip")
            with mock.patch("sys.stderr"):
                self.assertEqual(antrag_text.load_cache(tmp), antrag_text.empty_cache())


class FakeClient:
    """Answers /drucksache and /drucksache-text from fixed records."""

    def __init__(self, metadata, texts):
        self.metadata, self.texts, self.calls = metadata, texts, []

    def list_all(self, path, params, *, page_pause=0.0):
        self.calls.append(path)
        if path == "/drucksache":
            return [d for d in self.metadata if d["dokumentnummer"] in params["f.dokumentnummer"]]
        return [d for d in self.texts if d["id"] in params["f.id"]]


class RefreshTests(unittest.TestCase):
    # Value: protects=stage 3 fetches the votes' Drucksache metadata, then the Antrag text only, saves the cache, and a second run fetches nothing; fails_when=the stage fetches texts of non-Anträge, skips the save or refetches; why_new=antrag_text is new; seam=dip client faked
    def test_stage_three_fills_and_saves_only_misses(self) -> None:
        raw = {"id": "D1", "dokumentnummer": "20/123", "herausgeber": "BT", "drucksachetyp": "Antrag", "titel": "Testantrag",
               "urheber": [{"titel": "Fraktion der CDU/CSU", "einbringer": True}], "vorgangsbezug": [{"id": "vorgang-1"}],
               "fundstelle": {"pdf_url": "https://dserver.bundestag.de/btd/20/001/2000123.pdf"}}
        client = FakeClient([raw], [{"id": "D1", "text": ANTRAG}])
        vorgang_cache = cache(nummern={}, texte={})
        stats = {"drucksachen": 0, "texte": 0, "texte_failed": 0}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(build, "NUMBER_LOOKUP_PAUSE", 0):
            build.refresh_drucksache_texts(client, [report()], vorgang_cache, Path(tmp), stats)
            self.assertEqual(client.calls, ["/drucksache", "/drucksache-text"])
            self.assertEqual(stats, {"drucksachen": 1, "texte": 1, "texte_failed": 0})
            self.assertEqual(antrag_text.load_cache(tmp)["texte"], {"D1": {"text": ANTRAG}})
            self.assertEqual(answer(vorgang_cache).state, "extracted")
            build.refresh_drucksache_texts(client, [report()], vorgang_cache, Path(tmp), stats)
            self.assertEqual(len(client.calls), 2)


class PersistTests(unittest.TestCase):
    def persisted(self, vorgang_cache):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "data" / "store.sqlite"
        conn = pulse_store.connect(path)
        self.addCleanup(conn.close)
        pulse_store.persist_report(conn, report(), vorgang_cache)
        return conn, path

    # Value: protects=the passage, its state and the vote→document choice reach the store; fails_when=persist skips vote_passages or the document columns; why_new=schema 8; seam=none
    def test_the_passage_is_stored_on_the_document(self) -> None:
        conn, _path = self.persisted(cache())
        row = conn.execute("SELECT forderung, forderung_state, forderung_version FROM documents WHERE document_number = '20/123'").fetchone()
        self.assertEqual(tuple(row), ("\n\n".join((OPENING, *DEMANDS)), "extracted", antrag_text.EXTRACTOR_VERSION))
        self.assertEqual([tuple(r) for r in conn.execute("SELECT vote_id, proceeding_id, rank FROM vote_passages")], [("12345", "vorgang-1", 1)])
        self.assertEqual(conn.execute("SELECT passage_state FROM votes").fetchone()[0], "extracted")

    # Value: protects=a store persisted by another extractor version is refused before facts, export or render; fails_when=the version check goes; why_new=EXTRACTOR_VERSION; seam=none
    def test_a_stale_extractor_version_is_refused(self) -> None:
        conn, _path = self.persisted(cache())
        conn.execute("UPDATE speech_rule_inputs SET version = ?", (speech_kinds.VERSION,))
        conn.execute("UPDATE documents SET forderung_version = 0 WHERE forderung_state IS NOT NULL")
        with self.assertRaisesRegex(RuntimeError, "Stale persisted Antrag passages"):
            pulse_store.require_current_speech_rules(conn)

    # Value: protects=a replay with a lost text cache is refused instead of dropping known quotes, while DIP adding an abstract later is allowed; fails_when=the guard ignores passage_state or also refuses extracted → not_applicable; why_new=R6; seam=none
    def test_the_replay_guard_keeps_known_passages(self) -> None:
        conn, path = self.persisted(cache())
        conn.commit()
        entries = [{"report": report()}]
        with self.assertRaisesRegex(build.DatabaseRebuildError, "Antrag passage not_fetched"):
            build.require_vorgang_cache_for_tags(path, cache(nummern={}, texte={}), path.parent.parent, entries)
        build.require_vorgang_cache_for_tags(path, cache(abstract="Kurz."), path.parent.parent, entries)

    # Value: protects=a schema 7 store (no votes.passage_state) is refused with the repersist instruction; fails_when=the guard goes and initialize stamps 8 over NULL states; why_new=schema 8; seam=none
    def test_a_schema_7_store_is_refused(self) -> None:
        conn, _path = self.persisted(cache())
        conn.execute("ALTER TABLE votes DROP COLUMN passage_state")
        with self.assertRaisesRegex(RuntimeError, "Old build-store schema"):
            pulse_store.initialize(conn)


class PanelTests(unittest.TestCase):
    def panel(self, vorgang_cache, **vote_overrides):
        rep = report()
        item = rep["agenda_items"][0]
        item["votes"][0].update(vote_overrides)
        contexts = politikfelder.report_vote_vorgaenge(rep, vorgang_cache)
        return vote_summary(
            item, report=rep, vorgang_cache=vorgang_cache, vote_contexts=contexts,
            vote_passages=antrag_text.report_vote_passages(rep, vorgang_cache, contexts),
        )

    # Value: protects=the panel quotes the Antrag with its author and Drucksache link, folds the rest, and says nothing of the result inside the quote; fails_when=the caption, link, escaping or fold goes; why_new=antrag_text is new; seam=none
    def test_the_quote_replaces_no_description(self) -> None:
        markup = self.panel(cache())
        self.assertNotIn("Keine Beschreibung in DIP", markup)
        self.assertIn(
            'Aus dem Antrag „Testantrag“ (Fraktion der CDU/CSU, Drucksache '
            '<a href="https://dserver.bundestag.de/btd/20/001/2000123.pdf">20/123</a>):', markup,
        )
        self.assertIn(f"<blockquote><p>{OPENING}</p>{''.join(f'<p>{d}</p>' for d in DEMANDS)}</blockquote>", markup)
        self.assertNotIn("vote-context-quote-more", markup)

    # Value: protects=a long Antrag shows its first whole demands and folds the rest; fails_when=the fold or its count goes; why_new=antrag_text is new; seam=none
    def test_a_long_antrag_folds_the_rest(self) -> None:
        demands = "\n".join(f"{n}. die Forderung Nummer {n} mit einigem Text, der sie lang genug macht, umzusetzen;" for n in range(1, 11))
        text = f"{OPENING}\n{demands}\nBerlin, den 9. Januar 2024"
        markup = self.panel(cache(texte={"D1": {"text": text}}))
        self.assertIn("<summary>Weitere 7 Forderungen</summary>", markup)

    # Value: protects=a vote on the recommendation to reject still quotes the Antrag as its sponsor's demand, with the inversion note outside the quote; fails_when=the quote is dropped or framed as the Bundestag's decision; why_new=antrag_text is new; seam=none
    def test_an_inverted_vote_keeps_the_attribution(self) -> None:
        markup = self.panel(cache(), inverted=True)
        self.assertIn("Aus dem Antrag „Testantrag“ (Fraktion der CDU/CSU", markup)
        self.assertIn("Ja = Antrag ablehnen", markup)
        figure = markup[markup.index('<figure class="vote-context-quote">'):markup.index("</figure>")]
        self.assertNotIn("ablehnen", figure)

    # Value: protects=without a quote the gap stays honest: "no description" when DIP has none, plus a note when the text is only not fetched; fails_when=a cache miss reads as a final gap; why_new=antrag_text is new; seam=none
    def test_gaps(self) -> None:
        markup = self.panel(cache(texte={}))
        self.assertIn("Keine Beschreibung in DIP", markup)
        self.assertIn("Antragstext nicht abgerufen", markup)
        markup = self.panel(cache(texte={"D1": {"text": "Nur Feststellungen."}}))
        self.assertIn("Keine Beschreibung in DIP", markup)
        self.assertNotIn("Antragstext nicht abgerufen", markup)


if __name__ == "__main__":
    unittest.main()
