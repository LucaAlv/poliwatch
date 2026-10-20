"""Abweichler (CONTEXT.md) and the Beschlussempfehlung a vote cites, derived
from a cached report at render time (B4 Slices 1 and 3)."""

from __future__ import annotations

import json
import unittest
from collections import Counter

import _support  # noqa: F401
import derive
from _support import FIXTURES


def member(name: str, faction: str, vote: str) -> dict[str, str]:
    return {"name": name, "faction": faction, "vote": vote}


def fraction(name: str, yes: int = 0, no: int = 0, abstain: int = 0, absent: int = 0) -> dict[str, object]:
    counts = {"yes": yes, "no": no, "abstain": abstain, "absent": absent}
    return {"name": name, "counts": counts, "total": sum(counts.values())}


def roll_call(members: list[dict[str, str]], fractions: list[dict[str, object]] | None = None) -> dict[str, object]:
    """A vote whose fraction counts are exactly its member rows, unless given."""
    if fractions is None:
        tallies: dict[str, Counter] = {}
        for row in members:
            tallies.setdefault(row["faction"], Counter())[row["vote"]] += 1
        fractions = [fraction(name, **dict(counts)) for name, counts in tallies.items()]
    return {"id": "7", "fractions": fractions, "members": members}


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

    def test_no_member_rows_at_all_is_none(self) -> None:
        vote = json.loads((FIXTURES / "roll_call_1002.json").read_text(encoding="utf-8"))
        result = derive.vote_abweichler(vote)
        self.assertEqual(result, {"CDU/CSU": {"members": [], "state": "none"}, "AfD": {"members": [], "state": "none"}})

    def test_a_group_without_member_rows_is_none_beside_a_complete_one(self) -> None:
        rows = [member("Ada", "SPD", "yes")]
        result = derive.vote_abweichler(roll_call(rows, [fraction("SPD", yes=1), fraction("AfD", no=3)]))
        self.assertEqual({group: row["state"] for group, row in result.items()}, {"SPD": "complete", "AfD": "none"})

    def test_an_inverted_vote_names_the_same_abweichler(self) -> None:
        rows = [member("Ada", "SPD", "yes"), member("Bea", "SPD", "yes"), member("Cem", "SPD", "no")]
        plain = derive.vote_abweichler(roll_call(rows))
        inverted = derive.vote_abweichler({**roll_call(rows), "inverted": True})
        self.assertEqual(inverted, plain)

    def test_a_vote_without_fractions_has_no_groups(self) -> None:
        self.assertEqual(derive.vote_abweichler({"members": [member("Ada", "SPD", "yes")]}), {})


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


if __name__ == "__main__":
    unittest.main()
