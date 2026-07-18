#!/usr/bin/env python3
"""Build a static Bundestag Pulse overview site for multiple sittings."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

import render_dip_pulse_html as pulse_html
import persist_dip_pulse_store as pulse_store
import validate_dip_protocol as dip
import abgeordnetenwatch as aw


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
}


def slugify_document_number(document_number: str) -> str:
    value = document_number.strip().replace("/", "-")
    value = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value)
    return value.strip("-").lower()


def normalized_document_number(document_number: Any) -> str:
    return str(document_number or "").strip()


def protocol_sort_key(protocol: dict[str, Any]) -> tuple[str, str]:
    return (str(protocol.get("datum") or ""), str(protocol.get("id") or ""))


def protocol_xml_url(protocol: dict[str, Any]) -> str:
    fundstelle = protocol.get("fundstelle") or {}
    return str(fundstelle.get("xml_url") or "").strip()


def protocol_label(protocol: dict[str, Any]) -> str:
    document_number = normalized_document_number(protocol.get("dokumentnummer"))
    protocol_id = str(protocol.get("id") or "").strip()
    if document_number and protocol_id:
        return f"{document_number} (ID {protocol_id})"
    return document_number or protocol_id or "unbekanntes Protokoll"


def fetch_protocol_by_document_number(client: dip.ApiClient, document_number: str) -> dict[str, Any]:
    documents = client.list_all(
        "/plenarprotokoll",
        {"f.zuordnung": "BT", "f.dokumentnummer": document_number},
    )
    if not documents:
        raise dip.DipError(f"No BT Plenarprotokoll found for {document_number}")
    return documents[0]


def fetch_protocols(
    client: dip.ApiClient,
    limit: int,
    document_numbers: list[str],
    wahlperiode: int | None = None,
) -> list[dict[str, Any]]:
    if document_numbers:
        protocols: list[dict[str, Any]] = []
        for document_number in document_numbers:
            protocols.append(fetch_protocol_by_document_number(client, document_number))
        return sorted(protocols, key=protocol_sort_key, reverse=True)

    protocols: list[dict[str, Any]] = []
    params: dict[str, Any] = {"f.zuordnung": "BT"}
    if limit > 0 and wahlperiode:
        params["f.wahlperiode"] = wahlperiode
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

_VOTE_MEMBER_TITLES = {"dr", "prof", "professor"}


def _vote_member_name_parts(name: Any) -> tuple[str | None, str | None]:
    """Conservative first/last split for Bundestag roll-call member names."""
    text = " ".join(str(name or "").replace("\xa0", " ").split()).strip()
    text = re.sub(r",\s*MdB\b.*$", "", text, flags=re.I).strip()
    if not text:
        return None, None
    if "," in text:
        last, first = (part.strip() for part in text.split(",", 1))
        return first or None, last or None

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


def add_explicit_dossier_protocols(
    client: dip.ApiClient,
    protocols: list[dict[str, Any]],
    detail_protocols: list[dict[str, Any]],
    document_numbers: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not document_numbers:
        return protocols, detail_protocols

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


def report_paths(output_dir: Path, document_number: str) -> tuple[Path, Path, str]:
    slug = slugify_document_number(document_number)
    return (
        output_dir / "data" / f"plenarprotokoll-{slug}.json",
        output_dir / "protocols" / f"plenarprotokoll-{slug}.html",
        slug,
    )


def write_report_files(
    report: dict[str, Any],
    output_dir: Path,
    mp_lookup: dict[str, int] | None = None,
) -> dict[str, Any]:
    protocol = report.get("protocol") or {}
    document_number = normalized_document_number(protocol.get("dokumentnummer"))
    report_path, page_path, slug = report_paths(output_dir, document_number)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    page_path.write_text(
        pulse_html.render_html(
            report,
            home_href="../index.html",
            pulse_href="../puls.html",
            overview_href="../overview.html",
            catalog_href="../api-sitzungen.html",
            bills_href="../bills/index.html",
            sources_href="../sources.html",
            mp_lookup=mp_lookup,
        ),
        encoding="utf-8",
    )
    return {
        "report": report,
        "report_path": report_path,
        "page_path": page_path,
        "slug": slug,
    }


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
) -> list[dict[str, Any]]:
    """Regenerate dossier HTML from cached JSON reports without API calls."""
    entries = []
    for entry in load_existing_detail_entries(output_dir, protocols):
        entries.append(write_report_files(entry["report"], output_dir, mp_lookup))
    return entries


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


def rebuild_database_from_entries(database_path: Path, entries: list[dict[str, Any]]) -> None:
    temp_path = database_path.with_name(f".{database_path.name}.tmp")
    if temp_path.exists():
        temp_path.unlink()
    store = pulse_store.connect(temp_path)
    try:
        pulse_store.initialize(store)
        for entry in entries:
            pulse_store.persist_report(store, entry["report"])
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        store.close()
    temp_path.replace(database_path)


def usable_llm_summary(summary: Any) -> bool:
    return (
        isinstance(summary, dict)
        and bool(summary.get("text"))
        and bool(summary.get("source_chunks"))
    )


def agenda_item_reuse_keys(item: dict[str, Any]) -> list[str]:
    keys = []
    top_id = str(item.get("top_id") or "").strip()
    if top_id:
        keys.append(f"top:{top_id}")
    if item.get("index") is not None:
        keys.append(f"index:{item['index']}")
    return keys


def reuse_existing_llm_summaries(report: dict[str, Any], existing_report: dict[str, Any] | None) -> None:
    existing_by_key: dict[str, dict[str, Any]] = {}
    for item in (existing_report or {}).get("agenda_items") or []:
        summary = item.get("llm_summary")
        if not usable_llm_summary(summary):
            continue
        for key in agenda_item_reuse_keys(item):
            existing_by_key[key] = summary

    reused = 0
    for item in report.get("agenda_items") or []:
        if usable_llm_summary(item.get("llm_summary")):
            continue
        for key in agenda_item_reuse_keys(item):
            summary = existing_by_key.get(key)
            if summary:
                item["llm_summary"] = summary
                reused += 1
                break

    report["summary_generation"] = {
        "enabled": False,
        "mode": "reuse",
        "reason": "refresh not requested",
        "reused_top_count": reused,
        "generated_top_count": 0,
        "available_top_count": sum(
            1 for item in report.get("agenda_items") or [] if usable_llm_summary(item.get("llm_summary"))
        ),
    }


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
) -> dict[str, Any]:
    effective_summary_mode = "off" if summary_mode == "reuse" else summary_mode
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
        sleep=sleep,
    )
    report = dip.build_report(args)
    if summary_mode == "reuse":
        reuse_existing_llm_summaries(report, existing_report)
    enrich_report_with_profiles(report, profile_resolver)
    return write_report_files(report, output_dir, mp_lookup)


def sqlite_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def format_file_size(path: Path) -> str:
    size = path.stat().st_size if path.exists() else 0
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} {unit}"
        value /= 1024
    return f"{size} B"


def database_cell(value: Any, limit: int = 180) -> str:
    if value is None:
        return '<span class="null">NULL</span>'
    text = str(value)
    if len(text) > limit:
        text = text[:limit].rstrip() + "..."
    return pulse_html.esc(text)


def database_order_clause(columns: list[dict[str, Any]]) -> str:
    for column in columns:
        if column["pk"]:
            return f" ORDER BY {sqlite_identifier(column['name'])}"
    for name in ("updated_at", "created_at", "date", "id"):
        if any(column["name"] == name for column in columns):
            direction = "DESC" if name.endswith("_at") or name == "date" else "ASC"
            return f" ORDER BY {sqlite_identifier(name)} {direction}"
    return ""


def read_database_snapshot(database_path: Path, sample_limit: int = 12) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "path": database_path,
        "size": format_file_size(database_path),
        "tables": [],
        "relationships": [],
        "total_rows": 0,
    }
    if not database_path.exists():
        return snapshot

    uri = f"file:{database_path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
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
            for foreign_key in foreign_keys:
                snapshot["relationships"].append({"table": table, **foreign_key})

            row_count = int(conn.execute(f"SELECT COUNT(*) AS count FROM {sqlite_identifier(table)}").fetchone()["count"])
            snapshot["total_rows"] += row_count
            sample_sql = (
                f"SELECT * FROM {sqlite_identifier(table)}"
                f"{database_order_clause(columns)}"
                f" LIMIT {int(sample_limit)}"
            )
            sample_rows = [dict(row) for row in conn.execute(sample_sql).fetchall()]
            snapshot["tables"].append(
                {
                    "name": table,
                    "description": DATABASE_TABLE_DESCRIPTIONS.get(table, "Persistierte Tabelle aus dem Bundestag-Puls-Graph."),
                    "sql": table_row["sql"] or "",
                    "columns": columns,
                    "foreign_keys": foreign_keys,
                    "row_count": row_count,
                    "sample_rows": sample_rows,
                }
            )
    finally:
        conn.close()
    return snapshot


def render_database_columns(columns: list[dict[str, Any]]) -> str:
    rows = []
    for column in columns:
        flags = []
        if column["pk"]:
            flags.append("Primärschlüssel")
        if column["notnull"]:
            flags.append("Pflichtfeld")
        if column["default"] is not None:
            flags.append(f"Default {column['default']}")
        rows.append(
            f"""
            <tr>
              <td><code>{pulse_html.esc(column['name'])}</code></td>
              <td>{pulse_html.esc(column['type'] or 'untypisiert')}</td>
              <td>{pulse_html.esc(', '.join(flags) or 'optional')}</td>
            </tr>
            """
        )
    return "".join(rows)


def render_database_sample(table: dict[str, Any]) -> str:
    columns = [column["name"] for column in table["columns"]]
    if not columns:
        return '<p class="muted">Diese Tabelle hat keine Spalten.</p>'
    if not table["sample_rows"]:
        return '<p class="muted">Diese Tabelle enthält in diesem Build keine Zeilen.</p>'
    header = "".join(f"<th>{pulse_html.esc(column)}</th>" for column in columns)
    rows = []
    for row in table["sample_rows"]:
        cells = "".join(f"<td>{database_cell(row.get(column))}</td>" for column in columns)
        rows.append(f"<tr>{cells}</tr>")
    return f"""
      <div class="sample-table">
        <table>
          <thead><tr>{header}</tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    """


def render_database_page(database_path: Path, database_href: str | None) -> str:
    snapshot = read_database_snapshot(database_path)
    tables = snapshot["tables"]
    table_cards = []
    for table in tables:
        fk_rows = "".join(
            f"""
            <li><code>{pulse_html.esc(foreign_key['from'])}</code> &rarr; <code>{pulse_html.esc(foreign_key['to_table'])}.{pulse_html.esc(foreign_key['to_column'])}</code></li>
            """
            for foreign_key in table["foreign_keys"]
        )
        table_cards.append(
            f"""
            <article class="table-card" id="table-{pulse_html.esc(table['name'])}" data-table-card data-search="{pulse_html.esc(table['name'] + ' ' + table['description'])}">
              <div class="table-head">
                <div>
                  <span class="eyebrow">Tabelle</span>
                  <h2>{pulse_html.esc(table['name'])}</h2>
                  <p>{pulse_html.esc(table['description'])}</p>
                </div>
                <strong>{pulse_html.esc(table['row_count'])} Zeilen</strong>
              </div>
              <div class="table-body">
                <section>
                  <h3>Spalten</h3>
                  <table class="columns-table">
                    <thead><tr><th>Name</th><th>Typ</th><th>Eigenschaft</th></tr></thead>
                    <tbody>{render_database_columns(table['columns'])}</tbody>
                  </table>
                </section>
                <section>
                  <h3>Beispielzeilen</h3>
                  {render_database_sample(table)}
                </section>
                <details>
                  <summary>SQL-Schema und Beziehungen</summary>
                  {f'<ul class="fk-list">{fk_rows}</ul>' if fk_rows else '<p class="muted">Keine Fremdschlüssel aus dieser Tabelle.</p>'}
                  <pre>{pulse_html.esc(table['sql'])}</pre>
                </details>
              </div>
            </article>
            """
        )

    relationships = snapshot["relationships"]
    relationship_rows = "".join(
        f"""
        <tr>
          <td><a href="#table-{pulse_html.esc(item['table'])}">{pulse_html.esc(item['table'])}</a></td>
          <td><code>{pulse_html.esc(item['from'])}</code></td>
          <td><a href="#table-{pulse_html.esc(item['to_table'])}">{pulse_html.esc(item['to_table'])}</a>.<code>{pulse_html.esc(item['to_column'])}</code></td>
          <td>{pulse_html.esc(item['on_delete'])}</td>
        </tr>
        """
        for item in relationships
    )
    download_link = (
        f'<a class="button primary" href="{pulse_html.esc(database_href)}">SQLite herunterladen</a>'
        if database_href
        else ""
    )
    table_nav = "".join(
        f'<a href="#table-{pulse_html.esc(table["name"])}">{pulse_html.esc(table["name"])} <span>{pulse_html.esc(table["row_count"])}</span></a>'
        for table in tables
    )
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Datenbank</title>
  {pulse_html.theme_bootstrap_script()}
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
      letter-spacing:0;
      overflow-x:hidden;
    }}
    a {{ color:var(--blue); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size:.92em;
    }}
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
    .button {{
      display:inline-flex;
      align-items:center;
      min-height:32px;
      padding:5px 10px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      font-weight:700;
      color:var(--ink);
    }}
    .button.primary {{
      min-height:40px;
      padding:8px 14px;
      border-color:#bdd0ea;
      background:var(--blue);
      color:#fff;
    }}
    h1 {{ margin:0; font-size:36px; line-height:1.1; }}
    h2 {{ margin:5px 0 0; font-size:22px; line-height:1.2; }}
    h3 {{ margin:0 0 10px; font-size:15px; }}
    p {{ margin:7px 0 0; color:var(--muted); line-height:1.5; }}
    .subtitle {{ max-width:780px; }}
    .eyebrow {{
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.04em;
      font-weight:700;
    }}
    .download-panel {{
      display:grid;
      gap:8px;
      min-width:230px;
      padding:14px;
      border:1px solid var(--line);
      border-radius:8px;
      background:#fff;
    }}
    .summary-band {{
      display:grid;
      grid-template-columns:repeat(4, minmax(0,1fr));
      gap:12px;
      margin-top:18px;
    }}
    .summary-band div {{
      border:1px solid var(--line);
      border-radius:8px;
      background:#fff;
      padding:13px 14px;
    }}
    .summary-band span {{
      display:block;
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .summary-band strong {{ display:block; margin-top:4px; font-size:24px; }}
    .explainer {{
      display:grid;
      grid-template-columns:minmax(0,1fr) minmax(260px,.45fr);
      gap:16px;
      align-items:start;
      margin-top:18px;
    }}
    .panel, .table-card {{
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel);
      padding:18px;
    }}
    .table-nav {{
      display:flex;
      flex-wrap:wrap;
      gap:8px;
      margin-top:12px;
    }}
    .table-nav a {{
      display:inline-flex;
      gap:7px;
      align-items:center;
      min-height:28px;
      padding:4px 9px;
      border:1px solid var(--line);
      border-radius:999px;
      background:#fff;
      font-size:12px;
      font-weight:700;
    }}
    .table-nav span {{ color:var(--muted); font-weight:650; }}
    .filter {{
      display:grid;
      gap:5px;
      margin-top:18px;
      padding:14px;
      border:1px solid var(--line);
      border-radius:8px;
      background:#fff;
    }}
    .filter label {{
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.04em;
      font-weight:700;
    }}
    .filter input {{
      min-height:38px;
      padding:7px 10px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      font:inherit;
    }}
    .tables {{ display:grid; gap:16px; margin-top:18px; }}
    .table-card[hidden] {{ display:none; }}
    .table-head {{
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:16px;
      align-items:start;
      padding-bottom:14px;
      border-bottom:1px solid #edf1f5;
    }}
    .table-head strong {{
      display:inline-flex;
      align-items:center;
      min-height:30px;
      padding:4px 9px;
      border-radius:999px;
      background:var(--blue-soft);
      color:#103a7a;
      white-space:nowrap;
    }}
    .table-body {{ display:grid; gap:18px; margin-top:16px; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th, td {{
      padding:9px 8px;
      border-bottom:1px solid #edf1f5;
      text-align:left;
      vertical-align:top;
    }}
    th {{
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.04em;
      white-space:nowrap;
    }}
    .sample-table {{
      max-width:100%;
      overflow:auto;
      border:1px solid #edf1f5;
      border-radius:8px;
      background:#fff;
    }}
    .sample-table table {{ min-width:760px; }}
    .sample-table td {{
      max-width:300px;
      overflow-wrap:anywhere;
      line-height:1.4;
    }}
    details {{
      border:1px solid #edf1f5;
      border-radius:8px;
      background:#fbfcfd;
      overflow:hidden;
    }}
    summary {{
      padding:10px 12px;
      cursor:pointer;
      color:var(--blue);
      font-weight:750;
    }}
    details pre {{
      margin:0;
      padding:12px;
      border-top:1px solid #edf1f5;
      overflow:auto;
      white-space:pre-wrap;
      overflow-wrap:anywhere;
      font-size:12px;
      line-height:1.45;
    }}
    .fk-list {{
      display:grid;
      gap:6px;
      margin:0;
      padding:0 12px 12px 28px;
      color:var(--muted);
      font-size:13px;
    }}
    .null, .muted {{ color:var(--muted); }}
    .empty {{
      margin-top:18px;
      padding:20px;
      border:1px dashed var(--line);
      border-radius:8px;
      background:#fff;
      color:var(--muted);
      text-align:center;
    }}
    footer {{ padding-top:24px; color:var(--muted); font-size:12px; }}
    @media (max-width: 900px) {{
      .page-header, .explainer {{ grid-template-columns:1fr; }}
      .summary-band {{ grid-template-columns:1fr 1fr; }}
    }}
    @media (max-width: 640px) {{
      .shell {{ padding:18px 14px; }}
      h1 {{ font-size:29px; }}
      .summary-band, .table-head {{ grid-template-columns:1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(database_href="database.html", active="database")}
    <header class="page-header">
      <div>
        <span class="eyebrow">Transparenz</span>
        <h1>Datenbank erkunden</h1>
        <p class="subtitle">Diese statische Ansicht macht sichtbar, welche Tabellen Bundestag-Puls erzeugt, wie sie verknüpft sind und welche Beispielzeilen im aktuellen Build enthalten sind. Die Rohdaten bleiben zusätzlich als SQLite-Datei downloadbar.</p>
      </div>
      <div class="download-panel">
        <span class="eyebrow">Rohdaten</span>
        {download_link}
        <p>{pulse_html.esc(snapshot['size'])} · SQLite-Datei</p>
      </div>
    </header>
    <section class="summary-band">
      <div><span>Tabellen</span><strong>{pulse_html.esc(len(tables))}</strong></div>
      <div><span>Zeilen gesamt</span><strong>{pulse_html.esc(snapshot['total_rows'])}</strong></div>
      <div><span>Beziehungen</span><strong>{pulse_html.esc(len(relationships))}</strong></div>
      <div><span>Dateigröße</span><strong>{pulse_html.esc(snapshot['size'])}</strong></div>
    </section>
    <section class="explainer">
      <div class="panel">
        <span class="eyebrow">Was diese Ansicht leistet</span>
        <h2>Vom Protokoll zum Entitätengraph</h2>
        <p>Die Website nutzt dieselben verknüpften Datensätze, die hier sichtbar sind: Plenarprotokolle werden in Tagesordnungspunkte, Reden, Dokumente, Vorgänge, Parteien, Personen und Abstimmungen zerlegt. Dadurch lässt sich prüfen, welche Primärquellen hinter den sichtbaren Ansichten stehen.</p>
        <div class="table-nav">{table_nav}</div>
      </div>
      <div class="panel">
        <span class="eyebrow">Beziehungen</span>
        <h2>Fremdschlüssel</h2>
        {('<table><thead><tr><th>Tabelle</th><th>Spalte</th><th>Ziel</th><th>Löschen</th></tr></thead><tbody>' + relationship_rows + '</tbody></table>') if relationship_rows else '<p class="muted">Dieses Schema enthält noch keine Fremdschlüssel.</p>'}
      </div>
    </section>
    <section class="filter" aria-label="Tabellen filtern">
      <label for="database-search">Tabellen filtern</label>
      <input id="database-search" type="search" placeholder="z.B. speeches, votes, documents ..." autocomplete="off" data-table-search>
    </section>
    <section class="tables" data-table-list>
      {''.join(table_cards) if table_cards else '<div class="empty">In dieser SQLite-Datei wurden noch keine Tabellen angelegt.</div>'}
    </section>
    <footer>
      Diese Seite ist statisch aus der SQLite-Datei erzeugt. Sie führt keine SQL-Abfragen im Browser aus und verändert keine Daten. <a href="sources.html">Quellen und Methode</a> · <a href="index.html">Start</a>
    </footer>
  </div>
  <script>
    const search = document.querySelector('[data-table-search]');
    const cards = Array.from(document.querySelectorAll('[data-table-card]'));
    if (search) {{
      search.addEventListener('input', () => {{
        const query = search.value.trim().toLowerCase();
        for (const card of cards) {{
          const text = (card.getAttribute('data-search') || '').toLowerCase();
          card.hidden = query && !text.includes(query);
        }}
      }});
    }}
  </script>
  {pulse_html.theme_runtime_script()}
</body>
</html>
"""


