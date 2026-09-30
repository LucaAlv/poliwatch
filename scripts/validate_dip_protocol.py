#!/usr/bin/env python3
"""Validate DIP plenary protocol extraction.

This is an exploratory script for the Bundestag Pulse "Assignment": take one
official Plenarprotokoll XML as the canonical transcript and enrich it with DIP
API metadata for proceedings, activities, people, and linked Drucksachen.
"""

from __future__ import annotations

if __name__ == "__main__":
    from python_version_guard import require_supported_python

    require_supported_python()

import argparse
import hashlib
import http.client
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
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Callable, NamedTuple

import derive
import publication_state as publication
import speech_kinds


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
SUMMARY_SCHEMA_VERSION = 1
SUMMARY_PROMPT_VERSION = "fixed-public-v1"
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


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def summary_failure_code(error: Exception) -> str:
    """Reduce provider/parser detail to the schema's safe public vocabulary."""
    message = str(error).lower()
    if str(error) in publication.FAILURE_CODES:
        return str(error)
    if "timeout" in message or "timed out" in message:
        return "provider_timeout"
    if "duplicate" in message:
        return "duplicate_citation"
    if "target" in message or "resolve" in message:
        return "missing_target"
    if "page" in message and "bound" in message:
        return "page_out_of_bounds"
    if "cit" in message or "chunk" in message:
        return "invalid_citations"
    return "invalid_payload"


@dataclass(frozen=True)
class RollCallCandidateFetch:
    candidates: list[dict[str, Any]]
    list_html_seen: bool
    parsed_entry_count: int
    selector_warning: bool
    # How the scan ended: "date_passed" (an entry older than the sitting was
    # seen), "list_end" (the list ran out), "budget_exhausted" (all
    # --vote-scan-pages used with neither: older votes may still be listed
    # beyond the window) or "not_scanned". Only the first two prove that every
    # candidate of the sitting's date was seen.
    scan_end: str = "not_scanned"
    pages_fetched: int = 0
    pages_from_cache: int = 0
    #: Date of the newest entry on the first page; None when there was none.
    newest_entry_date: str | None = None


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
            except (OSError, http.client.HTTPException) as exc:
                # URLError and timeouts are OSErrors, and so is a connection
                # reset while the body is being read, which urlopen does not
                # wrap: without it one reset ended a two-hour backfill.
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


ROLL_CALL_OUTAGE_KEY = "__outage__"
#: After a network failure the rest of the build skips roll-call fetches for
#: this long, then tries again (the site may have recovered).
ROLL_CALL_OUTAGE_COOLDOWN_SECONDS = 300
#: A sitting this recent with no candidate, on a list whose newest entry is
#: older than the sitting, may just be ahead of the list.
ROLL_CALL_LIST_LAG_DAYS = 14
PAGE_FETCH_RETRIES = 2
PAGE_FETCH_RETRY_DELAY_SECONDS = 1.5


