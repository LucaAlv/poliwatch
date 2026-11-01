"""The week radar as data: feeds/week-radar.json and the RSS feed behind BUNDESTAG_PULSE_SITE_URL."""

from __future__ import annotations

import html
import io
import json
import os
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from unittest import mock

import _support  # noqa: F401
import build_demo_site as demo
import build_dip_pulse_site as site
import publication_state as publication
import render_dip_pulse_html as pulse_html
import test_build_dip_pulse_site as page_tests
import week_radar_feed as feed

SITE = "https://pulse.example.org/"
# Builders only (functions, not the TestCase class, so discovery does not run its tests twice).
make_entry = page_tests.SittingWeekComparisonTests._entry
make_item = page_tests.SittingWeekComparisonTests._item
make_speaker = page_tests.SittingWeekComparisonTests._speaker
pos = page_tests.WeekRadarDataTests._pos

SCHEMA_KEYS = {
    "top": {"schema_version", "stability", "build_date", "site_url", "weeks"},
    "week": {
        "week", "label", "monday", "sunday", "running", "speech_count", "top_count",
        "sittings", "rows", "question_formats", "unranked",
    },
    "sitting": {"dokumentnummer", "datum", "href"},
    "row": {
        "href", "dokumentnummer", "datum", "top_index", "top_id", "heading", "type_label", "lead_title",
        "equal_weight", "titles", "procedures", "speech_count", "share_percent", "speeches_by_group",
        "attributed_speech_count", "trace", "has_votes",
    },
    "procedure": {"vorgang_id", "titel", "vorgangstyp", "vorgangsposition"},
    "group": {"fraktion", "sprechrolle", "speech_count"},
    "trace": {"vorgang_id", "first_week", "first_position", "first_href", "current_position"},
    "format": {"heading", "speech_count", "share_percent", "href"},
    "unranked": {"dokumentnummer", "href", "count"},
}


def build(entries, *, today=date(2026, 9, 15), week=None, **kwargs):
    with mock.patch.object(sys, "stderr", new_callable=io.StringIO):
        return feed.build_payload(
            entries, today=today, week=week, vorgang_cache=None, dossier_href_for=site.dossier_href, **kwargs
        )


def radar_week() -> list[dict]:
    return page_tests.WeekRadarPageTests("test_header_running_week")._week()


def long_archive(weeks: int = 14) -> list[dict]:
    """One Wednesday sitting per week from 2026-03-04; every week continues procedure G1."""
    entries = []
    for k in range(weeks):
        day = date(2026, 3, 4) + timedelta(days=7 * k)
        entries.append(
            make_entry(
                day.isoformat(),
                f"21/{50 + k}",
                [
                    make_item(1, [("SPD", 100)] * (3 + k % 3), [pos("G1", "Dauergesetz", "Gesetzgebung", f"{k + 1}. Beratung")]),
                    make_item(2, [("AfD", 100)] * 2, [pos(f"X{k}", f"Antrag {k}")]),
                ],
            )
        )
    return entries


