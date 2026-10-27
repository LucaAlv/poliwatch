from __future__ import annotations

import json
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
import derive  # noqa: E402
import validate_dip_protocol as dip  # noqa: E402
from _votes_fixture import vote_summary  # noqa: E402


class RollCallScrapingTests(unittest.TestCase):
    def test_associated_debate_targets_from_bounded_live_fixtures(self) -> None:
        fixtures = REPO_ROOT / "tests" / "fixtures"
        for vote_id, article_id in (("906", "992936"), ("1005", "1181880"), ("994", None)):
            with self.subTest(vote_id=vote_id):
                page = (fixtures / f"vote_debate_{vote_id}.html").read_text()
                expected = f"https://www.bundestag.de/dokumente/textarchiv/{article_id}" if article_id else None
                self.assertEqual(dip.parse_vote_debate_url(page, dip.roll_call_vote_url(vote_id)), expected)

    def test_debate_association_is_bounded_unique_and_safe(self) -> None:
        page = (REPO_ROOT / "tests/fixtures/vote_debate_1005.html").read_text()
        source = dip.roll_call_vote_url("1005")
        expected = "https://www.bundestag.de/dokumente/textarchiv/1181880"
        unrelated = '<div id="showItContainer_999_7654043"></div><a href="/dokumente/textarchiv/999">Other</a>'
        self.assertEqual(dip.parse_vote_debate_url(unrelated + page + unrelated, source), expected)
        repeated = page.replace('</div>', '<div id="showItContainer_1181880_7654043"></div></div>', 1)
        self.assertEqual(dip.parse_vote_debate_url(repeated, source), expected)
        conflicting = page.replace('</div>', '<div id="showItContainer_999_7654043"></div></div>', 1)
        self.assertIsNone(dip.parse_vote_debate_url(conflicting, source))
        self.assertIsNone(dip.parse_vote_debate_url(page.replace('tab_debatte_7654043', 'tab_debatte_0'), source))
        canonical = "/dokumente/textarchiv/2026/kw24-de-familien-kinder-1181880"
        for href in (canonical, "https://evil.example" + canonical, "http://www.bundestag.de" + canonical,
                     "/dokumente/textarchiv/2026/unrelated-999", "javascript:alert(1)", "https://[broken"):
            with self.subTest(href=href):
                linked = page.replace('</div>', f'<a href="{href}">Bericht</a></div>', 1)
                self.assertEqual(dip.parse_vote_debate_url(linked, source),
                                 "https://www.bundestag.de" + canonical if href == canonical else expected)
        for unsafe in ("https://evil.example/dokumente/textarchiv/1181880", "javascript:alert(1)",
                       expected + "?redirect=evil", expected + "#debatte", "https://[broken", None):
            self.assertIsNone(dip.publication.vote_debate_url(unsafe))

    def test_detail_fetch_sets_nullable_debate_without_changing_the_ballot(self) -> None:
        page = (REPO_ROOT / "tests/fixtures/vote_debate_1005.html").read_text()
        vote = {"id": "1005", "total": {"yes": 442, "no": 141, "abstain": 0}}
        with patch.object(dip, "fetch_html", side_effect=[page, ""]), patch.object(dip, "namenslisten_entries", return_value=[]):
            enriched = dip.fetch_roll_call_vote_detail(vote)
        self.assertEqual(enriched["debate_url"], "https://www.bundestag.de/dokumente/textarchiv/1181880")
        self.assertEqual(enriched["total"], vote["total"])
        with patch.object(dip, "fetch_html", return_value=""), patch.object(dip, "namenslisten_entries", return_value=[]):
            refreshed = dip.fetch_roll_call_vote_detail(enriched)
        self.assertIn("debate_url", refreshed)
        self.assertIsNone(refreshed["debate_url"])

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

    def test_grundgesetz_amendment_with_more_ja_than_nein_is_unknown(self) -> None:
        # Art. 79 Abs. 2 GG: two thirds of the members, not Ja > Nein.
        title = "Gesetz zur Änderung des Grundgesetzes"
        self.assertEqual(dip.vote_result(official=None, yes_count=400, no_count=200, title=title), (None, None))
        self.assertEqual(
            dip.vote_result(official=None, yes_count=200, no_count=400, title=title), (None, None)
        )
        self.assertEqual(
            dip.vote_result(official="accepted", yes_count=400, no_count=200, title=title), ("accepted", "official")
        )

    def test_missing_counts_are_unknown(self) -> None:
        self.assertEqual(dip.vote_result(official=None, yes_count=0, no_count=0), (None, None))


class OfficialVoteResultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = (FIXTURES_DIR / "roll_call_detail_beschluss.html").read_text(encoding="utf-8")

    def test_finds_accepted_result_by_its_own_counts(self) -> None:
        self.assertEqual(dip.official_vote_result(self.html, 434, 128)[0], "accepted")

    def test_finds_rejected_result_for_a_different_vote_in_the_same_text(self) -> None:
        self.assertEqual(dip.official_vote_result(self.html, 127, 418)[0], "rejected")

    def test_no_matching_counts_returns_none(self) -> None:
        self.assertIsNone(dip.official_vote_result(self.html, 1, 2)[0])

    def test_missing_beschluss_section_returns_none(self) -> None:
        self.assertIsNone(dip.official_vote_result("<html><body>no beschluss here</body></html>", 434, 128)[0])

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
        self.assertIsNone(dip.official_vote_result(html, 300, 200)[0])

    def test_negated_outcome_is_not_read_as_official(self) -> None:
        # "nicht angenommen" (e.g. a qualified majority missed) must never be
        # stamped official "accepted"; the caller derives instead.
        html = """
        <h2 class="bt-artikel__aside-section-title">Beschluss</h2>
        <p>Gesamt: 500 Ja:300 Nein:200 Der Gesetzentwurf ist nicht angenommen.</p>
        </div>
        <div class="bt-artikel__aside-section">
        """
        self.assertIsNone(dip.official_vote_result(html, 300, 200)[0])

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
                self.assertIsNone(dip.official_vote_result(self._section(body), 100, 400)[0])

    def test_outcome_in_a_later_paragraph_is_not_this_votes(self) -> None:
        body = "<p>Gesamt:500 Ja:100 Nein:400 Enthaltungen --</p><p>Ein weiterer Antrag wurde angenommen.</p>"
        self.assertIsNone(dip.official_vote_result(self._section(body), 100, 400)[0])

    def test_outcome_on_the_line_after_the_tally_is_read(self) -> None:
        body = "<p>Gesamt: 500 Ja: 100 Nein: 400 Enthaltungen --<br/>Antrag abgelehnt</p>"
        self.assertEqual(dip.official_vote_result(self._section(body), 100, 400)[0], "rejected")

    def test_next_votes_tally_on_the_following_line_is_a_boundary(self) -> None:
        for body in (
            "<p>Gesamt:500 Ja:300 Nein:200<br/>Gesamt:400 Ja:100 Nein:300 Antrag abgelehnt</p>",
            "<p>Gesamt:500 Ja:300 Nein:200 Gesamt:400 Ja:100 Nein:300<br/>Antrag abgelehnt</p>",
        ):
            with self.subTest(body=body):
                self.assertIsNone(dip.official_vote_result(self._section(body), 300, 200)[0])

    def test_outcome_behind_a_blank_line_belongs_to_the_next_decision(self) -> None:
        # A show-of-hands decision after this vote's tally has no tally of its
        # own and, here, no document number; the blank line ("<br/><br/>")
        # that separates decision blocks on live pages keeps its outcome out.
        body = "<p>Gesamt:500 Ja:100 Nein:400 Enthaltungen --<br/><br/>Antrag einstimmig angenommen</p>"
        self.assertIsNone(dip.official_vote_result(self._section(body), 100, 400)[0])

    def test_negation_split_across_the_line_break_is_refused(self) -> None:
        body = "<p>Gesamt: 500 Ja:300 Nein:200 Enthaltungen -- Der Gesetzentwurf ist nicht<br/>angenommen.</p>"
        self.assertIsNone(dip.official_vote_result(self._section(body), 300, 200)[0])

    def test_list_items_are_lines_as_on_live_pages(self) -> None:
        # bundestag.de vote 949 (live, 2026-09-27): one <li> per line.
        body = (
            "<ul><li>endgültiges Ergebnis</li><li>Gesamt: 716 Ja: 87 Nein: 626 Enthaltungen: 3</li>"
            "<li>Gesetzentwurf 20/15099 abgelehnt</li></ul>"
        )
        self.assertEqual(dip.official_vote_result(self._section(body), 87, 626)[0], "rejected")
        # ...and the next vote's tally item is still a boundary.
        body = "<ul><li>Gesamt:500 Ja:300 Nein:200</li><li>Gesamt:400 Ja:100 Nein:300 Antrag abgelehnt</li></ul>"
        self.assertIsNone(dip.official_vote_result(self._section(body), 300, 200)[0])

    def test_nbsp_inside_the_tally_itself_still_matches(self) -> None:
        # Live pages can render the tally's own spacing as &nbsp; too, not
        # only the "nicht angenommen" phrase; strip_tags decodes it to a
        # literal NBSP character, which \s still has to match.
        body = "<p>Gesamt: 500 Ja: 300 Nein: 200 Enthaltungen --<br/>Gesetzentwurf angenommen</p>"
        self.assertEqual(dip.official_vote_result(self._section(body), 300, 200)[0], "accepted")

    def test_both_outcome_words_for_one_tally_are_refused(self) -> None:
        body = "<p>Gesamt: 500 Ja:300 Nein:200 angenommen aber abgelehnt</p>"
        self.assertIsNone(dip.official_vote_result(self._section(body), 300, 200)[0])

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
        self.assertIsNone(dip.official_vote_result(html, 300, 200)[0])

    def test_duplicate_tallies_in_one_section_are_not_attributed(self) -> None:
        # A Gesetzentwurf and its Entschließungsantrag voted along the same lines
        # can share Ja/Nein counts; the first match is not confidently this vote.
        html = """
        <h2 class="bt-artikel__aside-section-title">Beschluss</h2>
        <p>Gesamt: 500 Ja:300 Nein:200 angenommen. Gesamt: 500 Ja:300 Nein:200 abgelehnt.</p>
        </div>
        <div class="bt-artikel__aside-section">
        """
        self.assertIsNone(dip.official_vote_result(html, 300, 200)[0])

    def test_a_tally_less_neighbor_decision_is_rejected_when_it_names_another_document(self) -> None:
        # A unanimous/show-of-hands decision has no "Gesamt"/"Ja: N" of its own,
        # so it is not a boundary _NEXT_TALLY_RE recognizes; sitting right after
        # a real tally with no outcome sentence of its own, on the very next
        # line of the SAME paragraph, its "angenommen" would otherwise get
        # attributed to that unrelated tally (found by Codex's adversarial
        # review, 2026-09-27). document_numbers is this vote's own Drucksache
        # numbers; the neighbor names a specific, different one.
        body = "<p>Gesamt:500 Ja:100 Nein:400<br/>Entschließungsantrag 21/999 einstimmig angenommen</p>"
        self.assertIsNone(
            dip.official_vote_result(self._section(body), 100, 400, document_numbers=["21/123"])[0]
        )

    def test_document_numbers_still_confirm_a_genuine_match(self) -> None:
        body = "<p>Gesamt: 500 Ja: 100 Nein: 400 Enthaltungen --<br/>Antrag 21/123 abgelehnt</p>"
        self.assertEqual(
            dip.official_vote_result(self._section(body), 100, 400, document_numbers=["21/123"])[0],
            "rejected",
        )

    def test_document_numbers_never_refuse_an_outcome_sentence_that_names_no_number(self) -> None:
        # Regression pin (found via the roll_call_detail_beschluss fixture,
        # maintainability review 2026-09-27): a genuine outcome sentence often
        # repeats no Drucksache number at all ("Gesetzentwurf angenommen"),
        # with the number appearing only earlier, in the vote's own heading
        # line, outside the checked window. Absence of our number must never
        # by itself refuse a match - only a proven, different number does.
        html = (FIXTURES_DIR / "roll_call_detail_beschluss.html").read_text(encoding="utf-8")
        self.assertEqual(dip.official_vote_result(html, 434, 128, document_numbers=["21/6561"])[0], "accepted")
        self.assertEqual(dip.official_vote_result(html, 127, 418, document_numbers=["21/8195"])[0], "rejected")

    def test_document_numbers_defaults_to_the_old_behavior_when_unknown(self) -> None:
        # Without document_numbers (e.g. a candidate the overview list page
        # named no Drucksache for), the cross-check cannot run; the caller
        # still gets the pre-existing one-line-lookahead result.
        body = "<p>Gesamt:500 Ja:100 Nein:400<br/>Entschließungsantrag 21/999 einstimmig angenommen</p>"
        self.assertEqual(dip.official_vote_result(self._section(body), 100, 400)[0], "accepted")


