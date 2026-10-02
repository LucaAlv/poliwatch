"""Sprechrolle (CONTEXT.md, ADR 0001 amendment 2026-09-26): a Rede in a role counts
for one of three sides and for no Zusammenschluss; a role no rule maps fails the
build with one error naming all of them."""

from __future__ import annotations

import contextlib
import hashlib
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401
import build_dip_pulse_site as build
import derive
import facts
import persist_dip_pulse_store as pulse_store
import render_dip_pulse_html as html

#: Every distinct <rolle_lang> in the 302 cached reports of the store (2026-09-29),
#: and the side it counts for: the Bundesregierung side has 95 of them (5.394
#: Reden: Bundeskanzler, Bundesminister, Parlamentarische Staatssekretäre,
#: Staatsminister beim Bund, Beauftragte and Koordinatoren der Bundesregierung),
#: the Bundesrat 25 (61 Reden: every role that names a Land), weitere 3 (8 Reden:
#: Wehrbeauftragte, Polizeibeauftragter).
ROLES_IN_THE_CACHED_REPORTS = {
    'Beauftragte der Bundesregierung für Aussiedlerfragen und nationale Minderheiten': 'bundesregierung',
    'Beauftragte der Bundesregierung für Menschenrechtspolitik und humanitäre Hilfe': 'bundesregierung',
    'Beauftragte der Bundesregierung für Ostdeutschland': 'bundesregierung',
    'Beauftragte des Bundesministeriums für Wirtschaft und Klimaschutz für die Digitale Wirtschaft und Start-ups': 'bundesregierung',
    'Beauftragter der Bundesregierung für Menschenrechtspolitik und humanitäre Hilfe': 'bundesregierung',
    'Beauftragter der Bundesregierung für Ostdeutschland': 'bundesregierung',
    'Beauftragter der Bundesregierung für Sucht- und Drogenfragen': 'bundesregierung',
    'Beauftragter der Bundesregierung für die Akzeptanz sexueller und geschlechtlicher Vielfalt': 'bundesregierung',
    'Beauftragter der Bundesregierung für die Anliegen von Betroffenen von terroristischen und extremistischen Anschlägen im Inland': 'bundesregierung',
    'Beauftragter der Bundesregierung gegen Antiziganismus und für das Leben der Sinti und Roma in Deutschland': 'bundesregierung',
    'Bundeskanzler': 'bundesregierung',
    'Bundesminister der Finanzen': 'bundesregierung',
    'Bundesminister der Justiz': 'bundesregierung',
    'Bundesminister der Verteidigung': 'bundesregierung',
    'Bundesminister des Auswärtigen': 'bundesregierung',
    'Bundesminister des Innern': 'bundesregierung',
    'Bundesminister für Arbeit und Soziales': 'bundesregierung',
    'Bundesminister für Digitales und Staatsmodernisierung': 'bundesregierung',
    'Bundesminister für Digitales und Verkehr': 'bundesregierung',
    'Bundesminister für Digitales und Verkehr sowie der Justiz': 'bundesregierung',
    'Bundesminister für Ernährung und Landwirtschaft': 'bundesregierung',
    'Bundesminister für Ernährung und Landwirtschaft sowie für Bildung und Forschung': 'bundesregierung',
    'Bundesminister für Gesundheit': 'bundesregierung',
    'Bundesminister für Landwirtschaft, Ernährung und Heimat': 'bundesregierung',
    'Bundesminister für Umwelt, Klimaschutz, Naturschutz und nukleare Sicherheit': 'bundesregierung',
    'Bundesminister für Verkehr': 'bundesregierung',
    'Bundesminister für Wirtschaft und Klimaschutz': 'bundesregierung',
    'Bundesminister für besondere Aufgaben': 'bundesregierung',
    'Bundesministerin der Justiz und für Verbraucherschutz': 'bundesregierung',
    'Bundesministerin der Verteidigung': 'bundesregierung',
    'Bundesministerin des Auswärtigen': 'bundesregierung',
    'Bundesministerin des Innern und für Heimat': 'bundesregierung',
    'Bundesministerin für Arbeit und Soziales': 'bundesregierung',
    'Bundesministerin für Bildung und Forschung': 'bundesregierung',
    'Bundesministerin für Bildung, Familie, Senioren, Frauen und Jugend': 'bundesregierung',
    'Bundesministerin für Familie, Senioren, Frauen und Jugend': 'bundesregierung',
    'Bundesministerin für Forschung, Technologie und Raumfahrt': 'bundesregierung',
    'Bundesministerin für Gesundheit': 'bundesregierung',
    'Bundesministerin für Umwelt, Naturschutz, nukleare Sicherheit und Verbraucherschutz': 'bundesregierung',
    'Bundesministerin für Wirtschaft und Energie': 'bundesregierung',
    'Bundesministerin für Wohnen, Stadtentwicklung und Bauwesen': 'bundesregierung',
    'Bundesministerin für besondere Aufgaben': 'bundesregierung',
    'Bundesministerin für wirtschaftliche Zusammenarbeit und Entwicklung': 'bundesregierung',
    'Bürgermeister (Bremen)': 'bundesrat',
    'Koordinator der Bundesregierung für Maritime Wirtschaft und Tourismus': 'bundesregierung',
    'Koordinator der Bundesregierung für die Maritime Wirtschaft und Tourismus': 'bundesregierung',
    'Koordinatorin der Bundesregierung für die Deutsche Luft- und Raumfahrt': 'bundesregierung',
    'Minister (Baden-Württemberg)': 'bundesrat',
    'Minister (Brandenburg)': 'bundesrat',
    'Minister (Mecklenburg-Vorpommern)': 'bundesrat',
    'Minister (Nordrhein-Westfalen)': 'bundesrat',
    'Minister (Sachsen-Anhalt)': 'bundesrat',
    'Ministerin (Baden-Württemberg)': 'bundesrat',
    'Ministerin (Niedersachsen)': 'bundesrat',
    'Ministerpräsident (Bayern)': 'bundesrat',
    'Ministerpräsident (Brandenburg)': 'bundesrat',
    'Ministerpräsident (Hessen)': 'bundesrat',
    'Ministerpräsident (Niedersachsen)': 'bundesrat',
    'Ministerpräsident (Rheinland-Pfalz)': 'bundesrat',
    'Ministerpräsident (Sachsen-Anhalt)': 'bundesrat',
    'Ministerpräsident (Thüringen)': 'bundesrat',
    'Ministerpräsidentin (Mecklenburg-Vorpommern)': 'bundesrat',
    'Ministerpräsidentin (Saarland)': 'bundesrat',
    'Parl. Staatssekretär bei der Bundesministerin der Justiz und für Verbraucherschutz': 'bundesregierung',
    'Parl. Staatssekretär bei der Bundesministerin der Verteidigung': 'bundesregierung',
    'Parl. Staatssekretär bei der Bundesministerin des Innern und für Heimat': 'bundesregierung',
    'Parl. Staatssekretär bei der Bundesministerin für Bildung und Forschung': 'bundesregierung',
    'Parl. Staatssekretär bei der Bundesministerin für Bildung, Familie, Senioren, Frauen und Jugend': 'bundesregierung',
    'Parl. Staatssekretär bei der Bundesministerin für Familie, Senioren, Frauen und Jugend': 'bundesregierung',
    'Parl. Staatssekretär bei der Bundesministerin für Gesundheit': 'bundesregierung',
    'Parl. Staatssekretär bei der Bundesministerin für Umwelt, Naturschutz, nukleare Sicherheit und Verbraucherschutz': 'bundesregierung',
    'Parl. Staatssekretär bei der Bundesministerin für Wirtschaft und Energie': 'bundesregierung',
    'Parl. Staatssekretär bei der Bundesministerin für Wohnen, Stadtentwicklung und Bauwesen': 'bundesregierung',
    'Parl. Staatssekretär bei der Bundesministerin für wirtschaftliche Zusammenarbeit und Entwicklung': 'bundesregierung',
    'Parl. Staatssekretär beim Bundesminister der Finanzen': 'bundesregierung',
    'Parl. Staatssekretär beim Bundesminister der Justiz': 'bundesregierung',
    'Parl. Staatssekretär beim Bundesminister der Verteidigung': 'bundesregierung',
    'Parl. Staatssekretär beim Bundesminister des Innern': 'bundesregierung',
    'Parl. Staatssekretär beim Bundesminister für Digitales und Staatsmodernisierung': 'bundesregierung',
    'Parl. Staatssekretär beim Bundesminister für Digitales und Verkehr': 'bundesregierung',
    'Parl. Staatssekretär beim Bundesminister für Gesundheit': 'bundesregierung',
    'Parl. Staatssekretär beim Bundesminister für Umwelt, Klimaschutz, Naturschutz und nukleare Sicherheit': 'bundesregierung',
    'Parl. Staatssekretär beim Bundesminister für Verkehr': 'bundesregierung',
    'Parl. Staatssekretär beim Bundesminister für Wirtschaft und Klimaschutz': 'bundesregierung',
    'Parl. Staatssekretärin bei der Bundesministerin der Justiz und für Verbraucherschutz': 'bundesregierung',
    'Parl. Staatssekretärin bei der Bundesministerin der Verteidigung': 'bundesregierung',
    'Parl. Staatssekretärin bei der Bundesministerin des Innern und für Heimat': 'bundesregierung',
    'Parl. Staatssekretärin bei der Bundesministerin für Arbeit und Soziales': 'bundesregierung',
    'Parl. Staatssekretärin bei der Bundesministerin für Familie, Senioren, Frauen und Jugend': 'bundesregierung',
    'Parl. Staatssekretärin bei der Bundesministerin für Forschung, Technologie und Raumfahrt': 'bundesregierung',
    'Parl. Staatssekretärin bei der Bundesministerin für Umwelt, Naturschutz, nukleare Sicherheit und Verbraucherschutz': 'bundesregierung',
    'Parl. Staatssekretärin bei der Bundesministerin für Wirtschaft und Energie': 'bundesregierung',
    'Parl. Staatssekretärin bei der Bundesministerin für Wohnen, Stadtentwicklung und Bauwesen': 'bundesregierung',
    'Parl. Staatssekretärin bei der Bundesministerin für wirtschaftliche Zusammenarbeit und Entwicklung': 'bundesregierung',
    'Parl. Staatssekretärin beim Bundesminister der Finanzen': 'bundesregierung',
    'Parl. Staatssekretärin beim Bundesminister der Verteidigung': 'bundesregierung',
    'Parl. Staatssekretärin beim Bundesminister des Innern': 'bundesregierung',
    'Parl. Staatssekretärin beim Bundesminister für Arbeit und Soziales': 'bundesregierung',
    'Parl. Staatssekretärin beim Bundesminister für Digitales und Verkehr': 'bundesregierung',
    'Parl. Staatssekretärin beim Bundesminister für Ernährung und Landwirtschaft': 'bundesregierung',
    'Parl. Staatssekretärin beim Bundesminister für Gesundheit': 'bundesregierung',
    'Parl. Staatssekretärin beim Bundesminister für Landwirtschaft, Ernährung und Heimat': 'bundesregierung',
    'Parl. Staatssekretärin beim Bundesminister für Umwelt, Klimaschutz, Naturschutz und nukleare Sicherheit': 'bundesregierung',
    'Parl. Staatssekretärin beim Bundesminister für Wirtschaft und Klimaschutz': 'bundesregierung',
    'Polizeibeauftragter des Bundes beim Deutschen Bundestag': 'weitere',
    'Senatorin (Berlin)': 'bundesrat',
    'Staatsminister (Bayern)': 'bundesrat',
    'Staatsminister (Hessen)': 'bundesrat',
    'Staatsminister (Sachsen)': 'bundesrat',
    'Staatsminister beim Bundeskanzler': 'bundesregierung',
    'Staatsminister beim Bundesminister des Auswärtigen': 'bundesregierung',
    'Staatsminister im Auswärtigen Amt': 'bundesregierung',
    'Staatsministerin (Bayern)': 'bundesrat',
    'Staatsministerin (Hessen)': 'bundesrat',
    'Staatsministerin (Rheinland-Pfalz)': 'bundesrat',
    'Staatsministerin (Sachsen)': 'bundesrat',
    'Staatsministerin bei der Bundesministerin für Arbeit und Soziales': 'bundesregierung',
    'Staatsministerin beim Bundeskanzler': 'bundesregierung',
    'Staatsministerin beim Bundesminister der Finanzen': 'bundesregierung',
    'Staatsministerin beim Bundesminister des Auswärtigen': 'bundesregierung',
    'Staatsministerin im Auswärtigen Amt': 'bundesregierung',
    'Wehrbeauftragte des Deutschen Bundestages': 'weitere',
    'Wehrbeauftragter des Deutschen Bundestages': 'weitere',
}


