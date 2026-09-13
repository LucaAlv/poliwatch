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

    def test_enrichment_selection_does_not_drop_published_nav_item(self) -> None:
        selection = resolve(base=("bills",), disable=("bills",))
        markup = pulse_html.render_global_header(features=selection)
        nav = re.search(r'<nav[^>]*>(.*?)</nav>', markup).group(1)
        self.assertIn("Gesetze verfolgen", nav)
        self.assertIn('data-feature="bills"', markup)

    def test_dark_theme_covers_lede_rows_and_drops_retired_pulse_actions(self) -> None:
        # The dark palette is applied through two hand-maintained selector lists,
        # so a new surface is invisible in dark mode until it is added by hand.
        # .lede-top replaced the .pulse-actions links in the puls.html hero.
        css = pulse_html.global_header_styles()
        panels = re.search(
            r':root\[data-theme="dark"\] :is\(\s*\.metric,(.*?)\)\s*\{', css, re.S
        )
        self.assertIsNotNone(panels, "dark-theme panel selector list not found")
        self.assertIn(".lede-top", panels.group(1))
        self.assertNotIn(".pulse-actions", css)

    def test_dark_theme_styles_the_vorgangstyp_bubble_and_glossary_target(self) -> None:
        # The Debattenprofil hover bubble and the glossary :target highlight are
        # coloured inline for light mode, so dark mode needs explicit overrides.
        css = pulse_html.global_header_styles()
        self.assertIn(':root[data-theme="dark"] a.week-label[data-tip]::after', css)
        self.assertIn(':root[data-theme="dark"] .method-list li:target', css)

    def test_accessibility_state_is_wired(self) -> None:
        markup = pulse_html.render_global_header(active="overview", features=all_selection())
        self.assertEqual(markup.count('aria-current="page"'), 1)
        self.assertIn('aria-expanded="false"', markup)
        control = re.search(r'aria-controls="([^"]+)"', markup).group(1)
        self.assertIn(f'id="{control}"', markup)


if __name__ == "__main__":
    unittest.main()
