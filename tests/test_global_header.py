from __future__ import annotations

import re
import unittest

import _support  # noqa: F401
import render_dip_pulse_html as pulse_html


class GlobalHeaderTests(unittest.TestCase):
    def test_depth_prefixes_every_href(self) -> None:
        root = pulse_html.render_global_header(active="pulse")
        nested = pulse_html.render_global_header(depth=1, active="bills")
        root_hrefs = re.findall(r'href="([^"]+)"', root)
        nested_hrefs = re.findall(r'href="([^"]+)"', nested)
        self.assertTrue(all(not href.startswith("../") for href in root_hrefs))
        self.assertTrue(all(href.startswith("../") for href in nested_hrefs))

    def test_nested_header_has_exact_public_destinations(self) -> None:
        markup = pulse_html.render_global_header(depth=1, active="bills")
        self.assertIn('href="../abgeordnete/index.html"', markup)
        self.assertNotIn("bills/abgeordnete", markup)
        nav = re.search(r'<nav[^>]*>(.*?)</nav>', markup).group(1)
        self.assertEqual(nav.count("<a "), 5)
        for label in ("Aktueller Puls", "Sitzungen", "Gesetze", "Abgeordnete", "Quellen"):
            self.assertIn(label, nav)
        for retired in ("database.html", "api-sitzungen.html", "settings.html", "data-feature"):
            self.assertNotIn(retired, markup)

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
        markup = pulse_html.render_global_header(active="overview")
        self.assertEqual(markup.count('aria-current="page"'), 1)
        self.assertIn('aria-pressed="false"', markup)
        self.assertIn('aria-label="Globale Navigation"', markup)
        self.assertIn('aria-label="Dunkles Design aktivieren"', markup)


if __name__ == "__main__":
    unittest.main()
