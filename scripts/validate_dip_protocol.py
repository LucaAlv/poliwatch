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
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Literal, NamedTuple

import derive
import publication_state as publication
import reviewed_units
import protocol_cut
import speech_kinds
import vote_links
from stable_ids import source_index


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
    def __init__(self, message: str, *, source_rejected: bool = False):
        super().__init__(message)
        self.source_rejected = source_rejected


class SourceSlowError(RuntimeError):
    """A source answered slower than the pacing allows: the run stops.

    Deliberately not a DipError, which a build skips as one unavailable
    sitting and goes on: a slow answer is dserver's first sign of a block.
    """


class DipShapeError(DipError):
    def __init__(self, message: str, documents: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.documents = documents or []
        self.incomplete_membership = True


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


#: Set to a file path to append one line per outbound request attempt (UTC time,
#: source, target, attempt, outcome, seconds), so the moment a source stops
#: answering is known exactly (A3 pilot, Finding 2). The DIP key is never written.
REQUEST_LOG_ENV = "DIP_REQUEST_LOG"
_APIKEY_RE = re.compile(r"apikey=[^&\s]*")


def _read_logged(req: urllib.request.Request, timeout: float, source: str, target: str, attempt: int) -> bytes:
    """urlopen and read the body; with DIP_REQUEST_LOG set, log the attempt
    whatever its outcome."""
    started = time.monotonic()
    outcome = "?"
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            body = res.read()
            outcome = str(getattr(res, "status", "") or "ok")
        return body
    except urllib.error.HTTPError as exc:
        outcome = f"HTTP {exc.code}"
        raise
    except BaseException as exc:
        outcome = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        log_path = os.environ.get(REQUEST_LOG_ENV)
        if log_path:
            stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            fields = [stamp, source, target, f"attempt {attempt + 1}", outcome, f"{time.monotonic() - started:.2f}s"]
            line = _APIKEY_RE.sub("apikey=…", "\t".join(" ".join(f.split()) for f in fields))
            # A log that cannot be written must not turn an answer into a retried failure.
            try:
                with open(log_path, "a", encoding="utf-8") as log:
                    log.write(line + "\n")
            except OSError as exc:
                print(f"warning: {REQUEST_LOG_ENV} {log_path} is not writable: {exc}", file=sys.stderr)


def page_count(page: dict[str, Any]) -> int | None:
    """DIP's ``numFound`` for a cursor-paged list, or None when the page carries no
    usable count."""
    count = page.get("numFound")
    return count if isinstance(count, int) and not isinstance(count, bool) else None


def holds_all(documents: list[dict[str, Any]], count: int | None) -> bool:
    """True once ``documents`` hold ``count`` distinct ids: the next cursor page
    would only confirm the end (half of a sitting's Vorgang requests, 2026-10-23).
    A repeated document across pages does not count twice, and without a count
    or an id the cursor alone ends the list."""
    if count is None or any(not d.get("id") for d in documents):
        return False
    return len({str(d["id"]) for d in documents}) >= count


#: Consecutive DIP requests that may fail (after their retries) before the run
#: stops asking DIP. A blocked DIP times out every attempt at 60 s, and on
#: 2026-10-23 the run kept asking (a3-pilot.md, second attempt).
DIP_FAILURE_LIMIT = 2


class DipUnavailable(DipError):
    """DIP failed DIP_FAILURE_LIMIT requests in a row; this run sends it no more."""


@dataclass
class DipBreaker:
    """One per run, shared by every sitting's ApiClient: counts DIP requests that
    failed in a row (timeouts, resets, 429/5xx, unreadable bodies; a 404 is an
    answer) and, at ``limit``, stops the run's further DIP requests."""

    limit: int = DIP_FAILURE_LIMIT
    consecutive: int = 0
    last_error: str = ""

    def check(self) -> None:
        if self.consecutive >= self.limit:
            raise DipUnavailable(
                f"DIP stopped answering: {self.consecutive} requests in a row failed (last: {self.last_error}); "
                "this run sends it no more requests"
            )

    def failed(self, error: BaseException) -> None:
        self.consecutive += 1
        self.last_error = str(error)

    def answered(self) -> None:
        self.consecutive = 0


@dataclass(frozen=True)
class ApiClient:
    api_key: str
    base_url: str = BASE_URL
    sleep_seconds: float = 0.0
    timeout: int = 60
    retries: int = 2
    retry_delay_seconds: float = 1.5
    breaker: DipBreaker | None = None

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
        target = f"{path}?{urllib.parse.urlencode({k: v for k, v in params.items() if k != 'apikey'}, doseq=True)}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        if self.breaker is not None:
            self.breaker.check()
        for attempt in range(self.retries + 1):
            try:
                data = json.loads(_read_logged(req, self.timeout, "dip", target, attempt).decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                transient = exc.code in {429, 500, 502, 503, 504}
                if transient and attempt < self.retries:
                    self._retry_delay(path, exc, attempt)
                    continue
                if self.breaker is not None and transient:
                    self.breaker.failed(exc)
                elif self.breaker is not None:
                    self.breaker.answered()  # a 404 or 400 is DIP answering
                raise DipError(f"DIP API HTTP {exc.code} for {path}: {body[:500]}") from exc
            except ValueError as exc:
                # A 200 that is not JSON (an HTML bot-challenge page, a cut-off body): retried like a reset.
                if attempt < self.retries:
                    self._retry_delay(path, exc, attempt)
                    continue
                if self.breaker is not None:
                    self.breaker.failed(exc)
                raise DipError(f"DIP API returned an unreadable body for {path}: {exc}") from exc
            except (OSError, http.client.HTTPException) as exc:
                # URLError and timeouts are OSErrors, and so is a connection
                # reset while the body is being read, which urlopen does not
                # wrap: without it one reset ended a two-hour backfill.
                if attempt < self.retries:
                    self._retry_delay(path, exc, attempt)
                    continue
                if self.breaker is not None:
                    self.breaker.failed(exc)
                raise DipError(f"DIP API request failed for {path}: {exc}") from exc
        if self.breaker is not None:
            self.breaker.answered()
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)
        return data

    def list_all(
        self, path: str, params: dict[str, Any] | None = None, *, page_pause: float = 0.0
    ) -> list[dict[str, Any]]:
        """Every document of a cursor-paged list. ``page_pause`` seconds go before
        each request after the first, for callers that pace their requests."""
        params = dict(params or {})
        documents: list[dict[str, Any]] = []
        previous_cursor = None
        malformed_rows = False
        while True:
            if previous_cursor is not None and page_pause:
                time.sleep(page_pause)
            page = self.get_json(path, params)
            if (
                not isinstance(page, dict)
                or not isinstance(page.get("documents"), list)
            ):
                raise DipShapeError(f"DIP API returned an unexpected body for {path}: {str(page)[:200]}", documents)
            batch = page["documents"]
            malformed_rows |= any(not isinstance(d, dict) for d in batch)
            documents.extend(d for d in batch if isinstance(d, dict))
            cursor = page.get("cursor")
            if not batch or not cursor or cursor == previous_cursor or holds_all(documents, page_count(page)):
                break
            previous_cursor = cursor
            params["cursor"] = cursor
        if malformed_rows:
            raise DipShapeError(f"DIP API returned non-object documents for {path}", documents)
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
    parts = urllib.parse.urlsplit(url)
    target = parts.path + (f"?{parts.query}" if parts.query else "")
    for attempt in range(PAGE_FETCH_RETRIES + 1):
        try:
            return _read_logged(req, 60, parts.netloc, target, attempt).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DipError(f"Failed to fetch {kind} {url}: {exc}") from exc
        except urllib.error.HTTPError as exc:
            if exc.fp is not None:
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


#: Vorgang ids per ``/vorgang?f.id=`` request. DIP answered 400 ids in one call
#: (measured 2026-10-04, paginated by list_all in pages of 100); 100 keeps one
#: request to one page.
VORGANG_BATCH = 100


def vorgang_cache_record(document: dict[str, Any]) -> dict[str, Any]:
    """What the Vorgang cache keeps of a DIP ``/vorgang`` record. ``abstract`` and
    ``titel`` are not used by the Politikfelder; a vote's "Worum es geht" reads them.
    A Sachgebiet that is not a list of labels raises DipError."""
    sachgebiet = document.get("sachgebiet")
    if sachgebiet is None:
        sachgebiet = []
    if not isinstance(sachgebiet, list) or not all(isinstance(label, str) for label in sachgebiet):
        # A string would be cached as single letters, and stay: refuse it like a failed call.
        raise DipShapeError(f"DIP Vorgang {document.get('id')} has an unexpected sachgebiet: {str(sachgebiet)[:100]}")
    deskriptor = document.get("deskriptor") or []
    descriptors = [
        str(d.get("name"))
        for d in (deskriptor if isinstance(deskriptor, list) else [])
        if isinstance(d, dict) and d.get("typ") == "Sachbegriffe" and d.get("name")
    ]
    return {
        "sachgebiet": list(sachgebiet),
        "deskriptor_sachbegriffe": descriptors,
        "titel": document.get("titel"),
        "abstract": document.get("abstract"),
        "vorgangstyp": document.get("vorgangstyp"),
        "aktualisiert": document.get("aktualisiert"),
    }


def vorgang_id(document: dict[str, Any]) -> str:
    value = document.get("id")
    if type(value) not in (str, int) or not str(value).strip():
        raise DipShapeError(f"DIP Vorgang has an unusable id: {value!r}")
    return str(value).strip()


def fetch_vorgaenge(
    client: ApiClient, ids: list[str], *, page_pause: float = 0.0,
    on_shape_error: Callable[[DipShapeError], None] | None = None,
) -> dict[str, dict[str, Any]]:
    """Cache records of the Vorgänge ``ids``, batched. An id DIP does not return
    gets an empty record only when response membership is complete. Malformed
    records are warned about and left retryable; outages raise DipError."""
    def warn(exc: DipShapeError) -> None:
        print(f"warning: Vorgang validation: {exc}", file=sys.stderr)
        if on_shape_error is not None:
            on_shape_error(exc)

    records: dict[str, dict[str, Any]] = {}
    for start in range(0, len(ids), VORGANG_BATCH):
        batch = [str(i) for i in ids[start : start + VORGANG_BATCH]]
        complete = True
        try:
            documents = client.list_all("/vorgang", {"f.id": batch}, page_pause=page_pause)
        except DipShapeError as exc:
            warn(exc)
            documents = exc.documents
            complete = False
        found: set[str] = set()
        for document in documents:
            try:
                record_id = vorgang_id(document)
            except DipShapeError as exc:
                warn(exc)
                complete = False
                continue
            if record_id not in batch:
                continue
            found.add(record_id)
            try:
                records[record_id] = vorgang_cache_record(document)
            except DipShapeError as exc:
                warn(exc)
        if complete:
            for record_id in set(batch) - found:
                records[record_id] = vorgang_cache_record({})
    return records


def resolve_dokumentnummer(client: ApiClient, number: str, *, page_pause: float = 0.0) -> list[dict[str, Any]]:
    """The Vorgänge a Drucksache number belongs to, as raw DIP records. One lookup
    per number (a list_all, so two requests): a repeated ``f.dokumentnummer``
    returns one deduplicated union, so a batch cannot say which number belongs to
    which Vorgang."""
    return client.list_all("/vorgang", {"f.dokumentnummer": number}, page_pause=page_pause)


#: Drucksache numbers per ``/drucksache?f.dokumentnummer=`` request. Each record
#: names its own number, so, unlike ``/vorgang``, a batch can be split by number.
DRUCKSACHE_BATCH = 50
#: Drucksache ids per ``/drucksache-text`` request: a text can run to 60,000
#: characters, so a batch stays one modest page.
DRUCKSACHE_TEXT_BATCH = 10


def fetch_drucksache_metadata(
    client: ApiClient, numbers: list[str], *, page_pause: float = 0.0
) -> dict[str, list[dict[str, Any]]]:
    """The raw DIP ``/drucksache`` records of each number, Bundestag ones only.
    A number DIP returned nothing for maps to [] when its batch was complete; a
    batch DIP answered with a malformed page records only the numbers it did
    return, so the rest stay cache misses."""
    result: dict[str, list[dict[str, Any]]] = {}
    for start in range(0, len(numbers), DRUCKSACHE_BATCH):
        batch = [str(n) for n in numbers[start : start + DRUCKSACHE_BATCH]]
        complete = True
        try:
            documents = client.list_all("/drucksache", {"f.dokumentnummer": batch}, page_pause=page_pause)
        except DipShapeError as exc:
            print(f"warning: Drucksache validation: {exc}", file=sys.stderr)
            documents, complete = exc.documents, False
        found: dict[str, list[dict[str, Any]]] = {}
        for document in documents:
            number = derive.canonical_document_number(document.get("dokumentnummer"))
            if number in batch and document.get("herausgeber") in (None, "BT"):
                found.setdefault(number, []).append(document)
        result.update(found)
        if complete:
            for number in batch:
                result.setdefault(number, [])
    return result


def fetch_drucksache_texts(client: ApiClient, ids: list[str], *, page_pause: float = 0.0) -> dict[str, str]:
    """The full DIP text of each Drucksache id. An id DIP has no text for yet is
    left out (asked again by the next online build); a ``text`` that is not a
    string is refused like a failed call."""
    texts: dict[str, str] = {}
    for start in range(0, len(ids), DRUCKSACHE_TEXT_BATCH):
        batch = [str(i) for i in ids[start : start + DRUCKSACHE_TEXT_BATCH]]
        if start:
            time.sleep(page_pause)
        try:
            documents = client.list_all("/drucksache-text", {"f.id": batch}, page_pause=page_pause)
        except DipShapeError as exc:
            print(f"warning: Drucksache text validation: {exc}", file=sys.stderr)
            documents = exc.documents
        for document in documents:
            record_id = str(document.get("id") or "").strip()
            text = document.get("text")
            if record_id not in batch:
                continue
            if text is not None and not isinstance(text, str):
                print(f"warning: DIP Drucksache {record_id} has an unexpected text: {str(text)[:100]}", file=sys.stderr)
                continue
            texts[record_id] = text or ""
    return texts


def fetch_text(url: str) -> str:
    return _fetch_page(url, "application/xml,text/xml,*/*", "XML")


@dataclass
class XmlPacer:
    """Paces Plenarprotokoll XML requests to dserver.bundestag.de across one run
    (decision 9, docs/plans/a3-rule5-wp18-19-round2.md). dserver grants a request
    budget per window, not a rate (docs/plans/a3-pilot.md, Finding 2): about 50
    XML at 2 s spacing, then a 60-minute pause, and the first answer over 10 s
    stops the run."""

    spacing: float = 2.0
    window_size: int = 50
    window_pause: float = 3600.0
    slow_stop: float = 10.0
    clock: Callable[[], float] = field(default=time.monotonic, repr=False)
    sleep: Callable[[float], None] = field(default=time.sleep, repr=False)
    in_window: int = 0
    last: float | None = None

    def fetch(self, url: str) -> str:
        if self.in_window >= self.window_size:
            print(f"[xml] {self.in_window} XML in this window; pausing {self.window_pause / 60:g} minutes.",
                  file=sys.stderr, flush=True)
            self.sleep(self.window_pause)
            self.in_window, self.last = 0, None
        elif self.last is not None:
            wait = self.spacing - (self.clock() - self.last)
            if wait > 0:
                self.sleep(wait)
        started = self.clock()
        try:
            return fetch_text(url)
        finally:
            self.last = self.clock()
            self.in_window += 1
            took = self.last - started
            if took > self.slow_stop:
                raise SourceSlowError(
                    f"{url} took {took:.1f} s (over {self.slow_stop:g} s): stopping before dserver blocks. "
                    "Resume after a pause; fetched XML is kept.")


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
    return bool(href) and derive.is_bundestag_xml_url(href)


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


def called_drucksachen(top: ET.Element, *, heading: str, speech_count: int) -> list[str]:
    """The Drucksache numbers the chair names in a TOP section with no heading and
    no Rede, where the chair calls a vote debated jointly elsewhere (18/237
    Zusatzpunkt 10: "Abstimmung über den Antrag … auf Drucksache 18/12639"):
    every paragraph that is not a ``T…`` heading paragraph, read with
    ``vote_links.chair_numbers``. Empty for every other section. Step 2 of the
    vote-link rule reads it; it is not a printed Drucksache of the TOP."""
    if heading or speech_count:
        return []
    numbers: list[str] = []
    for paragraph in top.findall("p"):
        if (paragraph.attrib.get("klasse") or "").startswith("T"):
            continue
        numbers += [number for number in vote_links.chair_numbers("".join(paragraph.itertext())) if number not in numbers]
    return numbers


_REDNER_LABEL_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<fraktion>[^()]+)\)\s*:?$")


def parse_redner(redner: ET.Element | None) -> dict[str, Any] | None:
    if redner is None:
        return None
    name = redner.find("name")
    if name is None:
        return {"xml_redner_id": redner.attrib.get("id"), "display_name": elem_text(redner)}
    # A speaker printed as <name> whom the Bundestag gave no Redner-ID is bound
    # by a DIP Personenkennung (mark_name_speakers, "dip:<n>").
    dip_person = (redner.attrib.get("id") or "").partition("dip:")[2] or None

    title = child_text(name, "titel")
    first = child_text(name, "vorname")
    last = child_text(name, "nachname")
    fraction = child_text(name, "fraktion") or None
    role_long, role_short = speech_kinds.effective_role(redner)
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
    try:
        fraction = derive.printed_fraktion(fraction, role_long or role_short)
    except derive.UnknownFraktionError as exc:
        raise derive.UnknownFraktionError(f"{exc} at redner {redner.attrib.get('id')}") from None
    speaker = {
        "xml_redner_id": None if dip_person else redner.attrib.get("id"),
        "display_name": display_name,
        "first_name": first or None,
        "last_name": last or None,
        "fraktion": fraction,
        "role": role_long,
        "role_short": role_short,
    }
    if dip_person:
        speaker["dip_person_id"] = dip_person
    return speaker


def parse_toc(root: ET.Element) -> list[dict[str, Any]]:
    """Every Inhaltsverzeichnis block in source order. A title can repeat (18/44
    prints "Tagesordnungspunkt II: (Fortsetzung)" twice, the first block listing
    13 Reden and the second none), so blocks are never keyed by title."""
    toc: list[dict[str, Any]] = []
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
        toc.append({
            "title": title,
            "drucksachen": extract_drucksachen(block),
            "pages": sorted(pages, key=page_sort_key),
            "rid_pages": rid_pages,
        })
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
# Julia Klöckner:"). WP 18/19 print some other speakers there too; each is
# listed and rewritten into a speaker marker before this is read
# (``mark_name_speakers``), and an unlisted one withholds its unit, so a
# ``<name>`` still read here is the chair's. Compared by identity.
_SITZUNGSLEITUNG = object()
# ponytail: reviewed grant wording only; extend with source-backed regressions.
NESTED_GRANT_EVIDENCE = re.compile(
    r"(?P<grant>\bich\s+(?:lasse|gestatte|erlaube)\b.{0,80}\b(?:Zwischenfrage|Frage|Zwischenbemerkung)\b.{0,40}\bzu\b)"
    r"|(?P<direct>\bich\s+(?:erlaube\s+Zwischenfragen|freue mich auf Ihre Zwischenfrage)\b)"
    r"|(?P<ack>\b(?:dank\w*|bedanke(?: mich)?)\b.{0,100}\b(?:Zwischenfrage|Frage|Zwischenbemerkung)\b.{0,70}\b(?:zulass\w*|zugelassen haben)\b)",
    re.IGNORECASE,
)
# 6a: a nested MdB turn is a Zwischenfrage/-bemerkung when (1) the Redner's last
# turn before it is a short consent that followed the chair's offer of a
# question, or (2) the turn itself opens by thanking for being allowed to ask.
NESTED_OFFER = re.compile(r"\b(?:Zwischen)?(?:Fragen?|Bemerkung(?:en)?)\b", re.IGNORECASE)
# R1c: short offers that name no Frage or Bemerkung. They are an offer only
# when the chair's turn names the would-be asker.
NAMED_OFFER = re.compile(r"\bDarf (?:er|sie)(?: das)?\?|\bMögen Sie\?|\bGestatten Sie\?|\bZusatzfrage\b", re.IGNORECASE)
# R1b: the Redner's short turn after an offer is consent unless it refuses.
CONSENT_MAX_WORDS = 12
# With a Frage/Bemerkung word, the chair asks for a (new) question: a new exchange.
NEW_OFFER_WORDING = re.compile(r"\b(?:darf|dürfen|möchten?|wünscht|will|wollen)\b", re.IGNORECASE)
CONSENT_REFUSAL = re.compile(r"\b(?:nein|nee|nicht|kein\w*|später)\b", re.IGNORECASE)
# 6b: the chair gives the floor, with no question asked, to an MdB whose
# turn says the Redner addressed them.
ADDRESSED_MEMBER = re.compile(
    r"\bangesprochen\b|\bSie haben (?:was |etwas )?(?:zu|über) mir gesagt\b|\bSie haben mich\b"
    r"|\bweil Sie\b[^.!?]{0,40}\bzitiert\b", re.IGNORECASE)
NESTED_OPENING_THANKS = re.compile(
    r"\b(?:be)?dank\w*[^;–?!]{0,60}\b(?:Zulassen|Zulassung|Möglichkeit)\b[^;–?!]{0,40}\b(?:Zwischen)?(?:Frage|Bemerkung)"
    r"|\b(?:be)?dank\w*[^;–?!]{0,40}\bdass Sie\b[^;–?!]{0,40}\b(?:Zwischen)?(?:Frage|Bemerkung)\s+zulassen\b"
    r"|\bEs zeichnet Sie aus, dass Sie\b[^;–?!]{0,60}\b(?:Zwischen)?(?:Frage|Bemerkung)\s+zulassen\b",
    re.IGNORECASE)


def nested_consent(turn: list[str]) -> bool:
    text = clean_text(" ".join(turn))
    return 0 < len(text.split()) <= CONSENT_MAX_WORDS and not CONSENT_REFUSAL.search(text)


# Matched against the role with whitespace removed ("Vizepräsident in").
SITZUNGSLEITUNG_ROLE = speech_kinds.PRESIDIUM_ROLE
# The elected Präsident's acceptance, answering the chair's question (6d). 18/1
# prints "Herr Alterspräsident, lieber Kollege Riesenhuber, ich nehme die Wahl
# gerne an." (ADR 0004 plan, P4): any salutation of the chair, then the words.
ELECTION_QUESTION = re.compile(r"\bNehmen Sie die Wahl an\?\s*$")
ELECTION_ACCEPTANCE = re.compile(
    r"(?:(?:Herr|Frau) (?:Alters)?[Pp]räsident(?:in)?(?:, [^.!?]{1,60})?, )?[Ii]ch nehme die Wahl (?:sehr )?(?:gerne? )?an\.")
# ADR 0004 plan P4/P5: a short <rede> that reads like an acceptance of an
# election or an oath answer is a candidate. Listed (kind procedural) it is no
# Rede; unlisted it refuses its sitting, located, so it is never counted unread.
ACCEPTANCE_CANDIDATE = re.compile(r"\b[Nn]ehme\b[^.!?]{0,40}\b(?:[Ww]ahl|sie)\b[^.!?]{0,30}\ban\b")
ACCEPTANCE_MAX_CHARS = 200
OATH_CANDIDATE = re.compile(r"\b(?:Amts)?[Ee]id(?:es(?:formel|leistung)?)?\b|\b[Ss]chw(?:ör|ur)")
OATH_MAX_CHARS = 400


def procedural_candidate(text: str, heading: str, preceding: str) -> str | None:
    """What a Rede's own ``text`` reads like when it may be no Rede at all: an
    oath answer or an election acceptance (P4/P5), else None."""
    if len(text) <= OATH_MAX_CHARS and OATH_CANDIDATE.search(text):
        return "oath answer"
    if len(text) <= ACCEPTANCE_MAX_CHARS and ACCEPTANCE_CANDIDATE.search(text):
        return "election acceptance"
    if text == "Ja." and (re.search(r"\bWahl\b", heading) or re.search(r"\bWahl an\b|\bannehmen\b", preceding)):
        return "election acceptance"
    return None


# The chair gives the floor in the form of the Rednerliste, and the turn opens
# like a Rede (6c).
NESTED_REDE_FLOOR = re.compile(
    r"\b[Nn]ächste[rnm]? Redner(?:in)?\b|\b(?:[Ll]etzte|[Aa]bschließende)[rn]? Redner(?:in)?\b"
    r"|\b[Dd]as Wort (?:hat|erhält)\b|\bhat (?:[^.!?]{1,80} )?das Wort\b"
    r"|\b(?:gebe|erteile) (?:ich )?(?:[^.!?]{1,80} )?das Wort\b|\bspricht (?:jetzt|nun)\b"
)
NESTED_REDE_NOT_FLOOR = re.compile(r"Zwischenfrage|Zwischenbemerkung|Frage|Kurzintervention|Erwiderung|Bemerkung", re.IGNORECASE)
REDE_SALUTATION = re.compile(r"Sehr (?:geehrte|verehrte)[rn]?\b|(?:Frau|Herr) (?:Vize|Alters)?Präsident(?:in)?\s*!")
_NESTED_NAMED_ASKER = re.compile(
    r"\b(?i:Kollegen?|Kollegin|Abgeordnete[nr]?|von|vom)\s+(?:(?:Dr\.|Prof\.|Frau|Herrn?)\s+)*"
    r"([A-ZÄÖÜ][\wÄÖÜäöüß-]*(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß-]*)*)"
)


