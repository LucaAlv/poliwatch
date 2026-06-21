#!/usr/bin/env python3
"""Build a static Bundestag Pulse overview site for multiple sittings."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import render_dip_pulse_html as pulse_html
import persist_dip_pulse_store as pulse_store
import validate_dip_protocol as dip


def slugify_document_number(document_number: str) -> str:
    value = document_number.strip().replace("/", "-")
    value = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value)
    return value.strip("-").lower()


def protocol_sort_key(protocol: dict[str, Any]) -> tuple[str, str]:
    return (str(protocol.get("datum") or ""), str(protocol.get("id") or ""))


def fetch_protocols(client: dip.ApiClient, limit: int, document_numbers: list[str]) -> list[dict[str, Any]]:
    if document_numbers:
        protocols = []
        for document_number in document_numbers:
            documents = client.list_all(
                "/plenarprotokoll",
                {"f.zuordnung": "BT", "f.dokumentnummer": document_number},
            )
            if not documents:
                raise dip.DipError(f"No BT Plenarprotokoll found for {document_number}")
            protocols.append(documents[0])
        return sorted(protocols, key=protocol_sort_key, reverse=True)

    protocols: list[dict[str, Any]] = []
    params: dict[str, Any] = {"f.zuordnung": "BT"}
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
    if detail_limit is None:
        return protocols
    if detail_limit < 0:
        return []
    if detail_limit <= 0:
        return protocols
    return protocols[:detail_limit]


def write_report_and_page(
    protocol: dict[str, Any],
    output_dir: Path,
    api_key: str,
    sleep: float,
    person_limit: int,
    vote_scan_pages: int,
    summary_mode: str,
    anthropic_api_key: str | None,
    summary_model: str | None,
    store: Any | None,
) -> dict[str, Any]:
    document_number = str(protocol["dokumentnummer"])
    slug = slugify_document_number(document_number)
    report_path = output_dir / "data" / f"plenarprotokoll-{slug}.json"
    page_path = output_dir / "protocols" / f"plenarprotokoll-{slug}.html"

    args = argparse.Namespace(
        api_key=api_key,
        protocol_id=str(protocol["id"]),
        document_number=None,
        limit_tops=None,
        person_limit=person_limit,
        vote_scan_pages=vote_scan_pages,
        summary_mode=summary_mode,
        anthropic_api_key=anthropic_api_key,
        summary_model=summary_model,
        sleep=sleep,
    )
    report = dip.build_report(args)
    if store is not None:
        pulse_store.persist_report(store, report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    page_path.write_text(
        pulse_html.render_html(
            report,
            overview_href="../overview.html",
            catalog_href="../api-sitzungen.html",
            bills_href="../bills/index.html",
            sources_href="../sources.html",
        ),
        encoding="utf-8",
    )
    return {
        "report": report,
        "report_path": report_path,
        "page_path": page_path,
        "slug": slug,
    }


def render_front_page(entries: list[dict[str, Any]], database_href: str | None = "data/bundestag-pulse.sqlite") -> str:
    if not entries:
        return """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls</title>
