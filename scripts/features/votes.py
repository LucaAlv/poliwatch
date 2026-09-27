"""Namentliche-Abstimmungen component hooks and dossier rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import render_dip_pulse_html as html
from validate_dip_protocol import stored_vote_result

from . import BaseComponent, REGISTRY


RESULT_BADGE_LABELS = {"accepted": "Angenommen", "rejected": "Abgelehnt"}
# Only bundestag.de's own Beschluss wording is official; anything else is our
# yes>no rule, which misreads Beschlussempfehlungen and qualified-majority votes,
# so the reader sees which one a badge is.
RESULT_SOURCE_NOTES = {
    "official": "Laut Beschluss auf bundestag.de",
    "derived": "Aus den Stimmenzahlen berechnet (Ja gegen Nein), kein amtliches Ergebnis gefunden",
}


def result_badge_label(result_raw: Any) -> str | None:
    return RESULT_BADGE_LABELS.get(str(result_raw or ""))


def render_result_badge(vote: dict[str, Any]) -> str:
    """The Angenommen/Abgelehnt pill for the dossier panel and the votes
    archive; votes cached before the badge shipped fall back to the derived rule.
    """
    result_raw, result_source = stored_vote_result(vote)
    label = result_badge_label(result_raw)
    if not label:
        return ""
    if result_source == "official":
        return (
            f'<span class="vote-result vote-result-{html.esc(result_raw)}"'
            f' title="{html.esc(RESULT_SOURCE_NOTES["official"])}">{html.esc(label)}</span>'
        )
    return (
        f'<span class="vote-result vote-result-{html.esc(result_raw)} vote-result-derived"'
        f' title="{html.esc(RESULT_SOURCE_NOTES["derived"])}">{html.esc(label)}'
        ' <span class="vote-result-note">(berechnet)</span></span>'
    )


def document_source_links(item: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """Map a Drucksache number to (url, source) using the same XML/DIP objects
    ``validate_dip_protocol.top_document_numbers`` already matched this vote
    against, so a vote's ``document_numbers`` never need a second URL builder.
    The XML protocol is authoritative (footer: "Das XML-Protokoll ist
    maßgeblich") and wins over the DIP API when both name a URL for the number.
    """
    links: dict[str, tuple[str, str]] = {}
    for doc in (item.get("api") or {}).get("linked_drucksachen") or []:
        number = doc.get("dokumentnummer")
        url = doc.get("url")
        if number and url:
            links.setdefault(str(number), (url, "bundestag-dip"))
    for doc in item.get("xml_drucksachen") or []:
        number = doc.get("dokumentnummer")
        url = doc.get("url")
        if number and url:
            links[str(number)] = (url, "bundestag-xml")
    return links


def render_document_links(document_numbers: list[str], links: dict[str, tuple[str, str]]) -> str:
    parts = []
    for number in document_numbers:
        link = links.get(str(number))
        href = None
        if link:
            url, source = link
            try:
                href = html.source_url(url, source)
            except (html.publication.PublicationStateError, ValueError):
                # An off-allowlist URL from DIP/XML loses its link, never the build.
                href = None
        if href:
            parts.append(f'<a class="doc-link" href="{html.esc(href)}">{html.esc(number)}</a>')
        else:
            parts.append(f'<span class="doc-link muted">{html.esc(number)}</span>')
    if not parts:
        return ""
    return f'<span class="doc-link-list">{"".join(parts)}</span>'



def render_vote_summary(item: dict[str, Any], acquisition: dict[str, Any] | None = None) -> str:
    votes = item.get("votes") or ([item["vote"]] if item.get("vote") else [])
    acquisition_state = str((acquisition or {}).get("acquisition_state") or "complete")
    status_copy = {
        "not_requested": "Hinweis: Abstimmungsdaten wurden für diese Veröffentlichung nicht abgerufen.",
        "partial": "Teilweise verfügbar: Abstimmungsdaten sind unvollständig. Bitte prüfen Sie die Originalquelle.",
        "failed": "Nicht verfügbar: Abstimmungsdaten konnten nicht abgerufen werden.",
    }
    if not votes:
        message = status_copy.get(
            acquisition_state,
            "Zu diesem TOP ist keine namentliche Abstimmung verzeichnet.",
        )
        source_action = (
            ' <a href="https://www.bundestag.de/parlament/plenum/abstimmung">Beim Bundestag prüfen</a>.'
            if acquisition_state in {"partial", "failed"}
            else ""
        )
        return (
            f'<section class="vote-panel {html.esc(acquisition_state)}">'
            "<h3>Namentliche Abstimmungen</h3>"
            f"<p>{html.esc(message)}{source_action}</p></section>"
        )
    panels = []
    if acquisition_state == "partial":
        panels.append(
            '<aside class="vote-state-note">'
            f'<p>{html.esc(status_copy["partial"])}</p>'
            '</aside>'
        )
    for vote in votes:
        fraction_rows = []
        for fraction in vote.get("fractions") or []:
            name = fraction.get("name") or "Unbekannt"
            counts = fraction.get("counts") or {}
            leading = fraction.get("leading_vote") or "absent"
            color = html.PARTY_COLORS.get(name, "#6b7280")
            fraction_rows.append(
                '<div class="vote-fraction-row">'
                f'<span class="party-dot" style="background:{color}"></span>'
                f'<strong>{html.esc(name)}</strong>'
                f'{html.render_vote_stack(counts, int(fraction.get("total") or 0))}'
                f'<em class="vote-pill vote-{html.esc(leading)}">{html.esc(html.VOTE_LABELS.get(leading, leading))}</em>'
                "</div>"
            )
        member_groups: dict[str, list[dict[str, Any]]] = {}
        for member in vote.get("members") or []:
            member_groups.setdefault(str(member.get("faction") or "Unbekannt"), []).append(member)
        member_sections = []
        for faction in sorted(member_groups, key=lambda value: (value == "fraktionslos", value)):
            rows = []
            for member in sorted(member_groups[faction], key=lambda value: str(value.get("name") or "")):
                vote_key = str(member.get("vote") or "")
                name = html.esc(member.get("name"))
                url = member.get("profile_url")
                name_html = (
                    f'<a href="{html.esc(html.source_url(url, "public-profile"))}">{name}</a>'
                    if url
                    else name
                )
                rows.append(
                    '<li class="member-vote-row">'
                    f"<strong>{name_html}</strong>"
                    f'<span class="vote-pill vote-{html.esc(vote_key)}">{html.esc(html.VOTE_LABELS.get(vote_key, vote_key))}</span>'
                    "</li>"
                )
            member_sections.append(
                '<section class="member-vote-group">'
                f"<h4>{html.esc(faction)}</h4>"
                f'<ul class="member-vote-list">{"".join(rows)}</ul>'
                "</section>"
            )
        total = vote.get("total") or {}
        document_links = document_source_links(item)
        docs_html = render_document_links(vote.get("document_numbers") or [], document_links)
        docs_text = f" · Drucksachen {docs_html}" if docs_html else ""
        xlsx_url = vote.get("xlsx_url")
        xlsx_text = (
            f' · <a href="{html.esc(html.source_url(xlsx_url, "bundestag-roll-call"))}">Abstimmungsliste (XLSX)</a>'
            if xlsx_url
            else ""
        )
        detail_url = html.source_url(vote.get("detail_url"), "bundestag-roll-call")
        result_badge = render_result_badge(vote)
        panels.append(
            '<section class="vote-panel">'
            f'<div class="vote-head"><div><h3>Namentliche Abstimmung{result_badge}</h3>'
            f'<p><a href="{html.esc(detail_url)}">{html.esc(html.short(vote.get("title"), 140))}</a>{docs_text}{xlsx_text}</p>'
            "</div>"
            f'<div class="vote-total">{html.render_vote_stack(total)}{html.render_vote_pills(total)}</div></div>'
            f'<div class="vote-fractions">{"".join(fraction_rows)}</div>'
            '<details class="member-votes">'
            f'<summary>Einzelstimmen ({html.esc(len(vote.get("members") or []))} Abgeordnete)</summary>'
            f'<div class="member-vote-grid">{"".join(member_sections)}</div>'
            "</details></section>"
        )
    return "".join(panels)


class VotesComponent(BaseComponent):
    def persist(self, conn: Any, report: dict[str, Any], ctx: dict[str, Any]) -> None:
        callback = ctx.get("persist_votes")
        if callback:
            callback(conn, report, ctx)

    def dossier_sections(self, report: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
        acquisition = (report.get("acquisition") or {}).get("votes") or {}
        return [render_vote_summary(ctx["item"], acquisition)]

    def write_pages(self, output_dir: Path, ctx: dict[str, Any]) -> dict[str, Any]:
        selection = ctx.get("selection")
        if selection is not None and not selection.enabled("votes"):
            return {}
        rows = ctx["collect_votes_archive"](ctx["entries"])
        return ctx["write_votes_archive_page"](output_dir, rows, selection)


COMPONENT = VotesComponent(REGISTRY["votes"])
