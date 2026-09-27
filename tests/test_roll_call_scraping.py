from __future__ import annotations

import os
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import build_dip_pulse_site as build_site  # noqa: E402
import validate_dip_protocol as dip  # noqa: E402


class RollCallScrapingTests(unittest.TestCase):
    def test_default_roll_call_list_url_matches_previous_path(self) -> None:
        self.assertEqual(
            dip.roll_call_list_url(None, 0, 10),
            "https://www.bundestag.de/ajax/filterlist/de/parlament/plenum/abstimmung/484422-484422?offset=0&limit=10",
        )

    def test_layout_change_html_parses_empty_and_sets_selector_warning(self) -> None:
        changed_html = """
        <html>
          <body>
            <article class="vote-card">
              <time>01.07.2026</time>
              <h2>Namentliche Abstimmung</h2>
            </article>
          </body>
        </html>
        """

        self.assertEqual(dip.parse_roll_call_list_page(changed_html), [])

        with patch.object(dip, "fetch_html", return_value=changed_html):
            result = dip.fetch_roll_call_vote_candidates(
                "2026-07-01",
                1,
                include_diagnostics=True,
            )

        self.assertIsInstance(result, dip.RollCallCandidateFetch)
        assert isinstance(result, dip.RollCallCandidateFetch)
        self.assertEqual(result.candidates, [])
        self.assertTrue(result.list_html_seen)
        self.assertEqual(result.parsed_entry_count, 0)
        self.assertTrue(result.selector_warning)

    def test_valid_list_without_same_day_votes_does_not_set_selector_warning(self) -> None:
        valid_other_day_html = """
        <div class="col-xs-12 bt-slide">
          <canvas id="canvas-na-123456"></canvas>
          <span class="bt-date">01.07.2026</span>
          <span class="bt-dachzeile">TOP</span>
          <h3>TOP Abstimmung</h3>
          <div class="bt-teaser-haupttext"><p>Drucksache 21/123</p></div>
          <div data-chart-values="1,2,3,4"></div>
        </div>
        """

        with patch.object(dip, "fetch_html", return_value=valid_other_day_html):
            result = dip.fetch_roll_call_vote_candidates(
                "2026-07-02",
                1,
                include_diagnostics=True,
            )

        self.assertIsInstance(result, dip.RollCallCandidateFetch)
        assert isinstance(result, dip.RollCallCandidateFetch)
        self.assertEqual(result.candidates, [])
        self.assertEqual(result.parsed_entry_count, 1)
        self.assertFalse(result.selector_warning)

    def test_broken_selector_warning_reaches_report_and_stderr(self) -> None:
        class FakeClient:
            def list_all(self, path: str, params: dict[str, str]) -> list[dict[str, str]]:
                return []

        stderr = StringIO()
        with patch.object(dip, "fetch_html", return_value="<html><main>changed</main></html>"):
            with patch("sys.stderr", stderr):
                enrichment = dip.enrich_with_api(
                    FakeClient(),  # type: ignore[arg-type]
                    {"id": "protocol-1", "datum": "2026-07-01"},
                    {"agenda_items": []},
                    person_limit=0,
                    vote_scan_pages=1,
                )

        self.assertIn(dip.ROLL_CALL_LIST_PARSE_WARNING, enrichment["warnings"])
        self.assertIn(f"warning: {dip.ROLL_CALL_LIST_PARSE_WARNING}", stderr.getvalue())

    def test_roll_call_list_id_env_override_changes_requested_url(self) -> None:
        requested_urls: list[str] = []

        def fake_fetch_html(url: str) -> str:
            requested_urls.append(url)
            return ""

        with patch.dict(os.environ, {"BT_ROLL_CALL_LIST_ID": "999999-999999"}):
            with patch.object(dip, "fetch_html", side_effect=fake_fetch_html):
                dip.fetch_roll_call_vote_candidates("2026-07-01", 1)

        self.assertEqual(len(requested_urls), 1)
        self.assertIn("/abstimmung/999999-999999?", requested_urls[0])

    def test_roll_call_list_id_argument_overrides_env_url(self) -> None:
        requested_urls: list[str] = []

        def fake_fetch_html(url: str) -> str:
            requested_urls.append(url)
            return ""

        with patch.dict(os.environ, {"BT_ROLL_CALL_LIST_ID": "999999-999999"}):
            with patch.object(dip, "fetch_html", side_effect=fake_fetch_html):
                dip.fetch_roll_call_vote_candidates("2026-07-01", 1, "111111-111111")

        self.assertEqual(len(requested_urls), 1)
        self.assertIn("/abstimmung/111111-111111?", requested_urls[0])
        self.assertNotIn("999999-999999", requested_urls[0])

    def test_roll_call_list_id_flag_is_available_on_both_entry_points(self) -> None:
        with patch.object(sys, "argv", ["validate_dip_protocol.py", "--roll-call-list-id", "111111-111111"]):
            self.assertEqual(dip.parse_args().roll_call_list_id, "111111-111111")

        with patch.object(sys, "argv", ["build_dip_pulse_site.py", "--roll-call-list-id", "222222-222222"]):
            self.assertEqual(build_site.parse_args().roll_call_list_id, "222222-222222")


FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"


class VoteResultTests(unittest.TestCase):
    def test_official_result_wins_over_counts(self) -> None:
        self.assertEqual(
            dip.vote_result(official="accepted", yes_count=1, no_count=99), ("accepted", "official")
        )
        self.assertEqual(
            dip.vote_result(official="rejected", yes_count=99, no_count=1), ("rejected", "official")
        )

    def test_derived_yes_greater_than_no_is_accepted(self) -> None:
        self.assertEqual(dip.vote_result(official=None, yes_count=300, no_count=200), ("accepted", "derived"))

    def test_derived_tie_is_rejected(self) -> None:
        # GOBT Section 48 Abs. 2: at a tie the question is answered no.
        self.assertEqual(dip.vote_result(official=None, yes_count=200, no_count=200), ("rejected", "derived"))

    def test_derived_no_greater_than_yes_is_rejected(self) -> None:
        self.assertEqual(dip.vote_result(official=None, yes_count=100, no_count=300), ("rejected", "derived"))

    def test_missing_counts_are_unknown(self) -> None:
        self.assertEqual(dip.vote_result(official=None, yes_count=0, no_count=0), (None, None))


class StoredVoteResultTests(unittest.TestCase):
    def test_pre_badge_record_derives_from_the_stored_counts(self) -> None:
        vote = {"total": {"yes": 300, "no": 200}}
        self.assertEqual(dip.stored_vote_result(vote), ("accepted", "derived"))

    def test_already_recorded_result_is_returned_as_is(self) -> None:
        vote = {"result_raw": "rejected", "result_source": "official", "total": {"yes": 999, "no": 0}}
        # The recorded result wins even though the counts would derive
        # differently: persist/render must agree with what was actually stored.
        self.assertEqual(dip.stored_vote_result(vote), ("rejected", "official"))

    def test_result_source_present_without_result_raw_is_returned_verbatim(self) -> None:
        # An inconsistent stored row (result_source set, result_raw missing)
        # still short-circuits on "or" rather than falling through to derive -
        # this pins that behavior rather than a preference either way.
        vote = {"result_source": "official", "total": {"yes": 300, "no": 200}}
        self.assertEqual(dip.stored_vote_result(vote), (None, "official"))


class ScrapeOfficialVoteResultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (FIXTURES_DIR / "roll_call_detail_beschluss.html").read_text(encoding="utf-8")

    def test_finds_accepted_result_by_its_own_counts(self) -> None:
        self.assertEqual(dip.scrape_official_vote_result(self.html, 434, 128), "accepted")

    def test_finds_rejected_result_for_a_different_vote_in_the_same_text(self) -> None:
        self.assertEqual(dip.scrape_official_vote_result(self.html, 127, 418), "rejected")

    def test_no_matching_counts_returns_none(self) -> None:
        self.assertIsNone(dip.scrape_official_vote_result(self.html, 1, 2))

    def test_missing_beschluss_section_returns_none(self) -> None:
        self.assertIsNone(dip.scrape_official_vote_result("<html><body>no beschluss here</body></html>", 434, 128))

    def test_matching_counts_without_an_outcome_word_returns_none(self) -> None:
        # The Beschluss section can narrate a vote's counts without ever using
        # "angenommen"/"abgelehnt" nearby (e.g. it was withdrawn or adjourned
        # right after the tally) - the caller must derive rather than guess.
        html = """
        <h2 class="bt-artikel__aside-section-title">Beschluss</h2>
        <p>Gesamt: 500 Ja:300 Nein:200 Enthaltungen -- Ergebnis wird nachgereicht</p>
        </div>
        <div class="bt-artikel__aside-section">
        """
        self.assertIsNone(dip.scrape_official_vote_result(html, 300, 200))

    def test_negated_outcome_is_not_read_as_official(self) -> None:
        # "nicht angenommen" (e.g. a qualified majority missed) must never be
        # stamped official "accepted"; the caller derives instead.
        html = """
        <h2 class="bt-artikel__aside-section-title">Beschluss</h2>
        <p>Gesamt: 500 Ja:300 Nein:200 Der Gesetzentwurf ist nicht angenommen.</p>
        </div>
        <div class="bt-artikel__aside-section">
        """
        self.assertIsNone(dip.scrape_official_vote_result(html, 300, 200))

    def _section(self, body: str) -> str:
        return (
            '<h2 class="bt-artikel__aside-section-title">Beschluss</h2>'
            f"{body}</div>\n<div class=\"bt-artikel__aside-section\">"
        )

    def test_negation_behind_an_entity_or_markup_is_still_refused(self) -> None:
        for body in (
            "<p>Gesamt:500 Ja:100 Nein:400 Der Antrag ist nicht&nbsp;angenommen.</p>",
            "<p>Gesamt:500 Ja:100 Nein:400 Der Antrag ist <strong>nicht</strong> angenommen.</p>",
        ):
            with self.subTest(body=body):
                self.assertIsNone(dip.scrape_official_vote_result(self._section(body), 100, 400))

    def test_outcome_in_a_later_paragraph_is_not_this_votes(self) -> None:
        body = "<p>Gesamt:500 Ja:100 Nein:400 Enthaltungen --</p><p>Ein weiterer Antrag wurde angenommen.</p>"
        self.assertIsNone(dip.scrape_official_vote_result(self._section(body), 100, 400))

    def test_outcome_on_the_line_after_the_tally_is_read(self) -> None:
        body = "<p>Gesamt: 500 Ja: 100 Nein: 400 Enthaltungen --<br/>Antrag abgelehnt</p>"
        self.assertEqual(dip.scrape_official_vote_result(self._section(body), 100, 400), "rejected")

    def test_next_votes_tally_on_the_following_line_is_a_boundary(self) -> None:
        for body in (
            "<p>Gesamt:500 Ja:300 Nein:200<br/>Gesamt:400 Ja:100 Nein:300 Antrag abgelehnt</p>",
            "<p>Gesamt:500 Ja:300 Nein:200 Gesamt:400 Ja:100 Nein:300<br/>Antrag abgelehnt</p>",
        ):
            with self.subTest(body=body):
                self.assertIsNone(dip.scrape_official_vote_result(self._section(body), 300, 200))

    def test_negation_split_across_the_line_break_is_refused(self) -> None:
        body = "<p>Gesamt: 500 Ja:300 Nein:200 Enthaltungen -- Der Gesetzentwurf ist nicht<br/>angenommen.</p>"
        self.assertIsNone(dip.scrape_official_vote_result(self._section(body), 300, 200))

    def test_list_items_are_lines_as_on_live_pages(self) -> None:
        # bundestag.de vote 949 (live, 2026-09-27): one <li> per line.
        body = (
            "<ul><li>endgültiges Ergebnis</li><li>Gesamt: 716 Ja: 87 Nein: 626 Enthaltungen: 3</li>"
            "<li>Gesetzentwurf 20/15099 abgelehnt</li></ul>"
        )
        self.assertEqual(dip.scrape_official_vote_result(self._section(body), 87, 626), "rejected")
        # ...and the next vote's tally item is still a boundary.
        body = "<ul><li>Gesamt:500 Ja:300 Nein:200</li><li>Gesamt:400 Ja:100 Nein:300 Antrag abgelehnt</li></ul>"
        self.assertIsNone(dip.scrape_official_vote_result(self._section(body), 300, 200))

    def test_both_outcome_words_for_one_tally_are_refused(self) -> None:
        body = "<p>Gesamt: 500 Ja:300 Nein:200 angenommen aber abgelehnt</p>"
        self.assertIsNone(dip.scrape_official_vote_result(self._section(body), 300, 200))

    def test_boundary_stops_before_the_next_votes_outcome_word(self) -> None:
        # This vote's own count match is unique, but its sentence has no outcome
        # word before the next "Gesamt" marker; the next vote's "abgelehnt" must
        # not leak backwards and get attributed to this one.
        html = """
        <h2 class="bt-artikel__aside-section-title">Beschluss</h2>
        <p>Gesamt: 500 Ja:300 Nein:200 vertagt. Gesamt: 400 Ja:100 Nein:300 abgelehnt.</p>
        </div>
        <div class="bt-artikel__aside-section">
        """
        self.assertIsNone(dip.scrape_official_vote_result(html, 300, 200))

    def test_duplicate_tallies_in_one_section_are_not_attributed(self) -> None:
        # A Gesetzentwurf and its Entschließungsantrag voted along the same lines
        # can share Ja/Nein counts; the first match is not confidently this vote.
        html = """
        <h2 class="bt-artikel__aside-section-title">Beschluss</h2>
        <p>Gesamt: 500 Ja:300 Nein:200 angenommen. Gesamt: 500 Ja:300 Nein:200 abgelehnt.</p>
        </div>
        <div class="bt-artikel__aside-section">
        """
        self.assertIsNone(dip.scrape_official_vote_result(html, 300, 200))


class NamenslistenMatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        html = (FIXTURES_DIR / "namenslisten_list.html").read_text(encoding="utf-8")
        self.entries = dip.parse_namenslisten_page(html)

    def test_parses_every_row(self) -> None:
        self.assertEqual(len(self.entries), 3)
        self.assertEqual(
            {entry["date"] for entry in self.entries}, {"2026-06-12", "2026-06-11"}
        )

    def test_row_missing_the_xlsx_link_is_skipped(self) -> None:
        html = """
        <div class="e-linkListItem">
        <a class="e-linkListItem__anchor"><span>10.06.2026: Ohne XLSX </span></a>
        </div>
        <div class="e-linkListItem">
        <a class="e-linkListItem__anchor"><span>11.06.2026: Mit XLSX </span></a>
        <a class="e-linkListItem__anchor" href="https://www.bundestag.de/resource/blob/1/x.xlsx">XLSX</a>
        </div>
        """
        entries = dip.parse_namenslisten_page(html)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["title"], "Mit XLSX")

    def test_row_with_an_off_host_xlsx_link_is_skipped(self) -> None:
        html = (
            '<div class="e-linkListItem">'
            '<a href="https://example.com/x.xlsx" class="e-linkListItem__anchor">'
            "<span>11.06.2026: Bundeswehreinsatz in Kosovo (KFOR)</span></a></div>"
        )
        self.assertEqual(dip.parse_namenslisten_page(html), [])

    def test_relative_xlsx_link_is_made_absolute(self) -> None:
        html = (
            '<div class="e-linkListItem">'
            '<a href="/resource/blob/1/x_xls.xlsx" class="e-linkListItem__anchor">'
            "<span>11.06.2026: Bundeswehreinsatz in Kosovo (KFOR)</span></a></div>"
        )
        entries = dip.parse_namenslisten_page(html)
        self.assertEqual(entries[0]["xlsx_url"], "https://www.bundestag.de/resource/blob/1/x_xls.xlsx")

    def test_row_with_an_unparsable_date_is_skipped(self) -> None:
        html = """
        <div class="e-linkListItem">
        <a class="e-linkListItem__anchor"><span>not-a-date: Kaputt </span></a>
        <a class="e-linkListItem__anchor" href="https://www.bundestag.de/resource/blob/1/x.xlsx">XLSX</a>
        </div>
        """
        # The row regex itself requires DD.MM.YYYY, so a malformed date simply
        # never matches - this documents that the row is dropped, not kept
        # with a bad date.
        self.assertEqual(dip.parse_namenslisten_page(html), [])

    def test_exact_title_matches(self) -> None:
        url = dip.find_roll_call_xlsx_url("2026-06-11", "Bundeswehreinsatz in Kosovo (KFOR)", self.entries)
        self.assertEqual(url, "https://www.bundestag.de/resource/blob/1184016/20260611_3_xls.xlsx")

    def test_hyphenation_difference_still_matches(self) -> None:
        # bundestag.de hyphenates "Jahresemissionsgesamtmengen-Verordnung"
        # differently on this page than on the roll-call candidate list.
        url = dip.find_roll_call_xlsx_url(
            "2026-06-11", "Jahresemissionsgesamtmengen-Verordnung 2031-2040", self.entries
        )
        self.assertEqual(url, "https://www.bundestag.de/resource/blob/1184018/20260611_4_xls.xlsx")

    def test_no_match_returns_none_never_a_guess(self) -> None:
        self.assertIsNone(dip.find_roll_call_xlsx_url("2026-06-11", "Something else entirely", self.entries))
        self.assertIsNone(dip.find_roll_call_xlsx_url("2026-01-01", "Bundeswehreinsatz in Kosovo (KFOR)", self.entries))

    def test_missing_date_or_title_returns_none_before_matching(self) -> None:
        self.assertIsNone(dip.find_roll_call_xlsx_url(None, "Bundeswehreinsatz in Kosovo (KFOR)", self.entries))
        self.assertIsNone(dip.find_roll_call_xlsx_url("2026-06-11", None, self.entries))
        self.assertIsNone(dip.find_roll_call_xlsx_url("2026-06-11", "", self.entries))

    def test_umlaut_title_matches_after_entity_decoding(self) -> None:
        url = dip.find_roll_call_xlsx_url(
            "2026-06-12", "Gesetzentwurf zur Verhinderung missbräuchlicher Anerkennungen der Vaterschaft", self.entries
        )
        self.assertEqual(url, "https://www.bundestag.de/resource/blob/1184528/20260612_1_xls.xlsx")

    def test_ambiguous_match_with_two_distinct_xlsx_urls_returns_none(self) -> None:
        # Same (date, normalized title) key, two different XLSX exports - never
        # guess which one is right.
        entries = self.entries + [{"date": "2026-06-11", "title": "Bundeswehreinsatz in Kosovo (KFOR)", "xlsx_url": "https://www.bundestag.de/resource/blob/9/other.xlsx"}]
        self.assertIsNone(dip.find_roll_call_xlsx_url("2026-06-11", "Bundeswehreinsatz in Kosovo (KFOR)", entries))


