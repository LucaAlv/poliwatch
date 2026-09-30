"""What counts as a Rede (CONTEXT.md: Rede, Beitrag; ADR 0002). ``speeches`` holds
Reden only; Kurzinterventionen, Erwiderungen and the Fragen and Antworten of a
Befragung or Fragestunde are Beiträge. Fixtures are cut from real Plenarprotokoll
XML (long speech text trimmed, structure and wording kept):

- speech-kinds-kurzintervention.xml: 21/66 TOP 25, a Kurzintervention and its Erwiderung
- speech-kinds-no-announcement.xml: 20/188 TOP 18, "ob es eine Kurzintervention gibt"
- speech-kinds-befragung-fragestunde.xml: 21/6 TOP 1 (two opening reports) and TOP 2
- speech-kinds-continuation.xml: 20/209 Befragung, a Geschäftsordnung TOP, and the
  continuation with the same top-id and no heading
"""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

import _support  # noqa: F401
import speech_kinds as sk
import validate_dip_protocol as dip
from _support import FIXTURES


def parse(name: str) -> dict:
    return dip.parse_protocol_xml((FIXTURES / f"speech-kinds-{name}.xml").read_text(encoding="utf-8"))


def kinds(top: dict) -> list[str]:
    return [contribution["kind"] for contribution in top["contributions"]]


class KurzinterventionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.top = parse("kurzintervention")["agenda_items"][0]

    def test_kurzintervention_and_erwiderung_are_beitraege_not_reden(self) -> None:
        self.assertEqual(kinds(self.top), ["kurzintervention", "erwiderung"])
        names = [c["speaker"]["display_name"] for c in self.top["contributions"]]
        self.assertEqual(names, ["Lorenz Gösta Beutin", "Dr. Thomas Gebhart"])
        speech_ids = {s["rede_id"] for s in self.top["speeches"]}
        self.assertFalse(speech_ids & {c["rede_id"] for c in self.top["contributions"]})

    def test_both_belong_to_the_rede_the_kurzintervention_answers(self) -> None:
        ki, erwiderung = self.top["contributions"]
        self.assertEqual(ki["parent_rede_id"], "ID216604600")
        self.assertEqual(erwiderung["parent_rede_id"], "ID216604600")
        self.assertEqual(ki["rede_id"], "ID216604700")

    def test_the_rede_after_an_erwiderung_is_a_rede_again(self) -> None:
        ids = [s["rede_id"] for s in self.top["speeches"]]
        self.assertIn("ID216604600", ids)
        self.assertNotIn("ID216604700", ids)
        self.assertNotIn("ID216604800", ids)
        self.assertEqual(len(ids), 4)

    def test_a_remark_about_kurzinterventionen_announces_none(self) -> None:
        # 20/188 TOP 18: "Wenn jemand persönlich angesprochen wird, kann man überlegen,
        # ob es eine Kurzintervention gibt." The next Rede is an ordinary Rede.
        top = parse("no-announcement")["agenda_items"][0]
        self.assertEqual(top["contributions"], [])
        self.assertEqual(len(top["speeches"]), 2)

    def test_announcement_wording(self) -> None:
        announces = sk.announces_kurzintervention
        self.assertTrue(announces("Zu einer Kurzintervention darf ich Martin Sichert das Wort erteilen."))
        self.assertTrue(announces("Ich deute jetzt die Zwischenfrage als Kurzintervention und darf der Abgeordneten Piechotta das Wort erteilen."))
        self.assertTrue(announces("Für eine Kurzintervention erhält das Wort Karsten Hilse aus der AfD-Fraktion."))
        # No Wort, but the sentence names the next Redner.
        self.assertTrue(announces("Der Kollege Fricke zu einer Kurzintervention.", "Fricke"))
        self.assertFalse(announces("Der Kollege Fricke zu einer Kurzintervention."))
        # Talk about Kurzinterventionen that grants no Wort in the same sentence.
        self.assertFalse(announces("Kurzinterventionen gibt es bei einer Aktuellen Stunde nicht. – Das Wort hat der Kollege Hakan Demir."))
        self.assertFalse(announces("Wenn es jemanden gibt, der persönlich angesprochen wird, dann kann er sich zu einer Kurzintervention melden. Lieber Dr. Klaus Wiener, Sie haben das Wort."))

    def test_announcement_that_names_the_redner_a_sentence_later(self) -> None:
        announces = sk.announces_kurzintervention
        # "Dr." is no sentence end.
        self.assertTrue(announces("Jetzt kommen wir zur Kurzintervention von Herrn Dr. Gesenhues.", "Gesenhues"))
        self.assertTrue(announces("Die AfD-Fraktion hat eine Kurzintervention beantragt, die ich zulasse. Der Kollege Stöber hat das Wort.", "Stöber"))
        self.assertTrue(announces("Ich habe zwei Bitten um Kurzintervention. Beide lasse ich zu. Zunächst Herr Schäffler.", "Schäffler"))
        # Two sentences after the announcement is too far.
        self.assertFalse(announces("Das ist eine Kurzintervention. Es gilt für alle. Für alle Fraktionen. Das ist so. Herr Seif, bitte.", "Seif"))

    def test_announcement_that_names_the_fraktion_of_a_short_rede(self) -> None:
        announces = sk.announces_kurzintervention
        text = "Es gibt jetzt die Möglichkeit einer Kurzintervention für die AfD-Fraktion. – Sie ist aber zuzulassen."
        self.assertTrue(announces(text, "Bernhard", "AfD", 2119))
        self.assertFalse(announces(text, "Bernhard", "AfD", 8000))  # too long for a Kurzintervention
        self.assertFalse(announces(text, "Bernhard", "SPD", 2119))

    def test_rules_refusals_and_withdrawals_announce_none(self) -> None:
        announces = sk.announces_kurzintervention
        self.assertFalse(announces("Ab jetzt lasse ich keine Kurzinterventionen mehr zu. Das Wort hat Frau Wittmann.", "Wittmann"))
        self.assertFalse(announces("Wir lassen nicht zu, dass eine Kurzintervention folgt. Frau Wittmann hat das Wort.", "Wittmann"))
        self.assertFalse(announces("Wenn ich eine Kurzintervention zulasse, dann bitte mit Antwort. Herr Fiedler hat das Wort.", "Fiedler"))
        self.assertFalse(announces("Für eine Kurzintervention erhält das Wort der Kollege Kubicki. – Nein, er zieht zurück. – Weiter mit Dr. Bartsch."))


