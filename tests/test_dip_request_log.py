"""DIP_REQUEST_LOG: one line per outbound request attempt, so the moment a source
stops answering is known exactly (A3 pilot, Finding 2). The API key never
appears in it."""

from __future__ import annotations

import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import validate_dip_protocol as dip

KEY = "test-key-5f3a9c"


class Response:
    status = 200

    def __init__(self, body: str) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.body.encode("utf-8")


class DipRequestLogTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.log = Path(tmp.name) / "requests.log"

    def get_json(self, outcomes: list, *, log: bool = True) -> str:
        def urlopen(*args, **kwargs):
            outcome = outcomes.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome

        env = {"DIP_REQUEST_LOG": str(self.log)} if log else {}
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, env), mock.patch.object(dip.urllib.request, "urlopen", side_effect=urlopen), \
                mock.patch.object(dip.time, "sleep"), mock.patch("sys.stderr", stderr):
            if not log:
                os.environ.pop("DIP_REQUEST_LOG", None)
            dip.ApiClient(api_key=KEY, retries=1).get_json("/plenarprotokoll", {"f.wahlperiode": 18})
        return stderr.getvalue()

    # Value: protects=every DIP attempt is logged with its UTC time, path, parameters,
    # outcome and latency; fails_when=a retry or a failed attempt is missing, so where DIP
    # stopped stays unknown; seam=ApiClient.get_json with urlopen stubbed.
    def test_each_attempt_is_one_line_with_time_target_outcome_and_latency(self) -> None:
        self.get_json([TimeoutError("timed out"), Response(json.dumps({"documents": []}))])
        lines = self.log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        for attempt, line in enumerate(lines, start=1):
            fields = line.split("\t")
            self.assertRegex(fields[0], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$")
            self.assertEqual(fields[1], "dip")
            self.assertEqual(fields[2], "/plenarprotokoll?f.wahlperiode=18&format=json")
            self.assertEqual(fields[3], f"attempt {attempt}")
            self.assertRegex(fields[5], r"^\d+\.\d{2}s$")
        self.assertEqual(lines[0].split("\t")[4], "TimeoutError: timed out")
        self.assertEqual(lines[1].split("\t")[4], "200")

    # Value: protects=the API key never reaches the log or stderr; fails_when=the logged
    # target is built from the request URL, which carries the key as a query parameter;
    # seam=ApiClient.get_json with urlopen stubbed.
    def test_the_api_key_never_appears(self) -> None:
        stderr = self.get_json([TimeoutError("timed out"), Response("{}")])
        self.assertNotIn(KEY, self.log.read_text(encoding="utf-8"))
        self.assertNotIn("apikey", self.log.read_text(encoding="utf-8"))
        self.assertNotIn(KEY, stderr)

    # Value: protects=a log that cannot be written never changes a request; fails_when=the
    # write's OSError replaces the answer, get_json reads it as a network error and retries,
    # spending DIP budget on a fake outage; seam=ApiClient.get_json with urlopen stubbed.
    def test_an_unwritable_log_leaves_the_answer_alone(self) -> None:
        self.log = self.log.parent / "missing" / "requests.log"
        opener = mock.Mock(return_value=Response(json.dumps({"ok": 1})))
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"DIP_REQUEST_LOG": str(self.log)}), mock.patch.object(
            dip.urllib.request, "urlopen", opener
        ), mock.patch.object(dip.time, "sleep"), mock.patch("sys.stderr", stderr):
            self.assertEqual(dip.ApiClient(api_key=KEY, retries=1).get_json("/x"), {"ok": 1})
        self.assertEqual(opener.call_count, 1)
        self.assertIn("DIP_REQUEST_LOG", stderr.getvalue())

    def test_without_the_variable_nothing_is_written(self) -> None:
        self.get_json([Response("{}")], log=False)
        self.assertFalse(self.log.exists())

    # Value: protects=dserver and bundestag.de page fetches share the log, so a DIP stop can be
    # placed against the XML downloads around it; seam=fetch_text with urlopen stubbed.
    def test_a_page_fetch_is_logged_with_its_host(self) -> None:
        with mock.patch.dict(os.environ, {"DIP_REQUEST_LOG": str(self.log)}), mock.patch.object(
            dip.urllib.request, "urlopen", return_value=Response("<x/>")
        ):
            dip.fetch_text("https://dserver.bundestag.de/btp/19/19001.xml")
        fields = self.log.read_text(encoding="utf-8").splitlines()[0].split("\t")
        self.assertEqual(fields[1:5], ["dserver.bundestag.de", "/btp/19/19001.xml", "attempt 1", "200"])


if __name__ == "__main__":
    unittest.main()
