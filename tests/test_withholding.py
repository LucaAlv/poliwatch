"""Withholding refused Reden (coverage gate PR 2, ADR 0005,
docs/plans/coverage-gate-pr2.md): a Rede the parser cannot read, or one on the
reviewed list, is held back with its reason and text, outside every count, and
the rest of the sitting is kept unchanged."""
import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

import _support
import build_dip_pulse_site as build
import check_withhold_one
import persist_dip_pulse_store as store
import publish_dip_pulse_data as publish
import release_changes
import render_dip_pulse_html as html
import reviewed_units
import speech_kinds as sk
import validate_dip_protocol as dip

ASKER = '<p klasse="redner"><redner id="B"><name><nachname>Gast</nachname><fraktion>Grüne</fraktion></name></redner></p>'


def owner(rid, last="Haupt"):
    return f'<p klasse="redner"><redner id="{rid}-r"><name><nachname>{last}</nachname><fraktion>SPD</fraktion></name></redner></p>'


def rede(rid, last="Haupt", nested=""):
    return f'<rede id="{rid}">{owner(rid, last)}<p klasse="J">Rede von {last}.</p>{nested}</rede>'


GRANTED = ASKER + '<p>Herzlichen Dank, dass Sie die Frage zulassen. Ich wollte Sie fragen, ob das stimmt?</p>'
REFUSED = ASKER + '<p>Herzlichen Dank, dass Sie die Frage nicht zulassen. Eine Bemerkung</p>'


def sitting(*reden, number="7"):
    return (f'<dbtplenarprotokoll wahlperiode="18" sitzung-nr="{number}"><sitzungsverlauf>'
            f'<tagesordnungspunkt top-id="T1"><p klasse="T_NaS">Beratung</p>{"".join(reden)}</tagesordnungspunkt>'
            '</sitzungsverlauf><anlagen/></dbtplenarprotokoll>')


def report(parsed, number="18/7"):
    return {"protocol": {"id": number, "dokumentnummer": number, "datum": "2015-04-23",
                         "reviewed_digest": parsed["reviewed_digest"]},
            "agenda_items": [dict(index=t["index"], **dip.xml_top_fields(t)) for t in parsed["agenda_items"]],
            "xml_contributions": parsed.get("sitting_contributions", []),
            "validation_summary": dip.contribution_summary(parsed["agenda_items"], parsed.get("sitting_contributions"))}


def entry(rid, redner="", sitting_number="18/7"):
    return {"sitting": sitting_number, "rede_id": rid, "redner_id": redner or f"{rid}-r", "kind": "withhold", "reason": "Test."}


