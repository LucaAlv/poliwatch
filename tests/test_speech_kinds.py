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


def synthetic_rede(rede_id: str, redner_id: str, name: str, *, fraktion: str = "", rolle: str = "", after: str = "") -> str:
    """One ``<rede>`` as the XML writes it: the marker with the speaker's name, a
    paragraph of speech, and, when given, the Sitzungsleitung's text after it."""
    vorname, _, nachname = name.rpartition(" ")
    tail = f'<name>Vizepräsident Test:</name><p klasse="J">{after}</p>' if after else ""
    return (
        f'<rede id="{rede_id}"><p klasse="redner"><redner id="{redner_id}"><name>'
        f"<vorname>{vorname}</vorname><nachname>{nachname}</nachname>"
        + (f"<fraktion>{fraktion}</fraktion>" if fraktion else "")
        + (f"<rolle><rolle_lang>{rolle}</rolle_lang></rolle>" if rolle else "")
        + f'</name></redner>{name}:</p><p klasse="J_1">Text von {nachname}.</p>{tail}</rede>'
    )


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

    # Value: protects=an Erwiderung is the Rede of the person the Kurzintervention answered, never one the Sitzungsleitung's "antworten" or "Erwiderung" wording suggests;
    #   fails_when=classify_reden reads the between-text wording again, so an unrelated Rede or a further Kurzintervention turns into an Erwiderung;
    #   why_new=the fixture test only has the real same-person Erwiderung; the removed wording rule turned 10+ real Reden of WP 20 into Erwiderungen; seam=none
    def test_the_erwiderung_is_the_same_persons_rede_and_no_wording_makes_another_one(self) -> None:
        haupt = synthetic_rede(
            "R1", "1001", "Anna Haupt", fraktion="SPD",
            after="Zu einer Kurzintervention erteile ich dem Kollegen Müller das Wort.",
        )
        antworten = "Möchten Sie antworten? – Nein. Das Wort erhält jetzt Frau Schulz."
        weitere = (
            "Möchten Sie eine Erwiderung geben? – Nein. "
            "Zu einer weiteren Kurzintervention erteile ich dem Kollegen Weber das Wort."
        )
        cases = {
            "a different person after 'Möchten Sie antworten? - Nein' stays a Rede": (
                [
                    synthetic_rede("R2", "1002", "Max Müller", fraktion="AfD", after=antworten),
                    synthetic_rede("R3", "1003", "Berta Schulz", fraktion="CDU/CSU"),
                ],
                [(None, None), (sk.KURZINTERVENTION, "R1"), (None, None)],
            ),
            "the same person right after is the Erwiderung, with the wording or without": (
                [
                    synthetic_rede("R2", "1002", "Max Müller", fraktion="AfD", after=antworten),
                    synthetic_rede("R3", "1001", "Anna Haupt", fraktion="SPD"),
                ],
                [(None, None), (sk.KURZINTERVENTION, "R1"), (sk.ERWIDERUNG, "R1")],
            ),
            "a second announced Kurzintervention that mentions the Erwiderung is no Erwiderung": (
                [
                    synthetic_rede("R2", "1002", "Max Müller", fraktion="AfD", after=weitere),
                    synthetic_rede("R3", "1004", "Kai Weber", fraktion="FDP"),
                ],
                [(None, None), (sk.KURZINTERVENTION, "R1"), (sk.KURZINTERVENTION, "R1")],
            ),
        }
        for name, (following, expected) in cases.items():
            with self.subTest(name):
                top = ET.fromstring(f"<tagesordnungspunkt>{haupt}{''.join(following)}</tagesordnungspunkt>")
                labels = sk.classify_reden(top, frozenset())
                self.assertEqual([(label.kind, label.parent_rede_id) for label in labels], expected)

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

    # Value: protects=a Kurzintervention asked for and granted with "Bitte schön" is stored as a Beitrag, and a remark that closes one does not turn the next Redner's Rede into one;
    #   fails_when=INVITES or CLOSED is dropped from announces_kurzintervention, or "Bitte schön" after a refusal grants one;
    #   why_new=the wording tests all use "Wort" or a name; 20/112 and the closing remark sit outside them; seam=none
    def test_an_invitation_grants_and_a_closing_remark_does_not(self) -> None:
        announces = sk.announces_kurzintervention
        self.assertTrue(announces("Sie möchten eine Kurzintervention machen? – Bitte schön."))
        self.assertFalse(announces("Sie möchten eine Kurzintervention machen? – Nein. – Bitte schön, Frau Meier."))
        self.assertFalse(announces("Keine Kurzintervention? – Bitte schön."))
        self.assertFalse(announces("Damit ist die Kurzintervention beendet. Das Wort hat als Nächste die Kollegin Meier.", "Meier"))
        self.assertFalse(announces("Die Kurzintervention ist damit abgeschlossen. Kollegin Meier, Sie haben das Wort."))

    def test_bitte_schoen_grants_only_to_a_rede_as_short_as_a_kurzintervention(self) -> None:
        announces = sk.announces_kurzintervention
        # "Bitte schön" after a remark about Kurzinterventionen invites the next ordinary Redner.
        self.assertFalse(announces("Kurzinterventionen lasse ich am Ende der Debatte zu. – Bitte schön.", "Meier", "SPD", 8000))
        self.assertFalse(announces("Sie möchten eine Kurzintervention machen? – Bitte schön.", "Meier", "SPD", 8000))
        self.assertTrue(announces("Sie möchten eine Kurzintervention machen? – Bitte schön.", "Meier", "SPD", 1500))
        # 20/119: a statement, not a question, answered by "Bitte schön".
        self.assertTrue(announces("Aber erst einmal kommt natürlich die Kurzintervention. – Bitte schön.", "Gürpinar", "DIE LINKE", 1726))

    def test_bitte_schoen_after_a_rule_remark_or_a_redner_announcement_grants_none(self) -> None:
        announces = sk.announces_kurzintervention
        # A short ordinary Rede invited after a remark about Kurzinterventionen in general.
        self.assertFalse(announces("Kurzinterventionen lasse ich am Ende der Debatte zu. – Bitte schön.", "Meier", "SPD", 1500))
        self.assertFalse(announces("Zwischenbemerkungen gibt es heute erst am Schluss. – Bitte schön.", "Meier", "SPD", 1500))
        # The next Redner was announced for a Rede before the remark.
        self.assertFalse(
            announces("Nächster Redner ist der Kollege Meier. Die Kurzintervention kommt später. – Bitte schön.", "Meier", "SPD", 1500)
        )
        # "Bitte schön, Herr Meier" addresses the Kurzintervention's own Redner.
        self.assertTrue(announces("Sie möchten eine Kurzintervention machen? – Bitte schön, Herr Meier.", "Meier", "SPD", 1500))
        # 20/119: the Redner is named in a sentence about the Kurzintervention itself.
        self.assertTrue(
            announces(
                "Jetzt kann sich Frau Klein-Schmeink überlegen, ob sie auf die jetzt folgende Kurzintervention von Herrn "
                "Gürpinar antworten möchte. Aber erst einmal kommt natürlich die Kurzintervention. – Bitte schön.",
                "Gürpinar", "DIE LINKE", 1726,
            )
        )

    def test_a_grant_after_a_closing_remark_in_the_same_sentence(self) -> None:
        announces = sk.announces_kurzintervention
        self.assertTrue(announces("Die Kurzintervention ist beendet; zu einer weiteren Kurzintervention erhält Frau Meier das Wort.", "Meier"))
        self.assertTrue(announces("Die Kurzintervention ist beendet, und zu einer weiteren Kurzintervention hat Herr Fiedler das Wort."))
        self.assertFalse(announces("Die Kurzintervention ist beendet; Frau Meier hat das Wort.", "Meier"))

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

    # Value: protects=a Befragung or Fragestunde whose only heading paragraph is T_ZP_NaS (20/143, 20/159) still gets its question format, Reden and Beitraege;
    #   fails_when=parse_protocol_xml stops reading T_ZP_NaS as the heading, so the item has no format and every Frage counts as a Rede;
    #   why_new=all fixtures head their Befragung with T_fett; the T_ZP_NaS-only shape is a separate parser branch measured on two real sittings; seam=none
    def test_a_heading_only_in_a_zusatzpunkt_paragraph_still_names_the_format(self) -> None:
        official = synthetic_rede("R1", "2001", "Karl Minister", rolle="Bundesminister")
        member = synthetic_rede("R2", "2002", "Lena Fragerin", fraktion="CDU/CSU")
        for heading, formats in (("Befragung der Bundesregierung", ["befragung"]), ("Fragestunde", ["fragestunde"])):
            with self.subTest(heading):
                parsed = dip.parse_protocol_xml(
                    '<dbtplenarprotokoll wahlperiode="20" sitzung-nr="143"><sitzungsverlauf>'
                    '<tagesordnungspunkt top-id="Tagesordnungspunkt 2">'
                    '<p klasse="J">Ich rufe den Zusatzpunkt auf:</p>'
                    f'<p klasse="T_ZP_NaS">{heading}</p>{official}{member}'
                    "</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>"
                )
                top = parsed["agenda_items"][0]
                self.assertEqual(top["heading"], heading)
                self.assertEqual(top["question_formats"], formats)
                if formats == ["befragung"]:
                    self.assertEqual([s["rede_id"] for s in top["speeches"]], ["R1"])
                    self.assertEqual(kinds(top), ["befragung_frage"])
                    self.assertEqual(top["contributions"][0]["rede_id"], "R2")
                else:
                    # Flat turns are read only in a Fragestunde: <rede>s stay Reden here.
                    self.assertEqual([s["rede_id"] for s in top["speeches"]], ["R1", "R2"])

    # Value: protects=a headingless continuation inherits its top-id's question format however the XML spaces the id (21/5 mixes no-break and plain spaces);
    #   fails_when=top_format stops normalising top_id whitespace, so the continuation loses its format and its Fragen count as Reden;
    #   why_new=the continuation fixture has identical top-id strings on both items; spacing variants and the seen lookup were untested; seam=none
    def test_a_continuation_finds_its_format_however_the_top_id_is_spaced(self) -> None:
        plain, nbsp = "Tagesordnungspunkt 4", "Tagesordnungspunkt\u00a04"
        for first, later in ((plain, plain), (plain, nbsp), (nbsp, plain)):
            with self.subTest(first=first, later=later):
                seen: dict[str, frozenset[str]] = {}
                opening = sk.top_format("Fragestunde", first, seen)
                self.assertEqual((opening.formats, opening.continuation), (frozenset({"fragestunde"}), False))
                continuation = sk.top_format("", later, seen)
                self.assertEqual((continuation.formats, continuation.continuation), (frozenset({"fragestunde"}), True))
        # The spec case, directly: a seen plain key.
        direct = sk.top_format("", "Tagesordnungspunkt 4", {"Tagesordnungspunkt 4": frozenset({"fragestunde"})})
        self.assertEqual((direct.formats, direct.continuation), (frozenset({"fragestunde"}), True))

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
        (question, antwort), unplaced = sk.fragestunde_turns(top)
        self.assertIsNone(question.redner)
        self.assertEqual(question.announced, "Jan Köstering")
        self.assertEqual(question.paragraphs, ["Welche Konzepte gibt es?"])
        self.assertEqual(antwort.kind, sk.FRAGESTUNDE_ANTWORT)

    # Value: protects=a silent asker becomes an id-less speaker with the announced name, is counted as person-less, and an unplaced marker opens no turn;
    #   fails_when=parse_protocol_xml drops the announced name, the person-less counter miscounts, or an unplaced speaker's paragraphs join the previous turn;
    #   why_new=test_a_question_whose_asker_never_speaks stops at fragestunde_turns and never reaches the parsed contribution or the summary key; seam=none
    def test_a_silent_asker_reaches_the_report_by_name_and_an_unplaced_marker_is_no_turn(self) -> None:
        parsed = dip.parse_protocol_xml(
            "<dbtplenarprotokoll><sitzungsverlauf>"
            '<tagesordnungspunkt top-id="T1"><p klasse="T_fett">Fragestunde</p>'
            "<name>Vizepräsident Omid Nouripour:</name>"
            '<p klasse="J">Wir kommen zur Frage 7 des Abgeordneten Jan Köstering von der Linken:</p>'
            '<p klasse="p">Welche Konzepte gibt es?</p>'
            '<p klasse="J">Frau Staatssekretärin, bitte.</p>'
            '<p klasse="redner"><redner id="11003613"><name><vorname>Daniela</vorname><nachname>Ludwig</nachname>'
            "<rolle><rolle_lang>Parl. Staatssekretärin</rolle_lang></rolle></name></redner>Daniela Ludwig:</p>"
            '<p klasse="J_1">Die Konzepte sind vielfältig.</p>'
            # Neither a Fraktion nor a rolle: no one the parser can place. The marker
            # ends the answer before it; what follows belongs to no one.
            '<p klasse="redner"><redner id="11009999"><name><vorname>Gast</vorname><nachname>Unbekannt</nachname>'
            "</name></redner>Gast Unbekannt:</p>"
            '<p klasse="J_1">Ein Gastbeitrag ohne Zuordnung.</p>'
            "</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>"
        )
        top = parsed["agenda_items"][0]
        question, antwort = top["contributions"]
        self.assertEqual((question["kind"], antwort["kind"]), ("fragestunde_frage", "fragestunde_antwort"))
        self.assertEqual(question["speaker"], {"xml_redner_id": None, "display_name": "Jan Köstering"})
        self.assertEqual(question["text"], "Welche Konzepte gibt es?")
        self.assertNotIn("Gastbeitrag", antwort["text"])
        summary = dip.contribution_summary(parsed["agenda_items"])
        self.assertEqual(summary["fragestunde_questions_without_person"], 1)
        # The Gastbeitrag is no Beitrag, but it is counted rather than silently gone.
        self.assertEqual(summary["fragestunde_unplaced_turns"], 1)
        self.assertEqual(summary["xml_contribution_counts"], {"fragestunde_antwort": 1, "fragestunde_frage": 1})

    # Value: protects=the question the Sitzungsleitung reads out is credited to the MdB the announcement names, never to another whose surname is merely contained in the asker's;
    #   fails_when=names_asker matches a substring of the asker's name again;
    #   why_new=the existing asker tests have one follower whose name is whole in the announcement; seam=none
    def test_the_asker_is_matched_by_whole_name(self) -> None:
        def top(follower: str) -> ET.Element:
            return ET.fromstring(
                "<tagesordnungspunkt>"
                '<p klasse="T_fett">Fragestunde</p>'
                "<name>Vizepräsident Omid Nouripour:</name>"
                '<p klasse="J">Wir kommen zur Frage 7 des Abgeordneten Hans Müller-Rossbach von der SPD:</p>'
                '<p klasse="p">Welche Konzepte gibt es?</p>'
                '<p klasse="J">Frau Staatssekretärin, bitte.</p>'
                '<p klasse="redner"><redner id="11003613"><name><vorname>Daniela</vorname><nachname>Ludwig</nachname>'
                "<rolle><rolle_lang>Parl. Staatssekretärin</rolle_lang></rolle></name></redner>Daniela Ludwig:</p>"
                '<p klasse="J_1">Die Konzepte sind vielfältig.</p>'
                f'<p klasse="redner">{follower}Nachfrage:</p>'
                '<p klasse="J_1">Und die Kosten?</p>'
                "</tagesordnungspunkt>"
            )

        def nachfrage(vorname: str, nachname: str) -> str:
            return (
                f'<redner id="11001111"><name><vorname>{vorname}</vorname><nachname>{nachname}</nachname>'
                "<fraktion>SPD</fraktion></name></redner>"
            )

        # "Müller" is only part of "Müller-Rossbach": the first Nachfrage is not the asker's.
        (question, _, _), _ = sk.fragestunde_turns(top(nachfrage("Hans", "Müller")))
        self.assertIsNone(question.redner)
        (question, _, _), _ = sk.fragestunde_turns(top(nachfrage("Hans", "Müller-Rossbach")))
        self.assertIsNotNone(question.redner)

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
