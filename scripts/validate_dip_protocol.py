#!/usr/bin/env python3
"""Validate DIP plenary protocol extraction.

This is an exploratory script for the Bundestag Pulse "Assignment": take one
official Plenarprotokoll XML as the canonical transcript and enrich it with DIP
API metadata for proceedings, activities, people, and linked Drucksachen.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any, Callable


BASE_URL = "https://search.dip.bundestag.de/api/v1"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
GEMINI_GENERATE_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/{model}:generateContent"
# Re-verify fallback IDs against the official Anthropic and Gemini model lists before changing.
DEFAULT_ANTHROPIC_SUMMARY_MODELS = ("claude-opus-4-8", "claude-sonnet-5")
DEFAULT_GEMINI_SUMMARY_MODELS = ("gemini-3.5-flash",)
BT_BASE_URL = "https://www.bundestag.de"
DEFAULT_ROLL_CALL_LIST_PATH = "/ajax/filterlist/de/parlament/plenum/abstimmung/484422-484422"
ROLL_CALL_LIST_PATH_PREFIX = "/ajax/filterlist/de/parlament/plenum/abstimmung"
DEFAULT_ROLL_CALL_LIST_ID = DEFAULT_ROLL_CALL_LIST_PATH.rsplit("/", 1)[-1]
ROLL_CALL_LIST_ID_ENV = "BT_ROLL_CALL_LIST_ID"
ROLL_CALL_LIST_PARSE_WARNING = (
    "Die Abstimmungs-Listenseite lieferte HTML, aber keine parsebaren Einträge; "
    "vermutlich hat sich das Seitenformat oder die Filterlisten-ID geändert."
)
QUADRANT_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4}
VOTE_KEYS = ("yes", "no", "abstain", "absent")
SUMMARY_CHUNK_MIN = 3
SUMMARY_CHUNK_MAX = 5
SUMMARY_CHUNK_CHARS = 900
# Gemini's default models are reasoning models whose internal "thinking" tokens
# count against maxOutputTokens. The short JSON answer needs ~150 tokens, but the
# thinking phase alone can spend 400-600+, so a low cap truncates the response to
# invalid JSON. Keep a generous budget so both thinking and the answer fit.
GEMINI_SUMMARY_MAX_OUTPUT_TOKENS = 2048
ANTHROPIC_SUMMARY_MAX_OUTPUT_TOKENS = 400


class DipError(RuntimeError):
    pass


class SummaryError(RuntimeError):
    pass


@dataclass(frozen=True)
class RollCallCandidateFetch:
    candidates: list[dict[str, Any]]
    list_html_seen: bool
    parsed_entry_count: int
    selector_warning: bool


def load_local_env(path: Path | None = None) -> None:
    """Load local .env.local variables without overriding exported values."""
    env_path = path or Path(__file__).resolve().parent.parent / ".env.local"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        try:
            parts = shlex.split(line, comments=True, posix=True)
        except ValueError:
            continue
        if not parts or "=" not in parts[0]:
            continue
        key, value = parts[0].split("=", 1)
        if key and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class ApiClient:
    api_key: str
    base_url: str = BASE_URL
    sleep_seconds: float = 0.0
    timeout: int = 60
    retries: int = 2
    retry_delay_seconds: float = 1.5

    def _retry_delay(self, path: str, exc: BaseException, attempt: int) -> None:
        delay = self.retry_delay_seconds * (attempt + 1)
        print(
            f"warning: DIP API request failed for {path}: {exc}; "
            f"retrying {attempt + 2}/{self.retries + 1} in {delay:g}s.",
            file=sys.stderr,
        )
        time.sleep(delay)

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        params = dict(params or {})
        params["apikey"] = self.api_key
        params.setdefault("format", "json")
        url = f"{self.base_url}{path}?{urllib.parse.urlencode(params, doseq=True)}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        for attempt in range(self.retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as res:
                    data = json.loads(res.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                if exc.code in {429, 500, 502, 503, 504} and attempt < self.retries:
                    self._retry_delay(path, exc, attempt)
                    continue
                raise DipError(f"DIP API HTTP {exc.code} for {path}: {body[:500]}") from exc
            except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
                if attempt < self.retries:
                    self._retry_delay(path, exc, attempt)
                    continue
                raise DipError(f"DIP API request failed for {path}: {exc}") from exc
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)
        return data

    def list_all(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        params = dict(params or {})
        documents: list[dict[str, Any]] = []
        previous_cursor = None
        while True:
            page = self.get_json(path, params)
            batch = page.get("documents") or []
            documents.extend(batch)
            cursor = page.get("cursor")
            if not batch or not cursor or cursor == previous_cursor:
                break
            previous_cursor = cursor
            params["cursor"] = cursor
        return documents


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"Accept": "application/xml,text/xml,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return res.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise DipError(f"Failed to fetch XML {url}: {exc}") from exc


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return res.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise DipError(f"Failed to fetch HTML {url}: {exc}") from exc


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str], api_name: str = "LLM API") -> Any:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SummaryError(f"{api_name} HTTP {exc.code}: {body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise SummaryError(f"{api_name} request failed: {exc}") from exc


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def clamp_text(value: str, limit: int) -> str:
    value = clean_text(value)
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def strip_tags(value: str | None) -> str:
    if not value:
        return ""
    return clean_text(unescape(re.sub(r"<[^>]+>", " ", value)))


def iso_date(value: str | None) -> str | None:
    if not value:
        return None
    value = clean_text(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    match = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", value)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    return None


def elem_text(elem: ET.Element | None) -> str:
    if elem is None:
        return ""
    return clean_text("".join(elem.itertext()))


def child_text(elem: ET.Element, path: str) -> str:
    return elem_text(elem.find(path))


def page_sort_key(page: dict[str, Any]) -> tuple[int, int]:
    return (int(page.get("page") or 0), QUADRANT_ORDER.get(str(page.get("quadrant") or ""), 0))


def page_number(value: str | int | None) -> int | None:
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None


def extract_drucksachen(elem: ET.Element) -> list[dict[str, str | None]]:
    docs: list[dict[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for anchor in elem.findall(".//a"):
        href = anchor.attrib.get("href")
        text = elem_text(anchor)
        candidates = re.findall(r"\b\d{1,2}/\d{1,6}\b", text)
        for number in candidates:
            key = (number, href)
            if key not in seen:
                docs.append({"dokumentnummer": number, "url": href})
                seen.add(key)
    return docs


def parse_redner(redner: ET.Element | None) -> dict[str, Any] | None:
    if redner is None:
        return None
    name = redner.find("name")
    if name is None:
        return {"xml_redner_id": redner.attrib.get("id"), "display_name": elem_text(redner)}

    title = child_text(name, "titel")
    first = child_text(name, "vorname")
    last = child_text(name, "nachname")
    fraction = child_text(name, "fraktion") or None
    role_long = child_text(name, "rolle/rolle_lang") or None
    role_short = child_text(name, "rolle/rolle_kurz") or None
    parts = [part for part in (title, first, last) if part]
    display_name = clean_text(" ".join(parts)) or elem_text(redner)
    return {
        "xml_redner_id": redner.attrib.get("id"),
        "display_name": display_name,
        "first_name": first or None,
        "last_name": last or None,
        "fraktion": fraction,
        "role": role_long,
        "role_short": role_short,
    }


def parse_toc(root: ET.Element) -> dict[str, dict[str, Any]]:
    toc: dict[str, dict[str, Any]] = {}
    for block in root.findall("./vorspann/inhaltsverzeichnis/ivz-block"):
        title = elem_text(block.find("ivz-block-titel"))
        pages: list[dict[str, Any]] = []
        rid_pages: dict[str, dict[str, Any]] = {}
        for xref in block.findall(".//xref"):
            rid = xref.attrib.get("rid")
            page = page_number(xref.attrib.get("pnr") or child_text(xref, ".//seite"))
            quadrant = xref.attrib.get("div") or child_text(xref, ".//seitenbereich") or None
            if page is None:
                continue
            page_ref = {"page": page, "quadrant": quadrant}
            pages.append(page_ref)
            if rid:
                rid_pages[rid] = page_ref
        key = title or f"toc-block-{len(toc) + 1}"
        toc[key] = {
            "title": title,
            "drucksachen": extract_drucksachen(block),
            "pages": sorted(pages, key=page_sort_key),
            "rid_pages": rid_pages,
        }
    return toc


def speech_text_and_paragraphs(rede: ET.Element) -> tuple[str, list[str]]:
    paragraphs: list[str] = []
    for paragraph in rede.findall("p"):
        if paragraph.attrib.get("klasse") == "redner":
            continue
        text = elem_text(paragraph)
        if text:
            paragraphs.append(text)
    return clean_text(" ".join(paragraphs)), paragraphs


def parse_protocol_xml(xml_text: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    toc = parse_toc(root)
    rid_pages: dict[str, dict[str, Any]] = {}
    for block in toc.values():
        rid_pages.update(block["rid_pages"])

    agenda_items: list[dict[str, Any]] = []
    for index, top in enumerate(root.findall("./sitzungsverlauf/tagesordnungspunkt"), start=1):
        heading_lines: list[str] = []
        transfer_lines: list[str] = []
        for paragraph in top.findall("p"):
            klass = paragraph.attrib.get("klasse", "")
            if klass in {"T_NaS", "T_fett"}:
                text = elem_text(paragraph)
                if text:
                    heading_lines.append(text)
            elif klass == "T_Ueberweisung":
                text = elem_text(paragraph)
                if text:
                    transfer_lines.append(text)

        speeches: list[dict[str, Any]] = []
        pages: list[dict[str, Any]] = []
        for rede in top.findall("rede"):
            rid = rede.attrib.get("id")
            redner = parse_redner(rede.find("./p[@klasse='redner']/redner"))
            text, paragraphs = speech_text_and_paragraphs(rede)
            page_ref = rid_pages.get(rid or "")
            if page_ref:
                pages.append(page_ref)
            speeches.append(
                {
                    "rede_id": rid,
                    "source_page": page_ref,
                    "speaker": redner,
                    "paragraph_count": len(paragraphs),
                    "char_count": len(text),
                    "text": text,
                    "paragraphs": paragraphs,
                    "snippet": text[:240],
                }
            )

        sorted_pages = sorted(pages, key=page_sort_key)
        agenda_items.append(
            {
                "index": index,
                "top_id": top.attrib.get("top-id"),
                "heading": clean_text(" ".join(heading_lines)),
                "drucksachen": extract_drucksachen(top),
                "ueberweisung": transfer_lines,
                "page_range": {
                    "start": sorted_pages[0] if sorted_pages else None,
                    "end": sorted_pages[-1] if sorted_pages else None,
                },
                "speeches": speeches,
            }
        )

    return {
        "xml_protocol": {
            "wahlperiode": root.attrib.get("wahlperiode"),
            "sitzung_nr": root.attrib.get("sitzung-nr"),
            "sitzung_datum": root.attrib.get("sitzung-datum"),
            "sitzung_start": root.attrib.get("sitzung-start-uhrzeit"),
            "sitzung_end": root.attrib.get("sitzung-ende-uhrzeit"),
            "start_page": root.attrib.get("start-seitennr"),
        },
        "toc_block_count": len(toc),
        "agenda_items": agenda_items,
    }


def find_protocol(client: ApiClient, protocol_id: str | None, document_number: str | None) -> dict[str, Any]:
    if protocol_id:
        return client.get_json(f"/plenarprotokoll/{protocol_id}")

    params: dict[str, Any] = {"f.zuordnung": "BT"}
    if document_number:
        params["f.dokumentnummer"] = document_number
    documents = client.list_all("/plenarprotokoll", params)
    if not documents:
        selector = f"document number {document_number}" if document_number else "latest BT protocol"
        raise DipError(f"No Plenarprotokoll found for {selector}")
    return documents[0]


def norm_title(value: str | None) -> str:
    value = clean_text(value).lower()
    value = re.sub(r"[^a-zäöüß0-9]+", " ", value)
    return clean_text(value)


def overlaps(top: dict[str, Any], position: dict[str, Any]) -> bool:
    page_range = top.get("page_range") or {}
    start_ref = page_range.get("start")
    end_ref = page_range.get("end")
    if not start_ref or not end_ref:
        return False
    top_start = page_number(start_ref.get("page"))
    top_end = page_number(end_ref.get("page"))
    fundstelle = position.get("fundstelle") or {}
    pos_start = page_number(fundstelle.get("anfangsseite") or fundstelle.get("seite"))
    pos_end = page_number(fundstelle.get("endseite") or fundstelle.get("seite") or pos_start)
    if None in {top_start, top_end, pos_start, pos_end}:
        return False
    return int(pos_start) <= int(top_end) and int(pos_end) >= int(top_start)


def title_matches(heading: str | None, title: str | None) -> bool:
    heading_norm = norm_title(heading)
    title_norm = norm_title(title)
    if not heading_norm or not title_norm:
        return False
    if title_norm in heading_norm or heading_norm in title_norm:
        return True
    title_tokens = {token for token in title_norm.split() if len(token) > 4}
    heading_tokens = {token for token in heading_norm.split() if len(token) > 4}
    if not title_tokens:
        return False
    return len(title_tokens & heading_tokens) / len(title_tokens) >= 0.65


def activity_page(activity: dict[str, Any]) -> int | None:
    fundstelle = activity.get("fundstelle") or {}
    return page_number(fundstelle.get("seite") or fundstelle.get("anfangsseite"))


def activity_in_top(activity: dict[str, Any], top: dict[str, Any]) -> bool:
    page = activity_page(activity)
    page_range = top.get("page_range") or {}
    start_ref = page_range.get("start")
    end_ref = page_range.get("end")
    if page is None or not start_ref or not end_ref:
        return False
    start = page_number(start_ref.get("page"))
    end = page_number(end_ref.get("page"))
    return start is not None and end is not None and start <= page <= end


def compact_position(position: dict[str, Any]) -> dict[str, Any]:
    fundstelle = position.get("fundstelle") or {}
    return {
        "id": position.get("id"),
        "vorgang_id": position.get("vorgang_id"),
        "vorgangsposition": position.get("vorgangsposition"),
        "vorgangstyp": position.get("vorgangstyp"),
        "titel": position.get("titel"),
        "dokumentart": position.get("dokumentart"),
        "aktivitaet_anzahl": position.get("aktivitaet_anzahl"),
        "source": {
            "dokumentnummer": fundstelle.get("dokumentnummer"),
            "seite": fundstelle.get("seite"),
            "anfangsseite": fundstelle.get("anfangsseite"),
            "endseite": fundstelle.get("endseite"),
            "pdf_url": fundstelle.get("pdf_url"),
            "xml_url": fundstelle.get("xml_url"),
        },
        "mitberaten": position.get("mitberaten") or [],
    }


def compact_activity(activity: dict[str, Any]) -> dict[str, Any]:
    fundstelle = activity.get("fundstelle") or {}
    return {
        "id": activity.get("id"),
        "aktivitaetsart": activity.get("aktivitaetsart"),
        "titel": activity.get("titel"),
        "person_id": activity.get("person_id"),
        "seite": fundstelle.get("seite"),
        "pdf_url": fundstelle.get("pdf_url"),
        "vorgangsbezug_anzahl": activity.get("vorgangsbezug_anzahl"),
    }


def compact_person(person: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": person.get("id"),
        "titel": person.get("titel"),
        "namenszusatz": person.get("namenszusatz"),
        "vorname": person.get("vorname"),
        "nachname": person.get("nachname"),
        "fraktion": person.get("fraktion"),
        "funktion": person.get("funktion"),
        "wahlperiode": person.get("wahlperiode"),
        "basisdatum": person.get("basisdatum"),
        "aktualisiert": person.get("aktualisiert"),
    }


def compact_drucksache_position(position: dict[str, Any]) -> dict[str, Any]:
    fundstelle = position.get("fundstelle") or {}
    return {
        "vorgang_id": position.get("vorgang_id"),
        "vorgangsposition_id": position.get("id"),
        "vorgangsposition": position.get("vorgangsposition"),
        "titel": position.get("titel"),
        "dokumentnummer": fundstelle.get("dokumentnummer"),
        "drucksachetyp": fundstelle.get("drucksachetyp"),
        "datum": fundstelle.get("datum"),
        "url": fundstelle.get("pdf_url"),
        "urheber": fundstelle.get("urheber") or [],
    }


def unique_by(items: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        key = tuple(item.get(k) for k in keys)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def normalize_faction(value: str | None) -> str:
    value = clean_text(value)
    upper = value.upper()
    if upper in {"B90/GRÜNE", "GRÜNE", "BÜNDNIS 90/DIE GRÜNEN"}:
        return "BÜNDNIS 90/DIE GRÜNEN"
    if upper in {"LINKE", "DIE LINKE"}:
        return "Die Linke"
    if upper in {"FRAKTIONSLOSE", "FRAKTIONSLOS"}:
        return "fraktionslos"
    return value or "Unbekannt"


def vote_counts_from_csv(value: str | None) -> dict[str, int]:
    numbers = [int(part) for part in re.findall(r"\d+", value or "")[:4]]
    numbers.extend([0] * (4 - len(numbers)))
    return dict(zip(VOTE_KEYS, numbers))


def vote_total(counts: dict[str, int]) -> int:
    return sum(int(counts.get(key) or 0) for key in VOTE_KEYS)


def leading_vote(counts: dict[str, int]) -> str:
    cast = {key: int(counts.get(key) or 0) for key in ("yes", "no", "abstain")}
    if not any(cast.values()):
        return "absent"
    return max(cast, key=cast.get)


def configured_roll_call_list_id(value: str | None = None) -> str:
    return value or os.environ.get(ROLL_CALL_LIST_ID_ENV) or DEFAULT_ROLL_CALL_LIST_ID


def roll_call_list_path(list_id: str | None = None) -> str:
    return f"{ROLL_CALL_LIST_PATH_PREFIX}/{urllib.parse.quote(configured_roll_call_list_id(list_id))}"


def roll_call_list_url(list_id: str | None, offset: int, limit: int) -> str:
    params = urllib.parse.urlencode({"offset": offset, "limit": limit})
    return f"{BT_BASE_URL}{roll_call_list_path(list_id)}?{params}"


def roll_call_vote_url(vote_id: str) -> str:
    return f"{BT_BASE_URL}/parlament/plenum/abstimmung/abstimmung?id={urllib.parse.quote(vote_id)}"


def parse_roll_call_list_page(html_text: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    blocks = re.split(r'(?=<div class="col-xs-12 bt-slide">)', html_text)
    for block in blocks:
        vote_id_match = re.search(r"canvas-na-(\d+)", block)
        date_match = re.search(r'<span class="bt-date">([^<]+)</span>', block)
        if not vote_id_match or not date_match:
            continue

        topic_match = re.search(r'<span class="bt-dachzeile">\s*(.*?)\s*</span>', block, re.S)
        heading_matches = re.findall(r"<h3>\s*(.*?)\s*</h3>", block, re.S)
        description_match = re.search(r'<div class="bt-teaser-haupttext">\s*<p>\s*(.*?)\s*</p>', block, re.S)
        counts_match = re.search(r'data-chart-values="([^"]+)"', block)

        topic = strip_tags(topic_match.group(1)) if topic_match else ""
        heading = strip_tags(heading_matches[-1]) if heading_matches else ""
        if topic and heading.startswith(topic):
            heading = clean_text(heading[len(topic) :])
        document_numbers = sorted(set(re.findall(r"\b\d{1,2}/\d{1,6}\b", strip_tags(block))))
        vote_id = vote_id_match.group(1)
        entries.append(
            {
                "id": vote_id,
                "date": iso_date(date_match.group(1)),
                "topic": topic,
                "title": heading,
                "description": strip_tags(description_match.group(1)) if description_match else "",
                "document_numbers": document_numbers,
                "detail_url": roll_call_vote_url(vote_id),
                "total": vote_counts_from_csv(counts_match.group(1) if counts_match else None),
            }
        )
    return entries


def fetch_roll_call_vote_candidates(
    protocol_date: str | None,
    scan_pages: int,
    roll_call_list_id: str | None = None,
    *,
    include_diagnostics: bool = False,
) -> list[dict[str, Any]] | RollCallCandidateFetch:
    target_date = iso_date(protocol_date)
    if not target_date or scan_pages <= 0:
        result = RollCallCandidateFetch([], False, 0, False)
        return result if include_diagnostics else result.candidates

    candidates: list[dict[str, Any]] = []
    list_html_seen = False
    parsed_entry_count = 0
    page_size = 10
    for page_index in range(scan_pages):
        html_text = fetch_html(roll_call_list_url(roll_call_list_id, page_index * page_size, page_size))
        if html_text.strip():
            list_html_seen = True
        page_entries = parse_roll_call_list_page(html_text)
        parsed_entry_count += len(page_entries)
        if not page_entries:
            break
        candidates.extend(entry for entry in page_entries if entry.get("date") == target_date)
        dated = [entry.get("date") for entry in page_entries if entry.get("date")]
        if dated and min(dated) < target_date:
            break
    result = RollCallCandidateFetch(
        candidates=candidates,
        list_html_seen=list_html_seen,
        parsed_entry_count=parsed_entry_count,
        selector_warning=list_html_seen and parsed_entry_count == 0,
    )
    return result if include_diagnostics else result.candidates


def parse_fraction_votes(detail_html: str) -> list[dict[str, Any]]:
    fractions: list[dict[str, Any]] = []
    pattern = re.compile(
        r'data-value="([^"]+)".*?<h4 class="bt-chart-fraktion">(.*?)<br\s*/?>.*?data-chart-values="([^"]+)"',
        re.S,
    )
    for match in pattern.finditer(detail_html):
        counts = vote_counts_from_csv(match.group(3))
        name = normalize_faction(strip_tags(match.group(2)) or match.group(1))
        fractions.append(
            {
                "name": name,
                "counts": counts,
                "total": vote_total(counts),
                "leading_vote": leading_vote(counts),
            }
        )
    return unique_by(fractions, ("name",))


def parse_member_votes(member_html: str) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    blocks = re.split(r'(?=<div class="col-xs-4 col-sm-3 col-md-2 bt-slide">)', member_html)
    for block in blocks:
        name_match = re.search(r"<h3>(.*?)</h3>", block, re.S)
        faction_match = re.search(r'<p class="bt-person-fraktion">\s*(.*?)\s*</p>', block, re.S)
        vote_match = re.search(r'bt-person-abstimmung bt-abstimmung-([a-z]+)"[^>]*>\s*(.*?)\s*</p>', block, re.S)
        if not name_match or not faction_match or not vote_match:
            continue
        profile_match = re.search(r'<a href="([^"]+)"', block)
        profile_url = None
        if profile_match:
            href = unescape(profile_match.group(1))
            profile_url = href if href.startswith("http") else f"{BT_BASE_URL}{href}"
        vote_key = {
            "ja": "yes",
            "nein": "no",
            "enthalten": "abstain",
            "na": "absent",
        }.get(vote_match.group(1), vote_match.group(1))
        members.append(
            {
                "name": strip_tags(name_match.group(1)),
                "faction": normalize_faction(strip_tags(faction_match.group(1))),
                "vote": vote_key,
                "profile_url": profile_url,
            }
        )
    return members


def fetch_roll_call_vote_detail(vote: dict[str, Any]) -> dict[str, Any]:
    vote_id = str(vote["id"])
    detail_html = fetch_html(roll_call_vote_url(vote_id))
    member_html = fetch_html(f"{BT_BASE_URL}/apps/na/namensliste.form?id={urllib.parse.quote(vote_id)}&ajax=true")
    enriched_vote = dict(vote)
    enriched_vote["fractions"] = parse_fraction_votes(detail_html)
    enriched_vote["members"] = parse_member_votes(member_html)
    return enriched_vote


def top_document_numbers(top: dict[str, Any], linked_drucksachen: list[dict[str, Any]]) -> set[str]:
    numbers = {
        str(doc.get("dokumentnummer"))
        for doc in top.get("drucksachen", [])
        if doc.get("dokumentnummer")
    }
    numbers.update(
        str(doc.get("dokumentnummer"))
        for doc in linked_drucksachen
        if doc.get("dokumentnummer")
    )
    return numbers


def match_roll_call_votes(
    top: dict[str, Any],
    linked_drucksachen: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    cache: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    top_numbers = top_document_numbers(top, linked_drucksachen)
    matches: list[dict[str, Any]] = []
    for candidate in candidates:
        vote_numbers = set(candidate.get("document_numbers") or [])
        if top_numbers and vote_numbers and top_numbers & vote_numbers:
            vote_id = str(candidate["id"])
            if vote_id not in cache:
                cache[vote_id] = fetch_roll_call_vote_detail(candidate)
            matches.append(cache[vote_id])
    return matches


def configured_summary_provider(args: argparse.Namespace) -> str:
    provider = getattr(args, "summary_provider", "auto")
    if provider in {"anthropic", "gemini"}:
        return provider

    if anthropic_summary_api_key(args):
        return "anthropic"
    if gemini_summary_api_key(args):
        return "gemini"
    return "anthropic"


def anthropic_summary_api_key(args: argparse.Namespace) -> str | None:
    return getattr(args, "anthropic_api_key", None) or os.environ.get("ANTHROPIC_API_KEY")


def gemini_summary_api_key(args: argparse.Namespace) -> str | None:
    return (
        getattr(args, "gemini_api_key", None)
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )


def summary_api_key(args: argparse.Namespace, provider: str) -> str | None:
    if provider == "gemini":
        return gemini_summary_api_key(args)
    return anthropic_summary_api_key(args)


def summary_model_chain(args: argparse.Namespace, provider: str) -> list[str]:
    env_var = "GEMINI_SUMMARY_MODELS" if provider == "gemini" else "ANTHROPIC_SUMMARY_MODELS"
    configured = getattr(args, "summary_model", None) or os.environ.get(env_var)
    if configured:
        models = [model.strip() for model in str(configured).split(",")]
        return [model for model in models if model]
    if provider == "gemini":
        return list(DEFAULT_GEMINI_SUMMARY_MODELS)
    return list(DEFAULT_ANTHROPIC_SUMMARY_MODELS)


def summary_source_chunks(top: dict[str, Any]) -> list[dict[str, Any]]:
    speeches = sorted(top.get("speeches") or [], key=lambda speech: int(speech.get("char_count") or 0), reverse=True)
    chunks: list[dict[str, Any]] = []
    for speech in speeches:
        text = speech.get("text") or " ".join(speech.get("paragraphs") or [])
        text = clamp_text(text, SUMMARY_CHUNK_CHARS)
        if not text:
            continue
        speaker = speech.get("speaker") or {}
        sequence = len(chunks) + 1
        chunks.append(
            {
                "id": f"S{sequence}",
                "rede_id": speech.get("rede_id"),
                "source_page": speech.get("source_page"),
                "speaker": {
                    "display_name": speaker.get("display_name"),
                    "fraktion": speaker.get("fraktion"),
                    "role": speaker.get("role"),
                    "role_short": speaker.get("role_short"),
                },
                "text": text,
            }
        )
        if len(chunks) >= SUMMARY_CHUNK_MAX:
            break
    return chunks


def anthropic_text_from_response(response: dict[str, Any]) -> str:
    parts = []
    for block in response.get("content") or []:
        if block.get("type") == "text" and block.get("text"):
            parts.append(str(block["text"]))
    return "\n".join(parts).strip()


def gemini_text_from_response(response: dict[str, Any]) -> str:
    parts = []
    for candidate in response.get("candidates") or []:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            if part.get("text"):
                parts.append(str(part["text"]))
    return "\n".join(parts).strip()


def gemini_model_path(model: str) -> str:
    model_path = model if model.startswith("models/") else f"models/{model}"
    return urllib.parse.quote(model_path, safe="/")


def parse_summary_response(raw_text: str, allowed_chunk_ids: set[str]) -> dict[str, Any]:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        match = re.search(r"\{.*\}", raw_text, re.S)
        if not match:
            raise SummaryError("Summary response was not JSON.") from exc
        data = json.loads(match.group(0))

    sentences = data.get("sentences")
    if isinstance(sentences, str):
        text = clean_text(sentences)
    elif isinstance(sentences, list):
        text = clean_text(" ".join(str(sentence) for sentence in sentences[:3]))
    else:
        text = clean_text(data.get("summary") or "")

    source_ids = [str(chunk_id).strip() for chunk_id in data.get("source_chunk_ids") or []]
    source_ids = [chunk_id for chunk_id in source_ids if chunk_id in allowed_chunk_ids]
    if not text:
        raise SummaryError("Summary response did not include summary text.")
    if len(source_ids) < min(SUMMARY_CHUNK_MIN, len(allowed_chunk_ids)):
        raise SummaryError("Summary response did not cite enough supplied chunks.")
    return {
        "text": text,
        "source_chunk_ids": source_ids[:SUMMARY_CHUNK_MAX],
    }


def request_anthropic_summary(prompt: str, api_key: str, model: str) -> str:
    headers = {
        "Accept": "application/json",
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
    }
    payload = {
        "model": model,
        "max_tokens": ANTHROPIC_SUMMARY_MAX_OUTPUT_TOKENS,
        "system": "Du fasst parlamentarische Primärquellen knapp, neutral und zitattreu zusammen.",
        "messages": [{"role": "user", "content": prompt}],
    }
    return anthropic_text_from_response(post_json(ANTHROPIC_MESSAGES_URL, payload, headers, "Anthropic API"))


def request_gemini_summary(prompt: str, api_key: str, model: str) -> str:
    headers = {
        "Accept": "application/json",
        "x-goog-api-key": api_key,
    }
    payload = {
        "systemInstruction": {
            "parts": [{"text": "Du fasst parlamentarische Primärquellen knapp, neutral und zitattreu zusammen."}]
        },
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": GEMINI_SUMMARY_MAX_OUTPUT_TOKENS,
            "responseMimeType": "application/json",
        },
    }
    url = GEMINI_GENERATE_URL_TEMPLATE.format(model=gemini_model_path(model))
    return gemini_text_from_response(post_json(url, payload, headers, "Gemini API"))


def request_summary_text(provider: str, prompt: str, api_key: str, model: str) -> str:
    if provider == "gemini":
        return request_gemini_summary(prompt, api_key, model)
    return request_anthropic_summary(prompt, api_key, model)


def generate_top_summary(
    top: dict[str, Any],
    provider: str,
    api_key: str,
    models: list[str],
) -> dict[str, Any] | None:
    chunks = summary_source_chunks(top)
    if len(chunks) < SUMMARY_CHUNK_MIN:
        return None

    chunk_lines = "\n\n".join(
        "[{id}] {speaker} ({party_or_role}), Seite {page}: {text}".format(
            id=chunk["id"],
            speaker=clean_text((chunk.get("speaker") or {}).get("display_name") or "Unbekannt"),
            party_or_role=clean_text(
                (chunk.get("speaker") or {}).get("fraktion")
                or (chunk.get("speaker") or {}).get("role_short")
                or (chunk.get("speaker") or {}).get("role")
                or "unbekannt"
            ),
            page=(chunk.get("source_page") or {}).get("page") or "?",
            text=chunk["text"],
        )
        for chunk in chunks
    )
    prompt = f"""