class ParserTests(unittest.TestCase):
    # Value: protects=a located refusal withholds only its Rede; the others keep id, sequence and text;
    #   fails_when=the refusal still refuses the sitting, or a neighbour renumbers; why_new=no withholding before; seam=none
    def test_a_located_refusal_withholds_its_rede_and_keeps_the_rest(self):
        parsed = dip.parse_protocol_xml(sitting(rede("R1"), rede("R2", "Zwei", REFUSED), rede("R3", "Drei", GRANTED)))
        top = parsed["agenda_items"][0]
        self.assertEqual([(s["rede_id"], s["sequence"]) for s in top["speeches"]], [("R1", 1), ("R3", 3)])
        [held] = top["withheld"]
        self.assertEqual((held["rede_id"], held["sequence"], held["reason"]), ("R2", 2, "refused_nested_contribution"))
        self.assertIn("unresolved nested contribution at R2 marker 2", held["reason_detail"])
        self.assertEqual(held["text"], "Rede von Zwei.")
        self.assertEqual(held["word_count"], 3)
        self.assertEqual([(t["marker"], t["speaker"]["last_name"]) for t in held["nested_turns"]], [(2, "Gast")])
        self.assertEqual(held["nested_word_count"], 10)
        self.assertEqual([c["rede_id"] for c in top["contributions"]], ["nested:R3:2"])
        self.assertEqual(parsed["agenda_items"][0]["speeches"][1]["text"], "Rede von Drei.")
        self.assertEqual(dip.contribution_summary(parsed["agenda_items"])["withheld_rede_count"], 1)
        self.assertEqual(dip.contribution_summary(parsed["agenda_items"])["withheld_word_count"], 3)

    # Value: protects=the refusal is caught by type, so a withheld Rede is never confused with a refused sitting;
    #   fails_when=either located site raises a plain ValueError; why_new=new type; seam=none
    def test_located_refusals_are_typed(self):
        self.assertTrue(issubclass(dip.LocatedRefusal, ValueError))
        self.assertFalse(issubclass(reviewed_units.ReviewedUnitsError, ValueError))
        source = Path(dip.__file__).read_text(encoding="utf-8")
        self.assertEqual(source.count('reason="refused_nested_contribution"'), 1)
        self.assertEqual(source.count('reason="refused_nested_question_speaker"'), 1)

    # Value: protects=a Rede withheld after it emitted nested units leaves none behind (commit on finish);
    #   fails_when=nested units or same-asker merges of the withheld Rede reach the TOP; why_new=new path; seam=none
    def test_a_withheld_rede_leaves_no_nested_unit_or_merge_diagnostic(self):
        nested = (GRANTED + owner("R2", "Zwei") + '<p>Antwort.</p>' + ASKER + '<p>Und noch eine Frage dazu?</p>'
                  + '<p klasse="redner"><redner id="C"><name><nachname>Andere</nachname><fraktion>FDP</fraktion></name></redner></p>'
                  '<p>Eine Bemerkung ohne Fragezeichen.</p>')
        good = dip.parse_protocol_xml(sitting(rede("R1"), rede("R2", "Zwei", GRANTED + owner("R2", "Zwei") + '<p>Antwort.</p>'
                                                                + ASKER + '<p>Und noch eine Frage dazu?</p>')))
        self.assertIn("merged_zwischenfrage", [d["treatment"] for d in good["agenda_items"][0]["xml_turn_diagnostics"]])
        parsed = dip.parse_protocol_xml(sitting(rede("R1"), rede("R2", "Zwei", nested)))
        top = parsed["agenda_items"][0]
        self.assertEqual([w["rede_id"] for w in top["withheld"]], ["R2"])
        self.assertEqual(top["contributions"], [])
        self.assertNotIn("merged_zwischenfrage", [d["treatment"] for d in top["xml_turn_diagnostics"]])

    # Value: protects=D4: a refused split part is withheld alone, the outer Rede stays stored (real 18/10 source);
    #   fails_when=the whole outer Rede is withheld or the part vanishes; why_new=new path; seam=none
    def test_a_refused_split_part_is_withheld_alone(self):
        parsed = dip.parse_protocol_xml((_support.ROOT / "tests/fixtures/withholding/18-10-top3.xml").read_text(encoding="utf-8"), reviewed=[])
        top = parsed["agenda_items"][0]
        self.assertEqual([s["rede_id"] for s in top["speeches"]], ["ID1801002600"])
        [held] = top["withheld"]
        self.assertEqual((held["rede_id"], held["sequence"], held["reason"]), ("ID1801002600:2", 2, "refused_nested_contribution"))
        self.assertEqual((held["word_count"], held["nested_word_count"]), (608, 123))
        # The part is the main speaker's text after the split; the Kurzintervention inside it stays apart.
        self.assertEqual(held["speaker"]["last_name"], "Bartz")
        self.assertEqual([(t["marker"], t["speaker"]["last_name"]) for t in held["nested_turns"]], [(4, "Liebich")])

    # Value: protects=D7: text pass 1 gave to the previous Rede stays there when the resumed Rede is withheld, and
    #   text merged into a withheld Rede goes with it; fails_when=the moved words are lost or counted twice; why_new=new rule; seam=reviewed
    def test_moved_text_follows_the_d7_rule(self):
        xml = (_support.FIXTURES / "offline-v5/plenarprotokoll-21-43.xml").read_text(encoding="utf-8")
        base = dip.parse_protocol_xml(xml, reviewed=[])
        top = next(t for t in base["agenda_items"] if any(d["treatment"] == "merged_rede" for d in t["xml_turn_diagnostics"]))
        original = next(s for s in top["speeches"] if s["rede_id"] == "ID214301600")
        resumed = dip.parse_protocol_xml(xml, reviewed=[entry("ID214301700", "", "21/43") | {"redner_id": self._owner(xml, "ID214301700")}])
        top_r = resumed["agenda_items"][top["index"] - 1]
        self.assertEqual(next(s for s in top_r["speeches"] if s["rede_id"] == "ID214301600")["text"], original["text"])
        [held] = top_r["withheld"]
        self.assertEqual((held["rede_id"], held["text"]), ("ID214301700", ""))
        self.assertNotIn(original["text"][-40:], " ".join(t["text"] for t in held["nested_turns"]))
        target = dip.parse_protocol_xml(xml, reviewed=[entry("ID214301600", "", "21/43") | {"redner_id": self._owner(xml, "ID214301600")}])
        [held] = target["agenda_items"][top["index"] - 1]["withheld"]
        self.assertEqual(held["text"], original["text"])

    # Value: protects=the Befragung's located refusal withholds its Rede too, by its own reason code;
    #   fails_when=the question-speaker site raises a plain ValueError again; why_new=only counted in source before; seam=none
    def test_an_unresolved_question_speaker_is_withheld(self):
        minister = ('<p klasse="redner"><redner id="M"><name><vorname>Eva</vorname><nachname>Minister</nachname><rolle>'
                    '<rolle_lang>Bundesministerin für Arbeit</rolle_lang><rolle_kurz>Bundesministerin</rolle_kurz></rolle></name></redner></p>')
        xml = sitting(f'<rede id="R1">{minister}<p>Einleitung.</p>'
                      '<p klasse="redner"><redner id="X"><name><nachname>Ohne</nachname></name></redner></p><p>Eine Frage?</p></rede>'
                      ).replace("<p klasse=\"T_NaS\">Beratung</p>", "<p klasse=\"T_NaS\">Befragung der Bundesregierung</p>")
        [held] = dip.parse_protocol_xml(xml, reviewed=[])["agenda_items"][0]["withheld"]
        self.assertEqual((held["rede_id"], held["reason"]), ("R1", "refused_nested_question_speaker"))
        self.assertIn("unresolved nested question-format speaker at R1 marker 2", held["reason_detail"])

    # Value: protects=a withheld Rede reconciles as withheld, and a Rede left with no status still refuses the sitting;
    #   fails_when=withholding skips record_status or the reconciliation stops checking; why_new=PR 1 had no withheld status; seam=none
    def test_a_withheld_rede_reconciles_and_a_missing_status_still_refuses(self):
        parsed = dip.parse_protocol_xml(sitting(rede("R1"), rede("R2", "Zwei", REFUSED)), reviewed=[])
        self.assertEqual([w["rede_id"] for w in parsed["agenda_items"][0]["withheld"]], ["R2"])
        with self.assertRaisesRegex(dip.ReconciliationError, "R2 \\(TOP T1\\) has no status"):
            dip.reconcile_reden("18/7", {"R1": "TOP T1", "R2": "TOP T1"}, {"R1": "speech"}, set())
        dip.reconcile_reden("18/7", {"R1": "TOP T1", "R2": "TOP T1"}, {"R1": "speech", "R2": sk.WITHHELD_STATUS}, set())

    # Value: protects=re-reading a cached report from its XML withholds exactly what a fresh build withholds (the list is a
    #   repository file); fails_when=the offline replay drops xml_withheld or the digest; why_new=new report fields; seam=none
    def test_replay_equals_fresh(self):
        xml = sitting(rede("R1"), rede("R2", "Zwei", REFUSED))
        fresh = report(dip.parse_protocol_xml(xml, reviewed=[entry("R1")]))
        cached = report(dip.parse_protocol_xml(sitting(rede("R1"), rede("R2", "Zwei")), reviewed=[]))
        dip.reparse_report_xml(cached, dip.parse_protocol_xml(xml, reviewed=[entry("R1")]))
        self.assertEqual(cached["agenda_items"][0]["xml_withheld"], fresh["agenda_items"][0]["xml_withheld"])
        self.assertEqual(cached["protocol"]["reviewed_digest"], fresh["protocol"]["reviewed_digest"])
        self.assertEqual(cached["validation_summary"]["withheld_rede_count"], 2)

    @staticmethod
    def _owner(xml, rid):
        rede_element = next(r for r in dip.ET.fromstring(xml).iter("rede") if r.get("id") == rid)
        return dip.derive.first_redner_id(rede_element.find("./p[@klasse='redner']/redner").get("id"))