def nested_grant_names(announcement: str) -> set[str] | None:
    # Names before the question need an explicit asker predicate; an address
    # to the main speaker or a bystander alone is not permission.
    question = re.search(r"\b(?:Zwischenfragen?|Zwischenbemerkung(?:en)?|Fragen?|Bemerkung(?:en)?)\b", announcement, re.IGNORECASE)
    request = re.sub(r"\b[A-Z]\.\s+", "", announcement[question.end():]) if question else ""
    request = re.split(r"\ban (?:den|die) Abgeordnet", request, flags=re.IGNORECASE)[0]
    names = _NESTED_NAMED_ASKER.findall(speech_kinds._SENTENCE_END.split(request)[0])
    if question:
        names += re.findall(
            r"\b(?:Herr|Frau|Abgeordnete[nr]?|Kolleg(?:in|en|e))\s+(?:Dr\.\s+)?"
            r"([A-ZÄÖÜ][\wÄÖÜäöüß-]*(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß-]*)*)"
            r"\s+(?:hat (?:die Möglichkeit|eine)|würde[^.!?]{0,30}gerne?|hat sich gemeldet)",
            announcement[:question.start()])
    surnames = {name.split()[-1].rstrip(".").casefold() for name in names}
    return {name for name in surnames if name not in {"kollege", "kollegen", "kollegin", "fraktion", "ihnen", "zwischenfrage", "zwischenfragen", "frau", "herr"}
            and not any(re.search(pattern.pattern, name, re.IGNORECASE)
                        for pattern in speech_kinds.FRAKTION_WORDING.values())} or None


def asker_name(last_name: str | None) -> str:
    """The surname the chair names an asker by: WP 18/19 prints some with a
    middle initial inside ``<nachname>`` ("W. Birkwald"), the chair says
    "Birkwald" (R4). The stored ``last_name`` keeps the initial."""
    return re.sub(r"^[A-ZÄÖÜ]\.\s+", "", last_name or "").casefold()


# The chair's own words: an offer to the Redner, or the floor to the next one.
CHAIR_OFFER = re.compile(r"\b(?:gestatten|erlauben)\s+Sie\b[^.!?]{0,80}\b(?:Zwischen)?(?:frage|bemerkung)", re.IGNORECASE)


def mark_roleless_chairs(root: ET.Element) -> None:
    """WP 18/19 (and 21/17) can print the chair inside a member's ``<rede>`` as
    a plain MdB marker, with no presidium role. Such a marker is Sitzungsleitung
    when its person chairs this sitting (a ``<name>`` chair element ends with
    their first and last name) and their turn is chair text. It is marked
    ``sitzungsleitung="1"`` in place, so ``presidium_marker`` reads it as 6d.
    A Vizepräsident(in) asking as an MdB says no chair text and stays a member.
    """
    verlauf = root.find("sitzungsverlauf")
    if verlauf is None:
        return
    chairs = [elem_text(name) for name in verlauf.iter("name") if name.find("nachname") is None]
    for rede in verlauf.iter("rede"):
        own = redner_key(rede.find("./p[@klasse='redner']/redner"))
        children = list(rede)
        for index, child in enumerate(children):
            if child.tag != "p" or child.get("klasse") != "redner":
                continue
            redner = child.find("redner")
            if redner is None or redner_key(redner) in (own, None) or any(speech_kinds.effective_role(redner)):
                continue
            full = clean_text(f"{child_text(redner.find('name'), 'vorname') or ''} {child_text(redner.find('name'), 'nachname') or ''}")
            if not any(re.search(rf"(?<![\w-]){re.escape(full)}\s*:?$", chair) for chair in chairs):
                continue
            turn = [clean_text((redner.tail or "").partition(":")[2])]
            for following in children[index + 1:]:
                if following.tag == "name" or following.get("klasse") == "redner":
                    break
                if following.tag == "p":
                    turn.append(elem_text(following))
            text = " ".join(filter(None, turn))
            if CHAIR_OFFER.search(text) or (NESTED_REDE_FLOOR.search(text) and not NESTED_REDE_NOT_FLOOR.search(text)):
                redner.set("sitzungsleitung", "1")


# Matched against the role with whitespace removed, as SITZUNGSLEITUNG_ROLE.
VIZEPRAESIDIUM_ROLE = re.compile(r"Vizepräsident(?:in)?", re.IGNORECASE)


def mark_reviewed_units(root: ET.Element, entries: list[dict[str, str]]) -> None:
    """ADR 0004: mark each ``<rede>`` of this sitting that one of ``entries``
    (its presidium-kind entries of ``scripts/reviewed_units.json``) lists with
    its reviewed kind (``reviewed_kind``). The entry must name a ``<rede>`` of
    the Sitzungsverlauf (not an annex) printed once, owned by the entry's
    Redner-ID; anything else is a stale or misapplied entry and stops the run
    (``ReviewedUnitsError``), naming it."""
    if not entries:
        return
    sitting = f"{root.get('wahlperiode')}/{root.get('sitzung-nr')}"
    verlauf = root.find("sitzungsverlauf")
    reden = list(verlauf.iter("rede")) if verlauf is not None else []
    for entry in entries:
        where = f"scripts/reviewed_units.json: {sitting} {entry['rede_id']} ({entry['kind']})"
        found = [rede for rede in reden if rede.get("id") == entry["rede_id"]]
        if len(found) != 1:
            raise reviewed_units.ReviewedUnitsError(
                f"{where}: the Sitzungsverlauf prints this <rede> {len(found)} times, not once; the entry is stale or misapplied")
        first = found[0].find("./p[@klasse='redner']/redner")
        owner = derive.first_redner_id(first.get("id")) if first is not None else None
        if owner != entry["redner_id"]:
            raise reviewed_units.ReviewedUnitsError(
                f"{where}: owned by Redner-ID {owner}, the entry says {entry['redner_id']}; the entry is stale or misapplied")
        found[0].set("reviewed_kind", entry["kind"])
        found[0].set("reviewed_reason", entry["reason"])


def mark_listed_units(redes: list[ET.Element], entries: dict[str, dict[str, str]], formats: frozenset[str],
                      matched: set[str], sitting: str) -> None:
    """ADR 0002, amendment 2026-11-23: mark each ``<rede>`` of one TOP, as it
    stands after ``split_nested_reden``, that one of ``entries`` (the sitting's
    ``reviewed_units.UNIT_KINDS`` entries by id) lists, for
    ``speech_kinds.classify_reden`` (``listed_unit``). An entry of another owner,
    or on a ``<rede>`` whose kind is decided elsewhere (a presidium ``<rede>``;
    in a Befragung, whose question format decides, all but an Erklärung), stops
    the run."""
    for rede in redes:
        entry = entries.get(rede.get("id") or "")
        if entry is None:
            continue
        matched.add(entry["rede_id"])
        where = f"scripts/reviewed_units.json: {sitting} {entry['rede_id']} ({entry['kind']})"
        first = rede.find("./p[@klasse='redner']/redner")
        owner = derive.first_redner_id(first.get("id")) if first is not None else None
        if owner != entry["redner_id"]:
            raise reviewed_units.ReviewedUnitsError(
                f"{where}: owned by Redner-ID {owner}, the entry says {entry['redner_id']}; the entry is stale or misapplied")
        if rede.get("reviewed_kind") or speech_kinds.presidium_owner(rede):
            raise reviewed_units.ReviewedUnitsError(f"{where}: a presidium <rede> takes one of ADR 0004's kinds")
        if speech_kinds.BEFRAGUNG in formats and entry["kind"] != speech_kinds.ERKLAERUNG:
            raise reviewed_units.ReviewedUnitsError(f"{where}: a Befragung's question format decides its kinds")
        rede.set("listed_unit", entry["kind"])


