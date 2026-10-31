"""Abweichler (CONTEXT.md) and the Beschlussempfehlung a vote cites, derived
from a cached report at render time (B4 Slices 1 and 3)."""

from __future__ import annotations

import json
import unittest
from collections import Counter

import _support  # noqa: F401
import derive
from _support import FIXTURES
from _votes_fixture import fractions_of


def member(name: str, faction: str, vote: str) -> dict[str, str]:
    return {"name": name, "faction": faction, "vote": vote}


def fraction(name: str, yes: int = 0, no: int = 0, abstain: int = 0, absent: int = 0) -> dict[str, object]:
    counts = {"yes": yes, "no": no, "abstain": abstain, "absent": absent}
    return {"name": name, "counts": counts, "total": sum(counts.values())}


def roll_call(members: list[dict[str, str]], fractions: list[dict[str, object]] | None = None) -> dict[str, object]:
    """A vote whose fraction counts are exactly its member rows, unless given."""
    return {"id": "7", "fractions": fractions_of(members) if fractions is None else fractions, "members": members}


class VoteAbweichlerTests(unittest.TestCase):
    def names(self, result: dict, group: str) -> list[str]:
        return [row["name"] for row in result[group]["members"]]

    def test_ja_against_a_nein_majority_and_nein_against_a_ja_majority(self) -> None:
        result = derive.vote_abweichler(roll_call([
            member("Bea", "SPD", "yes"), member("Ada", "SPD", "yes"), member("Cem", "SPD", "no"),
            member("Dora", "AfD", "no"), member("Emil", "AfD", "no"), member("Finn", "AfD", "yes"),
        ]))
        self.assertEqual(self.names(result, "SPD"), ["Cem"])
        self.assertEqual(self.names(result, "AfD"), ["Finn"])
        self.assertEqual({group: row["state"] for group, row in result.items()}, {"SPD": "complete", "AfD": "complete"})

    # Value: protects=a Zusammenschluss with member rows but no fraction row is never counted complete, so nobody is told "Niemand stimmt anders"; fails_when=vote_abweichler only visits fraction rows and the unchecked group drops out; why_new=Claude and Codex adversarial review, B4 ship run 2; seam=none
    def test_a_group_without_a_fraction_row_is_partial(self) -> None:
        rows = [member("Ada", "SPD", "yes"), member("Bea", "SPD", "yes"), member("Dora", "AfD", "yes"), member("Finn", "AfD", "no")]
        result = derive.vote_abweichler(roll_call(rows, [fraction("SPD", yes=2)]))
        self.assertEqual(result["SPD"], {"members": [], "state": "complete"})
        self.assertEqual(result["AfD"], {"members": [], "state": "partial", "unlisted": True})
        # fraktionslos needs no fraction row; it is no Zusammenschluss.
        alone = derive.vote_abweichler(roll_call(rows[:2] + [member("Gil", "fraktionslos", "no")], [fraction("SPD", yes=2)]))
        self.assertEqual(set(alone), {"SPD"})

    def test_members_come_back_alphabetical(self) -> None:
        rows = [member(name, "SPD", "no") for name in ("Zoe", "Ada", "Mia")] + [member(f"J{n}", "SPD", "yes") for n in range(4)]
        self.assertEqual(self.names(derive.vote_abweichler(roll_call(rows)), "SPD"), ["Ada", "Mia", "Zoe"])

    def test_enthaltung_and_nicht_abgegeben_are_never_an_abweichung(self) -> None:
        result = derive.vote_abweichler(roll_call([
            member("Ada", "SPD", "yes"), member("Bea", "SPD", "yes"), member("Cem", "SPD", "abstain"), member("Dora", "SPD", "absent"),
        ]))
        self.assertEqual(result["SPD"], {"members": [], "state": "complete"})

    def test_a_tie_an_enthaltung_majority_and_nobody_voting_have_no_abweichler(self) -> None:
        for label, rows in (
            ("tie", [member("Ada", "SPD", "yes"), member("Bea", "SPD", "no")]),
            ("enthaltung", [member("Ada", "SPD", "abstain"), member("Bea", "SPD", "abstain"), member("Cem", "SPD", "yes")]),
            ("nobody voted", [member("Ada", "SPD", "absent"), member("Bea", "SPD", "absent")]),
        ):
            with self.subTest(label):
                self.assertEqual(derive.vote_abweichler(roll_call(rows))["SPD"], {"members": [], "state": "complete"})

    def test_fraktionslos_and_unknown_affiliation_are_not_groups(self) -> None:
        result = derive.vote_abweichler(roll_call([
            member("Ada", "fraktionslos", "yes"), member("Bea", "fraktionslos", "yes"), member("Cem", "fraktionslos", "no"),
            member("Dora", "", "no"), member("Emil", "", "yes"), member("Finn", "", "yes"),
        ]))
        self.assertEqual(result, {})

    def test_spelling_variants_are_one_group(self) -> None:
        rows = [member("Ada", "Gruppe BSW", "yes"), member("Bea", "BSW (Gruppe)", "yes"), member("Cem", "BSW", "no")]
        fractions = [fraction("Gruppe BSW", yes=1), fraction("BSW (Gruppe)", yes=1, no=1)]
        result = derive.vote_abweichler(roll_call(rows, fractions))
        self.assertEqual(list(result), ["Gruppe BSW"])
        self.assertEqual(self.names(result, "Gruppe BSW"), ["Cem"])

    def test_the_mehrheitsvotum_is_read_from_the_fraction_counts_not_the_member_list(self) -> None:
        # Two members are known, but the counts say 3 Nein and 2 Ja: an
        # incomplete list is partial and names nobody, even though its own
        # rows would make Ada look like an Abweichlerin.
        rows = [member("Ada", "SPD", "no"), member("Bea", "SPD", "yes")]
        result = derive.vote_abweichler(roll_call(rows, [fraction("SPD", yes=2, no=3)]))
        self.assertEqual(result["SPD"], {"members": [], "state": "partial"})

    def test_member_rows_that_disagree_with_the_counts_are_partial(self) -> None:
        rows = [member("Ada", "SPD", "yes"), member("Bea", "SPD", "no")]
        # Same total, different Stimmen.
        result = derive.vote_abweichler(roll_call(rows, [fraction("SPD", yes=2)]))
        self.assertEqual(result["SPD"]["state"], "partial")

    # Value: protects=a member row listed twice counts once, as the store keeps it; fails_when=a duplicate standing in for a missing member matches the counts and lists one Abweichler twice; why_new=B4 ship review (2026-10-22); seam=none
    def test_a_member_listed_twice_counts_once(self) -> None:
        voters = [member(name, "SPD", "yes") for name in ("Ada", "Bea", "Eva")]
        # Dora's Nein is missing and Cem's is listed twice: the counts would match.
        stand_in = derive.vote_abweichler(roll_call(voters + [member("Cem", "SPD", "no")] * 2, [fraction("SPD", yes=3, no=2)]))
        self.assertEqual(stand_in["SPD"], {"members": [], "state": "partial"})
        # A plain duplicate row is one member.
        plain = derive.vote_abweichler(roll_call(voters + [member("Cem", "SPD", "no")] * 2, [fraction("SPD", yes=3, no=1)]))
        self.assertEqual(self.names(plain, "SPD"), ["Cem"])

    # Value: protects=duplicates are judged on the identity key persist binds on, so two spellings sharing a trusted abgeordnetenwatch id are one member, as in the store; fails_when=vote_abweichler dedupes by name and calls a stand-in "complete" while the store holds one row fewer; why_new=Codex review of 143a49d (2026-10-22); seam=none
    def test_two_spellings_with_one_trusted_aw_id_are_one_member(self) -> None:
        voters = [member(name, "SPD", "yes") for name in ("Ada", "Bea", "Eva")]
        cem = [{**member(spelling, "SPD", "no"), "abgeordnetenwatch": {"id": 42, "match": "ext_id"}} for spelling in ("Cem", "Cem  Çelik")]
        stand_in = derive.vote_abweichler(roll_call(voters + cem, [fraction("SPD", yes=3, no=2)]))
        self.assertEqual(stand_in["SPD"], {"members": [], "state": "partial"})

    # Value: protects=an abgeordnetenwatch id found by name is no identity, so two people sharing one stay two members; fails_when=the dedupe trusts any aw id; why_new=Codex review of 143a49d; seam=none
    def test_an_untrusted_aw_id_does_not_merge_two_members(self) -> None:
        voters = [member(name, "SPD", "yes") for name in ("Ada", "Bea", "Eva")]
        guessed = [{**member(name, "SPD", "no"), "abgeordnetenwatch": {"id": 42, "match": "name"}} for name in ("Cem", "Dora")]
        result = derive.vote_abweichler(roll_call(voters + guessed, [fraction("SPD", yes=3, no=2)]))
        self.assertEqual(result["SPD"]["state"], "complete")
        self.assertEqual(self.names(result, "SPD"), ["Cem", "Dora"])

    # Value: protects=a name-guessed abgeordnetenwatch profile never sits beside a named Abweichler, a Redner-ID match does; fails_when=member_profile_url links the aw url whatever its match kind; why_new=B4 review item 8; seam=none
    def test_member_profile_url_links_aw_only_for_a_trusted_match(self) -> None:
        url = "https://www.abgeordnetenwatch.de/profile/cem-celik"
        own = "https://www.bundestag.de/abgeordnete/biografien/C/celik-1"
        for aw, expected in (
            ({"id": 42, "match": "ext_id", "url": url}, url),
            ({"id": 42, "match": "name", "url": url}, None),
            ({"id": 42, "url": url}, None),
            ({"url": url}, None),
        ):
            with self.subTest(aw=aw):
                self.assertEqual(derive.member_profile_url({"abgeordnetenwatch": aw}), expected)
        # An untrusted aw profile falls back to the member's own link.
        self.assertEqual(derive.member_profile_url({"abgeordnetenwatch": {"id": 42, "match": "name", "url": url}, "profile_url": own}), own)

    # Value: protects=bundestag.de links an MP without a biography back to the Abstimmung page; that link names nobody, so such MPs stay distinct; fails_when=the Abstimmung URL serves as a profile identity and folds every such MP of a vote into one (63 rows on the reference store); why_new=found while keying the dedupe on identity (2026-10-22); seam=none
    def test_members_linked_to_the_abstimmung_page_stay_distinct(self) -> None:
        page = "https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id=853"
        rows = [{**member(name, "SPD", "yes"), "profile_url": page} for name in ("Ada", "Bea")] + [member("Cem", "SPD", "no")]
        result = derive.vote_abweichler(roll_call(rows))
        self.assertEqual(result["SPD"], {"members": [rows[2]], "state": "complete"})

    # Value: protects=a row whose identity also appears in another group is one member, in the group of its last row, as vote_members (keyed on the vote and the MP) keeps it; fails_when=the dedupe is per group and counts the MP in both; why_new=the store keys member rows vote-wide; seam=none
    def test_one_identity_in_two_groups_counts_in_the_last_rows_group(self) -> None:
        profile = "https://www.bundestag.de/abgeordnete/biografien/C/cem-1"
        rows = [member("Ada", "SPD", "yes"), {**member("Cem", "SPD", "no"), "profile_url": profile},
                member("Dora", "AfD", "no"), {**member("Cem", "AfD", "no"), "profile_url": profile}]
        result = derive.vote_abweichler(roll_call(rows, [fraction("SPD", yes=1, no=1), fraction("AfD", no=2)]))
        self.assertEqual({group: row["state"] for group, row in result.items()}, {"SPD": "partial", "AfD": "complete"})

    def test_no_member_rows_at_all_is_none(self) -> None:
        vote = json.loads((FIXTURES / "roll_call_1002.json").read_text(encoding="utf-8"))
        result = derive.vote_abweichler(vote)
        self.assertEqual(result, {"CDU/CSU": {"members": [], "state": "no_members"}, "AfD": {"members": [], "state": "no_members"}})

    def test_a_group_without_member_rows_is_none_beside_a_complete_one(self) -> None:
        rows = [member("Ada", "SPD", "yes")]
        result = derive.vote_abweichler(roll_call(rows, [fraction("SPD", yes=1), fraction("AfD", no=3)]))
        self.assertEqual({group: row["state"] for group, row in result.items()}, {"SPD": "complete", "AfD": "no_members"})

    def test_an_all_zero_row_without_members_is_complete_not_missing(self) -> None:
        rows = [member("Ada", "SPD", "yes")]
        result = derive.vote_abweichler(roll_call(rows, [fraction("SPD", yes=1), fraction("AfD")]))
        self.assertEqual(result["AfD"], {"members": [], "state": "complete"})

    def test_an_inverted_vote_names_the_same_abweichler(self) -> None:
        rows = [member("Ada", "SPD", "yes"), member("Bea", "SPD", "yes"), member("Cem", "SPD", "no")]
        plain = derive.vote_abweichler(roll_call(rows))
        inverted = derive.vote_abweichler({**roll_call(rows), "inverted": True})
        self.assertEqual(inverted, plain)

    def test_a_vote_without_fractions_has_no_groups(self) -> None:
        self.assertEqual(derive.vote_abweichler({"members": [member("Ada", "SPD", "yes")]}), {})


