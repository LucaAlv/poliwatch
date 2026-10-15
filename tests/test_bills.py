"""Only a Gesetzgebung has a bill page (CONTEXT.md: Gesetzgebung, Gesetzesvorhaben):
the Vorgang's DIP Vorgangstyp decides, not a keyword in its title."""

from __future__ import annotations

import re
import copy
import argparse
import json
import sys
import tempfile
import unicodedata
import unittest
from pathlib import Path
from html.parser import HTMLParser

import _support  # noqa: F401
import build_dip_pulse_site as build
import render_dip_pulse_html as html
from stable_ids import speech_occurrence_id, synthetic_rede_id


def position(vorgang_id: str, typ: str, title: str, number: str) -> dict:
    return {
        "id": f"pos-{vorgang_id}",
        "vorgang_id": vorgang_id,
        "vorgangstyp": typ,
        "vorgangsposition": "1. Beratung",
        "titel": title,
        "source": {"dokumentnummer": number},
    }


def entry(positions: list[dict], docs: list[dict], number: str = "21/5", date: str = "2026-01-15") -> dict:
    return {
        "report": {
            "protocol": {"dokumentnummer": number, "datum": date, "titel": "Plenarprotokoll"},
            "agenda_items": [
                {
                    "index": 1,
                    "top_id": "TOP 1",
                    "heading": "Beratung",
                    "xml_speech_count": 0,
                    "api": {"positions": positions, "linked_drucksachen": docs},
                }
            ],
        },
        "page_path": Path(f"plenarprotokoll-{number.replace('/', '-')}.html"),
    }


GESETZ = position("100", "Gesetzgebung", "Entwurf eines Gesetzes zur Sache", "21/100")
ENTSCHLIESSUNG = position("200", "Entschließungsantrag", "Entschließung zum Gesetz zur Sache", "21/101")
ANTRAG = position("300", "Antrag", "Für eine gesetzliche Krankenversicherung, die trägt", "21/102")
VERORDNUNG = position("400", "Rechtsverordnung", "Verordnung nach dem Grundgesetz", "21/103")
WAHL = position("500", "Wahl", "Wahl des Bundeskanzlers (Art. 63 Grundgesetz)", "21/104")
DOCS = [
    {"vorgang_id": "100", "dokumentnummer": "21/100", "drucksachetyp": "Gesetzentwurf", "titel": "Entwurf eines Gesetzes"},
    {"vorgang_id": "200", "dokumentnummer": "21/101", "drucksachetyp": "Entschließungsantrag"},
    {"vorgang_id": "300", "dokumentnummer": "21/102", "drucksachetyp": "Antrag"},
]


def browser_fixture_bills() -> list[dict]:
    """Small deterministic publication covering paging, search and sort edges."""
    rows = []
    for i in range(41):
        year = (2022, 2024, 2026)[i % 3]
        rows.append({
            "id": f"browser-{i:02}", "slug": f"browser-{i:02}", "type": "Gesetzgebung",
            "title": f"Gesetzesvorhaben {i:02}", "latest_date": f"{year}-06-{(i % 27) + 1:02}",
            "latest_step": "Erste Beratung", "documents": [{"dokumentnummer": f"21/{500+i}"}],
            "protocol_refs": [], "votes": [], "events": [], "speakers": [], "related": [],
            "introduced_by": [], "primary_document": f"21/{500+i}", "vorgang_id": str(500+i),
        })
    rows[0]["documents"].append({"dokumentnummer": "21/9876"})
    for row in rows[:21]:
        row["documents"].append({"dokumentnummer": "21/COHORT"})
    rows[1]["title"] = "Änderung des Gesetzes"
    rows[2]["title"] = "Änderung des Gesetzes"  # decomposed umlaut: German collation tie
    rows[40]["latest_date"] = None
    rows[40]["documents"] = [{"dokumentnummer": "22/777"}]
    return rows


