"""A Rede's text is what its Redner said (CONTEXT.md: Rede, Sitzungsleitung,
Zwischenfrage). The Präsident's words and other MdBs' Zwischenfragen inside the
<rede> element are not counted. Fixture: rede-interjections.xml, three real
Reden cut from Plenarprotokoll 21/84."""

from __future__ import annotations

import time
import unittest
import xml.etree.ElementTree as ET

import _support  # noqa: F401
import persist_dip_pulse_store as store
import speech_kinds
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


class PrintedParagraphTests(unittest.TestCase):
    """The stored wording breaks where the print does: a flush ``<p klasse="O">``
    after a Zwischenruf goes on in the paragraph the Zwischenruf interrupted."""

    KOMMENTAR = "<kommentar>(Beifall)</kommentar>"

    def paragraphs(self, *body: str) -> list[str]:
        return dip.speech_text_and_paragraphs(rede(marker("100"), *body)).paragraphs

    # Value: protects=a sentence a Zwischenruf interrupts stays one paragraph, and an indented <p> after it opens one;
    #   fails_when=every <p> is a paragraph (48,440 breaks inside a sentence on 806 sittings); why_new=new rule; seam=none
    def test_a_flush_paragraph_after_a_kommentar_continues(self) -> None:
        self.assertEqual(
            self.paragraphs('<p klasse="J_1">Wir wollen,</p>', self.KOMMENTAR, '<p klasse="O">dass es gelingt.</p>',
                            self.KOMMENTAR, self.KOMMENTAR, '<p klasse="O">Ja, wirklich.</p>',
                            self.KOMMENTAR, '<p klasse="J">Ein neuer Absatz.</p>'),
            ["Wir wollen, dass es gelingt. Ja, wirklich.", "Ein neuer Absatz."])

    def test_a_page_anchor_or_an_empty_paragraph_does_not_end_the_interruption(self) -> None:
        self.assertEqual(
            self.paragraphs('<p klasse="J_1">Wir wollen,</p>', self.KOMMENTAR, '<a id="S1"/>', '<p klasse="J"></p>',
                            '<p klasse="O">dass es gelingt.</p>'),
            ["Wir wollen, dass es gelingt."])

    def test_a_flush_paragraph_after_anything_else_opens_one(self) -> None:
        quote = '<p klasse="Z">Zitat.</p>'
        for between in ("", quote, self.KOMMENTAR + quote, quote + self.KOMMENTAR):
            with self.subTest(between=between):
                self.assertEqual(self.paragraphs('<p klasse="J_1">Vorher.</p>', between, '<p klasse="O">Nachher.</p>')[-1],
                                 "Nachher.")

    # Value: protects=words are never joined across another speaker's turn; fails_when=an O paragraph after the chair's
    #   or a new marker's turn is glued to what its speaker said before; why_new=new rule; seam=none
    def test_another_turn_always_ends_the_paragraph(self) -> None:
        self.assertEqual(
            self.paragraphs('<p klasse="J_1">Eins.</p>', "<name>Präsidentin Julia Klöckner:</name>",
                            '<p klasse="J_1">Bitte zum Schluss.</p>', marker("100"), self.KOMMENTAR, '<p klasse="O">Zwei.</p>'),
            ["Eins.", "Zwei."])
        self.assertEqual(
            self.paragraphs('<p klasse="J_1">Eins.</p>', self.KOMMENTAR, marker("100"), '<p klasse="O">Zwei.</p>'),
            ["Eins.", "Zwei."])

    # Value: protects=another speaker's turn inside the Rede keeps the printed paragraphs too; fails_when=its branch of
    #   the walk reads every <p> as a paragraph; why_new=only the owner's branch was driven; seam=none
    def test_a_nested_turn_keeps_the_printed_paragraphs(self) -> None:
        _own, [turn] = dip.speech_segments(rede(
            marker("100"), '<p klasse="J_1">Rede.</p>', marker("200"), '<p klasse="J_1">Wissen Sie,</p>', self.KOMMENTAR,
            '<p klasse="O">dass das stimmt?</p>', '<p klasse="J">Und warum?</p>'))
        self.assertEqual(turn["paragraphs"], ["Wissen Sie, dass das stimmt?", "Und warum?"])

    def test_the_wording_joins_paragraphs_with_one_line_feed(self) -> None:
        result = dip.speech_text_and_paragraphs(
            rede(marker("100"), '<p klasse="J_1">Erster\n  Absatz.</p>', '<p klasse="J">Zweiter\u00a0Absatz.</p>'))
        self.assertEqual(result.text, "Erster Absatz.\nZweiter Absatz.")

    # Value: protects=a question of the Fragestunde keeps the print's paragraphs too; fails_when=its walk reads every <p>
    #   as a paragraph; why_new=second walk; seam=none
    def test_a_fragestunde_turn_keeps_the_printed_paragraphs(self) -> None:
        top = ET.fromstring(
            '<tagesordnungspunkt><p klasse="redner"><redner id="7"><name><vorname>A</vorname><nachname>B</nachname>'
            '<fraktion>SPD</fraktion></name></redner></p><p klasse="J_1">Warum,</p><kommentar>(Zuruf)</kommentar>'
            '<p klasse="O">frage ich.</p><p klasse="J">Und wann?</p></tagesordnungspunkt>')
        turns, _ = speech_kinds.fragestunde_turns(top)
        self.assertEqual([turn.paragraphs for turn in turns], [["Warum, frage ich.", "Und wann?"]])

    # Value: protects=the store keeps the breaks and only those; fails_when=persist collapses them again (clean) or lets
    #   other whitespace through; why_new=new cleaner; seam=none
    def test_the_store_keeps_the_breaks(self) -> None:
        self.assertEqual(store.clean_wording(" Eins\u00a0 zwei.\n\n Drei. \n"), "Eins zwei.\nDrei.")
        self.assertIsNone(store.clean_wording(None))
        self.assertIsNone(store.clean_wording(" \n "))