</head>
<body>
  <main>
    <h1>Bundestag-Puls</h1>
    <p>Es wurden noch keine Sitzungen erzeugt.</p>
  </main>
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
    store_note = (
        " Die SQLite-Datei enthält MPs, Parteien, Vorgänge, Reden und Abstimmungen als verknüpfte Datensätze."
        if database_href
        else ""
    )

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
  <title>Bundestag-Puls · Neueste Sitzung</title>
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
    header {{
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:20px;
      align-items:start;
      padding-bottom:20px;
      border-bottom:1px solid var(--line);
    }}
    h1 {{ margin:0; font-size:37px; line-height:1.08; font-weight:780; }}
    h2 {{ margin:0; font-size:18px; line-height:1.25; }}
    p {{ margin:7px 0 0; color:var(--muted); }}
    .subtitle {{ max-width:760px; font-size:15px; }}
    .nav-links {{ display:flex; flex-wrap:wrap; gap:9px; justify-content:flex-end; }}
    .nav-links a, .primary-link, .session-links a {{
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
    .primary-link {{ border-color:#bdd0ea; background:var(--blue-soft); }}
    .latest-strip {{
      display:grid;
      grid-template-columns:1.15fr minmax(420px,.85fr);
      gap:18px;
      margin-top:18px;
      align-items:stretch;
    }}
    .latest-panel, .future-panel {{
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel);
      padding:18px;
    }}
    .eyebrow, .metric span, .top-link span, label, .card-meta, .future-panel span {{
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .latest-title {{ margin:5px 0 0; font-size:25px; line-height:1.18; }}
    .metric-grid {{
      display:grid;
      grid-template-columns:repeat(4, minmax(92px,1fr));
      gap:10px;
      margin-top:18px;
    }}
    .metric {{
      min-height:68px;
      border:1px solid #e2e7ef;
      border-radius:8px;
      background:#fbfcfd;
      padding:10px 11px;
    }}
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
    .layout {{
      display:grid;
      grid-template-columns:minmax(0,1fr) 330px;
      gap:18px;
      margin-top:18px;
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
    aside {{ display:grid; gap:12px; }}
    .future-panel:nth-child(1) {{ background:var(--green-soft); }}
    .future-panel:nth-child(2) {{ background:var(--amber-soft); }}
    .future-panel:nth-child(3) {{ background:#f5f7fb; }}
    .future-panel h2 {{ margin-top:6px; }}
    .future-panel p {{ font-size:13px; line-height:1.45; }}
    .placeholder-lines {{ display:grid; gap:7px; margin-top:14px; }}
    .placeholder-lines i {{
      display:block;
      height:8px;
      border-radius:999px;
      background:rgba(23,26,31,.12);
    }}
    .placeholder-lines i:nth-child(2) {{ width:76%; }}
    .placeholder-lines i:nth-child(3) {{ width:54%; }}
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
      header, .latest-strip, .layout {{ grid-template-columns:1fr; }}
      .nav-links {{ justify-content:flex-start; }}
    }}
    @media (max-width: 700px) {{
      .shell {{ padding:16px 14px; }}
      h1 {{ font-size:29px; }}
      .latest-title {{ font-size:21px; }}
      .metric-grid, .bar-grid {{ grid-template-columns:1fr 1fr; }}
      .section-head {{ display:grid; }}
    }}
    @media (max-width: 460px) {{
      .metric-grid, .bar-grid {{ grid-template-columns:1fr; }}
      .card-meta a {{ margin-left:0; width:100%; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <span class="eyebrow">Neueste Sitzung</span>
        <h1>Bundestag-Puls</h1>
        <p class="subtitle">Das neueste erzeugte Plenarprotokoll, sortiert danach, wo sich die parlamentarische Aufmerksamkeit in der Sitzung konzentrierte.</p>
      </div>
      <nav class="nav-links" aria-label="Hauptnavigation">
        <a class="primary-link" href="{protocol_href}">Details öffnen</a>
        <a href="overview.html">Plenarprotokoll-Katalog</a>
        <a href="api-sitzungen.html">Alle API-Sitzungen</a>
        <a href="bills/index.html">Gesetze verfolgen</a>
      </nav>
    </header>

    <section class="latest-strip">
      <div class="latest-panel">
        <span class="eyebrow">BT-PlPr {pulse_html.esc(protocol.get('dokumentnummer'))}</span>
        <h2 class="latest-title">{pulse_html.esc(protocol.get('titel'))}</h2>
        <p>{pulse_html.esc(protocol.get('datum'))} · verteilt am {pulse_html.esc(protocol.get('verteildatum'))}</p>
        <div class="metric-grid">
          <div class="metric"><span>Tagesordnung</span><strong>{pulse_html.esc(summary.get('xml_top_count'))}</strong></div>
          <div class="metric"><span>Reden</span><strong>{pulse_html.esc(summary.get('xml_speech_count'))}</strong></div>
          <div class="metric"><span>Drucksachen</span><strong>{pulse_html.esc(summary.get('xml_drucksache_count'))}</strong></div>
          <div class="metric"><span>Personen</span><strong>{pulse_html.esc(summary.get('unique_person_ids'))}</strong></div>
        </div>
        <div class="session-links">
          <a href="{protocol_href}">Sitzungsdetails</a>
          <a href="{pulse_html.esc(protocol.get('xml_url'))}">XML-Protokoll</a>
          <a href="{pulse_html.esc(protocol.get('pdf_url'))}">PDF-Protokoll</a>
          <a href="{report_href}">Erzeugtes JSON</a>
          {sqlite_link}
        </div>
      </div>
      <div class="latest-panel source-panel">
        <div>
          <span class="eyebrow">Quellenlage</span>
          <h2>Primärquellen-Puls</h2>
          <p>Redezahlen, Textumfang, Drucksachen und Rednerdaten werden aus dem offiziellen Protokoll und DIP-Daten dieser Sitzung erzeugt.</p>
        </div>
        <div>
          <span class="eyebrow">Nächster Vergleich</span>
          <p>Dieser Bereich ist für Wochenvergleiche reserviert, sobald mehrere Sitzungswochen normalisiert sind.</p>
        </div>
      </div>
    </section>

    <div class="layout">
      <main>
        <div class="section-head">
          <div>
            <span class="eyebrow">Neueste Informationen</span>
            <h2>Aufmerksamkeitsranking</h2>
          </div>
          <p>Die wichtigsten Tagesordnungspunkte der neuesten Sitzung, sortiert nach extrahierter Redezahl.</p>
        </div>
        {warning_html}
        {''.join(attention_rows)}
      </main>
      <aside>
        <section class="future-panel">
          <span>Reserviert</span>
          <h2>Themenbewegung</h2>
          <p>Vergleiche, welche Themen diese Woche mehr Aufmerksamkeit erhielten als letzte Woche.</p>
          <div class="placeholder-lines" aria-hidden="true"><i></i><i></i><i></i></div>
        </section>
        <section class="future-panel">
          <span>Reserviert</span>
          <h2>Abstimmungsverschiebungen</h2>
          <p>Hebt namentliche Abstimmungen und Fraktionsabweichungen hervor, sobald der Parser dafür reift.</p>
          <div class="placeholder-lines" aria-hidden="true"><i></i><i></i><i></i></div>
        </section>
        <section class="future-panel">
          <span>Archiv</span>
          <h2>Frühere Sitzungen</h2>
          <p>Nutze die Übersichtsseite, um frühere erzeugte Sitzungen und ihre Quelldateien zu entdecken.</p>
          <div class="session-links"><a href="overview.html">Übersicht öffnen</a></div>
        </section>
      </aside>
    </div>

    <footer>
      Statischer Prototyp. Das XML-Protokoll ist maßgeblich; DIP-API-Daten ergänzen jede Sitzung.{store_note}
    </footer>
  </div>
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
    header {
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:22px;
      align-items:end;
      padding-bottom:20px;
      border-bottom:1px solid var(--line);
    }
    nav { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:10px; }
    nav a, .source-link {
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
      header, .bill-card, .content-grid { grid-template-columns:1fr; }
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
  <style>{bill_styles()}</style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <nav><a href="../index.html">Alle Sitzungen</a></nav>
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
    <footer>Die Folge-Markierung wird lokal im Browser gespeichert. Die Liste umfasst die Dossiers, die in diesem Build mit --detail-limit erzeugt wurden.</footer>
  </div>
  {render_bill_script()}
</body>
</html>
"""


def render_bill_detail(bill: dict[str, Any]) -> str:
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
        speakers.append(
            '<li class="speaker-row">'
            f'<strong>{pulse_html.esc(speaker.get("name"))}</strong>'
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
  <style>{bill_styles()}</style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <nav><a href="index.html">Alle Gesetze</a><a href="../index.html">Alle Sitzungen</a></nav>
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
    <footer>Diese Seite beschreibt nur Felder, die in den erzeugten Rohdaten vorhanden sind. Automatische Zusammenfassungen sind bewusst nicht enthalten.</footer>
  </div>
  {render_bill_script()}
</body>
</html>
"""


def write_bill_pages(output_dir: Path, bills: list[dict[str, Any]]) -> dict[str, Any]:
    bills_dir = output_dir / "bills"
    bills_dir.mkdir(parents=True, exist_ok=True)
    for bill in bills:
        (bills_dir / f"{bill['slug']}.html").write_text(render_bill_detail(bill), encoding="utf-8")
    (bills_dir / "index.html").write_text(render_bills_index(bills), encoding="utf-8")
    data_path = output_dir / "data" / "bills.json"
    data_path.write_text(json.dumps(bills, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"count": len(bills), "index_path": bills_dir / "index.html", "data_path": data_path}


def render_overview(
    protocols: list[dict[str, Any]],
    detail_entries: list[dict[str, Any]],
    bill_count: int = 0,
    database_href: str | None = "data/bundestag-pulse.sqlite",
    catalog_href: str = "api-sitzungen.html",
) -> str:
    generated_cards = []
    sqlite_link = f'<a href="{pulse_html.esc(database_href)}">SQLite</a>' if database_href else ""
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
    .page-nav {{
      display:flex;
      flex-wrap:wrap;
      gap:8px;
      margin-bottom:12px;
    }}
    .page-nav a {{
      display:inline-flex;
      align-items:center;
      min-height:30px;
      padding:4px 9px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      font-size:13px;
      font-weight:650;
    }}
    header {{
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
    .nav-links {{
      display:flex;
      flex-wrap:wrap;
      gap:9px;
      justify-content:flex-end;
    }}
    .nav-links a {{
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-height:34px;
      padding:5px 11px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      font-size:13px;
      font-weight:700;
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
    .nav-links {{
      display:flex;
      flex-wrap:wrap;
      gap:8px;
      margin-bottom:10px;
      font-size:13px;
    }}
    .nav-links a {{
      display:inline-flex;
      align-items:center;
      min-height:30px;
      padding:4px 9px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      font-weight:650;
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
      header, .session-main {{ grid-template-columns:1fr; }}
      .nav-links {{ justify-content:flex-start; }}
      h1 {{ font-size:29px; }}
      h2 {{ font-size:19px; }}
      .metrics {{ grid-template-columns:1fr 1fr; }}
      .top-preview li {{ grid-template-columns:1fr; gap:3px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <nav class="nav-links"><a href="{pulse_html.esc(catalog_href)}">Alle API-Sitzungen</a><a href="bills/index.html">Gesetze verfolgen</a><a href="sources.html">Quellen</a></nav>
        <h1>Bundestag-Puls</h1>
        <p class="subtitle">Umfassender Plenarprotokoll-Katalog aus der DIP-API mit erzeugten Dossiers für ausgewählte Sitzungen.</p>
      </div>
      <div>
        <nav class="nav-links" aria-label="Sitzungsnavigation">
          <a href="index.html">Neueste Sitzung</a>
          <a href="{pulse_html.esc(catalog_href)}">Alle Sitzungen</a>
        </nav>
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
      Das XML-Protokoll ist maßgeblich; DIP-API-Daten ergänzen jede Sitzung. Mit --detail-limit 0 werden Dossiers für alle geholten Protokolle erzeugt, mit --detail-limit -1 nur der Katalog. <a href="sources.html">Quellen und Methode</a>.
    </footer>
  </div>
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
            <article class="catalog-row" data-row data-search="{pulse_html.esc(search_terms)}" data-wp="{pulse_html.esc(period)}" data-dossier="{has_dossier}" data-date="{pulse_html.esc(protocol.get('datum') or '')}" data-sortnum="{catalog_sortnum(protocol)}">
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


def render_catalog_page(
    protocols: list[dict[str, Any]],
    detail_entries: list[dict[str, Any]],
    catalog_path: Path,
    overview_href: str = "overview.html",
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
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Alle API-Sitzungen</title>
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
    header {{
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:24px;
      align-items:end;
      padding-bottom:22px;
      border-bottom:1px solid var(--line);
    }}
    .nav-links {{
      display:flex;
      flex-wrap:wrap;
      gap:8px;
      margin-bottom:10px;
      font-size:13px;
    }}
    .nav-links a {{
      display:inline-flex;
      align-items:center;
      min-height:30px;
      padding:4px 9px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      font-weight:650;
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
      header {{ grid-template-columns:1fr; }}
      h1 {{ font-size:29px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <nav class="nav-links">
          <a href="index.html">Neueste Sitzung</a>
          <a href="{pulse_html.esc(overview_href)}">Plenarprotokoll-Katalog</a>
          <a href="bills/index.html">Gesetze verfolgen</a>
          <a href="sources.html">Quellen</a>
        </nav>
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
</body>
</html>
"""


def render_sources_page(entries: list[dict[str, Any]]) -> str:
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
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag-Puls · Quellen</title>
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
    header {{
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:24px;
      align-items:end;
      padding-bottom:22px;
      border-bottom:1px solid var(--line);
    }}
    .nav-links {{
      display:flex;
      flex-wrap:wrap;
      gap:8px;
      margin-bottom:10px;
      font-size:13px;
    }}
    .nav-links a {{
      display:inline-flex;
      align-items:center;
      min-height:30px;
      padding:4px 9px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      font-weight:650;
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
      header, .source-grid {{ grid-template-columns:1fr; }}
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
    <header>
      <div>
        <nav class="nav-links"><a href="index.html">Neueste Sitzung</a><a href="overview.html">Plenarprotokoll-Katalog</a><a href="api-sitzungen.html">Alle API-Sitzungen</a><a href="bills/index.html">Gesetze verfolgen</a></nav>
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
        </div>
      </section>
      <section class="panel">
        <h2>Wie die Seite sie nutzt</h2>
        <ul class="method-list">
          <li><strong>Tagesordnungspunkte</strong><span>Aus der Tagesordnungspunkt-Struktur des Plenarprotokoll-XML gelesen. Die parlamentarische Gliederung bildet die Themen-Grenze.</span></li>
          <li><strong>Aufmerksamkeitsranking</strong><span>Mechanisch aus extrahierter Redenanzahl und extrahierten Redetext-Zeichen pro Tagesordnungspunkt berechnet.</span></li>
          <li><strong>Redner und Fraktionen</strong><span>Aus den Redner-Knoten im XML-Protokoll gelesen. Regierungsrollen werden angezeigt, wenn das XML eine Rolle statt einer Fraktion liefert.</span></li>
          <li><strong>Verknüpfte Dokumente</strong><span>Kombiniert Drucksachen, die direkt im Protokoll verlinkt sind, mit zugehörigen DIP-Vorgangspositionen der Sitzung.</span></li>
          <li><strong>Abstimmungspanels</strong><span>Werden nur angezeigt, wenn eine namentliche Abstimmung am selben Datum über überlappende Drucksachennummern einem Tagesordnungspunkt zugeordnet werden kann.</span></li>
          <li><strong>Erzeugtes JSON</strong><span>Jede Sitzungsseite verlinkt den Zwischenbericht als JSON, damit Extraktion und Anreicherung direkt geprüft werden können.</span></li>
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
      Quellenlinks verweisen auf öffentliche Bundestags- und DIP-Datensätze. Verfügbarkeit und genaue Inhalte werden von diesen offiziellen Diensten bestimmt.
    </footer>
  </div>
</body>
</html>
"""


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
    parser.add_argument("--output-dir", type=Path, default=Path(".context/dip-pulse-site"))
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
        "--person-limit",
        type=int,
        default=0,
        help="Number of distinct person records to fetch for each detailed dossier. Use 0 for all seen person records.",
    )
    parser.add_argument(
        "--summary-mode",
        choices=("auto", "required", "off"),
        default="auto",
        help="Generate per-TOP LLM summaries when ANTHROPIC_API_KEY is available, require them, or disable them.",
    )
    parser.add_argument("--anthropic-api-key", help="Anthropic API key. Prefer ANTHROPIC_API_KEY for local use.")
    parser.add_argument(
        "--summary-model",
        help=(
            "Comma-separated Anthropic model IDs to try for summaries. "
            "Defaults to Claude Opus 4.8, then Sonnet 4.6."
        ),
    )
    parser.add_argument(
        "--vote-scan-pages",
        type=int,
        default=30,
        help="Number of Bundestag roll-call vote list pages to scan per sitting.",
    )
    parser.add_argument("--sleep", type=float, default=0.0, help="Optional delay between DIP API requests.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = args.api_key or os.environ.get("DIP_API_KEY")
    if not api_key:
        print("error: Provide a DIP API key via --api-key or DIP_API_KEY.", file=sys.stderr)
        return 1

    output_dir = args.output_dir
    (output_dir / "protocols").mkdir(parents=True, exist_ok=True)
    (output_dir / "data").mkdir(parents=True, exist_ok=True)
    (output_dir / "bills").mkdir(parents=True, exist_ok=True)
    database_path = args.database_path or output_dir / "data" / "bundestag-pulse.sqlite"

    client = dip.ApiClient(api_key=api_key, sleep_seconds=args.sleep)
    try:
        protocols = fetch_protocols(client, args.limit, args.document_number)
        detail_limit = None if args.document_number else args.detail_limit
        detail_protocols = protocols_for_detail_pages(protocols, detail_limit)
        store = None if args.no_persist else pulse_store.connect(database_path)
        try:
            entries = [
                write_report_and_page(
                    protocol=protocol,
                    output_dir=output_dir,
                    api_key=api_key,
                    sleep=args.sleep,
                    person_limit=args.person_limit,
                    vote_scan_pages=args.vote_scan_pages,
                    summary_mode=args.summary_mode,
                    anthropic_api_key=args.anthropic_api_key,
                    summary_model=args.summary_model,
                    store=store,
                )
                for protocol in detail_protocols
            ]
        finally:
            if store is not None:
                store.close()
    except dip.DipError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    database_href = None
    if not args.no_persist:
        try:
            database_href = database_path.resolve().relative_to(output_dir.resolve()).as_posix()
        except ValueError:
            database_href = None

    catalog_path = output_dir / "data" / "plenarprotokoll-catalog.json"
    catalog_path.write_text(json.dumps(protocols, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bills = collect_bill_pages(entries)
    bill_output = write_bill_pages(output_dir, bills)
    index_path = output_dir / "index.html"
    overview_path = output_dir / "overview.html"
    catalog_page_path = output_dir / "api-sitzungen.html"
    sources_path = output_dir / "sources.html"
    index_path.write_text(render_front_page(entries, database_href=database_href), encoding="utf-8")
    overview_path.write_text(
        render_overview(
            protocols,
            entries,
            bill_count=int(bill_output["count"]),
            database_href=database_href,
        ),
        encoding="utf-8",
    )
    catalog_page_path.write_text(
        render_catalog_page(protocols, entries, catalog_path),
        encoding="utf-8",
    )
    sources_path.write_text(render_sources_page(entries), encoding="utf-8")
    print(index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
