#!/usr/bin/env python3
"""Build a static Bundestag Pulse overview site for multiple sittings."""

# NOTE: the docstring above is short on purpose - parse_args() passes it to
# argparse as the --help description. The map of the build lives here instead.
#
# This is the top-level build script for the whole site. It fetches parliamentary
# data, persists it into SQLite, and writes every HTML file of the site into
# ``--output-dir`` (default ``.context/dip-pulse-site``). The site is fully static:
# the only code that runs in a visitor's browser are the small inline ``<script>``
# blocks that this file emits.
#
# Build pipeline -- see ``main()`` at the bottom of the file for the real sequence:
#
#   1. Resolve optional update-time enrichments. The published HTML always
#      contains the fixed public component set.
#   2. Fetch the plenary-protocol catalog from the DIP API -> ``fetch_protocols``.
#   3. For a subset of those sittings, build a full "dossier" (agenda items,
#      speeches, documents, roll-call votes, optional LLM summaries) by delegating
#      the heavy extraction work to ``validate_dip_protocol.build_report``
#      -> ``write_report_and_page``. Every dossier is written twice: as JSON under
#      ``data/`` and as an HTML page under ``protocols/``.
#   4. Rebuild the SQLite graph store from those dossiers
#      -> ``rebuild_database_from_entries`` (schema and writes live in
#      ``persist_dip_pulse_store``).
#   5. Read the store back to assemble the MP ("Abgeordnete") data
#      -> ``collect_abgeordnete``.
#   6. Export a distribution copy of the store, 16 CSVs and five executed SQL
#      recipes for the Daten page -> ``export_distribution_data``, writing
#      ``data/exports/datenstand.json`` and ``data/exports/g-<hash>/``.
#   7. Render every remaining page of the site -> ``render_site``.
#
# Which code writes which part of the website:
#
#   index.html           ``render_landing_page``     explanatory home page
#   puls.html            ``render_front_page``       "Aktueller Puls": week radar + Wochenvergleich
#   overview.html        ``render_overview``         dossier cards + catalog teaser
#   api-sitzungen.html   ``render_catalog_page``     searchable full DIP catalog
#   sources.html         ``render_sources_page``     sources and method transparency
#   database.html        ``render_database_page``    Daten: downloads, Datenstand, Rezepte, Schema
#   settings.html        ``render_settings_page``    0.5.x compatibility notice
#   protocols/*.html     ``render_dip_pulse_html``   per-sitting dossier (own module)
#   bills/index.html     ``render_bills_index``      "Gesetze verfolgen" list
#   bills/bill-*.html    ``render_bill_detail``      one legislative procedure
#   abgeordnete/index.html   ``render_abgeordnete_index``   MP roster with filters
#   abgeordnete/<id>.html    ``render_abgeordnete_detail``  one MP profile
#   data/*.json          raw reports, catalog, bills.json, abgeordnete.json,
#                        features.json
#   data/exports/        distribution SQLite + CSVs + datenstand.json manifest
#
# Every page is emitted as one big f-string containing its own ``<style>`` block,
# so a ``render_*`` function is self-contained: its Python code computes the
# numbers, and the f-string right below it is the literal page markup. Shared
# chrome (header, theme switch, AI disclosure runtime) comes from
# ``render_dip_pulse_html`` and is imported as ``pulse_html``.
#
# The site copy is German because the audience is German; code and comments are
# English.

from __future__ import annotations

if __name__ == "__main__":
    from python_version_guard import require_supported_python

    require_supported_python()

import argparse
import contextlib
import copy
import csv
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Sibling scripts, imported as plain modules (scripts/ is on sys.path when this
# file is run directly):
#   pulse_html  - shared HTML helpers + the per-sitting dossier page renderer
#   pulse_store - SQLite schema, upserts and report persistence
#   dip         - DIP API client and the protocol -> report extraction pipeline
#   aw          - abgeordnetenwatch.de profile lookup and caching
#   facts       - the Fakt der Woche metric registry, rule and storage engine
import render_dip_pulse_html as pulse_html
import persist_dip_pulse_store as pulse_store
import validate_dip_protocol as dip
import abgeordnetenwatch as aw
import publication_state as publication
import facts
# Public components are fixed product structure. EnrichmentSelection is the
# separate operator-controlled set of optional network acquisition jobs.
from features import (
    ENRICHMENT_REGISTRY,
    REGISTRY,
    EnrichmentSelection,
    FeatureError,
    Selection,
    publication_selection,
    resolve,
)
from features import loader as feature_loader


# Human-readable one-liners for every table in the SQLite store. Used only by the
# Daten page (database.html) to caption each schema row; a table that is missing
# here falls back to a generic sentence in render_daten_schema().
DATABASE_TABLE_DESCRIPTIONS = {
    "schema_migrations": "Interne Versionsmarke des SQLite-Schemas.",
    "parties": "Normalisierte Parteien und Rollen wie Regierung oder fraktionslos.",
    "mps": "Personen, die in Reden, DIP-Personendaten oder namentlichen Abstimmungen auftauchen.",
    "protocols": "Plenarprotokolle mit Dokumentnummer, Datum und offiziellen XML/PDF-Links.",
    "agenda_items": "Tagesordnungspunkte je Protokoll. Sie bilden die Themen-Grenze der aktuellen Pulse-Ansicht.",
    "proceedings": "DIP-Vorgänge, etwa Gesetzgebungsverfahren, die mit Tagesordnungspunkten verbunden werden.",
    "proceeding_positions": "DIP-Vorgangspositionen mit Dokument- und Seitenangaben aus der offiziellen API.",
    "documents": "Drucksachen und andere Dokumente, die aus XML, DIP oder Abstimmungen referenziert werden.",
    "agenda_item_documents": "Verknüpfung zwischen Tagesordnungspunkten und Dokumenten, inklusive Quelle xml/api.",
    "speeches": "Extrahierte Redebeiträge mit Redner, Seite, Textumfang, Snippet und optionalem Volltext.",
    "votes": "Namentliche Abstimmungen mit Summen und Bundestag-Detailseite.",
    "agenda_item_votes": "Zuordnung von namentlichen Abstimmungen zu Tagesordnungspunkten.",
    "vote_documents": "Drucksachen, die bei namentlichen Abstimmungen referenziert wurden.",
    "vote_fractions": "Fraktionssummen je namentlicher Abstimmung.",
    "vote_members": "Einzelne Stimmen von Abgeordneten je namentlicher Abstimmung.",
    "mp_canonical": "Bildet jede mps-Zeile auf die konsolidierte Person ab. Nur in der Verteilkopie.",
    "datenstand": "Herkunft dieser Verteilkopie: Tag, Exportformat, Lizenz, Schema- und Quell-Prüfsumme. Nur in der Verteilkopie.",
    "fact_metrics": "Registrierte Kennzahlen der Rubrik Fakt der Woche mit SQL, Richtung, Aggregation und Mindesthistorie.",
    "facts": "Wöchentliche Beobachtung je Kennzahl mit Wert, Perzentil, Baseline und Veröffentlichungsstatus.",
    "fact_sources": "Belege je Fakt: Rede, Abstimmung, Sitzung oder Drucksache, aus denen der Wert stammt.",
}

ENRICHMENT_IDS = frozenset({"votes", "aw-profiles", "mp-roster"})


# ---------------------------------------------------------------------------
# Document numbers, slugs and sort keys
#
# A Bundestag document number looks like "21/84" (Wahlperiode/running number).
# It is the primary human identifier for a sitting and gets turned into the
# file names used under data/ and protocols/.
# ---------------------------------------------------------------------------


# Turn "21/84" into "21-84" so it can be used inside a file name.
def slugify_document_number(document_number: str) -> str:
    value = document_number.strip().replace("/", "-")
    value = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value)
    return value.strip("-").lower()


# Defensive string coercion: DIP sometimes yields None or padded values, and
# document numbers are used as dict keys all over this file.
def normalized_document_number(document_number: Any) -> str:
    return str(document_number or "").strip()


# Sort protocols newest-first (used with reverse=True everywhere). Sitting date
# is the primary key; the protocol id only breaks ties for same-day sittings.
def protocol_sort_key(protocol: dict[str, Any]) -> tuple[str, str]:
    return (str(protocol.get("datum") or ""), str(protocol.get("id") or ""))


# Same ordering, but for a built dossier entry (the dict returned by
# write_report_files) rather than a bare protocol record.
def entry_sort_key(entry: dict[str, Any]) -> tuple[str, str]:
    return protocol_sort_key((entry.get("report") or {}).get("protocol") or {})


# Order Wahlperiode buckets numerically, lowest first. The bucket keys are
# strings, so a plain sort puts "9" above "21". The non-numeric fallback bucket
# ("unbekannt"/"unknown", used when a protocol carries no wahlperiode) sorts
# after every real period.
def period_sort_key(period: str) -> tuple[int, int, str]:
    if period.isdigit():
        return (0, int(period), "")
    return (1, 0, period)


# The official XML protocol URL. Its presence decides whether a sitting can get
# a dossier at all - the XML is the authoritative source for agenda items,
# speeches and speakers.
def protocol_xml_url(protocol: dict[str, Any]) -> str:
    fundstelle = protocol.get("fundstelle") or {}
    return str(fundstelle.get("xml_url") or "").strip()


# Human-readable label for log lines and warnings, e.g. "21/84 (ID 6122)".
def protocol_label(protocol: dict[str, Any]) -> str:
    document_number = normalized_document_number(protocol.get("dokumentnummer"))
    protocol_id = str(protocol.get("id") or "").strip()
    if document_number and protocol_id:
        return f"{document_number} (ID {protocol_id})"
    return document_number or protocol_id or "unbekanntes Protokoll"


# ---------------------------------------------------------------------------
# Fetching protocols and building dossiers
# ---------------------------------------------------------------------------


def build_dossiers_with_progress(
    protocols: list[dict[str, Any]],
    load_existing: Callable[[dict[str, Any]], dict[str, Any] | None],
    build_dossier: Callable[[dict[str, Any], dict[str, Any] | None], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build dossiers sequentially while emitting human-readable progress to stderr."""
    # Dossier building is the slow part of a build (XML download, DIP lookups,
    # roll-call scraping, optionally LLM calls), so each sitting gets a
    # numbered start/finish line on stderr. Failures print the elapsed time
    # before re-raising, which makes a hung or slow sitting easy to spot.
    total = len(protocols)
    if total == 0:
        print("[dossiers] No dossiers selected for processing.", file=sys.stderr, flush=True)
        return []

    overall_started = time.monotonic()
    print(f"[dossiers] Processing {total} dossier(s).", file=sys.stderr, flush=True)
    entries: list[dict[str, Any]] = []
    for index, protocol in enumerate(protocols, start=1):
        existing_report = load_existing(protocol)
        action = "Refreshing cached dossier" if existing_report is not None else "Downloading new dossier"
        label = f"BT-PlPr {protocol_label(protocol)}"
        protocol_date = str(protocol.get("datum") or "").strip()
        if protocol_date:
            label = f"{label} from {protocol_date}"

        started = time.monotonic()
        print(f"[dossiers] [{index}/{total}] {action}: {label}.", file=sys.stderr, flush=True)
        try:
            entry = build_dossier(protocol, existing_report)
        except dip.DipError as exc:
            elapsed = time.monotonic() - started
            protocol["dossier_failure_reasons"] = ["source_unavailable"]
            print(
                f"[dossiers] [{index}/{total}] Skipped unavailable {label} after {elapsed:.1f}s: {exc}",
                file=sys.stderr,
                flush=True,
            )
            continue
        except Exception:
            elapsed = time.monotonic() - started
            print(
                f"[dossiers] [{index}/{total}] Failed {label} after {elapsed:.1f}s.",
                file=sys.stderr,
                flush=True,
            )
            raise
        entries.append(entry)
        elapsed = time.monotonic() - started
        print(
            f"[dossiers] [{index}/{total}] Finished {label} in {elapsed:.1f}s.",
            file=sys.stderr,
            flush=True,
        )

    elapsed = time.monotonic() - overall_started
    print(
        f"[dossiers] Completed {len(entries)}/{total} dossier(s) in {elapsed:.1f}s.",
        file=sys.stderr,
        flush=True,
    )
    return entries


# Look up exactly one sitting by its document number, e.g. "21/84".
def fetch_protocol_by_document_number(client: dip.ApiClient, document_number: str) -> dict[str, Any]:
    documents = client.list_all(
        "/plenarprotokoll",
        {"f.zuordnung": "BT", "f.dokumentnummer": document_number},
    )
    if not documents:
        raise dip.DipError(f"No BT Plenarprotokoll found for {document_number}")
    return documents[0]


# Fetch the protocol catalog that the whole site is built from.
#
# Two modes:
#   * explicit --document-number values -> fetch just those sittings
#   * otherwise -> page through /plenarprotokoll until `limit` records are
#     collected (limit <= 0 means "every available BT protocol")
#
# The DIP API returns documents sorted by `datum` descending, so the first page
# already holds the newest sittings and a small --limit yields recent ones.
def fetch_protocols(
    client: dip.ApiClient,
    limit: int,
    document_numbers: list[str],
    wahlperiode: int | None = None,
) -> list[dict[str, Any]]:
    if document_numbers:
        # Explicit selection: fetch each requested number, then order newest first.
        protocols: list[dict[str, Any]] = []
        for document_number in document_numbers:
            protocols.append(fetch_protocol_by_document_number(client, document_number))
        return sorted(protocols, key=protocol_sort_key, reverse=True)

    # Catalog mode. Narrowing by Wahlperiode only makes sense for a limited
    # fetch; an unlimited fetch deliberately walks every period.
    protocols: list[dict[str, Any]] = []
    params: dict[str, Any] = {"f.zuordnung": "BT"}
    if limit > 0 and wahlperiode:
        params["f.wahlperiode"] = wahlperiode
    # Cursor pagination: DIP keeps returning the same cursor once the result set
    # is exhausted, which is the only reliable end-of-data signal.
    previous_cursor = None
    fetch_all = limit <= 0
    while fetch_all or len(protocols) < limit:
        page = client.get_json("/plenarprotokoll", params)
        protocols.extend(page.get("documents") or [])
        cursor = page.get("cursor")
        if not cursor or cursor == previous_cursor:
            break
        previous_cursor = cursor
        params["cursor"] = cursor
    return protocols if fetch_all else protocols[:limit]


# Decide which of the fetched protocols get a full dossier page.
#
#   detail_limit  < 0  -> none (catalog-only build)
#   detail_limit == 0  -> every protocol that has an XML URL
#   detail_limit  > 0  -> the first N protocols that have an XML URL
#   detail_limit is None -> no cap (used for explicitly requested dossiers)
#
# Protocols without fundstelle.xml_url are skipped with a warning because the
# extraction pipeline has nothing to read for them.
def protocols_for_detail_pages(protocols: list[dict[str, Any]], detail_limit: int | None) -> list[dict[str, Any]]:
    if detail_limit is not None and detail_limit < 0:
        return []
    selected: list[dict[str, Any]] = []
    for protocol in protocols:
        if protocol_xml_url(protocol):
            selected.append(protocol)
            if detail_limit is not None and detail_limit > 0 and len(selected) >= detail_limit:
                break
            continue
        print(
            f"warning: Skipping dossier for {protocol_label(protocol)} because fundstelle.xml_url is missing.",
            file=sys.stderr,
        )
    return selected


# ---------------------------------------------------------------------------
# Linking people to abgeordnetenwatch.de profiles
#
# Roll-call vote data from bundestag.de only carries a display name, so the
# surname has to be recovered heuristically before it can be matched against a
# profile. These two sets drive that heuristic.
# ---------------------------------------------------------------------------


# Lowercase nobiliary particles and connectors that belong to the surname
# ("von der Leyen", "van Aken") and must not be mistaken for a first name.
_VOTE_MEMBER_NAME_PARTICLES = {
    "auf",
    "da",
    "das",
    "de",
    "del",
    "den",
    "der",
    "di",
    "dos",
    "du",
    "la",
    "le",
    "ten",
    "ter",
    "und",
    "van",
    "vom",
    "von",
    "zu",
    "zum",
    "zur",
}

# Academic titles that are stripped from the front of a name before splitting.
_VOTE_MEMBER_TITLES = {"dr", "prof", "professor"}


def _vote_member_name_parts(name: Any) -> tuple[str | None, str | None]:
    """Conservative first/last split for Bundestag roll-call member names."""
    # Normalise whitespace (including NBSP) and drop a trailing ", MdB ..." tail.
    text = " ".join(str(name or "").replace("\xa0", " ").split()).strip()
    text = re.sub(r",\s*MdB\b.*$", "", text, flags=re.I).strip()
    if not text:
        return None, None
    # "Nachname, Vorname" is unambiguous - take it as given.
    if "," in text:
        last, first = (part.strip() for part in text.split(",", 1))
        return first or None, last or None

    # Otherwise: strip leading titles and a trailing MdB marker, then walk
    # backwards over particles to find where the surname starts. Only the
    # surname is returned; guessing the first name from free text is not safe.
    tokens = text.split()
    while tokens and tokens[0].strip(".").casefold() in _VOTE_MEMBER_TITLES:
        tokens.pop(0)
    while tokens and tokens[-1].strip(",.").casefold() == "mdb":
        tokens.pop()
    if not tokens:
        return None, None

    start = len(tokens) - 1
    while start > 0 and tokens[start - 1].strip(".").casefold() in _VOTE_MEMBER_NAME_PARTICLES:
        start -= 1
    return None, " ".join(tokens[start:])


# Agenda items carry either a list of roll-call votes ("votes") or a single
# legacy "vote" dict. Normalise both shapes into a list.
def _iter_report_votes(item: dict[str, Any]) -> list[dict[str, Any]]:
    return item.get("votes") or ([] if not item.get("vote") else [item["vote"]])


def enrich_report_with_profiles(report: dict[str, Any], resolver: Any | None) -> None:
    """Attach abgeordnetenwatch profile links to speakers and vote members.

    Each speaker dict gains an ``abgeordnetenwatch`` key holding the resolved
    profile (or ``None`` when no confident match exists). xml_speakers and
    xml_speakers_first share speaker objects for the first speeches, so the
    presence check keeps each speaker resolved at most once. Roll-call vote
    members use the same name+party resolver path with a conservative surname
    heuristic because Bundestag vote data only exposes a display name.
    """
    if resolver is None:
        return
    for item in report.get("agenda_items") or []:
        for key in ("xml_speakers", "xml_speakers_first"):
            for speech in item.get(key) or []:
                speaker = speech.get("speaker")
                if not isinstance(speaker, dict) or "abgeordnetenwatch" in speaker:
                    continue
                speaker["abgeordnetenwatch"] = resolver.resolve(
                    ext_id=speaker.get("xml_redner_id"),
                    first_name=speaker.get("first_name"),
                    last_name=speaker.get("last_name"),
                    fraktion=speaker.get("fraktion"),
                )
        for vote in _iter_report_votes(item):
            for member in vote.get("members") or []:
                if not isinstance(member, dict) or "abgeordnetenwatch" in member:
                    continue
                first_name, last_name = _vote_member_name_parts(member.get("name"))
                member["abgeordnetenwatch"] = (
                    resolver.resolve(
                        first_name=first_name,
                        last_name=last_name,
                        fraktion=member.get("faction"),
                    )
                    if last_name
                    else None
                )


# Handle --dossier-document-number: force these sittings to get a dossier even
# when the catalog fetch or --detail-limit would not have selected them, without
# narrowing the catalog itself.
def add_explicit_dossier_protocols(
    client: dip.ApiClient,
    protocols: list[dict[str, Any]],
    detail_protocols: list[dict[str, Any]],
    document_numbers: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not document_numbers:
        return protocols, detail_protocols

    # Index what we already have so an explicitly requested sitting is only
    # fetched from the API when it is genuinely missing.
    protocols_by_number = {
        normalized_document_number(protocol.get("dokumentnummer")): protocol for protocol in protocols
    }
    detail_by_number = {
        normalized_document_number(protocol.get("dokumentnummer")): protocol for protocol in detail_protocols
    }

    for document_number in document_numbers:
        document_number = normalized_document_number(document_number)
        if not document_number:
            continue
        protocol = protocols_by_number.get(document_number)
        if protocol is None:
            protocol = fetch_protocol_by_document_number(client, document_number)
            protocols.append(protocol)
            protocols_by_number[document_number] = protocol
        if document_number not in detail_by_number:
            detail_protocols.append(protocol)
            detail_by_number[document_number] = protocol

    return sorted(protocols, key=protocol_sort_key, reverse=True), detail_protocols


# ---------------------------------------------------------------------------
# Reading and writing dossier files
#
# Every dossier exists as two files that share one slug:
#   data/plenarprotokoll-<slug>.json   the intermediate report (source of truth
#                                      for rebuilds and for the SQLite store)
#   protocols/plenarprotokoll-<slug>.html   the rendered dossier page
# ---------------------------------------------------------------------------


def report_paths(output_dir: Path, document_number: str) -> tuple[Path, Path, str]:
    slug = slugify_document_number(document_number)
    return (
        output_dir / "data" / f"plenarprotokoll-{slug}.json",
        output_dir / "protocols" / f"plenarprotokoll-{slug}.html",
        slug,
    )


# Persist one dossier: the JSON report plus its HTML page. The page itself is
# rendered by the sibling module render_dip_pulse_html; mp_lookup lets speaker
# names in it link to the Abgeordnete profile pages.
def write_report_files(
    report: dict[str, Any],
    output_dir: Path,
    mp_lookup: dict[str, int] | None = None,
    features: Selection | None = None,
    *,
    include_dev_view: bool = False,
) -> dict[str, Any]:
    features = publication_selection()
    protocol = report.get("protocol") or {}
    document_number = normalized_document_number(protocol.get("dokumentnummer"))
    report_path, page_path, slug = report_paths(output_dir, document_number)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    page_path.write_text(
        pulse_html.render_html(
            report,
            features=features,
            mp_lookup=mp_lookup,
            include_dev_view=include_dev_view,
        ),
        encoding="utf-8",
    )
    return {
        "report": report,
        "report_path": report_path,
        "page_path": page_path,
        "slug": slug,
    }


# Load a previously built report for this sitting, if one is on disk. Used both
# to reuse LLM summaries and to report "Refreshing" vs "Downloading" in the
# progress log.
def load_existing_report(output_dir: Path, protocol: dict[str, Any]) -> dict[str, Any] | None:
    document_number = normalized_document_number(protocol.get("dokumentnummer"))
    if not document_number:
        return None
    report_path, _, _ = report_paths(output_dir, document_number)
    if not report_path.exists():
        return None
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"warning: Could not reuse existing dossier report {report_path}: {exc}", file=sys.stderr)
        return None


# Collect cached dossiers from data/ for the given protocols (--preserve-existing-dossiers
# and the offline render). Reports whose sitting is not part of this build's
# catalog are ignored, and unreadable files are skipped with a warning instead
# of failing the build.
def load_existing_detail_entries(output_dir: Path, protocols: list[dict[str, Any]]) -> list[dict[str, Any]]:
    protocol_numbers = {normalized_document_number(protocol.get("dokumentnummer")) for protocol in protocols}
    entries: list[dict[str, Any]] = []
    data_dir = output_dir / "data"
    if not data_dir.exists():
        return entries

    for report_path in sorted(data_dir.glob("plenarprotokoll-*.json")):
        if report_path.name == "plenarprotokoll-catalog.json":
            continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"warning: Skipping unreadable dossier report {report_path}: {exc}", file=sys.stderr)
            continue
        protocol = report.get("protocol") or {}
        document_number = normalized_document_number(protocol.get("dokumentnummer"))
        if not document_number or document_number not in protocol_numbers:
            continue
        expected_report_path, page_path, slug = report_paths(output_dir, document_number)
        entries.append(
            {
                "report": report,
                "report_path": expected_report_path if expected_report_path.exists() else report_path,
                "page_path": page_path,
                "slug": slug,
            }
        )
    return entries


def load_cached_protocols(output_dir: Path) -> list[dict[str, Any]]:
    """Load the protocol catalog from disk, augmenting it with cached dossier
    reports so offline renders work even when the catalog was never written."""
    catalog_path = output_dir / "data" / "plenarprotokoll-catalog.json"
    protocols: list[dict[str, Any]] = []
    if catalog_path.exists():
        try:
            cached = json.loads(catalog_path.read_text(encoding="utf-8"))
            if isinstance(cached, list):
                protocols.extend(item for item in cached if isinstance(item, dict))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"warning: Could not read cached protocol catalog {catalog_path}: {exc}", file=sys.stderr)

    protocols_by_number = {
        normalized_document_number(protocol.get("dokumentnummer")): protocol
        for protocol in protocols
        if normalized_document_number(protocol.get("dokumentnummer"))
    }
    protocols_by_id = {str(protocol.get("id") or ""): protocol for protocol in protocols if protocol.get("id")}

    data_dir = output_dir / "data"
    for report_path in sorted(data_dir.glob("plenarprotokoll-*.json")) if data_dir.exists() else []:
        if report_path.name == "plenarprotokoll-catalog.json":
            continue
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"warning: Skipping unreadable cached dossier {report_path}: {exc}", file=sys.stderr)
            continue
        protocol = report.get("protocol") if isinstance(report, dict) else None
        if not isinstance(protocol, dict):
            continue
        protocol_id = str(protocol.get("id") or "")
        document_number = normalized_document_number(protocol.get("dokumentnummer"))
        if protocol_id and protocol_id in protocols_by_id:
            continue
        if document_number and document_number in protocols_by_number:
            continue
        protocols.append(protocol)
        if protocol_id:
            protocols_by_id[protocol_id] = protocol
        if document_number:
            protocols_by_number[document_number] = protocol

    return sorted(protocols, key=protocol_sort_key, reverse=True)


def rebuild_cached_detail_pages(
    output_dir: Path,
    protocols: list[dict[str, Any]],
    mp_lookup: dict[str, int] | None = None,
    features: Selection | None = None,
    cached_entries: list[dict[str, Any]] | None = None,
    *,
    include_dev_view: bool = False,
) -> list[dict[str, Any]]:
    """Regenerate dossier HTML from cached JSON reports without API calls.

    Pass `cached_entries` when the caller already loaded them; the reports are
    large enough that a second parse of every file is noticeable.
    """
    if cached_entries is None:
        cached_entries = load_existing_detail_entries(output_dir, protocols)
    entries = []
    for entry in cached_entries:
        entries.append(
            write_report_files(
                entry["report"],
                output_dir,
                mp_lookup,
                features,
                include_dev_view=include_dev_view,
            )
        )
    return entries


# Combine cached and freshly generated dossiers into one list ordered like the
# catalog. Generated entries come last in the input, so they overwrite cached
# ones for the same sitting; the `seen` set keeps a sitting from appearing twice
# when it matches both by id and by document number.
def merge_detail_entries(
    protocols: list[dict[str, Any]],
    existing_entries: list[dict[str, Any]],
    generated_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entries_by_id: dict[str, dict[str, Any]] = {}
    entries_by_number: dict[str, dict[str, Any]] = {}
    for entry in [*existing_entries, *generated_entries]:
        protocol = entry["report"].get("protocol") or {}
        protocol_id = str(protocol.get("id") or "")
        document_number = normalized_document_number(protocol.get("dokumentnummer"))
        if protocol_id:
            entries_by_id[protocol_id] = entry
        if document_number:
            entries_by_number[document_number] = entry

    merged: list[dict[str, Any]] = []
    seen: set[int] = set()
    for protocol in protocols:
        entry = entries_by_id.get(str(protocol.get("id") or "")) or entries_by_number.get(
            normalized_document_number(protocol.get("dokumentnummer"))
        )
        if entry and id(entry) not in seen:
            merged.append(entry)
            seen.add(id(entry))
    return merged


# Rebuild the SQLite store from scratch out of the dossier reports.
#
# Written to a temporary file next to the target and moved into place only on
# success, so a failed build never leaves a half-written database behind - the
# database explorer page and the download link both read this file.
def rebuild_database_from_entries(
    database_path: Path,
    entries: list[dict[str, Any]],
    *,
    preserve_roster: bool = True,
) -> None:
    roster_rows: list[dict[str, Any]] = []
    if preserve_roster and database_path.exists():
        previous = pulse_store.connect(database_path)
        try:
            pulse_store.initialize(previous)
            roster_rows = [
                dict(row)
                for row in previous.execute(
                    """
                    SELECT m.*, p.name AS party_name
                    FROM mps m
                    LEFT JOIN parties p ON p.id = m.party_id
                    WHERE m.is_mdb = 1
                    """
                )
            ]
        finally:
            previous.close()

    # The facts the previous store held, carried into the fresh one. The engine
    # recomputes them right after this and overwrites them if anything moved -
    # but without the carry-over an online build would have nothing to diff
    # against, and the changed-winners report (D11) would never fire on the one
    # build that actually runs in production. Read-only, so nothing is migrated
    # in a store that is about to be replaced anyway.
    facts_snapshot: dict[str, list[list[Any]]] | None = None
    if database_path.exists():
        try:
            previous_facts = facts.open_readonly(database_path)
            try:
                facts_snapshot = facts.read_snapshot(previous_facts)
            finally:
                previous_facts.close()
        except sqlite3.Error as exc:
            # A store too damaged to read is about to be replaced anyway; the
            # engine recomputes every fact right after this. Losing the
            # carry-over costs one changed-winners report, not the build.
            print(f"warning: previous facts unreadable, not carried over ({exc})", file=sys.stderr)

    temp_path = database_path.with_name(f".{database_path.name}.tmp")
    if temp_path.exists():
        temp_path.unlink()
    store = pulse_store.connect(temp_path)
    try:
        pulse_store.initialize(store)
        for entry in entries:
            pulse_store.persist_report(store, entry["report"])
        if roster_rows:
            now = pulse_store.utc_now()
            with store:
                for row in roster_rows:
                    party_id = pulse_store.upsert_party(store, row.get("party_name"), now)
                    pulse_store.upsert_mp(
                        store,
                        now=now,
                        display_name=row.get("display_name"),
                        party_id=party_id,
                        identity_key=row["identity_key"],
                        dip_person_id=row.get("dip_person_id"),
                        xml_redner_id=row.get("xml_redner_id"),
                        title=row.get("title"),
                        function=row.get("function"),
                        wahlperiode=row.get("wahlperiode"),
                        profile_url=row.get("profile_url"),
                        birth_year=row.get("birth_year"),
                        gender=row.get("gender"),
                        profession=row.get("profession"),
                        wahlkreis=row.get("wahlkreis"),
                        bundesland=row.get("bundesland"),
                        aw_politician_id=row.get("aw_politician_id"),
                        person_roles_json=row.get("person_roles_json"),
                        is_mdb=True,
                    )
        if facts_snapshot is not None:
            facts.write_snapshot(store, facts_snapshot)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        store.close()
    temp_path.replace(database_path)


# ---------------------------------------------------------------------------
# LLM summary reuse
#
# Summaries cost money, so the default --summary-mode is "reuse": no LLM call is
# made, and summaries from the previous report are carried over into the new one.
# ---------------------------------------------------------------------------


# A summary is only worth keeping when it has text *and* the source chunks that
# back it up - the site never shows an unsourced summary.
def usable_llm_summary(summary: Any) -> bool:
    return (
        isinstance(summary, dict)
        and bool(summary.get("text"))
        and bool(summary.get("source_chunks"))
    )


# Keys under which an agenda item's summary can be matched across two builds:
# its TOP id first, its position in the sitting as a fallback.
def agenda_item_reuse_keys(item: dict[str, Any]) -> list[str]:
    keys = []
    top_id = str(item.get("top_id") or "").strip()
    if top_id:
        keys.append(f"top:{top_id}")
    if item.get("index") is not None:
        keys.append(f"index:{item['index']}")
    return keys


# Copy only source-compatible, fully cited summaries from the previous report.
def _reuse_valid_cached_summaries(
    report: dict[str, Any], existing_report: dict[str, Any] | None
) -> tuple[int, int]:
    existing_by_key: dict[str, dict[str, Any]] = {}
    for item in (existing_report or {}).get("agenda_items") or []:
        summary = item.get("llm_summary")
        if not usable_llm_summary(summary):
            continue
        for key in agenda_item_reuse_keys(item):
            existing_by_key[key] = summary

    reused = 0
    invalid = 0
    pdf_url = (report.get("protocol") or {}).get("pdf_url")
    for item in report.get("agenda_items") or []:
        top = {
            "top_id": item.get("top_id"),
            "heading": item.get("heading"),
            "speeches": item.get("xml_speakers") or [],
        }
        current_valid, _ = dip.validate_usable_summary(item.get("llm_summary"), top, pdf_url=pdf_url)
        if current_valid:
            continue
        for key in agenda_item_reuse_keys(item):
            summary = existing_by_key.get(key)
            if summary:
                valid, reason = dip.validate_usable_summary(summary, top, pdf_url=pdf_url)
                if valid:
                    item["llm_summary"] = copy.deepcopy(summary)
                    reused += 1
                else:
                    invalid += 1
                    print(
                        f"warning: cached summary for {item.get('top_id') or item.get('index')} "
                        f"was not reused ({reason or 'invalid_citations'}).",
                        file=sys.stderr,
                    )
                break

    return reused, invalid


def reuse_existing_llm_summaries(report: dict[str, Any], existing_report: dict[str, Any] | None) -> None:
    reused, invalid = _reuse_valid_cached_summaries(report, existing_report)
    report["summary_generation"] = {
        "enabled": False,
        "mode": "reuse",
        "reason": "refresh not requested",
        "reused_top_count": reused,
        "invalid_cache_count": invalid,
        "generated_top_count": 0,
        "available_top_count": sum(
            1 for item in report.get("agenda_items") or [] if usable_llm_summary(item.get("llm_summary"))
        ),
    }


def reconcile_generated_and_cached_summaries(
    report: dict[str, Any],
    existing_report: dict[str, Any] | None,
) -> None:
    """Fill generation gaps from validated cache and keep provenance counters exact."""
    fallback_count, invalid_cache_count = _reuse_valid_cached_summaries(report, existing_report)
    generation = report.setdefault("summary_generation", {})
    generation["reused_top_count"] = fallback_count
    generation["invalid_cache_count"] = invalid_cache_count

    raw = (report.setdefault("acquisition", {}).get("summaries") or {})
    eligible = int(raw.get("eligible") or 0)
    generated = int(raw.get("generated") or 0)
    pdf_url = (report.get("protocol") or {}).get("pdf_url")
    valid_top_ids: set[str] = set()
    valid_count = 0
    for item in report.get("agenda_items") or []:
        top = {
            "top_id": item.get("top_id"),
            "heading": item.get("heading"),
            "speeches": item.get("xml_speakers") or [],
        }
        if len(dip.summary_source_chunks(top)) < dip.SUMMARY_CHUNK_MIN:
            continue
        valid, _ = dip.validate_usable_summary(item.get("llm_summary"), top, pdf_url=pdf_url)
        if valid:
            valid_count += 1
            valid_top_ids.add(str(item.get("top_id") or item.get("index") or "unknown"))

    failures = [
        failure
        for failure in generation.get("failures") or []
        if str(failure.get("top_id") or "unknown") not in valid_top_ids
    ]
    generation["failures"] = failures
    generation["available_top_count"] = valid_count
    reused = max(0, valid_count - generated)
    raw_failed = int(raw.get("failed") or 0)
    failed = max(len(failures), raw_failed - fallback_count)
    omitted = max(0, eligible - generated - reused - failed)
    failure_reasons = tuple(
        dict.fromkeys(
            str(reason)
            for reason in (
                [failure["reason"] for failure in failures]
                or (raw.get("failure_reasons") or [])
            )
        )
    ) if failed else ()
    if failed:
        state = publication.AcquisitionState.PARTIAL if valid_count else publication.AcquisitionState.FAILED
    elif omitted:
        state = publication.AcquisitionState.PARTIAL
    else:
        state = publication.AcquisitionState.COMPLETE
    acquired_at = raw.get("acquired_at")
    if reused and not acquired_at:
        acquired_at = _prior_acquired_at(existing_report, "summaries")
    report["acquisition"]["summaries"] = publication.DomainFacts(
        domain="summaries",
        acquisition_state=state,
        source="llm-with-bundestag-citations",
        records=valid_count,
        reused=reused,
        rejected=failed,
        failure_reasons=failure_reasons,
        acquired_at=acquired_at,
        attempted_at=raw.get("attempted_at"),
        attempted=bool(raw.get("attempted")),
        counters={
            "eligible": eligible,
            "generated": generated,
            "omitted": omitted,
            "failed": failed,
            "fallbacks": fallback_count,
        },
    ).as_dict()


def reuse_existing_dossier_enrichments(
    report: dict[str, Any],
    existing_report: dict[str, Any] | None,
    *,
    votes: bool,
    profiles: bool,
) -> None:
    """Carry cached optional data forward when this update does not refresh it."""
    existing_by_key: dict[str, dict[str, Any]] = {}
    for item in (existing_report or {}).get("agenda_items") or []:
        for key in agenda_item_reuse_keys(item):
            existing_by_key[key] = item

    for item in report.get("agenda_items") or []:
        previous = next(
            (existing_by_key[key] for key in agenda_item_reuse_keys(item) if key in existing_by_key),
            None,
        )
        if not previous:
            continue
        if votes and not _iter_report_votes(item) and _iter_report_votes(previous):
            if previous.get("votes"):
                item["votes"] = copy.deepcopy(previous["votes"])
            elif previous.get("vote"):
                item["vote"] = copy.deepcopy(previous["vote"])
        if not profiles:
            continue

        previous_speakers: dict[tuple[str, str, str], dict[str, Any]] = {}
        for key in ("xml_speakers", "xml_speakers_first"):
            for speech in previous.get(key) or []:
                speaker = speech.get("speaker") or {}
                identity = (
                    str(speaker.get("xml_redner_id") or ""),
                    str(speaker.get("first_name") or ""),
                    str(speaker.get("last_name") or ""),
                )
                previous_speakers[identity] = speaker
        for key in ("xml_speakers", "xml_speakers_first"):
            for speech in item.get(key) or []:
                speaker = speech.get("speaker") or {}
                identity = (
                    str(speaker.get("xml_redner_id") or ""),
                    str(speaker.get("first_name") or ""),
                    str(speaker.get("last_name") or ""),
                )
                cached = previous_speakers.get(identity)
                if "abgeordnetenwatch" not in speaker and cached and "abgeordnetenwatch" in cached:
                    speaker["abgeordnetenwatch"] = copy.deepcopy(cached["abgeordnetenwatch"])

        previous_members = {
            (str(member.get("name") or ""), str(member.get("faction") or "")): member
            for vote in _iter_report_votes(previous)
            for member in (vote.get("members") or [])
        }
        for vote in _iter_report_votes(item):
            for member in vote.get("members") or []:
                cached = previous_members.get(
                    (str(member.get("name") or ""), str(member.get("faction") or ""))
                )
                if "abgeordnetenwatch" not in member and cached and "abgeordnetenwatch" in cached:
                    member["abgeordnetenwatch"] = copy.deepcopy(cached["abgeordnetenwatch"])


def _report_profile_counts(report: dict[str, Any]) -> tuple[int, int]:
    targets = 0
    records = 0
    for item in report.get("agenda_items") or []:
        for speech in item.get("xml_speakers") or []:
            speaker = speech.get("speaker") or {}
            targets += 1
            if (speaker.get("abgeordnetenwatch") or {}).get("url"):
                records += 1
        for vote in _iter_report_votes(item):
            for member in vote.get("members") or []:
                targets += 1
                if (member.get("abgeordnetenwatch") or {}).get("url"):
                    records += 1
    return records, targets


def _prior_acquired_at(existing_report: dict[str, Any] | None, domain: str) -> str | None:
    return (
        (((existing_report or {}).get("acquisition") or {}).get(domain) or {}).get("acquired_at")
    )


def annotate_report_acquisition(
    report: dict[str, Any],
    existing_report: dict[str, Any] | None,
    *,
    vote_scan_pages: int,
    profile_resolver: Any | None,
    summary_mode: str,
) -> None:
    """Finalize report-level optional-domain provenance after reuse/enrichment."""
    acquisition = report.setdefault("acquisition", {})

    vote_records = sum(
        len(_iter_report_votes(item)) for item in report.get("agenda_items") or []
    )
    if vote_scan_pages == 0:
        acquisition["votes"] = publication.DomainFacts(
            domain="votes",
            acquisition_state=(
                publication.AcquisitionState.COMPLETE
                if vote_records
                else publication.AcquisitionState.NOT_REQUESTED
            ),
            source="bundestag-roll-call",
            records=vote_records,
            reused=vote_records,
            acquired_at=_prior_acquired_at(existing_report, "votes") if vote_records else None,
        ).as_dict()

    profile_records, _profile_targets = _report_profile_counts(report)
    if profile_resolver is None:
        profile_state = (
            publication.AcquisitionState.COMPLETE
            if profile_records
            else publication.AcquisitionState.NOT_REQUESTED
        )
        acquisition["profiles"] = publication.DomainFacts(
            domain="profiles",
            acquisition_state=profile_state,
            source="abgeordnetenwatch",
            records=profile_records,
            reused=profile_records,
            acquired_at=_prior_acquired_at(existing_report, "profiles") if profile_records else None,
        ).as_dict()
    else:
        now = dip.utc_now()
        acquisition["profiles"] = publication.DomainFacts(
            domain="profiles",
            acquisition_state=publication.AcquisitionState.COMPLETE,
            source="abgeordnetenwatch",
            records=profile_records,
            acquired_at=now if profile_records else None,
            attempted_at=now,
            attempted=True,
        ).as_dict()

    if summary_mode == "reuse":
        eligible = sum(
            1
            for item in report.get("agenda_items") or []
            if len(
                dip.summary_source_chunks(
                    {
                        "top_id": item.get("top_id"),
                        "heading": item.get("heading"),
                        "speeches": item.get("xml_speakers") or [],
                    }
                )
            )
            >= dip.SUMMARY_CHUNK_MIN
        )
        reused = sum(
            1
            for item in report.get("agenda_items") or []
            if usable_llm_summary(item.get("llm_summary"))
        )
        invalid = min(
            max(0, eligible - reused),
            int((report.get("summary_generation") or {}).get("invalid_cache_count") or 0),
        )
        omitted = max(0, eligible - reused - invalid)
        if invalid:
            summary_state = (
                publication.AcquisitionState.PARTIAL
                if reused
                else publication.AcquisitionState.FAILED
            )
            reasons = ("invalid_citations",)
        elif reused:
            summary_state = publication.AcquisitionState.COMPLETE
            reasons = ()
        else:
            summary_state = publication.AcquisitionState.NOT_REQUESTED
            reasons = ()
        acquisition["summaries"] = publication.DomainFacts(
            domain="summaries",
            acquisition_state=summary_state,
            source="llm-with-bundestag-citations",
            records=reused,
            reused=reused,
            rejected=invalid,
            failure_reasons=reasons,
            acquired_at=_prior_acquired_at(existing_report, "summaries") if reused else None,
            counters={
                "eligible": eligible,
                "generated": 0,
                "omitted": omitted,
                "failed": invalid,
                "fallbacks": 0,
            },
        ).as_dict()


# Build one complete dossier for a single sitting and write both of its files.
#
# The heavy lifting (XML download, agenda/speech extraction, DIP lookups,
# roll-call scraping, LLM summaries) happens in validate_dip_protocol.build_report.
# This function only assembles the argparse.Namespace that function expects, then
# lets the enabled feature components enrich the resulting report.
def write_report_and_page(
    protocol: dict[str, Any],
    output_dir: Path,
    api_key: str,
    sleep: float,
    person_limit: int,
    vote_scan_pages: int,
    roll_call_list_id: str | None,
    summary_mode: str,
    summary_provider: str,
    anthropic_api_key: str | None,
    gemini_api_key: str | None,
    summary_model: str | None,
    existing_report: dict[str, Any] | None,
    profile_resolver: Any | None = None,
    mp_lookup: dict[str, int] | None = None,
    features: Selection | None = None,
    include_dev_view: bool = False,
    summary_max_calls: int = 25,
    summary_timeout: float = 60,
) -> dict[str, Any]:
    features = publication_selection()
    # "reuse" is a mode of *this* script, not of the report builder: tell the
    # builder not to call an LLM, then fill summaries in below from the cached
    # report via the summaries component.
    effective_summary_mode = "off" if summary_mode == "reuse" else (
        "auto" if summary_mode == "required" else summary_mode
    )
    args = argparse.Namespace(
        api_key=api_key,
        protocol_id=str(protocol["id"]),
        document_number=None,
        limit_tops=None,
        person_limit=person_limit,
        vote_scan_pages=vote_scan_pages,
        roll_call_list_id=roll_call_list_id,
        summary_mode=effective_summary_mode,
        summary_provider=summary_provider,
        anthropic_api_key=anthropic_api_key,
        gemini_api_key=gemini_api_key,
        summary_model=summary_model,
        summary_max_calls=summary_max_calls,
        summary_timeout=summary_timeout,
        # A cache may satisfy some or all required summaries. Without a cache,
        # fail before making any provider calls when the budget cannot suffice.
        summary_required_preflight=summary_mode == "required" and existing_report is None,
        sleep=sleep,
    )
    report = dip.build_report(args, protocol=protocol)
    if summary_mode in {"auto", "required"}:
        reconcile_generated_and_cached_summaries(report, existing_report)
    reuse_existing_dossier_enrichments(
        report,
        existing_report,
        votes=vote_scan_pages == 0,
        profiles=profile_resolver is None,
    )
    # Post-processing steps supplied by enrichment components. In reuse mode the
    # summaries component carries cached summaries over; aw-profiles attaches
    # abgeordnetenwatch profiles to speakers and vote members.
    components = {
        component.feature.id: component
        for component in feature_loader.load(features, include_dev_view=include_dev_view)
    }
    enrich_context = {
        "summary_mode": summary_mode,
        "existing_report": existing_report,
        "profile_resolver": profile_resolver,
        "reuse_existing_llm_summaries": reuse_existing_llm_summaries,
        "enrich_report_with_profiles": enrich_report_with_profiles,
    }
    for feature_id in ("summaries", "aw-profiles"):
        component = components.get(feature_id)
        if component:
            component.enrich_report(report, enrich_context)
    annotate_report_acquisition(
        report,
        existing_report,
        vote_scan_pages=vote_scan_pages,
        profile_resolver=profile_resolver,
        summary_mode=summary_mode,
    )
    if summary_mode == "required":
        missing = []
        for item in report.get("agenda_items") or []:
            top = {
                "top_id": item.get("top_id"),
                "heading": item.get("heading"),
                "speeches": item.get("xml_speakers") or [],
            }
            if len(dip.summary_source_chunks(top)) < dip.SUMMARY_CHUNK_MIN:
                continue
            valid, _ = dip.validate_usable_summary(
                item.get("llm_summary"),
                top,
                pdf_url=(report.get("protocol") or {}).get("pdf_url"),
            )
            if not valid:
                missing.append(str(item.get("top_id") or item.get("index")))
        if missing:
            raise dip.DipError(
                "Required summaries are incomplete for "
                + ", ".join(missing)
                + ". Fix: increase --summary-max-calls, provide provider credentials, or use --summary-mode auto."
            )
    return write_report_files(
        report,
        output_dir,
        mp_lookup,
        features,
        include_dev_view=include_dev_view,
    )


# ---------------------------------------------------------------------------
# PAGE: database.html - "Daten"
#
# database.html used to be a browser-side explorer of 12 sample rows per
# table. It is now a download page: a distribution copy of the SQLite store
# (with speeches.paragraphs_json dropped, a duplicate of speeches.text), 16
# CSV.gz files, and five SQL "recipes" executed at build time so a visitor can
# copy the SQL, run it against the file they just downloaded, and get the same
# rows. Everything the page shows - sizes, checksums, the Datenstand band, the
# recipe rows, the schema cards - is read from one manifest (datenstand.json)
# built by export_distribution_data(). The page itself never opens the build
# store.
# ---------------------------------------------------------------------------


def sqlite_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


# "47,2 MB" - German decimal comma, used everywhere the manifest reports a size.
def format_size_de(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(num_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}".replace(".", ",")
        value /= 1024
    return f"{num_bytes} B"


# One sqlite_schema walk shared by the export step (CSV + manifest columns) and
# anything else that needs to describe every table read-only. Never used on a
# writable connection to the live build store.
def iter_tables(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    table_rows = conn.execute(
        """
        SELECT name, sql
        FROM sqlite_schema
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    for table_row in table_rows:
        table = str(table_row["name"])
        columns = [
            {
                "cid": row["cid"],
                "name": row["name"],
                "type": row["type"] or "",
                "notnull": bool(row["notnull"]),
                "default": row["dflt_value"],
                "pk": bool(row["pk"]),
            }
            for row in conn.execute(f"PRAGMA table_info({sqlite_identifier(table)})")
        ]
        foreign_keys = [
            {
                "from": row["from"],
                "to_table": row["table"],
                "to_column": row["to"],
                "on_delete": row["on_delete"],
            }
            for row in conn.execute(f"PRAGMA foreign_key_list({sqlite_identifier(table)})")
        ]
        row_count = int(conn.execute(f"SELECT COUNT(*) AS n FROM {sqlite_identifier(table)}").fetchone()["n"])
        tables.append(
            {
                "name": table,
                "sql": table_row["sql"] or "",
                "columns": columns,
                "foreign_keys": foreign_keys,
                "row_count": row_count,
            }
        )
    return tables


# Column provenance for the manifest's data dictionary (F3.3/X2): almost every
# column comes from the DIP XML/API extraction. A short list of overrides marks
# the columns that come from elsewhere, so "primary sources only" is checkable
# per column instead of asserted for the whole page.
_COLUMN_SOURCE_ABGEORDNETENWATCH = {("mps", "aw_politician_id"), ("mps", "profile_url")}
_COLUMN_SOURCE_DIP_ROSTER = {
    ("mps", "birth_year"),
    ("mps", "gender"),
    ("mps", "profession"),
    ("mps", "wahlkreis"),
    ("mps", "bundesland"),
}
_TABLE_SOURCE_BUNDESTAG = {"votes", "vote_fractions", "vote_members", "vote_documents", "agenda_item_votes"}
# The facts tables are computed by scripts/facts.py from the rest of the store,
# so every one of their columns is "derived" - the fallback below would claim
# DIP wrote them. Their captions for the Daten page are T7's.
_TABLE_SOURCE_DERIVED = {"mp_canonical", "datenstand"} | set(facts.FACTS_TABLES)


def column_source(table: str, column: str) -> str:
    if table in _TABLE_SOURCE_DERIVED:
        return "derived"
    if (table, column) in _COLUMN_SOURCE_ABGEORDNETENWATCH:
        return "abgeordnetenwatch"
    if (table, column) in _COLUMN_SOURCE_DIP_ROSTER:
        return "dip"
    if table in _TABLE_SOURCE_BUNDESTAG:
        return "bundestag.de"
    return "dip"


EXPORT_FORMAT = 1
DATA_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SYNTHETIC_REDE_ID_RE = re.compile(r"^[0-9]+:[0-9]+:[0-9]+$")

# Which identifiers a downstream consumer can rely on across releases, and
# which ones are only guaranteed within a single build. Manifest honesty
# (eng addendum "stable_keys lists only external identifiers"): mps.id and
# mps.identity_key are per-build even though identity_key looks stable, because
# a name-party fallback key can change if a person's name is corrected upstream.
STABLE_KEYS: dict[str, tuple[str, ...]] = {
    "protocols": ("id", "document_number"),
    "votes": ("id",),
    "proceedings": ("id",),
    "mps": ("dip_person_id", "aw_politician_id"),
    "speeches": ("rede_id",),
}
PER_BUILD_KEYS: dict[str, tuple[str, ...]] = {
    "speeches": ("id",),
    "mps": ("id", "identity_key"),
    "agenda_items": ("id",),
    "documents": ("id",),
}

# The five recipes executed at build time against the distribution copy and
# rendered next to their SQL (design doc appendix, amended per the eng
# addendum: R1/R3 join mp_canonical and group by the canonical id, so their
# counts equal the pooled counts on the MP profile pages).
#
# Every "hidden" column is selected (it is the link key) but never rendered as
# its own cell; the "link" on a visible column says which kind of link to try
# resolving for that row (see resolve_entity_link). "truncate" caps a cell's
# visible text, keeping the full value in the HTML title attribute.
RECIPES: tuple[dict[str, Any], ...] = (
    {
        "id": "r1-meiste-reden",
        "title": "Wer hielt die meisten Reden?",
        "sql": (
            "SELECT m.identity_key AS mp_id, m.display_name, p.name AS fraktion,\n"
            "       COUNT(*) AS reden, SUM(s.char_count) AS zeichen\n"
            "FROM speeches s\n"
            "JOIN mp_canonical mc ON mc.mp_id = s.mp_id\n"
            "JOIN mps m ON m.id = mc.canonical_id\n"
            "LEFT JOIN parties p ON p.id = m.party_id\n"
            "GROUP BY mc.canonical_id\n"
            "ORDER BY reden DESC, zeichen DESC, mc.canonical_id\n"
            "LIMIT 5;"
        ),
        "columns": (
            {"name": "mp_id", "align": "text", "hidden": True},
            {"name": "display_name", "align": "text", "link": "mp"},
            {"name": "fraktion", "align": "text"},
            {"name": "reden", "align": "num"},
            {"name": "zeichen", "align": "num"},
        ),
        "depends_on": None,
        "caveat": "Regierungsmitglieder tragen im DIP die Fraktion „Regierung“.",
    },
    {
        "id": "r2-redeanteil-fraktion",
        "title": "Redeanteil je Fraktion nach Zeichen",
        "sql": (
            "SELECT COALESCE(NULLIF(s.fraktion, ''), p.name) AS fraktion, COUNT(*) AS reden,\n"
            "       ROUND(100.0 * SUM(s.char_count) / (SELECT SUM(char_count) FROM speeches), 1) AS anteil_prozent\n"
            "FROM speeches s\n"
            "JOIN mps m ON m.id = s.mp_id\n"
            "LEFT JOIN parties p ON p.id = m.party_id\n"
            "GROUP BY COALESCE(NULLIF(s.fraktion, ''), p.name)\n"
            "ORDER BY reden DESC, fraktion\n"
            "LIMIT 5;"
        ),
        "columns": (
            {"name": "fraktion", "align": "text"},
            {"name": "reden", "align": "num"},
            {"name": "anteil_prozent", "align": "num"},
        ),
        "depends_on": None,
        "caveat": None,
    },
    {
        "id": "r3-abweichler",
        "title": "Wer stimmt am häufigsten gegen die eigene Fraktion?",
        "sql": (
            "SELECT m.identity_key AS mp_id, m.display_name, p.name AS fraktion,\n"
            "       COUNT(DISTINCT vm.vote_id) AS abweichungen\n"
            "FROM vote_members vm\n"
            "JOIN vote_fractions vf ON vf.vote_id = vm.vote_id AND vf.party_id = vm.party_id\n"
            "JOIN mp_canonical mc ON mc.mp_id = vm.mp_id\n"
            "JOIN mps m ON m.id = mc.canonical_id\n"
            "JOIN parties p ON p.id = vm.party_id\n"
            "WHERE vm.vote IN ('yes', 'no')\n"
            "  AND vf.leading_vote IN ('yes', 'no')\n"
            "  AND vm.vote <> vf.leading_vote\n"
            "GROUP BY mc.canonical_id\n"
            "ORDER BY abweichungen DESC, m.display_name\n"
            "LIMIT 5;"
        ),
        "columns": (
            {"name": "mp_id", "align": "text", "hidden": True},
            {"name": "display_name", "align": "text", "link": "mp"},
            {"name": "fraktion", "align": "text"},
            {"name": "abweichungen", "align": "num"},
        ),
        "depends_on": "votes",
        "caveat": None,
    },
    {
        "id": "r4-knappste-abstimmungen",
        "title": "Die knappsten namentlichen Abstimmungen",
        "sql": (
            "SELECT MIN(p.document_number) AS document_number,\n"
            "       v.date, v.title, v.yes_count AS ja, v.no_count AS nein,\n"
            "       ABS(v.yes_count - v.no_count) AS differenz\n"
            "FROM votes v\n"
            "LEFT JOIN agenda_item_votes aiv ON aiv.vote_id = v.id\n"
            "LEFT JOIN agenda_items ai ON ai.id = aiv.agenda_item_id\n"
            "LEFT JOIN protocols p ON p.id = ai.protocol_id\n"
            "GROUP BY v.id\n"
            "ORDER BY differenz ASC, v.date DESC, v.id\n"
            "LIMIT 5;"
        ),
        "columns": (
            {"name": "document_number", "align": "text", "hidden": True},
            {"name": "date", "align": "text"},
            {"name": "title", "align": "text", "link": "document", "truncate": 90},
            {"name": "ja", "align": "num"},
            {"name": "nein", "align": "num"},
            {"name": "differenz", "align": "num"},
        ),
        "depends_on": "votes",
        "caveat": None,
    },
    {
        "id": "r5-vorgaenge-meiste-reden",
        "title": "Vorgänge mit den meisten Reden",
        "sql": (
            "SELECT pr.id AS proceeding_id, pr.title, pr.proceeding_type AS typ,\n"
            "       COUNT(DISTINCT s.id) AS reden, COUNT(DISTINCT ai.protocol_id) AS sitzungen,\n"
            "       MIN(p.document_number) AS erste_drucksache\n"
            "FROM proceedings pr\n"
            "JOIN proceeding_positions pp ON pp.proceeding_id = pr.id\n"
            "JOIN agenda_items ai ON ai.id = pp.agenda_item_id\n"
            "JOIN speeches s ON s.agenda_item_id = ai.id\n"
            "LEFT JOIN protocols p ON p.id = ai.protocol_id\n"
            "GROUP BY pr.id\n"
            "ORDER BY reden DESC, sitzungen DESC, pr.id\n"
            "LIMIT 5;"
        ),
        "columns": (
            {"name": "proceeding_id", "align": "text", "hidden": True},
            {"name": "title", "align": "text", "link": "proceeding", "truncate": 90},
            {"name": "typ", "align": "text"},
            {"name": "erste_drucksache", "align": "text"},
            {"name": "reden", "align": "num"},
            {"name": "sitzungen", "align": "num"},
        ),
        "depends_on": None,
        "caveat": None,
    },
)
RECIPES_BY_ID = {recipe["id"]: recipe for recipe in RECIPES}


class DataExportUnavailable(RuntimeError):
    """The store exists but cannot be exported (e.g. SQLite below 3.35)."""


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _recipes_hash(recipes: tuple[dict[str, Any], ...]) -> str:
    payload = [{"id": recipe["id"], "sql": recipe["sql"]} for recipe in recipes]
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


# Everything the page renders from the manifest is part of the skip rule, so a
# changed flag or a grown catalog re-exports instead of serving stale values
# until --force-export. Coverage is a dict of the three Baustein states.
def _inputs_hash(
    *,
    source_sha256: str,
    recipes_hash: str,
    export_format: int,
    tag: str,
    license_text: str,
    issues_url: str | None = None,
    catalog_count: int = 0,
    dossier_count: int = 0,
    readiness: dict[str, str] | None = None,
) -> str:
    payload = {
        "source_sha256": source_sha256,
        "recipes_hash": recipes_hash,
        "export_format": export_format,
        "tag": tag,
        "license": license_text,
        "issues_url": issues_url,
        "catalog_count": catalog_count,
        "dossier_count": dossier_count,
        "readiness": {
            feature_id: (readiness or {}).get(feature_id, "unavailable") for feature_id in ("votes", "aw-profiles", "mp-roster")
        },
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


# Rehash the build store only when its (mtime, size) changed since the last
# export (E4.1) - a 291 MB store would otherwise cost a multi-second hash on
# every offline UI rebuild, defeating the whole point of the skip rule.
def _source_sha256(database_path: Path, stat: os.stat_result, previous: dict[str, Any] | None) -> str:
    if (
        previous
        and previous.get("source_mtime_ns") == stat.st_mtime_ns
        and previous.get("source_bytes") == stat.st_size
        and previous.get("source_sha256")
    ):
        return str(previous["source_sha256"])
    return _hash_file(database_path)


def _read_previous_manifest(exports_dir: Path) -> dict[str, Any] | None:
    manifest_path = exports_dir / "datenstand.json"
    if not manifest_path.exists():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


# F1.1: a manifest is only reusable when it parses, matches the current
# export format and inputs, and every file it names still exists at the
# recorded size. Anything else re-exports rather than trusting stale bytes.
def _manifest_reusable(manifest: dict[str, Any] | None, exports_dir: Path, *, inputs_hash: str, export_format: int) -> bool:
    if not manifest:
        return False
    if manifest.get("export_format") != export_format:
        return False
    if manifest.get("inputs_hash") != inputs_hash:
        return False
    generation = manifest.get("generation")
    if not generation:
        return False
    gen_dir = exports_dir / str(generation)
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        return False
    for file_info in files:
        try:
            file_path = gen_dir / str(file_info["name"])
            if file_path.stat().st_size != file_info["bytes"]:
                return False
        except (KeyError, OSError, TypeError):
            return False
    return True


def _lock_holder_alive(pid_text: str) -> bool:
    """True unless the pid recorded in the lock is provably dead. An
    unparseable pid or a permission error counts as alive: the conservative
    answer keeps a live build's lock intact."""
    try:
        pid = int(pid_text)
    except ValueError:
        return True
    if pid <= 0:
        return True
    # Signal 0 is a liveness probe only on POSIX; on Windows os.kill() would
    # terminate the process, so there the lock is always treated as held.
    if os.name != "posix":
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


@contextlib.contextmanager
def _export_lock(exports_dir: Path):
    exports_dir.mkdir(parents=True, exist_ok=True)
    lock_path = exports_dir / ".lock"
    fd = None
    for attempt in range(2):
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            pid_text = ""
            try:
                pid_text = lock_path.read_text(encoding="utf-8").strip()
            except OSError:
                pass
            # A lock whose recorded process no longer exists was left by a
            # crashed build; clear it once and retry instead of blocking
            # every later build until someone deletes the file by hand.
            if attempt == 0 and not _lock_holder_alive(pid_text):
                print(f"export: clearing stale {lock_path} (pid {pid_text or '?'} is gone)", file=sys.stderr)
                lock_path.unlink(missing_ok=True)
                continue
            raise RuntimeError(f"error: another build holds {lock_path} (pid {pid_text or '?'})") from None
    assert fd is not None
    try:
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
        yield
    finally:
        lock_path.unlink(missing_ok=True)


# F2.1/F4.1: unique temp names inside exports_dir, cleaned up in `finally`;
# a stale *.tmp or half-written generation directory from a crashed run is
# swept before a new export starts.
def _sweep_stale_temp(exports_dir: Path) -> None:
    if not exports_dir.exists():
        return
    for path in exports_dir.glob("*.tmp"):
        path.unlink(missing_ok=True)
    for path in exports_dir.glob(".*-*.json"):
        if path.name.startswith(".datenstand-"):
            path.unlink(missing_ok=True)


# A lone surrogate (e.g. from surrogateescape-decoded bytes upstream) cannot
# be encoded as UTF-8; errors="replace" swaps it for U+FFFD when writing the
# CSV, and this counts how many characters that will happen to (F2.2).
def _surrogate_count(text: str) -> int:
    return sum(1 for ch in text if 0xD800 <= ord(ch) <= 0xDFFF)


# Stream one table into a gzip CSV: header row, NULL as empty string, ordered
# by primary key (rowid when none), errors="replace" with a count of any lone
# surrogates the source text contained (F2.2). Never fetchall()s (F7.1).
def _write_csv(conn: sqlite3.Connection, table: str, columns: list[dict[str, Any]], path: Path) -> tuple[int, int]:
    names = [column["name"] for column in columns]
    pk_columns = [column["name"] for column in columns if column["pk"]]
    order_clause = (
        f" ORDER BY {', '.join(sqlite_identifier(name) for name in pk_columns)}" if pk_columns else " ORDER BY rowid"
    )
    select_sql = f"SELECT {', '.join(sqlite_identifier(name) for name in names)} FROM {sqlite_identifier(table)}{order_clause}"

    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-", suffix=".tmp")
    tmp_path = Path(tmp_name)
    row_count = 0
    replacements = 0
    try:
        with os.fdopen(fd, "wb") as raw:
            gz = gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=6, mtime=0)
            try:
                text = io.TextIOWrapper(gz, encoding="utf-8", errors="replace", newline="")
                writer = csv.writer(text, lineterminator="\n")
                writer.writerow(names)
                for row in conn.execute(select_sql):
                    cells = []
                    for value in row:
                        if value is None:
                            cells.append("")
                            continue
                        text_value = str(value)
                        replacements += _surrogate_count(text_value)
                        cells.append(text_value)
                    writer.writerow(cells)
                    row_count += 1
                text.flush()
            finally:
                gz.close()
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return row_count, replacements


# Build the distribution copy, the 16 CSVs and datenstand.json from the build
# store. Called once per build, from main(), after the store and the MP
# identity mapping are final; render_site() and the page never open the build
# store themselves (eng addendum: "the page ... never opens the build store").
#
# Layout of exports_dir:
#   .lock                    held only while an export runs
#   datenstand.json          the manifest; written last via mkstemp+replace,
#                            the only pointer a reader needs to follow
#   g-<inputs_hash[:12]>/    one generation's files; a new export writes a
#                            fresh directory and only deletes the previous one
#                            after datenstand.json points at the new one
#   published.json           written by the (separate) publish script; never
#   LICENSE-DATA.md          touched by this function
def export_distribution_data(
    database_path: Path,
    exports_dir: Path,
    *,
    recipes: tuple[dict[str, Any], ...] = RECIPES,
    canonical_by_mp_id: dict[int, int] | None = None,
    mp_lookup: dict[str, int] | None = None,
    readiness: dict[str, str] | None = None,
    catalog_count: int = 0,
    dossier_count: int = 0,
    tag: str = "local",
    license_text: str = "",
    issues_url: str | None = None,
    commit: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    if sqlite3.sqlite_version_info < (3, 35, 0):
        raise DataExportUnavailable(
            f"data export needs SQLite 3.35+ (found {sqlite3.sqlite_version}); "
            "upgrade Python or run the export on another machine"
        )

    canonical_by_mp_id = canonical_by_mp_id or {}
    has_page_ids = set((mp_lookup or {}).values())
    readiness = readiness or {}

    exports_dir.mkdir(parents=True, exist_ok=True)
    with _export_lock(exports_dir):
        # Only the lock holder may sweep: a second build sweeping before it
        # fails on the lock would delete the first build's in-flight manifest.
        _sweep_stale_temp(exports_dir)
        previous = _read_previous_manifest(exports_dir)
        stat = database_path.stat()
        source_sha256 = _source_sha256(database_path, stat, previous)
        recipes_hash = _recipes_hash(recipes)
        inputs_hash = _inputs_hash(
            source_sha256=source_sha256,
            recipes_hash=recipes_hash,
            export_format=EXPORT_FORMAT,
            tag=tag,
            license_text=license_text,
            issues_url=issues_url,
            catalog_count=catalog_count,
            dossier_count=dossier_count,
            readiness=readiness,
        )

        if not force and _manifest_reusable(previous, exports_dir, inputs_hash=inputs_hash, export_format=EXPORT_FORMAT):
            print("export: reused data/exports (unchanged)", file=sys.stderr)
            return previous  # type: ignore[return-value]

        if previous is not None:
            print("export: manifest invalid or stale, re-exporting", file=sys.stderr)

        started = time.monotonic()
        generation = f"g-{inputs_hash[:12]}"
        gen_dir = exports_dir / generation
        if gen_dir.exists():
            shutil.rmtree(gen_dir)
        gen_dir.mkdir(parents=True)

        try:
            manifest = _run_export(
                database_path=database_path,
                gen_dir=gen_dir,
                recipes=recipes,
                canonical_by_mp_id=canonical_by_mp_id,
                has_page_ids=has_page_ids,
                readiness=readiness,
                catalog_count=catalog_count,
                dossier_count=dossier_count,
                tag=tag,
                license_text=license_text,
                issues_url=issues_url,
                commit=commit,
                source_sha256=source_sha256,
                source_stat=stat,
                recipes_hash=recipes_hash,
                inputs_hash=inputs_hash,
                generation=generation,
            )

            manifest_fd, manifest_tmp_name = tempfile.mkstemp(dir=exports_dir, prefix=".datenstand-", suffix=".json")
            os.close(manifest_fd)
            manifest_tmp_path = Path(manifest_tmp_name)
            manifest_tmp_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            manifest_tmp_path.replace(exports_dir / "datenstand.json")
        except sqlite3.Error as exc:
            # backup()/DROP COLUMN/VACUUM INTO fail with sqlite3 errors on a
            # locked or corrupt store or a full disk; surface them through the
            # CLI's clean "error:" path instead of a traceback.
            shutil.rmtree(gen_dir, ignore_errors=True)
            raise RuntimeError(f"export: distribution copy failed: {exc}") from exc
        except Exception:
            shutil.rmtree(gen_dir, ignore_errors=True)
            raise

        for old_dir in exports_dir.glob("g-*"):
            if old_dir.name != generation:
                shutil.rmtree(old_dir, ignore_errors=True)

        sqlite_file = manifest["files"][0]
        elapsed = time.monotonic() - started
        print(
            f"export: distribution copy {format_size_de(sqlite_file['unpacked_bytes'])} -> "
            f"{format_size_de(sqlite_file['bytes'])} gz in {elapsed:.1f} s",
            file=sys.stderr,
        )
        return manifest


# The part of export_distribution_data that actually writes bytes, split out
# so the lock/skip-rule/cleanup logic above stays readable.
def _run_export(
    *,
    database_path: Path,
    gen_dir: Path,
    recipes: tuple[dict[str, Any], ...],
    canonical_by_mp_id: dict[int, int],
    has_page_ids: set[int],
    readiness: dict[str, str],
    catalog_count: int,
    dossier_count: int,
    tag: str,
    license_text: str,
    issues_url: str | None,
    commit: str | None,
    source_sha256: str,
    source_stat: os.stat_result,
    recipes_hash: str,
    inputs_hash: str,
    generation: str,
) -> dict[str, Any]:
    dist_fd, dist_name = tempfile.mkstemp(dir=gen_dir, prefix=".dist-", suffix=".sqlite")
    os.close(dist_fd)
    dist_path = Path(dist_name)
    dist_path.unlink()  # backup() needs a fresh (non-existent or empty) target
    vacuum_fd, vacuum_name = tempfile.mkstemp(dir=gen_dir, prefix=".vacuum-", suffix=".sqlite")
    os.close(vacuum_fd)
    vacuum_path = Path(vacuum_name)
    vacuum_path.unlink()  # VACUUM INTO requires the target to not exist

    dist_conn = sqlite3.connect(dist_path, isolation_level=None)
    dist_conn.row_factory = sqlite3.Row
    source_conn = sqlite3.connect(f"file:{database_path.resolve()}?mode=ro", uri=True)
    try:
        source_conn.backup(dist_conn)
    except sqlite3.Error:
        dist_conn.close()
        raise
    finally:
        source_conn.close()

    try:
        # Direct exports and older SQLite stores may not have been migrated.
        if "paragraphs_json" in {row["name"] for row in dist_conn.execute("PRAGMA table_info(speeches)")}:
            dist_conn.execute("ALTER TABLE speeches DROP COLUMN paragraphs_json")
        dist_conn.execute(
            "CREATE TABLE mp_canonical (mp_id INTEGER PRIMARY KEY, canonical_id INTEGER NOT NULL, has_page INTEGER NOT NULL)"
        )
        mp_rows = [
            (mp_id, canonical_id, 1 if canonical_id in has_page_ids else 0)
            for mp_id, canonical_id in sorted(canonical_by_mp_id.items())
        ]
        dist_conn.executemany("INSERT INTO mp_canonical(mp_id, canonical_id, has_page) VALUES (?, ?, ?)", mp_rows)
        # Only the CREATE statements feed the hash; iter_tables() would also
        # COUNT(*) every table, which the final snapshot pass does once anyway.
        create_statements = sorted(
            str(row[0] or "")
            for row in dist_conn.execute(
                "SELECT sql FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        )
        schema_hash = hashlib.sha256("\n".join(create_statements).encode("utf-8")).hexdigest()
        dist_conn.execute(
            "CREATE TABLE datenstand (tag TEXT, export_format INTEGER, license TEXT, schema_hash TEXT, source_sha256 TEXT)"
        )
        dist_conn.execute(
            "INSERT INTO datenstand(tag, export_format, license, schema_hash, source_sha256) VALUES (?, ?, ?, ?, ?)",
            (tag, EXPORT_FORMAT, license_text, schema_hash, source_sha256),
        )
        dist_conn.execute(f"PRAGMA user_version = {int(EXPORT_FORMAT)}")
        vacuum_target = str(vacuum_path).replace("'", "''")
        dist_conn.execute(f"VACUUM INTO '{vacuum_target}'")
    finally:
        dist_conn.close()
    dist_path.unlink()

    snapshot_conn = sqlite3.connect(vacuum_path)
    snapshot_conn.row_factory = sqlite3.Row
    try:
        tables_info = iter_tables(snapshot_conn)
        snapshot_conn.create_function(
            "REGEXP", 2, lambda pattern, value: bool(re.search(pattern, value)) if value is not None else False
        )
        synthetic_rede_ids = int(
            snapshot_conn.execute(
                "SELECT COUNT(*) FROM speeches WHERE rede_id REGEXP '^[0-9]+:[0-9]+:[0-9]+$'"
            ).fetchone()[0]
        )
        conflicting_votes = int(
            snapshot_conn.execute(
                """
                SELECT COUNT(*) FROM (
                  SELECT mc.canonical_id, vm.vote_id
                  FROM vote_members vm
                  JOIN mp_canonical mc ON mc.mp_id = vm.mp_id
                  GROUP BY mc.canonical_id, vm.vote_id
                  HAVING COUNT(DISTINCT vm.vote) > 1
                )
                """
            ).fetchone()[0]
        )

        unpacked_bytes = vacuum_path.stat().st_size
        unpacked_sha256 = _hash_file(vacuum_path)
        sqlite_name = f"bundestag-pulse-{tag}.sqlite.gz"
        sqlite_path = gen_dir / sqlite_name
        with vacuum_path.open("rb") as source_file, sqlite_path.open("wb") as target_file:
            gz = gzip.GzipFile(filename="", mode="wb", fileobj=target_file, compresslevel=6, mtime=0)
            try:
                shutil.copyfileobj(source_file, gz)
            finally:
                gz.close()
        sqlite_sha256 = _hash_file(sqlite_path)

        files: list[dict[str, Any]] = [
            {
                "name": sqlite_name,
                "bytes": sqlite_path.stat().st_size,
                "unpacked_bytes": unpacked_bytes,
                "sha256": sqlite_sha256,
                "unpacked_sha256": unpacked_sha256,
            }
        ]
        for table in tables_info:
            if table["name"] == "schema_migrations":
                continue
            if not DATA_TABLE_NAME_RE.match(table["name"]):
                print(f"export: skipped table {table['name']} (unsafe name)", file=sys.stderr)
                continue
            csv_name = f"{table['name']}-{tag}.csv.gz"
            csv_path = gen_dir / csv_name
            row_count, replacements = _write_csv(snapshot_conn, table["name"], table["columns"], csv_path)
            if replacements:
                print(f"export: {table['name']}: {replacements} values had unencodable characters", file=sys.stderr)
            id_columns = [
                column["name"]
                for column in table["columns"]
                if column["pk"] or column["name"] == "id" or column["name"].endswith("_id")
            ]
            files.append(
                {
                    "name": csv_name,
                    "bytes": csv_path.stat().st_size,
                    "rows": row_count,
                    "sha256": _hash_file(csv_path),
                    "id_columns": id_columns,
                    "replacements": replacements,
                }
            )
            print(f"export: {csv_name} {row_count} rows {format_size_de(csv_path.stat().st_size)}", file=sys.stderr)

        manifest_tables = [
            {
                "name": table["name"],
                "rows": table["row_count"],
                "sql": table["sql"],
                "columns": [
                    {
                        "name": column["name"],
                        "type": column["type"],
                        "pk": column["pk"],
                        "notnull": column["notnull"],
                        "fk": next(
                            (
                                f"{fk['to_table']}.{fk['to_column']}"
                                for fk in table["foreign_keys"]
                                if fk["from"] == column["name"]
                            ),
                            None,
                        ),
                        "source": column_source(table["name"], column["name"]),
                    }
                    for column in table["columns"]
                ],
                "foreign_keys": table["foreign_keys"],
                "stable_keys": list(STABLE_KEYS.get(table["name"], ())),
                "per_build_keys": list(PER_BUILD_KEYS.get(table["name"], ())),
            }
            for table in tables_info
        ]

        recipe_rows: list[dict[str, Any]] = []
        for recipe in recipes:
            try:
                rows = [dict(row) for row in snapshot_conn.execute(recipe["sql"]).fetchall()]
            except sqlite3.Error as exc:
                raise RuntimeError(f"export: recipe {recipe['id']} failed: {exc}") from exc
            empty_reason = None
            if not rows:
                depends_on = recipe.get("depends_on")
                if depends_on and readiness.get(depends_on, "unavailable") == "unavailable":
                    empty_reason = f"nicht erfasst (Baustein nicht aktiviert): baue mit --enrich {depends_on}."
                else:
                    empty_reason = "keine Daten in diesem Build"
                print(f"export: recipe {recipe['id']}: 0 rows ({empty_reason})", file=sys.stderr)
            else:
                print(f"export: recipe {recipe['id']}: {len(rows)} rows", file=sys.stderr)
            recipe_rows.append(
                {
                    "id": recipe["id"],
                    "title": recipe["title"],
                    "sql": recipe["sql"],
                    "columns": [column["name"] for column in recipe["columns"]],
                    "rows": rows,
                    "empty_reason": empty_reason,
                }
            )

        protocols_count = int(snapshot_conn.execute("SELECT COUNT(*) FROM protocols").fetchone()[0])
        first_protocol = snapshot_conn.execute(
            "SELECT document_number, date FROM protocols ORDER BY date ASC, document_number ASC LIMIT 1"
        ).fetchone()
        last_protocol = snapshot_conn.execute(
            "SELECT document_number, date FROM protocols ORDER BY date DESC, document_number DESC LIMIT 1"
        ).fetchone()
        votes_count = int(snapshot_conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0])
        vote_members_count = int(snapshot_conn.execute("SELECT COUNT(*) FROM vote_members").fetchone()[0])
        relationships_count = sum(len(table["foreign_keys"]) for table in tables_info)
        total_rows = sum(table["row_count"] for table in tables_info)
    finally:
        snapshot_conn.close()
    vacuum_path.unlink()

    coverage_labels = {"ready": "erfasst", "partial": "teilweise erfasst", "unavailable": "nicht erfasst"}
    manifest: dict[str, Any] = {
        "export_format": EXPORT_FORMAT,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "commit": commit,
        "tag": tag,
        "license": license_text,
        "issues_url": issues_url,
        "transformation": "speeches.paragraphs_json entfernt (Duplikat von speeches.text, SQLite >= 3.35)",
        "source_mtime_ns": source_stat.st_mtime_ns,
        "source_bytes": source_stat.st_size,
        "source_sha256": source_sha256,
        "recipes_hash": recipes_hash,
        "inputs_hash": inputs_hash,
        "generation": generation,
        "schema_hash": schema_hash,
        "csv": {
            "encoding": "utf-8",
            "header": True,
            "null": "",
            "quoting": "minimal",
            "authoritative": "sqlite",
        },
        "files": files,
        "protocols": {
            "count": protocols_count,
            "first": first_protocol["document_number"] if first_protocol else None,
            "last": last_protocol["document_number"] if last_protocol else None,
            "from": first_protocol["date"] if first_protocol else None,
            "to": last_protocol["date"] if last_protocol else None,
        },
        "tables": manifest_tables,
        "relationships": relationships_count,
        "total_rows": total_rows,
        "votes": {"count": votes_count, "members": vote_members_count},
        "recipes": recipe_rows,
        "coverage": {
            "catalog_count": catalog_count,
            "dossier_count": dossier_count,
            "bausteine": {
                feature_id: coverage_labels.get(readiness.get(feature_id, "unavailable"), "nicht erfasst")
                for feature_id in ("votes", "aw-profiles", "mp-roster")
            },
            "synthetic_rede_ids": synthetic_rede_ids,
            "conflicting_votes": conflicting_votes,
        },
    }
    return manifest


# Fetch a manifest published at a URL (--data-manifest https://...): stdlib
# urllib, a 10 s timeout, no retries. Only ever called outside --offline. The
# body is capped so a misbehaving host cannot turn the build into an unbounded
# read (a real manifest is well under a megabyte).
MAX_REMOTE_MANIFEST_BYTES = 32 * 1024 * 1024


def load_remote_manifest(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 (operator-provided URL)
            payload = response.read(MAX_REMOTE_MANIFEST_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"error: could not fetch --data-manifest {url}: {exc}") from exc
    if len(payload) > MAX_REMOTE_MANIFEST_BYTES:
        raise RuntimeError(
            f"error: --data-manifest {url} exceeds {MAX_REMOTE_MANIFEST_BYTES // (1024 * 1024)} MB; refusing to parse it"
        )
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"error: --data-manifest {url} did not return valid JSON: {exc}") from exc


# "14.09.2026, 23:02 MESZ" plus the ISO string for <time datetime>. Falls back
# to UTC with an explicit label when the platform has no IANA tz database.
def format_datenstand_timestamp(generated_at: str) -> tuple[str, str]:
    try:
        parsed = datetime.fromisoformat(generated_at)
    except ValueError:
        return generated_at, generated_at
    try:
        localized = parsed.astimezone(ZoneInfo("Europe/Berlin"))
        label = "MESZ" if localized.dst() else "MEZ"
    except ZoneInfoNotFoundError:
        localized = parsed.astimezone(timezone.utc)
        label = "UTC"
    display = f"{localized:%d.%m.%Y}, {localized:%H:%M} {label}"
    return display, localized.isoformat()


def resolve_entity_link(
    link_kind: str | None,
    value: Any,
    *,
    mp_lookup: dict[str, int],
    document_numbers: set[str],
    bill_slugs: set[str],
) -> str | None:
    """Resolve an entity key into an href, or None when the target page does not
    exist in this build (the caller still renders the row, just as plain text).

    Shared by the recipe tables and the Fakten cards, which cite the same three
    entity kinds ("mp", "document", "proceeding") from their own receipts.
    """
    if value is None or link_kind is None:
        return None
    if link_kind == "mp":
        cid = mp_lookup.get(str(value))
        return f"abgeordnete/{cid}.html" if cid is not None else None
    if link_kind == "document":
        document_number = str(value)
        if document_number in document_numbers:
            return f"protocols/plenarprotokoll-{slugify_document_number(document_number)}.html"
        return None
    if link_kind == "proceeding":
        slug = bill_slug({"vorgang_id": value})
        return f"bills/{slug}.html" if slug in bill_slugs else None
    return None


def _truncate(text: str, limit: int) -> tuple[str, str | None]:
    if len(text) <= limit:
        return text, None
    return text[: limit - 1].rstrip() + "…", text


def render_daten_downloads(manifest: dict[str, Any], *, data_base_url: str, is_remote: bool) -> str:
    sqlite_file = manifest["files"][0]
    href = f"{data_base_url}{manifest['generation']}/{sqlite_file['name']}"
    csv_files = manifest["files"][1:]
    csv_rows = "".join(
        f"""
        <li class="file">
          <a href="{pulse_html.esc(data_base_url)}{pulse_html.esc(manifest['generation'])}/{pulse_html.esc(file['name'])}">{pulse_html.esc(file['name'])}</a>
          <span>{pulse_html.esc(format_size_de(file['bytes']))}</span>
        </li>
        """
        for file in csv_files
    )
    license_text = manifest.get("license") or ""
    license_line = (
        pulse_html.esc(license_text)
        if license_text
        else "Lizenzhinweis: siehe Quellen und Methode"
    )
    state_line = f"Release {manifest.get('tag') or '?'}" if is_remote else "lokaler Build"
    return f"""
      <div class="download-panel">
        <span class="eyebrow">Rohdaten &middot; {pulse_html.esc(state_line)}</span>
        <a class="button primary" href="{pulse_html.esc(href)}">SQLite herunterladen ({pulse_html.esc(format_size_de(sqlite_file['bytes']))})</a>
        <p class="file-meta">{pulse_html.esc(sqlite_file['name'])} &middot; {pulse_html.esc(format_size_de(sqlite_file['bytes']))} gepackt / {pulse_html.esc(format_size_de(sqlite_file['unpacked_bytes']))} entpackt</p>
        <p class="sha-label">sha256</p>
        <code class="sha">{pulse_html.esc(sqlite_file['sha256'])}</code>
        <details>
          <summary>CSV-Tabellen ({len(csv_files)})</summary>
          <ul class="file-list">{csv_rows}</ul>
        </details>
        <p class="transformation-note">{pulse_html.esc(manifest.get('transformation') or '')}</p>
        <p class="licence-line"><a href="sources.html#lizenz">{license_line}</a></p>
      </div>
    """


def render_daten_datenstand(manifest: dict[str, Any]) -> str:
    display, iso = format_datenstand_timestamp(manifest["generated_at"])
    protocols = manifest["protocols"]
    range_text = "&ndash;"
    if protocols.get("first") and protocols.get("last"):
        range_text = (
            f"{pulse_html.esc(protocols['first'])} bis {pulse_html.esc(protocols['last'])} &middot; "
            f"{pulse_html.esc(protocols.get('from') or '?')} bis {pulse_html.esc(protocols.get('to') or '?')}"
        )
    votes = manifest["votes"]
    coverage = manifest["coverage"]
    coverage_line = (
        f"{pulse_html.format_int(coverage['dossier_count'])} von {pulse_html.format_int(coverage['catalog_count'])} "
        "Protokollen im Katalog als Dossier erfasst"
    )
    bausteine_labels = {"votes": "Namentliche Abstimmungen", "aw-profiles": "abgeordnetenwatch-Profile", "mp-roster": "MdB-Kader"}
    bausteine_line = " &middot; ".join(
        f"{pulse_html.esc(bausteine_labels[key])}: {pulse_html.esc(value)}" for key, value in coverage["bausteine"].items()
    )
    provenance_bits = [f"Exportformat {manifest['export_format']}"]
    if manifest.get("commit"):
        provenance_bits.append(f"Commit {manifest['commit']}")
    provenance_line = " &middot; ".join(pulse_html.esc(bit) for bit in provenance_bits)
    return f"""
    <section class="summary-band">
      <div><span class="eyebrow">Datenstand</span><strong><time datetime="{pulse_html.esc(iso)}">{pulse_html.esc(display)}</time></strong></div>
      <div><span class="eyebrow">Plenarprotokolle</span><strong>{pulse_html.format_int(protocols['count'])}</strong><p class="tile-sub">{range_text}</p></div>
      <div><span class="eyebrow">Zeilen</span><strong>{pulse_html.format_int(manifest['total_rows'])}</strong><p class="tile-sub">{pulse_html.format_int(len(manifest['tables']))} Tabellen &middot; {pulse_html.format_int(manifest['relationships'])} Beziehungen</p></div>
      <div><span class="eyebrow">Namentliche Abstimmungen</span><strong>{pulse_html.format_int(votes['count'])}</strong><p class="tile-sub">{pulse_html.format_int(votes['members'])} Einzelstimmen</p></div>
    </section>
    <p class="coverage-line">{coverage_line}</p>
    <p class="bausteine-line">{bausteine_line}</p>
    <p class="provenance-line">{provenance_line}</p>
    """


def render_daten_recipes(
    manifest: dict[str, Any],
    *,
    mp_lookup: dict[str, int],
    document_numbers: set[str],
    bill_slugs: set[str],
) -> str:
    blocks = []
    for recipe_row in manifest["recipes"]:
        recipe = RECIPES_BY_ID.get(recipe_row["id"], {})
        columns = recipe.get("columns", ())
        visible_columns = [column for column in columns if not column.get("hidden")]
        rows = recipe_row["rows"]
        if not rows:
            body = f'<p class="recipe-empty">{pulse_html.esc(recipe_row["empty_reason"] or "keine Daten in diesem Build")}</p>'
        else:
            header = "".join(f"<th scope=\"col\">{pulse_html.esc(column['name'])}</th>" for column in visible_columns)
            body_rows = []
            link_column = next((column for column in columns if column.get("link")), None)
            for row in rows:
                link_href = None
                if link_column:
                    hidden_column = next((c for c in columns if c.get("hidden")), None)
                    key_value = row.get(hidden_column["name"]) if hidden_column else None
                    link_href = resolve_entity_link(
                        link_column.get("link"),
                        key_value,
                        mp_lookup=mp_lookup,
                        document_numbers=document_numbers,
                        bill_slugs=bill_slugs,
                    )
                cells = []
                for column in visible_columns:
                    value = row.get(column["name"])
                    if value is None:
                        cells.append('<td><span class="null">—</span></td>' if column["align"] != "num" else '<td class="num"><span class="null">—</span></td>')
                        continue
                    if column["align"] == "num":
                        if isinstance(value, float):
                            text_value = pulse_html.esc(str(value).replace(".", ","))
                        elif isinstance(value, int):
                            text_value = pulse_html.format_int(value)
                        else:
                            text_value = pulse_html.esc(value)
                        cells.append(f'<td class="num">{text_value}</td>')
                        continue
                    text_value = str(value)
                    title_attr = ""
                    if column.get("truncate"):
                        truncated, full = _truncate(text_value, column["truncate"])
                        if full is not None:
                            title_attr = f' title="{pulse_html.esc(full)}"'
                        text_value = truncated
                    escaped = pulse_html.esc(text_value)
                    if column is link_column and link_href:
                        cells.append(f'<td><a href="{pulse_html.esc(link_href)}"{title_attr}>{escaped}</a></td>')
                    else:
                        cells.append(f"<td{title_attr}>{escaped}</td>")
                body_rows.append(f"<tr>{''.join(cells)}</tr>")
            body = f"""
              <div class="table-scroll">
                <table>
                  <caption class="visually-hidden">{pulse_html.esc(recipe_row['title'])}</caption>
                  <thead><tr>{header}</tr></thead>
                  <tbody>{''.join(body_rows)}</tbody>
                </table>
              </div>
            """
        caveat = f'<p class="caveat">{pulse_html.esc(recipe.get("caveat"))}</p>' if recipe.get("caveat") else ""
        title_id = f"recipe-{pulse_html.esc(recipe_row['id'])}-title"
        blocks.append(
            f"""
            <section class="recipe" aria-labelledby="{title_id}">
              <div class="recipe-sql">
                <h3 id="{title_id}">{pulse_html.esc(recipe_row['title'])}</h3>
                <pre><code>{pulse_html.esc(recipe_row['sql'])}</code></pre>
              </div>
              <div class="recipe-result">
                {body}
                {caveat}
              </div>
            </section>
            """
        )
    return "".join(blocks)


def render_daten_schema(manifest: dict[str, Any]) -> tuple[str, str, str]:
    chips = "".join(
        f'<a href="#table-{pulse_html.esc(table["name"])}">{pulse_html.esc(table["name"])} <span>{pulse_html.format_int(table["rows"])}</span></a>'
        for table in manifest["tables"]
    )
    table_rows = []
    for table in manifest["tables"]:
        column_rows = "".join(
            f"""
            <tr>
              <td><code>{pulse_html.esc(column['name'])}</code></td>
              <td>{pulse_html.esc(column['type'] or 'untypisiert')}</td>
              <td>{pulse_html.esc(_column_hint(column))}</td>
            </tr>
            """
            for column in table["columns"]
        )
        description = DATABASE_TABLE_DESCRIPTIONS.get(table["name"], "Persistierte Tabelle aus dem Bundestag-Puls-Graph.")
        table_rows.append(
            f"""
            <div class="table-row" id="table-{pulse_html.esc(table['name'])}">
              <div class="table-row-head">
                <div>
                  <span class="table-name">{pulse_html.esc(table['name'])}</span>
                  <p>{pulse_html.esc(description)}</p>
                </div>
                <strong>{pulse_html.format_int(table['rows'])} Zeilen</strong>
              </div>
              <details>
                <summary>Spalten ({len(table['columns'])})</summary>
                <div class="table-scroll">
                  <table>
                    <thead><tr><th scope="col">Name</th><th scope="col">Typ</th><th scope="col">Hinweis</th></tr></thead>
                    <tbody>{column_rows}</tbody>
                  </table>
                </div>
              </details>
              <details>
                <summary>CREATE TABLE {pulse_html.esc(table['name'])}</summary>
                <pre>{pulse_html.esc(table['sql'])}</pre>
              </details>
            </div>
            """
        )

    relationship_rows_all = [
        {**fk, "table": table["name"]} for table in manifest["tables"] for fk in table["foreign_keys"]
    ]
    def render_relationship_row(item: dict[str, Any]) -> str:
        return f"""
        <tr>
          <td><a href="#table-{pulse_html.esc(item['table'])}">{pulse_html.esc(item['table'])}</a></td>
          <td><code>{pulse_html.esc(item['from'])}</code></td>
          <td><a href="#table-{pulse_html.esc(item['to_table'])}">{pulse_html.esc(item['to_table'])}</a>.<code>{pulse_html.esc(item['to_column'])}</code></td>
          <td>{pulse_html.esc(item['on_delete'])}</td>
        </tr>
        """
    visible_relationships = "".join(render_relationship_row(item) for item in relationship_rows_all[:8])
    hidden_relationships = "".join(render_relationship_row(item) for item in relationship_rows_all[8:])
    relationships_block = f"""
      <div class="table-scroll">
        <table>
          <caption class="visually-hidden">Fremdschlüssel</caption>
          <thead><tr><th scope="col">Tabelle</th><th scope="col">Spalte</th><th scope="col">Ziel</th><th scope="col">Löschen</th></tr></thead>
          <tbody>{visible_relationships}</tbody>
        </table>
      </div>
      {f'<details><summary>Alle {len(relationship_rows_all)} Beziehungen</summary><div class="table-scroll"><table><tbody>{hidden_relationships}</tbody></table></div></details>' if hidden_relationships else ''}
    """
    return chips, "".join(table_rows), relationships_block


def _column_hint(column: dict[str, Any]) -> str:
    flags = []
    if column["pk"]:
        flags.append("Primärschlüssel")
    if column.get("fk"):
        flags.append(f"→ {column['fk']}")
    if column["notnull"]:
        flags.append("Pflichtfeld")
    if column.get("source") and column["source"] != "dip":
        flags.append(column["source"])
    return ", ".join(flags) or "optional"


def _daten_page_styles() -> str:
    return """
    :root {
      --ink:#171a1f;
      --muted:#606a78;
      --line:#d9dee6;
      --paper:#f7f8fa;
      --panel:#ffffff;
      --blue:#174ea6;
      --teal:#0f766e;
      --surface-2:#f4f6f9;
      --surface-3:#e9edf2;
      --on-blue:#ffffff;
    }
    * { box-sizing:border-box; }
    body {
      margin:0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color:var(--ink);
      background:var(--paper);
      font-size:16px;
      line-height:1.55;
    }
    a { color:var(--blue); text-decoration:none; }
    a:hover { text-decoration:underline; }
    summary:focus-visible, .button:focus-visible {
      outline:2px solid var(--blue);
      outline-offset:2px;
    }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size:13px; }
    .shell { max-width:1360px; margin:0 auto; padding:28px 22px; }
    .visually-hidden {
      position:absolute; width:1px; height:1px; padding:0; margin:-1px;
      overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0;
    }
    .page-header {
      display:grid;
      grid-template-columns:minmax(0,1fr) 340px;
      gap:24px;
      align-items:start;
      padding-bottom:22px;
      border-bottom:1px solid var(--line);
    }
    .eyebrow {
      display:block;
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.08em;
      font-weight:700;
    }
    h1 { margin:6px 0 0; font-size:30px; line-height:1.1; }
    h2 { margin:0; font-size:20px; line-height:1.2; }
    h3 { margin:0 0 8px; font-size:16px; font-weight:650; }
    p { margin:8px 0 0; color:var(--muted); }
    .lede { max-width:68ch; }
    .button {
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-height:44px;
      padding:8px 16px;
      border:1px solid var(--blue);
      border-radius:8px;
      background:var(--blue);
      color:var(--on-blue);
      font-weight:700;
    }
    .download-panel { display:grid; gap:8px; padding:16px; border:1px solid var(--line); border-radius:10px; background:var(--panel); }
    .file-meta, .sha-label { font-size:14px; margin-top:10px; }
    .sha-label { margin-bottom:0; color:var(--muted); }
    code.sha { display:block; overflow-wrap:anywhere; font-size:13px; background:var(--surface-2); padding:8px; border-radius:6px; }
    .file-list { list-style:none; margin:0; padding:0; display:grid; gap:0; }
    .file { display:flex; justify-content:space-between; gap:10px; padding:6px 0; border-bottom:1px dotted var(--line); font-size:14px; background:var(--surface-2); }
    .file:last-child { border-bottom:none; }
    .transformation-note, .licence-line { font-size:14px; }
    main { display:block; }
    .rule-section { border-top:1px solid var(--line); padding-top:20px; margin-top:28px; }
    .summary-band {
      display:grid;
      grid-template-columns:repeat(4, minmax(0,1fr));
      gap:12px;
    }
    .summary-band div { border:1px solid var(--line); border-radius:8px; background:var(--panel); padding:13px 14px; }
    .summary-band strong { display:block; margin-top:4px; font-size:26px; font-variant-numeric:tabular-nums; }
    .tile-sub { font-size:12px; margin-top:2px; }
    .coverage-line, .bausteine-line, .provenance-line { font-size:14px; }
    .table-nav { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
    .table-nav a {
      display:inline-flex;
      min-height:32px;
      align-items:center;
      gap:7px;
      padding:4px 9px;
      border:1px solid var(--line);
      border-radius:999px;
      background:var(--panel);
      font-size:12px;
      font-weight:700;
    }
    .table-nav span { color:var(--muted); font-weight:650; }
    .recipes { display:grid; gap:24px; margin-top:18px; }
    .recipe {
      display:grid;
      grid-template-columns:minmax(0,2fr) minmax(0,3fr);
      gap:20px;
      padding-top:18px;
      border-top:1px solid var(--line);
    }
    .recipe:first-child { border-top:none; padding-top:0; }
    .recipe pre { margin:8px 0 0; padding:12px; background:var(--surface-2); border-radius:8px; overflow:auto; font-size:13px; line-height:1.5; white-space:pre-wrap; overflow-wrap:anywhere; }
    .recipe-empty { font-size:14px; }
    table { width:100%; border-collapse:collapse; font-size:14px; }
    th, td { padding:8px; border-bottom:1px solid var(--surface-3); text-align:left; vertical-align:top; }
    th { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-weight:600; font-size:13px; color:var(--muted); white-space:nowrap; }
    td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
    .table-scroll { max-width:100%; overflow-x:auto; }
    .table-scroll table { min-width:28rem; }
    .caveat { font-size:14px; margin-top:8px; }
    .null { color:var(--muted); }
    .loslegen pre { margin:8px 0 0; padding:12px; background:var(--surface-2); border-radius:8px; overflow:auto; font-size:13px; line-height:1.5; }
    .table-row { border-bottom:1px solid var(--line); padding:16px 0; }
    .table-row-head { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:16px; align-items:start; }
    .table-name { font-size:16px; font-weight:650; }
    details { margin-top:10px; }
    summary { cursor:pointer; color:var(--blue); font-weight:650; min-height:40px; display:flex; align-items:center; }
    details pre { margin:8px 0 0; padding:12px; background:var(--surface-2); border-radius:8px; overflow:auto; white-space:pre-wrap; overflow-wrap:anywhere; font-size:13px; line-height:1.45; }
    footer { padding-top:24px; margin-top:24px; border-top:1px solid var(--line); color:var(--muted); font-size:14px; }
    @media print {
      .site-header, .download-panel { display:none; }
    }
    @media screen and (max-width: 1024px) {
      .recipe { grid-template-columns:minmax(0,1fr); }
    }
    @media screen and (max-width: 900px) {
      .page-header { grid-template-columns:minmax(0,1fr); }
      .summary-band { grid-template-columns:repeat(2, minmax(0,1fr)); }
    }
    @media screen and (max-width: 480px) {
      .summary-band { grid-template-columns:minmax(0,1fr); }
      .table-nav a { flex:1 1 auto; }
      .file { flex-wrap:wrap; }
    }
    """


def render_database_page(
    manifest: dict[str, Any],
    *,
    data_base_url: str = "data/exports/",
    mp_lookup: dict[str, int] | None = None,
    document_numbers: set[str] | None = None,
    bill_slugs: set[str] | None = None,
    is_remote: bool = False,
    features: Selection | None = None,
) -> str:
    features = features or publication_selection()
    mp_lookup = mp_lookup or {}
    document_numbers = document_numbers or set()
    bill_slugs = bill_slugs or set()

    chips, table_rows_html, relationships_block = render_daten_schema(manifest)
    downloads_html = render_daten_downloads(manifest, data_base_url=data_base_url, is_remote=is_remote)
    datenstand_html = render_daten_datenstand(manifest)
    recipes_html = render_daten_recipes(
        manifest, mp_lookup=mp_lookup, document_numbers=document_numbers, bill_slugs=bill_slugs
    )

    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Daten</title>
  {pulse_html.page_head(features)}
  <style>
    {_daten_page_styles()}
    {pulse_html.global_header_styles()}
  </style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(active="database", features=features)}
    <main>
      <header class="page-header">
        <div>
          <span class="eyebrow">Rohdaten</span>
          <h1>Daten</h1>
          <p class="lede">Alle Personen, Reden, Vorgänge und namentlichen Abstimmungen, aus denen diese Website aufgebaut ist, als SQLite-Datei und als CSV &mdash; dieselben Daten, die hinter den Ansichten dieser Website stehen.</p>
        </div>
        {downloads_html}
      </header>
      <section class="rule-section">
        <span class="eyebrow">Datenstand</span>
        {datenstand_html}
      </section>
      <section class="rule-section">
        <span class="eyebrow">Fünf Abfragen</span>
        <h2>Rezepte</h2>
        <p class="lede">Diese fünf SQL-Abfragen laufen bei jedem Build gegen die Verteilkopie; ihre Ergebniszeilen stehen rechts daneben. Wer die Datei herunterlädt und die SQL <a href="#loslegen">lokal aus</a>führt, bekommt dieselben Zeilen.</p>
        <div class="recipes">{recipes_html}</div>
      </section>
      <section class="rule-section loslegen" id="loslegen">
        <span class="eyebrow">So geht's los</span>
        <h2>Drei Wege zu den Daten</h2>
        <p>Shell (sqlite3):</p>
        <pre><code>curl -LO {pulse_html.esc(data_base_url)}{pulse_html.esc(manifest['generation'])}/{pulse_html.esc(manifest['files'][0]['name'])}
gunzip {pulse_html.esc(manifest['files'][0]['name'])}
sqlite3 -header -column {pulse_html.esc(manifest['files'][0]['name'].removesuffix('.gz'))}</code></pre>
        <p>Python (stdlib):</p>
        <pre><code>import gzip, shutil, sqlite3, urllib.request
url = "{pulse_html.esc(data_base_url)}{pulse_html.esc(manifest['generation'])}/{pulse_html.esc(manifest['files'][0]['name'])}"
urllib.request.urlretrieve(url, "bundestag-pulse.sqlite.gz")
with gzip.open("bundestag-pulse.sqlite.gz", "rb") as src, open("bundestag-pulse.sqlite", "wb") as dst:
    shutil.copyfileobj(src, dst)
conn = sqlite3.connect("bundestag-pulse.sqlite")
print(conn.execute("SELECT COUNT(*) FROM protocols").fetchone())</code></pre>
        <p>Pandas:</p>
        <pre><code>import pandas as pd, sqlite3
conn = sqlite3.connect("bundestag-pulse.sqlite")
speeches = pd.read_sql("SELECT * FROM speeches", conn)
# CSV alternative: pd.read_csv("speeches-local.csv.gz", keep_default_na=False, dtype={{"mp_id": "Int64"}})</code></pre>
        <p>SQLite ist die maßgebliche Quelle; die CSV-Dateien sind ein verbatim Export ohne Formel-Escaping &mdash; beim Import in Tabellenkalkulationen als Text behandeln.</p>
      </section>
      <section class="rule-section">
        <span class="eyebrow">Schema</span>
        <h2>{len(manifest['tables'])} Tabellen</h2>
        <div class="table-nav">{chips}</div>
        {table_rows_html}
        <h2>Beziehungen</h2>
        {relationships_block}
      </section>
      <footer>
        Diese Seite ist statisch aus der Verteilkopie der SQLite-Datenbank erzeugt. Sie führt keine SQL-Abfragen im Browser aus. <a href="sources.html">Quellen und Methode</a> · <a href="index.html">Start</a>{f' · <a href="{pulse_html.esc(safe_issues_url(manifest.get("issues_url")))}">Fragen und Fehler</a>' if safe_issues_url(manifest.get("issues_url")) else ''}
      </footer>
    </main>
  </div>
  {pulse_html.page_scripts(features)}
</body>
</html>
"""


# Fallback for database.html when there is no manifest to render from: either
# the build ran with --no-persist, or the store exists but export_distribution_data
# raised DataExportUnavailable (old SQLite) - `reason` carries which.
def render_database_unavailable_page(features: Selection, *, reason: str | None = None) -> str:
    body = (
        reason
        or "Dieser Build wurde mit <code>--no-persist</code> gerendert. Ohne SQLite-Datei stehen Downloads, "
        "Datenstand und Rezepte in dieser Vorschau nicht zur Verfügung."
    )
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Daten</title>
  {pulse_html.page_head(features)}
  <style>
    :root {{ --ink:#171a1f; --muted:#606a78; --line:#d9dee6; --paper:#f7f8fa; --panel:#ffffff; --blue:#174ea6; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter, ui-sans-serif, system-ui, sans-serif; color:var(--ink); background:var(--paper); }}
    a {{ color:var(--blue); }}
    .shell {{ max-width:980px; margin:0 auto; padding:24px; }}
    {pulse_html.global_header_styles()}
    .panel {{ margin-top:32px; padding:24px; border:1px solid var(--line); border-radius:10px; background:var(--panel); }}
    .panel h1 {{ margin-top:0; }}
    .panel p {{ color:var(--muted); line-height:1.55; }}
  </style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(active="database", features=features)}
    <main class="panel">
      <span class="eyebrow">Primärquellen</span>
      <h1>Daten nicht erzeugt</h1>
      <p>{body}</p>
      <p>Erzeuge die Vorschau ohne <code>--no-persist</code>, um diese Seite zu füllen.</p>
    </main>
  </div>
  {pulse_html.page_scripts(features)}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# PAGE: index.html - the explanatory home page
#
# Not a data view: it states what Bundestag-Puls is, the four principles it
# claims to follow, and links out to every other area of the site.
# ---------------------------------------------------------------------------


def render_landing_page(
    entries: list[dict[str, Any]],
    *,
    database_page_href: str | None = None,
    data_stand: str | None = None,
    protocol_count: int = 0,
    bill_count: int = 0,
    features: Selection | None = None,
) -> str:
    """Explanatory home page: what Bundestag-Puls is, its principles, and links to every subpart."""
    features = features or publication_selection()
    # Right-hand "Aktueller Puls" card: a snapshot of the newest generated
    # dossier (entries are ordered newest-first by render_site), or a placeholder
    # when nothing has been generated yet.
    if entries:
        entry = entries[0]
        report = entry["report"]
        protocol = report.get("protocol") or {}
        summary = report.get("validation_summary") or {}
        snapshot = f"""
        <aside class="snapshot">
          <span class="eyebrow">Aktueller Puls</span>
          <strong class="snapshot-doc">BT-PlPr {pulse_html.esc(protocol.get('dokumentnummer'))}</strong>
          <p class="snapshot-title">{pulse_html.esc(pulse_html.short(protocol.get('titel'), 96))}</p>
          <p class="snapshot-date">Sitzung vom {pulse_html.esc(protocol.get('datum'))}</p>
          <div class="snapshot-metrics">
            <div><span>Tagesordnung</span><strong>{pulse_html.esc(summary.get('xml_top_count'))}</strong></div>
            <div><span>Reden</span><strong>{pulse_html.esc(summary.get('xml_speech_count'))}</strong></div>
            <div><span>Drucksachen</span><strong>{pulse_html.esc(summary.get('xml_drucksache_count'))}</strong></div>
            <div><span>Personen</span><strong>{pulse_html.esc(summary.get('unique_person_ids'))}</strong></div>
          </div>
          <a class="snapshot-link" href="puls.html">Was gerade l&auml;uft &rarr;</a>
        </aside>
        """
    else:
        snapshot = """
        <aside class="snapshot">
          <span class="eyebrow">Aktueller Puls</span>
          <p class="snapshot-title">Es wurde noch keine Sitzung erzeugt.</p>
          <p class="snapshot-date">Sobald ein Plenarprotokoll ausgewertet ist, erscheint hier der aktuelle Lageblick.</p>
          <a class="snapshot-link" href="puls.html">Was gerade l&auml;uft &rarr;</a>
        </aside>
        """

    # "Prinzipien" section - static editorial copy, four numbered cards.
    principles = [
        (
            "Nur Primärquellen",
            "Aufgebaut aus offiziellen Plenarprotokollen, Drucksachen und namentlichen Abstimmungen — niemals aus Nachrichtenberichten oder Kommentaren.",
        ),
        (
            "Jede Aussage belegbar",
            "Jede Kennzahl und jeder Auszug ist einen Klick von der exakten Protokollstelle oder Drucksache entfernt, aus der sie stammt.",
        ),
        (
            "Neutral und nicht-autoritativ",
            "Mechanische Kennzahlen statt unbelegter Haltungs-Aussagen. KI-Zusammenfassungen sind gekennzeichnet und immer mit zitierten Quellen hinterlegt.",
        ),
        (
            "Automatisch aktuell",
            "Eine geplante Pipeline holt neue Plenarprotokolle aus der DIP-API, wertet sie aus und veröffentlicht sie — ein veralteter Monitor wäre wertlos.",
        ),
    ]
    principle_cards = "".join(
        f"""
        <article class="principle">
          <span class="num">{i}</span>
          <h3>{pulse_html.esc(title)}</h3>
          <p>{pulse_html.esc(desc)}</p>
        </article>
        """
        for i, (title, desc) in enumerate(principles, start=1)
    )

    # "Bereiche" section - the navigation cards. Optional areas are inserted
    # only when the corresponding artifact exists,
    # so the home page never links to a page this build did not write.
    areas = [
        (
            "Wochenradar",
            "Aktueller Puls",
            "puls.html",
            "Worüber der Bundestag in der neuesten Sitzungswoche am meisten gesprochen hat: die Themen nach Redezahl, jede Zeile mit Beleg im Protokoll, dazu der Wochenvergleich.",
            None,
        ),
        (
            "Archiv",
            "Plenarprotokoll-Katalog",
            "overview.html",
            "Der vollständige Katalog aller Plenarprotokolle aus der DIP-API mit erzeugten Dossiers je Sitzung: Tagesordnung, Rednerinnen und Redner, verknüpfte Drucksachen und Roh-API-Daten.",
            None,
        ),
        (
            "Transparenz",
            "Quellen und Methode",
            "sources.html",
            "Welche offiziellen Quellen genutzt werden, wie sie verarbeitet werden und was bewusst ausgeschlossen bleibt — die Grundlage für das Neutralitätsversprechen.",
            None,
        ),
    ]
    if "bills" in features:
        areas.insert(
            2,
            (
                "Gesetzgebung",
                "Gesetze verfolgen",
                "bills/index.html",
                "Verfolge einzelne Vorgänge von der Drucksache über die Plenardebatte bis zur namentlichen Abstimmung. Gefolgte Gesetze werden lokal im Browser gemerkt.",
                None,
            ),
        )
    if database_page_href:
        areas.append(
            (
                "Transparenz",
                "Daten",
                database_page_href,
                "Downloads, Datenstand und fünf geprüfte SQL-Abfragen zu Personen, Reden, Vorgängen und Abstimmungen.",
                data_stand,
            )
        )
    area_cards = "".join(
        f"""
        <a class="area-card" href="{pulse_html.esc(href)}">
          <span class="eyebrow">{tag}</span>
          <h3>{title}</h3>
          <p>{pulse_html.esc(desc)}</p>
          {f'<p class="area-meta">{pulse_html.esc(meta)}</p>' if meta else ''}
          <span class="area-go">&Ouml;ffnen &rarr;</span>
        </a>
        """
        for tag, title, href, desc, meta in areas
    )

    # Page anatomy, top to bottom:
    #   global header
    #   hero        -> headline, lead paragraph, two CTAs + the snapshot card
    #   stat band   -> sitting / dossier / bill counters
    #   block 1     -> "Was ist Bundestag-Puls?" prose
    #   block 2     -> the principle cards
    #   block 3     -> the area cards
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Primärquellen-Monitor des Bundestags</title>
  {pulse_html.page_head(features)}
  <style>
    :root {{
      --ink:#171a1f;
      --muted:#606a78;
      --line:#d9dee6;
      --paper:#f7f8fa;
      --panel:#ffffff;
      --blue:#174ea6;
      --teal:#0f766e;
      --blue-soft:#eef5ff;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color:var(--ink);
      background:var(--paper);
    }}
    a {{ color:var(--blue); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .shell {{ max-width:1180px; margin:0 auto; padding:22px 22px 48px; }}
    {pulse_html.global_header_styles()}
    .eyebrow {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.05em; font-weight:700; }}
    .hero {{
      display:grid;
      grid-template-columns:minmax(0,1.5fr) minmax(300px,1fr);
      gap:30px;
      align-items:center;
      padding:46px 0 36px;
      border-bottom:1px solid var(--line);
    }}
    .hero h1 {{ margin:12px 0 0; font-size:46px; line-height:1.05; font-weight:820; letter-spacing:-.02em; }}
    .hero .lead {{ margin:18px 0 0; max-width:620px; font-size:17px; line-height:1.55; color:#3b4452; }}
    .cta-row {{ display:flex; flex-wrap:wrap; gap:12px; margin-top:26px; }}
    .btn {{
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-height:46px;
      padding:10px 20px;
      border-radius:8px;
      border:1px solid var(--line);
      background:#fff;
      font-weight:750;
      font-size:15px;
      color:var(--ink);
    }}
    .btn:hover {{ text-decoration:none; }}
    .btn-primary {{ background:var(--blue); border-color:var(--blue); color:#fff; }}
    .btn-primary:hover {{ background:#123e85; }}
    .btn-ghost:hover {{ border-color:#bdd0ea; background:var(--blue-soft); }}
    .snapshot {{
      border:1px solid var(--line);
      border-left:4px solid var(--teal);
      border-radius:12px;
      background:var(--panel);
      padding:20px;
    }}
    .snapshot-doc {{ display:block; margin-top:6px; font-size:15px; }}
    .snapshot-title {{ margin:8px 0 0; color:var(--ink); font-size:15px; line-height:1.35; font-weight:650; }}
    .snapshot-date {{ margin:4px 0 0; color:var(--muted); font-size:13px; }}
    .snapshot-metrics {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:16px 0; }}
    .snapshot-metrics div {{ border:1px solid #e2e7ef; border-radius:8px; background:#fbfcfd; padding:8px 10px; }}
    .snapshot-metrics span {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.04em; }}
    .snapshot-metrics strong {{ display:block; margin-top:3px; font-size:20px; }}
    .snapshot-link {{ font-weight:750; font-size:14px; }}
    .stat-band {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-top:28px; }}
    .stat-band div {{ border:1px solid var(--line); border-radius:10px; background:var(--panel); padding:14px 16px; }}
    .stat-band span {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
    .stat-band strong {{ display:block; margin-top:5px; font-size:26px; font-weight:780; }}
    section.block {{ padding:42px 0 0; }}
    section.block > .eyebrow {{ display:block; }}
    section.block h2 {{ margin:8px 0 0; font-size:26px; font-weight:780; letter-spacing:-.01em; }}
    section.block > p.intro {{ margin:10px 0 0; max-width:700px; color:var(--muted); font-size:15px; line-height:1.55; }}
    .principles {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-top:24px; }}
    .principle {{ border:1px solid var(--line); border-radius:10px; background:var(--panel); padding:18px; }}
    .principle .num {{
      display:inline-flex;
      align-items:center;
      justify-content:center;
      width:30px;
      height:30px;
      border-radius:8px;
      background:var(--blue-soft);
      color:var(--blue);
      font-weight:800;
      font-size:14px;
      margin-bottom:12px;
    }}
    .principle h3 {{ margin:0; font-size:16px; font-weight:740; }}
    .principle p {{ margin:8px 0 0; color:var(--muted); font-size:14px; line-height:1.5; }}
    .areas {{ display:grid; grid-template-columns:repeat(2,1fr); gap:16px; margin-top:24px; }}
    .area-card {{
      display:flex;
      flex-direction:column;
      border:1px solid var(--line);
      border-radius:12px;
      background:var(--panel);
      padding:22px;
      color:var(--ink);
      transition:border-color .12s, box-shadow .12s, transform .12s;
    }}
    .area-card:hover {{
      text-decoration:none;
      border-color:#bdd0ea;
      box-shadow:0 8px 24px rgba(23,26,31,.07);
      transform:translateY(-2px);
    }}
    .area-card h3 {{ margin:8px 0 0; font-size:20px; font-weight:760; }}
    .area-card p {{ margin:10px 0 0; color:var(--muted); font-size:14px; line-height:1.5; flex:1; }}
    .area-go {{ margin-top:16px; color:var(--blue); font-weight:750; font-size:14px; }}
    footer {{ margin-top:48px; padding-top:20px; border-top:1px solid var(--line); color:var(--muted); font-size:12px; line-height:1.6; }}
    @media (max-width: 900px) {{
      .hero {{ grid-template-columns:1fr; padding:30px 0 28px; }}
      .principles {{ grid-template-columns:1fr 1fr; }}
      .areas {{ grid-template-columns:1fr; }}
    }}
    @media (max-width: 600px) {{
      .shell {{ padding:16px 14px 40px; }}
      .hero h1 {{ font-size:34px; }}
      .principles, .stat-band {{ grid-template-columns:1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(features=features)}

    <section class="hero">
      <div class="hero-copy">
        <span class="eyebrow">Deutscher Bundestag · aus offiziellen Quellen</span>
        <h1>Was der Bundestag tut — mit Belegen.</h1>
        <p class="lead">Bundestag-Puls verdichtet die verstreute offizielle Tätigkeit des Parlaments — Reden, Gesetzentwürfe, Ausschussschritte und namentliche Abstimmungen — zu einem lesbaren Bild davon, worauf sich die parlamentarische Aufmerksamkeit gerade richtet und wer wofür steht. Aufgebaut ausschließlich aus Primärquellen, nicht aus Nachrichten.</p>
        <div class="cta-row">
          <a class="btn btn-primary" href="puls.html">Was gerade l&auml;uft</a>
          <a class="btn btn-ghost" href="sources.html">Wie wir arbeiten</a>
        </div>
      </div>
      {snapshot}
    </section>

    <section class="stat-band" aria-label="Kennzahlen">
      <div><span>API-Sitzungen</span><strong>{pulse_html.esc(protocol_count)}</strong></div>
      <div><span>Erzeugte Dossiers</span><strong>{pulse_html.esc(len(entries))}</strong></div>
      <div><span>Verfolgte Gesetze</span><strong>{pulse_html.esc(bill_count)}</strong></div>
      <div><span>Quellenart</span><strong>Primärquellen</strong></div>
    </section>

    <section class="block">
      <span class="eyebrow">Was ist Bundestag-Puls?</span>
      <h2>Ein zusammenhängendes Bild statt Fragmenten</h2>
      <p class="intro">Eine Rede, ein Gesetzentwurf, ein Ausschussschritt, eine namentliche Abstimmung — einzeln sind sie öffentlich, aber schwer lesbar. Bundestag-Puls fügt sie zu einem Bild zusammen: „Was passiert dort gerade, und wer stand wo?“ Wie ein ziviler Radar für parlamentarische Aufmerksamkeit — jede Aussage einen Klick von ihrer Primärquelle entfernt.</p>
    </section>

    <section class="block">
      <span class="eyebrow">Prinzipien</span>
      <h2>Worauf dieses Projekt aufbaut</h2>
      <div class="principles">{principle_cards}</div>
    </section>

    <section class="block">
      <span class="eyebrow">Bereiche</span>
      <h2>Was du hier findest</h2>
      <p class="intro">Alle Ansichten greifen auf dieselben verknüpften Primärdaten zu — wähle die passende Perspektive.</p>
      <div class="areas">{area_cards}</div>
    </section>

    <footer>
      Statischer Prototyp · Bundestag-Puls. Das XML-Protokoll ist maßgeblich; DIP-API-Daten ergänzen jede Sitzung. Datenquellen und Methode sind unter <a href="sources.html">Quellen</a> dokumentiert.
    </footer>
  </div>
  {pulse_html.page_scripts(features)}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# PAGE: puls.html - "Was der Bundestag in KW 24/2026 verhandelt hat"
#
# The week radar: one ISO sitting week (the newest dated one, or --week), its
# agenda items ranked by speech count with the DIP Vorgang titles as names and
# a receipt on every row, then the Wochenvergleich band against the previous
# sitting week. Older weeks live in the catalog pages instead. Design record:
# docs/designs/puls-wochenradar.md.
# ---------------------------------------------------------------------------


# How many returning procedures the Wochenvergleich band lists before it stops.
RETURNING_LIMIT = 5


# The comparison uses sums, either for whole weeks or shared weekdays.
def week_figure(value: float) -> str:
    return pulse_html.format_int(int(round(value)))


# ---------------------------------------------------------------------------
# The "Wochenvergleich" band under the radar.
#
# Five cards, all of them plain aggregates over the dossiers of two sitting
# weeks: the volume pulse with a 12-week sparkline, the shift in each fraction's
# share of speaking, the mix of business types, the procedures that came back
# from an earlier week, and the week's roll-call votes. Every row that names a
# sitting links to the agenda item it came from, so each number stays one click
# from its source. Without a comparison week the band still shows the current
# week's Wochenpuls, Redeanteil and votes, just without deltas or a sparkline.
# ---------------------------------------------------------------------------
def render_votes_card(stats: dict[str, Any], newest_href: str) -> str:
    """The week's roll-call votes, counted by vote id across every sitting.

    Rendered in both band states and gated client-side through
    id="abstimmungen" stays an external deep-link target.
    """
    count = int(stats.get("vote_count") or 0)
    if count:
        sentence = (
            f"{pulse_html.format_count(count, 'namentliche Abstimmung', 'namentliche Abstimmungen')} in "
            f"{pulse_html.format_count(int(stats.get('vote_top_count') or 0), 'Tagesordnungspunkt', 'Tagesordnungspunkten')}"
            " dieser Woche"
        )
        rows = []
        for label, page_path, first_index, n in stats.get("vote_sittings") or []:
            href = f"protocols/{pulse_html.esc(Path(page_path).name)}#top-{pulse_html.esc(first_index)}"
            rows.append(
                f'<li class="vote-row"><a href="{href}">{pulse_html.esc(label)} · '
                f"{pulse_html.format_count(n, 'Abstimmung', 'Abstimmungen')}</a></li>"
            )
        body = f'<p class="week-text">{pulse_html.esc(sentence)}</p><ul class="week-list">{"".join(rows)}</ul>'
    else:
        body = (
            '<p class="week-text">Keine namentlichen Abstimmungen in dieser Sitzungswoche erfasst.</p>'
            f'<a class="feature-link" href="{newest_href}">Sitzungsbelege pr&uuml;fen</a>'
        )
    return f"""
        <article class="week-card votes-card" id="abstimmungen">
          <span class="eyebrow">Erfasst</span>
          <h3>Namentliche Abstimmungen</h3>
          {body}
        </article>"""


def _speakers_note(stats: dict[str, Any]) -> str:
    """" Fraktionen für N von M Reden erfasst." when a week's speaker lists are cut short."""
    if stats.get("speakers_complete", True):
        return ""
    recorded = sum(stats["party_counts"].values())
    return (
        f" Fraktionen f&uuml;r {pulse_html.format_int(recorded)} von "
        f"{pulse_html.format_count(stats['speech_count'], 'Rede', 'Reden')} erfasst."
    )


def render_week_comparison_section(
    comparison: dict[str, Any] | None,
    weeks: dict[tuple[int, int], list[dict[str, Any]]],
    current_week: tuple[int, int] | None,
    *,
    current_stats: dict[str, Any] | None = None,
    features: Selection | None = None,
    returning: list[dict[str, Any]] | None = None,
) -> str:
    votes_card = ""
    if current_stats is not None and current_week is not None and features is not None and "votes" in features:
        newest = weeks[current_week][-1]
        votes_card = render_votes_card(current_stats, f"protocols/{pulse_html.esc(Path(newest['page_path']).name)}")

    if not comparison:
        note = (
            "Für einen Wochenvergleich braucht es zwei Sitzungswochen, die höchstens "
            f"{pulse_html.MAX_WEEK_GAP} Wochen auseinanderliegen. In den erzeugten Auswertungen "
            "ist bisher nur eine solche Woche vorhanden."
        )
        cards = ""
        if current_stats is not None:
            # No previous week means no deltas and no sparkline: week_comparison()
            # returns None and week_sparkline_points() is not gap-limited, so both
            # are built here straight from the current week's stats.
            metric_cells = []
            for key, label, _kind in pulse_html.WEEK_METRICS:
                if key == "total_chars" and not current_stats["chars_complete"]:
                    continue
                metric_cells.append(
                    f"""
              <div class="week-metric">
                <span>{pulse_html.esc(label)}</span>
                <strong>{week_figure(current_stats[key])}</strong>
                <div class="week-metric-foot">{pulse_html.render_delta(None)}</div>
              </div>"""
                )
            cards = f"""
      <div class="week-grid">
        <article class="week-card">
          <h3>Wochenpuls</h3>
          <div class="week-metrics">{"".join(metric_cells)}</div>
          <p class="week-note">Diese Sitzungswoche; ein Vergleichswert folgt mit der n&auml;chsten Sitzungswoche.</p>
        </article>
        <article class="week-card">
          <h3>Redeanteil der Fraktionen</h3>
          {pulse_html.render_share_shift(current_stats["party_counts"], None)}
          <p class="week-note">Anteil an allen Reden der Woche.{_speakers_note(current_stats)}</p>
        </article>{votes_card}
      </div>"""
        return f"""
    <section class="week-compare" id="wochenvergleich" aria-labelledby="wochenvergleich-h2">
      <div class="week-head">
        <div>
          <span class="eyebrow">Wochenvergleich</span>
          <h2 id="wochenvergleich-h2">Noch keine Vergleichswoche</h2>
        </div>
      </div>
      <p class="week-note">{pulse_html.esc(note)}</p>{cards}
    </section>
"""

    current = comparison["current"]
    previous = comparison["previous"]
    basis = comparison["basis"]
    compared_current = comparison["compared_current"]
    compared_previous = comparison["compared_previous"]

    # Volume metrics and deltas use the same comparison basis as the shares.
    metric_cells = []
    for metric in comparison["metrics"]:
        metric_cells.append(
            f"""
              <div class="week-metric">
                <span>{pulse_html.esc(metric["label"])}</span>
                <strong>{week_figure(metric["current"])}</strong>
                <div class="week-metric-foot">
                  {pulse_html.render_delta(metric["delta_percent"], "%")}
                  <em>{pulse_html.esc(previous["label"])}: {week_figure(metric["previous"])}</em>
                </div>
              </div>"""
        )

    points = pulse_html.week_sparkline_points(weeks, current_week) if current_week else []

    # Procedures carried over from an earlier sitting week. The list is capped for
    # display, but the note below counts every one of them.
    if returning is None:
        returning = pulse_html.returning_vorgaenge(weeks, current_week) if current_week else []
    shown = returning[:RETURNING_LIMIT]
    if shown:
        rows = []
        for row in shown:
            first = row["first"]
            latest = row["latest"]
            first_href = f"protocols/{pulse_html.esc(Path(first['page_path']).name)}#top-{pulse_html.esc(first['index'])}"
            latest_href = f"protocols/{pulse_html.esc(Path(latest['page_path']).name)}#top-{pulse_html.esc(latest['index'])}"
            rows.append(
                f"""
              <li class="week-row return-row">
                <span class="week-label">{pulse_html.esc(row["vorgangstyp"])}</span>
                <strong>{pulse_html.esc(pulse_html.short(row["titel"], 110))}</strong>
                <span class="week-trace">
                  <a href="{first_href}">{pulse_html.esc(first["label"])} · {pulse_html.esc(first["vorgangsposition"])}</a>
                  <em>&rarr;</em>
                  <a href="{latest_href}">{pulse_html.esc(latest["label"])} · {pulse_html.esc(latest["vorgangsposition"])}</a>
                </span>
              </li>"""
            )
        returning_html = f'<ul class="week-list">{"".join(rows)}</ul>'
        returning_note = (
            f"{len(returning)} von {len(current['vorgang_ids'])} Verfahren dieser Woche "
            "standen schon in einer früheren Sitzungswoche auf der Tagesordnung."
        )
        if len(shown) < len(returning):
            returning_note += f" Angezeigt sind die {len(shown)} zuletzt fortgesetzten."
    else:
        returning_html = ""
        returning_note = (
            "Kein Verfahren dieser Sitzungswoche stand zuvor schon einmal auf der Tagesordnung "
            "der erzeugten Auswertungen."
        )

    sittings_note = (
        f"{current['sitting_count']} Sitzung{'' if current['sitting_count'] == 1 else 'en'} "
        f"({pulse_html.esc(', '.join(d for d in current['documents'] if d))}) gegenüber "
        f"{previous['sitting_count']} Sitzung{'' if previous['sitting_count'] == 1 else 'en'} in {pulse_html.esc(previous['label'])}."
    )
    if basis == "weekdays":
        days = comparison["weekdays"]
        day_label = (
            f"{pulse_html.WEEKDAY_SHORT[days[0]]}–{pulse_html.WEEKDAY_SHORT[days[-1]]}"
            if len(days) > 1 and days == list(range(days[0], days[-1] + 1))
            else ", ".join(pulse_html.WEEKDAY_SHORT[day] for day in days)
        )
        sittings_note += f" Für Wochenpuls und Redeanteil verglichen: {pulse_html.esc(day_label)} beider Wochen."
        share_note = (
            "Anteil an allen Reden der verglichenen Sitzungstage, Ver&auml;nderung in Prozentpunkten "
            f"gegen&uuml;ber {pulse_html.esc(previous['label'])}."
        )
    elif basis is None:
        sittings_note += " Kein gemeinsamer Sitzungstag; kein Wochenpuls- oder Redeanteil-Vergleich."
        share_note = "Anteil an allen Reden dieser Woche; kein gemeinsamer Sitzungstag f&uuml;r einen Vergleich."
    else:
        share_note = (
            "Anteil an allen Reden der Woche, Ver&auml;nderung in Prozentpunkten "
            f"gegen&uuml;ber {pulse_html.esc(previous['label'])}."
        )
    share_note += _speakers_note(compared_current)

    return f"""
    <section class="week-compare" id="wochenvergleich" aria-labelledby="wochenvergleich-h2">
      <div class="week-head">
        <div>
          <span class="eyebrow">Wochenvergleich</span>
          <h2 id="wochenvergleich-h2">{pulse_html.esc(current["label"])} gegen&uuml;ber {pulse_html.esc(previous["label"])}</h2>
          <p class="week-sub">{sittings_note}</p>
        </div>
        <span class="feature-state">Aus Plenarprotokollen</span>
      </div>
      <div class="week-grid">
        <article class="week-card">
          <h3>Wochenpuls</h3>
          <div class="week-metrics">{"".join(metric_cells)}</div>
          {pulse_html.render_sparkline(points)}
          <p class="week-note">Reden je Sitzungswoche, letzte {len(points)} Sitzungswochen bis {pulse_html.esc(current["label"])}.</p>
        </article>
        <article class="week-card">
          <h3>Redeanteil der Fraktionen</h3>
          {pulse_html.render_share_shift(compared_current["party_counts"], compared_previous["party_counts"] if basis else None)}
          <p class="week-note">{share_note}</p>
        </article>
        <article class="week-card">
          <h3>Debattenprofil</h3>
          {pulse_html.render_type_mix(current["vorgangstyp_counts"], previous["vorgangstyp_counts"])}
          <p class="week-note">Vorgangspositionen nach Art, Ver&auml;nderung gegen&uuml;ber {pulse_html.esc(previous["label"])}. <a href="sources.html#{pulse_html.VORGANGSTYP_GLOSSARY_ANCHOR}">Was die Typen bedeuten</a></p>
        </article>
        <article class="week-card">
          <h3>Verfahren, die zur&uuml;ckkehren</h3>
          {returning_html}
          <p class="week-note">{pulse_html.esc(returning_note)}</p>
        </article>{votes_card}
      </div>
    </section>
"""


# ---------------------------------------------------------------------------
# Build clock and week selection for puls.html.
#
# puls.html is the only page whose wording depends on *when* it was rendered
# ("Auswertung vom", "vor N Wochen", running vs. past week). The clock is
# injectable so tests and CI builds are reproducible: --today, else the
# SOURCE_DATE_EPOCH convention (UTC, reproducible-builds.org), else the wall
# clock at call time. --week pins the sitting week instead of "newest".
# ---------------------------------------------------------------------------


def resolve_today(value: date | datetime | None = None, *, environ: dict[str, str] | None = None) -> date:
    """The build date: an explicit value, else SOURCE_DATE_EPOCH (UTC), else today."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    env = os.environ if environ is None else environ
    epoch = env.get("SOURCE_DATE_EPOCH")
    if epoch:
        try:
            return datetime.fromtimestamp(int(epoch), tz=timezone.utc).date()
        except (ValueError, OverflowError, OSError) as exc:
            raise ValueError(f"SOURCE_DATE_EPOCH must be an integer Unix timestamp, got {epoch!r}") from exc
    return date.today()


def parse_iso_date_arg(value: str) -> date:
    """argparse converter for --today (YYYY-MM-DD only; fromisoformat alone
    accepts more forms from Python 3.11 on, and the grammar must not depend
    on the interpreter)."""
    text = value.strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise argparse.ArgumentTypeError(f"--today expects YYYY-MM-DD, got {value!r}")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"--today expects YYYY-MM-DD, got {value!r}") from exc


def parse_iso_week_arg(value: str) -> tuple[int, int]:
    """argparse converter for --week (YYYY-WW, ISO week)."""
    match = re.fullmatch(r"(\d{4})-W?(\d{1,2})", value.strip())
    if not match:
        raise argparse.ArgumentTypeError(f"--week expects YYYY-WW (ISO week), got {value!r}")
    year, week = int(match.group(1)), int(match.group(2))
    try:
        date.fromisocalendar(year, week, 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"--week {value!r} is not a valid ISO week") from exc
    return (year, week)


def select_pulse_week(
    entries: list[dict[str, Any]],
    week: tuple[int, int] | None = None,
) -> tuple[tuple[int, int] | None, dict[tuple[int, int], list[dict[str, Any]]]]:
    """The sitting week puls.html shows: `week` if given, else the newest dated week.

    Raises ValueError, listing the available weeks, when `week` is not in the
    archive - callers check this before any output is written.
    """
    weeks = pulse_html.group_entries_by_week(entries)
    if week is not None:
        if week not in weeks:
            available = ", ".join(f"{y}-{w:02d}" for y, w in sorted(weeks)) or "keine"
            raise ValueError(f"--week {week[0]}-{week[1]:02d} ist nicht im Archiv; vorhanden: {available}")
        return week, weeks
    return (max(weeks) if weeks else None), weeks


def unknown_week_error(week: tuple[int, int] | None, protocols: list[dict[str, Any]]) -> str | None:
    """An error message when `week` is not among the protocols' sitting weeks, else None."""
    if week is None:
        return None
    known = {
        key for key in (pulse_html.iso_week_key(protocol.get("datum")) for protocol in protocols) if key is not None
    }
    if week in known:
        return None
    available = ", ".join(f"{y}-{w:02d}" for y, w in sorted(known)) or "keine"
    return f"--week {week[0]}-{week[1]:02d} ist nicht im Archiv; vorhanden: {available}"


def reject_unknown_week(week: tuple[int, int] | None, protocols: list[dict[str, Any]], *, note: str = "") -> bool:
    """Print the --week error for main() and say whether to stop (exit 2)."""
    week_error = unknown_week_error(week, protocols)
    if not week_error:
        return False
    print(f"error: {week_error}{note}", file=sys.stderr)
    return True


# ---------------------------------------------------------------------------
# puls.html: the week radar.
#
# One sitting week, topics first, receipts on every row (design record:
# docs/designs/puls-wochenradar.md). The data layer lives in
# render_dip_pulse_html (week_stats, week_topic_rows, topic_identity); the
# helpers below only turn those rows into markup. Every clause that depends on
# the build clock takes `today` explicitly so the page is reproducible.
# ---------------------------------------------------------------------------


def time_html(datum: Any, text: str) -> str:
    """`<time datetime>` around `text` when `datum` is an ISO date, else the bare text."""
    iso = str(datum or "")[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso):
        return f'<time datetime="{iso}">{pulse_html.esc(text)}</time>'
    return pulse_html.esc(text)


def entry_protocol(entry: dict[str, Any]) -> dict[str, Any]:
    """The DIP protocol record inside a built dossier entry, or {}."""
    return ((entry.get("report") or {}).get("protocol")) or {}


def sitting_label(entry: dict[str, Any]) -> str:
    """"21/84", or the page stem when the DIP record has no dokumentnummer."""
    document = str(entry_protocol(entry).get("dokumentnummer") or "").strip()
    if document:
        return document
    page_path = entry.get("page_path")
    return Path(page_path).stem if page_path else ""


def dossier_href(entry: dict[str, Any]) -> str:
    return f"protocols/{Path(entry['page_path']).name}"


def render_pulse_shell(features: Selection, message: str) -> str:
    """puls.html without a week to show: the shared chrome and one sentence."""
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls</title>
  {pulse_html.page_head(features)}
  <style>
    :root {{
      --ink:#171a1f;
      --muted:#606a78;
      --line:#d9dee6;
      --paper:#f7f8fa;
      --panel:#ffffff;
      --blue:#174ea6;
      --blue-soft:#eef5ff;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color:var(--ink);
      background:var(--paper);
    }}
    a {{ color:var(--blue); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .shell {{ max-width:960px; margin:0 auto; padding:24px; }}
    {pulse_html.global_header_styles()}
    .page-header {{
      padding-bottom:18px;
      border-bottom:1px solid var(--line);
    }}
    h1 {{ margin:0; font-size:34px; line-height:1.1; }}
    p {{ color:var(--muted); line-height:1.5; }}
    footer {{ margin-top:28px; color:var(--muted); font-size:12px; }}
  </style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(features=features)}
    <header class="page-header">
      <h1>Bundestag-Puls</h1>
      <p>{pulse_html.esc(message)}</p>
    </header>
    <footer>
      Das XML-Protokoll ist maßgeblich; DIP-API-Daten ergänzen jede Sitzung.
    </footer>
  </div>
  {pulse_html.page_scripts(features)}
</body>
</html>
"""


def week_header_facts(
    stats: dict[str, Any],
    week_entries: list[dict[str, Any]],
    week: tuple[int, int],
    today: date,
) -> dict[str, Any]:
    """Eyebrow, h1 and the facts sentence of the page header.

    Running iff Monday <= today <= Sunday of the sitting week: the data cannot
    tell whether a week is over (a stale cache rebuilt offline can hold one
    sitting of a finished week), so the build clock decides and the clock label
    is always "Auswertung vom". A past week within one ISO week of today reads
    "Stand: ..."; anything older leads with its age and the eyebrow becomes
    "Letzte Sitzungswoche". Returns {"eyebrow", "h1", "facts", "running",
    "warning"}; `facts` is HTML with every date in a <time> element.
    """
    label = pulse_html.week_label(week)
    monday = date.fromisocalendar(week[0], week[1], 1)
    sunday = monday + timedelta(days=6)
    running = monday <= today <= sunday
    warning = None
    if today < monday:
        warning = "warning: [puls] Auswertung liegt vor der Sitzungswoche"

    counts = (
        f"{pulse_html.format_count(stats['speech_count'], 'Rede', 'Reden')} in "
        f"{pulse_html.format_count(stats['top_count'], 'Tagesordnungspunkt', 'Tagesordnungspunkten')}"
    )
    sittings = pulse_html.format_count(stats["sitting_count"], "Sitzung", "Sitzungen")
    clock = time_html(today.isoformat(), pulse_html.format_date(today.isoformat()))

    if running:
        return {
            "eyebrow": "Sitzungswoche · Aktueller Puls",
            "h1": f"Was der Bundestag in {label} bisher verhandelt hat",
            "facts": f"{counts} · Stand {clock}: {sittings} erfasst, Sitzungswoche l&auml;uft",
            "running": True,
            "warning": warning,
        }

    # Newest protocol of the week: "verteilt am" from DIP's distribution date,
    # else the sitting date, else the bare document number.
    newest = week_entries[-1]
    protocol = entry_protocol(newest)
    latest = f"letztes Protokoll {pulse_html.esc(sitting_label(newest))}"
    distributed = pulse_html.format_date(protocol.get("verteildatum"))
    dated = pulse_html.format_date(protocol.get("datum"))
    if distributed:
        latest += f" verteilt am {time_html(protocol.get('verteildatum'), distributed)}"
    elif dated:
        latest += f" vom {time_html(protocol.get('datum'), dated)}"
    clock = f"Auswertung vom {clock}"

    age = pulse_html.week_span(week, pulse_html.iso_week_key(today.isoformat())) if today > sunday else 0
    if age <= 1:
        return {
            "eyebrow": "Sitzungswoche · Aktueller Puls",
            "h1": f"Was der Bundestag in {label} verhandelt hat",
            "facts": f"{counts} · Stand: {sittings}, {latest} · {clock}",
            "running": False,
            "warning": warning,
        }
    return {
        "eyebrow": "Letzte Sitzungswoche",
        "h1": f"Was der Bundestag in {label} verhandelt hat",
        "facts": f"Letzte Sitzungswoche vor {age} Wochen · {counts} · {sittings}, {latest} · {clock}",
        "running": False,
        "warning": warning,
    }


def render_sitting_chips(week_entries: list[dict[str, Any]]) -> str:
    """One chip per sitting of the week, "Fr 12.06. · 21/84", linking its dossier."""
    chips = []
    for entry in week_entries:
        datum = entry_protocol(entry).get("datum")
        parts = [time_html(datum, pulse_html.format_sitting_date(datum)), pulse_html.esc(sitting_label(entry))]
        chips.append(f'<a href="{pulse_html.esc(dossier_href(entry))}">{" · ".join(p for p in parts if p)}</a>')
    return "".join(chips)


def _neutral_types(identity: dict[str, Any], label: str) -> str:
    """The procedure types behind a type-neutral "Vorlagen" label, for a title attribute."""
    if "Vorlage" not in label:
        return ""
    return ", ".join(f"{kind} ({n})" for kind, n in identity["type_counts"].most_common())


def _more_titles_link(rest: list[str], href: str) -> str:
    """"und N weitere" linking the dossier TOP, the hidden titles in its title attribute."""
    if not rest:
        return ""
    tooltip = ", ".join(rest[: pulse_html.RADAR_TOOLTIP_TITLES])
    if len(rest) > pulse_html.RADAR_TOOLTIP_TITLES:
        tooltip += " …"
    return f'<a href="{href}" title="{pulse_html.esc(tooltip)}">und {len(rest)} weitere</a>'


def render_radar_row(
    row: dict[str, Any],
    position: int,
    *,
    peak: int,
    features: Selection,
    pdf_url: Any = None,
) -> str:
    """One ranked debate: what it was, how much of the week it took, who spoke."""
    esc = pulse_html.esc
    identity = row["identity"]
    href = f"{esc(row['dossier_href'])}#top-{esc(row['index'])}"
    heading = " ".join(str(row.get("heading") or "").split())
    label = pulse_html.type_label(identity)
    types = _neutral_types(identity, label)
    titles = identity["titles"]
    siblings_cap = pulse_html.RADAR_SIBLINGS

    if identity["equal_weight"]:
        # Antrag-only group with several titles (Final Gate D16): the label is the
        # link, every title at equal weight, so DIP order promotes no framing.
        link_title = f' title="{esc(heading)}"' if heading else ""
        span_title = f' title="{esc(types)}"' if types and not heading else ""
        label_html = f'<span class="eyebrow"{span_title}><a href="{href}"{link_title}>{esc(label)}</a></span>'
        items = "".join(f'<li class="radar-group-title">{esc(title)}</li>' for title in titles[:siblings_cap])
        more = _more_titles_link(titles[siblings_cap:], href)
        if more:
            items += f'<li class="radar-group-more">{more}</li>'
        title_html = f'<ul class="radar-titles">{items}</ul>'
    else:
        span_title = f' title="{esc(types)}"' if types else ""
        label_html = f'<span class="eyebrow"{span_title}>{esc(label)}</span>' if label else ""
        lead_title = identity["lead_title"] or ""
        link_title = f' title="{esc(heading)}"' if heading and heading != lead_title else ""
        title_html = f'<strong class="radar-title"><a href="{href}"{link_title}>{esc(lead_title)}</a></strong>'
        siblings = [title for title in titles if title != lead_title]
        if siblings:
            shown = " · ".join(esc(title) for title in siblings[:siblings_cap])
            more = _more_titles_link(siblings[siblings_cap:], href)
            if more:
                shown += f" · {more}"
            title_html += f'<p class="radar-siblings">mit: {shown}</p>'

    trace_html = ""
    if row["trace"]:
        first = row["trace"]["first"]
        earlier = f"{first['vorgangsposition']} in {first['label']}" if first.get("vorgangsposition") else first["label"]
        if first.get("page_path"):
            first_href = f"protocols/{esc(Path(first['page_path']).name)}#top-{esc(first['index'])}"
            earlier = f'<a href="{first_href}">{esc(earlier)}</a>'
        else:
            earlier = esc(earlier)
        current = row["trace"]["current_position"]
        now = f"{current} diese Woche" if current else "diese Woche"
        trace_html = f'<p class="radar-trace">Fortgesetzt: {earlier} &rarr; {esc(now)}</p>'

    summary_html = ""
    if row["summary"]:
        text = pulse_html.short(row["summary"].get("text"), pulse_html.RADAR_SUMMARY_CHARS)
        receipts = pulse_html.render_receipts(
            row["item"], row["stats"], row["summary"], dossier_href=row["dossier_href"], pdf_url=pdf_url
        )
        summary_html = (
            f'<div class="radar-summary"><p>{esc(text)}</p>'
            f'<p class="radar-receipts">{receipts}</p></div>'
        )

    badge_html = ""
    if row["has_votes"]:
        badge_html = '<span class="badge radar-badge">namentlich abgestimmt</span>'

    foot_parts = [pulse_html.format_sitting_date(row["datum"]), f"Tagesordnungspunkt {row['index']}", "Debatte im Protokoll öffnen"]
    foot_html = f'<p class="radar-open"><a href="{href}">{" · ".join(esc(part) for part in foot_parts if part)}</a></p>'

    width = row["speech_count"] / peak * 100 if peak else 0.0
    share_html = (
        f'<div class="radar-share"><strong>{pulse_html.format_count(row["speech_count"], "Rede", "Reden")}</strong>'
        f"<small>{pulse_html.format_percent(row['share'])} der Woche</small>"
        f'<div class="radar-bar" aria-hidden="true"><span style="width:{width:.2f}%"></span></div></div>'
    )

    # Exact-width stack over the recorded speeches (item_stats falls back to the
    # five-entry xml_speakers_first, so the total is the legend's, not the count).
    party_counts = row["party_counts"]
    stack = pulse_html.render_party_stack(party_counts, row["party_total"], min_width=0.0, class_name="who-stack")
    if row["party_total"]:
        legend = " · ".join(f"{pulse_html.PARTY_SHORT.get(party, party)} {count}" for party, count in party_counts.most_common())
        if not row["speakers_complete"]:
            legend += f" · Fraktionen nur für die ersten {len(row['speakers'])} Reden bekannt"
    else:
        legend = "Fraktionen nicht erfasst"
    who_html = (
        f'<div class="radar-who"><span class="eyebrow">Wer sprach</span><div aria-hidden="true">{stack}</div>'
        f'<p class="radar-legend">{esc(legend)}</p></div>'
    )

    return f"""
        <li class="radar-row" id="thema-{position}">
          <div class="radar-main">{label_html}{title_html}{trace_html}{summary_html}{badge_html}{foot_html}</div>
          {share_html}
          {who_html}
        </li>"""


def render_radar_also(radar: dict[str, Any]) -> str:
    """The "Außerdem" line: question formats, then the unranked debates per sitting."""
    esc = pulse_html.esc
    formats = []
    for item in radar["formats"]:
        where = ", ".join(p for p in (pulse_html.format_sitting_date(item["datum"]), f"TOP {item['index']}") if p)
        formats.append(
            f'<a href="{esc(item["href"])}">{esc(item["heading"])}</a> · '
            f"{pulse_html.format_count(item['speech_count'], 'Wortmeldung', 'Wortmeldungen')} · "
            f"{pulse_html.format_percent(item['share'])} ({esc(where)})"
        )
    remaining = ""
    if radar["remaining"]:
        total = sum(n for _document, _page, n in radar["remaining"])
        sittings = " · ".join(
            f'<a href="protocols/{esc(Path(page_path).name)}">{esc(document)}</a> ({n})'
            for document, page_path, n in radar["remaining"]
        )
        count = f"Weitere {total} Tagesordnungspunkte" if total != 1 else "1 weiterer Tagesordnungspunkt"
        remaining = f"{count}: {sittings}"
    if formats and remaining:
        text = f"Außerdem, nicht als Thema gerankt: {' · '.join(formats)} · {remaining}"
    elif formats:
        text = f"Außerdem, nicht als Thema gerankt: {' · '.join(formats)}"
    elif remaining:
        text = remaining
    else:
        return ""
    return f'<p class="radar-also">{text}</p>'


def render_radar_section(
    radar: dict[str, Any],
    stats: dict[str, Any],
    features: Selection,
    pdf_urls: dict[Any, Any] | None = None,
) -> str:
    """"Themen der Woche": the ranked rows, the method note, the Außerdem line."""
    esc = pulse_html.esc
    total = int(stats["speech_count"])
    head = (
        '<span class="eyebrow">Themen der Woche</span>'
        '<h2 id="radar-h2">Wor&uuml;ber am meisten gesprochen wurde</h2>'
    )
    if not total:
        body = '<p class="week-note">In dieser Sitzungswoche wurden keine Reden extrahiert.</p>'
    else:
        method = (
            "Die Tagesordnungspunkte mit den meisten Reden der Woche. "
            f"Anteil an allen {pulse_html.format_count(total, 'Rede', 'Reden')}"
        )
        if radar["formats"]:
            biggest = max(radar["formats"], key=lambda item: item["speech_count"])
            method += (
                f"; Frageformate wie die {biggest['heading']} "
                f"({pulse_html.format_count(biggest['speech_count'], 'Wortmeldung', 'Wortmeldungen')}) "
                "zählen mit, werden aber nicht als Thema gerankt."
            )
        else:
            method += "."
        rows = radar["rows"]
        peak = rows[0]["speech_count"] if rows else 0
        pdf_urls = pdf_urls or {}
        rows_html = "".join(
            render_radar_row(row, position, peak=peak, features=features, pdf_url=pdf_urls.get(row["page_path"]))
            for position, row in enumerate(rows, start=1)
        )
        body = f'<p class="week-note radar-method">{esc(method)}</p>'
        if rows_html:
            body += f'<ul class="radar-list">{rows_html}\n      </ul>'
        body += render_radar_also(radar)
    return f"""
    <section class="radar" aria-labelledby="radar-h2">
      <div class="radar-head">{head}</div>
      {body}
    </section>
"""


def render_front_page(
    entries: list[dict[str, Any]],
    database_href: str | None = "data/bundestag-pulse.sqlite",
    features: Selection | None = None,
    *,
    today: date | datetime | None = None,
    week: tuple[int, int] | None = None,
) -> str:
    features = features or publication_selection()
    today = resolve_today(today)
    selected_week, weeks = select_pulse_week(entries, week)
    if not entries:
        return render_pulse_shell(features, "Es wurden noch keine Sitzungen erzeugt.")

    # Sittings without a usable date cannot be placed in a week. They are left
    # out with a warning; the page only exists when at least one dated sitting
    # remains, and the header says how many were skipped.
    undated = [entry for entry in entries if pulse_html.iso_week_key(entry_protocol(entry).get("datum")) is None]
    if selected_week is None:
        print("warning: [puls] kein Wochenradar möglich: keine datierte Sitzung", file=sys.stderr)
        return render_pulse_shell(
            features, "Die erzeugten Sitzungen tragen kein Datum, ein Wochenradar ist nicht möglich."
        )
    if undated:
        skipped = ", ".join(sitting_label(entry) for entry in undated)
        print(f"warning: [puls] {len(undated)} Sitzungen ohne Datum ausgeschlossen ({skipped})", file=sys.stderr)

    # The week's data: one denominator (week_stats' speech count) for the header
    # sentence, the method note and every row share; one occurrence index for the
    # row traces and the returning card.
    week_entries = weeks[selected_week]
    stats = pulse_html.week_stats(selected_week, week_entries)
    occurrences = pulse_html.vorgang_occurrences(weeks, selected_week)
    returning = pulse_html.returning_vorgaenge(weeks, selected_week, occurrences)
    radar = pulse_html.week_topic_rows(
        week_entries, occurrences, total=stats["speech_count"], dossier_href_for=dossier_href
    )
    pdf_urls = {entry.get("page_path"): entry_protocol(entry).get("pdf_url") for entry in week_entries}

    # The previous week is the closest earlier week within MAX_WEEK_GAP; anything
    # further apart is a different era, not a Wochenvergleich.
    earlier = [key for key in sorted(weeks) if key < selected_week]
    comparison = None
    if earlier and pulse_html.week_span(earlier[-1], selected_week) <= pulse_html.MAX_WEEK_GAP:
        comparison = pulse_html.week_comparison(stats, pulse_html.week_stats(earlier[-1], weeks[earlier[-1]]))

    header = week_header_facts(stats, week_entries, selected_week, today)
    if header["warning"]:
        print(header["warning"], file=sys.stderr)
    if not stats["speech_count"]:
        print(
            f"warning: [puls] {pulse_html.week_label(selected_week)}: keine Reden extrahiert "
            "(leere Eingabe oder Extraktion), Abruf prüfen",
            file=sys.stderr,
        )
    formats = len(radar["formats"])
    remaining = sum(n for _document, _page, n in radar["remaining"])
    log = (
        f"[puls] {pulse_html.week_label(selected_week)}: "
        f"{pulse_html.format_count(stats['sitting_count'], 'Sitzung', 'Sitzungen')}, "
        f"{pulse_html.format_count(len(radar['rows']), 'Thema', 'Themen')}, "
        f"{pulse_html.format_count(formats, 'Frageformat', 'Frageformate')}, "
        f"{remaining} weitere, today={today.isoformat()}"
    )
    if undated:
        log += f", {len(undated)} Sitzungen ohne gültiges Datum"
    print(log, file=sys.stderr)

    newest_href = pulse_html.esc(dossier_href(week_entries[-1]))
    undated_note = ""
    if undated:
        undated_note = (
            f'<p class="week-note">{pulse_html.format_count(len(undated), "neuere Sitzung", "neuere Sitzungen")} '
            "ohne Datum nicht ber&uuml;cksichtigt</p>"
        )
    radar_html = render_radar_section(radar, stats, features, pdf_urls)
    week_compare_html = render_week_comparison_section(
        comparison, weeks, selected_week, current_stats=stats, features=features, returning=returning
    )
    store_note = (
        " Die SQLite-Datei enthält MPs, Parteien, Vorgänge, Reden und Abstimmungen als verknüpfte Datensätze."
        if database_href
        else ""
    )

    # Page anatomy, top to bottom:
    #   global header -> page header: the week's identity (eyebrow, h1, one chip
    #                    per sitting, the facts sentence, actions)
    #   radar         -> "Themen der Woche": ranked debate rows with type label,
    #                    Vorgang title(s), trace, summary + receipts, share bar,
    #                    who-spoke stack; the Außerdem line for formats and the rest
    #   week-compare  -> the Wochenvergleich band (four cards + the votes card)
    #   footer
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Aktueller Puls</title>
  {pulse_html.page_head(features)}
  <style>
    :root {{
      --ink:#171a1f;
      --muted:#606a78;
      --line:#d9dee6;
      --paper:#f7f8fa;
      --panel:#ffffff;
      --blue:#174ea6;
      --teal:#0f766e;
      --amber:#9a5a00;
      --green-soft:#eff8f6;
      --blue-soft:#eef5ff;
      --amber-soft:#fff7e6;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color:var(--ink);
      background:var(--paper);
      letter-spacing:0;
    }}
    a {{ color:var(--blue); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .shell {{ max-width:1280px; margin:0 auto; padding:26px 22px; }}
    {pulse_html.global_header_styles()}
    .page-header {{
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:20px;
      align-items:start;
      padding-bottom:20px;
      border-bottom:1px solid var(--line);
    }}
    h1 {{ margin:0; font-size:37px; line-height:1.08; font-weight:780; overflow-wrap:anywhere; }}
    h2 {{ margin:0; font-size:18px; line-height:1.25; }}
    p {{ margin:7px 0 0; color:var(--muted); }}
    .page-actions, .week-chips {{ display:flex; flex-wrap:wrap; gap:9px; justify-content:flex-start; }}
    .week-chips {{ margin-top:12px; }}
    .page-actions a, .week-chips a, .session-links a {{
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-height:34px;
      padding:5px 11px;
      border:1px solid var(--line);
      border-radius:6px;
      background:var(--panel);
      font-weight:700;
      font-size:13px;
    }}
    .page-actions a {{ border-color:#bdd0ea; background:var(--blue-soft); color:var(--blue); }}
    .week-chips a {{ color:var(--ink); }}
    .week-facts {{ margin-top:12px; max-width:860px; font-size:15px; line-height:1.5; }}
    .eyebrow {{
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .eyebrow a {{ color:inherit; }}
    .radar, .week-compare {{
      margin-top:18px;
      border:1px solid var(--line);
      border-radius:12px;
      background:var(--panel);
      padding:18px;
    }}
    .radar-head h2 {{ margin:5px 0 0; font-size:25px; line-height:1.15; }}
    .radar-method {{ margin-top:8px; max-width:860px; font-size:13px; }}
    .radar-list {{ margin:8px 0 0; padding:0; list-style:none; }}
    .radar-row {{
      display:grid;
      grid-template-columns:minmax(0,1fr) 220px 160px;
      gap:10px 22px;
      align-items:start;
      padding:14px 0;
      border-bottom:1px solid var(--line);
      break-inside:avoid;
    }}
    .radar-row:last-child {{ border-bottom:0; }}
    .radar-main {{ display:grid; gap:6px; align-content:start; }}
    .radar-main > .eyebrow {{ display:block; }}
    .radar-title {{ display:block; font-size:16px; font-weight:750; line-height:1.3; overflow-wrap:anywhere; }}
    .radar-title a {{ color:var(--ink); }}
    .radar-titles {{ display:grid; gap:3px; margin:0; padding:0; list-style:none; }}
    .radar-group-title {{ font-size:15px; font-weight:650; line-height:1.3; color:var(--ink); overflow-wrap:anywhere; }}
    .radar-group-more {{ font-size:13px; }}
    .radar-siblings {{ margin:0; font-size:13px; line-height:1.4; color:var(--muted); overflow-wrap:anywhere; }}
    .radar-trace {{ margin:0; font-size:12px; line-height:1.4; color:var(--muted); }}
    .radar-summary {{
      margin:4px 0 0;
      padding:0 0 0 8px;
      border-left:2px solid var(--line);
    }}
    .radar-summary p {{ margin:0; font-size:13px; line-height:1.5; color:var(--ink); }}
    .radar-summary .radar-receipts {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:6px; }}
    .radar-receipts a, .radar-receipts span {{
      display:inline-flex;
      align-items:center;
      min-height:22px;
      padding:2px 7px;
      border:1px solid var(--line);
      border-radius:999px;
      background:var(--paper);
      font-size:11px;
      color:var(--ink);
    }}
    .radar-badge {{ justify-self:start; color:var(--amber); border-color:var(--amber); }}
    .radar-open {{ margin:2px 0 0; font-size:13px; }}
    .radar-share {{ display:grid; gap:3px; align-content:start; padding-top:2px; }}
    .radar-share strong {{ font-size:18px; font-weight:750; font-variant-numeric:tabular-nums; line-height:1.2; }}
    .radar-share small {{ font-size:12px; color:var(--muted); }}
    .radar-bar {{ height:8px; margin-top:4px; border-radius:999px; background:var(--line); overflow:hidden; }}
    .radar-bar span {{ display:block; height:100%; border-radius:999px; background:var(--teal); }}
    .radar-who {{ display:grid; gap:6px; align-content:start; padding-top:2px; }}
    .who-stack {{ display:flex; overflow:hidden; height:10px; border-radius:999px; background:var(--line); }}
    .who-stack.empty {{ outline:1px solid var(--line); }}
    .radar-legend {{ margin:0; font-size:11px; line-height:1.4; color:var(--muted); }}
    .radar-row a {{ text-decoration-line:underline; text-decoration-color:transparent; text-underline-offset:2px; }}
    .radar-row a:hover {{ text-decoration-color:currentColor; }}
    .radar-row a:visited {{ text-decoration-color:var(--muted); }}
    .radar-row a:focus-visible {{ outline:2px solid var(--blue); outline-offset:2px; border-radius:2px; }}
    .radar-also {{ margin:14px 0 0; font-size:13px; line-height:1.5; color:var(--ink); }}
    .radar-also a {{ text-decoration:underline; text-underline-offset:2px; }}
    .week-head {{
      display:flex;
      justify-content:space-between;
      gap:14px;
      align-items:start;
      padding-bottom:14px;
      border-bottom:1px solid var(--line);
    }}
    .week-head h2 {{ margin:5px 0 0; font-size:25px; line-height:1.15; }}
    .week-sub {{ margin:6px 0 0; max-width:760px; font-size:13px; line-height:1.45; }}
    .feature-state {{
      display:inline-flex;
      align-items:center;
      min-height:26px;
      padding:3px 9px;
      border:1px solid rgba(23,26,31,.14);
      border-radius:999px;
      background:rgba(255,255,255,.72);
      color:#3f4a59;
      font-size:12px;
      font-weight:750;
      white-space:nowrap;
    }}
    .feature-link {{
      display:inline-flex;
      justify-self:start;
      align-items:center;
      min-height:34px;
      padding:5px 11px;
      border:1px solid rgba(23,26,31,.14);
      border-radius:6px;
      background:#fff;
      font-size:13px;
      font-weight:750;
    }}
    .week-grid {{
      display:grid;
      grid-template-columns:repeat(2, minmax(0,1fr));
      gap:16px;
      margin-top:16px;
    }}
    .week-card {{
      display:grid;
      gap:10px;
      align-content:start;
      border:1px solid var(--line);
      border-radius:10px;
      background:#fbfcfd;
      padding:14px;
    }}
    .week-card h3 {{
      margin:0;
      font-size:13px;
      font-weight:750;
      text-transform:uppercase;
      letter-spacing:.05em;
      color:var(--muted);
    }}
    .votes-card {{ grid-column:1 / -1; }}
    .votes-card .eyebrow {{ margin-bottom:-6px; }}
    .week-text {{ margin:0; font-size:15px; line-height:1.45; color:var(--ink); }}
    .vote-row {{ font-size:13px; }}
    .week-metrics {{
      display:grid;
      grid-template-columns:repeat(3, minmax(0,1fr));
      gap:8px;
    }}
    .week-metric {{
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel);
      padding:9px 10px;
    }}
    .week-metric span {{
      display:block;
      color:var(--muted);
      font-size:11px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .week-metric strong {{ display:block; margin-top:3px; font-size:21px; }}
    .week-metric-foot {{
      display:flex;
      flex-wrap:wrap;
      align-items:baseline;
      gap:6px;
      margin-top:5px;
    }}
    .week-metric-foot em {{ color:var(--muted); font-size:11px; font-style:normal; }}
    .week-delta {{ font-size:12px; font-weight:750; white-space:nowrap; }}
    .week-delta.up {{ color:var(--teal); }}
    .week-delta.down {{ color:var(--amber); }}
    .week-delta.flat {{ color:var(--muted); }}
    .week-spark {{
      display:flex;
      align-items:flex-end;
      gap:3px;
      height:56px;
      padding:6px;
      border-radius:8px;
      background:#edf0f4;
    }}
    .week-spark span {{
      flex:1;
      min-width:4px;
      border-radius:3px 3px 0 0;
      background:var(--teal);
    }}
    .week-spark span:last-child {{ background:var(--blue); }}
    .week-spark.empty {{ background:#edf0f4; }}
    .week-list {{ display:grid; gap:8px; margin:0; padding:0; list-style:none; }}
    .week-row {{
      display:grid;
      grid-template-columns:minmax(96px,1.1fr) minmax(0,2fr) auto auto;
      align-items:center;
      gap:9px;
    }}
    .week-label {{
      color:var(--muted);
      font-size:12px;
      overflow-wrap:anywhere;
    }}
    /* Vorgangstyp labels link to the glossary on sources.html and carry the
       one-line explanation as data-tip, shown as a CSS-only bubble on hover and
       keyboard focus. Touch devices get no bubble; tapping follows the link. */
    a.week-label {{
      position:relative;
      color:inherit;
      text-decoration:underline dotted;
      text-decoration-thickness:1px;
      text-underline-offset:2px;
    }}
    a.week-label:hover,
    a.week-label:focus-visible {{ color:var(--ink); }}
    a.week-label:focus-visible {{ outline:2px solid var(--blue); outline-offset:2px; border-radius:2px; }}
    a.week-label[data-tip]::after {{
      content:attr(data-tip);
      position:absolute;
      left:0;
      bottom:calc(100% + 6px);
      z-index:5;
      width:max-content;
      max-width:min(260px, 70vw);
      padding:7px 9px;
      border-radius:6px;
      background:#273142;
      color:#fff;
      font-size:12px;
      font-weight:400;
      line-height:1.4;
      white-space:normal;
      text-align:left;
      box-shadow:0 4px 14px rgba(20,30,45,.18);
      opacity:0;
      visibility:hidden;
      transform:translateY(2px);
      pointer-events:none;
      transition:opacity .12s ease, transform .12s ease, visibility 0s linear .12s;
    }}
    a.week-label[data-tip]:hover::after,
    a.week-label[data-tip]:focus-visible::after {{
      opacity:1;
      visibility:visible;
      transform:none;
      transition-delay:0s;
    }}
    @media (hover: none) {{
      a.week-label[data-tip]::after {{ display:none; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      a.week-label[data-tip]::after {{ transition:none; transform:none; }}
    }}
    .week-note a {{ color:inherit; text-decoration:underline; text-underline-offset:2px; }}
    .week-note a:hover,
    .week-note a:focus-visible {{ color:var(--ink); }}
    .week-bar {{
      display:block;
      height:9px;
      border-radius:999px;
      background:#edf0f4;
      overflow:hidden;
    }}
    .week-bar span {{ display:block; height:100%; border-radius:999px; }}
    .week-row strong {{ font-size:13px; }}
    .week-row.return-row {{
      grid-template-columns:minmax(0,1fr);
      gap:3px;
      padding-bottom:8px;
      border-bottom:1px solid var(--line);
    }}
    .week-row.return-row:last-child {{ border-bottom:0; padding-bottom:0; }}
    .week-row.return-row strong {{ font-size:14px; line-height:1.35; }}
    .week-trace {{
      display:flex;
      flex-wrap:wrap;
      align-items:center;
      gap:7px;
      font-size:12px;
    }}
    .week-trace em {{ color:var(--muted); font-style:normal; }}
    .week-note {{
      margin:0;
      color:var(--muted);
      font-size:12px;
      line-height:1.45;
    }}
    .badge {{
      display:inline-flex;
      align-items:center;
      min-height:23px;
      padding:3px 8px;
      border:1px solid var(--line);
      border-radius:999px;
      background:#fbfcfd;
      color:#333a45;
      font-size:12px;
      white-space:nowrap;
    }}
    .session-links {{ display:flex; flex-wrap:wrap; gap:9px; margin-top:16px; }}
    footer {{ padding:24px 0 4px; color:var(--muted); font-size:12px; }}
    @media (max-width: 980px) {{
      .page-header, .week-grid {{ grid-template-columns:1fr; }}
      .page-actions {{ justify-content:flex-start; }}
      .radar-row {{ grid-template-columns:minmax(0,1fr) 200px; }}
      .radar-who {{ grid-column:1 / -1; }}
    }}
    @media (max-width: 700px) {{
      .shell {{ padding:16px 14px; }}
      h1 {{ font-size:29px; }}
      .radar-row {{ grid-template-columns:1fr; gap:10px; }}
      .radar-share {{ max-width:320px; }}
      .week-head {{ display:grid; }}
      .feature-state {{ justify-self:start; white-space:normal; }}
      .week-metrics {{ grid-template-columns:1fr 1fr; }}
      .week-row {{ grid-template-columns:minmax(80px,1fr) minmax(0,1.6fr) auto auto; }}
    }}
    @media (max-width: 460px) {{
      .week-metrics {{ grid-template-columns:1fr; }}
      .week-row {{ grid-template-columns:minmax(0,1fr) auto auto; }}
      .week-row .week-bar {{ grid-column:1 / -1; order:3; }}
    }}
    @media print {{
      .page-actions {{ display:none; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(active="pulse", features=features)}
    <header class="page-header">
      <div>
        <span class="eyebrow">{header["eyebrow"]}</span>
        <h1>{header["h1"]}</h1>
        <nav class="week-chips" aria-label="Sitzungen dieser Woche">{render_sitting_chips(week_entries)}</nav>
        <p class="week-facts">{header["facts"]}</p>{undated_note}
      </div>
      <nav class="page-actions" aria-label="Seitenaktionen">
        <a href="#wochenvergleich">Wochenvergleich</a>
        <a href="{newest_href}">Neuestes Protokoll</a>
      </nav>
    </header>
{radar_html}{week_compare_html}
    <footer>
      Statischer Prototyp. Das XML-Protokoll ist maßgeblich; DIP-API-Daten ergänzen jede Sitzung.{store_note}
      <span class="session-links"><a href="overview.html">Sitzungen</a><a href="bills/index.html">Gesetze</a><a href="abgeordnete/index.html">Abgeordnete</a><a href="sources.html">Quellen</a></span>
    </footer>
  </div>
  {pulse_html.page_scripts(features)}
</body>
</html>
    """


# Small "XML | PDF" link pair for one protocol, used in the catalog rows.
def protocol_source_links(protocol: dict[str, Any]) -> str:
    fundstelle = protocol.get("fundstelle") or {}
    links = []
    for label, key in (("XML", "xml_url"), ("PDF", "pdf_url")):
        url = pulse_html.safe_href(fundstelle.get(key))
        if url:
            links.append(f'<a href="{pulse_html.esc(url)}">{label}</a>')
    return "".join(links) or '<span class="muted">Keine Quelllinks</span>'


# Collapsed <details> holding the raw DIP record for one protocol, appended to
# every catalog row so the API fields behind a row can be inspected.
def render_catalog_json(protocol: dict[str, Any]) -> str:
    text = json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        '<details class="api-details">'
        '<summary>API-Felder</summary>'
        f"<pre>{pulse_html.esc(text)}</pre>"
        "</details>"
    )


# ---------------------------------------------------------------------------
# PAGES: bills/index.html and bills/bill-*.html - "Gesetze verfolgen"
#
# These pages are derived data: nothing is fetched here. collect_bill_pages()
# walks the dossiers that were already built and reassembles them by legislative
# procedure (DIP "Vorgang") instead of by sitting, so one bill's documents,
# plenary appearances, speakers and roll-call votes end up on a single page.
# Public bill pages are always generated, including an honest empty state.
# ---------------------------------------------------------------------------


# Return the first of the given values that is non-empty after stripping.
def first_value(*values: Any) -> str:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


# De-duplicate strings while preserving order.
def unique_values(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip() if value is not None else ""
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


# De-duplicate dicts by a tuple of key fields while preserving order. Used to
# collapse the same document / position / vote seen across several sittings.
def unique_records(records: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    for record in records:
        key = tuple(record.get(k) for k in keys)
        if key not in seen:
            seen.add(key)
            result.append(record)
    return result


# File name for a bill's detail page, e.g. "bill-315678.html".
def bill_slug(bill: dict[str, Any]) -> str:
    identity = first_value(bill.get("vorgang_id"), bill.get("primary_document"), bill.get("title"), "bill")
    return "bill-" + slugify_document_number(identity)


# Decide whether a DIP Vorgangsposition is legislation at all. This is a
# deliberately crude keyword test over the procedure type, position, title and
# the linked documents - everything that does not look like a "Gesetz" is left
# out of the bills section rather than guessed at.
def bill_like(position: dict[str, Any], docs: list[dict[str, Any]]) -> bool:
    haystack = " ".join(
        [
            str(position.get("vorgangstyp") or ""),
            str(position.get("vorgangsposition") or ""),
            str(position.get("titel") or ""),
            " ".join(str(doc.get("drucksachetyp") or "") for doc in docs),
            " ".join(str(doc.get("titel") or "") for doc in docs),
        ]
    ).lower()
    return any(marker in haystack for marker in ("gesetz", "gesetzentwurf", "entwurf eines gesetzes"))


# The set of Drucksache numbers attached to a bill, used to match roll-call
# votes to it.
def doc_numbers(docs: list[dict[str, Any]]) -> set[str]:
    return {str(doc.get("dokumentnummer")) for doc in docs if doc.get("dokumentnummer")}


# Re-index the built dossiers by legislative procedure.
#
# Input: the dossier entries of this build. Output: one normalised bill record
# per procedure, sorted newest activity first, ready for render_bills_index and
# render_bill_detail.
def collect_bill_pages(detail_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bills: dict[str, dict[str, Any]] = {}
    speaker_counts: dict[str, dict[str, dict[str, Any]]] = {}

    # Walk every dossier, every agenda item, every DIP position within it.
    for entry in detail_entries:
        report = entry["report"]
        protocol = report.get("protocol") or {}
        protocol_href = f"../protocols/{entry['page_path'].name}"
        for item in report.get("agenda_items") or []:
            api = item.get("api") or {}
            linked_docs = api.get("linked_drucksachen") or []
            positions = api.get("positions") or []
            item_votes = item.get("votes") or []
            # A position is one step of a procedure (first reading, committee
            # report, ...). Collect the documents that belong to this procedure,
            # adding the position's own source document when DIP did not link it.
            for position in positions:
                vorgang_id = str(position.get("vorgang_id") or "")
                position_docs = [doc for doc in linked_docs if str(doc.get("vorgang_id") or "") == vorgang_id]
                source = position.get("source") or {}
                if source.get("dokumentnummer") and not any(
                    doc.get("dokumentnummer") == source.get("dokumentnummer") for doc in position_docs
                ):
                    position_docs.append(
                        {
                            "vorgang_id": vorgang_id,
                            "vorgangsposition_id": position.get("id"),
                            "vorgangsposition": position.get("vorgangsposition"),
                            "titel": position.get("titel"),
                            "dokumentnummer": source.get("dokumentnummer"),
                            "drucksachetyp": position.get("dokumentart") or position.get("vorgangsposition"),
                            "datum": protocol.get("datum"),
                            "url": source.get("pdf_url"),
                            "urheber": [],
                        }
                    )
                # Skip anything that is not legislation.
                if not bill_like(position, position_docs):
                    continue

                # Identity for the bill: the DIP Vorgang id when present, else a
                # document number, else the title. Records for the same key
                # collected across several sittings are merged into one bill.
                fallback_key = first_value(
                    vorgang_id,
                    *(doc.get("dokumentnummer") for doc in position_docs),
                    position.get("titel"),
                )
                key = f"vorgang:{fallback_key}"
                bill = bills.setdefault(
                    key,
                    {
                        "id": key,
                        "vorgang_id": vorgang_id,
                        "title": first_value(position.get("titel"), item.get("heading"), "Unbenannter Vorgang"),
                        "type": first_value(position.get("vorgangstyp"), "Gesetzgebung"),
                        "primary_document": "",
                        "introduced_by": [],
                        "latest_date": "",
                        "latest_step": "",
                        "protocol_refs": [],
                        "documents": [],
                        "positions": [],
                        "events": [],
                        "votes": [],
                        "raw": {"agenda_items": []},
                    },
                )
                bill["title"] = first_value(bill.get("title"), position.get("titel"), item.get("heading"))
                bill["type"] = first_value(position.get("vorgangstyp"), bill.get("type"))
                bill["documents"].extend(position_docs)
                bill["positions"].append(position)
                bill["introduced_by"].extend(
                    origin
                    for doc in position_docs
                    for origin in (doc.get("urheber") or [])
                )
                if not bill.get("primary_document"):
                    bill["primary_document"] = first_value(*(doc.get("dokumentnummer") for doc in position_docs))

                # A "Plenarstelle": where in which sitting this bill was debated.
                # href points at the agenda-item anchor inside the dossier page.
                ref = {
                    "protocol_number": protocol.get("dokumentnummer"),
                    "protocol_date": protocol.get("datum"),
                    "protocol_title": protocol.get("titel"),
                    "top_id": item.get("top_id"),
                    "heading": item.get("heading"),
                    "href": f"{protocol_href}#top-{item.get('index')}",
                    "speech_count": item.get("xml_speech_count") or 0,
                }
                bill["protocol_refs"].append(ref)
                bill["raw"]["agenda_items"].append({"protocol": protocol, "item": item})

                # Timeline entries ("Verlauf" on the detail page): one per linked
                # document, plus one for the plenary debate itself.
                for doc in position_docs:
                    bill["events"].append(
                        {
                            "date": first_value(doc.get("datum"), protocol.get("datum")),
                            "kind": first_value(doc.get("drucksachetyp"), "Drucksache"),
                            "title": first_value(doc.get("titel"), position.get("titel")),
                            "source": first_value(doc.get("dokumentnummer")),
                            "url": doc.get("url"),
                        }
                    )
                bill["events"].append(
                    {
                        "date": protocol.get("datum"),
                        "kind": first_value(position.get("vorgangsposition"), "Plenarberatung"),
                        "title": first_value(position.get("titel"), item.get("heading")),
                        "source": f"BT-PlPr {protocol.get('dokumentnummer')} · {item.get('top_id')}",
                        "url": ref["href"],
                    }
                )

                # Attach roll-call votes from this agenda item, but only when the
                # vote's Drucksache numbers overlap the bill's - an agenda item
                # can bundle several procedures, and a vote must not be credited
                # to the wrong one.
                numbers = doc_numbers(position_docs)
                for vote in item_votes:
                    vote_numbers = set(vote.get("document_numbers") or [])
                    if numbers and vote_numbers and not (numbers & vote_numbers):
                        continue
                    bill["votes"].append(vote)
                    bill["events"].append(
                        {
                            "date": first_value(vote.get("date"), protocol.get("datum")),
                            "kind": "Namentliche Abstimmung",
                            "title": vote.get("title"),
                            "source": ", ".join(vote.get("document_numbers") or []),
                            "url": vote.get("detail_url"),
                        }
                    )

                # Tally who spoke about this bill and how much, keyed by
                # name+party. External ids are kept so the detail page can link
                # the speaker to their Abgeordnete profile.
                speaker_bucket = speaker_counts.setdefault(key, {})
                for speech in item.get("xml_speakers") or []:
                    speaker = speech.get("speaker") or {}
                    name = first_value(speaker.get("display_name"), "Unbekannt")
                    party = pulse_html.speaker_party(speaker)
                    speaker_key = f"{name}|{party}"
                    entry_count = speaker_bucket.setdefault(
                        speaker_key,
                        {"name": name, "party": party, "speech_count": 0, "char_count": 0},
                    )
                    entry_count["speech_count"] += 1
                    entry_count["char_count"] += int(speech.get("char_count") or 0)
                    # Keep the speaker's external ids so the bill page can link to
                    # their Abgeordnete profile.
                    profile = speaker.get("abgeordnetenwatch") or {}
                    if profile.get("id") and not entry_count.get("aw_id"):
                        entry_count["aw_id"] = profile.get("id")
                    if speaker.get("xml_redner_id") and not entry_count.get("xml_redner_id"):
                        entry_count["xml_redner_id"] = speaker.get("xml_redner_id")

    # Second pass: de-duplicate the accumulated lists, sort the timeline, and
    # derive the "latest step / latest date" shown on the index cards.
    for key, bill in bills.items():
        bill["documents"] = unique_records(bill["documents"], ("vorgang_id", "dokumentnummer", "url"))
        bill["positions"] = unique_records(bill["positions"], ("id", "vorgang_id", "vorgangsposition"))
        bill["protocol_refs"] = unique_records(bill["protocol_refs"], ("protocol_number", "top_id", "heading"))
        bill["votes"] = unique_records(bill["votes"], ("id",))
        bill["introduced_by"] = unique_values(bill["introduced_by"])
        bill["slug"] = bill_slug(bill)
        bill["speakers"] = sorted(
            speaker_counts.get(key, {}).values(),
            key=lambda speaker: (int(speaker.get("speech_count") or 0), int(speaker.get("char_count") or 0)),
            reverse=True,
        )
        bill["events"] = unique_records(bill["events"], ("date", "kind", "title", "source"))
        bill["events"].sort(key=lambda event: str(event.get("date") or ""), reverse=True)
        latest = bill["events"][0] if bill["events"] else {}
        bill["latest_date"] = first_value(latest.get("date"), *(ref.get("protocol_date") for ref in bill["protocol_refs"]))
        bill["latest_step"] = first_value(latest.get("kind"), "Erfasst")

    return sorted(
        bills.values(),
        key=lambda bill: (str(bill.get("latest_date") or ""), str(bill.get("title") or "")),
        reverse=True,
    )


# Collapsed raw-JSON block used in the "Rohdaten" section of a bill page.
def render_bill_json_details(title: str, payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        '<details class="raw-block">'
        f"<summary>{pulse_html.esc(title)}</summary>"
        f"<pre>{pulse_html.esc(text)}</pre>"
        "</details>"
    )


# Inline script shared by both bill pages: the "Folgen" toggle. Followed bills
# are kept in localStorage only - there is no account and no server, so the
# marking never leaves the visitor's browser.
def render_bill_script() -> str:
    return """
  <script>
    (() => {
      const key = "bundestag-pulse-followed-bills";
      const read = () => {
        try { return new Set(JSON.parse(localStorage.getItem(key) || "[]")); }
        catch { return new Set(); }
      };
      const write = (followed) => localStorage.setItem(key, JSON.stringify([...followed]));
      const sync = () => {
        const followed = read();
        document.querySelectorAll("[data-follow-id]").forEach((button) => {
          const active = followed.has(button.dataset.followId);
          button.classList.toggle("is-followed", active);
          button.setAttribute("aria-pressed", active ? "true" : "false");
          button.textContent = active ? "Gefolgt" : "Folgen";
        });
        document.querySelectorAll("[data-bill-card]").forEach((card) => {
          card.classList.toggle("is-followed", followed.has(card.dataset.billCard));
        });
        const count = document.querySelector("[data-follow-count]");
        if (count) count.textContent = String(followed.size);
      };
      document.addEventListener("click", (event) => {
        const button = event.target.closest("[data-follow-id]");
        if (!button) return;
        const followed = read();
        const id = button.dataset.followId;
        if (followed.has(id)) followed.delete(id);
        else followed.add(id);
        write(followed);
        sync();
      });
      sync();
    })();
  </script>
"""


# CSS shared by bills/index.html and bills/bill-*.html. The Abgeordnete pages
# extend this same sheet (see abgeordnete_styles), which is why the class names
# below - .panel, .metric, .badge, .doc-row - reappear there.
def bill_styles() -> str:
    return """
    :root {
      --ink:#171a1f;
      --muted:#606a78;
      --line:#d9dee6;
      --paper:#f7f8fa;
      --panel:#ffffff;
      --blue:#174ea6;
      --green:#0f766e;
      --amber:#9a5a00;
    }
    * { box-sizing:border-box; }
    body {
      margin:0;
      font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color:var(--ink);
      background:var(--paper);
      letter-spacing:0;
    }
    a { color:var(--blue); text-decoration:none; }
    a:hover { text-decoration:underline; }
    .shell { max-width:1280px; margin:0 auto; padding:26px 22px; }
    """ + pulse_html.global_header_styles() + """
    .page-header {
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:22px;
      align-items:end;
      padding-bottom:20px;
      border-bottom:1px solid var(--line);
    }
    .local-nav { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:10px; }
    .local-nav a, .source-link {
      display:inline-flex;
      align-items:center;
      min-height:30px;
      padding:4px 9px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      font-size:13px;
      font-weight:650;
    }
    h1 { margin:0; font-size:34px; line-height:1.1; }
    h2 { margin:0; font-size:21px; line-height:1.25; }
    h3 { margin:0; font-size:14px; line-height:1.25; }
    p { margin:7px 0 0; color:var(--muted); line-height:1.45; }
    .eyebrow, .metric span, .field span {
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }
    .follow-summary {
      display:grid;
      gap:3px;
      min-width:190px;
      padding:12px 14px;
      border:1px solid var(--line);
      border-radius:8px;
      background:#fff;
    }
    .follow-summary strong { font-size:24px; }
    .summary-grid {
      display:grid;
      grid-template-columns:repeat(4, minmax(0,1fr));
      gap:10px;
      margin-top:16px;
    }
    .metric, .field {
      border:1px solid var(--line);
      border-radius:8px;
      background:#fff;
      padding:11px 12px;
    }
    .metric strong, .field strong { display:block; margin-top:4px; font-size:21px; overflow-wrap:anywhere; }
    .bill-list, .content-grid, .timeline, .speaker-list, .doc-list {
      display:grid;
      gap:12px;
      margin-top:18px;
    }
    .bill-card, .panel {
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel);
      padding:16px;
    }
    .bill-card {
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:16px;
      align-items:start;
    }
    .bill-card.is-followed { border-color:#8bc8bd; box-shadow:inset 4px 0 0 var(--green); }
    .bill-meta {
      display:flex;
      flex-wrap:wrap;
      gap:8px;
      margin-top:10px;
    }
    .badge {
      display:inline-flex;
      align-items:center;
      min-height:24px;
      padding:3px 8px;
      border:1px solid var(--line);
      border-radius:999px;
      background:#fbfcfd;
      color:#333a45;
      font-size:12px;
      white-space:nowrap;
    }
    .actions { display:flex; flex-wrap:wrap; gap:8px; justify-content:flex-end; }
    .follow-button, .open-button {
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-height:34px;
      padding:5px 12px;
      border:1px solid #bdd0ea;
      border-radius:6px;
      background:#eef5ff;
      color:var(--blue);
      font:inherit;
      font-size:13px;
      font-weight:750;
      cursor:pointer;
    }
    .follow-button.is-followed {
      border-color:#89c5ba;
      background:#e7f6f3;
      color:#0f5f59;
    }
    .content-grid {
      grid-template-columns:minmax(0,1fr) 360px;
      align-items:start;
    }
    .field-grid {
      display:grid;
      grid-template-columns:repeat(2, minmax(0,1fr));
      gap:10px;
      margin-top:14px;
    }
    .timeline-row, .speaker-row, .doc-row {
      display:grid;
      grid-template-columns:120px minmax(0,1fr) minmax(120px,.45fr);
      gap:10px;
      padding-bottom:10px;
      border-bottom:1px solid #eef1f5;
      font-size:13px;
    }
    .timeline-row:last-child, .speaker-row:last-child, .doc-row:last-child { border-bottom:0; padding-bottom:0; }
    .timeline-row time, .timeline-row em, .speaker-row em, .doc-row em {
      color:var(--muted);
      font-style:normal;
      overflow-wrap:anywhere;
    }
    .raw-block {
      margin-top:12px;
      border:1px solid #dfe5ed;
      border-radius:8px;
      background:#fbfcfd;
      overflow:hidden;
    }
    .raw-block summary {
      min-height:34px;
      padding:8px 10px;
      cursor:pointer;
      color:var(--blue);
      font-size:13px;
      font-weight:700;
    }
    .raw-block pre {
      max-height:420px;
      overflow:auto;
      margin:0;
      padding:10px;
      border-top:1px solid #e6ebf2;
      font-size:12px;
      line-height:1.45;
      white-space:pre-wrap;
      overflow-wrap:anywhere;
    }
    footer { padding-top:24px; color:var(--muted); font-size:12px; }
    @media (max-width: 900px) {
      .page-header, .bill-card, .content-grid { grid-template-columns:1fr; }
      .actions { justify-content:flex-start; }
      .summary-grid, .field-grid { grid-template-columns:1fr 1fr; }
      .timeline-row, .speaker-row, .doc-row { grid-template-columns:1fr; gap:4px; }
    }
    @media (max-width: 640px) {
      .shell { padding:18px 14px; }
      h1 { font-size:28px; }
      .summary-grid, .field-grid { grid-template-columns:1fr; }
    }
"""


# PAGE: bills/index.html - the list of detected legislative procedures.
def render_bills_index(bills: list[dict[str, Any]], features: Selection | None = None) -> str:
    features = features or publication_selection()
    # One card per bill: type and latest date, title linking to the detail page,
    # who introduced it, and badges counting documents, plenary appearances and
    # roll-call votes. Following is a page-local browser interaction.
    rows = []
    for bill in bills:
        introduced = ", ".join(bill.get("introduced_by") or []) or "Urheber nicht im Rohdatensatz"
        rows.append(
            f"""
            <article class="bill-card" data-bill-card="{pulse_html.esc(bill['id'])}">
              <div>
                <span class="eyebrow">{pulse_html.esc(bill.get('type'))} · {pulse_html.esc(bill.get('latest_date'))}</span>
                <h2><a href="{pulse_html.esc(bill['slug'])}.html">{pulse_html.esc(bill.get('title'))}</a></h2>
                <p>{pulse_html.esc(introduced)}</p>
                <div class="bill-meta">
                  <span class="badge">{pulse_html.esc(bill.get('latest_step'))}</span>
                  <span class="badge">{pulse_html.esc(len(bill.get('documents') or []))} Drucksachen</span>
                  <span class="badge">{pulse_html.esc(len(bill.get('protocol_refs') or []))} Plenarstellen</span>
                  <span class="badge">{pulse_html.esc(len(bill.get('votes') or []))} Abstimmungen</span>
                </div>
              </div>
              <div class="actions">
                {'<button class="follow-button" type="button" data-follow-id="' + pulse_html.esc(bill['id']) + '" aria-pressed="false">Folgen</button>'}
                <a class="open-button" href="{pulse_html.esc(bill['slug'])}.html">Details</a>
              </div>
            </article>
            """
        )

    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Gesetze verfolgen</title>
  {pulse_html.page_head(features)}
  <style>{bill_styles()}</style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(depth=1, active="bills", features=features)}
    <header class="page-header">
      <div>
        <h1>Gesetze verfolgen</h1>
        <p>Jeder Eintrag wird aus den erzeugten Plenarprotokoll-Dossiers, DIP-Vorgangspositionen und verknüpften Drucksachen abgeleitet. Es werden keine ML- oder LLM-Zusammenfassungen verwendet.</p>
      </div>
      <div class="follow-summary">
        <span class="eyebrow">Gefolgt in diesem Browser</span>
        <strong data-follow-count>0</strong>
      </div>
    </header>
    <section class="summary-grid">
      <div class="metric"><span>Aktuelle Gesetze</span><strong>{pulse_html.esc(len(bills))}</strong></div>
      <div class="metric"><span>Drucksachen</span><strong>{pulse_html.esc(sum(len(b.get('documents') or []) for b in bills))}</strong></div>
      <div class="metric"><span>Plenarstellen</span><strong>{pulse_html.esc(sum(len(b.get('protocol_refs') or []) for b in bills))}</strong></div>
      <div class="metric"><span>Abstimmungen</span><strong>{pulse_html.esc(sum(len(b.get('votes') or []) for b in bills))}</strong></div>
    </section>
    <section class="bill-list">
      {''.join(rows) if rows else '<p>In den erzeugten Detaildossiers wurden noch keine Gesetzgebungsvorgänge erkannt.</p>'}
    </section>
    <footer>Die Folge-Markierung wird lokal im Browser gespeichert. Die Liste umfasst die Dossiers, die in diesem Build mit --detail-limit erzeugt wurden. <a href="../overview.html">Plenarprotokoll-Katalog</a> · <a href="../sources.html">Quellen und Methode</a></footer>
  </div>
  {render_bill_script()}
  {pulse_html.page_scripts(features)}
</body>
</html>
"""


# PAGE: bills/bill-<slug>.html - everything known about one procedure.
def _bill_event_href(value: Any) -> str:
    """Accept an allowlisted official source or our generated dossier anchor."""
    href = str(value or "")
    if href.startswith("https://"):
        return pulse_html.source_url(href, "bundestag-dip")
    if re.fullmatch(r"\.\./protocols/plenarprotokoll-[a-z0-9-]+\.html#top-[0-9]+", href):
        return href
    raise publication.PublicationStateError("unsafe bill timeline URL")


def render_bill_detail(
    bill: dict[str, Any],
    mp_lookup: dict[str, int] | None = None,
    features: Selection | None = None,
) -> str:
    features = features or publication_selection()
    # The four list sections of the page are built first, then interpolated into
    # the template: Verlauf (timeline), Drucksachen, Rednerinnen und Redner
    # (top 12, linked to their MP profile when resolvable) and Plenarstellen.
    introduced = ", ".join(bill.get("introduced_by") or []) or "Urheber nicht im Rohdatensatz"
    events = []
    for event in bill.get("events") or []:
        title = pulse_html.esc(event.get("title") or "")
        if event.get("url"):
            title = (
                f'<a href="{pulse_html.esc(_bill_event_href(event.get("url")))}">{title}</a>'
            )
        events.append(
            '<li class="timeline-row">'
            f'<time>{pulse_html.esc(event.get("date") or "")}</time>'
            f'<strong>{title}<br><span class="eyebrow">{pulse_html.esc(event.get("kind") or "")}</span></strong>'
            f'<em>{pulse_html.esc(event.get("source") or "")}</em>'
            "</li>"
        )

    docs = []
    for doc in bill.get("documents") or []:
        number = pulse_html.esc(doc.get("dokumentnummer") or "")
        label = (
            f'<a href="{pulse_html.esc(pulse_html.source_url(doc.get("url"), "bundestag-dip"))}">{number}</a>'
            if doc.get("url")
            else number
        )
        docs.append(
            '<li class="doc-row">'
            f"<strong>{label}</strong>"
            f'<span>{pulse_html.esc(doc.get("drucksachetyp") or "")}</span>'
            f'<em>{pulse_html.esc(", ".join(doc.get("urheber") or []))}</em>'
            "</li>"
        )

    speakers = []
    for speaker in (bill.get("speakers") or [])[:12]:
        mp_href = pulse_html.mp_page_href(
            {
                "abgeordnetenwatch": {"id": speaker.get("aw_id")},
                "xml_redner_id": speaker.get("xml_redner_id"),
            },
            mp_lookup,
            "../abgeordnete/",
        )
        name = pulse_html.esc(speaker.get("name"))
        name_html = f'<a href="{pulse_html.esc(mp_href)}">{name}</a>' if mp_href else name
        speakers.append(
            '<li class="speaker-row">'
            f'<strong>{name_html}</strong>'
            f'<span>{pulse_html.esc(speaker.get("party"))}</span>'
            f'<em>{pulse_html.esc(speaker.get("speech_count"))} Reden · {pulse_html.esc(pulse_html.format_int(int(speaker.get("char_count") or 0)))} Zeichen</em>'
            "</li>"
        )

    refs = []
    for ref in bill.get("protocol_refs") or []:
        refs.append(
            f'<a class="source-link" href="{pulse_html.esc(ref.get("href"))}">'
            f'BT-PlPr {pulse_html.esc(ref.get("protocol_number"))} · {pulse_html.esc(ref.get("top_id"))}'
            "</a>"
        )

    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{pulse_html.esc(bill.get('title'))} · Bundestag-Puls</title>
  {pulse_html.page_head(features)}
  <style>{bill_styles()}</style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(depth=1, active="bills", features=features)}
    <header class="page-header">
      <div>
        <nav class="local-nav" aria-label="Gesetz-Navigation">
          <a href="index.html">Alle Gesetze</a>
        </nav>
        <span class="eyebrow">{pulse_html.esc(bill.get('type'))}</span>
        <h1>{pulse_html.esc(bill.get('title'))}</h1>
        <p>Rohdatenübersicht zu Vorgang, Drucksachen, Plenarstellen, Rednern und Abstimmungen.</p>
      </div>
      <div class="actions">
        {'<button class="follow-button" type="button" data-follow-id="' + pulse_html.esc(bill['id']) + '" aria-pressed="false">Folgen</button>'}
      </div>
    </header>
    <section class="summary-grid">
      <div class="metric"><span>Letzter Schritt</span><strong>{pulse_html.esc(bill.get('latest_step'))}</strong></div>
      <div class="metric"><span>Letztes Datum</span><strong>{pulse_html.esc(bill.get('latest_date'))}</strong></div>
      <div class="metric"><span>Drucksachen</span><strong>{pulse_html.esc(len(bill.get('documents') or []))}</strong></div>
      <div class="metric"><span>Vorgang</span><strong>{pulse_html.esc(bill.get('vorgang_id') or 'n/a')}</strong></div>
    </section>
    <div class="content-grid">
      <main>
        <section class="panel">
          <h2>Überblick</h2>
          <div class="field-grid">
            <div class="field"><span>Eingebracht von</span><strong>{pulse_html.esc(introduced)}</strong></div>
            <div class="field"><span>Primäre Drucksache</span><strong>{pulse_html.esc(bill.get('primary_document') or 'n/a')}</strong></div>
            <div class="field"><span>Plenarstellen</span><strong>{pulse_html.esc(len(bill.get('protocol_refs') or []))}</strong></div>
            <div class="field"><span>Namentliche Abstimmungen</span><strong>{pulse_html.esc(len(bill.get('votes') or []))}</strong></div>
          </div>
        </section>
        <section class="panel">
          <h2>Verlauf</h2>
          <ul class="timeline">{''.join(events) if events else '<li>Keine Verlaufseinträge.</li>'}</ul>
        </section>
        <section class="panel">
          <h2>Drucksachen</h2>
          <ul class="doc-list">{''.join(docs) if docs else '<li>Keine verknüpften Drucksachen.</li>'}</ul>
        </section>
        <section class="panel">
          <h2>Rohdaten</h2>
          {render_bill_json_details("Normalisierter Bill-Datensatz", bill)}
        </section>
      </main>
      <aside>
        <section class="panel">
          <h2>Plenarstellen</h2>
          <div class="bill-meta">{''.join(refs) if refs else '<span class="badge">Keine Plenarstelle</span>'}</div>
        </section>
        <section class="panel">
          <h2>Rednerinnen und Redner</h2>
          <ul class="speaker-list">{''.join(speakers) if speakers else '<li>Keine Reden zugeordnet.</li>'}</ul>
        </section>
      </aside>
    </div>
    <footer>Diese Seite beschreibt nur Felder, die in den erzeugten Rohdaten vorhanden sind. Automatische Zusammenfassungen sind bewusst nicht enthalten. <a href="index.html">Gesetze verfolgen</a> · <a href="../overview.html">Plenarprotokoll-Katalog</a></footer>
  </div>
  {render_bill_script()}
  {pulse_html.page_scripts(features)}
</body>
</html>
"""


# Write the bills area: one detail page per bill, the index, and data/bills.json.
# Called through features/bills.py on every publication build. An empty data set
# produces a usable empty page rather than removing the area.
def write_bill_pages(
    output_dir: Path,
    bills: list[dict[str, Any]],
    mp_lookup: dict[str, int] | None = None,
    features: Selection | None = None,
) -> dict[str, Any]:
    features = features or publication_selection()
    bills_dir = output_dir / "bills"
    bills_dir.mkdir(parents=True, exist_ok=True)
    expected_pages = {f"{bill['slug']}.html" for bill in bills}
    for stale_page in bills_dir.glob("bill-*.html"):
        if stale_page.name not in expected_pages:
            stale_page.unlink()
    for bill in bills:
        (bills_dir / f"{bill['slug']}.html").write_text(render_bill_detail(bill, mp_lookup, features), encoding="utf-8")
    (bills_dir / "index.html").write_text(render_bills_index(bills, features), encoding="utf-8")
    data_path = output_dir / "data" / "bills.json"
    data_path.write_text(json.dumps(bills, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "count": len(bills),
        "index_path": bills_dir / "index.html",
        "data_path": data_path,
    }


# ---------------------------------------------------------------------------
# PAGES: abgeordnete/index.html and abgeordnete/<id>.html - "Abgeordnete"
#
# The MP area is assembled in three steps:
#   1. ingest_mdb_roster()    - pull the full MdB roster from DIP /person into
#                               the SQLite store, so the list is complete rather
#                               than limited to people seen in ingested sittings
#   2. collect_abgeordnete()  - read the store back and consolidate rows that
#                               describe the same person into one profile
#   3. render/write functions - emit the roster page and one profile per person
#
# MP pages are public; only full-roster acquisition is operator-controlled.
# ---------------------------------------------------------------------------


# DIP marks a person's roles in "funktion"; a Bundestag member has one that
# contains "MdB".
def _has_mdb_funktion(funktion: Any) -> bool:
    return any("mdb" in str(value).lower() for value in (funktion or []))


def ingest_mdb_roster(
    client: dip.ApiClient,
    store: Any,
    *,
    wahlperiode: int,
    profile_resolver: Any | None = None,
) -> dict[str, int]:
    """Fetch the full set of MdBs for a legislative period from DIP /person and
    upsert them as is_mdb=1 rows, optionally enriched with abgeordnetenwatch
    biographical data. Makes the Abgeordnete list complete rather than limited to
    speakers seen in ingested protocols."""
    stats = {"fetched": 0, "mdb": 0, "enriched": 0}
    if store is None:
        return stats
    persons = client.list_all("/person", {"f.wahlperiode": wahlperiode})
    stats["fetched"] = len(persons)
    now = pulse_store.utc_now()
    pulse_store.initialize(store)
    with store:
        for person in persons:
            compact = dip.compact_person(person)
            funktion = compact.get("funktion") or []
            if not _has_mdb_funktion(funktion):
                continue
            stats["mdb"] += 1
            fraktion_list = compact.get("fraktion") or []
            fraktion = fraktion_list[0] if fraktion_list else None
            party_name = dip.normalize_faction(fraktion) if fraktion else None
            party_id = pulse_store.upsert_party(store, party_name, now)
            display_name = (
                pulse_store.clean(compact.get("titel"))
                or pulse_store.clean(f"{compact.get('vorname') or ''} {compact.get('nachname') or ''}")
                or "Unbekannt"
            )

            profile_url = aw_id = birth_year = gender = profession = wahlkreis = bundesland = None
            if profile_resolver is not None:
                profile = profile_resolver.resolve(
                    first_name=compact.get("vorname"),
                    last_name=compact.get("nachname"),
                    fraktion=fraktion,
                )
                if profile:
                    profile_url = profile.get("url")
                    aw_id = profile.get("id")
                    birth_year = profile.get("year_of_birth")
                    gender = profile.get("sex")
                    profession = profile.get("profession")
                    bio = profile_resolver.fetch_bio(profile.get("id"))
                    if bio:
                        wahlkreis = bio.get("wahlkreis")
                        bundesland = bio.get("bundesland")
                    stats["enriched"] += 1

            pulse_store.upsert_mp(
                store,
                now=now,
                display_name=display_name,
                party_id=party_id,
                identity_key=pulse_store.mp_identity(aw_politician_id=aw_id, dip_person_id=compact.get("id")),
                dip_person_id=compact.get("id"),
                title=compact.get("titel"),
                function=funktion,
                wahlperiode=compact.get("wahlperiode"),
                profile_url=profile_url,
                birth_year=birth_year,
                gender=gender,
                profession=profession,
                wahlkreis=wahlkreis,
                bundesland=bundesland,
                aw_politician_id=aw_id,
                person_roles_json=pulse_store.dumps(funktion) if funktion else None,
                is_mdb=True,
            )
    return stats


# --- Identity consolidation -------------------------------------------------
#
# The same person can arrive from three directions with different keys: the DIP
# roster (dip_person_id), a protocol speaker (xml_redner_id) and an
# abgeordnetenwatch profile (aw_politician_id). The store holds them as separate
# mps rows; the helpers below decide which rows are the same human being.


def _parse_listish(value: Any) -> list[Any]:
    """Parse the list-shaped TEXT columns (function/wahlperiode/person_roles),
    which may be stored as JSON or as a Python list repr (e.g. "['MdB']")."""
    if not value:
        return []
    text = str(value).strip()
    for candidate in (text, text.replace("'", '"')):
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, list) else [parsed]
        except (json.JSONDecodeError, ValueError):
            continue
    return [text]


def _mp_keys(row: dict[str, Any]) -> list[str]:
    """External identity keys for an MP row, used to link rows that describe the
    same person across sources (DIP roster vs. protocol speaker)."""
    keys: list[str] = []
    if row.get("aw_politician_id") is not None:
        keys.append(f"aw:{row['aw_politician_id']}")
    if row.get("dip_person_id"):
        keys.append(f"dip:{row['dip_person_id']}")
    if row.get("xml_redner_id"):
        keys.append(f"xml:{row['xml_redner_id']}")
    return keys


# The external ids a row carries, bucketed by kind. Two rows may only be merged
# by name+party when their id buckets do not contradict each other.
def _mp_external_ids(row: dict[str, Any]) -> dict[str, set[str]]:
    ids: dict[str, set[str]] = {"aw": set(), "dip": set(), "xml": set(), "profile": set()}
    if row.get("aw_politician_id") is not None:
        ids["aw"].add(str(row["aw_politician_id"]))
    if row.get("dip_person_id"):
        ids["dip"].add(str(row["dip_person_id"]))
    if row.get("xml_redner_id"):
        ids["xml"].add(str(row["xml_redner_id"]))
    if row.get("profile_url"):
        ids["profile"].add(str(row["profile_url"]))
    return ids


# Union of the id buckets across all rows already merged into one person.
def _merge_external_ids(rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    merged: dict[str, set[str]] = {"aw": set(), "dip": set(), "xml": set(), "profile": set()}
    for row in rows:
        for kind, values in _mp_external_ids(row).items():
            merged[kind].update(values)
    return merged


# True when both sides carry ids of the same kind and none of them overlap -
# that is positive evidence of two different people, so no merge.
def _external_ids_conflict(left: dict[str, set[str]], right: dict[str, set[str]]) -> bool:
    for kind in left:
        if left[kind] and right[kind] and not (left[kind] & right[kind]):
            return True
    return False


def _clean_mp_name(name: Any) -> str:
    # Roster display names are the verbose DIP "titel" ("Dr. Carolin Wagner, MdB,
    # SPD"); trim the ", MdB…" tail for a clean profile heading. Speaker names
    # (plain) pass through unchanged.
    text = str(name or "").strip()
    return text.split(", MdB")[0].strip() or text


# Casefolded, whitespace-collapsed name used as a merge bucket key.
def _normalized_mp_name(name: Any) -> str:
    return re.sub(r"\s+", " ", _clean_mp_name(name).casefold()).strip()


# Party names differ in spelling between sources ("BÜNDNIS 90/DIE GRÜNEN" vs
# "Grüne"), so compare the normalised token set instead of the raw string.
def _normalized_mp_party(party: Any) -> str:
    text = str(party or "").strip()
    if not text:
        return ""
    normalized = dip.normalize_faction(text)
    tokens = sorted(aw._party_tokens(normalized))
    return "|".join(tokens) if tokens else normalized.casefold()


def collect_abgeordnete(
    conn: sqlite3.Connection,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[int, int]]:
    """Read MPs with party, speeches, and roll-call votes for the Abgeordnete
    pages, consolidating rows that describe the same person (the DIP roster row
    carries the bio; the protocol-speaker row carries the speeches). Returns the
    consolidated MPs, a lookup from every external id to the page id (so
    speaker lists can link without dangling), and a map from every mps.id to
    its canonical (page) id - the third value feeds the Daten export's
    mp_canonical table, unconditioned by whether the person gets a page. One
    grouped query each avoids N+1."""
    # One query per relation, then grouped in Python - three flat queries beat
    # a per-MP query (N+1) by a wide margin at roster size.
    base = conn.execute(
        """
        SELECT m.id, m.display_name, m.title, m.function, m.wahlperiode,
               m.profile_url, m.birth_year, m.gender, m.profession,
               m.wahlkreis, m.bundesland, m.aw_politician_id, m.person_roles_json,
               m.is_mdb, m.dip_person_id, m.xml_redner_id,
               p.name AS party
        FROM mps m
        LEFT JOIN parties p ON m.party_id = p.id
        """
    ).fetchall()
    rows = [dict(r) for r in base]

    # All speeches with their protocol and agenda-item context, newest sitting
    # first. Feeds the "Reden im Bundestag" list on a profile page.
    speeches_by_mp: dict[int, list[dict[str, Any]]] = {}
    for row in conn.execute(
        """
        SELECT s.mp_id, s.rede_id, s.page, s.char_count, s.snippet, s.sequence,
               p.document_number, p.date AS protocol_date,
               ai.heading, ai.item_index
        FROM speeches s
        JOIN protocols p ON s.protocol_id = p.id
        LEFT JOIN agenda_items ai ON s.agenda_item_id = ai.id
        WHERE s.mp_id IS NOT NULL
        ORDER BY p.date DESC, s.sequence ASC
        """
    ).fetchall():
        speeches_by_mp.setdefault(row["mp_id"], []).append(
            {
                "rede_id": row["rede_id"],
                "page": row["page"],
                "char_count": row["char_count"] or 0,
                "snippet": row["snippet"],
                "document_number": row["document_number"],
                "date": row["protocol_date"],
                "heading": row["heading"],
                "item_index": row["item_index"],
            }
        )

    # All roll-call votes cast by an MP, newest first. Feeds the "Namentliche
    # Abstimmungen" list and the participation tally.
    votes_by_mp: dict[int, list[dict[str, Any]]] = {}
    for row in conn.execute(
        """
        SELECT vm.mp_id, vm.vote, v.id AS vote_id, v.date, v.title, v.topic, v.detail_url
        FROM vote_members vm
        JOIN votes v ON vm.vote_id = v.id
        WHERE vm.mp_id IS NOT NULL
        ORDER BY v.date DESC
        """
    ).fetchall():
        votes_by_mp.setdefault(row["mp_id"], []).append(
            {
                "vote_id": row["vote_id"],
                "vote": row["vote"],
                "date": row["date"],
                "title": row["title"],
                "topic": row["topic"],
                "detail_url": row["detail_url"],
            }
        )

    # Union-find: link rows that share any external id into one person.
    parent = {row["id"]: row["id"] for row in rows}

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # Pass 1: merge rows that share any external id. This is safe evidence.
    first_for_key: dict[str, int] = {}
    for row in rows:
        for key in _mp_keys(row):
            if key in first_for_key:
                union(row["id"], first_for_key[key])
            else:
                first_for_key[key] = row["id"]

    def component_external_ids(node: int) -> dict[str, set[str]]:
        root = find(node)
        return _merge_external_ids([row for row in rows if find(row["id"]) == root])

    def can_union_by_name_party(a: int, b: int) -> bool:
        return not _external_ids_conflict(component_external_ids(a), component_external_ids(b))

    # Pass 2: merge rows with the same name and party, but only when the two
    # sides' external ids do not contradict each other. This is what bridges the
    # DIP roster row (which has the biography) and the protocol speaker row
    # (which has the speeches) for a person whose abgeordnetenwatch id was never
    # resolved.
    name_party_buckets: dict[tuple[str, str], list[int]] = {}
    for row in rows:
        name_key = _normalized_mp_name(row.get("display_name"))
        party_key = _normalized_mp_party(row.get("party"))
        if name_key and party_key:
            name_party_buckets.setdefault((name_key, party_key), []).append(row["id"])

    for ids in name_party_buckets.values():
        ids.sort()
        for index, left in enumerate(ids):
            for right in ids[index + 1 :]:
                if find(left) != find(right) and can_union_by_name_party(left, right):
                    union(left, right)

    # Group the merged rows back into one bucket per person.
    components: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        components.setdefault(find(row["id"]), []).append(row)

    mps: list[dict[str, Any]] = []
    lookup: dict[str, int] = {}
    canonical_by_mp_id: dict[int, int] = {}
    # Collapse each bucket into a single MP record: the roster row wins for the
    # biography fields, speeches and votes are pooled from every member row.
    for members in components.values():
        # Canonical row: prefer an MdB (roster) row, then lowest id, for a stable
        # page id shared by the list and the profile.
        members.sort(key=lambda r: (0 if r["is_mdb"] else 1, r["id"]))
        cid = members[0]["id"]
        for r in members:
            canonical_by_mp_id[r["id"]] = cid

        def first(field: str) -> Any:
            for r in members:
                if r.get(field) not in (None, ""):
                    return r[field]
            return None

        # Pool speeches from every row of this person, newest first.
        merged_speeches: list[dict[str, Any]] = []
        for r in members:
            merged_speeches.extend(speeches_by_mp.get(r["id"], []))
        merged_speeches.sort(key=lambda s: (s.get("date") or ""), reverse=True)

        # Pool votes, de-duplicated by vote id (the same vote can be reachable
        # through more than one row), then tally the directions for the header.
        merged_votes: list[dict[str, Any]] = []
        seen_votes: set[Any] = set()
        for r in members:
            for vote in votes_by_mp.get(r["id"], []):
                if vote["vote_id"] in seen_votes:
                    continue
                seen_votes.add(vote["vote_id"])
                merged_votes.append(vote)
        tally = {"yes": 0, "no": 0, "abstain": 0, "absent": 0}
        for vote in merged_votes:
            key = (vote["vote"] or "").lower()
            if key in tally:
                tally[key] += 1

        mp = {
            "id": cid,
            "name": _clean_mp_name(first("display_name")),
            "party": first("party"),
            "title": first("title"),
            "function": _parse_listish(first("function")),
            "wahlperioden": _parse_listish(first("wahlperiode")),
            "person_roles": _parse_listish(first("person_roles_json")),
            "profile_url": first("profile_url"),
            "birth_year": first("birth_year"),
            "gender": first("gender"),
            "profession": first("profession"),
            "wahlkreis": first("wahlkreis"),
            "bundesland": first("bundesland"),
            "aw_politician_id": first("aw_politician_id"),
            "is_mdb": any(r["is_mdb"] for r in members),
            "speech_count": len(merged_speeches),
            "total_chars": sum(s["char_count"] for s in merged_speeches),
            "speeches": merged_speeches,
            "votes": merged_votes,
            "vote_tally": tally,
        }
        mps.append(mp)
        # Only persons that get a page contribute to the link lookup.
        if mp["is_mdb"] or mp["speech_count"] > 0:
            for r in members:
                for key in _mp_keys(r):
                    lookup[key] = cid

    # Stable, useful order: most speeches first, then alphabetical.
    mps.sort(key=lambda mp: (-(mp["speech_count"] or 0), str(mp["name"]).lower()))
    return mps, lookup, canonical_by_mp_id


# The MP pages reuse the bill stylesheet and add the roster table, the party
# filter chips and the vote/speech row layouts on top of it.
def abgeordnete_styles() -> str:
    return bill_styles() + """
    .filter-bar {
      display:flex;
      flex-wrap:wrap;
      gap:10px;
      align-items:center;
      margin-top:18px;
    }
    .filter-bar input[type="search"] {
      flex:1 1 260px;
      min-height:38px;
      padding:8px 12px;
      border:1px solid var(--line);
      border-radius:8px;
      background:#fff;
      color:var(--ink);
      font:inherit;
    }
    .party-filters { display:flex; flex-wrap:wrap; gap:6px; }
    .party-chip {
      min-height:30px;
      padding:4px 11px;
      border:1px solid var(--line);
      border-radius:999px;
      background:#fff;
      color:#333a45;
      font:inherit;
      font-size:13px;
      font-weight:650;
      cursor:pointer;
    }
    .party-chip.is-active { border-color:var(--blue); background:#eef5ff; color:var(--blue); }
    .mp-table { width:100%; border-collapse:collapse; margin-top:16px; font-size:14px; }
    .mp-table th, .mp-table td {
      text-align:left;
      padding:9px 10px;
      border-bottom:1px solid #eef1f5;
      vertical-align:top;
    }
    .mp-table th { font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:var(--muted); }
    .mp-table td.num { text-align:right; font-variant-numeric:tabular-nums; }
    .mp-table tr[hidden] { display:none; }
    .mp-empty { margin-top:16px; }
    .mp-notice {
      margin:16px 0 0;
      padding:11px 13px;
      border-left:3px solid #c49024;
      background:#fbf6e7;
      color:#654b13;
      line-height:1.5;
    }
    .vote-row { display:grid; grid-template-columns:96px minmax(0,1fr) auto; gap:10px; padding-bottom:10px; border-bottom:1px solid #eef1f5; font-size:13px; }
    .vote-row:last-child { border-bottom:0; padding-bottom:0; }
    .vote-row time { color:var(--muted); }
    .vote-badge { align-self:start; }
    .vote-badge.yes { border-color:#89c5ba; background:#e7f6f3; color:#0f5f59; }
    .vote-badge.no { border-color:#e0a3a3; background:#fbecec; color:#8a2b2b; }
    .vote-badge.abstain { border-color:#d9c48a; background:#fbf6e7; color:#7a5a10; }
    .vote-badge.absent { color:var(--muted); }
    .speech-row { display:grid; grid-template-columns:130px minmax(0,1fr); gap:10px; padding-bottom:10px; border-bottom:1px solid #eef1f5; font-size:13px; }
    .speech-row:last-child { border-bottom:0; padding-bottom:0; }
    .speech-row .meta { color:var(--muted); }
    @media (max-width: 640px) {
      .vote-row, .speech-row { grid-template-columns:1fr; gap:4px; }
    }
"""


# Inline script for abgeordnete/index.html: free-text search over name /
# constituency / state plus a party chip filter, applied by toggling row
# visibility. Purely client-side over the rows already in the HTML.
def render_abgeordnete_script() -> str:
    return """
  <script>
    (() => {
      const search = document.querySelector("[data-mp-search]");
      const rows = Array.from(document.querySelectorAll("[data-mp-row]"));
      const partyButtons = Array.from(document.querySelectorAll("[data-party-filter]"));
      const counter = document.querySelector("[data-mp-count]");
      let activeParty = "";
      const apply = () => {
        const q = (search ? search.value : "").trim().toLowerCase();
        let visible = 0;
        rows.forEach((row) => {
          const matchesText = !q || row.dataset.search.includes(q);
          const matchesParty = !activeParty || row.dataset.party === activeParty;
          const show = matchesText && matchesParty;
          row.hidden = !show;
          if (show) visible += 1;
        });
        if (counter) counter.textContent = String(visible);
      };
      if (search) search.addEventListener("input", apply);
      partyButtons.forEach((btn) => {
        btn.addEventListener("click", () => {
          activeParty = activeParty === btn.dataset.partyFilter ? "" : btn.dataset.partyFilter;
          partyButtons.forEach((b) => b.classList.toggle("is-active", b.dataset.partyFilter === activeParty));
          apply();
        });
      });
      apply();
    })();
  </script>
"""


# "Wahlkreis · Bundesland" for the roster table, or an em dash when unknown.
def _location_label(mp: dict[str, Any]) -> str:
    parts = [mp.get("wahlkreis"), mp.get("bundesland")]
    return " · ".join(p for p in parts if p) or "—"


# PAGE: abgeordnete/index.html - the filterable MP roster.
def _mp_domain_notice(domain: str, state: str) -> str:
    copy = {
        ("roster", "not_requested"): "Hinweis: Der vollständige Abgeordnetenkader wurde nicht abgerufen.",
        ("roster", "partial"): "Teilweise verfügbar: Der Abgeordnetenkader ist unvollständig.",
        ("roster", "failed"): "Nicht verfügbar: Der Abgeordnetenkader konnte nicht abgerufen werden.",
        ("profiles", "not_requested"): "Hinweis: Profilverknüpfungen wurden nicht abgerufen.",
        ("profiles", "partial"): "Teilweise verfügbar: Einige Profilverknüpfungen fehlen.",
        ("profiles", "failed"): "Nicht verfügbar: Profilverknüpfungen konnten nicht abgerufen werden.",
    }.get((domain, state))
    return f'<p class="mp-notice">{pulse_html.esc(copy)}</p>' if copy else ""


def render_abgeordnete_index(
    mps: list[dict[str, Any]],
    features: Selection | None = None,
    publication_domains: dict[str, Any] | None = None,
) -> str:
    features = features or publication_selection()
    # Only actual MdBs are listed. People who merely appear as speakers
    # (ministers, Bundesrat guests) still get a profile page - see
    # write_abgeordnete_pages - they just do not clutter the roster.
    listed = [mp for mp in mps if mp.get("is_mdb")]
    parties = sorted({mp["party"] for mp in listed if mp.get("party")})
    party_chips = "".join(
        f'<button class="party-chip" type="button" data-party-filter="{pulse_html.esc(party)}">{pulse_html.esc(party)}</button>'
        for party in parties
    )
    rows = []
    for mp in listed:
        search_key = " ".join(
            str(value).lower()
            for value in (mp.get("name"), mp.get("party"), mp.get("wahlkreis"), mp.get("bundesland"))
            if value
        )
        rows.append(
            f"""
            <tr data-mp-row data-party="{pulse_html.esc(mp.get('party') or '')}" data-search="{pulse_html.esc(search_key)}">
              <td><a href="{mp['id']}.html">{pulse_html.esc(mp.get('name'))}</a></td>
              <td>{pulse_html.esc(mp.get('party') or '—')}</td>
              <td>{pulse_html.esc(_location_label(mp))}</td>
              <td class="num">{pulse_html.esc(mp.get('speech_count') or 0)}</td>
            </tr>
            """
        )

    with_speeches = sum(1 for mp in listed if (mp.get("speech_count") or 0) > 0)
    total_speeches = sum(mp.get("speech_count") or 0 for mp in listed)
    domains = publication_domains or {}
    notices = "".join(
        (
            _mp_domain_notice("roster", str((domains.get("roster") or {}).get("acquisition_state") or "complete")),
            _mp_domain_notice("profiles", str((domains.get("profiles") or {}).get("acquisition_state") or "complete")),
        )
    )
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Abgeordnete</title>
  {pulse_html.page_head(features)}
  <style>{abgeordnete_styles()}</style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(depth=1, active="abgeordnete", features=features)}
    <header class="page-header">
      <div>
        <h1>Abgeordnete</h1>
        <p>Vollständige Liste der Mitglieder des Bundestages der laufenden Wahlperiode aus den DIP-Personendaten, ergänzt um abgeordnetenwatch.de-Profile. Filtern nach Name oder Fraktion.</p>
      </div>
      <div class="follow-summary">
        <span class="eyebrow">Angezeigt</span>
        <strong data-mp-count>{pulse_html.esc(len(listed))}</strong>
      </div>
    </header>
    <section class="summary-grid">
      <div class="metric"><span>Abgeordnete</span><strong>{pulse_html.esc(len(listed))}</strong></div>
      <div class="metric"><span>Fraktionen</span><strong>{pulse_html.esc(len(parties))}</strong></div>
      <div class="metric"><span>Mit Reden</span><strong>{pulse_html.esc(with_speeches)}</strong></div>
      <div class="metric"><span>Reden gesamt</span><strong>{pulse_html.esc(total_speeches)}</strong></div>
    </section>
    {notices}
    <div class="filter-bar">
      <input type="search" data-mp-search placeholder="Nach Name, Wahlkreis oder Bundesland suchen…" aria-label="Abgeordnete suchen">
      <div class="party-filters" role="group" aria-label="Nach Fraktion filtern">{party_chips}</div>
    </div>
    {'<table class="mp-table"><thead><tr><th>Name</th><th>Fraktion</th><th>Wahlkreis / Bundesland</th><th class="num">Reden</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>' if rows else '<p class="mp-empty">Noch keine Abgeordnetendaten veröffentlicht. Bei einem kontrollierten Update kann der vollständige DIP-Kader mit <code>--enrich mp-roster</code> ergänzt werden.</p>'}
    <footer>Personenstammdaten aus der DIP-API; Wahlkreis, Bundesland, Geburtsjahr und Beruf von abgeordnetenwatch.de (CC0). <a href="../sources.html">Quellen und Methode</a></footer>
  </div>
  {render_abgeordnete_script()}
  {pulse_html.page_scripts(features)}
</body>
</html>
"""


# PAGE: abgeordnete/<id>.html - one MP profile.
#
# The <id> in the file name is the canonical mps row id chosen by
# collect_abgeordnete, which is also what mp_lookup maps every external id to,
# so speaker links from dossier and bill pages resolve here.
def render_abgeordnete_detail(
    mp: dict[str, Any],
    features: Selection | None = None,
    publication_domains: dict[str, Any] | None = None,
) -> str:
    features = features or publication_selection()
    # Header link out to the abgeordnetenwatch.de profile, when one was resolved.
    profile_link = ""
    if mp.get("profile_url"):
        profile_link = (
            f'<a class="source-link" href="{pulse_html.esc(pulse_html.source_url(mp["profile_url"], "abgeordnetenwatch"))}" target="_blank" rel="noopener">'
            "abgeordnetenwatch.de-Profil ↗</a>"
        )

    # "Überblick" grid: only fields that actually exist in the data are shown -
    # the page never invents a placeholder biography.
    overview_fields = []
    if mp.get("birth_year"):
        overview_fields.append(f'<div class="field"><span>Geburtsjahr</span><strong>{pulse_html.esc(mp["birth_year"])}</strong></div>')
    if mp.get("profession"):
        overview_fields.append(f'<div class="field"><span>Beruf</span><strong>{pulse_html.esc(mp["profession"])}</strong></div>')
    if mp.get("bundesland"):
        overview_fields.append(f'<div class="field"><span>Bundesland</span><strong>{pulse_html.esc(mp["bundesland"])}</strong></div>')
    wahlperioden = ", ".join(str(w) for w in (mp.get("wahlperioden") or []))
    if wahlperioden:
        overview_fields.append(f'<div class="field"><span>Wahlperioden</span><strong>{pulse_html.esc(wahlperioden)}</strong></div>')
    # Committees only when DIP carries roles beyond plain "MdB".
    committees = [r for r in (mp.get("person_roles") or []) if str(r).strip().lower() != "mdb"]
    if committees:
        overview_fields.append(f'<div class="field"><span>Funktionen</span><strong>{pulse_html.esc(", ".join(str(c) for c in committees))}</strong></div>')
    if not overview_fields:
        overview_fields.append('<div class="field"><span>Hinweis</span><strong>Keine weiteren Stammdaten verfügbar.</strong></div>')

    speeches = []
    for speech in mp.get("speeches") or []:
        slug = slugify_document_number(speech.get("document_number") or "")
        href = f"../protocols/plenarprotokoll-{slug}.html"
        page = f'S. {speech["page"]}' if speech.get("page") else ""
        heading = pulse_html.esc(speech.get("heading") or "Tagesordnungspunkt")
        snippet = pulse_html.esc((speech.get("snippet") or "").strip())
        speeches.append(
            '<li class="speech-row">'
            f'<span class="meta"><a href="{pulse_html.esc(href)}">BT-PlPr {pulse_html.esc(speech.get("document_number"))}</a><br>{pulse_html.esc(speech.get("date") or "")} · {pulse_html.esc(page)}</span>'
            f'<span><strong>{heading}</strong>{("<br>" + snippet) if snippet else ""}</span>'
            "</li>"
        )

    votes = []
    for vote in mp.get("votes") or []:
        direction = (vote.get("vote") or "").lower()
        label = {"yes": "Ja", "no": "Nein", "abstain": "Enthalten", "absent": "Abwesend"}.get(direction, vote.get("vote") or "—")
        title = pulse_html.esc(vote.get("title") or vote.get("topic") or "Namentliche Abstimmung")
        if vote.get("detail_url"):
            title = (
                f'<a href="{pulse_html.esc(pulse_html.source_url(vote.get("detail_url"), "bundestag-roll-call"))}">{title}</a>'
            )
        votes.append(
            '<li class="vote-row">'
            f'<time>{pulse_html.esc(vote.get("date") or "")}</time>'
            f'<span>{title}</span>'
            f'<span class="badge vote-badge {pulse_html.esc(direction)}">{pulse_html.esc(label)}</span>'
            "</li>"
        )

    tally = mp.get("vote_tally") or {}
    participation = tally.get("yes", 0) + tally.get("no", 0) + tally.get("abstain", 0)
    domains = publication_domains or {}
    notices = "".join(
        (
            _mp_domain_notice("roster", str((domains.get("roster") or {}).get("acquisition_state") or "complete")),
            _mp_domain_notice("profiles", str((domains.get("profiles") or {}).get("acquisition_state") or "complete")),
        )
    )
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{pulse_html.esc(mp.get('name'))} · Bundestag-Puls</title>
  {pulse_html.page_head(features)}
  <style>{abgeordnete_styles()}</style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(depth=1, active="abgeordnete", features=features)}
    <header class="page-header">
      <div>
        <nav class="local-nav" aria-label="Abgeordneten-Navigation">
          <a href="index.html">Alle Abgeordnete</a>
        </nav>
        <span class="eyebrow">{pulse_html.esc(mp.get('party') or 'Fraktion unbekannt')}</span>
        <h1>{pulse_html.esc(mp.get('name'))}</h1>
        <p>Stammdaten aus der DIP-API und abgeordnetenwatch.de sowie alle in den erfassten Plenarprotokollen erkannten Reden.</p>
      </div>
      <div class="actions">{profile_link}</div>
    </header>
    <section class="summary-grid">
      <div class="metric"><span>Fraktion</span><strong>{pulse_html.esc(mp.get('party') or '—')}</strong></div>
      <div class="metric"><span>Wahlkreis</span><strong>{pulse_html.esc(mp.get('wahlkreis') or '—')}</strong></div>
      <div class="metric"><span>Reden</span><strong>{pulse_html.esc(mp.get('speech_count') or 0)}</strong></div>
      <div class="metric"><span>Namentliche Abstimmungen</span><strong>{pulse_html.esc(participation)}</strong></div>
    </section>
    {notices}
    <div class="content-grid">
      <main>
        <section class="panel">
          <h2>Überblick</h2>
          <div class="field-grid">{''.join(overview_fields)}</div>
        </section>
        <section class="panel">
          <h2>Reden im Bundestag</h2>
          <ul class="doc-list">{''.join(speeches) if speeches else '<li>In den bisher erfassten Plenarprotokollen wurden keine Reden erkannt.</li>'}</ul>
        </section>
      </main>
      <aside>
        <section class="panel">
          <h2>Namentliche Abstimmungen</h2>
          <ul class="doc-list">{''.join(votes) if votes else '<li>Keine namentlichen Abstimmungen erfasst.</li>'}</ul>
        </section>
      </aside>
    </div>
    <footer>Diese Seite zeigt nur Felder, die in den Rohdaten vorhanden sind. <a href="index.html">Alle Abgeordnete</a> · <a href="../sources.html">Quellen und Methode</a></footer>
  </div>
  {pulse_html.page_scripts(features)}
</body>
</html>
"""


# Write the Abgeordnete area: profile pages, the roster index and
# data/abgeordnete.json. Called through features/abgeordnete.py.
def write_abgeordnete_pages(
    output_dir: Path,
    mps: list[dict[str, Any]],
    features: Selection | None = None,
    publication_domains: dict[str, Any] | None = None,
) -> dict[str, Any]:
    features = features or publication_selection()
    abg_dir = output_dir / "abgeordnete"
    abg_dir.mkdir(parents=True, exist_ok=True)
    # Detail pages for MdBs and for anyone who actually spoke (so cross-links from
    # protocol/bill speaker lists never dangle, even for ministers/guests).
    detail_mps = [mp for mp in mps if mp.get("is_mdb") or (mp.get("speech_count") or 0) > 0]
    expected_pages = {f"{mp['id']}.html" for mp in detail_mps}
    for stale_page in abg_dir.glob("*.html"):
        if stale_page.name != "index.html" and stale_page.name not in expected_pages:
            stale_page.unlink()
    for mp in detail_mps:
        (abg_dir / f"{mp['id']}.html").write_text(
            render_abgeordnete_detail(mp, features, publication_domains),
            encoding="utf-8",
        )
    (abg_dir / "index.html").write_text(
        render_abgeordnete_index(mps, features, publication_domains),
        encoding="utf-8",
    )
    data_path = output_dir / "data" / "abgeordnete.json"
    data_path.write_text(json.dumps(mps, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    listed = sum(1 for mp in mps if mp.get("is_mdb"))
    return {"count": listed, "detail_count": len(detail_mps), "index_path": abg_dir / "index.html"}


# ---------------------------------------------------------------------------
# PAGES: fakt/index.html, fakt/<period_key>.html, fakt/<period_key>-<metric>.svg,
# fakt/methodik.html - "Fakt der Woche" (T6).
#
# scripts/facts.py computes and persists the rule (T5/T10) but keeps only
# stable receipt keys, never a name (D2A/D14): a rebuilt store must not carry
# a stale display name. This module reads the three tables back and resolves
# every receipt to its row through a direct join - the join key the plan
# measured for each of the five receipt kinds - then hands the rebuilt row to
# the same card helpers (facts.card_title, facts.card_sentence, ...) the A0
# replay already uses, so a published card and a sample card render
# identically. The outbound page link (to an MP profile or a protocol page)
# is a second, separate resolution: resolve_entity_link, shared with the
# recipe tables (D6A).
# ---------------------------------------------------------------------------

FACTS_METRIC_LABELS = {
    "knappste-abstimmung": "Abstimmung",
    "meiste-abweichler": "Abweichler",
    "laengste-debatte": "Debatte",
    "laengste-rede": "Rede",
    "laengste-sitzung": "Sitzung",
    "erste-reden": "Erste Reden",
    "aktivste-abgeordnete": "Aktivste Abgeordnete",
    "meistdiskutierter-vorgang": "Meistdiskutierter Vorgang",
}

#: (plural noun, "this <period>" demonstrative phrase) per period_kind, for
#: wording that must not assume every fact is a weekly one (T11). The
#: demonstrative is its own phrase, not "diese/dieser" + noun, because German
#: grammatical gender differs between "diese Sitzungswoche" (feminine) and
#: "dieser Monat" (masculine).
_PERIOD_NOUN = {
    "week": ("Sitzungswochen", "Diese Sitzungswoche"),
    "month": ("Monate", "Dieser Monat"),
}


def _facts_page_style() -> str:
    return f"""
    :root {{
      --ink:#171a1f;
      --muted:#606a78;
      --line:#d9dee6;
      --paper:#f7f8fa;
      --panel:#ffffff;
      --blue:#174ea6;
      --blue-soft:#eef5ff;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color:var(--ink);
      background:var(--paper);
    }}
    a {{ color:var(--blue); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .shell {{ max-width:1000px; margin:0 auto; padding:28px 22px; }}
    {pulse_html.global_header_styles()}
    h1 {{ margin:0 0 8px; font-size:32px; line-height:1.15; }}
    h2 {{ font-size:20px; margin:34px 0 10px; }}
    p.lead {{ color:var(--muted); max-width:72ch; }}
    .eyebrow {{
      display:block; font-size:12px; font-weight:700; letter-spacing:.04em;
      text-transform:uppercase; color:var(--muted); margin-bottom:6px;
    }}
    .table-scroll {{ overflow-x:auto; margin-top:20px; }}
    table.facts-archive {{ border-collapse:collapse; width:100%; font-size:14px; }}
    table.facts-archive th, table.facts-archive td {{
      padding:8px 10px; border-bottom:1px solid var(--line); text-align:left; white-space:nowrap;
    }}
    table.facts-archive td.num, table.facts-archive th.num {{ text-align:right; }}
    tr.archive-row.greyed td {{ color:var(--muted); }}
    td.muted {{ color:var(--muted); }}
    .fact-block {{ padding:22px 0; border-bottom:1px solid var(--line); }}
    .fact-card {{ display:block; max-width:320px; height:auto; margin:0 0 14px; border:1px solid var(--line); border-radius:8px; }}
    .fact-sentence {{ font-size:18px; max-width:60ch; }}
    .caveat {{ color:var(--muted); font-size:13px; max-width:60ch; }}
    .baseline {{ color:var(--muted); font-size:13px; }}
    .sources ul, .series ol {{ margin:4px 0 0; padding-left:18px; font-size:13px; }}
    .sources li, .series li {{ margin-bottom:2px; }}
    .series li.current {{ font-weight:700; color:var(--ink); }}
    details.recipe-sql {{ margin-top:10px; }}
    details.recipe-sql pre {{
      overflow-x:auto; background:var(--panel); border:1px solid var(--line);
      border-radius:6px; padding:10px; font-size:12px;
    }}
    ul.method-list, ol.method-list {{ list-style:none; margin:0; padding:0; }}
    ul.method-list li, ol.method-list li {{ padding:10px 0; border-bottom:1px solid var(--line); }}
    ul.method-list strong, ol.method-list strong {{ display:block; margin-bottom:2px; }}
    ul.method-list span, ol.method-list span {{ color:var(--muted); font-size:13px; }}
    footer {{ margin-top:28px; color:var(--muted); font-size:12px; }}
    """


def _ensure_lead_position_tables(conn: sqlite3.Connection) -> None:
    """Materialize LEAD_POSITION_CTE/LEAD_PROCEEDING_CTE once per connection.

    _fact_speech_citation/_fact_agenda_item_citation/_fact_proceeding_citation
    are each called once per receipt (a monthly grouped_extreme fact can cite
    dozens), and every call used to re-run the full proceeding_positions
    scan+GROUP BY these compute, even though the result is the same for every
    receipt in the build. ``CREATE TEMP TABLE IF NOT EXISTS`` makes repeat
    calls on the same connection a no-op, so callers can call this freely.
    """
    conn.execute(
        "CREATE TEMP TABLE IF NOT EXISTS _lead_position_topic AS\n"
        + facts.LEAD_POSITION_CTE
        + "SELECT agenda_item_id, title FROM lead_position"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lead_position_topic ON _lead_position_topic(agenda_item_id)"
    )
    conn.execute(
        "CREATE TEMP TABLE IF NOT EXISTS _lead_position_proceeding AS\n"
        + facts.LEAD_PROCEEDING_CTE
        + "SELECT agenda_item_id, proceeding_id FROM lead_position"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_lead_position_proceeding ON _lead_position_proceeding(agenda_item_id)"
    )


def _fact_speech_citation(
    conn: sqlite3.Connection,
    document_number: Any,
    rede_id: Any,
    page: Any,
    page_quadrant: Any,
) -> dict[str, Any] | None:
    """Resolve a speech receipt to its row (D14: (document_number, rede_id), or
    the page anchor (document_number, page, page_quadrant) for a synthetic id;
    0 duplicates on either key, measured 2026-09-22)."""
    if rede_id:
        where, params = "p.document_number = ? AND s.rede_id = ?", (str(document_number), str(rede_id))
    else:
        # IS, not =: page_quadrant is NULL whenever the XML page reference
        # carries neither a div nor a seitenbereich attribute (a legitimate,
        # common case - validate_dip_protocol.py's quadrant extraction), and
        # SQL "NULL = NULL" is never true, so "=" silently failed to resolve
        # every citation with no quadrant.
        where = "p.document_number = ? AND s.page = ? AND s.page_quadrant IS ?"
        params = (str(document_number), page, page_quadrant)
    row = conn.execute(
        f"""
        SELECT s.id, s.rede_id, s.page, s.page_quadrant, m.display_name,
               COALESCE(NULLIF(s.fraktion, ''), pa.name) AS fraktion,
               m.xml_redner_id, m.aw_politician_id, m.dip_person_id,
               ai.heading, lp.title AS proceeding_title, p.document_number
        FROM speeches s
        JOIN mps m ON m.id = s.mp_id
        LEFT JOIN parties pa ON pa.id = m.party_id
        JOIN protocols p ON p.id = s.protocol_id
        LEFT JOIN agenda_items ai ON ai.id = s.agenda_item_id
        LEFT JOIN _lead_position_topic lp ON lp.agenda_item_id = s.agenda_item_id
        WHERE {where}
        """,
        params,
    ).fetchone()
    return dict(row) if row else None


def _fact_agenda_item_citation(
    conn: sqlite3.Connection, document_number: Any, page: Any, page_quadrant: Any
) -> dict[str, Any] | None:
    """(document_number, page, page_quadrant) against page_start/page_start_quadrant
    (0 duplicates, measured 2026-09-22)."""
    row = conn.execute(
        """
        SELECT ai.id, ai.heading, lp.title AS proceeding_title, p.document_number
        FROM agenda_items ai
        JOIN protocols p ON p.id = ai.protocol_id
        LEFT JOIN _lead_position_topic lp ON lp.agenda_item_id = ai.id
        WHERE p.document_number = ? AND ai.page_start = ? AND ai.page_start_quadrant IS ?
        """,
        (str(document_number), page, page_quadrant),
    ).fetchone()
    return dict(row) if row else None


def _fact_proceeding_citation(
    conn: sqlite3.Connection, document_number: Any, page: Any, page_quadrant: Any
) -> dict[str, Any] | None:
    """(document_number, page, page_quadrant) against the agenda item's
    page_start, resolved through its lead position to the Vorgang
    (proceedings.id) it belongs to -- meistdiskutierter-vorgang's receipt."""
    row = conn.execute(
        """
        SELECT ai.id, lp.proceeding_id, pr.title, pr.proceeding_type, p.document_number
        FROM agenda_items ai
        JOIN protocols p ON p.id = ai.protocol_id
        JOIN _lead_position_proceeding lp ON lp.agenda_item_id = ai.id
        JOIN proceedings pr ON pr.id = lp.proceeding_id
        WHERE p.document_number = ? AND ai.page_start = ? AND ai.page_start_quadrant IS ?
        """,
        (str(document_number), page, page_quadrant),
    ).fetchone()
    return dict(row) if row else None


def _fact_protocol_citation(conn: sqlite3.Connection, document_number: Any) -> dict[str, Any] | None:
    """document_number, unique."""
    row = conn.execute(
        """
        SELECT p.id, p.document_number, p.date,
               json_extract(p.xml_header_json, '$.sitzung_start') AS sitzung_start,
               json_extract(p.xml_header_json, '$.sitzung_end') AS sitzung_end
        FROM protocols p WHERE p.document_number = ?
        """,
        (str(document_number),),
    ).fetchone()
    return dict(row) if row else None


def _fact_vote_citation(conn: sqlite3.Connection, official_url: Any) -> dict[str, Any] | None:
    """official_url holds votes.detail_url: unique across every vote, never
    empty. The receipt carries no vote id; detail_url is the join."""
    if not official_url:
        return None
    row = conn.execute(
        "SELECT v.id, v.title, v.date, v.yes_count, v.no_count FROM votes v WHERE v.detail_url = ?",
        (str(official_url),),
    ).fetchone()
    return dict(row) if row else None


def resolve_fact_citation(
    conn: sqlite3.Connection, metric: dict[str, Any], fact_row: dict[str, Any]
) -> dict[str, Any] | None:
    """Rebuild the in-memory ``citation`` shape facts._citation() produces -
    never persisted (D2A/D14) - from the fact's own receipts. None when a
    receipt no longer resolves (a rebuilt store dropped the row), so the
    caller renders an honest placeholder instead of crashing the build."""
    receipts = sorted(fact_row.get("receipts") or [], key=lambda r: int(r["position"]))
    subject = next((r for r in receipts if int(r["position"]) == 0), None)
    if subject is None:
        return None
    kind = metric["receipt"]
    if kind == "speech":
        resolved = _fact_speech_citation(
            conn, subject["document_number"], subject.get("rede_id"), subject.get("page"), subject.get("page_quadrant")
        )
        if resolved is None:
            return None
        return {
            "id": resolved["id"],
            "document_number": resolved["document_number"],
            "rede_id": resolved["rede_id"],
            "display_name": resolved["display_name"],
            "fraktion": pulse_html.speaker_party({"fraktion": resolved["fraktion"]}),
            "topic": pulse_html.agenda_topic(resolved["proceeding_title"], resolved["heading"]),
            "speaker_mps": [resolved],
        }
    if kind == "speeches":
        resolved_rows = [
            row
            for row in (
                _fact_speech_citation(conn, r["document_number"], r.get("rede_id"), r.get("page"), r.get("page_quadrant"))
                for r in receipts
            )
            if row is not None
        ]
        if not resolved_rows:
            return None
        first = resolved_rows[0]
        return {
            "id": first["id"],
            "document_number": first["document_number"],
            "rede_id": first["rede_id"],
            "display_name": first["display_name"],
            "fraktion": pulse_html.speaker_party({"fraktion": first["fraktion"]}),
            "topic": pulse_html.agenda_topic(first["proceeding_title"], first["heading"]),
            "speakers": [str(row.get("display_name") or "Unbekannt") for row in resolved_rows],
            "speaker_mps": resolved_rows,
        }
    if kind == "agenda_item":
        resolved = _fact_agenda_item_citation(conn, subject["document_number"], subject.get("page"), subject.get("page_quadrant"))
        if resolved is None:
            return None
        return {
            "id": resolved["id"],
            "document_number": resolved["document_number"],
            "topic": pulse_html.agenda_topic(resolved["proceeding_title"], resolved["heading"]),
            "heading": resolved["heading"],
            "speech_count": int(fact_row.get("denominator") or 0),
        }
    if kind == "protocol":
        resolved = _fact_protocol_citation(conn, subject["document_number"])
        if resolved is None:
            return None
        return {
            "id": resolved["id"],
            "document_number": resolved["document_number"],
            "date": resolved["date"],
            "sitzung_start": resolved["sitzung_start"],
            "sitzung_end": resolved["sitzung_end"],
        }
    if kind == "proceeding":
        resolved_occurrences = [
            row
            for row in (
                _fact_proceeding_citation(conn, r["document_number"], r.get("page"), r.get("page_quadrant"))
                for r in receipts
            )
            if row is not None
        ]
        if not resolved_occurrences:
            return None
        lead = resolved_occurrences[0]
        return {
            "id": lead["proceeding_id"],
            "document_number": lead["document_number"],
            "title": lead["title"],
            "proceeding_type": lead["proceeding_type"],
            "occurrences": len(resolved_occurrences),
        }
    if kind == "vote":
        resolved = _fact_vote_citation(conn, subject.get("official_url"))
        if resolved is None:
            return None
        return {
            "id": resolved["id"],
            "document_number": subject["document_number"],
            "title": resolved["title"],
            "date": resolved["date"],
            "yes_count": int(resolved["yes_count"] or 0),
            "no_count": int(resolved["no_count"] or 0),
            "denominator": int(fact_row["denominator"]) if fact_row.get("denominator") is not None else None,
        }
    return None


def _renderable_fact(conn: sqlite3.Connection, fact_row: dict[str, Any]) -> dict[str, Any] | None:
    """A persisted ``facts`` row plus its resolved ``citation``, ready for
    facts.headline/card_title/card_lead/render_card - or None when the
    citation no longer resolves."""
    metric = facts.REGISTRY_BY_ID.get(fact_row["metric_id"])
    if metric is None:
        return None
    citation = resolve_fact_citation(conn, metric, fact_row)
    if citation is None:
        return None
    row = dict(fact_row)
    row["citation"] = citation
    return row


def _fact_status_text(row: dict[str, Any] | None) -> tuple[str, str | None, bool]:
    """(cell text, in-page anchor or None, whether it is posted) for one
    metric's cell in a period. None row: the metric was not built this
    update (e.g. --enrich without votes)."""
    if row is None:
        return "–", None, False
    if not row.get("complete"):
        return "unvollständig erfasst", None, False
    if row.get("publishable"):
        return f"Platz {row['rank']}", row["metric_id"], True
    return facts.WITHHELD_CLAUSES.get(row.get("withheld"), "kein Fakt"), None, False


def _series_value_text(metric: dict[str, Any], row: dict[str, Any]) -> str:
    if not row.get("complete"):
        return "unvollständig erfasst"
    if row.get("value") is None:
        return "–"
    if metric["id"] == "knappste-abstimmung":
        return f"{row['value'] * 100:.1f} %".replace(".", ",")
    if metric["id"] == "laengste-sitzung":
        minutes = int(row["value"])
        return f"{minutes // 60} h {minutes % 60:02d} min"
    return pulse_html.format_int(int(row["value"]))


def _render_fact_series(
    metric: dict[str, Any],
    period_key: str,
    series: list[dict[str, Any]],
    series_index: dict[str, int],
) -> str:
    """The metric's own last periods, this one marked - every period already
    has a row (publishable or not), so no extra query beyond what
    write_facts_pages already loaded once for the whole build.

    ``series_index`` is ``series``'s own ``{period_key: position}`` map,
    built once per metric by ``_facts_group_by_metric`` - this renders once
    per posted row per period, so re-scanning ``series`` here would cost
    O(periods) per call instead of the O(1) lookup this uses.
    """
    cursor = series_index.get(period_key)
    if cursor is None:
        return ""
    recent = series[max(0, cursor - 7) : cursor + 1]
    items = []
    for entry in recent:
        current = ' class="current"' if entry["period_key"] == period_key else ""
        items.append(
            f"<li{current}>{pulse_html.esc(entry['period_key'])}: {pulse_html.esc(_series_value_text(metric, entry))}</li>"
        )
    return f'<div class="series"><span class="eyebrow">Verlauf</span><ol>{"".join(items)}</ol></div>'


def _render_fact_sources(
    row: dict[str, Any],
    *,
    mp_lookup: dict[str, int],
    document_numbers: set[str],
    bill_slugs: set[str],
) -> str:
    """The receipts as a linked list: the protocol they belong to
    (resolve_entity_link, shared with the recipe tables - D6A), the speaker's
    MP profile when the receipt names one, and any supporting Drucksache with
    its own DIP link. Never the raw store id (D14)."""
    citation = row["citation"]
    speaker_mps = citation.get("speaker_mps") or []
    receipts = sorted(row.get("receipts") or [], key=lambda r: int(r["position"]))
    items: list[str] = []
    for index, receipt in enumerate(receipts):
        document_number = receipt.get("document_number")
        if receipt["entity_kind"] == "document":
            url = pulse_html.safe_href(receipt.get("official_url"))
            label = f"Drucksache {document_number}"
            items.append(
                f'<li><a href="{pulse_html.esc(url)}">{pulse_html.esc(label)}</a></li>'
                if url else f"<li>{pulse_html.esc(label)}</li>"
            )
            continue
        href = resolve_entity_link(
            "document", document_number, mp_lookup=mp_lookup, document_numbers=document_numbers, bill_slugs=bill_slugs
        )
        protocol_text = f"Plenarprotokoll {document_number}"
        bits = [
            f'<a href="../{pulse_html.esc(href)}">{pulse_html.esc(protocol_text)}</a>' if href else pulse_html.esc(protocol_text)
        ]
        if receipt.get("page"):
            bits.append(f"Seite {pulse_html.esc(receipt['page'])}{pulse_html.esc(receipt.get('page_quadrant') or '')}")
        if receipt["entity_kind"] == "speech" and index < len(speaker_mps):
            mp = speaker_mps[index]
            mp_href = pulse_html.mp_page_href(
                {
                    "abgeordnetenwatch": {"id": mp.get("aw_politician_id")} if mp.get("aw_politician_id") else {},
                    "xml_redner_id": mp.get("xml_redner_id"),
                    "dip_person_id": mp.get("dip_person_id"),
                },
                mp_lookup,
                prefix="../abgeordnete/",
            )
            name = mp.get("display_name") or "Unbekannt"
            name_html = f'<a href="{pulse_html.esc(mp_href)}">{pulse_html.esc(name)}</a>' if mp_href else pulse_html.esc(name)
            bits.insert(0, name_html)
        if receipt["entity_kind"] == "vote":
            vote_url = pulse_html.safe_href(receipt.get("official_url"))
            if vote_url:
                bits.append(f'<a href="{pulse_html.esc(vote_url)}">Abstimmungsdetails ↗</a>')
        items.append(f"<li>{' · '.join(bits)}</li>")
    if not items:
        return ""
    return f'<div class="sources"><span class="eyebrow">Quellen</span><ul>{"".join(items)}</ul></div>'


def _render_fact_section(
    row: dict[str, Any],
    metric: dict[str, Any],
    resolved: bool,
    series: list[dict[str, Any]],
    series_index: dict[str, int],
    *,
    mp_lookup: dict[str, int],
    document_numbers: set[str],
    bill_slugs: set[str],
) -> str:
    metric_id = metric["id"]
    eyebrow = f"Platz {row['rank']} · {metric['title']}"
    if not resolved:
        return (
            f'<section id="{pulse_html.esc(metric_id)}" class="fact-block">'
            f'<span class="eyebrow">{pulse_html.esc(eyebrow)}</span>'
            "<p>Die zitierte Quelle ist in diesem Build nicht mehr auffindbar.</p>"
            "</section>"
        )
    caveat = facts.card_caveat(row)
    caveat_html = f'<p class="caveat">{pulse_html.esc(caveat)}</p>' if caveat else ""
    return f"""
    <section id="{pulse_html.esc(metric_id)}" class="fact-block">
      <span class="eyebrow">{pulse_html.esc(eyebrow)}</span>
      <img class="fact-card" src="{pulse_html.esc(facts.card_filename(row))}" width="320" height="320"
           alt="{pulse_html.esc(facts.card_title(row))}" loading="lazy">
      <p class="fact-sentence">{pulse_html.esc(facts.card_sentence(row))}</p>
      {caveat_html}
      <p class="baseline">{pulse_html.esc(facts.baseline_comparison_line(row))}</p>
      {_render_fact_sources(row, mp_lookup=mp_lookup, document_numbers=document_numbers, bill_slugs=bill_slugs)}
      {_render_fact_series(metric, row["period_key"], series, series_index)}
      <details class="recipe-sql"><summary>SQL</summary><pre><code>{pulse_html.esc(metric["sql"])}</code></pre></details>
    </section>
    """


def _render_facts_archive_table(
    all_facts: list[dict[str, Any]], registry: tuple[dict[str, Any], ...], period_kind: str, period_header: str
) -> str:
    by_period: dict[str, dict[str, dict[str, Any]]] = {}
    for row in all_facts:
        if row["period_kind"] != period_kind:
            continue
        by_period.setdefault(row["period_key"], {})[row["metric_id"]] = row
    if not by_period:
        return ""
    rows_html = []
    for period_key in sorted(by_period, reverse=True):
        period_rows = by_period[period_key]
        sample = next(iter(period_rows.values()))
        period_text = (
            pulse_html.week_label((sample["iso_year"], sample["iso_week"]))
            if sample.get("iso_year") and sample.get("iso_week")
            else period_key
        )
        cells = []
        any_posted = False
        for metric in registry:
            text, anchor, posted = _fact_status_text(period_rows.get(metric["id"]))
            any_posted = any_posted or posted
            if posted:
                cells.append(f'<td><a href="{pulse_html.esc(period_key)}.html#{pulse_html.esc(anchor)}">{pulse_html.esc(text)}</a></td>')
            else:
                cells.append(f'<td class="muted">{pulse_html.esc(text)}</td>')
        row_class = "archive-row" if any_posted else "archive-row greyed"
        rows_html.append(
            f'<tr class="{row_class}"><td><a href="{pulse_html.esc(period_key)}.html">{pulse_html.esc(period_text)}</a></td>'
            f'<td class="num">{pulse_html.esc(sample.get("wahlperiode"))}</td>{"".join(cells)}</tr>'
        )
    header_cells = "".join(f"<th>{pulse_html.esc(FACTS_METRIC_LABELS[metric['id']])}</th>" for metric in registry)
    return (
        f'<div class="table-scroll"><table class="facts-archive"><thead><tr><th>{pulse_html.esc(period_header)}</th>'
        f'<th class="num">WP</th>{header_cells}</tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody></table></div>'
    )


def render_facts_archive(all_facts: list[dict[str, Any]], features: Selection | None = None) -> str:
    features = features or publication_selection()
    weekly_table = _render_facts_archive_table(all_facts, facts.REGISTRY, "week", "Woche")
    monthly_table = _render_facts_archive_table(all_facts, facts.MONTHLY_REGISTRY, "month", "Monat")
    sections = []
    if weekly_table:
        sections.append(f"<section><h2>Wöchentlich</h2>{weekly_table}</section>")
    if monthly_table:
        sections.append(f"<section><h2>Monatlich</h2>{monthly_table}</section>")
    body = "".join(sections) if sections else '<p class="lead">Noch keine Fakten veröffentlicht.</p>'
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Fakt der Woche</title>
  {pulse_html.page_head(features)}
  <style>{_facts_page_style()}</style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(depth=1, active="fakten", features=features)}
    <header>
      <h1>Fakt der Woche</h1>
      <p class="lead">Ein automatisch berechneter, ungewöhnlicher Wert je Sitzungswoche und je Monat
      - aus den Primärdaten dieser Seite, nicht redaktionell ausgewählt. <a href="methodik.html">Wie
      das funktioniert</a>.</p>
    </header>
    {body}
    <footer>Primärquellen: Bundestag-DIP und die XML-Plenarprotokolle. <a href="methodik.html">Methodik</a></footer>
  </div>
  {pulse_html.page_scripts(features)}
</body>
</html>
"""


def render_facts_week(
    period_key: str,
    period_rows: list[dict[str, Any]],
    metric_series: dict[str, list[dict[str, Any]]],
    metric_series_index: dict[str, dict[str, int]],
    resolved_by_id: dict[Any, dict[str, Any] | None],
    *,
    mp_lookup: dict[str, int],
    document_numbers: set[str],
    bill_slugs: set[str],
    features: Selection | None = None,
) -> str:
    features = features or publication_selection()
    sample = period_rows[0]
    period_kind = sample["period_kind"]
    plural, demonstrative = _PERIOD_NOUN.get(period_kind, _PERIOD_NOUN["week"])
    if period_kind == "month":
        period_text = facts.month_display(period_key)
    else:
        period_text = (
            pulse_html.week_label((sample["iso_year"], sample["iso_week"]))
            if sample.get("iso_year") and sample.get("iso_week")
            else period_key
        )
    period_registry = facts.MONTHLY_REGISTRY if period_kind == "month" else facts.REGISTRY
    by_metric_id = {row["metric_id"]: row for row in period_rows}
    posted = sorted((row for row in period_rows if row["publishable"]), key=lambda row: int(row["rank"]))
    if posted:
        sections = []
        for row in posted:
            metric = facts.REGISTRY_BY_ID[row["metric_id"]]
            resolved = resolved_by_id.get(row["id"])
            sections.append(
                _render_fact_section(
                    resolved or row,
                    metric,
                    resolved is not None,
                    metric_series.get(row["metric_id"], []),
                    metric_series_index.get(row["metric_id"], {}),
                    mp_lookup=mp_lookup,
                    document_numbers=document_numbers,
                    bill_slugs=bill_slugs,
                )
            )
        content = "".join(sections)
    else:
        floor_pct = facts.format_percentile(facts.PUBLICATION_FLOOR)
        items = []
        for metric in period_registry:
            text, _, _ = _fact_status_text(by_metric_id.get(metric["id"]))
            items.append(f"<li><strong>{pulse_html.esc(metric['title'])}</strong><span>{pulse_html.esc(text)}</span></li>")
        content = (
            f'<p class="lead">{pulse_html.esc(demonstrative)} hat keinen Fakt über die '
            f"Veröffentlichungsschwelle ({pulse_html.esc(floor_pct)} %) gebracht.</p>"
            f'<ul class="method-list">{"".join(items)}</ul>'
        )
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Fakt der Woche {pulse_html.esc(period_text)}</title>
  {pulse_html.page_head(features)}
  <style>{_facts_page_style()}</style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(depth=1, active="fakten", features=features)}
    <header>
      <span class="eyebrow"><a href="index.html">Fakt der Woche</a></span>
      <h1>{pulse_html.esc(period_text)}</h1>
    </header>
    {content}
    <footer>
      Spätere {pulse_html.esc(plural)} ändern diese Karten nicht; nur eine Korrektur an den Rohdaten kann es.
      <a href="methodik.html">Methodik</a>
    </footer>
  </div>
  {pulse_html.page_scripts(features)}
</body>
</html>
"""


def _facts_methodik_metric_items(registry: tuple[dict[str, Any], ...], period_plural: str) -> str:
    items = []
    for metric in registry:
        gates = [f"mindestens {metric['min_history_weeks']} vergleichbare {period_plural}"]
        if metric.get("min_value") is not None:
            gates.append(f"Wert mindestens {pulse_html.format_int(int(metric['min_value']))}")
        if metric.get("requires_topic"):
            gates.append("Thema muss bestimmbar sein")
        caveat = f'<p class="caveat">{pulse_html.esc(metric["caveat"])}</p>' if metric.get("caveat") else ""
        direction_text = "größter" if metric["direction"] == "max" else "kleinster"
        per_period = "je Sitzungswoche" if period_plural == "Wochen" else "je Monat"
        items.append(
            f'<li id="metrik-{pulse_html.esc(metric["id"])}"><strong>{pulse_html.esc(metric["title"])}</strong>'
            f'<span>{pulse_html.esc(metric["unit"])} · {direction_text} Wert {per_period} · '
            f'Vergleichbarkeit: {pulse_html.esc(", ".join(gates))}</span>{caveat}</li>'
        )
    return "".join(items)


def render_facts_methodik(features: Selection | None = None) -> str:
    features = features or publication_selection()
    weekly_items = _facts_methodik_metric_items(facts.REGISTRY, "Wochen")
    monthly_items = _facts_methodik_metric_items(facts.MONTHLY_REGISTRY, "Monate")
    floor_pct = facts.format_percentile(facts.PUBLICATION_FLOOR)
    min_abweichler = int(facts.REGISTRY_BY_ID["meiste-abweichler"]["min_value"])
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Fakt der Woche: Methodik</title>
  {pulse_html.page_head(features)}
  <style>{_facts_page_style()}</style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(depth=1, active="fakten", features=features)}
    <header>
      <span class="eyebrow"><a href="index.html">Fakt der Woche</a></span>
      <h1>Wie „Fakt der Woche“ berechnet wird</h1>
      <p class="lead">Jede Sitzungswoche liefert für sechs Kennzahlen, jeder Monat für zwei weitere,
      höchstens einen Wert. Veröffentlicht wird eine Kennzahl nur, wenn sie ungewöhnlicher ist als
      {pulse_html.esc(floor_pct)} % der vergleichbaren Perioden seit Beginn der Erfassung - und, bei
      einigen Kennzahlen, eine zusätzliche absolute Schwelle erreicht.</p>
    </header>
    <section>
      <h2>Die Regel</h2>
      <ol class="method-list">
        <li><strong>Beobachtung</strong><span>Je Periode (Sitzungswoche oder Monat) und Kennzahl
        der größte oder kleinste Wert unter den Kandidatenzeilen dieser Periode, ihre Anzahl - bei
        „Die meisten ersten Reden der Woche“ - oder, bei den beiden monatlichen Kennzahlen, die
        größte Summe über alle Kandidatenzeilen einer Abgeordneten oder eines Vorgangs im Monat.
        Eine Periode ohne passende Zeile liefert keine Beobachtung.</span></li>
        <li><strong>Vergleichbarkeit</strong><span>Der Anteil der vorherigen Beobachtungen, den
        der Wert in der Richtung der Kennzahl schlägt (mehr beim Maximum, weniger beim Minimum).
        Verglichen wird zuerst mit der laufenden Wahlperiode, sobald sie genug frühere Perioden
        zählt (mindestens {facts.MIN_HISTORY_WEEKS} Sitzungswochen bzw. mindestens
        {facts.MIN_HISTORY_MONTHS} Monate), sonst mit der gesamten Erfassung; darunter gilt die
        Periode als „noch nicht vergleichbar“.</span></li>
        <li><strong>Veröffentlichungsschwelle</strong><span>Ab {pulse_html.esc(floor_pct)} % wird
        eine Kennzahl veröffentlicht - ungewöhnlicher als die Hälfte der Vergleichsperioden. Jede
        Kennzahl, die die Schwelle erreicht, bekommt eine Karte; eine Periode kann also mehrere
        Fakten tragen oder keinen.</span></li>
        <li><strong>Zusätzliche Schwellen</strong><span>„Die meisten Abweichler der Woche“
        erscheint erst ab {pulse_html.format_int(min_abweichler)} Abweichlern, sonst ist der Wert
        eine Anekdote, kein Fakt. „Die längste Debatte der Woche“ erscheint nur, wenn sich ihr
        Thema bestimmen lässt - sonst würde die Karte nur sagen, dass irgendein
        Tagesordnungspunkt lang war.</span></li>
      </ol>
    </section>
    <section>
      <h2>Die sechs wöchentlichen Kennzahlen</h2>
      <ul class="method-list">{weekly_items}</ul>
    </section>
    <section>
      <h2>Die zwei monatlichen Kennzahlen</h2>
      <p class="lead">Dieselbe Regel, mit Monaten statt Sitzungswochen als Perioden: die Beobachtung
      summiert dafür die Kandidatenzeilen einer Abgeordneten oder eines Vorgangs über alle Sitzungen
      des Monats, statt die einzelne größte Zeile zu nehmen.</p>
      <ul class="method-list">{monthly_items}</ul>
    </section>
    <section>
      <h2>Was sich nicht ändert</h2>
      <p>Spätere Sitzungswochen ändern frühere Karten nicht, und spätere Monate ändern ihre
      Monatskarten ebenso wenig. Nur eine Korrektur an den zugrunde liegenden Daten kann eine
      veröffentlichte Karte im Nachhinein verändern; das Build-Log verzeichnet jede solche
      Änderung.</p>
    </section>
    <footer><a href="index.html">Zurück zum Archiv</a> · <a href="../sources.html">Quellen und Methode</a></footer>
  </div>
  {pulse_html.page_scripts(features)}
</body>
</html>
"""


def _facts_group_by_period(all_facts: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in all_facts:
        grouped.setdefault((row["period_kind"], row["period_key"]), []).append(row)
    return grouped


def _facts_group_by_metric(
    all_facts: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, int]]]:
    """Each metric's own rows, oldest first, plus each row's position in that
    list - built once per build so ``_render_fact_series`` (called once per
    posted row per period) looks its period up instead of scanning."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in all_facts:
        grouped.setdefault(row["metric_id"], []).append(row)
    index = {
        metric_id: {row["period_key"]: position for position, row in enumerate(rows)}
        for metric_id, rows in grouped.items()
    }
    return grouped, index


def write_facts_pages(
    output_dir: Path,
    database_path: Path,
    no_persist: bool,
    mp_lookup: dict[str, int] | None,
    document_numbers: set[str],
    bill_slugs: set[str],
    features: Selection | None = None,
) -> dict[str, Any]:
    """fakt/index.html, fakt/<period_key>.html, fakt/<period_key>-<metric>.svg
    and fakt/methodik.html. Reads the three tables scripts/facts.py persisted;
    []/no rows when the store or its tables are missing (a fresh
    --no-persist render - D3A), since facts.load_facts already returns []
    rather than raising."""
    features = features or publication_selection()
    facts_dir = output_dir / "fakt"
    facts_dir.mkdir(parents=True, exist_ok=True)
    mp_lookup = mp_lookup or {}

    all_facts: list[dict[str, Any]] = []
    expected = {"index.html", "methodik.html"}
    read_store = not no_persist and database_path.exists()
    if read_store:
        conn = facts.open_readonly(database_path)
        try:
            all_facts = facts.load_facts(conn)
            by_period = _facts_group_by_period(all_facts)
            by_metric, by_metric_index = _facts_group_by_metric(all_facts)
            _ensure_lead_position_tables(conn)
            # Resolved once here and reused for both the page's HTML section
            # and its SVG card below - each was independently re-resolving
            # the same citation (a full join per receipt) until this shared.
            resolved_by_id = {
                row["id"]: _renderable_fact(conn, row) for row in all_facts if row["publishable"]
            }
            for (period_kind, period_key), period_rows in by_period.items():
                page_name = f"{period_key}.html"
                expected.add(page_name)
                (facts_dir / page_name).write_text(
                    render_facts_week(
                        period_key,
                        period_rows,
                        by_metric,
                        by_metric_index,
                        resolved_by_id,
                        mp_lookup=mp_lookup,
                        document_numbers=document_numbers,
                        bill_slugs=bill_slugs,
                        features=features,
                    ),
                    encoding="utf-8",
                )
                for row in period_rows:
                    if not row["publishable"]:
                        continue
                    resolved = resolved_by_id.get(row["id"])
                    if resolved is None:
                        print(
                            f"facts: {row['period_key']}-{row['metric_id']} Quelle nicht mehr auffindbar, Karte ausgelassen",
                            file=sys.stderr,
                        )
                        continue
                    svg_name = facts.card_filename(resolved)
                    expected.add(svg_name)
                    (facts_dir / svg_name).write_bytes(facts.render_card(resolved).encode("utf-8"))
        finally:
            conn.close()

    # Only prune stale files when the store was actually read: `expected`
    # otherwise never grows past the two static names, and this loop would
    # delete every previously published page/card left over from a real
    # build (a --no-persist dev render, or a build before the store exists,
    # must never touch what an earlier build already published).
    if read_store:
        for stale in facts_dir.glob("*"):
            if stale.name not in expected:
                stale.unlink()

    # Same reasoning as the stale-file guard above: a run that didn't read
    # the store has nothing accurate to say about what's published, so it
    # must not overwrite an already-accurate archive from a prior real
    # build with a false "nothing published yet" - unless there is no prior
    # archive to preserve (a fresh site's first page still needs one).
    archive_path = facts_dir / "index.html"
    if read_store or not archive_path.exists():
        archive_path.write_text(render_facts_archive(all_facts, features=features), encoding="utf-8")
    (facts_dir / "methodik.html").write_text(render_facts_methodik(features=features), encoding="utf-8")
    periods = {(row["period_kind"], row["period_key"]) for row in all_facts}
    posted = sum(1 for row in all_facts if row["publishable"])
    return {"periods": len(periods), "posted": posted, "index_path": facts_dir / "index.html"}


# ---------------------------------------------------------------------------
# PAGE: overview.html - "Plenarprotokoll-Katalog"
#
# The archive landing page: rich cards for the sittings that actually got a
# dossier in this build, plus a call-to-action into the full searchable catalog
# on api-sitzungen.html.
# ---------------------------------------------------------------------------


def render_overview(
    protocols: list[dict[str, Any]],
    detail_entries: list[dict[str, Any]],
    bill_count: int = 0,
    database_href: str | None = "data/bundestag-pulse.sqlite",
    database_page_href: str | None = None,
    catalog_href: str = "api-sitzungen.html",
    features: Selection | None = None,
) -> str:
    features = features or publication_selection()
    # One card per generated dossier: title linking to the dossier page, the four
    # headline metrics from the validation summary, a preview of the four
    # busiest agenda items, and the source links (XML/PDF/JSON/SQLite) plus a
    # warning count when extraction flagged something.
    generated_cards = []
    sqlite_link = f'<a href="{pulse_html.esc(database_href)}">SQLite</a>' if database_href else ""
    database_page_link = (
        f'<a href="{pulse_html.esc(database_page_href)}">Daten</a>' if database_page_href else ""
    )
    database_footer_link = f" · {database_page_link}" if database_page_link else ""
    for entry in detail_entries:
        report = entry["report"]
        protocol = report.get("protocol") or {}
        summary = report.get("validation_summary") or {}
        items = report.get("agenda_items") or []
        top_preview = []
        for item in sorted(items, key=lambda i: int(i.get("xml_speech_count") or 0), reverse=True)[:4]:
            top_preview.append(
                "<li>"
                f"<span>{pulse_html.esc(item.get('top_id'))}</span>"
                f"<strong>{pulse_html.esc(pulse_html.short(item.get('heading'), 110))}</strong>"
                f"<em>{pulse_html.esc(item.get('xml_speech_count'))} Reden</em>"
                "</li>"
            )
        warnings = report.get("warnings") or []
        warning_html = ""
        if warnings:
            warning_label = "Warnung" if len(warnings) == 1 else "Warnungen"
            warning_html = f'<span class="warn">{pulse_html.esc(str(len(warnings)))} {warning_label}</span>'
        source_links = []
        for label, key in (("XML", "xml_url"), ("PDF", "pdf_url")):
            safe_url = pulse_html.safe_href(protocol.get(key))
            if safe_url:
                source_links.append(f'<a href="{pulse_html.esc(safe_url)}">{label}</a>')

        generated_cards.append(
            f"""
            <article class="session-card">
              <div class="session-main">
                <div>
                  <span class="eyebrow">BT-PlPr {pulse_html.esc(protocol.get('dokumentnummer'))}</span>
                  <h2><a href="protocols/{pulse_html.esc(entry['page_path'].name)}">{pulse_html.esc(protocol.get('titel'))}</a></h2>
                  <p>{pulse_html.esc(protocol.get('datum'))} · verteilt am {pulse_html.esc(protocol.get('verteildatum'))}</p>
                </div>
                <a class="open-button" href="protocols/{pulse_html.esc(entry['page_path'].name)}">Öffnen</a>
              </div>
              <div class="metrics">
                <div><span>TOPs</span><strong>{pulse_html.esc(summary.get('xml_top_count'))}</strong></div>
                <div><span>Reden</span><strong>{pulse_html.esc(summary.get('xml_speech_count'))}</strong></div>
                <div><span>Drucksachen</span><strong>{pulse_html.esc(summary.get('xml_drucksache_count'))}</strong></div>
                <div><span>Personen</span><strong>{pulse_html.esc(summary.get('unique_person_ids'))}</strong></div>
              </div>
              <ul class="top-preview">{''.join(top_preview)}</ul>
              <div class="session-links">
                {''.join(source_links)}
                <a href="data/{pulse_html.esc(entry['report_path'].name)}">JSON</a>
                {sqlite_link}
                {warning_html}
              </div>
            </article>
            """
        )

    # Sitting counts per Wahlperiode, shown as badges under the summary band.
    by_period: dict[str, int] = {}
    for protocol in protocols:
        period = str(protocol.get("wahlperiode") or "unknown")
        by_period[period] = by_period.get(period, 0) + 1

    period_badges = "".join(
        f'<span class="badge">WP {pulse_html.esc(period)} <strong>{pulse_html.esc(count)}</strong></span>'
        for period, count in sorted(by_period.items(), key=lambda item: period_sort_key(item[0]))
    )
    latest = protocols[0] if protocols else {}
    generated_latest = detail_entries[0]["report"].get("protocol", {}) if detail_entries else {}
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Sitzungen</title>
  {pulse_html.page_head(features)}
  <style>
    :root {{
      --ink:#171a1f;
      --muted:#606a78;
      --line:#d9dee6;
      --paper:#f7f8fa;
      --panel:#ffffff;
      --blue:#174ea6;
      --amber:#9a5a00;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color:var(--ink);
      background:var(--paper);
      letter-spacing:0;
    }}
    a {{ color:var(--blue); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .shell {{ max-width:1360px; margin:0 auto; padding:28px 22px; }}
    {pulse_html.global_header_styles()}
    .page-header {{
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:24px;
      align-items:end;
      padding-bottom:22px;
      border-bottom:1px solid var(--line);
    }}
    h1 {{ margin:0; font-size:36px; line-height:1.1; }}
    .subtitle {{ margin:8px 0 0; color:var(--muted); }}
    .latest {{
      display:grid;
      gap:4px;
      min-width:220px;
      margin-top:9px;
      padding:12px 14px;
      border:1px solid var(--line);
      border-radius:8px;
      background:white;
      font-size:13px;
    }}
    .latest span, .eyebrow, .metrics span {{
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .latest strong {{ font-size:18px; }}
    .summary-band {{
      display:grid;
      grid-template-columns:repeat(4, minmax(0,1fr));
      gap:12px;
      margin-top:18px;
    }}
    .summary-band div {{
      border:1px solid var(--line);
      border-radius:8px;
      background:white;
      padding:13px 14px;
    }}
    .summary-band span {{
      display:block;
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .summary-band strong {{
      display:block;
      margin-top:4px;
      font-size:25px;
    }}
    .periods {{
      display:flex;
      flex-wrap:wrap;
      gap:8px;
      margin-top:12px;
    }}
    .badge {{
      display:inline-flex;
      gap:6px;
      align-items:center;
      min-height:26px;
      padding:3px 8px;
      border:1px solid var(--line);
      border-radius:999px;
      background:#fff;
      color:#333a45;
      font-size:12px;
    }}
    .sessions {{ display:grid; gap:14px; margin-top:18px; }}
    .session-card {{
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:8px;
      padding:18px;
    }}
    .session-main {{
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:18px;
      align-items:start;
    }}
    h2 {{ margin:5px 0 0; font-size:22px; line-height:1.25; }}
    p {{ margin:6px 0 0; color:var(--muted); }}
    .open-button {{
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-width:76px;
      min-height:34px;
      padding:5px 12px;
      border:1px solid #bdd0ea;
      border-radius:6px;
      background:#eef5ff;
      font-weight:700;
    }}
    .metrics {{
      display:grid;
      grid-template-columns:repeat(4, minmax(90px,1fr));
      gap:10px;
      margin-top:16px;
    }}
    .metrics div {{
      border:1px solid #e2e7ef;
      border-radius:8px;
      padding:9px 10px;
      background:#fbfcfd;
    }}
    .metrics strong {{ display:block; margin-top:3px; font-size:21px; }}
    .top-preview {{
      list-style:none;
      display:grid;
      gap:8px;
      margin:16px 0 0;
      padding:0;
    }}
    .top-preview li {{
      display:grid;
      grid-template-columns:128px minmax(0,1fr) 82px;
      gap:12px;
      align-items:start;
      padding-bottom:8px;
      border-bottom:1px solid #eef1f5;
      font-size:13px;
    }}
    .top-preview li:last-child {{ border-bottom:0; padding-bottom:0; }}
    .top-preview span, .top-preview em {{ color:var(--muted); font-style:normal; }}
    .top-preview strong {{ overflow-wrap:anywhere; }}
    .session-links {{
      display:flex;
      flex-wrap:wrap;
      gap:10px;
      align-items:center;
      margin-top:14px;
      font-size:13px;
    }}
    .session-links a {{
      display:inline-flex;
      min-height:26px;
      align-items:center;
      padding:3px 8px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      font-weight:650;
    }}
    .warn {{ color:#8a4a00; }}
    .catalog-cta {{
      display:flex;
      flex-wrap:wrap;
      gap:16px;
      align-items:center;
      justify-content:space-between;
      margin-top:18px;
      padding:18px;
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel);
    }}
    .catalog-cta strong {{ display:block; font-size:20px; }}
    .catalog-cta span {{ display:block; margin-top:4px; color:var(--muted); font-size:14px; max-width:560px; }}
    .section-head {{
      margin-top:26px;
      padding-top:20px;
      border-top:1px solid var(--line);
    }}
    .section-head h2 {{
      margin:0;
      font-size:24px;
      line-height:1.2;
    }}
    .section-head p {{
      max-width:780px;
      line-height:1.45;
    }}
    .muted {{ color:var(--muted); }}
    footer {{ padding-top:24px; color:var(--muted); font-size:12px; }}
    @media (max-width: 940px) {{
      .summary-band {{ grid-template-columns:1fr; }}
    }}
    @media (max-width: 740px) {{
      .shell {{ padding:18px 14px; }}
      .page-header, .session-main {{ grid-template-columns:1fr; }}
      .page-header {{ grid-template-columns:1fr; }}
      h1 {{ font-size:29px; }}
      h2 {{ font-size:19px; }}
      .metrics {{ grid-template-columns:1fr 1fr; }}
      .top-preview li {{ grid-template-columns:1fr; gap:3px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(active="overview", features=features)}
    <header class="page-header">
      <div>
        <h1>Bundestag-Puls</h1>
        <p class="subtitle">Umfassender Plenarprotokoll-Katalog aus der DIP-API mit erzeugten Dossiers für ausgewählte Sitzungen.</p>
      </div>
      <div>
        <div class="latest">
          <span>Neueste API-Sitzung</span>
          <strong>{pulse_html.esc(latest.get('dokumentnummer', ''))}</strong>
          <em>{pulse_html.esc(latest.get('datum', ''))}</em>
        </div>
      </div>
    </header>
    <section class="summary-band">
      <div><span>API-Sitzungen</span><strong>{pulse_html.esc(len(protocols))}</strong></div>
      <div><span>Erzeugte Dossiers</span><strong>{pulse_html.esc(len(detail_entries))}</strong></div>
      <div><span>Verfolgte Gesetze</span><strong>{pulse_html.esc(bill_count)}</strong></div>
      <div><span>Zuletzt erzeugt</span>
        <strong>{pulse_html.esc(generated_latest.get('dokumentnummer', ''))}</strong>
        <em>{pulse_html.esc(generated_latest.get('datum', ''))}</em>
      </div>
    </section>
    <div class="periods">{period_badges}</div>
    <div class="section-head">
      <h2>Erzeugte Sitzungsdossiers</h2>
      <p>Diese Seiten enthalten die XML-Protokollauswertung, die Aufmerksamkeit je Tagesordnungspunkt, Rednerinnen und Redner, Reden, zugeordnete DIP-Positionen und -Aktivitäten, verknüpfte Drucksachen, namentliche Abstimmungen, Personendatensätze und die Roh-API-Nutzdaten.</p>
    </div>
    <section class="sessions">
      {''.join(generated_cards) if generated_cards else '<p class="muted">In diesem Build wurden keine Detaildossiers erzeugt.</p>'}
    </section>
    <div class="section-head">
      <h2>Alle API-Sitzungen</h2>
      <p>Der vollständige Plenarprotokoll-Katalog umfasst {pulse_html.esc(len(protocols))} aus der DIP-API geholte Sitzungen. Durchsuchen und filtern lässt er sich auf einer eigenen Seite.</p>
    </div>
    <section class="catalog-cta">
      <div>
        <strong>{pulse_html.esc(len(protocols))} Sitzungen</strong>
        <span>Suche nach Dokumentnummer, Titel oder Datum, Filter nach Wahlperiode und Dossier-Status.</span>
      </div>
      <a class="open-button" href="{pulse_html.esc(catalog_href)}">Katalog durchsuchen</a>
    </section>
    <footer>
      Das XML-Protokoll ist maßgeblich; DIP-API-Daten ergänzen jede Sitzung. Mit --detail-limit 0 werden Dossiers für alle geholten Protokolle erzeugt, mit --detail-limit -1 nur der Katalog. <a href="puls.html">Aktueller Puls</a> · <a href="bills/index.html">Gesetze</a> · <a href="abgeordnete/index.html">Abgeordnete</a>{database_footer_link} · <a href="sources.html">Quellen</a>.
    </footer>
  </div>
  {pulse_html.page_scripts(features)}
</body>
</html>
    """


# ---------------------------------------------------------------------------
# PAGE: api-sitzungen.html - "Alle API-Sitzungen"
#
# The complete DIP protocol catalog as one searchable, sortable, filterable
# list. All filtering happens client-side over rows that are already in the
# HTML (see render_catalog_script), so the page stays static.
# ---------------------------------------------------------------------------


def catalog_sortnum(protocol: dict[str, Any]) -> str:
    """Zero-padded numeric sort key derived from the document number (WP/Nr)."""
    match = re.match(r"\s*(\d+)\s*/\s*(\d+)", str(protocol.get("dokumentnummer") or ""))
    if match:
        return f"{int(match.group(1)):04d}{int(match.group(2)):07d}"
    return "00000000000"


# Build the catalog rows plus the per-Wahlperiode counts.
#
# Each row carries its filter state in data-* attributes (search haystack,
# Wahlperiode, whether a dossier exists, date and numeric sort key); the inline
# script only reads those attributes and never re-derives anything.
def build_catalog_rows(
    protocols: list[dict[str, Any]],
    detail_entries: list[dict[str, Any]],
) -> tuple[list[str], dict[str, int]]:
    # Index the generated dossiers so a catalog row can tell whether this
    # sitting has one, and link to it if so.
    entries_by_id = {
        str(entry["report"].get("protocol", {}).get("id")): entry for entry in detail_entries
    }
    rows: list[str] = []
    by_period: dict[str, int] = {}
    for protocol in protocols:
        period = str(protocol.get("wahlperiode") or "unbekannt")
        document_number = normalized_document_number(protocol.get("dokumentnummer"))
        by_period[period] = by_period.get(period, 0) + 1
        fundstelle = protocol.get("fundstelle") or {}
        entry = entries_by_id.get(str(protocol.get("id")))
        has_dossier = "1" if entry else "0"
        dossier = '<span class="muted">Nicht erzeugt</span>'
        metrics = '<span class="muted">Nur Quell-Metadaten</span>'
        if entry:
            report = entry["report"]
            summary = report.get("validation_summary") or {}
            dossier = f'<a class="open-button" href="protocols/{pulse_html.esc(entry["page_path"].name)}">Dossier öffnen</a>'
            metrics = (
                f'{pulse_html.esc(summary.get("xml_top_count"))} TOPs · '
                f'{pulse_html.esc(summary.get("xml_speech_count"))} Reden · '
                f'{pulse_html.esc(summary.get("aktivitaet_count"))} Aktivitäten'
            )

        # Everything the search box should match on, lowercased into one string.
        search_terms = " ".join(
            str(value)
            for value in (
                protocol.get("dokumentnummer"),
                protocol.get("titel"),
                protocol.get("datum"),
                protocol.get("id"),
                protocol.get("dokumentart") or protocol.get("typ"),
                f"wp{period}",
                f"wahlperiode {period}",
            )
            if value
        ).lower()

        rows.append(
            f"""
            <article class="catalog-row" data-row data-search="{pulse_html.esc(search_terms)}" data-wp="{pulse_html.esc(period)}" data-dossier="{has_dossier}" data-docnumber="{pulse_html.esc(document_number)}" data-date="{pulse_html.esc(protocol.get('datum') or '')}" data-sortnum="{catalog_sortnum(protocol)}">
              <div>
                <span class="eyebrow">BT-PlPr {pulse_html.esc(protocol.get('dokumentnummer'))} · WP {pulse_html.esc(protocol.get('wahlperiode'))}</span>
                <h3>{pulse_html.esc(protocol.get('titel'))}</h3>
                <p>{pulse_html.esc(protocol.get('datum'))} · aktualisiert {pulse_html.esc(protocol.get('aktualisiert'))}</p>
              </div>
              <div class="catalog-meta">
                <span>{pulse_html.esc(protocol.get('dokumentart') or protocol.get('typ'))}</span>
                <strong>{pulse_html.esc(protocol.get('vorgangsbezug_anzahl', 0))}</strong>
                <em>Vorgangsbezüge</em>
              </div>
              <div class="catalog-meta">
                <span>Verteilt</span>
                <strong>{pulse_html.esc(fundstelle.get('verteildatum') or '')}</strong>
                <em>ID {pulse_html.esc(protocol.get('id'))}</em>
              </div>
              <div class="catalog-actions">
                {dossier}
                <div class="session-links">
                  {protocol_source_links(protocol)}
                </div>
              </div>
              <div class="catalog-status">{metrics}</div>
              {render_catalog_json(protocol)}
            </article>
            """
        )
    return rows, by_period


# Inline script for api-sitzungen.html: filters and sorts the catalog rows in
# place (search, Wahlperiode, dossier status) and keeps the result counter, the
# period badges and the reset button in sync with the active filters.
def render_catalog_script() -> str:
    return """
  <script>
    (() => {
      const container = document.querySelector('[data-catalog]');
      if (!container) return;
      const rows = Array.from(container.querySelectorAll('[data-row]'));
      const search = document.querySelector('[data-filter-search]');
      const wpSelect = document.querySelector('[data-filter-wp]');
      const dossierSelect = document.querySelector('[data-filter-dossier]');
      const sortSelect = document.querySelector('[data-filter-sort]');
      const countEl = document.querySelector('[data-result-count]');
      const noResults = document.querySelector('[data-no-results]');
      const resetBtn = document.querySelector('[data-filter-reset]');
      const badges = Array.from(document.querySelectorAll('[data-wp-filter]'));
      const apply = () => {
        const terms = (search.value || '').toLowerCase().trim().split(/\\s+/).filter(Boolean);
        const wp = wpSelect.value;
        const dossier = dossierSelect.value;
        let visible = 0;
        rows.forEach((row) => {
          const haystack = row.dataset.search || '';
          const matchesText = terms.every((term) => haystack.includes(term));
          const matchesWp = !wp || row.dataset.wp === wp;
          const matchesDossier = !dossier || row.dataset.dossier === dossier;
          const show = matchesText && matchesWp && matchesDossier;
          row.hidden = !show;
          if (show) visible += 1;
        });
        if (countEl) countEl.textContent = String(visible);
        if (noResults) noResults.hidden = visible !== 0;
        const filtersActive = Boolean(terms.length || wp || dossier);
        if (resetBtn) resetBtn.hidden = !filtersActive;
        badges.forEach((badge) => {
          badge.classList.toggle('is-active', Boolean(wp) && badge.dataset.wpFilter === wp);
        });
      };

      const sortRows = () => {
        const mode = sortSelect.value;
        const numeric = mode === 'num-asc' || mode === 'num-desc';
        const ascending = mode === 'date-asc' || mode === 'num-asc';
        const key = (row) => numeric ? (row.dataset.sortnum || '') : (row.dataset.date || '');
        rows.slice().sort((a, b) => {
          const av = key(a);
          const bv = key(b);
          const cmp = av < bv ? -1 : av > bv ? 1 : 0;
          return ascending ? cmp : -cmp;
        }).forEach((row) => container.appendChild(row));
      };

      search.addEventListener('input', apply);
      wpSelect.addEventListener('change', apply);
      dossierSelect.addEventListener('change', apply);
      sortSelect.addEventListener('change', sortRows);
      badges.forEach((badge) => {
        badge.addEventListener('click', () => {
          const value = badge.dataset.wpFilter;
          wpSelect.value = wpSelect.value === value ? '' : value;
          apply();
        });
      });
      if (resetBtn) {
        resetBtn.addEventListener('click', () => {
          search.value = '';
          wpSelect.value = '';
          dossierSelect.value = '';
          apply();
        });
      }
      apply();
    })();
  </script>
"""


# PAGE: api-sitzungen.html.
def render_catalog_page(
    protocols: list[dict[str, Any]],
    detail_entries: list[dict[str, Any]],
    catalog_path: Path,
    overview_href: str = "overview.html",
    database_page_href: str | None = None,
    features: Selection | None = None,
) -> str:
    features = features or publication_selection()
    # Rows first, then the filter controls derived from them: the Wahlperiode
    # dropdown and the clickable period badges share the same counts.
    rows, by_period = build_catalog_rows(protocols, detail_entries)
    rows_html = "".join(rows)
    periods_sorted = sorted(by_period.items(), key=lambda item: period_sort_key(item[0]))
    wp_options = "".join(
        f'<option value="{pulse_html.esc(period)}">WP {pulse_html.esc(period)} ({pulse_html.esc(count)})</option>'
        for period, count in periods_sorted
    )
    period_badges = "".join(
        f'<button type="button" class="badge" data-wp-filter="{pulse_html.esc(period)}">WP {pulse_html.esc(period)} <strong>{pulse_html.esc(count)}</strong></button>'
        for period, count in periods_sorted
    )
    latest = protocols[0] if protocols else {}
    total = len(protocols)
    dossier_count = len(detail_entries)
    database_page_link = (
        f'<a href="{pulse_html.esc(database_page_href)}">Daten</a>' if database_page_href else ""
    )
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Alle API-Sitzungen</title>
  {pulse_html.page_head(features)}
  <style>
    :root {{
      --ink:#171a1f;
      --muted:#606a78;
      --line:#d9dee6;
      --paper:#f7f8fa;
      --panel:#ffffff;
      --blue:#174ea6;
      --amber:#9a5a00;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color:var(--ink);
      background:var(--paper);
    }}
    a {{ color:var(--blue); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .shell {{ max-width:1360px; margin:0 auto; padding:28px 22px; }}
    {pulse_html.global_header_styles()}
    .page-header {{
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:24px;
      align-items:end;
      padding-bottom:22px;
      border-bottom:1px solid var(--line);
    }}
    h1 {{ margin:0; font-size:36px; line-height:1.1; }}
    .subtitle {{ margin:8px 0 0; color:var(--muted); max-width:760px; }}
    .latest {{
      display:grid;
      gap:4px;
      min-width:220px;
      padding:12px 14px;
      border:1px solid var(--line);
      border-radius:8px;
      background:white;
      font-size:13px;
    }}
    .latest span, .eyebrow, .catalog-meta span {{
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .latest strong {{ font-size:18px; }}
    .summary-band {{
      display:grid;
      grid-template-columns:repeat(3, minmax(0,1fr));
      gap:12px;
      margin-top:18px;
    }}
    .summary-band div {{
      border:1px solid var(--line);
      border-radius:8px;
      background:white;
      padding:13px 14px;
    }}
    .summary-band span {{
      display:block;
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .summary-band strong {{ display:block; margin-top:4px; font-size:25px; }}
    .filters {{
      display:grid;
      grid-template-columns:minmax(220px,2fr) repeat(3, minmax(150px,1fr));
      gap:12px;
      margin-top:22px;
      padding:16px;
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel);
    }}
    .filter-field {{ display:grid; gap:5px; }}
    .filter-field label {{
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .filter-field input, .filter-field select {{
      min-height:38px;
      padding:7px 10px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      font:inherit;
      color:inherit;
    }}
    .filter-field input:focus, .filter-field select:focus {{
      outline:2px solid #bdd0ea;
      border-color:#bdd0ea;
    }}
    .filter-status {{
      display:flex;
      flex-wrap:wrap;
      gap:10px;
      align-items:center;
      margin-top:14px;
      color:var(--muted);
      font-size:14px;
    }}
    .filter-status strong, .filter-status [data-result-count] {{ color:var(--ink); font-weight:700; }}
    .link-button {{
      border:0;
      background:none;
      padding:0;
      color:var(--blue);
      font:inherit;
      font-weight:650;
      cursor:pointer;
    }}
    .link-button:hover {{ text-decoration:underline; }}
    .periods {{
      display:flex;
      flex-wrap:wrap;
      gap:8px;
      margin-top:12px;
    }}
    .badge {{
      display:inline-flex;
      gap:6px;
      align-items:center;
      min-height:28px;
      padding:3px 10px;
      border:1px solid var(--line);
      border-radius:999px;
      background:#fff;
      color:#333a45;
      font:inherit;
      font-size:12px;
      cursor:pointer;
    }}
    .badge:hover {{ border-color:#bdd0ea; }}
    .badge.is-active {{
      border-color:#174ea6;
      background:#eef5ff;
      color:#103a7a;
    }}
    .catalog {{ display:grid; gap:10px; margin-top:18px; }}
    .catalog-row {{
      display:grid;
      grid-template-columns:minmax(260px,1.4fr) minmax(130px,.45fr) minmax(150px,.5fr) minmax(190px,.7fr);
      gap:14px;
      align-items:start;
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:8px;
      padding:14px;
    }}
    .catalog-row[hidden] {{ display:none; }}
    .catalog-row h3 {{
      margin:5px 0 0;
      font-size:17px;
      line-height:1.25;
      overflow-wrap:anywhere;
    }}
    .catalog-row p {{ margin:6px 0 0; color:var(--muted); }}
    .catalog-meta strong {{
      display:block;
      margin-top:4px;
      font-size:18px;
      overflow-wrap:anywhere;
    }}
    .catalog-meta em, .catalog-status {{
      color:var(--muted);
      font-size:12px;
      font-style:normal;
    }}
    .catalog-actions {{ display:grid; justify-items:start; gap:8px; }}
    .catalog-status {{
      grid-column:1 / -1;
      padding-top:10px;
      border-top:1px solid #eef1f5;
    }}
    .open-button {{
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-width:76px;
      min-height:34px;
      padding:5px 12px;
      border:1px solid #bdd0ea;
      border-radius:6px;
      background:#eef5ff;
      font-weight:700;
    }}
    .session-links {{
      display:flex;
      flex-wrap:wrap;
      gap:10px;
      align-items:center;
      font-size:13px;
    }}
    .session-links a {{
      display:inline-flex;
      min-height:26px;
      align-items:center;
      padding:3px 8px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      font-weight:650;
    }}
    .api-details {{
      grid-column:1 / -1;
      border:1px solid #e3e8ef;
      border-radius:8px;
      background:#fbfcfd;
      overflow:hidden;
    }}
    .api-details summary {{
      min-height:32px;
      padding:7px 10px;
      color:var(--blue);
      cursor:pointer;
      font-size:13px;
      font-weight:700;
    }}
    .api-details pre {{
      max-height:300px;
      overflow:auto;
      margin:0;
      padding:10px;
      border-top:1px solid #e6ebf2;
      font-size:12px;
      line-height:1.45;
      white-space:pre-wrap;
      overflow-wrap:anywhere;
    }}
    .no-results {{
      margin:14px 0 0;
      padding:18px;
      border:1px dashed var(--line);
      border-radius:8px;
      background:#fff;
      color:var(--muted);
      text-align:center;
    }}
    .muted {{ color:var(--muted); }}
    footer {{ padding-top:24px; color:var(--muted); font-size:12px; }}
    @media (max-width: 940px) {{
      .summary-band {{ grid-template-columns:1fr; }}
      .filters {{ grid-template-columns:1fr; }}
      .catalog-row {{ grid-template-columns:1fr; }}
      .catalog-status, .api-details {{ grid-column:auto; }}
    }}
    @media (max-width: 740px) {{
      .shell {{ padding:18px 14px; }}
      .page-header {{ grid-template-columns:1fr; }}
      h1 {{ font-size:29px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(active="catalog", features=features)}
    <header class="page-header">
      <div>
        <h1>Alle API-Sitzungen</h1>
        <p class="subtitle">Vollständiger Plenarprotokoll-Katalog aus der DIP-API. Suche nach Dokumentnummer, Titel oder Datum und filtere nach Wahlperiode oder Dossier-Status. Der Roh-Katalog steht zusätzlich als <a href="data/{pulse_html.esc(catalog_path.name)}">JSON</a> bereit.</p>
      </div>
      <div class="latest">
        <span>Neueste API-Sitzung</span>
        <strong>{pulse_html.esc(latest.get('dokumentnummer', ''))}</strong>
        <em>{pulse_html.esc(latest.get('datum', ''))}</em>
      </div>
    </header>
    <section class="summary-band">
      <div><span>API-Sitzungen</span><strong>{pulse_html.esc(total)}</strong></div>
      <div><span>Erzeugte Dossiers</span><strong>{pulse_html.esc(dossier_count)}</strong></div>
      <div><span>Wahlperioden</span><strong>{pulse_html.esc(len(periods_sorted))}</strong></div>
    </section>
    <section class="filters" aria-label="Sitzungen filtern">
      <div class="filter-field">
        <label for="catalog-search">Suche</label>
        <input id="catalog-search" type="search" placeholder="Dokumentnummer, Titel oder Datum …" autocomplete="off" data-filter-search>
      </div>
      <div class="filter-field">
        <label for="catalog-wp">Wahlperiode</label>
        <select id="catalog-wp" data-filter-wp>
          <option value="">Alle Wahlperioden</option>
          {wp_options}
        </select>
      </div>
      <div class="filter-field">
        <label for="catalog-dossier">Dossier</label>
        <select id="catalog-dossier" data-filter-dossier>
          <option value="">Alle Sitzungen</option>
          <option value="1">Nur mit Dossier</option>
          <option value="0">Nur ohne Dossier</option>
        </select>
      </div>
      <div class="filter-field">
        <label for="catalog-sort">Sortierung</label>
        <select id="catalog-sort" data-filter-sort>
          <option value="date-desc">Neueste zuerst</option>
          <option value="date-asc">Älteste zuerst</option>
          <option value="num-desc">Dokumentnummer absteigend</option>
          <option value="num-asc">Dokumentnummer aufsteigend</option>
        </select>
      </div>
    </section>
    <div class="filter-status">
      <span><span data-result-count>{pulse_html.esc(total)}</span> von {pulse_html.esc(total)} Sitzungen</span>
      <button type="button" class="link-button" data-filter-reset hidden>Filter zurücksetzen</button>
    </div>
    <div class="periods">{period_badges}</div>
    <section class="catalog" data-catalog>
      {rows_html}
    </section>
    <p class="no-results" data-no-results hidden>Keine Sitzungen entsprechen den Filterkriterien.</p>
    <footer>
      Das XML-Protokoll ist maßgeblich; DIP-API-Daten ergänzen jede Sitzung. <a href="{pulse_html.esc(overview_href)}">Zurück zum Plenarprotokoll-Katalog</a> · <a href="sources.html">Quellen und Methode</a>.
    </footer>
  </div>
  {render_catalog_script()}
  {pulse_html.page_scripts(features)}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# PAGE: sources.html - "Quellen und Methode"
#
# The transparency page: which official sources are used, how each visible
# feature is derived from them, and what is deliberately excluded. Mostly static
# editorial copy inside the template; the only generated part is the table of
# sittings produced in this build.
# ---------------------------------------------------------------------------


def render_sources_page(
    entries: list[dict[str, Any]],
    database_href: str | None = None,
    database_page_href: str | None = None,
    features: Selection | None = None,
    publication_manifest: dict[str, Any] | None = None,
) -> str:
    features = features or publication_selection()
    # "Erzeugte Sitzungsdatensätze" table: one row per dossier with its metrics
    # and direct links to the XML, the PDF and the generated JSON.
    generated_rows = []
    for entry in entries:
        report = entry["report"]
        protocol = report.get("protocol") or {}
        summary = report.get("validation_summary") or {}
        source_actions = []
        for label, key in (("XML", "xml_url"), ("PDF", "pdf_url")):
            safe_url = pulse_html.safe_href(protocol.get(key))
            if safe_url:
                source_actions.append(f'<a href="{pulse_html.esc(safe_url)}">{label}</a>')
        source_actions.append(
            f'<a href="data/{pulse_html.esc(entry["report_path"].name)}">JSON</a>'
        )
        generated_rows.append(
            """
            <tr>
              <td><a href="protocols/{page}">{document}</a></td>
              <td>{date}</td>
              <td>{tops}</td>
              <td>{speeches}</td>
              <td class="source-actions">
                {source_actions}
              </td>
            </tr>
            """.format(
                page=pulse_html.esc(entry["page_path"].name),
                document=pulse_html.esc(protocol.get("dokumentnummer")),
                date=pulse_html.esc(protocol.get("datum")),
                tops=pulse_html.esc(summary.get("xml_top_count")),
                speeches=pulse_html.esc(summary.get("xml_speech_count")),
                source_actions="".join(source_actions),
            )
        )

    if not generated_rows:
        generated_rows.append('<tr><td colspan="5" class="muted">In diesem Build wurden keine Sitzungen erzeugt.</td></tr>')

    latest = entries[0]["report"].get("protocol", {}) if entries else {}
    status_manifest = publication_manifest or {}
    status_domains = status_manifest.get("domains") or {}
    status_labels = {
        "ready": "Verfügbar",
        "domain_empty": "Keine passenden Daten",
        "partial": "Teilweise verfügbar",
        "unavailable": "Nicht verfügbar",
        "omitted": "Nicht veröffentlicht",
    }
    source_details = {
        "votes": ("Abstimmungen", "Bundestag", "https://www.bundestag.de/parlament/plenum/abstimmung"),
        "profiles": ("Profilverknüpfungen", "abgeordnetenwatch.de", "https://www.abgeordnetenwatch.de/api"),
        "roster": ("Abgeordnetenkader", "Bundestag DIP", "https://dip.bundestag.de"),
        "summaries": ("KI-Zusammenfassungen", "Bundestag-Protokolle mit KI", "#ki-zusammenfassungen"),
    }
    status_rows = []
    for domain_id in ("votes", "profiles", "roster", "summaries"):
        domain = status_domains.get(domain_id) or {}
        title, source_label, source_url = source_details[domain_id]
        state = str(domain.get("presentation_state") or "unavailable")
        timing = []
        if domain.get("acquired_at"):
            timing.append(f'Daten abgerufen: <time datetime="{pulse_html.esc(domain["acquired_at"])}">{pulse_html.esc(domain["acquired_at"])}</time>')
        if state in {"partial", "unavailable"} and domain.get("attempted_at"):
            timing.append(f'Letzter Versuch: <time datetime="{pulse_html.esc(domain["attempted_at"])}">{pulse_html.esc(domain["attempted_at"])}</time>')
        if domain.get("source_updated_at"):
            timing.append(f'Quellstand: <time datetime="{pulse_html.esc(domain["source_updated_at"])}">{pulse_html.esc(domain["source_updated_at"])}</time>')
        else:
            timing.append("Kein Quellstand von der Quelle angegeben")
        status_rows.append(
            '<li class="status-row status-{}"><div><strong>{}</strong><span>{}</span></div>'
            '<div><b>{}</b><small>{}</small></div></li>'.format(
                pulse_html.esc(state),
                pulse_html.esc(title),
                f'<a href="{pulse_html.esc(source_url)}">{pulse_html.esc(source_label)}</a>',
                pulse_html.esc(status_labels.get(state, "Nicht verfügbar")),
                " · ".join(timing),
            )
        )
    generated_at = status_manifest.get("generated_at") or ""
    database_page_link = (
        f'<a href="{pulse_html.esc(database_page_href)}">Daten</a>' if database_page_href else ""
    )
    # The SQLite bullet in the method list only appears when this build actually
    # produced a database to link to.
    database_method_item = ""
    if database_page_href or database_href:
        database_links = []
        if database_page_href:
            database_links.append(f'<a href="{pulse_html.esc(database_page_href)}">Daten</a>')
        if database_href:
            database_links.append(f'<a href="{pulse_html.esc(database_href)}">SQLite herunterladen</a>')
        database_method_item = (
            "<li><strong>SQLite-Graph</strong><span>"
            "Die normalisierten Entitäten werden als SQLite-Datei veröffentlicht; "
            f"{' · '.join(database_links)}."
            "</span></li>"
        )
    licence_method_item = (
        '<li id="lizenz"><strong>Lizenz und Weiterverwendung</strong><span>'
        "Lizenzhinweis: siehe Quellen und Methode. Die genaue Lizenzformulierung für die "
        "veröffentlichten Datensätze steht noch aus."
        "</span></li>"
    )
    # Glossary of the DIP vorgangstyp labels shown in the Debattenprofil card on
    # puls.html; each label there links to its entry here by anchor.
    vorgangstyp_items = "".join(
        f'<li id="{pulse_html.vorgangstyp_anchor(kind)}">'
        f"<strong>{pulse_html.esc(kind)}</strong>"
        f"<span>{pulse_html.esc(entry['lang'])}</span></li>"
        for kind, entry in pulse_html.VORGANGSTYP_GLOSSARY.items()
    )
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Quellen</title>
  {pulse_html.page_head(features)}
  <style>
    :root {{
      --ink:#171a1f;
      --muted:#606a78;
      --line:#d9dee6;
      --paper:#f7f8fa;
      --panel:#ffffff;
      --blue:#174ea6;
      --teal:#0f766e;
      --amber:#9a5a00;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color:var(--ink);
      background:var(--paper);
      letter-spacing:0;
    }}
    a {{ color:var(--blue); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .shell {{ max-width:1120px; margin:0 auto; padding:28px 22px; }}
    {pulse_html.global_header_styles()}
    .page-header {{
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:24px;
      align-items:end;
      padding-bottom:22px;
      border-bottom:1px solid var(--line);
    }}
    h1 {{ margin:0; font-size:36px; line-height:1.1; }}
    h2 {{ margin:0 0 10px; font-size:21px; line-height:1.25; }}
    h3 {{ margin:0 0 8px; font-size:15px; }}
    p {{ margin:6px 0 0; color:var(--muted); line-height:1.55; }}
    .subtitle {{ max-width:760px; }}
    .latest {{
      display:grid;
      gap:4px;
      min-width:220px;
      padding:12px 14px;
      border:1px solid var(--line);
      border-radius:8px;
      background:white;
      font-size:13px;
    }}
    .latest span, .eyebrow {{
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .latest strong {{ font-size:18px; }}
    main {{ display:grid; gap:16px; margin-top:18px; }}
    .panel {{
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:8px;
      padding:18px;
    }}
    .source-grid {{
      display:grid;
      grid-template-columns:repeat(2, minmax(0,1fr));
      gap:14px;
    }}
    .source-card {{
      border:1px solid #e2e7ef;
      border-radius:8px;
      padding:14px;
      background:#fbfcfd;
    }}
    .source-card p {{ font-size:14px; }}
    .source-card a {{
      display:inline-flex;
      margin-top:10px;
      font-size:13px;
      font-weight:650;
    }}
    .method-list {{
      display:grid;
      gap:10px;
      margin:0;
      padding:0;
      list-style:none;
    }}
    .method-list li {{
      display:grid;
      grid-template-columns:150px minmax(0,1fr);
      gap:12px;
      padding-bottom:10px;
      border-bottom:1px solid #eef1f5;
      line-height:1.45;
    }}
    .method-list li:last-child {{ border-bottom:0; padding-bottom:0; }}
    .method-list strong {{ color:#273142; }}
    .method-list span {{ color:var(--muted); }}
    /* Glossary entries are link targets from the Debattenprofil on puls.html.
       Their terms are long compound nouns, so the term column is wider and may
       hyphenate instead of running into the explanation. */
    .method-list li {{ scroll-margin-top:16px; }}
    .method-list.glossary {{ margin-top:14px; }}
    .method-list.glossary li {{ grid-template-columns:190px minmax(0,1fr); }}
    .method-list.glossary strong {{ hyphens:auto; overflow-wrap:anywhere; }}
    .method-list li:target {{
      background:#eef4ff;
      border-radius:6px;
      padding:8px 8px 10px;
      margin:-8px -8px 0;
    }}
    .method-list li:target:last-child {{ padding-bottom:8px; }}
    table {{
      width:100%;
      border-collapse:collapse;
      font-size:14px;
    }}
    th, td {{
      padding:10px 8px;
      border-bottom:1px solid #eef1f5;
      text-align:left;
      vertical-align:top;
    }}
    th {{
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .source-actions {{
      display:flex;
      flex-wrap:wrap;
      gap:7px;
    }}
    .source-actions a {{
      display:inline-flex;
      min-height:25px;
      align-items:center;
      padding:3px 8px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      font-size:13px;
      font-weight:650;
    }}
    .note {{
      border-left:4px solid var(--teal);
      padding-left:12px;
    }}
    .muted {{ color:var(--muted); }}
    .status-list {{ list-style:none; margin:14px 0 0; padding:0; }}
    .status-row {{ display:grid; grid-template-columns:minmax(0,1fr) minmax(260px,1fr); gap:18px; padding:13px 0; border-bottom:1px solid var(--line); }}
    .status-row:last-child {{ border-bottom:0; }}
    .status-row div {{ display:grid; gap:4px; }}
    .status-row span, .status-row small {{ color:var(--muted); line-height:1.45; }}
    .status-row b {{ width:max-content; padding:3px 7px; border-radius:4px; font-size:13px; }}
    .status-ready b, .status-domain_empty b {{ background:#e7f6f3; color:#0f5f59; }}
    .status-partial b {{ background:#fbf1d3; color:#765410; }}
    .status-unavailable b {{ background:#fbe8e8; color:#8a2424; }}
    .status-omitted b {{ background:#eef1f5; color:#4f5b6b; }}
    footer {{ padding-top:8px; color:var(--muted); font-size:12px; }}
    @media (max-width: 760px) {{
      .shell {{ padding:18px 14px; }}
      .page-header, .source-grid {{ grid-template-columns:1fr; }}
      h1 {{ font-size:29px; }}
      .method-list li, .method-list.glossary li {{ grid-template-columns:1fr; gap:3px; }}
      .status-row {{ grid-template-columns:1fr; }}
      table, thead, tbody, tr, th, td {{ display:block; }}
      thead {{ display:none; }}
      td {{ padding:8px 0; }}
      tr {{ display:grid; gap:2px; padding:10px 0; border-bottom:1px solid #eef1f5; }}
      tr td {{ border-bottom:0; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(active="sources", features=features)}
    <header class="page-header">
      <div>
        <h1>Quellen</h1>
        <p class="subtitle">Bundestag-Puls basiert auf offiziellen Parlamentsunterlagen. Diese Seite dokumentiert, welche Quellen genutzt werden, wie sie verarbeitet werden und was bewusst ausgeschlossen bleibt.</p>
      </div>
      <div class="latest">
        <span>Zuletzt erzeugt</span>
        <strong>{pulse_html.esc(latest.get('dokumentnummer', ''))}</strong>
        <em>{pulse_html.esc(latest.get('datum', ''))}</em>
      </div>
    </header>
    <main>
      <section class="panel" id="datenstand">
        <h2>Datenstand dieser Veröffentlichung</h2>
        <p>Veröffentlicht: <time datetime="{pulse_html.esc(generated_at)}">{pulse_html.esc(generated_at)}</time>. Optionale Quellen werden getrennt ausgewiesen, damit fehlende Daten nicht mit einem echten Null-Ergebnis verwechselt werden.</p>
        <ul class="status-list">{''.join(status_rows)}</ul>
      </section>
      <section class="panel">
        <h2>Primärquellen</h2>
        <div class="source-grid">
          <article class="source-card">
            <span class="eyebrow">Maßgebliches Protokoll</span>
            <h3>Bundestag Plenarprotokoll XML</h3>
            <p>Tagesordnungspunkte, Redetext, Redner, Seitenangaben und in der Sitzung genannte Drucksachen werden aus dem offiziellen XML-Protokoll gelesen.</p>
            <a href="https://search.dip.bundestag.de/api/v1/plenarprotokoll">DIP Plenarprotokoll API</a>
          </article>
          <article class="source-card">
            <span class="eyebrow">Metadaten-Anreicherung</span>
            <h3>DIP-API-Datensätze</h3>
            <p>Vorgangspositionen, parlamentarische Aktivitäten, Dokumentmetadaten und verknüpfte Drucksachen kommen aus der Bundestag-DIP-API und werden dem passenden Tagesordnungspunkt zugeordnet.</p>
            <a href="https://search.dip.bundestag.de/api/v1">DIP-API-Basis</a>
          </article>
          <article class="source-card">
            <span class="eyebrow">Originaldokumente</span>
            <h3>Drucksachen und PDFs</h3>
            <p>Dokumentnummern werden aus Protokoll-Links extrahiert und mit DIP-Positionen abgeglichen. PDF-Links erscheinen, wenn der offizielle Datensatz sie enthält.</p>
            <a href="https://dip.bundestag.de">DIP-Dokumentensuche</a>
          </article>
          <article class="source-card">
            <span class="eyebrow">Namentliche Abstimmungen</span>
            <h3>Namentliche Abstimmungen</h3>
            <p>Abstimmungssummen, Fraktionssummen und einzelne Stimmen kommen von den Bundestag-Seiten zu namentlichen Abstimmungen und werden über Sitzungsdatum und Drucksachennummern zugeordnet.</p>
            <a href="https://www.bundestag.de/parlament/plenum/abstimmung">Bundestag namentliche Abstimmungen</a>
          </article>
          <article class="source-card">
            <span class="eyebrow">Abgeordnetenprofile</span>
            <h3>abgeordnetenwatch.de</h3>
            <p>Rednerinnen und Redner werden mit ihrem Profil auf abgeordnetenwatch.de verknüpft — primär über die Bundestags-Redner-ID (ext_id_bundestagsverwaltung), ersatzweise über Name und Fraktion. Die offenen Daten stehen unter CC0.</p>
            <a href="https://www.abgeordnetenwatch.de/api">abgeordnetenwatch.de API</a>
          </article>
        </div>
      </section>
      <section class="panel">
        <h2>Wie die Seite sie nutzt</h2>
        <ul class="method-list">
          <li><strong>Tagesordnungspunkte</strong><span>Aus der Tagesordnungspunkt-Struktur des Plenarprotokoll-XML gelesen. Die parlamentarische Gliederung bildet die Themen-Grenze.</span></li>
          <li><strong>Aufmerksamkeitsranking</strong><span>Mechanisch aus extrahierter Redenanzahl und extrahierten Redetext-Zeichen pro Tagesordnungspunkt berechnet.</span></li>
          <li><strong>Redner und Fraktionen</strong><span>Aus den Redner-Knoten im XML-Protokoll gelesen. Regierungsrollen werden angezeigt, wenn das XML eine Rolle statt einer Fraktion liefert.</span></li>
          <li><strong>Abgeordnetenprofile</strong><span>Jeder Name verlinkt das passende Profil auf abgeordnetenwatch.de. Zugeordnet wird über die Bundestags-Redner-ID, ersatzweise über Name und Fraktion; nur eindeutige Treffer werden verlinkt, mehrdeutige bleiben ohne Link.</span></li>
          <li><strong>Verknüpfte Dokumente</strong><span>Kombiniert Drucksachen, die direkt im Protokoll verlinkt sind, mit zugehörigen DIP-Vorgangspositionen der Sitzung.</span></li>
          <li><strong>Abstimmungspanels</strong><span>Werden nur angezeigt, wenn eine namentliche Abstimmung am selben Datum über überlappende Drucksachennummern einem Tagesordnungspunkt zugeordnet werden kann.</span></li>
          <li><strong>Erzeugtes JSON</strong><span>Jede Sitzungsseite verlinkt den Zwischenbericht als JSON, damit Extraktion und Anreicherung direkt geprüft werden können.</span></li>
          <li id="ki-zusammenfassungen"><strong>KI-Zusammenfassungen</strong><span>Sie sind als „KI-generiert · nicht redaktionell geprüft“ markiert und verlinken drei bis fünf technisch geprüfte Belegstellen. Diese Linkprüfung beweist weder sachliche Richtigkeit noch Ausgewogenheit oder Vollständigkeit.</span></li>
          {database_method_item}
          {licence_method_item}
        </ul>
      </section>
      <section class="panel" id="{pulse_html.VORGANGSTYP_GLOSSARY_ANCHOR}">
        <h2>Vorgangstypen im Debattenprofil</h2>
        <p>Jede Vorgangsposition einer Sitzung gehört zu einem Vorgang im DIP, und jeder Vorgang hat dort einen Typ. Das Debattenprofil auf der Puls-Seite zählt die Vorgangspositionen der Sitzungswoche nach diesem Typ. Die Bezeichnungen folgen der DIP-Klassifikation; die Erläuterungen fassen zusammen, was jeweils dahintersteht.</p>
        <ul class="method-list glossary">
          {vorgangstyp_items}
        </ul>
      </section>
      <section class="panel note">
        <h2>Was nicht genutzt wird</h2>
        <p>Für den aktuellen Prototyp werden keine Nachrichtenartikel, Umfrage-Aggregatoren, Wahlkampfmaterialien, Social-Media-Posts oder redaktionellen Kommentare als Quellen genutzt. Die aktuellen Seiten zeigen extrahierte Datensätze und mechanische Kennzahlen; sie treffen keine unbelegten Haltungs-Aussagen.</p>
      </section>
      <section class="panel">
        <h2>Erzeugte Sitzungsdatensätze</h2>
        <table>
          <thead>
            <tr>
              <th>Protokoll</th>
              <th>Datum</th>
              <th>TOPs</th>
              <th>Reden</th>
              <th>Belege</th>
            </tr>
          </thead>
          <tbody>
            {''.join(generated_rows)}
          </tbody>
        </table>
      </section>
    </main>
    <footer>
      Quellenlinks verweisen auf öffentliche Bundestags- und DIP-Datensätze. Verfügbarkeit und genaue Inhalte werden von diesen offiziellen Diensten bestimmt. <a href="overview.html">Sitzungen</a> · <a href="bills/index.html">Gesetze</a> · <a href="abgeordnete/index.html">Abgeordnete</a>
    </footer>
  </div>
  {pulse_html.page_scripts(features)}
</body>
</html>
    """


# ---------------------------------------------------------------------------
# PAGE: settings.html - temporary 0.5.x compatibility notice.
# ---------------------------------------------------------------------------


def _publication_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_publication_manifest(
    *,
    root: Path,
    protocols: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    abg_mps: list[dict[str, Any]],
    bill_count: int,
    enrichments: EnrichmentSelection | None,
    summary_mode: str,
    acquisition_attempted: bool,
    development_output: bool,
    previous_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate validated schema-v2 facts after acquisition has finished."""
    now = _publication_timestamp()
    selected = set(enrichments.ids if enrichments is not None else ())
    reports = [entry.get("report") or {} for entry in entries]
    previous_domains = (previous_manifest or {}).get("domains") or {}

    def previous_time(domain: str, field: str) -> str | None:
        value = (previous_domains.get(domain) or {}).get(field)
        return str(value) if value else None
    agenda_items = [item for report in reports for item in (report.get("agenda_items") or [])]
    entry_by_number = {
        normalized_document_number((entry.get("report") or {}).get("protocol", {}).get("dokumentnummer")): entry
        for entry in entries
    }
    dossier_items = []
    for protocol in protocols:
        document_number = normalized_document_number(protocol.get("dokumentnummer"))
        entry = entry_by_number.get(document_number)
        if entry:
            dossier_items.append(
                publication.DossierItem(
                    document_number=document_number,
                    presentation_state="ready",
                    report_path=entry["report_path"].relative_to(root).as_posix(),
                    page_path=entry["page_path"].relative_to(root).as_posix(),
                )
            )
        else:
            reasons = tuple(protocol.get("dossier_failure_reasons") or ())
            dossier_items.append(
                publication.DossierItem(
                    document_number=document_number,
                    presentation_state="unavailable" if reasons else "not_requested",
                    failure_reasons=reasons,
                )
            )

    vote_records = sum(len(_iter_report_votes(item)) for item in agenda_items)
    profile_targets = len(abg_mps) + sum(len(item.get("xml_speakers") or []) for item in agenda_items)
    profile_records = sum(1 for mp in abg_mps if mp.get("profile_url")) + sum(
        1
        for item in agenda_items
        for speech in (item.get("xml_speakers") or [])
        if ((speech.get("speaker") or {}).get("abgeordnetenwatch") or {}).get("url")
    )
    roster_records = sum(1 for mp in abg_mps if mp.get("is_mdb"))
    summary_records = sum(1 for item in agenda_items if usable_llm_summary(item.get("llm_summary")))
    summary_eligible = max(summary_records, sum(
        1
        for item in agenda_items
        if sum(
            1
            for speech in (item.get("xml_speakers") or [])
            if speech.get("text") or speech.get("paragraphs")
        )
        >= 3
    ))

    def optional_domain(domain: str, source: str, records: int, selected_id: str) -> publication.DomainFacts:
        requested = selected_id in selected
        cached = records > 0 and not requested
        state = publication.AcquisitionState.COMPLETE if requested or cached else publication.AcquisitionState.NOT_REQUESTED
        return publication.DomainFacts(
            domain=domain,
            acquisition_state=state,
            source=source,
            records=records,
            reused=records if cached else 0,
            acquired_at=now if requested and acquisition_attempted and records else None,
            attempted_at=now if requested and acquisition_attempted else None,
            attempted=requested and acquisition_attempted,
        )

    def aggregate_report_domain(
        domain: str,
        source: str,
        records: int,
        selected_id: str,
    ) -> publication.DomainFacts:
        raw_facts = [
            ((report.get("acquisition") or {}).get(domain) or {})
            for report in reports
            if ((report.get("acquisition") or {}).get(domain) or {})
        ]
        if not raw_facts:
            if domain == "summaries":
                requested = summary_mode != "off"
                generated = records if requested and acquisition_attempted else 0
                reused_count = records - generated
                return publication.DomainFacts(
                    domain=domain,
                    acquisition_state=(
                        publication.AcquisitionState.COMPLETE
                        if requested or records
                        else publication.AcquisitionState.NOT_REQUESTED
                    ),
                    source=source,
                    records=records,
                    reused=reused_count,
                    acquired_at=now if generated else None,
                    attempted_at=now if requested and acquisition_attempted else None,
                    attempted=requested and acquisition_attempted,
                    counters={
                        "eligible": summary_eligible,
                        "generated": generated,
                        "omitted": max(0, summary_eligible - records),
                        "failed": 0,
                        "fallbacks": 0,
                    },
                )
            return optional_domain(domain, source, records, selected_id)

        states = [str(fact.get("acquisition_state")) for fact in raw_facts]
        aggregate_records = sum(int(fact.get("records") or 0) for fact in raw_facts)
        reused = sum(int(fact.get("reused") or 0) for fact in raw_facts)
        rejected = sum(int(fact.get("rejected") or 0) for fact in raw_facts)
        reasons = tuple(
            dict.fromkeys(
                reason
                for fact in raw_facts
                for reason in (fact.get("failure_reasons") or [])
            )
        )
        if all(state == "not_requested" for state in states):
            state = publication.AcquisitionState.NOT_REQUESTED
        elif any(state in {"partial", "failed"} for state in states) or len(set(states)) > 1:
            state = (
                publication.AcquisitionState.PARTIAL
                if aggregate_records
                else publication.AcquisitionState.FAILED
            )
            if state is publication.AcquisitionState.FAILED and not reasons:
                reasons = ("source_unavailable",)
        else:
            state = publication.AcquisitionState.COMPLETE

        acquired_times = sorted(str(fact["acquired_at"]) for fact in raw_facts if fact.get("acquired_at"))
        attempted_times = sorted(str(fact["attempted_at"]) for fact in raw_facts if fact.get("attempted_at"))
        source_times = sorted(str(fact["source_updated_at"]) for fact in raw_facts if fact.get("source_updated_at"))
        counters: dict[str, int] = {}
        if domain == "summaries":
            counters = {
                key: sum(int(fact.get(key) or 0) for fact in raw_facts)
                for key in ("eligible", "generated", "omitted", "failed", "fallbacks")
            }
        return publication.DomainFacts(
            domain=domain,
            acquisition_state=state,
            source=source,
            records=aggregate_records,
            reused=reused,
            rejected=rejected,
            failure_reasons=reasons,
            acquired_at=acquired_times[0] if acquired_times else None,
            attempted_at=attempted_times[-1] if attempted_times else None,
            source_updated_at=source_times[0] if source_times else None,
            attempted=bool(attempted_times),
            counters=counters,
        )

    catalog_state = publication.AcquisitionState.COMPLETE if protocols else publication.AcquisitionState.FAILED
    catalog_reasons = () if protocols else ("empty_required_dataset",)
    version = (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
    domains = (
        publication.DomainFacts(
            domain="catalog",
            acquisition_state=catalog_state,
            source="bundestag-dip",
            records=len(protocols),
            reused=len(protocols) if protocols and not acquisition_attempted else 0,
            failure_reasons=catalog_reasons,
            acquired_at=(now if acquisition_attempted and protocols else previous_time("catalog", "acquired_at")),
            attempted_at=now if acquisition_attempted else None,
            attempted=acquisition_attempted,
        ),
        publication.DomainFacts(
            domain="dossiers",
            acquisition_state=(publication.AcquisitionState.COMPLETE if entries else publication.AcquisitionState.NOT_REQUESTED),
            source="bundestag-xml",
            records=len(entries),
            reused=len(entries) if not acquisition_attempted else 0,
            acquired_at=(now if acquisition_attempted and entries else previous_time("dossiers", "acquired_at")),
            attempted_at=now if acquisition_attempted and entries else None,
            attempted=acquisition_attempted and bool(entries),
            items=tuple(dossier_items),
        ),
        aggregate_report_domain("votes", "bundestag-roll-call", vote_records, "votes"),
        aggregate_report_domain("profiles", "abgeordnetenwatch", profile_records, "aw-profiles"),
        (
            publication.DomainFacts(
                domain="roster",
                acquisition_state=publication.AcquisitionState.COMPLETE,
                source="bundestag-dip",
                records=roster_records,
                reused=roster_records if "mp-roster" not in selected else 0,
                acquired_at=(
                    now
                    if "mp-roster" in selected and acquisition_attempted
                    else previous_time("roster", "acquired_at")
                ),
                attempted_at=now if "mp-roster" in selected and acquisition_attempted else None,
                attempted="mp-roster" in selected and acquisition_attempted,
            )
            if roster_records
            else publication.DomainFacts(
                domain="roster",
                acquisition_state=(
                    publication.AcquisitionState.FAILED
                    if "mp-roster" in selected and acquisition_attempted
                    else publication.AcquisitionState.NOT_REQUESTED
                ),
                source="bundestag-dip",
                records=0,
                failure_reasons=(
                    ("empty_required_dataset",)
                    if "mp-roster" in selected and acquisition_attempted
                    else ()
                ),
                attempted_at=now if "mp-roster" in selected and acquisition_attempted else None,
                attempted="mp-roster" in selected and acquisition_attempted,
            )
        ),
        publication.DomainFacts(
            domain="bills",
            acquisition_state=publication.AcquisitionState.COMPLETE,
            source="derived-dip",
            records=bill_count,
        ),
        aggregate_report_domain(
            "summaries",
            "llm-with-bundestag-citations",
            summary_records,
            "summaries",
        ),
    )
    return publication.manifest(
        generated_at=now,
        version=version,
        development_output=development_output,
        domains=domains,
    )


def derive_feature_readiness(
    entries: list[dict[str, Any]],
    abg_mps: list[dict[str, Any]],
    *,
    bill_count: int,
) -> dict[str, str]:
    """Summarize acquired coverage for export metadata, never for UI gating."""
    reports = [entry.get("report") or {} for entry in entries]
    agenda_items = [item for report in reports for item in (report.get("agenda_items") or [])]
    vote_items = sum(1 for item in agenda_items if _iter_report_votes(item))
    summary_items = sum(1 for item in agenda_items if usable_llm_summary(item.get("llm_summary")))
    profile_targets = len(abg_mps)
    profile_count = sum(1 for mp in abg_mps if mp.get("profile_url"))
    for item in agenda_items:
        for speech in item.get("xml_speakers") or []:
            profile_targets += 1
            if ((speech.get("speaker") or {}).get("abgeordnetenwatch") or {}).get("url"):
                profile_count += 1

    def coverage(present: int, total: int) -> str:
        if present <= 0:
            return "unavailable"
        return "ready" if total > 0 and present >= total else "partial"

    bills_state = "ready" if bill_count else "unavailable"
    return {
        "votes": coverage(vote_items, len(agenda_items)),
        "summaries": coverage(summary_items, len(agenda_items)),
        "aw-profiles": coverage(profile_count, profile_targets),
        "mp-pages": "ready" if abg_mps else "unavailable",
        "mp-roster": "ready" if any(mp.get("is_mdb") for mp in abg_mps) else "unavailable",
        "bills": bills_state,
        "bill-follow": bills_state,
        "dev-view": "ready",
    }


def render_settings_page(
    features: Selection | None = None,
    readiness: dict[str, str] | None = None,
) -> str:
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Feste öffentliche Ansicht</title>
  {pulse_html.page_head()}
  <style>
    :root {{ --ink:#171a1f; --muted:#606a78; --line:#d9dee6; --paper:#f7f8fa; --panel:#fff; --blue:#174ea6; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:var(--ink); background:var(--paper); }}
    a {{ color:var(--blue); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .shell {{ max-width:1080px; margin:0 auto; padding:24px; }}
    {pulse_html.global_header_styles()}
    .page-header {{ margin-bottom:22px; }}
    .page-header h1 {{ margin:0; font-size:34px; }}
    .page-header p {{ max-width:760px; color:var(--muted); line-height:1.55; }}
    .compatibility-card {{ max-width:760px; padding:24px; border:1px solid var(--line); border-radius:10px; background:var(--panel); }}
    .compatibility-card h2 {{ margin-top:0; }}
    .compatibility-card p {{ line-height:1.6; }}
    .button {{ display:inline-flex; min-height:44px; align-items:center; padding:8px 14px; border:1px solid var(--blue); border-radius:6px; font-weight:700; }}
    .button:focus-visible {{ outline:2px solid var(--blue); outline-offset:3px; }}
    footer {{ margin-top:24px; padding-top:18px; border-top:1px solid var(--line); color:var(--muted); font-size:12px; }}
  </style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header()}
    <header class="page-header">
      <span class="eyebrow">Kompatibilitätsseite · Version 0.5.x</span>
      <h1>Eine feste öffentliche Ansicht</h1>
      <p>Bundestag-Puls veröffentlicht jetzt eine gemeinsame, redaktionell gestaltete Ansicht. Frühere Baustein-Einstellungen in diesem Browser werden nicht mehr verwendet.</p>
    </header>
    <main class="compatibility-card">
      <h2>Was sich geändert hat</h2>
      <p>Sitzungen, Abstimmungen, Gesetze und Abgeordnetenprofile werden immer dann gezeigt, wenn sie für die jeweilige Seite gelten. Fehlende oder unvollständige Daten werden direkt am betroffenen Inhalt erklärt.</p>
      <p>Nur vorhandene KI-Zusammenfassungen lassen sich weiterhin ein- oder ausklappen. Diese Einstellung betrifft ausschließlich KI-generierte Texte, nicht die Quelleninhalte.</p>
      <a class="button" href="sources.html#datenstand">Datenstand dieser Veröffentlichung</a>
    </main>
    <footer>Diese Seite bleibt für alte Lesezeichen bis Version 0.6.0 erreichbar. <a href="sources.html">Quellen und Methode</a></footer>
  </div>
  {pulse_html.page_scripts()}
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Site assembly
# ---------------------------------------------------------------------------


# Write every page of the site that is not a per-sitting dossier.
#
# By the time this runs, all data work is done: `entries` are the built dossiers,
# `abg_mps`/`mp_lookup` come from the store, and nothing here touches the
# network. Returns the path of index.html, which main() prints on stdout.
def render_site(
    *,
    output_dir: Path,
    database_path: Path,
    no_persist: bool,
    protocols: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    abg_mps: list[dict[str, Any]],
    mp_lookup: dict[str, int],
    features: Selection | None = None,
    enrichments: EnrichmentSelection | None = None,
    summary_mode: str = "reuse",
    acquisition_attempted: bool = False,
    include_dev_view: bool = False,
    today: date | datetime | None = None,
    week: tuple[int, int] | None = None,
    manifest: dict[str, Any] | None = None,
    data_base_url: str = "data/exports/",
    data_export_error: str | None = None,
    is_remote_manifest: bool = False,
    bill_slugs: set[str] | None = None,
) -> Path:
    # Publication is intentionally independent from update-time enrichments.
    # Keep the argument for one release so external callers do not break, but
    # never let a reduced enrichment selection remove visitor-facing pages.
    features = publication_selection()
    # Every page below treats entries[0] and protocols[0] as the current pulse, so
    # both lists must run newest sitting first. The offline render does not do that
    # on its own: it walks cached dossiers in glob order, where the slug 20-100
    # sorts ahead of 21-84 and a 2023 sitting wins the pulse. Sorting protocols is
    # a guard rather than a fix, because every caller happens to sort already and
    # the DIP catalog arrives newest-first, but that ordering is undocumented.
    entries = sorted(entries, key=entry_sort_key, reverse=True)
    protocols = sorted(protocols, key=protocol_sort_key, reverse=True)

    # Every protocol document number this build actually produced a dossier
    # for - the join key resolve_entity_link and the Fakt der Woche pages use
    # to decide whether a "document" citation gets a link at all.
    document_numbers = {
        entry["report"]["protocol"].get("dokumentnummer")
        for entry in entries
        if entry.get("report") and entry["report"].get("protocol")
    }
    document_numbers.discard(None)

    previous_manifest = None
    previous_manifest_path = output_dir / "data" / "features.json"
    if previous_manifest_path.is_file():
        try:
            previous_manifest = publication.validate_manifest(
                json.loads(previous_manifest_path.read_text(encoding="utf-8"))
            )
        except (OSError, json.JSONDecodeError, publication.PublicationStateError):
            # Legacy or damaged manifests never control the new publication;
            # they simply cannot contribute trusted acquisition timestamps.
            previous_manifest = None

    # The download link on every other page ("SQLite herunterladen") points at
    # the distribution copy named in the manifest, never at the build store
    # itself - the export step is the only writer of a manifest, and it never
    # runs under --no-persist.
    database_href = None
    if manifest is not None:
        sqlite_file = manifest["files"][0]
        database_href = f"{data_base_url}{manifest['generation']}/{sqlite_file['name']}"
    # database.html carries content exactly when a manifest exists (an export
    # from this build, or a --data-manifest override), so that is what the
    # in-page "Daten" links key on.
    database_page_href = "database.html" if manifest is not None else None
    data_stand = None
    if manifest is not None:
        stand_display, _ = format_datenstand_timestamp(manifest["generated_at"])
        data_stand = f"Stand {stand_display} · {pulse_html.format_int(manifest['protocols']['count'])} Protokolle"

    # The raw catalog as JSON. It is also what load_cached_protocols() reads back
    # for an --offline render.
    catalog_path = output_dir / "data" / "plenarprotokoll-catalog.json"
    catalog_path.write_text(json.dumps(protocols, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    components = {
        component.feature.id: component
        for component in feature_loader.load(features, include_dev_view=include_dev_view)
    }
    component_context = {
        "selection": features,
        "entries": entries,
        "abg_mps": abg_mps,
        "mp_lookup": mp_lookup,
        "collect_bill_pages": collect_bill_pages,
        "write_bill_pages": write_bill_pages,
        "write_abgeordnete_pages": write_abgeordnete_pages,
        "write_facts_pages": write_facts_pages,
        "database_path": database_path,
        "no_persist": no_persist,
        "document_numbers": document_numbers,
        "bill_slugs": bill_slugs or set(),
    }
    # Visitor-facing areas are always present. They render honest empty states
    # when the corresponding enrichment data has not been acquired yet.
    bill_output = components["bills"].write_pages(output_dir, component_context)
    publication_manifest = build_publication_manifest(
        root=output_dir,
        protocols=protocols,
        entries=entries,
        abg_mps=abg_mps,
        bill_count=int(bill_output["count"]),
        enrichments=enrichments,
        summary_mode=summary_mode,
        acquisition_attempted=acquisition_attempted,
        development_output=include_dev_view,
        previous_manifest=previous_manifest,
    )
    component_context["publication_domains"] = publication_manifest["domains"]
    abg_output = components["mp-pages"].write_pages(output_dir, component_context)
    print(
        f"abgeordnete: {abg_output['count']} gelistet, "
        f"{abg_output['detail_count']} Profilseiten",
        file=sys.stderr,
    )
    facts_output = components["facts"].write_pages(output_dir, component_context)
    print(
        f"fakten: {facts_output['posted']} Fakten in {facts_output['periods']} Sitzungswochen",
        file=sys.stderr,
    )
    # The core pages. Each render_* call below owns exactly one output file.
    index_path = output_dir / "index.html"
    pulse_path = output_dir / "puls.html"
    overview_path = output_dir / "overview.html"
    catalog_page_path = output_dir / "api-sitzungen.html"
    sources_path = output_dir / "sources.html"
    database_page_path = output_dir / "database.html"
    settings_path = output_dir / "settings.html"
    feature_manifest_path = output_dir / "data" / "features.json"
    feature_manifest_path.write_text(
        json.dumps(publication_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    index_path.write_text(
        render_landing_page(
            entries,
            database_page_href=database_page_href,
            data_stand=data_stand,
            protocol_count=len(protocols),
            bill_count=int(bill_output["count"]),
            features=features,
        ),
        encoding="utf-8",
    )
    pulse_path.write_text(
        render_front_page(entries, database_href=database_href, features=features, today=today, week=week),
        encoding="utf-8",
    )
    overview_path.write_text(
        render_overview(
            protocols,
            entries,
            bill_count=int(bill_output["count"]),
            database_href=database_href,
            database_page_href=database_page_href,
            features=features,
        ),
        encoding="utf-8",
    )
    catalog_page_path.write_text(
        render_catalog_page(
            protocols,
            entries,
            catalog_path,
            database_page_href=database_page_href,
            features=features,
        ),
        encoding="utf-8",
    )
    sources_path.write_text(
        render_sources_page(
            entries,
            database_href=database_href,
            database_page_href=database_page_href,
            features=features,
            publication_manifest=publication_manifest,
        ),
        encoding="utf-8",
    )
    if manifest is not None:
        database_page_path.write_text(
            render_database_page(
                manifest,
                data_base_url=data_base_url,
                mp_lookup=mp_lookup,
                document_numbers=document_numbers,
                bill_slugs=bill_slugs or set(),
                is_remote=is_remote_manifest,
                features=features,
            ),
            encoding="utf-8",
        )
    else:
        database_page_path.write_text(
            render_database_unavailable_page(features, reason=data_export_error),
            encoding="utf-8",
        )
    settings_path.write_text(render_settings_page(), encoding="utf-8")
    if not include_dev_view:
        publication.validate_publication_directory(output_dir)
    return index_path


# ---------------------------------------------------------------------------
# Update-time enrichment resolution and legacy feature compatibility
#
# The old feature vocabulary remains readable for one release. New configuration
# uses `enrich` / --enrich and affects network-backed acquisition only; the
# publication selection is fixed separately by publication_selection().
# ---------------------------------------------------------------------------


# Accept "a,b", ["a", "b"] and nested lists alike.
def _split_feature_tokens(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [token.strip() for token in value.split(",") if token.strip()]
    if isinstance(value, (list, tuple)):
        tokens: list[str] = []
        for item in value:
            tokens.extend(_split_feature_tokens(item))
        return tokens
    raise FeatureError(f"Ungültige Baustein-Konfiguration: {value!r}")


# Apply "+id" / "-id" / "id" tokens to the current set. An unknown id is fed
# through resolve() purely so it raises the standard FeatureError message.
def _apply_feature_tokens(current: set[str], tokens: list[str], vetoes: set[str]) -> None:
    for token in tokens:
        operation = token[:1] if token[:1] in {"+", "-"} else "+"
        feature_id = token[1:] if token[:1] in {"+", "-"} else token
        if feature_id not in REGISTRY:
            resolve(base=current, enable=(feature_id,))
        if operation == "+":
            current.add(feature_id)
            vetoes.discard(feature_id)
        else:
            current.discard(feature_id)
            vetoes.add(feature_id)


# Load enrichment config plus deprecated feature-selection shapes.
def _apply_features_file(path: Path, current: set[str], vetoes: set[str]) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FeatureError(f"Baustein-Datei {path} konnte nicht gelesen werden: {exc}") from exc
    if isinstance(payload, list):
        replacement = _split_feature_tokens(payload)
        current.clear()
        vetoes.clear()
        _apply_feature_tokens(current, replacement, vetoes)
        return
    if not isinstance(payload, dict):
        raise FeatureError(f"Baustein-Datei {path} muss ein Objekt oder eine Liste enthalten.")
    if "features" in payload:
        replacement = _split_feature_tokens(payload["features"])
        current.clear()
        vetoes.clear()
        if replacement == ["all"]:
            current.update(REGISTRY)
        else:
            _apply_feature_tokens(current, replacement, vetoes)
    _apply_feature_tokens(current, [f"+{item.lstrip('+')}" for item in _split_feature_tokens(payload.get("enable"))], vetoes)
    _apply_feature_tokens(current, [f"-{item.lstrip('-')}" for item in _split_feature_tokens(payload.get("disable"))], vetoes)
    for feature_id in _split_feature_tokens(payload.get("enrich")):
        if feature_id == "all":
            current.update(ENRICHMENT_IDS)
        elif feature_id in ENRICHMENT_IDS:
            current.add(feature_id)
        else:
            choices = ", ".join(sorted(ENRICHMENT_IDS))
            raise FeatureError(f"Unbekannte Anreicherung: {feature_id}. Verfügbar: {choices}, all")


# Build the final Selection for this run, then let features.resolve() close it
# over dependencies and validate it.
def resolve_from_args(args: argparse.Namespace, *, root: Path) -> EnrichmentSelection:
    """Resolve operator acquisition as one ordered, provenance-carrying stream."""
    current: set[str] = set()
    operations: list[tuple[str, str, str]] = []

    def validate_id(value: str, source: str) -> tuple[str, ...]:
        if value == "all":
            return tuple(ENRICHMENT_REGISTRY)
        if value not in ENRICHMENT_REGISTRY:
            choices = ", ".join(ENRICHMENT_REGISTRY)
            raise FeatureError(
                f"ERROR [invalid-enrichment]: {value!r} from {source}. "
                f"Valid values: {choices}, all. Fix: use --list-capabilities. "
                "Docs: README.md#operator-controls"
            )
        return (value,)

    def replace(values: Any, source: str) -> None:
        tokens = _split_feature_tokens(values)
        previous = sorted(current)
        current.clear()
        for value in previous:
            operations.append(("overridden", value, source))
        for token in tokens:
            for value in validate_id(token.lstrip("+"), source):
                current.add(value)
                operations.append(("replace", value, source))

    def add(values: Any, source: str) -> None:
        for token in _split_feature_tokens(values):
            for value in validate_id(token.lstrip("+"), source):
                current.add(value)
                operations.append(("add", value, source))

    def remove(values: Any, source: str) -> None:
        for token in _split_feature_tokens(values):
            raw = token[1:] if token.startswith("-") else token
            if raw not in ENRICHMENT_REGISTRY:
                continue
            current.discard(raw)
            operations.append(("remove", raw, source))

    def load_config(path: Path, *, replace_enrich: bool) -> None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise FeatureError(
                f"ERROR [invalid-enrichment-config]: {path}: {exc}. "
                "Fix: use a JSON object with an enrich array. Docs: README.md#operator-controls"
            ) from exc
        if not isinstance(payload, dict):
            raise FeatureError(f"ERROR [invalid-enrichment-config]: {path} must contain a JSON object")
        if "enrich" in payload:
            (replace if replace_enrich else add)(payload["enrich"], str(path))
        if "features" in payload:
            legacy = [token for token in _split_feature_tokens(payload["features"]) if token in ENRICHMENT_REGISTRY or token == "all"]
            replace(legacy, f"{path} (legacy features)")
        add([token for token in _split_feature_tokens(payload.get("enable")) if token in ENRICHMENT_REGISTRY], f"{path} (legacy enable)")
        remove(payload.get("disable"), f"{path} (legacy disable)")

    repository_config = root / "features.json"
    if repository_config.exists():
        load_config(repository_config, replace_enrich=True)
    local_config = root / "features.local.json"
    if local_config.exists():
        load_config(local_config, replace_enrich=True)
    if getattr(args, "features_file", None):
        load_config(Path(args.features_file), replace_enrich=True)

    legacy_env = _split_feature_tokens(os.environ.get("BUNDESTAG_PULSE_FEATURES"))
    if legacy_env:
        replace([token for token in legacy_env if token in ENRICHMENT_REGISTRY or token == "all"], "BUNDESTAG_PULSE_FEATURES")
    add(os.environ.get("BUNDESTAG_PULSE_ENRICHMENTS"), "BUNDESTAG_PULSE_ENRICHMENTS")

    if getattr(args, "features", None):
        tokens = [token for token in _split_feature_tokens(args.features) if token in ENRICHMENT_REGISTRY or token == "all"]
        replace(tokens, "--features")
    add([value for value in (getattr(args, "enable", None) or []) if value in ENRICHMENT_REGISTRY], "--enable")
    remove(getattr(args, "disable", None), "--disable")
    if getattr(args, "no_roster", False):
        remove(("mp-roster",), "--no-roster")
    if getattr(args, "no_abgeordnetenwatch", False):
        remove(("aw-profiles",), "--no-abgeordnetenwatch")

    add(getattr(args, "enrich", None), "--enrich")
    if (getattr(args, "vote_scan_pages", None) or 0) > 0:
        add(("votes",), "--vote-scan-pages")
    return EnrichmentSelection(frozenset(current), tuple(operations))


# Mirror the resolved selection back onto the argparse namespace, so the parts of
# the pipeline that still read the old flags stay consistent with it. Disabling
# "votes" this way also skips the (slow) roll-call scraping.
def apply_to_args(args: argparse.Namespace, selection: EnrichmentSelection) -> None:
    args.no_roster = "mp-roster" not in selection
    args.no_abgeordnetenwatch = "aw-profiles" not in selection
    if "votes" in selection:
        args.vote_scan_pages = 30 if getattr(args, "vote_scan_pages", None) is None else args.vote_scan_pages
    else:
        args.vote_scan_pages = 0


def warn_deprecated_feature_configuration(args: argparse.Namespace, *, root: Path) -> None:
    """Keep old commands working for one release while teaching the new model."""
    used = []
    if getattr(args, "features", None):
        used.append("--features")
    if getattr(args, "enable", None):
        used.append("--enable")
    if getattr(args, "disable", None):
        used.append("--disable")
    if os.environ.get("BUNDESTAG_PULSE_FEATURES"):
        used.append("BUNDESTAG_PULSE_FEATURES")
    if getattr(args, "no_roster", False):
        used.append("--no-roster")
    if getattr(args, "no_abgeordnetenwatch", False):
        used.append("--no-abgeordnetenwatch")
    config_paths = [root / "features.json", root / "features.local.json"]
    if getattr(args, "features_file", None):
        config_paths.append(Path(args.features_file))
    for path in config_paths:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, list) or (isinstance(payload, dict) and {"features", "enable", "disable"}.intersection(payload)):
            used.append(path.name)
    if used:
        print(
            "warning: "
            + ", ".join(used)
            + " is deprecated and will be removed in 0.6.0. "
            "Public sections are fixed; use --enrich for optional acquisition, "
            "--summary-mode for AI generation, or --include-dev-view for developer output.",
            file=sys.stderr,
        )


# Capability introspection exits before touching the network or output tree.
def print_capability_table(selection: EnrichmentSelection) -> None:
    print("Feste öffentliche Bereiche")
    print("  Aktueller Puls, Sitzungen, Gesetze, Abgeordnete, Quellen")
    print("\nOptionale Datenerfassung")
    for enrichment_id, enrichment in ENRICHMENT_REGISTRY.items():
        state = "ausgewählt" if enrichment_id in selection else "nicht ausgewählt"
        print(f"  {enrichment_id:<14} {state:<20} {enrichment.rebuild_hint}")
    print("\nKI-Zusammenfassungen")
    print("  --summary-mode reuse|off|auto|required (Standard: reuse)")
    print("\nEntwicklung")
    print("  --include-dev-view (nur mit separatem --output-dir)")


def print_effective_config(selection: EnrichmentSelection, args: argparse.Namespace) -> None:
    print("Effective operator configuration (no network or writes)")
    print(f"summary_mode={getattr(args, 'summary_mode', 'reuse')} source=--summary-mode/default")
    print(f"include_dev_view={str(bool(getattr(args, 'include_dev_view', False))).lower()} source=--include-dev-view/default")
    if not selection.ids:
        print("enrichments=(none) source=resolved configuration")
    else:
        for enrichment_id in sorted(selection.ids):
            winners = [source for action, value, source in selection.provenance if value == enrichment_id and action in {"add", "replace"}]
            print(f"enrichment={enrichment_id} source={winners[-1] if winners else 'default'}")
    for action, enrichment_id, source in selection.provenance:
        print(f"operation={action} enrichment={enrichment_id} source={source}")


# ---------------------------------------------------------------------------
# Command line and entry point
# ---------------------------------------------------------------------------


_ABSOLUTE_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://")


# --data-base-url only decides where download links point. Absolute only for
# https://, http:// or a leading /; any other scheme:// is a build-time error
# (F3.1) rather than a silently broken or unsafe href.
def resolve_data_base_url(value: str) -> str:
    if value.startswith("https://") or value.startswith("http://") or value.startswith("/"):
        return value if value.endswith("/") else value + "/"
    if _ABSOLUTE_SCHEME_RE.match(value):
        raise ValueError(
            f"--data-base-url {value!r} uses an unsupported scheme; use https://, http://, a leading / or a relative path"
        )
    return value if value.endswith("/") else value + "/"


def is_url(value: str) -> bool:
    return bool(re.match(r"^https?://", value))


# The "Fragen und Fehler" footer link may come from a --data-manifest that
# the operator fetched from elsewhere, so it gets the same scheme discipline
# as --data-base-url: https://, http://, mailto: or a site-relative path.
_ISSUES_URL_RE = re.compile(r"^(https?://|mailto:|/)")


def safe_issues_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    return value if _ISSUES_URL_RE.match(value) else None


# What the page and render_site read from a manifest. A --data-manifest
# override is operator input, so a wrong-shaped file fails here with one
# named error instead of a KeyError somewhere inside render_site().
_MANIFEST_REQUIRED: tuple[tuple[str, type | tuple[type, ...]], ...] = (
    ("export_format", int),
    ("generated_at", str),
    ("generation", str),
    ("files", list),
    ("protocols", dict),
    ("tables", list),
    ("relationships", int),
    ("total_rows", int),
    ("votes", dict),
    ("recipes", list),
    ("coverage", dict),
)


def validate_manifest(manifest: Any, source: str) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise RuntimeError(f"error: --data-manifest {source} is not a JSON object")
    problems = []
    for key, expected in _MANIFEST_REQUIRED:
        if key not in manifest:
            problems.append(f"missing {key}")
        elif not isinstance(manifest[key], expected) or (expected is int and isinstance(manifest[key], bool)):
            problems.append(f"{key} is not {getattr(expected, '__name__', expected)}")
    files = manifest.get("files")
    if isinstance(files, list):
        if not files:
            problems.append("files is empty")
        for index, entry in enumerate(files):
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not isinstance(entry.get("bytes"), int):
                problems.append(f"files[{index}] needs name and bytes")
                break
            if "/" in entry["name"] or "\\" in entry["name"] or entry["name"] in ("", ".", ".."):
                problems.append(f"files[{index}].name {entry['name']!r} is not a plain file name")
                break
        if files and isinstance(files[0], dict) and not all(k in files[0] for k in ("unpacked_bytes", "sha256")):
            problems.append("files[0] needs unpacked_bytes and sha256")
    generation = manifest.get("generation")
    if isinstance(generation, str) and not re.match(r"^g-[0-9a-f]{12}$", generation):
        problems.append(f"generation {generation!r} is not g-<12 hex>")
    for key in ("protocols", "votes", "coverage"):
        value = manifest.get(key)
        if isinstance(value, dict) and key == "protocols" and "count" not in value:
            problems.append("protocols.count missing")
        if isinstance(value, dict) and key == "votes" and not all(k in value for k in ("count", "members")):
            problems.append("votes.count/members missing")
        if isinstance(value, dict) and key == "coverage" and not all(
            k in value for k in ("catalog_count", "dossier_count", "bausteine")
        ):
            problems.append("coverage.catalog_count/dossier_count/bausteine missing")
    if isinstance(manifest.get("tables"), list) and not all(
        isinstance(t, dict) and isinstance(t.get("name"), str) and isinstance(t.get("columns"), list) for t in manifest["tables"]
    ):
        problems.append("tables[] entries need name and columns")
    if isinstance(manifest.get("recipes"), list) and not all(
        isinstance(r, dict) and isinstance(r.get("id"), str) and isinstance(r.get("rows"), list) for r in manifest["recipes"]
    ):
        problems.append("recipes[] entries need id and rows")
    if problems:
        raise RuntimeError(f"error: --data-manifest {source} is not a usable Daten manifest: " + "; ".join(problems))
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-key", help="DIP API key. Prefer DIP_API_KEY for local use.")
    parser.add_argument("--enable", metavar="ID", action="append", default=[], help="Deprecated compatibility alias; use --enrich.")
    parser.add_argument("--disable", metavar="ID", action="append", default=[], help="Deprecated compatibility veto for update enrichments.")
    parser.add_argument("--features", help="Deprecated compatibility selection; published website areas are always included.")
    parser.add_argument("--features-file", type=Path, help="Enrichment JSON file; legacy feature keys are deprecated.")
    parser.add_argument("--list-features", action="store_true", help="Deprecated alias for --list-capabilities.")
    parser.add_argument(
        "--list-capabilities",
        action="store_true",
        help="List fixed public areas, optional acquisitions, summary modes, and developer output; then exit.",
    )
    parser.add_argument(
        "--explain-config",
        action="store_true",
        help="Print effective operator configuration with provenance; then exit without network access or writes.",
    )
    parser.add_argument(
        "--enrich",
        metavar="ID",
        action="append",
        default=[],
        help="Update-time data enrichment: votes, aw-profiles, mp-roster, or all; repeatable.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Number of recent Bundestag protocols to include in the catalog. Use 0 for every available BT protocol.",
    )
    parser.add_argument(
        "--detail-limit",
        type=int,
        default=5,
        help="Number of fetched protocols to enrich into detailed dossier pages. Use 0 for every fetched protocol, or -1 for none.",
    )
    parser.add_argument(
        "--document-number",
        action="append",
        default=[],
        help="Specific protocol document number to include, e.g. 21/84. Can be repeated.",
    )
    parser.add_argument(
        "--dossier-document-number",
        action="append",
        default=[],
        help=(
            "Specific protocol document number to generate or regenerate as a dossier "
            "without restricting the catalog. Can be repeated."
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=Path(".context/dip-pulse-site"))
    parser.add_argument(
        "--include-dev-view",
        action="store_true",
        help="Include developer-only dossier payloads. Requires a non-public output directory.",
    )
    parser.add_argument(
        "--validate-publication",
        type=Path,
        metavar="DIR",
        help="Validate an existing ordinary publication directory and exit without network access or writes.",
    )
    parser.add_argument(
        "--today",
        type=parse_iso_date_arg,
        default=None,
        help=(
            "Build date for puls.html (YYYY-MM-DD). Default: SOURCE_DATE_EPOCH (UTC) when set, "
            "else the current date. Pin it for reproducible builds."
        ),
    )
    parser.add_argument(
        "--week",
        type=parse_iso_week_arg,
        default=None,
        help="Sitting week for puls.html as ISO YYYY-WW (e.g. 2026-24). Default: the newest dated week.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Render the site only from cached files in OUTPUT_DIR/data. "
            "No DIP, XML, roll-call, abgeordnetenwatch, or LLM API requests are made."
        ),
    )
    parser.add_argument(
        "--database-path",
        type=Path,
        help="SQLite graph store path. Defaults to OUTPUT_DIR/data/bundestag-pulse.sqlite.",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Skip writing the SQLite graph store.",
    )
    parser.add_argument(
        "--preserve-existing-dossiers",
        action="store_true",
        help="Load existing dossier JSON files from OUTPUT_DIR/data and keep them visible in the generated catalog.",
    )
    parser.add_argument(
        "--person-limit",
        type=int,
        default=0,
        help="Number of distinct person records to fetch for each detailed dossier. Use 0 for all seen person records.",
    )
    parser.add_argument(
        "--summary-mode",
        choices=("reuse", "auto", "required", "off"),
        default="reuse",
        help=(
            "How to handle per-TOP LLM summaries. The default reuses existing summaries "
            "and does not call an LLM API. Use auto or required to regenerate them."
        ),
    )
    parser.add_argument(
        "--refresh-summaries",
        dest="summary_mode",
        action="store_const",
        const="auto",
        help="Regenerate LLM summaries with the configured provider. Equivalent to --summary-mode auto.",
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
        "--summary-max-calls",
        type=int,
        default=25,
        help="Hard limit for LLM HTTP requests in auto/required mode (default 25; 0 disables calls).",
    )
    parser.add_argument(
        "--summary-timeout",
        type=float,
        default=60,
        help="Timeout in seconds for each summary-provider request (default 60).",
    )
    parser.add_argument(
        "--vote-scan-pages",
        type=int,
        default=None,
        help="Roll-call list pages per sitting (default 30 with --enrich votes, otherwise 0).",
    )
    parser.add_argument(
        "--roll-call-list-id",
        help=(
            "Bundestag roll-call vote filterlist id. "
            f"Defaults to {dip.ROLL_CALL_LIST_ID_ENV} or {dip.DEFAULT_ROLL_CALL_LIST_ID}."
        ),
    )
    parser.add_argument("--sleep", type=float, default=0.0, help="Optional delay between DIP API requests.")
    parser.add_argument(
        "--no-abgeordnetenwatch",
        action="store_true",
        help="Deprecated compatibility veto for --enrich aw-profiles.",
    )
    parser.add_argument(
        "--abgeordnetenwatch-cache",
        type=Path,
        help="Cache file for resolved abgeordnetenwatch profiles. Defaults to OUTPUT_DIR/data/abgeordnetenwatch-cache.json.",
    )
    parser.add_argument(
        "--abgeordnetenwatch-sleep",
        type=float,
        default=None,
        help="Minimum delay in seconds between abgeordnetenwatch API requests (default 0.5 to stay under its rate limit).",
    )
    parser.add_argument(
        "--roster-wahlperiode",
        type=int,
        default=21,
        help="Legislative period whose full MdB roster is fetched from DIP /person for the Abgeordnete pages (default 21).",
    )
    parser.add_argument(
        "--protocol-wahlperiode",
        type=int,
        default=21,
        help=(
            "Legislative period used to narrow limited protocol catalog fetches "
            "(default 21; use 0 to query all periods before applying --limit)."
        ),
    )
    parser.add_argument(
        "--no-roster",
        action="store_true",
        help="Deprecated compatibility veto for --enrich mp-roster.",
    )
    parser.add_argument(
        "--data-base-url",
        default=None,
        help=(
            "Base URL the Daten page's download links are built from. Defaults to "
            "data/exports/ (or $BUNDESTAG_PULSE_DATA_BASE_URL); absolute only for "
            "https://, http:// or a leading /."
        ),
    )
    parser.add_argument(
        "--data-manifest",
        default=None,
        help=(
            "Path or URL of the datenstand.json the Daten page renders from. Defaults to "
            "OUTPUT_DIR/data/exports/datenstand.json (or $BUNDESTAG_PULSE_DATA_MANIFEST). "
            "A URL is an explicit opt-in fetch and is rejected under --offline. While an override is "
            "given the local export is skipped unless --force-export is passed."
        ),
    )
    parser.add_argument(
        "--force-export",
        action="store_true",
        help="Re-run the Daten export even when its inputs are unchanged, or when --data-manifest would skip it.",
    )
    parser.add_argument(
        "--data-license",
        default=None,
        help="Licence string recorded in the Daten manifest (or $BUNDESTAG_PULSE_DATA_LICENSE).",
    )
    parser.add_argument(
        "--data-issues-url",
        default=None,
        help="Optional URL for a 'Fragen und Fehler' link on the Daten page (or $BUNDESTAG_PULSE_DATA_ISSUES_URL); https://, http://, mailto: or a leading / only.",
    )
    args = parser.parse_args()
    if args.force_export and args.no_persist:
        parser.error("--force-export cannot be combined with --no-persist: there is no store to export")
    if args.offline and args.data_manifest and is_url(args.data_manifest):
        parser.error(f"--offline cannot fetch --data-manifest {args.data_manifest} over the network; pass a local path")
    if args.no_persist and args.data_base_url:
        print(
            "warning: --data-base-url has no effect with --no-persist (no store, no download links)",
            file=sys.stderr,
        )
    return args


# CLI > env > default, read in the layer that actually runs the build (not in
# parse_args itself), per the DX addendum. getattr() throughout: main() must
# keep working against the pre-existing test stub that mocks parse_args() with
# a bare SimpleNamespace lacking these attributes.
def resolve_data_export_options(args: argparse.Namespace) -> tuple[str, str | None, str, str | None]:
    base_url_raw = (
        getattr(args, "data_base_url", None) or os.environ.get("BUNDESTAG_PULSE_DATA_BASE_URL") or "data/exports/"
    )
    manifest_raw = getattr(args, "data_manifest", None) or os.environ.get("BUNDESTAG_PULSE_DATA_MANIFEST")
    license_text = getattr(args, "data_license", None) or os.environ.get("BUNDESTAG_PULSE_DATA_LICENSE") or ""
    issues_url = getattr(args, "data_issues_url", None) or os.environ.get("BUNDESTAG_PULSE_DATA_ISSUES_URL")
    issues_url = (issues_url or "").strip() or None
    if issues_url and safe_issues_url(issues_url) is None:
        raise ValueError(f"--data-issues-url {issues_url!r} must start with https://, http://, mailto: or /")
    return base_url_raw, manifest_raw, license_text, issues_url


def resolve_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


# D1A/D3A: the Fakt der Woche engine sits between the finalised store and the
# export. It runs on every build, online and --offline, computes every fact in
# memory and writes the three tables only when they changed - so an --offline
# rebuild of an unchanged store leaves the store's mtime alone and the export's
# skip rule still holds. A metric whose SQL raises a FactsError aborts the
# build naming the metric (FactsError is a RuntimeError, which main() reports).
def run_facts_engine(database_path: Path, entries: list[dict[str, Any]]) -> dict[str, Any]:
    store = pulse_store.connect(database_path)
    try:
        pulse_store.initialize(store)
        built = {"votes"} if store.execute("SELECT COUNT(*) FROM votes").fetchone()[0] else set()
        return facts.compute_and_store(
            store,
            facts.ALL_REGISTRY,
            facts.completeness_from_entries(entries),
            built=built,
        )
    finally:
        store.close()


# Runs the export step (unless --no-persist, or the store does not exist) and
# resolves which manifest the Daten page renders from: the manifest this build
# just wrote, or an explicit --data-manifest override (local file or, outside
# --offline, a URL). Bills are collected once here for the coverage numbers
# and link resolution; render_site's own bills component re-collects them to
# write the actual bill pages.
def run_data_pipeline(
    *,
    args: argparse.Namespace,
    output_dir: Path,
    database_path: Path,
    entries: list[dict[str, Any]],
    protocols: list[dict[str, Any]],
    abg_mps: list[dict[str, Any]],
    mp_lookup: dict[str, int],
    canonical_by_mp_id: dict[int, int],
) -> tuple[dict[str, Any] | None, str | None, set[str], str, bool]:
    base_url_raw, manifest_raw, license_text, issues_url = resolve_data_export_options(args)
    data_base_url = resolve_data_base_url(base_url_raw)
    bills = collect_bill_pages(entries)
    bill_slugs = {bill["slug"] for bill in bills}
    readiness = derive_feature_readiness(entries, abg_mps, bill_count=len(bills))

    # Before the export, so the three facts tables are part of the store the
    # export copies and hashes.
    if not args.no_persist and database_path.exists():
        run_facts_engine(database_path, entries)

    manifest: dict[str, Any] | None = None
    data_export_error: str | None = None
    force_export = bool(getattr(args, "force_export", False))
    # A --data-manifest override replaces whatever this build would export, so
    # the export only runs when its result is used or explicitly forced.
    if manifest_raw and not force_export:
        print("export: skipped (--data-manifest overrides the manifest; pass --force-export to export anyway)", file=sys.stderr)
    elif not args.no_persist and database_path.exists():
        exports_dir = output_dir / "data" / "exports"
        try:
            manifest = export_distribution_data(
                database_path,
                exports_dir,
                canonical_by_mp_id=canonical_by_mp_id,
                mp_lookup=mp_lookup,
                readiness=readiness,
                catalog_count=len(protocols),
                dossier_count=len(entries),
                license_text=license_text,
                issues_url=issues_url,
                commit=resolve_commit(),
                force=force_export,
            )
        except DataExportUnavailable as exc:
            data_export_error = str(exc)
            print(f"error: {exc}", file=sys.stderr)

    is_remote_manifest = False
    if manifest_raw:
        if is_url(manifest_raw):
            manifest = validate_manifest(load_remote_manifest(manifest_raw), manifest_raw)
            is_remote_manifest = True
        else:
            manifest = validate_manifest(json.loads(Path(manifest_raw).read_text(encoding="utf-8")), manifest_raw)
    return manifest, data_export_error, bill_slugs, data_base_url, is_remote_manifest


# Entry point: run the whole build and print the path of the generated
# index.html on stdout (everything else this script says goes to stderr).
#
# Two paths through this function:
#   --offline -> render from the cached JSON in OUTPUT_DIR/data only, no network
#   default   -> fetch from DIP, build dossiers, persist, then render
def main() -> int:
    # Reads .env so DIP_API_KEY and the LLM keys can live outside the shell.
    dip.load_local_env()
    args = parse_args()
    args.include_dev_view = bool(getattr(args, "include_dev_view", False))
    args.summary_mode = getattr(args, "summary_mode", "reuse")

    if getattr(args, "validate_publication", None):
        try:
            publication.validate_publication_directory(args.validate_publication)
        except publication.PublicationStateError as exc:
            print(f"ERROR [invalid-publication]: {exc}", file=sys.stderr)
            return 1
        print(f"validated: {args.validate_publication}")
        return 0

    # Resolve update-time enrichments before doing any network work.
    root = Path(__file__).resolve().parents[1]
    try:
        enrichments = resolve_from_args(args, root=root)
    except FeatureError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if getattr(args, "list_features", False):
        print("warning: --list-features is deprecated; use --list-capabilities. Removal: 0.6.0.", file=sys.stderr)
        print_capability_table(enrichments)
        return 0
    if getattr(args, "list_capabilities", False):
        print_capability_table(enrichments)
        return 0
    if getattr(args, "explain_config", False):
        warn_deprecated_feature_configuration(args, root=root)
        print_effective_config(enrichments, args)
        return 0
    warn_deprecated_feature_configuration(args, root=root)
    apply_to_args(args, enrichments)
    features = publication_selection()
    if args.include_dev_view and args.output_dir.resolve() == Path(".context/dip-pulse-site").resolve():
        print(
            "ERROR [unsafe-dev-output]: --include-dev-view cannot write to the ordinary publication directory. "
            "Fix: add --output-dir .context/dip-pulse-site-dev. Docs: README.md#developer-output",
            file=sys.stderr,
        )
        return 2
    # The puls.html clock is resolved once, before any file is written, so a bad
    # SOURCE_DATE_EPOCH fails here and both render paths share one value. Tests
    # stub parse_args with a bare namespace, hence getattr.
    pulse_week = getattr(args, "week", None)
    try:
        build_today = resolve_today(getattr(args, "today", None))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    # Import addon modules only after this module and the renderer are fully loaded.
    components = {
        component.feature.id: component
        for component in feature_loader.load(features, include_dev_view=args.include_dev_view)
    }

    # Every visitor-facing output directory exists in every publication.
    output_dir = args.output_dir
    (output_dir / "protocols").mkdir(parents=True, exist_ok=True)
    (output_dir / "data").mkdir(parents=True, exist_ok=True)
    if "bills" in features:
        (output_dir / "bills").mkdir(parents=True, exist_ok=True)
    if "mp-pages" in features:
        (output_dir / "abgeordnete").mkdir(parents=True, exist_ok=True)
    if "facts" in features:
        (output_dir / "fakt").mkdir(parents=True, exist_ok=True)
    database_path = args.database_path or output_dir / "data" / "bundestag-pulse.sqlite"

    # --- offline render ----------------------------------------------------
    # Re-render every page from what is already on disk. Useful for iterating on
    # the HTML/CSS in this file without spending API calls or waiting on DIP.
    if args.offline:
        protocols = load_cached_protocols(output_dir)
        if not protocols:
            print(
                f"error: No cached protocols found in {output_dir / 'data'}. "
                "Run an online update first.",
                file=sys.stderr,
            )
            return 1

        abg_mps: list[dict[str, Any]] = []
        mp_lookup: dict[str, int] = {}
        canonical_by_mp_id: dict[int, int] = {}
        # The MP pages are read out of the existing store; the roster fetch is
        # skipped because it would need the network.
        if not args.no_persist and database_path.exists():
            store = pulse_store.connect(database_path)
            try:
                pulse_store.initialize(store)
                if "mp-pages" in features:
                    component_context = {
                        "selection": features,
                        "collect_abgeordnete": collect_abgeordnete,
                    }
                    components["mp-pages"].after_persist(store, component_context)
                    abg_mps = component_context["abg_mps"]
                    mp_lookup = component_context["mp_lookup"]
                    canonical_by_mp_id = component_context.get("canonical_by_mp_id", {})
            finally:
                store.close()

        # --week must name a week with a cached dossier (the catalog lists every
        # protocol back to 1949; only dossiers can be rendered). Check it before
        # any dossier page is regenerated so a typo leaves the output untouched.
        cached_entries = load_existing_detail_entries(output_dir, protocols)
        if reject_unknown_week(pulse_week, [entry["report"].get("protocol") or {} for entry in cached_entries]):
            return 2

        entries = rebuild_cached_detail_pages(
            output_dir,
            protocols,
            mp_lookup,
            features,
            cached_entries=cached_entries,
            include_dev_view=args.include_dev_view,
        )
        try:
            manifest, data_export_error, bill_slugs, data_base_url, is_remote_manifest = run_data_pipeline(
                args=args,
                output_dir=output_dir,
                database_path=database_path,
                entries=entries,
                protocols=protocols,
                abg_mps=abg_mps,
                mp_lookup=mp_lookup,
                canonical_by_mp_id=canonical_by_mp_id,
            )
        except (RuntimeError, OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        # Dossier pages are regenerated from the cached JSON reports, then the
        # rest of the site is rendered around them.
        index_path = render_site(
            output_dir=output_dir,
            database_path=database_path,
            no_persist=args.no_persist,
            protocols=protocols,
            entries=entries,
            abg_mps=abg_mps,
            mp_lookup=mp_lookup,
            features=features,
            enrichments=enrichments,
            summary_mode=args.summary_mode,
            acquisition_attempted=False,
            include_dev_view=args.include_dev_view,
            today=build_today,
            week=pulse_week,
            manifest=manifest,
            data_base_url=data_base_url,
            data_export_error=data_export_error,
            is_remote_manifest=is_remote_manifest,
            bill_slugs=bill_slugs,
        )
        print(f"offline: rendered {len(entries)} cached dossiers", file=sys.stderr)
        print(index_path)
        return 0

    # --- online build ------------------------------------------------------
    api_key = args.api_key or os.environ.get("DIP_API_KEY")
    if not api_key:
        print("error: Provide a DIP API key via --api-key or DIP_API_KEY.", file=sys.stderr)
        return 1

    # The abgeordnetenwatch resolver caches every lookup to disk and throttles
    # itself, because that API rate-limits aggressively.
    profile_resolver = None
    if not args.no_abgeordnetenwatch:
        cache_path = args.abgeordnetenwatch_cache or output_dir / "data" / "abgeordnetenwatch-cache.json"
        profile_resolver = aw.AbgeordnetenwatchResolver(
            cache_path=cache_path,
            sleep_seconds=args.abgeordnetenwatch_sleep,
        )

    client = dip.ApiClient(api_key=api_key, sleep_seconds=args.sleep)
    try:
        # Step 1: the catalog, then the subset of it that gets a dossier.
        # --dossier-document-number can add sittings to the dossier list without
        # changing the catalog; the second protocols_for_detail_pages() call
        # re-filters that combined list for a usable XML URL.
        protocol_wahlperiode = args.protocol_wahlperiode if args.protocol_wahlperiode > 0 else None
        protocols = fetch_protocols(client, args.limit, args.document_number, protocol_wahlperiode)
        detail_limit = None if args.document_number else args.detail_limit
        detail_protocols = protocols_for_detail_pages(protocols, detail_limit)
        protocols, detail_protocols = add_explicit_dossier_protocols(
            client,
            protocols,
            detail_protocols,
            args.dossier_document_number,
        )
        detail_protocols = protocols_for_detail_pages(detail_protocols, None)
        # With --preserve-existing-dossiers, dossiers from earlier builds stay
        # visible in the catalog even when this run only regenerates a few.
        existing_entries = (
            load_existing_detail_entries(output_dir, protocols) if args.preserve_existing_dossiers else []
        )
        # --week must name a week this build will actually hold; check it against
        # the dossier catalog (plus the preserved dossiers that stay in the
        # archive) now, before any dossier is written.
        if reject_unknown_week(
            pulse_week,
            [*detail_protocols, *(entry["report"].get("protocol") or {} for entry in existing_entries)],
        ):
            return 2
        abg_mps: list[dict[str, Any]] = []
        mp_lookup: dict[str, int] = {}
        canonical_by_mp_id: dict[int, int] = {}
        try:
            # Step 2: build the selected dossiers. Each one writes its own JSON
            # report and HTML page as a side effect.
            generated_entries = build_dossiers_with_progress(
                detail_protocols,
                load_existing=lambda protocol: load_existing_report(output_dir, protocol),
                build_dossier=lambda protocol, existing_report: write_report_and_page(
                    protocol=protocol,
                    output_dir=output_dir,
                    api_key=api_key,
                    sleep=args.sleep,
                    person_limit=args.person_limit,
                    vote_scan_pages=args.vote_scan_pages,
                    roll_call_list_id=args.roll_call_list_id,
                    summary_mode=args.summary_mode,
                    summary_provider=args.summary_provider,
                    anthropic_api_key=args.anthropic_api_key,
                    gemini_api_key=args.gemini_api_key,
                    summary_model=args.summary_model,
                    summary_max_calls=args.summary_max_calls,
                    summary_timeout=args.summary_timeout,
                    existing_report=existing_report,
                    profile_resolver=profile_resolver,
                    features=features,
                    include_dev_view=args.include_dev_view,
                ),
            )
            # Step 3: persist everything into a freshly rebuilt SQLite store,
            # then read it back for the MP pages. The dossier pages are written
            # a second time afterwards because mp_lookup only exists now, and it
            # is what makes speaker names in them link to MP profiles.
            entries = merge_detail_entries(protocols, existing_entries, generated_entries)
            # A dossier of the requested week can still have failed to build;
            # say so instead of letting the renderer's ValueError escape.
            if reject_unknown_week(
                pulse_week,
                [entry["report"].get("protocol") or {} for entry in entries],
                note=" (Dossiers wurden bereits geschrieben, puls.html nicht)",
            ):
                return 2
            if not args.no_persist:
                rebuild_database_from_entries(
                    database_path,
                    entries,
                    preserve_roster="mp-roster" not in enrichments,
                )
                store = pulse_store.connect(database_path)
                try:
                    pulse_store.initialize(store)
                    if "mp-pages" in features:
                        component_context = {
                            "selection": enrichments,
                            "client": client,
                            "roster_wahlperiode": args.roster_wahlperiode,
                            "profile_resolver": profile_resolver,
                            "ingest_mdb_roster": ingest_mdb_roster,
                            "collect_abgeordnete": collect_abgeordnete,
                        }
                        components["mp-pages"].after_persist(store, component_context)
                        roster_stats = component_context.get("roster_stats")
                        if roster_stats:
                            print(
                                f"roster: {roster_stats['mdb']} MdBs of {roster_stats['fetched']} persons "
                                f"(WP{args.roster_wahlperiode}), {roster_stats['enriched']} enriched",
                                file=sys.stderr,
                            )
                        abg_mps = component_context["abg_mps"]
                        mp_lookup = component_context["mp_lookup"]
                        canonical_by_mp_id = component_context.get("canonical_by_mp_id", {})
                finally:
                    store.close()
                entries = [
                    write_report_files(
                        entry["report"],
                        output_dir,
                        mp_lookup,
                        features,
                        include_dev_view=args.include_dev_view,
                    )
                    for entry in entries
                ]
        # Always flush the profile cache and report resolver statistics, even
        # when the build failed partway through - the cache is what keeps the
        # next run from re-hitting the rate-limited API.
        finally:
            if profile_resolver is not None:
                profile_resolver.save()
                stats = profile_resolver.stats
                print(
                    "abgeordnetenwatch: "
                    f"{stats['ext_id']} via id, {stats['name']} via name, "
                    f"{stats['unresolved']} unresolved "
                    f"({stats['api_calls']} API calls, {stats['throttled']} retried, "
                    f"{stats['errors']} errors)",
                    file=sys.stderr,
                )
    except dip.DipError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # Step 4: export the Daten distribution files, then render the rest of the
    # site around the dossiers.
    try:
        manifest, data_export_error, bill_slugs, data_base_url, is_remote_manifest = run_data_pipeline(
            args=args,
            output_dir=output_dir,
            database_path=database_path,
            entries=entries,
            protocols=protocols,
            abg_mps=abg_mps,
            mp_lookup=mp_lookup,
            canonical_by_mp_id=canonical_by_mp_id,
        )
    except (RuntimeError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    index_path = render_site(
        output_dir=output_dir,
        database_path=database_path,
        no_persist=args.no_persist,
        protocols=protocols,
        entries=entries,
        abg_mps=abg_mps,
        mp_lookup=mp_lookup,
        features=features,
        enrichments=enrichments,
        summary_mode=args.summary_mode,
        acquisition_attempted=True,
        include_dev_view=args.include_dev_view,
        today=build_today,
        week=pulse_week,
        manifest=manifest,
        data_base_url=data_base_url,
        data_export_error=data_export_error,
        is_remote_manifest=is_remote_manifest,
        bill_slugs=bill_slugs,
    )
    print(index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
