from __future__ import annotations

import copy
import unittest
from types import SimpleNamespace
from unittest import mock

import _support  # noqa: F401
import render_dip_pulse_html as html
import validate_dip_protocol as dip


def source_top() -> dict:
    return {
        "top_id": "TOP 1",
        "heading": "Beratung",
        "speeches": [
            {
                "rede_id": f"rede-{index}",
                "source_page": {"page": 10 + index},
                "speaker": {"display_name": f"Person {index}", "fraktion": "SPD"},
                "char_count": 1000 - index,
                "text": f"Quellentext {index}",
            }
            for index in range(1, 5)
        ],
    }


def valid_summary(top: dict) -> dict:
    chunks = dip.summary_source_chunks(top)[:3]
    return {
        "provider": "test",
        "model": "test",
        "summary_schema_version": dip.SUMMARY_SCHEMA_VERSION,
        "prompt_version": dip.SUMMARY_PROMPT_VERSION,
        "source_fingerprint": dip.summary_source_fingerprint(top),
        "text": "Eine belegte Zusammenfassung.",
        "source_chunk_ids": [chunk["id"] for chunk in chunks],
        "source_chunks": chunks,
    }


class SummaryValidationTests(unittest.TestCase):
    @staticmethod
    def report() -> dict:
        top = source_top()
        return {
            "protocol": {"pdf_url": "https://www.bundestag.de/test.pdf"},
            "agenda_items": [
                {
                    "index": 1,
                    "top_id": top["top_id"],
                    "heading": top["heading"],
                    "xml_speakers": top["speeches"],
                }
            ],
        }

    @staticmethod
    def args(mode: str, *, api_key: str | None = None) -> SimpleNamespace:
        return SimpleNamespace(
            summary_mode=mode,
            summary_provider="anthropic",
            anthropic_api_key=api_key,
            gemini_api_key=None,
            summary_model="model-a,model-b",
            summary_max_calls=3,
            summary_timeout=2,
        )

    def test_fingerprint_changes_when_source_text_changes(self) -> None:
        top = source_top()
        changed = copy.deepcopy(top)
        changed["speeches"][0]["text"] += " geändert"
        self.assertNotEqual(
            dip.summary_source_fingerprint(top),
            dip.summary_source_fingerprint(changed),
        )

    def test_validator_accepts_distinct_resolvable_targets(self) -> None:
        top = source_top()
        self.assertEqual(dip.validate_usable_summary(valid_summary(top), top), (True, None))

    def test_validator_rejects_duplicate_and_missing_targets(self) -> None:
        top = source_top()
        duplicate = valid_summary(top)
        duplicate["source_chunks"][1] = copy.deepcopy(duplicate["source_chunks"][0])
        self.assertEqual(dip.validate_usable_summary(duplicate, top)[1], "duplicate_citation")

        missing = valid_summary(top)
        missing["source_chunks"][0]["rede_id"] = "unknown"
        missing["source_chunks"][0]["source_page"] = None
        self.assertEqual(dip.validate_usable_summary(missing, top)[1], "missing_target")

    def test_provider_attempt_budget_is_hard(self) -> None:
        with self.assertRaisesRegex(dip.SummaryError, "summary_budget_exhausted"):
            dip.generate_top_summary(
                source_top(),
                "anthropic",
                "test-key",
                ["model-a"],
                budget={"used": 0, "limit": 0},
            )

    def test_generated_summary_carries_cache_binding_metadata(self) -> None:
        top = source_top()
        response = '{"sentences":["Kurz und neutral."],"source_chunk_ids":["S1","S2","S3"]}'
        with mock.patch.object(dip, "request_summary_text", return_value=response):
            summary = dip.generate_top_summary(
                top,
                "anthropic",
                "test-key",
                ["model-a"],
                budget={"used": 0, "limit": 1},
            )
        self.assertEqual(summary["source_fingerprint"], dip.summary_source_fingerprint(top))
        self.assertEqual(summary["prompt_version"], dip.SUMMARY_PROMPT_VERSION)

    def test_off_mode_never_calls_a_provider(self) -> None:
        report = self.report()
        with mock.patch.object(dip, "generate_top_summary") as generate:
            dip.enrich_with_llm_summaries(report, self.args("off"))
        generate.assert_not_called()
        self.assertEqual(report["acquisition"]["summaries"]["acquisition_state"], "not_requested")

    def test_missing_credentials_fail_open_in_auto_and_fail_required(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            auto = self.report()
            dip.enrich_with_llm_summaries(auto, self.args("auto"))
            self.assertEqual(auto["acquisition"]["summaries"]["acquisition_state"], "failed")
            with self.assertRaisesRegex(dip.DipError, "Provide an anthropic API key"):
                dip.enrich_with_llm_summaries(self.report(), self.args("required"))

    def test_provider_timeout_is_recorded_without_publishing_a_summary(self) -> None:
        report = self.report()
        with mock.patch.object(dip, "generate_top_summary", side_effect=dip.SummaryError("provider timeout")):
            dip.enrich_with_llm_summaries(report, self.args("auto", api_key="test-key"))
        self.assertNotIn("llm_summary", report["agenda_items"][0])
        self.assertEqual(report["acquisition"]["summaries"]["failure_reasons"], ["provider_timeout"])

    def test_fallback_model_consumes_the_shared_request_budget(self) -> None:
        budget = {"used": 0, "limit": 2}
        response = '{"sentences":["Kurz und neutral."],"source_chunk_ids":["S1","S2","S3"]}'
        with mock.patch.object(
            dip,
            "request_summary_text",
            side_effect=[dip.SummaryError("provider timeout"), response],
        ):
            summary = dip.generate_top_summary(
                source_top(),
                "anthropic",
                "test-key",
                ["model-a", "model-b"],
                budget=budget,
            )
        self.assertEqual(budget["used"], 2)
        self.assertEqual(summary["model"], "model-b")


class SummaryRenderingTests(unittest.TestCase):
    def test_summary_is_expanded_labelled_and_globally_controlled(self) -> None:
        top = source_top()
        item = {
            "index": 1,
            "top_id": top["top_id"],
            "heading": top["heading"],
            "xml_speakers": top["speeches"],
            "llm_summary": valid_summary(top),
        }
        markup = html.render_llm_summary(
            item,
            {"speakers": top["speeches"]},
            protocol={"dokumentnummer": "21/84", "pdf_url": "https://www.bundestag.de/test.pdf"},
        )
        self.assertIn("KI-generiert · nicht redaktionell geprüft", markup)
        self.assertIn('aria-expanded="true"', markup)
        self.assertIn("data-ai-summary-body", markup)
        self.assertNotIn(" hidden", markup)
        self.assertIn("Alle KI-Zusammenfassungen einklappen", markup)

    def test_invalid_storage_fails_open_to_expanded_content(self) -> None:
        runtime = html.ai_summary_runtime_script()
        self.assertIn('let state = "expanded"', runtime)
        self.assertIn("try {", runtime)
        self.assertIn("catch (_) {}", runtime)
        self.assertLess(runtime.index("addEventListener"), runtime.index("apply(state, false)"))

    def test_missing_summary_emits_no_empty_ai_card(self) -> None:
        self.assertEqual(html.render_llm_summary({}, {"speakers": []}), "")


if __name__ == "__main__":
    unittest.main()
