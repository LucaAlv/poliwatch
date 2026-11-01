from __future__ import annotations

import http.client
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import derive
import speech_kinds
import validate_dip_protocol as dip
from _support import FIXTURES


class PageFetchRetryTests(unittest.TestCase):
    def test_a_reset_while_fetching_a_page_is_retried_then_succeeds(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return "<html>ok</html>".encode("utf-8")

        calls = [ConnectionResetError(54, "reset"), Response()]

        def urlopen(*args, **kwargs):
            outcome = calls.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

        with mock.patch.object(dip.urllib.request, "urlopen", side_effect=urlopen), mock.patch.object(
            dip.time, "sleep"
        ), mock.patch("sys.stderr"):
            self.assertEqual(dip.fetch_html("https://example.test/x"), "<html>ok</html>")
        self.assertEqual(calls, [])

    def test_a_persistent_failure_is_a_dip_error_after_bounded_retries(self) -> None:
        opener = mock.Mock(side_effect=ConnectionResetError(54, "reset"))
        with mock.patch.object(dip.urllib.request, "urlopen", opener), mock.patch.object(
            dip.time, "sleep"
        ), mock.patch("sys.stderr"):
            with self.assertRaises(dip.DipError):
                dip.fetch_text("https://example.test/x.xml")
        self.assertEqual(opener.call_count, dip.PAGE_FETCH_RETRIES + 1)

    def test_a_permanent_http_error_is_not_retried_but_a_busy_server_is(self) -> None:
        import urllib.error

        def http_error(code: int) -> urllib.error.HTTPError:
            return urllib.error.HTTPError("https://example.test/x", code, "err", {}, None)  # type: ignore[arg-type]

        for code, calls in ((404, 1), (403, 1), (503, dip.PAGE_FETCH_RETRIES + 1)):
            with self.subTest(code=code):
                opener = mock.Mock(side_effect=lambda *a, **k: (_ for _ in ()).throw(http_error(code)))
                with mock.patch.object(dip.urllib.request, "urlopen", opener), mock.patch.object(dip.time, "sleep"):
                    with self.assertRaises(dip.DipError):
                        dip.fetch_html("https://example.test/x")
                self.assertEqual(opener.call_count, calls)

    def test_undecodable_bytes_are_not_retried(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b"\xff\xfe"

        opener = mock.Mock(return_value=Response())
        with mock.patch.object(dip.urllib.request, "urlopen", opener):
            with self.assertRaises(dip.DipError):
                dip.fetch_html("https://example.test/x")
        self.assertEqual(opener.call_count, 1)


class ApiClientRetryTests(unittest.TestCase):
    def client(self) -> "dip.ApiClient":
        return dip.ApiClient(api_key="k", retries=2, retry_delay_seconds=0)

    def test_a_connection_reset_while_reading_is_retried(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b'{"documents": []}'

        calls = [ConnectionResetError(54, "reset"), http.client.IncompleteRead(b""), Response()]

        def urlopen(*args, **kwargs):
            outcome = calls.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

        with mock.patch.object(dip.urllib.request, "urlopen", side_effect=urlopen), mock.patch.object(
            dip.time, "sleep"
        ), mock.patch("sys.stderr"):
            self.assertEqual(self.client().get_json("/x"), {"documents": []})
        self.assertEqual(calls, [])

    # Value: protects=a 200 response that is not JSON (an HTML bot-challenge page, a cut-off body) becomes a DipError the callers handle; fails_when=json.loads errors escape get_json as a ValueError, so a build dies with a traceback and loses a long fetch; why_new=only HTTP and connection failures were covered; seam=none
    def test_a_body_that_is_not_json_becomes_a_dip_error(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b"<!doctype html><title>Verification</title>"

        with mock.patch.object(dip.urllib.request, "urlopen", return_value=Response()):
            with self.assertRaisesRegex(dip.DipError, "unreadable body"):
                self.client().get_json("/x")

    def test_a_persistent_reset_becomes_a_dip_error_not_a_crash(self) -> None:
        with mock.patch.object(
            dip.urllib.request, "urlopen", side_effect=ConnectionResetError(54, "reset")
        ), mock.patch.object(dip.time, "sleep"), mock.patch("sys.stderr"):
            with self.assertRaises(dip.DipError):
                self.client().get_json("/x")


class ValidateDipProtocolHelperTests(unittest.TestCase):
    def test_build_report_fetches_protocol_when_none_is_preloaded(self) -> None:
        protocol = {
            "id": "5805",
            "dokumentnummer": "21/87",
            "fundstelle": {"xml_url": "https://example.test/protocol.xml"},
        }
        args = Namespace(
            api_key="test-key",
            sleep=0,
            protocol_id="5805",
            document_number=None,
            person_limit=0,
            vote_scan_pages=0,
            roll_call_list_id=None,
            limit_tops=None,
        )
        parsed_xml = {"xml_protocol": {}, "agenda_items": []}
        enrichment = {
            "agenda_items": [],
            "api_totals": {},
            "warnings": [],
            "sampled_people": [],
            "api_records": {},
            "sitting_votes": [],
        }

        with (
            mock.patch.object(dip, "find_protocol", return_value=protocol) as find_protocol,
            mock.patch.object(dip, "fetch_text", return_value="<xml />"),
            mock.patch.object(dip, "parse_protocol_xml", return_value=parsed_xml),
            mock.patch.object(dip, "enrich_with_api", return_value=enrichment),
            mock.patch.object(dip, "enrich_with_llm_summaries"),
        ):
            report = dip.build_report(args)

        find_protocol.assert_called_once()
        _, protocol_id, document_number = find_protocol.call_args.args
        self.assertEqual(protocol_id, "5805")
        self.assertIsNone(document_number)
        self.assertEqual(report["protocol"]["id"], "5805")

    def test_build_report_uses_preloaded_protocol_without_refetching_it(self) -> None:
        protocol = {
            "id": "5805",
            "dokumentnummer": "21/87",
            "fundstelle": {"xml_url": "https://example.test/protocol.xml"},
        }
        args = Namespace(
            api_key="test-key",
            sleep=0,
            protocol_id="5805",
            document_number=None,
            person_limit=0,
            vote_scan_pages=0,
            roll_call_list_id=None,
            limit_tops=None,
        )
        parsed_xml = {"xml_protocol": {}, "agenda_items": []}
        enrichment = {
            "agenda_items": [],
            "api_totals": {},
            "warnings": [],
            "sampled_people": [],
            "api_records": {},
            "sitting_votes": [],
        }

        with (
            mock.patch.object(dip, "find_protocol") as find_protocol,
            mock.patch.object(dip, "fetch_text", return_value="<xml />"),
            mock.patch.object(dip, "parse_protocol_xml", return_value=parsed_xml),
            mock.patch.object(dip, "enrich_with_api", return_value=enrichment),
            mock.patch.object(dip, "enrich_with_llm_summaries"),
        ):
            report = dip.build_report(args, protocol=protocol)

        find_protocol.assert_not_called()
        self.assertEqual(report["protocol"]["id"], "5805")

    def test_build_report_hands_the_fetched_xml_to_the_caller_for_a_rule_change_without_a_refetch(self) -> None:
        protocol = {
            "id": "5805",
            "dokumentnummer": "21/87",
            "fundstelle": {"xml_url": "https://example.test/protocol.xml"},
        }
        sink: dict[str, str] = {}
        args = Namespace(
            api_key="test-key",
            sleep=0,
            protocol_id="5805",
            document_number=None,
            person_limit=0,
            vote_scan_pages=0,
            roll_call_list_id=None,
            limit_tops=None,
            xml_sink=sink,
        )
        enrichment = {"agenda_items": [], "api_totals": {}, "warnings": [], "sampled_people": [], "api_records": {}, "sitting_votes": []}
        with (
            mock.patch.object(dip, "fetch_text", return_value="<dbtplenarprotokoll>ä</dbtplenarprotokoll>"),
            mock.patch.object(dip, "enrich_with_api", return_value=enrichment),
            mock.patch.object(dip, "enrich_with_llm_summaries"),
            mock.patch("sys.stderr"),
        ):
            report = dip.build_report(args, protocol=protocol)
        # build_report caches nothing: the caller keeps the XML only once it accepts the report.
        self.assertEqual(sink, {"text": "<dbtplenarprotokoll>ä</dbtplenarprotokoll>"})
        # A report an online update makes carries the current rule marker, so the A1 warning stays silent.
        self.assertEqual(report["validation_summary"]["speech_kinds_version"], speech_kinds.VERSION)

    def test_build_report_keeps_the_votes_no_top_claimed_where_derive_reads_them(self) -> None:
        protocol = {"id": "5805", "dokumentnummer": "21/87", "fundstelle": {"xml_url": "https://example.test/protocol.xml"}}
        args = Namespace(api_key="test-key", sleep=0, person_limit=0, vote_scan_pages=0, roll_call_list_id=None, limit_tops=None)
        sitting_vote = {"id": "996", "title": "Sitting-level vote", "date": "2026-07-01"}
        enrichment = {"agenda_items": [], "api_totals": {}, "warnings": [], "sampled_people": [],
                      "api_records": {"sitting_votes": [sitting_vote]}, "sitting_votes": [sitting_vote]}
        with (
            mock.patch.object(dip, "fetch_text", return_value="<xml />"),
            mock.patch.object(dip, "parse_protocol_xml", return_value={"xml_protocol": {}, "agenda_items": []}),
            mock.patch.object(dip, "enrich_with_api", return_value=enrichment),
            mock.patch.object(dip, "enrich_with_llm_summaries"),
        ):
            report = dip.build_report(args, protocol=protocol)
        self.assertEqual([vote["id"] for _, vote in derive.iter_report_votes(report)], ["996"])

    def test_vote_helpers(self) -> None:
        counts = dip.vote_counts_from_csv("10, 5, 2, 1")
        self.assertEqual(counts, {"yes": 10, "no": 5, "abstain": 2, "absent": 1})
        self.assertEqual(dip.vote_total(counts), 18)

    def test_text_date_and_faction_helpers(self) -> None:
        self.assertEqual(dip.normalize_faction("B90/GRÜNE"), "BÜNDNIS 90/DIE GRÜNEN")
        self.assertEqual(dip.normalize_faction("LINKE"), "Die Linke")
        self.assertEqual(dip.normalize_faction("Fraktionslose"), "fraktionslos")
        self.assertEqual(dip.iso_date("15.05.2024"), "2024-05-15")
        self.assertEqual(dip.iso_date("2024-05-15"), "2024-05-15")
        self.assertIsNone(dip.iso_date("15/05/2024"))
        self.assertEqual(dip.clamp_text("  eins   zwei drei  ", 9), "eins zwe" + "\u2026")

    def test_title_and_position_matching_helpers(self) -> None:
        self.assertEqual(dip.norm_title("Test: Gesetz 20/123!"), "test gesetz 20 123")
        self.assertTrue(dip.title_matches("TOP 1 Beratung Testgesetz", "Beratung Testgesetz"))
        self.assertTrue(
            dip.title_matches(
                "Gesetz zur Modernisierung der digitalen Verwaltung und Infrastruktur",
                "Modernisierung digitale Verwaltung Infrastruktur",
            )
        )
        self.assertFalse(dip.title_matches("Haushalt", "Verkehr Infrastruktur"))

        top = {"page_range": {"start": {"page": 5}, "end": {"page": 7}}}
        self.assertTrue(dip.overlaps(top, {"fundstelle": {"anfangsseite": "7", "endseite": "8"}}))
        self.assertFalse(dip.overlaps(top, {"fundstelle": {"anfangsseite": "8", "endseite": "9"}}))
        self.assertTrue(dip.activity_in_top({"fundstelle": {"seite": "6"}}, top))
        self.assertFalse(dip.activity_in_top({"fundstelle": {"seite": "8"}}, top))


class CompactDrucksachePositionTests(unittest.TestCase):
    # Value: protects=a DIP Drucksache position keeps its issuer (herausgeber) next to the number in the cached report; fails_when=the field is dropped, so persist reads every Bundesrat paper as a Bundestag one; why_new=persist tests inject herausgeber into reports by hand; seam=none; no_claim=DIP field names
    def test_the_issuer_travels_with_the_number_and_url(self) -> None:
        position = {
            "id": "p1", "vorgang_id": "v1", "vorgangsposition": "1. Beratung", "titel": "T",
            "fundstelle": {"dokumentnummer": "40/23", "herausgeber": "BR", "drucksachetyp": "Gesetzentwurf",
                           "datum": "2023-02-03", "pdf_url": "https://dserver.bundestag.de/brd/2023/0040-23.pdf"},
        }
        compact = dip.compact_drucksache_position(position)
        self.assertEqual(
            {key: compact[key] for key in ("vorgang_id", "vorgangsposition_id", "dokumentnummer", "herausgeber", "drucksachetyp", "datum", "url")},
            {"vorgang_id": "v1", "vorgangsposition_id": "p1", "dokumentnummer": "40/23", "herausgeber": "BR",
             "drucksachetyp": "Gesetzentwurf", "datum": "2023-02-03", "url": "https://dserver.bundestag.de/brd/2023/0040-23.pdf"},
        )
        self.assertIsNone(dip.compact_drucksache_position({"id": "p2"})["herausgeber"])


class ValidateDipProtocolParserTests(unittest.TestCase):
    def test_parse_protocol_xml_extracts_agenda_speeches_and_pages(self) -> None:
        parsed = dip.parse_protocol_xml((FIXTURES / "protocol.xml").read_text(encoding="utf-8"))

        self.assertEqual(parsed["xml_protocol"]["wahlperiode"], "20")
        self.assertEqual(len(parsed["agenda_items"]), 2)

        first = parsed["agenda_items"][0]
        self.assertEqual(first["top_id"], "T1")
        self.assertEqual(first["heading"], "TOP 1 Beratung Testgesetz")
        self.assertEqual(first["page_range"]["start"], {"page": 101, "quadrant": "A"})
        self.assertEqual(first["page_range"]["end"], {"page": 102, "quadrant": "C"})
        self.assertEqual(len(first["speeches"]), 2)
        self.assertEqual(first["speeches"][0]["speaker"]["display_name"], "Dr. Ada Lovelace")
        self.assertEqual(first["speeches"][0]["paragraph_count"], 2)
        self.assertIn("Zweiter Absatz", first["speeches"][0]["text"])

        second = parsed["agenda_items"][1]
        self.assertEqual(second["page_range"]["start"], {"page": 103, "quadrant": "B"})
        self.assertEqual(second["speeches"][0]["speaker"]["last_name"], "Kontrolle")

    def test_extract_drucksachen_ignores_external_urls_that_look_like_numbers(self) -> None:
        # Protocol 20/206 quotes these verbatim in a Fragestunde question; the
        # percent-encoded and dated paths matched the NN/NNNNNN regex and the
        # external hosts later failed the publication allowlist.
        syriahr = "https://www.syriahr.com/%D8%A7%D9%84%D9%85%D9%88/739016/"
        dated = "http://www.jmwiarda.de/2024/12/06/so-soll-der-digitalpakt-2-0-aussehen/"
        top = dip.ET.fromstring(
            "<top>"
            f'<p>vergleiche <a href="{syriahr}">www.syriahr.com/%D9%88/739016/</a> '
            f'und <a href="{dated}">www.jmwiarda.de/2024/12/06/</a></p>'
            '<p>Drucksache <a href="https://dserver.bundestag.de/btd/20/141/2014189.pdf">20/14189</a> '
            "und <a>20/999</a></p>"
            "</top>"
        )

        self.assertEqual(
            dip.extract_drucksachen(top),
            [
                {"dokumentnummer": "20/14189", "url": "https://dserver.bundestag.de/btd/20/141/2014189.pdf"},
                {"dokumentnummer": "20/999", "url": None},
            ],
        )

    def test_a_fractional_majority_in_the_teaser_is_no_document_number(self) -> None:
        html = (FIXTURES / "roll_call_list.html").read_text(encoding="utf-8").replace(
            "20/123 und 20/456.", "20/123 und 20/456 mit der erforderlichen 2/3-Mehrheit (3/4 im Bundesrat)."
        )
        self.assertEqual(dip.parse_roll_call_list_page(html)[0]["document_numbers"], ["20/123", "20/456"])

    def test_parse_roll_call_list_page(self) -> None:
        entries = dip.parse_roll_call_list_page((FIXTURES / "roll_call_list.html").read_text(encoding="utf-8"))

        self.assertEqual(len(entries), 1)
        vote = entries[0]
        self.assertEqual(vote["id"], "12345")
        self.assertEqual(vote["date"], "2024-05-15")
        self.assertEqual(vote["document_numbers"], ["20/123", "20/456"])
        self.assertEqual(vote["total"], {"yes": 10, "no": 5, "abstain": 2, "absent": 1})

    def test_fetch_html_wraps_a_malformed_response_body_as_dip_error(self) -> None:
        # A response that is not valid utf-8 used to crash the build with a raw
        # UnicodeDecodeError; fetch_html's except clause now widened to also
        # catch this and convert it into the same DipError callers expect.
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *exc: object) -> None:
                return None

            def read(self) -> bytes:
                return b"\xff\xfe not valid utf-8"

        with mock.patch.object(dip.urllib.request, "urlopen", return_value=FakeResponse()):
            with self.assertRaises(dip.DipError) as ctx:
                dip.fetch_html("https://example.test/page.html")
        self.assertIn("Failed to fetch HTML", str(ctx.exception))

    def test_fetch_text_wraps_an_http_client_exception_as_dip_error(self) -> None:
        # http.client exceptions (e.g. a truncated chunked response) are not
        # OSError/URLError subclasses; fetch_text's except clause now widened
        # to also catch these rather than letting them propagate raw.
        def fake_urlopen(*args: object, **kwargs: object) -> object:
            raise http.client.IncompleteRead(b"")

        with mock.patch.object(dip.urllib.request, "urlopen", side_effect=fake_urlopen), mock.patch.object(
            dip.time, "sleep"
        ), mock.patch("sys.stderr"):
            with self.assertRaises(dip.DipError) as ctx:
                dip.fetch_text("https://example.test/protocol.xml")
        self.assertIn("Failed to fetch XML", str(ctx.exception))

    def test_parse_member_votes_maps_vote_keys(self) -> None:
        members = dip.parse_member_votes((FIXTURES / "member_votes.html").read_text(encoding="utf-8"))

        self.assertEqual(
            {member["name"]: member["vote"] for member in members},
            {
                "Ada Lovelace": "yes",
                "Bruno Beispiel": "no",
                "Clara Kontrolle": "abstain",
                "Dora Abwesend": "absent",
            },
        )
        self.assertEqual(members[0]["faction"], "SPD")
        self.assertTrue(members[0]["profile_url"].endswith("/abgeordnete/ada-lovelace"))

    # Value: protects=a member card that links back to the Abstimmung (an MP without a biography) gets no profile URL; fails_when=any first <a href> is taken as the profile and later folds distinct MPs into one identity; why_new=77 such rows on the reference cache (2026-10-22); seam=none
    def test_a_link_back_to_the_abstimmung_is_no_profile(self) -> None:
        card = (
            '<div class="col-xs-4 col-sm-3 col-md-2 bt-slide">'
            '<a href="/parlament/plenum/abstimmung/abstimmung?id=853"><h3>Ada Ohnebio</h3></a>'
            '<p class="bt-person-fraktion">SPD</p><p class="bt-person-abstimmung bt-abstimmung-ja">Ja</p></div>'
        )
        self.assertIsNone(dip.parse_member_votes(card)[0]["profile_url"])


if __name__ == "__main__":
    unittest.main()


class PersonCacheTests(unittest.TestCase):
    # Value (D5): protects=a backfill pays one /person request per person, not one per sitting,
    # and never keeps a failed lookup; fails_when=a repeat person is fetched again or a failure
    # is cached; seam=enrich_with_api(person_cache=...); no_claim=live DIP person records.
    def test_a_person_is_fetched_once_per_build_and_a_failure_is_retried(self) -> None:
        requests: list[str] = []

        class FakeClient:
            def list_all(self, path, params):
                if path == "/aktivitaet":
                    return [{"id": "a1", "person_id": "p1"}, {"id": "a2", "person_id": "p2"}]
                return []

            def get_json(self, path):
                requests.append(path)
                if path == "/person/p2" and requests.count(path) == 1:
                    raise dip.DipError("DIP answered 503")
                return {"id": path.rsplit("/", 1)[1], "nachname": "N", "vorname": "V"}

        parsed = dip.parse_protocol_xml((FIXTURES / "protocol.xml").read_text(encoding="utf-8"))
        cache: dict = {}
        with mock.patch("sys.stderr"):
            first = dip.enrich_with_api(FakeClient(), {"id": "x", "dokumentnummer": "21/43", "datum": "2025-12-10"},
                                        parsed, person_limit=0, vote_scan_pages=0, person_cache=cache)
            second = dip.enrich_with_api(FakeClient(), {"id": "y", "dokumentnummer": "21/43", "datum": "2025-12-10"},
                                         parsed, person_limit=0, vote_scan_pages=0, person_cache=cache)
        self.assertEqual(requests, ["/person/p1", "/person/p2", "/person/p2"])
        self.assertEqual([p["id"] for p in first["sampled_people"]], ["p1"])
        self.assertEqual(sorted(p["id"] for p in second["sampled_people"]), ["p1", "p2"])

    # Value (A3 pilot, docs/plans/a3-pilot.md): protects=a DIP /person stall costs one sitting
    # three failed lookups, not three timed-out attempts per remaining person (51 minutes for
    # 18/154 in the pilot); fails_when=lookups continue after consecutive failures, or the
    # skipped persons are not counted as failures; seam=enrich_with_api.
    def test_person_lookups_stop_for_the_sitting_after_consecutive_failures(self) -> None:
        requests: list[str] = []

        class FakeClient:
            def list_all(self, path, params):
                if path == "/aktivitaet":
                    return [{"id": f"a{n}", "person_id": f"p{n}"} for n in range(6)]
                return []

            def get_json(self, path):
                requests.append(path)
                if path == "/person/p0":
                    return {"id": "p0"}
                raise dip.DipError("timed out")

        parsed = dip.parse_protocol_xml((FIXTURES / "protocol.xml").read_text(encoding="utf-8"))
        with mock.patch("sys.stderr"):
            result = dip.enrich_with_api(FakeClient(), {"id": "x", "dokumentnummer": "21/43", "datum": "2025-12-10"},
                                         parsed, person_limit=0, vote_scan_pages=0, person_cache={})
        self.assertEqual(requests, ["/person/p0", "/person/p1", "/person/p2", "/person/p3"])
        self.assertEqual(result["api_totals"]["person_record_fetch_error_count"], 5)
