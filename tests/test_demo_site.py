from __future__ import annotations

import copy
import json
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import build_demo_site as demo
import build_dip_pulse_site as site
import publication_state as publication
from features import EnrichmentSelection


class DemoSiteTests(unittest.TestCase):
    def test_official_demo_is_zero_network_and_matches_the_acceptance_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            socket, "create_connection", side_effect=AssertionError("demo attempted network access")
        ):
            output = Path(tmp) / "site"
            demo.build_demo(output)

            dossier = output / "protocols" / "plenarprotokoll-21-84.html"
            markup = dossier.read_text(encoding="utf-8")
            self.assertIn("Tagesordnungspunkt 32 a/b", markup)
            self.assertIn("21/6354", markup)
            self.assertIn("21/4833", markup)
            self.assertIn("16 Reden", markup)
            self.assertIn("Profilverknüpfungen wurden nicht abgerufen", markup)
            self.assertIn("keine namentliche Abstimmung verzeichnet", markup)
            self.assertNotIn("data-ai-generated", markup)
            publication.validate_publication_directory(output)
            manifest = json.loads((output / "data" / "features.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["domains"]["votes"]["acquisition_state"], "complete")
            self.assertEqual(manifest["domains"]["votes"]["presentation_state"], "domain_empty")
            self.assertTrue(manifest["domains"]["votes"]["attempted"])

    def test_development_demo_is_marked_and_not_deployable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "site-dev"
            demo.build_demo(output, include_dev_view=True)
            manifest = json.loads((output / "data" / "features.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["build"]["development_output"])
            self.assertIn("dev-only", (output / "protocols" / "plenarprotokoll-21-84.html").read_text(encoding="utf-8"))
            with self.assertRaisesRegex(publication.PublicationStateError, "development output"):
                publication.validate_publication_directory(output)

    def test_real_render_rejects_an_unsafe_protocol_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = json.loads(demo.DEFAULT_FIXTURE.read_text(encoding="utf-8"))
            fixture["protocol"]["xml_url"] = "javascript:alert(1)"
            fixture_path = root / "unsafe.json"
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

            with self.assertRaisesRegex(publication.PublicationStateError, "require https"):
                demo.build_demo(root / "site", fixture_path)

    def test_interrupted_render_is_not_a_valid_publication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "site"
            original_write_text = Path.write_text

            def fail_on_sources(path: Path, *args: object, **kwargs: object) -> int:
                if path.name == "sources.html":
                    raise OSError("injected write failure")
                return original_write_text(path, *args, **kwargs)

            with mock.patch.object(Path, "write_text", new=fail_on_sources):
                with self.assertRaisesRegex(OSError, "injected write failure"):
                    demo.build_demo(output)
            with self.assertRaises(publication.PublicationStateError):
                publication.validate_publication_directory(output)

    def test_ten_copy_offline_build_is_linear_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            start = time.monotonic()
            one = self._build_copies(root / "one", 1)
            ten = self._build_copies(root / "ten", 10)
            elapsed = time.monotonic() - start

            one_size = self._presentation_size(one)
            ten_size = self._presentation_size(ten)
            self.assertLess(elapsed, 30.0)
            self.assertLessEqual(ten_size, one_size * 12)

    @staticmethod
    def _presentation_size(root: Path) -> int:
        return sum(
            path.stat().st_size
            for path in root.rglob("*")
            if path.is_file() and path.suffix in {".html", ".json"}
        )

    @staticmethod
    def _build_copies(output: Path, count: int) -> Path:
        for directory in ("data", "protocols", "bills", "abgeordnete"):
            (output / directory).mkdir(parents=True, exist_ok=True)
        base = demo.demo_report(demo.DEFAULT_FIXTURE)
        entries = []
        protocols = []
        for offset in range(count):
            report = copy.deepcopy(base)
            document_number = f"21/{84 + offset}"
            report["protocol"]["id"] = f"scale-{offset}"
            report["protocol"]["dokumentnummer"] = document_number
            report["protocol"]["titel"] = f"Skalierungsfixture {document_number}"
            entries.append(site.write_report_files(report, output))
            protocol = copy.deepcopy(report["protocol"])
            protocol["wahlperiode"] = "21"
            protocol["fundstelle"] = {
                "pdf_url": protocol.get("pdf_url"),
                "xml_url": protocol.get("xml_url"),
            }
            protocols.append(protocol)
        site.render_site(
            output_dir=output,
            database_path=output / "data" / "bundestag-pulse.sqlite",
            no_persist=True,
            protocols=protocols,
            entries=entries,
            abg_mps=[],
            mp_lookup={},
            enrichments=EnrichmentSelection(frozenset()),
            summary_mode="off",
            acquisition_attempted=False,
            include_dev_view=False,
        )
        return output


if __name__ == "__main__":
    unittest.main()