class VoteGroupsCoverTotalTests(unittest.TestCase):
    # Value: protects=a vote-wide Abweichler claim is only made when the fraction rows account for every Stimme of the vote; fails_when=a Fraktion missing from both the fraction rows and the Einzelstimmen leaves the others "complete" and the panel says "Niemand stimmt anders"; why_new=B4 review edge 11 (ship run 3, 2026-10-23); seam=none; no_claim=217 of 217 reference votes cover their total
    def test_the_fraction_rows_must_add_up_to_the_vote_total(self) -> None:
        rows = [fraction("SPD", yes=2, no=1), fraction("fraktionslos", no=1, absent=1)]
        total = {"yes": 2, "no": 2, "abstain": 0, "absent": 1}
        self.assertTrue(derive.vote_groups_cover_total({"fractions": rows, "total": total}))
        # A Fraktion the tally holds but no row names: 40 Stimmen nobody accounts for.
        self.assertFalse(derive.vote_groups_cover_total({"fractions": rows, "total": {**total, "no": 42}}))
        # Two spellings of one Zusammenschluss are one row whose counts add.
        split = [fraction("Gruppe BSW", yes=1), fraction("BSW (Gruppe)", yes=1)]
        self.assertTrue(derive.vote_groups_cover_total({"fractions": split, "total": {"yes": 2, "no": 0, "abstain": 0, "absent": 0}}))

    def test_without_a_total_or_fraction_rows_nothing_is_covered(self) -> None:
        rows = [fraction("SPD", yes=2)]
        self.assertFalse(derive.vote_groups_cover_total({"fractions": rows}))
        self.assertFalse(derive.vote_groups_cover_total({"fractions": rows, "total": {}}))
        self.assertFalse(derive.vote_groups_cover_total({"fractions": [], "total": {"yes": 0, "no": 0, "abstain": 0, "absent": 0}}))

    # Value: protects=a total count that is not a number ("nicht überliefert" in the lead) makes no vote-wide claim instead of raising; fails_when=the count goes through int() and a stray string takes the page build down or a missing count passes as 0; why_new=code review 2026-10-31; seam=none
    def test_a_count_the_total_does_not_hold_as_a_number_covers_nothing(self) -> None:
        rows = [fraction("SPD", yes=2)]
        for count in ("x", "2", None, True):
            with self.subTest(count=count):
                total = {"yes": count, "no": 0, "abstain": 0, "absent": 0}
                self.assertFalse(derive.vote_groups_cover_total({"fractions": rows, "total": total}))
        self.assertFalse(derive.vote_groups_cover_total({"fractions": rows, "total": {"yes": 2, "no": 0, "abstain": 0}}))


