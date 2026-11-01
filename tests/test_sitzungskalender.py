"""The Sitzungskalender cache and the "Nächste Sitzungswoche" line of puls.html.

The fixtures in tests/fixtures/sitzungskalender/ are SYNTHETIC: hand-written from
the planning notes' description of the Bundestag's files (one all-day VEVENT per
week, exclusive DTEND, CRLF/folding/BOM tolerated). The real format is unverified,
and no test here touches the network.
"""

from __future__ import annotations

import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import ExitStack
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import _support  # noqa: F401
import build_demo_site as demo
import build_dip_pulse_site
import sitzungskalender as cal
import test_build_dip_pulse_site as page_tests
import validate_dip_protocol as dip

FIXTURES = _support.FIXTURES / "sitzungskalender"
ICS_2026_URL = "https://www.bundestag.de/resource/blob/9000001/parlamentstermine_2026.ics"
ICS_2027_URL = "https://www.bundestag.de/resource/blob/9000002/parlamentstermine_2026_ics-1-.ics"
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def ics_text(name: str) -> str:
    # Bytes, not read_text: universal newlines would turn the fixture's CRLF into LF.
    return (FIXTURES / name).read_bytes().decode("utf-8")


def event(start: str, end: str, summary: str = "Sitzungswoche Deutscher Bundestag", start_name: str = "DTSTART;VALUE=DATE") -> str:
    return (
        f"BEGIN:VEVENT\r\n{start_name}:{start}\r\nDTEND;VALUE=DATE:{end}\r\nSUMMARY:{summary}\r\nEND:VEVENT\r\n"
    )


def calendar(*events: str) -> str:
    return "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + "".join(events) + "END:VCALENDAR\r\n"


class FakeSource:
    """Records every fetch; serves the synthetic index and .ics files."""

    def __init__(self, pages: dict[str, str] | None = None, *, fail: Exception | None = None) -> None:
        self.pages = pages if pages is not None else {
            cal.INDEX_URL: ics_text("index.html"),
            ICS_2026_URL: ics_text("parlamentstermine_2026.ics"),
            ICS_2027_URL: ics_text("parlamentstermine_2026_ics-1-.ics"),
        }
        self.fail = fail
        self.calls: list[str] = []

    def fetch(self, url: str) -> str:
        self.calls.append(url)
        if self.fail:
            raise self.fail
        return self.pages[url]


def refresh(output_dir: Path, source: FakeSource, *, now: datetime = NOW) -> str:
    with mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
        cal.refresh_if_due(output_dir, now=now, fetch_html=source.fetch, fetch_text=source.fetch)
    return stderr.getvalue()


def synthetic_cache() -> dict:
    """The cache a first refresh from the synthetic fixtures writes."""
    with tempfile.TemporaryDirectory() as tmp:
        refresh(Path(tmp), FakeSource())
        return json.loads((Path(tmp) / "data" / cal.CACHE_NAME).read_text(encoding="utf-8"))


