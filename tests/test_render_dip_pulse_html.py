from __future__ import annotations

import copy
import json
import re
import unittest

import _support
import render_dip_pulse_html as pulse_html


class DossierLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = json.loads((_support.FIXTURES / "report.json").read_text(encoding="utf-8"))

    @staticmethod
    def _top_card(markup: str) -> str:
        match = re.search(r'<article class="top-card" id="top-1">(.*?)</article>', markup, re.S)
        if match is None:
            raise AssertionError("Rendered dossier has no first TOP card")
        return match.group(1)

    def test_documents_are_metadata_before_metrics_and_speakers_are_full_width(self) -> None:
        card = self._top_card(pulse_html.render_html(self.report))

        self.assertLess(card.index('class="top-documents"'), card.index('class="top-bars"'))
        self.assertLess(card.index('class="top-bars"'), card.index('class="speaker-section"'))
        self.assertIn('class="doc-link" href="https://example.test/20-123.pdf"', card)
        self.assertRegex(
            card,
            r'<section class="speaker-section">\s*<h3>Rednerinnen und Redner</h3>',
        )
        self.assertNotRegex(
            card,
            r'class="detail-grid"[^>]*>\s*<section>\s*<h3>Rednerinnen und Redner</h3>',
        )
        self.assertRegex(
            card,
            r'<section class="dev-only dev-top-details">[\s\S]*?class="detail-grid"',
        )

    def test_documents_metadata_is_omitted_when_top_has_no_documents(self) -> None:
        report = copy.deepcopy(self.report)
        report["agenda_items"][0]["xml_drucksachen"] = []

        card = self._top_card(pulse_html.render_html(report))

        self.assertNotIn('class="top-documents"', card)
        self.assertIn('<div><span>XML Drucksachen</span><span class="muted">Keine Drucksache im XML</span></div>', card)

    def test_documents_metadata_keeps_documents_without_a_source_url(self) -> None:
        report = copy.deepcopy(self.report)
        report["agenda_items"][0]["xml_drucksachen"] = [
            {"dokumentnummer": "20/123", "url": "https://example.test/20-123.pdf"},
            {"dokumentnummer": "20/456", "url": None},
        ]

        card = self._top_card(pulse_html.render_html(report))

        self.assertIn('class="doc-link" href="https://example.test/20-123.pdf"', card)
        self.assertIn('<span class="doc-link muted">20/456</span>', card)

    def test_layout_css_wraps_document_links_and_speaker_names(self) -> None:
        markup = pulse_html.render_html(self.report)

        self.assertRegex(markup, r'\.top-document-links\s*\{[^}]*flex-wrap:wrap;')
        self.assertRegex(
            markup,
            r'\.top-document-links \.doc-link\s*\{[^}]*overflow-wrap:anywhere;',
        )
        self.assertRegex(markup, r'\.speaker-row strong\s*\{[^}]*overflow-wrap:anywhere;')
        self.assertIn(
            "grid-template-columns:10px minmax(96px, .85fr) minmax(110px, 1fr) 44px max-content;",
            markup,
        )
        self.assertIn(
            "grid-template-columns:10px minmax(0,1fr) 48px max-content;",
            markup,
        )


if __name__ == "__main__":
    unittest.main()