class RoleTableTests(unittest.TestCase):
    def test_every_role_in_the_cached_reports_is_mapped(self) -> None:
        self.assertEqual(len(ROLES_IN_THE_CACHED_REPORTS), 123)
        for role, side in ROLES_IN_THE_CACHED_REPORTS.items():
            with self.subTest(role):
                self.assertEqual(derive.side_of_role(role), side)
                self.assertEqual(derive.sprechrolle({"role": role}), side)

    def test_the_table_covers_all_three_sides(self) -> None:
        sides = set(ROLES_IN_THE_CACHED_REPORTS.values())
        self.assertEqual(sides, set(derive.SPRECHROLLE_LABELS))

    def test_the_short_form_is_used_when_there_is_no_long_one(self) -> None:
        self.assertEqual(derive.sprechrolle({"role_short": "Bundeskanzler"}), "bundesregierung")

    def test_no_role_is_no_sprechrolle(self) -> None:
        self.assertIsNone(derive.sprechrolle({"display_name": "Ada", "fraktion": "SPD"}))
        self.assertIsNone(derive.sprechrolle(None))

    def test_an_unmapped_role_raises_strictly_and_reads_as_none_leniently(self) -> None:
        with self.assertRaises(derive.SprechrolleError):
            derive.sprechrolle({"role": "Präsident des Bundesrates"})
        self.assertIsNone(derive.sprechrolle({"role": "Präsident des Bundesrates"}, strict=False))

    def test_a_land_in_brackets_is_the_bundesrat_even_for_a_staatsminister(self) -> None:
        self.assertEqual(derive.side_of_role("Staatsminister (Hessen)"), "bundesrat")
        self.assertEqual(derive.side_of_role("Staatsminister beim Bundeskanzler"), "bundesregierung")
        self.assertEqual(derive.side_of_role("Staatsministerin im Auswärtigen Amt"), "bundesregierung")


