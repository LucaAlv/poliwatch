"""Reden the source prints outside any <tagesordnungspunkt> (18/49, 18/44).

The fixtures are the real XML, every Rede cut to its Redner line and first paragraph.
"""
import copy
from pathlib import Path
import tempfile
import unittest

import _support
import build_dip_pulse_site as site
import validate_dip_protocol as dip

FIXTURES = _support.FIXTURES / "reden-outside-tops"


def source(sitting):
    return (FIXTURES / f"{sitting}.xml").read_text(encoding="utf-8")


def speech_ids(item):
    return [speech["rede_id"] for speech in item["speeches"]]


def report_before_adoption(xml):
    """A cached report as the parser left it before it read these Reden: only the
    wrapped TOPs, numbered from 1, each with its DIP fields."""
    parsed = dip.parse_protocol_xml(xml)
    items = []
    for top in parsed["agenda_items"]:
        if top["top_source"]:
            continue
        items.append({"index": len(items) + 1, **dip.xml_top_fields(top),
                      "api": {"positions": [{"id": top["top_id"]}]}, "votes": [{"id": f"vote {top['top_id']}"}]})
    root = dip.ET.fromstring(xml)
    return {"protocol": {"dokumentnummer": f"{root.get('wahlperiode')}/{root.get('sitzung-nr')}"},
            "agenda_items": items, "validation_summary": {"xml_top_count": len(items)}}


class AdoptedTopTests(unittest.TestCase):
    def test_18_49_yields_all_51_reden_under_the_items_the_inhaltsverzeichnis_names(self):
        xml = source("18-49")
        items = dip.parse_protocol_xml(xml)["agenda_items"]
        self.assertEqual(
            [(i["index"], i["top_id"], i["top_source"], len(i["speeches"])) for i in items],
            [(1, "Tagesordnungspunkt 1", "inhaltsverzeichnis", 1),
             (2, "Allgemeine Finanzdebatte (einschließlich Einzelpläne 08, 20, 32 und 60)", "inhaltsverzeichnis", 12),
             (3, "Einzelplan 06", "inhaltsverzeichnis", 13),
             (4, "Einzelplan 07", None, 25)])
        self.assertEqual(speech_ids(items[0]), ["ID1804900100"])
        all_ids = [speech for item in items for speech in speech_ids(item)]
        self.assertEqual(all_ids, [rede.get("id") for rede in dip.ET.fromstring(xml).iter("rede")])
        self.assertEqual(len(all_ids), 51)

    def test_18_44_geschaeftsordnung_debate_keeps_its_three_reden(self):
        items = dip.parse_protocol_xml(source("18-44"))["agenda_items"]
        self.assertEqual((items[0]["index"], items[0]["top_id"], items[0]["top_source"]),
                         (1, "Zur Geschäftsordnung", "inhaltsverzeichnis"))
        self.assertEqual(speech_ids(items[0]), ["ID1804400100", "ID1804400200", "ID1804400300"])
        self.assertEqual(items[0]["heading"], "")
        self.assertEqual([i["top_id"] for i in items[1:3]], ["Tagesordnungspunkt V", "Tagesordnungspunkt II (Fortsetzung)"])

    def test_a_top_called_in_sitzungsbeginn_gives_the_first_run_its_heading(self):
        items = dip.parse_protocol_xml(source("18-49"))["agenda_items"]
        self.assertIn("Haushaltsgesetz 2015", items[0]["heading"])
        self.assertIn("Finanzplan des Bundes 2014 bis 2018", items[0]["heading"])
        self.assertEqual(items[1]["heading"], "")

    def test_a_rede_with_no_inhaltsverzeichnis_entry_refuses_the_sitting(self):
        root = dip.ET.fromstring(source("18-49"))
        for block in root.findall("./vorspann/inhaltsverzeichnis/ivz-block"):
            for entry in block.findall("ivz-eintrag"):
                xref = entry.find("xref")
                if xref is not None and xref.get("rid") == "ID1804900200":
                    block.remove(entry)
        with self.assertRaisesRegex(ValueError, "18/49: Rede ID1804900200 .*no Inhaltsverzeichnis entry"):
            dip.parse_protocol_xml(dip.ET.tostring(root, encoding="unicode"))

    def test_a_rede_after_a_top_refuses_the_sitting(self):
        root = dip.ET.fromstring(source("18-49"))
        verlauf = root.find("sitzungsverlauf")
        rede = verlauf.find("rede[@id='ID1804902600']")
        verlauf.remove(rede)
        verlauf.insert(list(verlauf).index(verlauf.find("tagesordnungspunkt")) + 1, rede)
        with self.assertRaisesRegex(ValueError, "18/49: Rede ID1804902600 .*after a TOP"):
            dip.parse_protocol_xml(dip.ET.tostring(root, encoding="unicode"))