def join_own_words(top: ET.Element, entries: dict[str, dict[str, str]], matched: set[str],
                   statuses: dict[str, str], sitting: str, rid_pages: dict[str, dict[str, Any]],
                   ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """ADR 0004, amendment 2026-11-23 on split Reden: join each ``<rede>`` of one TOP, as it stands
    after ``split_nested_reden``, that one of ``entries`` (the sitting's ``own_words``
    entries by id) lists, to the ``<rede>`` before it. The XML ended one Rede at the
    chair's remark and printed its rest as a new one; joined, the rest is the resumption
    the walk reads. The Rede keeps the id of its first part, but where that part is one
    ``split_nested_reden`` made, the listed id, which the Inhaltsverzeichnis names; its
    page there is the rest's, so ``rid_pages`` takes the entry's. A part joined away has
    the status ``own_words``. An entry whose ``<rede>`` does not follow its owner's
    directly, or whose page does not fit, stops the run. Returns the diagnostics and the
    pages of the rests, which the TOP still reaches."""
    diagnostics: list[dict[str, Any]] = []
    rest_pages: list[dict[str, Any]] = []
    for rede in top.findall("rede"):
        entry = entries.get(rede.get("id") or "")
        if entry is None:
            continue
        matched.add(entry["rede_id"])
        where = f"scripts/reviewed_units.json: {sitting} {entry['rede_id']} ({entry['kind']})"
        children = list(top)
        index = children.index(rede)
        before = children[index - 1] if index else None
        if before is None or before.tag != "rede":
            raise reviewed_units.ReviewedUnitsError(f"{where}: no <rede> stands directly before it")
        owners = [redner_key(part.find("./p[@klasse='redner']/redner")) for part in (before, rede)]
        if owners != [entry["redner_id"]] * 2:
            raise reviewed_units.ReviewedUnitsError(
                f"{where}: the two <rede> are owned by Redner-ID {owners[0]} and {owners[1]}, the entry says "
                f"{entry['redner_id']}; the entry is stale or misapplied")
        if any(part.get("reviewed_kind") or speech_kinds.presidium_owner(part) for part in (before, rede)):
            raise reviewed_units.ReviewedUnitsError(f"{where}: a presidium <rede> takes one of ADR 0004's kinds")
        marker = rede.find("./p[@klasse='redner']/redner")
        split_part = ":" in (before.get("id") or "")
        page = reviewed_units.PAGE_RE.fullmatch(entry["page"])
        if split_part != bool(page):
            raise reviewed_units.ReviewedUnitsError(
                f"{where}: " + ("the first part is one the parser split off, so the entry must give the page it begins on" if split_part
                                else "the first part has a page of its own; the entry's page must be empty"))
        rest_page = rid_pages.get(entry["rede_id"])
        if rest_page:
            rest_pages.append(rest_page)
        if split_part:
            start = {"page": int(page.group(1)), "quadrant": page.group(2)}
            outer_page = rid_pages.get(raw_rede_id(before.get("id")))
            if ((outer_page and page_sort_key(start) < page_sort_key(outer_page))
                    or (rest_page and page_sort_key(start) > page_sort_key(rest_page))):
                raise reviewed_units.ReviewedUnitsError(
                    f"{where}: page {entry['page']} is not between the <rede> the first part was split off and the rest")
            rid_pages[entry["rede_id"]] = start
            kept, gone = rede, before
            for offset, child in enumerate(list(before)):
                rede.insert(offset, child)
        else:
            kept, gone = before, rede
            before.extend(list(rede))
        top.remove(gone)
        record_status(statuses, gone.get("id") or "", reviewed_units.OWN_WORDS)
        diagnostics.append({
            "source_rede_id": gone.get("id"), "marker_ordinal": 1, "speaker": parse_redner(marker),
            "text": "", "evidence": "one Rede printed as two <rede>: " + entry["reason"],
            "treatment": "joined_rede", "target_rede_id": kept.get("id")})
    return diagnostics, rest_pages


def unwrap_quotes(root: ET.Element) -> None:
    """A block quote is ``<p klasse="Z">``; WP 18 wraps about half of its own in a
    ``<zitat>`` (1,939 of 3,893), WP 19 on none. The quote is read out by whoever is speaking,
    so each ``<zitat>`` is replaced by its children, and every walk of the parse
    reads both the same way. Text in a ``<zitat>`` outside its ``<p>`` (none in the
    806 sittings held) refuses the sitting: it would be lost here."""
    for parent in reversed([element for element in root.iter() if element.find("zitat") is not None]):
        for quote in parent.findall("zitat"):
            if any((text or "").strip() for text in (quote.text, *(child.tail for child in quote))):
                raise ValueError(f"{root.get('wahlperiode')}/{root.get('sitzung-nr')}: text in a <zitat> outside a paragraph: "
                                 f"{elem_text(quote)[:80]!r}")
            index = list(parent).index(quote)
            children = list(quote)
            if children:
                children[-1].tail = quote.tail
            parent.remove(quote)
            for offset, child in enumerate(children):
                parent.insert(index + offset, child)


def mark_stage_direction_names(root: ET.Element) -> None:
    """ADR 0004 (20/25): a ``<name>`` whose whole text stands in parentheses is a
    stage direction the source printed in the chair's element, not a chair turn:
    20/25 ``ID202506700`` holds ``<name>(Vizepräsident Wolfgang Kubicki räuspert
    sich)</name>`` before Lamya Kaddor's closing words. It is renamed
    ``<kommentar>``, which no reader of the parse treats as a turn, so the
    speaker before it goes on. A ``<name>`` that opens with a speaker's label is
    untouched, whatever parentheses it holds.
    """
    for name in root.iter("name"):
        if len(name) == 0 and re.fullmatch(r"\([^()]*\)", elem_text(name)):
            name.tag = "kommentar"


# ADR 0004 amendment (2026-11-22, docs/plans/name-tag-speakers.md): a <name>
# tag is the chair's when it opens with a presidium role, when it ends with the
# name of someone a presidium tag of this sitting names, or when it stands in
# parentheses (a stage direction; mark_stage_direction_names has renamed those
# by now). Any other <name> prints a speaker who is not the chair.
NAME_TAG_CHAIR_ROLE = re.compile(r"^(?:Alters|Vize)?[Pp]räsident(?:in)?\b")
_NAME_TAG_CHAIR_NAME = re.compile(r"^(?:Alters|Vize)?[Pp]räsident(?:in)?\s+(?:Dr\.\s+)?(?P<name>.+)$")
# The Beitrag kinds a listed speaker marker must be given by the rules.
NAME_KIND_CONTRIBUTION = {
    "name_zwischenfrage": speech_kinds.ZWISCHENFRAGE,
    "name_befragung_frage": speech_kinds.BEFRAGUNG_FRAGE,
    "name_befragung_antwort": speech_kinds.BEFRAGUNG_ANTWORT,
    "name_fragestunde_frage": speech_kinds.FRAGESTUNDE_FRAGE,
}
#: Where each name kind may stand: inside a source <rede>, or outside any.
NAME_KINDS_IN_REDE = frozenset({"name_rede", "name_zwischenfrage", "name_befragung_frage", "name_befragung_antwort",
                                "name_own_words", "name_procedural"})
NAME_KINDS_OUTSIDE = frozenset({"name_rede", "name_fragestunde_frage", "name_procedural", "name_ansprache", "name_remark"})
#: What to do when a sitting is refused for an unlisted speaker printed as
#: ``<name>`` outside any ``<rede>``: a re-fetch returns the same XML.
UNLISTED_NAME_SPEAKER_FIX = ("list the speaker in scripts/reviewed_units.json with a name_* kind, rede_id N<ordinal> "
                             "(ADR 0004 amendment 2026-11-22, docs/plans/name-tag-speakers.md), then re-run")


class UnlistedNameSpeakerError(ValueError):
    """A speaker printed as ``<name>`` outside any ``<rede>`` with no reviewed
    entry: there is no unit to withhold, so the sitting is refused. The XML is
    valid; the reviewed list lacks the entry (``UNLISTED_NAME_SPEAKER_FIX``)."""


def name_tag(name: ET.Element) -> str:
    """A ``<name>`` element's printed tag without its colon: "Sylvia Pantel (CDU/CSU)"."""
    return elem_text(name).strip(" :")


def name_tags(root: ET.Element) -> list[ET.Element]:
    """The Sitzungsverlauf's ``<name>`` elements in source order: the tag
    elements, not a structured name inside ``<redner>``. An entry outside any
    ``<rede>`` names one by its 1-based position here, ``N<ordinal>``."""
    verlauf = root.find("sitzungsverlauf")
    return [name for name in verlauf.iter("name") if len(name) == 0] if verlauf is not None else []


def chair_tag(tag: str, chairs: set[str]) -> bool:
    return bool(NAME_TAG_CHAIR_ROLE.match(tag)) or tag.startswith("(") or any(tag.endswith(chair) for chair in chairs)


def sitting_chairs(tags: list[ET.Element]) -> set[str]:
    """The names a presidium tag of this sitting prints ("Edelgard Bulmahn")."""
    return {match.group("name") for match in (_NAME_TAG_CHAIR_NAME.match(name_tag(name)) for name in tags) if match}


def name_tag_marker(tag: str, redner_id: str, tail: str | None) -> ET.Element:
    """A speaker marker for a tag printed as ``<name>``, as the source prints one:
    the name fields read from the tag, the tag itself as the label. A role after
    the comma ("Heiko Maas, Bundesminister der Justiz …") stays in the label,
    where ``speech_kinds.effective_role`` reads printed roles; a Fraktion in
    parentheses ends a tag without one."""
    rest, fraktion = tag, None
    if "," not in tag:
        match = re.fullmatch(r"(?P<rest>.*?)\s*\(\s*(?P<fraktion>[^()]*?)\s*\)", tag)
        if match:
            rest, fraktion = match.group("rest"), match.group("fraktion")
    rest = rest.split(",", 1)[0]
    place = re.fullmatch(r"(?P<rest>.*?)\s*\(\s*(?P<ort>[^()]*?)\s*\)", rest)
    if place:
        rest = place.group("rest")
    title = re.match(r"(?:(?:Dr\.|Prof\.)\s*)+", rest)
    words = rest[title.end() if title else 0:].split()
    if not words:
        raise ValueError(f"<name> {tag!r} names no person")
    name = ET.Element("name")
    for field, value in (("titel", title.group().strip() if title else ""), ("vorname", " ".join(words[:-1])),
                         ("nachname", words[-1]), ("ortszusatz", f"({place.group('ort')})" if place else ""),
                         ("fraktion", fraktion or "")):
        if value:
            ET.SubElement(name, field).text = value
    marker = ET.Element("p", {"klasse": "redner"})
    redner = ET.SubElement(marker, "redner", {"id": redner_id})
    redner.append(name)
    redner.tail = f"{tag}: "
    marker.tail = tail
    return marker


def mark_name_speakers(root: ET.Element, entries: list[dict[str, str]], created: set[str]) -> tuple[
        dict[int, list[dict[str, Any]]], list[dict[str, Any]]]:
    """ADR 0004 amendment (2026-11-22): rewrite each ``<name>`` that prints a
    speaker who is not the chair, by its entry in ``scripts/reviewed_units.json``.

    Inside a ``<rede>`` (an entry names the host ``<rede>`` and the tag), a Rede,
    Beitrag or own-words tag becomes a speaker marker of the entry's Redner-ID,
    in place; a Rede's marker carries ``listed_kind="rede"``, so
    ``split_nested_reden`` splits there. Outside any ``<rede>`` (an entry
    ``N<ordinal>``), a Rede is wrapped into ``<rede id="N<ordinal>">`` up to the
    next tag, marker or ``<rede>`` (its id goes into ``created``), and a
    Fragestunde question becomes a flat marker. An oath answer becomes a
    procedural diagnostic, an invited guest's address an Ansprache with no
    Redner-ID, and a remark nothing.

    An unlisted tag inside a ``<rede>`` is marked ``unreviewed_name``, so the
    unit that holds it is withheld; one outside any ``<rede>`` refuses the
    sitting (``ValueError``). An entry no tag matches, or one whose kind cannot
    stand where its tag stands, stops the run (``ReviewedUnitsError``).

    Returns the procedural diagnostics by TOP (``id`` of the element) and the
    Ansprachen, one per guest and parent element.
    """
    sitting = f"{root.get('wahlperiode')}/{root.get('sitzung-nr')}"
    tags = name_tags(root)
    chairs = sitting_chairs(tags)
    listed = {(entry["rede_id"], entry["name"]): entry for entry in entries}
    matched: set[tuple[str, str]] = set()
    parents = {child: parent for parent in root.iter() for child in parent}
    diagnostics: dict[int, list[dict[str, Any]]] = {}
    ansprachen: dict[tuple[int, str], dict[str, Any]] = {}
    wraps: list[tuple[ET.Element, str]] = []

    def turn_after(element: ET.Element) -> list[str]:
        parent = parents[element]
        children = list(parent)
        paragraphs: list[str] = []
        flow = speech_kinds.ParagraphFlow()
        for following in children[children.index(element) + 1:]:
            if following.tag in ("name", "rede") or following.get("klasse") == "redner":
                break
            flow.see(following)
            if following.tag == "p" and elem_text(following):
                flow.add(following, elem_text(following), paragraphs)
        return paragraphs

    for ordinal, element in enumerate(tags, 1):
        tag = name_tag(element)
        if chair_tag(tag, chairs):
            continue
        host, node = None, parents.get(element)
        while node is not None and host is None:
            host = node if node.tag == "rede" else None
            node = parents.get(node)
        key = (host.get("id") if host is not None else f"N{ordinal}", tag)
        entry = listed.get(key)
        where = f"{sitting} {key[0]} <name>{tag}</name>"
        if entry is None:
            if host is None:
                raise UnlistedNameSpeakerError(f"{where}: a speaker printed as <name> outside any <rede> has no entry in "
                                 "scripts/reviewed_units.json (ADR 0004)")
            element.set("unreviewed_name", tag)
            continue
        matched.add(key)
        kind = entry["kind"]
        if kind not in (NAME_KINDS_IN_REDE if host is not None else NAME_KINDS_OUTSIDE):
            raise reviewed_units.ReviewedUnitsError(
                f"scripts/reviewed_units.json: {where}: a {kind} entry cannot stand "
                + ("inside a <rede>" if host is not None else "outside any <rede>"))
        top = next((node for node in (parents.get(element), parents.get(parents.get(element)))
                    if node is not None and node.tag == "tagesordnungspunkt"), None)
        if kind == "name_remark":
            continue
        if kind == "name_procedural":
            diagnostics.setdefault(id(top), []).append({
                "source_rede_id": key[0] if host is not None else None, "marker_ordinal": ordinal,
                "speaker": {"xml_redner_id": None, "display_name": tag}, "text": clean_text(" ".join(turn_after(element))),
                "evidence": "procedural (reviewed <name> speaker): " + entry["reason"], "treatment": "procedural"})
            continue
        if kind == "name_ansprache":
            parent = parents[element]
            paragraphs = turn_after(element)
            unit = ansprachen.get((id(parent), tag))
            if unit is None:
                ansprachen[(id(parent), tag)] = contribution_unit(
                    speech_kinds.ANSPRACHE, f"N{ordinal}", None, 0, {"xml_redner_id": None, "display_name": tag},
                    paragraphs, None)
            else:
                ansprachen[(id(parent), tag)] = contribution_unit(
                    speech_kinds.ANSPRACHE, unit["rede_id"], None, 0, unit["speaker"], unit["paragraphs"] + paragraphs, None)
            continue
        redner_id = entry["redner_id"]
        if kind == "name_own_words":
            owner = redner_key(host.find("./p[@klasse='redner']/redner"))
            if owner != redner_id:
                raise reviewed_units.ReviewedUnitsError(
                    f"scripts/reviewed_units.json: {where}: own words of Redner-ID {redner_id}, "
                    f"but the <rede> is owned by {owner}; the entry is stale or misapplied")
        marker = name_tag_marker(tag, redner_id, element.tail)
        if kind == "name_rede":
            marker.find("redner").set("listed_kind", "rede")
        elif kind in NAME_KIND_CONTRIBUTION:
            marker.find("redner").set("listed_kind", NAME_KIND_CONTRIBUTION[kind])
        parent = parents[element]
        parent.insert(list(parent).index(element), marker)
        parent.remove(element)
        parents[marker] = parent
        if kind == "name_rede" and host is None:
            if parent.tag != "tagesordnungspunkt":
                raise reviewed_units.ReviewedUnitsError(
                    f"scripts/reviewed_units.json: {where}: a Rede outside any <rede> must stand in a TOP, not <{parent.tag}>")
            wraps.append((marker, f"N{ordinal}"))
    for marker, rid in wraps:
        parent = parents[marker]
        children = list(parent)
        start = children.index(marker)
        end = next((index for index in range(start + 1, len(children))
                    if children[index].tag in ("name", "rede") or children[index].get("klasse") == "redner"), len(children))
        rede = ET.Element("rede", {"id": rid})
        for moved in children[start:end]:
            parent.remove(moved)
            rede.append(moved)
        parent.insert(start, rede)
        created.add(rid)
    stale = sorted(set(listed) - matched)
    if stale:
        raise reviewed_units.ReviewedUnitsError(
            f"scripts/reviewed_units.json: {sitting} lists " + "; ".join(f"{rid} <name>{tag}</name>" for rid, tag in stale)
            + ", which no speaker printed as <name> in this sitting's XML matches; the entry is stale or misapplied")
    return diagnostics, list(ansprachen.values())


#: The Beitrag kinds a listed loose marker must be given by the rules.
LOOSE_KIND_CONTRIBUTION = {
    "loose_zwischenfrage": speech_kinds.ZWISCHENFRAGE,
    "loose_befragung_frage": speech_kinds.BEFRAGUNG_FRAGE,
    "loose_befragung_antwort": speech_kinds.BEFRAGUNG_ANTWORT,
}
#: What to do when a sitting is refused for an unlisted loose marker: a re-fetch
#: returns the same XML.
UNLISTED_LOOSE_MARKER_FIX = ("list the marker in scripts/reviewed_units.json with a loose_* kind, rede_id M<ordinal> "
                             "(ADR 0004, docs/plans/loose-speaker-markers.md), then re-run")


class UnlistedLooseMarkerError(ValueError):
    """A speaker marker standing directly in a TOP that is not a Fragestunde,
    outside any ``<rede>``, with no reviewed entry: no rule reads it and there is
    no unit to withhold, so the sitting is refused (``UNLISTED_LOOSE_MARKER_FIX``)."""


def loose_marker_ordinals(root: ET.Element) -> dict[int, int]:
    """Every speaker marker standing directly in a TOP of the source XML, by
    ``id()`` of the element: its 1-based position among them, Fragestunde TOPs
    included. Read before any tree edit; an entry names one as ``M<ordinal>``."""
    markers = (child for top in root.findall("./sitzungsverlauf/tagesordnungspunkt") for child in top
               if child.tag == "p" and child.get("klasse") == "redner")
    return {id(marker): ordinal for ordinal, marker in enumerate(markers, 1)}


def mark_loose_markers(top: ET.Element, formats: frozenset[str], ordinals: dict[int, int],
                       listed: dict[str, dict[str, str]], matched: set[str], sitting: str,
                       created: set[str]) -> list[dict[str, Any]]:
    """ADR 0004 (amendment of 2026-11-22 on markers outside any ``<rede>``):
    place each speaker marker that stands directly in a TOP that is not a
    Fragestunde, outside any ``<rede>``, by its entry in
    ``scripts/reviewed_units.json`` (``docs/plans/loose-speaker-markers.md``).

    Markers between two ``<rede>`` elements form a run, and a run's turns go
    to one place. ``wrap``: each ``loose_rede`` marker opens ``<rede
    id="M<ordinal>">``, which holds everything up to the next ``loose_rede``
    marker; the last ends after the run's last turn, so the chair text that
    follows stays in the TOP. ``prev``: the run up to its last turn moves to
    the end of the ``<rede>`` before it, with the chair text in it. ``next``:
    only the run's turns move, to the start of the ``<rede>`` after it; the
    chair text stays in the TOP, where the rules read an announcement such as
    a Kurzintervention's (20/9). A Beitrag kind's marker carries
    ``listed_kind``, which the rules must confirm; own words must be the Rede
    owner's. A marker of a kind that goes nowhere (``attach`` ``none``) stays
    where it is, read by nothing, even inside a run that moves:
    ``loose_procedural`` becomes a diagnostic, Sitzungsleitung and a remark
    nothing.

    An unlisted marker refuses the sitting (``UnlistedLooseMarkerError``); an
    entry whose Redner-ID, kind or attachment does not fit stops the run
    (``ReviewedUnitsError``). Returns the procedural diagnostics.
    """
    if speech_kinds.FRAGESTUNDE in formats:
        return []
    children = list(top)
    found = [(index, child) for index, child in enumerate(children) if id(child) in ordinals]
    if not found:
        return []
    diagnostics: list[dict[str, Any]] = []

    def is_marker(element: ET.Element) -> bool:
        return element.tag == "p" and element.get("klasse") == "redner"

    def turn_end(index: int) -> int:
        end = index + 1
        while end < len(children) and not (children[end].tag in ("name", "rede") or is_marker(children[end])):
            end += 1
        return end

    def owner_id(rede: ET.Element) -> str | None:
        first = rede.find("./p[@klasse='redner']/redner")
        return first.get("id") if first is not None else None

    runs: list[list[tuple[int, ET.Element, dict[str, str]]]] = []
    previous_rede = -1
    for index, marker in found:
        rid = f"M{ordinals[id(marker)]}"
        entry = listed.get(rid)
        where = f"{sitting} {top.get('top-id')} {rid} {clean_text(elem_text(marker))!r}"
        if entry is None:
            raise UnlistedLooseMarkerError(f"{where}: a speaker marker outside any <rede> has no entry in "
                                           "scripts/reviewed_units.json (ADR 0004)")
        printed = (marker.find("redner").get("id") if marker.find("redner") is not None else None) or ""
        if entry["redner_id"] != printed:
            raise reviewed_units.ReviewedUnitsError(
                f"scripts/reviewed_units.json: {where}: listed with Redner-ID {entry['redner_id']}, but the marker prints "
                f"{printed or 'none'}; the entry is stale or misapplied")
        matched.add(rid)
        last_rede = max((i for i in range(index) if children[i].tag == "rede"), default=-1)
        if not runs or last_rede != previous_rede:
            runs.append([])
        previous_rede = last_rede
        runs[-1].append((index, marker, entry))

    moves: list[tuple[list[ET.Element], ET.Element | None, str]] = []
    staying: set[int] = set()
    for _, marker, entry in (item for run in runs for item in run):
        if entry["attach"] == "none":
            index = children.index(marker)
            staying.update(id(element) for element in children[index:turn_end(index)])
            if entry["kind"] == "loose_procedural":
                paragraphs = [elem_text(c) for c in children[index + 1:turn_end(index)] if c.tag == "p" and elem_text(c)]
                diagnostics.append({
                    "source_rede_id": None, "marker_ordinal": ordinals[id(marker)],
                    "speaker": parse_redner(marker.find("redner")), "text": clean_text(" ".join(paragraphs)),
                    "evidence": "procedural (reviewed marker outside any <rede>): " + entry["reason"],
                    "treatment": "procedural"})
    for run in (r for r in ([item for item in run if item[2]["attach"] != "none"] for run in runs) if r):
        attaches = {entry["attach"] for _, _, entry in run}
        where = f"scripts/reviewed_units.json: {sitting} {top.get('top-id')} {', '.join(e['rede_id'] for _, _, e in run)}"
        if len(attaches) != 1:
            raise reviewed_units.ReviewedUnitsError(f"{where}: one run of markers outside any <rede> goes to one place, "
                                                    f"not {', '.join(sorted(attaches))}")
        attach = attaches.pop()
        for _, marker, entry in run:
            if entry["kind"] in LOOSE_KIND_CONTRIBUTION:
                marker.find("redner").set("listed_kind", LOOSE_KIND_CONTRIBUTION[entry["kind"]])
        first, last = run[0][0], turn_end(run[-1][0])
        if attach == "wrap":
            if run[0][2]["kind"] != "loose_rede":
                raise reviewed_units.ReviewedUnitsError(f"{where}: a wrapped run opens with a loose_rede marker")
            opens = [index for index, _, entry in run if entry["kind"] == "loose_rede"]
            for start, end in zip(opens, opens[1:] + [last]):
                owner = children[start].find("redner").get("id")
                for index, _, entry in run:
                    if start <= index < end and entry["kind"] == "loose_own_words" and entry["redner_id"] != owner:
                        raise reviewed_units.ReviewedUnitsError(
                            f"{where}: {entry['rede_id']} is listed as own words, but the Rede it joins is {owner}'s")
                moves.append((children[start:end], None, f"M{ordinals[id(children[start])]}"))
        elif attach == "prev":
            host = children[first - 1] if first and children[first - 1].tag == "rede" else None
            start = max((i for i in range(first) if children[i].tag == "rede"), default=-1) + 1
            if host is None and start > 0:
                host = children[start - 1]
            if host is None:
                raise reviewed_units.ReviewedUnitsError(f"{where}: attach prev, but no <rede> precedes the run")
            for _, _, entry in run:
                if entry["kind"] == "loose_own_words" and entry["redner_id"] != owner_id(host):
                    raise reviewed_units.ReviewedUnitsError(
                        f"{where}: {entry['rede_id']} is listed as own words, but the <rede> before is {owner_id(host)}'s")
            moves.append((children[start:last], host, "end"))
        else:
            end = next((i for i in range(last, len(children)) if children[i].tag == "rede"), None)
            if end is None:
                raise reviewed_units.ReviewedUnitsError(f"{where}: attach next, but no <rede> follows the run")
            host = children[end]
            if run[0][2]["redner_id"] != owner_id(host):
                raise reviewed_units.ReviewedUnitsError(
                    f"{where}: the run opens with {run[0][2]['redner_id']}, but the <rede> after is {owner_id(host)}'s; "
                    "a moved run must open with the owner's words")
            for _, _, entry in run:
                if entry["kind"] == "loose_own_words" and entry["redner_id"] != owner_id(host):
                    raise reviewed_units.ReviewedUnitsError(
                        f"{where}: {entry['rede_id']} is listed as own words, but the <rede> after is {owner_id(host)}'s")
            moves.append(([element for index, _, _ in run for element in children[index:turn_end(index)]], host, "start"))
    for moved, host, place in moves:
        moved = [element for element in moved if id(element) not in staying]
        if host is None:
            rede = ET.Element("rede", {"id": place})
            top.insert(list(top).index(moved[0]), rede)
            created.add(place)
        for element in moved:
            top.remove(element)
        if host is None:
            rede.extend(moved)
        elif place == "end":
            host.extend(moved)
        else:
            for offset, element in enumerate(moved):
                host.insert(offset, element)
    return diagnostics


def mark_presidium_fraktionsreden(root: ET.Element) -> None:
    """ADR 0004: a Vizepräsident(in) who owns a ``<rede>`` and is printed with a
    ``<fraktion>`` gives that Fraktion's Rede (18/46 Pau). The presidium
    ``<rolle>`` is removed from the owner's markers in that ``<rede>``, so the
    Rede reads as an MdB's. Without a Fraktion (18/245), and for the Präsident
    and Alterspräsident, the role stays: the ``<rede>`` needs a reviewed kind
    (``mark_reviewed_units``) or refuses its sitting. A listed ``<rede>`` keeps
    its role for the card.
    """
    for rede in root.iter("rede"):
        first = rede.find("./p[@klasse='redner']/redner")
        if rede.get("reviewed_kind") or first is None or not child_text(first.find("name"), "fraktion"):
            continue
        role = first.find("name/rolle")
        if role is None or not VIZEPRAESIDIUM_ROLE.fullmatch(re.sub(r"\s+", "", child_text(role, "rolle_lang"))):
            continue
        own = redner_key(first)
        for redner in rede.iter("redner"):
            name = redner.find("name")
            if redner_key(redner) == own and name is not None and name.find("rolle") is not None:
                name.remove(name.find("rolle"))


def mark_presidium_markers_outside_reden(root: ET.Element) -> None:
    """ADR 0004 (18/62, 18/90): a Vizepräsident(in) printed with a ``<fraktion>``
    at a marker outside any ``<rede>``, which a Fragestunde reads and, in any other
    TOP, the reviewed ``loose_*`` entry of ``mark_loose_markers`` places. When the
    last chair ``<name>`` before the marker ends with their first and last name,
    they chair and the marker is Sitzungsleitung: it is marked
    ``sitzungsleitung="1"`` (18/62 Singhammer). Otherwise they ask as an MdB, and
    the presidium ``<rolle>`` is removed so the turn reads as their Fraktion's
    (Pau's Nachfragen). The Präsident, the Alterspräsident and a marker without a
    Fraktion keep their role, which no Sprechrolle rule maps.
    """
    verlauf = root.find("sitzungsverlauf")
    if verlauf is None:
        return
    outside = {id(marker) for top in verlauf.iter("tagesordnungspunkt") for marker in top.findall("p[@klasse='redner']")}
    chair = ""
    for elem in verlauf.iter():
        if elem.tag == "name" and elem.find("nachname") is None:
            chair = elem_text(elem)
        if id(elem) not in outside:
            continue
        redner = elem.find("redner")
        name = redner.find("name") if redner is not None else None
        role = name.find("rolle") if name is not None else None
        if (role is None or not child_text(name, "fraktion")
                or not VIZEPRAESIDIUM_ROLE.fullmatch(re.sub(r"\s+", "", child_text(role, "rolle_lang")))):
            continue
        full = clean_text(f"{child_text(name, 'vorname') or ''} {child_text(name, 'nachname') or ''}")
        if full and re.search(rf"(?<![\w-]){re.escape(full)}\s*:?$", chair):
            redner.set("sitzungsleitung", "1")
        else:
            name.remove(role)


def adopt_reden_outside_tops(root: ET.Element) -> None:
    """18/49 and 18/44 print Reden directly under ``<sitzungsverlauf>``: the source
    lost the ``<tagesordnungspunkt>`` around them. The Inhaltsverzeichnis still names
    each one's item ("Einzelplan 06", "Zur Geschäftsordnung"), the labels other sittings
    use as ``top-id``. Each run under one Inhaltsverzeichnis label is wrapped in place
    under that label and marked ``top_source``; a TOP the chair called in
    ``<sitzungsbeginn>`` moves in with the run after it. A Rede with no entry, one
    listed under two different titles, or one after any other element is a shape no
    source has shown yet: refused, never placed by guess. ``top_source`` is the parser's mark, so a source element carrying
    it loses it first.
    """
    verlauf = root.find("sitzungsverlauf")
    if verlauf is None:
        return
    for element in verlauf.iter():
        element.attrib.pop("top_source", None)
    if verlauf.find("rede") is None:
        return
    blocks: dict[str, list[ET.Element]] = {}
    for block in root.findall("./vorspann/inhaltsverzeichnis/ivz-block"):
        for xref in block.findall(".//xref"):
            if xref.get("rid") and block not in blocks.setdefault(xref.get("rid"), []):
                blocks[xref.get("rid")].append(block)
    sitting = f"{root.get('wahlperiode')}/{root.get('sitzung-nr')}"
    arranged: list[ET.Element] = []
    before: ET.Element | None = None  # the first source element other than <sitzungsbeginn>
    open_label = None
    for child in list(verlauf):
        verlauf.remove(child)
        if child.tag != "rede":
            arranged.append(child)
            if before is None and child.tag != "sitzungsbeginn":
                before = child
            open_label = None
            continue
        rid = child.get("id")
        if before is not None:
            what = "a TOP" if before.tag == "tagesordnungspunkt" else f"a <{before.tag}> element"
            raise ValueError(f"{sitting}: Rede {rid} stands outside any TOP, after {what}")
        labels = {toc_block_label(block) for block in blocks.get(rid, [])} - {""}
        if len(labels) > 1:
            raise ValueError(f"{sitting}: Rede {rid} stands outside any TOP and two Inhaltsverzeichnis titles list it: "
                             + ", ".join(sorted(labels)))
        title = next(iter(labels), "")
        if not title:
            raise ValueError(f"{sitting}: Rede {rid} stands outside any TOP, with no Inhaltsverzeichnis entry")
        if title != open_label:
            top = ET.Element("tagesordnungspunkt", {"top-id": title, "top_source": "inhaltsverzeichnis"})
            if arranged and arranged[-1].tag == "sitzungsbeginn" and title.startswith(("Tagesordnungspunkt", "Zusatzpunkt")):
                for paragraph in arranged[-1].findall("p"):
                    if (paragraph.get("klasse") or "").startswith("T_"):
                        arranged[-1].remove(paragraph)
                        top.append(paragraph)
            arranged.append(top)
            open_label = title
        arranged[-1].append(child)
    verlauf.extend(arranged)


def toc_block_label(block: ET.Element) -> str:
    """The item an Inhaltsverzeichnis block names, as a ``top-id``: its title, a
    title broken with "-" joined to its ``A_TOP`` continuation, without the colon."""
    title = elem_text(block.find("ivz-block-titel"))
    if title.endswith("-"):
        title = title[:-1] + elem_text(block.find("p[@klasse='A_TOP']"))
    return title.rstrip(": ")


def presidium_marker(redner: ET.Element | None) -> bool:
    if redner is not None and redner.get("sitzungsleitung") == "1":
        return True
    return redner is not None and bool(SITZUNGSLEITUNG_ROLE.fullmatch(re.sub(r"\s+", "", parse_redner(redner).get("role") or "")))


def split_nested_reden(top: ET.Element, created: set[str] | None = None) -> None:
    """6c: WP 18/19 can print a whole Rede inside the previous ``<rede>``.

    When the chair gives that speaker the floor in the form of the Rednerliste
    and the turn opens with a salutation, the turn and everything after it
    becomes a Rede of its own, ``<outer id>:<marker>``; the outer Rede ends at
    the marker. The tree is changed in place. ``created``, when given, receives
    the id of each part made, so the reconciliation can require a status for it.
    """
    work = list(top.findall("rede"))
    while work:
        rede = work.pop(0)
        rid = rede.get("id")
        if not rid:
            continue
        own = redner_key(rede.find("./p[@klasse='redner']/redner"))
        # In a listed Sitzungsleitung <rede> (ADR 0004) the owner's own words
        # are the chair's, so a Rede given the floor there splits off.
        owner_chairs = rede.get("reviewed_kind") == "sitzungsleitung"
        children = list(rede)
        marker = 0
        chair = None
        for index, child in enumerate(children):
            if child.tag == "name":
                chair = ""
                continue
            if child.tag != "p":
                continue
            if child.get("klasse") != "redner":
                if chair is not None:
                    chair += " " + elem_text(child)
                continue
            marker += 1
            redner = child.find("redner")
            key = redner_key(redner)
            if (key not in (own, None) and presidium_marker(redner)) or (owner_chairs and key == own):
                chair = clean_text((redner.tail or "").partition(":")[2])
                continue
            last_name = (parse_redner(redner) or {}).get("last_name") or ""
            # A Rede printed under <name> (ADR 0004 amendment 2026-11-22) is
            # listed: it splits whatever words give the floor or open it.
            listed = key not in (own, None) and redner.get("listed_kind") == "rede"
            if listed or (key not in (own, None) and chair and last_name and NESTED_REDE_FLOOR.search(chair)
                          and not NESTED_REDE_NOT_FLOOR.search(chair)
                          and re.search(rf"(?<![\w-]){re.escape(last_name)}(?![\w-])", chair)):
                tail = clean_text((redner.tail or "").partition(":")[2])
                following = next((c for c in children[index + 1:] if c.tag == "p"), None)
                opening = tail or (elem_text(following) if following is not None and following.get("klasse") != "redner" else "")
                if listed or REDE_SALUTATION.match(opening):
                    split = ET.Element("rede", {"id": f"{rid}:{marker}"})
                    if created is not None:
                        created.add(split.get("id"))
                    for moved in children[index:]:
                        rede.remove(moved)
                        split.append(moved)
                    top.insert(list(top).index(rede) + 1, split)
                    work.insert(0, split)
                    break
            chair = None


def speech_segments(rede: ET.Element, *, inline: bool = False, all_speakers: bool = False) -> tuple[SpeechText, list[dict[str, Any]]]:
    """One source walk: own words and separate nested speaker segments.

    Marker ordinals count every speaker marker, including resumptions. The
    announcement field also carries explicit grant/acknowledgement evidence.
    Chair text and comments never become speaker text.
    """
    own = redner_key(rede.find("./p[@klasse='redner']/redner"))
    speaker: object = own
    paragraphs: list[str] = []
    nested: list[dict[str, Any]] = []
    segment = None
    unattributed = 0
    marker = 0
    chair_text = ""
    pending_nested_announcement = ""
    pending_nested_names = None
    # Carry refusals into classification even across empty speaker segments.
    grant_epoch = 0
    preceding_chair_text = ""
    refused = False
    pending_request = ""
    pending_factions = set()
    interrupted_request_pending = False
    floor_granted = False
    request_accepted = False
    declined_request = ""
    last_text = ""
    offer_open = False  # the chair offered a question and no MdB has taken it yet
    exchange = 0  # counts the chair's offers; one asker's turns within one are one Zwischenfrage
    consent_turn: list[str] | None = None  # the Redner's latest turn, if it followed an offer
    candidates = {asker_name(parse_redner(r)["last_name"]): r for r in rede.iter("redner")
                  if redner_key(r) != own and parse_redner(r).get("last_name")}

    candidate_keys = {name: {redner_key(r) for r in rede.iter("redner")
                             if redner_key(r) != own and asker_name(parse_redner(r).get("last_name")) == name}
                      for name in candidates}

    def recipients(context):
        questions = list(re.finditer(r"\b(?:Zwischenfragen?|Zwischenbemerkung|Frage(?:n|wunsch)?|Nachfrage|Rückfrage|Wortmeldung)\b", context, re.IGNORECASE))
        question = questions[0] if questions else None
        # Keep asker clauses on either side of the question, excluding its
        # addressee and unrelated chair addresses. A shortened compound surname
        # is safe only when it selects one structured candidate in this Rede.
        recipient_text = " ".join(speech_kinds._SENTENCE_END.split(context[q.end():])[0] for q in questions) if questions else speech_kinds._SENTENCE_END.split(context)[0]
        recipient_text = re.split(r"\ban (?:den|die) Abgeordnet", recipient_text, flags=re.IGNORECASE)[0]
        asker_context = re.split(r"\ban (?:den|die) Abgeordnet", context, flags=re.IGNORECASE)[0]
        names = set()
        for name, r in candidates.items():
            aliases = [name]
            short = name.split()[0]
            if short != name and short not in {"von", "van", "de", "zu", "zur", "zum"} and sum(len(candidate_keys[n]) for n in candidates if n.split()[0] == short) == 1:
                aliases.append(short)
            for alias in aliases:
                token = rf"(?<![\w-]){re.escape(alias)}(?![\w-])"
                if (re.search(token, recipient_text, re.IGNORECASE)
                    or re.search(token + r"[^.!?]{0,100}(?:gemeldet|würde[^.!?]{0,30}gerne?|hat die Möglichkeit)", asker_context, re.IGNORECASE)):
                    names.add(name)
        explicit_names = nested_grant_names(context) or set()
        if not question:
            explicit_names |= {name.split()[-1].casefold() for name in re.findall(
                r"\b(?:Herrn?|Frau|Kollegen?|Kollegin|Abgeordnete[nr]?)\s+(?:Dr\.\s+)?"
                r"([A-ZÄÖÜ][\wÄÖÜäöüß-]*(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß-]*)*)", recipient_text)}
        names |= {name for name in explicit_names
                  if not any((candidate.endswith(" " + name) or candidate.startswith(name + " ")) or speech_kinds._text(candidates[candidate].find("name/vorname")).casefold() == name
                             for candidate in names)
                  and name != speech_kinds._last_name(rede.find("./p[@klasse='redner']/redner")).casefold()}
        # A faction attached to a named asker does not grant its other members.
        factions = set()
        for clause in re.split(r"\bund (?:einmal|von|aus)\b", recipient_text, flags=re.IGNORECASE):
            if any(re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", clause, re.IGNORECASE) for name in names):
                continue
            factions |= {derive.zusammenschluss(faction) for faction, pattern in speech_kinds.FRAKTION_WORDING.items()
                         if pattern.search(clause)}
        return names or None, factions

    flow = speech_kinds.ParagraphFlow()
    for child in rede:
        flow.see(child)
        if child.tag == "name":
            speaker, segment = _SITZUNGSLEITUNG, None
            chair_text = ""
        elif child.tag == "p":
            if child.get("klasse") == "redner":
                marker += 1
                redner = child.find("redner")
                speaker, segment = redner_key(redner), None
                if speaker not in (own, None) and presidium_marker(redner):
                    # WP 18/19 prints the chair inside a member's Rede as a
                    # marker with a presidium role (ADR 0004): chair text, kept
                    # as a segment only for its procedural diagnostic.
                    speaker = _SITZUNGSLEITUNG
                    segment = {"speaker": parse_redner(redner), "marker": marker, "paragraphs": [],
                               "announcement": "", "sitzungsleitung": True}
                    nested.append(segment)
                if speaker == own:
                    preceding_chair_text = chair_text
                    consent_turn = [] if offer_open else None
                if speaker != own and speaker is not _SITZUNGSLEITUNG:
                    if speaker is not None:
                        candidate = parse_redner(redner)
                        named_in_grant = (candidate.get("last_name") and pending_nested_names
                                          and asker_name(candidate["last_name"]) in pending_nested_names)
                        faction_matches = derive.zusammenschluss(candidate.get("fraktion")) in pending_factions
                        recipient_mismatch = ((pending_nested_names is not None or bool(pending_factions))
                                              and not (named_in_grant or faction_matches))
                        if recipient_mismatch:
                            grant_context = ""
                            chair_text = ""
                        else:
                            grant_context = pending_nested_announcement
                        segment = {"speaker": candidate, "marker": marker, "paragraphs": [], "prompt": last_text,
                                   "listed_kind": redner.get("listed_kind"),
                                   "grant_epoch": grant_epoch, "refused": refused, "exchange": exchange,
                                   "recipient_mismatch": bool(recipient_mismatch),
                                   "granted": consent_turn is not None and nested_consent(consent_turn),
                                   "chair_floor": bool(chair_text.strip()) and not re.search(r"Kurzintervention|Erwiderung", chair_text, re.IGNORECASE),
                                   "authorized": bool(grant_context) and (not interrupted_request_pending or floor_granted),
                                   "incomplete_exchange": interrupted_request_pending and not (request_accepted and floor_granted),
                                   "announcement": " ".join(filter(None, (grant_context, chair_text)))}
                        nested.append(segment)
                        offer_open, consent_turn = False, None
                        if named_in_grant:
                            pending_nested_names.discard(asker_name(candidate["last_name"]))
                        elif faction_matches:
                            pending_factions.discard(derive.zusammenschluss(candidate.get("fraktion")))
                        if not pending_nested_names and not pending_factions:
                            pending_nested_announcement = pending_request = ""
                            pending_nested_names = None
                    else:
                        pending_nested_announcement = ""
                        pending_nested_names = None
                if speaker == own and all_speakers:
                    segment = {"speaker": parse_redner(redner), "marker": marker, "paragraphs": [],
                               "announcement": preceding_chair_text, "own": True}
                    nested.append(segment)
                chair_text = ""
                if not inline and segment is None:
                    continue
                # Written annexes can start the entire first paragraph in the
                # printed label's tail. Preserve only what follows its colon.
                text = clean_text((redner.tail or "").partition(":")[2]) if redner is not None else ""
            else:
                text = elem_text(child)
            if not text:
                continue
            last_text = text
            if speaker is None:
                unattributed += len(text)
            elif speaker is _SITZUNGSLEITUNG:
                if segment is not None:
                    flow.add(child, text, segment["paragraphs"])
                chair_text += " " + text
                offer_open = offer_open or bool(NESTED_OFFER.search(text))
                if NAMED_OFFER.search(text) and not NESTED_OFFER.search(chair_text):
                    named = {name for name in candidates
                             if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", chair_text, re.IGNORECASE)}
                    if named:
                        offer_open, pending_nested_names = True, named
                        exchange += 1
                question_request = re.search(
                    r"\b(?:Zwischenfragen?|Zwischenbemerkung|Frage(?:n|wunsch)?|Nachfrage|Rückfrage|Wortmeldung)\b", chair_text, re.IGNORECASE)
                interrupted_request = re.search(r"Ich wollte Sie fragen:.*\bHerr\b.*würde gerne\s*[–-]", chair_text)
                request_wording = re.search(
                    r"gestatt|erlaub|zulass|lassen.*\bzu\b|es gibt|es gäbe|es würde.*geben|wir haben|Sagen Sie Ja oder Nein|hat sich gemeldet|Fragewunsch|hat die Möglichkeit|Sind Sie bereit|würde[^.!?]{0,30}gerne?|geben Sie",
                    chair_text, re.IGNORECASE)
                if ((question_request and request_wording) or interrupted_request
                        or (NESTED_OFFER.search(text) and NEW_OFFER_WORDING.search(text))):
                    exchange += 1
                if (question_request and request_wording) or interrupted_request:
                    request_accepted = False
                    interrupted_request_pending = bool(interrupted_request)
                    floor_granted = False
                    if pending_request and not refused and re.search(r"\b(?:auch|noch|immer noch|zweite|weitere)\b", chair_text):
                        pending_request += " " + chair_text
                    else:
                        pending_request = chair_text
                        pending_nested_names = None
                    names, factions = recipients(pending_request)
                    if names:
                        pending_nested_names = (pending_nested_names or set()) | names
                    pending_factions = factions
                    if not refused and re.search(r"Zwischenfrage|Zwischenbemerkung", chair_text, re.IGNORECASE):
                        pending_nested_announcement = pending_request
                if declined_request and re.fullmatch(r"\s*Also doch\?", chair_text):
                    pending_request = declined_request
                    pending_nested_names, pending_factions = recipients(pending_request)
                    request_accepted = False
                if interrupted_request_pending and (speech_kinds.INVITES.match(chair_text)
                    or re.search(r"Es sind noch .* Sekunden\. Aber bitte schön\.", chair_text)):
                    floor_granted = True
                if pending_nested_announcement and re.search(r"\b(?:Herr|Frau)\b|\bWort\b", chair_text):
                    pending_nested_announcement += " " + chair_text
            elif speaker == own:
                flow.add(child, text, paragraphs, *([segment["paragraphs"]] if all_speakers and segment is not None else []))
                if consent_turn is not None:
                    consent_turn.append(text)
                grant = NESTED_GRANT_EVIDENCE.search(text)
                contextual_no = request_accepted and (
                    re.search(r"\b(?:Hoffnungen nicht enttäuschen|verlängert Ihre Redezeit|das ist abgesprochen)\b", preceding_chair_text, re.IGNORECASE)
                    or re.match(r"^\W*Nein, wir nehmen die Leute ernst\.", text))
                correction = re.fullmatch(r"Nein, von (?:Frau|Herrn?) [\wÄÖÜäöüß -]+\.", text)
                refusal = (grant and grant.group("grant") and speech_kinds.NOT_GRANTED.search(grant.group("grant"))) or (
                    pending_request and not contextual_no and not correction and re.match(r"^\W*(?:Nein|Nee|Auf keinen Fall|An dieser Stelle nicht)\b", text, re.IGNORECASE)) or any(
                        speech_kinds.NOT_GRANTED.search(sentence)
                        and re.search(r"Zwischenfragen?|Frage(?:n|wunsch)?|Rückfrage|Wortmeldung", sentence, re.IGNORECASE)
                        and re.search(r"\b(?:(?:ich|wir)\s+(?:lasse[n]?|gestatte[n]?|erlaube[n]?)|(?:lasse[n]?|gestatte[n]?|erlaube[n]?)\s+(?:ich|wir))\b", sentence, re.IGNORECASE)
                        for sentence in speech_kinds._SENTENCE_END.split(text))
                # An explicit reversal is fresh authorization, not a question-mark override.
                reversal = re.fullmatch(r"\W*Nein\?\s*Doch\.", text)
                refusal = refusal and not reversal
                renewed = declined_request and re.search(
                    r"\bDoch, ich lasse sie zu\b|\b(?:Bitte schön|Na los, dann fragen Sie),? (?:Herr|Frau)\b"
                    r"|\bDann stellen Sie doch eine Zwischenfrage\b|\bbitte schön, Frau\b.*\bgerne\b"
                    r"|\bWollen wir, (?:Frau|Herr)\b.*\bIch wäre bereit\b"
                    r"|\bBitte, bitte, wenn er unbedingt will\b", text, re.IGNORECASE)
                named_question = re.search(r"\b(?:Herr|Frau)\s+[^.!?]+\s+hat eine Frage\b", text)
                contextual_acceptance = pending_request and re.search(
                    r"\b(?:aber (?:bitte|gerne)|gerne .*ja|Also gerne in dieser Reihenfolge|"
                    r"ich mache das sehr gerne|Die lasse ich doch zu|Eine Frage .*lasse ich gerne zu|"
                    r"Dann kann er gerne|Von der CDU/CSU\?\s*[–-]\s*Ja)\b", text, re.IGNORECASE)
                if refusal:
                    offer_open, consent_turn = False, None
                    declined_request = pending_request or preceding_chair_text
                    pending_nested_announcement = pending_request = ""
                    pending_nested_names = None
                    pending_factions = set()
                    refused = True
                    request_accepted = False
                    grant_epoch += 1
                elif correction:
                    # Correcting the chair's recipient is neither consent nor
                    # refusal. Wait for the corrected request and acceptance.
                    pending_nested_announcement = pending_request = ""
                    pending_nested_names = None
                    pending_factions = set()
                    request_accepted = False
                elif named_question or contextual_acceptance or renewed or reversal or (grant and (grant.group("grant") or grant.group("direct"))) or (
                    pending_request and re.search(
                        r"^\W*(?:Ja\b|Bitte\b|(?:Aber )?(?:Sehr )?Gerne\b|(?:Aber )?Selbstverständlich\b|Unbedingt\b|"
                        r"(?:Die|Das) (?:würde ich dann auch zulassen|lasse ich zu|mache ich gerne|würde ich machen)|"
                        r"Vom Kollegen \w+ immer|Beide\b|Ach komm, dann mach)|\b(?:aber ja|ja, bitte)\b", text, re.IGNORECASE)):
                    request_accepted = True
                    if named_question:
                        interrupted_request_pending = True
                        floor_granted = False
                        pending_request = text
                        pending_nested_names, pending_factions = recipients(text)
                    if contextual_acceptance and re.search(r"Dann kann er gerne", text, re.IGNORECASE):
                        pending_request = preceding_chair_text
                        pending_nested_names, pending_factions = recipients(pending_request)
                    if renewed:
                        pending_request = pending_request or declined_request
                        pending_nested_names, pending_factions = recipients(pending_request)
                        named_recipients, _ = recipients(text)
                        if named_recipients:
                            pending_nested_names = named_recipients
                    pending_nested_announcement = " ".join(dict.fromkeys(filter(None, (pending_request, preceding_chair_text, text))))
                    if not pending_request or re.search(r"Vom Kollegen \w+ immer", text):
                        names, factions = recipients(text)
                        pending_nested_names = names or pending_nested_names
                        pending_factions |= factions
                    refused = False
            elif segment is not None:
                flow.add(child, text, segment["paragraphs"])
    granted_key = None
    for nested_segment in nested:
        text = " ".join(nested_segment["paragraphs"])
        evidence = NESTED_GRANT_EVIDENCE.search(text)
        if evidence and evidence.group("ack") and not nested_segment.get("refused") and not speech_kinds.NOT_GRANTED.search(evidence.group("ack")):
            nested_segment["announcement"] = " ".join(filter(None, (nested_segment["announcement"], evidence.group("ack"))))
        if "grant_epoch" in nested_segment:
            # 6a (2): an opening thank-you that is not negated grants, over a carried
            # refusal; the same speaker's next turn continues that grant.
            speaker_grant = ((nested_segment["speaker"] or {}).get("xml_redner_id"), nested_segment["grant_epoch"])
            thanks = NESTED_OPENING_THANKS.search(nested_segment["paragraphs"][0][:140]) if nested_segment["paragraphs"] else None
            if nested_segment["granted"] or (thanks and not speech_kinds.NOT_GRANTED.search(thanks.group())):
                nested_segment["granted"], granted_key = True, speaker_grant
            elif speaker_grant[0] and speaker_grant == granted_key:
                nested_segment["granted"] = True
            else:
                granted_key = None
    return SpeechText(speech_kinds.join_paragraphs(paragraphs), paragraphs, unattributed), [s for s in nested if s["paragraphs"]]


def speech_text_and_paragraphs(rede: ET.Element) -> SpeechText:
    return speech_segments(rede)[0]


def snippet_of(text: str) -> str:
    """The first 240 characters of a wording as one line."""
    return clean_text(text)[:240]


def contribution_unit(kind: str, rede_id: str | None, parent: str | None, sequence: int,
                      speaker: dict[str, Any] | None, paragraphs: list[str], page: dict[str, Any] | None) -> dict[str, Any]:
    text = speech_kinds.join_paragraphs(paragraphs)
    return {"kind": kind, "rede_id": rede_id, "parent_rede_id": parent,
            "sequence": sequence, "speaker": speaker, "paragraphs": paragraphs,
            "source_page": page, "text": text, "char_count": len(text),
            "paragraph_count": len(paragraphs), "snippet": snippet_of(text), "unattributed_char_count": 0}


ZU_PROTOKOLL_ANNEX = re.compile(r"zu protokoll gegebene reden?(?: zur beratung:?)?")

#: Annex titles whose Reden stay out on purpose: (rule, title pattern, reason). A
#: ``<rede>`` in an annex under any other title that is not a written submission is
#: left without a status and refuses the sitting (``reconcile_reden``), so an unseen
#: title is named here after review, never dropped silently. "Technisch bedingter
#: Neudruck der zu Protokoll gegebenen Rede" and "Zu Protokoll gegebene Ergänzung"
#: held no ``<rede>`` in the 716 sittings of the A3 store (#143), so they have no rule.
ANNEX_EXCLUSIONS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("paragraph_31", re.compile(r"erkl(?:ä|ae)rung(?:en)? nach § ?31\b.*"),
     "Erklärungen nach § 31 GO are not Reden (ADR 0002)"),
    ("paragraph_31_continuation", re.compile(r"zu der abstimmung über .+"),
     "19/115: the second block of a §31 annex, which lost the words \"nach § 31 GO\""),
    ("reprint", re.compile(r"neudruck eines redebeitrages\b.*"),
     "a reprint of a Rede of the sitting before (19/35, 19/45), which belongs to that sitting"),
)


#: A block printed under the wrong ``anlagen-typ`` and read by its own first
#: ``Anlage_3`` heading: (title pattern, heading pattern). 19/36's Anlage 2 repeats
#: Anlage 1's title "Liste der entschuldigten Abgeordneten" but holds no list: its
#: heading is "Zu Protokoll gegebene Fortsetzung des abgebrochenen Redebeitrages der
#: Abgeordneten Martina Stamm-Fibich (SPD)", as the protocol's Inhaltsverzeichnis
#: lists it (docs/source-errors.md). Of the 356 blocks under that exact title in
#: the 802 WP 18/19 sittings held (and the 799 under any "entschuldigt" title), it
#: is the only one holding a ``<rede>`` or such a heading, so a real list never
#: matches; the block is read only when both title and heading match.
MISTITLED_ZU_PROTOKOLL = (re.compile(r"liste der entschuldigten abgeordneten"),
                          re.compile(r"zu protokoll gegebene (?:reden?|fortsetzung)\b.*"))

#: A TOP reference that also names the page of the Rede it continues, as 19/36's
#: "(Tagesordnungspunkt 5, Seite 3370 C)": the page is not part of the TOP id.
TOP_REF_PAGE = re.compile(r",\s*Seite\s+\d+.*")


def annex_title(block: ET.Element) -> str:
    return clean_text(block.get("anlagen-typ") or "").casefold()


def zu_protokoll_annex_type(block: ET.Element) -> str | None:
    """What a block of written submissions is called, or None for any other block:
    its ``anlagen-typ``, or for a ``MISTITLED_ZU_PROTOKOLL`` block its own heading."""
    if ZU_PROTOKOLL_ANNEX.fullmatch(annex_title(block)):
        return block.get("anlagen-typ")
    title, heading_pattern = MISTITLED_ZU_PROTOKOLL
    if not title.fullmatch(annex_title(block)):
        return None
    heading = elem_text(next((p for p in block if p.tag == "p" and p.get("klasse") == "Anlage_3"), None))
    return heading if heading_pattern.fullmatch(heading.casefold()) else None


def annex_exclusion(block: ET.Element) -> str | None:
    """The rule that keeps an annex block's Reden out, or None."""
    title = annex_title(block)
    return next((rule for rule, pattern, _ in ANNEX_EXCLUSIONS if pattern.fullmatch(title)), None)


def exclude_annex_reden_in_verlauf(root: ET.Element, statuses: dict[str, str]) -> None:
    """18/158 prints the 37 Erklärungen nach § 31 GO of its Anlage 7 in the
    Sitzungsverlauf, as the ``<rede>``s of a headingless TOP "Geschaeftsordnung",
    and leaves Anlage 7 with its title alone (docs/source-errors.md E9). The
    Inhaltsverzeichnis still lists each under "Anlage 7". A ``<rede>`` of the
    Sitzungsverlauf that the Inhaltsverzeichnis lists under an "Anlage N" block,
    where the annex "Anlage N" is one block, kept out by an ``ANNEX_EXCLUSIONS``
    rule and holding no ``<rede>`` of its own, takes that rule's status as an
    annex Rede does and leaves the tree; a TOP it leaves empty goes too. In the
    802 WP 18-21 sittings held, only 18/158's 37 match."""
    annexes: dict[str, ET.Element] = {}
    for anlage in root.findall("./anlagen/anlage"):
        blocks = anlage.findall("anlagen-text")
        title = elem_text(anlage.find("anlagen-titel"))
        if title and len(blocks) == 1 and blocks[0].find(".//rede") is None:
            annexes[title] = blocks[0]
    rules: dict[str, str] = {}
    for block in root.findall("./vorspann/inhaltsverzeichnis/ivz-block"):
        title = elem_text(block.find("ivz-block-titel"))
        annex = annexes.get(title) if title else None
        rule = annex_exclusion(annex) if annex is not None else None
        if rule is not None:
            rules.update({xref.get("rid"): rule for xref in block.iter("xref") if xref.get("rid")})
    verlauf = root.find("sitzungsverlauf")
    if not rules or verlauf is None:
        return
    for top in [verlauf, *verlauf.findall("tagesordnungspunkt")]:
        moved = False
        for rede in top.findall("rede"):
            if rede.get("id") in rules:
                record_status(statuses, rede.get("id"), f"excluded_annex:{rules[rede.get('id')]}")
                top.remove(rede)
                moved = True
        # Only a TOP this rule emptied: one the source prints childless stays.
        if moved and top is not verlauf and len(top) == 0:
            verlauf.remove(top)


def annex_rede_key(block_index: int, sequence: int) -> str:
    """The key of an annex ``<rede>`` without an id: its block among all
    ``anlagen-text`` blocks and its place among the block's direct ``<rede>``s."""
    return f"annex:{block_index}:{sequence}"


#: An annex heading ends the text a block-level ``annex_rede`` entry wraps.
ANNEX_HEADINGS = frozenset({"Anlage_2", "Anlage_3", "Anlage_Strich"})
#: What to do when a sitting is refused for an unlisted annex shape: a re-fetch
#: returns the same XML.
UNLISTED_ANNEX_TEXT_FIX = ("list the written Rede in scripts/reviewed_units.json with kind annex_rede "
                           "(docs/source-errors.md E17, docs/plans/e17-wp18-texts.md), then re-run")


class UnlistedAnnexTextError(ValueError):
    """A zu-Protokoll annex where a ``<rede>`` holds markers of two Redner-IDs or
    none, or a speaker marker stands outside any ``<rede>``, with no reviewed
    entry: the words would be dropped or credited to nobody, so the sitting is
    refused (``UNLISTED_ANNEX_TEXT_FIX``)."""


def mark_annex_texts(root: ET.Element, entries: list[dict[str, str]], created: set[str]) -> None:
    """docs/source-errors.md E17: give each written Rede a zu-Protokoll annex
    prints without a ``<rede>`` of its own one, by its ``annex_rede`` entry in
    ``scripts/reviewed_units.json`` (``docs/plans/e17-wp18-texts.md``).

    The entry's ``label`` is found once where the entry's ``rede_id`` points: a
    speaker marker printing it (kept; it must carry the entry's Redner-ID and
    ``name``), a paragraph opening with it and a colon (the label leaves the
    paragraph, and a marker built from ``name`` goes before it), or, where neither
    is printed in a block, a heading naming the writer (the marker goes before
    the first paragraph after it that is no heading). In another writer's ``<rede>`` everything from the
    marker on becomes ``<rede id="<id>:<marker ordinal>">`` right after it, the
    form of ``split_nested_reden``; a ``<rede>`` the label opens keeps its id. In
    a block the marker and its paragraphs up to the next ``<rede>``, annex heading
    or block end become ``<rede id="annex:<block>:<place>">`` (``annex_rede_key``).
    Each id made goes into ``created``. Only annex blocks are edited.

    Afterwards a zu-Protokoll block where a ``<rede>`` holds markers of two
    Redner-IDs or none, or a marker stands outside any ``<rede>``, refuses the
    sitting (``UnlistedAnnexTextError``). An entry that does not match its place
    stops the run (``ReviewedUnitsError``).
    """
    sitting = f"{root.get('wahlperiode')}/{root.get('sitzung-nr')}"
    blocks = root.findall("./anlagen/anlage/anlagen-text")
    written = [block for block in blocks if zu_protokoll_annex_type(block) is not None]

    def is_marker(element: ET.Element) -> bool:
        return element.tag == "p" and element.get("klasse") == "redner"

    def marker_label(element: ET.Element) -> str:
        return clean_text((element.find("redner").tail or "") if element.find("redner") is not None else "").partition(":")[0].strip()

    for entry in entries:
        where = f"scripts/reviewed_units.json: {sitting} annex_rede {entry['rede_id']} ({entry['label']})"
        if re.fullmatch(r"A[1-9]\d*", entry["rede_id"]):
            index = int(entry["rede_id"][1:])
            container = blocks[index - 1] if index <= len(blocks) else None
            if container is None or container not in written:
                raise reviewed_units.ReviewedUnitsError(f"{where}: names no zu-Protokoll block of this sitting's XML")
            host = None
        else:
            host = next((rede for block in written for rede in block.findall("rede") if rede.get("id") == entry["rede_id"]), None)
            if host is None:
                raise reviewed_units.ReviewedUnitsError(f"{where}: names no <rede> of a zu-Protokoll annex in this sitting's XML")
            container = host
        children = list(container)
        label = re.compile(rf"\s*{re.escape(entry['label'])}\s*:\s*")
        places = []
        for index, child in enumerate(children):
            if is_marker(child) and marker_label(child) == entry["label"]:
                places.append((index, "marker"))
            elif child.tag == "p" and not is_marker(child) and label.match(child.text or ""):
                places.append((index, "paragraph"))
        if not places and host is None:
            # The heading names the writer of every written Rede below it; it
            # marks where a text begins only where no label is printed (18/34).
            places = [(index, "heading") for index, child in enumerate(children) if child.tag == "p"
                      and child.get("klasse") == "Anlage_3" and entry["label"] in elem_text(child)]
        if len(places) != 1:
            raise reviewed_units.ReviewedUnitsError(
                f"{where}: the label is found {'nowhere' if not places else f'{len(places)} times'} in its place")
        start, how = places[0]
        if how == "marker":
            marker = children[start]
            if redner_key(marker.find("redner")) != entry["redner_id"]:
                raise reviewed_units.ReviewedUnitsError(
                    f"{where}: the marker carries Redner-ID {marker.find('redner').get('id')}, not {entry['redner_id']}")
            if entry["name"] != entry["label"]:
                raise reviewed_units.ReviewedUnitsError(f"{where}: name {entry['name']!r} must equal the printed marker's label")
        else:
            if how == "heading":
                start = next((index for index in range(start + 1, len(children)) if children[index].tag == "p"
                              and children[index].get("klasse") not in ANNEX_HEADINGS), None)
                if start is None or is_marker(children[start]):
                    raise reviewed_units.ReviewedUnitsError(f"{where}: no text paragraph follows the heading")
            else:
                paragraph = children[start]
                paragraph.text = paragraph.text[label.match(paragraph.text).end():]
            marker = name_tag_marker(entry["name"], entry["redner_id"], None)
            container.insert(start, marker)
            children = list(container)
        if host is not None:
            owner = host.find("./p[@klasse='redner']/redner")
            if start == 0 and owner is marker.find("redner") and how != "marker":
                continue  # a <rede> without a marker that the label opens: it keeps its id
            if owner is None or redner_key(owner) == entry["redner_id"] or start == 0:
                raise reviewed_units.ReviewedUnitsError(f"{where}: the label opens the writer of the <rede> itself; nothing to split")
            ordinal = sum(1 for child in children[:start + 1] if is_marker(child))
            part = ET.Element("rede", {"id": f"{entry['rede_id']}:{ordinal}"})
            for moved in children[start:]:
                host.remove(moved)
                part.append(moved)
            parent = next(block for block in written if host in list(block))
            parent.insert(list(parent).index(host) + 1, part)
        else:
            end = next((index for index in range(start + 1, len(children)) if children[index].tag == "rede"
                        or (children[index].tag == "p" and children[index].get("klasse") in ANNEX_HEADINGS)), len(children))
            place = sum(1 for child in children[:start] if child.tag == "rede") + 1
            part = ET.Element("rede", {"id": annex_rede_key(blocks.index(container) + 1, place)})
            for moved in children[start:end]:
                container.remove(moved)
                part.append(moved)
            container.insert(start, part)
        created.add(part.get("id"))

    for block in written:
        for child in block:
            if is_marker(child):
                raise UnlistedAnnexTextError(f"{sitting}: a speaker marker stands outside any <rede> in annex "
                                             f"\"{block.get('anlagen-typ')}\" ({elem_text(child)[:60]!r})")
            if child.tag != "rede":
                continue
            # One writer per person: a merged record's ids name their first (redner_key).
            ids = {redner_key(marker.find("redner")) for marker in child.findall("p[@klasse='redner']")
                   if marker.find("redner") is not None}
            if len(ids) != 1:
                raise UnlistedAnnexTextError(
                    f"{sitting}: annex <rede> {child.get('id')} holds " + ("no speaker marker" if not ids else
                                                                           f"markers of {len(ids)} Redner-IDs ({', '.join(sorted(ids))})"))


def written_contributions(root: ET.Element, agenda_items: list[dict[str, Any]],
                         rid_pages: dict[str, dict[str, Any]],
                         statuses: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Only explicitly typed written submissions; an uncertain TOP stays null.

    ``statuses``, when given, records ``zu_protokoll`` for each annex Rede read and
    ``excluded_annex:<rule>`` for each Rede of a block an ``ANNEX_EXCLUSIONS`` rule
    keeps out (``reconcile_reden``)."""
    unassigned = []
    tops_by_id: dict[str, list[dict[str, Any]]] = {}
    for top in agenda_items:
        tops_by_id.setdefault(clean_text(top.get("top_id") or ""), []).append(top)
    # A page anchor marks where a page begins, so a block opens on the page of the
    # last anchor before it: the page of a Rede printed before the block's first
    # anchor, where the Inhaltsverzeichnis gives none (mark_annex_texts's units).
    page_before: dict[int, int | None] = {}
    last_page = None
    for node in root.iter():
        if node.tag == "anlagen-text":
            page_before[id(node)] = last_page
        elif node.tag == "a" and node.get("typ") == "druckseitennummer":
            last_page = page_number(re.sub(r"^S", "", node.get("id") or ""))
    for annex_index, block in enumerate(root.findall("./anlagen/anlage/anlagen-text"), 1):
        annex_type = zu_protokoll_annex_type(block)
        if annex_type is None:
            rule = annex_exclusion(block)
            if statuses is not None and rule is not None:
                for sequence, rede in enumerate(block.findall("rede"), 1):
                    record_status(statuses, rede.get("id") or annex_rede_key(annex_index, sequence), f"excluded_annex:{rule}")
            continue
        annex_pages = {}
        current_page = page_before[id(block)]
        for node in block.iter():
            if node.tag == "a" and node.get("typ") == "druckseitennummer":
                current_page = page_number(re.sub(r"^S", "", node.get("id") or ""))
            elif node.tag == "rede" and current_page is not None:
                annex_pages[node.get("id")] = {"page": current_page, "quadrant": None}

        target = None
        association_evidence = ""
        sequence = 0
        for child in block:
            if child.tag == "p":
                text = elem_text(child)
                refs = re.findall(r"\(Tagesordnungspunkt\s+([^()]+)\)", text)
                if refs:
                    association_evidence = text
                    top_id = "Tagesordnungspunkt " + clean_text(TOP_REF_PAGE.sub("", refs[0]))
                    candidates = tops_by_id.get(top_id, []) if len(refs) == 1 else []
                    target = candidates[0] if len(candidates) == 1 else None
                elif child.get("klasse") in {"Anlage_2", "Anlage_3", "Anlage_Strich"}:
                    # A new annex heading starts a new local context; a later TOP
                    # reference must not reach back across it.
                    target = None
                    association_evidence = text
                continue
            if child.tag != "rede":
                continue
            sequence += 1
            rid = child.get("id") or annex_rede_key(annex_index, sequence)
            if statuses is not None:
                record_status(statuses, rid, speech_kinds.REDE_STATUS[speech_kinds.ZU_PROTOKOLL])
            own, _nested = speech_segments(child, inline=True)
            unit = contribution_unit(speech_kinds.ZU_PROTOKOLL, rid, None, sequence,
                                     parse_redner(child.find("./p[@klasse='redner']/redner")),
                                     own.paragraphs, rid_pages.get(rid) or annex_pages.get(rid))
            unit["annex_type"] = annex_type
            unit["top_association_evidence"] = association_evidence
            if target is not None:
                unit["sequence"] = max((c["sequence"] for c in target["contributions"]), default=0) + 1
                target["contributions"].append(unit)
            else:
                unit["sequence"] = len(unassigned) + 1
                unassigned.append(unit)
    return unassigned


def xml_source_sha256(xml_text: str) -> str:
    """Hash XML text with canonical line endings, matching cache text reads.

    XML normalizes CR/CRLF to LF; transport line endings must not make an
    accepted source/report pair fail its later replay.
    """
    canonical = xml_text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class ReconciliationError(ValueError):
    """A ``<rede>`` of the source XML that the parse left without exactly one
    status, or a source shape the reconciliation cannot key (docs/data-methods.md).
    A ``ValueError``, so every caller refuses the sitting as for any parser refusal."""


class LocatedRefusal(ValueError):
    """A refusal located to one Rede and marker, raised while that Rede is
    emitted (pass 2). ``parse_protocol_xml`` withholds that Rede and goes on
    (ADR 0005); any other ``ValueError`` still refuses the sitting. Caught by
    type, never by message, so rewording a message cannot change which refusals
    are withheld."""

    def __init__(self, message: str, *, rede_id: str, marker: int, reason: str) -> None:
        super().__init__(message)
        self.rede_id = rede_id
        self.marker = marker
        self.reason = reason


class UnreviewedUnitError(LocatedRefusal):
    """A ``<rede>`` ADR 0004 says must be reviewed before it is counted: a
    presidium owner, an oath answer or an acceptance with no entry in
    ``scripts/reviewed_units.json``. Found while the TOP's Reden are read (pass
    1) and raised when that Rede is emitted, so the parser withholds it with
    reason ``unreviewed_presidium`` and keeps the sitting (decision O6)."""

    def __init__(self, message: str, *, rede_id: str) -> None:
        super().__init__(message, rede_id=rede_id, marker=1, reason="unreviewed_presidium")


#: Why a Rede is withheld: ``speech_kinds.WITHHELD_REASONS`` (one table for
#: the parser, the data dictionary, DATA.md and the Dossier).
WITHHELD_REASONS = {code: text for code, (_label, text) in speech_kinds.WITHHELD_REASONS.items()}

WORD_RE = re.compile(r"\S+")


def word_count(paragraphs: list[str]) -> int:
    """Words as whitespace-separated tokens, the count W1 measured and the N9
    shares compare."""
    return sum(len(WORD_RE.findall(paragraph)) for paragraph in paragraphs)


def withheld_record(rid: str, sequence: int, reason: str, detail: str, speaker: dict[str, Any] | None,
                    page: dict[str, Any] | None, own: "SpeechText", nested: list[dict[str, Any]]) -> dict[str, Any]:
    """A withheld Rede as it stands after pass 1: its speaker's own words
    (``text``, as a stored speech would hold them, with any text pass 1 merged
    into it) and, apart, the other speakers' turns pass 1 left in it, in marker
    order. Segments pass 1 moved out or ruled procedural are in neither (D7)."""
    turns = []
    for segment in nested:
        text = speech_kinds.join_paragraphs(segment["paragraphs"])
        turns.append({"marker": segment["marker"], "speaker": segment["speaker"],
                      "char_count": len(text), "word_count": word_count(segment["paragraphs"]), "text": text})
    return {
        "rede_id": rid, "sequence": sequence, "reason": reason, "reason_detail": detail,
        "speaker": speaker, "source_page": page,
        "paragraph_count": len(own.paragraphs), "char_count": len(own.text),
        "word_count": word_count(own.paragraphs), "text": own.text, "paragraphs": own.paragraphs,
        "nested_turns": turns, "nested_word_count": sum(turn["word_count"] for turn in turns),
    }


def raw_rede_id(unit_id: str) -> str:
    """The source ``<rede>`` id of a unit: a part ``split_nested_reden`` made,
    ``<id>:<marker>``, belongs to ``<id>``."""
    return unit_id.partition(":")[0]


def record_status(statuses: dict[str, str], key: str, status: str) -> None:
    if key in statuses:
        raise ReconciliationError(f"rede reconciliation: {key} has two statuses, {statuses[key]} and {status}")
    statuses[key] = status


def raw_rede_inventory(root: ET.Element) -> dict[str, str]:
    """Every ``<rede>`` of the source, read before any tree edit: its key and where
    it stands. The key is its id, or ``annex_rede_key`` for an annex Rede without
    one. A repeated key, or a ``<rede>`` without id outside an annex, refuses."""
    sitting = f"{root.get('wahlperiode')}/{root.get('sitzung-nr')}"
    parents = {child: parent for parent in root.iter() for child in parent}
    verlauf = root.find("sitzungsverlauf")
    blocks = {block: index for index, block in enumerate(root.findall("./anlagen/anlage/anlagen-text"), 1)}
    sequences: dict[ET.Element, int] = {}
    inventory: dict[str, str] = {}
    for rede in root.iter("rede"):
        parent = parents.get(rede)
        key = rede.get("id")
        if parent in blocks:
            sequences[parent] = sequences.get(parent, 0) + 1
            key = key or annex_rede_key(blocks[parent], sequences[parent])
            location = f"annex \"{parent.get('anlagen-typ') or ''}\""
        elif parent is not None and parent is verlauf:
            location = "sitzungsverlauf"
        elif parent is not None and parent.tag == "tagesordnungspunkt" and parents.get(parent) is verlauf:
            location = f"TOP {parent.get('top-id')}"
        else:
            path, node = [], parent
            while node is not None:
                path.append(node.tag)
                node = parents.get(node)
            location = "in " + "/".join(reversed(path))
        if not key:
            raise ReconciliationError(f"{sitting}: rede reconciliation: a <rede> without id ({location})")
        if ":" in (rede.get("id") or ""):
            raise ReconciliationError(f"{sitting}: rede reconciliation: <rede> id {key} ({location}) contains a colon, "
                                      "which marks a part split_nested_reden made")
        if key in inventory:
            raise ReconciliationError(f"{sitting}: rede reconciliation: <rede> {key} occurs twice ({inventory[key]}; {location})")
        inventory[key] = location
    return inventory


def reconcile_reden(sitting: str, inventory: dict[str, str], statuses: dict[str, str], split_parts: set[str]) -> None:
    """Each ``<rede>`` of the source, and each part ``split_nested_reden`` made of
    one, has exactly one status (``record_status``); nothing else has one."""
    for key, location in inventory.items():
        if key not in statuses:
            raise ReconciliationError(f"{sitting}: rede reconciliation: {key} ({location}) has no status")
    for part in sorted(split_parts):
        if part not in statuses:
            raise ReconciliationError(f"{sitting}: rede reconciliation: part {part} of {raw_rede_id(part)} has no status")
    unknown = sorted(set(statuses) - set(inventory) - split_parts)
    if unknown:
        raise ReconciliationError(f"{sitting}: rede reconciliation: status for units the source does not hold: {', '.join(unknown)}")


def parse_protocol_xml(xml_text: str, reviewed: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Parse one Plenarprotokoll XML. ``reviewed``: the reviewed-list entries
    of this sitting; by default those of ``scripts/reviewed_units.json``."""
    root = ET.fromstring(xml_text)
    unwrap_quotes(root)
    loose_ordinals = loose_marker_ordinals(root)
    mark_stage_direction_names(root)
    sitting = f"{root.get('wahlperiode')}/{root.get('sitzung-nr')}"
    # Read before any rule moves a <rede>: the notice of a first edition and the file's last Rede (E16).
    first_edition = protocol_cut.first_edition_notice(root)
    sitting_entries = reviewed_units.for_sitting(sitting) if reviewed is None else reviewed
    # Withhold entries name a unit as emitted; ADR 0004's kinds a whole source
    # <rede>, marked before classification (mark_reviewed_units).
    reviewed_entries = {entry["rede_id"]: entry for entry in sitting_entries
                        if entry["kind"] == reviewed_units.WITHHOLD}
    presidium_entries = [entry for entry in sitting_entries if entry["kind"] in reviewed_units.PRESIDIUM_KINDS]
    name_entries = [entry for entry in sitting_entries if entry["kind"] in reviewed_units.NAME_KINDS]
    loose_entries = {entry["rede_id"]: entry for entry in sitting_entries if entry["kind"] in reviewed_units.LOOSE_KINDS}
    unit_entries = {entry["rede_id"]: entry for entry in sitting_entries if entry["kind"] in reviewed_units.UNIT_KINDS}
    own_words_entries = {entry["rede_id"]: entry for entry in sitting_entries if entry["kind"] == reviewed_units.OWN_WORDS}
    matched_loose: set[str] = set()
    matched_entries: set[str] = set()
    inventory = raw_rede_inventory(root)
    statuses: dict[str, str] = {}
    split_parts: set[str] = set()
    exclude_annex_reden_in_verlauf(root, statuses)
    adopt_reden_outside_tops(root)
    toc = parse_toc(root)
    rid_pages: dict[str, dict[str, Any]] = {}
    for block in toc:
        for rid, page_ref in block["rid_pages"].items():
            listed = rid_pages.setdefault(rid, page_ref)
            if listed != page_ref:
                raise ValueError(f"{sitting}: Rede {rid} is listed in the Inhaltsverzeichnis at two pages: "
                                 + ", ".join(f"{p['page']} {p['quadrant'] or ''}".strip() for p in (listed, page_ref)))

    agenda_items: list[dict[str, Any]] = []
    seen_formats: dict[str, frozenset[str]] = {}
    mark_reviewed_units(root, presidium_entries)
    name_diagnostics, name_ansprachen = mark_name_speakers(root, name_entries, split_parts)
    mark_presidium_fraktionsreden(root)
    mark_presidium_markers_outside_reden(root)
    try:
        asker_candidates = speech_kinds.asker_candidates(root.iter("redner"))
    except ValueError as exc:
        raise ValueError(f"{root.get('wahlperiode')}/{root.get('sitzung-nr')}: {exc}") from exc
    mark_roleless_chairs(root)
    for index, top in enumerate(root.findall("./sitzungsverlauf/tagesordnungspunkt"), start=1):
        heading_lines: list[str] = []
        zusatz_lines: list[str] = []
        transfer_lines: list[str] = []
        for paragraph in top.findall("p"):
            klass = paragraph.attrib.get("klasse", "")
            if klass in {"T_NaS", "T_fett", "T_ohne_NaS"}:
                text = elem_text(paragraph)
                if text:
                    heading_lines.append(text)
            elif klass == "T_ZP_NaS":
                text = elem_text(paragraph)
                if text:
                    zusatz_lines.append(text)
            elif klass == "T_Ueberweisung":
                text = elem_text(paragraph)
                if text:
                    transfer_lines.append(text)

        # Some sittings put the heading of a Befragung or Fragestunde in a T_ZP_NaS paragraph
        # (20/143, 20/159) and no T_NaS/T_fett one: it is the heading then.
        heading = clean_text(" ".join(heading_lines or zusatz_lines))
        top_format = speech_kinds.top_format(heading, top.attrib.get("top-id"), seen_formats)
        loose_diagnostics = mark_loose_markers(top, top_format.formats, loose_ordinals, loose_entries, matched_loose,
                                               sitting, split_parts)
        if loose_diagnostics:
            name_diagnostics.setdefault(id(top), []).extend(loose_diagnostics)
        split_nested_reden(top, split_parts)
        joined, rest_pages = join_own_words(top, own_words_entries, matched_entries, statuses, sitting, rid_pages)
        if joined:
            name_diagnostics.setdefault(id(top), []).extend(joined)
        redes = top.findall("rede")
        for rede in redes:
            outer = raw_rede_id(rede.get("id") or "")
            if outer != rede.get("id") and outer in rid_pages:
                rid_pages.setdefault(rede.get("id"), rid_pages[outer])
        mark_listed_units(redes, unit_entries, top_format.formats, matched_entries, sitting)
        try:
            labels = speech_kinds.classify_reden(top, top_format.formats, top_format.continuation)
        except ValueError as exc:
            raise ValueError(f"{root.get('wahlperiode')}/{root.get('sitzung-nr')} {top.get('top-id')}: {exc}") from exc
        if len(labels) != len(redes):
            raise ReconciliationError(f"{sitting} {top.get('top-id')}: rede reconciliation: {len(labels)} labels for {len(redes)} Reden")
        speeches: list[dict[str, Any]] = []
        contributions: list[dict[str, Any]] = []
        pages: list[dict[str, Any]] = list(rest_pages)
        nested_units: list[dict[str, Any]] = []
        withheld: list[dict[str, Any]] = []
        diagnostics: list[dict[str, Any]] = list(name_diagnostics.pop(id(top), []))
        attachments: dict[str, list[str]] = {}
        procedural_reden = set()
        # Located refusals pass 1 finds (an ADR 0004 unit no entry names, O6; another
        # speaker's turn in a listed procedural <rede>): withheld when emitted.
        refused: dict[str, LocatedRefusal] = {}
        parsed_turns = [speech_segments(rede) for rede in redes]
        by_id = {rede.get("id"): i for i, rede in enumerate(redes)}

        def diagnostic(rid, segment, treatment, evidence, target=None):
            entry = {"source_rede_id": rid, "marker_ordinal": segment["marker"],
                     "speaker": segment["speaker"], "text": clean_text(" ".join(segment["paragraphs"])),
                     "evidence": evidence, "treatment": treatment}
            if target:
                entry["target_rede_id"] = target
                attachments.setdefault(target, []).extend(segment["paragraphs"])
            diagnostics.append(entry)

        for i, (rede, label) in enumerate(zip(redes, labels)):
            rid = rede.get("id")
            own_text, nested = parsed_turns[i]
            where = f"{sitting} {top.get('top-id')}"
            unlisted = rede.find(".//name[@unreviewed_name]")
            if unlisted is not None:
                refused[rid] = LocatedRefusal(
                    f"{where}: a speaker printed as <name>, {unlisted.get('unreviewed_name')!r}, at {rid} has no entry in "
                    "scripts/reviewed_units.json (ADR 0004)", rede_id=rid, marker=1, reason="unreviewed_name_speaker")
            if label.kind == speech_kinds.UNREVIEWED_PRESIDIUM:
                refused[rid] = UnreviewedUnitError(
                    f"{where}: presidium Rede at {rid} has no reviewed kind (scripts/reviewed_units.json, ADR 0004)", rede_id=rid)
            if label.kind is None:
                preceding = speech_kinds.trailing_sitzungsleitung_text(redes[i - 1]) if i else ""
                candidate = procedural_candidate(clean_text(own_text.text), heading, preceding)
                if candidate:
                    refused[rid] = UnreviewedUnitError(
                        f"{where}: {candidate} at {rid} has no reviewed kind (scripts/reviewed_units.json, ADR 0004)", rede_id=rid)
            reviewed_procedural = label.kind in (speech_kinds.SITZUNGSLEITUNG, speech_kinds.PROCEDURAL)
            if reviewed_procedural:
                procedural_reden.add(rid)
                evidence = ("Sitzungsleitung (reviewed): " if label.kind == speech_kinds.SITZUNGSLEITUNG
                            else "procedural (reviewed): ") + (rede.get("reviewed_reason") or "")
                for turn in speech_segments(rede, all_speakers=True)[1]:
                    if turn.get("own"):
                        diagnostic(rid, turn, "procedural", evidence)
            chair_evidence = ""
            chair = False
            for child in rede:
                if child.tag == "name":
                    chair = True
                elif child.tag == "p" and child.get("klasse") == "redner":
                    chair = False
                elif chair and child.tag == "p":
                    chair_evidence += " " + elem_text(child)
            remaining = []
            resumed_started = False
            parent_index = by_id.get(label.parent_rede_id)
            main_key = redner_key(redes[parent_index].find("./p[@klasse='redner']/redner")) if parent_index is not None else None
            reply = (i + 1 if i + 1 < len(redes) and labels[i + 1].kind == speech_kinds.ERWIDERUNG
                     and labels[i + 1].parent_rede_id == label.parent_rede_id
                     and sum(r.get("id") == redes[i + 1].get("id") for r in redes) == 1 else None)
            resumed = (i > 0 and label.kind is None and labels[i - 1].kind is None
                       and re.search(r"unterbreche den eigenen Redner", clean_text(own_text.text), re.IGNORECASE)
                       and re.search(r"\bHerbeirufung\b", own_text.text)
                       and re.search(r"Sie können weiterreden", chair_evidence)
                       and sum(r.get("id") == redes[i - 1].get("id") for r in redes) == 1)
            if resumed:
                procedural_reden.add(rid)
                for turn in speech_segments(rede, all_speakers=True)[1]:
                    if turn.get("own"):
                        diagnostic(rid, turn, "procedural", "summons request: " + clean_text(own_text.text))
            for segment in nested:
                key = derive.first_redner_id(segment["speaker"].get("xml_redner_id"))
                text = clean_text(" ".join(segment["paragraphs"]))
                if segment.get("sitzungsleitung"):
                    diagnostic(rid, segment, "procedural", "Sitzungsleitung: " + (segment["speaker"].get("role") or ""))
                    continue
                if ELECTION_QUESTION.search(segment.get("prompt") or "") and ELECTION_ACCEPTANCE.fullmatch(text):
                    diagnostic(rid, segment, "procedural", "election acceptance: " + segment["prompt"])
                    continue
                short_reply = re.fullmatch(r"(?:Nein\.|Nein, ich antworte nicht\.|Sehr gerne\.|Ja\.)", text)
                invited = re.search(r"(?:möchten Sie|dürfen.*Sie|Sie dürfen).*?(?:antworten|erwidern)", segment["announcement"], re.IGNORECASE)
                reply_evidence = re.search(r"(?:antworten|erwidern)", chair_evidence, re.IGNORECASE)
                next_rede = redes[i + 1] if i + 1 < len(redes) else None
                next_speaker = next_rede.find("./p[@klasse='redner']/redner") if next_rede is not None else None
                unique_next = next_rede is not None and sum(r.get("id") == next_rede.get("id") for r in redes) == 1
                intervention_negotiation = (
                    label.kind is None and unique_next and labels[i + 1].kind == speech_kinds.KURZINTERVENTION
                    and labels[i + 1].parent_rede_id == rid and redner_key(next_speaker) == key
                    and speech_kinds.names_asker(next_speaker, segment["announcement"])
                    and re.search(r"Sie können eine Kurzintervention machen, eine einzige", segment["announcement"])
                    and re.fullmatch(r"Eine einzige\? Ja, warum sollte ich mehrere Kurzinterventionen machen\?", text))
                delegated_reply = (
                    label.kind == speech_kinds.KURZINTERVENTION and key == main_key and invited
                    and reply is not None and unique_next and redner_key(next_speaker) != key
                    and re.fullmatch(r"Darf auch Herr [\wÄÖÜäöüß -]+ antworten\?", text)
                    and speech_kinds.names_asker(next_speaker, text)
                    and speech_kinds.names_asker(next_speaker, chair_evidence)
                    and re.search(r"Sind Sie einverstanden, dass der Abgeordnete .* antwortet\? [–-] Gut\.", chair_evidence))
                if intervention_negotiation or delegated_reply:
                    diagnostic(rid, segment, "procedural", chair_evidence)
                    continue
                if label.kind == speech_kinds.KURZINTERVENTION and key == main_key and short_reply and invited:
                    if text.startswith("Nein") or (reply is not None and redner_key(redes[reply].find("./p[@klasse='redner']/redner")) == key):
                        diagnostic(rid, segment, "procedural", segment["announcement"])
                        continue
                if (label.kind == speech_kinds.KURZINTERVENTION and key == main_key and reply is not None
                    and redner_key(redes[reply].find("./p[@klasse='redner']/redner")) == key and reply_evidence):
                    diagnostic(rid, segment, "merged_erwiderung", chair_evidence, redes[reply].get("id"))
                    continue
                if resumed and key == redner_key(redes[i - 1].find("./p[@klasse='redner']/redner")):
                    if text == "Alles gut.":
                        diagnostic(rid, segment, "procedural", "summons interruption: " + clean_text(own_text.text))
                        continue
                    if re.search(r"Sie können weiterreden", segment["announcement"]) or resumed_started:
                        resumed_started = True
                        diagnostic(rid, segment, "merged_rede", chair_evidence, redes[i - 1].get("id"))
                        continue
                if (resumed or re.fullmatch(r"Darf auch Herr [\wÄÖÜäöüß -]+ antworten\?", text)
                    or (label.kind == speech_kinds.KURZINTERVENTION and key == main_key)):
                    segment["unsupported_reply"] = True
                remaining.append(segment)
            if reviewed_procedural and remaining:
                # Nothing in a listed Sitzungsleitung or procedural <rede> is stored, so
                # no other speaker's turn in it may become a Beitrag pointing at it.
                refused[rid] = LocatedRefusal(
                    f"{where}: unresolved nested contribution at {rid} marker {remaining[0]['marker']} "
                    "inside a reviewed procedural <rede>",
                    rede_id=rid, marker=remaining[0]["marker"], reason="refused_nested_contribution")
            parsed_turns[i] = (SpeechText("", [], 0) if resumed else own_text, remaining)

        for sequence, (rede, label) in enumerate(zip(redes, labels), start=1):
            rid = rede.attrib.get("id")
            redner = parse_redner(rede.find("./p[@klasse='redner']/redner"))
            own_text, nested = parsed_turns[sequence - 1]
            if rid in attachments:
                prefix = attachments[rid] if label.kind == speech_kinds.ERWIDERUNG else []
                suffix = attachments[rid] if label.kind is None else []
                merged = prefix + own_text.paragraphs + suffix
                own_text = SpeechText(speech_kinds.join_paragraphs(merged), merged, own_text.unattributed_chars)
            granted_nested_speaker = None
            grant_epoch = 0
            open_exchange = None
            text, paragraphs, unattributed_chars = own_text
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
                "snippet": snippet_of(text),
                # The Rede's position among the TOP's <rede> elements after the
                # split (D3): withholding a neighbour never renumbers it.
                "sequence": sequence,
            }
            if nested and not rid:
                raise ValueError(f"nested contribution needs a source rede id at {top.get('top-id')} sequence {sequence}")
            entry = reviewed_entries.get(rid or "")
            if entry is not None:
                matched_entries.add(rid)
                owner = derive.first_redner_id((redner or {}).get("xml_redner_id"))
                if owner != entry["redner_id"]:
                    raise reviewed_units.ReviewedUnitsError(
                        f"scripts/reviewed_units.json: {sitting} {rid} names Redner-ID {entry['redner_id']}, "
                        f"but the source's owner of {rid} is {owner}; the entry is stale or misapplied")
                withheld.append(withheld_record(rid, sequence, "reviewed", entry["reason"], redner, page_ref, own_text, nested))
                record_status(statuses, rid, speech_kinds.WITHHELD_STATUS)
                continue
            # Commit on finish (ADR 0005): the Rede's own units and diagnostics
            # join the TOP's lists only once it is emitted whole, so a Rede
            # withheld for a located refusal leaves nothing behind.
            rede_nested: list[dict[str, Any]] = []
            rede_diagnostics: list[dict[str, Any]] = []
            try:
                if rid in refused:
                    raise refused[rid]
                for segment in nested:
                    if segment["grant_epoch"] != grant_epoch:
                        granted_nested_speaker = open_exchange = None
                        grant_epoch = segment["grant_epoch"]
                    nested_kind = speech_kinds.ZWISCHENFRAGE
                    side = derive.sprechrolle(segment["speaker"])
                    speaker_id = (segment["speaker"] or {}).get("xml_redner_id")
                    announced = (segment.get("authorized") or segment.get("granted") or re.search(r"Zwischenfrage|Zwischenbemerkung", segment["announcement"], re.IGNORECASE)
                                 or NESTED_GRANT_EVIDENCE.search(segment["announcement"])
                                 or (segment.get("chair_floor") and ADDRESSED_MEMBER.search(" ".join(segment["paragraphs"])[:300])))
                    continuation = speaker_id and speaker_id == granted_nested_speaker
                    if speech_kinds.BEFRAGUNG in top_format.formats:
                        if not side and not (segment["speaker"] or {}).get("fraktion"):
                            raise LocatedRefusal(
                                f"{root.get('wahlperiode')}/{root.get('sitzung-nr')} {top.get('top-id')}: unresolved nested question-format speaker at {rid} marker {segment['marker']}",
                                rede_id=rid, marker=segment["marker"], reason="refused_nested_question_speaker")
                        nested_kind = speech_kinds.BEFRAGUNG_ANTWORT if side else speech_kinds.BEFRAGUNG_FRAGE
                    elif (segment.get("recipient_mismatch") or segment.get("incomplete_exchange") or segment.get("unsupported_reply")
                          or (segment.get("refused") and not segment.get("granted"))
                          or side or not (segment["speaker"] or {}).get("fraktion")
                          or not (any("?" in p for p in segment["paragraphs"])
                                  or announced or continuation)):
                        raise LocatedRefusal(
                            f"{root.get('wahlperiode')}/{root.get('sitzung-nr')} {top.get('top-id')}: unresolved nested contribution at {rid} marker {segment['marker']}",
                            rede_id=rid, marker=segment["marker"], reason="refused_nested_contribution")
                    if segment.get("listed_kind") and segment["listed_kind"] != nested_kind:
                        raise reviewed_units.ReviewedUnitsError(
                            f"scripts/reviewed_units.json: {sitting} {top.get('top-id')}: the speaker printed as <name> at {rid} "
                            f"marker {segment['marker']} is listed as {segment['listed_kind']}, but the rules read a {nested_kind}")
                    granted_nested_speaker = speaker_id if nested_kind == speech_kinds.ZWISCHENFRAGE else None
                    exchange_identity = (speaker_id, segment.get("exchange")) if nested_kind == speech_kinds.ZWISCHENFRAGE else None
                    if exchange_identity and exchange_identity == open_exchange:
                        # The same asker again, with no new chair offer since: one
                        # Zwischenfrage, not one per marker.
                        first = rede_nested[-1]
                        rede_nested[-1] = contribution_unit(
                            nested_kind, first["rede_id"], rid, 0, first["speaker"],
                            first["paragraphs"] + segment["paragraphs"], first["source_page"])
                        rede_diagnostics.append({"source_rede_id": rid, "marker_ordinal": segment["marker"],
                                                 "speaker": segment["speaker"], "text": clean_text(" ".join(segment["paragraphs"])),
                                                 "evidence": "same asker, same exchange", "treatment": "merged_zwischenfrage",
                                                 "target_rede_id": first["rede_id"]})
                        continue
                    open_exchange = exchange_identity
                    rede_nested.append(contribution_unit(
                        nested_kind, f"nested:{rid}:{segment['marker']}", rid, 0,
                        segment["speaker"], segment["paragraphs"], page_ref))
            except LocatedRefusal as refusal:
                withheld.append(withheld_record(rid, sequence, refusal.reason, str(refusal), redner, page_ref, own_text, nested))
                record_status(statuses, rid, speech_kinds.WITHHELD_STATUS)
                continue
            nested_units.extend(rede_nested)
            diagnostics.extend(rede_diagnostics)
            if rid in procedural_reden:
                pass
            elif label.kind is None:
                speeches.append(unit)
            else:
                contributions.append(
                    {**unit, "kind": label.kind, "parent_rede_id": label.parent_rede_id, "sequence": sequence}
                )
            if rid not in procedural_reden and label.kind not in speech_kinds.REDE_STATUS:
                raise ReconciliationError(f"{sitting} {top.get('top-id')}: rede reconciliation: {rid} became {label.kind}, which has no status")
            record_status(statuses, rid, "procedural" if rid in procedural_reden else speech_kinds.REDE_STATUS[label.kind])
        unplaced_turn_count = 0
        if speech_kinds.FRAGESTUNDE in top_format.formats:
            counts: dict[str, int] = {}
            try:
                turns, unplaced_turn_count = speech_kinds.fragestunde_turns(top, asker_candidates, counts)
            except ValueError as exc:
                raise ValueError(f"{root.get('wahlperiode')}/{root.get('sitzung-nr')} {top.get('top-id')}: {exc}") from exc
            markers = len(top.findall("p[@klasse='redner']"))
            if counts["markers"] != markers:
                raise ReconciliationError(f"{sitting} {top.get('top-id')}: rede reconciliation: {markers} Fragestunde markers, {counts['markers']} turns")
            for flat_index, turn in enumerate(turns, start=1):
                text = speech_kinds.join_paragraphs(turn.paragraphs)
                if turn.redner is not None and turn.redner.get("listed_kind") not in (None, turn.kind):
                    raise reviewed_units.ReviewedUnitsError(
                        f"scripts/reviewed_units.json: {sitting} {top.get('top-id')}: the speaker printed as <name> "
                        f"{elem_text(turn.redner)!r} is listed as {turn.redner.get('listed_kind')}, but the Fragestunde reads a {turn.kind}")
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
                        "snippet": snippet_of(text),
                    }
                )

        for nested_unit in nested_units:
            nested_unit["sequence"] = max([len(redes), *(c["sequence"] for c in contributions)]) + 1
            contributions.append(nested_unit)
        sorted_pages = sorted(pages, key=page_sort_key)
        agenda_items.append(
            {
                "index": index,
                "top_id": top.attrib.get("top-id"),
                "top_source": top.get("top_source"),
                "heading": heading,
                "question_formats": sorted(top_format.formats),
                "xml_turn_diagnostics": diagnostics,
                "drucksachen": extract_drucksachen(top),
                "called_drucksachen": called_drucksachen(top, heading=heading, speech_count=len(speeches)),
                "ueberweisung": transfer_lines,
                "page_range": {
                    "start": sorted_pages[0] if sorted_pages else None,
                    "end": sorted_pages[-1] if sorted_pages else None,
                },
                "speeches": speeches,
                "contributions": contributions,
                "withheld": withheld,
                "unplaced_turn_count": unplaced_turn_count,
            }
        )

    unmatched = sorted((set(reviewed_entries) | set(unit_entries) | set(own_words_entries)) - matched_entries)
    if unmatched:
        raise reviewed_units.ReviewedUnitsError(
            f"scripts/reviewed_units.json: {sitting} lists {', '.join(unmatched)}, which names no Rede of a TOP in "
            "this sitting's XML (an annex Rede or a Fragestunde turn cannot be listed); the entry is stale or misapplied")
    stale_loose = sorted(set(loose_entries) - matched_loose, key=lambda rid: int(rid[1:]))
    if stale_loose:
        raise reviewed_units.ReviewedUnitsError(
            f"scripts/reviewed_units.json: {sitting} lists {', '.join(stale_loose)}, which names no speaker marker "
            "outside a <rede> in a TOP that is not a Fragestunde; the entry is stale or misapplied")
    if any(name_diagnostics.values()):
        raise reviewed_units.ReviewedUnitsError(
            f"scripts/reviewed_units.json: {sitting}: a name_procedural entry outside any TOP; it has nowhere to be recorded")
    mark_annex_texts(root, [entry for entry in sitting_entries if entry["kind"] == reviewed_units.ANNEX_REDE], split_parts)
    sitting_contributions = written_contributions(root, agenda_items, rid_pages, statuses)
    for ansprache in name_ansprachen:
        ansprache["sequence"] = len(sitting_contributions) + 1
        sitting_contributions.append(ansprache)
    reconcile_reden(sitting, inventory, statuses, split_parts)
    return {
        "xml_sha256": xml_source_sha256(xml_text),
        # The reviewed-list entries this parse applied, as a digest: the store
        # keeps it so an edit of the list forces a replay (R3).
        "reviewed_digest": reviewed_units.digest(list(sitting_entries)),
        "sitting_contributions": sitting_contributions,
        "vote_recommendations": parse_vote_recommendations(root),
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
        "first_edition": first_edition,
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
        # BT or BR: the two number Drucksachen independently, so the number
        # alone does not name one (persist keys a document by both).
        "herausgeber": fundstelle.get("herausgeber"),
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


def vote_counts_from_csv(value: str | None, missing: int | None = 0) -> dict[str, int | None]:
    """The four counts of a ``data-chart-values`` string; a count the string
    does not give becomes ``missing``. A vote's total passes ``None`` so a
    tally the source never printed is stored as NULL, not as an invented 0."""
    numbers: list[int | None] = [int(part) for part in re.findall(r"\d+", value or "")[:4]]
    numbers.extend([missing] * (4 - len(numbers)))
    return dict(zip(VOTE_KEYS, numbers))


def vote_total(counts: dict[str, int]) -> int:
    return sum(int(counts.get(key) or 0) for key in VOTE_KEYS)


def special_majority_procedure(title: str | None = None, procedure_context: Any = None) -> str | None:
    """Identify the procedure, not a mere reference to a constitutional article."""
    text = " ".join(str(value or "") for value in (title, procedure_context))
    patterns = {
        # A reference such as "Antrag zur Änderung des Grundgesetzes" is
        # not itself an amendment procedure. Require legislation/entwurf
        # evidence as well as the constitutional subject.
        "constitutional_amendment": r"(?:Änderung|Änderungen)\s+(?:des\s+)?Grundgesetz|Grundgesetzänderung|Verfassungsänderung",
        "confidence": r"Vertrauensfrage|Vertrauensantrag|Vertrauen\s+auszusprechen",
        "no_confidence": r"(?:konstruktiv\w*\s+)?Misstrauensvotum|Misstrauensantrag",
        "chancellor_election": r"Kanzlerwahl|Wahl\s+(?:des|eines|der|einer)\s+Bundeskanzler",
    }
    for kind, pattern in patterns.items():
        if not re.search(pattern, text, re.I):
            continue
        if kind == "constitutional_amendment" and not re.search(
            r"\b(?:Gesetz|Gesetzentwurf|Gesetzgebung|Änderungsgesetz|Entwurf|Grundgesetzänderung|Verfassungsänderung)\b", text, re.I
        ):
            continue
        return kind
    return None


def vote_result(
    *, official: str | None, yes_count: int, no_count: int, title: str | None = None,
    procedure_context: Any = None,
) -> tuple[str | None, str | None]:
    """Official proposition outcome wins; special procedures otherwise stay unknown."""
    if official in ("accepted", "rejected"):
        return official, "official"
    if special_majority_procedure(title, procedure_context):
        return None, None
    if yes_count == 0 and no_count == 0:
        return None, None
    return ("accepted" if yes_count > no_count else "rejected"), "derived"


# --- Protocol evidence for what a vote was about -------------------------------
#
# The chair announces a Beschlussempfehlung before it is voted on ("Der Ausschuss
# empfiehlt in seiner Beschlussempfehlung auf Drucksache N, den Antrag ... auf
# Drucksache A abzulehnen."). That sentence, not the roll-call title, says which
# way the recommendation points. Only the chair's paragraphs of the sitting
# proceedings count: a speech or a §31 declaration in the annex repeats the same
# words ("lehne den Antrag ... ab") without announcing anything.

_ABBREVIATION_RE = re.compile(
    r"\b(?:Dr|Nr|Prof|Abs|Art|Buchst|bzw|ca|Mio|Mrd|Ziff|Anl|Dipl|Ing|Rn|vgl|ggf|usw|etc|ff)\.|(?<=[ (])\d{1,2}\.(?=\s)"
)
_QUOTED_RE = re.compile(r"„[^“]*“")
_RECOMMENDS_RE = re.compile(r"\bempfiehl\w*", re.I)
_REJECT_PHRASE_RE = re.compile(r"\babzulehnen\b|\bAblehnung\s+(?:des|der|eines)\s+Antr", re.I)
_ACCEPT_PHRASE_RE = re.compile(r"\banzunehmen\b|\bAnnahme\s+(?:des|der|eines)\s+Antr", re.I)
_ANTRAG_WORD_RE = re.compile(r"\bAntr(?:ag|ages|ags|äge|ägen)\b")
_RECOMMENDATION_NEGATION_RE = re.compile(r"\b(?:nicht|kein\w*|ohne)\b", re.I)
_CLAUSE_SPLIT_RE = re.compile(r"[;,]?\s+(?:und|sowie)\s+(?=unter\s+Buchstabe)|;\s*")
# "Beschlussempfehlung (des Ausschusses ...) auf Drucksache N": the Drucksache of the
# recommendation itself, not one named after an Antrag or Gesetzentwurf.
_RECOMMENDATION_DOCUMENT_RE = re.compile(
    r"Beschlussempfehlung(?:(?!Antr|Gesetzentwurf|Entwurf|Ablehnung|Annahme|empfiehl|Drucksache).){0,120}?"
    r"\bauf\s+(?:der\s+|den\s+)?Drucksachen?\s+((?:[0-9]{1,2}/[0-9]{1,6}(?:\s*\(neu\))?(?:,|\s+und)?\s*)+)"
)
# DIP's note on a decision opens with the tally. Bounded digits: int() refuses a
# run of more than 4,300. ASCII digits only: int() also reads "٥٧٤", which \d matches.
_DIP_TALLY_RE = re.compile(r"\s*([0-9]{1,4})\s*:\s*([0-9]{1,4})\s*:\s*([0-9]{1,4})\b")
_DIP_REJECTING_RECOMMENDATION_RE = re.compile(r"Beschlussempfehlung\s+auf\s+Ablehnung", re.I)
DIP_DECISION_SOURCE = "bundestag-dip-beschlussfassung"
# What the chair's announcements say about one vote's recommendation; "none"
# when no announcement is attributable to it.
ProtocolDirection = Literal["reject", "accept", "conflict", "none"]


def _protocol_sentences(text: str) -> list[str]:
    """Sentences of one chair paragraph; periods inside quoted titles, after
    abbreviations and after an ordinal ("3. Ausschuss") do not end one."""
    protected = _QUOTED_RE.sub(lambda m: m.group(0).replace(".", "․"), text)
    protected = _ABBREVIATION_RE.sub(lambda m: m.group(0).replace(".", "․"), protected)
    return [part.replace("․", ".").strip() for part in re.split(r"(?<=[.!?])\s+", protected) if part.strip()]


def _document_numbers_in(text: str) -> list[str]:
    return list(dict.fromkeys(_DOCUMENT_NUMBER_RE.findall(text)))


def chair_paragraph_texts(root: ET.Element) -> list[tuple[str, str]]:
    """(top_id, text) of uninterrupted chair passages, joining adjacent
    paragraphs so an announcement can continue into the next one. Speeches,
    TOP boundaries, annexes and front matter never supply chair context."""
    paragraphs: list[tuple[str, str]] = []
    continued = False

    def chair_text(paragraph: ET.Element) -> str:
        copy = ET.fromstring(ET.tostring(paragraph))
        for note in copy.findall(".//fussnote"):
            note.clear()
        for mark in copy.findall(".//sup"):
            mark.text = None
        return elem_text(copy)

    def append_chair(paragraph: ET.Element, top_id: str) -> None:
        nonlocal continued
        text = chair_text(paragraph)
        if continued:
            paragraphs[-1] = (top_id, f"{paragraphs[-1][1]} {text}")
        else:
            paragraphs.append((top_id, text))
        continued = True

    for top in root.findall("./sitzungsverlauf/tagesordnungspunkt"):
        top_id = top.get("top-id") or ""
        continued = False
        for child in top:
            if child.tag == "p":
                if not (child.get("klasse") or "").startswith("T_"):
                    append_chair(child, top_id)
                else:
                    continued = False
            elif child.tag == "rede":
                chair = False
                for part in child:
                    if part.tag == "name":
                        chair = True
                    elif part.tag == "p" and part.get("klasse") == "redner":
                        chair = False
                        continued = False
                    elif chair and part.tag == "p":
                        append_chair(part, top_id)
                    elif part.tag == "p":
                        continued = False
            else:
                continued = False
    return paragraphs


def parse_vote_recommendations(root: ET.Element) -> list[dict[str, Any]]:
    """The chair's recommendation announcements about an Antrag, one record per
    clause: direction (reject, accept or conflict), the Antrag's Drucksachen,
    the Beschlussempfehlung's, and the clause as excerpt. Wording the parser
    does not understand yields nothing, never a guess."""
    records: list[dict[str, Any]] = []
    for paragraph_index, (top_id, text) in enumerate(chair_paragraph_texts(root)):
        context_numbers: list[str] = []
        for sentence in _protocol_sentences(text):
            named = _RECOMMENDATION_DOCUMENT_RE.search(sentence)
            if not _RECOMMENDS_RE.search(sentence):
                if named:
                    context_numbers = _document_numbers_in(named.group(1))
                continue
            # A later clause ("... und unter Buchstabe b den Antrag ... abzulehnen")
            # speaks of the Beschlussempfehlung its sentence named first.
            if named:
                context_numbers = _document_numbers_in(named.group(1))
            # The words of a quoted Antrag title ("Kein Heizungsgesetz ...") say nothing
            # about the recommendation: judge the clause with its quotes blanked out.
            masked = _QUOTED_RE.sub(lambda m: " " * len(m.group(0)), sentence)
            bounds = [0, *(pos for m in _CLAUSE_SPLIT_RE.finditer(masked) for pos in (m.start(), m.end())), len(sentence)]
            for start, end in zip(bounds[::2], bounds[1::2]):
                clause, plain = sentence[start:end], masked[start:end]
                rejects, accepts = _REJECT_PHRASE_RE.search(plain), _ACCEPT_PHRASE_RE.search(plain)
                antrag = _ANTRAG_WORD_RE.search(plain)
                if not (rejects or accepts) or antrag is None:
                    continue
                direction = "conflict" if (rejects and accepts) or _RECOMMENDATION_NEGATION_RE.search(plain) else (
                    "reject" if rejects else "accept"
                )
                recommendation_numbers = _document_numbers_in(clause[: antrag.start()]) or list(context_numbers)
                records.append({
                    "top_id": top_id,
                    "paragraph": paragraph_index,
                    "direction": direction,
                    "antrag_numbers": _document_numbers_in(clause[antrag.start():]),
                    "recommendation_numbers": recommendation_numbers,
                    "excerpt": clamp_text(clause, 300),
                })
    return records


def protocol_recommendation_evidence(
    vote: dict[str, Any], records: list[dict[str, Any]], sitting_votes: list[dict[str, Any]]
) -> tuple[ProtocolDirection, dict[str, Any] | None]:
    """What the chair's announcements say about this vote's recommendation.

    ("none", None): no announcement is attributable; fall back to other evidence.
    ("conflict", None): attributable evidence disagrees, fits several votes, or
    does not show that the Abstimmungsgegenstand is the Beschlussempfehlung;
    the direction stays unknown.
    ("reject" | "accept", record): every attributable announcement agrees."""
    numbers = set(vote.get("document_numbers") or [])
    if not numbers or not records:
        return "none", None

    def fits(record: dict[str, Any], candidate: dict[str, Any]) -> bool:
        candidate_numbers = set(candidate.get("document_numbers") or [])
        return bool(
            record["antrag_numbers"]
            and set(record["antrag_numbers"]) <= candidate_numbers
            and set(record["recommendation_numbers"]) <= candidate_numbers
        )

    matching = [record for record in records if fits(record, vote)]
    if not matching:
        return "none", None
    # One announcement fitting two votes of the sitting (a shared Drucksache) is
    # attributed to none of them, unless the listings' Abstimmungsgegenstand separates them.
    own_id = str(vote.get("id"))
    rivals = [other for other in sitting_votes if str(other.get("id")) != own_id and any(fits(r, other) for r in matching)]
    if any(derive.abstimmungsgegenstand(other) != "vorlage" for other in rivals):
        return "conflict", None
    # The Antrag's number alone fits a vote on the Antrag itself just as well: the
    # listing must open with the Beschlussempfehlung, or the chair must name a
    # Beschlussempfehlung Drucksache that is among the vote's.
    if derive.abstimmungsgegenstand(vote) != "beschlussempfehlung" and not any(record["recommendation_numbers"] for record in matching):
        return "conflict", None
    directions = {record["direction"] for record in matching}
    if directions != {"reject"} and directions != {"accept"}:
        return "conflict", None
    return directions.pop(), matching[0]


class DipDecision(NamedTuple):
    """One decision DIP records with a tally in a Vorgang position."""
    tally: tuple[int, int, int]  # (yes, no, abstain)
    numbers: frozenset[str]  # its Drucksachen
    note: str  # abstimm_ergebnis_bemerkung, clamped


def dip_vote_decisions(agenda_items: list[dict[str, Any]]) -> list[DipDecision]:
    """Every decision DIP records with a tally, in the sitting's Vorgang positions:
    ``abstimm_ergebnis_bemerkung`` reads "546:79:0 (Annahme der Beschlussempfehlung
    auf Ablehnung)". The same decision under several TOPs counts once. A malformed
    record (a position that is no object, a beschlussfassung that is no list, a
    decision without a tally) adds nothing."""
    decisions = {}
    for item in agenda_items:
        for position in ((item.get("api") or {}).get("raw") or {}).get("positions") or []:
            recorded = position.get("beschlussfassung") if isinstance(position, dict) else None
            for decision in recorded if isinstance(recorded, list) else []:
                note = decision.get("abstimm_ergebnis_bemerkung") if isinstance(decision, dict) else None
                tally = _DIP_TALLY_RE.match(note) if isinstance(note, str) else None
                if tally:
                    numbers = _DOCUMENT_NUMBER_RE.findall(str(decision.get("dokumentnummer") or ""))
                    entry = DipDecision(tuple(map(int, tally.groups())), frozenset(numbers), clamp_text(note, 300))
                    decisions[entry] = None
    return list(decisions)


def dip_decision_evidence(
    vote: dict[str, Any],
    decisions: list[DipDecision],
    sitting_votes: list[dict[str, Any]],
) -> str | None:
    """The excerpt of a DIP decision saying this ballot was on a Beschlussempfehlung
    to reject, else None. Its exact tally and a shared Drucksache prove which vote
    it is. A vote with no document numbers (638) rests on the tally alone, so that
    tally must occur once among the sitting's decisions and once among its votes.
    A count the vote does not give is unknown: it equals no decision's count, and a
    rival vote missing a count may still be the one the decision speaks of."""
    def tally_of(candidate: dict[str, Any]) -> tuple[int | None, ...]:
        counts = candidate.get("total") or {}
        return tuple(None if counts.get(key) in (None, "") else int(counts[key]) for key in ("yes", "no", "abstain"))

    def could_be(other: tuple[int | None, ...]) -> bool:
        return all(count is None or count == mine for count, mine in zip(other, tally))

    tally = tally_of(vote)
    numbers = set(vote.get("document_numbers") or [])
    fitting = [decision for decision in decisions if decision.tally == tally and any(tally)]
    if numbers:
        fitting = [decision for decision in fitting if decision.numbers & numbers]
    elif len(fitting) > 1 or sum(could_be(tally_of(other)) for other in sitting_votes) > 1:
        return None
    # A decision on the vote that does not say so leaves the direction open, as a chair's conflict does.
    if not fitting or not all(_DIP_REJECTING_RECOMMENDATION_RE.search(decision.note) for decision in fitting):
        return None
    chosen = min(fitting, key=lambda decision: (sorted(decision.numbers), decision.note))
    return f"Drucksache {', '.join(sorted(chosen.numbers))}: {chosen.note}" if chosen.numbers else chosen.note


def _text_recommendation_inversion(
    vote: dict[str, Any], documents: list[dict[str, Any]] | None = None
) -> tuple[Literal["reject", "blocked", "none"], str | None, str | None]:
    """("reject", source, text) when vote-specific wording or an unambiguous
    matched DIP recommendation says the Antrag is to be rejected; ("blocked", ...)
    when attributable text accepts or negates; else ("none", ...)."""
    reject = re.compile(r"Ablehnung\s+(?:eines|des|der)\s+(?:Antrag|Anträge)|(?:den|der|dem)\s+Antrag\b.{0,180}?(?:abzulehnen|ablehnen)", re.I)
    accept = re.compile(r"Annahme\s+(?:eines|des|der)\s+Antrag|(?:den|der|dem)\s+Antrag\b.{0,180}?anzunehmen", re.I)
    evidence = [("bundestag-roll-call", str(vote.get(field) or ""))
                for field in ("title", "description", "vote_heading")]
    numbers = set(vote.get("document_numbers") or [])
    for doc in documents or []:
        if doc.get("dokumentnummer") not in numbers:
            continue
        text = str(doc.get("titel") or "")
        # A recommendation naming another document cannot establish this vote.
        named = set(_DOCUMENT_NUMBER_RE.findall(text))
        if named - numbers:
            continue
        evidence.append(("bundestag-dip", text))
    rejection = None
    negation = re.compile(r"\b(?:nicht|kein\w*|ohne)\b", re.I)
    for source, text in evidence:
        # All attributable evidence must agree, including across fields and
        # documents. Negated wording never proves a recommendation to reject.
        if accept.search(text):
            return "blocked", None, None
        for match in reject.finditer(text):
            clause_start = max(text.rfind(mark, 0, match.start()) for mark in (".", ";", "\n")) + 1
            if negation.search(text[clause_start:match.end()]):
                return "blocked", None, None
            if rejection is None:
                rejection = (source, text)
    if rejection is not None:
        return "reject", rejection[0], rejection[1]
    return "none", None, None


def recommendation_inversion(
    vote: dict[str, Any],
    documents: list[dict[str, Any]] | None = None,
    protocol_evidence: tuple[ProtocolDirection, dict[str, Any] | None] | None = None,
    dip_decision: str | None = None,
) -> tuple[bool | None, str | None, str | None]:
    """Whether a Ja on this vote rejects an Antrag, with the evidence behind it.

    The chair's announcement in the sitting's proceedings leads. Without one,
    vote-specific wording, an unambiguous matched DIP recommendation or a DIP
    decision on the ballot counts, but never against attributable protocol
    evidence of any other reading."""
    direction, record = protocol_evidence or ("none", None)
    # A roll-call listing that opens with the Vorlage itself ("Gesetzentwurf der
    # ...", "Antrag der ...") is a vote on it: Ja is for the Vorlage even where a
    # title says "ablehnen".
    if derive.abstimmungsgegenstand(vote) == "vorlage":
        return None, None, None
    text_state, text_source, text_excerpt = _text_recommendation_inversion(vote, documents)
    if direction == "reject" and record is not None:
        if text_state == "blocked":
            return None, None, None
        return True, "bundestag-protocol", record["excerpt"]
    if direction in ("accept", "conflict"):
        return None, None, None
    if text_state == "reject":
        return True, text_source, text_excerpt
    if dip_decision is not None and text_state != "blocked":
        return True, DIP_DECISION_SOURCE, dip_decision
    return None, None, None


def _recorded_official_result(vote: dict[str, Any]) -> str | None:
    official = vote.get("official_result")
    if official is None and vote.get("result_source") == "official":
        official = vote.get("result_raw")
    return official


def interpret_vote(
    vote: dict[str, Any],
    documents: list[dict[str, Any]] | None = None,
    procedure_context: Any = None,
    protocol_evidence: tuple[ProtocolDirection, dict[str, Any] | None] | None = None,
    dip_decision: str | None = None,
) -> None:
    inverted, source, excerpt = recommendation_inversion(vote, documents, protocol_evidence, dip_decision)
    vote.update(inverted=inverted, inversion_source=source, inversion_excerpt=excerpt)
    vote["procedure_type"] = special_majority_procedure(vote.get("title"), procedure_context)
    official = _recorded_official_result(vote)
    # Preserve the official outcome and its scope across reinterpretation.
    # Consumers already distinguish application outcomes from recommendations.
    counts = vote.get("total") or {}
    vote["result_raw"], vote["result_source"] = vote_result(
        official=official, yes_count=int(counts.get("yes") or 0), no_count=int(counts.get("no") or 0),
        title=vote.get("title"), procedure_context=procedure_context,
    )
    if vote["result_source"] != "official":
        vote["result_scope"] = "proposition"


def _read_contradicted_official_result(vote: dict[str, Any], dip_decision: str | None = None) -> None:
    """The ballot was on a Beschlussempfehlung to reject, so a Ja majority cannot
    have accepted the Antrag: where a page's box says so (vote 990,
    docs/source-errors.md E6), its word is the ballot's, as the page's own Beschluss
    list and the protocol have it. Nothing proves such a mismatch for a Nein
    majority: the Antrag can fall or stand in a vote of its own. Runs once the
    sitting's evidence is in, since a title alone can read as a rejection the
    chair then refutes. Only the chair's announcement or DIP's decision on the
    ballot says what the ballot was on: an inversion read only from a roll-call or
    Drucksache title leaves the page's word about the Antrag. A title outranks DIP
    as the recorded ``inversion_source``, so a DIP decision bound to the ballot
    (``dip_decision``) counts here whichever source the inversion names."""
    counts = vote.get("total") or {}
    ballot_evidence = vote.get("inversion_source") in ("bundestag-protocol", DIP_DECISION_SOURCE) or dip_decision is not None
    if (vote.get("inverted") and ballot_evidence
            and vote.get("result_source") == "official" and vote.get("result_raw") == "accepted"
            and vote.get("result_scope") == "application" and int(counts.get("yes") or 0) > int(counts.get("no") or 0)):
        vote["result_scope"] = "proposition"


def position_drucksache_numbers(position: dict[str, Any], vorgang_numbers: Callable[[str], set[str]]) -> set[str]:
    """The Drucksachen a Vorgang position links to: those of its Vorgang and of
    every Vorgang beraten with it, as ``vorgang_numbers`` knows them (live from
    DIP while enriching, from the stored documents on replay)."""
    numbers: set[str] = set()
    if position.get("vorgang_id"):
        numbers |= vorgang_numbers(str(position["vorgang_id"]))
    for linked in position.get("mitberaten") or []:
        if linked.get("id"):
            numbers |= vorgang_numbers(str(linked["id"]))
    return numbers


def interpret_sitting_votes(
    agenda_items: list[dict[str, Any]],
    sitting_votes: list[dict[str, Any]],
    recommendations: list[dict[str, Any]] | None,
) -> None:
    """Interpret every vote of one sitting from its stored evidence, the same
    way online and on replay: the Drucksachen and Vorgang positions (with DIP's
    recorded decisions) the agenda items carry, plus the chair's recommendation
    announcements.

    ``agenda_items`` need ``api.linked_drucksachen``, ``api.raw.positions`` and
    ``votes``; ``sitting_votes`` are the votes no TOP claimed. A vote can appear
    several times (under several TOPs, among the matched votes), as separate
    dictionaries after a JSON reload: the evidence is gathered once per vote id
    from what all copies hold, and every copy is interpreted from it alike.

    With ``recommendations`` None (no protocol XML at hand) a protocol-sourced
    inversion already on a vote is kept rather than cleared. A present XML is
    the source and decides on its own, also when it announces nothing for a
    vote: the plan's "missing source evidence must not silently clear" means
    a missing XML (docs/plans/fix-vote-interpretation.md, step 4)."""
    documents = [doc for item in agenda_items for doc in (item.get("api") or {}).get("linked_drucksachen") or []]
    decisions = dip_vote_decisions(agenda_items)
    numbers_by_vorgang: dict[str, set[str]] = {}
    for doc in documents:
        if doc.get("vorgang_id") and doc.get("dokumentnummer"):
            numbers_by_vorgang.setdefault(str(doc["vorgang_id"]), set()).add(str(doc["dokumentnummer"]))

    def vorgang_numbers(vorgang_id: str) -> set[str]:
        return numbers_by_vorgang.get(vorgang_id, set())

    context_items: list[tuple[str, str, set[str]]] = []
    for item in agenda_items:
        for position in ((item.get("api") or {}).get("raw") or {}).get("positions") or []:
            linked_numbers = position_drucksache_numbers(position, vorgang_numbers)
            if position.get("titel"):
                context_items.append((str(position["titel"]), str(position.get("vorgangstyp") or ""), linked_numbers))
            for linked in position.get("mitberaten") or []:
                title = str(linked.get("titel") or "")
                linked_type = str(linked.get("vorgangstyp") or linked.get("typ") or "")
                if title or linked_type:
                    context_items.append((title, linked_type, vorgang_numbers(str(linked["id"])) if linked.get("id") else linked_numbers))

    occurrences: dict[str, list[dict[str, Any]]] = {}
    for vote in [*(vote for item in agenda_items for vote in item.get("votes") or []), *sitting_votes]:
        if vote.get("id") is not None:
            occurrences.setdefault(str(vote["id"]), []).append(vote)
    representatives = []
    for copies in occurrences.values():
        first = next((copy for copy in copies if derive.abstimmungsgegenstand(copy) is not None), copies[0])
        representative = dict(first)
        representative["document_numbers"] = list(dict.fromkeys(
            number for copy in copies for number in copy.get("document_numbers") or []
        ))
        for field in ("title", "description", "vote_heading"):
            representative[field] = "\n".join(dict.fromkeys(str(copy.get(field) or "") for copy in [first, *copies])).strip()
        representative["total"] = next((copy["total"] for copy in copies if copy.get("total")), {})
        representatives.append(representative)
    for copies, representative in zip(occurrences.values(), representatives):
        # An absent legacy key contributes no evidence; explicit null is a fresh
        # refusal. Conflicting copies lose the link rather than picking an order.
        debate_urls = {publication.vote_debate_url(copy.get("debate_url")) for copy in copies if "debate_url" in copy}
        if debate_urls:
            debate_url = next(iter(debate_urls)) if len(debate_urls) == 1 else None
            for copy in copies:
                copy["debate_url"] = debate_url
        numbers = set(representative["document_numbers"])
        vote_documents = [doc for doc in documents if doc.get("dokumentnummer") in numbers]
        context = [f"{title} {vorgang_type}" for title, vorgang_type, linked_numbers in context_items if numbers & linked_numbers]
        context.extend(f"{doc.get('titel') or ''} {doc.get('drucksachetyp') or ''}" for doc in vote_documents)
        official = next((o for o in map(_recorded_official_result, copies) if o is not None), None)
        scope = next((c.get("result_scope") for c in copies if _recorded_official_result(c) is not None and c.get("result_scope")), None)
        if recommendations is not None:
            evidence = protocol_recommendation_evidence(representative, recommendations, representatives)
        else:
            # No XML at hand: the announcement it once gave still leads, also over a title.
            kept = next((c.get("inversion_excerpt") for c in copies
                         if c.get("inverted") is True and c.get("inversion_source") == "bundestag-protocol"), None)
            evidence = ("reject", {"excerpt": kept}) if kept is not None else None
        subjects = {derive.abstimmungsgegenstand(copy) for copy in copies} - {None}
        if len(subjects) > 1:
            evidence = ("conflict", None)
        if official is not None:
            representative["official_result"] = official
            representative["result_scope"] = scope or "proposition"
        dip_decision = dip_decision_evidence(representative, decisions, representatives)
        interpret_vote(representative, documents=vote_documents, procedure_context=context, protocol_evidence=evidence,
                       dip_decision=dip_decision)
        _read_contradicted_official_result(representative, dip_decision)
        fields = ("inverted", "inversion_source", "inversion_excerpt", "procedure_type", "result_raw", "result_source", "result_scope")
        for vote in copies:
            vote.update({field: representative.get(field) for field in fields})
            if official is not None:
                vote["official_result"] = official


def interpret_report_votes(report: dict[str, Any], recommendations: list[dict[str, Any]] | None) -> None:
    """``interpret_sitting_votes`` on a stored report: its TOP votes and every
    other copy of a vote it holds (sitting-level votes, the matched list in
    ``api_records``). Restore sitting-level votes older reports kept only there."""
    records = report.get("api_records") or {}
    report.setdefault("sitting_votes", records.get("sitting_votes") or [])
    others = [*(report.get("sitting_votes") or []), *(records.get("sitting_votes") or []),
              *(records.get("matched_roll_call_votes") or [])]
    interpret_sitting_votes(report.get("agenda_items") or [], others, recommendations)


_BESCHLUSS_SECTION_RE = re.compile(
    r'<h2 class="bt-artikel__aside-section-title">Beschluss</h2>(.*?)</div>\s*<div class="bt-artikel__aside-section">',
    re.S,
)
_VOTE_OUTCOME_WORD_RE = re.compile(r"\b(angenommen|abgelehnt)\b")
_VOTE_NEGATION_RE = re.compile(r"\bnicht\b", re.I)
# Where the next vote's narration starts: its "Gesamt" or its own tally.
_NEXT_TALLY_RE = re.compile(r"Gesamt|Ja:\s*\d")
# A Drucksache number's shape on the vote pages and in the chair's
# announcements, e.g. "21/6561". Shared with parse_roll_call_list_page, which
# populates the document_numbers this function cross-checks against. Unlike
# derive.DOCUMENT_NUMBER_RE (Plenarprotokoll headings of every Wahlperiode) the
# Wahlperiode has two digits: bundestag.de lists namentliche Abstimmungen from
# WP 17 and structured XML starts at WP 18, so "2/3-Mehrheit" or "3/4" is never
# a Drucksache here and must neither join a vote's documents nor read as the
# "different document" that refuses an official outcome.
_DOCUMENT_NUMBER_RE = re.compile(r"\b[1-9][0-9]/[0-9]{1,6}\b")


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


# The tally as bundestag.de prints it, whichever vote it belongs to.
_ANY_TALLY_RE = re.compile(r"Ja:\s*(\d+)\s*Nein:\s*(\d+)\b")
_ROLL_CALL_START_RE = re.compile(r"namentliche\s+Abstimmung", re.I)
# The page prints the tally read out in the sitting; ours is the final one from
# the Plenarprotokoll. Measured on 217 votes (docs/research/bundestag-vote-pages.md):
# they differ by 1-3 per side.
_PROVISIONAL_TALLY_TOLERANCE = 3


class BeschlussTally(NamedTuple):
    """One tally of a Beschluss section with the text that belongs to it."""

    yes: int
    no: int
    announcement: str  # the block's lines above the tally: the roll call, naming the Vorlage
    outcome_text: str  # what follows the tally, up to the next vote


def _beschluss_tallies(section_html: str) -> list[BeschlussTally]:
    """Every tally of a Beschluss section, in page order (see ``_official_vote_text``)."""
    tallies: list[BeschlussTally] = []
    paragraphs = _beschluss_paragraphs(section_html)
    for paragraph_index, lines in enumerate(paragraphs):
        for index, line in enumerate(lines):
            for match in _ANY_TALLY_RE.finditer(line):
                rest = line[match.end() :]
                boundary = _NEXT_TALLY_RE.search(rest)
                # The text that belongs to this vote: the rest of its line and, only when
                # no other vote started on that line, the next line up to the next tally.
                text = rest[: boundary.start()] if boundary else rest
                if not boundary and index + 1 < len(lines):
                    following = lines[index + 1]
                    next_boundary = _NEXT_TALLY_RE.search(following)
                    text = f"{text} {following[: next_boundary.start()] if next_boundary else following}"
                start = index
                while start > 0 and lines[start - 1]:
                    start -= 1
                announcement = " ".join([*lines[start:index], line[: match.start()]])
                if roll_call := list(_ROLL_CALL_START_RE.finditer(announcement)):
                    announcement = announcement[roll_call[-1].start() :]
                if not boundary and not any(lines[index + 1 :]) and paragraph_index + 1 < len(paragraphs):
                    if trailing := _trailing_outcome(paragraphs[paragraph_index + 1], announcement):
                        text = f"{text} {trailing}"
                tallies.append(BeschlussTally(int(match.group(1)), int(match.group(2)), announcement, text))
    return tallies


def _trailing_outcome(lines: list[str], announcement: str) -> str:
    """The outcome a live page sets in the paragraph after the tally list (vote
    996: a <ul> ending in the tally, then "<p><br/>Antrag 21/4466 abgelehnt</p>"):
    its first block of lines, only when it names documents of this very block
    and starts no other vote; else ""."""
    upcoming: list[str] = []
    for line in lines:
        if upcoming and not line:
            break
        if line:
            upcoming.append(line)
    text = " ".join(upcoming)
    named = set(_DOCUMENT_NUMBER_RE.findall(text))
    if named and named <= set(_DOCUMENT_NUMBER_RE.findall(announcement)) and not _NEXT_TALLY_RE.search(text):
        return text
    return ""


def _official_vote_text(
    detail_html: str, yes_count: int, no_count: int, document_numbers: list[str] | None = None
) -> str | None:
    """bundestag.de states a vote's result only as prose in the page's
    "Beschluss" section, never as a machine-readable field, and one page's
    Beschluss text can narrate several related votes (a Gesetzentwurf, then its
    Entschließungsantrag). The text of this vote's own block is found by
    its Drucksache number: the block's roll-call announcement names the
    Vorlage voted on, and a block naming only this vote's documents, uniquely,
    is this vote's even where its printed tally is the provisional one read
    out in the sitting (1-3 off ours per side).

    Without a unique document match the vote's own Ja/Nein counts are the only
    way to find its sentence, and they must match exactly and once.

    The outcome must follow the tally directly: on the same
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
    tallies = _beschluss_tallies(section_match.group(1))
    own = set(document_numbers or [])
    if own:
        # An exact tally cannot override a different document on the current roll-call announcement.
        tallies = [
            tally for tally in tallies
            if not (
                _ROLL_CALL_START_RE.search(tally.announcement)
                and (announced := set(_DOCUMENT_NUMBER_RE.findall(tally.announcement)))
                and not announced & own
            )
        ]
        # A block counts as this vote's by its documents: it names some of them
        # and none besides. One shared Drucksache, or several parts of one
        # recommendation, name the same documents in several blocks: not unique.
        identified = [
            tally for tally in tallies
            if (named := set(_DOCUMENT_NUMBER_RE.findall(f"{tally.announcement} {tally.outcome_text}"))) and named <= own
        ]
        if len(identified) == 1:
            (tally,) = identified
            if abs(tally.yes - yes_count) <= _PROVISIONAL_TALLY_TOLERANCE and abs(tally.no - no_count) <= _PROVISIONAL_TALLY_TOLERANCE:
                return tally.outcome_text
        elif len(identified) > 1:
            tallies = identified
    # Two votes in one section with identical tallies would be indistinguishable:
    # only a unique match is confident enough to call official.
    hits = [tally for tally in tallies if (tally.yes, tally.no) == (yes_count, no_count)]
    if len(hits) != 1:
        return None
    return hits[0].outcome_text


def official_vote_result(
    detail_html: str, yes_count: int, no_count: int, document_numbers: list[str] | None = None
) -> tuple[str | None, str]:
    """(outcome, scope) from the one Beschluss block of this vote. The outcome
    is "accepted", "rejected" or None (derive instead); the scope is
    "application" when the block names the Antrag itself as accepted or rejected
    and "proposition" when it speaks of the Beschlussempfehlung or a Vorlage."""
    text = _official_vote_text(detail_html, yes_count, no_count, document_numbers)
    if text is None:
        return None, "proposition"
    words = set(_VOTE_OUTCOME_WORD_RE.findall(text))
    # The negation check spans both lines: "ist nicht<br/>angenommen".
    if len(words) != 1 or _VOTE_NEGATION_RE.search(text):
        return None, "proposition"
    # Refuse only on a proven mismatch (the text names a specific OTHER
    # document): a genuine outcome sentence often names no number at all, so
    # absence of our own number is not itself suspicious.
    named_numbers = set(_DOCUMENT_NUMBER_RE.findall(text))
    if document_numbers and named_numbers and not named_numbers & set(document_numbers):
        return None, "proposition"
    outcome = "accepted" if words == {"angenommen"} else "rejected"
    scope = "application" if re.search(r"\bAntrag\b", text, re.I) and not re.search(r"Beschlussempfehlung", text, re.I) else "proposition"
    return outcome, scope


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
                "total": vote_counts_from_csv(counts_match.group(1), missing=None) if counts_match else {},
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
            # An MP without a biography links back to the Abstimmung: no profile.
            profile_url = derive.person_profile_url(href if href.startswith("http") else f"{BT_BASE_URL}{href}")
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


class _VoteDebateParser(HTMLParser):
    """Only associations and links inside the vote's own Debatte panel."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[tuple[str, bool]] = []
        self.video_ids: set[str] = set()
        self.associations: set[tuple[str, str]] = set()
        self.links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id") or ""
        tab = re.fullmatch(r"tab_debatte_([0-9]+)", element_id)
        if (tag == "a" and tab and attributes.get("role") == "tab"
                and attributes.get("href") == "#debatte" and attributes.get("aria-controls") == "debatte"):
            self.video_ids.add(tab[1])
        inside = bool(self.stack and self.stack[-1][1]) or (
            element_id == "debatte" and attributes.get("role") == "tabpanel"
        )
        if inside:
            association = re.fullmatch(r"showItContainer_([0-9]+)_([0-9]+)", element_id)
            if association:
                self.associations.add((association[1], association[2]))
            if tag == "a" and attributes.get("href"):
                self.links.add(attributes["href"])
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append((tag, inside))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)