class BefragungTests(unittest.TestCase):
    def setUp(self) -> None:
        self.befragung, self.fragestunde = parse("befragung-fragestunde")["agenda_items"]

    def test_the_opening_reports_stay_reden(self) -> None:
        # 21/6 opens with two reports: Dobrindt, then Hubertz.
        names = [s["speaker"]["display_name"] for s in self.befragung["speeches"]]
        self.assertEqual(names, ["Alexander Dobrindt", "Verena Hubertz"])
        self.assertEqual(self.befragung["question_formats"], ["befragung"])

    def test_every_later_rede_is_a_frage_or_an_antwort(self) -> None:
        self.assertEqual(
            kinds(self.befragung)[:4],
            ["befragung_frage", "befragung_antwort", "befragung_frage", "befragung_antwort"],
        )
        first = self.befragung["contributions"][0]
        self.assertEqual(first["speaker"]["display_name"], "Dr. Gottfried Curio")
        self.assertEqual(first["speaker"]["fraktion"], "AfD")
        self.assertEqual(self.befragung["contributions"][1]["speaker"]["display_name"], "Alexander Dobrindt")
        self.assertTrue(self.befragung["contributions"][1]["rede_id"])

    def test_a_continuation_with_the_same_top_id_and_no_heading_inherits_the_format(self) -> None:
        first, geschaeftsordnung, continuation = parse("continuation")["agenda_items"]
        self.assertEqual(continuation["heading"], "")
        self.assertEqual(continuation["question_formats"], ["befragung"])
        # It has no opening reports of its own: its first Rede is a Frage.
        self.assertEqual(continuation["speeches"], [])
        self.assertEqual(kinds(continuation)[0], "befragung_frage")
        # An interposed TOP of another kind is no question format.
        self.assertEqual(geschaeftsordnung["question_formats"], [])
        self.assertEqual(geschaeftsordnung["contributions"], [])
        self.assertEqual(len(geschaeftsordnung["speeches"]), 3)

    def test_formats_of_a_heading(self) -> None:
        self.assertEqual(sk.heading_formats("  Befragung  der Bundesregierung (einleitend BMJ)"), {"befragung"})
        self.assertEqual(sk.heading_formats("Regierungsbefragung"), {"befragung"})
        self.assertEqual(sk.heading_formats("Fragestunde"), {"fragestunde"})
        # 20/136 merges both into one heading.
        self.assertEqual(
            sk.heading_formats("Befragung der Bundesregierung Fragestunde"), {"befragung", "fragestunde"}
        )
        self.assertEqual(sk.heading_formats("Beratung des Antrags: Befragung der Bundesregierung reformieren"), frozenset())
        self.assertEqual(sk.heading_formats(None), frozenset())


class FragestundeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.top = parse("befragung-fragestunde")["agenda_items"][1]

    def test_the_fragestunde_has_no_reden_only_beitraege(self) -> None:
        self.assertEqual(self.top["question_formats"], ["fragestunde"])
        self.assertEqual(self.top["speeches"], [])
        self.assertTrue(self.top["contributions"])
        for contribution in self.top["contributions"]:
            self.assertIn(contribution["kind"], {"fragestunde_frage", "fragestunde_antwort"})
            self.assertIsNone(contribution["rede_id"])
            self.assertIsNone(contribution["source_page"])
            self.assertEqual(contribution["char_count"], len(contribution["text"]))
            self.assertGreater(contribution["char_count"], 0)

    def test_the_question_the_praesident_reads_out_goes_to_the_asker(self) -> None:
        # Frage 1: "Hat die Bundesregierung in Gestalt des Bundesministeriums des Innern ..."
        # read out by the Vizepräsident; Dr. Rainer Kraft asks the first Nachfrage.
        question, antwort = self.top["contributions"][:2]
        self.assertEqual((question["kind"], antwort["kind"]), ("fragestunde_frage", "fragestunde_antwort"))
        self.assertTrue(question["text"].startswith("Hat die Bundesregierung in Gestalt"))
        self.assertEqual(question["speaker"]["display_name"], "Dr. Rainer Kraft")
        self.assertEqual(question["speaker"]["xml_redner_id"], "11004792")
        self.assertEqual(antwort["speaker"]["display_name"], "Daniela Ludwig")
        self.assertIn("Parl. Staatssekretärin", antwort["speaker"]["role"])
        self.assertNotIn("Herr Präsident", question["text"])

    def test_a_nachfrage_is_a_frage_and_the_sitzungsleitung_is_no_one(self) -> None:
        texts = [c["text"] for c in self.top["contributions"]]
        self.assertFalse(any("Jetzt bitte Ihre erste Nachfrage" in text for text in texts))
        nachfrage = self.top["contributions"][2]
        self.assertEqual(nachfrage["kind"], "fragestunde_frage")
        self.assertTrue(nachfrage["text"].startswith("Vielen Dank. – Frau Staatssekretärin"))

    def test_a_question_whose_asker_never_speaks_keeps_the_announced_name(self) -> None:
        top = ET.fromstring(
            "<tagesordnungspunkt>"
            '<p klasse="T_fett">Fragestunde</p>'
            '<name>Vizepräsident Omid Nouripour:</name>'
            '<p klasse="J">Wir kommen zur Frage 7 des Abgeordneten Jan Köstering von der Linken:</p>'
            '<p klasse="p">Welche Konzepte gibt es?</p>'
            '<p klasse="J">Frau Staatssekretärin, bitte.</p>'
            '<p klasse="redner"><redner id="11003613"><name><vorname>Daniela</vorname><nachname>Ludwig</nachname>'
            "<rolle><rolle_lang>Parl. Staatssekretärin</rolle_lang></rolle></name></redner>Daniela Ludwig:</p>"
            '<p klasse="J_1">Die Konzepte sind vielfältig.</p>'
            "</tagesordnungspunkt>"
        )
        question, antwort = sk.fragestunde_turns(top)
        self.assertIsNone(question.redner)
        self.assertEqual(question.announced, "Jan Köstering")
        self.assertEqual(question.paragraphs, ["Welche Konzepte gibt es?"])
        self.assertEqual(antwort.kind, sk.FRAGESTUNDE_ANTWORT)

    def test_announced_asker(self) -> None:
        cases = {
            "Wir kommen zur Frage 2 des Abgeordneten Bernd Schattner von der AfD-Fraktion:": "Bernd Schattner",
            "Ich rufe die Frage 13 der Abgeordneten Serap Güler auf:": "Serap Güler",
            "Wir kommen zur Frage 5, ebenfalls vom Kollegen Brandner:": "Brandner",
            "Wenn Sie erlauben, schreite ich jetzt voran und komme zur Frage 4 von Stephan Brandner:": "Stephan Brandner",
            "Die Frage 6 stellt die Kollegin Bünger von der Fraktion Die Linke:": "Bünger",
            "Wir kommen zur Frage 15 der Abgeordneten Frau Dr. Lena Gumnior für Bündnis 90/Die Grünen:": "Frau Dr. Lena Gumnior",
        }
        for text, name in cases.items():
            with self.subTest(text=text):
                self.assertEqual(sk.announced_asker(text), name)
        self.assertIsNone(sk.announced_asker("Damit ist die Fragestunde beendet."))


