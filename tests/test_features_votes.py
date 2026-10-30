from __future__ import annotations

import json
import unittest

import _support  # noqa: F401
import politikfelder
from _support import FIXTURES
from _votes_fixture import fractions_of, vote_summary
from features.votes import (
    CONTEXT_NO_VORGANG,
    CONTEXT_NONE,
    CONTEXT_NOT_FETCHED,
    document_source_links,
    document_source_chambers,
    render_document_links,
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

    def test_an_xml_reference_off_the_xml_host_never_replaces_the_dip_link(self) -> None:
        item = {
            "xml_drucksachen": [{"dokumentnummer": "21/6561", "url": "https://www.example.org/21/6561"}],
            "api": {"linked_drucksachen": [{"dokumentnummer": "21/6561", "url": "https://dip.bundestag.de/x"}]},
        }
        self.assertEqual(document_source_links(item), {"21/6561": ("https://dip.bundestag.de/x", "bundestag-dip")})

    def test_a_number_with_no_url_anywhere_is_absent_from_the_map(self) -> None:
        self.assertEqual(document_source_links({}), {})


class RenderDocumentLinksTests(unittest.TestCase):
    def test_bundesrat_labels_use_metadata_for_the_selected_link(self) -> None:
        item = {"api": {"linked_drucksachen": [
            {"dokumentnummer": "21/1", "herausgeber": "BR", "url": "https://dip.bundestag.de/x"},
        ]}}
        links = document_source_links(item)
        self.assertIn('>BR-Drs. 21/1</a>', render_document_links(["21/1"], links, document_source_chambers(item)))
        # XML selected a different, Bundestag document with the same number.
        item["xml_drucksachen"] = [{"dokumentnummer": "21/1", "url": "https://dserver.bundestag.de/btd/21/001/2100001.pdf"}]
        markup = render_document_links(["21/1"], document_source_links(item), document_source_chambers(item))
        self.assertIn('>21/1</a>', markup)
        self.assertNotIn("BR-Drs.", markup)
        self.assertIn('>BR-Drs. 557/25(B)</span>', render_document_links(["557/25(B)"], {}))
        item["api"]["linked_drucksachen"][0].update(herausgeber="BT", url="https://dserver.bundestag.de/brd/2025/example.pdf")
        item["xml_drucksachen"][0]["url"] = "https://dserver.bundestag.de/brd/2025/example.pdf"
        self.assertEqual(document_source_chambers(item), {"21/1": "BT"})
        item = {"api": {"linked_drucksachen": [{"dokumentnummer": "21/1", "herausgeber": "BR"}]}}
        self.assertEqual(document_source_chambers(item), {"21/1": "BR"})


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
        markup = vote_summary(item)
        self.assertIn('vote-result-accepted vote-result-derived"', markup)
        self.assertIn('>Angenommen <span class="vote-result-note">(berechnet)</span></span>', markup)

    def test_tied_vote_is_rejected_not_a_guess(self) -> None:
        # GOBT Section 48 Abs. 2: a tie is answered no.
        vote = _vote(result_raw="rejected", total={"yes": 100, "no": 100, "abstain": 0, "absent": 0})
        markup = vote_summary({"votes": [vote]})
        self.assertIn('vote-result-rejected vote-result-derived"', markup)
        self.assertIn('>Abgelehnt <span class="vote-result-note">(berechnet)</span></span>', markup)

    def test_abstention_heavy_vote_still_reads_off_yes_no_only(self) -> None:
        # abstain (200) outnumbers both yes (60) and no (40); the outcome still
        # follows yes>no, never the largest bucket.
        vote = _vote(result_raw="accepted", total={"yes": 60, "no": 40, "abstain": 200, "absent": 0})
        markup = vote_summary({"votes": [vote]})
        self.assertIn('vote-result-accepted vote-result-derived"', markup)
        self.assertIn('>Angenommen <span class="vote-result-note">(berechnet)</span></span>', markup)

    def test_official_result_is_solid_and_derived_one_says_berechnet(self) -> None:
        official = vote_summary({"votes": [_vote(result_raw="accepted", result_source="official")]})
        self.assertIn('class="vote-result vote-result-accepted" title="Laut Beschluss auf bundestag.de">Angenommen</span>', official)
        self.assertNotIn("berechnet", official)
        derived = vote_summary({"votes": [_vote(result_raw="accepted", result_source="derived")]})
        self.assertIn("vote-result-derived", derived)
        self.assertIn('title="Aus den Stimmenzahlen berechnet', derived)
        self.assertIn("(berechnet)", derived)

    def test_unknown_result_renders_no_badge(self) -> None:
        vote = _vote(result_raw=None, total={"yes": 0, "no": 0, "abstain": 0, "absent": 0})
        markup = vote_summary({"votes": [vote]})
        self.assertNotIn("vote-result", markup)

    def test_vote_without_a_recorded_result_renders_no_badge(self) -> None:
        vote = _vote(total={"yes": 100, "no": 100, "abstain": 5, "absent": 0})
        vote.pop("result_raw", None)
        vote.pop("result_source", None)
        self.assertNotIn("vote-result", vote_summary({"votes": [vote]}))

    # Value: protects=the no-result note is spaced off the panel title; fails_when=the note loses its styled class; why_new=it ran into the title; seam=none
    def test_no_result_note_carries_its_spacing_class(self) -> None:
        vote = _vote(total={"yes": 100, "no": 100, "abstain": 5, "absent": 0})
        vote.pop("result_raw", None)
        self.assertIn('<span class="vote-no-result">Kein Ergebnis verfügbar</span>', vote_summary({"votes": [vote]}))

    def test_drucksache_renders_as_a_link_when_a_source_url_is_known(self) -> None:
        item = {
            "votes": [_vote(document_numbers=["21/6561"])],
            "xml_drucksachen": [{"dokumentnummer": "21/6561", "url": "https://dserver.bundestag.de/btd/21/065/2106561.pdf"}],
        }
        markup = vote_summary(item)
        self.assertIn('<a class="doc-link"', markup)
        self.assertIn('href="https://dserver.bundestag.de/btd/21/065/2106561.pdf"', markup)
        self.assertIn("21/6561", markup)

    def test_drucksache_without_a_known_url_renders_unlinked(self) -> None:
        item = {"votes": [_vote(document_numbers=["21/9999"])]}
        markup = vote_summary(item)
        self.assertIn('<span class="doc-link muted">21/9999</span>', markup)

    # Value: protects=a vote panel labels a Bundesrat Drucksache "BR-Drs." in its Drucksachen list, for every vote of the item, and leaves a Bundestag one with the same number bare; fails_when=render_vote_summary stops passing document_chambers (or reads them per vote from the wrong item); why_new=only render_document_links was tested directly, not the panel call after the main merge; seam=none; no_claim=the committee line's own citation
    def test_the_vote_panel_labels_a_bundesrat_drucksache_in_each_votes_document_list(self) -> None:
        votes = [_vote(id="1", document_numbers=["21/1"]), _vote(id="2", document_numbers=["21/1", "21/2"])]
        item = {
            "votes": votes,
            "xml_drucksachen": [{"dokumentnummer": "21/2", "url": "https://dserver.bundestag.de/btd/21/000/2100002.pdf"}],
            "api": {"linked_drucksachen": [
                {"dokumentnummer": "21/1", "herausgeber": "BR", "url": "https://dip.bundestag.de/x"},
                {"dokumentnummer": "21/2", "herausgeber": "BR", "url": "https://dip.bundestag.de/y"},
            ]},
        }
        markup = vote_summary(item)
        self.assertEqual(markup.count('href="https://dip.bundestag.de/x">BR-Drs. 21/1</a>'), 2)
        # XML chose a different (Bundestag) document for 21/2; DIP's Bundesrat metadata does not apply to it.
        self.assertIn('href="https://dserver.bundestag.de/btd/21/000/2100002.pdf">21/2</a>', markup)
        self.assertNotIn("BR-Drs. 21/2", markup)

    def test_xlsx_link_present_when_url_is_known(self) -> None:
        item = {"votes": [_vote(xlsx_url="https://www.bundestag.de/resource/blob/1/x.xlsx")]}
        markup = vote_summary(item)
        self.assertIn("Abstimmungsliste (XLSX)", markup)
        self.assertIn("resource/blob/1/x.xlsx", markup)

    def test_xlsx_link_absent_when_url_is_missing(self) -> None:
        item = {"votes": [_vote(xlsx_url=None)]}
        markup = vote_summary(item)
        self.assertNotIn("XLSX", markup)

    def test_off_allowlist_xlsx_url_renders_the_rest_of_the_panel_instead_of_failing(self) -> None:
        # xlsx_url is scraped from a free-form href on a second bundestag.de
        # page, the same class of external data as a Drucksache link (which
        # render_document_links already degrades gracefully for); an
        # off-allowlist value must not take the whole vote panel down.
        item = {"votes": [_vote(xlsx_url="https://evil.example/x.xlsx")]}
        markup = vote_summary(item)
        self.assertNotIn("evil.example", markup)


if __name__ == "__main__":
    unittest.main()


class RenderVoteSummaryFractionTests(unittest.TestCase):
    SPELLINGS = [
        {"name": "Gruppe BSW", "counts": {"yes": 1}, "total": 1},
        {"name": "BSW (Gruppe)", "counts": {"no": 2}, "total": 2},
    ]

    def test_two_spellings_of_one_zusammenschluss_are_one_row_with_one_mehrheitsvotum(self) -> None:
        panel = vote_summary({"votes": [_vote(fractions=self.SPELLINGS)]})
        self.assertEqual(panel.count('class="vote-fraction-row"'), 1)
        self.assertEqual(panel.count("Gruppe BSW"), 1)
        self.assertEqual(panel.count('<em class="vote-pill vote-no">'), 1)
        self.assertNotIn('<em class="vote-pill vote-yes">', panel)


class VoteMemberProfileLinkTests(unittest.TestCase):
    def _item(self, member: dict[str, object], vote_id: str | None = "vote-1") -> dict[str, object]:
        vote = _vote(members=[member])
        if vote_id is None:
            vote.pop("id", None)
        else:
            vote["id"] = vote_id
        return {"votes": [vote]}

    def test_occurrence_key_resolves_to_internal_profile(self) -> None:
        from stable_ids import vote_member_occurrence_id
        key = vote_member_occurrence_id("vote-1", "Ada Beispiel", "SPD")
        markup = vote_summary(self._item({"name": "Ada Beispiel", "faction": "SPD"}), mp_lookup={key: "ada-beispiel"})
        self.assertIn('<a href="../abgeordnete/ada-beispiel.html">Ada Beispiel</a>', markup)

    def test_only_trusted_aw_id_resolves_internally(self) -> None:
        member = {"name": "Ada Beispiel", "faction": "SPD", "abgeordnetenwatch": {"id": 42, "match": "ext_id"}}
        markup = vote_summary(self._item(member), mp_lookup={"aw:42": "ada-beispiel"})
        self.assertIn('<a href="../abgeordnete/ada-beispiel.html">Ada Beispiel</a>', markup)

    def test_unresolved_member_falls_back_to_external_profile(self) -> None:
        member = {"name": "Ada Beispiel", "faction": "SPD", "profile_url": "https://www.bundestag.de/abgeordnete/ada-beispiel"}
        markup = vote_summary(self._item(member), mp_lookup={"other": "other-person"})
        self.assertIn('<a href="https://www.bundestag.de/abgeordnete/ada-beispiel">Ada Beispiel</a>', markup)

    def test_invalid_profile_fallback_keeps_member_and_vote_unlinked(self) -> None:
        for profile_url in ("https://evil.example/profile/ada", "javascript:alert(1)", "https://[invalid"):
            with self.subTest(profile_url=profile_url):
                member = {"name": "Ada Beispiel", "faction": "SPD", "vote": "yes", "profile_url": profile_url}
                markup = vote_summary(self._item(member), mp_lookup={})
                self.assertIn('<li class="member-vote-row"><strong>Ada Beispiel</strong>', markup)
                self.assertIn('<span class="vote-pill vote-yes">ja</span>', markup)
                self.assertNotIn('<strong><a href=', markup)
                self.assertNotIn(profile_url, markup)

    def test_internal_profile_wins_over_invalid_external_url(self) -> None:
        from stable_ids import vote_member_occurrence_id
        key = vote_member_occurrence_id("vote-1", "Ada Beispiel", "SPD")
        member = {"name": "Ada Beispiel", "faction": "SPD", "profile_url": "https://evil.example/profile/ada"}
        markup = vote_summary(self._item(member), mp_lookup={key: "ada-beispiel"})
        self.assertIn('<a href="../abgeordnete/ada-beispiel.html">Ada Beispiel</a>', markup)

    def test_member_without_any_profile_is_plain_text(self) -> None:
        markup = vote_summary(self._item({"name": "Ada Beispiel", "faction": "SPD"}), mp_lookup={})
        self.assertIn("<strong>Ada Beispiel</strong>", markup)
        self.assertNotIn('<strong><a href=', markup)

    def test_missing_lookup_preserves_current_markup(self) -> None:
        markup = vote_summary(self._item({"name": "Ada Beispiel", "faction": "SPD", "profile_url": "https://www.abgeordnetenwatch.de/profile/ada-beispiel"}))
        self.assertIn(
            '<li class="member-vote-row"><strong><a href="https://www.abgeordnetenwatch.de/profile/ada-beispiel">Ada Beispiel</a></strong>'
            '<span class="vote-pill vote-"></span></li>',
            markup,
        )

    def test_vote_member_key_preserves_persisted_key_for_numeric_and_cleaned_values(self) -> None:
        import derive
        from stable_ids import vote_member_occurrence_id

        vectors = [
            (42, {"name": "Ada Beispiel", "faction": "SPD"}, "42", "Ada Beispiel", "SPD"),
            ("  vote  ", {"name": "  Ada   Beispiel ", "faction": "SPD"}, "vote", "Ada Beispiel", "SPD"),
            ("vote", {"name": "  ", "faction": ""}, "vote", None, "Unbekannt"),
        ]
        for vote_id, member, clean_id, clean_name, party in vectors:
            with self.subTest(vote_id=vote_id, member=member):
                self.assertEqual(derive.vote_member_key(vote_id, member), vote_member_occurrence_id(clean_id, clean_name, party))

    def test_vote_member_key_is_none_without_vote_id(self) -> None:
        import derive

        self.assertIsNone(derive.vote_member_key("  ", {"name": "Ada Beispiel", "faction": "SPD"}))


def _members(faction: str, yes: list[str], no: list[str]) -> list[dict[str, str]]:
    return [{"name": name, "faction": faction, "vote": "yes"} for name in yes] + [
        {"name": name, "faction": faction, "vote": "no"} for name in no
    ]


def _roll_call(members: list[dict[str, str]], **overrides: object) -> dict[str, object]:
    """A vote whose fraction counts and total are exactly its member rows."""
    fractions = fractions_of(members)
    total = {key: sum(row["counts"][key] for row in fractions) for key in ("yes", "no", "abstain", "absent")}
    return _vote(fractions=fractions, members=members, total=total, **overrides)


ABWEICHLER_HEADING = "Anders als die Mehrheit der eigenen Fraktion oder Gruppe"
GAP_NOTE = "Einzelstimmen unvollständig – nicht ermittelbar, wer anders als die Mehrheit der eigenen Fraktion oder Gruppe stimmt"
NONE_NOTE = "Niemand stimmt anders als die Mehrheit der eigenen Fraktion oder Gruppe"


class AbweichlerPanelTests(unittest.TestCase):
    def abweichler_block(self, markup: str) -> str:
        start = markup.index('<div class="vote-abweichler">')
        return markup[start:markup.index("</div>", start)]

    def test_one_abweichler_is_named_under_its_group_with_no_fold(self) -> None:
        markup = vote_summary({"votes": [_roll_call(_members("SPD", ["Ada", "Bea"], ["Cem"]))]})
        block = self.abweichler_block(markup)
        self.assertIn(f"{ABWEICHLER_HEADING} (1)", block)
        self.assertIn("<li>Cem</li>", block)
        self.assertNotIn("<details", block)
        self.assertNotIn(NONE_NOTE, markup)
        self.assertNotIn(GAP_NOTE, markup)

    def test_ten_names_show_inline_and_eleven_fold_the_rest(self) -> None:
        for count, folded in ((10, 0), (11, 1), (62, 52)):
            with self.subTest(count=count):
                names = [f"MdB {n:02d}" for n in range(count)]
                majority = [f"Ja {n:03d}" for n in range(count + 1)]
                markup = vote_summary({"votes": [_roll_call(_members("SPD", majority, names))]})
                block = self.abweichler_block(markup)
                self.assertEqual(block.count("<li>"), count)
                if folded:
                    inline, rest = block.split("<details", 1)
                    self.assertEqual(inline.count("<li>"), 10)
                    self.assertIn(f"<summary>alle {count} anzeigen</summary>", rest)
                    self.assertEqual(rest.count("<li>"), folded)
                    # Alphabetical: the first ten are inline, the rest folded.
                    self.assertIn("<li>MdB 09</li>", inline)
                    self.assertIn("<li>MdB 10</li>", rest)
                else:
                    self.assertNotIn("<details", block)

    def test_every_group_complete_without_abweichler_says_so_once(self) -> None:
        members = _members("SPD", ["Ada", "Bea"], []) + _members("AfD", [], ["Cem"])
        markup = vote_summary({"votes": [_roll_call(members)]})
        self.assertEqual(markup.count(NONE_NOTE), 1)
        self.assertNotIn('class="vote-abweichler"', markup)
        self.assertNotIn(GAP_NOTE, markup)

    # Value: protects=a vote whose member rows name a group with no fraction row shows the gap note, not "Niemand stimmt anders"; fails_when=the vote-wide line ignores groups the fraction chart left out; why_new=adversarial review, B4 ship run 2; seam=none
    def test_a_group_missing_from_the_fraction_rows_shows_the_gap_note(self) -> None:
        members = _members("SPD", ["Ada", "Bea"], []) + _members("AfD", ["Dora"], ["Finn"])
        vote = _roll_call(members)
        vote["fractions"] = [row for row in vote["fractions"] if row["name"] == "SPD"]
        markup = vote_summary({"votes": [vote]})
        self.assertNotIn(NONE_NOTE, markup)
        self.assertEqual(markup.count(GAP_NOTE), 1)

    # Value: protects=a Fraktion missing from both the fraction rows and the Einzelstimmen stops "Niemand stimmt anders" and shows the gap note; fails_when=the vote-wide line only checks the groups it has, so the missing Fraktion's Stimmen go unseen; why_new=B4 review edge 11 (ship run 3, 2026-10-23); seam=none; no_claim=217 of 217 reference votes cover their total
    def test_groups_that_do_not_add_up_to_the_vote_make_no_vote_wide_claim(self) -> None:
        vote = _roll_call(_members("SPD", ["Ada", "Bea"], []) + _members("AfD", [], ["Cem"]))
        vote["total"] = {**vote["total"], "no": vote["total"]["no"] + 40}
        markup = vote_summary({"votes": [vote]})
        self.assertNotIn(NONE_NOTE, markup)
        self.assertEqual(markup.count(GAP_NOTE), 1)

    def test_a_ja_beside_an_enthaltung_majority_or_a_tie_is_no_abweichung_and_the_note_says_why(self) -> None:
        members = (
            _members("SPD", ["Ada", "Bea"], [])
            + [{"name": n, "faction": "FDP", "vote": v} for n, v in (("Cem", "abstain"), ("Dora", "abstain"), ("Emil", "yes"))]
            + _members("AfD", ["Finn"], ["Gus"])
        )
        markup = vote_summary({"votes": [_roll_call(members)]})
        self.assertNotIn('class="vote-abweichler"', markup)
        self.assertIn(
            '<p class="vote-abweichler-none">Niemand stimmt anders als die Mehrheit der eigenen Fraktion oder Gruppe '
            "(gezählt: Ja gegen eine Nein-Mehrheit oder Nein gegen eine Ja-Mehrheit)</p>",
            markup,
        )

    def test_a_vote_without_member_rows_never_reads_as_zero(self) -> None:
        import json
        from _support import FIXTURES

        vote = json.loads((FIXTURES / "roll_call_1002.json").read_text(encoding="utf-8"))
        markup = vote_summary({"votes": [vote]})
        self.assertEqual(markup.count(GAP_NOTE), 1)
        self.assertNotIn(NONE_NOTE, markup)

    def test_a_partial_group_gets_the_gap_note_and_others_still_list(self) -> None:
        members = _members("SPD", ["Ada", "Bea"], ["Cem"]) + _members("AfD", [], ["Dora"])
        vote = _roll_call(members)
        # AfD reports two Nein but only one member row is known.
        vote["fractions"][1]["counts"]["no"] = 2
        vote["total"]["no"] += 1
        markup = vote_summary({"votes": [vote]})
        self.assertIn("<li>Cem</li>", markup)
        self.assertEqual(markup.count(GAP_NOTE), 1)
        self.assertNotIn(NONE_NOTE, markup)
        # The note sits under the AfD row, after SPD's.
        self.assertLess(markup.index("<strong>AfD</strong>"), markup.index(GAP_NOTE))

    def test_a_vote_without_fraction_rows_shows_neither_note(self) -> None:
        markup = vote_summary({"votes": [_vote()]})
        self.assertNotIn(NONE_NOTE, markup)
        self.assertNotIn(GAP_NOTE, markup)

    def test_only_fraktionslos_rows_show_neither_note(self) -> None:
        markup = vote_summary({"votes": [_roll_call(_members("fraktionslos", ["Ada", "Bea"], ["Cem"]))]})
        self.assertNotIn(NONE_NOTE, markup)
        self.assertNotIn(GAP_NOTE, markup)
        self.assertNotIn('class="vote-abweichler"', markup)

    def test_an_inverted_vote_lists_the_same_abweichler(self) -> None:
        members = _members("SPD", ["Ada", "Bea"], ["Cem"])
        plain = self.abweichler_block(vote_summary({"votes": [_roll_call(members)]}))
        inverted = self.abweichler_block(vote_summary({"votes": [_roll_call(members, inverted=True)]}))
        self.assertEqual(inverted, plain)

    # Value: protects=a tied group on an inverted vote shows its "geteilt" pill with its own split class; fails_when=the pill gets no colour class (white text on no background) or a class built from the missing Mehrheitsvotum ("vote-pill vote-"); why_new=no test rendered a tie on an inverted vote; seam=none
    def test_a_tie_on_an_inverted_vote_gets_the_split_pill(self) -> None:
        members = _members("SPD", ["Ada"], ["Bea"])
        markup = vote_summary({"votes": [_roll_call(members, inverted=True)]})
        self.assertIn('<em class="vote-pill vote-split">geteilt</em>', markup)
        self.assertNotIn('vote-pill vote-"', markup)

    def test_abweichler_link_like_the_einzelstimmen(self) -> None:
        from stable_ids import vote_member_occurrence_id

        members = _members("SPD", ["Ada", "Bea"], ["Cem", "Dora", "Emil"]) + _members("SPD", ["Finn", "Gus"], [])
        members[2]["profile_url"] = "https://www.bundestag.de/abgeordnete/cem"
        members[3]["profile_url"] = "https://evil.example/dora"
        key = vote_member_occurrence_id("1", "Emil", "SPD")
        block = self.abweichler_block(vote_summary({"votes": [_roll_call(members)]}, mp_lookup={key: "emil"}))
        self.assertIn('<li><a href="https://www.bundestag.de/abgeordnete/cem">Cem</a></li>', block)
        self.assertIn("<li>Dora</li>", block)
        self.assertNotIn("evil.example", block)
        self.assertIn('<li><a href="../abgeordnete/emil.html">Emil</a></li>', block)

    def test_the_heading_avoids_the_glossary_avoid_list(self) -> None:
        block = self.abweichler_block(vote_summary({"votes": [_roll_call(_members("SPD", ["Ada", "Bea"], ["Cem"]))]}))
        for avoided in ("gegen die Linie", "gegen die eigene Fraktion", "Fraktionslinie"):
            self.assertNotIn(avoided, block)


def _committee_report(vote: dict[str, object], *, under_vote_top: bool = True) -> tuple[dict[str, object], dict[str, object]]:
    be = {
        "dokumentnummer": "20/101",
        "drucksachetyp": "Beschlussempfehlung und Bericht",
        "urheber": ["Haushaltsausschuss"],
        "url": "https://dserver.bundestag.de/btd/20/001/2000101.pdf",
    }
    item = {"votes": [vote], "api": {"linked_drucksachen": [be] if under_vote_top else []}}
    other = {"api": {"linked_drucksachen": [] if under_vote_top else [be]}}
    return item, {"agenda_items": [item, other]}


class CommitteePanelTests(unittest.TestCase):
    def committee_line(self, markup: str) -> str:
        start = markup.index('<p class="vote-committee')
        return markup[start:markup.index("</p>", start)]

    def test_a_matched_beschlussempfehlung_is_cited_with_its_drucksache(self) -> None:
        item, report = _committee_report(_vote(document_numbers=["20/101"]))
        line = self.committee_line(vote_summary(item, report=report))
        self.assertIn("Beschlussempfehlung des Haushaltsausschusses (Drucksache ", line)
        self.assertIn('<a class="doc-link" href="https://dserver.bundestag.de/btd/20/001/2000101.pdf">20/101</a>', line)
        self.assertNotIn("federführend", line.lower())

    def test_an_entschliessungsantrag_vote_cites_the_document_not_a_role(self) -> None:
        item, report = _committee_report(_vote(title="Entschließungsantrag der Fraktion X", document_numbers=["20/105", "20/101"]))
        line = self.committee_line(vote_summary(item, report=report))
        self.assertIn("Beschlussempfehlung des Haushaltsausschusses (Drucksache ", line)
        self.assertNotIn("Federführender", line)

    def test_a_beschlussempfehlung_under_another_top_is_found_and_linked(self) -> None:
        item, report = _committee_report(_vote(document_numbers=["20/101"]), under_vote_top=False)
        line = self.committee_line(vote_summary(item, report=report))
        self.assertIn("Beschlussempfehlung des Haushaltsausschusses", line)
        self.assertIn('href="https://dserver.bundestag.de/btd/20/001/2000101.pdf"', line)

    # Value: protects=a Bundesrat paper with the Beschlussempfehlung's number in the TOP's sources does not replace its Bundestag link or label; fails_when=the TOP's number-keyed links win for committee rows regardless of chamber; why_new=red team, B4 ship run 3; seam=none; no_claim=none
    def test_a_bundesrat_paper_with_the_same_number_is_not_cited_as_the_beschlussempfehlung(self) -> None:
        for br in (
            {"dokumentnummer": "20/101", "herausgeber": "BR", "url": "https://dip.bundestag.de/drucksache/br-20-101"},
            {"dokumentnummer": "20/101", "url": "https://dserver.bundestag.de/brd/2020/0101-20.pdf"},
        ):
            with self.subTest(url=br["url"]):
                item, report = _committee_report(_vote(document_numbers=["20/101"]), under_vote_top=False)
                item["api"]["linked_drucksachen"] = [br]
                line = self.committee_line(vote_summary(item, report=report))
                self.assertIn('<a class="doc-link" href="https://dserver.bundestag.de/btd/20/001/2000101.pdf">20/101</a>', line)
                self.assertNotIn("BR-Drs.", line)

    def test_no_beschlussempfehlung_says_ausschuss_nicht_ermittelt(self) -> None:
        item, report = _committee_report(_vote(document_numbers=["20/200"]))
        line = self.committee_line(vote_summary(item, report=report))
        self.assertIn("Ausschuss nicht ermittelt", line)

    def test_two_urheber_are_both_cited(self) -> None:
        vote = _vote(document_numbers=["20/400"])
        be = {"dokumentnummer": "20/400", "drucksachetyp": "Beschlussempfehlung",
              "urheber": ["Ausschuss für Inneres und Heimat", "Rechtsausschuss"], "url": None}
        line = self.committee_line(vote_summary({"votes": [vote], "api": {"linked_drucksachen": [be]}}))
        self.assertIn("Beschlussempfehlung des Ausschusses für Inneres und Heimat und des Rechtsausschusses (Drucksache ", line)
        self.assertIn('<span class="doc-link muted">20/400</span>', line)

    def test_an_urheber_of_unknown_shape_is_named_without_inflection(self) -> None:
        vote = _vote(document_numbers=["20/400"])
        be = {"dokumentnummer": "20/400", "drucksachetyp": "Beschlussempfehlung", "urheber": ["Bundesregierung"]}
        line = self.committee_line(vote_summary({"votes": [vote], "api": {"linked_drucksachen": [be]}}))
        self.assertIn("Beschlussempfehlung, Urheber: Bundesregierung (Drucksache ", line)

    def test_a_sitting_level_vote_uses_the_whole_report(self) -> None:
        vote = _vote(document_numbers=["20/101"])
        _, report = _committee_report(_vote(id="other"), under_vote_top=False)
        report["sitting_votes"] = [vote]
        line = self.committee_line(vote_summary({"votes": [vote]}, report=report))
        self.assertIn("Beschlussempfehlung des Haushaltsausschusses", line)

    def test_dossier_sections_pass_the_report(self) -> None:
        from features.votes import COMPONENT

        item, report = _committee_report(_vote(document_numbers=["20/101"]), under_vote_top=False)
        cache = politikfelder.empty_cache()
        ctx = {"item": item, "vorgang_cache": cache, "vote_contexts": politikfelder.report_vote_vorgaenge(report, cache)}
        markup = "".join(COMPONENT.dossier_sections(report, ctx))
        self.assertIn("Beschlussempfehlung des Haushaltsausschusses", markup)


def _context_cache(**records: dict[str, object]) -> dict[str, object]:
    return {"version": 1, "vorgaenge": records, "dokumentnummern": {"20/1": ["1"], "20/2": ["2"]}}


class VoteContextPanelTests(unittest.TestCase):
    def panel(self, ids: list[str], state: str, cache: dict[str, object]) -> str:
        vote = _vote(document_numbers=["20/1"])
        return vote_summary({"votes": [vote]}, vote_contexts={"1": politikfelder.VoteContext(ids, state)}, vorgang_cache=cache)

    def test_the_block_sits_above_the_tallies_with_its_source(self) -> None:
        markup = self.panel(["1"], "resolved", _context_cache(**{"1": {"titel": "Rentengesetz", "abstract": "Kurz."}}))
        self.assertIn("<strong>Worum es geht</strong> · Quelle: Deutscher Bundestag/Bundesrat – DIP", markup)
        self.assertLess(markup.index('class="vote-context"'), markup.index('class="vote-fractions"'))
        self.assertIn('<a href="https://dip.bundestag.de/vorgang/-/1">Rentengesetz · DIP</a>', markup)
        self.assertIn('<p class="vote-context-teaser">Kurz.</p>', markup)
        self.assertNotIn("vote-context-more", markup)

    # Value: protects=a block without a titel still names its Vorgang; fails_when=the label needs titel; why_new=D12 labels are new; seam=none
    def test_a_block_without_a_titel_is_labelled_by_its_id(self) -> None:
        cache = _context_cache(**{"1": {"vorgangstyp": "Gesetzgebung", "titel": "", "abstract": "A."}})
        markup = self.panel(["1", "2"], "not_fetched", cache)
        self.assertIn(">DIP-Vorgang 1</a>", markup)
        self.assertIn(">DIP-Vorgang 2</a>", markup)
        self.assertEqual(markup.count('class="vote-context-block"'), 2)

    # Value: protects=no markup injection from DIP text; fails_when=the sanitiser is skipped or the text unescaped; why_new=no abstract rendering before B4; seam=none
    def test_the_abstract_is_sanitised_escaped_and_folded(self) -> None:
        raw = "<strong>Ziel</strong> &amp; Zweck<script>alert(1)</script><br />\r\nZweiter &lt;Absatz&gt;"
        markup = self.panel(["1"], "resolved", _context_cache(**{"1": {"titel": "T", "abstract": raw}}))
        self.assertNotIn("<script", markup)
        self.assertNotIn("<strong>Ziel", markup)
        self.assertIn('<p class="vote-context-teaser">Ziel &amp; Zweck</p>', markup)
        self.assertIn(
            '<details class="vote-context-more"><summary>Ganze Beschreibung</summary>'
            "<p>Ziel &amp; Zweck</p><p>Zweiter &lt;Absatz&gt;</p></details>",
            markup,
        )

    # Value: protects=the panel never says DIP has nothing when we never asked; fails_when=none and not_fetched share copy; why_new=new states; seam=none
    def test_none_and_not_fetched_read_differently(self) -> None:
        no_vorgang = self.panel([], "none", _context_cache())
        self.assertIn(f'<p class="vote-context-gap">{CONTEXT_NO_VORGANG}</p>', no_vorgang)
        self.assertNotIn(CONTEXT_NONE, no_vorgang)
        self.assertIn(f'<p class="vote-context-gap">{CONTEXT_NOT_FETCHED}</p>', self.panel([], "not_fetched", _context_cache()))
        # A resolved Vorgang with no record yet, and one DIP gives no abstract.
        missing = self.panel(["1"], "resolved", _context_cache())
        self.assertIn(CONTEXT_NOT_FETCHED, missing)
        self.assertNotIn(CONTEXT_NONE, missing)
        empty = self.panel(["1"], "resolved", _context_cache(**{"1": {"titel": "T", "abstract": None}}))
        self.assertIn(CONTEXT_NONE, empty)
        self.assertNotIn(CONTEXT_NOT_FETCHED, empty)

    # Value: protects=a partial not_fetched answer (one known Vorgang, another number missing from the cache) says something is missing; fails_when=the gap note is shown only when no Vorgang is known, so a partial context reads as complete; why_new=D7 made such votes not_fetched but the panel showed only the known blocks; seam=none
    def test_a_partial_not_fetched_answer_says_a_vorgang_is_missing(self) -> None:
        cache = _context_cache(**{"1": {"titel": "T", "abstract": "A."}})
        partial = self.panel(["1"], "not_fetched", cache)
        self.assertIn("T · DIP", partial)
        self.assertIn(f'<p class="vote-context-gap">{CONTEXT_NOT_FETCHED}</p>', partial)
        self.assertNotIn(CONTEXT_NOT_FETCHED, self.panel(["1"], "resolved", cache))
        # A known Vorgang without a record says it in its own block, once.
        recordless = self.panel(["1", "2"], "not_fetched", cache)
        self.assertEqual(recordless.count(CONTEXT_NOT_FETCHED), 1)

    # Value: protects=a vote's two panels and its vote_proceedings name the same Vorgänge (D13); fails_when=the context is narrowed per rendering TOP; why_new=new block; seam=none
    def test_a_vote_under_two_tops_shows_one_selection_on_both_panels(self) -> None:
        vote = _vote(document_numbers=["20/1", "20/2"])
        cache = {
            "version": 1,
            "vorgaenge": {"1": {"titel": "Eins", "abstract": "A."}, "2": {"titel": "Zwei", "abstract": "B."}},
            "dokumentnummern": {"20/1": ["1"], "20/2": ["2"]},
        }
        first = {"index": 1, "votes": [vote], "api": {"positions": [{"vorgang_id": "2", "vorgangstyp": "Antrag"}]}}
        second = {"index": 2, "votes": [vote], "api": {}}
        report = {"protocol": {"wahlperiode": 20}, "agenda_items": [first, second]}
        contexts = politikfelder.report_vote_vorgaenge(report, cache)
        panels = [
            vote_summary(item, report=report, vote_contexts=contexts, vorgang_cache=cache) for item in (first, second)
        ]
        self.assertEqual(contexts["1"], (["2"], "resolved"))
        for markup in panels:
            self.assertIn(">Zwei · DIP</a>", markup)
            self.assertNotIn(">Eins · DIP</a>", markup)


class VotePanelAnchorTests(unittest.TestCase):
    # Value: protects=one valid anchor per vote (D9); fails_when=both copies get the id; why_new=no anchor before B4; seam=none
    def test_a_vote_under_two_tops_has_one_id_on_its_first_panel(self) -> None:
        vote = _vote(id=1002)
        first, second = {"index": 1, "votes": [vote]}, {"index": 2, "votes": [vote]}
        report = {"agenda_items": [first, second]}
        self.assertIn('<section class="vote-panel" id="vote-1002">', vote_summary(first, report=report))
        self.assertNotIn('id="vote-1002"', vote_summary(second, report=report))

    def test_a_sitting_level_vote_is_anchored_in_the_sitting_section(self) -> None:
        vote = _vote(id=7)
        report = {"agenda_items": [], "sitting_votes": [vote]}
        self.assertIn('id="vote-7"', vote_summary({"votes": [vote]}, report=report))


LEAD_TERM = '<a href="../bundestag.html#abstimmen">namentliche Abstimmung</a>'


class VoteLeadTests(unittest.TestCase):
    # Value: protects=the lead links "namentliche Abstimmung" to the explainer at the depth of the page that shows the panel, and still escapes the subject once; fails_when=the link is escaped into visible text, the subject is no longer escaped, or the prefix is fixed; why_new=TODO "Link the vote panel's namentlich badge to bundestag.html" (2026-10-30); seam=none
    def test_the_lead_links_the_term_to_the_explainer(self) -> None:
        vote = _vote(description='Antrag „A & B“ <b>fett</b>')
        markup = vote_summary({"votes": [vote]})
        self.assertIn(f"die {LEAD_TERM} „Antrag „A &amp; B“ &lt;b&gt;fett&lt;/b&gt;“ statt", markup)
        self.assertNotIn("&amp;amp;", markup)
        self.assertNotIn("<b>", markup)
        deeper = vote_summary({"votes": [vote]}, site_prefix="../../")
        self.assertIn('<a href="../../bundestag.html#abstimmen">namentliche Abstimmung</a>', deeper)

    def test_lead_names_raw_counts_and_marks_derived_result(self) -> None:
        vote = _vote(date="2024-03-14", result_raw="accepted", result_source="derived",
                     description='Antrag "X" <img>', total={"yes": 10, "no": 5, "abstain": 0})
        markup = vote_summary({"votes": [vote]})
        self.assertIn("Am 14.03.2024 fand im Bundestag", markup)
        self.assertIn("10 Ja, 5 Nein, 0 Enthaltungen", markup)
        self.assertIn("aus den Stimmenzahlen berechnet", markup)
        self.assertIn("&lt;img&gt;", markup)
        self.assertIn("&quot;X&quot;", markup)
        self.assertNotIn("<img>", markup)

    def test_missing_count_is_not_rendered_as_zero(self) -> None:
        vote = _vote(total={"yes": 0, "no": 5})
        markup = vote_summary({"votes": [vote]})
        self.assertIn("0 Ja, 5 Nein, Enthaltungen: nicht überliefert", markup)

    def test_fixture_votes_811_906_996_and_1005_keep_their_recorded_subject_and_counts(self) -> None:
        votes = json.loads((FIXTURES / "vote_interpretation_votes.json").read_text(encoding="utf-8"))
        for vote_id, expected in (("811", "Regelsätze spürbar erhöhen - 200 Euro mehr gegen Inflation und Armut"),
                                  ("906", "Taurus-Marschflugkörpers"), ("996", "Einbürgerungspolitik"),
                                  ("1005", "BAföG-Reform")):
            with self.subTest(vote=vote_id):
                markup = vote_summary({"votes": [{**votes[vote_id], "result_raw": "accepted", "result_source": "official"}]})
                self.assertIn(expected, markup)
                self.assertIn("Ja", markup)
                self.assertIn("Nein", markup)
                self.assertIn("Enthaltungen", markup)

    def test_vote_921_lead_preserves_procedural_motion_despite_matching_bill(self) -> None:
        # https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id=921
        description = (
            "Geschäftsordnungsantrag der Fraktion der CDU/CSU gemäß § 80 Abs. 2 Satz 1 und 2 "
            "i.V.m. § 20 Abs. 2 Satz 3 der Geschäftsordnung über den sofortigen Eintritt in die zweite Beratung "
            "Entwurf eines Lieferkettensorgfaltspflichtenaufhebungsgesetzes (Drucksache 20/11752)"
        )
        vote = _vote(id="921", description=description, document_numbers=["20/11752"],
                     title="Antrag zum Eintritt in die zweite Beratung zur Aufhebung des Lieferkettengesetzes",
                     result_raw="rejected", result_source="official")
        item = {"votes": [vote], "api": {"linked_drucksachen": [{
            "dokumentnummer": "20/11752", "drucksachetyp": "Gesetzentwurf", "herausgeber": "BT",
            "titel": "Lieferkettensorgfaltspflichtenaufhebungsgesetz",
        }]}}
        markup = vote_summary(item)
        self.assertIn(f"die {LEAD_TERM} „{description}“ statt", markup)
        self.assertIn("wurde abgelehnt", markup)

    def test_vote_889_lead_preserves_hier_scope_before_generic_title(self) -> None:
        # https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id=889
        description = (
            "Gesetzentwurf der Bundesregierung Entwurf eines Gesetzes zur Änderung des Erneuerbare-Energien-Gesetzes "
            "und weiterer energiewirtschaftlicher Vorschriften zur Steigerung des Ausbaus photovoltaischer Energieerzeugung "
            "hier: Entwurf eines Gesetzes zur Änderung des Erneuerbare-Energien-Gesetzes zur Vermeidung kurzfristig "
            "auftretender wirtschaftlicher Härten für den Ausbau der eneuerbaren Energien (Drucksachen 20/8657 und 20/9781)"
        )
        vote = _vote(id="889", description=description, document_numbers=["20/8657", "20/9781"],
                     title="Erneuerbare-Energien-Gesetz (GesEntw BReg)", result_raw="accepted", result_source="official")
        markup = vote_summary({"votes": [vote]})
        self.assertIn(f"die {LEAD_TERM} „{description}“ statt", markup)
        self.assertIn("Die Vorlage wurde angenommen", markup)

    def test_confirmed_rejecting_recommendation_names_application_outcome(self) -> None:
        vote = _vote(description="Beschlussempfehlung zum Antrag", result_raw="accepted",
                     result_source="official", result_scope="proposition", inverted=True)
        markup = vote_summary({"votes": [vote]})
        self.assertIn("Empfehlung lautete, den Antrag abzulehnen", markup)
        self.assertIn("Antrag wurde abgelehnt", markup)

    def test_other_recommendation_does_not_infer_antrag_outcome_from_counts(self) -> None:
        vote = _vote(description="Beschlussempfehlung zum Antrag", result_raw="accepted",
                     result_source="official", result_scope="proposition", inverted=None)
        markup = vote_summary({"votes": [vote]})
        self.assertIn("Beschlussempfehlung wurde angenommen", markup)
        self.assertNotIn("Antrag wurde", markup)

    def test_application_scope_is_not_inverted_again_even_for_unknown_subject(self) -> None:
        vote = _vote(description="Abstimmung über den Antrag", result_raw="rejected",
                     result_source="official", result_scope="application", inverted=True)
        markup = vote_summary({"votes": [vote]})
        self.assertIn("Antrag wurde abgelehnt", markup)

    def test_rejecting_recommendation_outcomes_respect_both_result_scopes(self) -> None:
        for scope, raw, expected in (("proposition", "accepted", "abgelehnt"),
                                     ("application", "rejected", "abgelehnt")):
            with self.subTest(scope=scope):
                vote = _vote(description="Beschlussempfehlung zum Antrag", result_raw=raw,
                             result_source="official", result_scope=scope, inverted=True)
                markup = vote_summary({"votes": [vote]})
                self.assertIn("Empfehlung lautete, den Antrag abzulehnen", markup)
                self.assertIn(f"Antrag wurde {expected}", markup)

    def test_direct_proposal_acceptance_and_rejection_use_the_recorded_outcome(self) -> None:
        for result_raw, expected in (("accepted", "angenommen"), ("rejected", "abgelehnt")):
            with self.subTest(result=result_raw):
                vote = _vote(description="Gesetzentwurf der Bundesregierung", result_raw=result_raw,
                             result_source="official")
                markup = vote_summary({"votes": [vote]})
                self.assertIn(f"Vorlage wurde {expected}", markup)

    def test_derived_result_unknown_result_and_special_majority_are_explicit(self) -> None:
        derived = vote_summary({"votes": [_vote(description="Antrag X", result_raw="accepted", result_source="derived")]})
        self.assertIn("aus den Stimmenzahlen berechnet", derived)
        unknown = vote_summary({"votes": [_vote(description="Antrag X", total={"yes": 20, "no": 0, "abstain": 0})]})
        self.assertIn("Ergebnis nicht verfügbar", unknown)
        self.assertNotIn("angenommen", unknown)
        special = vote_summary({"votes": [_vote(procedure_type="constitutional_amendment", total={"yes": 900, "no": 1, "abstain": 0})]})
        self.assertIn("Zweidrittelmehrheit der Mitglieder erforderlich", special)
        self.assertNotIn("angenommen", special)

    def test_missing_date_is_omitted_and_subject_text_is_escaped(self) -> None:
        vote = _vote(date="invalid", description="Antrag <script>alert(1)</script>", result_raw="accepted")
        markup = vote_summary({"votes": [vote]})
        self.assertIn("Im Bundestag fand", markup)
        self.assertIn("aus den Stimmenzahlen berechnet", markup)
        self.assertNotIn("Am —", markup)
        self.assertIn("&lt;script&gt;", markup)
        self.assertNotIn("<script>", markup)

    def test_committee_is_immediately_after_lead_and_context_is_retained_once(self) -> None:
        vote = _vote(description="Beschlussempfehlung zum Antrag", document_numbers=["20/100"])
        document = {"dokumentnummer": "20/100", "drucksachetyp": "Beschlussempfehlung",
                    "urheber": ["Haushaltsausschuss"], "url": "https://dserver.bundestag.de/btd/20/100/2010000.pdf"}
        item = {"votes": [vote], "api": {"linked_drucksachen": [document],
                                           "positions": [{"vorgang_id": "2", "vorgangstyp": "Antrag"}]}}
        report = {"agenda_items": [item]}
        cache = {"vorgaenge": {"2": {"titel": "Kontext", "abstract": "Eine Beschreibung."}}}
        contexts = politikfelder.report_vote_vorgaenge(report, cache)
        markup = vote_summary(item, report=report, vote_contexts=contexts, vorgang_cache=cache)
        self.assertLess(markup.index('class="vote-lead"'), markup.index('class="vote-committee"'))
        self.assertLess(markup.index('class="vote-committee"'), markup.index('class="vote-context"'))
        self.assertEqual(markup.count('class="vote-lead"'), 1)
        self.assertEqual(markup.count('class="vote-committee"'), 1)

    def test_report_link_is_optional_safe_and_present_even_with_dip_abstract(self) -> None:
        vote = _vote(debate_url="https://www.bundestag.de/dokumente/textarchiv/1181880")
        item = {"votes": [vote], "api": {"positions": [{"vorgang_id": "2", "vorgangstyp": "Antrag"}]}}
        report = {"agenda_items": [item]}
        cache = {"version": 1, "dokumentnummern": {"21/6561": ["2"]},
                 "vorgaenge": {"2": {"titel": "Kontext", "abstract": "Eine Beschreibung."}}}
        contexts = politikfelder.report_vote_vorgaenge(report, cache)
        markup = vote_summary(item, report=report, vote_contexts=contexts, vorgang_cache=cache)
        self.assertIn('>Bericht und Debatte beim Bundestag</a>', markup)
        self.assertIn("Eine Beschreibung.", markup)
        unsafe = vote_summary({"votes": [_vote(debate_url="https://evil.example/dokumente/textarchiv/1181880")]})
        malformed = vote_summary({"votes": [_vote(debate_url="https://www.bundestag.de/dokumente/textarchiv/1181880#debatte")]})
        self.assertNotIn("Bericht und Debatte beim Bundestag", unsafe)
        self.assertNotIn("Bericht und Debatte beim Bundestag", malformed)

