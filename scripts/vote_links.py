"""Which TOPs of a sitting a namentliche Abstimmung is linked to (N10).

One rule, applied online (``validate_dip_protocol.enrich_with_api``), on every
replay (``build_dip_pulse_site.reparse_cached_xml``) and after cached votes are
carried forward into a fresh report, so a cached placement never outlives the
rule. Persist writes the links and their basis to ``agenda_item_votes`` and
refuses a report whose placement disagrees with it.

1. **Drucksache.** A vote links to every TOP of its sitting that shares a
   Drucksache number with the vote's ``document_numbers`` (read from the
   bundestag.de list page). A TOP's numbers are those the protocol XML prints
   under it (``xml_drucksachen``) and those of every DIP Vorgang whose position
   was assigned to it, ``mitberaten`` Vorgänge included
   (``api.linked_drucksachen``). The basis is ``drucksache_xml`` where a shared
   number is printed under the TOP, else ``drucksache_vorgang``.
2. **Title.** A vote that shares no number with any TOP of its sitting links to
   the one TOP whose heading, or one of whose DIP position titles,
   ``title_matches`` the vote's title (basis ``title``).
   With no such TOP, or several, it links to none.

A vote linked to no TOP is a sitting vote (``report["sitting_votes"]``). A link
says the roll call was taken on a Vorlage this TOP dealt with, not that the
vote alone settled the TOP (``docs/data-methods.md``, "Abstimmungen und
Tagesordnungspunkte"; owner decision 1 in docs/plans/vote-links-and-figures.md).
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

import derive

#: Every value ``agenda_item_votes.basis`` takes.
BASES = ("drucksache_xml", "drucksache_vorgang", "title")


def norm_title(value: str | None) -> str:
    value = derive.clean_text(value).lower()
    value = re.sub(r"[^a-zäöüß0-9]+", " ", value)
    return derive.clean_text(value)


def title_matches(heading: str | None, title: str | None) -> bool:
    """Whether a TOP heading or position title and a vote title name the same
    matter: one contains the other, or at least 65% of the vote title's words
    longer than four letters are in the heading."""
    heading_norm = norm_title(heading)
    title_norm = norm_title(title)
    if not heading_norm or not title_norm:
        return False
    if title_norm in heading_norm or heading_norm in title_norm:
        return True
    title_tokens = {token for token in title_norm.split() if len(token) > 4}
    heading_tokens = {token for token in heading_norm.split() if len(token) > 4}
    if not title_tokens:
        return False
    return len(title_tokens & heading_tokens) / len(title_tokens) >= 0.65


def _numbers(documents: Iterable[Mapping[str, Any]] | None) -> set[str]:
    return {str(doc["dokumentnummer"]) for doc in documents or [] if doc.get("dokumentnummer")}


def _position_titles(item: Mapping[str, Any]) -> list[str]:
    """The titles of the DIP positions assigned to the TOP and of the Vorgänge
    beraten with them, as the online run read them."""
    positions = (item.get("api") or {}).get("positions") or []
    titles = [position.get("titel") for position in positions]
    titles += [linked.get("titel") for position in positions for linked in position.get("mitberaten") or []]
    return [str(title) for title in titles if title]


def top_links(items: list[Mapping[str, Any]], votes: Iterable[Mapping[str, Any]]) -> dict[str, dict[int, str]]:
    """vote id (``derive.vote_identity``) -> {position of the TOP in ``items``:
    basis}, empty for a vote linked to no TOP. ``items`` are a report's agenda
    items; ``votes`` need ``id``, ``title`` and ``document_numbers`` (a list
    page candidate or a fetched vote). A vote id given twice is decided by its
    last entry. The result depends on the votes and the TOPs alone, not on
    their order or on where a report placed a vote."""
    printed = [_numbers(derive.xml_drucksachen(item)) for item in items]
    linked = [_numbers((item.get("api") or {}).get("linked_drucksachen")) for item in items]
    titles = [[item.get("heading"), *_position_titles(item)] for item in items]
    result: dict[str, dict[int, str]] = {}
    for vote in votes:
        vote_numbers = {str(number) for number in vote.get("document_numbers") or []}
        matched: dict[int, str] = {}
        for position, (xml_numbers, dip_numbers) in enumerate(zip(printed, linked)):
            if vote_numbers & xml_numbers:
                matched[position] = "drucksache_xml"
            elif vote_numbers & dip_numbers:
                matched[position] = "drucksache_vorgang"
        if not matched:
            titled = [
                position for position, candidates in enumerate(titles)
                if any(title_matches(title, vote.get("title")) for title in candidates)
            ]
            if len(titled) == 1:
                matched[titled[0]] = "title"
        result[derive.vote_identity(vote)] = matched
    return result


def report_votes(report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Every fetched vote of a sitting, one copy per vote id, in order of first
    appearance: under the TOPs, then among the sitting votes, then among the
    matched votes the online run recorded. Keyed by ``derive.vote_identity``."""
    records = report.get("api_records") or {}
    votes: dict[str, dict[str, Any]] = {}
    for vote in [
        *(vote for item in report.get("agenda_items") or [] for vote in derive.item_votes(item)),
        *(report.get("sitting_votes") or []),
        *(records.get("sitting_votes") or []),
        *(records.get("matched_roll_call_votes") or []),
    ]:
        votes.setdefault(derive.vote_identity(vote), vote)
    return votes


