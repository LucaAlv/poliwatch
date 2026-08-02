from __future__ import annotations

import io
import json
import re
import unittest
from contextlib import redirect_stderr

import _support  # noqa: F401
import render_dip_pulse_html as pulse_html
from features import FEATURES, NAV_ITEMS, REGISTRY, FeatureError, all_selection, feature_css, manifest_json, resolve


class FeatureRegistryTests(unittest.TestCase):
    def test_registry_is_self_consistent(self) -> None:
        ids = [feature.id for feature in FEATURES]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(re.fullmatch(r"[a-z][a-z0-9-]*", feature_id) for feature_id in ids))
        nav_keys = {item.key for item in NAV_ITEMS}
        for feature in FEATURES:
            self.assertTrue(set(feature.requires).issubset(REGISTRY))
            self.assertTrue(set(feature.enhances).issubset(REGISTRY))
            if feature.nav_key:
                self.assertIn(feature.nav_key, nav_keys)

    def test_core_features_cannot_be_disabled(self) -> None:
        with self.assertRaisesRegex(FeatureError, "Kern-Bausteine"):
            resolve(disable=("store",))

    def test_unknown_id_lists_real_ids(self) -> None:
        with self.assertRaisesRegex(FeatureError, "votes"):
            resolve(enable=("not-real",))

    def test_requirements_are_added_with_a_note(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            selection = resolve(base=(), enable=("bill-follow",))
        self.assertTrue({"bill-follow", "bills", "dip-fetch"}.issubset(selection.ids))
        self.assertIn("automatisch aktiviert", stderr.getvalue())

    def test_explicit_veto_cascades_and_wins(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            selection = resolve(base=REGISTRY, enable=("bills",), disable=("bills",))
        self.assertNotIn("bills", selection)
        self.assertNotIn("bill-follow", selection)
        self.assertIn("ausdrücklich deaktiviert", stderr.getvalue())

    def test_manifest_is_compact_and_safe(self) -> None:
        payload = manifest_json(all_selection())
        decoded = json.loads(payload)
        self.assertNotIn("</", payload)
        self.assertNotIn("Namentliche Abstimmungen", payload)
        self.assertTrue(decoded)
        self.assertTrue(all(set(value) == {"a", "v", "c", "m"} for value in decoded.values()))

    def test_feature_css_has_expected_polarity(self) -> None:
        css = feature_css()
        for feature in FEATURES:
            selector = f'html:not([data-feature-{feature.id}]) [data-feature="{feature.id}"]'
            if feature.client_mode == "hide":
                self.assertEqual(css.count(selector), 1)
            else:
                self.assertNotIn(selector, css)
        self.assertIn("html[data-feature-dev-view] .dev-only", css)
        self.assertIn(".dev-only { display:none", css)

    def test_global_styles_embed_feature_css(self) -> None:
        styles = pulse_html.global_header_styles()
        self.assertNotIn("{feature_css()}", styles)
        self.assertIn('html:not([data-feature-votes]) [data-feature="votes"]', styles)


if __name__ == "__main__":
    unittest.main()
