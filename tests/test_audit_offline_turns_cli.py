# Value: protects=offline audit CLI report and baseline comparison; fails_when=the CLI omits or misstates per-sitting metadata and count deltas; why_new=existing audit tests call audit() directly and never exercise main() or argparse; seam=none
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock
from types import SimpleNamespace

import _support
import audit_offline_turns
import validate_dip_protocol as dip


class OfflineAuditCliTests(unittest.TestCase):
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
