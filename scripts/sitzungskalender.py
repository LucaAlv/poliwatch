"""The Bundestag's Sitzungskalender: planned Sitzungswochen for puls.html.

The calendar marks whole weeks, never sitting days, so this module only ever
says "Sitzungswoche". It reads the official ``.ics`` files linked from the
calendar page, keeps a small cache (``data/sitzungskalender.json``) and renders
the "Nächste Sitzungswoche" line of the puls.html header.

Source format: UNVERIFIED. The parser follows the planning notes in
docs/plans/todo-batch-7-puls-outward.md, which saw the real files only through
a summary (one all-day VEVENT per week, ``DTSTART;VALUE=DATE`` and an exclusive
``DTEND``, no VTIMEZONE). The tests run against a synthetic fixture
(tests/fixtures/sitzungskalender/). The first online build against the real
calendar is the first check of those assumptions; a changed layout fails soft
(a warning, the cache stays) and never breaks the build.

Only an online build refreshes the cache (``refresh_if_due``),
and only when it is due. ``--offline`` reads the cache and nothing else.
"""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import validate_dip_protocol as dip

INDEX_URL = "https://www.bundestag.de/parlament/plenum/sitzungskalender"
_INDEX_HOST = urlparse(INDEX_URL).hostname
CACHE_NAME = "sitzungskalender.json"
CACHE_VERSION = 1
#: At most this many .ics files are followed from the index page.
MAX_ICS_FILES = 4
#: A calendar year is only replaced by a parse with at least this many weeks.
MIN_WEEKS_PER_YEAR = 10
MAX_AGE_DAYS = 7

MONTHS = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)


class CalendarParseError(ValueError):
    """The calendar page or an .ics file does not look like what the parser expects."""


def _warn(message: str) -> None:
    print(f"warning: [sitzungskalender] {message}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Discovery and parsing
# ---------------------------------------------------------------------------


class _LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def discover_ics_urls(index_html: str) -> list[str]:
    """Absolute URLs of the ``.ics`` blobs linked from the calendar index page.

    Blob ids and file names change per year (the 2027 file's name says 2026),
    so a file is recognised by its path only; the year comes from its events.
    Duplicates are dropped and at most MAX_ICS_FILES are kept.
    """
    collector = _LinkCollector()
    collector.feed(index_html)
    urls: list[str] = []
    for href in collector.hrefs:
        try:
            absolute = urljoin(INDEX_URL, href.strip())
            parsed = urlparse(absolute)
        except ValueError:
            continue  # a malformed href (e.g. an unclosed IPv6 bracket) is skipped, the others still count
        # Only the Bundestag's own https blobs: a file:// or off-host link is never fetched.
        if parsed.scheme != "https" or parsed.hostname != _INDEX_HOST:
            continue
        path = parsed.path
        if path.lower().endswith(".ics") and "/resource/blob/" in path and absolute not in urls:
            urls.append(absolute)
    return urls[:MAX_ICS_FILES]


def _unfold(text: str) -> list[str]:
    """RFC 5545 unfolding: a line starting with a space or tab continues the previous one."""
    text = text.lstrip("﻿")
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def _ics_date(value: str, what: str) -> date:
    text = value.strip()
    if not re.fullmatch(r"\d{8}", text):
        raise CalendarParseError(f"{what} is not a plain date: {value!r}")
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:]))
    except ValueError as exc:
        raise CalendarParseError(f"{what} is not a valid date: {value!r}") from exc