class ParseIcsTests(unittest.TestCase):
    # Value: protects=the parser reads the Bundestag calendar's assumed shape (CRLF, a BOM, a folded SUMMARY line) into inclusive Monday-to-Friday weeks; fails_when=a BOM, CRLF or folded line breaks a VEVENT, or DTEND stays exclusive; why_new=the parser did not exist and the real bytes were seen only through a summary; seam=none; no_claim=the real Bundestag file (unverified)
    def test_synthetic_files_with_crlf_bom_and_folding(self) -> None:
        text = ics_text("parlamentstermine_2026.ics")
        self.assertTrue(text.startswith("﻿") and "\r\n" in text and "Deutscher\r\n  Bundestag" in text)
        weeks = cal.parse_ics(text)
        self.assertEqual(len(weeks), 20)
        self.assertIn((date(2026, 1, 26), date(2026, 1, 30)), weeks)  # the folded SUMMARY
        self.assertIn((date(2026, 11, 2), date(2026, 11, 6)), weeks)  # DTEND 20261107 is exclusive
        lf = cal.parse_ics(ics_text("parlamentstermine_2026_ics-1-.ics"))
        self.assertEqual(len(lf), 10)
        self.assertEqual({start.year for start, _ in lf}, {2027})

    # Value: protects=only Sitzungswoche events count, and a malformed or impossible week is refused loudly; fails_when=another event type becomes a week, or a datetime DTSTART, a weekend start, a reversed range, a two-ISO-week span or a non-calendar file passes; why_new=a wrong week would put a false date on the page; seam=none; no_claim=the real file
    def test_filtering_and_validation(self) -> None:
        other = event("20260105", "20260106", "Tag der offenen Tür")
        self.assertEqual(cal.parse_ics(calendar(other, event("20260112", "20260117"))), [(date(2026, 1, 12), date(2026, 1, 16))])
        self.assertEqual(cal.parse_ics(calendar(event("20260113", "20260117"))), [(date(2026, 1, 13), date(2026, 1, 16))])  # Tue-Fri
        for bad in (
            event("20260112T000000", "20260117"),
            event("2026-01-12", "20260117"),
            event("20260110", "20260112"),  # a Saturday
            event("20260117", "20260112"),  # ends before it starts
            event("20260112", "00010101"),  # ends on date.min: no OverflowError past refresh_if_due
            event("20260112", "20260112"),
            event("20260112", "20260124"),  # two ISO weeks
        ):
            with self.subTest(bad=bad), self.assertRaises(cal.CalendarParseError):
                cal.parse_ics(calendar(bad))
        with self.assertRaises(cal.CalendarParseError):
            cal.parse_ics("<html>Wartungsarbeiten</html>")
        with self.assertRaises(cal.CalendarParseError):
            cal.parse_ics("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Sitzungswoche\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")

    # Value: protects=the .ics links are found on the index page by their path, made absolute and capped, so the 2027 file named "2026" still yields 2027 weeks; fails_when=the year is taken from the URL, a relative href stays relative, a duplicate or foreign .ics is followed; why_new=blob ids and file names change per year; seam=none; no_claim=the real index layout
    def test_discover_ics_urls_and_the_year_comes_from_the_events(self) -> None:
        urls = cal.discover_ics_urls(ics_text("index.html"))
        self.assertEqual(urls, [ICS_2026_URL, ICS_2027_URL])
        self.assertIn("2026", ICS_2027_URL)
        self.assertEqual({s.year for s, _ in cal.parse_ics(ics_text("parlamentstermine_2026_ics-1-.ics"))}, {2027})
        # One malformed href (an unclosed IPv6 bracket) is skipped, not fatal for the other links.
        broken = '<a href="http://[bad/x.ics">x</a><a href="/resource/blob/7/ok.ics">ok</a>'
        self.assertEqual(cal.discover_ics_urls(broken), ["https://www.bundestag.de/resource/blob/7/ok.ics"])
        many = "".join(f'<a href="/resource/blob/{n}/x{n}.ics">x</a>' for n in range(9))
        self.assertEqual(len(cal.discover_ics_urls(many)), cal.MAX_ICS_FILES)
        self.assertEqual(cal.discover_ics_urls("<p>kein Link</p>"), [])
        # Only https on the Bundestag's own host is followed: a file://, plain-http or off-host blob path is not.
        foreign = (
            '<a href="file:///etc/resource/blob/1/x.ics">f</a>'
            '<a href="http://www.bundestag.de/resource/blob/2/x.ics">h</a>'
            '<a href="https://evil.example/resource/blob/3/x.ics">o</a>'
            '<a href="/resource/blob/4/ok.ics">ok</a>'
        )
        self.assertEqual(cal.discover_ics_urls(foreign), ["https://www.bundestag.de/resource/blob/4/ok.ics"])


class RefreshIfDueTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name)

    @property
    def cache_file(self) -> Path:
        return self.out / "data" / cal.CACHE_NAME

    # Value: protects=a missing cache is built from one index request and one request per .ics, merged per calendar year; fails_when=an extra request is made, a year is lost or the file is not written atomically under data/; why_new=the fetcher did not exist; seam=refresh_if_due; no_claim=the real site
    def test_due_fetches_the_index_and_each_ics_once(self) -> None:
        source = FakeSource()
        log = refresh(self.out, source)
        self.assertEqual(source.calls, [cal.INDEX_URL, ICS_2026_URL, ICS_2027_URL])
        cache = json.loads(self.cache_file.read_text(encoding="utf-8"))
        self.assertEqual(sorted(cache["years"]), ["2026", "2027"])
        self.assertEqual([len(cache["years"][y]) for y in ("2026", "2027")], [20, 10])
        self.assertEqual(cache["years"]["2026"][0], ["2026-01-12", "2026-01-16"])
        self.assertEqual((cache["version"], cache["fetched_at"], cache["source"]), (1, "2026-11-01T12:00:00+00:00", cal.INDEX_URL))
        self.assertIn("[sitzungskalender] angelegt: 30 Sitzungswochen", log)
        self.assertEqual(list(self.cache_file.parent.glob(".*.tmp")), [])

    # Value: protects=a fresh cache costs no request at all; fails_when=a build within 7 days (or within a day while next year's calendar is still unlisted) fetches again; why_new=every online build would otherwise hit bundestag.de; seam=refresh_if_due; no_claim=none
    def test_not_due_makes_no_call(self) -> None:
        refresh(self.out, FakeSource())
        again = FakeSource()
        refresh(self.out, again, now=datetime(2026, 11, 5, 12, tzinfo=timezone.utc))
        self.assertEqual(again.calls, [])
        # 2027 is listed, so October's "look again daily" rule does not apply either.
        refresh(self.out, again, now=datetime(2026, 11, 1, 12, 30, tzinfo=timezone.utc))
        self.assertEqual(again.calls, [])

    # Value: protects=due-ness follows wall-clock time and never the build date: the refresh takes no build date at all; fails_when=a frozen --today build starts deciding whether the calendar is fetched; why_new=--today and SOURCE_DATE_EPOCH pin the page clock; seam=refresh_if_due signature; no_claim=none
    def test_due_by_wall_clock_even_when_the_build_is_frozen(self) -> None:
        refresh(self.out, FakeSource())
        late = FakeSource()
        refresh(self.out, late, now=datetime(2026, 11, 20, tzinfo=timezone.utc))
        self.assertEqual(len(late.calls), 3)
        self.assertNotIn("today", cal.refresh_if_due.__annotations__)
        with mock.patch.dict("os.environ", {"SOURCE_DATE_EPOCH": "1000000000"}):
            frozen = FakeSource()
            refresh(self.out, frozen, now=datetime(2026, 11, 30, tzinfo=timezone.utc))
            self.assertEqual(len(frozen.calls), 3)

    # Value: protects=from 1 October a cache without next year is refetched, but at most once a day; fails_when=every build in October-December fetches 3 files again, or next year's calendar is never picked up; why_new=bundestag.de publishes next year late and the cache would otherwise wait 7 days; seam=refresh_if_due; no_claim=when the Bundestag publishes
    def test_missing_next_year_is_retried_daily_from_october(self) -> None:
        pages = FakeSource().pages
        only_2026 = FakeSource({cal.INDEX_URL: '<a href="/resource/blob/9000001/x.ics">x</a>', "https://www.bundestag.de/resource/blob/9000001/x.ics": pages[ICS_2026_URL]})
        refresh(self.out, only_2026, now=datetime(2026, 10, 10, 8, tzinfo=timezone.utc))
        self.assertEqual(sorted(json.loads(self.cache_file.read_text(encoding="utf-8"))["years"]), ["2026"])
        same_day = FakeSource({})
        refresh(self.out, same_day, now=datetime(2026, 10, 10, 20, tzinfo=timezone.utc))
        self.assertEqual(same_day.calls, [])
        next_day = FakeSource()
        refresh(self.out, next_day, now=datetime(2026, 10, 11, 9, tzinfo=timezone.utc))
        self.assertEqual(len(next_day.calls), 3)
        self.assertIn("2027", json.loads(self.cache_file.read_text(encoding="utf-8"))["years"])
        # Before October the same cache is not refetched early.
        self.cache_file.unlink()
        refresh(self.out, only_2026, now=datetime(2026, 8, 1, tzinfo=timezone.utc))
        quiet = FakeSource({})
        refresh(self.out, quiet, now=datetime(2026, 8, 3, tzinfo=timezone.utc))
        self.assertEqual(quiet.calls, [])

    # Value: protects=a source failure never breaks the build and never touches the cache: one warning, no raise; fails_when=a network, HTTP, decode or parse error propagates or the old cache is overwritten; why_new=the calendar is a side source and a build must not fail for it; seam=refresh_if_due; no_claim=a programming error (not caught on purpose)
    def test_fetch_error_keeps_the_cache_and_warns_once(self) -> None:
        refresh(self.out, FakeSource())
        before = self.cache_file.read_bytes()
        late = datetime(2026, 12, 1, tzinfo=timezone.utc)
        for failure in (dip.DipError("HTTP 503"), OSError("disk"), ValueError("x")):
            with self.subTest(failure=type(failure).__name__):
                log = refresh(self.out, FakeSource(fail=failure), now=late)
                self.assertEqual(self.cache_file.read_bytes(), before)
                self.assertEqual(log.count("warning: [sitzungskalender]"), 1, log)
        # A layout change (no .ics link) is a parse failure, not a crash.
        log = refresh(self.out, FakeSource({cal.INDEX_URL: "<p>neu gebaut</p>"}), now=late)
        self.assertEqual(self.cache_file.read_bytes(), before)
        self.assertIn("no .ics links", log)
        with self.assertRaises(TypeError):  # a programming error still surfaces
            cal.refresh_if_due(self.out, now=late, fetch_html=lambda url: None, fetch_text=lambda url: None)

    # Value: protects=a partial or shrunken parse never replaces a good year; fails_when=a 3-week parse of a cached 22-week year wins, or a week spilling into the next year is accepted; why_new=a half-served .ics would delete most of a year from the page; seam=refresh_if_due; no_claim=none
    def test_a_short_parse_keeps_the_cached_year_with_a_warning(self) -> None:
        refresh(self.out, FakeSource())
        cached = json.loads(self.cache_file.read_text(encoding="utf-8"))["years"]["2026"]
        short = calendar(event("20260302", "20260307"), event("20260406", "20260411"), event("20260504", "20260509"))
        source = FakeSource({**FakeSource().pages, ICS_2026_URL: short})
        log = refresh(self.out, source, now=datetime(2026, 12, 1, tzinfo=timezone.utc))
        after = json.loads(self.cache_file.read_text(encoding="utf-8"))["years"]
        self.assertEqual(after["2026"], cached)
        self.assertIn("3 weeks for 2026", log)
        self.assertEqual(len(after["2027"]), 10)  # the other file was still read

    # Value: protects=a moved week is visible in the build log; fails_when=the added and removed weeks are not printed; why_new=the Ältestenrat can change the plan and the page would change silently; seam=refresh_if_due; no_claim=none
    def test_added_and_removed_weeks_are_logged(self) -> None:
        refresh(self.out, FakeSource())
        moved = ics_text("parlamentstermine_2026.ics").replace("20261109", "20261116").replace("20261114", "20261121")
        log = refresh(
            self.out,
            FakeSource({**FakeSource().pages, ICS_2026_URL: moved}),
            now=datetime(2026, 11, 20, tzinfo=timezone.utc),
        )
        self.assertIn("+1 (2026-11-16)", log)
        self.assertIn("-1 (2026-11-09)", log)


