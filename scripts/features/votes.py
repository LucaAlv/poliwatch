"""Namentliche-Abstimmungen component hooks and dossier rendering."""

from __future__ import annotations

from typing import Any

import render_dip_pulse_html as html

from . import BaseComponent, REGISTRY


def render_vote_summary(item: dict[str, Any]) -> str:
    votes = item.get("votes") or ([item["vote"]] if item.get("vote") else [])
    if not votes:
        return ""
    panels = []
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
                name_html = f'<a href="{html.esc(url)}">{name}</a>' if url else name
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
        docs = ", ".join(vote.get("document_numbers") or [])
        docs_text = f" · Drucksachen {html.esc(docs)}" if docs else ""
        panels.append(
            '<section class="vote-panel" data-feature="votes">'
            '<div class="vote-head"><div><h3>Namentliche Abstimmung</h3>'
            f'<p><a href="{html.esc(vote.get("detail_url"))}">{html.esc(html.short(vote.get("title"), 140))}</a>{docs_text}</p>'
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
        return [render_vote_summary(ctx["item"])]


COMPONENT = VotesComponent(REGISTRY["votes"])