class OfficialVoteBlockTests(unittest.TestCase):
    """The Beschluss text prints the tally read out in the sitting; ours is the final
    one. A block is this vote's by its Drucksachen (docs/plans/fix-vote-interpretation.md)."""

    def _section(self, body: str) -> str:
        return (
            '<h2 class="bt-artikel__aside-section-title">Beschluss</h2>'
            f"{body}</div>\n<div class=\"bt-artikel__aside-section\">"
        )

    def block(self, documents: str, tally: str, outcome: str, heading: str = "namentliche Abstimmung zu") -> str:
        return f"<p>{heading} {documents}<br/>Gesamt: {tally}<br/>{outcome}</p>"

    def test_a_block_naming_this_votes_document_survives_a_one_vote_discrepancy(self) -> None:
        # Vote 996 (21/67), retrieved 2026-10-23: the page reads Ja 438, the final tally is 439/135.
        html = (FIXTURES_DIR / "roll_call_detail_996.html").read_text(encoding="utf-8")
        self.assertEqual(dip.official_vote_result(html, 439, 135, ["21/4466", "21/4792"]), ("rejected", "application"))
        # Without a document match only the exact tally counts; the page's own 438 is exact.
        self.assertEqual(dip.official_vote_result(html, 439, 135), (None, "proposition"))
        self.assertEqual(dip.official_vote_result(html, 438, 135), ("rejected", "application"))

    def test_a_three_vote_discrepancy_from_the_measured_corpus_is_still_this_votes_block(self) -> None:
        # Vote 869 (20/122), retrieved 2026-10-23: printed Ja 635, final 632. The block sits
        # between others of one bundled Beschluss.
        html = (FIXTURES_DIR / "roll_call_detail_869.html").read_text(encoding="utf-8")
        self.assertEqual(dip.official_vote_result(html, 632, 34, ["20/7226", "20/7623"]), ("accepted", "proposition"))
        # Four votes off is no provisional tally any more.
        self.assertEqual(dip.official_vote_result(html, 631, 34, ["20/7226", "20/7623"]), (None, "proposition"))
        self.assertEqual(dip.official_vote_result(html, 632, 34), (None, "proposition"))

    def test_a_nearby_tally_of_an_unrelated_block_is_not_adopted(self) -> None:
        other = self.block("Antrag 21/999", "500 Ja: 438 Nein: 135", "Antrag 21/999 angenommen")
        far = self.block("Antrag 21/4466", "500 Ja: 300 Nein: 250", "Antrag 21/4466 abgelehnt")
        self.assertEqual(
            dip.official_vote_result(self._section(other + far), 439, 135, ["21/4466"]), (None, "proposition")
        )
        near = self.block("Antrag 21/4466", "500 Ja: 437 Nein: 136", "Antrag 21/4466 abgelehnt")
        self.assertEqual(
            dip.official_vote_result(self._section(other + near), 439, 135, ["21/4466"]), ("rejected", "application")
        )

    def test_exact_tally_does_not_override_a_different_current_roll_call(self) -> None:
        # Value: protects=current announced document identity;
        # fails_when=matching counts override another document on the roll-call line;
        # why_new=existing cases checked only outcome-text documents; seam=none;
        # no_claim=synthetic HTML attribution, not live provider availability.
        body = "<p>namentliche Abstimmung zu Antrag 21/999<br/>Gesamt: 500 Ja: 300 Nein: 200<br/>Antrag angenommen</p>"
        self.assertEqual(
            dip.official_vote_result(self._section(body), 300, 200, ["21/123"]), (None, "proposition")
        )

    def test_last_roll_call_identity_ignores_earlier_unrelated_decisions(self) -> None:
        # Value: protects=current roll-call attribution in bundled decisions;
        # fails_when=earlier unrelated decisions contaminate announcement identity;
        # why_new=the new mismatch guard must retain this compatibility; seam=none;
        # no_claim=synthetic HTML attribution, not live provider availability.
        body = (
            "<p>Überweisung 20/9100 beschlossen<br/>Antrag 20/10057 angenommen<br/>"
            "namentliche Abstimmung zu Antrag 20/10050<br/>Gesamt: 500 Ja: 188 Nein: 420<br/>"
            "Antrag 20/10050 abgelehnt</p>"
        )
        self.assertEqual(
            dip.official_vote_result(self._section(body), 188, 420, ["20/10050"]), ("rejected", "application")
        )

    def test_a_block_naming_a_document_besides_this_votes_is_not_identified(self) -> None:
        mixed = self.block("Antrag 21/4466 und Antrag 21/5000", "500 Ja: 438 Nein: 135", "Antrag 21/4466 abgelehnt")
        self.assertEqual(dip.official_vote_result(self._section(mixed), 439, 135, ["21/4466"]), (None, "proposition"))
        self.assertEqual(dip.official_vote_result(self._section(mixed), 438, 135, ["21/4466"]), ("rejected", "application"))

    def test_two_blocks_sharing_the_documents_fall_back_to_the_exact_tally(self) -> None:
        # Parts of one recommendation name the same Drucksachen: neither is picked by them.
        parts = (
            self.block("Beschlussempfehlung 21/5546 Buchstabe c (Antrag 21/2363 ablehnen)", "585 Ja: 449 Nein: 136", "Beschlussempfehlung angenommen")
            + self.block("Beschlussempfehlung 21/5546 Buchstabe c (Antrag 21/2363 ablehnen)", "590 Ja: 454 Nein: 136", "Beschlussempfehlung abgelehnt")
        )
        numbers = ["21/2363", "21/5546"]
        self.assertEqual(dip.official_vote_result(self._section(parts), 447, 136, numbers), (None, "proposition"))
        self.assertEqual(dip.official_vote_result(self._section(parts), 449, 136, numbers), ("accepted", "proposition"))
        self.assertEqual(dip.official_vote_result(self._section(parts), 454, 136, numbers), ("rejected", "proposition"))

    def test_without_documents_a_provisional_tally_is_not_matched(self) -> None:
        body = "<p>Gesamt: 573 Ja: 438 Nein: 135 Enthaltungen 0<br/>Antrag abgelehnt</p>"
        self.assertEqual(dip.official_vote_result(self._section(body), 439, 135), (None, "proposition"))
        self.assertEqual(dip.official_vote_result(self._section(body), 438, 135), ("rejected", "application"))

    def test_the_outcome_and_the_scope_come_from_the_same_block(self) -> None:
        recommendation = self.block("Beschlussempfehlung 21/5 (Antrag 21/4 ablehnen)", "500 Ja: 300 Nein: 200", "Beschlussempfehlung 21/5 angenommen")
        antrag = self.block("Antrag 21/9", "500 Ja: 300 Nein: 200", "Antrag 21/9 abgelehnt")
        # Identical tallies in both blocks: the documents separate them, and the block that
        # answers for the vote answers for its scope too.
        for documents, expected in (
            (["21/4", "21/5"], ("accepted", "proposition")),
            (["21/9"], ("rejected", "application")),
            (None, (None, "proposition")),  # two blocks with this tally: no exact, unique match
        ):
            with self.subTest(documents=documents):
                self.assertEqual(dip.official_vote_result(self._section(recommendation + antrag), 301, 200, documents), expected)
                self.assertEqual(dip.official_vote_result(self._section(recommendation + antrag), 300, 200, documents), expected)

    def test_a_trailing_outcome_paragraph_counts_only_with_a_document_of_the_block(self) -> None:
        tally = "<ul><li>namentliche Abstimmung zu Antrag 21/4466</li><li>Gesamt: 573 Ja: 438 Nein: 135</li></ul>"
        self.assertEqual(
            dip.official_vote_result(self._section(tally + "<p><br/>Antrag 21/4466 abgelehnt</p>"), 438, 135),
            ("rejected", "application"),
        )
        self.assertEqual(
            dip.official_vote_result(self._section(tally + "<p><br/>Antrag 21/9999 abgelehnt</p>"), 438, 135),
            (None, "proposition"),
        )
        self.assertEqual(
            dip.official_vote_result(self._section(tally + "<p><br/>Der Antrag wurde abgelehnt</p>"), 438, 135),
            (None, "proposition"),
        )

    def test_the_detail_fetch_of_vote_996_keeps_the_final_tally_and_reads_the_antrag_outcome(self) -> None:
        page = (FIXTURES_DIR / "roll_call_detail_996.html").read_text(encoding="utf-8")
        listing = json.loads((FIXTURES_DIR / "vote_interpretation_votes.json").read_text(encoding="utf-8"))["996"]
        listing.pop("fractions")
        listing.pop("members")

        def fake_fetch_html(url: str) -> str:
            if "/liste/" in url:
                return ""
            return "" if "namensliste.form" in url else page

        dip._namenslisten_entries = None
        self.addCleanup(setattr, dip, "_namenslisten_entries", None)
        with patch.object(dip, "fetch_html", side_effect=fake_fetch_html), patch("sys.stderr", StringIO()):
            vote = dip.fetch_roll_call_vote_detail(listing)

        self.assertEqual(vote["total"], {"yes": 439, "no": 135, "abstain": 0, "absent": 55})
        self.assertEqual(
            (vote["official_result"], vote["result_raw"], vote["result_source"], vote["result_scope"]),
            ("rejected", "rejected", "official", "application"),
        )
        self.assertTrue(vote["inverted"])
        # The page speaks of the Antrag: rejected once, not inverted a second time.
        self.assertEqual(derive.vote_outcome(vote), "rejected")
        panel = vote_summary({"votes": [vote]})
        self.assertIn("Antrag: Abgelehnt", panel)
        self.assertIn("Ja = Antrag ablehnen · Nein = Antrag annehmen", panel)
        self.assertNotIn("berechnet", panel)