def parse_ics(text: str) -> list[tuple[date, date]]:
    """The planned Sitzungswochen of one .ics file as (first day, last day), both inclusive.

    Only VEVENTs whose SUMMARY contains "Sitzungswoche" count. DTEND is
    exclusive in iCalendar, so the last day is DTEND - 1. Every week is checked:
    it starts on a weekday, ends after it starts, and stays within one ISO week.
    Raises CalendarParseError on anything else that does not fit.
    """
    lines = _unfold(text)
    if not any(line.strip().upper() == "BEGIN:VCALENDAR" for line in lines):
        raise CalendarParseError("not an iCalendar file (no BEGIN:VCALENDAR)")
    weeks: list[tuple[date, date]] = []
    event: dict[str, str] | None = None
    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()
        if upper == "BEGIN:VEVENT":
            if event is not None:
                raise CalendarParseError("nested VEVENT")
            event = {}
        elif upper == "END:VEVENT":
            if event is None:
                raise CalendarParseError("END:VEVENT without BEGIN:VEVENT")
            if "Sitzungswoche" in event.get("SUMMARY", ""):
                weeks.append(_week_from_event(event))
            event = None
        elif event is not None and ":" in stripped:
            name_part, _, value = stripped.partition(":")
            name = name_part.split(";", 1)[0].upper()
            event.setdefault(name, value)
    if event is not None:
        raise CalendarParseError("VEVENT without END:VEVENT")
    return weeks


def _week_from_event(event: dict[str, str]) -> tuple[date, date]:
    if "DTSTART" not in event or "DTEND" not in event:
        raise CalendarParseError("Sitzungswoche event without DTSTART or DTEND")
    start = _ics_date(event["DTSTART"], "DTSTART")
    end = _ics_date(event["DTEND"], "DTEND")
    if end <= start:
        raise CalendarParseError(f"Sitzungswoche ends before it starts: {start} to {end}")
    last = end - timedelta(days=1)
    if start.weekday() > 4:
        raise CalendarParseError(f"Sitzungswoche starts on a weekend: {start}")
    if start.isocalendar()[:2] != last.isocalendar()[:2]:
        raise CalendarParseError(f"Sitzungswoche spans two ISO weeks: {start} to {last}")
    return start, last


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def cache_path(output_dir: Path) -> Path:
    return output_dir / "data" / CACHE_NAME


def _valid_cache(payload: Any) -> bool:
    if not isinstance(payload, dict) or payload.get("version") != CACHE_VERSION:
        return False
    years = payload.get("years")
    if not isinstance(years, dict):
        return False
    for year, weeks in years.items():
        if not re.fullmatch(r"\d{4}", str(year)) or not isinstance(weeks, list):
            return False
        for pair in weeks:
            if not (isinstance(pair, list) and len(pair) == 2):
                return False
            try:
                date.fromisoformat(pair[0])
                date.fromisoformat(pair[1])
            except (TypeError, ValueError):
                return False
    return True


def load_cache(output_dir: Path) -> dict[str, Any] | None:
    """The cached calendar, or None when it is missing. A damaged file warns, gives None
    and is left in place (the next due refresh replaces it)."""
    path = cache_path(output_dir)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        _warn(f"{path.name} unreadable ({exc}); the next-Sitzungswoche line is left out")
        return None
    if not _valid_cache(payload):
        _warn(f"{path.name} has an unexpected shape; the next-Sitzungswoche line is left out")
        return None
    return payload


def _cached_weeks(cache: dict[str, Any] | None) -> list[tuple[date, date]]:
    weeks: list[tuple[date, date]] = []
    for pairs in ((cache or {}).get("years") or {}).values():
        weeks.extend((date.fromisoformat(a), date.fromisoformat(b)) for a, b in pairs)
    return sorted(weeks)


def _is_due(cache: dict[str, Any] | None, now: datetime, max_age_days: int = MAX_AGE_DAYS) -> bool:
    if cache is None:
        return True
    try:
        fetched = datetime.fromisoformat(str(cache["fetched_at"]))
    except (KeyError, ValueError):
        return True
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    age = now - fetched
    if age > timedelta(days=max_age_days):
        return True
    # From October on the next year's calendar is expected. Until it is listed,
    # look again at most once a day, so each online build does not fetch.
    if now.month >= 10 and str(now.year + 1) not in (cache.get("years") or {}) and age > timedelta(days=1):
        return True
    return False


