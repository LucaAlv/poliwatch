from __future__ import annotations

import copy
from html.parser import HTMLParser
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

    def test_ranking_anchors_resolve_to_top_cards(self) -> None:
        class Anchors(HTMLParser):
            def __init__(self):
                super().__init__()
                self.targets = set()
                self.links = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if attrs.get("class") == "top-card":
                    self.targets.add(attrs["id"])
                if attrs.get("class") == "attention-row":
                    self.links.append(attrs["href"][1:])

        for index in (1, '1"&<>'):
            with self.subTest(index=index):
                report = copy.deepcopy(self.report)
                report["agenda_items"][0]["index"] = index
                anchors = Anchors()
                anchors.feed(pulse_html.render_html(report))
                self.assertTrue(anchors.links)
                self.assertTrue(set(anchors.links) <= anchors.targets)
                self.assertIn(f"top-{index}", anchors.targets)

    def test_protocol_dev_dump_follows_content_and_is_opt_in(self) -> None:
        normal = pulse_html.render_html(self.report)
        self.assertNotIn('class="api-overview dev-only"', normal)
        dev = pulse_html.render_html(self.report, include_dev_view=True)
        self.assertGreater(dev.index('class="api-overview dev-only"'), dev.index('</main>'))
        self.assertLess(dev.index('class="dev-only dev-top-details"'), dev.index('</main>'))
        self.assertIn('class="api-overview dev-only"', dev)

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

    def test_footer_links_to_the_daten_page_between_abgeordnete_and_quellen(self) -> None:
        # Same relative-path depth as its neighbours (dossiers live one level
        # down, under protocols/) and the same position render_overview uses
        # for this link: right before Quellen.
        markup = pulse_html.render_html(self.report)
        footer = re.search(r"<footer>.*?</footer>", markup, re.S).group(0)

        self.assertIn('<a href="../database.html">Daten</a>', footer)
        self.assertLess(footer.index("../abgeordnete/index.html"), footer.index("../database.html"))
        self.assertLess(footer.index("../database.html"), footer.index("../sources.html"))


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
        rows = re.findall(r'<a class="attention-row" href="#top-(\d+)"(?: title="[^"]*")?>', aside)
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

    def test_row_titles_show_topic_and_keep_full_heading_in_tooltip(self) -> None:
        topic = (
            'zur "Sicherung & Zukunft" <Thema> mit einem sehr langen ergänzenden Abschnitt, '
            "der die sichtbare Zeile über ihre maximale Länge hinaus verlängert"
        )
        normalized_heading = (
            "Beratung des Antrags der Abgeordneten Nicole Höchst und der Fraktion der CDU/CSU "
            + topic
        )
        heading = "  " + normalized_heading.replace(" Nicole", "\nNicole") + "  "
        item = self._item(1, 1)
        item["heading"] = heading

        row = re.search(r'<a class="attention-row"[^>]*>.*?</a>', self._render([item]), re.S)
        self.assertIsNotNone(row)
        rendered = row.group(0)
        self.assertIn(
            'title="Beratung des Antrags der Abgeordneten Nicole Höchst und der Fraktion der CDU/CSU '
            'zur &quot;Sicherung &amp; Zukunft&quot; &lt;Thema&gt; mit einem sehr langen ergänzenden Abschnitt, '
            'der die sichtbare Zeile über ihre maximale Länge hinaus verlängert"',
            rendered,
        )
        self.assertIn(
            'class="row-title">zur &quot;Sicherung &amp; Zukunft&quot; &lt;Thema&gt; mit einem sehr langen '
            'ergänzenden Abschnitt…</span>',
            rendered,
        )
        self.assertNotIn("Beratung des Antrags", rendered.split('<span class="row-title">', 1)[1].split('</span>', 1)[0])

    def test_row_titles_keep_plain_headings_and_omit_empty_tooltips(self) -> None:
        plain = self._item(1, 1)
        plain["heading"] = "Ein unerkannter Tagesordnungspunkt"
        missing = self._item(2, 1)
        missing["heading"] = None
        aside = self._aside(self._render([plain, missing]))
        rows = re.findall(r'<a class="attention-row"[^>]*>.*?</a>', aside, re.S)
        self.assertEqual(len(rows), 2)
        self.assertIn('title="Ein unerkannter Tagesordnungspunkt"', rows[0])
        self.assertNotIn(" title=", rows[1].split(">", 1)[0])
        self.assertIn('class="row-title">Ein unerkannter Tagesordnungspunkt</span>', rows[0])
        self.assertIn('class="row-title"></span>', rows[1])

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