def render_landing_page(
    entries: list[dict[str, Any]],
    *,
    database_href: str | None = None,
    database_page_href: str | None = None,
    protocol_count: int = 0,
    bill_count: int = 0,
) -> str:
    """Explanatory home page: what Bundestag-Puls is, its principles, and links to every subpart."""
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

    areas = [
        (
            "Lageblick",
            "Aktueller Puls",
            "puls.html",
            "Was gerade im Bundestag auffällt: Themenbewegung, Abstimmungsverschiebungen und darunter das belegbare Aufmerksamkeitsranking der neuesten Auswertung.",
        ),
        (
            "Archiv",
            "Plenarprotokoll-Katalog",
            "overview.html",
            "Der vollständige Katalog aller Plenarprotokolle aus der DIP-API mit erzeugten Dossiers je Sitzung: Tagesordnung, Rednerinnen und Redner, verknüpfte Drucksachen und Roh-API-Daten.",
        ),
        (
            "Gesetzgebung",
            "Gesetze verfolgen",
            "bills/index.html",
            "Verfolge einzelne Vorgänge von der Drucksache über die Plenardebatte bis zur namentlichen Abstimmung. Gefolgte Gesetze werden lokal im Browser gemerkt.",
        ),
        (
            "Transparenz",
            "Quellen und Methode",
            "sources.html",
            "Welche offiziellen Quellen genutzt werden, wie sie verarbeitet werden und was bewusst ausgeschlossen bleibt — die Grundlage für das Neutralitätsversprechen.",
        ),
    ]
    if database_href:
        areas.append(
            (
                "Daten",
                "SQLite herunterladen",
                database_href,
                "MPs, Parteien, Vorgänge, Reden und Abstimmungen als verknüpfte Datensätze zur eigenen Auswertung.",
            )
        )
    if database_page_href:
        areas.append(
            (
                "Transparenz",
                "Datenbank erkunden",
                database_page_href,
                "Tabellen, Spalten, Beziehungen und Beispielzeilen des SQLite-Graphen direkt im Browser prüfen.",
            )
        )
    area_cards = "".join(
        f"""
        <a class="area-card" href="{pulse_html.esc(href)}">
          <span class="eyebrow">{tag}</span>
          <h3>{title}</h3>
          <p>{pulse_html.esc(desc)}</p>
          <span class="area-go">&Ouml;ffnen &rarr;</span>
        </a>
        """
        for tag, title, href, desc in areas
    )

    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Primärquellen-Monitor des Bundestags</title>
  {pulse_html.theme_bootstrap_script()}
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
    {pulse_html.render_global_header(database_href=database_page_href)}

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
  {pulse_html.theme_runtime_script()}
