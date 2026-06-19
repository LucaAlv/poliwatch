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
    page_path.write_text(
        pulse_html.render_html(report, overview_href="../index.html", sources_href="../sources.html"),
        encoding="utf-8",
    )
    return {
        "report": report,
        "report_path": report_path,
        "page_path": page_path,
        "slug": slug,
    }


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
                f"<em>{pulse_html.esc(item.get('xml_speech_count'))} speeches</em>"
                "</li>"
            )
        warnings = report.get("warnings") or []
        warning_html = ""
        if warnings:
            warning_html = f'<span class="warn">{pulse_html.esc(str(len(warnings)))} warning</span>'

        rows.append(
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

    latest = entries[0]["report"].get("protocol", {}) if entries else {}
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
    footer {{ padding-top:24px; color:var(--muted); font-size:12px; }}
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
        <nav class="nav-links"><a href="sources.html">Sources</a></nav>
        <h1>Bundestag Pulse</h1>
        <p class="subtitle">Choose a sitting to inspect agenda items, speeches, factions, and linked primary-source documents.</p>
      </div>
      <div class="latest">
        <span>Latest generated</span>
        <strong>{pulse_html.esc(latest.get('dokumentnummer', ''))}</strong>
        <em>{pulse_html.esc(latest.get('datum', ''))}</em>
      </div>
    </header>
    <section class="sessions">
      {''.join(rows)}
    </section>
    <footer>
      Static prototype. XML transcript is canonical; DIP API data enriches each sitting. <a href="sources.html">See sources and method</a>.
    </footer>
  </div>
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
        generated_rows.append('<tr><td colspan="5" class="muted">No sittings were generated in this build.</td></tr>')

    latest = entries[0]["report"].get("protocol", {}) if entries else {}
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bundestag Pulse · Sources</title>
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
        <nav class="nav-links"><a href="index.html">All Sitzungen</a></nav>
        <h1>Sources</h1>
        <p class="subtitle">Bundestag Pulse is built from official parliamentary records. This page documents what is used, how it is transformed, and what is intentionally excluded.</p>
      </div>
      <div class="latest">
        <span>Latest generated</span>
        <strong>{pulse_html.esc(latest.get('dokumentnummer', ''))}</strong>
        <em>{pulse_html.esc(latest.get('datum', ''))}</em>
      </div>
    </header>
    <main>
      <section class="panel">
        <h2>Primary Sources</h2>
        <div class="source-grid">
          <article class="source-card">
            <span class="eyebrow">Canonical transcript</span>
            <h3>Bundestag Plenarprotokoll XML</h3>
            <p>Agenda items, speech text, speakers, page references, and Drucksachen mentioned inside a sitting are parsed from the official XML transcript.</p>
            <a href="https://search.dip.bundestag.de/api/v1/plenarprotokoll">DIP Plenarprotokoll API</a>
          </article>
          <article class="source-card">
            <span class="eyebrow">Metadata enrichment</span>
            <h3>DIP API records</h3>
            <p>Proceeding positions, parliamentary activities, document metadata, and linked Drucksachen are fetched from the Bundestag DIP API and attached to the matching agenda item.</p>
            <a href="https://search.dip.bundestag.de/api/v1">DIP API base</a>
          </article>
          <article class="source-card">
            <span class="eyebrow">Original documents</span>
            <h3>Drucksachen and PDFs</h3>
            <p>Document numbers are extracted from transcript links and cross-checked against DIP positions. PDF links are shown when the official record provides one.</p>
            <a href="https://dip.bundestag.de">DIP document search</a>
          </article>
          <article class="source-card">
            <span class="eyebrow">Recorded votes</span>
            <h3>Namentliche Abstimmungen</h3>
            <p>Roll-call vote totals, faction totals, and individual member votes come from the Bundestag roll-call pages and are matched by sitting date plus Drucksache numbers.</p>
            <a href="https://www.bundestag.de/parlament/plenum/abstimmung">Bundestag roll-call votes</a>
          </article>
        </div>
      </section>
      <section class="panel">
        <h2>How The Site Uses Them</h2>
        <ul class="method-list">
          <li><strong>Agenda items</strong><span>Parsed from the Plenarprotokoll XML Tagesordnungspunkt structure. The parliament's own segmentation is used as the topic boundary.</span></li>
          <li><strong>Attention ranking</strong><span>Derived mechanically from extracted speech counts and extracted speech-text character counts per agenda item.</span></li>
          <li><strong>Speaker and faction data</strong><span>Read from the Redner nodes in the XML transcript. Government roles are shown when the XML gives a role instead of a faction.</span></li>
          <li><strong>Linked documents</strong><span>Combined from Drucksachen explicitly linked in the transcript and related DIP Vorgangsposition records for the sitting.</span></li>
          <li><strong>Vote panels</strong><span>Rendered only when a roll-call vote on the same date can be matched to the agenda item through overlapping Drucksache numbers.</span></li>
          <li><strong>Generated JSON</strong><span>Each sitting page links to the intermediate JSON report so the extraction and enrichment payload can be inspected directly.</span></li>
        </ul>
      </section>
      <section class="panel note">
        <h2>What Is Not Used</h2>
        <p>No news articles, polling aggregators, campaign material, social media posts, or editorial commentary are used as sources for the current prototype. The current pages show extracted records and mechanical metrics; they do not make unsourced stance claims.</p>
      </section>
      <section class="panel">
        <h2>Generated Sitting Records</h2>
        <table>
          <thead>
            <tr>
              <th>Protocol</th>
              <th>Date</th>
              <th>TOPs</th>
              <th>Speeches</th>
              <th>Receipts</th>
            </tr>
          </thead>
          <tbody>
            {''.join(generated_rows)}
          </tbody>
        </table>
      </section>
    </main>
    <footer>
      Source links point to public Bundestag and DIP records. Availability and exact contents are controlled by those official services.
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
    index_path.write_text(render_overview(entries), encoding="utf-8")
    sources_path = output_dir / "sources.html"
    sources_path.write_text(render_sources_page(entries), encoding="utf-8")
    print(index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
