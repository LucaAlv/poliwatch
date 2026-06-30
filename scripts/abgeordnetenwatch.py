#!/usr/bin/env python3
"""Resolve Bundestag speakers to abgeordnetenwatch.de politician profiles.

abgeordnetenwatch.de publishes member-of-parliament data under CC0 through a
public REST API (https://www.abgeordnetenwatch.de/api). Speakers in the
Bundestag Plenarprotokoll XML carry a Bundestagsverwaltung speaker id (the
``redner`` id, e.g. ``11005074``), which matches the
``ext_id_bundestagsverwaltung`` field on abgeordnetenwatch politicians. That id
is a precise join key, so most speakers resolve without any fuzzy matching.
Where the id is missing (e.g. recently sworn-in members), we fall back to a
name search and disambiguate by party.

Resolutions are cached on disk so repeat builds do not re-query the API, and the
resolver degrades gracefully: if abgeordnetenwatch is unreachable the build
continues, simply without profile links.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API_BASE = "https://www.abgeordnetenwatch.de/api/v2"
USER_AGENT = "bundestag-pulse/1.0 (+https://www.abgeordnetenwatch.de/api)"
# v2 adds biographical fields to cached profiles and a separate mandate (bio)
# cache, so the v1 cache is rebuilt on first run after the upgrade.
CACHE_VERSION = 2

# abgeordnetenwatch sits behind an nginx burst limiter (~12 quick requests before
# it answers HTTP 429). A steady minimum interval between requests keeps us under
# it; transient 429s are retried with exponential backoff.
DEFAULT_MIN_INTERVAL = 0.5
MAX_RETRIES = 4
BACKOFF_BASE_SECONDS = 2.0
MAX_BACKOFF_SECONDS = 30.0

# Give up entirely after this many consecutive *connection* failures so a real
# outage does not stall the build. HTTP 429 does not count — the API is up.
MAX_CONSECUTIVE_FAILURES = 8


class AbgeordnetenwatchError(Exception):
    """Raised for unexpected API responses (network errors are handled inline)."""


def _clean_label(value: Any) -> str:
    # abgeordnetenwatch party labels contain a soft hyphen (\xad) inside
    # "BÜNDNIS 90/DIE GRÜNEN"; strip it and collapse whitespace for display.
    text = "" if value is None else str(value)
    return re.sub(r"\s+", " ", text.replace("\xad", "")).strip()


def _party_tokens(label: Any) -> set[str]:
    """Reduce a party / fraction label to comparable tokens.

    Handles the CDU/CSU joint fraction, the soft hyphen in the Greens' label and
    spelling variants ("Die Linke" vs. "DIE LINKE").
    """
    text = _clean_label(label).lower()
    if not text:
        return set()
    tokens: set[str] = set()
    if "cdu" in text:
        tokens.add("cdu")
    if "csu" in text:
        tokens.add("csu")
    if "grün" in text or "bündnis" in text:
        tokens.add("gruene")
    if "linke" in text:
        tokens.add("linke")
    if "afd" in text:
        tokens.add("afd")
    if "spd" in text:
        tokens.add("spd")
    if "fdp" in text or "freie demokrat" in text:
        tokens.add("fdp")
    if "fraktionslos" in text or "parteilos" in text:
        tokens.add("fraktionslos")
    if not tokens:
        # Fall back to a normalised slug so unusual parties can still match.
        tokens.add(re.sub(r"[^a-z0-9]", "", text))
    return tokens


def _party_matches(fraktion: Any, party_label: Any) -> bool:
    a = _party_tokens(fraktion)
    b = _party_tokens(party_label)
    if not a or not b:
        return False
    return bool(a & b)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _strip_period_suffix(text: Any) -> str:
    # abgeordnetenwatch appends the legislative period in parentheses to mandate
    # labels, e.g. "232 - Regensburg (Bundestag 2025 - 2029)"; drop it.
    cleaned = _clean_label(text)
    return re.sub(r"\s*\([^)]*\)\s*$", "", cleaned).strip()


# Records whose "occupation" is just the mandate itself carry no useful Beruf.
_MANDATE_OCCUPATIONS = {
    "mdb",
    "mitglied des bundestages",
    "mitglied des deutschen bundestages",
}


def _profession(politician: dict[str, Any]) -> str | None:
    for value in (politician.get("occupation"), politician.get("education")):
        cleaned = _clean_label(value)
        if cleaned and cleaned.lower() not in _MANDATE_OCCUPATIONS:
            return cleaned
    return None


def _profile_from_politician(politician: dict[str, Any], match: str) -> dict[str, Any]:
    party = politician.get("party") or {}
    profession = _profession(politician)
    return {
        "id": politician.get("id"),
        "label": _clean_label(politician.get("label")),
        "url": politician.get("abgeordnetenwatch_url"),
        "party": _clean_label(party.get("label")) or None,
        "year_of_birth": _int_or_none(politician.get("year_of_birth")),
        "sex": _clean_label(politician.get("sex")) or None,
        "profession": profession,
        "residence": _clean_label(politician.get("residence")) or None,
        "match": match,
    }


def _bundesland_from_list_label(label: Any) -> str | None:
    # Electoral-list labels read like "Landesliste Bayern (Bundestag 2025 - 2029)"
    # or "Landesliste Nordrhein-Westfalen 2025"; recover just the state name.
    text = re.sub(r"\s+\d{4}$", "", _strip_period_suffix(label)).strip()
    if not text:
        return None
    match = re.search(r"Landesliste\s+(.+)$", text)
    return (match.group(1).strip() if match else None) or None


def _bio_from_mandates(mandates: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Pick the most recent mandate and extract Wahlkreis + Bundesland."""
    bio: dict[str, Any] = {"wahlkreis": None, "bundesland": None}
    if not mandates:
        return bio
    # The latest legislative period carries the highest parliament_period id.
    def period_id(mandate: dict[str, Any]) -> int:
        period = mandate.get("parliament_period") or {}
        return _int_or_none(period.get("id")) or _int_or_none(mandate.get("id")) or 0

    latest = max(mandates, key=period_id)
    electoral = latest.get("electoral_data") or {}
    constituency = electoral.get("constituency") or {}
    bio["wahlkreis"] = _strip_period_suffix(constituency.get("label")) or None
    bio["bundesland"] = _bundesland_from_list_label((electoral.get("electoral_list") or {}).get("label"))
    return bio