class NamenslistenMatchingTests(unittest.TestCase):
    def setUp(self) -> None:
        html = (FIXTURES_DIR / "namenslisten_list.html").read_text(encoding="utf-8")
        self.entries = dip.parse_namenslisten_page(html)

    def test_parses_every_row(self) -> None:
        self.assertEqual(len(self.entries), 3)
        self.assertEqual(
            {entry["date"] for entry in self.entries}, {"2026-06-12", "2026-06-11"}
        )

    def test_row_missing_the_xlsx_link_is_kept_without_a_url(self) -> None:
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
        self.assertEqual([(e["title"], e["xlsx_url"] is None) for e in entries], [("Ohne XLSX", True), ("Mit XLSX", False)])

    def test_a_fileless_row_sharing_the_key_makes_the_filed_row_ambiguous(self) -> None:
        entries = [
            {"date": "2026-06-11", "title": "Antrag A", "xlsx_url": None},
            {"date": "2026-06-11", "title": "Antrag-A", "xlsx_url": "https://www.bundestag.de/resource/blob/1/x.xlsx"},
        ]
        self.assertEqual(len(dip.roll_call_xlsx_matches("2026-06-11", "Antrag A", entries)), 2)
        self.assertIsNone(dip.find_roll_call_xlsx_url("2026-06-11", "Antrag A", entries))

    def test_row_with_an_off_host_xlsx_link_keeps_no_url(self) -> None:
        html = (
            '<div class="e-linkListItem">'
            '<a href="https://example.com/x.xlsx" class="e-linkListItem__anchor">'
            "<span>11.06.2026: Bundeswehreinsatz in Kosovo (KFOR)</span></a></div>"
        )
        entries = dip.parse_namenslisten_page(html)
        self.assertEqual([e["xlsx_url"] for e in entries], [None])

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
        self.assertEqual([(e["title"], e["xlsx_url"] is None) for e in entries], [("Ohne Liste", True), ("Mit Liste", False)])

    def test_row_boundary_survives_attribute_reordering_and_extra_leading_classes(self) -> None:
        # The split only required the literal prefix class="e-linkListItem;
        # a markup change putting id before class, or another class first,
        # would silently merge two rows and let the second row's XLSX get
        # attributed to the first (Codex adversarial review, 2026-09-27).
        page = (
            '<div id="row1" class="e-linkListItem"><a class="e-linkListItem__anchor" href="/a.pdf"><span>'
            "11.06.2026: Ohne Liste</span></a></div>"
            '<div class="wrapper e-linkListItem"><a class="e-linkListItem__anchor" href="/b.pdf"><span>'
            "11.06.2026: Mit Liste</span></a>"
            '<a href="https://www.bundestag.de/resource/blob/2/b_xls.xlsx">XLSX</a></div>'
        )
        entries = dip.parse_namenslisten_page(page)
        self.assertEqual([(e["title"], e["xlsx_url"] is None) for e in entries], [("Ohne Liste", True), ("Mit Liste", False)])

    def test_unparsable_xlsx_href_is_skipped_not_raised(self) -> None:
        page = (
            '<div class="e-linkListItem"><a class="e-linkListItem__anchor" href="/a.pdf"><span>'
            '11.06.2026: Kaputt</span></a><a href="https://[broken/x.xlsx">XLSX</a></div>'
        )
        self.assertEqual([e["xlsx_url"] for e in dip.parse_namenslisten_page(page)], [None])


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
            # A real roll-call candidate always carries this from
            # parse_roll_call_list_page; pin that fetch_roll_call_vote_detail
            # actually threads it into official_vote_result.
            "document_numbers": ["21/6561"],
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
        self.assertEqual(len(entries), dip.NAMENSLISTEN_PAGE_LIMIT)
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