class ReviewedListTests(unittest.TestCase):
    # Value: protects=a listed unit is withheld with reason reviewed, even when it parses; fails_when=the list is ignored; why_new=new list; seam=reviewed
    def test_a_listed_rede_is_withheld(self):
        parsed = dip.parse_protocol_xml(sitting(rede("R1"), rede("R2", "Zwei")), reviewed=[entry("R1")])
        top = parsed["agenda_items"][0]
        self.assertEqual([s["rede_id"] for s in top["speeches"]], ["R2"])
        self.assertEqual([(w["rede_id"], w["reason"], w["reason_detail"]) for w in top["withheld"]], [("R1", "reviewed", "Test.")])
        self.assertEqual(parsed["reviewed_digest"], reviewed_units.digest([entry("R1")]))

    # Value: protects=a stale or misapplied entry stops the run with the entry named, never a silent no-op;
    #   fails_when=an unmatched id, a wrong owner or an annex id is skipped; why_new=new list; seam=reviewed
    def test_a_stale_or_misapplied_entry_refuses(self):
        annex = ('<anlage><anlagen-text anlagen-typ="Zu Protokoll gegebene Reden">'
                 f'{rede("A1", "Schrift")}</anlagen-text></anlage>')
        cases = {"missing": (sitting(rede("R1")), [entry("R9")], "R9, which names no Rede"),
                 "owner": (sitting(rede("R1")), [entry("R1", "OTHER")], "names Redner-ID OTHER"),
                 "annex": (sitting(rede("R1")).replace("<anlagen/>", f"<anlagen>{annex}</anlagen>"), [entry("A1")], "annex Rede")}
        for label, (xml, entries, message) in cases.items():
            with self.subTest(label), self.assertRaisesRegex(reviewed_units.ReviewedUnitsError, message):
                dip.parse_protocol_xml(xml, reviewed=entries)

    # Value: protects=a malformed list stops the run before any sitting; fails_when=a shape slips through; why_new=new file; seam=path
    def test_a_malformed_list_refuses_whole(self):
        good = {"sitting": "18/7", "rede_id": "R1", "redner_id": "1", "kind": "withhold", "reason": "x"}
        bad = {"not an object": [], "extra key": {"entries": [], "x": 1}, "missing field": {"entries": [{**good, "reason": None}]},
               "unknown kind": {"entries": [{**good, "kind": "ansprache"}]}, "bad sitting": {"entries": [{**good, "sitting": "18-7"}]},
               "bad id": {"entries": [{**good, "rede_id": "R 1"}]}, "twice": {"entries": [good, good]}}
        with tempfile.TemporaryDirectory() as tmp:
            for label, payload in bad.items():
                path = Path(tmp) / f"{label}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.subTest(label), self.assertRaises(reviewed_units.ReviewedUnitsError):
                    reviewed_units.load(path)

    # Value: protects=the 86 shipped exclusion reasons load through the real loader, every one with a known code;
    #   fails_when=the file drifts from the loader's shape and the owner's store refuses on its next run; why_new=W5; seam=none
    def test_the_shipped_exclusion_record_loads(self):
        record = _support.ROOT / "docs/plans/coverage-gate-pr2/coverage-exclusions.json"
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "data").mkdir()
            (Path(tmp) / "data" / build.COVERAGE_EXCLUSIONS_FILENAME).write_bytes(record.read_bytes())
            entries = build.load_coverage_exclusions(Path(tmp))
        self.assertEqual(len(entries), 86)
        by_reason = {}
        for row in entries:
            by_reason.setdefault(row["reason"], []).append(row["document_number"])
        self.assertEqual(by_reason["source_defect"], ["18/20"])
        self.assertEqual(len(by_reason["awaiting_rule"]), 13)
        self.assertIn("19/36", by_reason["awaiting_rule"])

    # Value: protects=the committed list loads and each N7 entry names its sitting's real unit (W8);
    #   fails_when=an entry is malformed or its owner drifts; why_new=new entries; seam=none
    def test_the_committed_list_is_well_formed(self):
        entries = reviewed_units.load(_support.ROOT / "scripts/reviewed_units.json")
        self.assertEqual(sorted(entries), ["18/2", "18/29", "18/83", "19/25"])
        self.assertEqual(sum(len(v) for v in entries.values()), 5)

    # Value: protects=the digest names a sitting's entries regardless of order, and changes with any field;
    #   fails_when=reordering or rewording leaves the store stale silently; why_new=R3; seam=none
    def test_the_digest_is_order_free_and_field_sensitive(self):
        a, b = entry("R1"), entry("R2")
        self.assertEqual(reviewed_units.digest([a, b]), reviewed_units.digest([b, a]))
        self.assertNotEqual(reviewed_units.digest([a]), reviewed_units.digest([{**a, "reason": "Anders."}]))
        self.assertNotEqual(reviewed_units.digest([]), reviewed_units.digest([a]))


    # Value: protects=R3 offline: a cached report parsed under other reviewed entries than the file holds for its sitting is re-read from XML, one under the current entries is not;
    #   fails_when=unparsed_reports ignores reviewed_digest (a list edit leaves a published Rede counted) or flags every report; why_new=test_a_changed_reviewed_list covers the store, not the cache; seam=none
    def test_a_cached_report_under_other_reviewed_entries_is_reread(self):
        def cached(number, digest, version=sk.VERSION):
            return {"report": {"protocol": {"dokumentnummer": number, "reviewed_digest": digest}, "validation_summary": {"speech_kinds_version": version}}}
        listed, unlisted = "18/2", "18/7"
        fresh = [cached(listed, reviewed_units.sitting_digest(listed)), cached(unlisted, reviewed_units.digest([]))]
        self.assertEqual(build.unparsed_reports(fresh), [])
        stale = [cached(listed, reviewed_units.digest([])), cached(unlisted, reviewed_units.digest([entry("R1")])),
                 cached(unlisted, reviewed_units.digest([]), version=sk.VERSION - 1)]
        self.assertEqual(build.unparsed_reports(stale), stale)