class AbgeordnetenwatchResolver:
    """Resolve speakers to abgeordnetenwatch profiles, with an on-disk cache."""

    def __init__(
        self,
        cache_path: Path | None = None,
        *,
        sleep_seconds: float | None = None,
        enabled: bool = True,
        timeout: int = 30,
    ) -> None:
        self.cache_path = Path(cache_path) if cache_path else None
        self.min_interval = DEFAULT_MIN_INTERVAL if sleep_seconds is None else sleep_seconds
        self.enabled = enabled
        self.timeout = timeout
        self._by_ext_id: dict[str, Any] = {}
        self._by_name: dict[str, Any] = {}
        self._by_bio: dict[str, Any] = {}
        self._dirty = False
        self._consecutive_failures = 0
        self._network_disabled = False
        self._call_failed = False
        self._last_request_ts = 0.0
        self.stats = {
            "ext_id": 0,
            "name": 0,
            "unresolved": 0,
            "api_calls": 0,
            "throttled": 0,
            "errors": 0,
        }
        self._load_cache()

    # -- cache ---------------------------------------------------------------

    def _load_cache(self) -> None:
        if not self.cache_path or not self.cache_path.exists():
            return
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
            return
        self._by_ext_id = dict(data.get("by_ext_id") or {})
        self._by_name = dict(data.get("by_name") or {})
        self._by_bio = dict(data.get("by_bio") or {})

    def save(self) -> None:
        if not self.cache_path or not self._dirty:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CACHE_VERSION,
            "by_ext_id": self._by_ext_id,
            "by_name": self._by_name,
            "by_bio": self._by_bio,
        }
        self.cache_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._dirty = False

    # -- API -----------------------------------------------------------------

    def _throttle(self) -> None:
        if self.min_interval > 0:
            wait = self._last_request_ts + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
        self._last_request_ts = time.monotonic()

    def _note_failure(self, *, connection: bool) -> None:
        self.stats["errors"] += 1
        self._call_failed = True
        if connection:
            self._consecutive_failures += 1
            if self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                self._network_disabled = True
        return None

    def _get(self, params: dict[str, Any]) -> list[dict[str, Any]] | None:
        """Search politicians; return the data list or None."""
        query = urllib.parse.urlencode({**params, "range_end": 50})
        return self._request(f"{API_BASE}/politicians?{query}")

    def _request(self, url: str) -> list[dict[str, Any]] | None:
        """Return the data list for a query, or None. Sets ``_call_failed`` when
        the request failed (vs. succeeding with an empty result), so callers can
        avoid caching transient failures as negative matches."""
        self._call_failed = False
        if self._network_disabled:
            self._call_failed = True
            return None
        for attempt in range(MAX_RETRIES + 1):
            self._throttle()
            req = urllib.request.Request(
                url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
            )
            self.stats["api_calls"] += 1
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as res:
                    payload = json.loads(res.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < MAX_RETRIES:
                    self.stats["throttled"] += 1
                    time.sleep(min(BACKOFF_BASE_SECONDS * (2 ** attempt), MAX_BACKOFF_SECONDS))
                    continue
                return self._note_failure(connection=False)
            except (urllib.error.URLError, json.JSONDecodeError, ValueError):
                return self._note_failure(connection=True)
            self._consecutive_failures = 0
            if not isinstance(payload, dict) or payload.get("meta", {}).get("status") != "ok":
                return None
            data = payload.get("data")
            return data if isinstance(data, list) else []
        return self._note_failure(connection=False)

    def _resolve_by_ext_id(self, ext_id: str) -> dict[str, Any] | None:
        data = self._get({"ext_id_bundestagsverwaltung": ext_id})
        if not data:
            return None
        return _profile_from_politician(data[0], "ext_id")

    def _resolve_by_name(
        self, first_name: str | None, last_name: str | None, fraktion: Any
    ) -> dict[str, Any] | None:
        if not last_name:
            return None
        params: dict[str, Any] = {"last_name": last_name}
        if first_name:
            params["first_name"] = first_name
        data = self._get(params)
        if not data:
            return None
        if len(data) == 1:
            return _profile_from_politician(data[0], "name")
        # Multiple candidates: only accept a unique party match to stay honest.
        matches = [p for p in data if _party_matches(fraktion, (p.get("party") or {}).get("label"))]
        if len(matches) == 1:
            return _profile_from_politician(matches[0], "name")
        return None

    # -- public --------------------------------------------------------------

    def resolve(
        self,
        *,
        ext_id: Any = None,
        first_name: str | None = None,
        last_name: str | None = None,
        fraktion: Any = None,
    ) -> dict[str, Any] | None:
        """Resolve a single speaker to a profile dict, or None.

        Negative results (no match found) are cached as ``None`` so they are not
        re-queried; transient network failures are *not* cached and may be
        retried on the next build.
        """
        if not self.enabled:
            return None

        ext_id = str(ext_id).strip() if ext_id else None
        if ext_id:
            if ext_id in self._by_ext_id:
                cached = self._by_ext_id[ext_id]
                # A positive hit wins; a cached negative falls through to the
                # name search below (some members lack an ext_id on abg.watch).
                if cached is not None:
                    return self._record_stat(cached)
            elif not self._network_disabled:
                profile = self._resolve_by_ext_id(ext_id)
                if profile is not None:
                    self._by_ext_id[ext_id] = profile
                    self._dirty = True
                    return self._record_stat(profile)
                # Only cache a negative when the API actually answered.
                if not self._call_failed:
                    self._by_ext_id[ext_id] = None
                    self._dirty = True

        last = (last_name or "").strip()
        if last:
            key = "|".join(
                [
                    (first_name or "").strip().casefold(),
                    last.casefold(),
                    "|".join(sorted(_party_tokens(fraktion))),
                ]
            )
            if key in self._by_name:
                return self._record_stat(self._by_name[key])
            if not self._network_disabled:
                profile = self._resolve_by_name(first_name, last, fraktion)
                # Only cache when the API answered (avoid poisoning the cache
                # with transient network failures).
                if profile is not None or not self._call_failed:
                    self._by_name[key] = profile
                    self._dirty = True
                return self._record_stat(profile)

        return self._record_stat(None)

    def _record_stat(self, profile: dict[str, Any] | None) -> dict[str, Any] | None:
        if profile is None:
            self.stats["unresolved"] += 1
        else:
            self.stats[profile.get("match", "name")] = self.stats.get(profile.get("match", "name"), 0) + 1
        return profile

    def fetch_bio(self, politician_id: Any) -> dict[str, Any] | None:
        """Resolve a politician's current Wahlkreis and Bundesland from their
        mandate record. Cached on disk; returns None when unavailable. These live
        on ``/candidacies-mandates`` rather than the base politician object."""
        if not self.enabled or not politician_id:
            return None
        key = str(politician_id)
        if key in self._by_bio:
            return self._by_bio[key]
        if self._network_disabled:
            return None
        url = f"{API_BASE}/candidacies-mandates?politician={urllib.parse.quote(key)}&type=mandate&range_end=20"
        data = self._request(url)
        if data is None:
            # Network failure — do not cache, retry on a later build.
            return None
        bio = _bio_from_mandates(data)
        self._by_bio[key] = bio
        self._dirty = True
        return bio


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Resolve a speaker to an abgeordnetenwatch profile.")
    parser.add_argument("--ext-id", help="Bundestagsverwaltung speaker id (redner id).")
    parser.add_argument("--first-name")
    parser.add_argument("--last-name")
    parser.add_argument("--fraktion")
    parser.add_argument("--cache", type=Path)
    args = parser.parse_args()

    resolver = AbgeordnetenwatchResolver(cache_path=args.cache)
    profile = resolver.resolve(
        ext_id=args.ext_id,
        first_name=args.first_name,
        last_name=args.last_name,
        fraktion=args.fraktion,
    )
    resolver.save()
    print(json.dumps(profile, ensure_ascii=False, indent=2))
    print(json.dumps(resolver.stats, ensure_ascii=False), file=__import__("sys").stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
