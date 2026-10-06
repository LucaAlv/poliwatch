"""Source regressions for the offline rule-v5 replay blockers."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import _support
import build_dip_pulse_site as build
import validate_dip_protocol as dip
from stable_ids import contribution_occurrence_id


FIXTURES = _support.FIXTURES / "offline-v5"
BLOCKERS = {
    "20-120": [("ID2012005800", 3)], "20-132": [("ID2013201500", 3)],
    "20-136": [("ID2013611100", 3)], "20-138": [("ID2013801000", 3)],
    "20-141": [("ID2014105600", 3)],
    "20-144": [("ID2014400100", 7), ("ID2014405100", 3), ("ID2014405100", 4)],
    "20-163": [("ID2016302300", 3)], "20-165": [("ID2016512400", 3)],
    "20-167": [("ID2016703200", 9)], "20-169": [("ID2016909900", 3)],
    "20-182": [("ID2018203700", 3)], "20-183": [("ID2018306700", 3)],
    "20-207": [("ID2020707400", 5)], "20-21": [("ID202111200", 3)],
    "20-28": [("ID202802000", 7)], "20-40": [("ID204000700", 3)],
    "20-44": [("ID204414000", 3)], "20-49": [("ID204906400", 3)],
    "20-51": [("ID205102700", 2), ("ID205104600", 4)], "20-58": [("ID205804200", 3)],
    "20-65": [("ID206509600", 3)], "20-76": [("ID207604900", 3)],
    "20-86": [("ID208602200", 4)], "20-92": [("ID209200900", 2)],
    "20-99": [("ID209912100", 6)], "21-10": [("ID211010200", 2)],
    "21-24": [("ID212400900", 2)], "21-35": [("ID213505100", 2)],
    "21-43": [("ID214301700", 2)], "21-44": [("ID214403900", 3)],
    "21-54": [("ID215405900", 3)], "21-66": [("ID216607300", 2)],
    "21-92": [("ID219203200", 2)],
    "20-113": [("ID2011305000", 3)],
    "20-119": [("ID2011904400", 5)],
    "20-191": [("ID2019101000", 2)],
    "20-208": [("ID2020801600", 3)],
    "20-57": [("ID205710600", 3)],
    "20-88": [("ID208803700", 3)],
    "20-91": [("ID209106100", 3)],
    "21-21": [("ID212113300", 5)],
    "21-47": [("ID214708400", 3)],
    "21-56": [("ID215612200", 4), ("ID215612200", 5),
              ("ID215612200", 6), ("ID215612200", 7)],
    "21-93": [("ID219311800", 5)],
}


def parse_sitting(name):
    return dip.parse_protocol_xml((FIXTURES / f"plenarprotokoll-{name}.xml").read_text(encoding="utf-8"))


def source_markers(sitting, rede_id):
    """Read marker ownership directly, without using the production segment parser."""
    root = ET.parse(FIXTURES / f"plenarprotokoll-{sitting}.xml").getroot()
    rede = root.find(f".//rede[@id='{rede_id}']")
    if rede is None:
        raise AssertionError(f"source Rede {rede_id} missing from {sitting}")
    markers = []
    active = None
    for child in rede:
        if child.tag == "name":
            active = None  # chair text is not owned by the previous speaker
        elif child.tag == "p" and child.get("klasse") == "redner":
            redner = child.find("redner")
            active = redner.get("id") if redner is not None else None
            markers.append({"speaker_id": active, "speaker": dip.parse_redner(redner), "paragraphs": []})
        elif child.tag == "p" and active:
            paragraph = dip.clean_text(dip.elem_text(child))
            if paragraph:
                markers[-1]["paragraphs"].append(paragraph)
    return markers


def assert_counts(test, unit):
    test.assertEqual(unit["text"], " ".join(unit["paragraphs"]))
    test.assertEqual(unit["paragraph_count"], len(unit["paragraphs"]))
    test.assertEqual(unit["char_count"], len(unit["text"]))
    test.assertEqual(unit["snippet"], unit["text"][:240])


class OfflineV5SourceTests(unittest.TestCase):
    def test_all_reported_first_blockers_parse_from_source_xml(self):
        self.assertEqual(len(BLOCKERS), 44)
        for sitting in BLOCKERS:
            with self.subTest(sitting=sitting):
                parsed = parse_sitting(sitting)
                self.assertTrue(parsed["agenda_items"])
                self.assertEqual(parsed["xml_protocol"]["sitzung_nr"], sitting.split("-")[1])

    def test_extra_named_markers_keep_their_native_nested_speaker(self):
        cases = {
            "20-136": [("ID2013612000", 3, "11004159")],
            "20-28": [("ID202810900", 3, "11004395"), ("ID202810900", 5, "11004395")],
            "20-86": [("ID208602900", 3, "11004116")],
            "20-44": [("ID204403100", 3, "11003578")],
        }
        for sitting, targets in cases.items():
            parsed = parse_sitting(sitting)
            contributions = [c for a in parsed["agenda_items"] for c in a["contributions"]]
            for source_id, marker, speaker_id in targets:
                with self.subTest(source_id=source_id, marker=marker):
                    matches = [c for c in contributions if c.get("rede_id") == f"nested:{source_id}:{marker}"]
                    self.assertEqual(len(matches), 1)
                    self.assertEqual(matches[0]["speaker"]["xml_redner_id"], speaker_id)
                    self.assertTrue(matches[0]["paragraphs"])
                    self.assertEqual(matches[0]["text"], " ".join(matches[0]["paragraphs"]))

    def test_each_reported_marker_matches_raw_source_paragraphs_and_speaker(self):
        targets = {sitting: list(markers) for sitting, markers in BLOCKERS.items()}
        for sitting, rid, marker in [
            ("20-136", "ID2013612000", 3),
            ("20-28", "ID202810900", 3), ("20-28", "ID202810900", 5),
            ("20-86", "ID208602900", 3), ("20-44", "ID204403100", 3),
            ("21-35", "ID213505100", 2),
            ("21-66", "ID216607300", 2), ("21-66", "ID216607300", 3),
            ("21-43", "ID214301700", 1), ("21-43", "ID214301700", 2),
            ("21-43", "ID214301700", 3), ("21-43", "ID214301700", 4),
            ("21-43", "ID214301700", 5), ("21-43", "ID214301700", 6),
        ]:
            targets.setdefault(sitting, []).append((rid, marker))

        parsed_by_sitting = {}
        seen_occurrences = set()
        for sitting, cases in targets.items():
            if sitting not in parsed_by_sitting:
                parsed_by_sitting[sitting] = parse_sitting(sitting)
            parsed = parsed_by_sitting[sitting]
            for source_id, marker in cases:
                with self.subTest(sitting=sitting, source_id=source_id, marker=marker):
                    source = source_markers(sitting, source_id)[marker - 1]
                    self.assertTrue(source["paragraphs"])
                    agenda = next(a for a in parsed["agenda_items"] if
                                  any(c.get("rede_id") == f"nested:{source_id}:{marker}"
                                      for c in a["contributions"]) or
                                  any(d.get("source_rede_id") == source_id and d.get("marker_ordinal") == marker
                                      for d in a["xml_turn_diagnostics"]))
                    nested = [c for c in agenda["contributions"]
                              if c.get("rede_id") == f"nested:{source_id}:{marker}"]
                    diagnostics = [d for d in agenda["xml_turn_diagnostics"]
                                   if d.get("source_rede_id") == source_id and d.get("marker_ordinal") == marker]
                    self.assertEqual(len(nested) + len(diagnostics), 1)
                    if nested:
                        unit = nested[0]
                        self.assertEqual(unit["kind"], "zwischenfrage")
                        self.assertEqual(unit["speaker"], source["speaker"])
                        self.assertEqual(unit["speaker"]["xml_redner_id"], source["speaker_id"])
                        self.assertEqual(unit["paragraphs"], source["paragraphs"])
                        assert_counts(self, unit)
                        occurrence_id = contribution_occurrence_id(
                            f"offline-v5:{sitting}", agenda["index"], unit["sequence"], unit["rede_id"])
                        self.assertEqual(occurrence_id, contribution_occurrence_id(
                            f"offline-v5:{sitting}", agenda["index"], unit["sequence"], f"nested:{source_id}:{marker}"))
                        self.assertNotIn(occurrence_id, seen_occurrences)
                        seen_occurrences.add(occurrence_id)
                    else:
                        diagnostic = diagnostics[0]
                        self.assertEqual(diagnostic["speaker"], source["speaker"])
                        self.assertEqual(diagnostic["speaker"]["xml_redner_id"], source["speaker_id"])
                        self.assertEqual(diagnostic["text"], " ".join(source["paragraphs"]))

    def test_native_reply_paragraphs_are_exact_source_prefix_plus_native_text(self):
        for sitting, source_id, markers, reply_id in [
            ("21-35", "ID213505100", [2], "ID213505200"),
            ("21-66", "ID216607300", [2, 3], "ID216607400"),
        ]:
            parsed = parse_sitting(sitting)
            item = parsed["agenda_items"][0]
            reply = next(c for c in item["contributions"] if c.get("rede_id") == reply_id)
            raw_prefix = [p for marker in markers for p in source_markers(sitting, source_id)[marker - 1]["paragraphs"]]
            native = source_markers(sitting, reply_id)[0]["paragraphs"]
            self.assertEqual(reply["paragraphs"], raw_prefix + native)
            assert_counts(self, reply)
            occurrence_id = contribution_occurrence_id(f"offline-v5:{sitting}", item["index"], reply["sequence"], reply_id)
            self.assertEqual(occurrence_id,
                             contribution_occurrence_id(f"offline-v5:{sitting}", item["index"], reply["sequence"], reply["rede_id"]))

    def test_brandner_procedural_exchange_and_froemming_resume_match_raw_paragraphs(self):
        parsed = parse_sitting("21-43")
        item = next(a for a in parsed["agenda_items"] if any(
            s.get("rede_id") == "ID214301600" for s in a["speeches"]))
        raw_turns = source_markers("21-43", "ID214301700")
        diagnostics = {d["marker_ordinal"]: d for d in item["xml_turn_diagnostics"]
                       if d.get("source_rede_id") == "ID214301700"}
        for marker, expected_treatment in [(1, "procedural"), (2, "procedural"), (3, "procedural"),
                                           (4, "merged_rede"), (5, "merged_rede"), (6, "merged_rede")]:
            self.assertEqual(diagnostics[marker]["speaker"]["xml_redner_id"], raw_turns[marker - 1]["speaker_id"])
            self.assertEqual(diagnostics[marker]["text"], " ".join(raw_turns[marker - 1]["paragraphs"]))
            self.assertEqual(diagnostics[marker]["treatment"], expected_treatment)
        self.assertEqual(diagnostics[4]["target_rede_id"], "ID214301600")
        self.assertEqual(diagnostics[5]["target_rede_id"], "ID214301600")
        self.assertEqual(diagnostics[6]["target_rede_id"], "ID214301600")
        original = next(s for s in item["speeches"] if s.get("rede_id") == "ID214301600")
        self.assertEqual(original["paragraphs"], source_markers("21-43", "ID214301600")[0]["paragraphs"]
                         + [p for marker in (4, 5, 6) for p in raw_turns[marker - 1]["paragraphs"]])
        assert_counts(self, original)

    def test_fresh_build_and_cached_xml_reparse_preserve_diagnostics_and_occurrence_ids(self):
        class FakeClient:
            def list_all(self, path, params):
                return []

        protocol = {"id": "fixture-21-43", "dokumentnummer": "21/43", "datum": "2025-12-10"}
        raw_xml = (FIXTURES / "plenarprotokoll-21-43.xml").read_text(encoding="utf-8")
        parsed = dip.parse_protocol_xml(raw_xml)
        with contextlib.redirect_stderr(io.StringIO()):
            enrichment = dip.enrich_with_api(FakeClient(), protocol, parsed, person_limit=0, vote_scan_pages=0)
        fresh = {
            "protocol": protocol,
            "agenda_items": enrichment["agenda_items"],
            "api_records": enrichment["api_records"],
            "warnings": enrichment["warnings"],
            "validation_summary": {},
            "xml_contributions": parsed.get("sitting_contributions", []),
        }

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "site"
            cache_path = build.xml_cache_path(output_dir, "21/43")
            cache_path.parent.mkdir(parents=True)
            cache_path.write_text(raw_xml, encoding="utf-8")
            report_path, _, _ = build.report_paths(output_dir, "21/43")
            report_path.parent.mkdir(parents=True, exist_ok=True)
            stale = copy.deepcopy(fresh)
            for item in stale["agenda_items"]:
                item["xml_turn_diagnostics"] = [{"source_rede_id": "STALE"}]
            report_path.write_text(json.dumps(stale), encoding="utf-8")
            entries = build.load_existing_detail_entries(output_dir, [protocol])
            self.assertEqual(build.reparse_cached_xml(output_dir, entries), 1)
            reparsed = entries[0]["report"]

        original_fresh = next(i for i in fresh["agenda_items"] if i["top_id"] == "Einzelplan I.9")
        original_reparsed = next(i for i in reparsed["agenda_items"] if i["top_id"] == "Einzelplan I.9")
        self.assertEqual(original_reparsed["xml_turn_diagnostics"], original_fresh["xml_turn_diagnostics"])
        self.assertEqual(original_reparsed["xml_speakers"], original_fresh["xml_speakers"])
        self.assertEqual(original_reparsed["xml_contributions"], original_fresh["xml_contributions"])

        def occurrence_ids(item):
            return [contribution_occurrence_id(
                protocol["id"], item["index"], unit["sequence"], unit.get("rede_id"))
                for unit in item["xml_contributions"]]

        self.assertEqual(occurrence_ids(original_reparsed), occurrence_ids(original_fresh))
        self.assertEqual(len(occurrence_ids(original_fresh)), len(set(occurrence_ids(original_fresh))))

    def test_remaining_markers_match_source_text_identity_and_diagnostics(self):
        cases = [
            ("20-51", "ID205102700", 2, "procedural"),
            ("20-144", "ID2014400100", 7, "zwischenfrage"),
            ("20-111", "ID2011117700", 3, "zwischenfrage"),
            ("20-116", "ID2011602100", 4, "zwischenfrage"),
            ("20-175", "ID2017509500", 6, "zwischenfrage"),
            ("20-175", "ID2017509500", 8, "zwischenfrage"),
            ("21-15", "ID211500800", 3, "zwischenfrage"),
            ("21-15", "ID211500800", 6, "zwischenfrage"),
            ("21-15", "ID211500800", 8, "zwischenfrage"),
            ("21-45", "ID214504900", 3, "zwischenfrage"),
            ("21-45", "ID214504900", 6, "zwischenfrage"),
            ("21-65", "ID216510500", 4, "zwischenfrage"),
            ("20-113", "ID2011305000", 3, "procedural"),
            ("20-119", "ID2011904400", 5, "zwischenfrage"),
            ("20-144", "ID2014405100", 3, "zwischenfrage"),
            ("20-144", "ID2014405100", 4, "zwischenfrage"),
            ("20-191", "ID2019101000", 2, "procedural"),
            ("20-208", "ID2020801600", 3, "zwischenfrage"),
            ("20-51", "ID205104600", 4, "zwischenfrage"),
            ("20-57", "ID205710600", 3, "zwischenfrage"),
            ("20-88", "ID208803700", 3, "zwischenfrage"),
            ("20-91", "ID209106100", 3, "zwischenfrage"),
            ("21-21", "ID212113300", 5, "zwischenfrage"),
            ("21-47", "ID214708400", 3, "zwischenfrage"),
            ("21-47", "ID214708400", 5, "zwischenfrage"),
            ("21-56", "ID215612200", 4, "zwischenfrage"),
            ("21-56", "ID215612200", 5, "zwischenfrage"),
            ("21-56", "ID215612200", 6, "zwischenfrage"),
            ("21-56", "ID215612200", 7, "zwischenfrage"),
            ("21-93", "ID219311800", 5, "zwischenfrage"),
            ("21-93", "ID219311800", 8, "zwischenfrage"),
        ]
        parsed_by_sitting = {}
        seen_occurrences = set()
        for sitting, source_id, marker, treatment in cases:
            with self.subTest(sitting=sitting, source_id=source_id, marker=marker):
                if sitting not in parsed_by_sitting:
                    parsed_by_sitting[sitting] = parse_sitting(sitting)
                parsed = parsed_by_sitting[sitting]
                source = source_markers(sitting, source_id)[marker - 1]
                text = " ".join(source["paragraphs"])
                self.assertTrue(text)
                item = next(a for a in parsed["agenda_items"] if
                            any(c.get("rede_id") == f"nested:{source_id}:{marker}"
                                for c in a["contributions"]) or
                            any(d.get("source_rede_id") == source_id and d.get("marker_ordinal") == marker
                                for d in a["xml_turn_diagnostics"]))
                nested = [c for c in item["contributions"] if c.get("rede_id") == f"nested:{source_id}:{marker}"]
                diagnostics = [d for d in item["xml_turn_diagnostics"]
                               if d.get("source_rede_id") == source_id and d.get("marker_ordinal") == marker]
                self.assertEqual(len(nested) + len(diagnostics), 1)
                if treatment == "procedural":
                    diagnostic = diagnostics[0]
                    self.assertEqual(diagnostic["treatment"], treatment)
                    self.assertEqual(diagnostic["speaker"], source["speaker"])
                    self.assertEqual(diagnostic["speaker"]["xml_redner_id"], source["speaker_id"])
                    self.assertEqual(diagnostic["text"], text)
                    self.assertEqual(len(diagnostic["text"]), len(text))
                    continue
                unit = nested[0]
                self.assertEqual(unit["kind"], treatment)
                self.assertEqual(unit["speaker"], source["speaker"])
                self.assertEqual(unit["parent_rede_id"], source_id)
                self.assertEqual(unit["speaker"]["xml_redner_id"], source["speaker_id"])
                self.assertEqual(unit["paragraphs"], source["paragraphs"])
                self.assertEqual(unit["text"], text)
                assert_counts(self, unit)
                self.assertEqual(len(unit["text"]), len(text))
                occurrence_id = contribution_occurrence_id(
                    f"offline-v5:{sitting}", item["index"], unit["sequence"], unit["rede_id"])
                self.assertEqual(unit["rede_id"], f"nested:{source_id}:{marker}")
                self.assertNotIn(occurrence_id, seen_occurrences)
                seen_occurrences.add(occurrence_id)

    def test_adjacent_procedural_replies_keep_native_kinds_and_ownership(self):
        for sitting, rede_id, kind, speaker_id in [
            ("20-113", "ID2011305100", "kurzintervention", "11004678"),
            ("20-113", "ID2011305200", "erwiderung", "11005192"),
            ("20-191", "ID2019101100", "erwiderung", "11003231"),
        ]:
            parsed = parse_sitting(sitting)
            matches = [c for a in parsed["agenda_items"] for c in a["contributions"]
                       if c.get("rede_id") == rede_id]
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["kind"], kind)
            self.assertEqual(matches[0]["speaker"]["xml_redner_id"], speaker_id)
            self.assertEqual(matches[0]["paragraphs"], [p for m in source_markers(sitting, rede_id)
                                                      if m["speaker_id"] == speaker_id for p in m["paragraphs"]])
            assert_counts(self, matches[0])

    def test_new_procedural_cases_survive_fresh_build_and_cached_xml_reparse(self):
        class FakeClient:
            def list_all(self, path, params):
                return []

        for sitting, protocol_id, document_number, date, source_id, marker in [
            ("20-113", "fixture-20-113", "20/113", "2024-09-11", "ID2011305000", 3),
            ("20-191", "fixture-20-191", "20/191", "2025-06-25", "ID2019101000", 2),
        ]:
            protocol = {"id": protocol_id, "dokumentnummer": document_number, "datum": date}
            raw_xml = (FIXTURES / f"plenarprotokoll-{sitting}.xml").read_text(encoding="utf-8")
            parsed = dip.parse_protocol_xml(raw_xml)
            with contextlib.redirect_stderr(io.StringIO()):
                enrichment = dip.enrich_with_api(FakeClient(), protocol, parsed, person_limit=0, vote_scan_pages=0)
            fresh = {
                "protocol": protocol,
                "agenda_items": enrichment["agenda_items"],
                "api_records": enrichment["api_records"],
                "warnings": enrichment["warnings"],
                "validation_summary": {},
                "xml_contributions": parsed.get("sitting_contributions", []),
            }
            with tempfile.TemporaryDirectory() as tmp:
                output_dir = Path(tmp) / "site"
                cache_path = build.xml_cache_path(output_dir, document_number)
                cache_path.parent.mkdir(parents=True)
                cache_path.write_text(raw_xml, encoding="utf-8")
                report_path, _, _ = build.report_paths(output_dir, document_number)
                report_path.parent.mkdir(parents=True, exist_ok=True)
                stale = copy.deepcopy(fresh)
                for item in stale["agenda_items"]:
                    item["xml_turn_diagnostics"] = [{"source_rede_id": "STALE"}]
                report_path.write_text(json.dumps(stale), encoding="utf-8")
                entries = build.load_existing_detail_entries(output_dir, [protocol])
                self.assertEqual(build.reparse_cached_xml(output_dir, entries), 1)
                reparsed = entries[0]["report"]

            def target(report):
                return next(item for item in report["agenda_items"] if any(
                    diagnostic.get("source_rede_id") == source_id
                    and diagnostic.get("marker_ordinal") == marker
                    for diagnostic in item["xml_turn_diagnostics"]))

            fresh_item, reparsed_item = target(fresh), target(reparsed)
            diagnostics = [d for d in fresh_item["xml_turn_diagnostics"]
                           if d.get("source_rede_id") == source_id and d.get("marker_ordinal") == marker]
            self.assertEqual(len(diagnostics), 1)
            self.assertEqual(diagnostics[0]["treatment"], "procedural")
            self.assertEqual(target(reparsed)["xml_turn_diagnostics"], fresh_item["xml_turn_diagnostics"])
            self.assertEqual(reparsed_item["xml_speakers"], fresh_item["xml_speakers"])
            self.assertEqual(reparsed_item["xml_contributions"], fresh_item["xml_contributions"])
            ids = [contribution_occurrence_id(protocol_id, fresh_item["index"], unit["sequence"], unit.get("rede_id"))
                   for unit in fresh_item["xml_contributions"]]
            reparsed_ids = [contribution_occurrence_id(protocol_id, reparsed_item["index"], unit["sequence"], unit.get("rede_id"))
                            for unit in reparsed_item["xml_contributions"]]
            self.assertEqual(reparsed_ids, ids)
            self.assertEqual(len(ids), len(set(ids)))

    def test_native_replies_are_counted_once_and_interruption_diagnostics_keep_source(self):
        for sitting, reply_id in [("21-35", "ID213505200"), ("21-66", "ID216607400")]:
            with self.subTest(reply_id=reply_id):
                parsed = parse_sitting(sitting)
                native = [c for a in parsed["agenda_items"] for c in a["contributions"]
                          if c.get("rede_id") == reply_id]
                self.assertEqual(len(native), 1)
                item = next(a for a in parsed["agenda_items"] if any(
                    d.get("source_rede_id") == ("ID213505100" if sitting == "21-35" else "ID216607300")
                    for d in a["xml_turn_diagnostics"]))
                source_id = "ID213505100" if sitting == "21-35" else "ID216607300"
                expected_markers = {2} if sitting == "21-35" else {2, 3}
                diagnostics = [d for d in item["xml_turn_diagnostics"]
                               if d.get("source_rede_id") == source_id]
                self.assertEqual({d["marker_ordinal"] for d in diagnostics}, expected_markers)
                self.assertTrue(all(d["treatment"] == "merged_erwiderung"
                                    and d.get("target_rede_id") == reply_id for d in diagnostics))

        parsed = parse_sitting("21-43")
        item = next(a for a in parsed["agenda_items"] if any(
            s.get("rede_id") == "ID214301600" for s in a["speeches"]))
        original = [s for s in item["speeches"] if s.get("rede_id") == "ID214301600"]
        self.assertEqual(len(original), 1)
        original_text = " ".join(original[0]["paragraphs"])
        self.assertIn("Vielen Dank, Frau Präsidentin.", original_text)
        self.assertIn("Ich komme zum Ende.", original_text)
        self.assertIn("ohne am Ende wie der Dorfrichter Adam", original_text)
        self.assertNotIn("beantrage ich für die AfD-Fraktion", original_text)
        diagnostics = item["xml_turn_diagnostics"]
        self.assertTrue(diagnostics)
        by_marker = {d["marker_ordinal"]: d for d in diagnostics
                     if d.get("source_rede_id") == "ID214301700"}
        self.assertEqual(set(by_marker), {1, 2, 3, 4, 5, 6})
        self.assertEqual(by_marker[1]["treatment"], "procedural")
        self.assertEqual(by_marker[2]["treatment"], "procedural")
        self.assertEqual(by_marker[3]["treatment"], "procedural")
        for marker in (4, 5, 6):
            self.assertEqual(by_marker[marker]["treatment"], "merged_rede")
            self.assertEqual(by_marker[marker].get("target_rede_id"), "ID214301600")
            self.assertIn(by_marker[marker]["text"], original_text)
        for diagnostic in diagnostics:
            self.assertTrue({"source_rede_id", "marker_ordinal", "speaker", "text", "evidence", "treatment"}
                            <= diagnostic.keys())


if __name__ == "__main__":
    unittest.main()
