"""Namentliche-Abstimmungen component hooks and dossier rendering."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import derive
import dip_text
import politikfelder
import render_dip_pulse_html as html

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
    archive; a vote with no recorded result renders no badge.
    """
    result_raw, result_source = derive.vote_outcome(vote), vote.get("result_source")
    label = result_badge_label(result_raw)
    if not label:
        reason = ("Zweidrittelmehrheit der Mitglieder erforderlich (Art. 79 Abs. 2 GG); kein amtliches Ergebnis gefunden"
                  if vote.get("procedure_type") == "constitutional_amendment"
                  else "Mehrheit der Mitglieder erforderlich; kein amtliches Ergebnis gefunden"
                  if vote.get("procedure_type") else "Kein Ergebnis verfügbar")
        return f'<span class="vote-no-result">{html.esc(reason)}</span>'
    if vote.get("inverted"):
        label = "Antrag: " + label
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


@dataclass(frozen=True)
class VotePanelContext:
    """What every vote panel of one dossier page reads besides the TOP itself.

    ``report`` is the sitting the TOP belongs to: the committee line looks a
    vote's Drucksachen up across all its TOPs (``derive.vote_committees``), and
    a vote's anchor goes where ``derive.iter_report_votes`` first meets it.
    ``vote_contexts`` is ``politikfelder.report_vote_vorgaenge`` of the report,
    read with ``vorgang_cache``, the same answer persist stores."""

    report: Mapping[str, Any]
    vote_contexts: Mapping[str, politikfelder.VoteContext]
    vorgang_cache: Mapping[str, Any]
    mp_lookup: dict[str, str] | None
    mp_prefix: str


def member_name_html(vote: dict[str, Any], member: dict[str, Any], panel: VotePanelContext) -> str:
    """A roll-call member's escaped name, linked to their Personenseite when the
    occurrence resolves to one, else to their public profile when that URL is
    allowed, else plain."""
    name = html.esc(member.get("name"))
    occurrence_id = derive.vote_member_key(vote.get("id"), member)
    href = html.mp_page_href({**member, "occurrence_id": occurrence_id}, panel.mp_lookup, panel.mp_prefix)
    profile_url = derive.member_profile_url(member)
    if not href and profile_url:
        try:
            href = html.source_url(profile_url, "public-profile")
        except (html.publication.PublicationStateError, ValueError):
            href = None
    return f'<a href="{html.esc(href)}">{name}</a>' if href else name


ABWEICHLER_HEADING = "Anders als die Mehrheit der eigenen Fraktion oder Gruppe"
# Public text says what an Abweichler does, never the term (CONTEXT.md, Abweichler).
ABWEICHLER_GAP = "Einzelstimmen unvollständig – nicht ermittelbar, wer anders als die Mehrheit der eigenen Fraktion oder Gruppe stimmt"
# Spells out the CONTEXT.md rule: a Ja beside an Enthaltung majority or a tie is no Abweichung.
ABWEICHLER_NONE = (
    "Niemand stimmt anders als die Mehrheit der eigenen Fraktion oder Gruppe"
    " (gezählt: Ja gegen eine Nein-Mehrheit oder Nein gegen eine Ja-Mehrheit)"
)
#: Names shown before the rest of a group's Abweichler fold away (D6).
ABWEICHLER_INLINE = 10
ABWEICHLER_GAP_HTML = f'<p class="vote-state-note vote-abweichler-gap">{html.esc(ABWEICHLER_GAP)}</p>'


def render_abweichler(vote: dict[str, Any], members: list[dict[str, Any]], panel: VotePanelContext) -> str:
    """The line under a group's tally row naming its Abweichler: the first ten
    inline, the rest behind a native <details>."""
    items = [f"<li>{member_name_html(vote, member, panel)}</li>" for member in members]
    inline, rest = items[:ABWEICHLER_INLINE], items[ABWEICHLER_INLINE:]
    more = (
        f'<details class="vote-abweichler-more"><summary>alle {len(items)} anzeigen</summary>'
        f'<ul class="vote-abweichler-list">{"".join(rest)}</ul></details>'
        if rest
        else ""
    )
    return (
        '<div class="vote-abweichler">'
        f'<span class="vote-abweichler-label">{html.esc(ABWEICHLER_HEADING)} ({len(items)}):</span>'
        f'<ul class="vote-abweichler-list">{"".join(inline)}</ul>{more}'
        "</div>"
    )