class VoteAbweichlerCountTests(unittest.TestCase):
    # Value: protects=the archive and the panel share one vote-wide Abweichler count: every group complete and the groups adding up to the total; fails_when=one caller drops the cover or completeness test the other applies; why_new=code review 2026-10-31 folded the two copies into derive; seam=none
    def test_a_count_needs_complete_groups_that_cover_the_vote(self) -> None:
        members = [member("Ada", "SPD", "yes"), member("Bo", "SPD", "no"), member("Cy", "SPD", "yes")]
        vote = {"fractions": [fraction("SPD", yes=2, no=1)], "members": members, "total": {"yes": 2, "no": 1, "abstain": 0, "absent": 0}}
        self.assertEqual(derive.vote_abweichler_count(vote), 1)
        self.assertEqual(derive.vote_abweichler_count(vote, derive.vote_abweichler(vote)), 1)
        self.assertIsNone(derive.vote_abweichler_count({**vote, "total": {"yes": 2, "no": 41, "abstain": 0, "absent": 0}}))
        self.assertIsNone(derive.vote_abweichler_count({**vote, "members": members[:2]}))
        self.assertIsNone(derive.vote_abweichler_count({"members": members, "total": vote["total"]}))


def linked(number: str, drucksachetyp: str, urheber: list[str], **extra: object) -> dict[str, object]:
    return {
        "dokumentnummer": number,
        "drucksachetyp": drucksachetyp,
        "urheber": urheber,
        "url": f"https://dserver.bundestag.de/btd/{number}.pdf",
        **extra,
    }


