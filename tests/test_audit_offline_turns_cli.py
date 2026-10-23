# Value: protects=offline audit CLI report and baseline comparison; fails_when=the CLI omits or misstates per-sitting metadata and count deltas; why_new=existing audit tests call audit() directly and never exercise main() or argparse; seam=none
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from textwrap import dedent
import unittest
from unittest.mock import Mock
from types import SimpleNamespace

import _support
import audit_offline_turns
import validate_dip_protocol as dip


class OfflineAuditCliTests(unittest.TestCase):
    # Value: protects=independently loaded historical parser/classifier pairs; fails_when=either parser shares the other's classifier; why_new=the changed-baseline wrapper calls the current parser; seam=none
    def test_cli_keeps_historical_classifier_separate_from_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml_dir = root / "xml"
            xml_dir.mkdir()
            xml = ('<dbtplenarprotokoll><sitzungsverlauf><tagesordnungspunkt top-id="1">'
                   '<rede id="R"><p klasse="redner"><redner id="A"><name>'
                   '<vorname>Anna</vorname><nachname>Test</nachname><fraktion>SPD</fraktion>'
                   '</name></redner></p><p>Eine Rede.</p></rede>'
                   '</tagesordnungspunkt></sitzungsverlauf></dbtplenarprotokoll>')
            # A second file detects a baseline classifier leaking into later current audits.
            for name in ("first", "second"):
                (xml_dir / f"{name}.xml").write_text(xml, encoding="utf-8")
            parser = root / "historical_parser.py"
            classifier = root / "historical_speech_kinds.py"
            # Small stand-ins retain the historical module-global import and classifier call.
            parser.write_text(dedent("""\
                import speech_kinds
                import xml.etree.ElementTree as ET

                def parse_protocol_xml(xml):
                    top = ET.fromstring(xml).find('./sitzungsverlauf/tagesordnungspunkt')
                    labels = speech_kinds.classify_reden(top, frozenset())
                    units = [{'rede_id': rede.get('id'), 'kind': label.kind}
                             for rede, label in zip(top.findall('rede'), labels)]
                    return {'agenda_items': [{
                        'speeches': [u for u in units if u['kind'] is None],
                        'contributions': [u for u in units if u['kind'] is not None]}]}

                def speech_segments(rede):
                    return '', []
                """), encoding="utf-8")
            classifier.write_text(dedent("""\
                from types import SimpleNamespace

                VERSION = 4

                def classify_reden(top, formats, continuation=False):
                    return [SimpleNamespace(kind='legacy_probe', parent_rede_id=None)
                            for rede in top.findall('rede')]
                """), encoding="utf-8")
            output = root / "report.json"
            subprocess.run(
                [sys.executable, str(_support.SCRIPTS / "audit_offline_turns.py"), str(xml_dir),
                 "--baseline-parser", str(parser), "--baseline-speech-kinds", str(classifier),
                 "--output", str(output)],
                cwd=_support.ROOT, capture_output=True, text=True, check=True)
            report = json.loads(output.read_text(encoding="utf-8"))

            self.assertEqual(report["rule_version"], dip.speech_kinds.VERSION)
            self.assertEqual(report["baseline_rule_version"], 4)
            self.assertEqual(report["baseline_parser_sha256"], hashlib.sha256(parser.read_bytes()).hexdigest())
            self.assertEqual(report["baseline_speech_kinds_sha256"], hashlib.sha256(classifier.read_bytes()).hexdigest())
            self.assertEqual(report["accepted"], 2)
            self.assertEqual(report["baseline_accepted"], 2)
            self.assertEqual(report["counts"], {"rede": 2})
            self.assertEqual(report["count_changes"], {"legacy_probe": -2, "rede": 2})
            self.assertEqual(set(report["sittings"]), {"first", "second"})
            for sitting in report["sittings"].values():
                self.assertEqual(sitting["counts"], {"rede": 1})
                self.assertEqual(sitting["count_changes"], {"legacy_probe": -1, "rede": 1})

    # Value: protects=historical baselines require both classifier files; fails_when=an incomplete baseline pair writes an audit; why_new=valid CLI modes do not exercise argparse rejection; seam=none
    def test_unpaired_baseline_flags_reject_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.json"
            for flag in ("--baseline-parser", "--baseline-speech-kinds"):
                result = subprocess.run(
                    [sys.executable, str(_support.ROOT / "scripts/audit_offline_turns.py"),
                     tmp, flag, "unused.py", "--output", str(output)],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("must be supplied together", result.stderr)
                self.assertFalse(output.exists())

    # Value: protects=audit stops on unisolatable parser errors without changing source; fails_when=an unknown error is swallowed or a repeated locator loops; why_new=successive distinct blockers do not exercise either stop guard; seam=none
    def test_unisolatable_errors_stop_without_changing_source(self):
        xml = '<root><rede id="R"><p klasse="redner"><redner id="A"/></p><p>Main.</p><p klasse="redner"><redner id="B"/></p><p>Unknown.</p></rede></root>'
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.xml"
            source.write_text(xml)
            for message, error in (("unexpected parser failure", ValueError),
                                   ("unresolved nested contribution at R marker 2", RuntimeError)):
                parser = SimpleNamespace(parse_protocol_xml=Mock(side_effect=ValueError(message)),
                                         speech_segments=dip.speech_segments)
                with self.assertRaises(error):
                    audit_offline_turns.audit(parser, source)
                self.assertEqual(source.read_text(), xml)
                self.assertEqual(parser.parse_protocol_xml.call_count, 2 if error is RuntimeError else 1)

    def test_cli_writes_report_and_compares_optional_baseline(self):
        scripts = _support.ROOT / "scripts"
        source = _support.FIXTURES / "a1-historical-18-13.xml"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            xml_dir = root / "xml"
            xml_dir.mkdir()
            (xml_dir / source.name).write_bytes(source.read_bytes())
            changed_baseline = root / "changed_baseline.py"
            changed_baseline.write_text(
                f"import sys\nsys.path.insert(0, {str(scripts)!r})\n"
                "import validate_dip_protocol as current\n"
                "speech_kinds = current.speech_kinds\n"
                "speech_segments = current.speech_segments\n"
                "def parse_protocol_xml(xml):\n"
                "    parsed = current.parse_protocol_xml(xml)\n"
                "    next(c for top in parsed['agenda_items'] for c in top['contributions'])['kind'] = 'legacy_probe'\n"
                "    return parsed\n",
                encoding="utf-8",
            )

            for baseline in (None, "same", "changed"):
                output = root / f"report-{baseline}.json"
                command = [sys.executable, str(scripts / "audit_offline_turns.py"), str(xml_dir), "--output", str(output)]
                if baseline:
                    parser_path = changed_baseline if baseline == "changed" else scripts / "validate_dip_protocol.py"
                    command += ["--baseline-parser", str(parser_path),
                                "--baseline-speech-kinds", str(scripts / "speech_kinds.py")]
                completed = subprocess.run(command, cwd=_support.ROOT, capture_output=True, text=True, check=True)
                summary = json.loads(completed.stdout)
                report = json.loads(output.read_text(encoding="utf-8"))

                self.assertEqual(summary["files"], 1)
                self.assertEqual(report["files"], 1)
                self.assertIn("a1-historical-18-13", report["sittings"])
                self.assertTrue(report["sittings"]["a1-historical-18-13"]["accepted"])
                source_xml = source.read_text(encoding="utf-8")
                self.assertEqual(report["sittings"]["a1-historical-18-13"]["source_sha256"],
                                 hashlib.sha256(source_xml.encode()).hexdigest())
                if baseline:
                    self.assertEqual(report["baseline_accepted"], 1)
                    if baseline == "same":
                        self.assertEqual(report["count_changes"], {})
                    else:
                        self.assertEqual(report["count_changes"]["legacy_probe"], -1)
                        self.assertTrue(any(delta == 1 for delta in report["count_changes"].values()))
                else:
                    self.assertIsNone(report["baseline_accepted"])


if __name__ == "__main__":
    unittest.main()
