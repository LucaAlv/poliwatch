"""The week radar as data: ``feeds/week-radar.json`` and, once a domain exists, an RSS feed.

puls.html shows the newest sitting week. This module renders the same rows
(``week_topic_rows``, one computation) a second way, for the newest 12 weeks:
a versioned JSON file and an RSS 2.0 feed with one item per finished week.

RSS needs absolute URLs and there is no domain yet. The JSON is always written;
``feeds/week-radar.xml`` only when ``BUNDESTAG_PULSE_SITE_URL`` holds an
absolute https URL ending in "/". A build without it deletes an older feed, so
a stale one cannot be deployed.

Design record: docs/plans/todo-batch-7-puls-outward.md (item 2). This module
does not import build_dip_pulse_site: the dossier link function is passed in.
"""

from __future__ import annotations

import html
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import derive
import render_dip_pulse_html as pulse_html
import sitzungskalender
import validate_dip_protocol as dip

SCHEMA_VERSION = 1
FEEDS_DIR = "feeds"
JSON_NAME = "week-radar.json"
RSS_NAME = "week-radar.xml"
SITE_URL_ENV = "BUNDESTAG_PULSE_SITE_URL"
#: The page title of puls.html ("Bundestag-Puls · Wochenübersicht"); one place to change on a rename.
CHANNEL_TITLE = "Bundestag-Puls · Wochenübersicht"
CHANNEL_DESCRIPTION = "Die Tagesordnungspunkte mit den meisten Reden je Sitzungswoche des Deutschen Bundestages."
WEEKS_BACK = 12
ITEM_TITLE_CHARS = 90
STABILITY = (
    "Fields are only added within schema_version 1; a rename, removal or meaning change raises "
    "schema_version. Links are relative to the site root. Weeks are newest first. "
    "In speeches_by_group, sprechrolle holds the release's codes (bundesregierung, bundesrat, weitere); "
    "a Rede in a Sprechrolle is counted on that side only, so a row need not equal "
    "GROUP BY fraktion, sprechrolle on the release."
)
_BERLIN = ZoneInfo("Europe/Berlin")
#: The radar names a Sprechrolle side by its display label; the release stores the code.
_ROLE_CODES = {label: code for code, label in derive.SPRECHROLLE_LABELS.items()}


def week_id(week: tuple[int, int]) -> str:
    return f"{week[0]}-W{week[1]:02d}"


def speeches_by_group(party_counts: Counter[str]) -> list[dict[str, Any]]:
    """Redeanteil je Zusammenschluss as the release's ``speeches.fraktion`` / ``sprechrolle`` columns.

    A radar label among the Sprechrolle sides goes to ``sprechrolle`` as the release's code
    ("Bundesregierung" -> "bundesregierung", ``fraktion`` null); the display label stays on the page.
    "Unbekannt" is the radar's word for a Rede whose protocol names no Zusammenschluss;
    the store holds that as NULL, so both columns are null. Every other label, "fraktionslos"
    included, is a ``fraktion``. Sorted by count descending, then label.
    """
    rows = []
    for label, count in sorted(party_counts.items(), key=lambda item: (-item[1], item[0])):
        if label in _ROLE_CODES:
            fraktion, sprechrolle = None, _ROLE_CODES[label]
        elif label == "Unbekannt":
            fraktion, sprechrolle = None, None
        else:
            fraktion, sprechrolle = label, None
        rows.append({"fraktion": fraktion, "sprechrolle": sprechrolle, "speech_count": int(count)})
    return rows


def _share(value: float) -> float:
    return round(value, 1)


def _row_payload(row: dict[str, Any]) -> dict[str, Any]:
    identity = row["identity"]
    trace = None
    if row["trace"]:
        first = row["trace"]["first"]
        first_href = None
        if first.get("page_path"):
            first_href = f"protocols/{Path(first['page_path']).name}#top-{first['index']}"
        trace = {
            "vorgang_id": row["trace"]["vorgang_id"],
            "first_week": week_id(first["week"]),
            "first_position": first.get("vorgangsposition") or None,
            "first_href": first_href,
            "current_position": row["trace"]["current_position"] or None,
        }
    return {
        "href": f"{row['dossier_href']}#top-{row['index']}",
        "dokumentnummer": row["dokumentnummer"],
        "datum": row["datum"],
        "top_index": row["index"],
        "top_id": row["top_id"],
        "heading": " ".join(str(row.get("heading") or "").split()),
        "type_label": pulse_html.type_label(identity),
        "lead_title": identity["lead_title"],
        "equal_weight": bool(identity["equal_weight"]),
        "titles": list(identity["titles"]),
        "procedures": [
            {
                "vorgang_id": p["vorgang_id"],
                "titel": p["titel"],
                "vorgangstyp": p["vorgangstyp"],
                "vorgangsposition": p["vorgangsposition"],
            }
            for p in identity["procedures"]
        ],
        "speech_count": int(row["speech_count"]),
        "share_percent": _share(row["share"]),
        "speeches_by_group": speeches_by_group(row["party_counts"]),
        "attributed_speech_count": int(row["party_total"]),
        "trace": trace,
        "has_votes": bool(row["has_votes"]),
    }