def refresh_if_due(
    output_dir: Path,
    *,
    now: datetime | None = None,
    fetch_html: Callable[[str], str] = dip.fetch_html,
    fetch_text: Callable[[str], str] = dip.fetch_text,
    max_age_days: int = MAX_AGE_DAYS,
) -> None:
    """Refresh data/sitzungskalender.json when it is due. Never raises on a source failure.

    `now` is wall-clock UTC. It is never the build date: --today and
    SOURCE_DATE_EPOCH pin the page clock, and a frozen build must not decide
    whether a fetch happens. A year is replaced only by a parse with at least
    MIN_WEEKS_PER_YEAR weeks, all inside that year; the added and removed weeks
    go to stderr so a moved week shows in the log.
    """
    now = now or datetime.now(timezone.utc)
    cache = load_cache(output_dir)
    if not _is_due(cache, now, max_age_days):
        return
    try:
        _refresh(output_dir, cache, now, fetch_html, fetch_text)
    except (dip.DipError, CalendarParseError, OSError, ValueError) as exc:
        _warn(f"calendar not refreshed ({exc}); keeping the cached calendar")


def _refresh(
    output_dir: Path,
    cache: dict[str, Any] | None,
    now: datetime,
    fetch_html: Callable[[str], str],
    fetch_text: Callable[[str], str],
) -> None:
    index_html = fetch_html(INDEX_URL)
    urls = discover_ics_urls(index_html)
    if not urls:
        raise CalendarParseError("no .ics links on the calendar page (layout changed?)")
    years: dict[str, list[list[str]]] = {y: [list(p) for p in pairs] for y, pairs in ((cache or {}).get("years") or {}).items()}
    accepted = 0
    for url in urls:
        try:
            parsed = parse_ics(fetch_text(url))
        except (dip.DipError, CalendarParseError) as exc:
            _warn(f"{url}: {exc}")
            continue
        by_year: dict[int, list[tuple[date, date]]] = {}
        for start, last in parsed:
            by_year.setdefault(start.year, []).append((start, last))
        for year, weeks in sorted(by_year.items()):
            inside = all(last.year == year for _start, last in weeks)
            if len(weeks) < MIN_WEEKS_PER_YEAR or not inside:
                _warn(
                    f"{url}: {len(weeks)} weeks for {year} "
                    f"(need at least {MIN_WEEKS_PER_YEAR}, all inside the year); keeping the cached {year}"
                )
                continue
            years[str(year)] = [[start.isoformat(), last.isoformat()] for start, last in sorted(weeks)]
            accepted += 1
    if not accepted:
        raise CalendarParseError("no calendar year could be read")

    before = {w for pairs in ((cache or {}).get("years") or {}).values() for w in map(tuple, pairs)}
    after = {w for pairs in years.values() for w in map(tuple, pairs)}
    added, removed = sorted(after - before), sorted(before - after)
    payload = {
        "version": CACHE_VERSION,
        "fetched_at": now.astimezone(timezone.utc).replace(microsecond=0).isoformat(),
        "source": INDEX_URL,
        "ics_urls": urls,
        "years": {year: years[year] for year in sorted(years)},
    }
    path = cache_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    dip.write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    if cache is None:
        print(f"[sitzungskalender] angelegt: {len(after)} Sitzungswochen aus {len(urls)} Dateien", file=sys.stderr)
    elif added or removed:
        print(
            "[sitzungskalender] geändert: "
            f"+{len(added)} ({', '.join(a for a, _ in added) or '-'}), "
            f"-{len(removed)} ({', '.join(a for a, _ in removed) or '-'})",
            file=sys.stderr,
        )
    else:
        print(f"[sitzungskalender] unverändert: {len(after)} Sitzungswochen", file=sys.stderr)


# ---------------------------------------------------------------------------
# The header line
# ---------------------------------------------------------------------------


def _iso_week_label(day: date) -> str:
    return f"KW {day.isocalendar()[1]}"