def report(number: str, *speakers: dict) -> dict:
    return {
        "protocol": {"id": f"p-{number}", "dokumentnummer": number, "datum": "2026-01-01"},
        "agenda_items": [
            {
                "index": 1,
                "top_id": "T1",
                "heading": "TOP 1",
                "xml_speakers": [
                    {
                        "rede_id": f"ID{number.replace('/', '')}{index:02d}",
                        "speaker": speaker,
                        "paragraph_count": 1,
                        "char_count": 100 * index,
                        "text": "Hallo",
                        "snippet": "Hallo",
                    }
                    for index, speaker in enumerate(speakers, start=1)
                ],
            }
        ],
    }


MERZ = {"xml_redner_id": "1", "display_name": "Friedrich Merz", "role": "Bundeskanzler", "role_short": "Bundeskanzler"}
GESUNDHEIT = {"xml_redner_id": "2", "display_name": "Karl Lauterbach", "role": "Bundesminister für Gesundheit"}
SOEDER = {"xml_redner_id": "3", "display_name": "Markus Söder", "role": "Ministerpräsident (Bayern)"}
EVA = {"xml_redner_id": "4", "display_name": "Eva Högl", "role": "Wehrbeauftragte des Deutschen Bundestages"}
ADA = {"xml_redner_id": "5", "display_name": "Ada Lovelace", "fraktion": "SPD"}
STAATSSEKRETAER_MDB = {  # an MdB who also speaks as Parl. Staatssekretär: the Rede counts for the Bundesregierung
    "xml_redner_id": "6", "display_name": "Bea Beispiel", "fraktion": "CDU/CSU",
    "role": "Parl. Staatssekretärin beim Bundesminister der Finanzen",
}