Erstelle eine neutrale, schlichte Zusammenfassung auf Deutsch für einen Bundestags-Tagesordnungspunkt.

Regeln:
- Schreibe 2 bis 3 Sätze.
- Beschreibe nur, was in den gelieferten Quellen erkennbar debattiert wurde.
- Keine Bewertung, keine Mutmaßungen, keine zusätzlichen Fakten.
- Zitiere 3 bis 5 der gelieferten Quellen über ihre IDs.
- Gib ausschließlich JSON im Format {{"sentences":["...","..."],"source_chunk_ids":["S1","S2","S3"]}} zurück.

TOP: {clean_text(top.get("top_id") or "")}
Titel: {clean_text(top.get("heading") or "")}

Quellen:
{chunk_lines}
""".strip()

    last_error: SummaryError | None = None
    allowed_ids = {chunk["id"] for chunk in chunks}
    for model in models:
        try:
            summary = parse_summary_response(request_summary_text(provider, prompt, api_key, model), allowed_ids)
            chunks_by_id = {chunk["id"]: chunk for chunk in chunks}
            return {
                "label": "Automatische Zusammenfassung — zur Quelle",
                "provider": provider,
                "model": model,
                "text": summary["text"],
                "source_chunk_ids": summary["source_chunk_ids"],
                "source_chunks": [chunks_by_id[chunk_id] for chunk_id in summary["source_chunk_ids"]],
            }
        except SummaryError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return None


def enrich_with_llm_summaries(report: dict[str, Any], args: argparse.Namespace) -> None:
    mode = getattr(args, "summary_mode", "auto")
    if mode == "off":
        report["summary_generation"] = {"enabled": False}
        return

    provider = configured_summary_provider(args)
    api_key = summary_api_key(args, provider)
    models = summary_model_chain(args, provider)
    if not api_key:
        env_hint = "GEMINI_API_KEY or GOOGLE_API_KEY" if provider == "gemini" else "ANTHROPIC_API_KEY"
        report["summary_generation"] = {
            "enabled": False,
            "provider": provider,
            "reason": f"{env_hint} not set",
            "models": models,
        }
        if mode == "required":
            flag_hint = "--gemini-api-key" if provider == "gemini" else "--anthropic-api-key"
            raise DipError(f"Provide a {provider} API key via {flag_hint} or {env_hint} for summaries.")
        return

    failures: list[str] = []
    for item in report.get("agenda_items") or []:
        try:
            parsed_top = {
                "top_id": item.get("top_id"),
                "heading": item.get("heading"),
                "speeches": item.get("xml_speakers") or [],
            }
            summary = generate_top_summary(parsed_top, provider, api_key, models)
            if summary:
                item["llm_summary"] = summary
        except SummaryError as exc:
            failures.append(f"{item.get('top_id') or item.get('index')}: {exc}")
            if mode == "required":
                raise DipError(f"Summary generation failed for {item.get('top_id')}: {exc}") from exc

    report["summary_generation"] = {
        "enabled": True,
        "provider": provider,
        "models": models,
        "generated_top_count": sum(1 for item in report.get("agenda_items") or [] if item.get("llm_summary")),
        "failures": failures,
    }


def enrich_with_api(
    client: ApiClient,
    protocol: dict[str, Any],
    parsed_xml: dict[str, Any],
    person_limit: int,
    vote_scan_pages: int = 30,
    roll_call_list_id: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    protocol_id = protocol["id"]
    positions = client.list_all("/vorgangsposition", {"f.plenarprotokoll": protocol_id})
    if progress:
        progress(f"Fetched {len(positions)} proceeding position(s).")
    activities = client.list_all("/aktivitaet", {"f.plenarprotokoll": protocol_id})
    if progress:
        progress(f"Fetched {len(activities)} parliamentary activity record(s).")
    roll_call_fetch = fetch_roll_call_vote_candidates(
        protocol.get("datum"),
        vote_scan_pages,
        roll_call_list_id,
        include_diagnostics=True,
    )
    assert isinstance(roll_call_fetch, RollCallCandidateFetch)
    roll_call_candidates = roll_call_fetch.candidates
    if progress:
        progress(f"Found {len(roll_call_candidates)} roll-call vote candidate(s).")
    roll_call_cache: dict[str, dict[str, Any]] = {}

    positions_by_vorgang: dict[str, list[dict[str, Any]]] = {}
    linked_drucksachen_by_vorgang: dict[str, list[dict[str, Any]]] = {}

    def load_vorgang_positions(vorgang_id: str) -> list[dict[str, Any]]:
        if vorgang_id not in positions_by_vorgang:
            positions_by_vorgang[vorgang_id] = client.list_all("/vorgangsposition", {"f.vorgang": vorgang_id})
        return positions_by_vorgang[vorgang_id]

    def linked_drucksachen_for_vorgang(vorgang_id: str) -> list[dict[str, Any]]:
        if vorgang_id not in linked_drucksachen_by_vorgang:
            drucksache_positions = [
                compact_drucksache_position(position)
                for position in load_vorgang_positions(vorgang_id)
                if position.get("dokumentart") == "Drucksache"
            ]
            linked_drucksachen_by_vorgang[vorgang_id] = drucksache_positions
        return linked_drucksachen_by_vorgang[vorgang_id]

    def position_drucksache_numbers(position: dict[str, Any]) -> set[str]:
        numbers: set[str] = set()
        if position.get("vorgang_id"):
            numbers.update(
                str(doc.get("dokumentnummer"))
                for doc in linked_drucksachen_for_vorgang(str(position["vorgang_id"]))
                if doc.get("dokumentnummer")
            )
        for linked in position.get("mitberaten") or []:
            if linked.get("id"):
                numbers.update(
                    str(doc.get("dokumentnummer"))
                    for doc in linked_drucksachen_for_vorgang(str(linked["id"]))
                    if doc.get("dokumentnummer")
                )
        return numbers

    def position_matches_top(position: dict[str, Any], top: dict[str, Any]) -> bool:
        if not overlaps(top, position):
            return False
        xml_numbers = {
            str(doc.get("dokumentnummer"))
            for doc in top.get("drucksachen", [])
            if doc.get("dokumentnummer")
        }
        if xml_numbers:
            return bool(xml_numbers & position_drucksache_numbers(position)) or title_matches(
                top.get("heading"), position.get("titel")
            )
        return title_matches(top.get("heading"), position.get("titel"))

    enriched_tops: list[dict[str, Any]] = []
    agenda_items = parsed_xml["agenda_items"]
    for top_index, top in enumerate(agenda_items, start=1):
        matching_positions = [position for position in positions if position_matches_top(position, top)]
        matching_activities = [activity for activity in activities if activity_in_top(activity, top)]

        linked_drucksachen: list[dict[str, Any]] = []
        vorgang_ids = {str(position.get("vorgang_id")) for position in matching_positions if position.get("vorgang_id")}
        for position in matching_positions:
            for linked in position.get("mitberaten") or []:
                if linked.get("id"):
                    vorgang_ids.add(str(linked["id"]))

        for vorgang_id in sorted(vorgang_ids):
            linked_drucksachen.extend(linked_drucksachen_for_vorgang(vorgang_id))

        linked_drucksachen = unique_by(linked_drucksachen, ("vorgang_id", "dokumentnummer", "url"))
        votes = match_roll_call_votes(top, linked_drucksachen, roll_call_candidates, roll_call_cache)

        enriched_tops.append(
            {
                "index": top["index"],
                "top_id": top["top_id"],
                "heading": top["heading"],
                "page_range": top["page_range"],
                "xml_drucksachen": top["drucksachen"],
                "xml_speech_count": len(top["speeches"]),
                "xml_speakers": [
                    {
                        "rede_id": speech["rede_id"],
                        "source_page": speech["source_page"],
                        "speaker": speech["speaker"],
                        "paragraph_count": speech["paragraph_count"],
                        "char_count": speech["char_count"],
                        "text": speech["text"],
                        "paragraphs": speech["paragraphs"],
                        "snippet": speech["snippet"],
                    }
                    for speech in top["speeches"]
                ],
                "xml_speakers_first": [
                    {
                        "rede_id": speech["rede_id"],
                        "source_page": speech["source_page"],
                        "speaker": speech["speaker"],
                        "char_count": speech["char_count"],
                        "snippet": speech["snippet"],
                    }
                    for speech in top["speeches"][:5]
                ],
                "api": {
                    "positions": [compact_position(position) for position in matching_positions],
                    "activities_count": len(matching_activities),
                    "activities": [compact_activity(activity) for activity in matching_activities],
                    "activities_first": [compact_activity(activity) for activity in matching_activities[:5]],
                    "linked_drucksachen": linked_drucksachen,
                    "raw": {
                        "positions": matching_positions,
                        "activities": matching_activities,
                    },
                },
                "votes": votes,
            }
        )
        if progress and (top_index % 10 == 0 or top_index == len(agenda_items)):
            progress(f"Enriched agenda items: {top_index}/{len(agenda_items)}.")

    unique_person_ids = []
    seen_person_ids: set[str] = set()
    for activity in activities:
        person_id = activity.get("person_id")
        if person_id and person_id not in seen_person_ids:
            seen_person_ids.add(person_id)
            unique_person_ids.append(str(person_id))

    people_to_fetch = unique_person_ids if person_limit <= 0 else unique_person_ids[:person_limit]
    if progress:
        progress(f"Fetching {len(people_to_fetch)} person record(s).")
    person_records: list[dict[str, Any]] = []
    person_fetch_errors: list[dict[str, str]] = []
    for person_index, person_id in enumerate(people_to_fetch, start=1):
        try:
            person = client.get_json(f"/person/{person_id}")
        except DipError as exc:
            person_fetch_errors.append({"person_id": person_id, "error": str(exc)})
        else:
            person_records.append(person)
        if progress and (person_index % 25 == 0 or person_index == len(people_to_fetch)):
            progress(
                f"Processed person records: {person_index}/{len(people_to_fetch)} "
                f"({len(person_records)} fetched, {len(person_fetch_errors)} failed)."
            )

    warnings: list[str] = []
    if any(not top["api"]["positions"] for top in enriched_tops):
        warnings.append("Mindestens ein XML-TOP konnte über den Seitenbereich keiner DIP-Vorgangsposition zugeordnet werden.")
    if any(top["xml_speech_count"] and top["api"]["activities_count"] == 0 for top in enriched_tops):
        warnings.append("Mindestens ein XML-TOP mit Reden hatte keine passenden DIP-Aktivitäten im Seitenbereich.")
    if len(activities) >= 100:
        warnings.append("Die Zahl der Aktivitäten überschritt eine API-Seite; Cursor-Paginierung wurde verwendet.")
    if roll_call_candidates and not roll_call_cache:
        warnings.append("Für dieses Sitzungsdatum wurden namentliche Abstimmungen gefunden, aber keine passte per Drucksachennummer zu einem TOP.")
    if roll_call_fetch.selector_warning:
        warnings.append(ROLL_CALL_LIST_PARSE_WARNING)
        print(f"warning: {ROLL_CALL_LIST_PARSE_WARNING}", file=sys.stderr)
    if person_fetch_errors:
        failed_ids = ", ".join(error["person_id"] for error in person_fetch_errors[:10])
        suffix = "" if len(person_fetch_errors) <= 10 else f" und {len(person_fetch_errors) - 10} weitere"
        warnings.append(
            "DIP-Personendaten konnten für "
            f"{len(person_fetch_errors)} von {len(people_to_fetch)} Stichproben nicht geladen werden: "
            f"{failed_ids}{suffix}."
        )

    return {
        "api_totals": {
            "vorgangsposition_count": len(positions),
            "aktivitaet_count": len(activities),
            "unique_person_ids": len(unique_person_ids),
            "person_record_count": len(person_records),
            "sampled_person_count": len(person_records),
            "person_record_fetch_error_count": len(person_fetch_errors),
            "person_records_complete": (
                not person_fetch_errors
                and (person_limit <= 0 or len(person_records) >= len(unique_person_ids))
            ),
            "roll_call_vote_candidate_count": len(roll_call_candidates),
            "matched_roll_call_vote_count": len(roll_call_cache),
        },
        "sampled_people": [compact_person(person) for person in person_records],
        "api_records": {
            "protocol": protocol,
            "vorgangspositionen": positions,
            "aktivitaeten": activities,
            "persons": person_records,
            "person_fetch_errors": person_fetch_errors,
            "roll_call_vote_candidates": roll_call_candidates,
            "matched_roll_call_votes": list(roll_call_cache.values()),
        },
        "agenda_items": enriched_tops,
        "warnings": warnings,
    }


def build_report(
    args: argparse.Namespace,
    protocol: dict[str, Any] | None = None,
) -> dict[str, Any]:
    load_local_env()
    api_key = args.api_key or os.environ.get("DIP_API_KEY")
    if not api_key:
        raise DipError("Provide a DIP API key via --api-key or DIP_API_KEY.")

    client = ApiClient(api_key=api_key, sleep_seconds=args.sleep)
    if protocol is None:
        protocol = find_protocol(client, args.protocol_id, args.document_number)
    document_number = str(protocol.get("dokumentnummer") or protocol.get("id") or "unknown")

    def progress(message: str) -> None:
        print(f"[dossier {document_number}] {message}", file=sys.stderr, flush=True)

    fundstelle = protocol.get("fundstelle") or {}
    xml_url = fundstelle.get("xml_url")
    if not xml_url:
        raise DipError(f"Protocol {protocol.get('id')} has no fundstelle.xml_url.")

    progress("Downloading XML transcript.")
    xml_text = fetch_text(xml_url)
    parsed_xml = parse_protocol_xml(xml_text)
    parsed_speech_count = sum(len(top["speeches"]) for top in parsed_xml["agenda_items"])
    progress(
        f"Parsed XML: {len(parsed_xml['agenda_items'])} agenda item(s), "
        f"{parsed_speech_count} speech(es)."
    )
    progress("Fetching DIP enrichment and roll-call data.")
    enrichment = enrich_with_api(
        client,
        protocol,
        parsed_xml,
        args.person_limit,
        getattr(args, "vote_scan_pages", 30),
        getattr(args, "roll_call_list_id", None),
        progress=progress,
    )

    agenda_items = enrichment["agenda_items"]
    if args.limit_tops is not None:
        agenda_items = agenda_items[: args.limit_tops]

    xml_speech_count = parsed_speech_count
    xml_drucksache_count = sum(len(top["drucksachen"]) for top in parsed_xml["agenda_items"])
    tops_with_xml_drucksachen = sum(1 for top in parsed_xml["agenda_items"] if top["drucksachen"])
    tops_with_api_positions = sum(1 for top in enrichment["agenda_items"] if top["api"]["positions"])
    tops_with_api_drucksachen = sum(1 for top in enrichment["agenda_items"] if top["api"]["linked_drucksachen"])

    report = {
        "protocol": {
            "id": protocol.get("id"),
            "dokumentnummer": protocol.get("dokumentnummer"),
            "datum": protocol.get("datum"),
            "titel": protocol.get("titel"),
            "verteildatum": fundstelle.get("verteildatum"),
            "pdf_url": fundstelle.get("pdf_url"),
            "xml_url": xml_url,
            "xml_header": parsed_xml["xml_protocol"],
        },
        "validation_summary": {
            "xml_top_count": len(parsed_xml["agenda_items"]),
            "xml_speech_count": xml_speech_count,
            "xml_drucksache_count": xml_drucksache_count,
            "tops_with_xml_drucksachen": tops_with_xml_drucksachen,
            "tops_with_api_positions": tops_with_api_positions,
            "tops_with_api_linked_drucksachen": tops_with_api_drucksachen,
            **enrichment["api_totals"],
        },
        "warnings": enrichment["warnings"],
        "sampled_people": enrichment["sampled_people"],
        "api_records": enrichment["api_records"],
        "agenda_items": agenda_items,
    }
    if getattr(args, "summary_mode", "off") != "off":
        progress("Processing LLM summaries.")
    enrich_with_llm_summaries(report, args)
    progress("Dossier data assembled; writing generated files.")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--protocol-id", help="DIP Plenarprotokoll ID, e.g. 5799")
    selector.add_argument("--document-number", help="DIP document number, e.g. 21/84")
    parser.add_argument("--api-key", help="DIP API key. Prefer DIP_API_KEY for local use.")
    parser.add_argument("--limit-tops", type=int, help="Only print the first N XML agenda items.")
    parser.add_argument(
        "--person-limit",
        type=int,
        default=25,
        help="Number of distinct person records to fetch. Use 0 to fetch all person records seen in activities.",
    )
    parser.add_argument(
        "--summary-mode",
        choices=("auto", "required", "off"),
        default="off",
        help="Generate per-TOP LLM summaries when requested, require them, or disable them.",
    )
    parser.add_argument(
        "--summary-provider",
        choices=("auto", "anthropic", "gemini"),
        default="auto",
        help="LLM provider for summaries. Auto keeps Anthropic as the default when both provider keys are set.",
    )
    parser.add_argument("--anthropic-api-key", help="Anthropic API key. Prefer ANTHROPIC_API_KEY for local use.")
    parser.add_argument(
        "--gemini-api-key",
        help="Google Gemini API key. Prefer GEMINI_API_KEY or GOOGLE_API_KEY for local use.",
    )
    parser.add_argument(
        "--summary-model",
        help=(
            "Comma-separated provider model IDs to try for summaries. "
            "Defaults depend on --summary-provider."
        ),
    )
    parser.add_argument(
        "--vote-scan-pages",
        type=int,
        default=30,
        help="Number of Bundestag roll-call vote list pages to scan for same-day matches.",
    )
    parser.add_argument(
        "--roll-call-list-id",
        help=(
            "Bundestag roll-call vote filterlist id. "
            f"Defaults to {ROLL_CALL_LIST_ID_ENV} or {DEFAULT_ROLL_CALL_LIST_ID}."
        ),
    )
    parser.add_argument("--sleep", type=float, default=0.0, help="Optional delay between DIP API requests.")
    return parser.parse_args()


def main() -> int:
    load_local_env()
    args = parse_args()
    try:
        report = build_report(args)
    except DipError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