def links(report: Mapping[str, Any]) -> dict[str, dict[int, str]]:
    """``top_links`` for every vote of ``report`` (``report_votes``)."""
    return top_links(report.get("agenda_items") or [], report_votes(report).values())


def _vote_order(report: Mapping[str, Any], votes: Mapping[str, Any]) -> list[str]:
    """The vote ids in the order of the bundestag.de list (the order the online
    run attached them in), then the votes the list does not name, as the report
    first holds them (a report carried forward without a scan has no list)."""
    listed = [
        derive.vote_identity(candidate)
        for candidate in (report.get("api_records") or {}).get("roll_call_vote_candidates") or []
        if derive.clean_text(candidate.get("id"))
    ]
    ordered = list(dict.fromkeys(vote_id for vote_id in listed if vote_id in votes))
    named = set(ordered)
    return ordered + [vote_id for vote_id in votes if vote_id not in named]


def attribute_votes(report: dict[str, Any]) -> dict[str, Any]:
    """Place every vote of ``report`` under the TOPs ``links`` gives it and the
    rest in ``report["sitting_votes"]``, each list in ``_vote_order``. A copy
    already in the right place stays as it is, so a replay that keeps a link
    changes nothing; a new place gets the vote's first copy itself (``report_votes``),
    as the online run puts one fetched vote under every TOP it links to. Returns
    ``report``."""
    votes = report_votes(report)
    placed = links(report)
    order = _vote_order(report, votes)
    for position, item in enumerate(report.get("agenda_items") or []):
        existing = {derive.vote_identity(vote): vote for vote in derive.item_votes(item)}
        item["votes"] = [
            existing.get(vote_id) or votes[vote_id]
            for vote_id in order if position in placed[vote_id]
        ]
    existing = {derive.vote_identity(vote): vote for vote in report.get("sitting_votes") or []}
    report["sitting_votes"] = [
        existing.get(vote_id) or votes[vote_id] for vote_id in order if not placed[vote_id]
    ]
    return report


def placement_errors(report: Mapping[str, Any]) -> list[str]:
    """Where ``report`` places a vote other than ``links`` does: a vote under a
    TOP the rule does not link it to, or missing under one it does. Empty for a
    report ``attribute_votes`` placed. Also a vote the rule links to no TOP that
    ``report["sitting_votes"]`` lacks, which persist would drop. Persist refuses
    a report with any."""
    placed = links(report)
    errors = []
    sitting = {derive.vote_identity(vote) for vote in report.get("sitting_votes") or []}
    under_a_top = {derive.vote_identity(vote) for item in report.get("agenda_items") or [] for vote in derive.item_votes(item)}
    # A vote held under a TOP is named below, once, for each TOP it should not sit under.
    errors += [f"vote {vote_id} is linked to no TOP and missing from sitting_votes"
               for vote_id, tops in sorted(placed.items()) if not tops and vote_id not in sitting | under_a_top]
    errors += [f"vote {vote_id} is linked to a TOP and also sits in sitting_votes"
               for vote_id in sorted(sitting & {vote_id for vote_id, tops in placed.items() if tops})]
    for position, item in enumerate(report.get("agenda_items") or []):
        held = {derive.vote_identity(vote) for vote in derive.item_votes(item)}
        should = {vote_id for vote_id, tops in placed.items() if position in tops}
        label = item.get("top_id") or f"item {item.get('index')}"
        errors += [f"vote {vote_id} sits under {label}, which the rule does not link it to" for vote_id in sorted(held - should)]
        errors += [f"vote {vote_id} is missing under {label}, which the rule links it to" for vote_id in sorted(should - held)]
    return errors