class PayloadTests(unittest.TestCase):
    # Value: protects=the data file and puls.html show the same rows because both come from week_topic_rows; fails_when=the feed ranks, titles or links a row differently from the page; why_new=the feed is a second renderer over the page's one computation; seam=build_payload; no_claim=the markup around the rows
    def test_rows_match_the_page_for_the_selected_week(self) -> None:
        entries = radar_week()
        payload = build(entries)
        with mock.patch.object(sys, "stderr", new_callable=io.StringIO):
            markup = site.render_front_page(entries, database_href=None, features=page_tests.all_selection(), today=date(2026, 9, 15))
        page_rows = markup.split('<li class="radar-row"')[1:]
        week = payload["weeks"][0]
        self.assertEqual(week["week"], "2026-W24")
        self.assertEqual(len(page_rows), len(week["rows"]))
        for page_row, row in zip(page_rows, week["rows"]):
            main = re.search(r'<div class="radar-main">(.*?)</div>', page_row, re.S).group(1)
            self.assertIn(f'href="{row["href"]}"', main)
            shown = [html.unescape(t) for t in re.findall(r'class="radar-(?:title|group-title)">(?:<a[^>]*>)?([^<]+)', main)]
            self.assertEqual(shown[0], row["lead_title"] if not row["equal_weight"] else row["titles"][0])
            if row["equal_weight"]:
                self.assertEqual(shown, row["titles"][:3])
            self.assertIn(f'{row["speech_count"]} Rede', page_row)

    # Value: protects=only named fields reach the file: no Counter, item, stats or speaker object; fails_when=a key outside the schema or a non-JSON type appears at any level; why_new=rows carry whole items and Counter objects that must never be dumped; seam=build_payload; no_claim=values
    def test_whitelist_projection(self) -> None:
        payload = build(radar_week())
        json.dumps(payload, allow_nan=False)  # plain JSON types only
        self.assertEqual(set(payload), SCHEMA_KEYS["top"])
        self.assertEqual((payload["schema_version"], payload["build_date"], payload["site_url"]), (1, "2026-09-15", None))
        week = payload["weeks"][0]
        self.assertEqual(set(week), SCHEMA_KEYS["week"])
        self.assertTrue(week["rows"] and week["sittings"] and week["unranked"] is not None)
        for sitting in week["sittings"]:
            self.assertEqual(set(sitting), SCHEMA_KEYS["sitting"])
        traced = 0
        for row in week["rows"]:
            self.assertEqual(set(row), SCHEMA_KEYS["row"])
            for procedure in row["procedures"]:
                self.assertEqual(set(procedure), SCHEMA_KEYS["procedure"])
            for group in row["speeches_by_group"]:
                self.assertEqual(set(group), SCHEMA_KEYS["group"])
            if row["trace"]:
                traced += 1
                self.assertEqual(set(row["trace"]), SCHEMA_KEYS["trace"])
        self.assertEqual(traced, 1)  # the four-Antrag group returning from KW 21
        for fmt in week["question_formats"]:
            self.assertEqual(set(fmt), SCHEMA_KEYS["format"])
        self.assertEqual(len(week["question_formats"]), 1)
        for unranked in week["unranked"]:
            self.assertEqual(set(unranked), SCHEMA_KEYS["unranked"])
        self.assertNotIn("rank", json.dumps(payload).lower().replace("unranked", ""))

    # Value: protects=Redeanteil je Zusammenschluss is split like the release's speeches.fraktion/sprechrolle: a Sprechrolle side is its release code (bundesregierung, bundesrat, weitere) and never a Fraktion, Unbekannt is NULL in both; fails_when=a display label ("Bundesregierung") reaches sprechrolle, a side lands in fraktion, Unbekannt is written as a Fraktion, or the counts stop adding up to the attributed Reden; why_new=the radar's label strings differ from the release's two columns and owner decision D10 fixed the codes; seam=speeches_by_group, build_payload; no_claim=equality with a SQL GROUP BY on a real store (a role speech the store also tags with a fraktion counts on its side only)
    def test_speeches_by_group_splits_like_the_release_columns(self) -> None:
        counts = Counter({"SPD": 4, "Bundesregierung": 3, "Unbekannt": 1, "fraktionslos": 1, "weitere Sprechrolle": 1, "Bundesrat": 1})
        self.assertEqual(
            feed.speeches_by_group(counts),
            [
                {"fraktion": "SPD", "sprechrolle": None, "speech_count": 4},
                {"fraktion": None, "sprechrolle": "bundesregierung", "speech_count": 3},
                {"fraktion": None, "sprechrolle": "bundesrat", "speech_count": 1},  # ties sort by the radar label
                {"fraktion": None, "sprechrolle": None, "speech_count": 1},  # "Unbekannt"
                {"fraktion": "fraktionslos", "sprechrolle": None, "speech_count": 1},
                {"fraktion": None, "sprechrolle": "weitere", "speech_count": 1},
            ],
        )
        minister = make_speaker(None, 100, role="Bundesminister für Finanzen")
        item = make_item(1, [("SPD", 100)] * 2, [pos("V1", "Haushalt", "Gesetzgebung", "1. Beratung")])
        item["xml_speakers"].append(minister)
        item["xml_speech_count"] = 3
        payload = build([make_entry("2026-06-10", "21/82", [item])])
        (row,) = payload["weeks"][0]["rows"]
        sides = {(g["fraktion"], g["sprechrolle"]): g["speech_count"] for g in row["speeches_by_group"]}
        self.assertEqual(sides, {("SPD", None): 2, (None, "bundesregierung"): 1})
        self.assertEqual(sum(sides.values()), row["attributed_speech_count"])
        self.assertEqual(row["attributed_speech_count"], row["speech_count"])
        self.assertEqual(row["share_percent"], 100.0)

    # Value: protects=the twelve-week window, newest first, and a --week build staying frozen on its week; fails_when=more than 12 weeks are written, the order flips, or a later week appears in a --week build; why_new=the feed keeps a rolling window of the archive; seam=build_payload; no_claim=none
    def test_window_order_and_frozen_week(self) -> None:
        entries = long_archive(14)
        payload = build(entries, today=date(2026, 9, 1))
        weeks = [w["week"] for w in payload["weeks"]]
        self.assertEqual(len(weeks), 12)
        self.assertEqual(weeks, sorted(weeks, reverse=True))
        self.assertEqual(weeks[0], "2026-W23")
        frozen = build(entries, today=date(2026, 9, 1), week=(2026, 18))
        self.assertEqual(frozen["weeks"][0]["week"], "2026-W18")
        self.assertEqual(len(frozen["weeks"]), 9)  # W10 .. W18
        self.assertEqual(max(w["week"] for w in frozen["weeks"]), "2026-W18")
        with self.assertRaises(ValueError):
            build(entries, week=(2030, 1))

    # Value: protects=one occurrence index for all weeks gives each week the trace it would get with its own index; fails_when=an older week's trace changes when the index is built once for the selected week; why_new=the feed computes the index once to avoid 12 passes (eng review P1); seam=build_payload; no_claim=timing
    def test_one_occurrence_index_equals_each_weeks_own(self) -> None:
        entries = long_archive(14)
        payload = build(entries, today=date(2026, 9, 1))
        weeks = pulse_html.group_entries_by_week(entries)
        checked = 0
        for week_payload in payload["weeks"]:
            year, number = week_payload["week"].split("-W")
            week = (int(year), int(number))
            own = pulse_html.week_topic_rows(
                weeks[week], pulse_html.vorgang_occurrences(weeks, week),
                total=pulse_html.week_stats(week, weeks[week])["speech_count"], dossier_href_for=site.dossier_href,
            )
            for row, expected in zip(week_payload["rows"], own["rows"]):
                if expected["trace"]:
                    checked += 1
                    self.assertEqual(row["trace"]["first_week"], feed.week_id(expected["trace"]["first"]["week"]))
                    self.assertEqual(row["trace"]["current_position"], expected["trace"]["current_position"] or None)
                else:
                    self.assertIsNone(row["trace"])
        self.assertGreaterEqual(checked, 11)

    # Value: protects=the file is byte-stable and carries no wall clock; fails_when=two calls differ, the build date is not the injected date, or SOURCE_DATE_EPOCH leaks into the data; why_new=builds must be reproducible; seam=build_payload; no_claim=none
    def test_determinism(self) -> None:
        entries = radar_week()
        first = json.dumps(build(entries), ensure_ascii=False)
        self.assertEqual(first, json.dumps(build(entries), ensure_ascii=False))
        with mock.patch.dict("os.environ", {"SOURCE_DATE_EPOCH": "1"}):
            self.assertEqual(first, json.dumps(build(entries), ensure_ascii=False))
        later = build(entries, today=date(2026, 9, 16))
        base = build(entries)
        self.assertEqual(later["build_date"], "2026-09-16")
        self.assertEqual({**later, "build_date": None}, {**base, "build_date": None})

    # Value: protects=an empty or undated archive still gives a valid file; fails_when=build_payload crashes without a dated week; why_new=render_site calls write on every build; seam=build_payload; no_claim=none
    def test_empty_archive(self) -> None:
        self.assertEqual(build([])["weeks"], [])
        undated = make_entry("kein Datum", "21/1", [make_item(1, [("SPD", 100)])])
        self.assertEqual(build([undated])["weeks"], [])