class PersistTests(unittest.TestCase):
    def store(self, *reports: dict) -> sqlite3.Connection:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = pulse_store.connect(Path(tmp.name) / "store.sqlite")
        self.addCleanup(conn.close)
        for item in reports:
            pulse_store.persist_report(conn, item)
        return conn

    def test_a_rede_in_a_sprechrolle_is_stored_with_its_side_and_no_party(self) -> None:
        conn = self.store(report("21/1", MERZ, GESUNDHEIT, SOEDER, EVA, ADA, STAATSSEKRETAER_MDB))
        rows = {
            row["display_name"]: (row["sprechrolle"], row["party"])
            for row in conn.execute(
                "SELECT m.display_name, s.sprechrolle, p.name AS party FROM speeches s "
                "JOIN mps m ON m.id = s.mp_id LEFT JOIN parties p ON p.id = m.party_id"
            )
        }
        self.assertEqual(rows, {
            "Friedrich Merz": ("bundesregierung", None),
            "Karl Lauterbach": ("bundesregierung", None),
            "Markus Söder": ("bundesrat", None),
            "Eva Högl": ("weitere", None),
            "Ada Lovelace": (None, "SPD"),
            # The role wins for this Rede; the person keeps the Fraktion the XML names for them.
            "Bea Beispiel": ("bundesregierung", "CDU/CSU"),
        })
        # No pseudo-Fraktion "Regierung" (or "Bundesregierung") in parties.
        self.assertEqual({row["name"] for row in conn.execute("SELECT name FROM parties")}, {"SPD", "CDU/CSU"})

    def test_the_redeanteil_recipe_gives_the_sides_their_own_rows_and_the_shares_sum_to_100(self) -> None:
        conn = self.store(report("21/1", MERZ, GESUNDHEIT, SOEDER, EVA, ADA, STAATSSEKRETAER_MDB))
        recipe = next(r for r in build.RECIPES if r["id"] == "r2-redeanteil-fraktion")
        sql = recipe["sql"].rstrip().removesuffix("LIMIT 5;")
        rows = {row["fraktion"]: (row["reden"], row["anteil_prozent"]) for row in conn.execute(sql)}
        self.assertEqual(set(rows), {"Bundesregierung", "Bundesrat", "weitere Sprechrolle", "SPD"})
        self.assertEqual(rows["Bundesregierung"][0], 3)
        self.assertAlmostEqual(sum(share for _, share in rows.values()), 100.0, places=0)

    def test_a_fact_row_names_the_side_not_a_fraktion_for_a_role_speech(self) -> None:
        conn = self.store(report("21/1", MERZ, ADA))
        sql = facts.REGISTRY_BY_ID["laengste-rede"]["sql"]
        rows = {row["display_name"]: (row["fraktion"], row["sprechrolle"]) for row in conn.execute(sql)}
        self.assertEqual(rows["Friedrich Merz"], (None, "bundesregierung"))
        self.assertEqual(rows["Ada Lovelace"], ("SPD", None))
        self.assertEqual(html.speaker_party({"fraktion": None, "sprechrolle": "bundesregierung"}), "Bundesregierung")
        self.assertEqual(html.speaker_party({"fraktion": "SPD", "sprechrolle": None}), "SPD")