def committee_report() -> dict[str, object]:
    """A sitting whose TOPs cover every case of the committee lookup."""
    return {
        "agenda_items": [
            {
                "heading": "TOP 1 Gesetz",
                "api": {"linked_drucksachen": [
                    linked("20/100", "Gesetzentwurf", ["Bundesregierung"]),
                    linked("20/101", "Beschlussempfehlung und Bericht", ["Haushaltsausschuss"]),
                ]},
                "votes": [
                    {"id": "1", "document_numbers": ["20/100", "20/101"]},
                    # An Entschließungsantrag to the same law lists the law's Beschlussempfehlung.
                    {"id": "2", "document_numbers": ["20/105", "20/101"]},
                ],
            },
            {
                "heading": "TOP 2 Antrag",
                "api": {"linked_drucksachen": [linked("20/200", "Antrag", ["Fraktion der SPD"])]},
                # A plain Antrag vote, and one whose Beschlussempfehlung is linked under TOP 3 only.
                "votes": [{"id": "3", "document_numbers": ["20/200"]}, {"id": "4", "document_numbers": ["20/0301"]}],
            },
            {
                "heading": "TOP 3",
                "api": {"linked_drucksachen": [
                    linked("20/301", "Beschlussempfehlung", ["Auswärtiger Ausschuss"]),
                    linked("20/400", "Beschlussempfehlung", ["Ausschuss für Inneres und Heimat", "Rechtsausschuss"]),
                    # A Bundesrat paper of the same shape is not the Bundestag's 20/500.
                    linked("20/500", "Beschlussempfehlung", ["Ausschuss des Bundesrates"], herausgeber="BR"),
                    linked("20/600", "Beschlussempfehlung", []),
                ]},
            },
        ],
        "sitting_votes": [
            {"id": "5", "document_numbers": ["20/400"]},
            {"id": "6", "document_numbers": ["20/500", "20/600"]},
        ],
    }


