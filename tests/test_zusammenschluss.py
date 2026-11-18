"""One Zusammenschluss is one parties row (CONTEXT.md: Zusammenschluss, Gruppe),
one Redner is one Person even when the Bundestag XML merged two records into
one element (Personenkennung)."""

from __future__ import annotations

import contextlib
import io
import sqlite3
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import _support  # noqa: F401
import derive
import persist_dip_pulse_store as pulse_store
import render_dip_pulse_html as html
import validate_dip_protocol as dip


class ZusammenschlussSpellingTests(unittest.TestCase):
    def test_spellings_map_to_the_one_name_a_parties_row_carries(self) -> None:
        table = {
            "SPD": "SPD",
            "CDU/CSU": "CDU/CSU",
            "  SPD ": "SPD",
            "B90/GRÜNE": "BÜNDNIS 90/DIE GRÜNEN",
            "Grüne": "BÜNDNIS 90/DIE GRÜNEN",
            "DIE LINKE": "Die Linke",
            "LINKE": "Die Linke",
            # Spellings of the WP 18/19 XML (A3 pilot census): 19/100 and two more.
            "BÜNDNIS 90/DIE GRÜNE N": "BÜNDNIS 90/DIE GRÜNEN",
            "BÜNDNIS 90/ DIE GRÜNEN": "BÜNDNIS 90/DIE GRÜNEN",
            "Fraktionslos": "fraktionslos",
            "Fraktionslose": "fraktionslos",
            # A Gruppe is its own kind of Zusammenschluss, spelt one way.
            "Gruppe BSW": "Gruppe BSW",
            "BSW (Gruppe)": "Gruppe BSW",
            "BSW": "Gruppe BSW",
            "Gruppe Die Linke": "Gruppe Die Linke",
            "Die Linke (Gruppe)": "Gruppe Die Linke",
            # Anything else passes through.
            "Regierung": "Regierung",
            "Unbekannt": "Unbekannt",
        }
        for spelling, expected in table.items():
            with self.subTest(spelling):
                self.assertEqual(derive.zusammenschluss(spelling), expected)

    def test_a_name_written_twice_is_that_name(self) -> None:
        self.assertEqual(derive.zusammenschluss("SPDSPD"), "SPD")
        self.assertEqual(derive.zusammenschluss("AfDAfD"), "AfD")

    def test_two_different_names_run_together_name_nothing(self) -> None:
        self.assertIsNone(derive.zusammenschluss("SPDCDU/CSU"))
        self.assertIsNone(derive.zusammenschluss(""))
        self.assertIsNone(derive.zusammenschluss(None))

    def test_the_parse_time_helper_falls_back_to_unbekannt(self) -> None:
        self.assertEqual(dip.normalize_faction("SPDSPD"), "SPD")
        self.assertEqual(dip.normalize_faction("SPDCDU/CSU"), "Unbekannt")
        self.assertEqual(dip.normalize_faction(None), "Unbekannt")

    def test_the_wp_20_gruppe_die_linke_is_told_apart_by_the_sitzung(self) -> None:
        speaker = {"fraktion": "DIE LINKE"}

        def named(number: str, date: str | None) -> str | None:
            return derive.speech_zusammenschluss(speaker, {"dokumentnummer": number, "datum": date})

        self.assertEqual(named("20/90", "2023-12-01"), "Die Linke")  # the Fraktion's last sitting day in the store
        self.assertEqual(named("20/98", "2024-02-21"), "Gruppe Die Linke")
        self.assertEqual(named("20/210", "2025-03-18"), "Gruppe Die Linke")
        self.assertEqual(named("21/18", "2025-10-01"), "Die Linke")  # WP 21: a Fraktion again
        self.assertEqual(named("20/98", None), "Die Linke")  # no date, no claim
        self.assertEqual(derive.speech_zusammenschluss(speaker, None), "Die Linke")
        self.assertEqual(derive.speech_zusammenschluss({"fraktion": "SPD"}, {"dokumentnummer": "20/98", "datum": "2024-02-21"}), "SPD")


