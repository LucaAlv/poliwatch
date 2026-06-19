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
    while len(protocols) < limit:
        page = client.get_json("/plenarprotokoll", params)
        protocols.extend(page.get("documents") or [])
        cursor = page.get("cursor")
        if not cursor or cursor == previous_cursor:
            break
        previous_cursor = cursor
        params["cursor"] = cursor
    return protocols[:limit]


def write_report_and_page(
    protocol: dict[str, Any],
    output_dir: Path,
    api_key: str,
    sleep: float,
    person_limit: int,
    vote_scan_pages: int,
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
        sleep=sleep,
    )
    report = dip.build_report(args)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    page_path.write_text(pulse_html.render_html(report, overview_href="../overview.html"), encoding="utf-8")
    return {
        "report": report,
        "report_path": report_path,
        "page_path": page_path,
        "slug": slug,
    }


def render_front_page(entries: list[dict[str, Any]]) -> str:
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
      <nav class="nav-links" aria-label="Primary">
        <a class="primary-link" href="{protocol_href}">Details öffnen</a>
        <a href="overview.html">Alle Sitzungen</a>
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
      Statischer Prototyp. Das XML-Protokoll ist maßgeblich; DIP-API-Daten ergänzen jede Sitzung.
    </footer>
  </div>
</body>
</html>
"""


def render_overview(entries: list[dict[str, Any]]) -> str:
    rows = []
    for entry in entries:
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

        rows.append(
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
                {warning_html}
              </div>
            </article>
            """
        )

    latest = entries[0]["report"].get("protocol", {}) if entries else {}
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
    .shell {{ max-width:1180px; margin:0 auto; padding:28px 22px; }}
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
    footer {{ padding-top:24px; color:var(--muted); font-size:12px; }}
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
        <h1>Bundestag-Puls</h1>
        <p class="subtitle">Übersicht der erzeugten Sitzungen, um frühere Tagesordnungspunkte, Reden, Fraktionen und verknüpfte Primärquellen zu prüfen.</p>
      </div>
      <div>
        <nav class="nav-links" aria-label="Overview navigation">
          <a href="index.html">Neueste Sitzung</a>
        </nav>
        <div class="latest">
          <span>Zuletzt erzeugt</span>
          <strong>{pulse_html.esc(latest.get('dokumentnummer', ''))}</strong>
          <em>{pulse_html.esc(latest.get('datum', ''))}</em>
        </div>
      </div>
    </header>
    <section class="sessions">
      {''.join(rows)}
    </section>
    <footer>
      Statischer Prototyp. Das XML-Protokoll ist maßgeblich; DIP-API-Daten ergänzen jede Sitzung.
    </footer>
  </div>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-key", help="DIP API key. Prefer DIP_API_KEY for local use.")
    parser.add_argument("--limit", type=int, default=5, help="Number of recent Bundestag protocols to generate.")
    parser.add_argument(
        "--document-number",
        action="append",
        default=[],
        help="Specific protocol document number to include, e.g. 21/84. Can be repeated.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path(".context/dip-pulse-site"))
    parser.add_argument("--person-limit", type=int, default=12)
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

    client = dip.ApiClient(api_key=api_key, sleep_seconds=args.sleep)
    try:
        protocols = fetch_protocols(client, args.limit, args.document_number)
        entries = [
            write_report_and_page(
                protocol=protocol,
                output_dir=output_dir,
                api_key=api_key,
                sleep=args.sleep,
                person_limit=args.person_limit,
                vote_scan_pages=args.vote_scan_pages,
            )
            for protocol in protocols
        ]
    except dip.DipError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    index_path = output_dir / "index.html"
    overview_path = output_dir / "overview.html"
    index_path.write_text(render_front_page(entries), encoding="utf-8")
    overview_path.write_text(render_overview(entries), encoding="utf-8")
    print(index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
