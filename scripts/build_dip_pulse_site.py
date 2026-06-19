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
    page_path.write_text(pulse_html.render_html(report, overview_href="../index.html"), encoding="utf-8")
    return {
        "report": report,
        "report_path": report_path,
        "page_path": page_path,
        "slug": slug,
    }


def protocol_source_links(protocol: dict[str, Any]) -> str:
    fundstelle = protocol.get("fundstelle") or {}
    links = []
    for label, key in (("XML", "xml_url"), ("PDF", "pdf_url")):
        url = fundstelle.get(key)
        if url:
            links.append(f'<a href="{pulse_html.esc(url)}">{label}</a>')
    return "".join(links) or '<span class="muted">No source links</span>'


def render_catalog_json(protocol: dict[str, Any]) -> str:
    text = json.dumps(protocol, ensure_ascii=False, indent=2, sort_keys=True)
    return (
        '<details class="api-details">'
        '<summary>API fields</summary>'
        f"<pre>{pulse_html.esc(text)}</pre>"
        "</details>"
    )


def render_overview(
    protocols: list[dict[str, Any]],
    detail_entries: list[dict[str, Any]],
    catalog_path: Path,
) -> str:
    entries_by_id = {str(entry["report"].get("protocol", {}).get("id")): entry for entry in detail_entries}
    generated_cards = []
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
                f"<em>{pulse_html.esc(item.get('xml_speech_count'))} speeches</em>"
                "</li>"
            )
        warnings = report.get("warnings") or []
        warning_html = ""
        if warnings:
            warning_html = f'<span class="warn">{pulse_html.esc(str(len(warnings)))} warning</span>'

        generated_cards.append(
            f"""
            <article class="session-card">
              <div class="session-main">
                <div>
                  <span class="eyebrow">BT-PlPr {pulse_html.esc(protocol.get('dokumentnummer'))}</span>
                  <h2><a href="protocols/{pulse_html.esc(entry['page_path'].name)}">{pulse_html.esc(protocol.get('titel'))}</a></h2>
                  <p>{pulse_html.esc(protocol.get('datum'))} · distributed {pulse_html.esc(protocol.get('verteildatum'))}</p>
                </div>
                <a class="open-button" href="protocols/{pulse_html.esc(entry['page_path'].name)}">Open</a>
              </div>
              <div class="metrics">
                <div><span>TOPs</span><strong>{pulse_html.esc(summary.get('xml_top_count'))}</strong></div>
                <div><span>Speeches</span><strong>{pulse_html.esc(summary.get('xml_speech_count'))}</strong></div>
                <div><span>Drucksachen</span><strong>{pulse_html.esc(summary.get('xml_drucksache_count'))}</strong></div>
                <div><span>People</span><strong>{pulse_html.esc(summary.get('unique_person_ids'))}</strong></div>
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

    catalog_rows = []
    by_period: dict[str, int] = {}
    for protocol in protocols:
        period = str(protocol.get("wahlperiode") or "unknown")
        by_period[period] = by_period.get(period, 0) + 1
        fundstelle = protocol.get("fundstelle") or {}
        entry = entries_by_id.get(str(protocol.get("id")))
        dossier = '<span class="muted">Not generated</span>'
        metrics = '<span class="muted">Source metadata only</span>'
        if entry:
            report = entry["report"]
            summary = report.get("validation_summary") or {}
            dossier = f'<a class="open-button" href="protocols/{pulse_html.esc(entry["page_path"].name)}">Open dossier</a>'
            metrics = (
                f'{pulse_html.esc(summary.get("xml_top_count"))} TOPs · '
                f'{pulse_html.esc(summary.get("xml_speech_count"))} speeches · '
                f'{pulse_html.esc(summary.get("aktivitaet_count"))} activities'
            )

        catalog_rows.append(
            f"""
            <article class="catalog-row">
              <div>
                <span class="eyebrow">BT-PlPr {pulse_html.esc(protocol.get('dokumentnummer'))} · WP {pulse_html.esc(protocol.get('wahlperiode'))}</span>
                <h3>{pulse_html.esc(protocol.get('titel'))}</h3>
                <p>{pulse_html.esc(protocol.get('datum'))} · updated {pulse_html.esc(protocol.get('aktualisiert'))}</p>
              </div>
              <div class="catalog-meta">
                <span>{pulse_html.esc(protocol.get('dokumentart') or protocol.get('typ'))}</span>
                <strong>{pulse_html.esc(protocol.get('vorgangsbezug_anzahl', 0))}</strong>
                <em>proceeding refs</em>
              </div>
              <div class="catalog-meta">
                <span>Distributed</span>
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

    period_badges = "".join(
        f'<span class="badge">WP {pulse_html.esc(period)} <strong>{pulse_html.esc(count)}</strong></span>'
        for period, count in sorted(by_period.items(), key=lambda item: item[0], reverse=True)
    )
    latest = protocols[0] if protocols else {}
    generated_latest = detail_entries[0]["report"].get("protocol", {}) if detail_entries else {}
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag Pulse · Sitzungen</title>
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
    .summary-band span, .catalog-meta span {{
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
    .catalog {{
      display:grid;
      gap:10px;
      margin-top:18px;
    }}
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
    .catalog-row h3 {{
      margin:5px 0 0;
      font-size:17px;
      line-height:1.25;
      overflow-wrap:anywhere;
    }}
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
    .catalog-actions {{
      display:grid;
      justify-items:start;
      gap:8px;
    }}
    .catalog-status {{
      grid-column:1 / -1;
      padding-top:10px;
      border-top:1px solid #eef1f5;
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
    .muted {{ color:var(--muted); }}
    footer {{ padding-top:24px; color:var(--muted); font-size:12px; }}
    @media (max-width: 940px) {{
      .summary-band, .catalog-row {{ grid-template-columns:1fr; }}
      .catalog-status, .api-details {{ grid-column:auto; }}
    }}
    @media (max-width: 740px) {{
      .shell {{ padding:18px 14px; }}
      header, .session-main {{ grid-template-columns:1fr; }}
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
        <h1>Bundestag Pulse</h1>
        <p class="subtitle">Comprehensive Bundestag Plenarprotokoll catalog from the DIP API, with generated dossiers for selected sittings.</p>
      </div>
      <div class="latest">
        <span>Latest API sitting</span>
        <strong>{pulse_html.esc(latest.get('dokumentnummer', ''))}</strong>
        <em>{pulse_html.esc(latest.get('datum', ''))}</em>
      </div>
    </header>
    <section class="summary-band">
      <div><span>API sittings</span><strong>{pulse_html.esc(len(protocols))}</strong></div>
      <div><span>Generated dossiers</span><strong>{pulse_html.esc(len(detail_entries))}</strong></div>
      <div><span>Latest generated</span>
        <strong>{pulse_html.esc(generated_latest.get('dokumentnummer', ''))}</strong>
        <em>{pulse_html.esc(generated_latest.get('datum', ''))}</em>
      </div>
    </section>
    <div class="periods">{period_badges}</div>
    <div class="section-head">
      <h2>Generated Sitting Dossiers</h2>
      <p>These pages include XML transcript extraction, agenda item attention, speakers, speeches, matched DIP positions and activities, linked Drucksachen, roll-call votes, people records, and raw API payloads.</p>
    </div>
    <section class="sessions">
      {''.join(generated_cards) if generated_cards else '<p class="muted">No detailed dossiers generated in this run.</p>'}
    </section>
    <div class="section-head">
      <h2>All API Sittings</h2>
      <p>Every fetched Plenarprotokoll record is listed below. The full catalog JSON is also written to <a href="data/{pulse_html.esc(catalog_path.name)}">data/{pulse_html.esc(catalog_path.name)}</a>.</p>
    </div>
    <section class="catalog">
      {''.join(catalog_rows)}
    </section>
    <footer>
      XML transcript is canonical; DIP API data enriches each sitting. Use --detail-limit 0 to generate detailed dossiers for every fetched protocol, or --detail-limit -1 for a catalog-only build.
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
        "--person-limit",
        type=int,
        default=0,
        help="Number of distinct person records to fetch for each detailed dossier. Use 0 for all seen person records.",
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

    client = dip.ApiClient(api_key=api_key, sleep_seconds=args.sleep)
    try:
        protocols = fetch_protocols(client, args.limit, args.document_number)
        detail_limit = None if args.document_number else args.detail_limit
        detail_protocols = protocols_for_detail_pages(protocols, detail_limit)
        entries = [
            write_report_and_page(
                protocol=protocol,
                output_dir=output_dir,
                api_key=api_key,
                sleep=args.sleep,
                person_limit=args.person_limit,
                vote_scan_pages=args.vote_scan_pages,
            )
            for protocol in detail_protocols
        ]
    except dip.DipError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    catalog_path = output_dir / "data" / "plenarprotokoll-catalog.json"
    catalog_path.write_text(json.dumps(protocols, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    index_path = output_dir / "index.html"
    index_path.write_text(render_overview(protocols, entries, catalog_path), encoding="utf-8")
    print(index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