class CurrentTopHighlightTests(unittest.TestCase):
    """The IntersectionObserver that marks the current .attention-row."""

    @staticmethod
    def _item(index: int, speech_count: int = 1) -> dict:
        return {
            "index": index,
            "top_id": f"TOP {index}",
            "heading": f"Beratung des Antrags {index}",
            "xml_speech_count": speech_count,
            "xml_speakers": [{"speaker": {"fraktion": "SPD"}, "char_count": 1000}],
        }

    @classmethod
    def _render(cls, count: int = 3) -> str:
        return pulse_html.render_html(
            {
                "protocol": {"dokumentnummer": "21/1", "titel": "Protokoll 21/1"},
                "validation_summary": {},
                "agenda_items": [cls._item(i) for i in range(1, count + 1)],
            }
        )

    def test_script_is_guarded_when_intersection_observer_or_list_are_missing(self) -> None:
        script = pulse_html.attention_runtime_script()
        guard = 'if (!list || typeof IntersectionObserver !== "function") return;'
        self.assertIn(guard, script)
        self.assertLess(script.index(guard), script.index("new IntersectionObserver"))

    def test_current_row_styling_is_keyed_on_aria_current(self) -> None:
        css = AttentionRankingTests._page_css(self._render())
        rule = AttentionRankingTests._css_block(css, '.attention-row[aria-current="true"]')
        self.assertIn("background:var(--blue-soft, #eef5ff);", rule)
        self.assertIn("box-shadow:inset 3px 0 0 var(--blue);", rule)

    def test_off_at_the_same_breakpoint_the_static_aside_css_uses(self) -> None:
        # The CSS uncaps the aside (position:static) at this exact query (plus
        # print, irrelevant to matchMedia while reading on screen); the script
        # must stop observing at the same width/height so it never marks a row
        # "current" in a layout with no sticky rail to show it on.
        script = pulse_html.attention_runtime_script()
        self.assertIn('window.matchMedia("(max-width: 1120px), (max-height: 480px)")', script)

    def test_reveal_scrolls_only_the_list_never_the_page(self) -> None:
        script = pulse_html.attention_runtime_script()
        observer_part = script.split('document.getElementById("attention-list")', 1)[1]
        self.assertIn("list.scrollBy({", script)
        self.assertNotIn(".scrollIntoView(", observer_part)
        self.assertIn('reducedMotion.matches ? "auto" : "smooth"', script)

    def test_root_margin_is_left_at_the_full_viewport(self) -> None:
        # A shrunk top-band root margin (the usual scrollspy trick) leaves a
        # dead zone above the band that the page header sits in, so nothing
        # would be "current" until the first card scrolled up into it. Caught
        # live in a browser check; the fix is to observe the full viewport
        # (no rootMargin option at all) and let pickCurrent's own rule decide
        # "nearest the top" from live geometry instead.
        script = pulse_html.attention_runtime_script()
        self.assertIn("new IntersectionObserver(onIntersect);", script)
        self.assertNotIn("rootMargin:", script)

    def test_pick_current_prefers_a_reached_card_over_one_still_descending(self) -> None:
        script = pulse_html.attention_runtime_script()
        for identifier in (
            "if (!reached || top > reached.top) reached = { card, top };",
            "} else if (!pending || top < pending.top) {",
            "const winner = reached || pending;",
        ):
            with self.subTest(identifier=identifier):
                self.assertIn(identifier, script)

    def test_runtime_script_is_still_emitted_once_after_the_aside(self) -> None:
        # Both jobs (toggle + observer) share the one <script> tag placed
        # right after the aside; this must stay a single tag, not a second
        # one elsewhere in the page.
        markup = self._render()
        self.assertEqual(markup.count("<script>"), markup.count("</script>"))
        self.assertEqual(markup.count('document.getElementById("attention-list")'), 1)
        self.assertLess(markup.index("</aside>"), markup.index('document.getElementById("attention-list")'))
        self.assertLess(markup.index('document.getElementById("attention-list")'), markup.index('<article class="top-card"'))


