#!/usr/bin/env python3
"""Render a static Bundestag Pulse HTML view from validation JSON."""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


PARTY_COLORS = {
    "CDU/CSU": "#222222",
    "SPD": "#d71920",
    "AfD": "#2f6fb4",
    "BÜNDNIS 90/DIE GRÜNEN": "#169b62",
    "Die Linke": "#b01873",
    "fraktionslos": "#7a8699",
    "Regierung": "#b06b00",
    "Rolle/Amt": "#b06b00",
    "Unbekannt": "#8b949e",
}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def short(value: str | None, limit: int = 150) -> str:
    if not value:
        return ""
    value = " ".join(str(value).split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def page_range_text(item: dict[str, Any]) -> str:
    page_range = item.get("page_range") or {}
    start = page_range.get("start") or {}
    end = page_range.get("end") or {}
    if not start or not end:
        return "no page range"
    start_ref = f"{start.get('page')}{start.get('quadrant') or ''}"
    end_ref = f"{end.get('page')}{end.get('quadrant') or ''}"
    return start_ref if start_ref == end_ref else f"{start_ref}-{end_ref}"


def source_page_text(page: dict[str, Any] | None) -> str:
    if not page:
        return ""
    return f"{page.get('page')}{page.get('quadrant') or ''}"


def speech_anchor(item: dict[str, Any], speech: dict[str, Any], sequence: int) -> str:
    speech_id = speech.get("rede_id")
    if speech_id:
        suffix = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(speech_id)).strip("-")
    else:
        suffix = str(sequence + 1)
    return f"speech-{item.get('index')}-{suffix or sequence + 1}"


def speaker_party(speaker: dict[str, Any] | None) -> str:
    if not speaker:
        return "Unbekannt"
    fraction = speaker.get("fraktion")
    if fraction:
        return str(fraction).replace("\xa0", " ")
    if speaker.get("role") or speaker.get("role_short"):
        return "Regierung"
    return "Unbekannt"


def item_stats(item: dict[str, Any]) -> dict[str, Any]:
    speakers = item.get("xml_speakers") or []
    if not speakers:
        speakers = item.get("xml_speakers_first") or []
    party_counts = Counter(speaker_party(s.get("speaker")) for s in speakers)
    total_chars = sum(int(s.get("char_count") or 0) for s in speakers)
    return {
        "party_counts": party_counts,
        "total_chars": total_chars,
        "speakers": speakers,
        "speech_count": int(item.get("xml_speech_count") or len(speakers)),
    }


def protocol_title(report: dict[str, Any]) -> str:
    protocol = report.get("protocol") or {}
    return f"Bundestag Pulse · {protocol.get('dokumentnummer', 'Plenarprotokoll')}"


def render_badges(items: list[dict[str, Any]], class_name: str = "badge") -> str:
    return "".join(f'<span class="{class_name}">{esc(item)}</span>' for item in items)


def render_party_stack(counter: Counter[str], total: int) -> str:
    if total <= 0:
        return '<div class="stack empty"></div>'
    parts = []
    for party, count in counter.most_common():
        width = max(4, count / total * 100)
        color = PARTY_COLORS.get(party, "#6b7280")
        parts.append(
            f'<span style="width:{width:.2f}%;background:{color}" '
            f'title="{esc(party)}: {count}"></span>'
        )
    return f'<div class="stack">{"".join(parts)}</div>'


def render_source_links(item: dict[str, Any]) -> str:
    links = []
    for doc in item.get("xml_drucksachen") or []:
        url = doc.get("url")
        number = doc.get("dokumentnummer")
        if url:
            links.append(f'<a class="doc-link" href="{esc(url)}">{esc(number)}</a>')
        else:
            links.append(f'<span class="doc-link muted">{esc(number)}</span>')
    if not links:
        return '<span class="muted">No Drucksache in XML</span>'
    return "".join(links)