def parse_vote_debate_url(html_text: str, detail_url: str) -> str | None:
    parser = _VoteDebateParser()
    parser.feed(html_text)
    article_ids = {article for article, _ in parser.associations}
    if len(article_ids) != 1 or not parser.associations or any(
        video not in parser.video_ids for _, video in parser.associations
    ):
        return None
    article_id = next(iter(article_ids))
    explicit = set()
    for href in parser.links:
        try:
            url = publication.vote_debate_url(urllib.parse.urljoin(detail_url, href), article_id)
        except ValueError:
            continue
        if url:
            explicit.add(url)
    if len(explicit) == 1:
        return next(iter(explicit))
    # The ID route redirects to the canonical article (verified on 906 and 1005).
    return publication.vote_debate_url(f"{BT_BASE_URL}/dokumente/textarchiv/{article_id}", article_id)


def fetch_roll_call_vote_detail(vote: dict[str, Any]) -> dict[str, Any]:
    vote_id = str(vote["id"])
    detail_html = fetch_html(roll_call_vote_url(vote_id))
    member_html = fetch_html(f"{BT_BASE_URL}/apps/na/namensliste.form?id={urllib.parse.quote(vote_id)}&ajax=true")
    enriched_vote = dict(vote)
    enriched_vote["debate_url"] = parse_vote_debate_url(detail_html, roll_call_vote_url(vote_id))
    heading = re.search(r"<h1\b[^>]*>(.*?)</h1>", detail_html, re.S | re.I)
    if heading:
        enriched_vote["vote_heading"] = strip_tags(heading.group(1))
    enriched_vote["fractions"] = parse_fraction_votes(detail_html)
    enriched_vote["members"] = parse_member_votes(member_html)

    total = vote.get("total") or {}
    yes_count = int(total.get("yes") or 0)
    no_count = int(total.get("no") or 0)
    official, scope = official_vote_result(detail_html, yes_count, no_count, vote.get("document_numbers"))
    enriched_vote["official_result"] = official
    enriched_vote["result_scope"] = scope
    result_raw, result_source = vote_result(
        official=official, yes_count=yes_count, no_count=no_count, title=vote.get("title")
    )
    enriched_vote["result_raw"] = result_raw
    enriched_vote["result_source"] = result_source
    interpret_vote(enriched_vote)

    # The XLSX link is optional provenance from a second page: a failed fetch
    # leaves it unknown rather than discarding the fractions/members/result
    # already fetched for this vote.
    xlsx_matches = roll_call_xlsx_matches(vote.get("date"), vote.get("title"), namenslisten_entries())
    enriched_vote["xlsx_url"] = next(iter(xlsx_matches)) if len(xlsx_matches) == 1 else None
    # A successful fetch that found two files for this vote is a refusal, not
    # missing data: carry_forward_vote_provenance must not restore an old link.
    enriched_vote["xlsx_ambiguous"] = len(xlsx_matches) > 1
    return enriched_vote


