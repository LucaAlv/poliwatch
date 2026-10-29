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
#      -> ``rebuild_database_from_entries``: staged under the writer lock, with the
#      optional roster ingest, ``person_registry.reconcile``, the facts engine and
#      the integrity checks (schema and writes live in ``persist_dip_pulse_store``).
#   5. Read the store back to assemble the MP ("Abgeordnete") data
#      -> ``collect_abgeordnete``.
#   6. Export a distribution copy of the store, its CSVs and the executed SQL
#      recipes for the Daten page -> ``export_distribution_data``, writing
#      ``data/exports/datenstand.json`` and ``data/exports/g-<hash>/``.
#   7. Render every remaining page of the site -> ``render_site``.
#
# Which code writes which part of the website:
#
#   index.html           ``render_landing_page``     explanatory home page
#   puls.html            ``render_front_page``       "Wochenübersicht": week radar + Wochenvergleich
#   overview.html        ``render_overview``         dossier cards + catalog teaser
#   api-sitzungen.html   ``render_catalog_page``     searchable full DIP catalog
#   sources.html         ``render_sources_page``     sources and method transparency
#   database.html        ``render_database_page``    Daten: downloads, Datenstand, Rezepte, Schema
#   settings.html        ``render_settings_page``    0.5.x compatibility notice
#   protocols/*.html     ``render_dip_pulse_html``   per-sitting dossier (own module)
#   bills/index.html     ``render_bills_index``      Gesetzesvorhaben list with search
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
import glob
import hashlib
import io
import json
import os
import shlex
import re
import shutil
import sqlite3
import subprocess
import stat as stat_module
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request
from urllib.parse import urlparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from dataclasses import dataclass
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
import derive
import speech_kinds
import publication_state as publication
import facts
import politikfelder
import person_registry as registry
from stable_ids import (
    KEY_VERSION, canonical_dip_person_id, key_prefix, roster_occurrence_id, source_index, speech_occurrence_id,
    speech_rede_id,
)
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
from features import votes as votes_feature


