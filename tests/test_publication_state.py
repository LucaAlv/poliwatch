from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401
import publication_state as publication
from features.votes import render_vote_summary


class PublicationStateContractTests(unittest.TestCase):
    def test_state_mapping_distinguishes_empty_skipped_partial_and_failed(self) -> None:
        self.assertEqual(
            publication.derive_presentation_state("votes", "complete", records=0),
            publication.PresentationState.DOMAIN_EMPTY,
        )
        self.assertEqual(
            publication.derive_presentation_state("votes", "not_requested", records=0),
            publication.PresentationState.UNAVAILABLE,
        )
        self.assertEqual(
            publication.derive_presentation_state("votes", "partial", records=2),
            publication.PresentationState.PARTIAL,
        )
        self.assertEqual(
            publication.derive_presentation_state("votes", "failed", records=0),
            publication.PresentationState.UNAVAILABLE,
        )

    def test_complete_empty_roster_is_invalid(self) -> None:
        with self.assertRaisesRegex(publication.PublicationStateError, "complete roster"):
            publication.DomainFacts(
                domain="roster",
                acquisition_state="complete",
                source="bundestag-dip",
                records=0,
            )

    def test_timestamps_attempts_and_summary_counters_are_validated(self) -> None:
        with self.assertRaisesRegex(publication.PublicationStateError, "attempted_at"):
            publication.DomainFacts(
                domain="votes",
                acquisition_state="complete",
                source="bundestag-roll-call",
                records=0,
                attempted=True,
            )
        with self.assertRaisesRegex(publication.PublicationStateError, "outcomes"):
            publication.DomainFacts(
                domain="summaries",
                acquisition_state="partial",
                source="llm-with-bundestag-citations",
                records=1,
                rejected=1,
                failure_reasons=("invalid_citations",),
                counters={"eligible": 3, "generated": 1, "omitted": 0, "failed": 1, "fallbacks": 0},
            )

    def test_manifest_round_trip_preserves_schema_v2(self) -> None:
        domains = [
            publication.DomainFacts("catalog", "complete", "bundestag-dip", 1),
            publication.DomainFacts(
                "dossiers",
                "complete",
                "bundestag-xml",
                1,
                items=(
                    publication.DossierItem(
                        "21/84", "ready", "data/plenarprotokoll-21-84.json", "protocols/plenarprotokoll-21-84.html"
                    ),
                ),
            ),
            publication.DomainFacts("votes", "complete", "bundestag-roll-call", 0),
            publication.DomainFacts("profiles", "complete", "abgeordnetenwatch", 0),
            publication.DomainFacts("roster", "complete", "bundestag-dip", 630),
            publication.DomainFacts("bills", "complete", "derived-dip", 0),
            publication.DomainFacts(
                "summaries",
                "not_requested",
                "llm-with-bundestag-citations",
                0,
                counters={"eligible": 2, "generated": 0, "omitted": 2, "failed": 0, "fallbacks": 0},
            ),
        ]
        payload = publication.manifest(
            generated_at="2026-09-17T10:00:00Z",
            version="0.3.0",
            development_output=False,
            domains=domains,
        )
        self.assertEqual(publication.validate_manifest(payload), payload)
        self.assertEqual(payload["domains"]["votes"]["presentation_state"], "domain_empty")

    def test_output_paths_reject_traversal_and_platform_separators(self) -> None:
        for value in ("../secret", "%2e%2e/secret", "data\\secret.json", "/absolute"):
            with self.subTest(value=value):
                with self.assertRaises(publication.PublicationStateError):
                    publication.validate_relative_output_path(value)

    def test_source_urls_require_https_allowlisted_hosts_and_no_credentials(self) -> None:
        self.assertEqual(
            publication.validate_external_url("https://www.bundestag.de/parlament", "bundestag-roll-call"),
            "https://www.bundestag.de/parlament",
        )
        for url in (
            "http://www.bundestag.de/parlament",
            "https://user:secret@www.bundestag.de/parlament",
            "https://example.test/parlament",
        ):
            with self.subTest(url=url):
                with self.assertRaises(publication.PublicationStateError):
                    publication.validate_external_url(url, "bundestag-roll-call")

    def test_public_output_validator_scans_presentation_surfaces_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "index.html").write_text("<p>public</p>", encoding="utf-8")
            (root / "data" / "raw-report.json").write_text('{"build_command":"/Users/example"}', encoding="utf-8")
            self.assertEqual(publication.validate_public_output(root), [])
            (root / "index.html").write_text('<section class="dev-only">/Users/example</section>', encoding="utf-8")
            findings = publication.validate_public_output(root)
            self.assertTrue(any("developer-class" in finding for finding in findings))
            self.assertTrue(any("local-path" in finding for finding in findings))
            (root / "index.html").write_text('<section data-feature="votes">public</section>', encoding="utf-8")
            self.assertTrue(
                any("retired-feature-state" in finding for finding in publication.validate_public_output(root))
            )


class VoteStateCopyTests(unittest.TestCase):
    def test_empty_vote_copy_reflects_pipeline_truth(self) -> None:
        expected = {
            "complete": "Zu diesem TOP ist keine namentliche Abstimmung verzeichnet.",
            "not_requested": "Abstimmungsdaten wurden für diese Veröffentlichung nicht abgerufen.",
            "partial": "Abstimmungsdaten sind unvollständig.",
            "failed": "Abstimmungsdaten konnten nicht abgerufen werden.",
        }
        for state, copy in expected.items():
            with self.subTest(state=state):
                markup = render_vote_summary({}, {"acquisition_state": state})
                self.assertIn(copy, markup)


if __name__ == "__main__":
    unittest.main()