def render_committee_line(committees: list[dict[str, Any]], links: dict[str, tuple[str, str]]) -> str:
    """One citation per Beschlussempfehlung among the vote's Drucksachen,
    "Beschlussempfehlung des <Ausschuss> (Drucksache <link>)". It cites the
    document and claims no role for this vote (D14), so it stays true for a
    vote on an Entschließungsantrag that lists the law's Beschlussempfehlung.
    """
    if not committees:
        return '<p class="vote-committee muted">Ausschuss nicht ermittelt</p>'
    # The Drucksache link comes from the sitting-wide match, then from ``links``,
    # this TOP's own sources, which win as they do for the vote's document list.
    links = {**{row["number"]: (row["url"], "bundestag-dip") for row in committees if row.get("url")}, **links}
    lines = []
    for row in committees:
        genitives = [dip_text.committee_genitive(name) for name in row["urheber"]]
        if all(genitives):
            who = "Beschlussempfehlung " + dip_text.join_with_und(genitives)
        else:
            who = "Beschlussempfehlung, Urheber: " + dip_text.join_with_und(row["urheber"])
        lines.append(f"{html.esc(who)} (Drucksache {render_document_links([row['number']], links)})")
    return f'<p class="vote-committee">{"<br>".join(lines)}</p>'


CONTEXT_HEADING = "Worum es geht"
CONTEXT_SOURCE = "Quelle: Deutscher Bundestag/Bundesrat – DIP"
CONTEXT_NONE = "Keine Beschreibung in DIP"
CONTEXT_NO_VORGANG = "Kein einzelner DIP-Vorgang ermittelt"
CONTEXT_NOT_FETCHED = "Vorgang nicht abgerufen"


def dip_vorgang_url(vorgang_id: str) -> str:
    """DIP's page of a Vorgang; the slug before the id is free text DIP ignores."""
    return f"https://dip.bundestag.de/vorgang/-/{vorgang_id}"


def _vorgang_label(vorgang_id: str, record: Mapping[str, Any] | None) -> str:
    """"<titel> · DIP"; "DIP-Vorgang <id>" where there is no titel to show, a
    record not fetched yet or (none on the reference cache) an empty one from DIP."""
    titel = " ".join(str((record or {}).get("titel") or "").split())
    return f"{titel} · DIP" if titel else f"DIP-Vorgang {vorgang_id}"


def render_vote_context(vorgang_ids: list[str], state: politikfelder.ContextState, cache: Mapping[str, Any] | None) -> str:
    """The "Worum es geht" block: one DIP abstract per Vorgang the vote is about
    (``politikfelder.vote_vorgang_ids``). It describes the Vorhaben, not the vote's
    result, which stays in the badge. "Keine Beschreibung in DIP" only where DIP was
    asked and has none; "Vorgang nicht abgerufen" where the cache lacks the answer,
    also after the known blocks of a partial ``not_fetched`` answer; "Kein einzelner
    DIP-Vorgang ermittelt" for ``none``, which also covers Drucksachen that name a
    bundle of Vorgänge DIP does describe."""
    records = (cache or {}).get("vorgaenge") or {}
    blocks = []
    if not vorgang_ids:
        gap = CONTEXT_NOT_FETCHED if state == "not_fetched" else CONTEXT_NO_VORGANG
        blocks.append(f'<p class="vote-context-gap">{html.esc(gap)}</p>')
    for vorgang_id in vorgang_ids:
        record = records.get(vorgang_id)
        label = html.esc(_vorgang_label(vorgang_id, record))
        try:
            label = f'<a href="{html.esc(html.source_url(dip_vorgang_url(vorgang_id), "bundestag-dip"))}">{label}</a>'
        except (html.publication.PublicationStateError, ValueError):
            pass
        text = dip_text.abstract_text((record or {}).get("abstract"))
        if record is None:
            body = f'<p class="vote-context-gap">{html.esc(CONTEXT_NOT_FETCHED)}</p>'
        elif not text:
            body = f'<p class="vote-context-gap">{html.esc(CONTEXT_NONE)}</p>'
        else:
            teaser, more = dip_text.abstract_teaser(text)
            body = f'<p class="vote-context-teaser">{html.esc(teaser)}</p>'
            if more:
                full = "".join(f"<p>{html.esc(paragraph)}</p>" for paragraph in text.split("\n\n"))
                body += f'<details class="vote-context-more"><summary>Ganze Beschreibung</summary>{full}</details>'
        blocks.append(f'<div class="vote-context-block"><p class="vote-context-label">{label}</p>{body}</div>')
    # A Vorgang without a record already says so in its own block; the note marks
    # what no block shows, a number the cache cannot resolve (D7).
    if vorgang_ids and state == "not_fetched" and all(vorgang_id in records for vorgang_id in vorgang_ids):
        blocks.append(f'<p class="vote-context-gap">{html.esc(CONTEXT_NOT_FETCHED)}</p>')
    return (
        '<div class="vote-context">'
        f'<p class="vote-context-head"><strong>{html.esc(CONTEXT_HEADING)}</strong> · {html.esc(CONTEXT_SOURCE)}</p>'
        f'{"".join(blocks)}</div>'
    )