class NamenslistenRowBoundaryTests(unittest.TestCase):
    def test_row_with_extra_classes_still_starts_its_own_block(self) -> None:
        page = (
            '<div class="e-linkListItem"><a class="e-linkListItem__anchor" href="/a.pdf"><span>'
            "11.06.2026: Ohne Liste</span></a></div>"
            '<div class="e-linkListItem extra"><a class="e-linkListItem__anchor" href="/b.pdf"><span>'
            "11.06.2026: Mit Liste</span></a>"
            '<a href="https://www.bundestag.de/resource/blob/2/b_xls.xlsx">XLSX</a></div>'
        )
        entries = dip.parse_namenslisten_page(page)
        self.assertEqual([entry["title"] for entry in entries], ["Mit Liste"])

    def test_unparsable_xlsx_href_is_skipped_not_raised(self) -> None:
        page = (
            '<div class="e-linkListItem"><a class="e-linkListItem__anchor" href="/a.pdf"><span>'
            '11.06.2026: Kaputt</span></a><a href="https://[broken/x.xlsx">XLSX</a></div>'
        )
        self.assertEqual(dip.parse_namenslisten_page(page), [])


class FetchRollCallVoteDetailTests(unittest.TestCase):
    def setUp(self) -> None:
        # namenslisten_entries() memoizes per process; each test brings its own page.
        dip._namenslisten_entries = None
        self.addCleanup(setattr, dip, "_namenslisten_entries", None)

    def test_wires_official_result_and_xlsx_url_onto_the_vote(self) -> None:
        beschluss_html = (FIXTURES_DIR / "roll_call_detail_beschluss.html").read_text(encoding="utf-8")
        namenslisten_html = (FIXTURES_DIR / "namenslisten_list.html").read_text(encoding="utf-8")

        def fake_fetch_html(url: str) -> str:
            if "namenslisten" in url or "/liste/" in url:
                return namenslisten_html
            if "namensliste.form" in url:
                return ""
            return beschluss_html

        vote = {
            "id": "1007",
            "date": "2026-06-11",
            "title": "Bundeswehreinsatz in Kosovo (KFOR)",
            "total": {"yes": 434, "no": 128, "abstain": 0, "absent": 68},
        }
        with patch.object(dip, "fetch_html", side_effect=fake_fetch_html):
            enriched = dip.fetch_roll_call_vote_detail(vote)

        self.assertEqual(enriched["result_raw"], "accepted")
        self.assertEqual(enriched["result_source"], "official")
        self.assertEqual(enriched["xlsx_url"], "https://www.bundestag.de/resource/blob/1184016/20260611_3_xls.xlsx")

    def test_falls_back_to_derived_result_and_no_xlsx_when_nothing_matches(self) -> None:
        def fake_fetch_html(url: str) -> str:
            return ""

        vote = {
            "id": "9999",
            "date": "2026-01-01",
            "title": "Unmatched vote",
            "total": {"yes": 100, "no": 300, "abstain": 0, "absent": 0},
        }
        with patch.object(dip, "fetch_html", side_effect=fake_fetch_html):
            enriched = dip.fetch_roll_call_vote_detail(vote)

        self.assertEqual(enriched["result_raw"], "rejected")
        self.assertEqual(enriched["result_source"], "derived")
        self.assertIsNone(enriched["xlsx_url"])

    def test_two_files_for_one_vote_mark_the_match_ambiguous(self) -> None:
        row = (
            '<div class="e-linkListItem"><a class="e-linkListItem__anchor" href="/x.pdf"><span>'
            "11.06.2026: Gleicher Titel</span></a>"
            '<a href="https://www.bundestag.de/resource/blob/{n}/a_xls.xlsx">XLSX</a></div>'
        )
        page = row.format(n=1) + row.format(n=2)
        vote = {"id": "1", "date": "2026-06-11", "title": "Gleicher Titel", "total": {"yes": 2, "no": 1}}
        with patch.object(dip, "fetch_html", side_effect=lambda url: page if "/liste/" in url else ""):
            enriched = dip.fetch_roll_call_vote_detail(vote)
        self.assertIsNone(enriched["xlsx_url"])
        self.assertTrue(enriched["xlsx_ambiguous"])

    def _namenslisten_row(self, index: int, xlsx: bool = True) -> str:
        link = f'<a href="https://www.bundestag.de/resource/blob/{index}/x_xls.xlsx">XLSX</a>' if xlsx else ""
        return (
            '<div class="e-linkListItem">'
            f'<a href="#" class="e-linkListItem__anchor"><span>11.06.2026: Abstimmung {index}</span></a>{link}</div>'
        )

    def test_full_page_warning_counts_raw_rows_not_filtered_entries(self) -> None:
        # 200 rows on the page, one without an XLSX link: still a full page.
        html = "".join(self._namenslisten_row(i, xlsx=i != 0) for i in range(dip.NAMENSLISTEN_PAGE_LIMIT))
        stderr = StringIO()
        with patch.object(dip, "fetch_html", return_value=html), patch("sys.stderr", stderr):
            entries = dip.namenslisten_entries()
        self.assertEqual(len(entries), dip.NAMENSLISTEN_PAGE_LIMIT - 1)
        self.assertIn(f"returned {dip.NAMENSLISTEN_PAGE_LIMIT} rows", stderr.getvalue())

    def test_zero_row_page_warns_and_is_not_cached(self) -> None:
        stderr = StringIO()
        with patch.object(dip, "fetch_html", return_value="<html>maintenance</html>"), patch("sys.stderr", stderr):
            self.assertEqual(dip.namenslisten_entries(), [])
        self.assertIn("parsed to 0 rows", stderr.getvalue())
        with patch.object(dip, "fetch_html", return_value=self._namenslisten_row(1)):
            self.assertEqual(len(dip.namenslisten_entries()), 1)

    def test_namenslisten_list_id_env_override_changes_requested_url(self) -> None:
        with patch.dict(os.environ, {"BT_NAMENSLISTEN_LIST_ID": "999999-999999"}):
            self.assertIn("/liste/999999-999999?", dip.namenslisten_list_url())
        self.assertIn(f"/liste/{dip.DEFAULT_NAMENSLISTEN_LIST_ID}?", dip.namenslisten_list_url())

    def test_namenslisten_timeout_is_a_fetch_failure_not_a_crash(self) -> None:
        def fake_urlopen(*args: object, **kwargs: object) -> object:
            raise TimeoutError("read timed out")

        with patch.object(dip.urllib.request, "urlopen", side_effect=fake_urlopen):
            self.assertEqual(dip.namenslisten_entries(), [])

    def test_namenslisten_fetch_error_is_not_cached_the_next_vote_retries(self) -> None:
        # A failed fetch must not memoize "no entries" for the rest of the
        # build (comment above _namenslisten_entries): the very next call
        # should hit the network again and can succeed.
        with patch.object(dip, "fetch_html", side_effect=dip.DipError("Failed to fetch HTML: timed out")):
            self.assertEqual(dip.namenslisten_entries(), [])
        with patch.object(dip, "fetch_html", return_value=self._namenslisten_row(1)):
            self.assertEqual(len(dip.namenslisten_entries()), 1)

    def test_namenslisten_list_is_fetched_once_for_several_votes(self) -> None:
        namenslisten_html = (FIXTURES_DIR / "namenslisten_list.html").read_text(encoding="utf-8")
        list_fetches = []

        def fake_fetch_html(url: str) -> str:
            if "/liste/" in url:
                list_fetches.append(url)
                return namenslisten_html
            return ""

        votes = [
            {"id": "1007", "date": "2026-06-11", "title": "Bundeswehreinsatz in Kosovo (KFOR)", "total": {}},
            {"id": "1008", "date": "2026-06-11", "title": "Jahresemissionsgesamtmengen-Verordnung 2031-2040", "total": {}},
        ]
        with patch.object(dip, "fetch_html", side_effect=fake_fetch_html):
            enriched = [dip.fetch_roll_call_vote_detail(vote) for vote in votes]

        self.assertEqual(len(list_fetches), 1)
        self.assertTrue(all(vote["xlsx_url"] for vote in enriched))

    def test_namenslisten_fetch_failure_keeps_the_rest_of_the_vote(self) -> None:
        beschluss_html = (FIXTURES_DIR / "roll_call_detail_beschluss.html").read_text(encoding="utf-8")

        def fake_fetch_html(url: str) -> str:
            if "/liste/" in url:
                raise dip.DipError("Failed to fetch HTML: timed out")
            if "namensliste.form" in url:
                return ""
            return beschluss_html

        vote = {
            "id": "1007",
            "date": "2026-06-11",
            "title": "Bundeswehreinsatz in Kosovo (KFOR)",
            "total": {"yes": 434, "no": 128, "abstain": 0, "absent": 68},
        }
        with patch.object(dip, "fetch_html", side_effect=fake_fetch_html):
            enriched = dip.fetch_roll_call_vote_detail(vote)

        self.assertEqual(enriched["result_raw"], "accepted")
        self.assertEqual(enriched["result_source"], "official")
        self.assertIsNone(enriched["xlsx_url"])


if __name__ == "__main__":
    unittest.main()