class RssTests(unittest.TestCase):
    def rss(self, payload, site_url=SITE):
        text = feed.render_rss(payload, site_url)
        return text, ET.fromstring(text.split("\n", 1)[1])

    # Value: protects=the feed has one item per finished week with a unique week GUID, absolute links, a parseable document, and never a running week; fails_when=a running week gets an item, GUIDs repeat or are not YYYY-Www, a link is relative, or the XML does not parse; why_new=the feed is new public output; seam=render_rss; no_claim=feed-reader rendering
    def test_finished_weeks_only_with_absolute_links(self) -> None:
        entries = long_archive(4)
        payload = build(entries, today=date(2026, 3, 27))  # KW 13 runs: its Wednesday is 2026-03-25
        self.assertTrue(any(w["running"] for w in payload["weeks"]))
        _text, root = self.rss(payload)
        guids = [g.text for g in root.iter("guid")]
        self.assertEqual(len(guids), len(set(guids)))
        self.assertTrue(all(re.fullmatch(r"\d{4}-W\d{2}", g) for g in guids))
        self.assertEqual(guids, [w["week"] for w in payload["weeks"] if not w["running"]])
        self.assertNotIn("2026-W13", guids)
        for item in root.iter("item"):
            self.assertTrue(item.find("link").text.startswith(SITE + "protocols/"))
            self.assertEqual(item.find("guid").get("isPermaLink"), "false")
        channel = root.find("channel")
        self.assertEqual(channel.find("title").text, "Bundestag-Puls · Wochenübersicht")
        self.assertEqual(channel.find("link").text, SITE + "puls.html")
        self.assertEqual(channel.find("language").text, "de")

    # Value: protects=pubDate is deterministic (Monday after the week, 00:00 Berlin) and never later than the build; fails_when=an item is dated after the build date, or a week not yet over gets an item; why_new=an early-Monday build would otherwise publish an item from the future (eng review C4); seam=render_rss; no_claim=none
    def test_pub_date_is_never_after_the_build(self) -> None:
        entries = long_archive(3)
        for today in (date(2026, 3, 16), date(2026, 3, 23), date(2026, 3, 30)):
            payload = build(entries, today=today)
            _text, root = self.rss(payload)
            built = parsedate_to_datetime(root.find("channel/lastBuildDate").text)
            for item in root.iter("item"):
                published = parsedate_to_datetime(item.find("pubDate").text)
                self.assertLessEqual(published, built)
                self.assertEqual((published.hour, published.minute, published.weekday()), (0, 0, 0))
        # Build exactly on the Monday after KW 10: the item exists and equals the build moment.
        _text, root = self.rss(build(entries, today=date(2026, 3, 9)))
        self.assertEqual([g.text for g in root.iter("guid")], ["2026-W10"])
        # A build dated before the shown week gives no item for it.
        _text, root = self.rss(build(entries, today=date(2026, 3, 1)))
        self.assertEqual(list(root.iter("item")), [])

    # Value: protects=an item title leads with the top topic, names an equal-weight group by its type label (never one Antrag's title) and is cut at 90 characters; fails_when=one Fraktion's Antrag title is promoted, or the cut is missing; why_new=Final Gate D16 and the topic-led title (D9); seam=render_rss; no_claim=wording
    def test_item_title_is_topic_led_and_neutral(self) -> None:
        group = make_item(
            1, [("SPD", 100)] * 6, [pos(f"A{i}", f"Antrag der Fraktion {i}") for i in range(4)]
        )
        other = make_item(2, [("AfD", 100)] * 2, [pos("W1", "x" * 200, "Gesetzgebung", "1. Beratung")])
        payload = build([make_entry("2026-06-10", "21/82", [group, other])], today=date(2026, 7, 1))
        _text, root = self.rss(payload)
        (title,) = [t.text for t in root.iter("title") if t.text and t.text.startswith("KW")]
        self.assertEqual(title, "KW 24/2026: Antrag · Beratung · 4 Anträge gemeinsam und 1 weiteres Thema")
        self.assertNotIn("Antrag der Fraktion", title)
        top_long = make_item(1, [("SPD", 100)] * 3, [pos("W1", "x" * 200, "Gesetzgebung", "1. Beratung")])
        payload = build([make_entry("2026-06-10", "21/82", [top_long])], today=date(2026, 7, 1))
        _text, root = self.rss(payload)
        (title,) = [t.text for t in root.iter("title") if t.text and t.text.startswith("KW")]
        self.assertEqual(title, "KW 24/2026: " + "x" * 89 + "…")

    # Value: protects=the item description carries the denominator, a method note and a source line naming every sitting of the week with absolute links (the source duty, ADR 0003); fails_when=the Reden total, the share, or a sitting's dokumentnummer or link is missing; why_new=a feed item is read without the page; seam=render_rss; no_claim=HTML rendering in readers
    def test_item_description_denominator_and_sources(self) -> None:
        payload = build(radar_week(), today=date(2026, 9, 15))
        _text, root = self.rss(payload)
        item = next(root.iter("item"))  # the newest finished week, KW 24
        description = item.find("description").text
        self.assertIn("<p>8.–12. Juni 2026 · 29 Reden in 9 Tagesordnungspunkten</p>", description)
        self.assertIn("Anteil an allen 29 Reden der Woche", description)
        self.assertRegex(description, r"<li><a href=\"https://pulse\.example\.org/protocols/[^\"]+#top-\d+\">[^<]+</a> — \d+ Reden? · \d+,\d %</li>")
        source = re.search(r"<p>Quelle: (.*?)</p>", description).group(1)
        self.assertTrue(source.startswith("Deutscher Bundestag, Plenarprotokolle "))
        for number in ("21/82", "21/83", "21/84"):
            self.assertIn(f">{number}</a>", source)
        self.assertEqual(item.find("link").text, SITE + "protocols/plenarprotokoll-21-84.html")
        # The description is escaped HTML inside the XML text, not child elements.
        self.assertEqual(list(item.find("description")), [])


class WriteTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name)
        self.entries = radar_week()

    def write(self, env: dict[str, str] | None = None, **kwargs) -> str:
        environ = {key: value for key, value in os.environ.items() if key != feed.SITE_URL_ENV}
        environ.update(env or {})
        with mock.patch.dict("os.environ", environ, clear=True), mock.patch.object(sys, "stderr", new_callable=io.StringIO) as err:
            feed.write(
                self.out, self.entries, today=kwargs.get("today", date(2026, 9, 15)), week=kwargs.get("week"),
                vorgang_cache=None, dossier_href_for=site.dossier_href,
            )
        return err.getvalue()

    # Value: protects=without BUNDESTAG_PULSE_SITE_URL the JSON is written, no RSS exists, and the log says why; fails_when=an RSS appears without a base URL or the skip is silent; why_new=route B of the plan: no domain yet; seam=write; no_claim=none
    def test_no_site_url_writes_json_only(self) -> None:
        log = self.write()
        self.assertTrue((self.out / "feeds" / "week-radar.json").is_file())
        self.assertFalse((self.out / "feeds" / "week-radar.xml").exists())
        self.assertIn("week-radar: RSS übersprungen (BUNDESTAG_PULSE_SITE_URL nicht gesetzt)", log)
        data = json.loads((self.out / "feeds" / "week-radar.json").read_text(encoding="utf-8"))
        self.assertEqual((data["schema_version"], data["site_url"], len(data["weeks"])), (1, None, 2))  # KW 24 and KW 21

    # Value: protects=a later build without the variable removes an older feed so a stale one is never deployed; fails_when=feeds/week-radar.xml survives a build without a valid URL; why_new=eng review A2; seam=write; no_claim=none
    def test_stale_feed_is_removed_when_unset_or_invalid(self) -> None:
        self.write({feed.SITE_URL_ENV: SITE})
        rss = self.out / "feeds" / "week-radar.xml"
        self.assertTrue(rss.is_file())
        ET.fromstring(rss.read_text(encoding="utf-8").split("\n", 1)[1])
        self.write()
        self.assertFalse(rss.exists())
        self.write({feed.SITE_URL_ENV: SITE})
        self.assertTrue(rss.is_file())
        log = self.write({feed.SITE_URL_ENV: "http://pulse.example.org/"})
        self.assertFalse(rss.exists())
        self.assertIn("warning: [week-radar]", log)

    # Value: protects=only an absolute https URL with a trailing slash is accepted as the feed base; fails_when=a relative, http, query-carrying or slash-less URL produces a feed with broken links; why_new=RSS needs absolute URLs; seam=valid_site_url, write; no_claim=that the host exists
    def test_site_url_validation(self) -> None:
        for bad in ("", "pulse.example.org/", "https://pulse.example.org", "http://pulse.example.org/", "https:///", "https://a.example/?x=1/", "/relative/"):
            with self.subTest(url=bad):
                self.assertFalse(feed.valid_site_url(bad))
                log = self.write({feed.SITE_URL_ENV: bad}) if bad else ""
                self.assertFalse((self.out / "feeds" / "week-radar.xml").exists())
                if bad:
                    self.assertIn("warning: [week-radar]", log)
        self.assertTrue(feed.valid_site_url(SITE))
        self.assertTrue(feed.valid_site_url("https://example.org/pulse/"))

    # Value: protects=a malformed BUNDESTAG_PULSE_SITE_URL (an unclosed IPv6 bracket, an impossible port) takes the documented invalid-URL path: the JSON is written, no RSS exists, a stale RSS is removed, one warning, and the build does not raise; fails_when=urlparse's ValueError (or the port check) escapes write() and aborts the build; why_new=Codex review found valid_site_url crashing on "https://[example.org/"; seam=valid_site_url, write; no_claim=that every possible malformed string is listed
    def test_malformed_site_url_does_not_abort_the_build(self) -> None:
        self.write({feed.SITE_URL_ENV: SITE})
        rss = self.out / "feeds" / "week-radar.xml"
        self.assertTrue(rss.is_file())
        for bad in ("https://[example.org/", "https://example.org:99999999/", "https://example.org:abc/"):
            with self.subTest(url=bad):
                self.assertFalse(feed.valid_site_url(bad))
                self.write({feed.SITE_URL_ENV: SITE})
                (self.out / "feeds" / "week-radar.json").unlink()
                log = self.write({feed.SITE_URL_ENV: bad})
                self.assertTrue((self.out / "feeds" / "week-radar.json").is_file())
                self.assertFalse(rss.exists())
                self.assertEqual(log.count("warning: [week-radar]"), 1, log)
                data = json.loads((self.out / "feeds" / "week-radar.json").read_text(encoding="utf-8"))
                self.assertIsNone(data["site_url"])

    # Value: protects=the JSON carries the configured site URL and the RSS the week's items when a valid URL is set; fails_when=site_url stays null or the feed is empty; why_new=the route-B switch is the env var; seam=write; no_claim=none
    def test_valid_site_url_writes_both(self) -> None:
        log = self.write({feed.SITE_URL_ENV: SITE}, today=date(2026, 9, 15))
        self.assertIn("RSS feeds/week-radar.xml", log)
        data = json.loads((self.out / "feeds" / "week-radar.json").read_text(encoding="utf-8"))
        self.assertEqual(data["site_url"], SITE)
        root = ET.fromstring((self.out / "feeds" / "week-radar.xml").read_text(encoding="utf-8").split("\n", 1)[1])
        self.assertEqual([g.text for g in root.iter("guid")], ["2026-W24", "2026-W21"])
        self.assertEqual(list((self.out / "feeds").glob(".*.tmp")), [])

    # Value: protects=a --week build writes the frozen week as its newest; fails_when=the file shows a later week than --week; why_new=--week builds must stay frozen; seam=write; no_claim=none
    def test_week_flag_freezes_the_newest_week(self) -> None:
        self.entries = long_archive(5)
        self.write(week=(2026, 11), today=date(2026, 9, 1))
        data = json.loads((self.out / "feeds" / "week-radar.json").read_text(encoding="utf-8"))
        self.assertEqual(data["weeks"][0]["week"], "2026-W11")
        self.assertEqual(len(data["weeks"]), 2)  # W10, W11; the later weeks stay out

    # Value: protects=the public-output validator scans both feed files; fails_when=a denylisted string planted in feeds/week-radar.json or .xml is not reported, or an unrelated feeds file is scanned; why_new=the feed is public text outside HTML; seam=validate_public_output; no_claim=none
    def test_validate_public_output_scans_the_feeds(self) -> None:
        self.write({feed.SITE_URL_ENV: SITE})
        self.assertEqual(publication.validate_public_output(self.out), [])
        for name in ("week-radar.json", "week-radar.xml"):
            path = self.out / "feeds" / name
            original = path.read_text(encoding="utf-8")
            path.write_text(original.replace("\n", "\nSiehe /Users/example/x\n", 1), encoding="utf-8")
            self.assertEqual(publication.validate_public_output(self.out), [f"feeds/{name}:2: local-path"])
            path.write_text(original, encoding="utf-8")
        (self.out / "feeds" / "other.json").write_text("/Users/example", encoding="utf-8")
        self.assertEqual(publication.validate_public_output(self.out), [])


class RenderSiteWiringTests(unittest.TestCase):
    # Value: protects=render_site writes the feed next to the pages and leaves it out of nothing it did before; fails_when=a demo build has no feeds/week-radar.json or it is not valid schema-1 JSON; why_new=render_site gained the one write call; seam=render_site; no_claim=the real archive
    def test_demo_build_writes_the_json_and_no_rss(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ"):
            os.environ.pop(feed.SITE_URL_ENV, None)
            output = Path(tmp) / "site"
            with mock.patch.object(sys, "stderr", new_callable=io.StringIO):
                demo.build_demo(output)
            data = json.loads((output / "feeds" / "week-radar.json").read_text(encoding="utf-8"))
            self.assertEqual((data["schema_version"], len(data["weeks"])), (1, 1))
            self.assertFalse((output / "feeds" / "week-radar.xml").exists())
            self.assertEqual(publication.validate_public_output(output), [])


if __name__ == "__main__":
    unittest.main()
