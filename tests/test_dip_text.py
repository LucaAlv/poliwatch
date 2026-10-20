from __future__ import annotations

import unittest

import _support  # noqa: F401
from dip_text import CONTEXT_TEASER, abstract_teaser, abstract_text, committee_genitive


class AbstractTextTests(unittest.TestCase):
    """dip_text.abstract_text: DIP abstract HTML to plain paragraphs (F7)."""

    # Value: protects=DIP abstract markup (<br />\r\n runs, <strong>, nested or unclosed tags, entities, a <script>) becomes plain paragraphs the caller can escape; fails_when=the sanitizer is a regex that misses nesting or keeps script text, or <br> runs collapse into one paragraph; why_new=no abstract was stored or shown before B4; seam=none
    def test_the_table(self) -> None:
        cases = [
            (None, ""),
            ("", ""),
            ("  Ein Satz.  ", "Ein Satz."),
            ("Erster Absatz<br />\r\n<br />\r\nZweiter", "Erster Absatz\n\nZweiter"),
            ("Eins<br>Zwei<BR/>Drei", "Eins\n\nZwei\n\nDrei"),
            ("Zeile\r\nweiter  im\tText", "Zeile weiter im Text"),
            ("<strong>Beschlussempfehlung:</strong> Annahme", "Beschlussempfehlung: Annahme"),
            ("<strong>fett <a href='x'>und <em>tief</em></a></strong> verschachtelt", "fett und tief verschachtelt"),
            ("&quot;Zitat&quot; &ndash; &bdquo;so&ldquo; &#39;x&#39; &amp;lt;", "\"Zitat\" – „so“ 'x' &lt;"),
            ("Vor<script>alert(1)</script>nach<style>p{}</style>", "Vornach"),
            ("<div>Block eins</div><div>Block zwei</div>", "Block eins\n\nBlock zwei"),
            ("offen <strong>nie geschlossen", "offen nie geschlossen"),
            ("a < b und c > d", "a < b und c > d"),
            ("Ende<br />\r\n", "Ende"),
        ]
        for raw_text, expected in cases:
            with self.subTest(raw=raw_text):
                self.assertEqual(abstract_text(raw_text), expected)


class AbstractTeaserTests(unittest.TestCase):
    def test_a_short_first_paragraph_is_the_teaser(self) -> None:
        self.assertEqual(abstract_teaser("Kurz.\n\nZweiter Absatz."), ("Kurz.", True))
        self.assertEqual(abstract_teaser("Kurz."), ("Kurz.", False))

    def test_a_long_paragraph_is_cut_at_a_sentence_not_at_an_abbreviation(self) -> None:
        first = "Änderung des § 5 Abs. 2 Nr. 3 und Art. 1 z. B. bei Renten. " + "Weiterer Satz mit Inhalt. " * 20
        teaser, more = abstract_teaser(first.strip())
        self.assertTrue(more)
        # The last whole sentence within the limit: nine more after the first.
        self.assertEqual(teaser, "Änderung des § 5 Abs. 2 Nr. 3 und Art. 1 z. B. bei Renten. " + "Weiterer Satz mit Inhalt. " * 8 + "Weiterer Satz mit Inhalt.")
        self.assertLessEqual(len(teaser), CONTEXT_TEASER)
        # "Abs.", "Nr. 3", "Art. 1" and "z. B." end no sentence.
        self.assertEqual(abstract_teaser("Nach § 5 Abs. 2 Nr. 3 z. B. gilt " + "x" * 300)[0], "Nach § 5 Abs. 2 Nr. 3 z. B. gilt …")

    def test_without_a_sentence_end_it_is_cut_at_a_word_with_an_ellipsis(self) -> None:
        teaser, more = abstract_teaser("wort " * 100)
        self.assertTrue(more)
        self.assertTrue(teaser.endswith("wort …"))
        self.assertLessEqual(len(teaser), CONTEXT_TEASER + 2)