class WeekRadarHelperTests(unittest.TestCase):
    """Pure helpers behind the puls.html week radar (build order §1-2)."""

    @staticmethod
    def _position(vorgang_id: str, titel: str, typ: str = "Antrag", stage: str = "Beratung", twins=()):
        return {
            "id": f"pos-{vorgang_id}",
            "vorgang_id": vorgang_id,
            "titel": titel,
            "vorgangstyp": typ,
            "vorgangsposition": stage,
            "mitberaten": [
                {"id": tid, "titel": ttitel, "vorgangstyp": ttyp, "vorgangsposition": tstage}
                for tid, ttitel, ttyp, tstage in twins
            ],
        }

    @staticmethod
    def _item(positions, heading="Beratung des Antrags der Abgeordneten X", top_id="Tagesordnungspunkt 8", index=8):
        return {"index": index, "top_id": top_id, "heading": heading, "api": {"positions": positions}}

    # -- dates and counts ---------------------------------------------------

    def test_date_helpers_use_a_fixed_german_weekday_table(self) -> None:
        self.assertEqual(pulse_html.format_sitting_date("2026-06-12"), "Fr 12.06.")
        self.assertEqual(pulse_html.format_date("2026-06-12"), "12.06.2026")
        self.assertEqual(pulse_html.format_date("2026-06-12T09:00:00"), "12.06.2026")
        self.assertEqual(pulse_html.format_sitting_date(None), "")
        self.assertEqual(pulse_html.format_date("12.06.2026"), "")
        self.assertEqual(pulse_html.format_date("2026-13-40"), "")

    def test_format_count_picks_singular_and_thousands_separator(self) -> None:
        self.assertEqual(pulse_html.format_count(1, "Rede", "Reden"), "1 Rede")
        self.assertEqual(pulse_html.format_count(1234, "Rede", "Reden"), "1.234 Reden")
        self.assertEqual(pulse_html.format_count(0, "Wortmeldung", "Wortmeldungen"), "0 Wortmeldungen")

    def test_question_format_is_a_prefix_match_on_the_normalised_heading(self) -> None:
        self.assertTrue(pulse_html.is_question_format({"heading": "  Befragung  der Bundesregierung (einleitend BMJ)"}))
        self.assertTrue(pulse_html.is_question_format({"heading": "Fragestunde"}))
        self.assertTrue(pulse_html.is_question_format({"heading": "Regierungsbefragung"}))
        self.assertFalse(pulse_html.is_question_format({"heading": "Beratung des Antrags: Befragung der Bundesregierung reformieren"}))
        self.assertFalse(pulse_html.is_question_format({"heading": None}))
        self.assertFalse(pulse_html.is_question_format({}))

    def test_safe_href_allows_only_allowlisted_https_sources(self) -> None:
        self.assertEqual(pulse_html.safe_href("https://dserver.bundestag.de/x.pdf"), "https://dserver.bundestag.de/x.pdf")
        self.assertIsNone(pulse_html.safe_href(" HTTP://example.test/a "))
        self.assertIsNone(pulse_html.safe_href("https://example.test/a"))
        self.assertIsNone(pulse_html.safe_href("javascript:alert(1)"))
        self.assertIsNone(pulse_html.safe_href("data:text/html,hi"))
        self.assertIsNone(pulse_html.safe_href(""))
        self.assertIsNone(pulse_html.safe_href(None))

    # -- party stack ---------------------------------------------------------

    def test_party_stack_exact_widths_and_own_class_for_the_radar(self) -> None:
        counter = pulse_html.Counter({"CDU/CSU": 18, "fraktionslos": 1})
        markup = pulse_html.render_party_stack(counter, 19, min_width=0.0, class_name="who-stack")
        self.assertIn('<div class="who-stack">', markup)
        self.assertIn('width:5.26%', markup)
        self.assertIn('title="fraktionslos: 1"', markup)
        self.assertEqual(pulse_html.render_party_stack(pulse_html.Counter(), 0, class_name="who-stack"), '<div class="who-stack empty"></div>')

    def test_party_stack_default_call_keeps_the_dossier_contract(self) -> None:
        counter = pulse_html.Counter({"CDU/CSU": 99, "fraktionslos": 1})
        markup = pulse_html.render_party_stack(counter, 100)
        self.assertIn('<div class="stack">', markup)
        self.assertIn('width:4.00%', markup)  # the 4% floor still applies by default
        self.assertEqual(pulse_html.render_party_stack(pulse_html.Counter(), 0), '<div class="stack empty"></div>')

    # -- topic identity -----------------------------------------------------

    def test_gesetzgebung_position_leads_a_mixed_group(self) -> None:
        item = self._item([
            self._position("A1", "Antrag eins"),
            self._position("G1", "Gesetz zur Sache", "Gesetzgebung", "1. Beratung"),
            self._position("A2", "Antrag zwei"),
        ])
        identity = pulse_html.topic_identity(item)
        self.assertEqual(identity["lead_title"], "Gesetz zur Sache")
        self.assertFalse(identity["equal_weight"])
        self.assertEqual(identity["titles"], ["Antrag eins", "Gesetz zur Sache", "Antrag zwei"])
        self.assertEqual(identity["vorgang_ids"], ["A1", "G1", "A2"])
        self.assertEqual(pulse_html.type_label(identity), "Gesetzgebung · 1. Beratung · mit 2 Anträgen")

    def test_a_gesetzgebung_twin_leads_even_when_every_position_is_an_antrag(self) -> None:
        item = self._item([
            self._position("A1", "Antrag eins", twins=[("G1", "Gebäudeenergiegesetz", "Gesetzgebung", "1. Beratung")]),
        ])
        identity = pulse_html.topic_identity(item)
        self.assertEqual(identity["lead_title"], "Gebäudeenergiegesetz")
        self.assertEqual(identity["vorgang_ids"], ["A1", "G1"])
        self.assertEqual(pulse_html.type_label(identity), "Gesetzgebung · 1. Beratung · mit 1 Antrag")

    def test_antrag_only_group_with_several_titles_is_equal_weight(self) -> None:
        # Real shape: every position lists the other three as mitberaten twins.
        ids = [("A1", "Bildung bezahlbar machen"), ("A2", "Zukunftsinvestitionen statt Kürzungen"),
               ("A3", "Bildung darf nicht vom Einkommen abhängen"), ("A4", "BAföG stärken")]
        positions = [
            self._position(vid, titel, twins=[(oid, otitel, "Antrag", "Beratung") for oid, otitel in ids if oid != vid])
            for vid, titel in ids
        ]
        identity = pulse_html.topic_identity(item := self._item(positions))
        self.assertTrue(identity["equal_weight"])
        self.assertIsNone(identity["lead_title"])
        self.assertEqual(len(identity["procedures"]), 4)  # twins must not double-count
        self.assertEqual(identity["titles"], [titel for _, titel in ids])
        self.assertEqual(pulse_html.type_label(identity), "Antrag · Beratung · 4 Anträge gemeinsam")
        self.assertNotIn(item["heading"], identity["titles"])

    def test_identical_titles_under_different_ids_stay_two_procedures(self) -> None:
        item = self._item([self._position("A1", "Gleicher Titel"), self._position("A2", "Gleicher  Titel ")])
        identity = pulse_html.topic_identity(item)
        self.assertEqual(len(identity["procedures"]), 2)
        self.assertEqual(identity["titles"], ["Gleicher Titel"])  # whitespace variant collapsed for display
        self.assertFalse(identity["equal_weight"])  # one distinct title, so a lead
        self.assertEqual(identity["lead_title"], "Gleicher Titel")
        self.assertEqual(pulse_html.type_label(identity), "Antrag · Beratung · 2 Anträge gemeinsam")

    def test_single_antrag_has_a_plain_label(self) -> None:
        identity = pulse_html.topic_identity(self._item([self._position("A1", "Nur einer")]))
        self.assertEqual(identity["lead_title"], "Nur einer")
        self.assertEqual(pulse_html.type_label(identity), "Antrag · Beratung")

    def test_mixed_non_gesetzgebung_remainder_uses_the_neutral_noun(self) -> None:
        item = self._item([
            self._position("G1", "Gesetz", "Gesetzgebung", "2. Beratung"),
            self._position("A1", "Antrag", "Antrag"),
            self._position("E1", "Entschließung", "Entschließungsantrag"),
        ])
        self.assertEqual(pulse_html.type_label(pulse_html.topic_identity(item)), "Gesetzgebung · 2. Beratung · mit 2 weiteren Vorlagen")

    def test_fallback_chain_applies_only_without_titles(self) -> None:
        heading = "Abgabe einer Regierungserklärung durch den Bundeskanzler"
        identity = pulse_html.topic_identity(self._item([], heading=heading))
        self.assertEqual(identity["lead_title"], heading)
        self.assertFalse(identity["equal_weight"])
        self.assertEqual(pulse_html.type_label(identity), "")
        self.assertEqual(pulse_html.topic_identity(self._item([], heading="", top_id="Einzelplan 17"))["lead_title"], "Einzelplan 17")
        self.assertEqual(pulse_html.topic_identity(self._item([], heading="", top_id="", index=3))["lead_title"], "Tagesordnungspunkt 3")
        long_heading = "x" * 300
        self.assertLessEqual(len(pulse_html.topic_identity(self._item([], heading=long_heading))["lead_title"]), pulse_html.RADAR_TITLE_CHARS)

    def test_positions_without_titles_still_yield_procedures(self) -> None:
        item = self._item([self._position("A1", ""), self._position("A2", "")], heading="Beratung ohne Titel")
        identity = pulse_html.topic_identity(item)
        self.assertEqual(identity["vorgang_ids"], ["A1", "A2"])
        self.assertEqual(identity["titles"], [])
        self.assertEqual(identity["lead_title"], "Beratung ohne Titel")
        self.assertFalse(identity["equal_weight"])


