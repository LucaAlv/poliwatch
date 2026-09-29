"""A Rede's text is what its Redner said (CONTEXT.md: Rede, Sitzungsleitung,
Zwischenfrage). The Präsident's words and other MdBs' Zwischenfragen inside the
<rede> element are not counted. Fixture: rede-interjections.xml, three real
Reden cut from Plenarprotokoll 21/84."""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

import _support  # noqa: F401
import validate_dip_protocol as dip
from _support import FIXTURES

REDEN = {
    rede.attrib["id"]: rede
    for rede in ET.parse(FIXTURES / "rede-interjections.xml").getroot().iter("rede")
}


def old_text(rede: ET.Element) -> str:
    """What the parser stored before: every <p> except the marker lines."""
    return dip.clean_text(
        " ".join(
            dip.elem_text(paragraph)
            for paragraph in rede.findall("p")
            if paragraph.attrib.get("klasse") != "redner" and dip.elem_text(paragraph)
        )
    )


class ZwischenfrageTests(unittest.TestCase):
    """ID218401300, Emmi Zeulner: the Präsidentin asks, Zeulner agrees, the Präsidentin
    lets the asker ask, Johannes Wagner asks, Zeulner answers."""

    def setUp(self) -> None:
        self.rede = REDEN["ID218401300"]
        self.result = dip.speech_text_and_paragraphs(self.rede)

    def test_only_the_redners_paragraphs_are_kept_in_order(self) -> None:
        starts = [
            "Sehr geehrte Frau Präsidentin! Liebe Ko",
            "Selbstverständlich.",
            "Das Thema der Finanzierung der Gesundhe",
            "Aber natürlich ist es nicht das Ende de",
            "Es ist insgesamt ein hochsensibles Them",
            "Jetzt ist die Aufgabe, in kluger Art un",
            "Es wird auch einen Tag nach den Reformgesetzen",
            "Danke.",
        ]
        self.assertEqual(len(self.result.paragraphs), len(starts))
        for paragraph, start in zip(self.result.paragraphs, starts):
            self.assertTrue(paragraph.startswith(start), f"{paragraph[:50]!r} does not start with {start!r}")

    def test_the_sitzungsleitung_and_the_asker_are_not_counted(self) -> None:
        text = self.result.text
        self.assertNotIn("lassen Sie eine Zwischenfrage", text)  # Präsidentin
        self.assertNotIn("Bitte.", text)  # Präsidentin
        self.assertNotIn("Vielen Dank, Frau Präsidentin. – Vielen Dank, Frau Kollegin Zeulner", text)  # Wagner
        self.assertNotIn("Ihre Redezeit ist abgelaufen", text)  # Präsidentin's closing interjection
        self.assertEqual(self.result.unattributed_chars, 0)

    def test_the_counted_text_is_shorter_than_the_old_all_paragraphs_text(self) -> None:
        old = old_text(self.rede)
        # Old: Präsidentin (3 paragraphs) and Wagner (1) were counted as Zeulner's.
        self.assertGreater(len(old), len(self.result.text))
        for foreign in ("lassen Sie eine Zwischenfrage", "Ihre Redezeit ist abgelaufen"):
            self.assertIn(foreign, old)
        self.assertEqual(len(self.result.text), len(dip.clean_text(" ".join(self.result.paragraphs))))


class InterjectionTests(unittest.TestCase):
    def test_an_interjection_followed_by_a_resuming_marker(self) -> None:
        result = dip.speech_text_and_paragraphs(REDEN["ID218400200"])
        self.assertNotIn("Ihre Zeit ist um.", result.text)
        # The Redner resumes under a marker carrying the same id.
        self.assertIn("– und handeln Sie im Interesse Ihres Arbeitgebers", result.text)
        self.assertIn("Vielen Dank.", result.paragraphs)
        self.assertEqual(result.unattributed_chars, 0)

    def test_closing_words_of_the_sitzungsleitung_after_the_last_marker_are_not_the_redners(self) -> None:
        for rede_id, closing in (
            ("ID218400200", "Für die SPD-Fraktion hat nun Herr Abgeordneter Dr. Christos Pantazis das Wort"),
            ("ID218400400", "Für die Fraktion Die Linke hat nun Frau Abgeordnete Stella Merendino das Wort"),
        ):
            with self.subTest(rede_id):
                result = dip.speech_text_and_paragraphs(REDEN[rede_id])
                self.assertNotIn(closing, result.text)
                self.assertIn(closing, old_text(REDEN[rede_id]))

    def test_every_interjection_of_a_rede_with_several_is_excluded(self) -> None:
        result = dip.speech_text_and_paragraphs(REDEN["ID218400400"])
        self.assertNotIn("Ihre Redezeit ist abgelaufen", result.text)
        self.assertEqual(
            [paragraph for paragraph in result.paragraphs if paragraph.startswith(("– sondern", "Wir sagen"))],
            [
                "– sondern schreibt Gastbeiträge für die Pharmaindustrie.",
                "Wir sagen dieser Gesundheitspolitik den Kampf an.",
            ],
        )


def rede(*children: str) -> ET.Element:
    return ET.fromstring("<rede id='R1'>" + "".join(children) + "</rede>")


def marker(redner_id: str | None) -> str:
    attribute = f' id="{redner_id}"' if redner_id is not None else ""
    return f'<p klasse="redner"><redner{attribute}><name><vorname>V</vorname><nachname>N</nachname></name></redner>V N:</p>'


