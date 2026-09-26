from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401
import _daten_fixture
import build_dip_pulse_site as b
import persist_dip_pulse_store as pulse_store
from features import all_selection


READINESS = {"votes": "ready", "aw-profiles": "unavailable", "mp-roster": "ready"}


def build_manifest(tmp: Path) -> tuple[dict, dict]:
    db_path = tmp / "pulse.sqlite"
    ids = _daten_fixture.seed_store(db_path)
    conn = pulse_store.connect(db_path)
    try:
        mps, lookup, canonical_by_mp_id = b.collect_abgeordnete(conn)
    finally:
        conn.close()
    manifest = b.export_distribution_data(
        db_path,
        tmp / "exports",
        canonical_by_mp_id=canonical_by_mp_id,
        mp_lookup=lookup,
        readiness=READINESS,
        catalog_count=2,
        dossier_count=2,
        commit="abc123",
    )
    return manifest, lookup


class DatenPageTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)
        self.addCleanup(self._tmpdir.cleanup)
        self.manifest, self.lookup = build_manifest(self.tmp)
        self.html = b.render_database_page(
            self.manifest,
            data_base_url="data/exports/",
            mp_lookup=self.lookup,
            document_numbers={"20/100", "20/101"},
            bill_slugs={"bill-vg-1"},
            features=all_selection(),
        )

    def test_no_sample_table_or_search_box(self) -> None:
        # The shared dark-theme stylesheet still lists .sample-table in an
        # unrelated selector (harmless, unrelated to this page); this page
        # itself must have no such element or the old filter box.
        self.assertNotIn('class="sample-table"', self.html)
        self.assertNotIn("data-table-search", self.html)

    def test_all_five_recipe_titles_present(self) -> None:
        for recipe in b.RECIPES:
            with self.subTest(recipe=recipe["id"]):
                self.assertIn(recipe["title"], self.html)

    def test_sha256_is_present_full_length(self) -> None:
        self.assertIsNotNone(re.search(r"[0-9a-f]{64}", self.html))

    def test_sizes_come_from_the_manifest(self) -> None:
        expected = b.format_size_de(self.manifest["files"][0]["bytes"])
        self.assertIn(expected, self.html)

    def test_german_number_formatting_never_bare_thousands(self) -> None:
        total = self.manifest["total_rows"]
        self.assertIn(b.pulse_html.format_int(total), self.html)

    def test_null_cell_renders_em_dash_not_none(self) -> None:
        self.assertNotIn(">None<", self.html)

    def test_mp_link_resolves_for_a_canonical_person(self) -> None:
        ada_cid = self.lookup["dip:ada"]
        self.assertIn(f'href="abgeordnete/{ada_cid}.html"', self.html)

    def test_mp_link_is_plain_text_when_the_identity_key_does_not_resolve(self) -> None:
        # Vera Stimme's identity_key is profile:..., never registered in the
        # lookup (she gets no page), so R3 must render her name unlinked.
        self.assertIn("Vera Stimme", self.html)
        cell = re.search(r"<td>[^<]*Vera Stimme[^<]*</td>", self.html)
        self.assertIsNotNone(cell)
        self.assertNotIn("<a ", cell.group(0))

    def test_document_link_resolves_when_document_number_known(self) -> None:
        self.assertIn("protocols/plenarprotokoll-20-100.html", self.html)

    def test_document_link_absent_when_document_number_unknown(self) -> None:
        html = b.render_database_page(
            self.manifest,
            data_base_url="data/exports/",
            mp_lookup=self.lookup,
            document_numbers=set(),
            bill_slugs=set(),
            features=all_selection(),
        )
        self.assertNotIn("protocols/plenarprotokoll-20-100.html", html)

    def test_proceeding_link_resolves_when_slug_known(self) -> None:
        self.assertIn("bills/bill-vg-1.html", self.html)

    def test_proceeding_link_absent_when_slug_unknown(self) -> None:
        html = b.render_database_page(
            self.manifest,
            data_base_url="data/exports/",
            mp_lookup=self.lookup,
            document_numbers={"20/100", "20/101"},
            bill_slugs=set(),
            features=all_selection(),
        )
        self.assertNotIn("bills/bill-vg-1.html", html)

    def test_no_hex_colours_in_the_page_specific_css(self) -> None:
        css = b._daten_page_styles()
        root_end = css.index("}", css.index(":root")) + 1
        after_root = css[root_end:]
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,6}\b", after_root), [])

    def test_print_media_block_present(self) -> None:
        self.assertIn("@media print", b._daten_page_styles())

    def test_schema_anchor_is_not_inside_a_details_element(self) -> None:
        # id="table-speeches" must sit on a visible element, not inside a
        # collapsed <details>, so #table-speeches resolves even when closed.
        match = re.search(r'<div class="table-row" id="table-speeches">', self.html)
        self.assertIsNotNone(match)
        self.assertEqual(self.html.count('<summary>Spalten'), len(self.manifest["tables"]))

    def test_result_tables_have_caption_and_scoped_headers(self) -> None:
        self.assertIn('<caption class="visually-hidden">', self.html)
        self.assertIn('<th scope="col">', self.html)

    def test_recipe_sql_shown_verbatim(self) -> None:
        for recipe in b.RECIPES:
            with self.subTest(recipe=recipe["id"]):
                self.assertIn(recipe["sql"].split("\n")[0][:20], self.html)

    def test_recipe_copy_button_present_once_per_recipe(self) -> None:
        # Rendered hidden without JS - no dead button when the script did not
        # run - and revealed by recipe_copy_runtime_script().
        button = '<button type="button" class="recipe-copy" aria-live="polite" hidden>Kopieren</button>'
        self.assertEqual(self.html.count(button), len(b.RECIPES))
        recipe_sql = re.search(r'<div class="recipe-sql">(.*?)</div>', self.html, re.S).group(1)
        self.assertLess(recipe_sql.index("</pre>"), recipe_sql.index(button))

    def test_recipe_copy_script_writes_clipboard_with_selection_fallback(self) -> None:
        script = b.recipe_copy_runtime_script()
        self.assertIn('navigator.clipboard.writeText(code.textContent).then(() => flash("Kopiert"), selectFallback);', script)
        self.assertIn("range.selectNodeContents(code);", script)
        self.assertIn('flash("Markiert – mit ⌘C/Strg+C kopieren");', script)
        self.assertNotIn("document.execCommand(", script)
        self.assertIn("button.hidden = false;", script)
        self.assertIn("!!(navigator.clipboard && window.isSecureContext)", script)

    def test_recipe_copy_script_is_emitted_once_after_page_scripts(self) -> None:
        self.assertEqual(self.html.count('document.querySelectorAll(".recipe-copy")'), 1)
        self.assertLess(self.html.index("bundestag-pulse-ai-summaries-v1"), self.html.rindex("recipe-copy"))
        self.assertNotIn("file://", self.html)

    def test_recipe_copy_button_follows_pre_in_every_recipe_block(self) -> None:
        # The single-recipe check above only proves the first block; every
        # recipe's button must sit after its own </pre>, not just the first.
        button = '<button type="button" class="recipe-copy" aria-live="polite" hidden>Kopieren</button>'
        for block in re.findall(r'<div class="recipe-sql">(.*?)</div>', self.html, re.S):
            with self.subTest(block=block[:40]):
                self.assertLess(block.index("</pre>"), block.index(button))

    def test_recipe_copy_button_hidden_without_js_by_author_css(self) -> None:
        # [hidden] alone is not display:none once any author rule sets
        # display on the element (.recipe-copy sets display:inline-flex);
        # this rule is what actually keeps the button invisible until the
        # runtime script clears the attribute.
        self.assertIn(".recipe-copy[hidden] { display:none; }", b._daten_page_styles())

    def test_recipe_copy_hidden_in_print_alongside_site_chrome(self) -> None:
        css = b._daten_page_styles()
        print_block_start = css.index("@media print")
        print_block = css[print_block_start:css.index("}", print_block_start) + 1]
        self.assertIn(".recipe-copy", print_block)

    def test_recipe_copy_script_guards_before_reading_clipboard_state(self) -> None:
        script = b.recipe_copy_runtime_script()
        guard = "if (!buttons.length) return;"
        self.assertIn(guard, script)
        self.assertLess(script.index(guard), script.index("clipboardAvailable"))

    def test_recipe_copy_per_button_guard_precedes_wiring_and_reveal(self) -> None:
        # A recipe row with no <code> block (markup drifted) must skip that
        # button rather than wire a handler onto a null reference, and the
        # click handler must be attached before the button is ever revealed.
        script = b.recipe_copy_runtime_script()
        code_guard = script.index("if (!code) return;")
        wire = script.index('button.addEventListener("click", () => {')
        reveal = script.index("button.hidden = false;")
        self.assertLess(code_guard, wire)
        self.assertLess(wire, reveal)

    def test_recipe_copy_click_falls_back_before_touching_the_clipboard(self) -> None:
        # Without a secure context, selectFallback runs directly and returns
        # -- writeText is never reached from that branch.
        script = b.recipe_copy_runtime_script()
        branch = script.index("if (!clipboardAvailable) {")
        direct_call = script.index("selectFallback();")
        write = script.index("navigator.clipboard.writeText(")
        self.assertLess(branch, direct_call)
        self.assertLess(direct_call, write)
        self.assertIn("if (selection) {", script)

    def test_recipe_copy_flash_clears_pending_timer_before_rescheduling(self) -> None:
        # Covers the rapid-double-click case: a second click while the first
        # "Kopiert" flash is still showing must cancel the first timer, not
        # stack a second one that later stomps the label back too early.
        script = b.recipe_copy_runtime_script()
        clear = script.index("if (resetTimer) window.clearTimeout(resetTimer);")
        schedule = script.index("window.setTimeout(() => {")
        self.assertLess(clear, schedule)
        self.assertIn("button.textContent = defaultLabel;", script)

    def test_footer_issues_link_only_for_allowed_schemes(self) -> None:
        for url, expected in (
            ("https://example.org/issues", True),
            ("mailto:daten@example.org", True),
            ("javascript:alert(1)", False),
            ("", False),
        ):
            with self.subTest(url=url):
                manifest = dict(self.manifest, issues_url=url)
                html = b.render_database_page(manifest, mp_lookup=self.lookup, features=all_selection())
                self.assertEqual("Fragen und Fehler" in html, expected)
                self.assertNotIn("javascript:", html)

    def test_local_build_state_line(self) -> None:
        self.assertIn("Rohdaten &middot; lokaler Build", self.html)

    def test_remote_manifest_state_line_is_escaped_exactly_once(self) -> None:
        manifest = dict(self.manifest, tag="release & <preview>")
        html = b.render_daten_downloads(manifest, data_base_url="https://example.org/d/", is_remote=True)
        self.assertIn("Rohdaten &middot; Release release &amp; &lt;preview&gt;", html)
        self.assertNotIn("&amp;amp;", html)