def _week_payload(
    week: tuple[int, int],
    week_entries: list[dict[str, Any]],
    occurrences: dict[str, list[dict[str, Any]]],
    *,
    today: date,
    vorgang_cache: dict[str, Any] | None,
    dossier_href_for: Callable[[dict[str, Any]], str],
) -> dict[str, Any]:
    stats = pulse_html.week_stats(week, week_entries)
    radar = pulse_html.week_topic_rows(
        week_entries, occurrences, total=stats["speech_count"], dossier_href_for=dossier_href_for,
        vorgang_cache=vorgang_cache,
    )
    monday = date.fromisocalendar(week[0], week[1], 1)
    sunday = monday + timedelta(days=6)
    by_page = {entry.get("page_path"): entry for entry in week_entries}

    def unranked(item: tuple[str, Any, int]) -> dict[str, Any]:
        document, page_path, count = item
        entry = by_page.get(page_path)
        return {"dokumentnummer": document, "href": dossier_href_for(entry) if entry else None, "count": int(count)}

    return {
        "week": week_id(week),
        "label": pulse_html.week_label(week),
        "monday": monday.isoformat(),
        "sunday": sunday.isoformat(),
        "running": monday <= today <= sunday,
        "speech_count": int(stats["speech_count"]),
        "top_count": int(stats["top_count"]),
        "sittings": [
            {
                "dokumentnummer": str(pulse_html._entry_protocol(entry).get("dokumentnummer") or "").strip() or None,
                "datum": pulse_html._entry_protocol(entry).get("datum"),
                "href": dossier_href_for(entry),
            }
            for entry in week_entries
        ],
        "rows": [_row_payload(row) for row in radar["rows"]],
        "question_formats": [
            {
                "heading": item["heading"],
                "speech_count": int(item["speech_count"]),
                "share_percent": _share(item["share"]),
                "href": item["href"],
            }
            for item in radar["formats"]
        ],
        "unranked": [unranked(item) for item in radar["remaining"]],
    }


def build_payload(
    entries: list[dict[str, Any]],
    *,
    today: date,
    week: tuple[int, int] | None,
    vorgang_cache: dict[str, Any] | None,
    dossier_href_for: Callable[[dict[str, Any]], str],
    weeks_back: int = WEEKS_BACK,
    site_url: str | None = None,
) -> dict[str, Any]:
    """Schema 1: the selected week and the weeks before it, newest first.

    The selected week is `week`, else the newest, exactly like select_pulse_week,
    so a --week build stays frozen. Nothing from a row (item, stats, Counter) is
    dumped as is: every field is named here.
    """
    weeks = pulse_html.group_entries_by_week(entries)
    if week is not None and weeks and week not in weeks:
        raise ValueError(f"week {week_id(week)} is not in the archive")
    selected = week if week is not None else (max(weeks) if weeks else None)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "stability": STABILITY,
        "build_date": today.isoformat(),
        "site_url": site_url,
        "weeks": [],
    }
    if selected is None:
        return payload
    # One occurrence index for every week: topic_row keeps only occurrences of an
    # earlier week, so an older week's trace is the same as with its own index.
    occurrences = pulse_html.vorgang_occurrences(weeks, selected)
    shown = [key for key in sorted(weeks) if key <= selected][-weeks_back:]
    payload["weeks"] = [
        _week_payload(
            key, weeks[key], occurrences, today=today, vorgang_cache=vorgang_cache, dossier_href_for=dossier_href_for
        )
        for key in reversed(shown)
    ]
    return payload


def valid_site_url(value: str | None) -> bool:
    """An absolute https URL with a host, ending in "/"."""
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and value.endswith("/") and not parsed.query and not parsed.fragment


def _berlin_midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=_BERLIN)


