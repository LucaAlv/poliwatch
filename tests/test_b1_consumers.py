import unittest
import json
import sqlite3
from unittest.mock import Mock
from pathlib import Path

import _support  # noqa: F401
import build_dip_pulse_site as build
import derive
import facts
import persist_dip_pulse_store as pulse_store
import render_dip_pulse_html as pulse_html
from _support import FIXTURES


class SittingVoteConsumerTests(unittest.TestCase):
    def test_fresh_resolver_replaces_cached_vote_member_profile(self):
        for at_sitting_level in (False, True):
            with self.subTest(at_sitting_level=at_sitting_level):
                member = {"name": "Anna Beispiel", "faction": "SPD"}
                old_vote = {"id": "1", "members": [{**member, "abgeordnetenwatch": {"id": 7}}]}
                new_vote = {"id": "1", "members": [dict(member)]}
                if at_sitting_level:
                    old_report = {"sitting_votes": [old_vote]}
                    report = {"sitting_votes": [new_vote]}
                else:
                    old_report = {"agenda_items": [{"index": 1, "votes": [old_vote]}]}
                    report = {"agenda_items": [{"index": 1, "votes": [new_vote]}]}
                resolver = Mock()
                resolver.resolve.return_value = {"id": 8}

                build.reuse_existing_dossier_enrichments(report, old_report, votes=False, profiles=False)
                build.enrich_report_with_profiles(report, resolver)

                resolver.resolve.assert_called_once()
                self.assertEqual(new_vote["members"][0]["abgeordnetenwatch"], {"id": 8})

    def test_cached_vote_member_profiles_are_reused_without_resolver(self):
        cached_profile = {"id": 7}
        old_report = {"sitting_votes": [{"id": "1", "members": [
            {"name": "Anna Beispiel", "faction": "SPD", "abgeordnetenwatch": cached_profile}
        ]}]}
        member = {"name": "Anna Beispiel", "faction": "SPD"}
        report = {"sitting_votes": [{"id": "1", "members": [member]}]}

        build.reuse_existing_dossier_enrichments(report, old_report, votes=False, profiles=True)

        self.assertEqual(member["abgeordnetenwatch"], cached_profile)
        self.assertIsNot(member["abgeordnetenwatch"], cached_profile)

    def test_archive_keeps_sitting_vote_and_links_to_sitting_section(self):
        vote = {
            "id": 9012,
            "date": "2026-04-24",
            "title": "Antrag zur Übergewinnsteuer",
            "result_raw": "accepted",
            "result_source": "derived",
            "inverted": True,
            "fractions": [
                {"name": "SPD", "counts": {"yes": 10, "no": 2, "abstain": 0}},
                {"name": "FDP", "counts": {"yes": 2, "no": 2, "abstain": 0}},
            ],
        }
        report = {
            "agenda_items": [{"index": 1, "votes": [{**vote}]}],
            "sitting_votes": [vote],
        }
        rows = build.collect_votes_archive([
            {"report": report, "page_path": "protocols/plenarprotokoll-21-1.html"}
        ])
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertTrue(row["href"].endswith("#top-1"))
        self.assertEqual(row["fraction_positions"]["SPD"], "gegen den Antrag")
        self.assertEqual(row["fraction_positions"]["FDP"], "geteilt")
        self.assertEqual(derive.vote_outcome(row["vote"]), "rejected")

    def test_archive_filter_uses_support_for_application(self):
        script = build.render_votes_archive_script()
        self.assertIn("positions[name] === 'für den Antrag'", script)
        self.assertNotIn("positions[name] === 'gegen den Antrag'", script)

    def test_unmatched_vote_archives_with_sitting_anchor(self):
        vote = {"id": 9013, "date": "2026-04-24", "title": "Unzugeordnete Abstimmung"}
        rows = build.collect_votes_archive([
            {"report": {"agenda_items": [], "sitting_votes": [vote]},
             "page_path": "protocols/plenarprotokoll-21-1.html"}
        ])
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["href"].endswith("#sitting-votes"))
        self.assertEqual(rows[0]["document_links"], {})

    def _sitting_only_store(self):
        report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
        vote = report["agenda_items"][0]["votes"][0]
        for item in report["agenda_items"]:
            item["votes"] = []
            item.pop("vote", None)
        report["sitting_votes"] = [vote]
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        pulse_store.persist_report(conn, report)
        return conn, report, vote

    def test_sitting_only_vote_reaches_facts_export_and_mp_history(self):
        conn, report, vote = self._sitting_only_store()
        self.addCleanup(conn.close)
        for metric_id in ("knappste-abstimmung", "meiste-abweichler"):
            sql = next(metric["sql"] for metric in facts.REGISTRY if metric["id"] == metric_id)
            self.assertEqual(conn.execute(sql).fetchone()["id"], str(vote["id"]))
        r4 = next(recipe["sql"] for recipe in build.RECIPES if recipe["id"] == "r4-knappste-abstimmungen")
        self.assertEqual(conn.execute(r4).fetchone()["document_number"], report["protocol"]["dokumentnummer"])
        mps, _, _ = build.collect_abgeordnete(conn)
        histories = [entry for mp in mps for entry in mp.get("votes", [])]
        self.assertTrue(any(str(entry.get("vote_id")) == str(vote["id"]) for entry in histories))

    def test_weekly_sitting_count_includes_sitting_level_vote(self):
        vote = {"id": 9001, "date": "2026-04-24", "title": "TOP fehlt"}
        stats = build.pulse_html.week_stats(
            (2026, 17),
            [{"report": {"protocol": {"datum": "2026-04-24", "dokumentnummer": "21/1"},
                         "agenda_items": [], "sitting_votes": [vote]},
              "protocol": {"dokumentnummer": "21/1", "datum": "2026-04-24"},
              "page_path": "protocols/plenarprotokoll-21-1.html"}],
        )
        self.assertEqual(stats["vote_count"], 1)
        self.assertEqual(stats["vote_sittings"][0][2:], (None, 1))
        card = build.render_votes_card(stats, "protocols/latest.html")
        self.assertIn("#sitting-votes", card)

    def test_dossier_renders_sitting_votes_section(self):
        report = json.loads((FIXTURES / "report.json").read_text(encoding="utf-8"))
        votes = []
        for item in report["agenda_items"]:
            votes.extend(item.get("votes") or [])
            item["votes"] = []
        report["sitting_votes"] = votes[:1]
        html = pulse_html.render_html(report)
        self.assertIn('id="sitting-votes"', html)
        self.assertIn("TOP nicht zugeordnet", html)


if __name__ == "__main__":
    unittest.main()