# Human-readable one-liners for every table in the SQLite store. Used only by the
# Daten page (database.html) to caption each schema row; a table that is missing
# here falls back to a generic sentence in render_daten_schema().
DATABASE_TABLE_DESCRIPTIONS = {
    "schema_migrations": "Interne Versionsmarke des SQLite-Schemas.",
    "parties": "Zusammenschlüsse (Fraktionen und Gruppen, etwa CDU/CSU oder Gruppe BSW) und fraktionslos für Abgeordnete ohne Zusammenschluss.",
    "mps": "Personen, die in Reden, DIP-Personendaten oder namentlichen Abstimmungen auftauchen.",
    "protocols": "Plenarprotokolle mit Dokumentnummer, Datum und offiziellen XML/PDF-Links.",
    "agenda_items": "Tagesordnungspunkte je Protokoll. Sie bilden die Themen-Grenze der aktuellen Pulse-Ansicht.",
    "proceedings": "DIP-Vorgänge, etwa Gesetzgebungsverfahren, die mit Tagesordnungspunkten oder namentlichen Abstimmungen verbunden werden; abstract ist die DIP-Zusammenfassung als Klartext (HTML entfernt, Leerraum normalisiert).",
    "proceeding_positions": "DIP-Vorgangspositionen mit Dokument- und Seitenangaben aus der offiziellen API.",
    "documents": "Drucksachen und andere Dokumente, die aus XML, DIP oder Abstimmungen referenziert werden.",
    "agenda_item_documents": "Verknüpfung zwischen Tagesordnungspunkten und Dokumenten, inklusive Quelle xml/api.",
    "speeches": "Extrahierte Reden mit Redner, Seite, Textumfang (nur die Worte des Redners), Snippet, optionalem Volltext und der Sprechrolle (bundesregierung, bundesrat, weitere). Nur Reden: Kurzinterventionen, Erwiderungen sowie Fragen und Antworten stehen in contributions.",
    "speech_rule_inputs": "Tatsächlich persistierte Zählregel je Plenarprotokoll; fehlende oder alte Version verlangt einen expliziten XML-Replay.",
    "contributions": "Beiträge, die keine Rede sind: Zwischenfrage, schriftlicher Beitrag (zu_protokoll), Kurzintervention, Erwiderung, Frage und Antwort der Befragung der Bundesregierung und der Fragestunde, je mit kind, Redner, Textumfang und Volltext. Ohne Seitenangabe bei Fragestunde-Beiträgen; Ein vorgelesener Fragesteller erhält mp_id nur bei eindeutiger Quellevidenz.",
    "votes": "Namentliche Abstimmungen mit Summen, Bundestag-Detailseite und optionalem debate_url zum zugeordneten Bundestagsbericht (aus der Debatte-Zuordnung auf bundestag.de ermittelt); context_state sagt, ob ihr DIP-Vorgang ermittelt wurde (resolved), keiner zu ermitteln ist (none) oder die Angaben nicht abgerufen wurden (not_fetched: ein ermittelter Vorgang oder eine Drucksache der Abstimmung fehlt im Cache; bekannte Zeilen stehen trotzdem in vote_proceedings).",
    "agenda_item_votes": "Zuordnung von namentlichen Abstimmungen zu Tagesordnungspunkten.",
    "vote_documents": "Drucksachen, die bei namentlichen Abstimmungen referenziert wurden.",
    "vote_proceedings": "DIP-Vorgänge, um die es bei einer namentlichen Abstimmung geht, mit Rang; abgeleitet aus ihren Drucksachen, die höchstens zwei Vorgänge nennen, eingeschränkt auf die Vorgänge ihres Tagesordnungspunkts, wo sie sich überschneiden. Keine Zeile oder unvollständig: siehe votes.context_state (not_fetched: ein Vorgang oder eine Drucksache fehlt im Cache; bekannte Zeilen stehen trotzdem hier).",
    "agenda_item_politikfelder": "Politikfelder (1 bis 3 von 13, sonst untagged) je Tagesordnungspunkt, abgeleitet aus dem DIP-Sachgebiet der Vorgänge des Tagesordnungspunkts (siehe proceedings.sachgebiet), bei Bedarf über seine Drucksachen; Rang und Herkunft stehen in der Zeile.",
    "vote_politikfelder": "Politikfelder (1 bis 3 von 13, sonst untagged) je namentlicher Abstimmung, abgeleitet aus dem DIP-Sachgebiet ihrer Drucksachen oder ihrer Tagesordnungspunkte; Rang und Herkunft stehen in der Zeile.",
    "vote_fractions": "Summen je Zusammenschluss und namentlicher Abstimmung; leading_vote ist das Mehrheitsvotum, leer bei Gleichstand oder wenn niemand abgestimmt hat.",
    "vote_members": "Einzelne Stimmen von Abgeordneten je namentlicher Abstimmung.",
    "persons": "Dauerhafte Personenkennungen und Reihenfolge ihrer Vergabe.",
    "person_aliases": "Historische Personenkennungen und ihre gültigen Ziele.",
    "person_records": "Quellenidentitäten mit dauerhafter Personenzuordnung und Abgleichbelegen.",
    "person_bindings": "Dauerhafte Zuordnung einzelner Reden, Beiträge, MdB-Einträge und Abstimmungsmitglieder.",
    "mp_canonical": "Bildet jede mps-Zeile auf die konsolidierte Person ab. Nur in der Verteilkopie.",
    "datenstand": "Herkunft dieser Verteilkopie: Tag, Exportformat, Lizenz, Schema- und Quell-Prüfsumme. Nur in der Verteilkopie.",
    "fact_metrics": "Registrierte Kennzahlen der Rubrik Fakt der Woche mit SQL, Richtung, Aggregation und Mindesthistorie.",
    "facts": "Wöchentliche Beobachtung je Kennzahl mit Wert, Perzentil, Baseline und Veröffentlichungsstatus.",
    "fact_sources": "Belege je Fakt: Reden, Tagesordnungspunkte, Abstimmungen, Sitzungen oder Drucksachen, aus denen der Wert stammt.",
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
        label = f"BT-PlPr. {protocol_label(protocol)}"
        protocol_date = str(protocol.get("datum") or "").strip()
        if protocol_date:
            label = f"{label} from {protocol_date}"

        started = time.monotonic()
        print(f"[dossiers] [{index}/{total}] {action}: {label}.", file=sys.stderr, flush=True)
        try:
            entry = build_dossier(protocol, existing_report)
        except dip.DipError as exc:
            if exc.source_rejected:
                raise  # D4: no staged store may replace accepted data after source refusal.
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
    num_found: int | None = None
    while fetch_all or len(protocols) < limit:
        page = client.get_json("/plenarprotokoll", params)
        protocols.extend(page.get("documents") or [])
        if isinstance(page.get("numFound"), int) and not isinstance(page.get("numFound"), bool):
            num_found = page["numFound"]
        cursor = page.get("cursor")
        if not cursor or cursor == previous_cursor:
            break
        previous_cursor = cursor
        params["cursor"] = cursor
    unique_protocols = len({str(p.get("id") or p.get("dokumentnummer")) for p in protocols})
    if fetch_all and num_found is not None and unique_protocols < num_found:
        # The whole catalog is what completeness is judged against and what the
        # store keeps dossiers for: a short fetch must stop the build, not
        # become an "authoritative" catalog.
        raise dip.DipError(
            f"DIP returned {unique_protocols} of {num_found} protocols; the catalog is incomplete. "
            "Fix: run the update again."
        )
    return protocols if fetch_all else protocols[:limit]


# Which sittings of the catalog this run acquires. --document-number and
# --limit narrow the acquisition only: the catalog stays whole, because
# completeness is judged against everything DIP lists and the store keeps every
# cached dossier whatever this run refreshes.
def select_acquisition_protocols(
    catalog: list[dict[str, Any]],
    document_numbers: list[str],
    limit: int,
    wahlperiode: int | None,
) -> list[dict[str, Any]]:
    ordered = sorted(catalog, key=protocol_sort_key, reverse=True)
    if document_numbers:
        by_number = {normalized_document_number(protocol.get("dokumentnummer")): protocol for protocol in ordered}
        wanted = [normalized_document_number(number) for number in document_numbers]
        missing = [number for number in wanted if number not in by_number]
        if missing:
            raise dip.DipError(f"No BT Plenarprotokoll found for {', '.join(missing)}")
        return [protocol for protocol in ordered if normalized_document_number(protocol.get("dokumentnummer")) in wanted]
    if limit > 0:
        if wahlperiode:
            prefix = f"{wahlperiode}/"
            ordered = [
                protocol
                for protocol in ordered
                if normalized_document_number(protocol.get("dokumentnummer")).startswith(prefix)
            ]
        return ordered[:limit]
    return ordered


# --backfill-incomplete: the sittings a facts period is waiting for. A sitting
# counts when the catalog lists it and the cached dossiers do not cover it
# (missing), or when its report says votes or speeches are not fully acquired.
# Sittings DIP has published no XML for cannot be acquired yet and are
# returned separately so the caller can say so instead of failing on them.
_BUDGET_PAGES_RE = re.compile(r"scan_budget_exhausted after (\d+) pages")


def _structural_vote_gap(gap: dict[str, Any], scan_pages: int | None = None) -> bool:
    """A gap a rescan at the current settings reproduces exactly: votes the list
    shows that no agenda item claims (only a better match rule closes it), or a
    scan that ran out of pages at a budget no larger than the one asked for now.
    ``scan_pages`` is the budget the next acquisition would use."""
    reasons = gap["reasons"]
    if set(reasons) != {"votes"}:
        return False
    text = reasons["votes"]
    if text == "roll-call votes matched no TOP":
        return True
    listed = text[text.index("(") + 1 : text.rindex(")")].split(", ") if "(" in text and text.endswith(")") else []
    tokens = {token.split(" after ")[0] for token in listed}
    # Reproduced by a rescan whatever else is going on: the list shows votes no
    # TOP claims.
    if "unmatched_candidate" in tokens:
        return True
    if text == "votes partial (source_stale)":
        # Only while the list may still be catching up; after that a rescan can
        # settle it, so the backfill takes it again.
        day = str(gap.get("date") or "")[:10]
        try:
            age = (datetime.now(timezone.utc).date() - date.fromisoformat(day)).days
        except ValueError:
            return False
        return age <= dip.ROLL_CALL_LIST_LAG_DAYS
    used = _BUDGET_PAGES_RE.search(text)
    return bool(used) and bool(scan_pages) and scan_pages <= int(used.group(1))


def incomplete_sitting_protocols(
    entries: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
    *,
    votes: bool = True,
    scan_pages: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    stored = []
    for entry in entries:
        protocol = (entry.get("report") or {}).get("protocol") or {}
        stored.append(
            {
                "document_number": normalized_document_number(protocol.get("dokumentnummer")),
                "date": str(protocol.get("datum") or "")[:10],
            }
        )
    gaps = facts.sitting_gaps(
        stored, facts.completeness_from_entries(entries), facts.sitting_catalog(catalog, authoritative=True)
    )
    acquirable: list[dict[str, Any]] = []
    waiting: list[dict[str, Any]] = []
    vote_only: list[dict[str, Any]] = []
    structural: list[dict[str, Any]] = []
    for protocol in sorted(catalog, key=protocol_sort_key, reverse=True):
        gap = gaps.get(normalized_document_number(protocol.get("dokumentnummer")))
        if gap is None:
            continue
        if _structural_vote_gap(gap, scan_pages):
            structural.append(protocol)
        elif not votes and set(gap["reasons"]) == {"votes"}:
            # Votes are off, so re-acquiring this sitting would download it
            # again and leave it exactly as incomplete as it is.
            vote_only.append(protocol)
        else:
            (acquirable if protocol_xml_url(protocol) else waiting).append(protocol)
    return acquirable, waiting, vote_only, structural


def _first_numbers(numbers: list[str], limit: int = 3) -> str:
    shown = ", ".join(numbers[:limit])
    return f"{shown}, …" if len(numbers) > limit else shown


# What keeps facts periods from being complete, printed on every build that
# ran the engine: the periods, the sittings behind them, and the exact command
# that acquires them.
def format_incomplete_report(
    report: dict[str, Any],
    *,
    output_dir: Path,
    catalog_protocols: list[dict[str, Any]],
    vote_scan_pages: int,
    shown_periods: int = 6,
) -> list[str]:
    periods = report.get("incomplete_periods") or []
    gaps = report.get("sitting_gaps") or {}
    if not periods and not gaps:
        return []
    has_xml = {
        normalized_document_number(protocol.get("dokumentnummer")): bool(protocol_xml_url(protocol))
        for protocol in catalog_protocols
    }
    weeks = [period for period in periods if period["period_kind"] == "week"]
    months = [period for period in periods if period["period_kind"] == "month"]
    missing = [number for number, gap in gaps.items() if gap["reasons"].get("dossier") == "not_persisted"]
    waiting = [number for number in missing if not has_xml.get(number, True)]
    partial = {number: gap for number, gap in gaps.items() if "dossier" not in gap["reasons"]}
    redated = [number for number, gap in gaps.items() if gap["reasons"].get("dossier") == "date_changed"]
    # A scan that ran out of pages is only fixed by a wider scan, so the fix
    # below raises the budget and judges what it would reach at that budget.
    exhausted = any("scan_budget_exhausted" in reason for gap in partial.values() for reason in gap["reasons"].values())
    raised_pages = max(2 * vote_scan_pages, vote_scan_pages + 30) if exhausted and vote_scan_pages else vote_scan_pages
    structural = [number for number, gap in gaps.items() if _structural_vote_gap(gap, raised_pages)]
    no_xml = [number for number in gaps if not has_xml.get(number, True)]
    acquirable = [number for number in gaps if number not in no_xml and number not in structural]
    lines = [
        f"warning: [facts] {len(weeks)} weeks and {len(months)} months are incomplete: "
        "a Fakt needs every sitting DIP lists, fully acquired."
    ]
    if missing:
        lines.append(f"  {len(missing)} listed sittings are not in the store: {_first_numbers(missing, 12)}")
    if waiting:
        lines.append(f"  not acquirable yet (DIP has no XML for them): {', '.join(waiting)}")
    if structural:
        lines.append(
            f"  {len(structural)} sittings a backfill cannot fix now: roll-call votes no agenda item claims (they need "
            f"a better match rule), a scan budget already used, or a list "
            f"that may not have caught up yet ({_first_numbers(structural, 12)})"
        )
    if redated:
        lines.append(f"  DIP dates {len(redated)} stored sittings differently now: {_first_numbers(redated, 12)}")
    if partial:
        counts = Counter(
            f"{domain}: {reason}" for gap in partial.values() for domain, reason in sorted(gap["reasons"].items())
        )
        lines.append(f"  {len(partial)} sittings are in the store but not fully acquired:")
        lines.extend(f"    {label} ({count}×)" for label, count in counts.most_common())
    for label, group in (("weeks", weeks), ("months", months)):
        if not group:
            continue
        newest = sorted(group, key=lambda period: period["period_key"], reverse=True)[:shown_periods]
        rendered = []
        for period in newest:
            lost = [s["document_number"] for s in period["sittings"] if "dossier" in s["reasons"]]
            weak = [s["document_number"] for s in period["sittings"] if "dossier" not in s["reasons"]]
            detail = "; ".join(
                part
                for part in (
                    f"missing {_first_numbers(lost)}" if lost else "",
                    f"incomplete {_first_numbers(weak)}" if weak else "",
                )
                if part
            )
            rendered.append(f"{period['period_key']} ({detail})")
        more = f" (newest {len(newest)} of {len(group)})" if len(group) > len(newest) else ""
        lines.append(f"  incomplete {label}{more}: {'; '.join(rendered)}")
    if acquirable:
        command = f"python3 scripts/build_dip_pulse_site.py --output-dir {shlex.quote(str(output_dir))} --backfill-incomplete"
        vote_gaps = any("votes" in gap["reasons"] for gap in gaps.values())
        if vote_scan_pages == 0 and vote_gaps:
            # Votes are switched off in this build's configuration; an
            # explicit --enrich lifts a config veto (not --no-votes).
            command += " --enrich votes"
        elif exhausted:
            command += f" --vote-scan-pages {raised_pages}"
        lines.append(f"  Fix: {command}   (acquires {len(acquirable)} sittings; every other cached dossier is kept)")
    else:
        lines.append("  Fix: none available now; run an online update once DIP publishes the missing protocols")
    lines.append("  Docs: README.md#backfill-incomplete-sittings")
    return lines


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


# Every list of an agenda item that holds speakers: Reden and Beiträge.
SPEAKER_LISTS = ("xml_speakers", "xml_speakers_first", "xml_contributions")


def speaker_identity(speaker: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(speaker.get("xml_redner_id") or ""),
        str(speaker.get("first_name") or ""),
        str(speaker.get("last_name") or ""),
    )


def speaker_profiles(item: dict[str, Any]) -> dict[tuple[str, str, str], Any]:
    """The abgeordnetenwatch profiles an agenda item's speakers carry, by identity."""
    profiles: dict[tuple[str, str, str], Any] = {}
    for key in SPEAKER_LISTS:
        for speech in item.get(key) or []:
            speaker = speech.get("speaker")
            if isinstance(speaker, dict) and "abgeordnetenwatch" in speaker:
                profiles[speaker_identity(speaker)] = speaker["abgeordnetenwatch"]
    return profiles


def attach_speaker_profiles(
    item: dict[str, Any],
    profiles: dict[tuple[str, str, str], Any],
    by_redner_id: dict[str, Any] | None = None,
) -> None:
    """Give the speakers of an agenda item the profile a cached one of the same
    identity carried, where they have none yet; else the profile any cached report
    resolved for the same Redner-ID (``by_redner_id``)."""
    for key in SPEAKER_LISTS:
        for speech in item.get(key) or []:
            speaker = speech.get("speaker")
            if not isinstance(speaker, dict) or "abgeordnetenwatch" in speaker:
                continue
            identity = speaker_identity(speaker)
            if identity in profiles:
                speaker["abgeordnetenwatch"] = copy.deepcopy(profiles[identity])
            elif by_redner_id and derive.first_redner_id(speaker.get("xml_redner_id")) in by_redner_id:
                speaker["abgeordnetenwatch"] = copy.deepcopy(by_redner_id[derive.first_redner_id(speaker.get("xml_redner_id"))])


def enrich_report_with_profiles(report: dict[str, Any], resolver: Any | None) -> None:
    """Attach abgeordnetenwatch profile links to speakers and vote members.

    Each speaker dict gains an ``abgeordnetenwatch`` key holding the resolved
    profile (or ``None`` when no confident match exists). xml_speakers and
    xml_speakers_first share speaker objects for the first speeches, so the
    presence check keeps each speaker resolved at most once. The speakers of
    xml_contributions (Beiträge) are resolved the same way, so one Person's
    Reden and Beiträge carry the same profile and so one identity. Roll-call vote
    members use the same name+party resolver path with a conservative surname
    heuristic because Bundestag vote data only exposes a display name.
    """
    if resolver is None:
        return
    for item in [report, *(report.get("agenda_items") or [])]:
        for key in SPEAKER_LISTS:
            for speech in item.get(key) or []:
                speaker = speech.get("speaker")
                if not isinstance(speaker, dict) or "abgeordnetenwatch" in speaker:
                    continue
                if key == "xml_contributions" and not speaker.get("xml_redner_id"):
                    continue  # a question whose asker never speaks: a name only
                speaker["abgeordnetenwatch"] = resolver.resolve(
                    ext_id=speaker.get("xml_redner_id"),
                    first_name=speaker.get("first_name"),
                    last_name=speaker.get("last_name"),
                    fraktion=speaker.get("fraktion"),
                )
    for _, vote in derive.iter_report_votes(report):
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


# The sitting's Plenarprotokoll XML as fetched, kept so a rule change in the
# parser needs --offline --repersist and no re-fetch.
def xml_cache_path(output_dir: Path, document_number: str) -> Path:
    return output_dir / "data" / "xml" / f"plenarprotokoll-{slugify_document_number(document_number)}.xml"


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
    mp_lookup: dict[str, str] | None = None,
    features: Selection | None = None,
    *,
    include_dev_view: bool = False,
    database_page_href: str | None = None,
    vorgang_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    features = publication_selection()
    protocol = report.get("protocol") or {}
    document_number = normalized_document_number(protocol.get("dokumentnummer"))
    report_path, page_path, slug = report_paths(output_dir, document_number)
    rendered = pulse_html.render_html(
        report, features=features, mp_lookup=mp_lookup,
        include_dev_view=include_dev_view, database_page_href=database_page_href,
        vorgang_cache=vorgang_cache,
    )
    dip.write_text_atomic(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    dip.write_text_atomic(page_path, rendered)
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


class CachedReportError(Exception):
    """A cached dossier report that a strict load could not read."""


# What a build prints when a cached report stops it before any dossier is
# fetched, so the online update that would re-fetch the sitting cannot run
# either. A plain update re-fetches only the newest sittings, hence the flag.
CACHED_REPORT_FIX = (
    "Fix: move that report out of data/, then re-fetch its sitting with an online update "
    "and --document-number <its number>"
)


# Collect cached dossiers from data/ for the given protocols (every online build
# keeps them all, and the offline render reads them). Reports whose sitting is
# not part of this build's catalog are ignored, and unreadable files are skipped
# with a warning instead of failing the build.
#
# ``strict`` is for a re-persist, which must not swap in a database built from
# fewer reports than the cache holds: an unreadable file raises instead.
def load_existing_detail_entries(
    output_dir: Path, protocols: list[dict[str, Any]], *, strict: bool = False
) -> list[dict[str, Any]]:
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
            if not isinstance(report, dict):
                raise ValueError("the top-level JSON value is not an object")
            if not isinstance(report.get("protocol") or {}, dict):
                raise ValueError("protocol must be an object")
            items = report.get("agenda_items", [])
            if not isinstance(items, list) or any(not isinstance(item, dict) or item.get("index") is None for item in items):
                raise ValueError("agenda_items must contain objects with integer source indices")
            # An index given as 3 or "3" is one item (stable_ids.source_index);
            # the file keeps the form it was written in.
            indexes = [source_index(item.get("index")) for item in items]
            if len(set(indexes)) != len(indexes):
                raise ValueError("agenda_items repeat a source index")
            for item in [report, *items]:
                for key in SPEAKER_LISTS:
                    units = item.get(key) or []
                    if not isinstance(units, list) or any(not isinstance(unit, dict) for unit in units):
                        raise ValueError(f"{key} must be a list of source units")
        except (OSError, ValueError) as exc:  # json.JSONDecodeError is a ValueError
            if strict:
                raise CachedReportError(f"{report_path} is unreadable: {exc}") from exc
            print(f"warning: Skipping unreadable dossier report {report_path}: {exc}", file=sys.stderr)
            continue
        protocol = report.get("protocol") or {}
        document_number = normalized_document_number(protocol.get("dokumentnummer"))
        if strict and not document_number:
            raise CachedReportError(f"{report_path} has no document number; restore source identity before replay")
        if not document_number or document_number not in protocol_numbers:
            continue
        # Raised even on a lenient load, which would otherwise drop the whole
        # sitting with a warning; a report outside the catalog is never read.
        try:
            derive.require_vote_shape(report)
        except ValueError as exc:
            raise CachedReportError(f"{report_path}: {exc}") from exc
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
    catalog_path = output_dir / "data" / facts.CATALOG_FILENAME
    protocols: list[dict[str, Any]] = []
    if catalog_path.exists():
        try:
            cached = json.loads(catalog_path.read_text(encoding="utf-8"))
            if isinstance(cached, dict) and isinstance(cached.get("protocols"), list):
                protocols.extend(item for item in cached["protocols"] if isinstance(item, dict))
            else:
                print(
                    f"warning: Ignoring cached protocol catalog {catalog_path}: it predates the catalog format "
                    "completeness is judged against. Fix: run an online update.",
                    file=sys.stderr,
                )
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
    mp_lookup: dict[str, str] | None = None,
    features: Selection | None = None,
    cached_entries: list[dict[str, Any]] | None = None,
    *,
    include_dev_view: bool = False,
    database_page_href: str | None = None,
    vorgang_cache: dict[str, Any] | None = None,
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
                database_page_href=database_page_href,
                vorgang_cache=vorgang_cache,
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


@dataclass(frozen=True)
class Rebuilt:
    """A staged rebuild that succeeded: whether the store file was replaced, and
    the facts engine's report for the store it built (computed on every rebuild,
    so the data pipeline never computes the facts a second time)."""
    replaced: bool
    facts_report: dict[str, Any]


class DatabaseRebuildError(Exception):
    """The staged rebuild failed (an unpersistable report, a registry, facts or SQLite
    error, missing cached evidence, a failed roster fetch or integrity check); the
    previous store stays."""


# What a failed data pipeline (export, facts, staged store write) raises: main
# reports each as one error: line and exit 1, offline and online alike.
PIPELINE_ERRORS = (RuntimeError, OSError, ValueError, json.JSONDecodeError, DatabaseRebuildError, sqlite3.Error)


# Columns holding when a row was written, not what it says. A re-persist that
# changes nothing but these has changed nothing (E9).
_TIMESTAMP_COLUMNS = frozenset({"created_at", "updated_at", "applied_at"})


def _read_roster_rows(database_path: Path) -> list[dict[str, Any]]:
    """The MdB roster rows of an existing store, read without migrating it."""
    if not database_path.exists():
        return []
    previous = facts.open_readonly(database_path)
    try:
        columns = {row[1] for row in previous.execute("PRAGMA table_info(mps)")}
        if "is_mdb" not in columns:
            return []
        return [
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


def _content_digests(database_path: Path) -> dict[str, str] | None:
    """table -> digest of its column names, row count and rows, timestamps left
    out; None when the file cannot be read that way (then it counts as changed).

    Each row's sha256 is summed modulo 2**256 in whatever order SQLite returns
    the rows, so no table is sorted by its text primary key (that sort was most
    of the cost); a changed, deleted or duplicated row still changes the digest."""
    try:
        conn = sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        digests: dict[str, str] = {}
        tables = [
            name
            for (name,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        for table in tables:
            columns = [row[1] for row in conn.execute(f"PRAGMA table_info({sqlite_identifier(table)})")
                       if row[1] not in _TIMESTAMP_COLUMNS]
            selected = ", ".join(sqlite_identifier(column) for column in columns)
            total = count = 0
            for row in conn.execute(f"SELECT {selected} FROM {sqlite_identifier(table)}"):
                total += int.from_bytes(hashlib.sha256(repr(row).encode("utf-8")).digest(), "big")
                count += 1
            digests[table] = hashlib.sha256(repr((columns, count, total % 2**256)).encode("utf-8")).hexdigest()
        return digests
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def _same_content(current: Path, rebuilt: Path) -> bool:
    before = _content_digests(current)
    return before is not None and before == _content_digests(rebuilt)


def _entry_label(entry: dict[str, Any]) -> str:
    protocol = entry["report"].get("protocol") or {}
    number = normalized_document_number(protocol.get("dokumentnummer")) or "an unnumbered protocol"
    return f"{number} ({entry.get('report_path')})"


# Rebuild the SQLite store from scratch out of the dossier reports.
#
# Written to a temporary file in the store's private directory (never in the
# published tree) and moved into place only on
# success, so a failed build never leaves a half-written database behind - the
# database explorer page and the download link both read this file. The store
# being replaced is only ever read, and through a read-only connection: a
# rebuild that fails part-way must leave it byte for byte as it was, even when
# it was written by an older schema.
def rebuild_database_from_entries(database_path, entries, *, preserve_roster=True, keep_if_unchanged=False, catalog=None, roster_ingest=None,
                                  today=None, upgrade=False, vorgang_cache=None) -> Rebuilt:
    """Stage a fresh build store from ``entries`` and swap it over ``database_path``.

    Holds the writer lock; carries the person registry and previous facts forward;
    persists every report; re-applies the preserved roster (``preserve_roster``) or
    runs ``roster_ingest(staged_connection)``; reconciles persons; recomputes facts
    against ``catalog``; validates the registry and integrity; replaces the store
    only when all of that succeeded (and, with ``keep_if_unchanged``, only when its
    content changed). ``today`` is the build date the facts are computed for. Only ``upgrade`` (``--offline --repersist``)
    accepts a store of an older schema; every other caller is refused, so the
    registry is re-minted only on that explicit step. Returns a ``Rebuilt``. Any registry, SQLite,
    OS or facts failure, and missing cached evidence for a stored protocol, raise
    DatabaseRebuildError with the previous store untouched."""
    # One spelling for the lock, the staging directory and the swap: a rebuild
    # through a symlink to the store replaces the store, not the link.
    database_path = Path(database_path).resolve()
    try:
        with registry.writer_lock(database_path):
            return _rebuild_database_from_entries(database_path, entries,
                preserve_roster=preserve_roster, keep_if_unchanged=keep_if_unchanged,
                catalog=catalog, roster_ingest=roster_ingest, today=today, upgrade=upgrade,
                vorgang_cache=vorgang_cache)
    except (registry.RegistryError, sqlite3.Error, OSError, facts.FactsError) as exc:
        raise DatabaseRebuildError(str(exc)) from exc


def _staged_store_path(database_path: Path) -> Path:
    """A fresh staged file for a store, under the writer lock: in the store's
    private directory, never in the published tree (registry.private_dir), and on
    the store's file system so the final rename is atomic."""
    staging = registry.private_dir(database_path)
    if staging.stat().st_dev != database_path.parent.stat().st_dev:
        raise DatabaseRebuildError(
            f"{staging} is on another file system than {database_path}; the staged store could not replace it atomically"
        )
    # Only the lock holder is here, so a staged copy that is still lying around
    # is from a crashed run; it holds full speech text, so it must not pile up.
    # (the ``.tmp*`` pattern also takes a crashed build's -journal/-wal/-shm sidecars)
    name = database_path.resolve().name
    for stale in staging.glob(f"{glob.escape(name)}.*.tmp*"):
        stale.unlink(missing_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f"{name}.", suffix=".tmp", dir=staging)
    os.close(fd)
    return Path(temporary)


def _replace_store(database_path: Path, temp_path: Path) -> None:
    """Swap a staged store in; the store keeps the file mode it had (mkstemp
    makes the staged copy private)."""
    os.chmod(temp_path, stat_module.S_IMODE(database_path.stat().st_mode) if database_path.exists() else 0o644)
    temp_path.replace(database_path)


def _rebuild_database_from_entries(
    database_path: Path,
    entries: list[dict[str, Any]],
    *,
    preserve_roster: bool = True,
    keep_if_unchanged: bool = False,
    catalog: facts.SittingCatalog | None = None,
    roster_ingest: Any = None,
    today: date | None = None,
    upgrade: bool = False,
    vorgang_cache: dict[str, Any] | None = None,
) -> Rebuilt:
    """Body of rebuild_database_from_entries (see its docstring); the caller holds the writer lock."""
    if database_path.exists():
        try:
            probe = facts.open_readonly(database_path)
            try:
                probe.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
            finally:
                probe.close()
        except sqlite3.Error as exc:
            raise DatabaseRebuildError(f"The store {database_path} cannot be read ({exc})") from exc
    if not upgrade and database_path.exists():
        current = facts.open_readonly(database_path)
        try:
            pulse_store.require_current_schema(current)
        except RuntimeError as exc:  # the old-schema refusal; RegistryError reaches the caller as it is
            raise DatabaseRebuildError(str(exc)) from exc
        finally:
            current.close()
    # Every cached role is checked first, so one error lists all of them and
    # nothing is built or replaced (DX-E1).
    derive.check_sprechrollen(entry["report"] for entry in entries)
    roster_rows = _read_roster_rows(database_path) if preserve_roster else []

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

    temp_path = _staged_store_path(database_path)
    store = pulse_store.connect(temp_path)
    try:
        pulse_store.initialize(store)
        registry.begin_build(store)
        if database_path.exists():
            previous = facts.open_readonly(database_path)
            try:
                previous_protocols = {row[0] for row in previous.execute("SELECT id FROM protocols")}
                available = {str(entry["report"]["protocol"]["id"]) for entry in entries}
                missing = previous_protocols - available
                if missing:
                    raise DatabaseRebuildError(f"Missing cached evidence for protocols {sorted(missing)}; restore their reports before --offline --repersist")
                registry.copy_previous(previous, store)
            finally:
                previous.close()
        for entry in sorted(entries, key=entry_sort_key, reverse=True):
            try:
                pulse_store.persist_report(store, entry["report"], vorgang_cache)
            except Exception as exc:
                raise DatabaseRebuildError(f"{_entry_label(entry)} did not persist: {exc}") from exc
        if roster_rows:
            now = pulse_store.utc_now()
            with store:
                skipped = [row for row in roster_rows if not canonical_dip_person_id(row.get("dip_person_id"))]
                if skipped:
                    # No roster identity: ingest_mdb_roster skips such rows too.
                    print(f"warning: [roster] {len(skipped)} preserved roster rows have no DIP id and were skipped", file=sys.stderr)
                for row in roster_rows:
                    if not canonical_dip_person_id(row.get("dip_person_id")):
                        continue
                    party_id = pulse_store.upsert_party(store, row.get("party_name"), now)
                    pulse_store.upsert_mp(
                        store,
                        now=now,
                        display_name=row.get("display_name"),
                        party_id=party_id,
                        # Keyed by today's rule, not the stored key: a roster row
                        # written when a name-found abgeordnetenwatch id still named
                        # identity would otherwise fold into a speaker row sharing it.
                        identity_key=pulse_store.mp_identity(
                            aw_politician_id=row.get("aw_politician_id"),
                            aw_match=row.get("aw_match"),
                            dip_person_id=row.get("dip_person_id"),
                            # The roster never supplies a Redner-ID. A stored
                            # one came from an old speaker merge and may name a
                            # namesake; only the cached reports can restore it.
                            xml_redner_id=None,
                            profile_url=row.get("profile_url"),
                            display_name=row.get("display_name"),
                            party_name=row.get("party_name"),
                        ),
                        dip_person_id=row.get("dip_person_id"),
                        occurrence_id=roster_occurrence_id(row.get("dip_person_id")),
                        xml_redner_id=None,
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
                        aw_match=row.get("aw_match"),
                        person_roles_json=row.get("person_roles_json"),
                        is_mdb=True,
                    )
        if roster_ingest is not None:
            try:
                roster_ingest(store)
            except RuntimeError as exc:  # the roster API failed (dip.DipError): nothing may be swapped in
                raise DatabaseRebuildError(f"The Abgeordnetenkader could not be fetched: {exc}") from exc
        try:
            pulse_store.require_current_speech_rules(store)
        except RuntimeError as exc:
            raise DatabaseRebuildError(str(exc)) from exc
        registry.reconcile(store)
        store.commit()
        if facts_snapshot is not None:
            facts.write_snapshot(store, facts_snapshot)
        report = facts.compute_and_store(store, facts.ALL_REGISTRY, facts.completeness_from_entries(entries),
                                         built=facts.built_sources(store), catalog=catalog, today=today)
        registry.validate(store)
        if store.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise DatabaseRebuildError("Rebuilt database failed integrity_check")
        if store.execute("PRAGMA foreign_key_check").fetchone():
            raise DatabaseRebuildError("Rebuilt database failed foreign_key_check")
        store.commit()
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        store.close()
    if keep_if_unchanged and database_path.exists() and _same_content(database_path, temp_path):
        temp_path.unlink()
        return Rebuilt(replaced=False, facts_report=report)
    _replace_store(database_path, temp_path)
    return Rebuilt(replaced=True, facts_report=report)


def unparsed_reports(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cached reports with missing or older speech-counting rule provenance."""
    return [
        entry
        for entry in entries
        if (entry["report"].get("validation_summary") or {}).get("speech_kinds_version") != speech_kinds.VERSION
    ]


def require_parsed_reports(entries: list[dict[str, Any]]) -> None:
    """Refuse stale rule inputs before mixing them into the store's counts."""
    stale = unparsed_reports(entries)
    if stale:
        numbers = ", ".join(
            sorted(str((entry["report"].get("protocol") or {}).get("dokumentnummer") or "?") for entry in stale)
        )
        raise CachedReportError(
            f"{len(stale)} cached reports predate the current speech-counting rule and have no cached XML in data/xml/ to re-read "
            f"them from ({numbers}). Run --fetch-xml, then --offline --repersist; a report whose XML cannot be "
            "fetched (no xml_url) must be deleted from data/"
        )


def warn_unparsed_reports(entries: list[dict[str, Any]], *, keeping: str = "keep") -> int:
    """Warn about missing or older rule inputs and return their count."""
    stale = unparsed_reports(entries)
    if stale:
        print(
            f"warning: {len(stale)} of {len(entries)} cached reports predate the current speech-counting rule and {keeping} "
            "their older classifications, so Reden counts, Redeanteil and Fakten may mix rule versions. "
            "Fix: run --fetch-xml if XML is missing, then --offline --repersist.",
            file=sys.stderr,
        )
    return len(stale)


def reparse_cached_xml(
    output_dir: Path, entries: list[dict[str, Any]], profiles_from: list[dict[str, Any]] | None = None
) -> int:
    """Re-read Reden and Beiträge of every cached report from its cached XML,
    where the XML exists, keeping the abgeordnetenwatch profiles its speakers
    carry or that ``profiles_from`` (default: ``entries``) holds for them, and
    interpret the report's votes again (what each was about and its outcome),
    with the chair's announcements from that XML where it exists.
    Returns how many reports it re-parsed."""
    # The XML knows nothing of abgeordnetenwatch: the profiles resolved online must
    # survive the re-parse, also for a Person who only asks a Frage in a sitting.
    by_redner_id: dict[str, Any] = {}
    for entry in entries if profiles_from is None else profiles_from:
        for item in [entry["report"], *(entry["report"].get("agenda_items") or [])]:
            for identity, profile in speaker_profiles(item).items():
                redner_id = derive.first_redner_id(identity[0])
                if redner_id and isinstance(profile, dict) and profile.get("id") is not None:
                    by_redner_id.setdefault(redner_id, profile)
    reparsed = 0
    for entry in entries:
        report = entry["report"]
        document_number = normalized_document_number((report.get("protocol") or {}).get("dokumentnummer"))
        path = xml_cache_path(output_dir, document_number)
        if not document_number or not path.exists():
            # No XML to read the chair's announcements from: the votes are still
            # re-read from what the report holds, keeping what the XML once gave.
            dip.interpret_report_votes(report, None)
            continue
        profiles = {item.get("index"): speaker_profiles(item) for item in [report, *(report.get("agenda_items") or [])]}
        try:
            parsed = dip.parse_protocol_xml(path.read_text(encoding="utf-8"))
            dip.reparse_report_xml(report, parsed)
        except (dip.ET.ParseError, OSError, UnicodeDecodeError, ValueError, derive.SprechrolleError) as exc:
            raise CachedReportError(
                f"{path} is not the Plenarprotokoll XML of {document_number}: {exc}. Check the source identity and TOP evidence; reacquire the report on ambiguous association, or delete corrupt XML and run --fetch-xml again"
            ) from exc
        for item in [report, *(report.get("agenda_items") or [])]:
            attach_speaker_profiles(item, profiles.get(item.get("index"), {}), by_redner_id)
        dip.interpret_report_votes(report, parsed["vote_recommendations"])
        reparsed += 1
    return reparsed


def fetch_missing_xml(output_dir: Path, entries: list[dict[str, Any]], *, pause: float = 0.25) -> tuple[int, int]:
    """Download the Plenarprotokoll XML of every cached report that has none in
    ``data/xml/`` (a public bundestag.de file, no API key). Returns (fetched,
    failed). Older builds did not keep the XML."""
    fetched = failed = 0
    for entry in entries:
        protocol = entry["report"].get("protocol") or {}
        document_number = normalized_document_number(protocol.get("dokumentnummer"))
        path = xml_cache_path(output_dir, document_number)
        if not document_number:
            print("warning: cached report has no document number; XML acquisition failed.", file=sys.stderr)
            failed += 1
            continue
        if path.exists():
            continue
        if not protocol.get("xml_url"):
            print(f"warning: {document_number} has no xml_url; its XML cannot be fetched.", file=sys.stderr)
            failed += 1
            continue
        try:
            publication.validate_external_url(protocol["xml_url"], "bundestag-xml")
            text = dip.fetch_text(protocol["xml_url"])
            # An error or maintenance page served with HTTP 200 must not become the cache.
            root = dip.ET.fromstring(text)
            wahlperiode, _, sitzung = document_number.partition("/")
            if (root.tag, root.attrib.get("wahlperiode"), root.attrib.get("sitzung-nr")) != (
                "dbtplenarprotokoll",
                wahlperiode,
                sitzung,
            ):
                raise ValueError(f"it is not the Plenarprotokoll XML of {document_number}")
            if not root.findall("./sitzungsverlauf/tagesordnungspunkt"):
                raise ValueError("it holds no agenda items (not a Plenarprotokoll?)")
        except (dip.DipError, dip.ET.ParseError, ValueError, publication.PublicationStateError) as exc:
            print(f"warning: {document_number}: {exc}", file=sys.stderr)
            failed += 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        dip.write_text_atomic(path, text)
        fetched += 1
        if pause:
            time.sleep(pause)
    return fetched, failed


def validate_cached_kinds(entries: list[dict[str, Any]]) -> None:
    for entry in entries:
        report = entry["report"]
        kinds = [c.get("kind") for item in [report, *(report.get("agenda_items") or [])]
                 for c in item.get("xml_contributions") or []]
        kinds += [m.get("kind") for m in (report.get("validation_summary") or {}).get("contribution_dip_mismatches") or []]
        try:
            for kind in kinds:
                speech_kinds.validate_kind(kind)
        except ValueError as exc:
            raise CachedReportError(f"{_entry_label(entry)}: {exc}") from exc


def write_classification_diagnostics(output_dir: Path, entries: list[dict[str, Any]]) -> dict[str, Any]:
    details = []
    for entry in entries:
        report = entry["report"]
        for mismatch in (report.get("validation_summary") or {}).get("contribution_dip_mismatches") or []:
            speech_kinds.validate_kind(mismatch["kind"])
            details.append({"document_number": (report.get("protocol") or {}).get("dokumentnummer"), **mismatch})
    details.sort(key=lambda row: (row["document_number"] or "", row["kind"]))
    audit = {"speech_kinds_version": speech_kinds.VERSION, "mismatches": details}
    path = output_dir / "data" / "a1-classification-diagnostics.json"
    dip.write_text_atomic(path, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    if details:
        sittings = len({row["document_number"] for row in details})
        print(f"warning: [classification] {len(details)} sitting/kind differences against DIP across {sittings} sittings. "
              f"Inspect source turns in {path}; disagreement alone does not reject a parse.", file=sys.stderr)
    return audit


#: Failed DIP calls in a row after which the Vorgang fetch stops for this build.
VORGANG_FETCH_MAX_FAILURES = 5
#: Seconds before every DIP request of the Vorgang fetch. A lookup is one list_all,
#: which takes two requests (the second confirms the cursor ended), and the pause
#: goes before each, so the fetch stays near 1.5 requests a second. At about 4 a
#: second DIP's edge answered 400 with a bot challenge to the whole API for over
#: an hour (2026-10-04). The first full fill (about 2,400 numbers) took 1,577 s with
#: one pause per lookup and takes about 45 minutes with two; later builds fetch
#: only new numbers.
NUMBER_LOOKUP_PAUSE = 0.5
#: Drucksache-number lookups between two saves of the Vorgang cache.
CACHE_SAVE_EVERY = 100


def refresh_vorgang_cache(
    client: Any, entries: list[dict[str, Any]], cache: dict[str, Any], output_dir: Path
) -> dict[str, int]:
    """Fetch the Vorgänge and Drucksache numbers the Politikfelder still need, into
    ``cache`` (updated in place) and ``data/dip-vorgang-cache.json``.

    Fetches only what is missing, plus cached Vorgänge that still have no
    Sachgebiet (DIP may have filled it since). Ids go first: when they show the
    API is down, the number lookups are not tried. A failed
    call leaves a cache miss, which the Politikfelder store as ``not_fetched``; the
    build warns and goes on. Returns the fetch counts.
    """
    reports = [entry["report"] for entry in entries]
    stats = {"vorgaenge": 0, "vorgaenge_failed": 0, "nummern": 0, "nummern_failed": 0, "shape_errors": 0}

    def shape_error(exc: dip.DipShapeError) -> None:
        stats["shape_errors"] += 1

    def warn_shape(exc: dip.DipShapeError) -> None:
        shape_error(exc)
        print(f"warning: Vorgang validation: {exc}", file=sys.stderr)

    def save() -> None:
        try:
            politikfelder.save_cache(output_dir, cache)
        except OSError as exc:  # a full disk must not end the build or hide its own error
            print(f"warning: could not save the Vorgang cache: {exc}", file=sys.stderr)

    def fetch_ids(ids: list[str]) -> bool:
        """Fetch ``ids`` in batches into the cache; True when the API looks down
        (VORGANG_FETCH_MAX_FAILURES batches failed in a row), so the caller stops."""
        failures = 0
        for start in range(0, len(ids), dip.VORGANG_BATCH):
            batch = ids[start : start + dip.VORGANG_BATCH]
            time.sleep(NUMBER_LOOKUP_PAUSE)
            try:
                records = dip.fetch_vorgaenge(
                    client, batch, page_pause=NUMBER_LOOKUP_PAUSE, on_shape_error=shape_error
                )
                cache["vorgaenge"].update(records)
                stats["vorgaenge"] += len(records)
                stats["vorgaenge_failed"] += len(set(batch) - records.keys())
                failures = 0
            except dip.DipError as exc:
                stats["vorgaenge_failed"] += len(batch)
                failures += 1
                print(f"warning: Vorgang fetch failed for {len(batch)} ids: {exc}", file=sys.stderr)
                if failures >= VORGANG_FETCH_MAX_FAILURES:
                    stats["vorgaenge_failed"] += len(ids) - start - len(batch)
                    return True
        return False

    def resolve_numbers(numbers: list[str]) -> None:
        """Resolve numbers one call each, saving the cache every CACHE_SAVE_EVERY
        lookups so an interrupted first fill keeps its progress; stops after
        VORGANG_FETCH_MAX_FAILURES failures in a row."""
        failures = 0
        try:
            for position, number in enumerate(numbers):
                time.sleep(NUMBER_LOOKUP_PAUSE)
                complete = True
                try:
                    documents = dip.resolve_dokumentnummer(client, number, page_pause=NUMBER_LOOKUP_PAUSE)
                except dip.DipShapeError as exc:
                    warn_shape(exc)
                    documents = exc.documents
                    complete = False
                except dip.DipError as exc:
                    stats["nummern_failed"] += 1
                    failures += 1
                    print(f"warning: could not resolve Drucksache {number}: {exc}", file=sys.stderr)
                    if failures >= VORGANG_FETCH_MAX_FAILURES:
                        stats["nummern_failed"] += len(numbers) - position - 1
                        return
                    continue
                failures = 0
                ids: list[str] = []
                for document in documents:
                    try:
                        record_id = dip.vorgang_id(document)
                    except dip.DipShapeError as exc:
                        warn_shape(exc)
                        complete = False
                        continue
                    if record_id not in ids:
                        ids.append(record_id)
                    try:
                        cache["vorgaenge"][record_id] = dip.vorgang_cache_record(document)
                    except dip.DipShapeError as exc:
                        warn_shape(exc)
                if complete:
                    stats["nummern"] += 1
                    cache["dokumentnummern"][number] = ids
                else:
                    stats["nummern_failed"] += 1
                if (position + 1) % CACHE_SAVE_EVERY == 0:
                    save()
        finally:
            save()

    ids, numbers = politikfelder.fetch_targets(reports, cache)
    try:
        down = fetch_ids(ids)
    finally:
        save()

    # A lookup returns its Vorgang records inline, so no further id pass is needed.
    if not down:
        resolve_numbers(numbers)
    print(
        f"politikfelder: fetched {stats['vorgaenge']} Vorgänge and {stats['nummern']} Drucksache numbers "
        f"({stats['vorgaenge_failed']} Vorgänge and {stats['nummern_failed']} numbers failed, left retryable; "
        f"{stats['shape_errors']} validation errors)",
        file=sys.stderr,
    )
    return stats


def log_politikfelder_summary(database_path: Path, cache: dict[str, Any]) -> None:
    """One line per build, on every path: how many TOPs and votes the store tags by
    source, how many of them are ``not_fetched`` (a cache miss: run an online update),
    and any Sachgebiet label DIP now uses that the mapping does not know."""
    unknown = politikfelder.unknown_sachgebiete(cache)
    if unknown:
        print(
            f"warning: [politikfelder] Sachgebiet labels the mapping does not know, skipped: {sorted(unknown)}. "
            "Fix: map them in SACHGEBIET_TO_POLITIKFELD.",
            file=sys.stderr,
        )
    try:
        conn = sqlite3.connect(f"{Path(database_path).resolve().as_uri()}?mode=ro", uri=True)
        try:
            counts = {
                kind: dict(conn.execute(f"SELECT source, COUNT(DISTINCT {key}) FROM {table} GROUP BY source"))
                for kind, table, key in (
                    ("TOPs", "agenda_item_politikfelder", "agenda_item_id"),
                    ("Abstimmungen", "vote_politikfelder", "vote_id"),
                )
            }
        finally:
            conn.close()
    except sqlite3.Error as exc:
        print(f"note: [politikfelder] no summary, the store could not be read: {exc}", file=sys.stderr)
        return
    for kind, by_source in counts.items():
        listed = ", ".join(f"{n} {source}" for source, n in sorted(by_source.items(), key=lambda item: -item[1]))
        print(f"politikfelder: {kind}: {listed or 'none'}", file=sys.stderr)
    missing = sum(by_source.get("not_fetched", 0) for by_source in counts.values())
    if missing:
        print(
            f"warning: [politikfelder] {missing} TOPs or votes are not_fetched (not in the Vorgang cache). "
            "Fix: run an online update.",
            file=sys.stderr,
        )


def require_vorgang_cache_for_tags(
    database_path: Path, vorgang_cache: dict[str, Any] | None, output_dir: Path, entries: list[dict[str, Any]]
) -> None:
    """Refuse replay when a previously known TOP or vote becomes not_fetched, or a
    vote whose context (``votes.context_state``) was known, resolved or none, would
    become not_fetched.
    Only an absent store or both absent legacy tag tables bypass this check."""
    if not database_path.exists():
        return
    try:
        conn = sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE name IN ('agenda_item_politikfelder', 'vote_politikfelder')"
            )}
            if not tables:
                version = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]
                if type(version) is int and 0 < version < 5:
                    return
            if len(tables) != 2:
                raise DatabaseRebuildError(
                    f"Cannot check Politikfelder in {database_path}: incomplete store, tag tables are missing. "
                    "Fix: restore a complete store before replay"
                )
            known_tops, known_votes = (
                {row[0] for row in conn.execute(f"SELECT DISTINCT {key} FROM {table} WHERE source != 'not_fetched'")}
                for table, key in (("agenda_item_politikfelder", "agenda_item_id"), ("vote_politikfelder", "vote_id"))
            )
            # A schema-5 store has no context yet, so there is nothing to lose.
            vote_columns = {row[1] for row in conn.execute("PRAGMA table_info(votes)")}
            known_contexts = (
                dict(conn.execute("SELECT id, context_state FROM votes WHERE context_state IN ('resolved', 'none')"))
                if "context_state" in vote_columns else {}
            )
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise DatabaseRebuildError(
            f"The store {database_path.resolve()} cannot be read for the Politikfelder check: {exc}. "
            "Fix: restore read access, release any database lock, or restore a healthy store before replay"
        ) from exc
    cache = vorgang_cache or politikfelder.empty_cache()
    missing_tops: set[str] = set()
    vote_sources: dict[str, str] = {}
    context_states: dict[str, str] = {}
    for entry in sorted(entries, key=entry_sort_key, reverse=True):
        report = entry["report"]
        item_tags, vote_tags = politikfelder.report_politikfelder(report, cache)
        contexts = politikfelder.report_vote_vorgaenge(report, cache)
        protocol_id = pulse_store.clean((report.get("protocol") or {}).get("id"))
        for item, (_tags, source) in zip(report.get("agenda_items") or [], item_tags):
            if source == "not_fetched":
                missing_tops.add(pulse_store.stable_key("agenda", protocol_id, source_index(item.get("index"))))
        for _item, vote in derive.iter_report_votes(report):
            vote_id = pulse_store.clean(vote.get("id"))
            if vote_id:
                # Match persistence's final overwrite for normalized duplicate IDs.
                vote_sources[vote_id] = vote_tags[politikfelder.vote_key(vote)][1]
                context_states[vote_id] = contexts[politikfelder.vote_key(vote)].state
    regressed_tops = missing_tops & known_tops
    regressed_votes = {key for key, source in vote_sources.items() if source == "not_fetched"} & known_votes
    regressed_contexts = {key for key, state in context_states.items() if state == "not_fetched"} & known_contexts.keys()
    regressed_none = sum(1 for key in regressed_contexts if known_contexts[key] == "none")
    if regressed_tops or regressed_votes or regressed_contexts:
        raise DatabaseRebuildError(
            f"with the Vorgang cache {politikfelder.cache_path(output_dir)} as it is, a re-persist would leave "
            f"{len(regressed_tops)} previously known TOPs and {len(regressed_votes)} previously known votes "
            f"not_fetched and {len(regressed_contexts)} previously known vote contexts not_fetched "
            f"({len(regressed_contexts) - regressed_none} resolved, {regressed_none} none) "
            f"(TOP examples: {sorted(regressed_tops)[:3]}; vote examples: {sorted(regressed_votes)[:3]}; "
            f"context examples: {sorted(regressed_contexts)[:3]}). "
            "Fix: run an online update (it refills the cache) or restore the cache file, then re-run"
        )


def repersist_cached_reports(
    output_dir: Path, database_path: Path, protocols: list[dict[str, Any]], *, preserve_roster: bool = True,
    today: date | None = None,
    vorgang_cache: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], Rebuilt]:
    """``--offline --repersist``: every cached report into a fresh store, in the
    order an online build persists them, swapped in only if all of them
    persisted. Reden and Beiträge are first re-read from each report's cached
    XML; a report from before A1 without one stops the run. Returns the loaded entries (the render reuses them) and the
    ``Rebuilt`` result. Raises CachedReportError or DatabaseRebuildError
    with the previous store untouched."""
    cached = load_existing_detail_entries(output_dir, protocols, strict=True)
    reparse_cached_xml(output_dir, cached)
    require_parsed_reports(cached)
    entries = merge_detail_entries(protocols, cached, [])
    require_vorgang_cache_for_tags(database_path, vorgang_cache, output_dir, entries)
    rebuilt = rebuild_database_from_entries(
        database_path, entries, preserve_roster=preserve_roster, keep_if_unchanged=True,
        catalog=facts.load_sitting_catalog(output_dir / "data" / facts.CATALOG_FILENAME),
        today=today, upgrade=True, vorgang_cache=vorgang_cache,
    )
    write_classification_diagnostics(output_dir, cached)
    return cached, rebuilt


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
        # A previous report is read without the cached-report load's checks; a
        # malformed index there matches nothing rather than failing the build.
        with contextlib.suppress(ValueError):
            keys.append(f"index:{source_index(item['index'])}")
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


def carry_forward_vote_provenance(report: dict[str, Any], existing_report: dict[str, Any] | None) -> None:
    """Keep a vote's XLSX link when a rescan found no link this time.

    The SQLite store is rebuilt from these reports every run, so the report is
    the only place a previously found link survives. A vote ages out of the
    Namenslisten page's 200-row window: without this the next build reverts
    it to no link.

    The official result is deliberately NOT carried forward: every vote this
    function sees was just fetched fresh by fetch_roll_call_vote_detail, which
    always sets result_raw/result_source, so "not official this time" is never
    missing data - it is this run's own scrape (with today's parser) disagreeing
    with a cached run. Carrying the old value forward would silently revert any
    parser fix - a rescan that now correctly refuses a match (e.g. a "nicht
    angenommen" negation the old parser missed) must not have that refusal
    overwritten by the stale cached "official" result.
    """
    previous_votes: dict[str, dict[str, Any]] = {}
    for _, vote in derive.iter_report_votes(existing_report or {}):
        previous_votes.setdefault(pulse_html.vote_key(vote), vote)
    if not previous_votes:
        return
    for _, vote in derive.iter_report_votes(report):
        previous = previous_votes.get(pulse_html.vote_key(vote))
        if not previous:
            continue
        # The link was matched by (date, title); if either changed, the
        # old match no longer vouches for this vote.
        if (
            not vote.get("xlsx_url")
            and not vote.get("xlsx_ambiguous")
            and previous.get("xlsx_url")
            and vote.get("date") == previous.get("date")
            and dip.title_match_key(vote.get("title")) == dip.title_match_key(previous.get("title"))
        ):
            vote["xlsx_url"] = previous["xlsx_url"]


def reuse_existing_dossier_enrichments(
    report: dict[str, Any],
    existing_report: dict[str, Any] | None,
    *,
    votes: bool,
    profiles: bool,
) -> None:
    """Carry cached optional data forward when this update does not refresh it."""
    carry_forward_vote_provenance(report, existing_report)
    if votes and not report.get("sitting_votes") and (existing_report or {}).get("sitting_votes"):
        report["sitting_votes"] = copy.deepcopy(existing_report["sitting_votes"])
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
        # Cached votes are kept whole and only for an item the cache identifies
        # unambiguously (equal top_id when both have one): an index match alone
        # can be another TOP. Nothing is merged into a TOP that has votes.
        top_ids = {str(item.get("top_id") or ""), str(previous.get("top_id") or "")} - {""}
        if votes and not derive.item_votes(item) and derive.item_votes(previous) and len(top_ids) <= 1:
            item["votes"] = copy.deepcopy(previous["votes"])
        if not profiles:
            continue

        attach_speaker_profiles(item, speaker_profiles(previous))

    if not profiles:
        return

    previous_members = {
        (str(member.get("name") or ""), str(member.get("faction") or "")): member
        for _, vote in derive.iter_report_votes(existing_report or {})
        for member in (vote.get("members") or [])
    }
    for _, vote in derive.iter_report_votes(report):
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
    for _, vote in derive.iter_report_votes(report):
        for member in vote.get("members") or []:
            targets += 1
            if (member.get("abgeordnetenwatch") or {}).get("url"):
                records += 1
    return records, targets


def _prior_acquired_at(existing_report: dict[str, Any] | None, domain: str) -> str | None:
    return (
        (((existing_report or {}).get("acquisition") or {}).get(domain) or {}).get("acquired_at")
    )


def _keep_prior_scan_end(report: dict[str, Any], existing_report: dict[str, Any] | None) -> None:
    """Votes reused from the cache keep the evidence their scan recorded.

    validation_summary.roll_call_scan_end says how the roll-call scan ended
    (date_passed / list_end). A build that does not scan writes "not_scanned"
    for itself, which must not erase what the reused votes were verified by.
    A report cached before the field existed has none, and stays unverified.
    """
    prior_summary = (existing_report or {}).get("validation_summary") or {}
    prior = prior_summary.get("roll_call_scan_end")
    if prior:
        summary = report.setdefault("validation_summary", {})
        summary["roll_call_scan_end"] = prior
        # The shortfall the scan recorded travels with the votes: a build that
        # does not scan writes 0 for itself, which must not un-hold a sitting.
        for counter in (
            "unmatched_roll_call_vote_count",
            "roll_call_vote_candidate_count",
            "matched_roll_call_vote_count",
            "roll_call_scan_pages",
        ):
            if counter in prior_summary:
                summary[counter] = prior_summary[counter]


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

    vote_records = len(list(derive.iter_report_votes(report)))
    prior_votes = ((existing_report or {}).get("acquisition") or {}).get("votes")
    if vote_scan_pages == 0:
        # No scan this run: the votes on the report are the cached ones, so
        # they keep the state their acquisition recorded (partial and failed
        # included). Only a report that never recorded one has nothing to keep;
        # its votes are unknown provenance (no acquired_at), not "complete".
        if prior_votes:
            # The prior evidence vouches for the votes it verified. If a re-parse
            # (different top_ids) left some of them without an item to sit on,
            # it no longer does: the sitting reads as unverified and a backfill
            # acquires it again.
            unique_now = len({pulse_html.vote_key(v) for _, v in derive.iter_report_votes(report)})
            if unique_now >= int(prior_votes.get("records") or 0):
                _keep_prior_scan_end(report, existing_report)
            acquisition["votes"] = publication.DomainFacts(
                domain="votes",
                acquisition_state=prior_votes.get("acquisition_state") or "not_requested",
                source="bundestag-roll-call",
                records=vote_records,
                reused=vote_records,
                rejected=int(prior_votes.get("rejected") or 0),
                failure_reasons=tuple(prior_votes.get("failure_reasons") or ()),
                acquired_at=prior_votes.get("acquired_at"),
                attempted_at=prior_votes.get("attempted_at"),
                attempted=bool(prior_votes.get("attempted")),
            ).as_dict()
        else:
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
            ).as_dict()
    # With a scan the result of that scan stands as it is (enrich_with_api wrote
    # its state): nothing is merged from the cache and no earlier verification
    # is restored. A scan that failed for a transient reason never gets here
    # when the cache holds votes (write_report_and_page keeps the cached dossier).

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


def keep_cached_dossier_when_votes_failed(
    report: dict[str, Any], existing_report: dict[str, Any] | None, vote_scan_pages: int
) -> None:
    """A vote scan that failed for a transient reason must not replace a cached
    dossier that holds votes.

    The dossier is skipped like any dossier whose refresh failed (the build
    keeps the cached one whole), so a network blip cannot turn verified votes
    into a partial sitting. Without cached votes the failed scan stands.
    """
    if vote_scan_pages == 0 or existing_report is None:
        return
    fresh = (report.get("acquisition") or {}).get("votes") or {}
    cached_votes = any(True for _ in derive.iter_report_votes(existing_report))
    if not cached_votes:
        return
    transient = {"source_unavailable", "source_changed"} & set(fresh.get("failure_reasons") or ())
    if fresh.get("acquisition_state") in {"partial", "failed"} and transient:
        raise dip.DipError(
            f"Roll-call scan failed ({', '.join(sorted(transient))}); keeping the cached dossier with its votes."
        )
    # A scan that reads as complete but attaches no vote at all to a sitting whose
    # cache holds some is more likely a shortened or stale list page than a
    # sitting that lost its votes: keep the cached dossier and say so.
    if fresh.get("acquisition_state") == "complete" and not int(fresh.get("records") or 0):
        raise dip.DipError(
            "Roll-call scan attached no vote although the cached dossier holds some; keeping the cached dossier."
        )


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
    mp_lookup: dict[str, str] | None = None,
    features: Selection | None = None,
    include_dev_view: bool = False,
    summary_max_calls: int = 25,
    summary_timeout: float = 60,
    database_page_href: str | None = None,
    roll_call_page_cache: dict[str, str] | None = None,
    vorgang_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    features = publication_selection()
    # "reuse" is a mode of *this* script, not of the report builder: tell the
    # builder not to call an LLM, then fill summaries in below from the cached
    # report via the summaries component.
    effective_summary_mode = "off" if summary_mode == "reuse" else (
        "auto" if summary_mode == "required" else summary_mode
    )
    xml_sink: dict[str, str] = {}  # the downloaded XML, kept only with an accepted report
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
        roll_call_page_cache=roll_call_page_cache,
        xml_sink=xml_sink,
    )
    report = dip.build_report(args, protocol=protocol)
    keep_cached_dossier_when_votes_failed(report, existing_report, vote_scan_pages)
    if summary_mode in {"auto", "required"}:
        reconcile_generated_and_cached_summaries(report, existing_report)
    # Cached votes carry forward when this run did not scan.
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
    if "text" in xml_sink:
        xml_path = xml_cache_path(output_dir, normalized_document_number(protocol.get("dokumentnummer")))
        xml_path.parent.mkdir(parents=True, exist_ok=True)
        dip.write_text_atomic(xml_path, xml_sink["text"])
    return write_report_files(
        report,
        output_dir,
        mp_lookup,
        features,
        include_dev_view=include_dev_view,
        database_page_href=database_page_href,
        vorgang_cache=vorgang_cache,
    )


# ---------------------------------------------------------------------------
# PAGE: database.html - "Daten"
#
# database.html used to be a browser-side explorer of 12 sample rows per
# table. It is now a download page: a distribution copy of the SQLite store
# (with speeches.paragraphs_json dropped, a duplicate of speeches.text), its
# CSV.gz files, and the SQL "recipes" executed at build time so a visitor can
# copy the SQL, run it against the file they just downloaded, and get the same
# rows. Everything the page shows - sizes, checksums, the Datenstand band, the
# recipe rows, the schema cards - is read from one manifest (datenstand.json)
# built by export_distribution_data(). The page itself never opens the build
# store.
# ---------------------------------------------------------------------------


def _prefix_range(prefix: str) -> tuple[str, str]:
    """Bounds for ``id >= ? AND id < ?``: a prefix match the primary-key index can serve (LIKE cannot)."""
    return prefix, prefix[:-1] + chr(ord(prefix[-1]) + 1)


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
_COLUMN_SOURCE_ABGEORDNETENWATCH = {
    ("mps", "aw_politician_id"),
    ("mps", "profile_url"),
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
#
# The Politikfeld tables are derived by scripts/politikfelder.py from DIP's
# Sachgebiet labels (proceedings.sachgebiet, which is raw DIP data and so stays
# "dip"); no model writes them. vote_proceedings is the same module's choice of
# the Vorgänge a vote is about; proceedings.abstract is DIP's text with the HTML
# stripped, so it stays "dip".
_TABLE_SOURCE_DERIVED = (
    set(registry.REGISTRY_TABLES)
    | {
        "mp_canonical", "datenstand", "speech_rule_inputs", "agenda_item_politikfelder", "vote_politikfelder",
        "vote_proceedings",
    }
    | set(facts.FACTS_TABLES)
)


# The outcome is mostly computed here from the counts (vote_result); only a
# minority is read off bundestag.de's Beschluss text, so the column is derived.
_COLUMN_SOURCE_DERIVED = {
    ("votes", "result_raw"),
    ("votes", "result_source"),
    # Inferred rejection-recommendation semantics and their supporting evidence.
    ("votes", "inverted"),
    ("votes", "inversion_source"),
    ("votes", "inversion_excerpt"),
    # Whether vote_proceedings found the vote's Vorgang (politikfelder.CONTEXT_STATES).
    ("votes", "context_state"),
    # Computed from the counts / the speaker's role when persisting, not read.
    ("vote_fractions", "leading_vote"),
    ("speeches", "sprechrolle"),
    ("speeches", "unattributed_char_count"),
    # The kind is decided by the parser from the sitting's wording and structure.
    ("contributions", "kind"),
    ("contributions", "parent_rede_id"),
    ("contributions", "sprechrolle"),
}


def column_source(table: str, column: str) -> str:
    if table in _TABLE_SOURCE_DERIVED or (table, column) in _COLUMN_SOURCE_DERIVED:
        return "derived"
    if (table, column) in _COLUMN_SOURCE_ABGEORDNETENWATCH:
        return "abgeordnetenwatch"
    if table in _TABLE_SOURCE_BUNDESTAG:
        return "bundestag.de"
    return "dip"


EXPORT_FORMAT = 8
DATA_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SYNTHETIC_REDE_ID_RE = re.compile(r"^[0-9]+:[0-9]+:[0-9]+$")

# All exported primary keys identify stable source rows or issued registry keys.
# The manifest derives their declared order directly from the table schema.

# The row whose name and party r1 and r3 show for a person, chosen once per
# person: a roster row first, then a speaker row, then by identity_key, a source
# key (mps.id is a hash). collect_abgeordnete orders a person's rows the same
# way, so the label is the row the Personenseite takes its heading from.
REPRESENTATIVE_SQL = (
    "WITH representative AS (\n"
    "  SELECT person_id, display_name, party_id FROM (\n"
    "    SELECT person_id, display_name, party_id,\n"
    "           ROW_NUMBER() OVER (PARTITION BY person_id\n"
    "                              ORDER BY is_mdb DESC, xml_redner_id IS NULL, identity_key) AS rank\n"
    "    FROM mps\n"
    "  ) WHERE rank = 1\n"
    ")\n"
)

# The recipes executed at build time against the distribution copy and
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
            REPRESENTATIVE_SQL
            + "SELECT mc.canonical_id AS mp_id, m.display_name, p.name AS fraktion,\n"
            "       COUNT(*) AS reden, SUM(s.char_count) AS zeichen\n"
            "FROM speeches s\n"
            "JOIN mp_canonical mc ON mc.mp_id = s.mp_id\n"
            "JOIN representative m ON m.person_id = mc.canonical_id\n"
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
        "caveat": (
            "Mitglieder der Bundesregierung, Bundesratsmitglieder und weitere Redner in einer Sprechrolle "
            "erscheinen ohne Fraktion."
        ),
    },
    {
        "id": "r2-redeanteil-fraktion",
        "title": "Redeanteil je Fraktion nach Zeichen",
        "sql": (
            "SELECT CASE s.sprechrolle WHEN 'bundesregierung' THEN 'Bundesregierung' WHEN 'bundesrat' THEN 'Bundesrat'\n"
            "                          WHEN 'weitere' THEN 'weitere Sprechrolle'\n"
            "                          ELSE COALESCE(NULLIF(s.fraktion, ''), p.name) END AS fraktion,\n"
            "       COUNT(*) AS reden,\n"
            "       ROUND(100.0 * SUM(s.char_count) / (SELECT SUM(char_count) FROM speeches), 1) AS anteil_prozent\n"
            "FROM speeches s\n"
            "JOIN mps m ON m.id = s.mp_id\n"
            "LEFT JOIN parties p ON p.id = m.party_id\n"
            "GROUP BY 1\n"
            "ORDER BY reden DESC, fraktion\n"
            "LIMIT 5;"
        ),
        "columns": (
            {"name": "fraktion", "align": "text"},
            {"name": "reden", "align": "num"},
            {"name": "anteil_prozent", "align": "num"},
        ),
        "depends_on": None,
        "caveat": (
            "Bundesregierung, Bundesrat und weitere Sprechrollen stehen als eigene Zeilen und zählen im Nenner mit: "
            "alle Zeilen zusammen ergeben 100 %."
        ),
    },
    {
        "id": "r3-abweichler",
        "title": "Wer stimmt am häufigsten anders als die Mehrheit der eigenen Fraktion oder Gruppe?",
        "sql": (
            REPRESENTATIVE_SQL
            + "SELECT mc.canonical_id AS mp_id, m.display_name, p.name AS fraktion,\n"
            "       COUNT(DISTINCT vm.vote_id) AS abweichungen\n"
            "FROM vote_members vm\n"
            "JOIN vote_fractions vf ON vf.vote_id = vm.vote_id AND vf.party_id = vm.party_id\n"
            "JOIN mp_canonical mc ON mc.mp_id = vm.mp_id\n"
            "JOIN representative m ON m.person_id = mc.canonical_id\n"
            "JOIN parties p ON p.id = vm.party_id\n"
            "WHERE vm.vote IN ('yes', 'no')\n"
            "  AND vf.leading_vote IN ('yes', 'no')\n"
            "  AND vm.vote <> vf.leading_vote\n"
            "  AND p.name <> 'fraktionslos'\n"
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
            "SELECT COALESCE(MIN(p.document_number),\n"
            "              (SELECT p2.document_number FROM protocols p2 WHERE p2.id = v.protocol_id)) AS document_number,\n"
            "       v.date, v.title, v.yes_count AS ja, v.no_count AS nein,\n"
            "       ABS(v.yes_count - v.no_count) AS differenz\n"
            "FROM votes v\n"
            "LEFT JOIN agenda_item_votes aiv ON aiv.vote_id = v.id\n"
            "LEFT JOIN agenda_items ai ON ai.id = aiv.agenda_item_id\n"
            "LEFT JOIN protocols p ON p.id = COALESCE(ai.protocol_id, v.protocol_id)\n"
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
    {
        # The same Beschlussempfehlung urheber the vote panels cite
        # (derive.vote_committees), joined by the vote's Drucksache numbers.
        "id": "r6-ausschuss",
        "title": "Aus welchen Ausschüssen kommen die Beschlussempfehlungen namentlicher Abstimmungen?",
        "sql": (
            "SELECT u.value AS beschlussempfehlung_urheber,\n"
            "       COUNT(DISTINCT vd.vote_id) AS abstimmungen\n"
            "FROM vote_documents vd\n"
            "JOIN documents d ON d.id = vd.document_id\n"
            "JOIN json_each(d.origin_json) u\n"
            "WHERE d.document_type LIKE 'Beschlussempfehlung%'\n"
            "  AND d.herausgeber = 'BT'\n"
            "GROUP BY u.value\n"
            "ORDER BY abstimmungen DESC, beschlussempfehlung_urheber\n"
            "LIMIT 5;"
        ),
        "columns": (
            {"name": "beschlussempfehlung_urheber", "align": "text"},
            {"name": "abstimmungen", "align": "num"},
        ),
        "depends_on": "votes",
        "caveat": (
            "Zählt die Abstimmungen, unter deren Drucksachen eine Beschlussempfehlung dieses Ausschusses ist "
            "(Urheber laut DIP). Das zitiert das Dokument und sagt nicht, dass der Ausschuss federführend war: "
            "Eine Abstimmung über einen Entschließungsantrag nennt oft die Beschlussempfehlung zum Gesetz."
        ),
    },
)
RECIPES_BY_ID = {recipe["id"]: recipe for recipe in RECIPES}

_NUMBER_WORDS = ("null", "eine", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun", "zehn", "elf", "zwölf")


def _recipe_count_word() -> str:
    """``len(RECIPES)`` as the German word the Daten page and landing text use."""
    count = len(RECIPES)
    return _NUMBER_WORDS[count] if count < len(_NUMBER_WORDS) else str(count)


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
        "store_schema": pulse_store.SCHEMA_VERSION,
        "key_version": KEY_VERSION,
        "stable_key_policy": "declared-primary-keys",
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


def export_work_dir(exports_dir: Path) -> Path:
    """Where an export holds its lock and builds its files: the private
    directory beside the published tree (``person_registry.private_dir``), so
    nothing half-written or a full store copy is ever inside ``exports_dir``."""
    return registry.private_dir(exports_dir) / "exports"


@contextlib.contextmanager
def _export_lock(work_dir: Path):
    work_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = work_dir / ".lock"
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


# F2.1/F4.1: every export builds in its own scratch directory under the work
# directory, removed in `finally`; whatever a crashed run left there is swept
# before a new export starts.
def _sweep_stale_work(work_dir: Path) -> None:
    for path in work_dir.iterdir():
        if path.name == ".lock":
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
        else:
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


# Build the distribution copy, the CSVs and datenstand.json from the build
# store. Called once per build, from main(), after the store and the MP
# identity mapping are final; render_site() and the page never open the build
# store themselves (eng addendum: "the page ... never opens the build store").
#
# Layout of exports_dir (published):
#   datenstand.json          the manifest; replaced last, the only pointer a
#                            reader needs to follow
#   g-<inputs_hash[:12]>/    one generation's files, renamed in complete; the
#                            previous one is deleted only after datenstand.json
#                            points at the new one
#   published.json           written by the (separate) publish script; never
#   LICENSE-DATA.md          touched by this function
# The lock, the store copies, the temp files and the generation being built
# live in export_work_dir(exports_dir), on the same file system.
def export_distribution_data(
    database_path: Path,
    exports_dir: Path,
    *,
    recipes: tuple[dict[str, Any], ...] = RECIPES,
    mp_lookup: dict[str, str] | None = None,
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

    source = facts.open_readonly(database_path)
    try:
        pulse_store.require_current_schema(source)
        pulse_store.require_current_speech_rules(source)
    finally:
        source.close()
    has_page_ids = set((mp_lookup or {}).values())
    readiness = readiness or {}

    exports_dir.mkdir(parents=True, exist_ok=True)
    work_dir = export_work_dir(exports_dir)
    work_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if work_dir.stat().st_dev != exports_dir.stat().st_dev:
        raise RuntimeError(f"export: {work_dir} and {exports_dir} must be on one file system (the generation is renamed into place)")
    with _export_lock(work_dir):
        # Only the lock holder may sweep: a second build sweeping before it
        # fails on the lock would delete the first build's in-flight files.
        _sweep_stale_work(work_dir)
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
        scratch = Path(tempfile.mkdtemp(dir=work_dir, prefix="export-"))
        gen_dir = scratch / generation
        gen_dir.mkdir()
        published = exports_dir / generation
        aside = scratch / "replaced"
        try:
            manifest = _run_export(
                database_path=database_path,
                gen_dir=gen_dir,
                scratch_dir=scratch,
                recipes=recipes,
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

            manifest_tmp_path = scratch / "datenstand.json"
            manifest_tmp_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            # A forced re-export of unchanged inputs names the published
            # generation again: set it aside for the two renames, not for the
            # whole export.
            if published.exists():
                published.replace(aside)
            gen_dir.replace(published)
            manifest_tmp_path.replace(exports_dir / "datenstand.json")
        except sqlite3.Error as exc:
            # backup()/DROP COLUMN/VACUUM INTO fail with sqlite3 errors on a
            # locked or corrupt store or a full disk; surface them through the
            # CLI's clean "error:" path instead of a traceback.
            raise RuntimeError(f"export: distribution copy failed: {exc}") from exc
        finally:
            if aside.exists() and not published.exists():
                aside.replace(published)
            shutil.rmtree(scratch, ignore_errors=True)

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
    scratch_dir: Path,
    recipes: tuple[dict[str, Any], ...],
    has_page_ids: set[str],
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
    dist_fd, dist_name = tempfile.mkstemp(dir=scratch_dir, prefix="dist-", suffix=".sqlite")
    os.close(dist_fd)
    dist_path = Path(dist_name)
    dist_path.unlink()  # backup() needs a fresh (non-existent or empty) target
    vacuum_fd, vacuum_name = tempfile.mkstemp(dir=scratch_dir, prefix="vacuum-", suffix=".sqlite")
    os.close(vacuum_fd)
    vacuum_path = Path(vacuum_name)
    vacuum_path.unlink()  # VACUUM INTO requires the target to not exist

    dist_conn = sqlite3.connect(dist_path, isolation_level=None)
    dist_conn.row_factory = sqlite3.Row
    source_conn = sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        source_conn.backup(dist_conn)
    except sqlite3.Error:
        dist_conn.close()
        raise
    finally:
        source_conn.close()
    # The manifest's source hash was taken from the file as it was before the
    # copy; a store swapped in meanwhile would be published under that hash.
    after = database_path.stat()
    if (after.st_ino, after.st_size, after.st_mtime_ns) != (source_stat.st_ino, source_stat.st_size, source_stat.st_mtime_ns):
        dist_conn.close()
        raise RuntimeError("export: the build store changed while it was copied; re-run the export")

    try:
        # Direct exports and older SQLite stores may not have been migrated.
        if "paragraphs_json" in {row["name"] for row in dist_conn.execute("PRAGMA table_info(speeches)")}:
            dist_conn.execute("ALTER TABLE speeches DROP COLUMN paragraphs_json")
        dist_conn.execute(
            "CREATE TABLE mp_canonical (mp_id TEXT PRIMARY KEY NOT NULL REFERENCES mps(id), canonical_id TEXT NOT NULL REFERENCES persons(id), has_page INTEGER NOT NULL)"
        )
        # Read from the copy, not the source: another build may have replaced
        # the store since, and the mapping must match the rows it points at.
        mp_rows = [
            (mp_id, canonical_id, 1 if canonical_id in has_page_ids else 0)
            for mp_id, canonical_id in dist_conn.execute("SELECT id, person_id FROM mps ORDER BY id")
        ]
        dist_conn.executemany("INSERT INTO mp_canonical(mp_id, canonical_id, has_page) VALUES (?, ?, ?)", mp_rows)
        violations = dist_conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"export: distribution copy has foreign-key violations: {[tuple(row) for row in violations[:3]]}")
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
            "CREATE TABLE datenstand (tag TEXT PRIMARY KEY NOT NULL, export_format INTEGER, license TEXT, schema_hash TEXT, source_sha256 TEXT)"
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
                "stable_keys": [column["name"] for column in sorted(table["columns"], key=lambda col: col["pk"]) if column["pk"]],
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
    mp_lookup: dict[str, str],
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
    mp_lookup: dict[str, str],
    document_numbers: set[str],
    bill_slugs: set[str],
) -> str:
    blocks = []
    for recipe_row in manifest["recipes"]:
        # validate_manifest (an override) or the export itself (this build's
        # manifest) guarantees every id is a local recipe with the same SQL.
        recipe = RECIPES_BY_ID[recipe_row["id"]]
        columns = recipe["columns"]
        visible_columns = [column for column in columns if not column.get("hidden")]
        rows = recipe_row["rows"]
        if not rows:
            body = f'<p class="recipe-empty">{pulse_html.esc(recipe_row.get("empty_reason") or "keine Daten in diesem Build")}</p>'
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
                    if column["name"] == "erste_drucksache":
                        # r5 selects protocols.document_number despite this export column's name.
                        text_value = f"BT-PlPr. {text_value}"
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
                  <caption class="visually-hidden">{pulse_html.esc(recipe['title'])}</caption>
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
                <h3 id="{title_id}">{pulse_html.esc(recipe['title'])}</h3>
                <pre><code>{pulse_html.esc(recipe['sql'])}</code></pre>
                <button type="button" class="recipe-copy" aria-live="polite" hidden>Kopieren</button>
              </div>
              <div class="recipe-result">
                {body}
                {caveat}
              </div>
            </section>
            """
        )
    return "".join(blocks)


# Rendered without JS as hidden ("no dead button shows without JS") and
# revealed once this script has wired up a click handler for it. One script
# tag for all recipe buttons, next to the markup it controls rather than
# folded into page_scripts (shared by every page, most of which have none).
def recipe_copy_runtime_script() -> str:
    return """
  <script>
    (() => {
      const buttons = document.querySelectorAll(".recipe-copy");
      if (!buttons.length) return;
      const clipboardAvailable = !!(navigator.clipboard && window.isSecureContext);
      // Page-wide, bumped on every copy click: a clipboard write that fails
      // late (e.g. behind a permission prompt) must not select its SQL over
      // a newer click or a selection the reader made in the meantime.
      let latestCopy = 0;

      buttons.forEach((button) => {
        const sqlBlock = button.closest(".recipe-sql");
        const code = sqlBlock && sqlBlock.querySelector("pre code");
        if (!code) return;
        const defaultLabel = button.textContent;
        let resetTimer = null;

        const flash = (label) => {
          if (resetTimer) window.clearTimeout(resetTimer);
          button.textContent = label;
          resetTimer = window.setTimeout(() => {
            button.textContent = defaultLabel;
            resetTimer = null;
          }, 2000);
        };

        // Non-secure contexts (e.g. a page opened straight off disk, no
        // server) have no navigator.clipboard at all; select the SQL text
        // instead so Cmd/Ctrl+C still works, and never fall back to the
        // deprecated document.execCommand.
        const selectFallback = () => {
          const range = document.createRange();
          range.selectNodeContents(code);
          const selection = window.getSelection();
          if (selection) {
            selection.removeAllRanges();
            selection.addRange(range);
          }
          flash("Markiert – mit ⌘C/Strg+C kopieren");
        };

        button.addEventListener("click", () => {
          const copy = ++latestCopy;
          if (!clipboardAvailable) {
            selectFallback();
            return;
          }
          const selection = window.getSelection();
          const selectionAtClick = Array.from({ length: selection ? selection.rangeCount : 0 }, (_, i) => {
            const range = selection.getRangeAt(i);
            return [range.startContainer, range.startOffset, range.endContainer, range.endOffset];
          });
          navigator.clipboard.writeText(code.textContent).then(
            () => {
              if (copy === latestCopy) flash("Kopiert");
            },
            () => {
              if (copy !== latestCopy) return;
              const current = window.getSelection();
              const untouched = (current ? current.rangeCount : 0) === selectionAtClick.length &&
                selectionAtClick.every(([startContainer, startOffset, endContainer, endOffset], i) => {
                  const range = current.getRangeAt(i);
                  return range.startContainer === startContainer && range.startOffset === startOffset &&
                    range.endContainer === endContainer && range.endOffset === endOffset;
                });
              if (untouched) selectFallback();
              else flash("Nicht kopiert");
            },
          );
        });

        button.hidden = false;
      });
    })();
  </script>
"""


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
    .recipe-copy {
      appearance:none;
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-height:36px;
      margin-top:8px;
      padding:6px 12px;
      border:1px solid var(--line);
      border-radius:6px;
      background:var(--panel);
      color:var(--blue);
      font:inherit;
      font-size:13px;
      font-weight:650;
      cursor:pointer;
    }
    .recipe-copy[hidden] { display:none; }
    .recipe-copy:hover { border-color:var(--blue); }
    .recipe-copy:focus-visible { outline:2px solid var(--blue); outline-offset:2px; }
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
      .site-header, .download-panel, .recipe-copy { display:none; }
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
    mp_lookup: dict[str, str] | None = None,
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
        <span class="eyebrow">{_recipe_count_word().capitalize()} Abfragen</span>
        <h2>Rezepte</h2>
        <p class="lede">Diese {_recipe_count_word()} SQL-Abfragen laufen bei jedem Build gegen die Verteilkopie; ihre Ergebniszeilen stehen rechts daneben. Wer die Datei herunterlädt und die SQL <a href="#loslegen">lokal aus</a>führt, bekommt dieselben Zeilen.</p>
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
# CSV alternative: pd.read_csv("speeches-local.csv.gz", keep_default_na=False, dtype={{"mp_id": "string"}})</code></pre>
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
  {recipe_copy_runtime_script()}
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
# PAGE: index.html - direct routes to the latest available sitting and week
# ---------------------------------------------------------------------------


def render_landing_page(
    entries: list[dict[str, Any]],
    *,
    database_page_href: str | None = None,
    data_stand: str | None = None,
    features: Selection | None = None,
    today: date | datetime | None = None,
    week: tuple[int, int] | None = None,
) -> str:
    """Homepage periods use the same generated entries and selection as puls.html."""
    features = features or publication_selection()
    today = resolve_today(today)
    selected_week, weeks = select_pulse_week(entries, week)
    esc = pulse_html.esc
    recovery = '<a class="home-action" href="overview.html">Sitzungen ansehen &rarr;</a>'
    if entries:
        latest = max(entries, key=entry_sort_key)
        protocol = entry_protocol(latest)
        datum = protocol.get("datum")
        dated = pulse_html.format_date(datum) if pulse_html.iso_week_key(datum) else ""
        sitting = f"""
          <p class="home-meta">Zuletzt verfügbar · Protokoll {esc(sitting_label(latest))}</p>
          <p>{time_html(datum, dated) if dated else 'Sitzungsdatum nicht verfügbar'}</p>
          <p>Tagesordnung, Reden und vorliegende Abstimmungen der zuletzt verfügbaren Sitzung.</p>
          <a class="home-action" href="{esc(dossier_href(latest))}">Sitzungsprotokoll öffnen &rarr;</a>"""
    else:
        sitting = f'<p>Noch kein Sitzungsprotokoll verfügbar</p>{recovery}'

    week_heading = "Ausgewählte Woche" if week is not None else "Wochenübersicht"
    if selected_week is None:
        weekly = f'<p>Noch keine Woche auswertbar</p>{recovery}'
    else:
        week_entries = weeks[selected_week]
        monday = date.fromisocalendar(*selected_week, 1)
        sunday = monday + timedelta(days=6)
        period = " – ".join(time_html(d.isoformat(), pulse_html.format_date(d.isoformat())) for d in (monday, sunday))
        count = pulse_html.format_count(len(week_entries), "Sitzung", "Sitzungen")
        coverage = "bisher erfasst" if monday <= today <= sunday else "erfasst"
        earlier = [key for key in weeks if key < selected_week]
        comparison = bool(earlier and pulse_html.week_span(max(earlier), selected_week) <= pulse_html.MAX_WEEK_GAP)
        description = "Themen und Redeanteile der ausgewählten Woche" if week is not None else "Themen und Redeanteile der zuletzt erfassten Woche"
        if comparison:
            description += ", mit Vergleich zur vorherigen erfassten Woche"
        action = "Wochenübersicht und Vergleich öffnen" if comparison else "Wochenübersicht öffnen"
        undated = len(entries) - sum(len(bucket) for bucket in weeks.values())
        missing = f'<p class="home-meta">{pulse_html.format_count(undated, "Sitzung", "Sitzungen")} ohne Datum nicht berücksichtigt</p>' if undated else ""
        weekly = f"""
          <p class="home-meta">{esc(pulse_html.week_label(selected_week))} · {esc(count)} {coverage}</p>
          <p>{period}</p>
          <p>{esc(description)}.</p>
          {missing}
          <a class="home-action" href="puls.html">{action} &rarr;</a>"""

    areas = [
        ("Sitzungen", "overview.html", "Sitzungsprotokolle und verfügbare Auswertungen im Archiv."),
        ("Abstimmungen", "votes/index.html", "Namentliche Abstimmungen, Ergebnisse und einzelne Stimmen."),
        ("Gesetzesvorhaben", "bills/index.html", "Beratungen im Plenum, Drucksachen und Verfahrensschritte zu einem Vorhaben."),
        ("Abgeordnete", "abgeordnete/index.html", "Reden und erfasste Abstimmungen einzelner Abgeordneter."),
        ("Fakten", "fakt/index.html", "Auswertungen zu Wochen und Monaten mit ihren Belegen."),
    ]
    rows = "".join(
        f'<li><h3><a href="{esc(href)}">{esc(title)} &rarr;</a></h3><p>{esc(description)}</p></li>'
        for title, href, description in areas
    )
    data = ""
    if database_page_href:
        meta = f'<p class="home-meta">{esc(data_stand)}</p>' if data_stand else ""
        data = f'<li><h3><a href="{esc(database_page_href)}">Daten</a></h3><p>Downloads, Datenstand und {_recipe_count_word()} geprüfte SQL-Abfragen zu Personen, Reden, Vorgängen, Abstimmungen und Ausschüssen.</p>{meta}</li>'

    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Debatten und Entscheidungen im Bundestag</title>
  {pulse_html.page_head(features)}
  <style>
    :root {{
      --ink:#171a1f; --muted:#606a78; --line:#d9dee6; --paper:#f7f8fa;
      --panel:#ffffff; --blue:#174ea6; --teal:#0f766e; --blue-soft:#eef5ff;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:var(--ink); background:var(--paper); }}
    a {{ color:var(--blue); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .shell {{ max-width:1180px; margin:0 auto; padding:22px 22px 48px; }}
    {pulse_html.global_header_styles()}
    .home-intro {{ padding:24px 0; }}
    .home-intro h1 {{ margin:0; max-width:900px; font-size:46px; line-height:1.05; font-weight:820; letter-spacing:-.02em; }}
    main p {{ margin:12px 0; font-size:16px; line-height:1.55; color:var(--muted); }}
    .home-periods {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:30px; }}
    .home-periods section, .home-section {{ padding:24px 0; border-top:1px solid var(--line); }}
    main h2 {{ margin:0 0 16px; font-size:26px; font-weight:780; letter-spacing:-.01em; }}
    .home-action, .home-rows a {{ display:inline-flex; align-items:center; min-height:44px; font-weight:750; }}
    main .home-meta {{ font-size:12px; }}
    .home-rows {{ list-style:none; padding:0; margin:0; }}
    .home-rows li {{ padding:16px 0; border-bottom:1px solid var(--line); }}
    .home-rows h3 {{ margin:0; font-size:20px; }}
    .home-rows p {{ margin:0; }}
    footer {{ margin-top:24px; padding-top:20px; border-top:1px solid var(--line); color:var(--muted); font-size:12px; line-height:1.6; }}
    @media (max-width:1023px) {{ .home-periods {{ grid-template-columns:1fr; gap:0; }} }}
    @media (max-width:600px) {{
      .shell {{ padding:16px 14px 40px; }}
      .home-intro h1 {{ font-size:34px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(features=features)}
    <main>
      <header class="home-intro">
        <h1>Debatten und Entscheidungen im Bundestag</h1>
        <p>Sitzungsprotokolle, Themen der Woche und Abstimmungen aus offiziellen Quellen.</p>
      </header>
      <div class="home-periods">
        <section aria-labelledby="latest-sitting"><h2 id="latest-sitting">Letzte Sitzung</h2>{sitting}</section>
        <section aria-labelledby="selected-week"><h2 id="selected-week">{week_heading}</h2>{weekly}</section>
      </div>
      <section class="home-section" aria-labelledby="other-areas">
        <h2 id="other-areas">Weitere Bereiche</h2><ul class="home-rows">{rows}</ul>
      </section>
      <section class="home-section" aria-labelledby="sources-data">
        <h2 id="sources-data">Quellen und Daten</h2>
        <ul class="home-rows"><li><h3><a href="sources.html">Quellen und Methode &rarr;</a></h3>
        <p>Offizielle Quellen, Verarbeitung und Grenzen der Auswertungen.</p></li>{data}</ul>
      </section>
    </main>
    <footer>Statischer Prototyp · Bundestag-Puls. Das XML-Protokoll ist maßgeblich; DIP-API-Daten ergänzen jede Sitzung. Datenquellen und Methode sind unter <a href="sources.html">Quellen</a> dokumentiert.</footer>
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
            anchor = f"top-{pulse_html.esc(first_index)}" if first_index is not None else "sitting-votes"
            href = f"protocols/{pulse_html.esc(Path(page_path).name)}#{anchor}"
            rows.append(
                f'<li class="vote-row"><a href="{href}">{pulse_html.esc(label)} · '
                f"{pulse_html.format_count(n, 'Abstimmung', 'Abstimmungen')}</a></li>"
            )
        body = f'<p class="week-text">{pulse_html.esc(sentence)}</p><ul class="week-list">{"".join(rows)}</ul>'
    else:
        body = (
            '<p class="week-text">Keine namentlichen Abstimmungen in dieser Woche erfasst.</p>'
            f'<a class="feature-link" href="{newest_href}">Sitzungsbelege pr&uuml;fen</a>'
        )
    return f"""
        <article class="week-card votes-card" id="abstimmungen">
          <span class="eyebrow">Erfasst</span>
          <h3>Namentliche Abstimmungen</h3>
          {body}
        </article>"""


# ---------------------------------------------------------------------------
# PAGE: votes/index.html - every roll-call vote across every sitting
#
# Reverse-chronological, grouped by month, with client-side Fraktion chips.
# Row rendering (badge, linked Drucksachen) reuses features.votes rather than
# forking the dossier panel's markup.
# ---------------------------------------------------------------------------


def _vote_procedure_type(
    vote: dict[str, Any], item: dict[str, Any] | None, sitting_documents: dict[str, Any]
) -> str:
    """The DIP type of the first of the vote's Drucksachen its TOP links; else of the
    first the sitting links under any TOP (``derive.report_drucksachen``, the map the
    committee line reads, D4), which also serves a vote under no TOP; else "–"."""
    numbers = {str(number) for number in vote.get("document_numbers") or []}
    for doc in ((item or {}).get("api") or {}).get("linked_drucksachen") or []:
        if str(doc.get("dokumentnummer")) in numbers and doc.get("drucksachetyp"):
            return str(doc["drucksachetyp"])
    for raw in vote.get("document_numbers") or []:
        doc = sitting_documents.get(derive.canonical_document_number(raw))
        if doc and doc.get("drucksachetyp"):
            return str(doc["drucksachetyp"])
    return "–"


def _abweichler_count(vote: dict[str, Any]) -> int | None:
    """The vote's Abweichler, or None unless every group's member rows are complete."""
    groups = derive.vote_abweichler(vote)
    if not groups or any(group["state"] != "complete" for group in groups.values()):
        return None
    return sum(len(group["members"]) for group in groups.values())


def _fraction_position(fraction: dict[str, Any], inverted: bool = False) -> str | None:
    # The "Ja-Mehrheit" chip needs Ja from more than half of the votes cast
    # (Ja + Nein + Enthaltung): a Mehrheitsvotum of Ja alone would also match a
    # plurality (40 Ja, 35 Nein, 25 Enthaltungen). That is a stricter test than
    # the Mehrheitsvotum, not a second definition of it: a Zusammenschluss with
    # no Mehrheitsvotum (a tie, or nobody voted) has no position and no chip.
    # For rejection recommendations, Nein support uses the same >50% test.
    counts = fraction.get("counts") or {}
    if inverted:
        position = derive.fraction_position(counts, True)
        if position == "für den Antrag":
            yes, no, abstain = (int(counts.get(key) or 0) for key in derive.MAJORITY_KEYS)
            return position if no > yes + abstain else "geteilt"
        return position
    leading = derive.majority_vote(counts)
    if leading != "yes":
        return leading
    yes, no, abstain = (int(counts.get(key) or 0) for key in derive.MAJORITY_KEYS)
    return "yes" if yes > no + abstain else "tie"


def _vote_id_sort_key(vote_id: Any) -> tuple[int, str]:
    # bundestag.de roll-call ids are integers of varying width; compare them
    # numerically so "10" sorts after "9" on the same date.
    text = str(vote_id or "")
    return (int(text), "") if text.isdigit() else (-1, text)


def collect_votes_archive(
    entries: list[dict[str, Any]], vorgang_cache: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Every roll-call vote across every dossier, one row per unique vote id.

    A vote can attach to two agenda items (pulse_html.vote_key handles the
    dedupe, same rule week_stats uses for the Wochenvergleich vote count). Each
    row carries the vote's Politikfelder, derived from ``vorgang_cache`` the way
    persist derives the stored ones.
    """
    cache = vorgang_cache or politikfelder.empty_cache()
    rows: dict[str, dict[str, Any]] = {}
    for entry in entries:
        report = entry.get("report") or {}
        page_path = entry.get("page_path")
        _, vote_politikfelder = politikfelder.report_politikfelder(report, cache)
        sitting_documents = derive.report_drucksachen(report)
        page_href = f"../protocols/{pulse_html.esc(Path(page_path).name)}" if page_path else None
        for item, vote in derive.iter_report_votes(report):
            key = pulse_html.vote_key(vote)
            if key in rows:
                continue
            fraction_positions = {
                fraction["name"]: position
                for fraction in derive.merge_fractions(vote.get("fractions"))
                if (position := _fraction_position(fraction, vote.get("inverted") is True)) is not None
            }
            rows[key] = {
                "vote": vote,
                "politikfelder": politikfelder.shown(vote_politikfelder[politikfelder.vote_key(vote)]),
                "document_links": votes_feature.document_source_links(item) if item else {},
                "document_chambers": votes_feature.document_source_chambers(item) if item else {},
                "fraction_positions": fraction_positions,
                "procedure_type": _vote_procedure_type(vote, item, sitting_documents),
                "abweichler": _abweichler_count(vote),
                # The vote's own panel (D9).
                "href": f"{page_href}#{pulse_html.esc(votes_feature.vote_anchor_id(vote))}" if page_href else None,
            }
    return sorted(
        rows.values(),
        key=lambda row: (row["vote"].get("date") or "", _vote_id_sort_key(row["vote"].get("id"))),
        reverse=True,
    )


def _month_label(date_iso: str | None) -> str:
    match = re.match(r"(\d{4})-(\d{2})", date_iso or "")
    if not match:
        return "Unbekanntes Datum"
    year, month = match.groups()
    if not 1 <= int(month) <= 12:
        return "Unbekanntes Datum"
    return facts.month_display(f"{year}-{month}")


def render_votes_archive_index(rows: list[dict[str, Any]], features: Selection | None = None) -> str:
    features = features or publication_selection()
    fraktion_names = sorted(
        {name for row in rows for name in row["fraction_positions"]},
        key=lambda value: (value == "fraktionslos", value),
    )
    chips = "".join(
        f'<button type="button" class="chip" aria-pressed="false" data-fraktion-chip="{pulse_html.esc(name)}">{pulse_html.esc(name)}</button>'
        for name in fraktion_names
    )

    present = {tag for row in rows for tag in row["politikfelder"]}
    feld_chips = "".join(
        f'<button type="button" class="chip" aria-pressed="false" data-politikfeld-chip="{pulse_html.esc(name)}">{pulse_html.esc(name)}</button>'
        for name in politikfelder.POLITIKFELDER
        if name in present
    )
    if feld_chips and politikfelder.UNTAGGED in present:
        feld_chips += (
            '<button type="button" class="chip" aria-pressed="false" '
            f'data-politikfeld-chip="{politikfelder.UNTAGGED}">Ohne Politikfeld</button>'
        )

    current_month = None
    items = []
    for row in rows:
        vote = row["vote"]
        month = _month_label(vote.get("date"))
        if month != current_month:
            items.append(f'<h2 class="archive-month" data-month="{pulse_html.esc(month)}">{pulse_html.esc(month)}</h2>')
            current_month = month
        badge_html = votes_feature.render_result_badge(vote)
        docs_html = votes_feature.render_document_links(vote.get("document_numbers") or [], row["document_links"], row.get("document_chambers"))
        title = vote.get("title") or vote.get("topic") or "Ohne Titel"
        title_html = f'<a href="{row["href"]}">{pulse_html.esc(title)}</a>' if row["href"] else pulse_html.esc(title)
        positions_json = json.dumps(row["fraction_positions"], ensure_ascii=False)
        # Counted only where every group's Einzelstimmen are complete, so a
        # missing badge never stands for zero (plan Slice 1).
        abweichler = row.get("abweichler")
        abweichler_attr = f' data-abweichler="{pulse_html.esc(abweichler)}"' if abweichler is not None else ""
        abweichler_html = (
            f' · <span class="archive-abweichler">{pulse_html.esc(pulse_html.format_count(abweichler, "stimmt", "stimmen"))}'
            " anders als die Mehrheit der eigenen Fraktion oder Gruppe</span>"
            if abweichler
            else ""
        )
        items.append(
            f'<article class="archive-row" data-row data-month="{pulse_html.esc(month)}"{abweichler_attr}'
            f' data-fraktion-positions=\'{pulse_html.esc(positions_json)}\''
            f' data-politikfelder=\'{pulse_html.esc(json.dumps(row["politikfelder"], ensure_ascii=False))}\'>'
            f'<time>{pulse_html.esc(vote.get("date"))}</time>'
            f'<div class="archive-row-body"><h3>{title_html}{badge_html}</h3>'
            f'<p>{pulse_html.esc(row["procedure_type"])}{" · Drucksachen " + docs_html if docs_html else ""}{abweichler_html}</p>'
            f'{pulse_html.render_politikfeld_tags(row["politikfelder"])}</div>'
            "</article>"
        )

    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls &middot; Abstimmungen</title>
  {pulse_html.page_head(features)}
  <style>{votes_archive_styles()}</style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(depth=1, active="votes", features=features)}
    <header class="page-header">
      <div>
        <h1>Abstimmungen</h1>
        <p>Jede namentliche Abstimmung aus den erzeugten Plenarprotokoll-Dossiers, neueste zuerst.</p>
      </div>
    </header>
    <p class="archive-count" data-archive-count data-total="{pulse_html.esc(len(rows))}" aria-live="polite"><strong>{pulse_html.esc(len(rows))}</strong> Abstimmungen</p>
    {'<section class="archive-filters" aria-label="Nach Politikfeld filtern"><span class="eyebrow">Nach Politikfeld</span><p>Das Politikfeld folgt dem DIP-Sachgebiet des Vorgangs, zu dem die Abstimmung gehört.</p><div class="chip-row">' + feld_chips + '</div></section>' if feld_chips else ''}
    {'<section class="archive-filters" aria-label="Nach Fraktion filtern"><span class="eyebrow">Nach Fraktion (Ja-Mehrheit)</span><p>Zeigt Abstimmungen mit einer Ja-Mehrheit der gewählten Fraktion. Bei Ablehnungsempfehlungen zählt stattdessen die Nein-Mehrheit als Unterstützung des Antrags.</p><div class="chip-row">' + chips + '</div></section>' if chips else ''}
    <section class="archive-list" data-archive>
      {''.join(items) if items else '<p>In den erzeugten Dossiers wurden noch keine namentlichen Abstimmungen erkannt.</p>'}
      <p class="archive-empty" data-no-results hidden>Keine Abstimmungen f&uuml;r die gew&auml;hlte Auswahl.</p>
    </section>
    <footer>Die Liste umfasst die Dossiers, die in diesem Build mit --detail-limit erzeugt wurden. <a href="../overview.html">Plenarprotokoll-Katalog</a> &middot; <a href="../sources.html">Quellen und Methode</a></footer>
  </div>
  {render_votes_archive_script()}
  {pulse_html.page_scripts(features)}
</body>
</html>
"""


def votes_archive_styles() -> str:
    return bill_styles() + """
    .archive-count { margin:16px 0 0; color:var(--muted); font-size:14px; }
    .archive-count strong { color:var(--ink); font-size:18px; }
    .archive-filters { margin-top:20px; }
    .chip-row { display:flex; flex-wrap:wrap; gap:8px; margin-top:8px; }
    .chip {
      min-height:30px;
      padding:4px 11px;
      border:1px solid var(--line);
      border-radius:999px;
      background:var(--panel);
      color:#333a45;
      font:inherit;
      font-size:13px;
      font-weight:650;
      cursor:pointer;
    }
    .chip.is-active { border-color:var(--blue); background:#eef5ff; color:var(--blue); }
    .chip:focus-visible { outline:2px solid var(--blue); outline-offset:2px; }
    @media (pointer:coarse) {
      .chip { min-height:44px; }
    }
    :root[data-theme="dark"] .chip { color:var(--ink); }
    :root[data-theme="dark"] .chip.is-active { background:var(--surface-2); color:var(--blue); }
    .archive-list { margin-top:20px; display:grid; gap:10px; }
    .archive-month { margin:18px 0 4px; font-size:15px; color:var(--muted); }
    .archive-row {
      display:grid;
      grid-template-columns:110px minmax(0,1fr);
      gap:14px;
      padding:12px;
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel);
    }
    .archive-row[hidden], .archive-month[hidden] { display:none; }
    .archive-row time { color:var(--muted); font-size:13px; }
    .archive-row-body h3 { margin:0 0 4px; font-size:15px; overflow-wrap:break-word; }
    .archive-row-body p { margin:0; font-size:13px; color:var(--muted); }
    .archive-empty { margin-top:16px; color:var(--muted); }
    .archive-abweichler { color:var(--ink); font-weight:650; }
""" + pulse_html.VOTE_RESULT_BADGE_CSS + pulse_html.DOC_LINK_CSS + pulse_html.POLITIKFELD_CHIP_CSS + """
    @media (max-width: 640px) {
      /* minmax(0, ...): a long title or chip wraps instead of widening the page. */
      .archive-row { grid-template-columns:minmax(0,1fr); gap:4px; }
    }
"""


# Inline script for votes/index.html: toggles the Fraktion and Politikfeld chips
# (multi-select within a group, both groups must match). A row shows when an
# active Fraktion supported the Vorlage (for an inverted recommendation, support
# for the Antrag comes from Nein) and when one of its Politikfelder is active.
# ``?politikfeld=Migration`` (repeatable) activates a Politikfeld chip on load, so
# a link from another page can open the archive already filtered.
def render_votes_archive_script() -> str:
    return """
  <script>
    (() => {
      const container = document.querySelector('[data-archive]');
      if (!container) return;
      const rows = Array.from(container.querySelectorAll('[data-row]')).map((row) => {
        let positions = {};
        let felder = [];
        try {
          positions = JSON.parse(row.dataset.fraktionPositions || '{}');
        } catch (err) {
          positions = {};
        }
        try {
          felder = JSON.parse(row.dataset.politikfelder || '[]');
        } catch (err) {
          felder = [];
        }
        return { row, positions, felder, month: row.dataset.month };
      });
      const headings = Array.from(container.querySelectorAll('h2[data-month]'));
      const groups = [
        { chips: Array.from(document.querySelectorAll('[data-fraktion-chip]')), key: 'fraktionChip', active: new Set() },
        { chips: Array.from(document.querySelectorAll('[data-politikfeld-chip]')), key: 'politikfeldChip', active: new Set() },
      ];
      const [fraktion, feld] = groups;
      const noResults = document.querySelector('[data-no-results]');
      const count = document.querySelector('[data-archive-count]');
      const apply = () => {
        let visible = 0;
        const visibleMonths = new Set();
        const fraktionList = Array.from(fraktion.active);
        const feldList = Array.from(feld.active);
        rows.forEach(({ row, positions, felder, month }) => {
          const fraktionOk = fraktionList.length === 0 || fraktionList.some((name) =>
            positions[name] === 'yes' || positions[name] === 'für den Antrag'
          );
          const feldOk = feldList.length === 0 || feldList.some((name) => felder.includes(name));
          const show = fraktionOk && feldOk;
          row.hidden = !show;
          if (show) {
            visible += 1;
            visibleMonths.add(month);
          }
        });
        headings.forEach((heading) => {
          heading.hidden = !visibleMonths.has(heading.dataset.month);
        });
        const filtering = fraktion.active.size + feld.active.size > 0;
        if (noResults) noResults.hidden = visible !== 0 || !filtering;
        if (count) {
          const total = count.dataset.total;
          count.innerHTML = !filtering
            ? `<strong>${total}</strong> Abstimmungen`
            : `<strong>${visible}</strong> von ${total} Abstimmungen`;
        }
        groups.forEach(({ chips, key, active }) => chips.forEach((chip) => {
          const on = active.has(chip.dataset[key]);
          chip.classList.toggle('is-active', on);
          chip.setAttribute('aria-pressed', on ? 'true' : 'false');
        }));
      };
      groups.forEach(({ chips, key, active }) => chips.forEach((chip) => {
        chip.addEventListener('click', () => {
          const value = chip.dataset[key];
          if (active.has(value)) {
            active.delete(value);
          } else {
            active.add(value);
          }
          apply();
        });
      }));
      try {
        const known = new Set(feld.chips.map((chip) => chip.dataset.politikfeldChip));
        new URLSearchParams(window.location.search).getAll('politikfeld').forEach((name) => {
          if (known.has(name)) feld.active.add(name);
        });
      } catch (err) {
        // A URL the browser cannot parse leaves the list unfiltered.
      }
      apply();
    })();
  </script>
"""


def write_votes_archive_page(
    output_dir: Path,
    rows: list[dict[str, Any]],
    features: Selection | None = None,
) -> dict[str, Any]:
    features = features or publication_selection()
    votes_dir = output_dir / "votes"
    votes_dir.mkdir(parents=True, exist_ok=True)
    (votes_dir / "index.html").write_text(render_votes_archive_index(rows, features), encoding="utf-8")
    return {"count": len(rows), "index_path": votes_dir / "index.html"}


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
            "Für einen Wochenvergleich braucht es zwei Wochen mit Sitzung, die höchstens "
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
              </div>"""
                )
            cards = f"""
      <div class="week-grid">
        <article class="week-card">
          <h3>Wochenpuls</h3>
          <div class="week-metrics">{"".join(metric_cells)}</div>
          <p class="week-note">Diese Woche; ein Vergleichswert folgt mit der n&auml;chsten Woche mit Sitzung.</p>
        </article>
        <article class="week-card">
          <h3>Redeanteil der Fraktionen</h3>
          {pulse_html.render_share_shift(current_stats["party_counts"], None, show_deltas=False)}
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
        previous_figure = (
            f'<em>{pulse_html.esc(previous["label"])}: {week_figure(metric["previous"])}</em>'
            if metric["previous"] is not None else ""
        )
        metric_cells.append(
            f"""
              <div class="week-metric">
                <span>{pulse_html.esc(metric["label"])}</span>
                <strong>{week_figure(metric["current"])}</strong>
                <div class="week-metric-foot">
                  {pulse_html.render_delta(metric["delta_percent"], "%")}
                  {previous_figure}
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
            f"{len(returning)} von {len(current['vorgang_ids'])} Vorgängen dieser Woche "
            "standen schon in einer früheren Woche mit Sitzung auf der Tagesordnung."
        )
        if len(shown) < len(returning):
            returning_note += f" Angezeigt sind die {len(shown)} zuletzt fortgesetzten."
    else:
        returning_html = ""
        returning_note = (
            "Kein Vorgang dieser Woche stand zuvor schon einmal auf der Tagesordnung "
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
        spark_note = "Verlauf aller Sitzungstage: Reden je Woche mit Sitzung"
    elif basis is None:
        sittings_note += " Kein gemeinsamer Sitzungstag; kein Wochenpuls- oder Redeanteil-Vergleich."
        share_note = "Anteil an allen Reden dieser Woche; kein gemeinsamer Sitzungstag f&uuml;r einen Vergleich."
        spark_note = "Reden je Woche mit Sitzung"
    else:
        share_note = (
            "Anteil an allen Reden der Woche, Ver&auml;nderung in Prozentpunkten "
            f"gegen&uuml;ber {pulse_html.esc(previous['label'])}."
        )
        spark_note = "Reden je Woche mit Sitzung"
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
          <p class="week-note">{pulse_html.esc(spark_note)}, letzte {pulse_html.format_count(len(points), "Woche mit Sitzung", "Wochen mit Sitzung")} bis {pulse_html.esc(current["label"])}.</p>
        </article>
        <article class="week-card">
          <h3>Redeanteil der Fraktionen</h3>
          {pulse_html.render_share_shift(compared_current["party_counts"], compared_previous["party_counts"] if basis else None)}
          <p class="week-note">{share_note}</p>
        </article>
        <article class="week-card">
          <h3>Debattenprofil</h3>
          {pulse_html.render_type_mix(current["vorgangstyp_counts"], previous["vorgangstyp_counts"])}
          <p class="week-note">Je Kalenderwoche zählt jeder Tagesordnungspunkt einmal pro vorkommendem Vorgangstyp; Veränderung gegenüber {pulse_html.esc(previous["label"])}. <a href="sources.html#{pulse_html.VORGANGSTYP_GLOSSARY_ANCHOR}">Was die Typen bedeuten</a></p>
        </article>
        <article class="week-card">
          <h3>Wieder auf der Tagesordnung</h3>
          {returning_html}
          <p class="week-note">{pulse_html.esc(returning_note)}</p>
        </article>{votes_card}
      </div>
    </section>
"""


# ---------------------------------------------------------------------------
# Build clock and week selection for puls.html.
#
# The homepage and puls.html describe periods using the same build clock
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


#: Past this many ISO weeks the shown week is flagged beside the h1, not only in
#: the facts line: a gap of up to four weeks is an ordinary sitting break.
STALE_AFTER_WEEKS = 4


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
    "Stand: ..."; anything older leads with its age ("Letzte Woche mit
    Sitzung: vor N Wochen"), and past STALE_AFTER_WEEKS the age moves to a
    "Nicht aktuell" flag after the h1 (`stale`, the age in weeks, else None). Returns
    {"eyebrow", "h1", "facts", "running", "warning", "stale"}; `facts` is HTML
    with every date in a <time> element.
    """
    label = pulse_html.week_label(week)
    monday = date.fromisocalendar(week[0], week[1], 1)
    sunday = monday + timedelta(days=6)
    running = monday <= today <= sunday
    warning = None
    if today < monday:
        warning = "warning: [puls] Auswertung liegt vor der ausgewählten Woche"

    counts = (
        f"{pulse_html.format_count(stats['speech_count'], 'Rede', 'Reden')} in "
        f"{pulse_html.format_count(stats['top_count'], 'Tagesordnungspunkt', 'Tagesordnungspunkten')}"
    )
    sittings = pulse_html.format_count(stats["sitting_count"], "Sitzung", "Sitzungen")
    clock = time_html(today.isoformat(), pulse_html.format_date(today.isoformat()))

    if running:
        return {
            "eyebrow": "Wochenübersicht",
            "h1": f"Was der Bundestag in {label} bisher verhandelt hat",
            "facts": f"{counts} · Stand {clock}: {sittings} erfasst, Woche l&auml;uft",
            "running": True,
            "warning": warning,
            "stale": None,
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
            "eyebrow": "Wochenübersicht",
            "h1": f"Was der Bundestag in {label} verhandelt hat",
            "facts": f"{counts} · Stand: {sittings}, {latest} · {clock}",
            "running": False,
            "warning": warning,
            "stale": None,
        }
    if age > STALE_AFTER_WEEKS:
        # The flag beside the h1 carries the age; the facts line does not repeat it.
        return {
            "eyebrow": "Wochenübersicht",
            "h1": f"Was der Bundestag in {label} verhandelt hat",
            "facts": f"{counts} · {sittings}, {latest} · {clock}",
            "running": False,
            "warning": warning,
            "stale": age,
        }
    return {
        "eyebrow": "Wochenübersicht",
        "h1": f"Was der Bundestag in {label} verhandelt hat",
        "facts": f"Letzte Woche mit Sitzung: vor {age} Wochen · {counts} · {sittings}, {latest} · {clock}",
        "running": False,
        "warning": warning,
        "stale": None,
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

    tags_html = pulse_html.render_politikfeld_tags(row.get("politikfelder"))
    tags_json = esc(json.dumps(row.get("politikfelder") or [], ensure_ascii=False))
    return f"""
        <li class="radar-row" id="thema-{position}" data-politikfelder='{tags_json}'>
          <div class="radar-main">{label_html}{title_html}{tags_html}{trace_html}{summary_html}{badge_html}{foot_html}</div>
          {share_html}
          {who_html}
        </li>"""


def render_radar_filter(rows: list[dict[str, Any]]) -> str:
    """The Politikfeld chips above the radar: only those some shown row carries."""
    present = {tag for row in rows for tag in row.get("politikfelder") or []}
    present.discard(politikfelder.UNTAGGED)
    chips = "".join(
        f'<button type="button" class="chip" aria-pressed="false" data-radar-chip="{pulse_html.esc(name)}">{pulse_html.esc(name)}</button>'
        for name in politikfelder.POLITIKFELDER
        if name in present
    )
    if not chips:
        return ""
    return (
        '<div class="radar-filter" role="group" aria-label="Nach Politikfeld filtern">'
        f'<span class="eyebrow">Nach Politikfeld</span><div class="chip-row">{chips}</div></div>'
    )


# Filters the radar rows by Politikfeld chip (multi-select, any match). Without
# script every row stays visible.
RADAR_FILTER_SCRIPT = """
      <script>
        (() => {
          const list = document.querySelector('.radar-list');
          if (!list) return;
          const rows = Array.from(list.querySelectorAll('.radar-row')).map((row) => {
            let felder = [];
            try { felder = JSON.parse(row.dataset.politikfelder || '[]'); } catch (err) { felder = []; }
            return { row, felder };
          });
          const chips = Array.from(document.querySelectorAll('[data-radar-chip]'));
          const empty = document.querySelector('[data-radar-empty]');
          const active = new Set();
          const apply = () => {
            let visible = 0;
            rows.forEach(({ row, felder }) => {
              const show = active.size === 0 || felder.some((name) => active.has(name));
              row.hidden = !show;
              if (show) visible += 1;
            });
            if (empty) empty.hidden = visible !== 0 || active.size === 0;
            chips.forEach((chip) => {
              const on = active.has(chip.dataset.radarChip);
              chip.classList.toggle('is-active', on);
              chip.setAttribute('aria-pressed', on ? 'true' : 'false');
            });
          };
          chips.forEach((chip) => chip.addEventListener('click', () => {
            const value = chip.dataset.radarChip;
            if (active.has(value)) active.delete(value); else active.add(value);
            apply();
          }));
        })();
      </script>
"""


def render_radar_also(radar: dict[str, Any]) -> str:
    """The "Außerdem" line: question formats, then the unranked debates per sitting."""
    esc = pulse_html.esc
    formats = []
    for item in radar["formats"]:
        where = ", ".join(p for p in (pulse_html.format_sitting_date(item["datum"]), f"TOP {item['index']}") if p)
        counts = pulse_html.format_question_counts(item["speech_count"], item["contribution_counts"])
        share = f" · {pulse_html.format_percent(item['share'])}" if item["speech_count"] else ""
        formats.append(
            f'<a href="{esc(item["href"])}">{esc(item["heading"])}</a> · '
            f"{counts}{share} ({esc(where)})"
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
        # A week of Fragestunden only has no Reden but still has its questions and
        # answers: the Außerdem line lists them.
        note = "In dieser Woche wurden keine Reden extrahiert"
        note += ", nur Fragen und Antworten aus Frageformaten." if radar["formats"] else "."
        body = f'<p class="week-note">{note}</p>' + render_radar_also(radar)
    else:
        method = (
            "Die Tagesordnungspunkte mit den meisten Reden der Woche. "
            f"Anteil an allen {pulse_html.format_count(total, 'Rede', 'Reden')}"
        )
        if radar["formats"]:
            biggest = max(
                radar["formats"],
                key=lambda item: item["speech_count"] + sum(item["contribution_counts"].values()),
            )
            counts = pulse_html.format_question_counts(biggest["speech_count"], biggest["contribution_counts"])
            method += (
                f"; Frageformate wie die {biggest['heading']} ({counts}) werden nicht als Thema gerankt, "
                "und ihre Fragen und Antworten sind keine Reden."
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
            body += render_radar_filter(rows)
            body += f'<ul class="radar-list">{rows_html}\n      </ul>'
            body += '<p class="week-note" data-radar-empty hidden>Kein Thema der Woche in diesem Politikfeld.</p>'
            body += RADAR_FILTER_SCRIPT
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
    vorgang_cache: dict[str, Any] | None = None,
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
        week_entries, occurrences, total=stats["speech_count"], dossier_href_for=dossier_href,
        vorgang_cache=vorgang_cache,
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
    stale_flag = (
        f'<p class="stale-flag">Nicht aktuell: letzte Woche mit Sitzung vor {header["stale"]} Wochen</p>'
        if header["stale"]
        else ""
    )
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
  <title>Bundestag-Puls · Wochenübersicht</title>
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
    h1 {{ margin:0; font-size:37px; line-height:1.08; font-weight:780; overflow-wrap:anywhere; text-wrap:balance; }}
    h2 {{ margin:0; font-size:18px; line-height:1.25; text-wrap:balance; }}
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
    .week-chips a {{ color:var(--ink); gap:.3em; }}
    .stale-flag {{ display:inline-block; margin:10px 0 0; padding:3px 9px; border:1px solid var(--amber); border-radius:6px; background:var(--amber-soft); color:var(--amber); font-size:14px; font-weight:650; }}
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
      grid-template-columns:minmax(0,1fr) 220px 200px;
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
      font-size:12px;
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
    .radar-legend {{ margin:0; font-size:12px; line-height:1.4; color:var(--muted); }}
    .radar-row a {{ text-decoration-line:underline; text-decoration-color:transparent; text-underline-offset:2px; }}
    .radar-row a:hover {{ text-decoration-color:currentColor; }}
    .radar-row a:visited {{ text-decoration-color:var(--muted); }}
    .radar-row a:focus-visible {{ outline:2px solid var(--blue); outline-offset:2px; border-radius:2px; }}
    .radar-row[hidden] {{ display:none; }}
    .radar-filter {{ margin-top:12px; }}
    .radar-filter .chip-row {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:6px; }}
    .radar-filter .chip {{
      min-height:30px; padding:4px 11px; border:1px solid var(--line); border-radius:999px;
      background:var(--panel); color:var(--ink); font:inherit; font-size:13px; font-weight:650; cursor:pointer;
    }}
    .radar-filter .chip.is-active {{ border-color:var(--blue); background:var(--blue-soft); color:var(--blue); }}
    .radar-filter .chip:focus-visible {{ outline:2px solid var(--blue); outline-offset:2px; }}
    {pulse_html.POLITIKFELD_CHIP_CSS}
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
      font-size:12px;
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
    .week-metric-foot em {{ color:var(--muted); font-size:12px; font-style:normal; }}
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
    .week-list-current-only .week-row {{
      grid-template-columns:minmax(96px,1.1fr) minmax(0,2fr) auto;
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
    @media (pointer:coarse) {{
      .page-actions a, .week-chips a, .session-links a, .feature-link {{ min-height:44px; }}
      .radar-filter .chip {{ min-height:44px; }}
      .radar-open a {{ display:inline-block; min-height:44px; padding:12px 0; }}
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
      .week-list-current-only .week-row {{ grid-template-columns:minmax(80px,1fr) minmax(0,1.6fr) auto; }}
    }}
    @media (max-width: 460px) {{
      .week-metrics {{ grid-template-columns:1fr; }}
      .week-row {{ grid-template-columns:minmax(0,1fr) auto auto; }}
      .week-list-current-only .week-row {{ grid-template-columns:minmax(0,1fr) auto; }}
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
        <h1>{header["h1"]}</h1>{stale_flag}
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
      <span class="session-links"><a href="overview.html">Sitzungen</a><a href="bills/index.html">Gesetzesvorhaben</a><a href="abgeordnete/index.html">Abgeordnete</a><a href="sources.html">Quellen</a></span>
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
# PAGES: bills/index.html and bills/bill-*.html - "Gesetzesvorhaben"
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


# Same-day order of a bill's timeline events, latest step highest. A Drucksache
# dated on the sitting day is filed before the debate it belongs to, the sitting's
# Plenarprotokoll only records the day, a roll-call vote happens inside its
# Beratung, and the Gesetzesbeschluss follows the final Beratung. A kind not
# listed ranks by where the event came from (BILL_EVENT_ORIGIN_RANK), so an
# unfamiliar Vorgangsposition still outranks a Drucksache of the same day.
BILL_STEP_RANK = {
    "Plenarprotokoll": 0,
    "Gesetzentwurf": 10,
    "Antrag": 10,
    "Unterrichtung": 10,
    "Stellungnahme": 12,
    "Entschließungsantrag": 14,
    "Änderungsantrag": 14,
    "Beschlussempfehlung": 16,
    "Beschlussempfehlung und Bericht": 16,
    "Bericht": 16,
    "Namentliche Abstimmung": 25,
    "Beratung": 30,
    "Beratung und Ausschussüberweisung": 30,
    "Plenarberatung": 30,
    "1. Beratung": 30,
    "2. Beratung": 32,
    "3. Beratung": 34,
    "Gesetzesbeschluss": 40,
}
BILL_EVENT_ORIGIN_RANK = {"document": 10, "vote": 25, "position": 30}


# File name for a bill's detail page, e.g. "bill-315678.html".
def bill_slug(bill: dict[str, Any]) -> str:
    identity = first_value(bill.get("vorgang_id"), bill.get("primary_document"), bill.get("title"), "bill")
    return "bill-" + slugify_document_number(identity)


# Only a Gesetzgebung is legislation (CONTEXT.md): a Vorgang whose DIP
# Vorgangstyp says so. An Entschließungsantrag or Antrag that accompanies one is
# its own Vorgang, and a Rechtsverordnung is none even when the Bundestag must
# consent to it. The old keyword test kept anything mentioning "gesetz",
# "Grundgesetz" or "gesetzliche Krankenversicherung" as well.
def is_gesetzgebung(position: dict[str, Any]) -> bool:
    return str(position.get("vorgangstyp") or "") == "Gesetzgebung"


# The set of Drucksache numbers attached to a bill, used to match roll-call
# votes to it.
def doc_numbers(docs: list[dict[str, Any]]) -> set[str]:
    return {str(doc.get("dokumentnummer")) for doc in docs if doc.get("dokumentnummer")}


# The Vorgänge on an agenda item that are not Gesetzgebungen, one row each with
# the Drucksachen DIP links to it. Sharing an agenda item is all they have in
# common with a Gesetzgebung there: nothing here says one accompanies another.
def _related_vorgaenge(positions: list[dict[str, Any]], linked_docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for position in positions:
        vorgang_id = str(position.get("vorgang_id") or "")
        if not vorgang_id or is_gesetzgebung(position):
            continue
        row = rows.setdefault(
            vorgang_id,
            {
                "vorgang_id": vorgang_id,
                "type": first_value(position.get("vorgangstyp"), "Vorgang"),
                "title": first_value(position.get("titel")),
                "documents": [],
            },
        )
        row["documents"].extend(
            {"dokumentnummer": doc.get("dokumentnummer"), "drucksachetyp": doc.get("drucksachetyp"), "url": doc.get("url")}
            for doc in linked_docs
            if str(doc.get("vorgang_id") or "") == vorgang_id
        )
    for row in rows.values():
        row["documents"] = unique_records(row["documents"], ("dokumentnummer", "url"))
    return list(rows.values())


# Re-index the built dossiers by legislative procedure.
#
# Input: the dossier entries of this build. Output: one normalised bill record
# per procedure, sorted newest activity first, ready for render_bills_index and
# render_bill_detail.
def collect_bill_pages(detail_entries: list[dict[str, Any]], mp_lookup: dict[str, str] | None = None) -> list[dict[str, Any]]:
    bills: dict[str, dict[str, Any]] = {}
    speaker_counts: dict[str, dict[str, dict[str, Any]]] = {}
    seen_speeches: dict[str, set[str]] = {}
    seen_agenda_items: dict[str, set[tuple[Any, Any]]] = {}
    # id(event) -> where it came from, for BILL_EVENT_ORIGIN_RANK; kept out of
    # the event itself because bills.json publishes the whole record.
    event_origin: dict[int, str] = {}

    def add_event(bill: dict[str, Any], origin: str, event: dict[str, Any]) -> None:
        bill["events"].append(event)
        event_origin[id(event)] = origin

    def step_rank(event: dict[str, Any]) -> int:
        rank = BILL_STEP_RANK.get(str(event.get("kind") or ""))
        return rank if rank is not None else BILL_EVENT_ORIGIN_RANK[event_origin[id(event)]]

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
            # What else is on this agenda item next to its Gesetzgebungen:
            # Entschließungsanträge, Anträge and the like. DIP does not say which
            # Gesetzgebung one of them belongs to when an item bundles several
            # procedures, so each Gesetzgebung page lists them as the other
            # Vorgänge of the same item, not as its own companions.
            related = _related_vorgaenge(positions, linked_docs)
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
                # Skip anything that is not a Gesetzgebung.
                if not is_gesetzgebung(position):
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
                        "related": [],
                        "events": [],
                        "votes": [],
                        "raw": {"agenda_items": []},
                    },
                )
                bill["related"].extend(row for row in related if row["vorgang_id"] != vorgang_id)
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
                    "href": f"{protocol_href}#top-{source_index(item.get('index'))}",
                    "speech_count": item.get("xml_speech_count") or 0,
                }
                bill["protocol_refs"].append(ref)
                # Several DIP positions can repeat one agenda item; keep its raw copy once.
                agenda_key = (protocol_href, source_index(item["index"]) if item.get("index") is not None else id(item))
                if agenda_key not in seen_agenda_items.setdefault(key, set()):
                    seen_agenda_items[key].add(agenda_key)
                    bill["raw"]["agenda_items"].append({"protocol": protocol, "item": item})

                # Timeline entries ("Verlauf" on the detail page): one per linked
                # document, plus one for the plenary debate itself.
                for doc in position_docs:
                    add_event(
                        bill,
                        "document",
                        {
                            "date": first_value(doc.get("datum"), protocol.get("datum")),
                            "kind": first_value(doc.get("drucksachetyp"), "Drucksache"),
                            "title": first_value(doc.get("titel"), position.get("titel")),
                            "source": _document_citation(doc) if doc.get("dokumentnummer") else "",
                            "url": doc.get("url"),
                        }
                    )
                add_event(
                    bill,
                    "position",
                    {
                        "date": protocol.get("datum"),
                        "kind": first_value(position.get("vorgangsposition"), "Plenarberatung"),
                        "title": first_value(position.get("titel"), item.get("heading")),
                        "source": f"BT-PlPr. {protocol.get('dokumentnummer')} · {item.get('top_id')}",
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
                    add_event(
                        bill,
                        "vote",
                        {
                            "date": first_value(vote.get("date"), protocol.get("datum")),
                            "kind": "Namentliche Abstimmung",
                            "title": vote.get("title"),
                            "source": ", ".join(vote.get("document_numbers") or []),
                            "url": vote.get("detail_url"),
                        }
                    )

                # Tally who spoke about this bill and how much, keyed by the
                # person the store bound the speech to, else by name+party (two
                # namesakes of one party would otherwise share one row and one
                # link). External ids are kept so the detail page can link
                # the speaker to their Abgeordnete profile.
                speaker_bucket = speaker_counts.setdefault(key, {})
                for sequence, speech in enumerate(item.get("xml_speakers") or [], start=1):
                    # The reviewed speaker, as on the protocol page: a shared
                    # Redner-ID's occurrences are tallied under their own person.
                    rede_id = speech_rede_id(protocol.get("id"), source_index(item.get("index")), sequence, speech.get("rede_id"))
                    speech_href = f"{protocol_href}#{pulse_html.speech_anchor(item, speech, sequence - 1)}"
                    # Several DIP positions can repeat the same bill's agenda item.
                    seen = seen_speeches.setdefault(key, set())
                    if speech_href in seen:
                        continue
                    seen.add(speech_href)
                    speaker = registry.corrected_speaker(speech.get("speaker") or {}, protocol.get("id"), rede_id)
                    name = derive.speaker_display_name(speaker)
                    party = pulse_html.speaker_party(speaker, protocol)
                    occurrence_id = speech_occurrence_id(protocol.get("id"), rede_id)
                    person_id = (mp_lookup or {}).get(occurrence_id)
                    speaker_key = f"person:{person_id}" if person_id else f"{name}|{party}"
                    entry_count = speaker_bucket.setdefault(
                        speaker_key,
                        {"name": name, "party": party, "speech_count": 0, "char_count": 0, "speeches": []},
                    )
                    entry_count["occurrence_id"] = occurrence_id
                    entry_count["speech_count"] += 1
                    entry_count["speeches"].append({
                        "href": speech_href,
                        "protocol_number": protocol.get("dokumentnummer"),
                        "protocol_date": protocol.get("datum"),
                        "source_page": speech.get("source_page"),
                    })
                    entry_count["char_count"] += int(speech.get("char_count") or 0)
                    # Keep the speaker's external ids so the bill page can link to
                    # their Abgeordnete profile.
                    profile = speaker.get("abgeordnetenwatch") or {}
                    if profile.get("id") and not entry_count.get("aw_id"):
                        entry_count["aw_id"] = profile.get("id")
                        entry_count["aw_match"] = profile.get("match")
                    if speaker.get("xml_redner_id") and not entry_count.get("xml_redner_id"):
                        entry_count["xml_redner_id"] = speaker.get("xml_redner_id")

    # Second pass: de-duplicate the accumulated lists, sort the timeline, and
    # derive the "latest step / latest date" shown on the index cards.
    for key, bill in bills.items():
        bill["documents"] = unique_records(bill["documents"], ("vorgang_id", "dokumentnummer", "url"))
        bill["positions"] = unique_records(bill["positions"], ("id", "vorgang_id", "vorgangsposition"))
        bill["related"] = unique_records(bill["related"], ("vorgang_id",))
        bill["protocol_refs"] = unique_records(bill["protocol_refs"], ("protocol_number", "top_id", "heading"))
        bill["votes"] = unique_records(bill["votes"], ("id",))
        bill["introduced_by"] = unique_values(bill["introduced_by"])
        bill["slug"] = bill_slug(bill)
        bill["speakers"] = sorted(
            speaker_counts.get(key, {}).values(),
            key=lambda speaker: (int(speaker.get("speech_count") or 0), int(speaker.get("char_count") or 0)),
            reverse=True,
        )
        for speaker in bill["speakers"]:
            speaker["speeches"].sort(key=lambda ref: str(ref.get("protocol_date") or ""), reverse=True)
        bill["events"] = unique_records(bill["events"], ("date", "kind", "title", "source"))
        # On a date tie the procedurally later step leads (BILL_STEP_RANK); the
        # stable sort keeps insertion order among equal ranks.
        bill["events"].sort(key=lambda event: (str(event.get("date") or ""), step_rank(event)), reverse=True)
        latest = bill["events"][0] if bill["events"] else {}
        bill["latest_date"] = first_value(latest.get("date"), *(ref.get("protocol_date") for ref in bill["protocol_refs"]))
        bill["latest_step"] = first_value(latest.get("kind"), "Erfasst")

    # Published order: newest first, then title A-Z, then id. The overview
    # script's default sort breaks date ties by this rank (data-rank), so the
    # list does not reshuffle when the script runs.
    by_title = sorted(bills.values(), key=lambda bill: (_title_sort_key(bill.get("title")), str(bill.get("id") or "")))
    return sorted(by_title, key=lambda bill: str(bill.get("latest_date") or ""), reverse=True)


def _title_sort_key(title: Any) -> list[Any]:
    """Approximates Intl.Collator('de', {sensitivity: 'base', numeric: true})."""
    text = "".join(ch for ch in unicodedata.normalize("NFD", str(title or "")) if not unicodedata.combining(ch)).casefold()
    # Digit runs compare by length then digits: numeric order without int(), which
    # refuses very long runs.
    return [(0, len(part.lstrip("0")), part.lstrip("0")) if part.isdecimal() else (1, 0, part) for part in re.split(r"(\d+)", text) if part]


# Collapsed raw-JSON block used in the "Quellen und Daten" section of a bill page.
def render_bill_json_details(title: str, payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        '<details class="raw-block">'
        f"<summary>{pulse_html.esc(title)}</summary>"
        f"<pre>{pulse_html.esc(text)}</pre>"
        "</details>"
    )


# Overview enhancement: static rows -> metadata matches -> ordered page.
# No visitor fetch; failures restore the same complete readable rows.
def render_bill_script() -> str:
    return r"""
  <script>
    (() => {
      const root = document.querySelector('[data-bills-index]');
      if (!root) return;
      const rows = Array.from(root.querySelectorAll('[data-bill-row]'));
      if (!rows.length) return;
      const list = root.querySelector('[data-bill-list]');
      const search = root.querySelector('[data-bill-search]');
      const year = root.querySelector('[data-bill-year]');
      const sort = root.querySelector('[data-bill-sort]');
      const reset = root.querySelector('[data-bill-reset]');
      const prev = root.querySelector('[data-bill-prev]');
      const next = root.querySelector('[data-bill-next]');
      const pager = root.querySelector('[data-bill-pagination]');
      const summary = root.querySelector('[data-bill-summary]');
      const criteria = root.querySelector('[data-bill-criteria]');
      const noResults = root.querySelector('[data-bill-no-results]');
      const unavailable = root.querySelector('[data-bill-unavailable]');
      const announcement = root.querySelector('[data-bill-announcement]');
      const controls = [search, year, sort, reset, prev, next];
      let failed = false;
      const fallback = () => {
        failed = true;
        rows.forEach(row => { row.hidden = false; if (list) list.appendChild(row); });
        controls.forEach(control => { if (control) control.disabled = true; });
        delete root.dataset.billReady;
        if (summary) summary.textContent = rows.length + ' Gesetzesvorhaben';
        if (criteria) criteria.textContent = '';
        if (noResults) noResults.hidden = true;
        if (pager) pager.hidden = true;
        if (reset) reset.hidden = true;
        if (unavailable) unavailable.hidden = false;
        if (announcement) announcement.textContent = unavailable ? unavailable.textContent : '';
      };
      const guarded = fn => () => {
        if (failed) return;
        try { fn(); } catch (error) { console.error(error); fallback(); }
      };
      try {
        if (!list || !summary || !criteria || !noResults || !unavailable ||
            !announcement || !pager || controls.some(control => !control)) {
          throw new Error('Incomplete law overview');
        }
        const collator = new Intl.Collator('de', { sensitivity: 'base', numeric: true });
        const records = rows.map(row => ({
          row, id: row.dataset.id, rank: Number(row.dataset.rank), title: row.dataset.title || '',
          date: row.dataset.date || '', search: row.dataset.search || ''
        }));
        const years = new Set(Array.from(year.options, option => option.value));
        const sorts = new Set(['date-desc', 'date-asc', 'title']);
        const readUrl = () => {
          const params = new URL(location.href).searchParams;
          const requestedPage = params.get('page') || '1';
          const page = /^\d+$/.test(requestedPage) ? Number(requestedPage) : 1;
          return {
            q: (params.get('q') || '').trim(),
            year: years.has(params.get('year')) ? params.get('year') : '',
            sort: sorts.has(params.get('sort')) ? params.get('sort') : 'date-desc',
            page: Number.isSafeInteger(page) && page > 0 ? page : 1
          };
        };
        let state = readUrl();
        const syncControls = () => {
          search.value = state.q;
          year.value = state.year;
          sort.value = state.sort;
        };
        const writeUrl = mode => {
          if (!mode) return;
          const url = new URL(location.href);
          for (const [key, value] of Object.entries({
            q: state.q, year: state.year,
            sort: state.sort === 'date-desc' ? '' : state.sort,
            page: state.page === 1 ? '' : String(state.page)
          })) {
            if (value) url.searchParams.set(key, value);
            else url.searchParams.delete(key);
          }
          if (mode === 'push' && url.href === location.href) return;
          // URL sync is a convenience: a throttled history API (Safari) must not
          // switch the whole list to the fallback.
          try { history[mode === 'push' ? 'pushState' : 'replaceState'](null, '', url); } catch {}
        };
        const apply = (mode = 'replace', focusResults = false, announce = true) => {
          state.q = search.value.trim();
          state.year = year.value;
          state.sort = sort.value;
          // Fold accents and ß exactly as in the build-time search metadata.
          const terms = state.q.toLowerCase().replace(/ß/g, 'ss').normalize('NFD').replace(/\p{M}/gu, '').split(/\s+/).filter(Boolean);
          const matches = records.filter(record =>
            terms.every(term => record.search.includes(term)) &&
            (!state.year || record.date.startsWith(state.year + '-'))
          );
          const stableTitle = (a, b) => collator.compare(a.title, b.title) ||
            (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);
          matches.sort((a, b) => {
            if (state.sort === 'title') return stableTitle(a, b);
            if (!a.date || !b.date) return a.date ? -1 : b.date ? 1 : state.sort === 'date-asc' ? stableTitle(a, b) : a.rank - b.rank;
            const cmp = a.date < b.date ? -1 : a.date > b.date ? 1 : 0;
            if (state.sort === 'date-asc') return cmp || stableTitle(a, b);
            return -cmp || a.rank - b.rank;
          });
          const pages = Math.max(1, Math.ceil(matches.length / 20));
          state.page = Math.max(1, Math.min(state.page, pages));
          const start = (state.page - 1) * 20;
          const visible = new Set(matches.slice(start, start + 20).map(record => record.row));
          rows.forEach(row => { row.hidden = !visible.has(row); });
          // Non-matches follow in published order, so print (which shows every row) stays sorted.
          const matched = new Set(matches);
          matches.forEach(record => list.appendChild(record.row));
          records.forEach(record => { if (!matched.has(record)) list.appendChild(record.row); });
          summary.textContent = matches.length
            ? (start + 1) + '–' + Math.min(start + 20, matches.length) + ' von ' + matches.length + ' Gesetzesvorhaben'
            : '0 passende Gesetzesvorhaben';
          criteria.textContent = [
            state.q ? 'Suche: „' + state.q + '“' : '',
            state.year ? 'Letzte erfasste Aktivität: ' + state.year : ''
          ].filter(Boolean).join(' · ');
          noResults.hidden = matches.length !== 0;
          reset.hidden = !state.q && !state.year;
          pager.hidden = matches.length <= 20;
          prev.disabled = state.page === 1;
          next.disabled = state.page === pages;
          writeUrl(mode);
          announcement.textContent = focusResults || !announce ? '' : summary.textContent;
          if (focusResults) {
            summary.focus({ preventScroll: true });
            summary.scrollIntoView({ block: 'start', behavior: 'instant' });
          }
        };
        const changed = mode => guarded(() => { state.page = 1; apply(mode); });
        search.addEventListener('input', changed('replace'));
        year.addEventListener('change', changed('push'));
        sort.addEventListener('change', changed('push'));
        reset.addEventListener('click', guarded(() => {
          search.value = '';
          year.value = '';
          state.page = 1;
          apply('push');
          search.focus();
        }));
        prev.addEventListener('click', guarded(() => { state.page -= 1; apply('push', true); }));
        next.addEventListener('click', guarded(() => { state.page += 1; apply('push', true); }));
        const restore = guarded(() => { state = readUrl(); syncControls(); apply(null, false, false); });
        addEventListener('popstate', restore);
        addEventListener('pageshow', event => { if (event.persisted) restore(); });
        syncControls();
        apply('replace', false, false);
        [search, year, sort, reset].forEach(control => { control.disabled = false; });
        root.dataset.billReady = 'true';
      } catch (error) { console.error(error); fallback(); }
    })();
  </script>
"""


def render_bill_help_script() -> str:
    """Hover/focus explanations leave their native glossary links usable."""
    return """
  <script>
    (() => {
      let active = null;
      let dismissed = null;
      let timer;
      const hide = () => {
        if (active) active.tip.hidden = true;
        active = null;
      };
      const position = () => {
        if (!active) return;
        const anchor = active.link.getBoundingClientRect();
        const box = active.tip.getBoundingClientRect();
        const left = Math.max(12, Math.min(anchor.left, innerWidth - box.width - 12));
        const below = anchor.bottom + 8;
        const top = below + box.height <= innerHeight - 12
          ? below : anchor.top - box.height - 8;
        active.tip.style.left = left + 'px';
        active.tip.style.top = Math.max(12, Math.min(top, innerHeight - box.height - 12)) + 'px';
      };
      const closeLater = () => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          if (active && document.activeElement !== active.link &&
              !active.link.matches(':hover') && !active.tip.matches(':hover')) hide();
        }, 100);
      };
      document.querySelectorAll('[data-bill-help]').forEach(link => {
        const tip = document.getElementById(link.dataset.billHelp);
        if (!tip) return;
        const show = () => {
          clearTimeout(timer);
          if (dismissed === link) return;
          hide();
          tip.hidden = false;
          active = { link, tip };
          position();
        };
        link.addEventListener('mouseenter', show);
        link.addEventListener('focus', show);
        link.addEventListener('mouseleave', () => {
          if (document.activeElement !== link) dismissed = null;
          closeLater();
        });
        link.addEventListener('blur', () => {
          if (!link.matches(':hover')) dismissed = null;
          closeLater();
        });
        tip.addEventListener('mouseenter', () => clearTimeout(timer));
        tip.addEventListener('mouseleave', closeLater);
      });
      document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && active) { dismissed = active.link; hide(); }
      });
      addEventListener('resize', position);
      addEventListener('scroll', position, true);
    })();
  </script>
"""


# Base sheet shared by the bill, Abgeordnete and vote pages (abgeordnete_styles
# and the vote archive extend it). Bill-only rules belong in bill_page_styles().
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
    .content-grid, .speaker-list, .doc-list {
      display:grid;
      gap:12px;
      margin-top:18px;
    }
    .panel {
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel);
      padding:16px;
    }
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
    .open-button {
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
    .speaker-row, .doc-row {
      display:grid;
      grid-template-columns:120px minmax(0,1fr) minmax(120px,.45fr);
      gap:10px;
      padding-bottom:10px;
      border-bottom:1px solid #eef1f5;
      font-size:13px;
    }
    .speaker-row:last-child, .doc-row:last-child { border-bottom:0; padding-bottom:0; }
    .speaker-row em, .doc-row em {
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
      .page-header, .content-grid { grid-template-columns:1fr; }
      .actions { justify-content:flex-start; }
      .summary-grid, .field-grid { grid-template-columns:1fr 1fr; }
      .speaker-row, .doc-row { grid-template-columns:1fr; gap:4px; }
    }
    @media (max-width: 640px) {
      .shell { padding:18px 14px; }
      h1 { font-size:28px; }
      .summary-grid, .field-grid { grid-template-columns:1fr; }
    }
"""



def bill_page_styles() -> str:
    """Bill-only refinements; the shared MP/vote base sheet stays independent."""
    return bill_styles() + """
    .bill-page main { min-width:0; }
    .bill-page .page-header { grid-template-columns:minmax(0,1fr); }
    .bill-page p { max-width:72ch; font-size:16px; line-height:1.5; }
    .bill-page h1, .bill-page h2, .bill-page h3, .bill-page a { overflow-wrap:anywhere; }
    .bill-page .eyebrow { font-size:14px; text-transform:none; letter-spacing:0; }
    .bill-page a { transition:color 140ms ease, border-color 140ms ease; }
    .bill-page :is(button,input,select,summary):focus-visible {
      outline:2px solid var(--blue); outline-offset:3px;
    }
    .bill-page .local-nav a, .bill-section-nav a { min-height:44px; background:var(--panel); font-size:16px; }
    .bill-controls {
      display:grid; grid-template-columns:minmax(0,2fr) minmax(0,1fr) minmax(0,1fr);
      gap:12px; padding:22px 0 18px;
    }
    .bill-control { display:grid; align-content:start; gap:6px; min-width:0; font-size:16px; color:var(--ink); }
    .bill-control label { line-height:1.4; }
    .bill-control :is(input,select), .bill-page .bill-button {
      min-height:44px; min-width:0; width:100%; border:1px solid var(--line);
      border-radius:6px; padding:10px 12px; background:var(--panel); color:var(--ink); font:inherit;
      transition:border-color 140ms ease, background-color 140ms ease;
    }
    .bill-control input:hover, .bill-control select:hover, .bill-page .bill-button:hover { border-color:var(--blue); }
    .bill-control small { font-size:14px; color:var(--muted); line-height:1.4; }
    .bill-page .bill-button { width:auto; cursor:pointer; color:var(--blue); }
    .bill-page .bill-button:disabled { opacity:.55; cursor:default; }
    .bill-results-header { display:flex; flex-wrap:wrap; align-items:start; justify-content:space-between; gap:12px; }
    .bill-page .bill-result-summary { font-size:18px; font-weight:650; color:var(--ink); margin:0; scroll-margin-top:18px; }
    .bill-page .bill-coverage, .bill-page .bill-criteria, .bill-page .bill-result-meta,
    .bill-page .bill-unavailable { font-size:14px; color:var(--muted); }
    .bill-page .bill-criteria:empty { display:none; }
    .bill-results { margin-top:20px; }
    .bill-result { border-top:1px solid var(--line); padding:20px 0; }
    .bill-result h2 { max-width:58ch; }
    .bill-page .bill-result-context { margin-top:8px; color:var(--ink); }
    .bill-result[hidden], .bill-page [hidden] { display:none; }
    .bill-pagination { display:flex; flex-wrap:wrap; gap:12px; padding:14px 0; border-top:1px solid var(--line); }
    .bill-empty { padding:24px 0; }
    .bill-empty strong { font-size:18px; }
    .bill-section-nav { display:flex; flex-wrap:wrap; gap:8px 16px; margin:16px 0; }
    .bill-section-nav a { display:inline-flex; align-items:center; padding:8px 12px; border:1px solid var(--line); border-radius:6px; }
    .bill-page .bill-context { margin-top:14px; }
    .bill-page .bill-caveat { font-size:14px; }
    .bill-detail-grid { display:grid; grid-template-columns:minmax(0,1fr) 360px; grid-template-rows:min-content 1fr; gap:12px; align-items:start; }
    .bill-reading-lead { grid-column:1; grid-row:1; min-width:0; }
    .bill-support { grid-column:2; grid-row:1 / span 2; display:grid; gap:12px; min-width:0; background:transparent !important; }
    .bill-reading-rest { grid-column:1; grid-row:2; display:grid; gap:12px; min-width:0; }
    .bill-page section { scroll-margin-top:18px; }
    .bill-page .panel { min-width:0; }
    .bill-page .panel h2 { margin-bottom:10px; }
    .bill-page .panel h3 { font-size:18px; margin-top:22px; }
    .bill-events, .bill-documents, .bill-debates, .bill-speakers, .bill-votes, .bill-related {
      list-style:none; padding:0; margin:14px 0 0; display:grid; gap:14px;
    }
    .bill-events li, .bill-documents li, .bill-speakers li, .bill-votes li,
    .bill-debates li, .bill-related li { min-width:0; border-bottom:1px solid var(--line); padding-bottom:14px; font-size:16px; line-height:1.5; overflow-wrap:anywhere; }
    .bill-events li:last-child, .bill-documents li:last-child, .bill-speakers li:last-child,
    .bill-votes li:last-child, .bill-debates li:last-child, .bill-related li:last-child { border-bottom:0; padding-bottom:0; }
    .bill-page .bill-event-date { font-size:16px; margin-top:20px; color:var(--muted); }
    .bill-speaker-name, .bill-speaker-role, .bill-speaker-count { display:block; }
    .bill-speaker-name { font-weight:650; }
    .bill-speaker-role { margin-top:3px; }
    .bill-speaker-count { margin-top:5px; font-size:14px; color:var(--muted); }
    .bill-page .bill-document-meta { font-size:14px; }
    .bill-speaker-speeches { margin-top:5px; }
    .bill-speaker-speeches summary, .bill-speech-links a { min-height:44px; padding:10px 0; font-size:14px; line-height:1.5; }
    .bill-speaker-speeches summary { cursor:pointer; color:var(--blue); }
    .bill-speech-links a { display:block; }
    .bill-more-speakers { margin-top:16px; }
    .bill-more-speakers summary, .bill-page .raw-block summary { min-height:44px; cursor:pointer; font-size:16px; line-height:1.5; padding:10px 0; color:var(--blue); }
    .bill-page .raw-block { background:var(--panel); border-color:var(--line); }
    .bill-page .raw-block summary { padding:10px; }
    .bill-term-link { text-decoration-line:underline; text-decoration-style:dotted; text-underline-offset:4px; }
    .bill-tooltip {
      position:fixed; z-index:20; width:max-content; max-width:min(320px,calc(100vw - 24px));
      max-height:calc(100vh - 24px); overflow:auto;
      padding:12px; border:1px solid var(--line); border-radius:6px; background:var(--panel);
      color:var(--ink); font-size:14px; font-weight:400; line-height:1.5;
      animation:bill-help-appear 120ms ease-out;
    }
    .bill-sr-only { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); white-space:nowrap; }
    @keyframes bill-help-appear { from { opacity:0; } to { opacity:1; } }
    @media (min-width:641px) and (max-width:1023px) {
      .bill-controls { grid-template-columns:repeat(2,minmax(0,1fr)); }
      .bill-control:first-child { grid-column:1 / -1; }
    }
    @media (min-width:1024px) { .bill-control label { min-height:2.8em; } }
    @media (max-width:900px) {
      .bill-detail-grid { grid-template-columns:minmax(0,1fr); grid-template-rows:none; }
      .bill-detail-grid > * { grid-column:auto; grid-row:auto; }
    }
    @media (max-width:640px) { .bill-controls { grid-template-columns:minmax(0,1fr); } }
    @media (prefers-reduced-motion:reduce) {
      .bill-page a, .bill-control :is(input,select), .bill-page .bill-button { transition:none; }
      .bill-tooltip { animation:none; }
    }
    @media print {
      .bill-page [data-bill-row][hidden] { display:block !important; }
      .bill-controls, .bill-pagination, .bill-tooltip, .bill-unavailable,
      .bill-criteria, .bill-result-summary, .bill-empty[data-bill-no-results],
      .bill-page [data-bill-reset] { display:none !important; }
      .bill-result, .bill-page .panel { break-inside:avoid; }
    }
"""


# PAGE: bills/index.html. All rows are readable before enhancement runs.
def render_bills_index(bills: list[dict[str, Any]], features: Selection | None = None) -> str:
    features = features or publication_selection()
    rows = []
    years = set()
    for index, bill in enumerate(bills):
        parsed_date = pulse_html._parse_datum(bill.get("latest_date"))
        date_iso = parsed_date.isoformat() if parsed_date else ""
        if parsed_date:
            years.add(parsed_date.year)
        title = str(bill.get("title") or "Unbenanntes Gesetzesvorhaben")
        search = " ".join([title, *(str(doc.get("dokumentnummer") or "") for doc in bill.get("documents") or [])]).lower().replace("ß", "ss")
        search = "".join(ch for ch in unicodedata.normalize("NFD", search) if not unicodedata.category(ch).startswith("M"))
        date_label = pulse_html.format_date(date_iso) or "Datum nicht erfasst"
        date_html = f'<time datetime="{date_iso}">{date_label}</time>' if date_iso else date_label
        event = pulse_html.render_parliamentary_term(str(bill.get("latest_step") or "Erfasster Vorgang"), tip_id=f"result-{index}-event")
        counts = " · ".join((
            pulse_html.format_count(len(bill.get("documents") or []), "Dokument", "Dokumente"),
            pulse_html.format_count(len(bill.get("protocol_refs") or []), "Beratung im Plenum", "Beratungen im Plenum"),
            pulse_html.format_count(len(bill.get("votes") or []), "namentliche Abstimmung", "namentliche Abstimmungen"),
        ))
        rows.append(f"""
        <article class="bill-result" data-bill-row data-rank="{index}" data-id="{pulse_html.esc(bill['id'])}"
          data-title="{pulse_html.esc(title)}" data-date="{date_iso}" data-search="{pulse_html.esc(search)}">
          <h2><a href="{pulse_html.esc(bill['slug'])}.html">{pulse_html.esc(title)}</a></h2>
          <p class="bill-result-context">Zuletzt erfasst: {date_html} · {event}</p>
          <p class="bill-result-meta">{pulse_html.esc(counts)}</p>
        </article>""")
    controls = ""
    results = """<div class="bill-empty"><strong>Noch keine Gesetzesvorhaben verfügbar.</strong>
      <p>Hier erscheinen Vorhaben aus den erfassten Sitzungsauswertungen.</p>
      <p><a href="../overview.html">Sitzungen ansehen</a> · <a href="../sources.html">Quellen und Methode</a></p></div>"""
    if rows:
        year_options = "".join(f'<option value="{year}">{year}</option>' for year in sorted(years, reverse=True))
        controls = f"""
      <div class="bill-controls" role="search" aria-label="Gesetzesvorhaben finden">
        <div class="bill-control"><label for="bill-search">Gesetzesvorhaben suchen</label>
          <input id="bill-search" type="search" data-bill-search aria-describedby="bill-search-hint" disabled>
          <small id="bill-search-hint">Titel oder Drucksachennummer</small></div>
        <div class="bill-control"><label for="bill-year">Jahr der letzten erfassten Aktivität</label>
          <select id="bill-year" data-bill-year aria-describedby="bill-year-hint" disabled><option value="">Alle Jahre</option>{year_options}</select>
          <small id="bill-year-hint">Erfasste Aktivität, nicht das Jahr der Einbringung.</small></div>
        <div class="bill-control"><label for="bill-sort">Sortierung</label>
          <select id="bill-sort" data-bill-sort disabled><option value="date-desc">Zuletzt erfasst</option>
            <option value="date-asc">Älteste zuerst</option><option value="title">Titel A–Z</option></select></div>
      </div>"""
        results = f"""
      <div class="bill-results-header">
        <div><p class="bill-result-summary" data-bill-summary tabindex="-1">{len(bills)} Gesetzesvorhaben</p>
          <p class="bill-coverage">Die Liste zeigt Vorhaben aus den hier ausgewerteten Sitzungen, nicht alle Gesetzesvorhaben.</p>
          <p class="bill-criteria" data-bill-criteria></p></div>
        <button type="button" class="bill-button" data-bill-reset disabled hidden>Suche und Filter zurücksetzen</button>
      </div>
      <p class="bill-unavailable" data-bill-unavailable hidden>Suche derzeit nicht verfügbar. Alle erfassten Gesetzesvorhaben werden angezeigt.</p>
      <noscript><p class="bill-unavailable">Die interaktive Suche benötigt JavaScript. Alle erfassten Gesetzesvorhaben werden angezeigt; nutze auch die Suche deines Browsers.</p></noscript>
      <div class="bill-empty" data-bill-no-results hidden><strong>Keine passenden Gesetzesvorhaben gefunden.</strong>
        <p>Versuche einen anderen Suchbegriff oder setze Suche und Filter zurück.</p></div>
      <div class="bill-results" data-bill-list>{''.join(rows)}</div>
      <nav class="bill-pagination" data-bill-pagination aria-label="Ergebnisseiten" hidden>
        <button class="bill-button" data-bill-prev type="button" disabled>Zurück</button>
        <button class="bill-button" data-bill-next type="button" disabled>Weiter</button>
      </nav>
      <span class="bill-sr-only" data-bill-announcement role="status" aria-live="polite" aria-atomic="true"></span>"""
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Gesetzesvorhaben</title>
  {pulse_html.page_head(features)}
  <style>{bill_page_styles()}</style>
</head>
<body class="bill-page">
  <div class="shell">
    {pulse_html.render_global_header(depth=1, active="bills", features=features)}
    <header class="page-header"><div><h1>Gesetzesvorhaben</h1>
      <p>Finde Gesetzesvorhaben und lies nach, wie sie im Bundestag beraten wurden.</p></div></header>
    <main data-bills-index>{controls}{results}</main>
    <footer><a href="../overview.html">Sitzungen ansehen</a> · <a href="../sources.html">Quellen und Methode</a></footer>
  </div>
  {render_bill_script() if rows else ''}
  {render_bill_help_script() if rows else ''}
  {pulse_html.page_scripts(features)}
</body>
</html>
"""


def _bill_event_href(value: Any) -> str:
    """Accept an allowlisted official source or our generated dossier anchor."""
    href = str(value or "")
    if href.startswith("https://"):
        return pulse_html.source_url(href, "bundestag-dip")
    if re.fullmatch(r"\.\./protocols/plenarprotokoll-[a-z0-9-]+\.html#(?:top-[0-9]+|speech-[0-9]+-[A-Za-z0-9_-]+)", href):
        return href
    raise publication.PublicationStateError("unsafe bill timeline URL")


def _is_bundesrat_document(doc: dict[str, Any]) -> bool:
    return pulse_html.document_chamber(doc) == "BR"


def _document_citation(doc: dict[str, Any]) -> str:
    number = str(doc.get("dokumentnummer") or "").strip()
    kind = str(doc.get("drucksachetyp") or doc.get("dokumentart") or "")
    protocol = "plenarprotokoll" in kind.lower() or bool(re.match(r"PlPr\.?\s", number, re.I))
    if protocol:
        number = re.sub(r"^PlPr\.?\s+", "", number, flags=re.I)
    chamber = pulse_html.document_chamber(doc)
    if chamber:
        return f"{chamber}-{'PlPr.' if protocol else 'Drs.'} {number}"
    return f"{'Plenarprotokoll' if protocol else 'Drucksache'} {number} (Kammer nicht erfasst)"


# PAGE: bills/bill-<slug>.html. DOM order stays readable without scripts.
def render_bill_detail(
    bill: dict[str, Any],
    mp_lookup: dict[str, str] | None = None,
    features: Selection | None = None,
) -> str:
    features = features or publication_selection()
    term = pulse_html.render_parliamentary_term
    events_by_date: dict[str, list[dict[str, Any]]] = {}
    for event in bill.get("events") or []:
        parsed = pulse_html._parse_datum(event.get("date"))
        events_by_date.setdefault(parsed.isoformat() if parsed else "", []).append(event)
    timeline = []
    event_index = 0
    for date_iso in sorted(events_by_date, reverse=True):
        event_rows = []
        for event in events_by_date[date_iso]:
            kind = str(event.get("kind") or "Erfasster Vorgang")
            label = pulse_html.esc(event.get("source") or "Quelle öffnen")
            if event.get("url"):
                label = f'<a href="{pulse_html.esc(_bill_event_href(event["url"]))}">{label}</a>'
            elif not event.get("source"):
                label = "Quelle nicht verknüpft"
            distinct_title = str(event.get("title") or "")
            title_html = f'<p>{pulse_html.esc(distinct_title)}</p>' if distinct_title and distinct_title != bill.get("title") else ""
            event_rows.append(f'<li><strong>{term(kind, tip_id=f"event-{event_index}")}</strong>{title_html}<p>{label}</p></li>')
            event_index += 1
        date_label = pulse_html.format_date(date_iso) or "Datum nicht erfasst"
        date_html = f'<time datetime="{date_iso}">{date_label}</time>' if date_iso else date_label
        timeline.append(f'<div><h3 class="bill-event-date">{date_html}</h3><ul class="bill-events">{"".join(event_rows)}</ul></div>')

    documents = []
    for index, doc in enumerate(bill.get("documents") or []):
        number = pulse_html.esc(doc.get("dokumentnummer") or "Dokument ohne Nummer")
        if doc.get("url"):
            number = f'<a href="{pulse_html.esc(pulse_html.source_url(doc["url"], "bundestag-dip"))}">{number}</a>'
        kind = str(doc.get("drucksachetyp") or doc.get("dokumentart") or "Dokumenttyp nicht erfasst")
        # Bundesrat papers ("557/25(B)", served under /brd/) are not Bundestag
        # Drucksachen; the glossary's Drucksache tooltip would misattribute them.
        if _is_bundesrat_document(doc):
            document_label_html = "Bundesrat-Plenarprotokoll" if "plenarprotokoll" in kind.lower() else "Bundesrat-Drucksache"
        else:
            document_label = "Plenarprotokoll" if "plenarprotokoll" in kind.lower() else (
                "Drucksache" if kind in {"Gesetzentwurf", "Beschlussempfehlung", "Beschlussempfehlung und Bericht", "Bericht", "Unterrichtung", "Stellungnahme"} else "Dokument"
            )
            document_label_html = term(document_label, tip_id=f"document-{index}-label")
        authors = pulse_html.esc(", ".join(doc.get("urheber") or []) or "Urheber nicht erfasst")
        documents.append(f'<li><strong>{document_label_html} {number}</strong><p>{term(kind, tip_id=f"document-{index}-kind")}</p><p class="bill-document-meta">{authors}</p></li>')

    related = []
    for row in bill.get("related") or []:
        numbers = ", ".join(str(doc.get("dokumentnummer")) for doc in row.get("documents") or [] if doc.get("dokumentnummer"))
        related.append(f'<li><strong>{pulse_html.esc(row.get("title") or "Ohne Titel")}</strong><p>{pulse_html.esc(row.get("type") or "")}{" · " + pulse_html.esc(numbers) if numbers else ""}</p></li>')
    related_html = (
        '<h3>Weitere Vorgänge zu diesem Tagesordnungspunkt</h3>'
        '<p>Diese Vorgänge wurden am selben Tagesordnungspunkt beraten. Sie sind nicht automatisch Änderungen dieses Vorhabens.</p>'
        f'<ul class="bill-related">{"".join(related)}</ul>'
    ) if related else ""

    speakers = []
    for speaker in bill.get("speakers") or []:
        href = pulse_html.mp_page_href(
            {"abgeordnetenwatch": {"id": speaker.get("aw_id"), "match": speaker.get("aw_match")},
             "occurrence_id": speaker.get("occurrence_id"), "xml_redner_id": speaker.get("xml_redner_id")},
            mp_lookup, "../abgeordnete/",
        )
        name = pulse_html.esc(speaker.get("name") or "Name nicht erfasst")
        name_html = f'<a href="{pulse_html.esc(href)}">{name}</a>' if href else name
        counts = pulse_html.format_count(int(speaker.get("speech_count") or 0), "Rede", "Reden")
        chars = pulse_html.format_int(int(speaker.get("char_count") or 0))
        speech_links = []
        speech_refs = speaker.get("speeches") or []
        for index, ref in enumerate(speech_refs, start=1):
            date = pulse_html.format_date(ref.get("protocol_date")) or "Datum nicht erfasst"
            source = f'BT-PlPr. {ref.get("protocol_number") or "ohne Nummer"}'
            page = pulse_html.source_page_text(ref.get("source_page"))
            action = 'Rede lesen' if len(speech_refs) == 1 else f'Rede {index}'
            label = f'{action} · {date} · {source}' + (f' · S. {page}' if page else '')
            speech_links.append(f'<a href="{pulse_html.esc(_bill_event_href(ref["href"]))}">{pulse_html.esc(label)}</a>')
        if len(speech_links) == 1:
            speech_html = f'<div class="bill-speech-links">{speech_links[0]}</div>'
        elif speech_links:
            speech_html = f'<details class="bill-speaker-speeches"><summary>{counts} ansehen</summary><div class="bill-speech-links">{"".join(speech_links)}</div></details>'
        else:
            speech_html = ""
        count_html = f'{chars} Zeichen' if speech_links else f'{counts} · {chars} Zeichen'
        speakers.append(f'<li><strong class="bill-speaker-name">{name_html}</strong><span class="bill-speaker-role">{pulse_html.esc(speaker.get("party") or "Zugehörigkeit nicht erfasst")}</span>{speech_html}<span class="bill-speaker-count">{count_html}</span></li>')
    speaker_list = f'<ul class="bill-speakers">{"".join(speakers[:12])}</ul>' if speakers else '<p>Keine Reden in den erfassten Daten zugeordnet.</p>'
    if len(speakers) > 12:
        speaker_list += f'<details class="bill-more-speakers"><summary>Weitere Rednerinnen und Redner ({len(speakers) - 12})</summary><ul class="bill-speakers">{"".join(speakers[12:])}</ul></details>'

    debates = []
    for index, ref in enumerate(bill.get("protocol_refs") or []):
        label = f'BT-PlPr. {ref.get("protocol_number") or "ohne Nummer"}'
        if ref.get("href"):
            label = f'<a href="{pulse_html.esc(_bill_event_href(ref["href"]))}">{pulse_html.esc(label)}</a>'
        else:
            label = pulse_html.esc(label)
        date_label = pulse_html.format_date(ref.get("protocol_date")) or "Datum nicht erfasst"
        # Only TOP ids get the Tagesordnungspunkt term; Zusatzpunkt or
        # Einzelplan ids keep their own label.
        top_id = " ".join(str(ref.get("top_id") or "").split())
        top_match = re.fullmatch(r"(?:TOP|Tagesordnungspunkt)(?: (.+))?", top_id)
        if top_match or not top_id:
            number = top_match.group(1) if top_match else None
            top = f'{term("Tagesordnungspunkt", tip_id=f"debate-{index}")} {pulse_html.esc(number or "nicht erfasst")}'
        else:
            top = pulse_html.esc(top_id)
        debates.append(f'<li><strong>{label}</strong><p>{date_label} · {top}</p></li>')

    votes = []
    for vote in bill.get("votes") or []:
        label = pulse_html.esc(vote.get("title") or "Namentliche Abstimmung")
        if vote.get("detail_url"):
            label = f'<a href="{pulse_html.esc(pulse_html.source_url(vote["detail_url"], "bundestag-roll-call"))}">{label}</a>'
        date_label = pulse_html.format_date(vote.get("date")) or "Datum nicht erfasst"
        votes.append(f'<li><strong>{label}</strong><p>{date_label}</p></li>')

    latest_date = pulse_html.format_date(bill.get("latest_date")) or "Datum nicht erfasst"
    latest_step = term(str(bill.get("latest_step") or "Erfasster Vorgang"), tip_id="latest-event")
    latest = next((event for event in bill.get("events") or [] if event.get("date") == bill.get("latest_date") and event.get("kind") == bill.get("latest_step")), {})
    source_link = f' · <a href="{pulse_html.esc(_bill_event_href(latest["url"]))}">Quelle öffnen</a>' if latest.get("url") else ""
    authors = pulse_html.esc(", ".join(bill.get("introduced_by") or []) or "nicht erfasst")
    sections = (("verlauf", "Verlauf"), ("plenarstellen", "Beratungen im Plenum"), ("redner", "Rednerinnen und Redner"),
                ("abstimmungen", "Abstimmungen"), ("dokumente", "Dokumente"), ("quellen", "Quellen und Daten"))
    anchors = "".join(f'<a href="#{id}">{label}</a>' for id, label in sections)
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{pulse_html.esc(bill.get('title'))} · Bundestag-Puls</title>
  {pulse_html.page_head(features)}
  <style>{bill_page_styles()}</style>
</head>
<body class="bill-page">
  <div class="shell">
    {pulse_html.render_global_header(depth=1, active="bills", features=features)}
    <header class="page-header"><div>
      <nav class="local-nav" aria-label="Gesetzesvorhaben-Navigation"><a href="index.html">Alle Gesetzesvorhaben</a></nav>
      <span class="eyebrow">Gesetzesvorhaben</span><h1>{pulse_html.esc(bill.get('title') or 'Unbenanntes Gesetzesvorhaben')}</h1>
      <p class="bill-context">Zuletzt erfasst: {latest_date} · {latest_step}{source_link}</p>
      <p class="bill-caveat">Der zuletzt erfasste Schritt beschreibt die vorliegenden Quellen, nicht zwingend den aktuellen Rechtsstand.</p>
    </div></header>
    <nav class="bill-section-nav" aria-label="Abschnitte dieses Gesetzesvorhabens">{anchors}</nav>
    <main class="bill-detail-grid">
      <div class="bill-reading-lead"><section class="panel" id="verlauf"><h2>Verlauf</h2>
        {''.join(timeline) if timeline else '<p>Keine Verlaufseinträge in den erfassten Daten.</p>'}
      </section></div>
      <aside class="bill-support" aria-label="Beratungen im Plenum und Beteiligte">
        <section class="panel" id="plenarstellen"><h2>Beratungen im Plenum</h2>
          <p>Jeder Eintrag verknüpft einen {term("Tagesordnungspunkt", tip_id="plenarstellen-top")} einer Sitzung, an dem dieses Vorhaben behandelt wurde – auch ohne erfasste Rede. Ein gemeinsamer Tagesordnungspunkt kann mehrere Vorhaben betreffen.</p>
          {'<ul class="bill-debates">' + ''.join(debates) + '</ul>' if debates else '<p>Keine Beratungen im Plenum in den erfassten Daten verknüpft.</p>'}
        </section>
        <section class="panel" id="redner"><h2>Rednerinnen und Redner</h2>
          <p>Erfasste Personen: {len(speakers)}. Nach Zahl der erfassten Reden.</p>
          <p>Angegeben ist die {term('Fraktion', tip_id='speaker-fraktion')} oder {term('Sprechrolle', tip_id='speaker-role')} im Protokoll. Die Reden am gemeinsamen Tagesordnungspunkt können mehrere Vorhaben betreffen.</p>
          {speaker_list}
        </section>
        <section class="panel" id="abstimmungen"><h2>Abstimmungen</h2>
          <p>Hier sind nur verknüpfte {term('namentliche Abstimmungen', tip_id='vote-kind')} aufgeführt.</p>
          {'<ul class="bill-votes">' + ''.join(votes) + '</ul>' if votes else '<p>Keine namentliche Abstimmung in den erfassten Daten verknüpft.</p>'}
        </section>
      </aside>
      <div class="bill-reading-rest">
        <section class="panel" id="dokumente"><h2>Dokumente</h2>
          <p>Urheber der verknüpften Dokumente: {authors}.</p>
          {'<ul class="bill-documents">' + ''.join(documents) + '</ul>' if documents else '<p>Keine Dokumente in den erfassten Daten verknüpft.</p>'}
          {related_html}
        </section>
        <section class="panel" id="quellen"><h2>Quellen und Daten</h2>
          <p>DIP-Vorgang: {pulse_html.esc(bill.get('vorgang_id') or 'nicht erfasst')}. Die Übersicht zeigt nur die in den ausgewerteten Sitzungen verknüpften Quellen.</p>
          <p><a href="../sources.html">Quellen und Methode</a> · {term('Gesetzgebung', tip_id='law-definition')}</p>
          {render_bill_json_details('Erfasste Quelldaten', bill)}
        </section>
      </div>
    </main>
    <footer><a href="index.html">Alle Gesetzesvorhaben</a> · <a href="../overview.html">Sitzungen ansehen</a> · <a href="../sources.html">Quellen und Methode</a></footer>
  </div>
  {render_bill_help_script()}
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
    mp_lookup: dict[str, str] | None = None,
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
#                               the staged store (inside the rebuild, followed by
#                               person_registry.reconcile), so the list is complete
#                               rather than limited to people seen in sittings
#   2. collect_abgeordnete()  - read the store back and pool the records of each
#                               person (mps.person_id) into one profile
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
    stats = {"fetched": 0, "mdb": 0, "enriched": 0, "skipped_no_id": 0}
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
            if not canonical_dip_person_id(compact.get("id")):
                # A DIP person is identified by its id alone; without one, every
                # such row would share one name-party:Unbekannt record.
                stats["skipped_no_id"] += 1
                continue
            stats["mdb"] += 1
            fraktion_list = compact.get("fraktion") or []
            fraktion = fraktion_list[0] if fraktion_list else None
            party_name = derive.zusammenschluss(fraktion)
            party_id = pulse_store.upsert_party(store, party_name, now)
            display_name = (
                pulse_store.clean(compact.get("titel"))
                or pulse_store.clean(f"{compact.get('vorname') or ''} {compact.get('nachname') or ''}")
                or "Unbekannt"
            )

            profile_url = aw_id = aw_match = birth_year = gender = profession = wahlkreis = bundesland = None
            if profile_resolver is not None:
                profile = profile_resolver.resolve(
                    first_name=compact.get("vorname"),
                    last_name=compact.get("nachname"),
                    fraktion=fraktion,
                )
                if profile:
                    profile_url = profile.get("url")
                    aw_id = profile.get("id")
                    aw_match = profile.get("match")
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
                identity_key=pulse_store.mp_identity(
                    aw_politician_id=aw_id, aw_match=aw_match, dip_person_id=compact.get("id")
                ),
                dip_person_id=compact.get("id"),
                occurrence_id=roster_occurrence_id(compact.get("id")),
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
                aw_match=aw_match,
                person_roles_json=pulse_store.dumps(funktion) if funktion else None,
                is_mdb=True,
            )
    if stats["skipped_no_id"]:
        print(f"warning: [roster] {stats['skipped_no_id']} DIP persons with an MdB function have no id and were skipped", file=sys.stderr)
    return stats


# --- Identity consolidation -------------------------------------------------
#
# The same person can arrive from three directions with different keys: the DIP
# roster (dip_person_id), a protocol speaker (xml_redner_id) and an
# abgeordnetenwatch profile (aw_politician_id). The store holds them as separate
# mps rows; person_registry.reconcile decides which rows are the same human being
# and writes the result to mps.person_id.


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


def has_abgeordnete_page(mp: dict[str, Any]) -> bool:
    """An MdB, a person the registry gives a page, or anyone who spoke or
    contributed in a sitting (so cross-links from protocol and bill speaker
    lists never dangle, even for ministers)."""
    return bool(
        mp.get("is_mdb")
        or mp.get("has_page")
        or (mp.get("speech_count") or 0) > 0
        or (mp.get("contribution_count") or 0) > 0
    )


def collect_abgeordnete(conn: sqlite3.Connection) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Read MPs with party, speeches, and roll-call votes for the Abgeordnete
    pages. The store already settled who is the same Person (``mps.person_id``,
    written by ``registry.reconcile``): the DIP roster row carries the bio, the
    protocol-speaker rows the speeches, and this pools every record of a person
    into one entry. Returns the pooled MPs and a lookup from every occurrence
    binding (speech, roster, roll-call vote member), person key and unambiguous external id to the page id, so
    speaker lists can link without dangling. One grouped query each avoids N+1.

    Matching does not run here; see ``person_registry.reconcile`` for the join
    rules and which of them are durable."""
    # One query per relation, then grouped in Python - flat queries beat
    # a per-MP query (N+1) by a wide margin at roster size.
    base = conn.execute(
        f"""
        SELECT m.id, m.display_name, m.title, m.function, m.wahlperiode,
               m.profile_url, m.birth_year, m.gender, m.profession,
               m.wahlkreis, m.bundesland, m.aw_politician_id,
               m.aw_match, m.person_roles_json,
               m.is_mdb, m.dip_person_id, m.xml_redner_id, m.identity_key, pr.partition,
               p.name AS party
        FROM mps m
        LEFT JOIN parties p ON m.party_id = p.id
        LEFT JOIN person_records pr ON pr.id = m.id
        """
    ).fetchall()
    rows = [dict(r) for r in base]

    # All speeches with their protocol and agenda-item context, newest sitting
    # first. Feeds the "Reden im Bundestag" list on a profile page.
    speeches_by_mp: dict[str, list[dict[str, Any]]] = {}
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

    # Beiträge that are no Rede (Kurzintervention, Frage, Antwort ...) per MP and
    # kind: shown beside the Reden on a profile page, never added to them.
    contributions_by_mp: dict[str, dict[str, int]] = {}
    for row in conn.execute(
        "SELECT mp_id, kind, COUNT(*) AS n FROM contributions WHERE mp_id IS NOT NULL GROUP BY mp_id, kind"
    ).fetchall():
        contributions_by_mp.setdefault(row["mp_id"], {})[row["kind"]] = row["n"]

    contribution_links_by_mp: dict[str, list[dict[str, Any]]] = {}
    for row in conn.execute(
        "SELECT c.id, c.mp_id, c.kind, p.document_number, p.date "
        "FROM contributions c JOIN protocols p ON p.id=c.protocol_id "
        "WHERE c.mp_id IS NOT NULL ORDER BY p.date DESC, c.sequence, c.id"
    ):
        contribution_links_by_mp.setdefault(row["mp_id"], []).append(dict(row))

    # All roll-call votes cast by an MP, newest first. Feeds the "Namentliche
    # Abstimmungen" list and the participation tally.
    votes_by_mp: dict[str, list[dict[str, Any]]] = {}
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

    assignments = {row["id"]: row["person_id"] for row in conn.execute("SELECT id, person_id FROM mps")}
    current_person_ids = set(assignments.values())
    page_eligible = set()
    for namespace in ("speech", "contribution"):
        page_eligible.update(row[0] for row in conn.execute(
            "SELECT DISTINCT person_id FROM person_bindings WHERE id >= ? AND id < ?", _prefix_range(key_prefix(namespace))))
    historical = []
    for record in conn.execute("SELECT * FROM person_records ORDER BY id"):
        evidence = json.loads(record["evidence_json"])
        person_id = registry.resolve(conn, record["person_id"])
        if evidence.get("ever_mdb") or evidence.get("is_mdb"):
            page_eligible.add(person_id)
        # A record with no mps row is stale evidence. It keeps a page only for a
        # person this build has no current record of, or as the biography a
        # stale roster partner pools into its live person; a stale record of a
        # person with current records stays off the page (the source no longer
        # supports its name, party or link key; docs/stable-ids.md).
        if record["id"] not in assignments and (person_id not in current_person_ids or registry.is_stale_roster_partner(evidence)):
            evidence.update(id=record["id"], identity_key=record["identity_key"], is_mdb=False, partition=record["partition"])
            historical.append(evidence)
            assignments[record["id"]] = person_id
    rows.extend(row for row in historical if assignments[row["id"]] in page_eligible)
    components = {}
    for row in rows:
        components.setdefault(assignments[row["id"]], []).append(row)

    mps: list[dict[str, Any]] = []
    lookup: dict[str, str] = {}
    # Collapse each bucket into a single MP record: the roster row wins for the
    # biography fields, speeches and votes are pooled from every member row.
    for members in components.values():
        # Prefer roster, then speaker biography over roll-call attributes, then
        # the source key (mps.id is a hash); Daten recipes r1/r3 pick their row
        # in the same order (REPRESENTATIVE_SQL). The page key still comes from
        # the registry.
        members.sort(key=lambda r: (0 if r["is_mdb"] else 1 if r.get("xml_redner_id") else 2, r["identity_key"]))
        cid = assignments[members[0]["id"]]

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

        contribution_counts: dict[str, int] = {}
        for r in members:
            for kind, n in contributions_by_mp.get(r["id"], {}).items():
                contribution_counts[kind] = contribution_counts.get(kind, 0) + n

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
            "has_page": cid in page_eligible,
            "name": registry.clean_mp_name(first("display_name")),
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
            "contribution_counts": dict(sorted(contribution_counts.items())),
            "contribution_links": [c for r in members for c in contribution_links_by_mp.get(r["id"], [])],
            "contribution_count": sum(contribution_counts.values()),
            "votes": merged_votes,
            "vote_tally": tally,
        }
        mps.append(mp)
        # Only persons that get a page contribute to the link lookup.
        if has_abgeordnete_page(mp):
            for r in members:
                for key in registry.mp_keys(r):
                    lookup[key] = cid

    key_owners = {}
    for row in rows:
        for key in registry.mp_keys(row):
            key_owners.setdefault(key, set()).add(assignments[row["id"]])
    lookup = {key: owner for key, owner in lookup.items() if len(key_owners[key]) == 1}
    page_ids = {mp["id"] for mp in mps if has_abgeordnete_page(mp)}
    for binding in conn.execute("SELECT id, person_id FROM person_bindings"):
        if binding["person_id"] in page_ids:
            lookup[binding["id"]] = binding["person_id"]
    for person_id in page_ids:
        lookup[person_id] = person_id
    # Every retired or moved key resolves to the person its records are on now:
    # first through the durable alias chain, then through the guess that may have
    # moved that survivor's records.
    current = {registry.resolve(conn, row["home_person_id"]): row["person_id"]
               for row in conn.execute("SELECT DISTINCT home_person_id, person_id FROM person_records")}
    aliases = {}
    for row in conn.execute("SELECT id FROM person_aliases"):
        survivor = registry.resolve(conn, row["id"])
        aliases[row["id"]] = current.get(survivor, survivor)
    for home, person in current.items():
        if home != person:
            aliases.setdefault(home, person)
    # Person keys become file names under abgeordnete/; a store edited or damaged
    # since its last validation must not write outside it or over the index.
    aliases = {key: target for key, target in aliases.items() if key not in page_ids}  # a live page is never overwritten by a redirect
    folded: dict[str, str] = {}
    for key in (*page_ids, *aliases):
        if not registry.valid_person_key(key):
            raise registry.RegistryError(f"Invalid person key {key!r} in the build store; restore the build-store backup")
        if folded.setdefault(key.casefold(), key) != key:
            raise registry.RegistryError(f"Person keys {folded[key.casefold()]!r} and {key!r} differ only by case; restore the build-store backup")
    aliases_of: dict[str, list[str]] = {}
    for alias, target in aliases.items():
        aliases_of.setdefault(target, []).append(alias)
    for mp in mps:
        mp["aliases"] = sorted(aliases_of.get(mp["id"], ()))
    # Stable, useful order: most speeches first, then alphabetical.
    mps.sort(key=lambda mp: (-(mp["speech_count"] or 0), str(mp["name"]).lower()))
    return mps, lookup


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
# The <id> in the file name is the issued person key from the registry,
# which is also what mp_lookup maps source occurrences and external ids to,
# so speaker links from dossier and bill pages resolve here.
def render_contributions_panel(mp: dict[str, Any]) -> str:
    """Beiträge that are no Rede, by kind. Never part of "Reden"."""
    counts = mp.get("contribution_counts") or {}
    if not counts:
        return ""
    for kind in counts:
        speech_kinds.validate_kind(kind)
    fields = "".join(
        f'<div class="field"><span>{pulse_html.esc(speech_kinds.KIND_LABELS[kind][1])}</span>'
        f"<strong>{pulse_html.esc(counts[kind])}</strong></div>"
        for kind in speech_kinds.CONTRIBUTION_KINDS
        if counts.get(kind)
    )
    links = "".join(
        f'<li><a href="../protocols/plenarprotokoll-{slugify_document_number(c["document_number"])}.html#contribution-{pulse_html.esc(c["id"])}">'
        f'BT-PlPr. {pulse_html.esc(c["document_number"])} · {pulse_html.esc(speech_kinds.KIND_LABELS[c["kind"]][0])}</a></li>'
        for c in mp.get("contribution_links") or []
    )
    return (
        '<section class="panel">'
        "<h2>Weitere Beiträge (keine Reden)</h2>"
        "<p>Zwischenfragen, schriftliche Beiträge, Kurzinterventionen, Erwiderungen sowie Fragen und Antworten zählen gesondert.</p>"
        f'<div class="field-grid">{fields}</div><ul>{links}</ul>'
        "</section>"
    )


def render_abgeordnete_detail(
    mp: dict[str, Any],
    features: Selection | None = None,
    publication_domains: dict[str, Any] | None = None,
) -> str:
    features = features or publication_selection()
    # Joined roll-call records may supply a Bundestag profile when no
    # abgeordnetenwatch profile exists. Keep the link's source label accurate.
    profile_link = ""
    if mp.get("profile_url"):
        profile_href = pulse_html.source_url(mp["profile_url"], "public-profile")
        profile_source = "abgeordnetenwatch.de" if (urlparse(profile_href).hostname or "").endswith("abgeordnetenwatch.de") else "Bundestag"
        profile_link = (
            f'<a class="source-link" href="{pulse_html.esc(profile_href)}" target="_blank" rel="noopener">'
            f"{profile_source}-Profil ↗</a>"
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
            f'<span class="meta"><a href="{pulse_html.esc(href)}">BT-PlPr. {pulse_html.esc(speech.get("document_number"))}</a><br>{pulse_html.esc(speech.get("date") or "")} · {pulse_html.esc(page)}</span>'
            f'<span><strong>{heading}</strong>{("<br>" + snippet) if snippet else ""}</span>'
            "</li>"
        )

    votes = []
    for vote in mp.get("votes") or []:
        direction = (vote.get("vote") or "").lower()
        label = {"yes": "Ja", "no": "Nein", "abstain": "Enthalten", "absent": "nicht abgegeben"}.get(direction, vote.get("vote") or "—")
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
        {render_contributions_panel(mp)}
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
def _write_person_page(abg_dir: Path, key: Any, text: str) -> None:
    """Write ``abgeordnete/<key>.html`` without trusting the caller: the key is
    checked again (a filename, no path), whatever already sits at the target (a
    symlink above all) is removed first, and the file is created with
    O_EXCL|O_NOFOLLOW, so the write cannot land outside abg_dir."""
    if not registry.valid_person_key(key):
        raise registry.RegistryError(f"Invalid person key {key!r} for a page under {abg_dir}; restore the build-store backup")
    _write_new_file(abg_dir / f"{key}.html", text)


def _write_new_file(path: Path, text: str) -> None:
    """Replace ``path`` by a new regular file, never writing through a link there."""
    path.unlink(missing_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)


def write_abgeordnete_pages(
    output_dir: Path,
    mps: list[dict[str, Any]],
    features: Selection | None = None,
    publication_domains: dict[str, Any] | None = None,
) -> dict[str, Any]:
    features = features or publication_selection()
    abg_dir = output_dir / "abgeordnete"
    abg_dir.mkdir(parents=True, exist_ok=True)
    # The stale-page sweep and every page write below happen in this directory;
    # an abgeordnete/ that is a link out of the output tree is refused first.
    if abg_dir.resolve() != output_dir.resolve() / "abgeordnete":
        raise registry.RegistryError(f"{abg_dir} resolves outside {output_dir}; person pages are not written through it")
    # Detail pages for MdBs and for anyone who actually spoke (so cross-links from
    # protocol/bill speaker lists never dangle, even for ministers/guests).
    detail_mps = [mp for mp in mps if has_abgeordnete_page(mp)]
    expected_pages = {f"{key}.html" for mp in detail_mps for key in [mp["id"]] + mp.get("aliases", [])}
    for stale_page in abg_dir.glob("*.html"):
        if stale_page.name != "index.html" and stale_page.name not in expected_pages:
            stale_page.unlink()
    for mp in detail_mps:
        _write_person_page(abg_dir, mp["id"], render_abgeordnete_detail(mp, features, publication_domains))
    for mp in detail_mps:
        for alias in mp.get("aliases", []):
            target = pulse_html.esc(f"{mp['id']}.html")
            _write_person_page(abg_dir, alias, f'<!doctype html><html lang="de"><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={target}"><link rel="canonical" href="{target}"><title>Person</title><a href="{target}">Zur Person</a></html>')
    _write_new_file(abg_dir / "index.html", render_abgeordnete_index(mps, features, publication_domains))
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

#: "this <period>" demonstrative phrase per period_kind, for wording that must
#: not assume every fact is a weekly one (T11). It is its own phrase, not
#: "diese/dieser" + noun, because German grammatical gender differs between
#: "diese Woche" (feminine) and "dieser Monat" (masculine).
_PERIOD_DEMONSTRATIVE = {
    "week": "Diese Woche",
    "month": "Dieser Monat",
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
               {derive.ZUSAMMENSCHLUSS_SQL} AS fraktion, s.sprechrolle AS sprechrolle,
               m.person_id, m.xml_redner_id, m.aw_politician_id, m.aw_match, m.dip_person_id,
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
            "fraktion": pulse_html.speaker_party({"fraktion": resolved["fraktion"], "sprechrolle": resolved["sprechrolle"]}),
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
            "fraktion": pulse_html.speaker_party({"fraktion": first["fraktion"], "sprechrolle": first["sprechrolle"]}),
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
    # Resolve issuer/type from the receipt's exact document id, never its number.
    row["receipts"] = []
    for receipt in fact_row.get("receipts") or []:
        receipt = dict(receipt)
        if receipt["entity_kind"] == "document":
            document = conn.execute(
                "SELECT herausgeber, document_type FROM documents WHERE id = ?",
                (receipt.get("source_entity_id"),),
            ).fetchone()
            if document:
                receipt.update(herausgeber=document["herausgeber"], dokumentart=document["document_type"])
        row["receipts"].append(receipt)
    return row


def _fact_status_text(row: dict[str, Any] | None, *, with_note: bool = True) -> tuple[str, str | None, bool]:
    """(cell text, in-page anchor or None, whether it is posted) for one
    metric's cell in a period. None row: the metric was not built this
    update (e.g. --enrich without votes). An incomplete period names the
    sitting that keeps it incomplete when ``write_facts_pages`` attached a
    ``gap_note`` (the archive table keeps the short text and puts the note in
    a tooltip; the week page shows it)."""
    if row is None:
        return "–", None, False
    if not row.get("complete"):
        note = row.get("gap_note") if with_note else None
        return (f"unvollständig erfasst: {note}" if note else "unvollständig erfasst"), None, False
    if row.get("publishable"):
        return f"Platz {row['rank']}", row["metric_id"], True
    text = facts.comparison_clause(row) if row.get("withheld") in facts.WITHHELD_CLAUSES else "kein Fakt"
    return text, None, False


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
    mp_lookup: dict[str, str],
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
            label = _document_citation({
                "dokumentnummer": document_number, "url": receipt.get("official_url"),
                "herausgeber": receipt.get("herausgeber"), "dokumentart": receipt.get("dokumentart"),
            })
            items.append(
                f'<li><a href="{pulse_html.esc(url)}">{pulse_html.esc(label)}</a></li>'
                if url else f"<li>{pulse_html.esc(label)}</li>"
            )
            continue
        href = resolve_entity_link(
            "document", document_number, mp_lookup=mp_lookup, document_numbers=document_numbers, bill_slugs=bill_slugs
        )
        protocol_text = f"BT-PlPr. {document_number}"
        bits = [
            f'<a href="../{pulse_html.esc(href)}">{pulse_html.esc(protocol_text)}</a>' if href else pulse_html.esc(protocol_text)
        ]
        if receipt.get("page"):
            bits.append(f"Seite {pulse_html.esc(receipt['page'])}{pulse_html.esc(receipt.get('page_quadrant') or '')}")
        if receipt["entity_kind"] == "speech" and index < len(speaker_mps):
            mp = speaker_mps[index]
            mp_href = pulse_html.mp_page_href(
                {
                    "abgeordnetenwatch": (
                        {"id": mp.get("aw_politician_id"), "match": mp.get("aw_match")} if mp.get("aw_politician_id") else {}
                    ),
                    "person_id": mp.get("person_id"),
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
    return f'<div class="sources"><span class="eyebrow">Belege</span><ul>{"".join(items)}</ul></div>'


def _render_fact_section(
    row: dict[str, Any],
    metric: dict[str, Any],
    resolved: bool,
    series: list[dict[str, Any]],
    series_index: dict[str, int],
    *,
    mp_lookup: dict[str, str],
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
            cell_row = period_rows.get(metric["id"])
            text, anchor, posted = _fact_status_text(cell_row, with_note=False)
            any_posted = any_posted or posted
            if posted:
                cells.append(f'<td><a href="{pulse_html.esc(period_key)}.html#{pulse_html.esc(anchor)}">{pulse_html.esc(text)}</a></td>')
            else:
                note = (cell_row or {}).get("gap_note") if cell_row and not cell_row.get("complete") else None
                title = f' title="{pulse_html.esc(note)}"' if note else ""
                cells.append(f'<td class="muted"{title}>{pulse_html.esc(text)}</td>')
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
      <p class="lead">Ein automatisch berechneter, ungewöhnlicher Wert je Woche mit Sitzung und je Monat
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
    mp_lookup: dict[str, str],
    document_numbers: set[str],
    bill_slugs: set[str],
    features: Selection | None = None,
) -> str:
    features = features or publication_selection()
    sample = period_rows[0]
    period_kind = sample["period_kind"]
    demonstrative = _PERIOD_DEMONSTRATIVE.get(period_kind, _PERIOD_DEMONSTRATIVE["week"])
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
      Diese Karten werden bei jedem Neubau neu erzeugt; Datenkorrekturen und Änderungen an Regeln oder Formulierungen können sie verändern.
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
        per_period = "je Woche mit Sitzung" if period_plural == "Wochen" else "je Monat"
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
      <p class="lead">Jede Woche mit Sitzung liefert für sechs Kennzahlen, jeder Monat für zwei weitere,
      höchstens einen Wert. Veröffentlicht wird eine Kennzahl nur, wenn sie ungewöhnlicher ist als
      {pulse_html.esc(floor_pct)} % der vergleichbaren Perioden seit Beginn der Erfassung - und, bei
      einigen Kennzahlen, eine zusätzliche absolute Schwelle erreicht.</p>
    </header>
    <section>
      <h2>Die Regel</h2>
      <ol class="method-list">
        <li><strong>Beobachtung</strong><span>Je Periode (Woche mit Sitzung oder Monat) und Kennzahl
        der größte oder kleinste Wert unter den Kandidatenzeilen dieser Periode, ihre Anzahl - bei
        „Die meisten ersten Reden der Woche“ - oder, bei den beiden monatlichen Kennzahlen, die
        größte Summe über alle Kandidatenzeilen einer Abgeordneten oder eines Vorgangs im Monat.
        Eine Periode ohne passende Zeile liefert keine Beobachtung.</span></li>
        <li><strong>Vergleichbarkeit</strong><span>Der Anteil der vorherigen Beobachtungen, den
        der Wert in der Richtung der Kennzahl schlägt (mehr beim Maximum, weniger beim Minimum).
        Verglichen wird zuerst mit der laufenden Wahlperiode, sobald sie genug frühere Perioden
        zählt (mindestens {facts.MIN_HISTORY_WEEKS} Wochen mit Sitzung bzw. mindestens
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
        <li><strong>Was als Rede zählt</strong><span>Alle Kennzahlen über Reden, Zeichen und Redner
        zählen nur Reden. Kurzinterventionen, Erwiderungen sowie die Fragen und Antworten der
        Befragung der Bundesregierung und der Fragestunde sind keine Reden; sie werden als eigene
        Beiträge erfasst und in keiner dieser Kennzahlen mitgezählt. Die Eingangsberichte einer
        Befragung sind Reden.</span></li>
      </ol>
    </section>
    <section>
      <h2>Die sechs wöchentlichen Kennzahlen</h2>
      <ul class="method-list">{weekly_items}</ul>
    </section>
    <section>
      <h2>Die zwei monatlichen Kennzahlen</h2>
      <p class="lead">Dieselbe Regel, mit Monaten statt Wochen mit Sitzung als Perioden: die Beobachtung
      summiert dafür die Kandidatenzeilen einer Abgeordneten oder eines Vorgangs über alle Sitzungen
      des Monats, statt die einzelne größte Zeile zu nehmen.</p>
      <ul class="method-list">{monthly_items}</ul>
    </section>
    <section>
      <h2>Was sich bei einem Neubau ändern kann</h2>
      <p>Wochen- und Monatskarten werden bei jedem Neubau der Website neu erzeugt.
      Korrekturen an den Daten und Änderungen an den Regeln (etwa Schwellen oder Mindestwerten)
      können frühere Karten verändern; auch geänderte Formulierungen erscheinen auf ihnen.
      Lässt sich ein Beleg nicht mehr auflösen, entfällt die zugehörige Karte.</p>
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
    mp_lookup: dict[str, str] | None,
    document_numbers: set[str],
    bill_slugs: set[str],
    features: Selection | None = None,
    entries: list[dict[str, Any]] | None = None,
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
            # An incomplete period says which sitting keeps it incomplete. The
            # store holds no acquisition state, so the reports the build is
            # holding and the cached catalog are read again here, exactly as the
            # engine judged them.
            notes = facts.gap_notes(
                facts.load_protocols(conn),
                facts.completeness_from_entries(entries or []),
                facts.load_sitting_catalog(output_dir / "data" / facts.CATALOG_FILENAME),
            )
            for row in all_facts:
                if not row["complete"]:
                    metric = facts.REGISTRY_BY_ID.get(row["metric_id"])
                    note = notes.get((row["period_kind"], row["period_key"], (metric or {}).get("coverage")))
                    if note:
                        row["gap_note"] = note
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
                  <span class="eyebrow">BT-PlPr. {pulse_html.esc(protocol.get('dokumentnummer'))}</span>
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
      <div><span>Verfolgte Gesetzesvorhaben</span><strong>{pulse_html.esc(bill_count)}</strong></div>
      <div><span>Zuletzt erzeugt</span>
        <strong>{pulse_html.esc(generated_latest.get('dokumentnummer', ''))}</strong>
        <em>{pulse_html.esc(generated_latest.get('datum', ''))}</em>
      </div>
    </section>
    <div class="periods">{period_badges}</div>
    <div class="section-head">
      <h2>Erzeugte Dossiers</h2>
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
      Das XML-Protokoll ist maßgeblich; DIP-API-Daten ergänzen jede Sitzung. Mit --detail-limit 0 werden Dossiers für alle geholten Protokolle erzeugt, mit --detail-limit -1 nur der Katalog. <a href="puls.html">Wochenübersicht</a> · <a href="bills/index.html">Gesetzesvorhaben</a> · <a href="abgeordnete/index.html">Abgeordnete</a>{database_footer_link} · <a href="sources.html">Quellen</a>.
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
                <span class="eyebrow">BT-PlPr. {pulse_html.esc(protocol.get('dokumentnummer'))} · WP {pulse_html.esc(protocol.get('wahlperiode'))}</span>
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
    parliamentary_items = "".join(
        f'<li id="parlament-{pulse_html.esc(entry["slug"])}">'
        f'<strong>{pulse_html.esc(term)}</strong><span>{pulse_html.esc(entry["lang"])} '
        f'<a href="{pulse_html.esc(pulse_html.source_url(entry["source_url"], "bundestag-dip"))}">'
        f'{pulse_html.esc(entry.get("source_label", "Erläuterung beim Deutschen Bundestag"))}</a></span></li>'
        for term, entry in pulse_html.PARLIAMENTARY_GLOSSARY.items()
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
          <li><strong>Was als Rede zählt</strong><span>Eine Rede ist ein Redebeitrag zu einem Tagesordnungspunkt. Kurzinterventionen, Erwiderungen sowie die Fragen und Antworten der Befragung der Bundesregierung und der Fragestunde zählen nicht als Reden, sondern als eigene Beiträge (Tabelle „contributions“ der Daten); die Eingangsberichte einer Befragung sind Reden. Für Zeichenzahlen zählt nur der Text der Rede.</span></li>
          <li><strong>Meiste Reden</strong><span>Tagesordnungspunkte nach Anzahl der extrahierten Reden sortiert. Die Balken zeigen Redeanteil und Textanteil an der gesamten Sitzung. Beiträge, die keine Reden sind, gehen nicht ein.</span></li>
          <li><strong>Redner und Fraktionen</strong><span>Aus den Redner-Knoten im XML-Protokoll gelesen. Regierungsrollen werden angezeigt, wenn das XML eine Rolle statt einer Fraktion liefert.</span></li>
          <li><strong>Abgeordnetenprofile</strong><span>Jeder Name verlinkt das passende Profil auf abgeordnetenwatch.de. Zugeordnet wird über die Bundestags-Redner-ID, ersatzweise über Name und Fraktion; nur eindeutige Treffer werden verlinkt, mehrdeutige bleiben ohne Link.</span></li>
          <li><strong>Verknüpfte Dokumente</strong><span>Kombiniert Drucksachen, die direkt im Protokoll verlinkt sind, mit zugehörigen DIP-Vorgangspositionen der Sitzung.</span></li>
          <li><strong>Abstimmungspanels</strong><span>Werden nur angezeigt, wenn eine namentliche Abstimmung am selben Datum über überlappende Drucksachennummern einem Tagesordnungspunkt zugeordnet werden kann.</span></li>
          <li><strong>Erzeugtes JSON</strong><span>Jedes Dossier verlinkt den Zwischenbericht als JSON, damit Extraktion und Anreicherung direkt geprüft werden können.</span></li>
          <li id="ki-zusammenfassungen"><strong>KI-Zusammenfassungen</strong><span>Sie sind als „KI-generiert · nicht redaktionell geprüft“ markiert und verlinken drei bis fünf technisch geprüfte Belegstellen. Diese Linkprüfung beweist weder sachliche Richtigkeit noch Ausgewogenheit oder Vollständigkeit.</span></li>
          {database_method_item}
          {licence_method_item}
        </ul>
      </section>
      <section class="panel" id="{pulse_html.VORGANGSTYP_GLOSSARY_ANCHOR}">
        <h2>Vorgangstypen im Debattenprofil</h2>
        <p>Jede Vorgangsposition einer Sitzung gehört zu einem Vorgang im DIP, und jeder Vorgang hat dort einen Typ. Das Debattenprofil auf der Puls-Seite zählt je Kalenderwoche jeden Tagesordnungspunkt einmal pro vorkommendem Vorgangstyp: Wiederholte Vorgangspositionen desselben Typs zählen einmal, mehrere verschiedene Typen desselben Tagesordnungspunkts jeweils einmal. Die Bezeichnungen folgen der DIP-Klassifikation; die Erläuterungen fassen zusammen, was jeweils dahintersteht.</p>
        <ul class="method-list glossary">
          {vorgangstyp_items}
        </ul>
      </section>
      <section class="panel" id="parlamentarische-begriffe">
        <h2>Parlamentarische Begriffe</h2>
        <p>Kurze Erläuterungen zu Dokumenten, Beratungen und Beteiligten. Die Links führen zu den offiziellen Quellen des Deutschen Bundestages.</p>
        <ul class="method-list glossary">{parliamentary_items}</ul>
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
      Quellenlinks verweisen auf öffentliche Bundestags- und DIP-Datensätze. Verfügbarkeit und genaue Inhalte werden von diesen offiziellen Diensten bestimmt. <a href="overview.html">Sitzungen</a> · <a href="bills/index.html">Gesetzesvorhaben</a> · <a href="abgeordnete/index.html">Abgeordnete</a>
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

    vote_records = sum(len(list(derive.iter_report_votes(report))) for report in reports)
    profile_targets = len(abg_mps) + sum(len(item.get("xml_speakers") or []) for item in agenda_items)
    profile_records = sum(1 for mp in abg_mps if mp.get("profile_url")) + sum(
        1
        for item in agenda_items
        for speech in (item.get("xml_speakers") or [])
        if ((speech.get("speaker") or {}).get("abgeordnetenwatch") or {}).get("url")
    )
    for report in reports:
        for _, vote in derive.iter_report_votes(report):
            for member in vote.get("members") or []:
                profile_targets += 1
                if (member.get("abgeordnetenwatch") or {}).get("url"):
                    profile_records += 1
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
        # Selected is a configuration; requested is something this run did. An
        # offline render selects the default enrichments too but fetches nothing.
        requested = selected_id in selected and acquisition_attempted
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
    vote_items = sum(len(list(derive.iter_report_votes(report))) for report in reports)
    summary_items = sum(1 for item in agenda_items if usable_llm_summary(item.get("llm_summary")))
    profile_targets = len(abg_mps)
    profile_count = sum(1 for mp in abg_mps if mp.get("profile_url"))
    for item in agenda_items:
        for speech in item.get("xml_speakers") or []:
            profile_targets += 1
            if ((speech.get("speaker") or {}).get("abgeordnetenwatch") or {}).get("url"):
                profile_count += 1
    for report in reports:
        for _, vote in derive.iter_report_votes(report):
            for member in vote.get("members") or []:
                profile_targets += 1
                if (member.get("abgeordnetenwatch") or {}).get("url"):
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
      <p>Sitzungen, Abstimmungen, Gesetzesvorhaben und Abgeordnetenprofile werden immer dann gezeigt, wenn sie für die jeweilige Seite gelten. Fehlende oder unvollständige Daten werden direkt am betroffenen Inhalt erklärt.</p>
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
    mp_lookup: dict[str, str],
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
    authoritative_catalog: bool = False,
    vorgang_cache: dict[str, Any] | None = None,
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
    today = resolve_today(today)

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
    # for an --offline render, and what completeness is judged against. Only a
    # build that fetched the whole DIP catalog may write it: an offline render
    # holds the cache plus dossier-derived protocols, and rewriting the file
    # from that would turn a partial list into an "authoritative" one.
    catalog_path = output_dir / "data" / facts.CATALOG_FILENAME
    if authoritative_catalog:
        dip.write_text_atomic(
            catalog_path,
            json.dumps(
                {"authoritative": True, "fetched_at": dip.utc_now(), "protocols": protocols},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
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
        "collect_votes_archive": collect_votes_archive,
        "write_votes_archive_page": write_votes_archive_page,
        "write_abgeordnete_pages": write_abgeordnete_pages,
        "write_facts_pages": write_facts_pages,
        "database_path": database_path,
        "no_persist": no_persist,
        "document_numbers": document_numbers,
        "bill_slugs": bill_slugs or set(),
        "vorgang_cache": vorgang_cache,
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
        f"fakten: {facts_output['posted']} Fakten in {facts_output['periods']} Perioden (Wochen und Monate)",
        file=sys.stderr,
    )
    votes_output = components["votes"].write_pages(output_dir, component_context)
    if votes_output:
        print(f"abstimmungen: {votes_output['count']} im Archiv", file=sys.stderr)
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
            features=features,
            today=today,
            week=week,
        ),
        encoding="utf-8",
    )
    pulse_path.write_text(
        render_front_page(
            entries, database_href=database_href, features=features, today=today, week=week,
            vorgang_cache=vorgang_cache,
        ),
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


# Enrichments an online update acquires unless an operator vetoes them. Votes
# are here because a build that silently skips them records every sitting as
# "not requested" and leaves the store without the newest roll calls.
DEFAULT_ENRICHMENTS: tuple[str, ...] = ("votes",)

# Order in which sources speak, lowest first; shown by --explain-config.
ENRICHMENT_PRECEDENCE = (
    "built-in default < features.json < features.local.json < --features-file < "
    "BUNDESTAG_PULSE_ENRICHMENTS < --enrich / --vote-scan-pages N > 0; "
    "a veto (--no-votes, --vote-scan-pages 0, a '-votes' entry, legacy 'disable') "
    "beats every default and every layer below it, and --no-votes beats all of them"
)


# Build the final Selection for this run, then let features.resolve() close it
# over dependencies and validate it.
def resolve_from_args(args: argparse.Namespace, *, root: Path) -> EnrichmentSelection:
    """Resolve operator acquisition as one ordered, provenance-carrying stream."""
    current: set[str] = set()
    operations: list[tuple[str, str, str]] = []
    # Ids an operator explicitly switched off. A default never re-adds one; a
    # later explicit add lifts the veto again (later layers win).
    vetoed: set[str] = set()

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

    def veto(token: str, source: str) -> None:
        # A "-id" entry of an enrich list. Unlike the legacy disable key it is
        # validated: a mistyped veto must not silently leave the default on.
        for value in validate_id(token[1:], source):
            remove([value], source)

    def replace(values: Any, source: str) -> None:
        tokens = _split_feature_tokens(values)
        previous = sorted(current)
        current.clear()
        for value in previous:
            operations.append(("overridden", value, source))
        for token in tokens:
            if token.startswith("-"):
                veto(token, source)
                continue
            for value in validate_id(token.lstrip("+"), source):
                current.add(value)
                vetoed.discard(value)
                operations.append(("replace", value, source))

    def add(values: Any, source: str) -> None:
        for token in _split_feature_tokens(values):
            if token.startswith("-"):
                veto(token, source)
                continue
            for value in validate_id(token.lstrip("+"), source):
                current.add(value)
                vetoed.discard(value)
                operations.append(("add", value, source))

    def remove(values: Any, source: str) -> None:
        for token in _split_feature_tokens(values):
            raw = token[1:] if token.startswith("-") else token
            if raw not in ENRICHMENT_REGISTRY:
                continue
            current.discard(raw)
            vetoed.add(raw)
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
    scan_pages = getattr(args, "vote_scan_pages", None)
    if scan_pages is not None and scan_pages > 0:
        add(("votes",), "--vote-scan-pages")
    elif scan_pages == 0:
        remove(("votes",), "--vote-scan-pages 0")
    # Defaults come last, so a config file that lists other enrichments (a
    # replacement of the set) cannot silently turn them off. Only a veto can.
    for default in DEFAULT_ENRICHMENTS:
        if default not in current and default not in vetoed:
            current.add(default)
            operations.append(("add", default, "default"))
    # --no-votes is the operator's last word: it beats --enrich votes and
    # --vote-scan-pages N > 0 given on the same command line.
    if getattr(args, "no_votes", False):
        remove(("votes",), "--no-votes")
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
    print("  Wochenübersicht, Sitzungen, Gesetzesvorhaben, Abgeordnete, Quellen")
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
    print(f"precedence={ENRICHMENT_PRECEDENCE}")
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


# The Daten page shows each recipe's SQL next to its rows and offers it for
# copying, so an override must carry exactly this build's recipes: the rows
# came from the manifest's SQL, and showing any other SQL beside them (local or
# tampered, sqlite3 dot-commands included) would misstate where they came from.
# Titles are display copy and come from RECIPES, like recipes_hash ignores them.
def _manifest_recipe_problems(recipes: list[Any]) -> list[str]:
    if not all(
        isinstance(r, dict)
        and isinstance(r.get("id"), str)
        and isinstance(r.get("rows"), list)
        and (r.get("empty_reason") is None or isinstance(r.get("empty_reason"), str))
        for r in recipes
    ):
        return ["recipes[] entries need id, rows and empty_reason (text or null)"]
    problems = []
    for index, recipe in enumerate(recipes):
        local = RECIPES_BY_ID.get(recipe["id"])
        if local is None:
            problems.append(f"recipes[{index}] id {recipe['id']!r} is not a recipe of this build")
        elif recipe.get("sql") != local["sql"]:
            problems.append(
                f"recipes[{index}] ({recipe['id']}) SQL differs from this build's; export the data with this version of the code"
            )
    ids = [recipe["id"] for recipe in recipes]
    expected = [recipe["id"] for recipe in RECIPES]
    if not problems and ids != expected:
        problems.append(f"recipes ids {ids} differ from this build's {expected}")
    return problems


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
    if isinstance(manifest.get("recipes"), list):
        problems.extend(_manifest_recipe_problems(manifest["recipes"]))
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
        help=(
            "Update-time data enrichment: votes, aw-profiles, mp-roster, or all; repeatable. "
            "votes is on by default (turn it off with --no-votes). A config file's enrich list "
            "replaces earlier config layers but never removes a default; only a veto does "
            "(see --explain-config for the precedence)."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help=(
            "Acquire only the newest N Bundestag protocols of --protocol-wahlperiode (0 = no cap). "
            "The catalog itself is always fetched whole: completeness is judged against it."
        ),
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
        help=(
            "Acquire only this protocol, e.g. 21/84 (repeatable). The catalog and every cached dossier "
            "are kept; only the named sittings are refreshed."
        ),
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
        "--fetch-xml",
        action="store_true",
        help=(
            "Download the Plenarprotokoll XML of every cached report that has none in OUTPUT_DIR/data/xml/ "
            "(public bundestag.de files, no API key), then exit. --offline --repersist re-reads Reden and "
            "Beiträge from those files. Reports built before they were kept need this once."
        ),
    )
    parser.add_argument(
        "--repersist",
        action="store_true",
        help=(
            "With --offline: persist every cached report into a fresh SQLite store (roster rows kept) and "
            "swap it in only when all of them persisted, so fixes that derive values at persist time apply "
            "without a network. Reden and Beiträge are first re-read from the cached XML in OUTPUT_DIR/data/xml/ "
            "(see --fetch-xml). Any failure exits 1 and leaves the previous store untouched; a store whose "
            "content would not change (timestamps aside) is left as it is."
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
        "--backfill-incomplete",
        action="store_true",
        help=(
            "Acquire exactly the sittings the last build left missing or not fully acquired (the list every build "
            "prints under 'incomplete'), ignoring --limit and --detail-limit. Every other cached dossier is kept."
        ),
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
        help=(
            "Roll-call list pages scanned per sitting (default 30: votes are acquired by default). "
            "0 turns vote acquisition off, like --no-votes. A sitting whose date lies beyond the "
            "window is recorded as partial (scan_budget_exhausted); raise this to reach older sittings."
        ),
    )
    parser.add_argument(
        "--no-votes",
        action="store_true",
        help="Skip roll-call vote acquisition for this update (cached votes and their state are kept).",
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
            "Legislative period --limit counts the newest protocols of "
            "(default 21; use 0 to count across all periods)."
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
    if args.vote_scan_pages is not None and args.vote_scan_pages < 0:
        parser.error("--vote-scan-pages must be 0 (off) or a positive number of list pages")
    if args.backfill_incomplete and args.document_number:
        parser.error("--backfill-incomplete cannot be combined with --document-number: it acquires the sittings the last build listed as incomplete")
    if args.repersist and not args.offline:
        parser.error(
            "--repersist re-persists the cached reports and needs --offline; "
            "an online update already rebuilds the store from every cached report"
        )
    if args.repersist and args.no_persist:
        parser.error("--repersist writes the SQLite store; it cannot be combined with --no-persist")
    if args.backfill_incomplete and args.offline:
        parser.error("--backfill-incomplete needs the network: an --offline build acquires nothing")
    if args.fetch_xml and (args.offline or args.repersist or args.backfill_incomplete):
        parser.error(
            "--fetch-xml downloads the missing XML files and exits; run --offline --repersist as a second command"
        )
    if args.offline and args.data_manifest and is_url(args.data_manifest):
        parser.error(f"--offline cannot fetch --data-manifest {args.data_manifest} over the network; pass a local path")
    if args.no_persist and args.data_base_url:
        print(
            "warning: --data-base-url has no effect with --no-persist (no store, no download links)",
            file=sys.stderr,
        )
    return args


def data_manifest_source(args: argparse.Namespace) -> str | None:
    return getattr(args, "data_manifest", None) or os.environ.get("BUNDESTAG_PULSE_DATA_MANIFEST")


# Dossiers are written before run_data_pipeline produces the manifest that every
# other page's "Daten" link keys on, so their footer predicts it from the
# export's own condition: a manifest override, or a persisted store to export.
# The one miss is an export that raises DataExportUnavailable (old SQLite);
# database.html is then the fallback page, which says exactly that.
def dossier_database_page_href(args: argparse.Namespace, database_path: Path) -> str | None:
    if data_manifest_source(args) or (not args.no_persist and database_path.exists()):
        return "../database.html"
    return None


# CLI > env > default, read in the layer that actually runs the build (not in
# parse_args itself), per the DX addendum. getattr() throughout: main() must
# keep working against the pre-existing test stub that mocks parse_args() with
# a bare SimpleNamespace lacking these attributes.
def resolve_data_export_options(args: argparse.Namespace) -> tuple[str, str | None, str, str | None]:
    base_url_raw = (
        getattr(args, "data_base_url", None) or os.environ.get("BUNDESTAG_PULSE_DATA_BASE_URL") or "data/exports/"
    )
    manifest_raw = data_manifest_source(args)
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
def run_facts_engine(
    database_path: Path,
    entries: list[dict[str, Any]],
    catalog: facts.SittingCatalog | None,
    today: date | None = None,
) -> dict[str, Any]:
    """Compute the facts for a store no rebuild staged in this build. They are
    computed read-only; a changed snapshot is written into a staged copy that
    replaces the store, so the published store never has a write (or SQLite's
    rollback journal) beside it."""
    database_path = Path(database_path).resolve()
    with registry.writer_lock(database_path):
        store = facts.open_readonly(database_path)
        try:
            pulse_store.require_current_schema(store)
            return facts.compute_and_store(
                store,
                facts.ALL_REGISTRY,
                facts.completeness_from_entries(entries),
                catalog=catalog,
                built=facts.built_sources(store),
                today=today,
                write=lambda snapshot: _write_facts_staged(database_path, snapshot),
            )
        finally:
            store.close()


def _write_facts_staged(database_path: Path, snapshot: Mapping[str, list[list[Any]]]) -> None:
    """``facts.write_snapshot`` into a staged copy of the store, checked and
    swapped in; the caller holds the writer lock."""
    temp_path = _staged_store_path(database_path)
    try:
        source = facts.open_readonly(database_path)
        staged = sqlite3.connect(temp_path)
        try:
            source.backup(staged)
            facts.write_snapshot(staged, snapshot)
            staged.commit()
            if staged.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("facts: the staged store failed integrity_check")
        finally:
            staged.close()
            source.close()
        _replace_store(database_path, temp_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


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
    mp_lookup: dict[str, str],
    catalog: facts.SittingCatalog | None,
    facts_report: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None, set[str], str, bool]:
    base_url_raw, manifest_raw, license_text, issues_url = resolve_data_export_options(args)
    data_base_url = resolve_data_base_url(base_url_raw)
    bills = collect_bill_pages(entries, mp_lookup)
    bill_slugs = {bill["slug"] for bill in bills}
    readiness = derive_feature_readiness(entries, abg_mps, bill_count=len(bills))

    # Before the export, so the three facts tables are part of the store the
    # export copies and hashes. A rebuild in this build already computed them
    # for the same entries, catalog and date and hands over its report; only
    # ``None`` (no rebuild ran) computes them here.
    if not args.no_persist and database_path.exists():
        if facts_report is None:
            facts_report = run_facts_engine(
                database_path,
                entries,
                catalog,
                today=resolve_today(getattr(args, "today", None)),
            )
        for line in format_incomplete_report(
            facts_report,
            output_dir=output_dir,
            catalog_protocols=protocols,
            vote_scan_pages=30 if getattr(args, "vote_scan_pages", None) is None else int(args.vote_scan_pages),
        ):
            print(line, file=sys.stderr)

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

    if getattr(args, "fetch_xml", False):
        output_dir = args.output_dir
        try:
            entries = load_existing_detail_entries(output_dir, load_cached_protocols(output_dir))
        except CachedReportError as exc:
            print(f"ERROR [cached input]: {exc}. {CACHED_REPORT_FIX}", file=sys.stderr)
            return 1
        fetched, failed = fetch_missing_xml(output_dir, entries)
        print(f"fetch-xml: {fetched} fetched, {failed} failed, {len(entries) - fetched - failed} already cached", file=sys.stderr)
        if not failed:
            print("fetch-xml: next, run --offline --repersist to re-read Reden and Beiträge from it.", file=sys.stderr)
        return 1 if failed else 0

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
    # The Vorgang cache the Politikfelder are derived from, loaded once per
    # build; an online build fills it before it persists.
    try:
        vorgang_cache = politikfelder.load_cache(output_dir)
    except politikfelder.CacheLoadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # Explicit replay upgrades an old schema. Store consumers, including
    # no-persist rendering, require current persisted rules; an online rebuild
    # can repair the rules from accepted source inputs.
    if not getattr(args, "repersist", False) and database_path.exists():
        previous = None
        try:
            # Opening is inside: a directory or an unreadable file at the store
            # path fails here (or at the first query), not as a traceback.
            previous = facts.open_readonly(database_path)
            pulse_store.require_current_schema(previous)
            if args.offline or args.no_persist:
                pulse_store.require_current_speech_rules(previous)
                # The render applies the corrections file to the pages without a
                # reconcile, so an applied partition missing from it stops here.
                registry.require_applied_partitions(previous)
        except sqlite3.Error as exc:
            print(f"error: the store {database_path} cannot be read ({exc}); it is left as it is", file=sys.stderr)
            return 1
        except (RuntimeError, registry.RegistryError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        finally:
            if previous is not None:
                previous.close()

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

        # --repersist: apply what persist derives from the cached reports (the
        # render alone never does). All or nothing: any failure leaves the
        # previous store untouched and the run stops before anything is rendered.
        cached_entries: list[dict[str, Any]] | None = None
        rebuilt_facts: dict[str, Any] | None = None
        if getattr(args, "repersist", False):
            try:
                cached_entries, rebuilt = repersist_cached_reports(
                    output_dir, database_path, protocols, preserve_roster=True,
                    today=resolve_today(getattr(args, "today", None)),
                    vorgang_cache=vorgang_cache,
                )
            except derive.SprechrolleError as exc:
                print(exc, file=sys.stderr)
                return 1
            except CachedReportError as exc:
                print(
                    f"ERROR [repersist]: {exc}. The previous store is untouched. "
                    "Fix: repair that cached report, or move it out of data/ and re-fetch its sitting with an online update "
                    "and --document-number <its number>, then re-run. "
                    "Docs: README.md#re-persist-the-cached-reports",
                    file=sys.stderr,
                )
                return 1
            except DatabaseRebuildError as exc:
                print(
                    f"ERROR [repersist]: {exc}. The previous store is untouched. "
                    "Fix: resolve the cause named above (a missing cached report is restored, not deleted), then re-run. "
                    "Docs: docs/stable-ids.md",
                    file=sys.stderr,
                )
                return 1
            rebuilt_facts = rebuilt.facts_report
            print(
                f"repersist: {len(cached_entries)} cached reports persisted; "
                + ("store replaced" if rebuilt.replaced else "store content unchanged, file kept"),
                file=sys.stderr,
            )

        abg_mps: list[dict[str, Any]] = []
        mp_lookup: dict[str, str] = {}
        # The MP pages are read out of the existing store; the roster fetch is
        # skipped because it would need the network.
        if not args.no_persist and database_path.exists():
            # Read only: the published store is written by a staged rebuild alone.
            store = facts.open_readonly(database_path)
            try:
                pulse_store.require_current_schema(store)
                if "mp-pages" in features:
                    component_context = {
                        "selection": features,
                        "collect_abgeordnete": collect_abgeordnete,
                    }
                    components["mp-pages"].after_persist(store, component_context)
                    abg_mps = component_context["abg_mps"]
                    mp_lookup = component_context["mp_lookup"]
            finally:
                store.close()

        # --week must name a week with a cached dossier (the catalog lists every
        # protocol back to 1949; only dossiers can be rendered). Check it before
        # any dossier page is regenerated so a typo leaves the output untouched.
        if cached_entries is None:
            try:
                cached_entries = load_existing_detail_entries(output_dir, protocols)
            except CachedReportError as exc:
                print(f"ERROR [cached input]: {exc}. {CACHED_REPORT_FIX}", file=sys.stderr)
                return 1
            warn_unparsed_reports(cached_entries)
        if reject_unknown_week(pulse_week, [entry["report"].get("protocol") or {} for entry in cached_entries]):
            return 2

        try:
            validate_cached_kinds(cached_entries)
        except CachedReportError as exc:
            print(f"ERROR [cached input]: {exc}", file=sys.stderr)
            return 1
        if not getattr(args, "repersist", False):
            write_classification_diagnostics(output_dir, cached_entries)
        entries = rebuild_cached_detail_pages(
            output_dir,
            protocols,
            mp_lookup,
            features,
            cached_entries=cached_entries,
            include_dev_view=args.include_dev_view,
            database_page_href=dossier_database_page_href(args, database_path),
            vorgang_cache=vorgang_cache,
        )
        if not args.no_persist and database_path.exists():
            log_politikfelder_summary(database_path, vorgang_cache)
        try:
            manifest, data_export_error, bill_slugs, data_base_url, is_remote_manifest = run_data_pipeline(
                args=args,
                output_dir=output_dir,
                database_path=database_path,
                entries=entries,
                protocols=protocols,
                abg_mps=abg_mps,
                mp_lookup=mp_lookup,
                # The cached catalog on its own, never the protocols above: those
                # also hold dossier-derived entries, which prove nothing about
                # what DIP lists.
                catalog=facts.load_sitting_catalog(output_dir / "data" / facts.CATALOG_FILENAME),
                facts_report=rebuilt_facts,
            )
        except PIPELINE_ERRORS as exc:
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
            vorgang_cache=vorgang_cache,
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
    # One roll-call list page cache per build: every sitting reads the same
    # pages from the top, so only the first one pays for them.
    roll_call_page_cache: dict[str, str] = {}
    try:
        # Step 1: the catalog, then the subset of it that gets a dossier.
        # --dossier-document-number can add sittings to the dossier list without
        # changing the catalog; the second protocols_for_detail_pages() call
        # re-filters that combined list for a usable XML URL.
        protocol_wahlperiode = args.protocol_wahlperiode if args.protocol_wahlperiode > 0 else None
        # The whole catalog, whatever narrows the acquisition below.
        protocols = fetch_protocols(client, 0, [], None)
        if getattr(args, "backfill_incomplete", False):
            try:
                backfill_entries = load_existing_detail_entries(output_dir, protocols)
            except CachedReportError as exc:
                print(f"ERROR [cached input]: {exc}. {CACHED_REPORT_FIX}", file=sys.stderr)
                return 1
            acquisition_scope, waiting, vote_only, structural = incomplete_sitting_protocols(
                backfill_entries,
                protocols,
                votes=args.vote_scan_pages != 0,
                scan_pages=args.vote_scan_pages,
            )
            if structural:
                print(
                    f"[backfill] leaving {len(structural)} sitting(s) a rescan at these settings cannot fix: roll-call "
                    "votes no agenda item claims (they need a better match rule), or a scan that already used "
                    f"{args.vote_scan_pages} pages (raise --vote-scan-pages).",
                    file=sys.stderr,
                )
            if vote_only:
                print(
                    f"[backfill] skipping {len(vote_only)} sitting(s) held back only by votes: votes are off "
                    "(--no-votes, --vote-scan-pages 0 or a -votes entry). Fix: add --enrich votes.",
                    file=sys.stderr,
                )
            print(
                f"[backfill] {len(acquisition_scope)} incomplete or missing sitting(s) to acquire"
                + (
                    f"; {len(waiting)} not acquirable yet (DIP has no XML): "
                    + ", ".join(normalized_document_number(p.get("dokumentnummer")) for p in waiting)
                    if waiting
                    else ""
                ),
                file=sys.stderr,
            )
        else:
            acquisition_scope = select_acquisition_protocols(
                protocols, args.document_number, args.limit, protocol_wahlperiode
            )
        detail_limit = None if (args.document_number or getattr(args, "backfill_incomplete", False)) else args.detail_limit
        detail_protocols = protocols_for_detail_pages(acquisition_scope, detail_limit)
        protocols, detail_protocols = add_explicit_dossier_protocols(
            client,
            protocols,
            detail_protocols,
            args.dossier_document_number,
        )
        detail_protocols = protocols_for_detail_pages(detail_protocols, None)
        # What this run acquires is one scope; what the store keeps is another.
        # Every cached dossier of the catalog stays, whatever the acquisition
        # was narrowed to, and only the acquired sittings are refreshed.
        try:
            existing_entries = load_existing_detail_entries(output_dir, protocols)
        except CachedReportError as exc:
            print(f"ERROR [cached input]: {exc}. {CACHED_REPORT_FIX}", file=sys.stderr)
            return 1
        # --week must name a week this build will actually hold; check it against
        # the dossier catalog (plus the cached dossiers that stay in the
        # archive) now, before any dossier is written.
        if reject_unknown_week(
            pulse_week,
            [*detail_protocols, *(entry["report"].get("protocol") or {} for entry in existing_entries)],
        ):
            return 2
        abg_mps: list[dict[str, Any]] = []
        mp_lookup: dict[str, str] = {}
        # One catalog for the staged rebuild's facts and the data pipeline, so the
        # rebuild's facts report is handed over instead of computed twice.
        catalog = facts.sitting_catalog(protocols, authoritative=True, fetched_at=dip.utc_now())
        rebuilt_facts: dict[str, Any] | None = None
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
                    database_page_href=dossier_database_page_href(args, database_path),
                    roll_call_page_cache=roll_call_page_cache,
                    vorgang_cache=vorgang_cache,
                ),
            )
            # Step 3: persist everything into a freshly rebuilt SQLite store,
            # then read it back for the MP pages. The dossier pages are written
            # a second time afterwards because mp_lookup only exists now, and it
            # is what makes speaker names in them link to MP profiles.
            entries = merge_detail_entries(protocols, existing_entries, generated_entries)
            # A sitting whose refresh failed keeps its cached report: re-read a kept pre-A1
            # one from its cached XML, and persist none that is still pre-A1.
            try:
                reparse_cached_xml(output_dir, unparsed_reports(entries), profiles_from=entries)
                if args.no_persist:
                    warn_unparsed_reports(entries)
                else:
                    require_parsed_reports(entries)
            except CachedReportError as exc:
                print(
                    f"ERROR [persist]: {exc}. The previous store is untouched "
                    "(Dossiers wurden bereits geschrieben, puls.html nicht).",
                    file=sys.stderr,
                )
                return 1
            # A dossier of the requested week can still have failed to build;
            # say so instead of letting the renderer's ValueError escape.
            if reject_unknown_week(
                pulse_week,
                [entry["report"].get("protocol") or {} for entry in entries],
                note=" (Dossiers wurden bereits geschrieben, puls.html nicht)",
            ):
                return 2
            if not args.no_persist:
                refresh_vorgang_cache(client, entries, vorgang_cache, output_dir)

                def ingest_roster(staged: sqlite3.Connection) -> None:
                    stats = ingest_mdb_roster(client, staged, wahlperiode=args.roster_wahlperiode, profile_resolver=profile_resolver)
                    print(
                        f"roster: {stats['mdb']} MdBs of {stats['fetched']} persons "
                        f"(WP{args.roster_wahlperiode}), {stats['enriched']} enriched",
                        file=sys.stderr,
                    )

                try:
                    rebuilt_facts = rebuild_database_from_entries(
                        database_path,
                        entries,
                        preserve_roster="mp-roster" not in enrichments,
                        catalog=catalog,
                        roster_ingest=ingest_roster if "mp-roster" in enrichments else None,
                        today=resolve_today(getattr(args, "today", None)),
                        vorgang_cache=vorgang_cache,
                    ).facts_report
                except derive.SprechrolleError as exc:
                    print(exc, file=sys.stderr)
                    return 1
                except DatabaseRebuildError as exc:
                    print(
                        f"ERROR [rebuild]: {exc}. The previous store is untouched and nothing was persisted. "
                        "Fix: resolve the cause named above (after a roster outage, re-run once the API answers).",
                        file=sys.stderr,
                    )
                    return 1
                # Read only: the published store is written by a staged rebuild alone.
                store = facts.open_readonly(database_path)
                try:
                    pulse_store.require_current_schema(store)
                    if "mp-pages" in features:
                        abg_mps, mp_lookup = collect_abgeordnete(store)
                finally:
                    store.close()
                database_page_href = dossier_database_page_href(args, database_path)
                entries = [
                    write_report_files(
                        entry["report"],
                        output_dir,
                        mp_lookup,
                        features,
                        include_dev_view=args.include_dev_view,
                        database_page_href=database_page_href,
                        vorgang_cache=vorgang_cache,
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

    write_classification_diagnostics(output_dir, entries)
    # Step 4: export the Daten distribution files, then render the rest of the
    # site around the dossiers.
    if not args.no_persist and database_path.exists():
        log_politikfelder_summary(database_path, vorgang_cache)
    try:
        manifest, data_export_error, bill_slugs, data_base_url, is_remote_manifest = run_data_pipeline(
            args=args,
            output_dir=output_dir,
            database_path=database_path,
            entries=entries,
            protocols=protocols,
            abg_mps=abg_mps,
            mp_lookup=mp_lookup,
            catalog=catalog,
            facts_report=rebuilt_facts,
        )
    except PIPELINE_ERRORS as exc:
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
        authoritative_catalog=True,
        vorgang_cache=vorgang_cache,
    )
    print(index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