class RednerIdentityTests(unittest.TestCase):
    def test_a_merged_record_is_the_first_person(self) -> None:
        self.assertEqual(derive.first_redner_id("11005217 999990074"), "11005217")
        self.assertEqual(derive.first_redner_id("11005217"), "11005217")
        self.assertIsNone(derive.first_redner_id(""))
        self.assertIsNone(derive.first_redner_id(None))

    def test_only_a_word_made_of_two_identical_halves_is_halved(self) -> None:
        self.assertEqual(derive.undouble("SvenjaSvenja SchulzeSchulze"), "Svenja Schulze")
        self.assertEqual(derive.undouble("Dr. Anna Maria Lang"), "Dr. Anna Maria Lang")
        self.assertEqual(derive.undouble("Bora Bora"), "Bora Bora")
        self.assertIsNone(derive.undouble(""))


LABEL_XML = """
<p klasse="redner"><a id="r1"/><redner id="11005304"><name>
  <vorname>Dirk-UlrichAlexander</vorname><nachname>Mende Föhr</nachname><fraktion>SPDCDU/CSU</fraktion>
</name></redner>Alexander Föhr (CDU/CSU):</p>
"""


class MergedRecordParseTests(unittest.TestCase):
    def test_two_people_folded_into_one_element_take_name_and_fraktion_from_the_printed_label(self) -> None:
        # 20/91 ID209110200: the Bundestag XML folded Dirk-Ulrich Mende (SPD) into
        # the element of Alexander Föhr (CDU/CSU); the label after it is right.
        redner = ET.fromstring(LABEL_XML).find("redner")
        speaker = dip.parse_redner(redner)
        self.assertEqual(speaker["xml_redner_id"], "11005304")
        self.assertEqual(speaker["display_name"], "Alexander Föhr")
        self.assertEqual(speaker["fraktion"], "CDU/CSU")
        # No field of the garbled element is trusted, so no name is guessed from it.
        self.assertIsNone(speaker["first_name"])
        self.assertIsNone(speaker["last_name"])

    def test_an_ordinary_record_is_untouched(self) -> None:
        redner = ET.fromstring(
            '<p klasse="redner"><redner id="11004452"><name><vorname>Emmi</vorname>'
            "<nachname>Zeulner</nachname><fraktion>CDU/CSU</fraktion></name></redner>Emmi Zeulner (CDU/CSU):</p>"
        ).find("redner")
        speaker = dip.parse_redner(redner)
        self.assertEqual((speaker["display_name"], speaker["first_name"], speaker["fraktion"]), ("Emmi Zeulner", "Emmi", "CDU/CSU"))

    def test_a_merged_record_without_a_label_keeps_its_fields_for_persist_to_reject(self) -> None:
        redner = ET.fromstring(
            '<redner id="1"><name><vorname>AB</vorname><nachname>CD</nachname><fraktion>SPDCDU/CSU</fraktion></name></redner>'
        )
        self.assertEqual(dip.parse_redner(redner)["fraktion"], "SPDCDU/CSU")


#: The two speaker lines whose <fraktion> names no Fraktion, verbatim from the cached XML.
FREUDENSTEIN_XML = (  # 18/222 ID1822204600, docs/source-errors.md C6
    '<p klasse="redner"><redner id="11004277"><name><titel>Dr.</titel><vorname>Astrid</vorname>'
    "<nachname>Freudenstein</nachname><fraktion>CDU/CSU: Ich glaube, ich habe auch nicht gesagt – –</fraktion>"
    "</name></redner>Dr. Astrid Freudenstein (CDU/CSU): Ich glaube, ich habe auch nicht gesagt – –</p>"
)
SIELING_XML = (  # 19/60 ID196001500, docs/source-errors.md E7
    '<p klasse="redner"><redner id="10000"><name><titel>Dr.</titel><vorname>Carsten Sieling,</vorname>'
    "<nachname>Bürgermeister</nachname><fraktion>Bremen</fraktion></name></redner>"
    "Dr. Carsten Sieling, Bürgermeister (Bremen):</p>"
)