class UnmappedRoleTests(unittest.TestCase):
    ODD = {"xml_redner_id": "9", "display_name": "Dora", "role": "Präsident des Bundesrates"}
    ODDER = {"xml_redner_id": "10", "display_name": "Emil", "role": "Sonderbeauftragter der Bundesregierung"}

    def test_persist_names_the_role_the_protocol_the_rede_and_the_fix(self) -> None:
        conn = pulse_store.connect(Path(tempfile.mkdtemp()) / "store.sqlite")
        self.addCleanup(conn.close)
        with self.assertRaises(derive.SprechrolleError) as caught:
            pulse_store.persist_report(conn, report("21/7", self.ODD, ADA))
        message = str(caught.exception)
        self.assertTrue(message.startswith("ERROR [sprechrolle]: 1 speaker role(s) map to no Sprechrolle:"))
        self.assertIn('"Präsident des Bundesrates" (21/7 ID21701)', message)
        self.assertIn("Fix: add each role to SPRECHROLLE_RULES in scripts/derive.py", message)
        self.assertIn("Docs: README.md#sprechrolle-rules", message)
        # Nothing of the report was written.
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM speeches").fetchone()[0], 0)

    def test_a_rebuild_lists_every_unmapped_role_at_once_and_keeps_the_old_store(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        database = tmp / "store.sqlite"
        build.rebuild_database_from_entries(database, [{"report": report("21/1", ADA), "report_path": tmp / "a.json"}])
        before = hashlib.sha256(database.read_bytes()).hexdigest()
        entries = [
            {"report": report("21/7", self.ODD, ADA), "report_path": tmp / "b.json"},
            {"report": report("21/8", self.ODDER, self.ODD), "report_path": tmp / "c.json"},
        ]
        with self.assertRaises(derive.SprechrolleError) as caught:
            build.rebuild_database_from_entries(database, entries)
        message = str(caught.exception)
        self.assertEqual(message.count("ERROR [sprechrolle]"), 1)
        self.assertIn("2 speaker role(s)", message)
        self.assertIn('"Präsident des Bundesrates" (21/7 ID21701, 21/8 ID21802)', message)
        self.assertIn('"Sonderbeauftragter der Bundesregierung" (21/8 ID21801)', message)
        self.assertEqual(before, hashlib.sha256(database.read_bytes()).hexdigest())
        self.assertEqual(list(database.parent.glob(f".{database.name}.*.tmp")), [])

    def test_the_command_prints_the_error_line_and_exits_1(self) -> None:
        import json
        import sys
        from unittest import mock

        tmp = Path(tempfile.mkdtemp())
        (tmp / "data").mkdir()
        (tmp / "protocols").mkdir()
        (tmp / "data" / "plenarprotokoll-21-7.json").write_text(json.dumps(report("21/7", self.ODD)), encoding="utf-8")
        err = io.StringIO()
        with mock.patch.object(sys, "argv", ["build", "--offline", "--repersist", "--output-dir", str(tmp)]),                 contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = build.main()
        self.assertEqual(code, 1)
        self.assertIn("ERROR [sprechrolle]:", err.getvalue())
        self.assertIn("21/7 ID21701", err.getvalue())


class RenderTests(unittest.TestCase):
    def test_a_stale_cached_speaker_shows_its_side_not_regierung(self) -> None:
        self.assertEqual(html.speaker_party(MERZ), "Bundesregierung")
        self.assertEqual(html.speaker_party(SOEDER), "Bundesrat")
        self.assertEqual(html.speaker_party(EVA), "weitere Sprechrolle")
        self.assertEqual(html.speaker_party(STAATSSEKRETAER_MDB), "Bundesregierung")
        self.assertEqual(html.speaker_party(ADA), "SPD")
        # A page must render: an unmapped role claims nothing.
        self.assertEqual(html.speaker_party({"role": "Präsident des Bundesrates"}), "Unbekannt")

    def test_the_week_figures_count_the_sides_as_their_own_rows_in_the_denominator(self) -> None:
        item = {
            "index": 1,
            "xml_speakers": [
                {"rede_id": f"R{index}", "speaker": speaker, "char_count": 10}
                for index, speaker in enumerate([MERZ, GESUNDHEIT, SOEDER, EVA, ADA, ADA], start=1)
            ],
        }
        stats = html.item_stats(item, {"dokumentnummer": "21/1", "datum": "2026-01-01"})
        self.assertEqual(
            dict(stats["party_counts"]),
            {"Bundesregierung": 2, "Bundesrat": 1, "weitere Sprechrolle": 1, "SPD": 2},
        )
        self.assertEqual(sum(stats["party_counts"].values()), stats["speech_count"])
        self.assertNotIn("Regierung", stats["party_counts"])
        for label in ("Bundesregierung", "Bundesrat", "weitere Sprechrolle"):
            self.assertIn(label, html.PARTY_COLORS)


if __name__ == "__main__":
    unittest.main()