def write_browser_fixture(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    bills = browser_fixture_bills()
    (directory / "index.html").write_text(build.render_bills_index(bills), encoding="utf-8")
    detail_bill = dict(bills[0])
    detail_bill.update({
        "latest_date": "2026-06-01",
        "introduced_by": ["Bundesregierung", "Deutscher Bundestag"],
        "speakers": [
            {
                "name": f"Abgeordnete Person mit langem Namen {i:02}",
                "party": "Mitglied des Ausschusses für eine besonders ausführliche parlamentarische Zuständigkeit",
                "speech_count": i + 1,
                "char_count": 1200 + i,
            }
            for i in range(15)
        ],
        "events": [
            {"date": "2026-06-01", "kind": "Erste Beratung", "title": "Einbringung des Gesetzentwurfs", "source": "DIP-Vorgang", "url": "https://dip.bundestag.de/vorgang/100"},
            {"date": "2026-06-01", "kind": "Ausschussüberweisung", "title": "Überweisung an den federführenden Ausschuss", "source": "Plenarprotokoll", "url": "https://www.bundestag.de/protokolle/21/1"},
        ],
        "documents": [
            {"dokumentnummer": "21/500", "drucksachetyp": "Gesetzentwurf", "urheber": ["Bundesregierung"], "url": "https://dip.bundestag.de/drucksache/21/500"},
            {"dokumentnummer": "PlPr 21/1", "drucksachetyp": "Plenarprotokoll", "urheber": ["Deutscher Bundestag"], "url": "https://dip.bundestag.de/plenarprotokoll/21/1"},
        ],
        "votes": [
            {"title": "Namentliche Abstimmung zum Gesetzesvorhaben", "date": "2026-06-01", "detail_url": "https://www.bundestag.de/abstimmung?id=100"},
        ],
        "protocol_refs": [
            {"protocol_number": "21/1", "protocol_date": "2026-06-01", "top_id": "TOP 4", "href": "https://www.bundestag.de/protokolle/21/1"},
        ],
    })
    for index in (0, 1):
        detail_bill["speakers"][index]["speeches"] = [
            {"href": f"../protocols/plenarprotokoll-21-1.html#speech-4-ID{sequence}",
             "protocol_number": "21/1", "protocol_date": "2026-06-01", "source_page": {"page": 123, "quadrant": "A"}}
            for sequence in range(index + 1)
        ]
    (directory / "detail.html").write_text(build.render_bill_detail(detail_bill, {}), encoding="utf-8")
    (directory / "empty.html").write_text(build.render_bills_index([]), encoding="utf-8")


class _Markup(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.nodes: list[tuple[str, dict[str, str | None]]] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.nodes.append((tag, dict(attrs)))

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def parsed(markup: str) -> list[tuple[str, dict[str, str | None]]]:
    parser = _Markup()
    parser.feed(markup)
    return parser.nodes


class PredicateTests(unittest.TestCase):
    def test_only_the_vorgangstyp_gesetzgebung_is_legislation(self) -> None:
        self.assertTrue(build.is_gesetzgebung(GESETZ))
        for other in (ENTSCHLIESSUNG, ANTRAG, VERORDNUNG, WAHL, {}):
            with self.subTest(other.get("vorgangstyp")):
                # The keyword test kept these through "Gesetz", "Grundgesetz" and
                # "gesetzliche Krankenversicherung" in a title.
                self.assertFalse(build.is_gesetzgebung(other))


class CollectTests(unittest.TestCase):
    def test_speech_links_match_dossier_anchors_and_count_each_speech_once_per_bill(self) -> None:
        other_bill = position("101", "Gesetzgebung", "Anderes Gesetz", "21/101")
        current = entry([GESETZ, dict(GESETZ, id="another-position"), other_bill], DOCS)
        current["report"]["protocol"]["id"] = "p1"
        current["report"]["agenda_items"][0]["xml_speakers"] = [
            {"rede_id": "ID / 1", "speaker": {"display_name": "Ada Example", "fraktion": "SPD"}, "char_count": 10},
            {"rede_id": None, "speaker": {"display_name": "Ada Example", "fraktion": "SPD"}, "char_count": 20},
        ]
        older = copy.deepcopy(current)
        older["page_path"] = Path("plenarprotokoll-21-4.html")
        older["report"]["protocol"].update(id="p0", dokumentnummer="21/4", datum="2026-01-10")
        older["report"]["agenda_items"][0]["xml_speakers"] = [
            {"rede_id": "ID / 1", "speaker": {"display_name": "Ada Example", "fraktion": "SPD"}, "char_count": 5},
        ]
        bills = build.collect_bill_pages([older, current])
        self.assertEqual(len(bills), 2)
        for bill in bills:
            speaker = bill["speakers"][0]
            self.assertEqual((speaker["speech_count"], speaker["char_count"]), (3, 35))
            refs = speaker["speeches"]
            self.assertEqual([ref["protocol_date"] for ref in refs], ["2026-01-15", "2026-01-15", "2026-01-10"])
            self.assertEqual(len({ref["href"] for ref in refs}), 3)
            # Two positions of one agenda item keep one raw copy of that item.
            self.assertEqual(len(bill["raw"]["agenda_items"]), 2)
            markup = build.render_bill_detail(bill)
            self.assertIn("3 Reden ansehen", markup)
            for ref in refs:
                self.assertIn(f'href="{ref["href"]}"', markup)
                source = current if ref["protocol_number"] == "21/5" else older
                self.assertIn(f'id="{ref["href"].split("#")[1]}"', html.render_html(source["report"]))
        self.assertTrue(bills[0]["speakers"][0]["speeches"][1]["href"].endswith("#speech-1-2"))
        # A single speech remains one direct link, and unsafe links fail publication.
        single = build.collect_bill_pages([older])[0]
        single_markup = build.render_bill_detail(single)
        self.assertIn("Rede lesen", single_markup)
        self.assertNotIn('class="bill-speaker-speeches"', single_markup)
        single["speakers"][0]["speeches"][0]["href"] = "javascript:alert(1)"
        with self.assertRaises(build.publication.PublicationStateError):
            build.render_bill_detail(single)

    # Value: protects=a same-day Plenarprotokoll document never becomes the latest step, and the published order matches the overview script's default (newest first, then German title order with numbers in numeric order); fails_when=date ties keep insertion order or titles sort Z-A/codepoint-wise, so the list reshuffles when the script runs; why_new=no collect test had same-date events or same-date bills; seam=none; no_claim=Intl.Collator parity beyond accents, case and digit runs
    def test_same_day_ties_pick_the_step_and_order_titles_like_the_overview_script(self) -> None:
        protocol_doc = {"vorgang_id": "100", "dokumentnummer": "PlPr 21/5", "drucksachetyp": "Plenarprotokoll", "datum": "2026-01-15"}
        draft = dict(DOCS[0], datum="2026-01-02")
        first = entry([GESETZ], [draft, protocol_doc])
        bill = build.collect_bill_pages([first])[0]
        self.assertEqual((bill["latest_date"], bill["latest_step"]), ("2026-01-15", "1. Beratung"))
        self.assertEqual(bill["events"][0]["kind"], "1. Beratung")
        titles = ["Zollgesetz", "Gesetz 10", "Änderungsgesetz", "Gesetz 2", "Abgabengesetz", "Gesetz 2²"]
        same_day = entry([position(str(600 + i), "Gesetzgebung", t, f"21/{600 + i}") for i, t in enumerate(titles)], [
            {"vorgang_id": str(600 + i), "dokumentnummer": f"21/{600 + i}", "drucksachetyp": "Gesetzentwurf"} for i in range(len(titles))
        ])
        older = entry([position("700", "Gesetzgebung", "Aaa älter", "21/700")], [
            {"vorgang_id": "700", "dokumentnummer": "21/700", "drucksachetyp": "Gesetzentwurf"}
        ], number="21/4", date="2026-01-10")
        ordered = [b["title"] for b in build.collect_bill_pages([older, same_day])]
        self.assertEqual(ordered, ["Abgabengesetz", "Änderungsgesetz", "Gesetz 2", "Gesetz 2²", "Gesetz 10", "Zollgesetz", "Aaa älter"])
        # The overview script breaks date ties by this published rank, not by its own collation.
        ranks = re.findall(r'data-rank="(\d+)"', build.render_bills_index(build.collect_bill_pages([older, same_day])))
        self.assertEqual(ranks, [str(i) for i in range(len(ordered))])

    # Value: protects=odd source data cannot crash or silently merge bill records: a very long digit run in a title, and two sittings whose reports lack a protocol id, each keep their own raw agenda item; fails_when=the title key goes back to int() or the raw dedupe keys on protocol id; why_new=the order and dedupe tests used well-formed ids and short numbers; seam=none
    def test_long_digit_titles_and_id_less_sittings_neither_crash_nor_merge(self) -> None:
        long_number = "9" * 5000
        self.assertLess(build._title_sort_key("Gesetz 10"), build._title_sort_key(f"Gesetz {long_number}"))
        self.assertLess(build._title_sort_key("Gesetz 2"), build._title_sort_key("Gesetz 010"))
        first, second = entry([GESETZ], DOCS), entry([GESETZ], DOCS, number="21/6", date="2026-01-20")
        for sitting in (first, second):
            sitting["report"]["protocol"].pop("id", None)
        bill = build.collect_bill_pages([first, second])[0]
        self.assertEqual(len(bill["raw"]["agenda_items"]), 2)
        self.assertEqual(len(bill["protocol_refs"]), 2)

    # Value: protects=search text is NFC, so a title stored with a decomposed umlaut is found by a typed composed query; fails_when=the build stops normalising data-search; why_new=search metadata tests used composed text only; seam=none; no_claim=the query-side normalisation in the browser script (bills_browser_check.js)
    def test_search_metadata_is_nfc(self) -> None:
        bills = browser_fixture_bills()[:3]
        markup = build.render_bills_index(bills)
        searches = re.findall(r'data-search="([^"]*)"', markup)
        self.assertTrue(all(value == unicodedata.normalize("NFC", value) for value in searches))
        self.assertEqual(sum("änderung des gesetzes" in value for value in searches), 2)

    # Value: protects=a bill page's speaker occurrence key equals the key the store bound, also for a speech with no rede_id; fails_when=the collector hashes the missing rede_id instead of the synthetic <protocol>:<item>:<sequence> id the store uses; why_new=no test collected bill pages from a speech without a rede_id; seam=none
    def test_a_speaker_without_a_rede_id_gets_the_synthetic_occurrence_key(self) -> None:
        bill_entry = entry([GESETZ], DOCS)
        bill_entry["report"]["protocol"]["id"] = "p1"
        bill_entry["report"]["agenda_items"][0]["xml_speakers"] = [
            {"rede_id": None, "speaker": {"display_name": "Ada Example", "fraktion": "SPD"}, "char_count": 10},
            {"rede_id": "IDREAL", "speaker": {"display_name": "Bea Beispiel", "fraktion": "SPD"}, "char_count": 10},
        ]
        speakers = {row["name"]: row["occurrence_id"] for row in build.collect_bill_pages([bill_entry])[0]["speakers"]}
        self.assertEqual(speakers["Ada Example"], speech_occurrence_id("p1", synthetic_rede_id("p1", 1, 1)))
        self.assertEqual(speakers["Bea Beispiel"], speech_occurrence_id("p1", "IDREAL"))

    # Value: protects=an agenda index written as "01" gives the bill tally the occurrence key the store mints (synthetic rede id p1:1:1); fails_when=the collector formats the raw index ("p1:01:1") so the speaker loses its person link; why_new=only int indexes reached the collector before; seam=none
    def test_a_text_index_gives_the_stored_occurrence_key(self) -> None:
        bill_entry = entry([GESETZ], DOCS)
        bill_entry["report"]["protocol"]["id"] = "p1"
        bill_entry["report"]["agenda_items"][0]["index"] = "01"
        bill_entry["report"]["agenda_items"][0]["xml_speakers"] = [
            {"rede_id": None, "speaker": {"display_name": "Ada Example", "fraktion": "SPD"}, "char_count": 10},
        ]
        (row,) = build.collect_bill_pages([bill_entry])[0]["speakers"]
        self.assertEqual(row["occurrence_id"], speech_occurrence_id("p1", synthetic_rede_id("p1", 1, 1)))

    # Value: protects=a bill page tallies a reviewed occurrence of the shared Redner-ID 11005304 under its reviewed name, as the protocol page does; fails_when=the bill collector reads the raw printed speaker, so the garbled double name gets its own row and links to whichever occurrence came last; why_new=bill tests used clean names only; seam=none
    def test_a_reviewed_occurrence_is_tallied_under_its_reviewed_name(self) -> None:
        bill_entry = entry([GESETZ], DOCS)
        bill_entry["report"]["protocol"]["id"] = "5560"
        garbled = "Dirk-UlrichAlexander Mende Föhr"
        bill_entry["report"]["agenda_items"][0]["xml_speakers"] = [
            {"rede_id": "ID209407600", "speaker": {"display_name": garbled, "fraktion": "SPD", "xml_redner_id": "11005304"}, "char_count": 10},
            {"rede_id": "ID209400000", "speaker": {"display_name": "Alexander Föhr", "fraktion": "CDU/CSU", "xml_redner_id": "11005304"}, "char_count": 10},
        ]
        speakers = {row["name"]: row["occurrence_id"] for row in build.collect_bill_pages([bill_entry])[0]["speakers"]}
        self.assertEqual(speakers, {"Dirk-Ulrich Mende": speech_occurrence_id("5560", "ID209407600"),
                                    "Alexander Föhr": speech_occurrence_id("5560", "ID209400000")})


    # Value: protects=two persons who share a display name and party keep their own bill-page row, count and link; fails_when=the tally is keyed by name+party only, so their speeches are summed and linked to whichever spoke last; why_new=bill tests had one person per name; seam=none
    def test_namesakes_of_one_party_keep_their_own_rows(self) -> None:
        bill_entry = entry([GESETZ], DOCS)
        bill_entry["report"]["protocol"]["id"] = "p1"
        bill_entry["report"]["agenda_items"][0]["xml_speakers"] = [
            {"rede_id": rede_id, "speaker": {"display_name": "Max Müller", "fraktion": "SPD", "xml_redner_id": xml}, "char_count": 10}
            for rede_id, xml in (("ID1", "1"), ("ID2", "2"), ("ID3", "1"))
        ]
        lookup = {speech_occurrence_id("p1", "ID1"): "max-a", speech_occurrence_id("p1", "ID3"): "max-a",
                  speech_occurrence_id("p1", "ID2"): "max-b"}
        speakers = build.collect_bill_pages([bill_entry], lookup)[0]["speakers"]
        rows = sorted((lookup[row["occurrence_id"]], row["speech_count"]) for row in speakers)
        self.assertEqual(rows, [("max-a", 2), ("max-b", 1)])

    def test_one_gesetzgebung_is_one_page_and_its_companions_are_listed_on_it(self) -> None:
        bills = build.collect_bill_pages([entry([GESETZ, ENTSCHLIESSUNG, ANTRAG, VERORDNUNG, WAHL], DOCS)])
        self.assertEqual([bill["vorgang_id"] for bill in bills], ["100"])
        related = {row["vorgang_id"]: row for row in bills[0]["related"]}
        self.assertEqual(set(related), {"200", "300", "400", "500"})
        self.assertEqual(related["200"]["type"], "Entschließungsantrag")
        self.assertEqual([doc["dokumentnummer"] for doc in related["200"]["documents"]], ["21/101"])
        # A companion is not part of the Gesetzgebung's own documents.
        self.assertEqual({doc["dokumentnummer"] for doc in bills[0]["documents"]}, {"21/100"})

    def test_an_item_without_a_gesetzgebung_yields_no_page(self) -> None:
        self.assertEqual(build.collect_bill_pages([entry([ENTSCHLIESSUNG, ANTRAG, VERORDNUNG, WAHL], DOCS)]), [])

    def test_the_same_gesetzgebung_over_two_sittings_stays_one_bill_with_one_companion_row(self) -> None:
        bills = build.collect_bill_pages(
            [
                entry([GESETZ, ENTSCHLIESSUNG], DOCS, "21/5", "2026-01-15"),
                entry([GESETZ, ENTSCHLIESSUNG], DOCS, "21/6", "2026-01-16"),
            ]
        )
        self.assertEqual(len(bills), 1)
        self.assertEqual([row["vorgang_id"] for row in bills[0]["related"]], ["200"])


class PageTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.out = Path(self._tmp.name)
        (self.out / "data").mkdir()
        self.bills = build.collect_bill_pages([entry([GESETZ, ENTSCHLIESSUNG, ANTRAG], DOCS)])
        build.write_bill_pages(self.out, self.bills)

    def test_the_gesetzgebung_has_a_page_its_companions_do_not(self) -> None:
        pages = sorted(path.name for path in (self.out / "bills").glob("bill-*.html"))
        self.assertEqual(pages, [f"{self.bills[0]['slug']}.html"])
        detail = (self.out / "bills" / pages[0]).read_text(encoding="utf-8")
        self.assertIn("Weitere Vorgänge zu diesem Tagesordnungspunkt", detail)
        self.assertNotIn("Begleitende Vorlagen", detail)
        self.assertIn("Entschließung zum Gesetz zur Sache", detail)
        self.assertIn("Entschließungsantrag", detail)
        self.assertIn("21/101", detail)
        self.assertNotIn(build.bill_slug({"vorgang_id": "200"}), detail)

    def test_a_link_to_a_vorgang_without_a_page_is_plain_text(self) -> None:
        slugs = {bill["slug"] for bill in self.bills}
        link = lambda vorgang: build.resolve_entity_link(  # noqa: E731
            "proceeding", vorgang, mp_lookup={}, document_numbers=set(), bill_slugs=slugs
        )
        self.assertEqual(link("100"), f"bills/{self.bills[0]['slug']}.html")
        self.assertIsNone(link("200"))

    def test_no_generated_page_links_to_a_bill_page_that_does_not_exist(self) -> None:
        existing = {path.name for path in (self.out / "bills").glob("*.html")}
        for page in (self.out / "bills").glob("*.html"):
            for href in re.findall(r'href="(?:\.\./bills/|bills/)?(bill-[^"#]+\.html)"', page.read_text(encoding="utf-8")):
                self.assertIn(href, existing, f"{page.name} links to a missing {href}")

    def test_public_labels_say_gesetzesvorhaben(self) -> None:
        index = (self.out / "bills" / "index.html").read_text(encoding="utf-8")
        detail = (self.out / "bills" / f"{self.bills[0]['slug']}.html").read_text(encoding="utf-8")
        retired = re.compile(r"\b(Gesetze verfolgen|Alle Gesetze|Aktuelle Gesetze|Verfolgte Gesetze|Gefolgte Gesetze)\b|>Gesetze<")
        for markup in (index, detail):
            self.assertIn("Gesetzesvorhaben", markup)
            # assertIsNone, not assertNotIn: a failing assertNotIn prints the whole page.
            self.assertIsNone(retired.search(markup))
        self.assertIn("Gesetzesvorhaben", index)
        self.assertIn("Alle Gesetzesvorhaben", detail)
        self.assertNotIn("Folgen", index)
        header = html.render_global_header(depth=1, active="bills")
        self.assertIn(">Gesetzesvorhaben<", header)
        self.assertIsNone(re.search(r">Gesetze<", header))

    def test_generated_overview_is_readable_first_and_has_search_metadata(self) -> None:
        markup = build.render_bills_index(browser_fixture_bills())
        nodes = parsed(markup)
        attrs = [attrs for _, attrs in nodes]
        rows = [a for a in attrs if "data-bill-row" in a]
        self.assertEqual(len(rows), 41)
        self.assertTrue(all("hidden" not in row for row in rows), "server-rendered rows must remain visible before enhancement")
        self.assertEqual(len({r["data-id"] for r in rows}), 41)
        self.assertTrue(all(r.get("data-search") and r.get("data-title") is not None for r in rows))
        self.assertTrue(any(r.get("data-date") == "" for r in rows))
        self.assertTrue(any("21/9876" in (r.get("data-search") or "") for r in rows))
        self.assertTrue(any("data-bills-index" in a for a in attrs))
        self.assertEqual(sum(tag == "h2" for tag, _ in nodes), 41)
        self.assertEqual(sum("data-bill-search" in a for a in attrs), 1)
        self.assertEqual(sum("data-bill-year" in a for a in attrs), 1)
        self.assertEqual(sum("data-bill-sort" in a for a in attrs), 1)
        self.assertTrue(all("disabled" in a for a in attrs if any(k in a for k in ("data-bill-search", "data-bill-year", "data-bill-sort"))))
        self.assertTrue(any("data-bill-summary" in a and a.get("tabindex") == "-1" for a in attrs))
        self.assertTrue(any("data-bill-announcement" in a for a in attrs))
        self.assertTrue(any("data-bill-criteria" in a for a in attrs))
        self.assertTrue(any("data-bill-no-results" in a for a in attrs))
        self.assertTrue(any("data-bill-unavailable" in a for a in attrs))

    def test_generated_empty_publication_offers_only_the_session_recovery(self) -> None:
        markup = build.render_bills_index([])
        nodes = parsed(markup)
        attrs = [attrs for _, attrs in nodes]
        self.assertFalse(any(any(k in a for k in ("data-bill-search", "data-bill-year", "data-bill-sort", "data-bill-reset", "data-bill-prev", "data-bill-next")) for a in attrs))
        self.assertTrue(any(a.get("href") == "../overview.html" for a in attrs))
        self.assertIn("Noch keine Gesetzesvorhaben verfügbar", " ".join(_MarkupText(markup).text))

    def test_generated_detail_has_reading_order_and_expanded_speakers(self) -> None:
        bill = browser_fixture_bills()[0]
        bill["speakers"] = [
            {"name": f"Redner {i}", "party": "SPD", "speech_count": i + 1, "char_count": 100+i}
            for i in range(15)
        ]
        bill["documents"] = [
            {"dokumentnummer": "21/500", "drucksachetyp": "Gesetzentwurf", "urheber": ["A"],
             "url": "https://dip.bundestag.de/vorgang/1"},
            {"dokumentnummer": "PlPr 21/1", "drucksachetyp": "Plenarprotokoll", "urheber": ["B"]},
        ]
        markup = build.render_bill_detail(bill, {})
        nodes = parsed(markup)
        ids = [a.get("id") for _, a in nodes if a.get("id")]
        expected = ["verlauf", "debatten", "redner", "abstimmungen", "dokumente", "quellen"]
        positions = [ids.index(anchor) for anchor in expected]
        self.assertEqual(positions, sorted(positions))
        # Native details keeps the remaining names available without a script.
        self.assertGreaterEqual(sum(tag == "details" for tag, _ in nodes), 1)
        self.assertIn("Weitere Rednerinnen und Redner", " ".join(_MarkupText(markup).text))
        self.assertGreaterEqual(sum("bill-speaker-name" in (a.get("class") or "") for _, a in nodes), 15)
        self.assertGreaterEqual(sum("bill-speaker-role" in (a.get("class") or "") for _, a in nodes), 15)
        self.assertGreaterEqual(sum("bill-speaker-count" in (a.get("class") or "") for _, a in nodes), 15)
        text = " ".join(_MarkupText(markup).text)
        self.assertIn("Dokumente", text)
        self.assertIn("Urheber der verknüpften Dokumente", text)
        self.assertFalse(any("data-follow-id" in a for _, a in nodes))

    # Value: protects=every glossary link on bill pages lands on an id the sources page really renders; fails_when=a slug/prefix/alias drifts from the sources-page anchor; why_new=only the href string of single terms was asserted, never the target; seam=none; no_claim=tooltip JS and in-browser :target scrolling (static HTML only)
    def test_every_glossary_link_on_bill_pages_resolves_to_a_sources_page_anchor(self) -> None:
        sources = build.render_sources_page([], features=build.publication_selection())
        source_ids = {a["id"] for _, a in parsed(sources) if a.get("id")}
        for term, entry in html.PARLIAMENTARY_GLOSSARY.items():
            self.assertIn(f"parlament-{entry['slug']}", source_ids, term)
        self.assertIn("parlamentarische-begriffe", source_ids)
        for alias, canonical in html._PARLIAMENTARY_TERM_ALIASES.items():
            self.assertIn(canonical, html.PARLIAMENTARY_GLOSSARY, alias)
        bill = browser_fixture_bills()[0]
        bill.update(
            latest_step="1. Beratung",
            events=[{"date": "2026-06-01", "kind": "Beschlussempfehlung/Bericht", "title": "x", "source": "s"}],
            documents=[
                {"dokumentnummer": "21/1", "drucksachetyp": "Beschlussempfehlung und Bericht"},
                {"dokumentnummer": "PlPr 21/1", "drucksachetyp": "Plenarprotokoll"},
            ],
            protocol_refs=[{"protocol_number": "21/1", "protocol_date": "2026-06-01", "top_id": "TOP 4"}],
            speakers=[{"name": "A", "party": "SPD", "speech_count": 1, "char_count": 1}],
        )
        linked = 0
        for markup in (build.render_bill_detail(bill, {}), build.render_bills_index([bill])):
            for tag, attrs in parsed(markup):
                if "data-bill-help" in attrs:
                    fragment = attrs["href"].split("#", 1)[1]
                    self.assertTrue(attrs["href"].startswith("../sources.html#"), attrs["href"])
                    self.assertIn(fragment, source_ids, attrs["href"])
                    linked += 1
        self.assertGreaterEqual(linked, 8)

    # Value: protects=Bundesrat papers on a bill page are not presented as Bundestag Drucksachen, and the Sprechrolle citation says what it is; fails_when=the (B)/brd check is dropped and the Bundestag Drucksache tooltip is attached to Bundesrat documents, or the sources page calls our own term an official Bundestag explanation; why_new=document labels were tested with Bundestag papers only; seam=none; no_claim=completeness of DIP's (B)//brd/ marking (real data: all 2,047 Bundesrat documents carry it)
    def test_bundesrat_documents_are_not_labelled_as_bundestag_drucksachen(self) -> None:
        bill = browser_fixture_bills()[0]
        bill["documents"] = [
            {"dokumentnummer": "557/25(B)", "drucksachetyp": "Stellungnahme", "url": "https://dserver.bundestag.de/brd/2025/0557-25B.pdf"},
            {"dokumentnummer": "300/25", "drucksachetyp": "Gesetzentwurf", "url": "https://dserver.bundestag.de/brd/2025/0300-25.pdf"},
            {"dokumentnummer": "21/500", "drucksachetyp": "Gesetzentwurf", "url": "https://dserver.bundestag.de/btd/21/005/2100500.pdf"},
        ]
        documents = build.render_bill_detail(bill, {}).split('id="dokumente"')[1].split('id="quellen"')[0]
        items = re.findall(r"<li><strong>(.*?)</strong>", documents)
        self.assertEqual(len(items), 3)
        for item, number in zip(items[:2], ("557/25(B)", "300/25")):
            self.assertTrue(item.startswith("Bundesrat-Drucksache <a "), item)
            self.assertIn(f">{number}</a>", item)
            self.assertNotIn("data-bill-help", item)
        self.assertIn(">Drucksache</a>", items[2])
        self.assertNotIn("Bundesrat", items[2])
        self.assertIn("Bundesrat", html.PARLIAMENTARY_GLOSSARY["Stellungnahme"]["kurz"])
        sources = build.render_sources_page([], features=build.publication_selection())
        sprechrolle = sources.split('id="parlament-sprechrolle"')[1].split("</li>")[0]
        self.assertIn(">Plenarprotokolle, in denen die Rolle erfasst ist</a>", sprechrolle)
        self.assertNotIn("Erläuterung beim Deutschen Bundestag", sprechrolle)
        drucksache = sources.split('id="parlament-drucksache"')[1].split("</li>")[0]
        self.assertIn(">Erläuterung beim Deutschen Bundestag</a>", drucksache)

    # Value: protects=bill detail tooltips have unique ids paired with aria-describedby, the timeline groups by date with undated last, and unsafe source URLs fail publication; fails_when=ids collide, grouping/ordering regresses, or an off-allowlist/http link is emitted; why_new=detail tests covered speakers and section order only; seam=none; no_claim=visual layout and tooltip behavior in a browser
    def test_detail_tooltip_ids_timeline_grouping_and_unsafe_event_urls(self) -> None:
        bill = browser_fixture_bills()[0]
        title = bill["title"]
        bill.update(
            events=[
                {"date": "2026-06-01", "kind": "Erste Beratung", "title": title, "source": "DIP-Vorgang", "url": "https://dip.bundestag.de/vorgang/100"},
                {"date": "2026-06-01", "kind": "Ausschussüberweisung", "title": "Überweisung <b>an</b> den Ausschuss", "source": None, "url": None},
                {"date": "2025-12-01", "kind": "Erste Beratung", "title": title, "source": "Quelle B", "url": None},
                {"date": None, "kind": "Gesetzgebung", "title": title, "source": "Quelle C", "url": None},
            ],
            documents=[
                {"dokumentnummer": "PlPr 21/1", "drucksachetyp": "Plenarprotokoll"},
                {"dokumentnummer": "21/500", "drucksachetyp": "Gesetzentwurf"},
                {"dokumentnummer": "21/501", "drucksachetyp": "Antrag"},
            ],
            protocol_refs=[
                {"protocol_number": "21/1", "protocol_date": "2026-06-01", "top_id": "Tagesordnungspunkt 4"},
                {"protocol_number": "21/2", "protocol_date": "2026-06-02", "top_id": "TOP 7"},
                {"protocol_number": "21/3", "protocol_date": "2026-06-03", "top_id": "Zusatzpunkt 21"},
                {"protocol_number": "21/4", "protocol_date": "2026-06-04", "top_id": "Einzelplan 06"},
                {"protocol_number": "21/5", "protocol_date": "2026-06-05", "top_id": "Tagesordnungspunkt\xa09"},
                {"protocol_number": "21/6", "protocol_date": "2026-06-06", "top_id": "Tagesordnungspunkt"},
            ],
            latest_step="Erste Beratung", latest_date="2026-06-01",
            votes=[{"title": "Abstimmung A", "date": "2026-06-01", "detail_url": "https://www.bundestag.de/abstimmung?id=100"}],
        )
        markup = build.render_bill_detail(bill, {})
        nodes = parsed(markup)
        self.assertIn('<ul class="bill-votes"><li><strong><a href="https://www.bundestag.de/abstimmung?id=100">Abstimmung A</a>', markup)
        self.assertIn(' · <a href="https://dip.bundestag.de/vorgang/100">Quelle öffnen</a>', markup)
        ids = [a["id"] for _, a in nodes if a.get("id")]
        self.assertEqual(len(ids), len(set(ids)), "duplicate ids break aria-describedby and anchors")
        helped = [a for _, a in nodes if "data-bill-help" in a]
        self.assertGreaterEqual(len(helped), 8)
        for attrs in helped:
            self.assertEqual(attrs["aria-describedby"], attrs["data-bill-help"])
            self.assertIn(attrs["data-bill-help"], ids)
        dates = re.findall(r'<h3 class="bill-event-date">(.*?)</h3>', markup)
        self.assertEqual(len(dates), 3)
        self.assertIn('datetime="2026-06-01"', dates[0])
        self.assertIn('datetime="2025-12-01"', dates[1])
        self.assertEqual(dates[2], "Datum nicht erfasst")
        timeline = markup.split('id="verlauf"')[1].split('id="debatten"')[0]
        self.assertNotIn(f"<p>{title}</p>", timeline, "an event title equal to the bill title is not repeated")
        self.assertIn("Überweisung &lt;b&gt;an&lt;/b&gt; den Ausschuss", timeline)
        self.assertIn("Quelle nicht verknüpft", timeline)
        self.assertIn('<a href="https://dip.bundestag.de/vorgang/100">DIP-Vorgang</a>', timeline)
        # Documents: Plenarprotokoll and Drucksache are glossary terms, anything else is plain.
        documents = markup.split('id="dokumente"')[1]
        self.assertIn(">Plenarprotokoll</a>", documents)
        self.assertIn(">Drucksache</a>", documents)
        self.assertIn("Dokument 21/501", documents)
        # A TOP id reads "Tagesordnungspunkt N" once; Zusatzpunkte and Einzelplaene keep their own label.
        debates = markup.split('id="debatten"')[1].split('id="redner"')[0]
        visible = re.sub(r'<span class="bill-tooltip".*?</span>', "", debates)
        labels = [" ".join("".join(_MarkupText(row).text).split()) for row in re.findall(r"<li>(.*?)</li>", visible, flags=re.S)]
        self.assertEqual([label.split(" · ", 1)[1] for label in labels], [
            "Tagesordnungspunkt 4", "Tagesordnungspunkt 7", "Zusatzpunkt 21", "Einzelplan 06",
            "Tagesordnungspunkt 9", "Tagesordnungspunkt nicht erfasst",
        ])
        for bad_url in ("http://dip.bundestag.de/vorgang/1", "https://evil.example/vorgang/1"):
            unsafe = copy.deepcopy(bill)
            unsafe["events"][0]["url"] = bad_url
            with self.assertRaises(build.publication.PublicationStateError, msg=bad_url):
                build.render_bill_detail(unsafe, {})

    # Value: protects=the overview offers exactly the years present in the data (newest first), shows undated bills as "Datum nicht erfasst" without a <time>, and escapes titles; fails_when=year options or undated/escaping handling regress; why_new=index tests assert row metadata only; seam=none; no_claim=client-side year filtering (see bills_browser_check.js)
    def test_index_year_options_undated_row_and_title_escaping(self) -> None:
        bills = browser_fixture_bills()
        bills[3]["title"] = 'Gesetz <img src=x onerror="1"> & mehr'
        markup = build.render_bills_index(bills)
        options = re.findall(r'<option value="(\d{4})">', markup)
        self.assertEqual(options, ["2026", "2024", "2022"])
        self.assertNotIn("<img", markup)
        self.assertIn("Gesetz &lt;img src=x onerror=&quot;1&quot;&gt; &amp; mehr", markup)
        undated = markup.split('data-id="browser-40"')[1].split("</article>")[0]
        self.assertIn("Datum nicht erfasst", undated)
        self.assertNotIn("<time", undated)
        self.assertIn('data-date=""', undated)
        dated = markup.split('data-id="browser-00"')[1].split("</article>")[0]
        self.assertIn('<time datetime="2022-06-01">', dated)

    # Value: protects=the related-Vorgaenge list renders each row's title, type and Drucksache numbers, falls back to "Ohne Titel", escapes markup and is absent when there are none; fails_when=a row field is dropped or unescaped, the fallback goes, or the heading is emitted for an empty list; why_new=only the heading string was asserted through write_bill_pages; seam=none; no_claim=which Vorgaenge collect_bill_pages selects as related (CollectTests)
    def test_related_vorgaenge_rows_render_title_type_numbers_and_escape(self) -> None:
        bill = browser_fixture_bills()[0]
        bill["related"] = [
            {"title": "Entschließung <script>x</script>", "type": "Entschließungsantrag",
             "documents": [{"dokumentnummer": "21/101"}, {"dokumentnummer": None}, {"dokumentnummer": "21/102"}]},
            {"title": None, "type": "Antrag", "documents": []},
        ]
        markup = build.render_bill_detail(bill, {})
        self.assertIn("Weitere Vorgänge zu diesem Tagesordnungspunkt", markup)
        self.assertIn("Sie sind nicht automatisch Änderungen dieses Vorhabens.", markup)
        items = re.findall(r'<ul class="bill-related">(.*?)</ul>', markup, flags=re.S)
        self.assertEqual(len(items), 1)
        rows = re.findall(r"<li>(.*?)</li>", items[0], flags=re.S)
        self.assertEqual(rows, [
            "<strong>Entschließung &lt;script&gt;x&lt;/script&gt;</strong><p>Entschließungsantrag · 21/101, 21/102</p>",
            "<strong>Ohne Titel</strong><p>Antrag</p>",
        ])
        self.assertNotIn("<script>x", markup)
        bill["related"] = []
        empty = build.render_bill_detail(bill, {})
        self.assertNotIn("Weitere Vorgänge", empty)
        self.assertNotIn("bill-related", empty.split("<style>")[0] + empty.split("</style>")[1])

    # Value: protects=a bill with no events, documents, speakers, debates, votes or title renders readable empty states instead of crashing, and the overview ships its scripts only when it has rows; fails_when=a missing-data fallback or the empty-list guard is removed, or the scripts are emitted for an empty overview; why_new=detail tests always supplied data and the empty-overview test checked controls only; seam=none; no_claim=script behavior (bills_browser_check.js)
    def test_bare_bill_detail_and_empty_overview_degrade_to_readable_states(self) -> None:
        bare = {"id": "bare", "slug": "bill-bare"}
        markup = build.render_bill_detail(bare, {})
        text = " ".join(_MarkupText(markup).text)
        for message in (
            "Unbenanntes Gesetzesvorhaben", "Datum nicht erfasst", "Erfasster Vorgang",
            "Keine Verlaufseinträge in den erfassten Daten.", "Keine Debatten in den erfassten Daten verknüpft.",
            "Keine Reden in den erfassten Daten zugeordnet.", "Keine namentliche Abstimmung in den erfassten Daten verknüpft.",
            "Keine Dokumente in den erfassten Daten verknüpft.", "Urheber der verknüpften Dokumente: nicht erfasst.",
            "DIP-Vorgang: nicht erfasst.",
        ):
            self.assertIn(message, text)
        self.assertIsNone(re.search(r'class="bill-(events|documents|speakers|votes|debates|related)"', markup.split("</style>")[1]))
        # Debates and votes without a link target keep a plain label.
        partial = browser_fixture_bills()[0]
        partial.update(
            protocol_refs=[{"protocol_number": None, "protocol_date": None, "top_id": None}],
            votes=[{"title": None, "date": None}],
        )
        body = build.render_bill_detail(partial, {}).split("</style>")[1]
        self.assertIn("<strong>Sitzung ohne Nummer</strong>", body)
        self.assertIn("nicht erfasst</p>", body)
        self.assertIn("<strong>Namentliche Abstimmung</strong><p>Datum nicht erfasst</p>", body)
        self.assertNotIn("<a href=\"None", body)
        # Scripts: only an overview with rows carries them; the empty overview and the detail do not need the list script.
        script = build.render_bill_script()
        helper = build.render_bill_help_script()
        full = build.render_bills_index(browser_fixture_bills()[:2])
        empty = build.render_bills_index([])
        self.assertEqual((full.count(script), full.count(helper)), (1, 1))
        self.assertEqual((empty.count(script), empty.count(helper)), (0, 0))
        detail = build.render_bill_detail(partial, {})
        self.assertEqual((detail.count(helper), detail.count(script)), (1, 0))

    # Value: protects=each speech link label carries date, session number and source page in a fixed order, speeches ship in data/bills.json with the same shape the page reads; fails_when=source_page is dropped from the collected ref, the label parts reorder, or write_bill_pages stops serialising speakers[].speeches; why_new=the collector test asserted hrefs and counts, never labels or the written bills.json; seam=none; no_claim=how external consumers read bills.json (no consumer in repo)
    def test_speech_link_labels_and_written_bills_json_carry_the_same_speech_refs(self) -> None:
        current = entry([GESETZ], DOCS)
        current["report"]["protocol"]["id"] = "p1"
        current["report"]["agenda_items"][0]["xml_speakers"] = [
            {"rede_id": "ID1", "speaker": {"display_name": "Ada Example", "fraktion": "SPD"}, "char_count": 10,
             "source_page": {"page": 7, "quadrant": "B"}},
            {"rede_id": "ID2", "speaker": {"display_name": "Ada Example", "fraktion": "SPD"}, "char_count": 20},
        ]
        bills = build.collect_bill_pages([current])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "data").mkdir()
            build.write_bill_pages(out, bills)
            written = json.loads((out / "data" / "bills.json").read_text(encoding="utf-8"))
            page = (out / "bills" / f"{bills[0]['slug']}.html").read_text(encoding="utf-8")
        refs = written[0]["speakers"][0]["speeches"]
        self.assertEqual(refs, bills[0]["speakers"][0]["speeches"])
        self.assertEqual(
            sorted((ref["href"], ref["protocol_number"], ref["protocol_date"], ref["source_page"]) for ref in refs),
            [("../protocols/plenarprotokoll-21-5.html#speech-1-ID1", "21/5", "2026-01-15", {"page": 7, "quadrant": "B"}),
             ("../protocols/plenarprotokoll-21-5.html#speech-1-ID2", "21/5", "2026-01-15", None)],
        )
        labels = re.findall(r'<div class="bill-speech-links">(.*?)</div>', page, flags=re.S)[0]
        self.assertEqual(
            re.findall(r">([^<]+)</a>", labels),
            ["Rede 1 · 15.01.2026 · Sitzung 21/5 · S. 7B", "Rede 2 · 15.01.2026 · Sitzung 21/5"],
        )


class _MarkupText(HTMLParser):
    def __init__(self, markup: str) -> None:
        super().__init__()
        self.text: list[str] = []
        self.feed(markup)

    def handle_data(self, data: str) -> None:
        self.text.append(data)


if __name__ == "__main__":
    if "--browser-fixture" in sys.argv:
        parser = argparse.ArgumentParser()
        parser.add_argument("--browser-fixture", type=Path, required=True)
        write_browser_fixture(parser.parse_args().browser_fixture)
    else:
        unittest.main()
