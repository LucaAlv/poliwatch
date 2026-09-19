from __future__ import annotations

import unittest

import _support  # noqa: F401
import render_dip_pulse_html as pulse_html
from features import ENRICHMENT_REGISTRY, EnrichmentSelection, FeatureError, NAV_ITEMS
from features import loader


class FixedPresentationTests(unittest.TestCase):
    def test_navigation_is_the_fixed_six_destination_product(self) -> None:
        self.assertEqual(
            [(item.key, item.label, item.path) for item in NAV_ITEMS],
            [
                ("pulse", "Aktueller Puls", "puls.html"),
                ("overview", "Sitzungen", "overview.html"),
                ("bills", "Gesetze", "bills/index.html"),
                ("abgeordnete", "Abgeordnete", "abgeordnete/index.html"),
                ("database", "Daten", "database.html"),
                ("sources", "Quellen", "sources.html"),
            ],
        )
        markup = pulse_html.render_global_header(active="overview")
        self.assertEqual(markup.count("<nav"), 1)
        self.assertEqual(markup.count('aria-current="page"'), 1)
        self.assertNotIn("settings", markup.lower())
        self.assertNotIn("data-feature", markup)

    def test_only_three_operator_enrichments_exist(self) -> None:
        self.assertEqual(set(ENRICHMENT_REGISTRY), {"votes", "aw-profiles", "mp-roster"})
        selection = EnrichmentSelection(frozenset({"votes", "mp-roster"}))
        self.assertEqual(selection.ids, frozenset({"votes", "mp-roster"}))
        with self.assertRaisesRegex(FeatureError, "Unbekannte Anreicherung"):
            EnrichmentSelection(frozenset({"bills"}))

    def test_public_components_are_unconditional_and_dev_view_is_explicit(self) -> None:
        public_ids = {component.feature.id for component in loader.load()}
        self.assertEqual(public_ids, {"votes", "summaries", "aw-profiles", "mp-pages", "bills"})
        self.assertNotIn("dev-view", public_ids)
        dev_ids = {component.feature.id for component in loader.load(include_dev_view=True)}
        self.assertEqual(dev_ids, public_ids | {"dev-view"})

    def test_general_feature_runtime_is_not_emitted(self) -> None:
        head = pulse_html.page_head()
        scripts = pulse_html.page_scripts()
        styles = pulse_html.global_header_styles()
        for output in (head, scripts, styles):
            self.assertNotIn("bundestag-pulse-features", output)
            self.assertNotIn("data-feature-", output)
        self.assertIn("bundestag-pulse-ai-summaries-v1", scripts)
        self.assertIn('root.dataset.aiSummaryController = "ready"', scripts)
        self.assertIn("body.hidden = collapsed", scripts)


if __name__ == "__main__":
    unittest.main()