class ReplayTests(unittest.TestCase):
    def test_replay_adds_the_new_items_and_old_items_keep_their_dip_fields(self):
        xml = source("18-44")
        report = report_before_adoption(xml)
        parsed = dip.parse_protocol_xml(xml)
        dip.reparse_report_xml(report, parsed)
        items = report["agenda_items"]
        self.assertEqual([i["index"] for i in items], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual([i["top_id"] for i in items], [t["top_id"] for t in parsed["agenda_items"]])
        self.assertEqual(items[0]["votes"], [])
        self.assertEqual(items[0]["api"]["positions"], [])
        self.assertEqual([s["rede_id"] for s in items[0]["xml_speakers"]],
                         ["ID1804400100", "ID1804400200", "ID1804400300"])
        for item in items[1:]:
            self.assertEqual(item["votes"], [{"id": f"vote {item['top_id']}"}])
            self.assertEqual(item["api"]["positions"], [{"id": item["top_id"]}])
        self.assertEqual(report["validation_summary"]["xml_top_count"], 7)

    def test_a_second_replay_changes_nothing(self):
        xml = source("18-49")
        report = report_before_adoption(xml)
        dip.reparse_report_xml(report, dip.parse_protocol_xml(xml))
        once = copy.deepcopy(report)
        dip.reparse_report_xml(report, dip.parse_protocol_xml(xml))
        self.assertEqual(report, once)

    def test_any_other_change_to_the_item_set_still_refuses(self):
        xml = source("18-44")
        parsed = dip.parse_protocol_xml(xml)
        lost_item = report_before_adoption(xml)
        del lost_item["agenda_items"][-1]
        with self.assertRaisesRegex(ValueError, "agenda item set changed"):
            dip.reparse_report_xml(lost_item, parsed)
        renamed = report_before_adoption(xml)
        renamed["agenda_items"][0]["top_id"] = "Tagesordnungspunkt Z"
        with self.assertRaisesRegex(ValueError, "missing source TOP"):
            dip.reparse_report_xml(renamed, parsed)

    def test_an_adopted_item_the_xml_no_longer_yields_refuses(self):
        xml = source("18-44")
        report = report_before_adoption(xml)
        dip.reparse_report_xml(report, dip.parse_protocol_xml(xml))
        root = dip.ET.fromstring(xml)
        verlauf = root.find("sitzungsverlauf")
        for rede in verlauf.findall("rede"):
            verlauf.remove(rede)
        with self.assertRaisesRegex(ValueError, "agenda item set changed"):
            dip.replay_top_map(report, dip.parse_protocol_xml(dip.ET.tostring(root, encoding="unicode")))

    def test_a_speaker_keeps_the_profile_of_the_item_when_replay_renumbers_it(self):
        xml = source("18-49")
        report = report_before_adoption(xml)
        speaker = report["agenda_items"][0]["xml_speakers"][0]["speaker"]
        # No id: only the item's own profiles carry it, not the by-Redner-ID fallback.
        speaker["abgeordnetenwatch"] = {"url": "https://example.invalid/p"}
        with tempfile.TemporaryDirectory() as tmp:
            path = site.xml_cache_path(Path(tmp), "18/49")
            path.parent.mkdir(parents=True)
            path.write_text(xml, encoding="utf-8")
            self.assertEqual(site.reparse_cached_xml(Path(tmp), [{"report": report}]), 1)
        item = report["agenda_items"][3]
        self.assertEqual(item["top_id"], "Einzelplan 07")
        self.assertEqual(item["xml_speakers"][0]["speaker"].get("abgeordnetenwatch"), {"url": "https://example.invalid/p"})


if __name__ == "__main__":
    unittest.main()