def render_linked_docs(item: dict[str, Any]) -> str:
    docs = item.get("api", {}).get("linked_drucksachen") or []
    if not docs:
        return '<span class="muted">None linked by API</span>'
    rows = []
    for doc in docs[:8]:
        number = esc(doc.get("dokumentnummer"))
        kind = esc(doc.get("drucksachetyp") or doc.get("vorgangsposition") or "Drucksache")
        date = esc(doc.get("datum") or "")
        origin = ", ".join(doc.get("urheber") or [])
        url = doc.get("url")
        label = f'<a href="{esc(url)}">{number}</a>' if url else number
        rows.append(
            "<li>"
            f"<strong>{label}</strong>"
            f"<span>{kind}</span>"
            f"<span>{date}</span>"
            f"<em>{esc(short(origin, 80))}</em>"
            "</li>"
        )
    overflow = len(docs) - 8
    if overflow > 0:
        rows.append(f'<li class="muted">+ {overflow} more linked documents</li>')
    return f'<ul class="doc-list">{"".join(rows)}</ul>'


def render_positions(item: dict[str, Any]) -> str:
    positions = item.get("api", {}).get("positions") or []
    if not positions:
        return '<span class="status warn">No API position match</span>'
    parts = []
    for position in positions:
        source = position.get("source") or {}
        pdf = source.get("pdf_url")
        title = esc(position.get("titel"))
        kind = esc(position.get("vorgangsposition"))
        vorgang = esc(position.get("vorgang_id"))
        if pdf:
            title_html = f'<a href="{esc(pdf)}">{title}</a>'
        else:
            title_html = title
        mit = position.get("mitberaten") or []
        mit_text = f" · {len(mit)} mitberaten" if mit else ""
        parts.append(f"<li><strong>{kind}</strong><span>{title_html}</span><em>Vorgang {vorgang}{mit_text}</em></li>")
    return f'<ul class="position-list">{"".join(parts)}</ul>'


def render_speakers(item: dict[str, Any], stats: dict[str, Any]) -> str:
    rows = []
    for sequence, speech in enumerate(stats["speakers"]):
        speaker = speech.get("speaker") or {}
        name = esc(speaker.get("display_name") or "Unknown")
        party = speaker_party(speaker)
        color = PARTY_COLORS.get(party, "#6b7280")
        role = speaker.get("role") or speaker.get("role_short") or party
        source = source_page_text(speech.get("source_page"))
        anchor = speech_anchor(item, speech, sequence)
        rows.append(
            '<li class="speaker-row">'
            f'<span class="party-dot" style="background:{color}"></span>'
            f'<strong><a class="speaker-link" href="#{esc(anchor)}">{name}</a></strong>'
            f'<span>{esc(role)}</span>'
            f'<em>{esc(source)}</em>'
            "</li>"
        )
    return f'<ul class="speaker-list">{"".join(rows)}</ul>'


def render_speech_details(item: dict[str, Any], stats: dict[str, Any]) -> str:
    cards = []
    for sequence, speech in enumerate(stats["speakers"]):
        speaker = speech.get("speaker") or {}
        name = esc(speaker.get("display_name") or "Unknown")
        party = speaker_party(speaker)
        color = PARTY_COLORS.get(party, "#6b7280")
        role = speaker.get("role") or speaker.get("role_short") or party
        source = source_page_text(speech.get("source_page"))
        paragraphs = speech.get("paragraphs") or []
        if not paragraphs and speech.get("text"):
            paragraphs = [speech.get("text")]
        if not paragraphs and speech.get("snippet"):
            paragraphs = [speech.get("snippet")]
        paragraph_html = "".join(f"<p>{esc(paragraph)}</p>" for paragraph in paragraphs)
        if not paragraph_html:
            paragraph_html = '<p class="muted">No speech text was included in this report. Rebuild the JSON with the current validator to render this speech inline.</p>'
        meta = " · ".join(part for part in [esc(role), f"page {esc(source)}" if source else ""] if part)
        cards.append(
            f"""
            <details class="speech-card" id="{esc(speech_anchor(item, speech, sequence))}">
              <summary>
                <span class="party-dot" style="background:{color}"></span>
                <strong>{name}</strong>
                <em>{meta}</em>
              </summary>
              <div class="speech-text">
                {paragraph_html}
              </div>
            </details>
            """
        )
    if not cards:
        return '<span class="muted">No speeches in XML</span>'
    return f'<div class="speech-cards">{"".join(cards)}</div>'