def _cut(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _item_title(week: dict[str, Any]) -> str:
    """"KW 43/2026: <top topic> und N weitere Themen". An equal-weight top row is named by its
    type label, so no single Fraktion's Antrag title is promoted."""
    rows = week["rows"]
    if not rows:
        return f"{week['label']}: Wochenübersicht"
    first = rows[0]
    topic = (first["type_label"] if first["equal_weight"] else first["lead_title"]) or first["heading"] or first["top_id"] or ""
    title = f"{week['label']}: {_cut(topic, ITEM_TITLE_CHARS)}"
    rest = len(rows) - 1
    if rest:
        title += f" und {rest} weitere Themen" if rest > 1 else " und 1 weiteres Thema"
    return title


def _item_description(week: dict[str, Any], site_url: str) -> str:
    esc = html.escape

    def link(href: str, text: str) -> str:
        return f'<a href="{esc(site_url + href)}">{esc(text)}</a>'

    monday = date.fromisoformat(week["monday"])
    span = sitzungskalender.range_text(monday, monday + timedelta(days=4))
    counts = (
        f"{pulse_html.format_count(week['speech_count'], 'Rede', 'Reden')} in "
        f"{pulse_html.format_count(week['top_count'], 'Tagesordnungspunkt', 'Tagesordnungspunkten')}"
    )
    parts = [f"<p>{esc(span)} · {esc(counts)}</p>"]
    items = []
    for row in week["rows"]:
        share = f"{row['share_percent']:.1f}".replace(".", ",")
        amount = f"{pulse_html.format_count(row['speech_count'], 'Rede', 'Reden')} · {share} %"
        if row["equal_weight"]:
            shown = row["titles"][: pulse_html.RADAR_SIBLINGS]
            more = len(row["titles"]) - len(shown)
            titles = " · ".join(esc(title) for title in shown) + (f" · und {more} weitere" if more > 0 else "")
            head = f"{link(row['href'], row['type_label'])}: {titles}"
        else:
            head = link(row["href"], row["lead_title"] or row["heading"] or row["top_id"] or "")
        items.append(f"<li>{head} — {esc(amount)}</li>")
    if items:
        parts.append(f"<ul>{''.join(items)}</ul>")
    parts.append(f"<p>Anteil an allen {esc(pulse_html.format_count(week['speech_count'], 'Rede', 'Reden'))} der Woche</p>")
    sources = ", ".join(
        link(sitting["href"], sitting["dokumentnummer"] or "Protokoll") for sitting in week["sittings"]
    )
    noun = "Plenarprotokoll" if len(week["sittings"]) == 1 else "Plenarprotokolle"
    parts.append(f"<p>Quelle: Deutscher Bundestag, {noun} {sources}</p>")
    return "".join(parts)


def render_rss(payload: dict[str, Any], site_url: str) -> str:
    """RSS 2.0, one item per finished week (its Sunday is before the build date).

    A running week's content changes under one GUID, so it never gets an item. The
    item link is the week's newest dossier, since there is no per-week page.
    """
    build_date = date.fromisoformat(payload["build_date"])
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = CHANNEL_TITLE
    ET.SubElement(channel, "link").text = site_url + "puls.html"
    ET.SubElement(channel, "description").text = CHANNEL_DESCRIPTION
    ET.SubElement(channel, "language").text = "de"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(_berlin_midnight(build_date))
    for week in payload["weeks"]:
        sunday = date.fromisoformat(week["sunday"])
        if sunday >= build_date or not week["sittings"]:
            continue
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = _item_title(week)
        ET.SubElement(item, "link").text = site_url + week["sittings"][-1]["href"]
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = week["week"]
        ET.SubElement(item, "pubDate").text = format_datetime(_berlin_midnight(sunday + timedelta(days=1)))
        ET.SubElement(item, "description").text = _item_description(week, site_url)
    ET.indent(rss)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="unicode") + "\n"


def write(
    output_dir: Path,
    entries: list[dict[str, Any]],
    *,
    today: date,
    week: tuple[int, int] | None,
    vorgang_cache: dict[str, Any] | None,
    dossier_href_for: Callable[[dict[str, Any]], str],
) -> None:
    """Write feeds/week-radar.json always; feeds/week-radar.xml only with a valid site URL.

    Without one an existing feed is deleted, so a build without the variable cannot
    leave a stale feed to be deployed.
    """
    configured = os.environ.get(SITE_URL_ENV)
    site_url = configured if valid_site_url(configured) else None
    payload = build_payload(
        entries, today=today, week=week, vorgang_cache=vorgang_cache, dossier_href_for=dossier_href_for,
        site_url=site_url,
    )
    feeds = output_dir / FEEDS_DIR
    feeds.mkdir(parents=True, exist_ok=True)
    dip.write_text_atomic(feeds / JSON_NAME, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n")
    rss_path = feeds / RSS_NAME
    if site_url:
        dip.write_text_atomic(rss_path, render_rss(payload, site_url))
        rss_note = f"RSS {FEEDS_DIR}/{RSS_NAME}"
    else:
        rss_path.unlink(missing_ok=True)
        if configured:
            print(
                f"warning: [week-radar] {SITE_URL_ENV} muss eine absolute https-URL mit abschließendem / sein, "
                f"war {configured!r}; kein RSS",
                file=sys.stderr,
            )
        rss_note = f"RSS übersprungen ({SITE_URL_ENV} nicht gesetzt)" if not configured else "RSS übersprungen (ungültige URL)"
    weeks = pulse_html.format_count(len(payload["weeks"]), "Woche", "Wochen")
    print(f"week-radar: {rss_note}; {weeks} in {FEEDS_DIR}/{JSON_NAME}", file=sys.stderr)
