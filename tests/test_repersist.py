"""``--offline --repersist`` (DX-O1, E5, E9): every cached report into a fresh
store, swapped in only when all of them persisted."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import build_dip_pulse_site as build
import persist_dip_pulse_store as pulse_store
import speech_kinds
from _support import FIXTURES


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protocol_xml(number: str) -> str:
    """The smallest download --fetch-xml accepts for a sitting: a Plenarprotokoll root
    carrying that sitting's Wahlperiode and Sitzungsnummer."""
    wahlperiode, _, sitzung = number.partition("/")
    return f'<dbtplenarprotokoll wahlperiode="{wahlperiode}" sitzung-nr="{sitzung}"/>'


class ReparseCachedXmlTests(unittest.TestCase):
    """A rule change in the parser reaches the cached reports and the store from the
    cached XML, with no re-fetch (A1)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.output_dir = Path(self._tmp.name) / "site"
        (self.output_dir / "data" / "xml").mkdir(parents=True)
        (self.output_dir / "protocols").mkdir()
        self.database = self.output_dir / "data" / "bundestag-pulse.sqlite"
        xml = (FIXTURES / "speech-kinds-befragung-fragestunde.xml").read_text(encoding="utf-8")
        (self.output_dir / "data" / "xml" / "plenarprotokoll-21-6.xml").write_text(xml, encoding="utf-8")
        # The report as the parser of before A1 wrote it: every <rede> a Rede.
        # Dobrindt's opening report (Rede) carries the profile resolved online; Kraft's
        # only sitting item in the report is a Rede of an older parse.
        self.dobrindt = {"id": 4711, "url": "https://www.abgeordnetenwatch.de/profile/dobrindt", "match": "ext_id"}
        self.kraft = {"id": 815, "url": "https://www.abgeordnetenwatch.de/profile/kraft", "match": "ext_id"}
        stale = {
            "rede_id": "OLD",
            "speaker": {"xml_redner_id": "11003516", "first_name": "Alexander", "last_name": "Dobrindt",
                        "display_name": "Alexander Dobrindt", "abgeordnetenwatch": self.dobrindt},
            "char_count": 5,
            "text": "alt",
        }
        stale_kraft = {
            "rede_id": "OLDK",
            "speaker": {"xml_redner_id": "11004792", "first_name": "Rainer", "last_name": "Kraft",
                        "display_name": "Dr. Rainer Kraft", "abgeordnetenwatch": self.kraft},
            "char_count": 5,
            "text": "alt",
        }
        self.report = {
            "protocol": {"id": "5709", "dokumentnummer": "21/6", "datum": "2025-05-14"},
            "validation_summary": {"xml_speech_count": 1},
            "warnings": ["Die XML zählt 9 Erwiderungen, DIP 0.", "Anderes."],
            "api_records": {"aktivitaeten": [{"aktivitaetsart": "Kurzintervention"}]},
            "agenda_items": [
                {"index": 1, "top_id": "Tagesordnungspunkt 1", "heading": "Befragung der Bundesregierung",
                 "xml_speech_count": 1, "xml_speakers": [stale], "xml_speakers_first": [stale]},
                {"index": 2, "top_id": "Tagesordnungspunkt 2", "heading": "Fragestunde",
                 "xml_speech_count": 1, "xml_speakers": [stale_kraft]},
            ],
        }
        (self.output_dir / "data" / "plenarprotokoll-21-6.json").write_text(json.dumps(self.report), encoding="utf-8")

    def entries(self) -> list[dict]:
        return build.load_existing_detail_entries(self.output_dir, [{"dokumentnummer": "21/6"}])

    def test_the_report_is_reparsed_from_its_cached_xml(self) -> None:
        entries = self.entries()
        self.assertEqual(build.reparse_cached_xml(self.output_dir, entries), 1)
        report = entries[0]["report"]
        befragung, fragestunde = report["agenda_items"]
        self.assertEqual([s["speaker"]["display_name"] for s in befragung["xml_speakers"]], ["Alexander Dobrindt", "Verena Hubertz"])
        self.assertEqual(befragung["xml_speech_count"], 2)
        self.assertEqual(befragung["question_formats"], ["befragung"])
        self.assertEqual(befragung["xml_contributions"][0]["kind"], "befragung_frage")
        self.assertEqual(fragestunde["xml_contributions"][0]["kind"], "fragestunde_frage")
        summary = report["validation_summary"]
        self.assertEqual(summary["xml_speech_count"], 2)
        self.assertGreater(summary["xml_contribution_counts"]["fragestunde_antwort"], 0)
        # The DIP check is refreshed: the stale warning goes, the unrelated one stays.
        self.assertEqual(
            summary["contribution_dip_mismatches"], [{"kind": "kurzintervention", "xml": 0, "dip": 1}]
        )
        self.assertEqual(
            report["warnings"],
            ["Anderes.", "Die XML zählt 0 Kurzinterventionen, DIP 1."],
        )

    # Value: protects=a reparsed report holds exactly what a fresh build of the same XML holds, for every XML-derived key of an agenda item, the heading included (a T_ZP_NaS heading the parser learned to read reaches cached reports);
    #   fails_when=enrich_with_api gains an XML-derived item key that reparse_report_xml does not refresh, or the reparse stops refreshing the heading, so a repersisted store and an online build disagree;
    #   why_new=the heading fix of A1 reached question_formats but not the stored heading, and no test compared a reparse with a fresh build; seam=none
    def test_a_reparse_leaves_every_xml_derived_key_as_a_fresh_build_writes_it(self) -> None:
        import copy

        import validate_dip_protocol as dip

        class FakeClient:
            def list_all(self, path: str, params: dict[str, str]) -> list:
                return []

        parsed = dip.parse_protocol_xml((self.output_dir / "data" / "xml" / "plenarprotokoll-21-6.xml").read_text(encoding="utf-8"))
        with contextlib.redirect_stderr(io.StringIO()):
            fresh = dip.enrich_with_api(
                FakeClient(),  # type: ignore[arg-type]
                {"id": "5709", "dokumentnummer": "21/6", "datum": "2025-05-14"},
                parsed, person_limit=0, vote_scan_pages=0,
            )
        dip_side = {"index", "api", "votes"}
        stale = copy.deepcopy(fresh)
        for item in stale["agenda_items"]:
            for key in item:
                if key not in dip_side:
                    item[key] = "STALE"
        stale["protocol"] = {"id": "5709", "dokumentnummer": "21/6", "datum": "2025-05-14"}
        dip.reparse_report_xml(stale, parsed)
        for refreshed, built in zip(stale["agenda_items"], fresh["agenda_items"]):
            self.assertEqual(
                {k: v for k, v in refreshed.items() if k not in dip_side},
                {k: v for k, v in built.items() if k not in dip_side},
            )
        self.assertEqual([item["heading"] for item in stale["agenda_items"]], ["Befragung der Bundesregierung", "Fragestunde"])

    # Value: protects=a cached AI summary whose cited Rede the reparse turned into a Beitrag (or otherwise changed) is dropped, one whose source still matches is kept;
    #   fails_when=reparse_report_xml keeps an llm_summary whose source_fingerprint no longer matches the re-read Reden, so a dossier or the week radar quotes a turn that has no speech anchor;
    #   why_new=no repersist test carried an llm_summary through a parse-rule change; seam=none
    def test_a_summary_whose_source_changed_is_dropped_by_the_reparse(self) -> None:
        import validate_dip_protocol as dip

        entries = self.entries()
        build.reparse_cached_xml(self.output_dir, entries)
        report = entries[0]["report"]
        befragung, fragestunde = report["agenda_items"]
        current = dip.summary_source_fingerprint(
            {"top_id": befragung["top_id"], "heading": befragung["heading"], "speeches": befragung["xml_speakers"]}
        )
        befragung["llm_summary"] = {"text": "Bleibt.", "source_chunks": [{"id": "S1"}], "source_fingerprint": current}
        fragestunde["llm_summary"] = {"text": "Geht.", "source_chunks": [{"id": "S1"}], "source_fingerprint": "old-parse"}
        report["summary_generation"] = {"available_top_count": 2}
        build.reparse_cached_xml(self.output_dir, entries)
        self.assertEqual(befragung["llm_summary"]["text"], "Bleibt.")
        self.assertNotIn("llm_summary", fragestunde)
        self.assertEqual(report["summary_generation"]["available_top_count"], 1)

    def test_the_profiles_resolved_online_survive_the_reparse(self) -> None:
        entries = self.entries()
        build.reparse_cached_xml(self.output_dir, entries)
        befragung, fragestunde = entries[0]["report"]["agenda_items"]
        # Dobrindt's Reden and the Antworten he gives carry the profile ...
        for speech in [*befragung["xml_speakers"], *befragung["xml_contributions"]]:
            if speech["speaker"]["last_name"] == "Dobrindt":
                self.assertEqual(speech["speaker"]["abgeordnetenwatch"], self.dobrindt)
        # ... and so does a Fragestunde question of an MdB, by the Redner-ID.
        kraft = [c for c in fragestunde["xml_contributions"] if c["speaker"]["last_name"] == "Kraft"]
        self.assertTrue(kraft)
        self.assertTrue(all(c["speaker"]["abgeordnetenwatch"] == self.kraft for c in kraft))
        # A speaker nobody resolved stays unresolved.
        curio = next(c for c in befragung["xml_contributions"] if c["speaker"]["last_name"] == "Curio")
        self.assertNotIn("abgeordnetenwatch", curio["speaker"])

    # Value: protects=a Person whose profile a cached report holds only from another sitting gets it back on a Frage of this sitting, matched by Redner-ID;
    #   fails_when=attach_speaker_profiles loses its by_redner_id fallback or reparse_cached_xml stops collecting profiles across reports;
    #   why_new=test_the_profiles_resolved_online_survive_the_reparse matches Kraft by identity within the report, so the cross-report Redner-ID path never runs; seam=none
    def test_a_profile_resolved_in_another_sitting_reaches_a_person_who_only_asks_a_frage(self) -> None:
        report_path = self.output_dir / "data" / "plenarprotokoll-21-6.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        kraft_here = report["agenda_items"][1]["xml_speakers"][0]
        kraft_elsewhere = json.loads(json.dumps(kraft_here))  # still carries the profile
        del kraft_here["speaker"]["abgeordnetenwatch"]
        report_path.write_text(json.dumps(report), encoding="utf-8")
        # 21/5 has no cached XML: it is not re-parsed, it only supplies the profile.
        other = {
            "protocol": {"id": "5708", "dokumentnummer": "21/5", "datum": "2025-05-13"},
            "agenda_items": [{"index": 1, "heading": "Aktuelle Stunde", "xml_speakers": [kraft_elsewhere]}],
        }
        (self.output_dir / "data" / "plenarprotokoll-21-5.json").write_text(json.dumps(other), encoding="utf-8")

        entries = build.load_existing_detail_entries(
            self.output_dir, [{"dokumentnummer": "21/6"}, {"dokumentnummer": "21/5"}]
        )
        self.assertEqual(build.reparse_cached_xml(self.output_dir, entries), 1)

        this_sitting = next(e for e in entries if e["report"]["protocol"]["dokumentnummer"] == "21/6")
        fragestunde = this_sitting["report"]["agenda_items"][1]
        kraft = [c for c in fragestunde["xml_contributions"] if c["speaker"]["last_name"] == "Kraft"]
        self.assertTrue(kraft)
        self.assertTrue(all(c["speaker"]["abgeordnetenwatch"] == self.kraft for c in kraft))

    # Value: protects=--fetch-xml counts a missing xml_url or failed download without stopping, exits 1 on any, and hints at --offline --repersist only if none failed;
    #   fails_when=one failed download aborts the run, a failure is counted as fetched, or the command exits 0 with failures;
    #   why_new=test_the_xml_of_a_cached_report_can_be_fetched covers only the successful download and never runs the --fetch-xml command or its hint; seam=none
    def test_fetch_xml_counts_failures_and_the_command_exits_1_on_any(self) -> None:
        entries = [
            {"report": {"protocol": {"dokumentnummer": "21/1"}}},
            {"report": {"protocol": {"dokumentnummer": "21/2", "xml_url": "https://example.test/2.xml"}}},
            {"report": {"protocol": {"dokumentnummer": "21/3", "xml_url": "https://example.test/3.xml"}}},
        ]

        def fetch(url: str) -> str:
            if url.endswith("2.xml"):
                raise build.dip.DipError("HTTP 404")
            return protocol_xml("21/3")

        stderr = io.StringIO()
        with mock.patch.object(build.dip, "fetch_text", side_effect=fetch), contextlib.redirect_stderr(stderr):
            self.assertEqual(build.fetch_missing_xml(self.output_dir, entries, pause=0), (1, 2))
        xml_dir = self.output_dir / "data" / "xml"
        self.assertEqual(sorted(p.name for p in xml_dir.glob("plenarprotokoll-21-[123].xml")), ["plenarprotokoll-21-3.xml"])
        self.assertIn("21/1 has no xml_url", stderr.getvalue())
        self.assertIn("21/2: HTTP 404", stderr.getvalue())

        # The command, over the one cached report (21/6), whose XML is not cached and
        # whose protocol names an xml_url.
        report_path = self.output_dir / "data" / "plenarprotokoll-21-6.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["protocol"]["xml_url"] = "https://example.test/6.xml"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        (xml_dir / "plenarprotokoll-21-6.xml").unlink()
        for name, side_effect, code, said in (
            ("failing", build.dip.DipError("HTTP 500"), 1, "21/6: HTTP 500"),
            ("working", None, 0, "fetch-xml: 1 fetched, 0 failed, 0 already cached"),
        ):
            with self.subTest(name):
                (xml_dir / "plenarprotokoll-21-6.xml").unlink(missing_ok=True)
                argv = ["build", "--fetch-xml", "--output-dir", str(self.output_dir)]
                err = io.StringIO()
                with mock.patch.object(sys, "argv", argv), mock.patch.object(
                    build.dip, "fetch_text", side_effect=side_effect, return_value=protocol_xml("21/6")
                ), mock.patch.object(build.time, "sleep"), contextlib.redirect_stderr(err):
                    self.assertEqual(build.main(), code)
                self.assertIn(said, err.getvalue())
                if code:
                    self.assertIn("fetch-xml: 0 fetched, 1 failed, 0 already cached", err.getvalue())
                # The next-step hint only follows a run that failed nowhere.
                self.assertEqual("next, run --offline --repersist" in err.getvalue(), code == 0)

    def test_the_xml_of_a_cached_report_can_be_fetched_and_a_missing_one_is_said(self) -> None:
        (self.output_dir / "data" / "xml" / "plenarprotokoll-21-6.xml").unlink()
        report_path = self.output_dir / "data" / "plenarprotokoll-21-6.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["protocol"]["xml_url"] = "https://www.bundestag.de/resource/blob/x/21006.xml"
        report_path.write_text(json.dumps(report), encoding="utf-8")
        stderr = io.StringIO()
        with mock.patch.object(build.dip, "fetch_text", return_value=protocol_xml("21/6")) as fetch, \
                contextlib.redirect_stderr(stderr):
            fetched, failed = build.fetch_missing_xml(self.output_dir, self.entries(), pause=0)
            # Nothing is fetched twice.
            self.assertEqual(build.fetch_missing_xml(self.output_dir, self.entries(), pause=0), (0, 0))
        self.assertEqual((fetched, failed), (1, 0))
        fetch.assert_called_once_with("https://www.bundestag.de/resource/blob/x/21006.xml")
        self.assertEqual(
            (self.output_dir / "data" / "xml" / "plenarprotokoll-21-6.xml").read_text(encoding="utf-8"),
            protocol_xml("21/6"),
        )
        # A repersist over a report with no cached XML says what that leaves behind.
        (self.output_dir / "data" / "xml" / "plenarprotokoll-21-6.xml").unlink()
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            build.repersist_cached_reports(self.output_dir, self.database, build.load_cached_protocols(self.output_dir))
        self.assertIn("1 of 1 cached reports predate the A1 Rede rule and have no cached XML", stderr.getvalue())
        self.assertIn("--fetch-xml", stderr.getvalue())

    # Value: protects=a cached report from before A1 is counted and named once with the two commands that fix it, and a current report stays silent;
    #   fails_when=the warning drops the count, --fetch-xml or --offline --repersist, fires for a marked report, or the return count is wrong;
    #   why_new=the warning text was only checked as a side effect of repersist_cached_reports on one report; seam=none
    def test_warn_unparsed_reports_names_the_stale_count_and_the_fix(self) -> None:
        current = {"report": {"validation_summary": {"speech_kinds_version": speech_kinds.VERSION}}}
        old = {"report": {"validation_summary": {"xml_speech_count": 1}}}
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(build.warn_unparsed_reports([current, old]), 1)
        message = stderr.getvalue()
        self.assertEqual(message.count("warning:"), 1)
        self.assertIn("1 of 2 cached reports predate the A1 Rede rule", message)
        self.assertIn("--fetch-xml", message)
        self.assertIn("--offline --repersist", message)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(build.warn_unparsed_reports([current, current]), 0)
        self.assertEqual(stderr.getvalue(), "")

    # Value: protects=re-parsing from cached XML stamps the report with the current speech_kinds_version and a report without XML keeps none, so only it is warned about;
    #   fails_when=reparse_report_xml stops writing the marker, or a report without cached XML gets one;
    #   why_new=no test read the marker after a reparse; the warning depends on it to clear; seam=none
    def test_a_reparse_stamps_the_speech_kinds_version_and_a_report_without_xml_keeps_none(self) -> None:
        bare = {"protocol": {"id": "5710", "dokumentnummer": "21/7", "datum": "2025-05-15"}, "agenda_items": []}
        (self.output_dir / "data" / "plenarprotokoll-21-7.json").write_text(json.dumps(bare), encoding="utf-8")
        entries = build.load_existing_detail_entries(
            self.output_dir, [{"dokumentnummer": "21/6"}, {"dokumentnummer": "21/7"}]
        )
        self.assertEqual(build.warn_unparsed_reports(entries), 2)
        self.assertEqual(build.reparse_cached_xml(self.output_dir, entries), 1)
        reparsed, without_xml = (entry["report"] for entry in entries)
        self.assertEqual(reparsed["validation_summary"]["speech_kinds_version"], speech_kinds.VERSION)
        self.assertNotIn("speech_kinds_version", without_xml.get("validation_summary") or {})
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(build.warn_unparsed_reports(entries), 1)
        self.assertIn("1 of 2 cached reports predate", stderr.getvalue())

    # Value: protects=a cached XML that is not XML stops the re-parse with an error naming the file and --fetch-xml, and the repersist leaves the store file untouched;
    #   fails_when=reparse_cached_xml lets the ParseError escape unwrapped, drops the path or the --fetch-xml fix, or the store is replaced before the error;
    #   why_new=only the unreadable report JSON path was tested; a bad cached XML is a separate failure with its own message; seam=none
    def test_a_cached_xml_that_is_not_xml_stops_the_reparse_and_leaves_the_store_untouched(self) -> None:
        build.repersist_cached_reports(self.output_dir, self.database, build.load_cached_protocols(self.output_dir))
        before, stat = self.database.read_bytes(), self.database.stat()
        xml_path = self.output_dir / "data" / "xml" / "plenarprotokoll-21-6.xml"
        xml_path.write_text("<html>maintenance", encoding="utf-8")
        with self.assertRaises(build.CachedReportError) as caught:
            build.reparse_cached_xml(self.output_dir, self.entries())
        self.assertIn(str(xml_path), str(caught.exception))
        self.assertIn("run --fetch-xml", str(caught.exception))
        with self.assertRaises(build.CachedReportError):
            build.repersist_cached_reports(self.output_dir, self.database, build.load_cached_protocols(self.output_dir))
        after = self.database.stat()
        self.assertEqual(before, self.database.read_bytes())
        self.assertEqual((stat.st_ino, stat.st_mtime_ns), (after.st_ino, after.st_mtime_ns))

    # Value: protects=a cached XML of another sitting, a non-protocol, without agenda items or short of a report's item stops the reparse before any change or marker;
    #   fails_when=check_xml_belongs_to_report drops one of its four checks, or the error is not turned into a CachedReportError naming the file;
    #   why_new=the ParseError test covers ill-formed XML; these well-formed files parse and would stamp the marker over a report holding the old rule; seam=none
    def test_a_cached_xml_that_is_not_this_sittings_protocol_stops_the_reparse_unmarked(self) -> None:
        build.repersist_cached_reports(self.output_dir, self.database, build.load_cached_protocols(self.output_dir))
        before, stat = self.database.read_bytes(), self.database.stat()
        xml_path = self.output_dir / "data" / "xml" / "plenarprotokoll-21-6.xml"
        sitzungsverlauf = "<sitzungsverlauf>{}</sitzungsverlauf>"
        cases = {
            "another sitting": (FIXTURES / "speech-kinds-befragung-fragestunde.xml")
            .read_text(encoding="utf-8")
            .replace('wahlperiode="21" sitzung-nr="6"', 'wahlperiode="20" sitzung-nr="9"'),
            "not a protocol": "<html><body>Wartung</body></html>",
            "no agenda items": f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="6">{sitzungsverlauf.format("")}</dbtplenarprotokoll>',
            "an agenda item of the report missing": (
                '<dbtplenarprotokoll wahlperiode="21" sitzung-nr="6">'
                + sitzungsverlauf.format('<tagesordnungspunkt top-id="Tagesordnungspunkt 1"/>')
                + "</dbtplenarprotokoll>"
            ),
        }
        for name, xml in cases.items():
            with self.subTest(name):
                xml_path.write_text(xml, encoding="utf-8")
                entries = self.entries()
                with self.assertRaises(build.CachedReportError) as caught:
                    build.reparse_cached_xml(self.output_dir, entries)
                self.assertIn(str(xml_path), str(caught.exception))
                self.assertIn("21/6", str(caught.exception))
                report = entries[0]["report"]
                self.assertNotIn("speech_kinds_version", report["validation_summary"])
                self.assertEqual(report["agenda_items"][0]["xml_speakers"][0]["rede_id"], "OLD")
                self.assertEqual(report["agenda_items"][1]["xml_speakers"][0]["rede_id"], "OLDK")
                with self.assertRaises(build.CachedReportError):
                    build.repersist_cached_reports(
                        self.output_dir, self.database, build.load_cached_protocols(self.output_dir)
                    )
                after = self.database.stat()
                self.assertEqual(before, self.database.read_bytes())
                self.assertEqual((stat.st_ino, stat.st_mtime_ns), (after.st_ino, after.st_mtime_ns))
        with self.subTest("no agenda items, and the report holds none either"):
            # Nothing is missing then, so only the emptiness check stops a marker over nothing.
            bare = {"protocol": {"id": "5710", "dokumentnummer": "21/7", "datum": "2025-05-15"}, "agenda_items": []}
            (self.output_dir / "data" / "plenarprotokoll-21-7.json").write_text(json.dumps(bare), encoding="utf-8")
            (self.output_dir / "data" / "xml" / "plenarprotokoll-21-7.xml").write_text(
                f'<dbtplenarprotokoll wahlperiode="21" sitzung-nr="7">{sitzungsverlauf.format("")}</dbtplenarprotokoll>',
                encoding="utf-8",
            )
            entries = build.load_existing_detail_entries(self.output_dir, [{"dokumentnummer": "21/7"}])
            with self.assertRaises(build.CachedReportError) as caught:
                build.reparse_cached_xml(self.output_dir, entries)
            self.assertIn("plenarprotokoll-21-7.xml", str(caught.exception))
            self.assertNotIn("speech_kinds_version", entries[0]["report"].get("validation_summary") or {})

    # Value: protects=--fetch-xml refuses a well-formed download that is not the wanted sitting's Plenarprotokoll (maintenance page, other sitting): failed, not cached;
    #   fails_when=fetch_missing_xml checks only that the text parses, or not the root tag, Wahlperiode and Sitzungsnummer, so a wrong file becomes the cache;
    #   why_new=the ill-formed download test stops at ParseError; a well-formed wrong root is a separate branch of the same check; seam=none
    def test_a_well_formed_download_of_the_wrong_document_is_counted_failed_and_never_cached(self) -> None:
        xml_dir = self.output_dir / "data" / "xml"
        (xml_dir / "plenarprotokoll-21-6.xml").unlink()
        entries = [{"report": {"protocol": {"dokumentnummer": "21/6", "xml_url": "https://example.test/6.xml"}}}]
        for name, text in (
            ("not a protocol", "<html><body>Wartung</body></html>"),
            ("another sitting", protocol_xml("21/7")),
            ("the right numbers on the wrong root", '<html wahlperiode="21" sitzung-nr="6"/>'),
        ):
            with self.subTest(name):
                stderr = io.StringIO()
                with mock.patch.object(build.dip, "fetch_text", return_value=text), contextlib.redirect_stderr(stderr):
                    self.assertEqual(build.fetch_missing_xml(self.output_dir, entries, pause=0), (0, 1))
                self.assertEqual(list(xml_dir.iterdir()), [])
                self.assertIn("warning: 21/6: it is not the Plenarprotokoll XML of 21/6", stderr.getvalue())

    # Value: protects=--fetch-xml refuses a download that is not XML (an error page served with HTTP 200): counted failed, named by document number, nothing cached;
    #   fails_when=fetch_missing_xml stops parsing the text before writing, so an HTML page becomes the cached XML the next repersist trips over;
    #   why_new=the fetch tests only return valid XML or raise DipError; a 200 with a non-XML body is a separate branch; seam=none
    def test_a_download_that_is_not_xml_is_counted_failed_and_never_cached(self) -> None:
        (self.output_dir / "data" / "xml" / "plenarprotokoll-21-6.xml").unlink()
        entries = [{"report": {"protocol": {"dokumentnummer": "21/6", "xml_url": "https://example.test/6.xml"}}}]
        stderr = io.StringIO()
        with mock.patch.object(build.dip, "fetch_text", return_value="<html>maintenance"), contextlib.redirect_stderr(stderr):
            self.assertEqual(build.fetch_missing_xml(self.output_dir, entries, pause=0), (0, 1))
        self.assertEqual(list((self.output_dir / "data" / "xml").iterdir()), [])
        self.assertIn("warning: 21/6:", stderr.getvalue())

    def test_a_report_without_cached_xml_is_left_alone(self) -> None:
        (self.output_dir / "data" / "xml" / "plenarprotokoll-21-6.xml").unlink()
        entries = self.entries()
        self.assertEqual(build.reparse_cached_xml(self.output_dir, entries), 0)
        self.assertEqual(entries[0]["report"]["agenda_items"][0]["xml_speakers"][0]["rede_id"], "OLD")

    def test_repersist_stores_reden_and_contributions_apart(self) -> None:
        build.repersist_cached_reports(self.output_dir, self.database, build.load_cached_protocols(self.output_dir))
        conn = sqlite3.connect(self.database)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM speeches").fetchone()[0], 2)
            kinds = dict(conn.execute("SELECT kind, COUNT(*) FROM contributions GROUP BY kind"))
            self.assertGreater(kinds["befragung_frage"], 0)
            self.assertGreater(kinds["fragestunde_antwort"], 0)
            # A Beitrag names its speaker like a Rede does: MdB row, Fraktion, Sprechrolle.
            row = conn.execute(
                "SELECT c.speaker_name, c.fraktion, c.sprechrolle, c.mp_id, c.rede_id, c.page FROM contributions c "
                "WHERE c.kind = 'befragung_antwort' ORDER BY c.sequence LIMIT 1"
            ).fetchone()
            self.assertEqual(row[0], "Alexander Dobrindt")
            self.assertEqual(row[2], "bundesregierung")
            self.assertIsNotNone(row[3])
            # A Fragestunde turn has neither a rede_id nor a page.
            turn = conn.execute(
                "SELECT rede_id, page, agenda_item_id FROM contributions WHERE kind = 'fragestunde_frage' LIMIT 1"
            ).fetchone()
            self.assertEqual((turn[0], turn[1]), (None, None))
            self.assertIsNotNone(turn[2])
        finally:
            conn.close()


class RepersistTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.output_dir = Path(self._tmp.name) / "site"
        (self.output_dir / "data").mkdir(parents=True)
        (self.output_dir / "protocols").mkdir()
        self.database = self.output_dir / "data" / "bundestag-pulse.sqlite"
        for fixture, slug in (("report.json", "20-999"), ("demo-report-21-84.json", "21-84")):
            report = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
            (self.output_dir / "data" / f"plenarprotokoll-{slug}.json").write_text(
                json.dumps(report), encoding="utf-8"
            )

    def protocols(self) -> list[dict]:
        return build.load_cached_protocols(self.output_dir)

    def repersist(self, **kwargs):
        return build.repersist_cached_reports(self.output_dir, self.database, self.protocols(), **kwargs)

    def count(self, table: str) -> int:
        conn = sqlite3.connect(self.database)
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            conn.close()

    def test_every_cached_report_lands_in_a_fresh_store(self) -> None:
        entries, replaced = self.repersist()
        self.assertTrue(replaced)
        self.assertEqual(len(entries), 2)
        self.assertEqual(self.count("protocols"), 2)
        # Rows of a protocol that is no longer cached do not survive a re-persist.
        conn = sqlite3.connect(self.database)
        try:
            conn.execute("INSERT INTO protocols(id, document_number, created_at, updated_at) VALUES ('x', '99/1', 't', 't')")
            conn.commit()
        finally:
            conn.close()
        self.repersist()
        self.assertEqual(self.count("protocols"), 2)

    def test_the_roster_rows_are_preserved(self) -> None:
        conn = pulse_store.connect(self.database)
        try:
            pulse_store.initialize(conn)
            now = pulse_store.utc_now()
            with conn:
                pulse_store.upsert_mp(
                    conn,
                    now=now,
                    display_name="Ada Lovelace",
                    party_id=pulse_store.upsert_party(conn, "SPD", now),
                    identity_key="dip:ada",
                    dip_person_id="ada",
                    is_mdb=True,
                )
        finally:
            conn.close()
        self.repersist()
        conn = sqlite3.connect(self.database)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM mps WHERE identity_key = 'dip:ada' AND is_mdb = 1").fetchone()[0], 1)
        finally:
            conn.close()

    def test_malformed_cached_json_aborts_and_leaves_the_store_alone(self) -> None:
        self.repersist()
        before = sha(self.database)
        (self.output_dir / "data" / "plenarprotokoll-21-99.json").write_text("{not json", encoding="utf-8")
        with self.assertRaises(build.CachedReportError) as caught:
            self.repersist()
        self.assertIn("plenarprotokoll-21-99.json", str(caught.exception))
        self.assertEqual(before, sha(self.database))
        self.assertFalse(self.database.with_name(f".{self.database.name}.tmp").exists())

    def test_non_object_cached_json_aborts_and_leaves_the_store_alone(self) -> None:
        self.repersist()
        before = sha(self.database)
        (self.output_dir / "data" / "plenarprotokoll-21-99.json").write_text("[]", encoding="utf-8")
        with self.assertRaises(build.CachedReportError) as caught:
            self.repersist()
        self.assertIn("top-level JSON value is not an object", str(caught.exception))
        self.assertEqual(before, sha(self.database))
        self.assertFalse(self.database.with_name(f".{self.database.name}.tmp").exists())

    def test_a_report_that_fails_to_persist_leaves_an_old_schema_store_byte_identical(self) -> None:
        # An older schema: a column the current initialize() would add is
        # missing. The source must be read as it is, not migrated, so even a
        # failed run cannot change its bytes.
        conn = pulse_store.connect(self.database)
        try:
            pulse_store.initialize(conn)
            conn.execute("ALTER TABLE mps DROP COLUMN person_roles_json")
            conn.commit()
        finally:
            conn.close()
        before = sha(self.database)
        real = pulse_store.persist_report

        def failing(store, report):
            if (report.get("protocol") or {}).get("dokumentnummer") == "21/84":
                raise ValueError("boom")
            return real(store, report)

        with mock.patch.object(pulse_store, "persist_report", side_effect=failing):
            with self.assertRaises(build.DatabaseRebuildError) as caught:
                self.repersist()
        self.assertIn("21/84", str(caught.exception))
        self.assertIn("boom", str(caught.exception))
        self.assertEqual(before, sha(self.database))
        self.assertNotIn("person_roles_json", self.columns("mps"))
        self.assertFalse(self.database.with_name(f".{self.database.name}.tmp").exists())

    def columns(self, table: str) -> set[str]:
        conn = sqlite3.connect(self.database)
        try:
            return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        finally:
            conn.close()

    def test_a_second_run_with_a_different_clock_keeps_the_file(self) -> None:
        _, replaced = self.repersist()
        self.assertTrue(replaced)
        stat = self.database.stat()
        before = sha(self.database)
        with mock.patch.object(pulse_store, "utc_now", return_value="2099-01-01T00:00:00Z"):
            _, replaced = self.repersist()
        self.assertFalse(replaced)
        after = self.database.stat()
        self.assertEqual((stat.st_ino, stat.st_mtime_ns), (after.st_ino, after.st_mtime_ns))
        self.assertEqual(before, sha(self.database))

    def test_a_content_change_replaces_the_file(self) -> None:
        self.repersist()
        path = self.output_dir / "data" / "plenarprotokoll-21-84.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report["protocol"]["titel"] = "Ein anderer Titel"
        path.write_text(json.dumps(report), encoding="utf-8")
        _, replaced = self.repersist()
        self.assertTrue(replaced)

    def run_main(self, *extra: str) -> tuple[int, str]:
        argv = ["build", "--offline", "--output-dir", str(self.output_dir), *extra]
        err = io.StringIO()
        # What follows the re-persist (Daten export, page rendering) is not under
        # test here, and the fixture MPs carry profile URLs the renderer refuses.
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stderr(err), contextlib.redirect_stdout(
            io.StringIO()
        ), mock.patch.object(build, "run_data_pipeline", return_value=(None, None, [], None, False)), mock.patch.object(
            build, "render_site", return_value=self.output_dir / "index.html"
        ):
            code = build.main()
        return code, err.getvalue()

    def test_the_command_reports_a_failure_as_one_error_line_and_exits_1(self) -> None:
        self.repersist()
        before = sha(self.database)
        (self.output_dir / "data" / "plenarprotokoll-21-99.json").write_text("[1, 2", encoding="utf-8")
        code, err = self.run_main("--repersist")
        self.assertEqual(code, 1)
        self.assertIn("ERROR [repersist]:", err)
        self.assertIn("plenarprotokoll-21-99.json", err)
        self.assertIn("Fix:", err)
        self.assertIn("Docs: README.md#re-persist-the-cached-reports", err)
        self.assertEqual(before, sha(self.database))

    def test_the_command_repersists_then_renders(self) -> None:
        code, err = self.run_main("--repersist")
        self.assertEqual(code, 0, err)
        self.assertIn("repersist: 2 cached reports persisted; store replaced", err)
        code, err = self.run_main("--repersist")
        self.assertEqual(code, 0, err)
        self.assertIn("store content unchanged, file kept", err)

    def test_the_command_preserves_roster_when_mp_roster_is_selected(self) -> None:
        self.repersist()
        conn = pulse_store.connect(self.database)
        try:
            now = pulse_store.utc_now()
            with conn:
                pulse_store.upsert_mp(
                    conn,
                    now=now,
                    display_name="Ada Lovelace",
                    party_id=pulse_store.upsert_party(conn, "SPD", now),
                    identity_key="dip:ada",
                    dip_person_id="ada",
                    is_mdb=True,
                )
        finally:
            conn.close()

        code, err = self.run_main("--repersist", "--enrich", "mp-roster")

        self.assertEqual(code, 0, err)
        conn = sqlite3.connect(self.database)
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM mps WHERE identity_key = 'dip:ada' AND is_mdb = 1").fetchone()[0],
                1,
            )
        finally:
            conn.close()

    def test_the_flag_needs_offline_and_persistence(self) -> None:
        for argv in (["build", "--repersist"], ["build", "--offline", "--repersist", "--no-persist"]):
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    build.parse_args()
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