class SessionSummaryReceiptTests(unittest.TestCase):
    """Characterization of the dossier's KI-Zusammenfassung receipts, taken before the
    receipt construction is shared with the puls.html week radar (build order §5)."""

    @staticmethod
    def _item(index: int, chunks, rede_ids=("r-1", "r-2", "r-3", "r-4", "r-5", "r-6")) -> dict:
        speakers = [
            {"rede_id": rid, "char_count": 100, "speaker": {"fraktion": "SPD", "display_name": f"P{rid}"}}
            for rid in rede_ids
        ]
        return {
            "index": index,
            "top_id": f"Tagesordnungspunkt {index}",
            "heading": "Erste Beratung <b>x</b>",
            "xml_speakers": speakers,
            "xml_speech_count": len(speakers),
            "llm_summary": {"text": "Zusammenfassung & <Test>", "source_chunks": chunks},
        }

    @classmethod
    def _render(cls, items, pdf_url="https://dserver.bundestag.de/pp.pdf") -> str:
        stats = {item["index"]: pulse_html.item_stats(item) for item in items}
        protocol = {"pdf_url": pdf_url} if pdf_url else {}
        return pulse_html.render_session_llm_summary(items, stats, {"enabled": True}, protocol)

    def test_receipts_link_resolved_chunks_and_cap_at_four(self) -> None:
        chunks = [{"id": f"C{i}", "rede_id": f"r-{i}", "source_page": {"page": 100 + i, "quadrant": "A"}} for i in range(1, 7)]
        markup = self._render([self._item(1, chunks)])
        sources = re.search(r'<div class="session-summary-sources">(.*?)</div>', markup, re.S).group(1)
        self.assertEqual(sources.count("<a "), 5)  # 4 chunks + Originalprotokoll
        self.assertIn('<a href="#speech-1-r-1">C1 · S. 101A</a>', sources)
        self.assertIn('<a href="#speech-1-r-4">C4 · S. 104A</a>', sources)
        self.assertNotIn("C5", sources)
        self.assertIn('<a href="https://dserver.bundestag.de/pp.pdf">Originalprotokoll</a>', sources)

    def test_unresolved_chunk_degrades_to_a_span_and_missing_pdf_drops_the_link(self) -> None:
        chunks = [{"id": "C9", "rede_id": "r-missing", "source_page": {"page": 7}}, {"id": "C1", "rede_id": "r-1"}]
        markup = self._render([self._item(1, chunks)], pdf_url=None)
        sources = re.search(r'<div class="session-summary-sources">(.*?)</div>', markup, re.S).group(1)
        self.assertIn("<span>C9 · S. 7</span>", sources)
        self.assertIn('<a href="#speech-1-r-1">C1</a>', sources)
        self.assertNotIn("Originalprotokoll", sources)

    def test_summary_text_and_heading_are_escaped(self) -> None:
        markup = self._render([self._item(1, [{"id": "C1", "rede_id": "r-1"}])])
        self.assertIn("<p>Zusammenfassung &amp; &lt;Test&gt;</p>", markup)
        self.assertIn("<h3>Erste Beratung &lt;b&gt;x&lt;/b&gt;</h3>", markup)

    def test_section_shape_is_stable(self) -> None:
        markup = self._render([self._item(1, [{"id": "C1", "rede_id": "r-1"}]), self._item(2, [])])
        # Only the item with chunks is summarised; the count label reflects it.
        self.assertIn('>1 TOP-Zusammenfassung · Methode</a>', markup)
        self.assertEqual(markup.count('<article class="session-summary-item">'), 1)
        self.assertIn('<a class="top-jump" href="#top-1">Tagesordnungspunkt 1</a>', markup)

    def test_render_receipts_prefixes_a_dossier_href_and_refuses_unsafe_pdf_urls(self) -> None:
        item = self._item(3, [{"id": "C1", "rede_id": "r-1"}, {"id": "C2", "rede_id": "r-9"}])
        stats = pulse_html.item_stats(item)
        markup = pulse_html.render_receipts(
            item, stats, item["llm_summary"], dossier_href="protocols/plenarprotokoll-21-84.html", pdf_url="javascript:alert(1)"
        )
        self.assertIn('<a href="protocols/plenarprotokoll-21-84.html#speech-3-r-1">C1</a>', markup)
        self.assertIn("<span>C2</span>", markup)
        self.assertNotIn("Originalprotokoll", markup)
        self.assertNotIn("javascript:", markup)
        capped = pulse_html.render_receipts(
            item, stats, {"source_chunks": [{"id": f"C{i}", "rede_id": "r-1"} for i in range(9)]}, limit=2
        )
        self.assertEqual(capped.count("<a "), 2)

    def test_receipts_label_chunks_without_page_or_id_and_tolerate_a_summary_without_chunks(self) -> None:
        item = self._item(4, [])
        stats = pulse_html.item_stats(item)
        chunks = [{"id": "C7", "rede_id": "r-2"}, {"rede_id": "r-3"}, {}]
        markup = pulse_html.render_receipts(item, stats, {"source_chunks": chunks}, pdf_url="https://dserver.bundestag.de/pp.pdf")
        self.assertEqual(
            markup,
            '<a href="#speech-4-r-2">C7</a>'
            '<a href="#speech-4-r-3">Quelle</a>'
            "<span>Quelle</span>"
            '<a href="https://dserver.bundestag.de/pp.pdf">Originalprotokoll</a>',
        )
        self.assertEqual(pulse_html.render_receipts(item, stats, {}), "")
        self.assertEqual(
            pulse_html.render_receipts(
                item,
                stats,
                {"source_chunks": None},
                pdf_url=" https://dserver.bundestag.de/p.pdf ",
            ),
            '<a href="https://dserver.bundestag.de/p.pdf">Originalprotokoll</a>',
        )

    def test_dossier_summary_drops_a_non_http_pdf_link(self) -> None:
        # The dossier page shares render_receipts, so a scheme-less or scripted
        # pdf_url from a cached protocol no longer becomes an Originalprotokoll link.
        for url in ("javascript:alert(1)", "dserver.bundestag.de/pp.pdf", "data:text/html,x"):
            markup = self._render([self._item(1, [{"id": "C1", "rede_id": "r-1"}])], pdf_url=url)
            sources = re.search(r'<div class="session-summary-sources">(.*?)</div>', markup, re.S).group(1)
            self.assertEqual(sources, '<a href="#speech-1-r-1">C1</a>', url)
        markup = self._render([self._item(1, [{"id": "C1", "rede_id": "r-1"}])], pdf_url="HTTPS://dserver.bundestag.de/pp.pdf")
        self.assertIn('<a href="HTTPS://dserver.bundestag.de/pp.pdf">Originalprotokoll</a>', markup)