REFERENCE_URHEBER = (
    # Every Beschlussempfehlung urheber on the reference store (2026-10-20).
    "Petitionsausschuss", "Haushaltsausschuss", "Finanzausschuss", "Auswärtiger Ausschuss",
    "Ausschuss für Inneres und Heimat", "Ausschuss für Klimaschutz und Energie", "Rechtsausschuss",
    "Ausschuss für Arbeit und Soziales", "Wirtschaftsausschuss", "Ausschuss für Gesundheit", "Verkehrsausschuss",
    "Ausschuss für Ernährung und Landwirtschaft", "Ausschuss für Wohnen, Stadtentwicklung, Bauwesen und Kommunen",
    "Ausschuss für Wirtschaft und Energie", "Ausschuss für Umwelt, Naturschutz, nukleare Sicherheit und Verbraucherschutz",
    "Innenausschuss", "Ausschuss für Bildung, Forschung und Technikfolgenabschätzung",
    "Ausschuss für Umwelt, Klimaschutz, Naturschutz und nukleare Sicherheit", "Ausschuss für Recht und Verbraucherschutz",
    "Verteidigungsausschuss", "Ausschuss für wirtschaftliche Zusammenarbeit und Entwicklung",
    "Ausschuss für Familie, Senioren, Frauen und Jugend", "Ausschuss für Wahlprüfung, Immunität und Geschäftsordnung",
    "Ausschuss für Landwirtschaft, Ernährung und Heimat", "Ausschuss für Kultur und Medien", "Sportausschuss",
    "Ausschuss für Digitales", "Vermittlungsausschuss", "Ältestenrat", "Ausschuss für Menschenrechte und humanitäre Hilfe",
    "Ausschuss für Digitales und Staatsmodernisierung", "Wahlprüfungsausschuss",
    "Ausschuss für die Angelegenheiten der Europäischen Union", "Ausschuss für Bildung, Familie, Senioren, Frauen und Jugend",
    "Ausschuss für Tourismus", "Ausschuss für Sport und Ehrenamt",
    "Bundesministerium für Umwelt, Naturschutz, nukleare Sicherheit und Verbraucherschutz",
    "Ausschuss für Forschung, Technologie, Raumfahrt und Technikfolgenabschätzung",
    "2. Untersuchungsausschuss", "1. Untersuchungsausschuss",
)


class CommitteeGenitiveTests(unittest.TestCase):
    def test_known_shapes(self) -> None:
        self.assertEqual(committee_genitive("Haushaltsausschuss"), "des Haushaltsausschusses")
        self.assertEqual(committee_genitive("Auswärtiger Ausschuss"), "des Auswärtigen Ausschusses")
        self.assertEqual(committee_genitive("Ausschuss für Inneres und Heimat"), "des Ausschusses für Inneres und Heimat")
        self.assertEqual(committee_genitive("Ältestenrat"), "des Ältestenrates")
        self.assertEqual(committee_genitive("1. Untersuchungsausschuss"), "des 1. Untersuchungsausschusses")
        self.assertEqual(
            committee_genitive("Bundesministerium für Umwelt, Naturschutz, nukleare Sicherheit und Verbraucherschutz"),
            "des Bundesministeriums für Umwelt, Naturschutz, nukleare Sicherheit und Verbraucherschutz",
        )

    def test_every_reference_urheber_inflects(self) -> None:
        for name in REFERENCE_URHEBER:
            with self.subTest(name=name):
                genitive = committee_genitive(name)
                self.assertIsNotNone(genitive)
                self.assertTrue(genitive.startswith("des "))
                self.assertRegex(genitive, r"(ausschusses|Ausschusses|rates|iums)\b")

    def test_an_unknown_shape_is_not_guessed(self) -> None:
        for name in ("Bundesregierung", "Fraktion der SPD", ""):
            with self.subTest(name=name):
                self.assertIsNone(committee_genitive(name))


if __name__ == "__main__":
    unittest.main()