def _fetch_page(url: str, accept: str, kind: str) -> str:
    """GET a page, retrying a transient network error like ApiClient does.

    Roll-call pages go through here on every update now that votes are on by
    default; without a retry one connection reset downgraded a whole sitting's
    votes to partial.
    """
    req = urllib.request.Request(url, headers={"Accept": accept})
    for attempt in range(PAGE_FETCH_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                return res.read().decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DipError(f"Failed to fetch {kind} {url}: {exc}") from exc
        except urllib.error.HTTPError as exc:
            exc.close()
            # A 404 or 403 will not change on a retry; a busy or failing server might.
            if exc.code in {429, 500, 502, 503, 504} and attempt < PAGE_FETCH_RETRIES:
                time.sleep(PAGE_FETCH_RETRY_DELAY_SECONDS * (attempt + 1))
                continue
            failure = DipError(f"Failed to fetch {kind} {url}: {exc}")
            failure.transient = exc.code in {429, 500, 502, 503, 504}  # type: ignore[attr-defined]
            raise failure from exc
        except (OSError, http.client.HTTPException) as exc:
            if attempt < PAGE_FETCH_RETRIES:
                delay = PAGE_FETCH_RETRY_DELAY_SECONDS * (attempt + 1)
                print(
                    f"warning: {kind} request failed for {url}: {exc}; retrying {attempt + 2}/{PAGE_FETCH_RETRIES + 1} in {delay:g}s.",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue
            failure = DipError(f"Failed to fetch {kind} {url}: {exc}")
            failure.transient = True  # type: ignore[attr-defined]
            raise failure from exc
    raise AssertionError("unreachable")


def fetch_text(url: str) -> str:
    return _fetch_page(url, "application/xml,text/xml,*/*", "XML")


def fetch_html(url: str) -> str:
    return _fetch_page(url, "text/html,*/*", "HTML")


def post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    api_name: str = "LLM API",
    timeout: float = 60,
) -> Any:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
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


def is_bundestag_document_url(href: str | None) -> bool:
    """True when an anchor points at an official Bundestag document host.

    Speeches quote external URLs verbatim (news sites, NGOs), and a percent-encoded
    or dated path such as ``.../%D9%88/739016/`` or ``/2024/12/06/`` looks like a
    Drucksache number to the regex below. Only Bundestag-hosted links can be
    Drucksachen, and only those pass the publication allowlist later.
    """
    if not href:
        return False
    parsed = urllib.parse.urlsplit(href)
    hostname = (parsed.hostname or "").lower().rstrip(".")
    return parsed.scheme == "https" and hostname in publication.SOURCE_HOSTS["bundestag-xml"]


def extract_drucksachen(elem: ET.Element) -> list[dict[str, str | None]]:
    docs: list[dict[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for anchor in elem.findall(".//a"):
        href = anchor.attrib.get("href")
        if href and not is_bundestag_document_url(href):
            continue
        text = elem_text(anchor)
        candidates = re.findall(r"\b\d{1,2}/\d{1,6}\b", text)
        for number in candidates:
            key = (number, href)
            if key not in seen:
                docs.append({"dokumentnummer": number, "url": href})
                seen.add(key)
    return docs


_REDNER_LABEL_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<fraktion>[^()]+)\)\s*:?$")


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
    if fraction and derive.zusammenschluss(fraction) is None:
        # Two people folded into one element ("SPDCDU/CSU", first name
        # "Dirk-UlrichAlexander"): no field of it can be trusted, but the label
        # the protocol prints after the element ("Alexander Föhr (CDU/CSU):")
        # names the person. Its name and Fraktion replace the garbled ones.
        label = _REDNER_LABEL_RE.match(clean_text(redner.tail))
        if label:
            display_name, first, last = clean_text(label.group("name")), None, None
            fraction = clean_text(label.group("fraktion"))
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


def redner_key(redner: ET.Element | None) -> str | None:
    """The person a ``<redner id="...">`` names, or None when it names nobody
    (a merged record's two ids name the first)."""
    return derive.first_redner_id(redner.attrib.get("id")) if redner is not None else None


class SpeechText(NamedTuple):
    """What one Rede's XML yields: the Redner's own text and paragraphs, and
    how many characters no speaker could be determined for."""

    text: str
    paragraphs: list[str]
    unattributed_chars: int


# Whoever a ``<name>`` element introduces is the Sitzungsleitung ("Präsidentin
# Julia Klöckner:"): the XML uses it for nobody else. Compared by identity.
_SITZUNGSLEITUNG = object()


def speech_text_and_paragraphs(rede: ET.Element) -> SpeechText:
    """The words the Rede's Redner spoke (CONTEXT.md: Rede, Sitzungsleitung,
    Zwischenfrage).

    A ``<rede>`` interleaves the Redner with the Sitzungsleitung and with MdBs
    asking a Zwischenfrage. The current speaker starts as the Rede's first
    ``<redner>``, becomes the Sitzungsleitung at a ``<name>`` element and
    becomes whoever a ``<p klasse="redner">`` marker names. Only paragraphs
    spoken while the Redner is the current speaker are his or hers. The
    Redner resumes with a marker of his or her own id: measured on 961 Reden
    of eight sittings (WP 20 and 21) a ``<name>`` block was always followed by
    such a marker or by the end of the Rede, so no resumption is inferred from
    paragraph classes. Text with no determinable speaker (a marker that names
    nobody, or a Rede that never names its Redner) goes to nobody and is
    counted in ``unattributed_chars``. ``<kommentar>`` is not a ``<p>`` and
    stays excluded.
    """
    own = redner_key(rede.find("./p[@klasse='redner']/redner"))
    speaker: object = own
    paragraphs: list[str] = []
    unattributed = 0
    for child in rede:
        if child.tag == "name":
            speaker = _SITZUNGSLEITUNG
        elif child.tag == "p":
            if child.attrib.get("klasse") == "redner":
                speaker = redner_key(child.find("redner"))
                continue
            text = elem_text(child)
            if not text:
                continue
            if speaker is None:
                unattributed += len(text)
            elif speaker == own:
                paragraphs.append(text)
    return SpeechText(clean_text(" ".join(paragraphs)), paragraphs, unattributed)


def parse_protocol_xml(xml_text: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    toc = parse_toc(root)
    rid_pages: dict[str, dict[str, Any]] = {}
    for block in toc.values():
        rid_pages.update(block["rid_pages"])

    agenda_items: list[dict[str, Any]] = []
    seen_formats: dict[str, frozenset[str]] = {}
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

        heading = clean_text(" ".join(heading_lines))
        top_format = speech_kinds.top_format(heading, top.attrib.get("top-id"), seen_formats)
        redes = top.findall("rede")
        labels = speech_kinds.classify_reden(top, top_format.formats, top_format.continuation)
        speeches: list[dict[str, Any]] = []
        contributions: list[dict[str, Any]] = []
        pages: list[dict[str, Any]] = []
        for sequence, (rede, label) in enumerate(zip(redes, labels), start=1):
            rid = rede.attrib.get("id")
            redner = parse_redner(rede.find("./p[@klasse='redner']/redner"))
            text, paragraphs, unattributed_chars = speech_text_and_paragraphs(rede)
            page_ref = rid_pages.get(rid or "")
            if page_ref:
                pages.append(page_ref)
            unit = {
                "rede_id": rid,
                "source_page": page_ref,
                "speaker": redner,
                "paragraph_count": len(paragraphs),
                "char_count": len(text),
                "unattributed_char_count": unattributed_chars,
                "text": text,
                "paragraphs": paragraphs,
                "snippet": text[:240],
            }
            if label.kind is None:
                speeches.append(unit)
            else:
                contributions.append(
                    {**unit, "kind": label.kind, "parent_rede_id": label.parent_rede_id, "sequence": sequence}
                )
        if speech_kinds.FRAGESTUNDE in top_format.formats:
            for flat_index, turn in enumerate(speech_kinds.fragestunde_turns(top), start=1):
                text = clean_text(" ".join(turn.paragraphs))
                if turn.redner is not None:
                    speaker = parse_redner(turn.redner)
                else:
                    speaker = {"xml_redner_id": None, "display_name": turn.announced} if turn.announced else None
                contributions.append(
                    {
                        "kind": turn.kind,
                        "rede_id": None,
                        "parent_rede_id": None,
                        "sequence": len(redes) + flat_index,
                        "source_page": None,
                        "speaker": speaker,
                        "paragraph_count": len(turn.paragraphs),
                        "char_count": len(text),
                        "unattributed_char_count": 0,
                        "text": text,
                        "paragraphs": turn.paragraphs,
                        "snippet": text[:240],
                    }
                )

        sorted_pages = sorted(pages, key=page_sort_key)
        agenda_items.append(
            {
                "index": index,
                "top_id": top.attrib.get("top-id"),
                "heading": heading,
                "question_formats": sorted(top_format.formats),
                "drucksachen": extract_drucksachen(top),
                "ueberweisung": transfer_lines,
                "page_range": {
                    "start": sorted_pages[0] if sorted_pages else None,
                    "end": sorted_pages[-1] if sorted_pages else None,
                },
                "speeches": speeches,
                "contributions": contributions,
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
    """derive.zusammenschluss, with "Unbekannt" where it names nothing (the
    vote pages need a label for every Fraktion row)."""
    return derive.zusammenschluss(value) or "Unbekannt"


def vote_counts_from_csv(value: str | None) -> dict[str, int]:
    numbers = [int(part) for part in re.findall(r"\d+", value or "")[:4]]
    numbers.extend([0] * (4 - len(numbers)))
    return dict(zip(VOTE_KEYS, numbers))


def vote_total(counts: dict[str, int]) -> int:
    return sum(int(counts.get(key) or 0) for key in VOTE_KEYS)


_CONSTITUTIONAL_TITLE_RE = re.compile(r"Grundgesetz", re.I)


def vote_result(
    *, official: str | None, yes_count: int, no_count: int, title: str | None = None
) -> tuple[str | None, str | None]:
    """Decide a roll-call vote's outcome: ``(result_raw, result_source)``.

    The bundestag.de page wins when it states one (``official`` is "accepted"
    or "rejected", scraped from its Beschluss text by
    ``scrape_official_vote_result``); otherwise the result is derived from the
    counts. A tie is rejected (GOBT Section 48 Abs. 2: at a tie the question is
    answered no). No counts at all means unknown - never guess.

    A Grundgesetz amendment needs two thirds of the Bundestag's members
    (Art. 79 Abs. 2 GG), not a Ja > Nein majority, so more Ja than Nein cannot
    be read as acceptance there: the derived result is unknown. Ja <= Nein is
    still a certain rejection.
    """
    if official in ("accepted", "rejected"):
        return official, "official"
    if yes_count == 0 and no_count == 0:
        return None, None
    if yes_count > no_count:
        if _CONSTITUTIONAL_TITLE_RE.search(title or ""):
            return None, None
        return "accepted", "derived"
    return "rejected", "derived"


_BESCHLUSS_SECTION_RE = re.compile(
    r'<h2 class="bt-artikel__aside-section-title">Beschluss</h2>(.*?)</div>\s*<div class="bt-artikel__aside-section">',
    re.S,
)
_VOTE_OUTCOME_WORD_RE = re.compile(r"\b(angenommen|abgelehnt)\b")
_VOTE_NEGATION_RE = re.compile(r"\bnicht\b", re.I)
# Where the next vote's narration starts: its "Gesamt" or its own tally.
_NEXT_TALLY_RE = re.compile(r"Gesamt|Ja:\s*\d")
# A Drucksache number's shape, e.g. "21/6561". Shared with
# parse_roll_call_list_page, which populates the document_numbers this
# function cross-checks against.
_DOCUMENT_NUMBER_RE = re.compile(r"\b\d{1,2}/\d{1,6}\b")


def _beschluss_paragraphs(section_html: str) -> list[list[str]]:
    """The Beschluss section as paragraphs of plain-text lines: <p> and lists
    end a paragraph; <br> and list items end a line (live pages put the tally
    and its outcome in consecutive <li>s, "Gesamt: 716 Ja: 87 Nein: 626 ...",
    then "Gesetzentwurf ... abgelehnt"). A blank line ("<br/><br/>") is kept as
    "" so callers can see where one decision's block ends. Markup and entities
    are flattened."""
    paragraphs = []
    for block in re.split(r"</?(?:p|ul|ol)\b[^>]*>", section_html, flags=re.I):
        block = re.sub(r"(?:</?li\b[^>]*>\s*)+", "<br/>", block, flags=re.I)
        lines = [strip_tags(line) for line in re.split(r"<br\s*/?>", block, flags=re.I)]
        if any(lines):
            paragraphs.append(lines)
    return paragraphs


def scrape_official_vote_result(
    detail_html: str, yes_count: int, no_count: int, document_numbers: list[str] | None = None
) -> str | None:
    """bundestag.de states a vote's result only as prose in the page's
    "Beschluss" section, never as a machine-readable field, and one page's
    Beschluss text can narrate several related votes (a Gesetzentwurf, then its
    Entschließungsantrag). This vote's own Ja/Nein counts are the only way to
    find its sentence. The outcome must follow the tally directly: on the same
    line before the next "Gesamt", or on the next line of the same paragraph
    ("Gesamt: 562 Ja:434 Nein:128 Enthaltungen --<br/>Gesetzentwurf
    angenommen"). Anything looser, a negation ("nicht angenommen") or both
    outcome words returns None - the caller then derives.

    A tally with no outcome line of its own (e.g. a unanimous show-of-hands
    decision needs no "Gesamt"/"Ja: N" marker) is not a boundary _NEXT_TALLY_RE
    recognizes, so the one-line lookahead can otherwise bleed into a completely
    unrelated neighboring decision's outcome word. When document_numbers is
    known and the attributed text names a *different*, specific document
    number, refuse rather than guess - a real outcome sentence often does not
    repeat its own Drucksache number at all (the fixture and several live
    pages read "Gesetzentwurf angenommen" with no number), so the check must
    not require a match, only reject a proven mismatch.

    A blank line ends a vote's block: live pages separate consecutive
    decisions with "<br/><br/>", so a tally-less neighbor (a show-of-hands item)
    sits behind a blank line and its outcome word is never adopted; only the
    line directly under the tally counts. Two decisions with no blank line
    between them remain indistinguishable (not observed on any live page).
    """
    section_match = _BESCHLUSS_SECTION_RE.search(detail_html)
    if not section_match:
        return None
    tally_re = re.compile(rf"Ja:\s*{yes_count}\s*Nein:\s*{no_count}\b")
    # Two votes in one section with identical tallies would be indistinguishable:
    # only a unique match is confident enough to call official.
    hits = [
        (lines, index, match)
        for lines in _beschluss_paragraphs(section_match.group(1))
        for index, line in enumerate(lines)
        for match in tally_re.finditer(line)
    ]
    if len(hits) != 1:
        return None
    lines, index, match = hits[0]
    rest = lines[index][match.end() :]
    boundary = _NEXT_TALLY_RE.search(rest)
    # The text that belongs to this vote: the rest of its line and, only when
    # no other vote started on that line, the next line up to the next tally.
    text = rest[: boundary.start()] if boundary else rest
    if not boundary and index + 1 < len(lines):
        following = lines[index + 1]
        next_boundary = _NEXT_TALLY_RE.search(following)
        text = f"{text} {following[: next_boundary.start()] if next_boundary else following}"
    words = set(_VOTE_OUTCOME_WORD_RE.findall(text))
    # The negation check spans both lines: "ist nicht<br/>angenommen".
    if len(words) != 1 or _VOTE_NEGATION_RE.search(text):
        return None
    # Refuse only on a proven mismatch (the text names a specific OTHER
    # document): a genuine outcome sentence often names no number at all, so
    # absence of our own number is not itself suspicious.
    named_numbers = set(_DOCUMENT_NUMBER_RE.findall(text))
    if document_numbers and named_numbers and not named_numbers & set(document_numbers):
        return None
    return "accepted" if words == {"angenommen"} else "rejected"


# bundestag.de publishes each roll-call vote's PDF/XLSX Namensliste on a page
# separate from the vote's own detail page (no XLSX link exists there at all,
# confirmed against several live votes), keyed by nothing the roll-call list
# shares - only a "DD.MM.YYYY: <title>" link label. Matching is therefore by
# (date, normalized title), never a derived URL pattern (blob ids are opaque
# and the "_xls"/"-xls" filename suffix is inconsistent across sittings).
DEFAULT_NAMENSLISTEN_LIST_ID = "462112-462112"
NAMENSLISTEN_LIST_ID_ENV = "BT_NAMENSLISTEN_LIST_ID"
NAMENSLISTEN_PAGE_LIMIT = 200


def namenslisten_list_url(list_id: str | None = None) -> str:
    # Like the roll-call list id, the catalog id can change per Wahlperiode.
    list_id = list_id or os.environ.get(NAMENSLISTEN_LIST_ID_ENV) or DEFAULT_NAMENSLISTEN_LIST_ID
    return (
        f"{BT_BASE_URL}/ajax/filterlist/de/parlament/plenum/abstimmung/liste/{list_id}"
        f"?offset=0&limit={NAMENSLISTEN_PAGE_LIMIT}"
    )


_NAMENSLISTEN_ROW_RE = re.compile(
    r'<a[^>]*class="e-linkListItem__anchor"[^>]*>\s*<span>\s*(\d{2}\.\d{2}\.\d{4}):\s*(.*?)\s*</span>',
    re.S,
)
_NAMENSLISTEN_XLSX_RE = re.compile(r'href="([^"]+\.xlsx)"')


def _is_publishable_xlsx_url(url: str) -> bool:
    # Checked at scrape time with the same allowlist render uses: an off-host
    # or non-https href would otherwise be cached in the dossier JSON and fail
    # every later (offline) render.
    try:
        publication.validate_external_url(url, "bundestag-roll-call")
    except (publication.PublicationStateError, ValueError):
        # urlsplit raises ValueError on e.g. "https://[broken"; an optional link
        # must never take the vote's other data down with it.
        return False
    return True


def namenslisten_blocks(html_text: str) -> list[str]:
    # Any row div starts a new block, regardless of attribute order or extra
    # classes (\b matches the class as a whole word anywhere in class=""):
    # otherwise a row without an XLSX would run into the next row and take
    # its file, or a markup change that reorders id/class would merge rows.
    return re.split(r'(?=<div\b[^>]*\bclass="[^"]*\be-linkListItem\b[^"]*")', html_text)[1:]


def parse_namenslisten_page(html_text: str) -> list[dict[str, str | None]]:
    """Each row on the Namenslisten page names one vote and links its XLSX
    export next to its PDF; there is no id shared with the roll-call vote
    pages, so every row is identified only by its "DD.MM.YYYY: <title>" text.
    """
    entries: list[dict[str, str | None]] = []
    for block in namenslisten_blocks(html_text):
        row_match = _NAMENSLISTEN_ROW_RE.search(block)
        xlsx_match = _NAMENSLISTEN_XLSX_RE.search(block)
        if not row_match:
            continue
        date = iso_date(row_match.group(1))
        if not date:
            continue
        # A row without a publishable file is kept with xlsx_url None: it still
        # counts when deciding whether a (date, title) key is ambiguous.
        xlsx_url = None
        if xlsx_match:
            xlsx_href = unescape(xlsx_match.group(1))
            candidate = xlsx_href if xlsx_href.startswith("http") else f"{BT_BASE_URL}{xlsx_href}"
            xlsx_url = candidate if _is_publishable_xlsx_url(candidate) else None
        entries.append({"date": date, "title": strip_tags(row_match.group(2)), "xlsx_url": xlsx_url})
    return entries


# The Namenslisten list is the same page for every vote, so one build process
# fetches it once. A failed fetch is not memoized: the next vote retries.
_namenslisten_entries: list[dict[str, str | None]] | None = None


def namenslisten_entries() -> list[dict[str, str | None]]:
    global _namenslisten_entries
    if _namenslisten_entries is None:
        try:
            html_text = fetch_html(namenslisten_list_url())
        except DipError:
            return []
        entries = parse_namenslisten_page(html_text)
        raw_rows = len(namenslisten_blocks(html_text))
        if not entries:
            # A placeholder page or drifted markup: warn, and let the next vote
            # retry rather than caching "no links" for the whole build.
            print("warning: Namenslisten page parsed to 0 rows; no XLSX links this time", file=sys.stderr)
            return []
        if raw_rows >= NAMENSLISTEN_PAGE_LIMIT:
            print(
                f"warning: Namenslisten page returned {raw_rows} rows (the request limit); "
                "votes older than the last row get no XLSX link",
                file=sys.stderr,
            )
        _namenslisten_entries = entries
    return _namenslisten_entries


def title_match_key(value: str | None) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "", value or "").lower()


def find_roll_call_xlsx_url(
    date: str | None, title: str | None, namenslisten: list[dict[str, str | None]]
) -> str | None:
    """Match a vote to its XLSX export by (date, normalized title): the two
    bundestag.de pages hyphenate the same title slightly differently, so
    matching compares letters and digits only. No match, or more than one
    distinct XLSX for the same key, returns None - never guess a URL.
    """
    matches = roll_call_xlsx_matches(date, title, namenslisten)
    return next(iter(matches)) if len(matches) == 1 else None


def roll_call_xlsx_matches(
    date: str | None, title: str | None, namenslisten: list[dict[str, str | None]]
) -> set[str | None]:
    target_title = title_match_key(title)
    if not date or not target_title:
        return set()
    # A fileless row (xlsx_url None) is a member too: a filed row sharing its
    # key may belong to that other vote, so {url, None} is ambiguous, not unique.
    return {
        entry["xlsx_url"]
        for entry in namenslisten
        if entry["date"] == date and title_match_key(entry["title"]) == target_title
    }


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
        document_numbers = sorted(set(_DOCUMENT_NUMBER_RE.findall(strip_tags(block))))
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
    page_cache: dict[str, str] | None = None,
) -> list[dict[str, Any]] | RollCallCandidateFetch:
    """Scan the roll-call list, newest first, for votes dated ``protocol_date``.

    ``page_cache`` maps a list URL to its HTML so the sittings of one build
    share the pages instead of each re-reading them from the top.
    """
    target_date = iso_date(protocol_date)
    if not target_date or scan_pages <= 0:
        result = RollCallCandidateFetch([], False, 0, False)
        return result if include_diagnostics else result.candidates

    candidates: list[dict[str, Any]] = []
    list_html_seen = False
    parsed_entry_count = 0
    page_size = 10
    scan_end = "budget_exhausted"
    pages_fetched = 0
    pages_from_cache = 0
    newest_entry_date: str | None = None
    for page_index in range(scan_pages):
        url = roll_call_list_url(roll_call_list_id, page_index * page_size, page_size)
        if page_cache is not None and url in page_cache:
            html_text = page_cache[url]
            pages_from_cache += 1
        else:
            if page_cache is not None and ROLL_CALL_OUTAGE_KEY in page_cache:
                # A list page already failed after its retries in this build:
                # further uncached pages would spend the same minutes on the
                # same outage, until the cooldown ends. Cached pages are served.
                failed_at, _, message = page_cache[ROLL_CALL_OUTAGE_KEY].partition("|")
                if time.monotonic() - float(failed_at) < ROLL_CALL_OUTAGE_COOLDOWN_SECONDS:
                    raise DipError(f"roll-call list unavailable earlier in this build: {message}")
                del page_cache[ROLL_CALL_OUTAGE_KEY]
            try:
                html_text = fetch_html(url)
            except DipError as exc:
                # Only a network or server failure says the site is down; a 404
                # or 403 on one page says nothing about the next sitting's pages.
                if page_cache is not None and getattr(exc, "transient", False):
                    page_cache[ROLL_CALL_OUTAGE_KEY] = f"{time.monotonic()}|{exc}"
                raise
            pages_fetched += 1
            # An empty page is not remembered: it may be a maintenance page,
            # and every later sitting of the build would reuse it as the end.
            if page_cache is not None and parse_roll_call_list_page(html_text):
                page_cache[url] = html_text
        if html_text.strip():
            list_html_seen = True
        page_entries = parse_roll_call_list_page(html_text)
        if page_index == 0:
            first_dates = [entry.get("date") for entry in page_entries if entry.get("date")]
            newest_entry_date = max(first_dates) if first_dates else None
        parsed_entry_count += len(page_entries)
        if not page_entries:
            scan_end = "list_end"
            break
        candidates.extend(entry for entry in page_entries if entry.get("date") == target_date)
        dated = [entry.get("date") for entry in page_entries if entry.get("date")]
        if dated and min(dated) < target_date:
            scan_end = "date_passed"
            break
    result = RollCallCandidateFetch(
        candidates=candidates,
        list_html_seen=list_html_seen,
        parsed_entry_count=parsed_entry_count,
        # A blank page 1 is as unverifiable as a page whose markup changed: it
        # must not read as "the list is empty, so this sitting had no votes".
        selector_warning=parsed_entry_count == 0,
        scan_end=scan_end,
        pages_fetched=pages_fetched,
        pages_from_cache=pages_from_cache,
        newest_entry_date=newest_entry_date,
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

    total = vote.get("total") or {}
    yes_count = int(total.get("yes") or 0)
    no_count = int(total.get("no") or 0)
    official = scrape_official_vote_result(detail_html, yes_count, no_count, vote.get("document_numbers"))
    result_raw, result_source = vote_result(
        official=official, yes_count=yes_count, no_count=no_count, title=vote.get("title")
    )
    enriched_vote["result_raw"] = result_raw
    enriched_vote["result_source"] = result_source

    # The XLSX link is optional provenance from a second page: a failed fetch
    # leaves it unknown rather than discarding the fractions/members/result
    # already fetched for this vote.
    xlsx_matches = roll_call_xlsx_matches(vote.get("date"), vote.get("title"), namenslisten_entries())
    enriched_vote["xlsx_url"] = next(iter(xlsx_matches)) if len(xlsx_matches) == 1 else None
    # A successful fetch that found two files for this vote is a refusal, not
    # missing data: carry_forward_vote_provenance must not restore an old link.
    enriched_vote["xlsx_ambiguous"] = len(xlsx_matches) > 1
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


def _days_since(day: str) -> int | None:
    """Whole days from an ISO date to today (UTC); None for a date that does not exist."""
    try:
        return (datetime.now(timezone.utc).date() - date.fromisoformat(day)).days
    except ValueError:
        return None


def match_roll_call_votes(
    top: dict[str, Any],
    linked_drucksachen: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    cache: dict[str, dict[str, Any]],
    errors: list[DipError] | None = None,
) -> list[dict[str, Any]]:
    """The roll-call votes whose Drucksachen overlap the TOP's.

    With ``errors`` given, a failed detail fetch is appended there and the
    votes fetched so far are still returned: a later failure must not discard
    a vote that was fetched successfully. Without it the error propagates.
    """
    top_numbers = top_document_numbers(top, linked_drucksachen)
    matches: list[dict[str, Any]] = []
    for candidate in candidates:
        vote_numbers = set(candidate.get("document_numbers") or [])
        if top_numbers and vote_numbers and top_numbers & vote_numbers:
            vote_id = str(candidate["id"])
            if vote_id not in cache:
                try:
                    cache[vote_id] = fetch_roll_call_vote_detail(candidate)
                except DipError as exc:
                    if errors is None:
                        raise
                    errors.append(exc)
                    break
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


def summary_source_fingerprint(top: dict[str, Any]) -> str:
    """Bind a cached summary to the exact ordered source passed to the model."""
    canonical = {
        "top_id": clean_text(str(top.get("top_id") or "")),
        "heading": clean_text(str(top.get("heading") or "")),
        "chunks": [
            {
                "id": chunk.get("id"),
                "rede_id": chunk.get("rede_id"),
                "source_page": chunk.get("source_page"),
                "speaker": chunk.get("speaker"),
                "text": clean_text(chunk.get("text") or ""),
            }
            for chunk in summary_source_chunks(top)
        ],
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_usable_summary(
    summary: Any,
    top: dict[str, Any],
    *,
    pdf_url: str | None = None,
    pdf_page_count: int | None = None,
) -> tuple[bool, str | None]:
    if not isinstance(summary, dict) or not clean_text(summary.get("text") or ""):
        return False, "invalid_citations"
    if summary.get("summary_schema_version") != SUMMARY_SCHEMA_VERSION:
        return False, "source_changed"
    if summary.get("prompt_version") != SUMMARY_PROMPT_VERSION:
        return False, "source_changed"
    if summary.get("source_fingerprint") != summary_source_fingerprint(top):
        return False, "source_changed"
    chunks = summary.get("source_chunks")
    if not isinstance(chunks, list) or not SUMMARY_CHUNK_MIN <= len(chunks) <= SUMMARY_CHUNK_MAX:
        return False, "invalid_citations"
    speech_ids = {
        str(speech.get("rede_id"))
        for speech in (top.get("speeches") or top.get("xml_speakers") or [])
        if speech.get("rede_id")
    }
    seen_ids: set[str] = set()
    seen_targets: set[str] = set()
    for chunk in chunks:
        chunk_id = clean_text(str(chunk.get("id") or ""))
        text = clean_text(chunk.get("text") or "")
        if not chunk_id or not text or chunk_id in seen_ids:
            return False, "duplicate_citation" if chunk_id in seen_ids else "invalid_citations"
        seen_ids.add(chunk_id)
        rede_id = str(chunk.get("rede_id") or "").strip()
        page = chunk.get("source_page")
        page_number = page.get("page") if isinstance(page, dict) else page
        target = None
        if rede_id and rede_id in speech_ids:
            target = f"speech:{rede_id}"
        elif page_number is not None and str(page_number).isdigit() and int(page_number) > 0 and pdf_url:
            if pdf_page_count is not None and int(page_number) > pdf_page_count:
                return False, "page_out_of_bounds"
            target = f"page:{int(page_number)}"
        if target is None:
            return False, "missing_target"
        if target in seen_targets:
            return False, "duplicate_citation"
        seen_targets.add(target)
    return True, None


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


def request_anthropic_summary(prompt: str, api_key: str, model: str, timeout: float = 60) -> str:
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
    return anthropic_text_from_response(post_json(ANTHROPIC_MESSAGES_URL, payload, headers, "Anthropic API", timeout))


def request_gemini_summary(prompt: str, api_key: str, model: str, timeout: float = 60) -> str:
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
    return gemini_text_from_response(post_json(url, payload, headers, "Gemini API", timeout))


def request_summary_text(provider: str, prompt: str, api_key: str, model: str, timeout: float = 60) -> str:
    if provider == "gemini":
        return request_gemini_summary(prompt, api_key, model, timeout)
    return request_anthropic_summary(prompt, api_key, model, timeout)


def generate_top_summary(
    top: dict[str, Any],
    provider: str,
    api_key: str,
    models: list[str],
    *,
    budget: dict[str, int] | None = None,
    timeout: float = 60,
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
            if budget is not None:
                if budget["used"] >= budget["limit"]:
                    raise SummaryError("summary_budget_exhausted")
                budget["used"] += 1
            summary = parse_summary_response(request_summary_text(provider, prompt, api_key, model, timeout), allowed_ids)
            chunks_by_id = {chunk["id"]: chunk for chunk in chunks}
            result = {
                "provider": provider,
                "model": model,
                "summary_schema_version": SUMMARY_SCHEMA_VERSION,
                "prompt_version": SUMMARY_PROMPT_VERSION,
                "source_fingerprint": summary_source_fingerprint(top),
                "text": summary["text"],
                "source_chunk_ids": summary["source_chunk_ids"],
                "source_chunks": [chunks_by_id[chunk_id] for chunk_id in summary["source_chunk_ids"]],
            }
            valid, reason = validate_usable_summary(result, top)
            if not valid:
                raise SummaryError(reason or "invalid_citations")
            return result
        except SummaryError as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return None


def enrich_with_llm_summaries(report: dict[str, Any], args: argparse.Namespace) -> None:
    mode = getattr(args, "summary_mode", "auto")
    eligible = sum(
        1
        for item in report.get("agenda_items") or []
        if len(
            summary_source_chunks(
                {
                    "top_id": item.get("top_id"),
                    "heading": item.get("heading"),
                    "speeches": item.get("xml_speakers") or [],
                }
            )
        )
        >= SUMMARY_CHUNK_MIN
    )
    if mode == "off":
        report["summary_generation"] = {"enabled": False}
        report.setdefault("acquisition", {})["summaries"] = publication.DomainFacts(
            domain="summaries",
            acquisition_state=publication.AcquisitionState.NOT_REQUESTED,
            source="llm-with-bundestag-citations",
            records=0,
            counters={"eligible": eligible, "generated": 0, "omitted": eligible, "failed": 0, "fallbacks": 0},
        ).as_dict()
        return

    provider = configured_summary_provider(args)
    api_key = summary_api_key(args, provider)
    models = summary_model_chain(args, provider)
    if not api_key:
        env_hint = "GEMINI_API_KEY or GOOGLE_API_KEY" if provider == "gemini" else "ANTHROPIC_API_KEY"
        report["summary_generation"] = {
            "enabled": False,
            "provider": provider,
            "reason": "source_unavailable",
            "models": models,
        }
        report.setdefault("acquisition", {})["summaries"] = publication.DomainFacts(
            domain="summaries",
            acquisition_state=publication.AcquisitionState.FAILED,
            source="llm-with-bundestag-citations",
            records=0,
            rejected=eligible,
            failure_reasons=("source_unavailable",),
            counters={"eligible": eligible, "generated": 0, "omitted": 0, "failed": eligible, "fallbacks": 0},
        ).as_dict()
        if mode == "required":
            flag_hint = "--gemini-api-key" if provider == "gemini" else "--anthropic-api-key"
            article = "an" if provider[:1].lower() in "aeiou" else "a"
            raise DipError(f"Provide {article} {provider} API key via {flag_hint} or {env_hint} for summaries.")
        return

    failures: list[dict[str, str]] = []
    budget = {
        "used": 0,
        "limit": max(0, int(getattr(args, "summary_max_calls", 25))),
    }
    if (mode == "required" or getattr(args, "summary_required_preflight", False)) and budget["limit"] < eligible:
        raise DipError(
            "summary_budget_exhausted: required summaries need at least "
            f"{eligible} provider call(s), but --summary-max-calls is {budget['limit']}."
        )
    timeout = max(1.0, float(getattr(args, "summary_timeout", 60)))
    for item in report.get("agenda_items") or []:
        try:
            parsed_top = {
                "top_id": item.get("top_id"),
                "heading": item.get("heading"),
                "speeches": item.get("xml_speakers") or [],
            }
            summary = generate_top_summary(
                parsed_top,
                provider,
                api_key,
                models,
                budget=budget,
                timeout=timeout,
            )
            if summary:
                item["llm_summary"] = summary
        except SummaryError as exc:
            failure_code = summary_failure_code(exc)
            failures.append(
                {
                    "top_id": str(item.get("top_id") or item.get("index") or "unknown"),
                    "reason": failure_code,
                }
            )
            print(
                f"warning: summary generation failed for {item.get('top_id') or item.get('index')}: {exc}",
                file=sys.stderr,
            )
            if mode == "required":
                raise DipError(f"Summary generation failed for {item.get('top_id')}: {exc}") from exc

    generated = sum(1 for item in report.get("agenda_items") or [] if item.get("llm_summary"))
    failed = len(failures)
    omitted = max(0, eligible - generated - failed)
    attempted_at = utc_now() if budget["used"] else None
    failure_reasons = tuple(dict.fromkeys(failure["reason"] for failure in failures))
    if failures:
        acquisition_state = (
            publication.AcquisitionState.PARTIAL if generated else publication.AcquisitionState.FAILED
        )
    else:
        acquisition_state = publication.AcquisitionState.COMPLETE
    report["summary_generation"] = {
        "enabled": True,
        "provider": provider,
        "models": models,
        "generated_top_count": generated,
        "request_count": budget["used"],
        "request_budget": budget["limit"],
        "failures": failures,
    }
    report.setdefault("acquisition", {})["summaries"] = publication.DomainFacts(
        domain="summaries",
        acquisition_state=acquisition_state,
        source="llm-with-bundestag-citations",
        records=generated,
        rejected=failed,
        failure_reasons=failure_reasons,
        acquired_at=attempted_at if generated else None,
        attempted_at=attempted_at,
        attempted=bool(attempted_at),
        counters={
            "eligible": eligible,
            "generated": generated,
            "omitted": omitted,
            "failed": failed,
            "fallbacks": 0,
        },
    ).as_dict()


def xml_top_fields(top: dict[str, Any]) -> dict[str, Any]:
    """The keys of a report's agenda item that come from the parsed XML alone:
    Reden (``xml_speakers``) and Beiträge (``xml_contributions``). Used when a
    report is built and when a cached one is re-parsed from its cached XML."""
    return {
        "question_formats": top["question_formats"],
        "xml_speech_count": len(top["speeches"]),
        "xml_contributions": [
            {
                "kind": contribution["kind"],
                "rede_id": contribution["rede_id"],
                "parent_rede_id": contribution["parent_rede_id"],
                "sequence": contribution["sequence"],
                "source_page": contribution["source_page"],
                "speaker": contribution["speaker"],
                "paragraph_count": contribution["paragraph_count"],
                "char_count": contribution["char_count"],
                "text": contribution["text"],
                "paragraphs": contribution["paragraphs"],
                "snippet": contribution["snippet"],
            }
            for contribution in top["contributions"]
        ],
        "xml_speakers": [
            {
                "rede_id": speech["rede_id"],
                "source_page": speech["source_page"],
                "speaker": speech["speaker"],
                "paragraph_count": speech["paragraph_count"],
                "char_count": speech["char_count"],
                "unattributed_char_count": speech["unattributed_char_count"],
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
    }


def contribution_summary(agenda_items: list[dict[str, Any]]) -> dict[str, Any]:
    """The ``validation_summary`` keys for Reden and Beiträge, over parsed
    agenda items."""
    contributions = [c for top in agenda_items for c in top["contributions"]]
    return {
        "xml_speech_count": sum(len(top["speeches"]) for top in agenda_items),
        "xml_contribution_counts": speech_kinds.kind_counts(contributions),
        "fragestunde_questions_without_person": sum(
            1
            for c in contributions
            if c["kind"] == speech_kinds.FRAGESTUNDE_FRAGE
            and c["rede_id"] is None
            and not (c["speaker"] or {}).get("xml_redner_id")
        ),
    }


KIND_MISMATCH_WARNING = "Die XML zählt "


def kind_mismatch_warnings(mismatches: list[dict[str, Any]]) -> list[str]:
    def label(mismatch: dict[str, Any]) -> str:
        singular, plural = speech_kinds.KIND_LABELS[mismatch["kind"]]
        return singular if mismatch["xml"] == 1 else plural

    return [f"{KIND_MISMATCH_WARNING}{m['xml']} {label(m)}, DIP {m['dip']}." for m in mismatches]


def reparse_report_xml(report: dict[str, Any], parsed_xml: dict[str, Any]) -> None:
    """Replace what a cached report holds of Reden and Beiträge with what the
    current parser reads from the sitting's XML, leaving every DIP-derived field
    alone. Agenda items pair up by ``index``; the XML is the same document, so
    the numbering does not move."""
    by_index = {top["index"]: top for top in parsed_xml["agenda_items"]}
    for item in report.get("agenda_items") or []:
        top = by_index.get(item.get("index"))
        if top is not None:
            item.update(xml_top_fields(top))
    summary = report.setdefault("validation_summary", {})
    summary.update(contribution_summary(parsed_xml["agenda_items"]))
    mismatches = speech_kinds.dip_mismatches(
        summary["xml_contribution_counts"], (report.get("api_records") or {}).get("aktivitaeten") or []
    )
    summary["contribution_dip_mismatches"] = mismatches
    report["warnings"] = [
        warning for warning in report.get("warnings") or [] if not warning.startswith(KIND_MISMATCH_WARNING)
    ] + kind_mismatch_warnings(mismatches)


def write_text_atomic(path: Path, text: str) -> None:
    """A crash mid-write must never leave a truncated file where a cached report,
    the catalog or a cached XML used to be."""
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def enrich_with_api(
    client: ApiClient,
    protocol: dict[str, Any],
    parsed_xml: dict[str, Any],
    person_limit: int,
    vote_scan_pages: int = 30,
    roll_call_list_id: str | None = None,
    progress: Callable[[str], None] | None = None,
    roll_call_page_cache: dict[str, str] | None = None,
) -> dict[str, Any]:
    protocol_id = protocol["id"]
    positions = client.list_all("/vorgangsposition", {"f.plenarprotokoll": protocol_id})
    if progress:
        progress(f"Fetched {len(positions)} proceeding position(s).")
    activities = client.list_all("/aktivitaet", {"f.plenarprotokoll": protocol_id})
    if progress:
        progress(f"Fetched {len(activities)} parliamentary activity record(s).")
    # A failed roll-call fetch is a vote acquisition failure, not a reason to
    # lose the whole dossier: the first error stops further vote requests and
    # the state below records it.
    vote_fetch_error: DipError | None = None
    try:
        roll_call_fetch = fetch_roll_call_vote_candidates(
            protocol.get("datum"),
            vote_scan_pages,
            roll_call_list_id,
            include_diagnostics=True,
            page_cache=roll_call_page_cache,
        )
    except DipError as exc:
        vote_fetch_error = exc
        roll_call_fetch = RollCallCandidateFetch([], False, 0, False, scan_end="failed")
        print(f"warning: roll-call list unavailable for {protocol.get('dokumentnummer') or protocol_id}: {exc}", file=sys.stderr)
    assert isinstance(roll_call_fetch, RollCallCandidateFetch)
    roll_call_candidates = roll_call_fetch.candidates
    if progress:
        progress(f"Found {len(roll_call_candidates)} roll-call vote candidate(s).")
        if vote_scan_pages > 0:
            progress(
                f"Roll-call scan ended by {roll_call_fetch.scan_end}: "
                f"{roll_call_fetch.pages_fetched} list page(s) fetched, "
                f"{roll_call_fetch.pages_from_cache} reused from this build."
            )
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
        votes = []
        if vote_fetch_error is None:
            match_errors: list[DipError] = []
            votes = match_roll_call_votes(
                top, linked_drucksachen, roll_call_candidates, roll_call_cache, match_errors
            )
            if match_errors:
                vote_fetch_error = match_errors[0]
                print(
                    f"warning: roll-call vote details unavailable for {protocol.get('dokumentnummer') or protocol_id}: {vote_fetch_error}",
                    file=sys.stderr,
                )

        enriched_tops.append(
            {
                "index": top["index"],
                "top_id": top["top_id"],
                "heading": top["heading"],
                "page_range": top["page_range"],
                "xml_drucksachen": top["drucksachen"],
                **xml_top_fields(top),
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
    attached_vote_ids = {str(vote["id"]) for top in enriched_tops for vote in top["votes"]}
    unmatched_candidates = [
        candidate for candidate in roll_call_candidates if str(candidate["id"]) not in attached_vote_ids
    ]
    if progress and vote_scan_pages > 0:
        # Every fetched vote costs two requests (detail page, member list); the
        # Namenslisten page is one more per build, shared by all sittings.
        progress(
            f"Roll-call details: {len(roll_call_cache)} vote(s) fetched "
            f"({2 * len(roll_call_cache)} requests), {len(unmatched_candidates)} candidate(s) matched no TOP."
        )
    if roll_call_candidates and not attached_vote_ids:
        warnings.append("Für dieses Sitzungsdatum wurden namentliche Abstimmungen gefunden, aber keine passte per Drucksachennummer zu einem TOP.")
    elif unmatched_candidates and vote_fetch_error is None:
        warnings.append(
            f"{len(unmatched_candidates)} von {len(roll_call_candidates)} namentlichen Abstimmungen dieses Sitzungsdatums "
            "passten per Drucksachennummer zu keinem TOP."
        )
    if unmatched_candidates and vote_fetch_error is None:
        for candidate in unmatched_candidates:
            print(
                f"warning: [{protocol.get('dokumentnummer') or protocol_id}] roll-call vote {candidate['id']} "
                f"({candidate.get('title')!r}, {candidate.get('document_numbers') or 'no document numbers'}) "
                "matched no TOP",
                file=sys.stderr,
            )
    if roll_call_fetch.scan_end == "budget_exhausted":
        message = (
            f"warning: [{protocol.get('dokumentnummer') or protocol_id}] roll-call scan used all "
            f"{vote_scan_pages} list page(s) without reaching {protocol.get('datum')}; older votes may be missing. "
            "Fix: raise --vote-scan-pages."
        )
        warnings.append(
            f"Die Suche in der Liste der namentlichen Abstimmungen endete nach {vote_scan_pages} Seiten, "
            "bevor sie das Sitzungsdatum passierte; Abstimmungen können fehlen."
        )
        print(message, file=sys.stderr)
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

    kind_mismatches = speech_kinds.dip_mismatches(
        speech_kinds.kind_counts(c for top in agenda_items for c in top["contributions"]), activities
    )
    warnings.extend(kind_mismatch_warnings(kind_mismatches))

    vote_records = len(attached_vote_ids)
    if vote_scan_pages <= 0:
        vote_facts = publication.DomainFacts(
            domain="votes",
            acquisition_state=publication.AcquisitionState.NOT_REQUESTED,
            source="bundestag-roll-call",
            records=0,
        )
    else:
        attempted_at = utc_now()
        # A complete acquisition needs full evidence: the scan reached the end
        # of the list or passed the sitting's date, no request failed and every
        # candidate found its TOP. Anything else is partial (some votes attached)
        # or failed (none), with the reason named. Unmatched candidates are also
        # logged above and counted in api_totals.
        failure_reasons: list[str] = []
        if roll_call_fetch.selector_warning:
            failure_reasons.append("source_changed")
        if vote_fetch_error is not None:
            failure_reasons.append("source_unavailable")
        if roll_call_fetch.scan_end == "budget_exhausted":
            failure_reasons.append("scan_budget_exhausted")
        # A vote the list shows but no TOP claims is not in the store: the
        # sitting's votes are known to be short, so they cannot be complete.
        if unmatched_candidates and vote_fetch_error is None:
            failure_reasons.append("unmatched_candidate")
        # A recent sitting with no candidate on a list whose newest entry is
        # older than the sitting: the list may simply not have caught up.
        target_day = iso_date(protocol.get("datum"))
        if (
            not roll_call_candidates
            and vote_fetch_error is None
            and roll_call_fetch.scan_end == "date_passed"
            and roll_call_fetch.newest_entry_date
            and target_day
            and roll_call_fetch.newest_entry_date < target_day
            and _days_since(target_day) is not None
            and 0 <= _days_since(target_day) <= ROLL_CALL_LIST_LAG_DAYS
        ):
            failure_reasons.append("source_stale")
        if failure_reasons:
            vote_facts = publication.DomainFacts(
                domain="votes",
                acquisition_state=(
                    publication.AcquisitionState.PARTIAL
                    if vote_records or failure_reasons in (["unmatched_candidate"], ["source_stale"])
                    else publication.AcquisitionState.FAILED
                ),
                source="bundestag-roll-call",
                records=vote_records,
                rejected=1 if roll_call_fetch.selector_warning else 0,
                failure_reasons=tuple(failure_reasons),
                acquired_at=attempted_at if vote_records else None,
                attempted_at=attempted_at,
                attempted=True,
            )
        else:
            # A verified zero-vote sitting is stamped too: acquired_at says
            # the list was read to the end of the date, not that a vote exists.
            vote_facts = publication.DomainFacts(
                domain="votes",
                acquisition_state=publication.AcquisitionState.COMPLETE,
                source="bundestag-roll-call",
                records=vote_records,
                acquired_at=attempted_at,
                attempted_at=attempted_at,
                attempted=True,
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
            "unmatched_roll_call_vote_count": len(unmatched_candidates),
            "roll_call_scan_end": roll_call_fetch.scan_end,
            "roll_call_scan_pages": vote_scan_pages,
            "contribution_dip_mismatches": kind_mismatches,
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
            "unmatched_roll_call_vote_ids": [str(candidate["id"]) for candidate in unmatched_candidates],
        },
        "agenda_items": enriched_tops,
        "warnings": warnings,
        "acquisition": {"votes": vote_facts.as_dict()},
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
    xml_cache_path = getattr(args, "xml_cache_path", None)
    if xml_cache_path is not None:
        xml_cache_path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomic(xml_cache_path, xml_text)
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
        roll_call_page_cache=getattr(args, "roll_call_page_cache", None),
    )

    agenda_items = enrichment["agenda_items"]
    if args.limit_tops is not None:
        agenda_items = agenda_items[: args.limit_tops]

    xml_drucksache_count = sum(len(top["drucksachen"]) for top in parsed_xml["agenda_items"])
    tops_with_xml_drucksachen = sum(1 for top in parsed_xml["agenda_items"] if top["drucksachen"])
    tops_with_api_positions = sum(1 for top in enrichment["agenda_items"] if top["api"]["positions"])
    tops_with_api_drucksachen = sum(1 for top in enrichment["agenda_items"] if top["api"]["linked_drucksachen"])
    acquisition = enrichment.get("acquisition")
    if not acquisition:
        # enrich_with_api always reports its own vote acquisition. Without one,
        # only "not requested" is a statement the caller can make; claiming a
        # requested scan complete would be unsupported.
        if int(getattr(args, "vote_scan_pages", 30)) > 0:
            raise DipError("Vote acquisition was requested but the enrichment reported no vote acquisition state.")
        acquisition = {
            "votes": publication.DomainFacts(
                domain="votes",
                acquisition_state=publication.AcquisitionState.NOT_REQUESTED,
                source="bundestag-roll-call",
                records=int((enrichment.get("api_totals") or {}).get("matched_roll_call_vote_count") or 0),
            ).as_dict()
        }

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
            **contribution_summary(parsed_xml["agenda_items"]),
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
        "acquisition": acquisition,
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
    parser.add_argument("--summary-max-calls", type=int, default=25, help="Hard LLM request budget.")
    parser.add_argument("--summary-timeout", type=float, default=60, help="Per-request timeout in seconds.")
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
