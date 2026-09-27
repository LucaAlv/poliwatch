from __future__ import annotations

import unittest

import _support  # noqa: F401
from features.votes import (
    document_source_links,
    render_document_links,
    render_vote_summary,
    result_badge_label,
)


def _vote(**overrides: object) -> dict[str, object]:
    vote = {
        "id": "1",
        "title": "Testabstimmung",
        "detail_url": "https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id=1",
        "document_numbers": ["21/6561"],
        "total": {"yes": 10, "no": 5, "abstain": 2, "absent": 1},
        "fractions": [],
        "members": [],
    }
    vote.update(overrides)
    return vote


class ResultBadgeLabelTests(unittest.TestCase):
    def test_known_results_map_to_fixed_german_copy(self) -> None:
        self.assertEqual(result_badge_label("accepted"), "Angenommen")
        self.assertEqual(result_badge_label("rejected"), "Abgelehnt")

    def test_unknown_or_missing_result_has_no_label(self) -> None:
        self.assertIsNone(result_badge_label(None))
        self.assertIsNone(result_badge_label("something-else"))


class DocumentSourceLinksTests(unittest.TestCase):
    def test_xml_drucksache_wins_over_a_dip_link_for_the_same_number(self) -> None:
        item = {
            "xml_drucksachen": [{"dokumentnummer": "21/6561", "url": "https://dserver.bundestag.de/btd/21/065/2106561.pdf"}],
            "api": {"linked_drucksachen": [{"dokumentnummer": "21/6561", "url": "https://dip.bundestag.de/other"}]},
        }
        links = document_source_links(item)
        self.assertEqual(links["21/6561"], ("https://dserver.bundestag.de/btd/21/065/2106561.pdf", "bundestag-xml"))

    def test_dip_link_used_when_xml_has_none_for_that_number(self) -> None:
        item = {"api": {"linked_drucksachen": [{"dokumentnummer": "21/8157", "url": "https://dip.bundestag.de/x"}]}}
        links = document_source_links(item)
        self.assertEqual(links["21/8157"], ("https://dip.bundestag.de/x", "bundestag-dip"))

    def test_a_number_with_no_url_anywhere_is_absent_from_the_map(self) -> None:
        self.assertEqual(document_source_links({}), {})


class RenderDocumentLinksTests(unittest.TestCase):
    def test_linked_number_becomes_an_anchor(self) -> None:
        links = {"21/6561": ("https://dserver.bundestag.de/btd/21/065/2106561.pdf", "bundestag-xml")}
        html = render_document_links(["21/6561"], links)
        self.assertIn("<a class=\"doc-link\"", html)
        self.assertIn('href="https://dserver.bundestag.de/btd/21/065/2106561.pdf"', html)
        self.assertIn("21/6561", html)

    def test_dip_sourced_link_also_passes_the_publication_allowlist(self) -> None:
        # document_source_links can hand back a "bundestag-dip" tuple (DIP API's
        # own pdf_url) rather than "bundestag-xml"; only the xml source was
        # exercised through render_document_links's html.source_url() call
        # elsewhere, so this pins the other allowed source too.
        links = {"21/8157": ("https://dip.bundestag.de/x", "bundestag-dip")}
        html = render_document_links(["21/8157"], links)
        self.assertIn('href="https://dip.bundestag.de/x"', html)
        self.assertIn("21/8157", html)

    def test_off_allowlist_drucksache_url_renders_unlinked_instead_of_failing(self) -> None:
        html = render_document_links(["21/1"], {"21/1": ("https://evil.example/x.pdf", "bundestag-dip")})
        self.assertNotIn("<a ", html)
        self.assertIn('<span class="doc-link muted">21/1</span>', html)

    def test_several_drucksachen_render_as_one_pill_list_without_commas(self) -> None:
        html = render_document_links(["21/1", "21/2"], {})
        self.assertTrue(html.startswith('<span class="doc-link-list">'))
        self.assertNotIn(", ", html)
        self.assertEqual(render_document_links([], {}), "")

    def test_unlinked_number_never_guesses_a_url(self) -> None:
        html = render_document_links(["21/9999"], {})
        self.assertNotIn("<a ", html)
        self.assertIn("muted", html)
        self.assertIn("21/9999", html)