class WeekRadarLabelEdgeTests(unittest.TestCase):
    """type_label / topic_identity branches not reached by the mainline groups."""

    _position = staticmethod(WeekRadarHelperTests._position)
    _item = staticmethod(WeekRadarHelperTests._item)

    def _label(self, positions) -> str:
        return pulse_html.type_label(pulse_html.topic_identity(self._item(positions)))

    def test_remainder_wording_by_type_count_and_case(self) -> None:
        self.assertEqual(
            self._label([
                self._position("G1", "Erstes Gesetz", "Gesetzgebung", "1. Beratung"),
                self._position("G2", "Zweites Gesetz", "Gesetzgebung", "1. Beratung"),
                self._position("G3", "Drittes Gesetz", "Gesetzgebung", "1. Beratung"),
            ]),
            "Gesetzgebung · 1. Beratung · 3 Gesetzentwürfe gemeinsam",
        )
        self.assertEqual(
            self._label([
                self._position("E1", "Entschließung eins", "Entschließungsantrag"),
                self._position("E2", "Entschließung zwei", "Entschließungsantrag"),
            ]),
            "Entschließungsantrag · Beratung · 2 Entschließungsanträge gemeinsam",
        )
        # A type without a plural table entry, repeated: the neutral noun.
        self.assertEqual(
            self._label([
                self._position("U1", "Bericht eins", "Unterrichtung"),
                self._position("U2", "Bericht zwei", "Unterrichtung"),
            ]),
            "Unterrichtung · Beratung · 2 Vorlagen gemeinsam",
        )
        # Mixed remainders of one known type take the dative plural or the singular.
        self.assertEqual(
            self._label([
                self._position("A1", "Antrag", "Antrag"),
                self._position("E1", "Entschließung eins", "Entschließungsantrag"),
                self._position("E2", "Entschließung zwei", "Entschließungsantrag"),
            ]),
            "Antrag · Beratung · mit 2 Entschließungsanträgen",
        )
        self.assertEqual(
            self._label([
                self._position("A1", "Antrag", "Antrag"),
                self._position("E1", "Entschließung", "Entschließungsantrag"),
            ]),
            "Antrag · Beratung · mit 1 Entschließungsantrag",
        )
        self.assertEqual(
            self._label([
                self._position("A1", "Antrag", "Antrag"),
                self._position("G1", "Gesetz", "Gesetzgebung", "2. Beratung"),
                self._position("G2", "Gesetz zwei", "Gesetzgebung", "2. Beratung"),
            ]),
            # The first Gesetzgebung leads even when listed second; the remainder
            # (an Antrag and a second Gesetzentwurf) is mixed, hence the neutral noun.
            "Gesetzgebung · 2. Beratung · mit 2 weiteren Vorlagen",
        )

    def test_unknown_single_remainder_and_untyped_remainders_use_the_neutral_singular(self) -> None:
        self.assertEqual(
            self._label([
                self._position("G1", "Gesetz", "Gesetzgebung", "1. Beratung"),
                self._position("U1", "Bericht", "Unterrichtung"),
            ]),
            "Gesetzgebung · 1. Beratung · mit 1 weiteren Vorlage",
        )
        self.assertEqual(
            self._label([
                self._position("A1", "Antrag", "Antrag"),
                self._position("X1", "Ohne Typ", ""),
                self._position("X2", "Auch ohne Typ", ""),
            ]),
            "Antrag · Beratung · mit 2 weiteren Vorlagen",
        )
        # Empty ids never become procedures; a lead without a title borrows the first title.
        identity = pulse_html.topic_identity(self._item([
            self._position("", "Verwaist", "Antrag"),
            self._position("G1", "", "Gesetzgebung", "1. Beratung"),
            self._position("A1", "Antrag mit Titel", "Antrag"),
        ]))
        self.assertEqual(identity["vorgang_ids"], ["G1", "A1"])
        self.assertEqual(identity["lead"]["vorgang_id"], "G1")
        self.assertEqual(identity["lead_title"], "Antrag mit Titel")
        self.assertFalse(identity["equal_weight"])
        self.assertEqual(pulse_html.type_label(identity), "Gesetzgebung · 1. Beratung · mit 1 Antrag")


