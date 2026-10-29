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
        antrag_text.CACHE_NAMESPACE: {
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


def real_text(name: str) -> str:
    """A real Drucksache's pdftotext output (provenance: a1-source-manifest.json)."""
    return (FIXTURES / "antrag-text" / name).read_text(encoding="utf-8").replace("\f", "\n")


class RealDrucksacheTests(unittest.TestCase):
    """Real Anträge, as pdftotext reads their PDFs (the DIP text was not reachable
    when these were added): a clean list is quoted whole and in order; a text layer
    that lost the order of the list gives no quote rather than a reordered one."""

    # Value: protects=a real Antrag's operative part is quoted with its 14 demands in order and the Begründung left out; fails_when=a real running head, break hyphen or item boundary is misread; why_new=first real-text check (2026-10-28); seam=none
    def test_21_2234_is_quoted_whole(self) -> None:
        forderung = antrag_text.extract_forderung(real_text("drucksache-2102234.txt"))
        self.assertTrue(forderung.opening.startswith("Der Deutsche Bundestag fordert die Bundesregierung auf, umgehend einen Gesetzentwurf"))
        self.assertEqual([d.split(".", 1)[0] for d in forderung.demands], [str(n) for n in range(1, 15)])
        self.assertTrue(forderung.demands[-1].endswith("anrechnungsfrei gestellt."))
        self.assertNotIn("Begründung", forderung.text())

    # Value: protects=a text layer that detached list markers from their items ("2." "3." alone, or "2." glued to sub-item "e.") gives no quote instead of a reordered one; fails_when=bare markers are joined to whatever line follows; why_new=found on real texts 2026-10-28 (21/5780, 19/7398, 20/13902); seam=none
    def test_a_scrambled_list_gives_no_quote(self) -> None:
        for name in ("drucksache-2105780.txt", "drucksache-1907398.txt", "drucksache-2013902.txt"):
            with self.subTest(name):
                self.assertIsNone(antrag_text.extract_forderung(real_text(name)))

    # Value: protects=the same Anträge read in layout order are quoted with every item in order, lettered "a." sub-items included; fails_when=layout-mode running heads or "a." items are misread; why_new=found on real texts 2026-10-28; seam=none
    def test_the_layout_text_of_the_same_antraege_is_quoted_in_order(self) -> None:
        kindergeld = antrag_text.extract_forderung(real_text("drucksache-2105780.layout.txt"))
        self.assertEqual([d.split(".", 1)[0] for d in kindergeld.demands], [str(n) for n in range(1, 11)])
        self.assertIn("BAföG-beziehenden Studienanfänger*innen", kindergeld.demands[3])
        buerokratie = antrag_text.extract_forderung(real_text("drucksache-1907398.layout.txt"))
        self.assertEqual(
            [d.split(" ", 1)[0] for d in buerokratie.demands],
            ["1.", "a.", "b.", "c.", "d.", "e.", "f.", "2.", "a.", "b.", "c.", "d."],
        )


class DipTextTests(unittest.TestCase):
    """Real DIP ``drucksache-text`` bodies (2026-10-29), each kept for one trap the
    text layer sets; provenance in a1-source-manifest.json."""

    def test_a_stranded_elision_hyphen_stays_with_its_word(self) -> None:
        forderung = antrag_text.extract_forderung(real_text("dip-2100224.txt"))
        self.assertIn("Steuerzahler und -zahlerinnen", forderung.demands[5])
        self.assertEqual(len(forderung.demands), 10)
        self.assertEqual(antrag_text._join("ein Einschub -", "bleibt getrennt"), "ein Einschub - bleibt getrennt")

    # Value: protects=the first-page head DIP repeats at a page break never lands in a demand; fails_when=only the PDF running-head forms are dropped; why_new=found in DIP text of 21/5780; seam=none
    def test_a_repeated_page_head_is_dropped(self) -> None:
        forderung = antrag_text.extract_forderung(real_text("dip-2105780.txt"))
        self.assertEqual(len(forderung.demands), 10)
        self.assertTrue(forderung.demands[2].endswith("um tatsächlichen Wohnkosten Rechnung zu tragen;"))
        self.assertNotIn("Wahlperiode", forderung.text())

    # Value: protects=the letter-spaced advance-copy watermark DIP sets mid-sentence is removed and the sentence joins; fails_when=the watermark is quoted as part of a demand; why_new=found in DIP text of 21/8314, 21/8551, 21/8568; seam=none
    def test_the_advance_copy_watermark_is_removed(self) -> None:
        forderung = antrag_text.extract_forderung(real_text("dip-2108568.txt"))
        self.assertNotIn("orabfassung", forderung.text())
        self.assertIn("zu schaffen, um gute Rahmenbedingungen", forderung.demands[5])

    # Value: protects=a footnote that a page break put inside the operative part gives no quote; fails_when=the footnote text is quoted inside a demand; why_new=found in DIP text of 21/8385; seam=none
    def test_a_footnote_inside_the_passage_gives_no_quote(self) -> None:
        self.assertIn("3 Vgl. Bundestagsdrucksache 21/4996", real_text("dip-2108385.txt"))
        self.assertIsNone(antrag_text.extract_forderung(real_text("dip-2108385.txt")))

    # Value: protects=the adverb may stand before the object ("fordert daher die Bundesregierung auf"); fails_when=the anchor only allows it after; why_new=found in DIP text of 18/12797; seam=none
    def test_the_adverb_before_the_object(self) -> None:
        forderung = antrag_text.extract_forderung(real_text("dip-1812797.txt"))
        self.assertEqual(forderung.opening, "Der Deutsche Bundestag fordert daher die Bundesregierung auf,")
        self.assertEqual([d.split(".", 1)[0] for d in forderung.demands], [str(n) for n in range(1, len(forderung.demands) + 1)])


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

    # Value: protects=layout is undone without changing, dropping or cutting words: a wrapped line that starts with "Begründung", "1. Januar" or "–" stays in its demand, a line naming another Drucksache is kept, a hyphen after a digit stays without a space, a soft hyphen at a line end joins the word, a section heading on its own line ends the passage, and a passage cut mid-sentence is no quote; fails_when=the end, item, layout-line or hyphen rules go back to matching any line start; why_new=code review of B4 extractive (2026-10-28); seam=none
    def test_wrapped_lines_keep_every_word(self) -> None:
        def passage(*lines: str, end: str = "Berlin, den 9. Januar 2024") -> antrag_text.Forderung | None:
            return antrag_text.extract_forderung("\n".join(("Drucksache 20/123", OPENING, *lines, end)))

        self.assertEqual(
            passage("1. jede Ablehnung mit einer", "Begründung zu versehen;", "2. bis zum", "1. Januar 2026 zu berichten;",
                    "3. die Mittel – soweit möglich", "– aufzustocken und den Gesetzentwurf auf", "Drucksache 20/1234",
                    "zurückzuziehen;", "4. die CO2-", "Bepreisung und das 49-", "Euro-Ticket zu erhalten und die Sätze an\u00ad",
                    "zuheben."),
            antrag_text.Forderung(OPENING, (
                "1. jede Ablehnung mit einer Begründung zu versehen;",
                "2. bis zum 1. Januar 2026 zu berichten;",
                "3. die Mittel – soweit möglich – aufzustocken und den Gesetzentwurf auf Drucksache 20/1234 zurückzuziehen;",
                "4. die CO2-Bepreisung und das 49-Euro-Ticket zu erhalten und die Sätze anzuheben.",
            )),
        )
        self.assertEqual(
            passage("1. das Gesetz zu ändern;", "2. dem Bundestag zu berichten.", "III.", "Der Deutsche Bundestag bittet den Bundesrat."),
            antrag_text.Forderung(OPENING, ("1. das Gesetz zu ändern;", "2. dem Bundestag zu berichten.")),
        )
        self.assertIsNone(passage("1. das Gesetz zu ändern;", "2. dem Bundestag bis zum", end="Begründung"))

    # Value: protects=the teaser never cuts a demand and always shows the first; fails_when=a long first demand is cut or dropped; why_new=R5; seam=none
    def _with_wrapped(self, wrapped: str, elsewhere: str = "") -> str | None:
        text = f"{elsewhere}\n{OPENING}\n1. die {wrapped}-Regeln umzusetzen;\n2. weiter zu berichten.\nBerlin, den 1. Januar 2024"
        forderung = antrag_text.extract_forderung(text)
        return forderung.demands[0] if forderung else None

    # Value: protects=a hard hyphen a line end splits is kept where the text prints the word whole elsewhere, a break hyphen goes, and after a capital without evidence the passage is not quoted; fails_when=every lower-case continuation drops the hyphen ("EUweite"); why_new=Greptile P1 on PR #113, cases from DIP text ("NATO-geführten", "BA-föG"); seam=none
    def test_a_line_end_hyphen_follows_the_texts_own_spelling(self) -> None:
        self.assertEqual(self._with_wrapped("EU-\nweiten", "Für EU-weiten Schutz."), "1. die EU-weiten-Regeln umzusetzen;")
        self.assertEqual(self._with_wrapped("BA-\nföG", "Das BAföG-Gesetz."), "1. die BAföG-Regeln umzusetzen;")
        self.assertEqual(self._with_wrapped("Know-\nhow", "Das Know-how fehlt."), "1. die Know-how-Regeln umzusetzen;")
        self.assertEqual(self._with_wrapped("Bundesre-\ngierungs"), "1. die Bundesregierungs-Regeln umzusetzen;")
        self.assertIsNone(self._with_wrapped("EU-\nweiten"))

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

    # Value: protects=a number DIP had no record for, or whose Antrag was not yet linked to a Vorgang, is asked again like an unresolved number of the Vorgang cache; fails_when=a first empty answer is cached for good, so the vote never gets its quote; why_new=code review of B4 extractive (2026-10-28); seam=none
    def test_an_empty_or_unlinked_answer_is_asked_again(self) -> None:
        for name, records in (("no record", []), ("not linked", [drucksache(vorgang_ids=())])):
            with self.subTest(name):
                self.assertEqual(antrag_text.fetch_targets([report()], cache(nummern={"20/123": records}, texte={})), (["20/123"], []))


class CacheFileTests(unittest.TestCase):
    # Value: protects=the cache round-trips and an unchanged save is byte-identical (A3's unchanged-replay gate, R2), and the Vorgang cache file never carries the texts; fails_when=gzip writes a timestamp or the texts leak into dip-vorgang-cache.json; why_new=antrag_text is new; seam=none
    def test_round_trip_and_stable_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            texts = cache()[antrag_text.CACHE_NAMESPACE]
            antrag_text.save_cache(tmp, texts)
            first = antrag_text.cache_path(tmp).read_bytes()
            loaded = antrag_text.load_cache(tmp)
            with mock.patch("time.time", return_value=4_000_000_000):
                antrag_text.save_cache(tmp, loaded)
            self.assertEqual(antrag_text.cache_path(tmp).read_bytes(), first)
            self.assertEqual(loaded["texte"], {"D1": {"text": ANTRAG}})
            politikfelder.save_cache(tmp, cache())
            self.assertNotIn(antrag_text.CACHE_NAMESPACE, json.loads(politikfelder.cache_path(tmp).read_text()))

    # Value: protects=a corrupt file reads as empty with a warning, never a crash; fails_when=load raises; why_new=antrag_text is new; seam=none
    def test_a_corrupt_file_reads_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            antrag_text.cache_path(tmp).parent.mkdir(parents=True)
            antrag_text.cache_path(tmp).write_bytes(b"not gzip")
            with mock.patch("sys.stderr"):
                self.assertEqual(antrag_text.load_cache(tmp), antrag_text.empty_cache())

    # Value: protects=a damaged deflate stream or a deeply nested file reads as empty and is moved aside, so a later save cannot overwrite it, while an unsupported version or a read error stops the build with the file untouched (as the Vorgang cache does); fails_when=zlib.error or RecursionError escapes, or a newer cache is read as empty and overwritten by the next online build; why_new=code review of B4 extractive (2026-10-28); seam=none
    def test_damaged_and_unsupported_files(self) -> None:
        import gzip

        good = gzip.compress(json.dumps({"version": 1, "nummern": {}, "texte": {"x": {"text": "a" * 5000}}}).encode(), mtime=0)
        damaged = bytes(good[:15]) + bytes(b ^ 0xFF for b in good[15:40]) + bytes(good[40:])
        for name, data in (("deflate", damaged), ("nested", gzip.compress(b"[" * 100_000 + b"]" * 100_000, mtime=0))):
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                path = antrag_text.cache_path(tmp)
                path.parent.mkdir(parents=True)
                path.write_bytes(data)
                with mock.patch("sys.stderr"):
                    self.assertEqual(antrag_text.load_cache(tmp), antrag_text.empty_cache())
                self.assertFalse(path.exists())
        with tempfile.TemporaryDirectory() as tmp:
            path = antrag_text.cache_path(tmp)
            path.parent.mkdir(parents=True)
            newer = gzip.compress(json.dumps({"version": 2, "nummern": {}, "texte": {}}).encode(), mtime=0)
            path.write_bytes(newer)
            with self.assertRaisesRegex(politikfelder.CacheLoadError, "Unsupported Drucksache text cache version 2"):
                antrag_text.load_cache(tmp)
            self.assertEqual(path.read_bytes(), newer)


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
            self.assertEqual(stats, {"drucksachen": 1, "drucksachen_failed": 0, "texte": 1, "texte_failed": 0})
            self.assertEqual(antrag_text.load_cache(tmp)["texte"], {"D1": {"text": ANTRAG}})
            self.assertEqual(answer(vorgang_cache).state, "extracted")
            saved = antrag_text.cache_path(tmp).stat().st_mtime_ns
            build.refresh_drucksache_texts(client, [report()], vorgang_cache, Path(tmp), stats)
            self.assertEqual(len(client.calls), 2)
            self.assertEqual(antrag_text.cache_path(tmp).stat().st_mtime_ns, saved)  # nothing fetched, nothing written

    # Value: protects=when the Drucksache-number pass of the Vorgang fetch shows the API down, stage 3 asks DIP nothing; fails_when=resolve_numbers' breaker is not passed on, so a blocked API gets more calls; why_new=code review of B4 extractive (2026-10-28); seam=dip client faked
    def test_an_outage_on_the_number_pass_skips_stage_three(self) -> None:
        class Down:
            def __init__(self):
                self.calls = []

            def list_all(self, path, params, *, page_pause=0.0):
                self.calls.append(path)
                if path == "/vorgang" and "f.dokumentnummer" in params:
                    raise build.dip.DipError("blocked")
                return []

        rep = report()
        rep["agenda_items"][0]["votes"][0]["document_numbers"] = ["20/123", "20/124"]
        client = Down()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(build, "NUMBER_LOOKUP_PAUSE", 0), \
                mock.patch.object(build, "VORGANG_FETCH_MAX_FAILURES", 1), mock.patch("sys.stderr"):
            build.refresh_vorgang_cache(client, [{"report": rep}], cache(nummern={}, texte={}), Path(tmp))
        self.assertEqual([c for c in client.calls if c.startswith("/drucksache")], [])


class PersistTests(unittest.TestCase):
    def persisted(self, vorgang_cache, rep=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "data" / "store.sqlite"
        conn = pulse_store.connect(path)
        self.addCleanup(conn.close)
        pulse_store.persist_report(conn, rep or report(), vorgang_cache)
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
        with self.assertRaisesRegex(build.DatabaseRebuildError, "known Antrag passages of votes not_fetched"):
            build.require_vorgang_cache_for_tags(path, cache(nummern={}, texte={}), path.parent.parent, entries)
        build.require_vorgang_cache_for_tags(path, cache(abstract="Kurz."), path.parent.parent, entries)

    # Value: protects=a vote quoting two Anträge cannot lose one of them on replay while the other keeps the vote extracted; fails_when=the guard compares the vote-level state only; why_new=Greptile P1 on PR #113; seam=none
    def test_the_replay_guard_checks_each_quoted_antrag(self) -> None:
        rep = report()
        rep["agenda_items"][0]["votes"][0]["document_numbers"] = ["20/123", "20/124"]
        two = cache(
            nummern={"20/123": [drucksache()], "20/124": [drucksache(number="20/124", drucksache_id="D2")]},
            texte={"D1": {"text": ANTRAG}, "D2": {"text": ANTRAG}},
        )
        two["dokumentnummern"]["20/124"] = ["vorgang-1"]
        conn, path = self.persisted(two, rep)
        conn.commit()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM vote_passages").fetchone()[0], 2)
        one_lost = copy.deepcopy(two)
        del one_lost[antrag_text.CACHE_NAMESPACE]["texte"]["D2"]
        self.assertEqual(antrag_text.report_vote_passages(rep, one_lost)["12345"].state, "extracted")
        with self.assertRaisesRegex(build.DatabaseRebuildError, r"1 known Antrag passages.*'20/124'"):
            build.require_vorgang_cache_for_tags(path, one_lost, path.parent.parent, [{"report": rep}])
        build.require_vorgang_cache_for_tags(path, two, path.parent.parent, [{"report": rep}])

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
        self.assertIn("<summary>Ganzen Forderungsteil zeigen</summary>", markup)

    # Value: protects=a vote on the recommendation to reject still quotes the Antrag as its sponsor's demand, with the inversion note outside the quote; fails_when=the quote is dropped or framed as the Bundestag's decision; why_new=antrag_text is new; seam=none
    def test_an_inverted_vote_keeps_the_attribution(self) -> None:
        markup = self.panel(cache(), inverted=True)
        self.assertIn("Aus dem Antrag „Testantrag“ (Fraktion der CDU/CSU", markup)
        self.assertIn("Ja = Antrag ablehnen", markup)
        figure = markup[markup.index('<figure class="vote-context-quote">'):markup.index("</figure>")]
        self.assertNotIn("ablehnen", figure)

    # Value: protects=the "not fetched" note is per Vorgang block: a block whose own Antrag text is missing says so even when another block of the vote is quoted, and a block with only a read text and no passage does not; fails_when=the note reads the vote-wide state again; why_new=code review of B4 extractive (2026-10-28); seam=none
    def test_the_text_note_belongs_to_its_block(self) -> None:
        from features import votes as votes_feature

        result = answer(cache())
        missing = result.by_vorgang["vorgang-1"][0]._replace(vorgang_id="vorgang-2", state="not_fetched", forderung=None)
        read = missing._replace(vorgang_id="vorgang-3", state="no_passage")
        passages = antrag_text.VotePassages({**result.by_vorgang, "vorgang-2": [missing], "vorgang-3": [read]}, "extracted")
        self.assertIn("Antragstext nicht abgerufen", votes_feature._abstractless_body(passages, "vorgang-2"))
        self.assertNotIn("Antragstext nicht abgerufen", votes_feature._abstractless_body(passages, "vorgang-3"))
        self.assertIn("Antragstext nicht abgerufen", votes_feature._abstractless_body(passages._replace(metadata_missing=True), "vorgang-3"))
        for partial in (
            result._replace(metadata_missing=True),
            result._replace(by_vorgang={"vorgang-1": [*result.by_vorgang["vorgang-1"], missing._replace(vorgang_id="vorgang-1")]}),
        ):
            body = votes_feature._abstractless_body(partial, "vorgang-1")
            self.assertIn('class="vote-context-quote"', body)
            self.assertIn("Antragstext nicht abgerufen", body)
            self.assertNotIn("Keine Beschreibung in DIP", body)

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