def _range_parts(start: date, last: date) -> dict[str, str]:
    """Preformatted range, every string a reader sees, so the script only compares dates.

    "2.–6. November 2026"; across a month "30. November – 4. Dezember 2026";
    across a year the year shows on both ends.
    """
    if start == last:
        return {"start": "", "sep": "", "end": f"{last.day}. {MONTHS[last.month - 1]} {last.year}"}
    if (start.year, start.month) == (last.year, last.month):
        return {"start": f"{start.day}.", "sep": "–", "end": f"{last.day}. {MONTHS[last.month - 1]} {last.year}"}
    year = f" {start.year}" if start.year != last.year else ""
    return {
        "start": f"{start.day}. {MONTHS[start.month - 1]}{year}",
        "sep": " – ",
        "end": f"{last.day}. {MONTHS[last.month - 1]} {last.year}",
    }


def range_text(start: date, last: date) -> str:
    """The range as one string, "2.–6. November 2026" (the parts of `_range_parts` joined)."""
    parts = _range_parts(start, last)
    return f"{parts['start']}{parts['sep']}{parts['end']}"


def page_weeks(cache: dict[str, Any] | None, shown_week: tuple[int, int]) -> list[dict[str, str]]:
    """The planned weeks puls.html embeds: those ending on or after the shown week's Monday.

    Each entry is {"mon", "fri", "kw", "start", "sep", "end"}: the first and last day
    of the planned week as ISO dates (Monday and Friday in practice) and the
    preformatted range parts.
    """
    monday = date.fromisocalendar(shown_week[0], shown_week[1], 1)
    entries = []
    for start, last in _cached_weeks(cache):
        if last >= monday:
            entries.append({"mon": start.isoformat(), "fri": last.isoformat(), "kw": _iso_week_label(start), **_range_parts(start, last)})
    return entries


def _time(iso: str, text: str) -> str:
    return f'<time datetime="{html.escape(iso)}">{html.escape(text)}</time>'


def _range_html(week: dict[str, str]) -> str:
    start = _time(week["mon"], week["start"]) if week["start"] else ""
    return f'{start}{html.escape(week["sep"])}{_time(week["fri"], week["end"])}'


def gap_sentence(shown_kw: str, count: int) -> str:
    """The D4 clause: planned weeks after the shown week that lie entirely in the past."""
    if count <= 0:
        return ""
    if count == 1:
        return f". Seit {shown_kw} lag laut Sitzungskalender 1 weitere Sitzungswoche; sie ist hier noch nicht ausgewertet."
    return f". Seit {shown_kw} lagen laut Sitzungskalender {count} weitere Sitzungswochen; sie sind hier noch nicht ausgewertet."


def next_sitting_state(weeks: list[dict[str, str]], *, shown_week: tuple[int, int], today: date) -> dict[str, Any]:
    """Which line a reader on `today` gets. Mirrored by NEXT_SITTING_SCRIPT, so keep them in step.

    {"hidden": bool, "lead": str, "week": the planned week or None, "gap": int}.
    """
    shown_mon = date.fromisocalendar(shown_week[0], shown_week[1], 1)
    shown_end = shown_mon + timedelta(days=6)
    now = today.isoformat()
    upcoming = next((w for w in weeks if w["fri"] >= now), None)
    if upcoming is None:
        return {"hidden": True, "lead": "Nächste Sitzungswoche:", "week": None, "gap": 0}
    running = upcoming["mon"] <= now
    is_shown_week = upcoming["mon"] <= shown_end.isoformat() and upcoming["fri"] >= shown_mon.isoformat()
    if running and is_shown_week:
        return {"hidden": True, "lead": "Nächste Sitzungswoche:", "week": None, "gap": 0}
    gap = sum(1 for w in weeks if w["mon"] > shown_end.isoformat() and w["fri"] < now)
    return {
        "hidden": False,
        "lead": "Sitzungswoche läuft:" if running else "Nächste Sitzungswoche:",
        "week": upcoming,
        "gap": gap,
    }