class RenderVoteSummaryBadgeTests(unittest.TestCase):
    def test_accepted_vote_shows_angenommen_badge(self) -> None:
        item = {"votes": [_vote(result_raw="accepted")]}
        markup = render_vote_summary(item)
        self.assertIn('vote-result-accepted vote-result-derived"', markup)
        self.assertIn('>Angenommen <span class="vote-result-note">(berechnet)</span></span>', markup)

    def test_tied_vote_is_rejected_not_a_guess(self) -> None:
        # GOBT Section 48 Abs. 2: a tie is answered no.
        vote = _vote(result_raw="rejected", total={"yes": 100, "no": 100, "abstain": 0, "absent": 0})
        markup = render_vote_summary({"votes": [vote]})
        self.assertIn('vote-result-rejected vote-result-derived"', markup)
        self.assertIn('>Abgelehnt <span class="vote-result-note">(berechnet)</span></span>', markup)

    def test_abstention_heavy_vote_still_reads_off_yes_no_only(self) -> None:
        # abstain (200) outnumbers both yes (60) and no (40); the outcome still
        # follows yes>no, never the largest bucket.
        vote = _vote(result_raw="accepted", total={"yes": 60, "no": 40, "abstain": 200, "absent": 0})
        markup = render_vote_summary({"votes": [vote]})
        self.assertIn('vote-result-accepted vote-result-derived"', markup)
        self.assertIn('>Angenommen <span class="vote-result-note">(berechnet)</span></span>', markup)

    def test_official_result_is_solid_and_derived_one_says_berechnet(self) -> None:
        official = render_vote_summary({"votes": [_vote(result_raw="accepted", result_source="official")]})
        self.assertIn('class="vote-result vote-result-accepted" title="Laut Beschluss auf bundestag.de">Angenommen</span>', official)
        self.assertNotIn("berechnet", official)
        derived = render_vote_summary({"votes": [_vote(result_raw="accepted", result_source="derived")]})
        self.assertIn("vote-result-derived", derived)
        self.assertIn('title="Aus den Stimmenzahlen berechnet', derived)
        self.assertIn("(berechnet)", derived)

    def test_unknown_result_renders_no_badge(self) -> None:
        vote = _vote(result_raw=None, total={"yes": 0, "no": 0, "abstain": 0, "absent": 0})
        markup = render_vote_summary({"votes": [vote]})
        self.assertNotIn("vote-result", markup)

    def test_pre_badge_vote_derives_its_badge_from_the_counts(self) -> None:
        # Cached dossier JSON from before the badge: no result keys at all. The
        # tie must come out rejected through vote_result, not a preset value.
        vote = _vote(total={"yes": 100, "no": 100, "abstain": 5, "absent": 0})
        markup = render_vote_summary({"votes": [vote]})
        self.assertIn('vote-result-rejected vote-result-derived"', markup)
        self.assertIn('>Abgelehnt <span class="vote-result-note">(berechnet)</span></span>', markup)

    def test_drucksache_renders_as_a_link_when_a_source_url_is_known(self) -> None:
        item = {
            "votes": [_vote(document_numbers=["21/6561"])],
            "xml_drucksachen": [{"dokumentnummer": "21/6561", "url": "https://dserver.bundestag.de/btd/21/065/2106561.pdf"}],
        }
        markup = render_vote_summary(item)
        self.assertIn('<a class="doc-link"', markup)
        self.assertIn('href="https://dserver.bundestag.de/btd/21/065/2106561.pdf"', markup)
        self.assertIn("21/6561", markup)

    def test_drucksache_without_a_known_url_renders_unlinked(self) -> None:
        item = {"votes": [_vote(document_numbers=["21/9999"])]}
        markup = render_vote_summary(item)
        self.assertIn('<span class="doc-link muted">21/9999</span>', markup)

    def test_xlsx_link_present_when_url_is_known(self) -> None:
        item = {"votes": [_vote(xlsx_url="https://www.bundestag.de/resource/blob/1/x.xlsx")]}
        markup = render_vote_summary(item)
        self.assertIn("Abstimmungsliste (XLSX)", markup)
        self.assertIn("resource/blob/1/x.xlsx", markup)

    def test_xlsx_link_absent_when_url_is_missing(self) -> None:
        item = {"votes": [_vote(xlsx_url=None)]}
        markup = render_vote_summary(item)
        self.assertNotIn("XLSX", markup)


if __name__ == "__main__":
    unittest.main()
