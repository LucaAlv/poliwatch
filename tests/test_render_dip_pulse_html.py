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
        self.assertIn('class="doc-link" href="https://www.bundestag.de/20-123.pdf"', card)
        self.assertRegex(
            card,
            r'<section class="speaker-section">\s*<h3>Rednerinnen und Redner</h3>',
        )
        self.assertNotRegex(
            card,
            r'class="detail-grid"[^>]*>\s*<section>\s*<h3>Rednerinnen und Redner</h3>',
        )
        self.assertNotIn("dev-only", card)
        dev_card = self._top_card(pulse_html.render_html(self.report, include_dev_view=True))
        self.assertRegex(dev_card, r'<section class="dev-only dev-top-details">[\s\S]*?class="detail-grid"')

    def test_documents_metadata_is_omitted_when_top_has_no_documents(self) -> None:
        report = copy.deepcopy(self.report)
        report["agenda_items"][0]["xml_drucksachen"] = []

        card = self._top_card(pulse_html.render_html(report))

        self.assertNotIn('class="top-documents"', card)
        self.assertNotIn("XML Drucksachen", card)
        self.assertIn('class="speaker-section"', card)

    def test_documents_metadata_keeps_documents_without_a_source_url(self) -> None:
        report = copy.deepcopy(self.report)
        report["agenda_items"][0]["xml_drucksachen"] = [
            {"dokumentnummer": "20/123", "url": "https://www.bundestag.de/20-123.pdf"},
            {"dokumentnummer": "20/456", "url": None},
        ]

        card = self._top_card(pulse_html.render_html(report))

        self.assertIn('class="doc-link" href="https://www.bundestag.de/20-123.pdf"', card)
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