class VoteCommitteesTests(unittest.TestCase):
    def committees(self, vote_id: str) -> list[dict[str, object]]:
        report = committee_report()
        vote = next(vote for _, vote in derive.iter_report_votes(report) if vote["id"] == vote_id)
        return derive.vote_committees(vote, report)

    def test_a_matched_beschlussempfehlung_names_its_urheber_and_drucksache(self) -> None:
        self.assertEqual(self.committees("1"), [{
            "number": "20/101",
            "drucksachetyp": "Beschlussempfehlung und Bericht",
            "urheber": ["Haushaltsausschuss"],
            "url": "https://dserver.bundestag.de/btd/20/101.pdf",
        }])

    def test_an_entschliessungsantrag_vote_cites_the_laws_beschlussempfehlung(self) -> None:
        self.assertEqual([row["number"] for row in self.committees("2")], ["20/101"])

    def test_a_plain_antrag_vote_has_none(self) -> None:
        self.assertEqual(self.committees("3"), [])

    def test_a_beschlussempfehlung_linked_under_another_top_of_the_sitting_counts(self) -> None:
        rows = self.committees("4")
        self.assertEqual([(row["number"], row["urheber"]) for row in rows], [("20/301", ["Auswärtiger Ausschuss"])])

    def test_a_sitting_level_vote_uses_the_same_map_and_keeps_two_urheber(self) -> None:
        rows = self.committees("5")
        self.assertEqual([row["urheber"] for row in rows], [["Ausschuss für Inneres und Heimat", "Rechtsausschuss"]])

    def test_a_bundesrat_paper_and_a_beschlussempfehlung_without_urheber_name_nobody(self) -> None:
        self.assertEqual(self.committees("6"), [])

    def test_a_report_without_linked_drucksachen_has_none(self) -> None:
        self.assertEqual(derive.vote_committees({"document_numbers": ["20/101"]}, {}), [])