class DatenUnavailablePageTests(unittest.TestCase):
    def test_no_persist_fallback_mentions_the_flag(self) -> None:
        html = b.render_database_unavailable_page(all_selection())
        self.assertIn("--no-persist", html)

    def test_sqlite_too_old_reason_is_shown_instead_of_the_default(self) -> None:
        html = b.render_database_unavailable_page(all_selection(), reason="data export needs SQLite 3.35+ (found 3.30.0)")
        self.assertIn("SQLite 3.35", html)
        self.assertNotIn("--no-persist</code> gerendert", html)


class RenderSiteDatenWiringTests(unittest.TestCase):
    def test_render_site_writes_daten_page_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            output_dir = tmp_path / "site"
            output_dir.mkdir()
            (output_dir / "data").mkdir()
            manifest, lookup = build_manifest(tmp_path)
            database_path = tmp_path / "pulse.sqlite"
            b.render_site(
                output_dir=output_dir,
                database_path=database_path,
                no_persist=False,
                protocols=[],
                entries=[],
                abg_mps=[],
                mp_lookup=lookup,
                manifest=manifest,
                data_base_url="data/exports/",
            )
            content = (output_dir / "database.html").read_text(encoding="utf-8")
            self.assertIn(manifest["files"][0]["sha256"], content)
            index_content = (output_dir / "index.html").read_text(encoding="utf-8")
            self.assertIn(">Daten<", index_content)
            self.assertNotIn("Datenbank erkunden", index_content)


if __name__ == "__main__":
    unittest.main()