class PrintedFraktionTests(unittest.TestCase):
    """A <fraktion> value is one we know, or the sitting is refused (TODOS.md,
    "Stored Fraktion values that are not Fraktionen")."""

    def parsed(self, xml: str) -> dict:
        return dip.parse_redner(ET.fromstring(xml).find("redner"))

    # Value: protects=18/222's Erwiderung counts for CDU/CSU and no "CDU/CSU: Ich glaube, ..." group or parties row appears; fails_when=the parser copies <fraktion> as printed again; why_new=the store held the spoken text as a Fraktion on 1 Beitrag and 1 parties row; seam=none
    def test_spoken_text_after_the_name_is_the_name(self) -> None:
        speaker = self.parsed(FREUDENSTEIN_XML)
        self.assertEqual((speaker["display_name"], speaker["fraktion"]), ("Dr. Astrid Freudenstein", "CDU/CSU"))

    # Value: protects=19/60's Bundesrat Rede counts for the Bundesrat with no Fraktion, as the other 108 Bundesrat Reden do; fails_when=the Land name passes through as a Fraktion; why_new=the store held "Bremen" as a Fraktion on 1 Rede and 1 parties row; seam=none
    def test_a_land_beside_a_bundesrat_member_is_no_fraktion(self) -> None:
        speaker = self.parsed(SIELING_XML)
        self.assertEqual((speaker["fraktion"], speaker["role"]), (None, "Bürgermeister (Bremen)"))
        self.assertEqual(derive.sprechrolle(speaker), "bundesrat")

    # Value: protects=no stray string reaches a per-Fraktion count unseen: the sitting is refused instead; fails_when=the known-set check is dropped or widened to anything; why_new=nothing checked the value before; seam=none
    def test_any_other_unknown_value_is_refused(self) -> None:
        for fraktion, label in (
            ("Bremen", "Dr. Max Muster (Bremen):"),                       # a Land on an MdB, with no Bundesrat role
            ("Hessen", "Dr. Max Muster, Bürgermeister (Bremen):"),         # a Land the role does not name
            ("Piraten", "Dr. Max Muster (Piraten):"),
            ("SPD Ich glaube", "Dr. Max Muster (SPD):"),                   # spoken text without the colon
            ("Piraten: Ja", "Dr. Max Muster (Piraten):"),
        ):
            with self.subTest(fraktion):
                xml = (f'<p klasse="redner"><redner id="1"><name><vorname>Max</vorname><nachname>Muster</nachname>'
                       f"<fraktion>{fraktion}</fraktion></name></redner>{label}</p>")
                with self.assertRaisesRegex(derive.UnknownFraktionError, "unknown Fraktion"):
                    self.parsed(xml)
        # A garbled merged record's label is checked too.
        with self.assertRaises(derive.UnknownFraktionError):
            self.parsed('<p klasse="redner"><redner id="1"><name><vorname>AB</vorname><nachname>CD</nachname>'
                        "<fraktion>SPDCDU/CSU</fraktion></name></redner>Alexander Föhr (Piraten):</p>")

    # Value: protects=every known spelling, a merged record and a missing value still parse; fails_when=the check refuses a spelling the stored sittings print; why_new=the check is new; seam=none
    def test_known_values_pass_as_printed(self) -> None:
        # "CDU/ CSU" and "BÜNDNIS90/DIE GRÜNEN" are printed in the cached XML (Inhaltsverzeichnis, Rednerliste,
        # an 18/144 annex) where no unit is read yet; one reaching a Rede must not stop the build.
        for printed in ("SPD", "DIE LINKE", "BÜNDNIS 90/DIE GRÜNE N", "fraktionslos", "BSW (Gruppe)", "SPDSPD", "SPDCDU/CSU", "", "  CDU/CSU ",
                        "CDU/ CSU", "BÜNDNIS90/DIE GRÜNEN"):
            with self.subTest(printed):
                self.assertEqual(derive.printed_fraktion(printed, None), printed.strip() or None)
        self.assertEqual(derive.printed_fraktion("BÜNDNIS 90/DIE GRÜNEN", "Ministerin (Hessen)"), "BÜNDNIS 90/DIE GRÜNEN")

    # Value: protects=a whole sitting with an unknown value is refused with the Redner named; fails_when=the error is swallowed or names no place; why_new=the refusal is new; seam=validate_dip_protocol.parse_protocol_xml
    def test_the_sitting_is_refused_naming_the_redner(self) -> None:
        xml = ('<dbtplenarprotokoll wahlperiode="20" sitzung-nr="1"><sitzungsverlauf><tagesordnungspunkt top-id="TOP 1">'
               '<rede id="ID1"><p klasse="redner"><redner id="42"><name><vorname>Max</vorname><nachname>Muster</nachname>'
               "<fraktion>Piraten</fraktion></name></redner>Max Muster (Piraten):</p><p>Text.</p></rede>"
               "</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>")
        with self.assertRaisesRegex(ValueError, r"unknown Fraktion 'Piraten' at redner 42"):
            dip.parse_protocol_xml(xml)