class NextSittingLineTests(unittest.TestCase):
    """render_next_sitting: one test per row of the plan's states table."""

    SHOWN = (2026, 43)  # 2026-10-19 .. 2026-10-25

    @classmethod
    def setUpClass(cls) -> None:
        cls.cache = synthetic_cache()

    def render(self, today: date, shown: tuple[int, int] | None = None, cache: dict | None = None) -> str:
        shown = shown or self.SHOWN
        weeks = cal.page_weeks(cache if cache is not None else self.cache, shown)
        return cal.render_next_sitting(weeks, shown_week=shown, today=today)

    @staticmethod
    def text(markup: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", markup.split(">", 1)[1])).strip()

    # Value: protects=a reader in a sitzungsfreie week gets the next planned week, date range first; fails_when=the line names the wrong week, puts the KW first or loses the link; why_new=the line is new copy; seam=render_next_sitting; no_claim=wording the owner may still change
    def test_sitzungsfrei_week_names_the_next_sitzungswoche(self) -> None:
        markup = self.render(date(2026, 10, 28))
        self.assertNotIn(" hidden", markup.split(">", 1)[0])
        self.assertEqual(self.text(markup), "Nächste Sitzungswoche: 2.–6. November 2026 (KW 45), laut Sitzungskalender")
        self.assertIn('<a href="https://www.bundestag.de/parlament/plenum/sitzungskalender">Sitzungskalender</a>', markup)
        self.assertEqual(markup.count("Sitzungskalender</a>"), 1)
        self.assertEqual(markup.count(">Sitzungskalender<"), 1)
        # A Saturday after the planned week points at the following one.
        self.assertIn("9.–13. November 2026 (KW 46)", self.text(self.render(date(2026, 11, 7))))

    # Value: protects=inside a planned week that the page has not evaluated yet the line says it is running; fails_when=a running Sitzungswoche is called "next", or the shown week's own gap is counted; why_new=a page built in KW 42 and read in KW 45 must not point at the past; seam=render_next_sitting; no_claim=none
    def test_running_sitzungswoche_other_than_the_shown_week(self) -> None:
        markup = self.render(date(2026, 11, 4), shown=(2026, 42))
        self.assertEqual(self.text(markup), "Sitzungswoche läuft: 2.–6. November 2026 (KW 45), laut Sitzungskalender")

    # Value: protects=the page that shows the running week says nothing, but still carries the data and the script for a later reader; fails_when=the paragraph is dropped instead of hidden, so a page built in a running week never shows the next week; why_new=eng review A3; seam=render_next_sitting; no_claim=none
    def test_running_shown_week_is_hidden_but_keeps_the_data(self) -> None:
        markup = self.render(date(2026, 11, 4), shown=(2026, 45))
        self.assertTrue(markup.startswith('<p class="next-sitting" hidden data-sitzungswochen='))
        self.assertIn('data-shown-week="2026-11-02"', markup)
        self.assertIn("2026-11-09", markup)

    # Value: protects=past the last listed week the page says nothing; fails_when=a stale "next week" is shown after the list ends; why_new=the list is silent past its end; seam=render_next_sitting; no_claim=none
    def test_past_the_last_listed_week_is_hidden(self) -> None:
        markup = self.render(date(2027, 6, 1))
        self.assertTrue(markup.startswith('<p class="next-sitting" hidden '))

    # Value: protects=no planned week ending on or after the shown week's Monday means no line at all; fails_when=an empty or old calendar still emits markup; why_new=the page must stay byte-identical without a calendar; seam=page_weeks, render_next_sitting; no_claim=none
    def test_no_line_without_planned_weeks(self) -> None:
        self.assertEqual(self.render(date(2026, 10, 28), cache={"version": 1, "years": {}}), "")
        old = {"version": 1, "years": {"2025": [["2025-01-13", "2025-01-17"]]}}
        self.assertEqual(self.render(date(2026, 10, 28), cache=old), "")
        self.assertEqual(cal.page_weeks(None, self.SHOWN), [])

    # Value: protects=the D4 sentence counts the planned weeks that lay entirely after the shown week and before the reader, in singular and plural; fails_when=the count includes the running week or the shown week, or the singular reads "2 weitere"; why_new=the honest-gap clause is new; seam=render_next_sitting; no_claim=wording
    def test_gap_sentence_singular_and_plural(self) -> None:
        plural = self.text(self.render(date(2026, 11, 11), shown=(2026, 41)))
        self.assertEqual(
            plural,
            "Sitzungswoche läuft: 9.–13. November 2026 (KW 46), laut Sitzungskalender. "
            "Seit KW 41 lagen laut Sitzungskalender 2 weitere Sitzungswochen; sie sind hier noch nicht ausgewertet.",
        )
        singular = self.text(self.render(date(2026, 11, 11), shown=(2026, 42)))
        self.assertTrue(singular.endswith("Seit KW 42 lag laut Sitzungskalender 1 weitere Sitzungswoche; sie ist hier noch nicht ausgewertet."), singular)
        self.assertNotIn("Seit KW", self.text(self.render(date(2026, 10, 28))))

    # Value: protects=month and year boundaries read in full and every date sits in a <time datetime> element; fails_when=a range across a month loses a month name, a bare date appears outside <time>, or the datetime attributes are wrong; why_new=the range text is preformatted for the script; seam=page_weeks, render_next_sitting; no_claim=none
    def test_ranges_and_time_elements(self) -> None:
        across = {"version": 1, "years": {"2026": [["2026-11-30", "2026-12-04"]], "2027": []}}
        markup = self.render(date(2026, 11, 24), cache=across)
        self.assertIn(
            '<time datetime="2026-11-30">30. November</time> – <time datetime="2026-12-04">4. Dezember 2026</time>',
            markup,
        )
        self.assertEqual(re.findall(r'<time datetime="(\d{4}-\d{2}-\d{2})"', markup), ["2026-11-30", "2026-12-04"])
        text_outside = re.sub(r"<time[^>]*>.*?</time>", "", markup.split(">", 1)[1])
        self.assertNotRegex(re.sub(r"\(KW \d+\)", "", re.sub(r"<[^>]+>", "", text_outside)), r"\d")
        year = {"version": 1, "years": {"2026": [["2026-12-28", "2027-01-01"]]}}
        self.assertIn("28. Dezember 2026</time> – <time", self.render(date(2026, 12, 20), cache=year))
        self.assertEqual(
            cal.page_weeks(self.cache, self.SHOWN)[0],
            {"mon": "2026-11-02", "fri": "2026-11-06", "kw": "KW 45", "start": "2.", "sep": "–", "end": "6. November 2026"},
        )


class CacheFileTests(unittest.TestCase):
    """load_cache and the due-ness of a cache file that is damaged, odd or unchanged."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name)
        self.cache_file = self.out / "data" / cal.CACHE_NAME
        self.cache_file.parent.mkdir(parents=True)

    def load(self) -> tuple[dict | None, str]:
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
            return cal.load_cache(self.out), stderr.getvalue()

    # Value: protects=a damaged, truncated or wrongly shaped data/sitzungskalender.json leaves the line out with one warning and is not deleted, while a missing file is silent; fails_when=load_cache raises on bad JSON or on a week that is not an ISO date pair, trusts a cache of another version, or warns for a first build; why_new=only valid caches were ever loaded in the tests, and puls.html reads this file on every build; seam=none; no_claim=the real Bundestag file
    def test_a_damaged_or_odd_cache_is_left_out_with_one_warning(self) -> None:
        self.assertEqual(self.load(), (None, ""))  # no file: a first build, nothing to say
        good = {"version": 1, "years": {"2026": [["2026-11-02", "2026-11-06"]]}}
        self.cache_file.write_text(json.dumps(good), encoding="utf-8")
        self.assertEqual(self.load(), (good, ""))
        bad_texts = {
            "truncated": '{"version": 1, "years": {"2026": [[',
            "not utf-8": None,
            "a list": "[]",
            "other version": json.dumps({**good, "version": 2}),
            "years a list": json.dumps({"version": 1, "years": []}),
            "year key": json.dumps({"version": 1, "years": {"26": [["2026-11-02", "2026-11-06"]]}}),
            "weeks not a list": json.dumps({"version": 1, "years": {"2026": "x"}}),
            "triple": json.dumps({"version": 1, "years": {"2026": [["2026-11-02", "2026-11-06", "x"]]}}),
            "not a date": json.dumps({"version": 1, "years": {"2026": [["2026-11-02", "bald"]]}}),
            "null date": json.dumps({"version": 1, "years": {"2026": [[None, "2026-11-06"]]}}),
        }
        for label, text in bad_texts.items():
            with self.subTest(case=label):
                if text is None:
                    self.cache_file.write_bytes(b"\xff\xfe{")
                else:
                    self.cache_file.write_text(text, encoding="utf-8")
                before = self.cache_file.read_bytes()
                cache, log = self.load()
                self.assertIsNone(cache)
                self.assertEqual(log.count("warning: [sitzungskalender]"), 1, log)
                self.assertEqual(self.cache_file.read_bytes(), before)
                self.assertEqual(cal.page_weeks(cache, (2026, 45)), [])

    # Value: protects=a damaged cache does not stay damaged: the next online build is due, refetches and replaces it, and an identical refetch logs "unverändert"; fails_when=a cache that fails validation or lacks fetched_at counts as fresh, so the line stays missing for a week, or the refresh trusts the damaged years; why_new=_is_due's unreadable-timestamp branch and the damaged-file recovery the load_cache docstring promises had no test; seam=refresh_if_due; no_claim=none
    def test_a_damaged_cache_is_replaced_by_the_next_refresh(self) -> None:
        self.cache_file.write_text("{kaputt", encoding="utf-8")
        source = FakeSource()
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO):
            cal.refresh_if_due(self.out, now=NOW, fetch_html=source.fetch, fetch_text=source.fetch)
        self.assertEqual(len(source.calls), 3)
        cache, log = self.load()
        self.assertEqual(sorted(cache["years"]), ["2026", "2027"])
        self.assertEqual(log, "")
        # A valid cache whose fetched_at is missing or garbage is due; a naive timestamp reads as UTC.
        for stamp in (None, "gestern", ""):
            with self.subTest(fetched_at=stamp):
                broken = {k: v for k, v in cache.items() if k != "fetched_at"}
                if stamp is not None:
                    broken["fetched_at"] = stamp
                self.assertTrue(cal._is_due(broken, NOW))
        self.assertFalse(cal._is_due({**cache, "fetched_at": "2026-11-01T11:00:00"}, NOW))
        self.assertTrue(cal._is_due({**cache, "fetched_at": "2026-10-20T11:00:00"}, NOW))
        # The same calendar again, a week later: rewritten, and the log says nothing moved.
        again = FakeSource()
        log = refresh(self.out, again, now=datetime(2026, 11, 10, 12, tzinfo=timezone.utc))
        self.assertEqual(len(again.calls), 3)
        self.assertIn("[sitzungskalender] unverändert: 30 Sitzungswochen", log)
        self.assertEqual(self.load()[0]["fetched_at"], "2026-11-10T12:00:00+00:00")

    # Value: protects=a one-day Sitzungswoche, which parse_ics accepts (DTEND the next day), reads as a single date with one <time> element and no range separator; fails_when=the single-day branch is dropped, so the line shows "–" with an empty start or a doubled date; why_new=every other range test spans several days; seam=parse_ics, page_weeks, render_next_sitting; no_claim=that the Bundestag plans one-day weeks
    def test_a_one_day_week_reads_as_one_date(self) -> None:
        (week,) = cal.parse_ics(calendar(event("20261104", "20261105")))
        self.assertEqual(week, (date(2026, 11, 4), date(2026, 11, 4)))
        cache = {"version": 1, "years": {"2026": [["2026-11-04", "2026-11-04"]]}}
        weeks = cal.page_weeks(cache, (2026, 43))
        self.assertEqual((weeks[0]["start"], weeks[0]["sep"], weeks[0]["end"]), ("", "", "4. November 2026"))
        markup = cal.render_next_sitting(weeks, shown_week=(2026, 43), today=date(2026, 10, 28))
        self.assertEqual(re.findall(r'<time datetime="([^"]+)"', markup), ["2026-11-04"])
        self.assertIn(
            'data-next-sitting-range><time datetime="2026-11-04">4. November 2026</time></span>', markup
        )
        self.assertEqual(cal.range_text(week[0], week[1]), "4. November 2026")


class FrontPageTests(unittest.TestCase):
    TODAY = date(2026, 9, 15)

    @classmethod
    def setUpClass(cls) -> None:
        cls.cache = synthetic_cache()
        cls.entries = page_tests.WeekRadarPageTests("test_header_running_week")._week()

    def render(self, **kwargs) -> str:
        today = kwargs.pop("today", self.TODAY)
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO):
            return build_dip_pulse_site.render_front_page(
                self.entries, database_href=None, features=page_tests.all_selection(), today=today, **kwargs
            )

    # Value: protects=pre-release rule (no output moves): without a calendar cache, or with none that reaches the shown week, puls.html gains no byte; fails_when=a hook writes markup, style or script without a cache; why_new=new hooks in render_front_page; seam=render_front_page; no_claim=real-store output
    def test_without_a_cache_the_page_is_unchanged(self) -> None:
        plain = self.render()
        self.assertEqual(self.render(sitzungskalender_cache=None), plain)
        self.assertEqual(self.render(sitzungskalender_cache={"version": 1, "years": {}}), plain)
        for marker in ("next-sitting", "data-sitzungswochen", "Sitzungskalender"):
            self.assertNotIn(marker, plain)

    # Value: protects=with a cache exactly one line, one style rule set and one script reach the page, and the page's other bytes stay; fails_when=the line or script is emitted twice, or removing them does not give the plain page back; why_new=new markup in the header; seam=render_front_page; no_claim=browser behaviour (tests/next_sitting_browser_check.js)
    def test_with_a_cache_one_line_one_script(self) -> None:
        plain = self.render()
        markup = self.render(sitzungskalender_cache=self.cache)
        self.assertEqual(markup.count('<p class="next-sitting"'), 1)
        self.assertEqual(markup.count("data-sitzungswochen="), 1)
        self.assertEqual(markup.count("p.next-sitting[data-sitzungswochen]"), 1)
        self.assertEqual(markup.count(".next-sitting {"), 1)
        header = re.search(r'<header class="page-header">(.*?)</header>', markup, re.S).group(1)
        self.assertRegex(
            header,
            r'</p><p class="next-sitting" data-sitzungswochen=.*laut <a href="[^"]+">Sitzungskalender</a>.*</p>\s*</div>',
        )
        self.assertIn("Nächste Sitzungswoche: ", re.sub(r"<[^>]+>", "", header))
        stripped = markup
        stripped = re.sub(r'<p class="next-sitting".*?</p>', "", stripped, flags=re.S)
        stripped = stripped.replace(cal.NEXT_SITTING_STYLE, "").replace(cal.NEXT_SITTING_SCRIPT, "")
        self.assertEqual(stripped, plain)

    # Value: protects=a page built during the running week hides the line but keeps data and script, so a later reader still sees the next week; fails_when=the hidden state emits nothing; why_new=eng review A3; seam=render_front_page; no_claim=none
    def test_running_shown_week_hides_the_line_but_keeps_data_and_script(self) -> None:
        markup = self.render(sitzungskalender_cache=self.cache, today=date(2026, 6, 11))
        self.assertIn('<p class="next-sitting" hidden data-sitzungswochen=', markup)
        self.assertIn(cal.NEXT_SITTING_SCRIPT, markup)

    # Value: protects=the script never writes HTML and touches only the line's own slots; fails_when=innerHTML, document.write or an outside selector is introduced; why_new=the inline script ships on every page with a calendar; seam=NEXT_SITTING_SCRIPT; no_claim=runtime behaviour
    def test_script_is_text_only(self) -> None:
        script = cal.NEXT_SITTING_SCRIPT
        for forbidden in ("innerHTML", "outerHTML", "document.write", "eval(", "insertAdjacent"):
            self.assertNotIn(forbidden, script)
        self.assertIn("textContent", script)
        self.assertIn("Europe/Berlin", script)


class RenderSiteWiringTests(unittest.TestCase):
    """render_site reads data/sitzungskalender.json of its own output directory into puls.html."""

    def _build(self, cache_text: str | None) -> tuple[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "site"
            if cache_text is not None:
                (output / "data").mkdir(parents=True)
                (output / "data" / cal.CACHE_NAME).write_text(cache_text, encoding="utf-8")
            with mock.patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
                demo.build_demo(output)
            return (output / "puls.html").read_text(encoding="utf-8"), stderr.getvalue()

    # Value: protects=a cache file in the build's output directory reaches puls.html through render_site, and a damaged one gives the plain page with a warning instead of a failed build; fails_when=render_site stops passing load_cache(output_dir) to render_front_page (or reads another path), so the cached calendar never shows on the real site, or a damaged file aborts the build; why_new=the front-page tests hand the cache to render_front_page directly and main() is stubbed, so the one line that connects file and page was untested; seam=render_site via build_demo_site.build_demo; no_claim=the line's text (NextSittingLineTests)
    def test_the_cache_file_in_the_output_directory_reaches_puls_html(self) -> None:
        far = {"version": 1, "years": {"2099": [["2099-01-12", "2099-01-16"]]}}
        markup, log = self._build(json.dumps(far))
        self.assertEqual(markup.count('<p class="next-sitting"'), 1)
        self.assertIn("12.–16. Januar 2099", re.sub(r"<[^>]+>", "", markup))
        self.assertNotIn("[sitzungskalender]", log)
        plain, _ = self._build(None)
        self.assertNotIn("next-sitting", plain)
        damaged, damaged_log = self._build("{kaputt")
        self.assertNotIn("next-sitting", damaged)
        self.assertEqual(damaged_log.count("warning: [sitzungskalender]"), 1, damaged_log)


class MainWiringTests(unittest.TestCase):
    """Only an online build that persists may refresh the calendar."""

    def _run(self, argv_extra: list[str], *, offline: bool) -> tuple[mock.MagicMock, Path]:
        entry = page_tests.SittingWeekComparisonTests._entry(
            "2026-06-12", "21/84", [page_tests.SittingWeekComparisonTests._item(1, [("SPD", 100)])]
        )
        entry["report"]["protocol"]["id"] = "5799"
        protocol = page_tests.BuildClockAndWeekTests._catalog_protocol("21/84", "5799", "2026-06-12")
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "site"
            patches = [
                mock.patch.object(build_dip_pulse_site, "render_site", return_value=output_dir / "index.html"),
                mock.patch.object(sys, "stderr", new_callable=io.StringIO),
                mock.patch.object(sys, "stdout", new_callable=io.StringIO),
            ]
            if offline:
                args = SimpleNamespace(
                    output_dir=output_dir, database_path=None, offline=True, no_persist=False, week=None, today=date(2026, 9, 15)
                )
                patches += [
                    mock.patch.object(build_dip_pulse_site, "parse_args", return_value=args),
                    mock.patch.object(build_dip_pulse_site, "load_cached_protocols", return_value=[{"id": "cached", "datum": "2026-06-12"}]),
                    mock.patch.object(build_dip_pulse_site, "load_existing_detail_entries", return_value=[entry]),
                    mock.patch.object(build_dip_pulse_site, "rebuild_cached_detail_pages", return_value=[entry]),
                    mock.patch.object(build_dip_pulse_site, "run_data_pipeline", return_value=({}, None, set(), None, False)),
                ]
            else:
                argv = ["build", "--api-key", "k", "--no-abgeordnetenwatch", "--output-dir", str(output_dir), *argv_extra]
                # Everything between the dossiers and the export is stubbed: the point is only
                # whether main() reaches the calendar hook, not the store pipeline.
                patches += [
                    mock.patch.object(sys, "argv", argv),
                    mock.patch.object(build_dip_pulse_site, "fetch_protocols", return_value=[protocol]),
                    mock.patch.object(build_dip_pulse_site, "build_dossiers_with_progress", return_value=[entry]),
                    mock.patch.object(build_dip_pulse_site, "run_data_pipeline", return_value=({}, None, set(), None, False)),
                    mock.patch.object(build_dip_pulse_site, "refresh_vorgang_cache"),
                    mock.patch.object(build_dip_pulse_site, "require_parsed_reports"),
                    mock.patch.object(build_dip_pulse_site, "reparse_cached_xml"),
                    mock.patch.object(build_dip_pulse_site, "rebuild_database_from_entries", return_value=SimpleNamespace(facts_report={})),
                    mock.patch.object(build_dip_pulse_site.facts, "open_readonly"),
                    mock.patch.object(build_dip_pulse_site.pulse_store, "require_current_schema"),
                    mock.patch.object(build_dip_pulse_site, "collect_abgeordnete", return_value=([], {})),
                    mock.patch.object(build_dip_pulse_site, "write_report_files", return_value=entry),
                ]
            refresher = mock.patch.object(cal, "refresh_if_due")
            with ExitStack() as stack:
                for patch in patches:
                    stack.enter_context(patch)
                refresh_mock = stack.enter_context(refresher)
                build_dip_pulse_site.main()
            return refresh_mock, output_dir

    # Value: protects=--offline and an online --no-persist build never reach bundestag.de for the calendar; fails_when=either path calls refresh_if_due; why_new=the new hook sits in main(), and CI must stay off the network; seam=main; no_claim=the store pipeline (stubbed)
    def test_offline_and_no_persist_never_refresh(self) -> None:
        self.assertEqual(self._run([], offline=True)[0].call_count, 0)
        self.assertEqual(self._run(["--no-persist"], offline=False)[0].call_count, 0)

    # Value: protects=an online build that persists refreshes the calendar exactly once, into the output directory; fails_when=the hook is removed, moved behind --no-persist's guard the wrong way or called twice; why_new=positive control for the negative test above, so it cannot pass because main() exits early; seam=main; no_claim=the store pipeline (stubbed)
    def test_online_persisting_build_refreshes_once(self) -> None:
        refresh_mock, output_dir = self._run([], offline=False)
        refresh_mock.assert_called_once_with(output_dir)


def write_next_sitting_browser_fixture(output: Path) -> None:
    """Two copies of one puls.html built on 2026-09-15 from the synthetic calendar: with the
    script (next-sitting.html) and without it (next-sitting-nojs.html, the build's own fallback).
    tests/next_sitting_browser_check.js loads the first under frozen reader dates and compares
    the line with the second."""
    output.mkdir(parents=True, exist_ok=True)
    entries = page_tests.WeekRadarPageTests("test_header_running_week")._week()
    with mock.patch.object(sys, "stderr", new_callable=io.StringIO):
        markup = build_dip_pulse_site.render_front_page(
            entries, database_href=None, features=page_tests.default_selection(), today=date(2026, 9, 15),
            sitzungskalender_cache=synthetic_cache(),
        )
    assert cal.NEXT_SITTING_SCRIPT in markup
    (output / "next-sitting.html").write_text(markup, encoding="utf-8")
    (output / "next-sitting-nojs.html").write_text(markup.replace(cal.NEXT_SITTING_SCRIPT, ""), encoding="utf-8")


if __name__ == "__main__":
    if "--browser-fixture" in sys.argv:
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--browser-fixture", type=Path, required=True)
        write_next_sitting_browser_fixture(parser.parse_args().browser_fixture)
    else:
        unittest.main()