class StoreTests(unittest.TestCase):
    def persisted(self, xml, reviewed=None, number="18/7"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "store.sqlite"
        conn = store.connect(path)
        self.addCleanup(conn.close)
        store.persist_report(conn, report(dip.parse_protocol_xml(xml, reviewed=reviewed), number))
        return conn

    # Value: protects=a withheld Rede is stored with its turns, bound to no person, outside speeches and contributions;
    #   fails_when=it reaches a count, binds an MP, or its turns are lost; why_new=D2/R2 tables; seam=none
    def test_a_withheld_rede_is_stored_apart_and_bound_to_no_person(self):
        conn = self.persisted(sitting(rede("R1"), rede("R2", "Zwei", REFUSED), rede("R3", "Drei")), reviewed=[])
        self.assertEqual([tuple(r) for r in conn.execute("SELECT rede_id, sequence FROM speeches ORDER BY sequence")], [("R1", 1), ("R3", 3)])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM contributions").fetchone()[0], 0)
        row = conn.execute("SELECT rede_id, sequence, reason, xml_redner_id, speaker_name, fraktion, word_count, nested_word_count, text "
                           "FROM withheld_units").fetchone()
        self.assertEqual(tuple(row), ("R2", 2, "refused_nested_contribution", "R2-r", "Zwei", "SPD", 3, 10, "Rede von Zwei."))
        self.assertEqual([tuple(r) for r in conn.execute("SELECT marker, xml_redner_id, speaker_name, word_count FROM withheld_turns")],
                         [(2, "B", "Gast", 10)])
        # Two stored Reden bind two people; the withheld Rede and its turn bind none.
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM person_bindings").fetchone()[0], 2)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM person_bindings WHERE id LIKE 'withheld%'").fetchone()[0], 0)

    # Value: protects=R3: a store persisted under other reviewed entries than the file holds is refused downstream;
    #   fails_when=a list edit leaves a published Rede counted; why_new=R3; seam=none
    def test_a_changed_reviewed_list_makes_the_store_stale(self):
        conn = self.persisted(sitting(rede("R1")), reviewed=[], number="18/2")
        with self.assertRaisesRegex(RuntimeError, "18/2 predate the current scripts/reviewed_units.json"):
            store.require_current_speech_rules(conn)
        conn.execute("UPDATE speech_rule_inputs SET reviewed_digest = ?", (reviewed_units.sitting_digest("18/2"),))
        store.require_current_speech_rules(conn)

    # Value: protects=a schema 11 store (speech_rule_inputs without reviewed_digest) is refused with the repersist instruction, never stamped 12 with no withheld Reden;
    #   fails_when=require_current_schema stops checking reviewed_digest; why_new=schema 12 is new; seam=none
    def test_a_schema_11_store_without_reviewed_digest_is_refused(self):
        conn = self.persisted(sitting(rede("R1")), reviewed=[])
        store.require_current_schema(conn)
        conn.execute("ALTER TABLE speech_rule_inputs DROP COLUMN reviewed_digest")
        with self.assertRaisesRegex(RuntimeError, "Old build-store schema.*--offline --repersist"):
            store.require_current_schema(conn)

    # Value: protects=D5: the run summary names every withheld Rede the new store adds, and the ones it releases;
    #   fails_when=a new withheld Rede passes silently; why_new=D5; seam=none
    def test_the_run_summary_lists_newly_withheld_reden(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, new = Path(tmp) / "old.sqlite", Path(tmp) / "new.sqlite"
            for path, xml in ((old, sitting(rede("R1"), rede("R2", "Zwei"))), (new, sitting(rede("R1"), rede("R2", "Zwei", REFUSED)))):
                conn = store.connect(path)
                store.persist_report(conn, report(dip.parse_protocol_xml(xml, reviewed=[])))
                conn.close()
            lines = build.newly_withheld_lines(old, new)
            self.assertIn("[summary] 1 newly withheld Rede(n)", lines[0])
            self.assertIn("18/7 R2, Zwei (SPD): refused_nested_contribution", lines[1])
            self.assertIn("1 Rede(n) no longer withheld: 18/7 R2", build.newly_withheld_lines(new, old)[0])
            self.assertEqual(build.newly_withheld_lines(Path(tmp) / "missing.sqlite", old), [])


class OutputTests(unittest.TestCase):
    # Value: protects=the data dictionary lists exactly the parser's reason codes; fails_when=a code is added on one side; why_new=red flag 8; seam=none
    def test_reason_codes_match_the_data_dictionary(self):
        dictionary = json.loads((_support.SCRIPTS / "data_dictionary.json").read_text(encoding="utf-8"))
        unit = dictionary["tables"]["withheld_units"]["columns"]["reason"]["unit"]
        self.assertEqual(unit, "Einer der Codes " + ", ".join(sk.WITHHELD_REASONS) + ".")
        self.assertEqual(set(dip.WITHHELD_REASONS), set(sk.WITHHELD_REASONS))

    # Value: protects=the Dossier names a withheld Rede, its speaker and reason, instead of dropping a speaker;
    #   fails_when=the line is missing or an all-withheld TOP reads "Keine Reden im XML"; why_new=new line; seam=none
    def test_the_dossier_names_a_withheld_rede(self):
        parsed = dip.parse_protocol_xml(sitting(rede("R2", "Zwei", REFUSED)), reviewed=[])
        item = dip.xml_top_fields(parsed["agenda_items"][0])
        line = html.render_top_withheld(item)
        self.assertIn("Zurückgehalten, nicht mitgezählt (1 Rede): Zwei (SPD): ein Beitrag eines anderen Redners", line)
        self.assertEqual(html.render_top_withheld({"xml_withheld": []}), "")
        # A TOP whose only Rede is withheld says so instead of "Keine Reden im XML".
        self.assertIn("Keine gezählten Reden; zurückgehaltene Reden siehe oben",
                      html.render_speech_details(item, {"speech_count": 0, "total_chars": 0, "speakers": []}))

    # Value: protects=D5/D9 end to end: a release names each newly withheld Rede and refuses more than the cap unless
    #   each is confirmed; an older manifest without the list counts as none; fails_when=the layers do not hand data on; why_new=R4; seam=none
    def test_the_release_lists_and_caps_newly_withheld_reden(self):
        units = [{"document_number": "18/7", "rede_id": f"R{i}", "reason": "refused_nested_contribution"} for i in range(1, 4)]
        previous = {"tag": "2026.11.01", "export_format": 16}
        for count, expect_problem in ((1, False), (3, True)):
            manifest = {"tag": "2026.11.02", "export_format": 17, "withheld_reden": units[:count]}
            changes = release_changes.assemble(version="2026.11.02", released=date(2026, 11, 2), manifest=manifest,
                                               previous_manifest=previous, authored={"summary": "Test.", "schema_changes": [
                                                   {"table": "withheld_units", "column": None, "change": "table-added", "description": "x"}]})
            self.assertEqual(len(changes["withheld_reden_added"]), count)
            problem = publish.withheld_cap_problem(changes, [])
            self.assertEqual(bool(problem), expect_problem)
            if expect_problem:
                self.assertIn("18/7:R1, 18/7:R2, 18/7:R3", problem)
                self.assertIsNone(publish.withheld_cap_problem(changes, ["18/7:R1", "18/7:R2", "18/7:R3"]))
                self.assertIn("neu zurückgehalten: 18/7 R3", release_changes.render_markdown(changes))
        initial = release_changes.assemble(version="2026.11.02", released=date(2026, 11, 2),
                                           manifest={"tag": "2026.11.02", "withheld_reden": units}, previous_manifest=None, authored=None)
        self.assertIsNone(publish.withheld_cap_problem(initial, []))

    # Value: protects=D9 boundary: exactly the cap passes unconfirmed, a partial confirmation names only the missing Rede, and a release shows what it lets go;
    #   fails_when=the cap is off by one, one confirmation excuses all, or the released line is dropped; why_new=the table test covers 1 and 3 with no or full confirmation; seam=none; no_claim=run_release wiring (test_publish)
    def test_the_release_cap_boundary_and_partial_confirmation(self):
        units = [{"document_number": "18/7", "rede_id": f"R{i}", "reason": "refused_nested_contribution"} for i in range(1, 4)]
        previous = {"tag": "2026.11.01", "export_format": 17, "withheld_reden": [units[2]]}

        def assemble(current):
            return release_changes.assemble(version="2026.11.02", released=date(2026, 11, 2),
                                            manifest={"tag": "2026.11.02", "export_format": 17, "withheld_reden": current},
                                            previous_manifest={**previous, "withheld_reden": previous["withheld_reden"]}, authored={"summary": "Test."})
        at_cap = assemble(units[:2] + [units[2]])
        self.assertEqual([u["rede_id"] for u in at_cap["withheld_reden_added"]], ["R1", "R2"])
        self.assertIsNone(publish.withheld_cap_problem(at_cap, []))
        over = release_changes.assemble(version="2026.11.02", released=date(2026, 11, 2),
                                        manifest={"tag": "2026.11.02", "export_format": 17, "withheld_reden": units},
                                        previous_manifest={"tag": "2026.11.01", "export_format": 17, "withheld_reden": []}, authored={"summary": "Test."})
        problem = publish.withheld_cap_problem(over, ["18/7:R1", "18/7:R2"])
        self.assertIn("for: 18/7:R3", problem)
        self.assertNotIn("18/7:R1,", problem.split("for:")[1])
        released = assemble([units[0]])
        self.assertEqual([u["rede_id"] for u in released["withheld_reden_released"]], ["R3"])
        self.assertIn("nicht mehr zurückgehalten: 18/7 R3", release_changes.render_markdown(released))

class WithholdOneTests(unittest.TestCase):
    # Value: protects=the D6 check catches a change to any other unit and passes an untouched sitting;
    #   fails_when=compare() misses a moved neighbour; why_new=W6 script; seam=none
    def test_compare_flags_only_unexplained_changes(self):
        xml = sitting(rede("R1"), rede("R2", "Zwei", GRANTED), rede("R3", "Drei"))
        result = check_withhold_one.check_sitting(xml)
        self.assertEqual(result["middle"], {"withheld": 1, "problems": []})
        base = dip.parse_protocol_xml(xml, reviewed=[])
        forced = dip.parse_protocol_xml(xml, reviewed=[entry("R2", "", "18/7")])
        forced["agenda_items"][0]["speeches"][0]["text"] = "verändert"
        self.assertEqual(check_withhold_one.compare(base, forced, {1: "R2"}), ["T1 R1: text changed"])


if __name__ == "__main__":
    unittest.main()