def report(number: str, date: str, *speakers: dict) -> dict:
    return {
        "protocol": {"id": f"p-{number}", "dokumentnummer": number, "datum": date},
        "agenda_items": [
            {
                "index": 1,
                "top_id": "T1",
                "heading": "TOP 1",
                "xml_speakers": [
                    {
                        "rede_id": f"ID{index}",
                        "speaker": speaker,
                        "paragraph_count": 1,
                        "char_count": 5,
                        "text": "Hallo",
                        "snippet": "Hallo",
                    }
                    for index, speaker in enumerate(speakers, start=1)
                ],
            }
        ],
    }


SCHULZE = {
    "xml_redner_id": "11005217 999990074",
    "display_name": "SvenjaSvenja SchulzeSchulze",
    "first_name": "SvenjaSvenja",
    "last_name": "SchulzeSchulze",
    "fraktion": "SPDSPD",
}
FOEHR_CACHED = {
    "xml_redner_id": "fixture-unreviewed-merged-id",
    "display_name": "Dirk-UlrichAlexander Mende Föhr",
    "fraktion": "SPDCDU/CSU",
}


class PersistTests(unittest.TestCase):
    def persist(self, *reports: dict) -> tuple[sqlite3.Connection, str]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = pulse_store.connect(Path(tmp.name) / "store.sqlite")
        self.addCleanup(conn.close)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            for item in reports:
                pulse_store.persist_report(conn, item)
        return conn, err.getvalue()

    def test_a_doubled_record_is_one_person_and_one_fraktion(self) -> None:
        conn, err = self.persist(report("21/18", "2025-10-01", SCHULZE))
        row = conn.execute(
            "SELECT m.identity_key, m.xml_redner_id, m.display_name, s.fraktion, p.name AS party "
            "FROM speeches s JOIN mps m ON m.id = s.mp_id LEFT JOIN parties p ON p.id = m.party_id"
        ).fetchone()
        self.assertEqual(dict(row), {
            "identity_key": "xml:11005217", "xml_redner_id": "11005217", "display_name": "Svenja Schulze",
            "fraktion": "SPD", "party": "SPD",
        })
        self.assertEqual([r["name"] for r in conn.execute("SELECT name FROM parties")], ["SPD"])

    def test_the_merged_id_warning_names_the_protocol_and_the_rede(self) -> None:
        _, err = self.persist(report("21/18", "2025-10-01", SCHULZE))
        self.assertIn("warning: [redner-id] 21/18 Rede ID1:", err)
        self.assertIn('"11005217 999990074"', err)
        self.assertIn("using the first, 11005217", err)
        # A clean record says nothing.
        _, quiet = self.persist(report("21/19", "2025-10-02", {"xml_redner_id": "1", "display_name": "Ada", "fraktion": "SPD"}))
        self.assertEqual(quiet, "")

    def test_two_people_folded_into_one_element_name_no_zusammenschluss(self) -> None:
        conn, _ = self.persist(report("20/91", "2023-03-16", FOEHR_CACHED))
        self.assertIsNone(conn.execute("SELECT fraktion FROM speeches").fetchone()["fraktion"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM parties").fetchone()[0], 0)

    def test_a_wp_20_gruppe_rede_names_the_gruppe(self) -> None:
        linke = {"xml_redner_id": "7", "display_name": "Gregor Gysi", "fraktion": "DIE LINKE"}
        bsw = {"xml_redner_id": "8", "display_name": "Sahra Wagenknecht", "fraktion": "BSW"}
        conn, _ = self.persist(
            report("20/90", "2023-12-01", linke),
            report("20/98", "2024-02-21", linke, bsw),
            report("21/18", "2025-10-01", linke),
        )
        by_protocol = {
            (r["document_number"], r["display_name"]): r["fraktion"]
            for r in conn.execute(
                "SELECT pr.document_number, m.display_name, s.fraktion FROM speeches s "
                "JOIN protocols pr ON pr.id = s.protocol_id JOIN mps m ON m.id = s.mp_id"
            )
        }
        self.assertEqual(by_protocol, {
            ("20/90", "Gregor Gysi"): "Die Linke",
            ("20/98", "Gregor Gysi"): "Gruppe Die Linke",
            ("20/98", "Sahra Wagenknecht"): "Gruppe BSW",
            ("21/18", "Gregor Gysi"): "Die Linke",
        })

    def test_every_spelling_of_a_gruppe_in_vote_data_is_one_parties_row(self) -> None:
        item = report("20/98", "2024-02-21")
        item["agenda_items"][0]["xml_drucksachen"] = [{"dokumentnummer": "20/1"}]  # shared with the vote: vote_links places it here
        item["agenda_items"][0]["votes"] = [
            {
                "id": "v1",
                "document_numbers": ["20/1"],
                "total": {},
                "fractions": [
                    {"name": "Gruppe BSW", "counts": {"yes": 1}, "total": 1},
                    {"name": "BSW (Gruppe)", "counts": {"no": 2}, "total": 2},
                ],
                "members": [{"name": "A", "faction": "BSW (Gruppe)", "vote": "yes"}, {"name": "B", "faction": "Gruppe BSW", "vote": "no"}],
            }
        ]
        conn, _ = self.persist(item)
        self.assertEqual([r["name"] for r in conn.execute("SELECT name FROM parties")], ["Gruppe BSW"])
        # ... and one vote_fractions row: the counts add before the Mehrheitsvotum
        # is derived (1 Ja + 2 Nein is Nein, not two rows saying Ja and Nein).
        rows = conn.execute("SELECT yes_count, no_count, total_count, leading_vote FROM vote_fractions").fetchall()
        self.assertEqual([tuple(row) for row in rows], [(1, 2, 3, "no")])


class RenderTests(unittest.TestCase):
    def test_a_stale_cached_speaker_shows_the_same_zusammenschluss_as_the_store(self) -> None:
        self.assertEqual(html.speaker_party({"fraktion": "SPDSPD"}), "SPD")
        self.assertEqual(html.speaker_party({"fraktion": "BSW (Gruppe)"}), "Gruppe BSW")
        self.assertEqual(html.speaker_party({"fraktion": "Fraktionslos"}), "fraktionslos")
        # A merged record that names two: no Fraktion, so the role or Unbekannt.
        self.assertEqual(html.speaker_party({"fraktion": "SPDCDU/CSU"}), "Unbekannt")

    def test_the_sitzung_decides_between_fraktion_and_gruppe_die_linke(self) -> None:
        speaker = {"fraktion": "Die Linke"}
        self.assertEqual(html.speaker_party(speaker, {"dokumentnummer": "20/98", "datum": "2024-02-21"}), "Gruppe Die Linke")
        self.assertEqual(html.speaker_party(speaker, {"dokumentnummer": "21/18", "datum": "2025-10-01"}), "Die Linke")

    def test_item_stats_and_the_speaker_list_agree_on_the_gruppe(self) -> None:
        item = {
            "index": 1,
            "xml_speakers": [
                {"rede_id": "R1", "speaker": {"display_name": "SvenjaSvenja SchulzeSchulze", "fraktion": "SPDSPD"}, "char_count": 5},
                {"rede_id": "R2", "speaker": {"display_name": "Gregor Gysi", "fraktion": "DIE LINKE"}, "char_count": 5},
            ],
        }
        protocol = {"dokumentnummer": "20/98", "datum": "2024-02-21"}
        stats = html.item_stats(item, protocol)
        self.assertEqual(stats["parties"], ["SPD", "Gruppe Die Linke"])
        self.assertEqual(dict(stats["party_counts"]), {"SPD": 1, "Gruppe Die Linke": 1})
        markup = html.render_speakers(item, stats)
        self.assertIn("Svenja Schulze", markup)
        self.assertNotIn("SvenjaSvenja", markup)
        self.assertIn("Gruppe Die Linke", markup)
        self.assertNotIn("SPDSPD", markup)


if __name__ == "__main__":
    unittest.main()