class BlockQuoteTests(unittest.TestCase):
    """WP 18 wraps about half of its block quotes in <zitat>; whoever is speaking reads it out."""

    def parse(self, body: str, wrap: bool = True, top: str = "Tagesordnungspunkt 1") -> dict:
        quote = '<zitat><a id="S2"/><p klasse="Z">Das Zitat.</p></zitat>' if wrap else '<a id="S2"/><p klasse="Z">Das Zitat.</p>'
        return dip.parse_protocol_xml(
            '<dbtplenarprotokoll wahlperiode="18" sitzung-nr="1"><sitzungsverlauf>'
            f'<tagesordnungspunkt top-id="{top}">{body.replace("QUOTE", quote)}</tagesordnungspunkt>'
            "</sitzungsverlauf></dbtplenarprotokoll>", reviewed=[])["agenda_items"][0]

    REDE = ('<rede id="R"><p klasse="redner"><redner id="1"><name><vorname>A</vorname><nachname>B</nachname><fraktion>SPD</fraktion>'
            '</name></redner></p><p klasse="J_1">Ich zitiere:</p>QUOTE<kommentar>(Zuruf)</kommentar><p klasse="O">Zitat Ende.</p>'
            '<name>Präsident Dr. Norbert Lammert:</name><p klasse="J_1">Frau Kollegin.</p></rede>')

    # Value: protects=a quote the Redner reads out is stored; fails_when=<zitat> is skipped (41,335 words
    #   in 1,028 stored WP 18 Reden); why_new=was dropped; seam=none
    def test_a_quote_is_the_redners_and_its_own_paragraph(self) -> None:
        [speech] = self.parse(self.REDE)["speeches"]
        self.assertEqual(speech["text"], "Ich zitiere:\nDas Zitat.\nZitat Ende.")

    def test_both_spellings_of_a_quote_read_the_same(self) -> None:
        self.assertEqual(self.parse(self.REDE)["speeches"], self.parse(self.REDE, wrap=False)["speeches"])

    # Value: protects=a quote the chair reads out never becomes the Redner's; fails_when=the unwrapped quote ignores who
    #   speaks; why_new=26 of 1,814 follow the chair; seam=none
    def test_a_quote_the_chair_reads_out_is_not_the_redners(self) -> None:
        body = self.REDE.replace("QUOTE", "").replace("Frau Kollegin.</p>", "Frau Kollegin, es heißt:</p>QUOTE")
        [speech] = self.parse(body)["speeches"]
        self.assertEqual(speech["text"], "Ich zitiere: Zitat Ende.")

    # Value: protects=a quote in a Rede zu Protokoll (an annex) is stored; fails_when=quotes are unwrapped in the TOPs
    #   only; why_new=the other cases stand in a TOP; seam=none
    def test_a_quote_in_a_rede_zu_protokoll_is_kept(self) -> None:
        xml = (FIXTURES / "a1-written-18-100.xml").read_text(encoding="utf-8")
        annex = xml.index('anlagen-typ="Zu Protokoll')
        first = xml.index('<p klasse="J">', annex)
        quoted = xml[:first] + '<zitat><p klasse="Z">Ein Zitat im Anhang.</p></zitat>' + xml[first:]
        before, after = ([c["text"] for c in dip.parse_protocol_xml(x, reviewed=[])["sitting_contributions"]]
                         + [c["text"] for top in dip.parse_protocol_xml(x, reviewed=[])["agenda_items"] for c in top["contributions"]]
                         for x in (xml, quoted))
        changed = [(a, b) for a, b in zip(before, after) if a != b]
        self.assertEqual((len(before), len(changed)), (len(after), 1))
        self.assertIn("\nEin Zitat im Anhang.\n", changed[0][1])

    def test_a_second_quote_after_the_first_is_kept_in_order(self) -> None:
        root = ET.fromstring('<rede><p>Vor.</p><zitat><p klasse="Z">1</p></zitat><zitat><p klasse="Z">2</p><p klasse="Z">3</p></zitat>'
                             "<zitat><zitat><p>4</p></zitat></zitat><zitat/><p>Nach.</p></rede>")
        dip.unwrap_quotes(root)
        self.assertEqual([child.text for child in root], ["Vor.", "1", "2", "3", "4", "Nach."])

    # Value: protects=unwrapping stays linear in the quotes under one element; fails_when=each <zitat> is found,
    #   removed or inserted by position again (20 s here before); why_new=no test had more than a few; seam=none
    def test_many_quotes_under_one_element_unwrap_in_linear_time(self) -> None:
        root = ET.fromstring("<rede>" + "".join(f'<zitat><p klasse="Z">{n}</p></zitat>' for n in range(50_000)) + "</rede>")
        start = time.process_time()
        dip.unwrap_quotes(root)
        self.assertLess(time.process_time() - start, 3)
        self.assertEqual([child.text for child in root], [str(n) for n in range(50_000)])

    # Value: protects=unwrapping drops no words; fails_when=the text after an empty <zitat/> goes with it (first under its
    #   parent, after a paragraph, several in a row, around a full quote); why_new=only blank tails were tested; seam=none
    def test_the_text_after_an_empty_quote_stays_where_it_stood(self) -> None:
        root = ET.fromstring('<rede><zitat/>a<p>B</p><zitat/>c<zitat/>d<zitat><p>E</p></zitat>f<zitat/>g<p>H</p></rede>')
        dip.unwrap_quotes(root)
        self.assertEqual([child.tag for child in root], ["p", "p", "p"])
        self.assertEqual("".join(root.itertext()), "aBcdEfgH")

    # Value: protects=a quote never becomes a paragraph inside a paragraph, its words read as the outer one's;
    #   fails_when=a <zitat> under a <p> is unwrapped; why_new=new refusal, the XML has no such case to read it by; seam=none
    def test_a_quote_inside_a_paragraph_refuses_the_sitting(self) -> None:
        quote = '<zitat><p klasse="Z">1</p></zitat>'
        for body in (f"<p>Er sagte: {quote}</p>", f"<p>A<fussnote>{quote}</fussnote></p>", "<p>Er sagte: <zitat>1</zitat></p>"):
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, "21/1: a <zitat> inside a <p>"):
                dip.unwrap_quotes(ET.fromstring(f'<x wahlperiode="21" sitzung-nr="1"><rede>{body}</rede></x>'))

    # Value: protects=no quoted words are dropped unseen; fails_when=text directly in a <zitat> is lost; why_new=new
    #   rewrite of the tree; seam=none
    def test_text_outside_a_quotes_paragraphs_refuses_the_sitting(self) -> None:
        for quote in ("<zitat>Lose Worte</zitat>", '<zitat><p klasse="Z">1</p> lose </zitat>'):
            with self.subTest(quote=quote), self.assertRaisesRegex(ValueError, "outside a paragraph"):
                dip.unwrap_quotes(ET.fromstring(f"<rede>{quote}</rede>"))


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