def vote_anchor_id(vote: Mapping[str, Any]) -> str:
    """The HTML id of a vote's first panel on its dossier page (D9)."""
    return f"vote-{derive.vote_identity(vote)}"


_STATUS_COPY = {
    "not_requested": "Hinweis: Abstimmungsdaten wurden für diese Veröffentlichung nicht abgerufen.",
    "partial": "Teilweise verfügbar: Abstimmungsdaten sind unvollständig. Bitte prüfen Sie die Originalquelle.",
    "failed": "Nicht verfügbar: Abstimmungsdaten konnten nicht abgerufen werden.",
}


def _panel_id(vote: dict[str, Any], item: dict[str, Any], first_item: Mapping[str, Any], anchored: set[str]) -> str:
    """``id="vote-<id>"`` on the panel where ``derive.iter_report_votes`` first
    meets the vote (its TOP, or None for a sitting-level vote, which is only
    ever drawn in the sitting's own section), so a vote under two TOPs has one
    anchor (D9); "" on every other copy."""
    key = derive.vote_identity(vote)
    first = first_item.get(key, item)
    if key in anchored or not (first is item or first is None):
        return ""
    anchored.add(key)
    return f' id="{html.esc(vote_anchor_id(vote))}"'


def _fraction_group_html(
    fraction: dict[str, Any], abweichler: Mapping[str, Any], no_members: bool, panel: VotePanelContext, vote: dict[str, Any]
) -> str:
    """One group's tally row, its Mehrheitsvotum pill, and its Abweichler line or gap note."""
    name = fraction["name"]
    counts = fraction["counts"]
    # From the counts, never the report's cached leading_vote: a stale
    # report must not show a Mehrheitsvotum the store does not hold.
    leading = derive.majority_vote(counts)
    color = html.PARTY_COLORS.get(name, "#6b7280")
    # No Mehrheitsvotum (a tie, or nobody voted) is no pill, not a
    # "nicht abgegeben" one. An inverted vote names a tie ("geteilt"),
    # which gets its own colour.
    position = (derive.fraction_position(counts, True) if vote.get("inverted") else html.VOTE_LABELS.get(leading))
    pill = (
        f'<em class="vote-pill vote-{html.esc(leading or "split")}">{html.esc(position)}</em>'
        if position
        else ""
    )
    group = abweichler.get(name)
    note = ""
    if group and group["members"]:
        note = render_abweichler(vote, group["members"], panel)
    elif group and group["state"] != "complete" and not no_members:
        note = ABWEICHLER_GAP_HTML
    return (
        '<div class="vote-fraction-group">'
        '<div class="vote-fraction-row">'
        f'<span class="party-dot" style="background:{color}"></span>'
        f'<strong>{html.esc(name)}</strong>'
        f'{html.render_vote_stack(counts, fraction["total"])}'
        f"{pill}"
        "</div>"
        f"{note}</div>"
    )


def _abweichler_summary_html(abweichler: Mapping[str, Any], no_members: bool) -> str:
    """The vote-wide line under the groups: one gap note when no group has
    member rows, "Niemand stimmt anders …" when every group is complete and
    has none, else nothing (each short group carries its own note)."""
    if no_members:
        return ABWEICHLER_GAP_HTML
    if abweichler and all(group["state"] == "complete" and not group["members"] for group in abweichler.values()):
        return f'<p class="vote-abweichler-none">{html.esc(ABWEICHLER_NONE)}</p>'
    return ""


def _member_sections_html(vote: dict[str, Any], panel: VotePanelContext) -> str:
    """The Einzelstimmen grid, one section per group, fraktionslos last."""
    member_groups: dict[str, list[dict[str, Any]]] = {}
    for member in vote.get("members") or []:
        member_groups.setdefault(str(member.get("faction") or "Unbekannt"), []).append(member)
    member_sections = []
    for faction in sorted(member_groups, key=lambda value: (value == "fraktionslos", value)):
        rows = []
        for member in sorted(member_groups[faction], key=lambda value: str(value.get("name") or "")):
            vote_key = str(member.get("vote") or "")
            name_html = member_name_html(vote, member, panel)
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
    return "".join(member_sections)


