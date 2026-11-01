from __future__ import annotations

import copy
import json
import re
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
import render_dip_pulse_html as pulse_html
from features import EnrichmentSelection


# A complete operator file's values, flattened as load_operator returns them.
COMPLETE_OPERATOR = {
    "name": "Erika <script>alert(1)</script> Muster",
    "street": "Musterstraße 1",
    "postal_code": "12345",
    "city": "Musterstadt",
    "email": "impressum@example.org",
    "hosting.provider": "Beispiel Hosting GmbH",
    "hosting.address": "Hostweg 2, 54321 Hoststadt",
    "hosting.privacy_url": "https://hosting.example.org/datenschutz",
    "hosting.log_retention": "7 Tage",
    "supervisory_authority.name": "Landesbeauftragte für Datenschutz Musterland",
    "supervisory_authority.url": "https://datenschutz.example.org/",
}
OPERATOR_KEYS = set(COMPLETE_OPERATOR)
LEGAL_SPAN_RE = re.compile(r'<span class="legal-links">.*?</span>', re.S)


def _site_pages(output: Path) -> dict[str, str]:
    """Every generated page but the meta-refresh alias redirects, by relative path."""
    pages = {}
    for path in sorted(output.rglob("*.html")):
        markup = path.read_text(encoding="utf-8")
        if 'http-equiv="refresh"' not in markup:
            pages[path.relative_to(output).as_posix()] = markup
    return pages


class LegalPagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.output = Path(cls._tmp.name) / "site"
        demo.build_demo(cls.output)
        cls.pages = _site_pages(cls.output)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    # Value: protects=the TODO's done criterion: every non-redirect page links impressum.html and datenschutz.html with the prefix of its depth, and both targets exist; fails_when=a footer lacks the links, a depth-1 page links impressum.html relative to its own directory, or a target is not written; why_new=ADR 0003 D4 needs the legal pages reachable from every page; seam=build_demo; no_claim=footer wording
    def test_every_page_links_both_legal_pages_at_its_depth(self) -> None:
        self.assertGreater(len(self.pages), 10)
        for relative, markup in self.pages.items():
            with self.subTest(page=relative):
                prefix = "../" * relative.count("/")
                (span,) = LEGAL_SPAN_RE.findall(markup)
                self.assertIn(f'href="{prefix}impressum.html"', span)
                self.assertIn(f'href="{prefix}datenschutz.html"', span)
                self.assertIn(span, markup.split("<footer")[-1])
        for name in ("impressum.html", "datenschutz.html"):
            self.assertTrue((self.output / name).is_file())
        for depth_one in ("protocols/plenarprotokoll-21-84.html", "bills/index.html", "abgeordnete/index.html", "votes/index.html", "fakt/index.html"):
            self.assertIn(depth_one, self.pages)

    # Value: protects=without an operator file each operator field renders one marked placeholder kind per page, and only the two legal pages carry markers; fails_when=a missing value renders blank or unmarked, a field has no marker, or a marker leaks onto another page; why_new=eng review D2 A; seam=build_demo; no_claim=the deploy gate on markers (TODOS hosting item)
    def test_without_an_operator_file_every_field_is_a_marked_placeholder(self) -> None:
        def fields(markup: str) -> set[str]:
            return set(re.findall(r'<span data-operator-missing="([^"]+)">Angabe folgt\.</span>', markup))

        self.assertEqual(fields(self.pages["impressum.html"]), {"name", "street", "postal_code", "city", "email"})
        self.assertEqual(fields(self.pages["datenschutz.html"]), OPERATOR_KEYS)
        self.assertEqual(sorted(name for name, markup in self.pages.items() if "data-operator-missing" in markup), ["datenschutz.html", "impressum.html"])

    # Value: protects=with a complete operator file no generated page carries data-operator-missing, every value is escaped, sources.html no longer says the licence "steht noch aus", and the authority is one link; fails_when=a field is not read, a value is written raw, or the licence placeholder remains; why_new=eng review D2 A done criterion; seam=build_demo with an operator; no_claim=legal sufficiency of the text
    def test_a_complete_operator_file_leaves_no_marker_and_is_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "site"
            demo.build_demo(output, operator=COMPLETE_OPERATOR)
            pages = _site_pages(output)
        self.assertEqual([name for name, markup in pages.items() if "data-operator-missing" in markup], [])
        for name in ("impressum.html", "datenschutz.html"):
            with self.subTest(name):
                self.assertNotIn("<script>alert(1)</script>", pages[name])
                self.assertIn("Erika &lt;script&gt;alert(1)&lt;/script&gt; Muster", pages[name])
                self.assertIn('<a href="mailto:impressum@example.org">impressum@example.org</a>', pages[name])
        self.assertIn('<a href="https://datenschutz.example.org/">Landesbeauftragte für Datenschutz Musterland</a>', pages["datenschutz.html"])
        self.assertIn("7 Tage", pages["datenschutz.html"])
        self.assertNotIn("steht noch aus", pages["sources.html"])
        self.assertIn('id="lizenz"', pages["sources.html"])
        self.assertIn("BT-PlPr.", pages["sources.html"])

    # Value: protects=the publication validator refuses an output tree without impressum.html or datenschutz.html; fails_when=a deployable tree can lack a legal page; why_new=ADR 0003 D4 makes both pages part of every public build; seam=validate_publication_directory; no_claim=page content
    def test_the_publication_validator_requires_both_legal_pages(self) -> None:
        import shutil

        for name in ("impressum.html", "datenschutz.html"):
            with self.subTest(name), tempfile.TemporaryDirectory() as tmp:
                copy_dir = Path(tmp) / "site"
                shutil.copytree(self.output, copy_dir)
                publication.validate_publication_directory(copy_dir)
                (copy_dir / name).unlink()
                with self.assertRaisesRegex(publication.PublicationStateError, f"entry points are missing: {name}"):
                    publication.validate_publication_directory(copy_dir)

    # Value: protects=the Datenschutz page names exactly the localStorage keys the page scripts use and no host is loaded that it does not name (none today); fails_when=a new stored setting or a CDN font/script/style is added without a matching text change; why_new=eng review D4 A, a false privacy statement is a correctness defect; seam=page_scripts and the demo build's HTML; no_claim=outbound links, which load nothing until clicked
    def test_datenschutz_names_every_stored_key_and_every_loaded_host(self) -> None:
        scripts = pulse_html.page_head() + pulse_html.page_scripts()
        used = set(re.findall(r'const key = "([^"]+)"', scripts))
        self.assertEqual(scripts.count("localStorage"), scripts.count("window.localStorage"))
        named = {key for key, _ in site.DATENSCHUTZ_STORAGE_KEYS}
        self.assertEqual(used, named)
        for key in named:
            self.assertIn(f"<code>{key}</code>", self.pages["datenschutz.html"])
        for word in ("sessionStorage", "indexedDB", "document.cookie"):
            self.assertNotIn(word, scripts)
        loaded = set()
        for relative, markup in self.pages.items():
            urls = re.findall(r'<(?:script|img|iframe|source|video|audio)\b[^>]*\ssrc="([^"]+)"', markup)
            urls += re.findall(r'<link\b[^>]*\shref="([^"]+)"', markup)
            urls += re.findall(r'@import\s+(?:url\()?["\']?([^"\')\s;]+)', markup)
            urls += re.findall(r'url\(["\']?((?:https?:)?//[^"\')]+)', markup)
            for url in urls:
                if re.match(r"(?:https?:)?//", url):
                    loaded.add(re.sub(r"^(?:https?:)?//", "", url).split("/")[0])
        self.assertEqual(loaded, set(site.DATENSCHUTZ_LOADED_HOSTS))

    # Value: protects=the footer change added the legal span and nothing else on any page, and the database-unavailable page gained a footer with the links; fails_when=a footer link or sentence is lost, moved or altered while appending the span; why_new=eng review D5 A, 17 of 18 footers had no coverage; seam=build_demo rendered with render_legal_links patched to ""; no_claim=pages the demo does not build
    def test_the_legal_span_is_the_only_footer_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(pulse_html, "render_legal_links", return_value=""):
            output = Path(tmp) / "site"
            demo.build_demo(output)
            without = _site_pages(output)
        self.assertEqual(set(without), set(self.pages))

        def normalise(markup: str) -> str:
            markup = LEGAL_SPAN_RE.sub("", markup)
            return re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)?", "<time>", markup)

        for relative, markup in self.pages.items():
            with self.subTest(page=relative):
                self.assertEqual(normalise(markup), normalise(without[relative]))
        unavailable = self.pages["database.html"]
        self.assertIn("Daten nicht erzeugt", unavailable)
        footer = unavailable.split("<footer>")[1].split("</footer>")[0]
        self.assertIn('<a href="sources.html">Quellen und Methode</a>', footer)
        self.assertIn('href="impressum.html"', footer)


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
            # Since A1 the Kurzintervention and its Erwiderung are Beiträge, not Reden.
            self.assertIn("14 Reden", markup)
            self.assertIn("nicht mitgezählt: 1 Kurzintervention, 1 Erwiderung, 1 Zwischenfrage.", markup)
            self.assertIn("Profilverknüpfungen wurden nicht abgerufen", markup)
            self.assertIn("keine namentliche Abstimmung verzeichnet", markup)
            self.assertNotIn("data-ai-generated", markup)
            publication.validate_publication_directory(output)
            manifest = json.loads((output / "data" / "features.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["domains"]["votes"]["acquisition_state"], "complete")
            self.assertEqual(manifest["domains"]["votes"]["presentation_state"], "domain_empty")
            self.assertTrue(manifest["domains"]["votes"]["attempted"])

    # Value: protects=the demo's grouped Antrag TOP lists each Antrag's own title at equal weight on puls.html, as a real build does; fails_when=the fixture or extractor copies the joint "a) … b) …" heading into both titles, which collapses them into one bold .radar-title block; why_new=the demo was the only place the four-line block appeared; seam=none; no_claim=wording of real DIP titles beyond these two Drucksachen
    def test_demo_radar_lists_each_antrag_title_not_the_joint_heading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "site"
            demo.build_demo(output)
            markup = (output / "puls.html").read_text(encoding="utf-8")
        row = markup.split('<li class="radar-row"')[1].split("</li>\n")[0]
        self.assertNotIn('class="radar-title"', row)
        # The joint heading stays only in the label link's tooltip.
        self.assertNotIn("b) Beratung", re.search(r'<ul class="radar-titles">(.*?)</ul>', row, re.S).group(1))
        self.assertEqual(
            re.findall(r'<li class="radar-group-title">(.*?)</li>', row),
            [
                "Deutschland in die KI-Zukunft bringen – Für einen nationalen Aufbruch an die digitale Weltspitze",
                "Technologische Souveränität durch deutsches Fachwissen sichern – Staatliche Koordination "
                "für ein europäisches KI-Kooperationsprojekt nach Vorbild von Airbus starten",
            ],
        )

    def test_development_demo_is_marked_and_not_deployable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "site-dev"
            demo.build_demo(output, include_dev_view=True)
            manifest = json.loads((output / "data" / "features.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["build"]["development_output"])
            self.assertIn("dev-only", (output / "protocols" / "plenarprotokoll-21-84.html").read_text(encoding="utf-8"))
            with self.assertRaisesRegex(publication.PublicationStateError, "development output"):
                publication.validate_publication_directory(output)

    def test_real_render_omits_an_unsafe_protocol_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = json.loads(demo.DEFAULT_FIXTURE.read_text(encoding="utf-8"))
            fixture["protocol"]["xml_url"] = "javascript:alert(1)"
            fixture_path = root / "unsafe.json"
            fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

            output = root / "site"
            demo.build_demo(output, fixture_path)
            generated = "\n".join(
                path.read_text(encoding="utf-8") for path in output.rglob("*.html")
            )
            self.assertNotIn('href="javascript:', generated)

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