class CommitteeRecipeParityTests(unittest.TestCase):
    """D1: the Daten recipe counts the same Beschlussempfehlung urheber the
    vote panels cite, read from the store instead of the report."""

    def report(self) -> dict[str, object]:
        report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
        cases = committee_report()
        template = report["agenda_items"][0]["votes"][0]
        for target, source in zip(report["agenda_items"], cases["agenda_items"]):
            target.setdefault("api", {})["linked_drucksachen"] = source["api"]["linked_drucksachen"]
        # TOP 3 of the cases joins TOP 2's links, so a vote under TOP 1 finds
        # a Beschlussempfehlung that only TOP 2 lists.
        report["agenda_items"][1]["api"]["linked_drucksachen"] += cases["agenda_items"][2]["api"]["linked_drucksachen"]

        def vote(source: dict[str, object]) -> dict[str, object]:
            return {**template, "id": source["id"], "document_numbers": source["document_numbers"], "members": []}

        report["agenda_items"][0]["votes"] = [vote(v) for item in cases["agenda_items"] for v in item.get("votes", [])]
        report["sitting_votes"] = [vote(v) for v in cases["sitting_votes"]]
        return report

    def test_recipe_rows_equal_the_panel_derivation(self) -> None:
        import sqlite3
        import tempfile
        from pathlib import Path

        import build_dip_pulse_site as build
        import persist_dip_pulse_store as pulse_store

        report = self.report()
        panel = Counter(
            name
            for _, vote in derive.iter_report_votes(report)
            for name in {name for row in derive.vote_committees(vote, report) for name in row["urheber"]}
        )
        self.assertEqual(
            panel,
            {"Haushaltsausschuss": 2, "Auswärtiger Ausschuss": 1, "Ausschuss für Inneres und Heimat": 1, "Rechtsausschuss": 1},
        )
        recipe = build.RECIPES_BY_ID["r6-ausschuss"]
        self.assertEqual(recipe["depends_on"], "votes")
        self.assertEqual([column["name"] for column in recipe["columns"]], ["beschlussempfehlung_urheber", "abstimmungen"])
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                with conn:
                    pulse_store.persist_report(conn, report)
                sql = recipe["sql"].rstrip().removesuffix("LIMIT 5;")
                conn.row_factory = sqlite3.Row
                rows = [dict(row) for row in conn.execute(sql)]
            finally:
                conn.close()
        self.assertEqual({row["beschlussempfehlung_urheber"]: row["abstimmungen"] for row in rows}, dict(panel))
        self.assertEqual(rows[0], {"beschlussempfehlung_urheber": "Haushaltsausschuss", "abstimmungen": 2})