class DossierSourceLinkTests(unittest.TestCase):
    """The dossier's own source links share safe_href with the receipts."""

    def test_position_and_activity_titles_link_only_to_http_pdfs(self) -> None:
        item = {
            "api": {
                "positions": [
                    {"titel": "Gesetz A", "vorgangsposition": "1. Beratung", "vorgang_id": "V1",
                     "source": {"pdf_url": "https://dserver.bundestag.de/btp/21/21082.pdf"}},
                    {"titel": "Gesetz B", "vorgangsposition": "1. Beratung", "vorgang_id": "V2",
                     "source": {"pdf_url": "javascript:alert(1)"}},
                    {"titel": "Gesetz C", "vorgangsposition": "1. Beratung", "vorgang_id": "V3"},
                ],
                "activities": [
                    {"titel": "Rede A", "aktivitaetsart": "Rede", "pdf_url": "https://dserver.bundestag.de/btp/21/21082.pdf"},
                    {"titel": "Rede B", "aktivitaetsart": "Rede", "pdf_url": "data:text/html,x"},
                ],
            }
        }
        positions = pulse_html.render_positions(item)
        self.assertIn('<a href="https://dserver.bundestag.de/btp/21/21082.pdf">Gesetz A</a>', positions)
        self.assertNotIn("javascript:", positions)
        self.assertIn("Gesetz B", positions)
        self.assertIn("Gesetz C", positions)
        self.assertEqual(positions.count("<a "), 1)
        activities = pulse_html.render_activities(item)
        self.assertIn('<a href="https://dserver.bundestag.de/btp/21/21082.pdf">Rede A</a>', activities)
        self.assertNotIn("data:", activities)
        self.assertIn("Rede B", activities)
        self.assertEqual(activities.count("<a "), 1)

    def test_dev_details_pdf_source_links_only_to_http(self) -> None:
        def details(url: str) -> str:
            item = {"index": 1, "api": {"positions": [{"titel": "X", "source": {"pdf_url": url}}]}}
            return pulse_html.render_top_dev_details(item)
        self.assertIn('<a href="https://dserver.bundestag.de/btp/21/21082.pdf">PDF-Quelle</a>', details("https://dserver.bundestag.de/btp/21/21082.pdf"))
        unsafe = details("javascript:alert(1)")
        self.assertNotIn("javascript:", unsafe)
        self.assertIn("Keine direkte PDF-Verknüpfung", unsafe)

    def test_per_top_summary_offers_the_original_only_for_http_pdfs(self) -> None:
        item = SessionSummaryReceiptTests._item(1, [{"id": "C1", "rede_id": "r-1", "speaker": {"display_name": "P", "fraktion": "SPD"}}])
        stats = pulse_html.item_stats(item)
        with_pdf = pulse_html.render_llm_summary(item, stats, {"enabled": True}, {"pdf_url": "https://dserver.bundestag.de/pp.pdf"})
        self.assertIn('<a href="https://dserver.bundestag.de/pp.pdf">Originalprotokoll (PDF)</a>', with_pdf)
        without = pulse_html.render_llm_summary(item, stats, {"enabled": True}, {"pdf_url": "javascript:alert(1)"})
        self.assertNotIn("Originalprotokoll (PDF)", without)
        self.assertNotIn("javascript:", without)
        self.assertEqual(without, pulse_html.render_llm_summary(item, stats, {"enabled": True}, {}))