class UndeterminableSpeakerTests(unittest.TestCase):
    def test_text_after_a_marker_that_names_nobody_is_attributed_to_nobody(self) -> None:
        result = dip.speech_text_and_paragraphs(
            rede(
                marker("100"),
                '<p klasse="J_1">Eigene Worte.</p>',
                marker(None),
                '<p klasse="J_1">Wessen Worte?</p>',
                marker("100"),
                '<p klasse="J_1">Wieder eigene Worte.</p>',
            )
        )
        self.assertEqual(result.paragraphs, ["Eigene Worte.", "Wieder eigene Worte."])
        self.assertEqual(result.unattributed_chars, len("Wessen Worte?"))
        # Not the Redner's and not stored as the Sitzungsleitung's either.
        self.assertNotIn("Wessen", result.text)

    def test_a_rede_that_never_names_its_redner_has_no_counted_text(self) -> None:
        result = dip.speech_text_and_paragraphs(rede('<p klasse="J_1">Herrenlos.</p>'))
        self.assertEqual((result.text, result.paragraphs), ("", []))
        self.assertEqual(result.unattributed_chars, len("Herrenlos."))

    def test_a_merged_two_id_marker_is_the_first_person(self) -> None:
        # Bundestag XML: id="11005217 999990074" is one person; the Redner keeps
        # the words spoken under either spelling of the id.
        result = dip.speech_text_and_paragraphs(
            rede(
                marker("11005217 999990074"),
                '<p klasse="J_1">Erster Teil.</p>',
                "<name>Präsidentin Julia Klöckner:</name>",
                '<p klasse="J_1">Kommen Sie zum Schluss.</p>',
                marker("11005217"),
                '<p klasse="J_1">Zweiter Teil.</p>',
            )
        )
        self.assertEqual(result.paragraphs, ["Erster Teil.", "Zweiter Teil."])

    def test_kommentare_and_empty_paragraphs_are_not_text(self) -> None:
        result = dip.speech_text_and_paragraphs(
            rede(marker("100"), "<kommentar>(Beifall)</kommentar>", '<p klasse="J"></p>', '<p klasse="J">Text.</p>')
        )
        self.assertEqual(result.paragraphs, ["Text."])
        self.assertEqual(result.unattributed_chars, 0)


class ParsedProtocolTests(unittest.TestCase):
    def test_a_parsed_speech_carries_the_redners_counts_and_the_unattributed_chars(self) -> None:
        xml = (FIXTURES / "rede-interjections.xml").read_text(encoding="utf-8")
        parsed = dip.parse_protocol_xml(xml)
        speeches = parsed["agenda_items"][0]["speeches"]
        self.assertEqual([s["rede_id"] for s in speeches], ["ID218401300", "ID218400400", "ID218400200"])
        for speech in speeches:
            self.assertEqual(speech["char_count"], len(speech["text"]))
            self.assertEqual(speech["paragraph_count"], len(speech["paragraphs"]))
            self.assertEqual(speech["unattributed_char_count"], 0)
        zeulner = speeches[0]
        self.assertEqual(zeulner["speaker"]["display_name"], "Emmi Zeulner")
        self.assertEqual(zeulner["paragraph_count"], 8)

    def test_the_report_keeps_the_unattributed_count_so_persist_can_store_it(self) -> None:
        class FakeClient:
            def list_all(self, path: str, params: dict[str, str]) -> list:
                return []

        parsed = dip.parse_protocol_xml((FIXTURES / "rede-interjections.xml").read_text(encoding="utf-8"))
        enrichment = dip.enrich_with_api(
            FakeClient(),  # type: ignore[arg-type]
            {"id": "5805", "datum": "2026-09-25"},
            parsed,
            person_limit=0,
            vote_scan_pages=0,
        )
        speakers = enrichment["agenda_items"][0]["xml_speakers"]
        self.assertEqual([speaker["unattributed_char_count"] for speaker in speakers], [0, 0, 0])


class PersistedCountsTests(unittest.TestCase):
    def test_persist_stores_the_redners_chars_and_null_for_a_report_that_predates_the_count(self) -> None:
        import sqlite3
        import tempfile
        from pathlib import Path

        import persist_dip_pulse_store as pulse_store

        def report(speech_extra: dict) -> dict:
            return {
                "protocol": {"id": "p1", "dokumentnummer": "21/84", "datum": "2026-09-25"},
                "agenda_items": [
                    {
                        "index": 1,
                        "top_id": "T1",
                        "heading": "TOP 1",
                        "xml_speakers": [
                            {
                                "rede_id": "R1",
                                "speaker": {"xml_redner_id": "1", "display_name": "Ada", "fraktion": "SPD"},
                                "paragraph_count": 1,
                                "char_count": 5,
                                "text": "Hallo",
                                "snippet": "Hallo",
                                **speech_extra,
                            }
                        ],
                    }
                ],
            }

        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "store.sqlite")
            try:
                pulse_store.initialize(conn)
                pulse_store.persist_report(conn, report({"unattributed_char_count": 7}))
                self.assertEqual(conn.execute("SELECT char_count, unattributed_char_count FROM speeches").fetchone()[:], (5, 7))
                pulse_store.persist_report(conn, report({}))
                self.assertEqual(conn.execute("SELECT char_count, unattributed_char_count FROM speeches").fetchone()[:], (5, None))
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
