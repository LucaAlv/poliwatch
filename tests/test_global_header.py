from __future__ import annotations

import re
import unittest

import _support  # noqa: F401
import render_dip_pulse_html as pulse_html
from features import all_selection, resolve


class GlobalHeaderTests(unittest.TestCase):
    def test_depth_prefixes_every_href(self) -> None:
        root = pulse_html.render_global_header(active="pulse", features=all_selection())
        nested = pulse_html.render_global_header(depth=1, active="bills", features=all_selection())
        root_hrefs = re.findall(r'href="([^"]+)"', root)
        nested_hrefs = re.findall(r'href="([^"]+)"', nested)
        self.assertTrue(all(not href.startswith("../") for href in root_hrefs))
        self.assertTrue(all(href.startswith("../") for href in nested_hrefs))

    def test_nested_bills_header_has_correct_mp_link_and_database(self) -> None:
        markup = pulse_html.render_global_header(depth=1, active="bills", features=all_selection())
        self.assertIn('href="../abgeordnete/index.html"', markup)
        self.assertNotIn("bills/abgeordnete", markup)
        self.assertIn('href="../database.html"', markup)

    def test_database_is_present_at_every_depth(self) -> None:
        for depth in (0, 1, 2):
            with self.subTest(depth=depth):
                self.assertIn(("../" * depth) + "database.html", pulse_html.render_global_header(depth=depth))

    def test_disabled_feature_drops_nav_item(self) -> None:
        selection = resolve(base=("bills",), disable=("bills",))
        markup = pulse_html.render_global_header(features=selection)
        nav = re.search(r'<nav[^>]*>(.*?)</nav>', markup).group(1)
        self.assertNotIn("Gesetze verfolgen", nav)
        enabled = pulse_html.render_global_header(features=all_selection())
        self.assertIn('data-feature="bills"', enabled)

    def test_accessibility_state_is_wired(self) -> None:
        markup = pulse_html.render_global_header(active="overview", features=all_selection())
        self.assertEqual(markup.count('aria-current="page"'), 1)
        self.assertIn('aria-expanded="false"', markup)
        control = re.search(r'aria-controls="([^"]+)"', markup).group(1)
        self.assertIn(f'id="{control}"', markup)


if __name__ == "__main__":
    unittest.main()