def _days_since(day: str) -> int | None:
    """Whole days from an ISO date to today (UTC); None for a date that does not exist."""
    try:
        return (datetime.now(timezone.utc).date() - date.fromisoformat(day)).days
    except ValueError:
        return None


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
    """Every key of a report's agenda item that comes from the parsed XML alone
    (all but ``index``, which pairs the item with its XML, and the DIP-derived
    ``api`` and ``votes``): heading, page range, Drucksachen, Reden
    (``xml_speakers``) and Beiträge (``xml_contributions``). Used when a report is
    built and when a cached one is re-parsed from its cached XML, so the two
    cannot disagree."""
    return {
        **({"top_source": top["top_source"]} if top.get("top_source") else {}),
        "top_id": top["top_id"],
        "heading": top["heading"],
        "page_range": top["page_range"],
        "xml_drucksachen": top["drucksachen"],
        # The numbers the chair names in a section without heading and Rede (vote_links step 2).
        "called_drucksachen": list(top["called_drucksachen"]),
        "question_formats": top["question_formats"],
        "xml_turn_diagnostics": [dict(d) for d in top.get("xml_turn_diagnostics", [])],
        "xml_speech_count": len(top["speeches"]),
        "xml_contributions": [dict(c) for c in top["contributions"]],
        # Reden the parser withheld (ADR 0005), outside every count.
        "xml_withheld": [dict(w) for w in top.get("withheld") or []],
        "xml_speakers": [
            {
                "rede_id": speech["rede_id"],
                "sequence": speech["sequence"],
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


def contribution_summary(agenda_items: list[dict[str, Any]], sitting_contributions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The ``validation_summary`` keys for Reden and Beiträge, over parsed
    agenda items."""
    contributions = [c for top in agenda_items for c in top["contributions"]] + (sitting_contributions or [])
    return {
        "speech_kinds_version": speech_kinds.VERSION,
        # What the vote-link rule reads from this parse (build_dip_pulse_site.stale_causes, "votes").
        "vote_inputs_version": vote_links.INPUTS_VERSION,
        "xml_speech_count": sum(len(top["speeches"]) for top in agenda_items),
        "xml_contribution_counts": speech_kinds.kind_counts(contributions),
        # Withheld Reden (ADR 0005): outside every count above, own words only.
        "withheld_rede_count": sum(len(top.get("withheld") or []) for top in agenda_items),
        "withheld_word_count": sum(w["word_count"] for top in agenda_items for w in top.get("withheld") or []),
        "fragestunde_questions_without_person": sum(
            1
            for c in contributions
            if c["kind"] == speech_kinds.FRAGESTUNDE_FRAGE
            and c["rede_id"] is None
            and not (c["speaker"] or {}).get("xml_redner_id")
        ),
        # Retained report field for compatibility; D4 rejects unresolved turns
        # before an accepted report can contain an unplaced turn.
        "fragestunde_unplaced_turns": sum(top.get("unplaced_turn_count", 0) for top in agenda_items),
    }


KIND_MISMATCH_WARNING = "Die XML zählt "


def kind_mismatch_warnings(mismatches: list[dict[str, Any]]) -> list[str]:
    def label(mismatch: dict[str, Any]) -> str:
        speech_kinds.validate_kind(mismatch["kind"])
        singular, plural = speech_kinds.KIND_LABELS[mismatch["kind"]]
        return singular if mismatch["xml"] == 1 else plural

    return [f"{KIND_MISMATCH_WARNING}{m['xml']} {label(m)}, DIP {m['dip']}." for m in mismatches]


def xml_sitting_mismatch(document_number: str, parsed_xml: dict[str, Any]) -> str | None:
    """Why the parsed XML is not the sitting ``document_number`` (WP/NR), or None.
    One comparison for every path that parses: the online build, --fetch-xml and
    the re-parse. The parse keys the reviewed list by the XML's own number and
    persist by ``dokumentnummer``, so only an equal pair may reach the store."""
    wahlperiode, _, sitzung = document_number.partition("/")
    xml_protocol = parsed_xml.get("xml_protocol") or {}
    found = (str(xml_protocol.get("wahlperiode") or ""), str(xml_protocol.get("sitzung_nr") or ""))
    if not document_number:
        return f"the DIP record has no dokumentnummer to check the XML of {found[0]}/{found[1]} against"
    if found != (wahlperiode, sitzung):
        return f"it is the XML of {found[0]}/{found[1]}, not of {document_number}"
    return None


def xml_root_sitting(root: ET.Element) -> dict[str, Any]:
    """The sitting a Plenarprotokoll root names, shaped like ``parsed_xml`` for
    ``xml_sitting_mismatch``, so a caller can check it before the parse."""
    return {"xml_protocol": {"wahlperiode": root.attrib.get("wahlperiode"),
                             "sitzung_nr": root.attrib.get("sitzung-nr")}}


def check_xml_belongs_to_report(
    report: dict[str, Any], parsed_xml: dict[str, Any], by_index: dict[Any, Any]
) -> None:
    """Raise ValueError unless the parsed XML is the protocol this report was built
    from: same Wahlperiode and Sitzung, at least one agenda item, and an XML item for
    every report item. A re-parse that stamps the marker over anything else would
    hide a report that still holds the old rule."""
    cached_sha = (report.get("protocol") or {}).get("xml_sha256")
    if cached_sha and cached_sha != parsed_xml.get("xml_sha256"):
        raise ValueError("cached report/XML SHA-256 mismatch; reacquire the sitting report")
    number = str((report.get("protocol") or {}).get("dokumentnummer") or "")
    mismatch = xml_sitting_mismatch(number, parsed_xml) if number else None
    if mismatch:
        raise ValueError(mismatch)
    if not parsed_xml["agenda_items"]:
        raise ValueError("it holds no agenda items (not a Plenarprotokoll?)")
    # A cached report may hold its index as text ("3"); the XML numbers items as ints.
    xml_indexes = {source_index(index) for index in by_index}
    missing = [
        str(item.get("index"))
        for item in report.get("agenda_items") or []
        if source_index(item.get("index")) not in xml_indexes
    ]
    if missing:
        raise ValueError(f"it has no agenda item {', '.join(missing)} that the report holds")


def replay_top_map(report: dict[str, Any], parsed_xml: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Prove one-to-one source association before changing enrichment fields."""
    old = report.get("agenda_items") or []
    # A TOP adopted since this report was built (adopt_reden_outside_tops) has no item
    # in it yet: reparse_report_xml adds it. Any other change to the set still refuses.
    adopted = {clean_text(item.get("top_id") or "") for item in old if item.get("top_source")}
    new = [top for top in parsed_xml["agenda_items"]
           if not top.get("top_source") or clean_text(top["top_id"]) in adopted]
    if len(old) != len(new):
        raise ValueError("agenda item set changed; reacquire the sitting report")
    remaining = list(new)
    result = {}
    for old_index, item in enumerate(old):
        top_id = clean_text(item.get("top_id") or "")
        candidates = [t for t in remaining if clean_text(t.get("top_id") or "") == top_id]
        if len(candidates) > 1 or not top_id:
            same_heading = [t for t in candidates if clean_text(t.get("heading") or "") == clean_text(item.get("heading") or "")]
            if len(same_heading) == 1:
                candidates = same_heading
            else:
                ids = {u.get("rede_id") for key in ("xml_speakers", "xml_contributions") for u in item.get(key) or [] if u.get("rede_id")}
                supported = [t for t in candidates if ids & {u.get("rede_id") for key in ("speeches", "contributions") for u in t[key] if u.get("rede_id")}]
                candidates = supported
                if not candidates:
                    # Repeated procedural TOPs may have no rede IDs (21/2).
                    # Distinguish them by their neighboring source identities;
                    # source index by itself is never sufficient evidence.
                    def neighborhood(items, position):
                        return tuple(clean_text(items[i].get("top_id") or "") if 0 <= i < len(items) else None
                                     for i in (position - 1, position + 1))
                    context = neighborhood(old, old_index)
                    candidates = [t for t in same_heading if neighborhood(new, new.index(t)) == context]
        if len(candidates) != 1:
            raise ValueError(f"ambiguous or missing source TOP {top_id!r} ({item.get('heading')!r}); reacquire the sitting report")
        target = candidates[0]
        result[item["index"]] = target
        remaining.remove(target)
    if remaining:
        raise ValueError("unmatched source TOPs; reacquire the sitting report")
    return result


def no_api_fields() -> dict[str, Any]:
    """The ``api`` of an agenda item that matched nothing in DIP."""
    return {"positions": [], "activities_count": 0, "activities": [], "activities_first": [],
            "linked_drucksachen": [], "raw": {"positions": [], "activities": []}}


def reparse_report_xml(report: dict[str, Any], parsed_xml: dict[str, Any]) -> None:
    """Replace what a cached report holds of the XML-derived fields (heading,
    Reden, Beiträge; see ``xml_top_fields``) with what the current parser reads
    from the sitting's XML, leaving every DIP-derived field
    alone. Agenda items pair by validated source TOP identity, including repeated
    TOP context; the existing report index remains its stable enrichment key.

    An AI summary cites Reden of the old parse. One whose source no longer matches
    the re-read Reden (a cited turn is now a Beitrag) is dropped: it would quote
    that turn as evidence for a Rede that has no anchor any more."""
    by_index = {top["index"]: top for top in parsed_xml["agenda_items"]}
    check_xml_belongs_to_report(report, parsed_xml, by_index)
    by_index = replay_top_map(report, parsed_xml)
    protocol = report.setdefault("protocol", {})
    protocol["xml_sha256"] = parsed_xml.get("xml_sha256")
    protocol["reviewed_digest"] = parsed_xml.get("reviewed_digest")
    protocol["xml_header"] = parsed_xml["xml_protocol"]
    dropped = 0
    for item in report.get("agenda_items") or []:
        top = by_index.get(item.get("index"))
        if top is not None:
            item.update(xml_top_fields(top))
            summary = item.get("llm_summary")
            if summary and (
                not isinstance(summary, dict)
                or summary.get("source_fingerprint")
                != summary_source_fingerprint(
                    {"top_id": item.get("top_id"), "heading": item.get("heading"), "speeches": item["xml_speakers"]}
                )
            ):
                del item["llm_summary"]
                dropped += 1
    if len(by_index) != len(parsed_xml["agenda_items"]):
        # Newly adopted TOPs: the sitting's order and numbering a fresh build gives.
        # Their DIP fields stay empty until the sitting is acquired again.
        items = {id(by_index[item["index"]]): item for item in report["agenda_items"]}
        report["agenda_items"] = [
            items.get(id(top)) or {**xml_top_fields(top), "api": no_api_fields(), "votes": []}
            for top in parsed_xml["agenda_items"]
        ]
        for item, top in zip(report["agenda_items"], parsed_xml["agenda_items"]):
            item["index"] = top["index"]
        report.setdefault("validation_summary", {})["xml_top_count"] = len(parsed_xml["agenda_items"])
    generation = report.get("summary_generation")
    if dropped and isinstance(generation, dict) and "available_top_count" in generation:
        generation["available_top_count"] = sum(1 for item in report.get("agenda_items") or [] if item.get("llm_summary"))
    report["xml_contributions"] = parsed_xml.get("sitting_contributions", [])
    summary = report.setdefault("validation_summary", {})
    summary.update(contribution_summary(parsed_xml["agenda_items"], parsed_xml.get("sitting_contributions")))
    mismatches = speech_kinds.dip_mismatches(
        summary["xml_contribution_counts"], (report.get("api_records") or {}).get("aktivitaeten") or []
    )
    summary["contribution_dip_mismatches"] = mismatches
    summary.update(protocol_cut.cut_summary(parsed_xml, (report.get("api_records") or {}).get("aktivitaeten")))
    report["warnings"] = [
        warning for warning in report.get("warnings") or [] if not warning.startswith(KIND_MISMATCH_WARNING)
    ] + kind_mismatch_warnings(mismatches)


def write_text_atomic(path: Path, text: str) -> None:
    """A crash mid-write must never leave a truncated file where a cached report,
    the catalog or a cached XML used to be."""
    temp = path.with_name(f".{path.name}.tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


#: Consecutive failed /person lookups after which a sitting stops asking.
PERSON_FAILURE_LIMIT = 3


def enrich_with_api(
    client: ApiClient,
    protocol: dict[str, Any],
    parsed_xml: dict[str, Any],
    person_limit: int,
    vote_scan_pages: int = 30,
    roll_call_list_id: str | None = None,
    progress: Callable[[str], None] | None = None,
    roll_call_page_cache: dict[str, str] | None = None,
    person_cache: dict[str, dict[str, Any]] | None = None,
    vorgang_drucksachen_cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """``person_cache`` maps a DIP person id to its /person record for the whole
    build, so a person seen in an earlier sitting costs no request (D5). Only
    successful fetches are cached; a failed one is tried again next sitting.
    ``vorgang_drucksachen_cache`` maps a Vorgang id to its Drucksache positions
    (``compact_drucksache_position``, all the derivation reads of a Vorgang) and
    the Wahlperiode of the sitting that fetched them, so a Vorgang met again
    costs no request (two per Vorgang otherwise)."""
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

    linked_drucksachen_by_vorgang: dict[str, dict[str, Any]] = (
        vorgang_drucksachen_cache if vorgang_drucksachen_cache is not None else {}
    )

    def linked_drucksachen_for_vorgang(vorgang_id: str) -> list[dict[str, Any]]:
        if vorgang_id not in linked_drucksachen_by_vorgang:
            # A list that fails part-way raises here, so nothing partial is cached.
            drucksache_positions = [
                compact_drucksache_position(position)
                for position in client.list_all("/vorgangsposition", {"f.vorgang": vorgang_id})
                if position.get("dokumentart") == "Drucksache"
            ]
            linked_drucksachen_by_vorgang[vorgang_id] = {
                "wahlperiode": protocol.get("wahlperiode"),
                "drucksachen": drucksache_positions,
            }
        return linked_drucksachen_by_vorgang[vorgang_id]["drucksachen"]

    def vorgang_drucksache_numbers(vorgang_id: str) -> set[str]:
        return {str(doc.get("dokumentnummer")) for doc in linked_drucksachen_for_vorgang(vorgang_id) if doc.get("dokumentnummer")}

    def position_matches_top(position: dict[str, Any], top: dict[str, Any]) -> bool:
        if not overlaps(top, position):
            return False
        xml_numbers = {
            str(doc.get("dokumentnummer"))
            for doc in derive.printed_drucksachen(top.get("drucksachen"))
            if doc.get("dokumentnummer")
        }
        if xml_numbers:
            return bool(xml_numbers & position_drucksache_numbers(position, vorgang_drucksache_numbers)) or vote_links.title_matches(
                top.get("heading"), position.get("titel")
            )
        return vote_links.title_matches(top.get("heading"), position.get("titel"))

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

        enriched_tops.append(
            {
                "index": top["index"],
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
                "votes": [],
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
    consecutive_failures = 0
    for person_index, person_id in enumerate(people_to_fetch, start=1):
        if person_cache is not None and person_id in person_cache:
            person_records.append(person_cache[person_id])
        elif consecutive_failures >= PERSON_FAILURE_LIMIT:
            # DIP stopped answering /person (a 2026-10-19 stall timed out every
            # lookup for an hour): each further try costs three timed-out
            # attempts, so the rest of this sitting's persons count as failed.
            person_fetch_errors.append({"person_id": person_id, "error": f"skipped after {PERSON_FAILURE_LIMIT} consecutive failures"})
        else:
            try:
                person = client.get_json(f"/person/{person_id}")
            except DipError as exc:
                person_fetch_errors.append({"person_id": person_id, "error": str(exc)})
                consecutive_failures += 1
            else:
                person_records.append(person)
                consecutive_failures = 0
                if person_cache is not None:
                    person_cache[person_id] = person
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
    # Which TOPs each listed vote belongs to: one rule (vote_links), here and on
    # every replay, with the reviewed drops and flags of the listed votes
    # applied (a stale one stops the run; one whose vote this scan did not list
    # waits for the placement after cached votes are carried forward). A
    # candidate whose details then fail still counts as matched.
    candidate_by_id = {derive.vote_identity(candidate): candidate for candidate in roll_call_candidates}
    candidate_tops, _reviews = vote_links.apply_reviews(
        protocol.get("dokumentnummer"), enriched_tops, vote_links.top_links(enriched_tops, candidate_by_id.values()),
        listed_only=True)

    # Fetch every candidate independently: one unavailable detail must not
    # prevent later candidates in the sitting from being preserved.
    vote_fetch_errors: list[tuple[str, DipError]] = []
    for candidate in candidate_by_id.values():
        vote_id = str(candidate["id"])
        try:
            roll_call_cache[vote_id] = fetch_roll_call_vote_detail(candidate)
        except DipError as exc:
            vote_fetch_errors.append((vote_id, exc))
            if vote_fetch_error is None:
                vote_fetch_error = exc
            print(
                f"warning: roll-call vote {vote_id} details unavailable for {protocol.get('dokumentnummer') or protocol_id}: {exc}",
                file=sys.stderr,
            )
            continue
    for vote in roll_call_cache.values():
        vote["protocol_id"] = protocol_id
    # One rule run: the placement of the fetched votes is the candidates' links,
    # which also drive the warnings below (a fetched vote keeps its candidate's
    # title, description and numbers).
    placed = vote_links.attribute_votes({
        "agenda_items": enriched_tops,
        "api_records": {"roll_call_vote_candidates": roll_call_candidates,
                        "matched_roll_call_votes": list(roll_call_cache.values())},
    }, placed=candidate_tops)
    sitting_votes = placed.get("sitting_votes", [])

    attributed_vote_ids = {vote_id for vote_id, link in candidate_tops.items() if link.tops}
    unmatched_candidates = [candidate for vote_id, candidate in candidate_by_id.items() if vote_id not in attributed_vote_ids]
    # Interpret each vote once from the evidence attributable to its documents
    # and the chair's announcements. A shared vote may have several TOP links;
    # no later TOP can erase evidence. A replay runs the same step.
    interpret_sitting_votes(enriched_tops, sitting_votes, parsed_xml.get("vote_recommendations"))
    if progress and vote_scan_pages > 0:
        # Every fetched vote costs two requests (detail page, member list); the
        # Namenslisten page is one more per build, shared by all sittings.
        progress(
            f"Roll-call details: {len(roll_call_cache)} vote(s) fetched "
            f"({2 * len(roll_call_cache)} requests), {len(unmatched_candidates)} candidate(s) matched no TOP."
        )
    if roll_call_candidates and not attributed_vote_ids:
        warnings.append("Für dieses Sitzungsdatum wurden namentliche Abstimmungen gefunden, aber keine passte per Drucksachennummer oder Titel zu einem TOP.")
    elif unmatched_candidates:
        warnings.append(
            f"{len(unmatched_candidates)} von {len(roll_call_candidates)} namentlichen Abstimmungen dieses Sitzungsdatums "
            "passten per Drucksachennummer oder Titel zu keinem TOP."
        )
    if unmatched_candidates:
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

    vote_records = len(roll_call_cache)
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
        # of the list or passed the sitting's date, and no request failed.
        # TOP attribution is optional because sitting_votes preserves the vote.
        # or failed (none), with the reason named. Unmatched candidates are also
        # logged above and counted in api_totals.
        failure_reasons: list[str] = []
        if roll_call_fetch.selector_warning:
            failure_reasons.append("source_changed")
        if vote_fetch_error is not None:
            failure_reasons.append("source_unavailable")
        if roll_call_fetch.scan_end == "budget_exhausted":
            failure_reasons.append("scan_budget_exhausted")
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
                    if vote_records or failure_reasons == ["source_stale"]
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
            "roll_call_vote_detail_fetch_error_count": len(vote_fetch_errors),
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
            "sitting_votes": sitting_votes,
            "roll_call_vote_detail_fetch_errors": [
                {"vote_id": vote_id, "error": str(error)} for vote_id, error in vote_fetch_errors
            ],
            "unmatched_roll_call_vote_ids": [str(candidate["id"]) for candidate in unmatched_candidates],
        },
        "agenda_items": enriched_tops,
        "sitting_votes": sitting_votes,
        "warnings": warnings,
        "acquisition": {"votes": vote_facts.as_dict()},
    }


def cut_refusal(document_number: str, exc: protocol_cut.ProtocolCutError) -> DipError:
    """The source refusal of a sitting the cut rule cannot judge (E16)."""
    return DipError(f"{document_number}: protocol source rejected: {exc}; {protocol_cut.REFUSAL_FIX}",
                    source_rejected=True)


def build_report(
    args: argparse.Namespace,
    protocol: dict[str, Any] | None = None,
) -> dict[str, Any]:
    load_local_env()
    api_key = args.api_key or os.environ.get("DIP_API_KEY")
    if not api_key:
        raise DipError("Provide a DIP API key via --api-key or DIP_API_KEY.")

    breaker = getattr(args, "dip_breaker", None)
    if breaker is not None:
        breaker.check()  # after the run's stop, a sitting sends nothing, not even its XML request
    client = ApiClient(api_key=api_key, sleep_seconds=args.sleep, breaker=breaker)
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
    pacer = getattr(args, "xml_pacer", None)
    xml_text = pacer.fetch(xml_url) if isinstance(pacer, XmlPacer) else fetch_text(xml_url)
    xml_fetched_at = utc_now()
    # The caller decides whether to keep the report; only then does its XML become
    # the cache, so a cached XML never outlives the report it was parsed into.
    xml_sink = getattr(args, "xml_sink", None)
    if isinstance(xml_sink, dict):
        xml_sink["text"] = xml_text
    # Before the parse, which applies the reviewed list of the XML's own number and
    # can refuse a wrong-sitting file with ReviewedUnitsError, and before enrichment,
    # so no DIP request is spent on the wrong file (P3f).
    try:
        root_sitting = xml_root_sitting(ET.fromstring(xml_text))
    except ET.ParseError as exc:
        raise DipError(f"{document_number}: protocol source rejected: {exc}", source_rejected=True) from exc
    mismatch = xml_sitting_mismatch(str(protocol.get("dokumentnummer") or ""), root_sitting)
    if mismatch:
        raise DipError(f"{document_number}: protocol source rejected: {mismatch}", source_rejected=True)
    try:
        parsed_xml = parse_protocol_xml(xml_text)
    except derive.UnknownFraktionError as exc:
        raise DipError(f"{document_number}: protocol source rejected: {exc}; {derive.UNKNOWN_FRAKTION_FIX}",
                       source_rejected=True) from exc
    except UnlistedNameSpeakerError as exc:
        raise DipError(f"{document_number}: protocol source rejected: {exc}; {UNLISTED_NAME_SPEAKER_FIX}",
                       source_rejected=True) from exc
    except UnlistedLooseMarkerError as exc:
        raise DipError(f"{document_number}: protocol source rejected: {exc}; {UNLISTED_LOOSE_MARKER_FIX}",
                       source_rejected=True) from exc
    except UnlistedAnnexTextError as exc:
        raise DipError(f"{document_number}: protocol source rejected: {exc}; {UNLISTED_ANNEX_TEXT_FIX}",
                       source_rejected=True) from exc
    except protocol_cut.ProtocolCutError as exc:
        raise cut_refusal(document_number, exc) from exc
    except (ET.ParseError, ValueError) as exc:
        raise DipError(f"{document_number}: protocol source rejected: {exc}", source_rejected=True) from exc
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
        person_cache=getattr(args, "person_cache", None),
        vorgang_drucksachen_cache=getattr(args, "vorgang_drucksachen_cache", None),
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

    try:
        # Whether the XML is a first edition that stops partway (E16), by DIP's Aktivitäten.
        cut_keys = protocol_cut.cut_summary(parsed_xml, enrichment["api_records"].get("aktivitaeten"))
    except protocol_cut.ProtocolCutError as exc:
        raise cut_refusal(document_number, exc) from exc

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
            "xml_sha256": xml_source_sha256(xml_text),
            # What DIP listed for the file this fetch read, and when: a backfill leaves a cut sitting whose file
            # differs from that hash alone for a while (build_dip_pulse_site.replaced_cut_files). A replay keeps both.
            "xml_listed_hash": str(protocol.get("xml_hash") or "").strip().lower() or None,
            "xml_fetched_at": xml_fetched_at,
            "reviewed_digest": parsed_xml.get("reviewed_digest"),
        },
        "validation_summary": {
            "xml_top_count": len(parsed_xml["agenda_items"]),
            **contribution_summary(parsed_xml["agenda_items"], parsed_xml.get("sitting_contributions")),
            "xml_drucksache_count": xml_drucksache_count,
            "tops_with_xml_drucksachen": tops_with_xml_drucksachen,
            "tops_with_api_positions": tops_with_api_positions,
            "tops_with_api_linked_drucksachen": tops_with_api_drucksachen,
            **enrichment["api_totals"],
            **cut_keys,
        },
        "warnings": enrichment["warnings"],
        "sampled_people": enrichment["sampled_people"],
        "api_records": enrichment["api_records"],
        "agenda_items": agenda_items,
        # The votes no TOP claimed; derive and the store read them from here.
        "sitting_votes": enrichment["sitting_votes"],
        "xml_contributions": parsed_xml.get("sitting_contributions", []),
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
        reviewed_units.load()
        report = build_report(args)
    except reviewed_units.ReviewedUnitsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except DipError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
