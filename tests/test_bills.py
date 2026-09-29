"""Only a Gesetzgebung has a bill page (CONTEXT.md: Gesetzgebung, Gesetzesvorhaben):
the Vorgang's DIP Vorgangstyp decides, not a keyword in its title."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401
import build_dip_pulse_site as build
import render_dip_pulse_html as html


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


class PredicateTests(unittest.TestCase):
    def test_only_the_vorgangstyp_gesetzgebung_is_legislation(self) -> None:
        self.assertTrue(build.is_gesetzgebung(GESETZ))
        for other in (ENTSCHLIESSUNG, ANTRAG, VERORDNUNG, WAHL, {}):
            with self.subTest(other.get("vorgangstyp")):
                # The keyword test kept these through "Gesetz", "Grundgesetz" and
                # "gesetzliche Krankenversicherung" in a title.
                self.assertFalse(build.is_gesetzgebung(other))


class CollectTests(unittest.TestCase):
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
        self.assertIn("Aktuelle Gesetzesvorhaben", index)
        self.assertIn("Alle Gesetzesvorhaben", detail)
        self.assertIn("Gesetzesvorhaben verfolgen", index)
        header = html.render_global_header(depth=1, active="bills")
        self.assertIn(">Gesetzesvorhaben<", header)
        self.assertIsNone(re.search(r">Gesetze<", header))


if __name__ == "__main__":
    unittest.main()