def render_vote_summary(item: dict[str, Any], acquisition: dict[str, Any] | None, panel: VotePanelContext) -> str:
    """The vote panels of one TOP (or of a sitting's votes under no TOP)."""
    votes = derive.item_votes(item)
    acquisition_state = str((acquisition or {}).get("acquisition_state") or "complete")
    if not votes:
        message = _STATUS_COPY.get(
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
            f'<p>{html.esc(_STATUS_COPY["partial"])}</p>'
            '</aside>'
        )
    first_item = {derive.vote_identity(vote): first for first, vote in derive.iter_report_votes(panel.report)}
    anchored: set[str] = set()
    document_links = document_source_links(item)
    for vote in votes:
        context = panel.vote_contexts[derive.vote_identity(vote)]
        vote_context_html = render_vote_context(context.vorgang_ids, context.state, panel.vorgang_cache)
        abweichler = derive.vote_abweichler(vote)
        # One gap note for the vote when no group has member rows, else one
        # under each group that is short.
        no_members = bool(abweichler) and all(group["state"] == "no_members" for group in abweichler.values())
        fraction_rows = "".join(
            _fraction_group_html(fraction, abweichler, no_members, panel, vote)
            for fraction in derive.merge_fractions(vote.get("fractions"))
        )
        committee_line = render_committee_line(derive.vote_committees(vote, panel.report), document_links)
        total = vote.get("total") or {}
        docs_html = render_document_links(vote.get("document_numbers") or [], document_links)
        docs_text = f" · Drucksachen {docs_html}" if docs_html else ""
        xlsx_url = vote.get("xlsx_url")
        xlsx_href = None
        if xlsx_url:
            try:
                xlsx_href = html.source_url(xlsx_url, "bundestag-roll-call")
            except (html.publication.PublicationStateError, ValueError):
                # Scraped from a free-form href on a second bundestag.de page,
                # same class of external data as a Drucksache link: an
                # off-allowlist value must not take the vote panel down.
                xlsx_href = None
        xlsx_text = (
            f' · <a href="{html.esc(xlsx_href)}">Abstimmungsliste (XLSX)</a>' if xlsx_href else ""
        )
        detail_url = html.source_url(vote.get("detail_url"), "bundestag-roll-call")
        result_badge = render_result_badge(vote)
        explanation = ""
        if vote.get("inverted"):
            explanation = '<p class="vote-state-note">Abgestimmt wurde über die Empfehlung, den Antrag abzulehnen. Ja = Antrag ablehnen · Nein = Antrag annehmen</p>'

        panels.append(
            f'<section class="vote-panel"{_panel_id(vote, item, first_item, anchored)}>'
            f'<div class="vote-head"><div><h3>Namentliche Abstimmung{result_badge}</h3>'
            f'<p><a href="{html.esc(detail_url)}">{html.esc(html.short(vote.get("title"), 140))}</a>{docs_text}{xlsx_text}</p>'
            "</div>"
            f'<div class="vote-total">{html.render_vote_stack(total)}{html.render_vote_pills(total)}</div></div>'
            f'{vote_context_html}{committee_line}{explanation}<div class="vote-fractions">{fraction_rows}</div>'
            f'{_abweichler_summary_html(abweichler, no_members)}'
            '<details class="member-votes">'
            f'<summary>Einzelstimmen ({html.esc(len(vote.get("members") or []))} Abgeordnete)</summary>'
            f'<div class="member-vote-grid">{_member_sections_html(vote, panel)}</div>'
            "</details></section>"
        )
    return "".join(panels)


class VotesComponent(BaseComponent):
    def dossier_sections(self, report: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
        acquisition = (report.get("acquisition") or {}).get("votes") or {}
        panel = VotePanelContext(
            report=report,
            vote_contexts=ctx["vote_contexts"],
            vorgang_cache=ctx["vorgang_cache"],
            mp_lookup=ctx.get("mp_lookup"),
            mp_prefix=ctx.get("mp_prefix", "../abgeordnete/"),
        )
        return [render_vote_summary(ctx["item"], acquisition, panel)]

    def write_pages(self, output_dir: Path, ctx: dict[str, Any]) -> dict[str, Any]:
        selection = ctx.get("selection")
        if selection is not None and not selection.enabled("votes"):
            return {}
        rows = ctx["collect_votes_archive"](ctx["entries"], ctx.get("vorgang_cache"))
        return ctx["write_votes_archive_page"](output_dir, rows, selection)


COMPONENT = VotesComponent(REGISTRY["votes"])