class VoteMemberIdentityTests(unittest.TestCase):
    """derive.vote_member_identity is the key persist hands upsert_mp for a vote member."""

    # Value: protects=derive and persist key a vote member identically, so the Abweichler dedupe and vote_members cannot drift; fails_when=either side changes its rule alone; why_new=Codex review of 143a49d; seam=persist_dip_pulse_store.mp_identity
    def test_it_matches_what_persist_passes_mp_identity(self) -> None:
        from persist_dip_pulse_store import mp_identity

        biography = "https://www.bundestag.de/abgeordnete/biografien/A/ada-1"
        shapes = [
            member("Ada  Lovelace", "SPD", "yes"),
            member("", "", "no"),
            {**member("Ada", "Gruppe BSW", "no"), "profile_url": biography},
            {**member("Ada", "SPD", "no"), "profile_url": "https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id=853"},
            {**member("Ada", "SPD", "yes"), "abgeordnetenwatch": {"id": 7, "match": "ext_id", "url": "https://www.abgeordnetenwatch.de/profile/ada"}},
            {**member("Ada", "SPD", "yes"), "abgeordnetenwatch": {"id": 7, "match": "name"}, "profile_url": biography},
            {**member("Ada", "SPD", "yes"), "abgeordnetenwatch": {"id": "7", "match": "ext_id"}},
        ]
        for shape in shapes:
            with self.subTest(shape=shape):
                profile = shape.get("abgeordnetenwatch") or {}
                persisted = mp_identity(
                    aw_politician_id=profile.get("id") if isinstance(profile.get("id"), int) else None,
                    aw_match=profile.get("match"),
                    profile_url=derive.member_profile_url(shape),
                    display_name=shape.get("name"),
                    party_name=derive.zusammenschluss(shape.get("faction")) or "Unbekannt",
                )
                self.assertEqual(derive.vote_member_identity(shape), persisted)

    def test_only_a_page_about_one_person_is_a_profile(self) -> None:
        for url, expected in (
            ("https://www.bundestag.de/abgeordnete/biografien/A/abdi_sanae-861028?subview=na", True),
            ("https://www.bundestag.de/abgeordnete/biografien20/A/x-1?subview=na", True),
            ("https://www.abgeordnetenwatch.de/profile/ada-beispiel", True),
            ("https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id=853", False),
            ("https://evil.example/abgeordnete/x", False),
            # A browser reads these as another host or user: no profile (B4 ship run 3 review).
            ("https://evil.example\\@www.bundestag.de/abgeordnete/x", False),
            ("https://user@www.bundestag.de/abgeordnete/x", False),
            ("https://www.bundestag.de:443/abgeordnete/x", False),
            ("https://www.bundestag.de:99999/abgeordnete/x", False),
            ("https://www.bundestag.de/abgeordnete/x\ty", False),
            ("https://www.abgeordnetenwatch.de/profile/ada beispiel", False),
            # A dot segment leaves the person path once a browser resolves it.
            ("https://www.bundestag.de/abgeordnete/../apps/na/x", False),
            ("https://www.bundestag.de/abgeordnete/%2E%2e/parlament/plenum/abstimmung/abstimmung?id=853", False),
            ("https://www.bundestag.de/abgeordnete/./x", False),
            ("https://www.abgeordnetenwatch.de/profile/..", False),
            ("https://www.bundestag.de/abgeordnete/biografien/A/a..b-1", True),
            ("https://[invalid", False),
            (None, False),
        ):
            with self.subTest(url=url):
                self.assertEqual(derive.member_profile_url({"profile_url": url}), url if expected else None)

    # Value: protects=the abgeordnetenwatch URL passes the same person-page check as the member's own link before it becomes an identity key or mps.profile_url; fails_when=member_profile_url returns any aw url as-is again; why_new=only the bundestag.de link was checked (B4 ship review 2026-10-22); seam=none
    def test_an_abgeordnetenwatch_url_must_name_a_person_too(self) -> None:
        own = "https://www.bundestag.de/abgeordnete/biografien/A/x-1"
        aw = "https://www.abgeordnetenwatch.de/profile/ada-beispiel"
        self.assertEqual(derive.member_profile_url({"abgeordnetenwatch": {"id": 1, "match": "ext_id", "url": aw}, "profile_url": own}), aw)
        for bad in (
            "https://evil.example/profile/ada",
            "javascript:alert(1)",
            "javascript://www.abgeordnetenwatch.de/profile/x",
            "http://www.abgeordnetenwatch.de/profile/ada-beispiel",
            "https://www.abgeordnetenwatch.de/",
            "https://[invalid",
        ):
            with self.subTest(aw=bad):
                self.assertEqual(derive.member_profile_url({"abgeordnetenwatch": {"id": 1, "match": "ext_id", "url": bad}, "profile_url": own}), own)
                self.assertIsNone(derive.member_profile_url({"abgeordnetenwatch": {"url": bad}}))