def render_html(report: dict[str, Any], overview_href: str | None = None) -> str:
    protocol = report.get("protocol") or {}
    summary = report.get("validation_summary") or {}
    items = report.get("agenda_items") or []
    stats_by_index = {item["index"]: item_stats(item) for item in items}
    max_speeches = max((stats["speech_count"] for stats in stats_by_index.values()), default=1)
    max_chars = max((stats["total_chars"] for stats in stats_by_index.values()), default=1)

    attention_rows = []
    for item in sorted(items, key=lambda x: stats_by_index[x["index"]]["speech_count"], reverse=True):
        stats = stats_by_index[item["index"]]
        speech_width = stats["speech_count"] / max_speeches * 100
        char_width = stats["total_chars"] / max_chars * 100
        attention_rows.append(
            '<a class="attention-row" href="#top-{index}">'
            '<span class="row-top">{top}</span>'
            '<span class="row-title">{title}</span>'
            '<span class="mini-bars"><i style="width:{speech_width:.2f}%"></i><b style="width:{char_width:.2f}%"></b></span>'
            '<span class="row-metric">{speeches} speeches</span>'
            "</a>".format(
                index=item["index"],
                top=esc(item.get("top_id")),
                title=esc(short(item.get("heading"), 78)),
                speech_width=speech_width,
                char_width=char_width,
                speeches=stats["speech_count"],
            )
        )

    top_sections = []
    for item in items:
        stats = stats_by_index[item["index"]]
        party_total = sum(stats["party_counts"].values())
        party_labels = [
            f"{party} {count}"
            for party, count in stats["party_counts"].most_common()
        ]
        xml_docs = [doc.get("dokumentnummer") for doc in item.get("xml_drucksachen") or [] if doc.get("dokumentnummer")]
        api_positions_count = len(item.get("api", {}).get("positions") or [])
        linked_docs_count = len(item.get("api", {}).get("linked_drucksachen") or [])
        source_url = None
        positions = item.get("api", {}).get("positions") or []
        if positions:
            source_url = (positions[0].get("source") or {}).get("pdf_url")
        top_sections.append(
            f"""
            <article class="top-card" id="top-{item['index']}">
              <div class="top-head">
                <div>
                  <span class="eyebrow">{esc(item.get('top_id'))} · {esc(page_range_text(item))}</span>
                  <h2>{esc(item.get('heading'))}</h2>
                </div>
                <div class="score">
                  <strong>{stats['speech_count']}</strong>
                  <span>speeches</span>
                </div>
              </div>
              <div class="top-bars">
                <div>
                  <label>Speech share</label>
                  <div class="bar"><span style="width:{stats['speech_count'] / max_speeches * 100:.2f}%"></span></div>
                </div>
                <div>
                  <label>Text volume</label>
                  <div class="bar alt"><span style="width:{stats['total_chars'] / max_chars * 100:.2f}%"></span></div>
                </div>
              </div>
              <div class="party-block">
                {render_party_stack(stats['party_counts'], party_total)}
                <div class="party-labels">{render_badges(party_labels)}</div>
              </div>
              <div class="source-strip">
                <div><span>XML Drucksachen</span>{render_source_links(item)}</div>
                <div><span>API enrichment</span>{api_positions_count} positions · {item.get('api', {}).get('activities_count', 0)} activities · {linked_docs_count} linked docs</div>
                <div><span>Transcript</span>{f'<a href="{esc(source_url)}">PDF source</a>' if source_url else '<span class="muted">No direct PDF anchor</span>'}</div>
              </div>
              <div class="detail-grid">
                <section>
                  <h3>Speakers</h3>
                  {render_speakers(item, stats)}
                </section>
                <section>
                  <h3>API Positions</h3>
                  {render_positions(item)}
                </section>
                <section>
                  <h3>Linked Documents</h3>
                  {render_linked_docs(item)}
                </section>
              </div>
              <section class="speech-section">
                <h3>Speeches</h3>
                {render_speech_details(item, stats)}
              </section>
            </article>
            """
        )

    warnings = report.get("warnings") or []
    warning_html = ""
    if warnings:
        warning_html = '<div class="notice">' + " ".join(esc(w) for w in warnings) + "</div>"
    overview_link = ""
    if overview_href:
        overview_link = f'<a class="overview-link" href="{esc(overview_href)}">All Sitzungen</a>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(protocol_title(report))}</title>
  <style>
    :root {{
      --ink:#171a1f;
      --muted:#606a78;
      --line:#d9dee6;
      --paper:#f7f8fa;
      --panel:#ffffff;
      --teal:#0f766e;
      --blue:#2458a6;
      --amber:#b06b00;
      --red:#b91c1c;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color:var(--ink);
      background:var(--paper);
      letter-spacing:0;
    }}
    a {{ color:#174ea6; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .shell {{ max-width:1440px; margin:0 auto; padding:24px; }}
    header {{
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:24px;
      align-items:end;
      padding:10px 0 22px;
      border-bottom:1px solid var(--line);
    }}
    .overview-link {{
      display:inline-flex;
      align-items:center;
      min-height:30px;
      margin-bottom:10px;
      padding:4px 9px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      color:#174ea6;
      font-size:13px;
      font-weight:650;
    }}
    h1 {{ margin:0; font-size:34px; line-height:1.1; font-weight:760; }}
    .subtitle {{ margin:8px 0 0; color:var(--muted); font-size:15px; }}
    .meta-grid {{
      display:grid;
      grid-template-columns:repeat(4, minmax(112px, 1fr));
      gap:10px;
    }}
    .metric {{
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:8px;
      padding:10px 12px;
      min-height:62px;
    }}
    .metric span {{ display:block; color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
    .metric strong {{ display:block; margin-top:4px; font-size:22px; }}
    .layout {{
      display:grid;
      grid-template-columns:340px minmax(0,1fr);
      gap:18px;
      margin-top:18px;
      align-items:start;
    }}
    aside {{
      position:sticky;
      top:14px;
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:8px;
      overflow:hidden;
    }}
    aside h2 {{ margin:0; padding:14px 16px; font-size:15px; border-bottom:1px solid var(--line); }}
    .attention-row {{
      display:grid;
      gap:5px;
      padding:12px 16px;
      border-bottom:1px solid #edf0f4;
      color:var(--ink);
    }}
    .attention-row:last-child {{ border-bottom:0; }}
    .row-top, .eyebrow {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
    .row-title {{ font-weight:650; line-height:1.25; }}
    .row-metric {{ color:var(--muted); font-size:12px; }}
    .mini-bars {{ display:grid; gap:3px; height:9px; }}
    .mini-bars i, .mini-bars b {{ display:block; height:3px; border-radius:999px; }}
    .mini-bars i {{ background:var(--teal); }}
    .mini-bars b {{ background:var(--amber); }}
    main {{ display:grid; gap:16px; }}
    .notice {{
      padding:12px 14px;
      border:1px solid #e3c46a;
      background:#fff7d6;
      border-radius:8px;
      color:#614a00;
      font-size:14px;
    }}
    .top-card {{
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:8px;
      padding:18px;
    }}
    .top-head {{
      display:grid;
      grid-template-columns:minmax(0,1fr) 96px;
      gap:18px;
      align-items:start;
    }}
    h2 {{ margin:5px 0 0; font-size:21px; line-height:1.25; }}
    h3 {{ margin:0 0 10px; font-size:13px; text-transform:uppercase; color:var(--muted); letter-spacing:.04em; }}
    .score {{
      text-align:right;
      border-left:1px solid var(--line);
      padding-left:16px;
    }}
    .score strong {{ display:block; font-size:34px; line-height:1; }}
    .score span {{ color:var(--muted); font-size:12px; }}
    .top-bars {{
      display:grid;
      grid-template-columns:1fr 1fr;
      gap:16px;
      margin-top:16px;
    }}
    label {{ display:block; color:var(--muted); font-size:12px; margin-bottom:6px; }}
    .bar {{ height:11px; background:#edf0f4; border-radius:999px; overflow:hidden; }}
    .bar span {{ display:block; height:100%; background:var(--teal); border-radius:999px; }}
    .bar.alt span {{ background:var(--amber); }}
    .party-block {{ margin-top:14px; }}
    .stack {{ display:flex; overflow:hidden; height:14px; background:#edf0f4; border-radius:999px; }}
    .stack span {{ min-width:3px; }}
    .party-labels {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }}
    .badge {{
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
    }}
    .source-strip {{
      display:grid;
      grid-template-columns:1.1fr 1fr .8fr;
      gap:12px;
      margin-top:16px;
      padding:12px;
      background:#f5f7f9;
      border:1px solid #e3e8ef;
      border-radius:8px;
      font-size:13px;
    }}
    .source-strip > div {{ min-width:0; }}
    .source-strip span:first-child {{
      display:block;
      margin-bottom:6px;
      color:var(--muted);
      font-size:11px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .doc-link {{
      display:inline-block;
      margin:0 6px 6px 0;
      padding:3px 7px;
      border:1px solid #cfd7e3;
      border-radius:6px;
      background:white;
      font-weight:650;
    }}
    .detail-grid {{
      display:grid;
      grid-template-columns:1.05fr 1fr 1.2fr;
      gap:18px;
      margin-top:18px;
      align-items:start;
    }}
    ul {{ list-style:none; margin:0; padding:0; }}
    .speaker-list, .position-list, .doc-list {{
      display:grid;
      gap:7px;
      font-size:13px;
    }}
    .speaker-row {{
      display:grid;
      grid-template-columns:10px minmax(96px, .85fr) minmax(110px, 1fr) 44px;
      gap:8px;
      align-items:center;
      min-height:24px;
    }}
    .party-dot {{ width:8px; height:8px; border-radius:50%; }}
    .speaker-row strong, .position-list strong, .doc-list strong {{ font-weight:680; }}
    .speaker-row span, .position-list span, .doc-list span {{ color:#3c4654; min-width:0; overflow-wrap:anywhere; }}
    .speaker-row em, .position-list em, .doc-list em {{ color:var(--muted); font-style:normal; overflow-wrap:anywhere; }}
    .speaker-link {{ color:var(--ink); text-decoration:none; }}
    .speaker-link:hover {{ color:#174ea6; text-decoration:underline; }}
    .position-list li, .doc-list li {{
      display:grid;
      grid-template-columns:minmax(78px,.45fr) minmax(0,1fr) minmax(54px,.35fr) minmax(0,.8fr);
      gap:8px;
      padding-bottom:7px;
      border-bottom:1px solid #eef1f5;
    }}
    .position-list li {{ grid-template-columns:minmax(88px,.5fr) minmax(0,1.5fr) minmax(90px,.7fr); }}
    .position-list li:last-child, .doc-list li:last-child {{ border-bottom:0; }}
    .speech-section {{
      margin-top:18px;
      padding-top:16px;
      border-top:1px solid #eef1f5;
    }}
    .speech-cards {{
      display:grid;
      gap:8px;
    }}
    .speech-card {{
      border:1px solid #e1e6ee;
      border-radius:8px;
      background:#fbfcfd;
      scroll-margin-top:16px;
    }}
    .speech-card[open] {{
      background:#fff;
      border-color:#c8d7eb;
      box-shadow:0 1px 0 rgba(23, 26, 31, .04);
    }}
    .speech-card summary {{
      display:grid;
      grid-template-columns:10px minmax(120px, .5fr) minmax(0,1fr);
      gap:8px;
      align-items:center;
      min-height:36px;
      padding:7px 10px;
      cursor:pointer;
      font-size:13px;
      list-style:none;
    }}
    .speech-card summary::-webkit-details-marker {{ display:none; }}
    .speech-card summary em {{
      color:var(--muted);
      font-style:normal;
      overflow-wrap:anywhere;
    }}
    .speech-text {{
      padding:0 14px 12px 28px;
      font-size:14px;
      line-height:1.55;
      color:#252b33;
    }}
    .speech-text p {{
      margin:10px 0 0;
    }}
    .muted {{ color:var(--muted); }}
    .status.warn {{ color:var(--red); }}
    footer {{ padding:22px 0 4px; color:var(--muted); font-size:12px; }}
    @media (max-width: 1120px) {{
      .layout {{ grid-template-columns:1fr; }}
      aside {{ position:static; }}
      .detail-grid {{ grid-template-columns:1fr; }}
      .source-strip {{ grid-template-columns:1fr; }}
    }}
    @media (max-width: 720px) {{
      .shell {{ padding:14px; }}
      header, .top-head {{ grid-template-columns:1fr; }}
      .meta-grid {{ grid-template-columns:1fr 1fr; }}
      h1 {{ font-size:27px; }}
      h2 {{ font-size:18px; }}
      .score {{ text-align:left; border-left:0; padding-left:0; }}
      .top-bars {{ grid-template-columns:1fr; }}
      .speaker-row {{ grid-template-columns:10px minmax(0,1fr) 48px; }}
      .speaker-row span:nth-of-type(2) {{ display:none; }}
      .speech-card summary {{ grid-template-columns:10px minmax(0,1fr); }}
      .speech-card summary em {{ grid-column:2; }}
      .speech-text {{ padding-left:14px; }}
      .position-list li, .doc-list li {{ grid-template-columns:1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        {overview_link}
        <h1>Bundestag Pulse</h1>
        <p class="subtitle">{esc(protocol.get('titel'))} · sitting {esc(protocol.get('datum'))} · distributed {esc(protocol.get('verteildatum'))}</p>
      </div>
      <div class="meta-grid">
        <div class="metric"><span>Agenda Items</span><strong>{esc(summary.get('xml_top_count'))}</strong></div>
        <div class="metric"><span>Speeches</span><strong>{esc(summary.get('xml_speech_count'))}</strong></div>
        <div class="metric"><span>Drucksachen</span><strong>{esc(summary.get('xml_drucksache_count'))}</strong></div>
        <div class="metric"><span>People IDs</span><strong>{esc(summary.get('unique_person_ids'))}</strong></div>
      </div>
    </header>
    <div class="layout">
      <aside>
        <h2>Attention Ranking</h2>
        {''.join(attention_rows)}
      </aside>
      <main>
        {warning_html}
        {''.join(top_sections)}
      </main>
    </div>
    <footer>
      XML transcript is treated as canonical; DIP API records enrich proceedings, activities, people, and linked documents.
    </footer>
  </div>
  <script>
    (() => {{
      const openHashTarget = () => {{
        const id = decodeURIComponent(window.location.hash.slice(1));
        if (!id) return;
        const target = document.getElementById(id);
        if (!target) return;
        const details = target.tagName.toLowerCase() === "details" ? target : target.closest("details");
        if (details) {{
          details.open = true;
          details.scrollIntoView({{ block: "start" }});
        }}
      }};
      window.addEventListener("hashchange", openHashTarget);
      openHashTarget();
    }})();
  </script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Validation JSON produced by validate_dip_protocol.py")
    parser.add_argument("output", type=Path, help="Standalone HTML output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(report), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