class ReportShapeTests(unittest.TestCase):
    def test_reden_and_beitraege_reach_the_report_keys(self) -> None:
        tops = parse("befragung-fragestunde")["agenda_items"]
        fields = dip.xml_top_fields(tops[0])
        self.assertEqual(fields["xml_speech_count"], 2)
        self.assertEqual(len(fields["xml_speakers"]), 2)
        self.assertEqual(len(fields["xml_contributions"]), len(tops[0]["contributions"]))
        self.assertEqual(fields["question_formats"], ["befragung"])
        summary = dip.contribution_summary(tops)
        self.assertEqual(summary["xml_speech_count"], 2)
        counts = summary["xml_contribution_counts"]
        self.assertGreater(counts["befragung_frage"], 0)
        self.assertGreater(counts["fragestunde_antwort"], 0)
        self.assertEqual(sum(counts.values()), sum(len(t["contributions"]) for t in tops))

    def test_a_befragung_top_keeps_the_pages_of_its_contributions(self) -> None:
        # A Befragung's Fragen and Antworten are no Reden but still anchor the TOP's
        # page range: DIP matching (activity_in_top) reads it.
        parsed = dip.parse_protocol_xml(
            "<dbtplenarprotokoll><vorspann><inhaltsverzeichnis><ivz-block>"
            "<ivz-block-titel>TOP 1 Befragung der Bundesregierung</ivz-block-titel>"
            '<xref rid="R1" pnr="10" div="A">10</xref><xref rid="R2" pnr="12" div="B">12</xref>'
            "</ivz-block></inhaltsverzeichnis></vorspann><sitzungsverlauf>"
            '<tagesordnungspunkt top-id="T1"><p klasse="T_fett">Befragung der Bundesregierung</p>'
            '<rede id="R1"><p klasse="redner"><redner id="1"><name><vorname>A</vorname><nachname>Minister</nachname>'
            "<rolle><rolle_lang>Bundesminister</rolle_lang></rolle></name></redner></p><p>Bericht.</p></rede>"
            '<rede id="R2"><p klasse="redner"><redner id="2"><name><vorname>B</vorname><nachname>Frager</nachname>'
            "<fraktion>SPD</fraktion></name></redner></p><p>Frage?</p></rede>"
            "</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>"
        )
        top = parsed["agenda_items"][0]
        self.assertEqual([s["rede_id"] for s in top["speeches"]], ["R1"])
        self.assertEqual([c["rede_id"] for c in top["contributions"]], ["R2"])
        self.assertEqual(top["page_range"]["start"], {"page": 10, "quadrant": "A"})
        self.assertEqual(top["page_range"]["end"], {"page": 12, "quadrant": "B"})

    def test_kind_counts_and_the_dip_check(self) -> None:
        counts = sk.kind_counts(
            [{"kind": "kurzintervention"}, {"kind": "kurzintervention"}, {"kind": "erwiderung"}, {"kind": "befragung_frage"}]
        )
        self.assertEqual(counts, {"befragung_frage": 1, "erwiderung": 1, "kurzintervention": 2})
        activities = [
            {"aktivitaetsart": "Kurzintervention"},
            {"aktivitaetsart": "Kurzintervention"},
            {"aktivitaetsart": "Erwiderung"},
            {"aktivitaetsart": "Frage"},  # DIP's Frage is not comparable: never checked
            {"aktivitaetsart": "Rede"},
        ]
        self.assertEqual(sk.dip_mismatches(counts, activities), [])
        self.assertEqual(
            sk.dip_mismatches(counts, activities[:2]),
            [{"kind": "erwiderung", "xml": 1, "dip": 0}],
        )


if __name__ == "__main__":
    unittest.main()