class VoteSubjectTests(unittest.TestCase):
    def test_unique_exact_document_supplies_its_type_and_title(self) -> None:
        report = {"agenda_items": [{"api": {"linked_drucksachen": [
            linked("20/100", "Gesetzentwurf", ["Bundesregierung"], titel="Gespeicherter Titel"),
            linked("20/101", "Antrag", ["Fraktion"], titel="Nachbar"),
        ]}}]}
        self.assertEqual(derive.vote_subject({"document_numbers": ["20/100"]}, report),
                         "Gesetzentwurf: Gespeicherter Titel")
        self.assertEqual(derive.vote_subject({"document_numbers": ["20/100", "20/999"],
                                            "title": "Verzeichneter Abstimmungstitel"}, report),
                         "Verzeichneter Abstimmungstitel")

    def test_subject_classifier_keeps_field_precedence(self) -> None:
        self.assertEqual(derive.abstimmungsgegenstand({"description": "Antrag X", "title": "Beschlussempfehlung"}), "vorlage")
        self.assertEqual(derive.abstimmungsgegenstand({"description": "Beschlussempfehlung X"}), "beschlussempfehlung")
        self.assertIsNone(derive.abstimmungsgegenstand({"description": "Unklar"}))

    def test_subject_does_not_pick_a_neighbor_document(self) -> None:
        report = {"agenda_items": [{"api": {"linked_drucksachen": [
            linked("20/100", "Gesetzentwurf", ["Bundesregierung"], titel="Nachbar"),
        ]}}]}
        self.assertEqual(derive.vote_subject({"description": "Vorlage", "document_numbers": ["20/999"]}, report), "Vorlage")

    def test_multiple_matching_documents_do_not_supply_one_arbitrary_title(self) -> None:
        report = {"agenda_items": [{"api": {"linked_drucksachen": [
            linked("20/100", "Antrag", ["Fraktion"], titel="Erster Titel"),
            linked("20/101", "Gesetzentwurf", ["Bundesregierung"], titel="Zweiter Titel"),
        ]}}]}
        vote = {"description": "Vorlagen im Paket", "title": "Allgemeiner Titel",
                "document_numbers": ["20/100", "20/101"]}
        self.assertEqual(derive.vote_subject(vote, report), "Vorlagen im Paket")

    def test_conflicting_metadata_for_the_same_document_does_not_supply_a_title(self) -> None:
        report = {"agenda_items": [
            {"api": {"linked_drucksachen": [linked("20/100", "Antrag", ["Fraktion"], titel="Erster Titel")]}},
            {"api": {"linked_drucksachen": [linked("20/100", "Antrag", ["Fraktion"], titel="Anderer Titel")]}},
        ]}
        self.assertEqual(derive.vote_subject({"description": "Antrag mit unklarer Zuordnung", "document_numbers": ["20/100"]}, report),
                         "Antrag mit unklarer Zuordnung")

    def test_recommendation_uses_its_recorded_description_not_an_underlying_document_title(self) -> None:
        report = {"agenda_items": [{"api": {"linked_drucksachen": [
            linked("20/100", "Antrag", ["Fraktion"], titel="Underlying title"),
        ]}}]}
        vote = {"description": "Beschlussempfehlung des Ausschusses zu einem Antrag",
                "title": "Allgemeiner Titel", "document_numbers": ["20/100"]}
        self.assertEqual(derive.vote_subject(vote, report), vote["description"])

    def test_vote_811_preserves_the_motion_description_and_falls_back_when_missing(self) -> None:
        vote = json.loads((FIXTURES / "vote_interpretation_votes.json").read_text(encoding="utf-8"))["811"]
        self.assertEqual(derive.vote_subject(vote, {}), vote["description"])
        for description in (None, "", "   "):
            with self.subTest(description=description):
                self.assertEqual(derive.vote_subject({**vote, "description": description}, {}), vote["title"])

    def test_bookstabe_or_artikel_in_heading_prevents_title_shortening(self) -> None:
        report = {"agenda_items": [{"api": {"linked_drucksachen": [
            linked("20/100", "Gesetzentwurf", ["Bundesregierung"], titel="Gesetz"),
        ]}}]}
        for field in ("vote_heading", "title"):
            with self.subTest(field=field):
                vote = {"document_numbers": ["20/100"], field: "Gesetzentwurf hier: Artikel 5 Buchstabe a"}
                self.assertIn("Artikel 5 Buchstabe a", derive.vote_subject(vote, report))

    def test_procedural_subject_and_hier_scope_survive_title_fallbacks(self) -> None:
        report = {"agenda_items": [{"api": {"linked_drucksachen": [
            linked("20/100", "Gesetzentwurf", ["Bundesregierung"], titel="Allgemeiner Gesetzentwurf"),
        ]}}]}
        for subject in (
            "Geschäftsordnungsantrag über den sofortigen Eintritt in die zweite Beratung",
            "Gesetzentwurf hier: Änderung zur Vermeidung wirtschaftlicher Härten",
        ):
            for field in ("description", "vote_heading", "title"):
                for numbers in (["20/100"], ["20/100", "20/101"]):
                    with self.subTest(subject=subject, field=field, numbers=numbers):
                        vote = {"description": "Gesetzentwurf", "title": "Allgemeiner Titel",
                                "document_numbers": numbers, field: subject}
                        self.assertIn(subject, derive.vote_subject(vote, report))


if __name__ == "__main__":
    unittest.main()