</body>
</html>
"""


def render_front_page(
    entries: list[dict[str, Any]],
    database_href: str | None = "data/bundestag-pulse.sqlite",
    database_page_href: str | None = None,
) -> str:
    if not entries:
        return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls</title>
  {pulse_html.theme_bootstrap_script()}
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
    {pulse_html.render_global_header()}
    <header class="page-header">
      <h1>Bundestag-Puls</h1>
      <p>Es wurden noch keine Sitzungen erzeugt.</p>
    </header>
    <footer>
      Das XML-Protokoll ist maßgeblich; DIP-API-Daten ergänzen jede Sitzung.
    </footer>
  </div>
  {pulse_html.theme_runtime_script()}
</body>
</html>
"""

    entry = entries[0]
    report = entry["report"]
    protocol = report.get("protocol") or {}
    summary = report.get("validation_summary") or {}
    items = report.get("agenda_items") or []
    stats_by_index = {item["index"]: pulse_html.item_stats(item) for item in items}
    total_speeches = sum(stats["speech_count"] for stats in stats_by_index.values())
    total_chars = sum(stats["total_chars"] for stats in stats_by_index.values())
    ranked_items = sorted(items, key=lambda item: stats_by_index[item["index"]]["speech_count"], reverse=True)
    protocol_href = f"protocols/{pulse_html.esc(entry['page_path'].name)}"
    report_href = f"data/{pulse_html.esc(entry['report_path'].name)}"
    sqlite_link = f'<a href="{pulse_html.esc(database_href)}">SQLite-Graph</a>' if database_href else ""
    database_page_link = (
        f'<a href="{pulse_html.esc(database_page_href)}">Datenbank erkunden</a>' if database_page_href else ""
    )
    store_note = (
        " Die SQLite-Datei enthält MPs, Parteien, Vorgänge, Reden und Abstimmungen als verknüpfte Datensätze."
        if database_href
        else ""
    )
    total_votes = sum(
        len(item.get("votes") or ([item["vote"]] if item.get("vote") else []))
        for item in items
    )
    top_focus = ranked_items[0] if ranked_items else None
    if top_focus:
        top_stats = stats_by_index[top_focus["index"]]
        focus_text = (
            f"{top_focus.get('top_id')} bündelt aktuell {top_stats['speech_count']} Reden "
            f"und {pulse_html.format_int(top_stats['total_chars'])} Zeichen Redetext."
        )
        focus_href = f"{protocol_href}#top-{pulse_html.esc(top_focus.get('index'))}"
        focus_link = f'<a class="feature-link" href="{focus_href}">Belege zum Schwerpunkt</a>'
    else:
        focus_text = "Noch keine Tagesordnungspunkte in der neuesten Auswertung."
        focus_link = '<a class="feature-link" href="overview.html">Katalog prüfen</a>'

    vote_items = [
        item
        for item in items
        if item.get("votes") or item.get("vote")
    ]
    if vote_items:
        vote_focus = (
            f"{total_votes} namentliche Abstimmung"
            f"{'' if total_votes == 1 else 'en'} in {len(vote_items)} Tagesordnungspunkt"
            f"{'' if len(vote_items) == 1 else 'en'} zugeordnet."
        )
        vote_href = f"{protocol_href}#top-{pulse_html.esc(vote_items[0].get('index'))}"
        vote_link = f'<a class="feature-link" href="{vote_href}">Abstimmungen prüfen</a>'
    else:
        vote_focus = "Für die neueste Auswertung sind noch keine namentlichen Abstimmungen zugeordnet."
        vote_link = f'<a class="feature-link" href="{protocol_href}">Sitzungsbelege prüfen</a>'

    attention_rows = []
    for item in ranked_items[:6]:
        stats = stats_by_index[item["index"]]
        party_total = sum(stats["party_counts"].values())
        speech_share = pulse_html.percent(stats["speech_count"], total_speeches)
        text_share = pulse_html.percent(stats["total_chars"], total_chars)
        party_labels = [
            f"{party} {count}"
            for party, count in stats["party_counts"].most_common(5)
        ]
        if len(stats["party_counts"]) > 5:
            party_labels.append(f"+{len(stats['party_counts']) - 5} weitere")
        doc_count = len(item.get("xml_drucksachen") or [])
        attention_rows.append(
            f"""
            <article class="attention-card">
              <a class="top-link" href="{protocol_href}#top-{pulse_html.esc(item.get('index'))}">
                <span>{pulse_html.esc(item.get('top_id'))} · {pulse_html.esc(pulse_html.page_range_text(item))}</span>
                <strong>{pulse_html.esc(pulse_html.short(item.get('heading'), 132))}</strong>
              </a>
              <div class="bar-grid">
                <div>
                  <label>Reden <strong>{stats['speech_count']} · {speech_share:.1f}%</strong></label>
                  <div class="bar"><span style="width:{speech_share:.2f}%"></span></div>
                </div>
                <div>
                  <label>Redetext <strong>{pulse_html.format_int(stats['total_chars'])} Zeichen · {text_share:.1f}%</strong></label>
                  <div class="bar alt"><span style="width:{text_share:.2f}%"></span></div>
                </div>
              </div>
              <div class="party-block">
                {pulse_html.render_party_stack(stats['party_counts'], party_total)}
                <div class="party-labels">{pulse_html.render_badges(party_labels)}</div>
              </div>
              <div class="card-meta">
                <span>{doc_count} XML-Drucksachen</span>
                <span>{len(item.get('api', {}).get('positions') or [])} API-Positionen</span>
                <a href="{protocol_href}#top-{pulse_html.esc(item.get('index'))}">Prüfen</a>
              </div>
            </article>
            """
        )

    warnings = report.get("warnings") or []
    warning_html = ""
    if warnings:
        warning_html = (
            '<div class="notice">'
            f"{pulse_html.esc(str(len(warnings)))} Validierungswarnung"
            f"{'' if len(warnings) == 1 else 'en'} zu dieser erzeugten Sitzung."
            "</div>"
        )

    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Aktueller Lageblick</title>
  {pulse_html.theme_bootstrap_script()}
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
      grid-template-columns:1fr;
      gap:20px;
      align-items:start;
      padding-bottom:20px;
      border-bottom:1px solid var(--line);
    }}
    h1 {{ margin:0; font-size:37px; line-height:1.08; font-weight:780; }}
    h2 {{ margin:0; font-size:18px; line-height:1.25; }}
    p {{ margin:7px 0 0; color:var(--muted); }}
    .subtitle {{ max-width:760px; font-size:15px; }}
    .page-actions {{ display:flex; flex-wrap:wrap; gap:9px; justify-content:flex-start; }}
    .page-actions a, .session-links a {{
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-height:34px;
      padding:5px 11px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      font-weight:700;
      font-size:13px;
    }}
    .page-actions a {{ border-color:#bdd0ea; background:var(--blue-soft); color:var(--blue); }}
    .radar-hero {{
      display:grid;
      grid-template-columns:minmax(0,1.25fr) minmax(320px,.75fr);
      gap:18px;
      margin-top:18px;
      align-items:stretch;
    }}
    .latest-panel, .pulse-feature, .context-panel {{
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel);
      padding:18px;
    }}
    .eyebrow, .metric span, .top-link span, label, .card-meta {{
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .pulse-lede h2 {{ margin:6px 0 0; font-size:27px; line-height:1.16; }}
    .pulse-lede p {{ max-width:760px; font-size:15px; line-height:1.5; }}
    .pulse-actions {{
      display:flex;
      flex-wrap:wrap;
      gap:9px;
      margin-top:16px;
    }}
    .pulse-actions a {{
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-height:36px;
      padding:6px 12px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      font-size:13px;
      font-weight:750;
      color:var(--ink);
    }}
    .pulse-actions .primary-link {{ color:var(--blue); }}
    .context-title {{ margin:5px 0 0; font-size:19px; line-height:1.22; }}
    .metric-grid {{
      display:grid;
      grid-template-columns:repeat(4, minmax(92px,1fr));
      gap:10px;
      margin-top:18px;
    }}
    .context-panel .metric-grid {{ grid-template-columns:repeat(2, minmax(0,1fr)); }}
    .metric {{
      min-height:68px;
      border:1px solid #e2e7ef;
      border-radius:8px;
      background:#fbfcfd;
      padding:10px 11px;
    }}
    .metric span {{ overflow-wrap:anywhere; }}
    .metric strong {{ display:block; margin-top:5px; font-size:24px; }}
    .session-links {{
      display:flex;
      flex-wrap:wrap;
      gap:9px;
      margin-top:16px;
    }}
    .source-panel {{
      display:grid;
      gap:12px;
      border-left:4px solid var(--teal);
    }}
    .source-panel p {{ margin-top:4px; font-size:14px; line-height:1.45; }}
    .feature-grid {{
      display:grid;
      grid-template-columns:repeat(2, minmax(0,1fr));
      gap:18px;
      margin-top:18px;
    }}
    .pulse-feature {{
      display:grid;
      gap:14px;
      min-height:220px;
    }}
    .pulse-feature.movement {{ background:var(--green-soft); border-color:#cfe7df; }}
    .pulse-feature.votes {{ background:var(--amber-soft); border-color:#ead8ab; }}
    .feature-head {{
      display:flex;
      justify-content:space-between;
      gap:14px;
      align-items:start;
    }}
    .feature-head h2 {{
      margin:5px 0 0;
      font-size:25px;
      line-height:1.15;
    }}
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
    .feature-body {{
      display:grid;
      gap:12px;
      align-content:start;
    }}
    .feature-body p {{
      margin:0;
      color:#252b33;
      font-size:16px;
      line-height:1.45;
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
    .feature-microgrid {{
      display:grid;
      grid-template-columns:repeat(3, minmax(0,1fr));
      gap:8px;
    }}
    .feature-microgrid div {{
      border:1px solid rgba(23,26,31,.12);
      border-radius:8px;
      background:rgba(255,255,255,.65);
      padding:9px 10px;
    }}
    .feature-microgrid span {{
      display:block;
      color:var(--muted);
      font-size:11px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .feature-microgrid strong {{ display:block; margin-top:3px; font-size:19px; }}
    .layout {{
      display:grid;
      grid-template-columns:minmax(0,1fr);
      gap:18px;
      margin-top:28px;
      align-items:start;
    }}
    main {{ display:grid; gap:12px; }}
    .section-head {{
      display:flex;
      justify-content:space-between;
      gap:14px;
      align-items:end;
      margin-bottom:2px;
    }}
    .section-head p {{ font-size:13px; }}
    .attention-card {{
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel);
      padding:15px;
    }}
    .top-link {{
      display:grid;
      gap:5px;
      color:var(--ink);
    }}
    .top-link strong {{ font-size:17px; line-height:1.27; overflow-wrap:anywhere; }}
    .bar-grid {{
      display:grid;
      grid-template-columns:1fr 1fr;
      gap:14px;
      margin-top:13px;
    }}
    label {{
      display:flex;
      justify-content:space-between;
      gap:10px;
      margin-bottom:6px;
    }}
    label strong {{ color:var(--ink); font-size:12px; }}
    .bar {{ height:10px; overflow:hidden; border-radius:999px; background:#edf0f4; }}
    .bar span {{ display:block; height:100%; border-radius:999px; background:var(--teal); }}
    .bar.alt span {{ background:var(--amber); }}
    .party-block {{ margin-top:13px; }}
    .stack {{ display:flex; overflow:hidden; height:13px; background:#edf0f4; border-radius:999px; }}
    .stack span {{ min-width:3px; }}
    .party-labels {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }}
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
    .card-meta {{
      display:flex;
      flex-wrap:wrap;
      gap:10px;
      align-items:center;
      margin-top:12px;
    }}
    .card-meta a {{ margin-left:auto; font-weight:750; }}
    .ranking-intro {{
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:14px;
      align-items:end;
      padding-top:24px;
      border-top:1px solid var(--line);
    }}
    .notice {{
      padding:11px 13px;
      border:1px solid #e3c46a;
      border-radius:8px;
      background:#fff7d6;
      color:#614a00;
      font-size:13px;
    }}
    footer {{ padding:24px 0 4px; color:var(--muted); font-size:12px; }}
    @media (max-width: 980px) {{
      .page-header, .radar-hero, .layout, .feature-grid {{ grid-template-columns:1fr; }}
      .page-actions {{ justify-content:flex-start; }}
    }}
    @media (max-width: 700px) {{
      .shell {{ padding:16px 14px; }}
      h1 {{ font-size:29px; }}
      .context-title {{ font-size:18px; }}
      .metric-grid, .bar-grid {{ grid-template-columns:1fr 1fr; }}
      .section-head, .ranking-intro {{ display:grid; grid-template-columns:1fr; }}
      .feature-head {{ display:grid; }}
      .feature-state {{ justify-self:start; white-space:normal; }}
      .feature-microgrid {{ grid-template-columns:1fr; }}
    }}
    @media (max-width: 460px) {{
      .metric-grid, .bar-grid {{ grid-template-columns:1fr; }}
      .card-meta a {{ margin-left:0; width:100%; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(database_href=database_page_href, active="pulse")}
    <header class="page-header">
      <div>
        <span class="eyebrow">Aktueller Lageblick</span>
        <h1>Was gerade im Bundestag l&auml;uft</h1>
        <p class="subtitle">Diese Seite ist der aktuelle Bundestag-Puls: Sie hebt Themenbewegung und Abstimmungsverschiebungen hervor. Das Plenarprotokoll-Dossier bleibt als Quelle verlinkt, ist aber nicht der Zweck dieser Seite.</p>
      </div>
      <nav class="page-actions" aria-label="Seitenaktionen">
        <a href="#bewegung">Zum Lageblick</a>
        <a href="{protocol_href}">Protokolldossier</a>
        <a href="#aufmerksamkeit">Aufmerksamkeitsranking</a>
      </nav>
    </header>

    <section class="radar-hero">
      <div class="latest-panel pulse-lede">
        <span class="eyebrow">Momentaufnahme aus Primärquellen</span>
        <h2>Themen, Abstimmungen und Aufmerksamkeit statt Sitzungsreview</h2>
        <p>Bundestag-Puls liest die neueste erzeugte Auswertung als Lagebild: Welche Themen ziehen gerade Aufmerksamkeit, wo verändern Abstimmungen das Bild, und welche Tagesordnungspunkte liefern die Belege?</p>
        <div class="pulse-actions">
          <a class="primary-link" href="#bewegung">Themenbewegung ansehen</a>
          <a href="#abstimmungen">Abstimmungsverschiebungen ansehen</a>
          <a href="#aufmerksamkeit">Aufmerksamkeitsranking</a>
        </div>
      </div>
      <div class="context-panel source-panel">
        <span class="eyebrow">BT-PlPr {pulse_html.esc(protocol.get('dokumentnummer'))}</span>
        <h2 class="context-title">{pulse_html.esc(protocol.get('titel'))}</h2>
        <p>{pulse_html.esc(protocol.get('datum'))} · verteilt am {pulse_html.esc(protocol.get('verteildatum'))}</p>
        <div class="metric-grid">
          <div class="metric"><span>Tagesordnung</span><strong>{pulse_html.esc(summary.get('xml_top_count'))}</strong></div>
          <div class="metric"><span>Reden</span><strong>{pulse_html.esc(summary.get('xml_speech_count'))}</strong></div>
          <div class="metric"><span>Abstimmungen</span><strong>{pulse_html.esc(total_votes)}</strong></div>
          <div class="metric"><span>Personen</span><strong>{pulse_html.esc(summary.get('unique_person_ids'))}</strong></div>
        </div>
        <div class="session-links">
          <a href="{protocol_href}">Protokolldossier</a>
          <a href="{pulse_html.esc(protocol.get('xml_url'))}">XML-Protokoll</a>
          <a href="{pulse_html.esc(protocol.get('pdf_url'))}">PDF-Protokoll</a>
          <a href="{report_href}">Erzeugtes JSON</a>
          {database_page_link}
          {sqlite_link}
        </div>
      </div>
    </section>

    <section class="feature-grid" id="bewegung">
      <article class="pulse-feature movement">
        <div class="feature-head">
          <div>
            <span class="eyebrow">Themenbewegung</span>
            <h2>Was nach vorne rückt</h2>
          </div>
          <span class="feature-state">Aktueller Fokus</span>
        </div>
        <div class="feature-body">
          <p>{pulse_html.esc(focus_text)}</p>
          <div class="feature-microgrid">
            <div><span>TOPs</span><strong>{pulse_html.esc(summary.get('xml_top_count'))}</strong></div>
            <div><span>Reden</span><strong>{pulse_html.esc(summary.get('xml_speech_count'))}</strong></div>
            <div><span>Drucksachen</span><strong>{pulse_html.esc(summary.get('xml_drucksache_count'))}</strong></div>
          </div>
          <p>Der Wochenvergleich wird hier sichtbar, sobald mehrere Sitzungswochen im selben Modell normalisiert sind.</p>
          {focus_link}
        </div>
      </article>
      <article class="pulse-feature votes" id="abstimmungen">
        <div class="feature-head">
          <div>
            <span class="eyebrow">Abstimmungsverschiebung</span>
            <h2>Wo Stimmen das Bild verändern</h2>
          </div>
          <span class="feature-state">Namentliche Abstimmungen</span>
        </div>
        <div class="feature-body">
          <p>{pulse_html.esc(vote_focus)}</p>
          <div class="feature-microgrid">
            <div><span>Zugeordnet</span><strong>{pulse_html.esc(total_votes)}</strong></div>
            <div><span>TOPs mit Vote</span><strong>{pulse_html.esc(len(vote_items))}</strong></div>
            <div><span>Quelle</span><strong>BT</strong></div>
          </div>
          <p>Fraktionsabweichungen und Veränderungen gegenüber vorherigen Abstimmungen werden hier zur Hauptspur, sobald genügend Vergleichsdaten vorliegen.</p>
          {vote_link}
        </div>
      </article>
    </section>

    <div class="layout">
      <main>
        <div class="ranking-intro" id="aufmerksamkeit">
          <div>
            <span class="eyebrow">Belegbares Detailmaterial</span>
            <h2>Aufmerksamkeitsranking</h2>
            <p>Die Informationen zu einzelnen Tagesordnungspunkten bleiben erhalten, stehen aber unter dem aktuellen Lageblick.</p>
          </div>
          <p>Sortiert nach extrahierter Redezahl.</p>
        </div>
        {warning_html}
        {''.join(attention_rows)}
      </main>
    </div>

    <footer>
      Statischer Prototyp. Das XML-Protokoll ist maßgeblich; DIP-API-Daten ergänzen jede Sitzung.{store_note}
      <span class="session-links"><a href="overview.html">Plenarprotokoll-Katalog</a><a href="bills/index.html">Gesetze verfolgen</a><a href="sources.html">Quellen und Methode</a></span>
    </footer>
  </div>
  {pulse_html.theme_runtime_script()}
</body>
</html>
    """


def protocol_source_links(protocol: dict[str, Any]) -> str:
    fundstelle = protocol.get("fundstelle") or {}
    links = []
    for label, key in (("XML", "xml_url"), ("PDF", "pdf_url")):
        url = fundstelle.get(key)
        if url:
            links.append(f'<a href="{pulse_html.esc(url)}">{label}</a>')
    return "".join(links) or '<span class="muted">Keine Quelllinks</span>'


def render_catalog_json(protocol: dict[str, Any]) -> str:
    text = json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        '<details class="api-details">'
        '<summary>API-Felder</summary>'
        f"<pre>{pulse_html.esc(text)}</pre>"
        "</details>"
    )


def first_value(*values: Any) -> str:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def unique_values(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip() if value is not None else ""
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def unique_records(records: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    for record in records:
        key = tuple(record.get(k) for k in keys)
        if key not in seen:
            seen.add(key)
            result.append(record)
    return result


def bill_slug(bill: dict[str, Any]) -> str:
    identity = first_value(bill.get("vorgang_id"), bill.get("primary_document"), bill.get("title"), "bill")
    return "bill-" + slugify_document_number(identity)


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


def doc_numbers(docs: list[dict[str, Any]]) -> set[str]:
    return {str(doc.get("dokumentnummer")) for doc in docs if doc.get("dokumentnummer")}


def collect_bill_pages(detail_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bills: dict[str, dict[str, Any]] = {}
    speaker_counts: dict[str, dict[str, dict[str, Any]]] = {}

    for entry in detail_entries:
        report = entry["report"]
        protocol = report.get("protocol") or {}
        protocol_href = f"../protocols/{entry['page_path'].name}"
        for item in report.get("agenda_items") or []:
            api = item.get("api") or {}
            linked_docs = api.get("linked_drucksachen") or []
            positions = api.get("positions") or []
            item_votes = item.get("votes") or []
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
                if not bill_like(position, position_docs):
                    continue

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


def render_bill_json_details(title: str, payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        '<details class="raw-block">'
        f"<summary>{pulse_html.esc(title)}</summary>"
        f"<pre>{pulse_html.esc(text)}</pre>"
        "</details>"
    )


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


def render_bills_index(bills: list[dict[str, Any]]) -> str:
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
                <button class="follow-button" type="button" data-follow-id="{pulse_html.esc(bill['id'])}" aria-pressed="false">Folgen</button>
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
  {pulse_html.theme_bootstrap_script()}
  <style>{bill_styles()}</style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(home_href="../index.html", pulse_href="../puls.html", overview_href="../overview.html", catalog_href="../api-sitzungen.html", bills_href="index.html", sources_href="../sources.html", active="bills")}
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
  {pulse_html.theme_runtime_script()}
</body>
</html>
"""


def render_bill_detail(bill: dict[str, Any], mp_lookup: dict[str, int] | None = None) -> str:
    introduced = ", ".join(bill.get("introduced_by") or []) or "Urheber nicht im Rohdatensatz"
    events = []
    for event in bill.get("events") or []:
        title = pulse_html.esc(event.get("title") or "")
        if event.get("url"):
            title = f'<a href="{pulse_html.esc(event.get("url"))}">{title}</a>'
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
        label = f'<a href="{pulse_html.esc(doc.get("url"))}">{number}</a>' if doc.get("url") else number
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
  {pulse_html.theme_bootstrap_script()}
  <style>{bill_styles()}</style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(home_href="../index.html", pulse_href="../puls.html", overview_href="../overview.html", catalog_href="../api-sitzungen.html", bills_href="index.html", sources_href="../sources.html", active="bills")}
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
        <button class="follow-button" type="button" data-follow-id="{pulse_html.esc(bill['id'])}" aria-pressed="false">Folgen</button>
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
  {pulse_html.theme_runtime_script()}
</body>
</html>
"""


def write_bill_pages(
    output_dir: Path,
    bills: list[dict[str, Any]],
    mp_lookup: dict[str, int] | None = None,
) -> dict[str, Any]:
    bills_dir = output_dir / "bills"
    bills_dir.mkdir(parents=True, exist_ok=True)
    for bill in bills:
        (bills_dir / f"{bill['slug']}.html").write_text(render_bill_detail(bill, mp_lookup), encoding="utf-8")
    (bills_dir / "index.html").write_text(render_bills_index(bills), encoding="utf-8")
    data_path = output_dir / "data" / "bills.json"
    data_path.write_text(json.dumps(bills, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"count": len(bills), "index_path": bills_dir / "index.html", "data_path": data_path}


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


def _merge_external_ids(rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    merged: dict[str, set[str]] = {"aw": set(), "dip": set(), "xml": set(), "profile": set()}
    for row in rows:
        for kind, values in _mp_external_ids(row).items():
            merged[kind].update(values)
    return merged


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


def _normalized_mp_name(name: Any) -> str:
    return re.sub(r"\s+", " ", _clean_mp_name(name).casefold()).strip()


def _normalized_mp_party(party: Any) -> str:
    text = str(party or "").strip()
    if not text:
        return ""
    normalized = dip.normalize_faction(text)
    tokens = sorted(aw._party_tokens(normalized))
    return "|".join(tokens) if tokens else normalized.casefold()


def collect_abgeordnete(conn: sqlite3.Connection) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Read MPs with party, speeches, and roll-call votes for the Abgeordnete
    pages, consolidating rows that describe the same person (the DIP roster row
    carries the bio; the protocol-speaker row carries the speeches). Returns the
    consolidated MPs plus a lookup from every external id to the page id, so
    speaker lists can link without dangling. One grouped query each avoids N+1."""
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

    components: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        components.setdefault(find(row["id"]), []).append(row)

    mps: list[dict[str, Any]] = []
    lookup: dict[str, int] = {}
    for members in components.values():
        # Canonical row: prefer an MdB (roster) row, then lowest id, for a stable
        # page id shared by the list and the profile.
        members.sort(key=lambda r: (0 if r["is_mdb"] else 1, r["id"]))
        cid = members[0]["id"]

        def first(field: str) -> Any:
            for r in members:
                if r.get(field) not in (None, ""):
                    return r[field]
            return None

        merged_speeches: list[dict[str, Any]] = []
        for r in members:
            merged_speeches.extend(speeches_by_mp.get(r["id"], []))
        merged_speeches.sort(key=lambda s: (s.get("date") or ""), reverse=True)

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
    return mps, lookup


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


def _location_label(mp: dict[str, Any]) -> str:
    parts = [mp.get("wahlkreis"), mp.get("bundesland")]
    return " · ".join(p for p in parts if p) or "—"


def render_abgeordnete_index(mps: list[dict[str, Any]]) -> str:
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
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Abgeordnete</title>
  {pulse_html.theme_bootstrap_script()}
  <style>{abgeordnete_styles()}</style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(home_href="../index.html", pulse_href="../puls.html", overview_href="../overview.html", catalog_href="../api-sitzungen.html", bills_href="../bills/index.html", abgeordnete_href="index.html", sources_href="../sources.html", active="abgeordnete")}
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
    <div class="filter-bar">
      <input type="search" data-mp-search placeholder="Nach Name, Wahlkreis oder Bundesland suchen…" aria-label="Abgeordnete suchen">
      <div class="party-filters" role="group" aria-label="Nach Fraktion filtern">{party_chips}</div>
    </div>
    {'<table class="mp-table"><thead><tr><th>Name</th><th>Fraktion</th><th>Wahlkreis / Bundesland</th><th class="num">Reden</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>' if rows else '<p class="mp-empty">Noch keine Abgeordneten geladen. Den Build mit aktivem DIP-Personen-Roster ausführen (ohne --no-roster).</p>'}
    <footer>Personenstammdaten aus der DIP-API; Wahlkreis, Bundesland, Geburtsjahr und Beruf von abgeordnetenwatch.de (CC0). <a href="../sources.html">Quellen und Methode</a></footer>
  </div>
  {render_abgeordnete_script()}
  {pulse_html.theme_runtime_script()}
</body>
</html>
"""


def render_abgeordnete_detail(mp: dict[str, Any]) -> str:
    profile_link = ""
    if mp.get("profile_url"):
        profile_link = (
            f'<a class="source-link" href="{pulse_html.esc(mp["profile_url"])}" target="_blank" rel="noopener">'
            "abgeordnetenwatch.de-Profil ↗</a>"
        )

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
            title = f'<a href="{pulse_html.esc(vote.get("detail_url"))}">{title}</a>'
        votes.append(
            '<li class="vote-row">'
            f'<time>{pulse_html.esc(vote.get("date") or "")}</time>'
            f'<span>{title}</span>'
            f'<span class="badge vote-badge {pulse_html.esc(direction)}">{pulse_html.esc(label)}</span>'
            "</li>"
        )

    tally = mp.get("vote_tally") or {}
    participation = tally.get("yes", 0) + tally.get("no", 0) + tally.get("abstain", 0)
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{pulse_html.esc(mp.get('name'))} · Bundestag-Puls</title>
  {pulse_html.theme_bootstrap_script()}
  <style>{abgeordnete_styles()}</style>
</head>
<body>
  <div class="shell">
    {pulse_html.render_global_header(home_href="../index.html", pulse_href="../puls.html", overview_href="../overview.html", catalog_href="../api-sitzungen.html", bills_href="../bills/index.html", abgeordnete_href="index.html", sources_href="../sources.html", active="abgeordnete")}
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
  {pulse_html.theme_runtime_script()}
</body>
</html>
"""


def write_abgeordnete_pages(output_dir: Path, mps: list[dict[str, Any]]) -> dict[str, Any]:
    abg_dir = output_dir / "abgeordnete"
    abg_dir.mkdir(parents=True, exist_ok=True)
    # Detail pages for MdBs and for anyone who actually spoke (so cross-links from
    # protocol/bill speaker lists never dangle, even for ministers/guests).
    detail_mps = [mp for mp in mps if mp.get("is_mdb") or (mp.get("speech_count") or 0) > 0]
    for mp in detail_mps:
        (abg_dir / f"{mp['id']}.html").write_text(render_abgeordnete_detail(mp), encoding="utf-8")
    (abg_dir / "index.html").write_text(render_abgeordnete_index(mps), encoding="utf-8")
    data_path = output_dir / "data" / "abgeordnete.json"
    data_path.write_text(json.dumps(mps, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    listed = sum(1 for mp in mps if mp.get("is_mdb"))
    return {"count": listed, "detail_count": len(detail_mps), "index_path": abg_dir / "index.html"}


def render_overview(
    protocols: list[dict[str, Any]],
    detail_entries: list[dict[str, Any]],
    bill_count: int = 0,
    database_href: str | None = "data/bundestag-pulse.sqlite",
    database_page_href: str | None = None,
    catalog_href: str = "api-sitzungen.html",
) -> str:
    generated_cards = []
    sqlite_link = f'<a href="{pulse_html.esc(database_href)}">SQLite</a>' if database_href else ""
    database_page_link = (
        f'<a href="{pulse_html.esc(database_page_href)}">Datenbank</a>' if database_page_href else ""
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
                <a href="{pulse_html.esc(protocol.get('xml_url'))}">XML</a>
                <a href="{pulse_html.esc(protocol.get('pdf_url'))}">PDF</a>
                <a href="data/{pulse_html.esc(entry['report_path'].name)}">JSON</a>
                {sqlite_link}
                {warning_html}
              </div>
            </article>
            """
        )

    by_period: dict[str, int] = {}
    for protocol in protocols:
        period = str(protocol.get("wahlperiode") or "unknown")
        by_period[period] = by_period.get(period, 0) + 1

    period_badges = "".join(
        f'<span class="badge">WP {pulse_html.esc(period)} <strong>{pulse_html.esc(count)}</strong></span>'
        for period, count in sorted(by_period.items(), key=lambda item: item[0], reverse=True)
    )
    latest = protocols[0] if protocols else {}
    generated_latest = detail_entries[0]["report"].get("protocol", {}) if detail_entries else {}
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Sitzungen</title>
  {pulse_html.theme_bootstrap_script()}
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
    {pulse_html.render_global_header(database_href=database_page_href, active="overview")}
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
      Das XML-Protokoll ist maßgeblich; DIP-API-Daten ergänzen jede Sitzung. Mit --detail-limit 0 werden Dossiers für alle geholten Protokolle erzeugt, mit --detail-limit -1 nur der Katalog. <a href="puls.html">Aktueller Puls</a> · <a href="bills/index.html">Gesetze verfolgen</a>{database_footer_link} · <a href="sources.html">Quellen und Methode</a>.
    </footer>
  </div>
  {pulse_html.theme_runtime_script()}
</body>
</html>
    """


def catalog_sortnum(protocol: dict[str, Any]) -> str:
    """Zero-padded numeric sort key derived from the document number (WP/Nr)."""
    match = re.match(r"\s*(\d+)\s*/\s*(\d+)", str(protocol.get("dokumentnummer") or ""))
    if match:
        return f"{int(match.group(1)):04d}{int(match.group(2)):07d}"
    return "00000000000"


def build_catalog_rows(
    protocols: list[dict[str, Any]],
    detail_entries: list[dict[str, Any]],
) -> tuple[list[str], dict[str, int]]:
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
              <label class="catalog-select" title="Für Dossier-Erzeugung auswählen">
                <input type="checkbox" data-dossier-select value="{pulse_html.esc(document_number)}">
                <span>Auswählen</span>
              </label>
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


def render_catalog_script() -> str:
    return """
  <script>
    (() => {
      const container = document.querySelector('[data-catalog]');
      if (!container) return;
      const rows = Array.from(container.querySelectorAll('[data-row]'));
      const checkboxes = Array.from(container.querySelectorAll('[data-dossier-select]'));
      const search = document.querySelector('[data-filter-search]');
      const wpSelect = document.querySelector('[data-filter-wp]');
      const dossierSelect = document.querySelector('[data-filter-dossier]');
      const sortSelect = document.querySelector('[data-filter-sort]');
      const countEl = document.querySelector('[data-result-count]');
      const noResults = document.querySelector('[data-no-results]');
      const resetBtn = document.querySelector('[data-filter-reset]');
      const badges = Array.from(document.querySelectorAll('[data-wp-filter]'));
      const developerPanel = document.querySelector('[data-dossier-command]');
      const selectedCountEl = document.querySelector('[data-selected-count]');
      const commandEl = document.querySelector('[data-command-output]');
      const refreshSummariesInput = document.querySelector('[data-refresh-summaries]');
      const selectVisibleBtn = document.querySelector('[data-select-visible]');
      const selectMissingBtn = document.querySelector('[data-select-missing]');
      const clearSelectionBtn = document.querySelector('[data-clear-selection]');
      const copyCommandBtn = document.querySelector('[data-copy-command]');

      const shellQuote = (value) => {
        const text = String(value);
        return /^[A-Za-z0-9_./:=+-]+$/.test(text) ? text : "'" + text.replace(/'/g, "'\\\\''") + "'";
      };

      const selectedDocumentNumbers = () => checkboxes
        .filter((checkbox) => checkbox.checked)
        .map((checkbox) => checkbox.value)
        .filter(Boolean);

      const updateCommand = () => {
        if (!developerPanel || !commandEl) return;
        const docs = selectedDocumentNumbers();
        if (selectedCountEl) selectedCountEl.textContent = String(docs.length);
        if (copyCommandBtn) copyCommandBtn.disabled = docs.length === 0;
        const outputDir = developerPanel.dataset.outputDir || '.context/dip-pulse-site';
        const args = [
          'python3',
          'scripts/build_dip_pulse_site.py',
          '--limit',
          '0',
          '--detail-limit',
          '-1',
          '--preserve-existing-dossiers',
          '--output-dir',
          outputDir,
        ];
        if (refreshSummariesInput && refreshSummariesInput.checked) {
          args.push('--refresh-summaries');
        }
        docs.forEach((doc) => {
          args.push('--dossier-document-number', doc);
        });
        commandEl.value = docs.length ? args.map(shellQuote).join(' ') : '';
      };

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
      checkboxes.forEach((checkbox) => checkbox.addEventListener('change', updateCommand));
      if (refreshSummariesInput) {
        refreshSummariesInput.addEventListener('change', updateCommand);
      }
      if (selectVisibleBtn) {
        selectVisibleBtn.addEventListener('click', () => {
          rows.forEach((row) => {
            const checkbox = row.querySelector('[data-dossier-select]');
            if (checkbox && !row.hidden) checkbox.checked = true;
          });
          updateCommand();
        });
      }
      if (selectMissingBtn) {
        selectMissingBtn.addEventListener('click', () => {
          rows.forEach((row) => {
            const checkbox = row.querySelector('[data-dossier-select]');
            if (checkbox && !row.hidden && row.dataset.dossier === '0') checkbox.checked = true;
          });
          updateCommand();
        });
      }
      if (clearSelectionBtn) {
        clearSelectionBtn.addEventListener('click', () => {
          checkboxes.forEach((checkbox) => {
            checkbox.checked = false;
          });
          updateCommand();
        });
      }
      if (copyCommandBtn && commandEl) {
        copyCommandBtn.addEventListener('click', async () => {
          if (!commandEl.value) return;
          commandEl.select();
          try {
            await navigator.clipboard.writeText(commandEl.value);
            copyCommandBtn.textContent = 'Kopiert';
            window.setTimeout(() => {
              copyCommandBtn.textContent = 'Befehl kopieren';
            }, 1400);
          } catch {
            document.execCommand('copy');
          }
        });
      }
      apply();
      updateCommand();
    })();
  </script>
"""


def render_catalog_page(
    protocols: list[dict[str, Any]],
    detail_entries: list[dict[str, Any]],
    catalog_path: Path,
    output_dir: Path,
    overview_href: str = "overview.html",
    database_page_href: str | None = None,
) -> str:
    rows, by_period = build_catalog_rows(protocols, detail_entries)
    rows_html = "".join(rows)
    periods_sorted = sorted(by_period.items(), key=lambda item: item[0], reverse=True)
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
        f'<a href="{pulse_html.esc(database_page_href)}">Datenbank</a>' if database_page_href else ""
    )
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Alle API-Sitzungen</title>
  {pulse_html.theme_bootstrap_script()}
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
    .developer-panel {{
      display:grid;
      gap:12px;
      margin-top:16px;
      padding:16px;
      border:1px solid #bdd0ea;
      border-radius:8px;
      background:#f6f9ff;
    }}
    .developer-panel h2 {{
      margin:0;
      font-size:18px;
      line-height:1.25;
    }}
    .developer-panel p {{
      margin:0;
      color:var(--muted);
      line-height:1.45;
    }}
    .developer-actions {{
      display:flex;
      flex-wrap:wrap;
      gap:8px;
      align-items:center;
    }}
    .developer-option {{
      display:flex;
      gap:8px;
      align-items:flex-start;
      color:var(--muted);
      font-size:13px;
      line-height:1.4;
    }}
    .developer-option input {{
      width:17px;
      height:17px;
      margin:1px 0 0;
      accent-color:#174ea6;
    }}
    .dev-button {{
      min-height:34px;
      padding:5px 11px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      color:var(--ink);
      font:inherit;
      font-size:13px;
      font-weight:700;
      cursor:pointer;
    }}
    .dev-button.primary {{
      border-color:#bdd0ea;
      background:#eef5ff;
      color:#103a7a;
    }}
    .dev-button:disabled {{
      cursor:not-allowed;
      opacity:.55;
    }}
    .command-output {{
      width:100%;
      min-height:78px;
      padding:10px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      color:#182230;
      font:13px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      resize:vertical;
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
      grid-template-columns:minmax(96px,.3fr) minmax(260px,1.4fr) minmax(130px,.45fr) minmax(150px,.5fr) minmax(190px,.7fr);
      gap:14px;
      align-items:start;
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:8px;
      padding:14px;
    }}
    .catalog-select {{
      display:inline-flex;
      gap:7px;
      align-items:center;
      min-height:32px;
      color:var(--muted);
      font-size:13px;
      font-weight:650;
      cursor:pointer;
    }}
    .catalog-select input {{
      width:17px;
      height:17px;
      margin:0;
      accent-color:#174ea6;
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
    {pulse_html.render_global_header(database_href=database_page_href, active="catalog")}
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
    <section class="developer-panel" data-dossier-command data-output-dir="{pulse_html.esc(str(output_dir))}">
      <h2>Dossiers erzeugen</h2>
      <p><strong data-selected-count>0</strong> Sitzungen ausgewählt. Der Befehl erzeugt oder regeneriert die ausgewählten Dossiers, erhält bestehende Dossiers und rendert diesen Katalog neu. Vorhandene KI-Zusammenfassungen werden wiederverwendet, bis sie aktiv neu erzeugt werden.</p>
      <label class="developer-option">
        <input type="checkbox" data-refresh-summaries>
        <span>KI-Zusammenfassungen neu erzeugen und dafür den konfigurierten LLM-Anbieter aufrufen.</span>
      </label>
      <div class="developer-actions">
        <button type="button" class="dev-button" data-select-visible>Sichtbare auswählen</button>
        <button type="button" class="dev-button" data-select-missing>Sichtbare ohne Dossier</button>
        <button type="button" class="dev-button" data-clear-selection>Auswahl leeren</button>
        <button type="button" class="dev-button primary" data-copy-command disabled>Befehl kopieren</button>
      </div>
      <textarea class="command-output" data-command-output readonly placeholder="Sitzungen auswählen, um den Regenerationsbefehl zu erzeugen."></textarea>
    </section>
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
  {pulse_html.theme_runtime_script()}
</body>
</html>
"""


def render_sources_page(
    entries: list[dict[str, Any]],
    database_href: str | None = None,
    database_page_href: str | None = None,
) -> str:
    generated_rows = []
    for entry in entries:
        report = entry["report"]
        protocol = report.get("protocol") or {}
        summary = report.get("validation_summary") or {}
        generated_rows.append(
            """
            <tr>
              <td><a href="protocols/{page}">{document}</a></td>
              <td>{date}</td>
              <td>{tops}</td>
              <td>{speeches}</td>
              <td class="source-actions">
                <a href="{xml_url}">XML</a>
                <a href="{pdf_url}">PDF</a>
                <a href="data/{json_file}">JSON</a>
              </td>
            </tr>
            """.format(
                page=pulse_html.esc(entry["page_path"].name),
                document=pulse_html.esc(protocol.get("dokumentnummer")),
                date=pulse_html.esc(protocol.get("datum")),
                tops=pulse_html.esc(summary.get("xml_top_count")),
                speeches=pulse_html.esc(summary.get("xml_speech_count")),
                xml_url=pulse_html.esc(protocol.get("xml_url")),
                pdf_url=pulse_html.esc(protocol.get("pdf_url")),
                json_file=pulse_html.esc(entry["report_path"].name),
            )
        )

    if not generated_rows:
        generated_rows.append('<tr><td colspan="5" class="muted">In diesem Build wurden keine Sitzungen erzeugt.</td></tr>')

    latest = entries[0]["report"].get("protocol", {}) if entries else {}
    database_page_link = (
        f'<a href="{pulse_html.esc(database_page_href)}">Datenbank</a>' if database_page_href else ""
    )
    database_method_item = ""
    if database_page_href or database_href:
        database_links = []
        if database_page_href:
            database_links.append(f'<a href="{pulse_html.esc(database_page_href)}">Datenbank erkunden</a>')
        if database_href:
            database_links.append(f'<a href="{pulse_html.esc(database_href)}">SQLite herunterladen</a>')
        database_method_item = (
            "<li><strong>SQLite-Graph</strong><span>"
            "Die normalisierten Entitäten werden als SQLite-Datei veröffentlicht; "
            f"{' · '.join(database_links)}."
            "</span></li>"
        )
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Quellen</title>
  {pulse_html.theme_bootstrap_script()}
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
    footer {{ padding-top:8px; color:var(--muted); font-size:12px; }}
    @media (max-width: 760px) {{
      .shell {{ padding:18px 14px; }}
      .page-header, .source-grid {{ grid-template-columns:1fr; }}
      h1 {{ font-size:29px; }}
      .method-list li {{ grid-template-columns:1fr; gap:3px; }}
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
    {pulse_html.render_global_header(database_href=database_page_href, active="sources")}
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
          {database_method_item}
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
      Quellenlinks verweisen auf öffentliche Bundestags- und DIP-Datensätze. Verfügbarkeit und genaue Inhalte werden von diesen offiziellen Diensten bestimmt. <a href="overview.html">Plenarprotokoll-Katalog</a> · <a href="bills/index.html">Gesetze verfolgen</a>
    </footer>
  </div>
  {pulse_html.theme_runtime_script()}
</body>
</html>
    """


def render_site(
    *,
    output_dir: Path,
    database_path: Path,
    no_persist: bool,
    protocols: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    abg_mps: list[dict[str, Any]],
    mp_lookup: dict[str, int],
) -> Path:
    database_href = None
    if not no_persist:
        try:
            database_href = database_path.resolve().relative_to(output_dir.resolve()).as_posix()
        except ValueError:
            database_href = None
    database_page_href = "database.html" if not no_persist and database_path.exists() else None

    catalog_path = output_dir / "data" / "plenarprotokoll-catalog.json"
    catalog_path.write_text(json.dumps(protocols, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bills = collect_bill_pages(entries)
    bill_output = write_bill_pages(output_dir, bills, mp_lookup)
    abg_output = write_abgeordnete_pages(output_dir, abg_mps)
    print(
        f"abgeordnete: {abg_output['count']} gelistet, "
        f"{abg_output['detail_count']} Profilseiten",
        file=sys.stderr,
    )
    index_path = output_dir / "index.html"
    pulse_path = output_dir / "puls.html"
    overview_path = output_dir / "overview.html"
    catalog_page_path = output_dir / "api-sitzungen.html"
    sources_path = output_dir / "sources.html"
    database_page_path = output_dir / "database.html"
    index_path.write_text(
        render_landing_page(
            entries,
            database_href=database_href,
            database_page_href=database_page_href,
            protocol_count=len(protocols),
            bill_count=int(bill_output["count"]),
        ),
        encoding="utf-8",
    )
    pulse_path.write_text(
        render_front_page(entries, database_href=database_href, database_page_href=database_page_href),
        encoding="utf-8",
    )
    overview_path.write_text(
        render_overview(
            protocols,
            entries,
            bill_count=int(bill_output["count"]),
            database_href=database_href,
            database_page_href=database_page_href,
        ),
        encoding="utf-8",
    )
    catalog_page_path.write_text(
        render_catalog_page(
            protocols,
            entries,
            catalog_path,
            output_dir,
            database_page_href=database_page_href,
        ),
        encoding="utf-8",
    )
    sources_path.write_text(
        render_sources_page(entries, database_href=database_href, database_page_href=database_page_href),
        encoding="utf-8",
    )
    if database_page_href:
        database_page_path.write_text(render_database_page(database_path, database_href), encoding="utf-8")
    return index_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-key", help="DIP API key. Prefer DIP_API_KEY for local use.")
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
        "--vote-scan-pages",
        type=int,
        default=30,
        help="Number of Bundestag roll-call vote list pages to scan per sitting.",
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
        help="Skip linking speakers and vote members to their abgeordnetenwatch.de profiles.",
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
        help="Skip fetching the full MdB roster; Abgeordnete pages then cover only people seen in ingested protocols.",
    )
    return parser.parse_args()


def main() -> int:
    dip.load_local_env()
    args = parse_args()

    output_dir = args.output_dir
    (output_dir / "protocols").mkdir(parents=True, exist_ok=True)
    (output_dir / "data").mkdir(parents=True, exist_ok=True)
    (output_dir / "bills").mkdir(parents=True, exist_ok=True)
    (output_dir / "abgeordnete").mkdir(parents=True, exist_ok=True)
    database_path = args.database_path or output_dir / "data" / "bundestag-pulse.sqlite"

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
        if not args.no_persist and database_path.exists():
            store = pulse_store.connect(database_path)
            try:
                abg_mps, mp_lookup = collect_abgeordnete(store)
            finally:
                store.close()

        entries = rebuild_cached_detail_pages(output_dir, protocols, mp_lookup)
        index_path = render_site(
            output_dir=output_dir,
            database_path=database_path,
            no_persist=args.no_persist,
            protocols=protocols,
            entries=entries,
            abg_mps=abg_mps,
            mp_lookup=mp_lookup,
        )
        print(f"offline: rendered {len(entries)} cached dossiers", file=sys.stderr)
        print(index_path)
        return 0

    api_key = args.api_key or os.environ.get("DIP_API_KEY")
    if not api_key:
        print("error: Provide a DIP API key via --api-key or DIP_API_KEY.", file=sys.stderr)
        return 1

    profile_resolver = None
    if not args.no_abgeordnetenwatch:
        cache_path = args.abgeordnetenwatch_cache or output_dir / "data" / "abgeordnetenwatch-cache.json"
        profile_resolver = aw.AbgeordnetenwatchResolver(
            cache_path=cache_path,
            sleep_seconds=args.abgeordnetenwatch_sleep,
        )

    client = dip.ApiClient(api_key=api_key, sleep_seconds=args.sleep)
    try:
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
        existing_entries = (
            load_existing_detail_entries(output_dir, protocols) if args.preserve_existing_dossiers else []
        )
        abg_mps: list[dict[str, Any]] = []
        mp_lookup: dict[str, int] = {}
        try:
            generated_entries = [
                write_report_and_page(
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
                    existing_report=load_existing_report(output_dir, protocol),
                    profile_resolver=profile_resolver,
                )
                for protocol in detail_protocols
            ]
            entries = merge_detail_entries(protocols, existing_entries, generated_entries)
            if not args.no_persist:
                rebuild_database_from_entries(database_path, entries)
                store = pulse_store.connect(database_path)
                try:
                    pulse_store.initialize(store)
                    if not args.no_roster:
                        roster_stats = ingest_mdb_roster(
                            client,
                            store,
                            wahlperiode=args.roster_wahlperiode,
                            profile_resolver=profile_resolver,
                        )
                        print(
                            f"roster: {roster_stats['mdb']} MdBs of {roster_stats['fetched']} persons "
                            f"(WP{args.roster_wahlperiode}), {roster_stats['enriched']} enriched",
                            file=sys.stderr,
                        )
                    abg_mps, mp_lookup = collect_abgeordnete(store)
                finally:
                    store.close()
                entries = [write_report_files(entry["report"], output_dir, mp_lookup) for entry in entries]
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

    index_path = render_site(
        output_dir=output_dir,
        database_path=database_path,
        no_persist=args.no_persist,
        protocols=protocols,
        entries=entries,
        abg_mps=abg_mps,
        mp_lookup=mp_lookup,
    )
    print(index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