class AgendaTopicTests(unittest.TestCase):
    """agenda_topic() resolves an agenda item to a readable topic (plan D22)."""

    # The four shapes an agenda item can have. Real rows from the store built
    # 2026-09-19; the Haushaltsgesetz heading and its Vorgang title are the
    # same item.
    HAUSHALT_HEADING = (
        "1 a) Erste Beratung des von der Bundesregierung eingebrachten Entwurfs "
        "eines Gesetzes über die Feststellung des Bundeshaushaltsplans für das "
        "Haushaltsjahr 2027 (Haushaltsgesetz 2027 - HG 2027)"
    )

    def test_a_proceeding_title_wins_over_the_heading(self) -> None:
        self.assertEqual(
            pulse_html.agenda_topic("Haushaltsgesetz 2027", self.HAUSHALT_HEADING),
            "Haushaltsgesetz 2027",
        )

    def test_a_boilerplate_heading_loses_its_procedural_opener(self) -> None:
        self.assertEqual(
            pulse_html.agenda_topic(None, self.HAUSHALT_HEADING),
            "Gesetz über die Feststellung des Bundeshaushaltsplans für das "
            "Haushaltsjahr 2027 (Haushaltsgesetz 2027 - HG 2027)",
        )
        self.assertEqual(
            pulse_html.agenda_topic(
                "",
                "Beratung des Antrags der Abgeordneten Schahina Gambir, Dr. Ophelia Nick, "
                "weiterer Abgeordneter und der Fraktion BÜNDNIS 90/DIE GRÜNEN "
                "Ernährungssouveränität herstellen",
            ),
            "Ernährungssouveränität herstellen",
        )
        self.assertEqual(
            pulse_html.agenda_topic(
                None,
                "Aktuelle Stunde auf Verlangen der Fraktionen der CDU/CSU und SPD "
                "Ungarn nach der Wahl – Neue Chance für Europa",
            ),
            "Ungarn nach der Wahl – Neue Chance für Europa",
        )

    def test_a_plain_heading_is_returned_unchanged(self) -> None:
        self.assertEqual(pulse_html.agenda_topic(None, "Fragestunde"), "Fragestunde")
        self.assertEqual(
            pulse_html.agenda_topic(None, "  Befragung der\n Bundesregierung "),
            "Befragung der Bundesregierung",
        )

    def test_neither_a_title_nor_a_heading_yields_no_topic(self) -> None:
        self.assertIsNone(pulse_html.agenda_topic(None, None))
        self.assertIsNone(pulse_html.agenda_topic("", "   "))

    def test_the_gesetzentwurf_rule_restores_the_nominative(self) -> None:
        cases = {
            "Erste Beratung des von der Bundesregierung eingebrachten Entwurfs eines "
            "Infrastruktur-Zukunftsgesetzes": "Infrastruktur-Zukunftsgesetz",
            "14 a) – Zweite und dritte Beratung des von den Fraktionen SPD, "
            "BÜNDNIS 90/DIE GRÜNEN und FDP eingebrachten Entwurfs eines "
            "Steuerentlastungsgesetzes 2022": "Steuerentlastungsgesetz 2022",
            "a) – Zweite und dritte Beratung des von der Bundesregierung eingebrachten "
            "Entwurfs eines Dreizehnten Gesetzes zur Änderung des Zweiten Buches "
            "Sozialgesetzbuch": "Dreizehntes Gesetz zur Änderung des Zweiten Buches Sozialgesetzbuch",
        }
        for heading, expected in cases.items():
            with self.subTest(heading=heading[:40]):
                self.assertEqual(pulse_html.strip_heading_boilerplate(heading), expected)

    def test_committee_and_regierungserklaerung_openers_are_stripped(self) -> None:
        self.assertEqual(
            pulse_html.strip_heading_boilerplate(
                "Beratung der Beschlussempfehlung des Ausschusses für Wahlprüfung, Immunität "
                "und Geschäftsordnung (1. Ausschuss) Antrag auf Genehmigung zur Durchführung "
                "eines Strafverfahrens"
            ),
            "Antrag auf Genehmigung zur Durchführung eines Strafverfahrens",
        )
        self.assertEqual(
            pulse_html.strip_heading_boilerplate(
                "Abgabe einer Regierungserklärung durch den Bundeskanzler: Zur Lage in der Ukraine"
            ),
            "Zur Lage in der Ukraine",
        )

    def test_the_beschlussempfehlung_zu_dem_antrag_opener_is_stripped(self) -> None:
        # Distinct from the "(N. Ausschuss)" variant above: no parenthetical
        # committee marker, the opener instead runs through "... zu dem
        # Antrag der Fraktion X <Thema>".
        self.assertEqual(
            pulse_html.strip_heading_boilerplate(
                "Beratung der Beschlussempfehlung und des Berichts des Haushaltsausschusses "
                "zu dem Antrag der Fraktion der AfD Rente mit 63 sofort abschaffen"
            ),
            "Rente mit 63 sofort abschaffen",
        )

    def test_an_unrecognised_opener_leaves_the_heading_intact(self) -> None:
        heading = "hier: Einzelplan 30 Bundesministerium für Bildung und Forschung"
        self.assertEqual(pulse_html.strip_heading_boilerplate(heading), heading)
        self.assertEqual(pulse_html.strip_heading_boilerplate(""), "")

    def test_a_bundled_heading_keeps_the_first_sub_items_topic(self) -> None:
        # A joint agenda item files an Antrag under a) and a Gesetzentwurf
        # under b). The Gesetzentwurf rule's opener has no fixed starting
        # phrase, so matched against the whole heading it can skip past a)
        # entirely and surface b)'s topic instead, hiding a)'s.
        self.assertEqual(
            pulse_html.strip_heading_boilerplate(
                "a) Beratung des Antrags der Fraktion der AfD Rente mit 63 "
                "sofort abschaffen b) Erste Beratung des von der "
                "Bundesregierung eingebrachten Entwurfs eines Gesetzes zur "
                "Änderung des Rentenrechts"
            ),
            "Rente mit 63 sofort abschaffen",
        )


if __name__ == "__main__":
    unittest.main()