class AttentionRankingTests(unittest.TestCase):
    """The Aufmerksamkeitsrang aside on the dossier page.

    The aside is sticky on desktop and stacks above the TOP list at or below
    1120px. These tests pin the two shapes that fix the "tail of the ranking
    is unreachable" bug: the capped, inner-scrolling aside (aside{display:flex;
    flex-direction:column; max-height} + .attention-list{overflow-y:auto;
    min-height:0}, which only work together) and the server-rendered collapse
    that the narrow layout shows. The CSS assertions are text assertions —
    there is no browser in CI — so they extract the exact rule blocks rather
    than matching substrings anywhere in the page.
    """

    @staticmethod
    def _item(index: int, speech_count: int, fractions: tuple[str, ...] = ("SPD",)) -> dict:
        return {
            "index": index,
            "top_id": f"TOP {index}",
            "heading": f"Beratung des Antrags {index}",
            "xml_speech_count": speech_count,
            "xml_speakers": [
                {"speaker": {"fraktion": fraction}, "char_count": 1000}
                for fraction in fractions
            ],
        }

    @classmethod
    def _render(cls, items: list[dict]) -> str:
        return pulse_html.render_html(
            {
                "protocol": {"dokumentnummer": "21/1", "titel": "Protokoll 21/1"},
                "validation_summary": {},
                "agenda_items": items,
            }
        )

    @staticmethod
    def _aside(markup: str) -> str:
        match = re.search(r"<aside[^>]*>.*?</aside>", markup, re.S)
        if match is None:
            raise AssertionError("Rendered dossier has no aside")
        return match.group(0)

    @staticmethod
    def _css_block(css: str, selector: str) -> str:
        """Body of the first `selector {` rule, brace-matched (rules may nest)."""
        start = css.find(selector + " {")
        if start < 0:
            raise AssertionError(f"No CSS rule for {selector!r}")
        depth = 0
        for pos in range(start, len(css)):
            if css[pos] == "{":
                depth += 1
            elif css[pos] == "}":
                depth -= 1
                if depth == 0:
                    return css[start:pos]
        raise AssertionError(f"Unbalanced CSS rule for {selector!r}")

    @staticmethod
    def _page_css(markup: str) -> str:
        blocks = re.findall(r"<style>(.*?)</style>", markup, re.S)
        for block in blocks:
            if ".attention-row {" in block:
                return block
        raise AssertionError("Dossier page has no attention CSS")

    def _assert_rows_resolve(self, markup: str, aside: str, expected_count: int) -> list[str]:
        """Rows sit inside #attention-list, every href lands on a card, every card links back."""
        list_match = re.search(r'<div class="attention-list" id="attention-list">(.*?)</div>', aside, re.S)
        self.assertIsNotNone(list_match)
        self.assertEqual(list_match.group(1).count('class="attention-row"'), expected_count)
        rows = re.findall(r'<a class="attention-row" href="#top-(\d+)">', aside)
        self.assertEqual(len(rows), expected_count)
        for index in rows:
            with self.subTest(top=index):
                self.assertIn(f'id="top-{index}"', markup)
        self.assertEqual(markup.count('class="back-to-rank" href="#aufmerksamkeitsrang"'), expected_count)
        return rows

    def test_rows_are_wrapped_in_a_scroll_list_and_still_resolve(self) -> None:
        # Speech counts are deliberately not monotonic in agenda order, so the
        # expected order below only holds if the renderer really sorts.
        counts = {1: 2, 2: 9, 3: 4, 4: 7, 5: 1, 6: 8, 7: 5}
        markup = self._render([self._item(i, counts[i]) for i in range(1, 8)])
        aside = self._aside(markup)

        self.assertRegex(aside, r'<aside[^>]*id="aufmerksamkeitsrang"')
        rows = self._assert_rows_resolve(markup, aside, 7)
        self.assertEqual(rows, ["2", "6", "4", "7", "3", "1", "5"], "rows must be sorted by speech count, descending")
        self.assertNotIn("<h2>Aufmerksamkeitsrang <span", aside, "no count badge; the header tile already carries the number")

    def test_collapse_is_rendered_server_side_above_the_preview_size(self) -> None:
        preview = pulse_html.ATTENTION_PREVIEW_ROWS

        at_limit = self._aside(self._render([self._item(i, 3) for i in range(1, preview + 1)]))
        self.assertNotRegex(at_limit, r'<aside[^>]*data-collapsed')
        self.assertNotIn('<button class="attention-toggle"', at_limit)

        over = self._aside(self._render([self._item(i, 3) for i in range(1, preview + 2)]))
        self.assertRegex(over, r'<aside[^>]*data-collapsed="true"')
        self.assertRegex(
            over,
            r'<button class="attention-toggle" type="button" aria-expanded="false" '
            r'aria-controls="attention-list" data-label-more="Alle %d Tagesordnungspunkte anzeigen" '
            r'data-label-less="Weniger anzeigen">Alle %d Tagesordnungspunkte anzeigen</button>'
            % (preview + 1, preview + 1),
        )
        # The toggle is rendered after the list so it sits below the rows.
        self.assertLess(over.index('id="attention-list"'), over.index('class="attention-toggle"'))

    def test_empty_states_replace_the_list_but_keep_the_anchor(self) -> None:
        none = self._aside(self._render([]))
        self.assertRegex(none, r'<aside[^>]*id="aufmerksamkeitsrang"')
        self.assertIn('<p class="ranking-empty">Keine Tagesordnungspunkte im XML-Protokoll gefunden.</p>', none)
        self.assertNotIn('class="attention-row"', none)
        self.assertNotIn('<button class="attention-toggle"', none)
        self.assertNotIn('class="legend"', none)
        self.assertNotIn('class="ranking-note"', none)

        silent = self._aside(self._render([self._item(i, 0, ()) for i in range(1, 4)]))
        self.assertIn('<p class="ranking-empty">Keine Reden im XML extrahiert – kein Ranking möglich.</p>', silent)
        self.assertNotIn('class="attention-row"', silent)
        self.assertNotRegex(silent, r'<aside[^>]*data-collapsed')

    def test_aside_cap_and_inner_scroll_are_one_fix(self) -> None:
        css = self._page_css(self._render([self._item(1, 1)]))

        aside = self._css_block(css, "aside")
        for declaration in (
            "display:flex;",
            "flex-direction:column;",
            "top:var(--aside-gap);",
            "max-height:calc(100vh - 2 * var(--aside-gap));",
            "max-height:calc(100dvh - 2 * var(--aside-gap));",
        ):
            self.assertIn(declaration, aside)
        scroll_list = self._css_block(css, ".attention-list")
        for declaration in ("overflow-y:auto;", "min-height:0;"):
            self.assertIn(declaration, scroll_list)
        self.assertIn("--aside-gap:14px;", self._css_block(css, ".layout"))
        self.assertIn("scroll-margin-top:var(--aside-gap);", aside)
        self.assertIn("scroll-margin-top:var(--aside-gap);", self._css_block(css, ".top-card"))

    def test_collapse_rules_live_only_in_screen_media_blocks(self) -> None:
        css = self._page_css(self._render([self._item(1, 1)]))
        desktop_rule = "nth-child(n+%d)" % (pulse_html.ATTENTION_PREVIEW_ROWS + 1)
        phone_rule = "nth-child(n+%d)" % (pulse_html.ATTENTION_PREVIEW_ROWS_PHONE + 1)

        self.assertEqual(css.count(desktop_rule), 1)
        self.assertEqual(css.count(phone_rule), 1)
        screen_1120 = self._css_block(css, "@media screen and (max-width: 1120px)")
        screen_720 = self._css_block(css, "@media screen and (max-width: 720px)")
        self.assertIn(":root[data-js] aside[data-collapsed=\"true\"] .attention-row:" + desktop_rule, screen_1120)
        self.assertIn(":root[data-js] .attention-toggle { display:block; }", screen_1120)
        self.assertIn(":root[data-js] aside[data-collapsed=\"true\"] .attention-row:" + phone_rule, screen_720)
        # The plain (print-matching) breakpoints never hide rows; the cap is
        # undone once, for narrow screens and print alike.
        self.assertNotIn("nth-child", self._css_block(css, "@media (max-width: 1120px)"))
        self.assertNotIn("nth-child", self._css_block(css, "@media (max-width: 720px)"))
        uncap = self._css_block(css, "@media (max-width: 1120px), (max-height: 480px), print")
        self.assertIn("aside { position:static; max-height:none; }", uncap)
        self.assertIn(".attention-list { overflow:visible; }", uncap)
        self.assertIn(".attention-list::after { display:none; }", uncap)
        self.assertEqual(css.count("aside { position:static; max-height:none; }"), 1)
        for block in ("@media (max-width: 1120px)", "@media (max-width: 720px)", "@media print"):
            self.assertNotIn("max-height:none", self._css_block(css, block), block)
        print_block = self._css_block(css, "@media print")
        self.assertIn(".attention-toggle, .back-to-rank, .ai-summary-toggle", print_block)
        self.assertIn("[data-ai-summary-body][hidden] { display:block !important; }", print_block)

    def test_toggle_is_not_forced_to_ink_in_dark_mode(self) -> None:
        markup = self._render([self._item(1, 1)])
        allowlist = re.search(
            r':root\[data-theme="dark"\] :is\((\s*\.site-nav a,.*?)\)\s*\{', markup, re.S
        )
        self.assertIsNotNone(allowlist, "dark-mode button allowlist not found")
        self.assertNotIn(".attention-toggle", allowlist.group(1))
        self.assertIn("color:var(--blue);", self._css_block(self._page_css(markup), ".attention-toggle"))
        self.assertRegex(markup, r':root\[data-theme="dark"\] :is\([^)]*\.ranking-empty')

    def test_runtime_is_guarded_on_pages_without_a_toggle(self) -> None:
        # The script ships on every dossier, including the empty states that
        # render no #attention-list and no toggle; it must return before it
        # touches either.
        script = pulse_html.attention_runtime_script()
        probe = 'document.getElementById("aufmerksamkeitsrang")'

        self.assertIn("if (!toggle) return;", script)
        self.assertLess(script.index("if (!toggle) return;"), script.index("addEventListener"))
        for markup in (self._render([]), self._render([self._item(i, 0, ()) for i in range(1, 4)])):
            self.assertIn(probe, markup)
            self.assertNotIn('id="attention-list"', markup)

    # -- regressions: existing markup the sidebar fix reshaped ---------------

    def test_ranking_header_and_note_replace_the_old_h2_block(self) -> None:
        # The aside used to open with a bare <h2> followed by a two-line
        # .ranking-note that carried the legend. The legend now sits next to
        # the heading in .ranking-head and the note is a single line.
        markup = self._render([self._item(1, 1)])
        aside = self._aside(markup)

        self.assertRegex(
            aside,
            r'<div class="ranking-head">\s*<h2>Aufmerksamkeitsrang</h2>\s*'
            r'<div class="legend"><span><i></i>Reden</span><span><i></i>Redetext</span></div>\s*</div>',
        )
        self.assertRegex(
            aside,
            r'<div class="ranking-note">Nach Anzahl der Reden sortiert · Balken: Anteil an der gesamten Sitzung</div>',
        )
        self.assertNotIn("Sortiert nach Anzahl der Reden.", aside)
        self.assertLess(aside.index('class="ranking-head"'), aside.index('class="ranking-note"'))
        self.assertLess(aside.index('class="ranking-note"'), aside.index('id="attention-list"'))
        css = self._page_css(markup)
        self.assertNotIn("aside h2 {", css)
        self.assertIn("margin:0;", self._css_block(css, ".ranking-head h2"))
        self.assertIn("display:flex;", self._css_block(css, ".ranking-head"))

    def test_top_head_keeps_eyebrow_then_back_link_then_heading(self) -> None:
        markup = self._render([self._item(1, 1)])
        aside_id = re.search(r'<aside[^>]*\bid="([^"]+)"', markup).group(1)
        card = re.search(r'<article class="top-card" id="top-1">(.*?)</article>', markup, re.S).group(1)
        head = re.search(r'<div class="top-head">(.*?)<div class="score">', card, re.S).group(1)

        self.assertRegex(
            head,
            r'<span class="eyebrow">TOP 1 · [^<]+</span>\s*'
            r'<a class="back-to-rank" href="#aufmerksamkeitsrang">↑ Aufmerksamkeitsrang</a>\s*'
            r"<h2>Beratung des Antrags 1</h2>",
        )
        self.assertEqual(f"#{aside_id}", re.search(r'class="back-to-rank" href="([^"]+)"', head).group(1))

    def test_js_marker_is_set_in_head_on_every_page_even_without_storage(self) -> None:
        # Every page (dossier and build_dip_pulse_site pages alike) emits the
        # marker through page_head. It has to sit outside the localStorage
        # try/catch so a blocked storage API still marks scripts as running.
        markup = self._render([self._item(1, 1)])
        marker = 'root.dataset.js = "1";'

        self.assertIn(marker, pulse_html.page_head())
        self.assertEqual(markup.count(marker), 1)
        self.assertLess(markup.index(marker), markup.index("</head>"))
        self.assertLess(markup.index("} catch (_) {}"), markup.index(marker))

    # -- coverage: branches and sizes the first tests did not reach ----------

    def test_zero_speeches_never_collapse_even_above_the_preview_size(self) -> None:
        # ranking_collapsed guards on total_speeches too: seven silent TOPs are
        # more than the preview size, yet nothing must be hidden or toggleable.
        silent = self._aside(
            self._render([self._item(i, 0, ()) for i in range(1, pulse_html.ATTENTION_PREVIEW_ROWS + 3)])
        )

        self.assertNotRegex(silent, r'<aside[^>]*data-collapsed')
        self.assertNotIn('<button class="attention-toggle"', silent)
        self.assertNotIn('id="attention-list"', silent)
        # No ranking, so nothing for the cards to link back to.
        self.assertNotIn('class="back-to-rank"', self._render([self._item(i, 0, ()) for i in range(1, 4)]))

    def test_missing_agenda_items_key_renders_the_empty_state(self) -> None:
        markup = pulse_html.render_html({"protocol": {"dokumentnummer": "21/1"}, "validation_summary": {}})
        aside = self._aside(markup)

        self.assertRegex(aside, r'<aside[^>]*id="aufmerksamkeitsrang"')
        self.assertIn('<p class="ranking-empty">Keine Tagesordnungspunkte im XML-Protokoll gefunden.</p>', aside)
        self.assertNotIn('class="attention-row"', aside)
        self.assertNotIn('<button class="attention-toggle"', aside)

    def test_thirty_tops_render_every_row_in_agenda_order_for_ties(self) -> None:
        # plenarprotokoll-20-169 has 30 TOPs. Sorting is stable, so TOPs with
        # the same speech count keep their agenda order instead of shuffling
        # the "map" the sidebar is meant to be.
        markup = self._render([self._item(i, 3 if i % 2 else 2) for i in range(1, 31)])
        aside = self._aside(markup)

        rows = self._assert_rows_resolve(markup, aside, 30)
        self.assertEqual(rows, [str(i) for i in range(1, 31, 2)] + [str(i) for i in range(2, 31, 2)])
        self.assertRegex(aside, r'<aside[^>]*data-collapsed="true"')
        self.assertIn('data-label-more="Alle 30 Tagesordnungspunkte anzeigen"', aside)

    def test_phone_preview_is_smaller_and_collapse_keys_on_the_desktop_size(self) -> None:
        # Both nth-child rules apply at <=720px, so the phone size must be the
        # smaller one to have any effect. Below the desktop threshold nothing
        # collapses at all - ATTENTION_PREVIEW_ROWS_PHONE + 1 TOPs are shown in
        # full on a phone too.
        self.assertGreater(pulse_html.ATTENTION_PREVIEW_ROWS_PHONE, 0)
        self.assertLessEqual(pulse_html.ATTENTION_PREVIEW_ROWS_PHONE, pulse_html.ATTENTION_PREVIEW_ROWS)

        between = self._aside(
            self._render([self._item(i, 2) for i in range(1, pulse_html.ATTENTION_PREVIEW_ROWS_PHONE + 2)])
        )
        self.assertNotRegex(between, r'<aside[^>]*data-collapsed')
        self.assertNotIn('<button class="attention-toggle"', between)
        self.assertEqual(between.count('class="attention-row"'), pulse_html.ATTENTION_PREVIEW_ROWS_PHONE + 1)

    def test_runtime_script_is_emitted_once_after_the_aside(self) -> None:
        markup = self._render([self._item(i, 2) for i in range(1, 8)])
        probe = 'document.getElementById("aufmerksamkeitsrang")'

        self.assertEqual(markup.count(probe), 1)
        self.assertLess(markup.index("</aside>"), markup.index(probe))
        # Before the first TOP card: the button must work as soon as it is on
        # screen, not after the multi-megabyte main has parsed.
        self.assertLess(markup.index(probe), markup.index('<article class="top-card"'))
        self.assertNotIn("aufmerksamkeitsrang", pulse_html.page_head())
        self.assertNotIn("aufmerksamkeitsrang", pulse_html.page_scripts())

    def test_runtime_script_identifiers_match_the_markup_and_css(self) -> None:
        # The script, the server-rendered attributes and the CSS agree on a
        # handful of names; renaming one side silently breaks the toggle.
        markup = self._render([self._item(i, 2) for i in range(1, 8)])
        aside = self._aside(markup)
        css = self._page_css(markup)
        script = pulse_html.attention_runtime_script()

        # The state contract: server renders data-collapsed="true" and
        # aria-expanded="false"; the first click must expand, the second
        # collapse and scroll the aside back into view.
        for ident in (
            'document.getElementById("aufmerksamkeitsrang")',
            'aside.querySelector(".attention-toggle")',
            'const collapsed = aside.dataset.collapsed !== "true";',
            'aside.dataset.collapsed = collapsed ? "true" : "false";',
            'toggle.setAttribute("aria-expanded", collapsed ? "false" : "true");',
            "toggle.textContent = collapsed ? toggle.dataset.labelMore : toggle.dataset.labelLess;",
            'if (collapsed) aside.scrollIntoView({ block: "nearest" });',
            "else if (revealed) revealed.focus();",
        ):
            with self.subTest(identifier=ident):
                self.assertIn(ident, script)
        controls = re.search(r'aria-controls="([^"]+)"', aside).group(1)
        self.assertIn(f'id="{controls}"', aside)
        self.assertEqual(controls, "attention-list")
        self.assertRegex(aside, r'<aside[^>]*\bdata-collapsed="true"')
        self.assertIn('aria-expanded="false"', aside)
        self.assertIn('data-label-more="', aside)
        self.assertIn('data-label-less="Weniger anzeigen"', aside)
        self.assertIn('aside[data-collapsed="true"] .attention-toggle { border-top:0; }', css)

    def test_controls_are_hidden_without_js_and_on_desktop(self) -> None:
        # Without [data-js] (no JavaScript) or on desktop, neither the toggle
        # nor the per-card back link may show; every row is visible instead.
        css = self._page_css(self._render([self._item(1, 1)]))

        self.assertIn("display:none;", self._css_block(css, ".attention-toggle"))
        self.assertEqual(css.count(".attention-toggle { display:block; }"), 1)
        self.assertIn("display:none;", self._css_block(css, ".back-to-rank"))
        screen_1120 = self._css_block(css, "@media screen and (max-width: 1120px)")
        self.assertRegex(screen_1120, r"\.back-to-rank \{[^}]*display:inline-flex;")
        # 44px hit area without inflating the eyebrow's line box: padding
        # extends the target, the negative block margin cancels it in layout.
        self.assertRegex(screen_1120, r"\.back-to-rank \{[^}]*padding-block:14px 6px;")
        self.assertRegex(screen_1120, r"\.back-to-rank \{[^}]*margin-block:-14px -6px;")
        toggle = self._css_block(css, ".attention-toggle")
        self.assertIn("min-height:44px;", toggle)
        self.assertIn("outline:2px solid var(--blue);", self._css_block(css, ".attention-toggle:focus-visible"))
        self.assertIn("background:", self._css_block(css, ".attention-toggle:hover"))

    def test_narrow_layout_removes_the_cap_and_the_fade(self) -> None:
        css = self._page_css(self._render([self._item(1, 1)]))

        # The fade is pure CSS: a sticky pseudo-element that scrolls away over
        # the last rows. No margin trick, no opacity toggle, no script state.
        fade = self._css_block(css, ".attention-list::after")
        for declaration in ("position:sticky;", "bottom:0;", "pointer-events:none;", "background:linear-gradient(transparent, var(--panel));"):
            self.assertIn(declaration, fade)
        for absent in ("margin-top:-", "opacity:", "transition:"):
            self.assertNotIn(absent, fade)
        self.assertNotIn("data-more", css)
        self.assertNotIn("dataset.more", pulse_html.attention_runtime_script())
        self.assertIn(".ranking-head .legend { font-size:12px; color:var(--muted); }", css)


if __name__ == "__main__":
    unittest.main()