def render_next_sitting(weeks: list[dict[str, str]], *, shown_week: tuple[int, int], today: date) -> str:
    """The header paragraph, or "" when no planned week ends on or after the shown week.

    With at least one planned week the paragraph, its data and (via
    NEXT_SITTING_SCRIPT) the script are always emitted; only `hidden` and the
    slot texts differ between states, so a page built during a running week
    still shows the next week to a reader one week later. The text is the
    no-script fallback for the build date.
    """
    if not weeks:
        return ""
    shown_mon = date.fromisocalendar(shown_week[0], shown_week[1], 1)
    state = next_sitting_state(weeks, shown_week=shown_week, today=today)
    week = state["week"]
    shown_kw = f"KW {shown_week[1]}"
    data = html.escape(json.dumps(weeks, ensure_ascii=False, separators=(",", ":")), quote=True)
    range_html = _range_html(week) if week else ""
    kw_text = f"({week['kw']})" if week else ""
    gap_text = gap_sentence(shown_kw, state["gap"])
    hidden = " hidden" if state["hidden"] else ""
    return (
        f'<p class="next-sitting"{hidden} data-sitzungswochen=\'{data}\' '
        f'data-shown-week="{shown_mon.isoformat()}" data-shown-end="{(shown_mon + timedelta(days=6)).isoformat()}" '
        f'data-shown-kw="{html.escape(shown_kw)}">'
        f'<span data-next-sitting-lead>{html.escape(state["lead"])}</span> '
        f'<span class="next-sitting-range" data-next-sitting-range>{range_html}</span> '
        f'<span data-next-sitting-kw>{html.escape(kw_text)}</span>, '
        f'laut <a href="{INDEX_URL}">Sitzungskalender</a>'
        f'<span data-next-sitting-gap>{html.escape(gap_text)}</span></p>'
    )


NEXT_SITTING_STYLE = """
    .next-sitting { margin:8px 0 0; max-width:860px; font-size:15px; line-height:1.5; color:var(--muted); }
    .next-sitting-range { color:var(--ink); font-weight:650; white-space:nowrap; }"""

# Picks the line for the reader's date in Europe/Berlin. The build's own text is
# the fallback: the script changes the three slots, the hidden flag and nothing
# else, never uses innerHTML, and leaves the fallback on any error.
NEXT_SITTING_SCRIPT = """
  <script>
    (function () {
      try {
        var p = document.querySelector('p.next-sitting[data-sitzungswochen]');
        if (!p) return;
        var weeks = JSON.parse(p.getAttribute('data-sitzungswochen'));
        var shownMon = p.getAttribute('data-shown-week');
        var shownEnd = p.getAttribute('data-shown-end');
        var shownKw = p.getAttribute('data-shown-kw');
        var today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Berlin' }).format(new Date());
        if (!/^\\d{4}-\\d{2}-\\d{2}$/.test(today)) return;
        var next = null;
        for (var i = 0; i < weeks.length; i++) { if (weeks[i].fri >= today) { next = weeks[i]; break; } }
        if (!next) { p.hidden = true; return; }
        var running = next.mon <= today;
        if (running && next.mon <= shownEnd && next.fri >= shownMon) { p.hidden = true; return; }
        var slot = function (name) { return p.querySelector('[data-next-sitting-' + name + ']'); };
        var time = function (iso, text) {
          var el = document.createElement('time');
          el.setAttribute('datetime', iso);
          el.textContent = text;
          return el;
        };
        slot('lead').textContent = running ? 'Sitzungswoche läuft:' : 'Nächste Sitzungswoche:';
        var range = slot('range');
        while (range.firstChild) range.removeChild(range.firstChild);
        if (next.start) range.appendChild(time(next.mon, next.start));
        range.appendChild(document.createTextNode(next.sep));
        range.appendChild(time(next.fri, next.end));
        slot('kw').textContent = '(' + next.kw + ')';
        var gap = 0;
        for (var j = 0; j < weeks.length; j++) { if (weeks[j].mon > shownEnd && weeks[j].fri < today) gap++; }
        slot('gap').textContent = gap === 0 ? '' : gap === 1
          ? '. Seit ' + shownKw + ' lag laut Sitzungskalender 1 weitere Sitzungswoche; sie ist hier noch nicht ausgewertet.'
          : '. Seit ' + shownKw + ' lagen laut Sitzungskalender ' + gap + ' weitere Sitzungswochen; sie sind hier noch nicht ausgewertet.';
        p.hidden = false;
      } catch (error) { /* keep the build's own line */ }
    })();
  </script>"""
