"""Which TOPs of a sitting a namentliche Abstimmung is linked to (N10).

One rule, applied online (``validate_dip_protocol.enrich_with_api``), on every
replay (``build_dip_pulse_site.reparse_cached_xml``), after cached votes are
carried forward into a fresh report, and to every report right before persist
(``build_dip_pulse_site.rebuild_database_from_entries``), so a cached placement
never outlives the rule. Persist writes the links, their basis and the step that
decided them, and refuses a report whose placement disagrees with the rule.

**Inputs.** Drucksache numbers compare as Bundestag numbers without leading
zeros (``derive.canonical_document_number``). A TOP's numbers are those the
protocol XML prints under it (``xml_drucksachen``) and the Bundestag Drucksachen
(``herausgeber`` BT) of every DIP Vorgang whose position was assigned to it,
``mitberaten`` Vorgänge included (``api.linked_drucksachen``), except the
Vorgänge a procedural motion (a position "Geschäftsordnungsantrag" or "Antrag
zur Geschäftsordnung") names only as ``mitberaten``: the TOP did not deal with
them. A TOP with no heading and no Rede also has the numbers the chair names in
it (``called_drucksachen``, read by the parser with ``chair_numbers``).

**Steps, per vote, in this order** (docs/plans/vote-pr-c.md, section 2):

1. **Match.** Every TOP sharing a vote number: ``drucksache_xml`` where a shared
   number is printed under the TOP, else ``drucksache_vorgang``. With none, the
   one TOP whose heading, or one of whose DIP position titles, ``title_matches``
   the vote's title (``title``); with no such TOP, or several, none.
2. **The section where the chair calls the vote.** If exactly one TOP without
   heading and Rede names one of the vote's numbers, the vote links to it alone
   (``drucksache_call``). Stop.
3. **The Einzelplan.** If the vote is not an Entschließungsantrag, its title and
   description name exactly one Einzelplan, it is not on the third reading, and
   exactly one TOP heading names that Einzelplan, the vote links to that TOP
   alone (``einzelplan``). Stop.
4. **Drop the umbrella.** Of two or more TOPs matched by number, drop every TOP
   whose shared numbers are a proper subset of another's.
5. **Drop the neighbour.** Of two or more left, drop a TOP whose shared numbers
   come only through DIP positions that touch it on a single page while the same
   position covers another TOP on more pages.
6. **The third reading.** Of two or more left, if exactly one heading begins
   with "Dritte Beratung" (after a list mark), keep that one.

``top_links`` returns, per vote, the TOPs and the step that decided them:
``match`` when the TOPs are step 1's, else ``call``, ``einzelplan`` or
``narrowed``; ``none`` for no TOP. A vote linked to no TOP is a sitting vote
(``report["sitting_votes"]``). A link says the roll call was taken on a Vorlage
this TOP dealt with, not that the vote alone settled the TOP
(``docs/data-methods.md``, "Abstimmungen und Tagesordnungspunkte"; owner
decision 1 in docs/plans/vote-links-and-figures.md).
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, NamedTuple

import derive
import stable_ids

#: Every value ``agenda_item_votes.basis`` takes.
BASES = ("drucksache_xml", "drucksache_vorgang", "title", "einzelplan", "drucksache_call")

#: Every value ``votes.top_link_step`` takes: which step decided a vote's TOPs.
STEPS = ("none", "match", "call", "einzelplan", "narrowed")

#: The steps after the plain match. A vote they decided, or one linked to two or
#: more TOPs, is contested: the release gate needs a reviewed entry for each link.
CONTESTED_STEPS = ("call", "einzelplan", "narrowed")

#: What the rule reads from the parsed XML. A change of it (a new parse field,
#: another reading of one) bumps this, so every cached report is re-read from its
#: XML (``build_dip_pulse_site.stale_causes``, cause "votes"). 1: ``called_drucksachen``.
INPUTS_VERSION = 1


class TopLink(NamedTuple):
    """A vote's TOPs: {position of the TOP in the report's items: basis}, and
    the step (``STEPS``) that decided them."""
    tops: dict[int, str]
    step: str


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


_PROCEDURAL_MOTION_RE = re.compile(r"(?:Geschäftsordnungsantrag|Antrag zur Geschäftsordnung)")
_EINZELPLAN_RE = re.compile(r"\bEinzelplan\s+(\d{1,2})\b")
_THIRD_READING_RE = re.compile(r"(?:[IVX]+ |[a-z]\) ?)?[–-]? ?Dritte Beratung")
_LEADING_MARKS_RE = re.compile(r"\W+")
_CHAIR_CALL_RE = re.compile(r"\bDrucksachen? ((?:\d{2}/\d+\b(?: ?(?:,|und|sowie) ?)?)+)")
_CHAIR_NUMBER_RE = re.compile(r"\d{2}/\d+")


def chair_numbers(text: str | None) -> list[str]:
    """The Drucksache numbers a chair's paragraph names ("Drucksache 18/12639",
    "Drucksachen 19/1, 19/2 und 19/3"), in order, each once. A Bundesrat form
    ("Drucksache 447/26") yields nothing."""
    numbers: list[str] = []
    for match in _CHAIR_CALL_RE.finditer(derive.clean_text(text)):
        numbers += [number for number in _CHAIR_NUMBER_RE.findall(match.group(1)) if number not in numbers]
    return numbers


def _canonical(numbers: Iterable[Any]) -> set[str]:
    return {canonical for number in numbers if (canonical := derive.canonical_document_number(number))}


def _printed_numbers(item: Mapping[str, Any]) -> set[str]:
    return _canonical(doc.get("dokumentnummer") for doc in derive.xml_drucksachen(item))


def _dip_documents(item: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """The TOP's DIP-linked Bundestag Drucksachen, without those of a Vorgang a
    procedural motion names only as ``mitberaten`` (step B)."""
    api = item.get("api") or {}
    positions = api.get("positions") or []
    own = {str(position.get("vorgang_id")) for position in positions if position.get("vorgang_id")}
    dealt = set(own)
    named = set()
    for position in positions:
        others = {str(other.get("id")) for other in position.get("mitberaten") or [] if other.get("id")}
        if _PROCEDURAL_MOTION_RE.match(derive.clean_text(position.get("vorgangsposition"))):
            named |= others
        else:
            dealt |= others
    return [
        doc for doc in api.get("linked_drucksachen") or []
        if doc.get("dokumentnummer")
        and stable_ids.document_issuer(doc.get("herausgeber"), doc.get("url")) == "BT"
        and str(doc.get("vorgang_id")) not in named - dealt
    ]


def _position_titles(item: Mapping[str, Any]) -> list[str]:
    """The titles of the DIP positions assigned to the TOP and of the Vorgänge
    beraten with them, as the online run read them."""
    positions = (item.get("api") or {}).get("positions") or []
    titles = [position.get("titel") for position in positions]
    titles += [linked.get("titel") for position in positions for linked in position.get("mitberaten") or []]
    return [str(title) for title in titles if title]


def _called_numbers(item: Mapping[str, Any]) -> set[str]:
    """The numbers the chair names in a TOP section with no heading and no Rede."""
    if derive.clean_text(item.get("heading")) or item.get("xml_speech_count"):
        return set()
    return _canonical(item.get("called_drucksachen") or [])


def einzelplan_numbers(text: str | None) -> set[int]:
    """The Einzelpläne a text names, as numbers ("Einzelplan 4" is "Einzelplan 04")."""
    return {int(number) for number in _EINZELPLAN_RE.findall(derive.clean_text(text))}


def _page(value: Any) -> int | None:
    text = str(value or "").strip().split()
    try:
        return int(text[0]) if text else None
    except ValueError:
        return None


def _overlap(item: Mapping[str, Any], position: Mapping[str, Any]) -> int | None:
    """How many pages a DIP position shares with a TOP; None where a page is unknown."""
    pages = item.get("page_range") or {}
    top_start, top_end = _page((pages.get("start") or {}).get("page")), _page((pages.get("end") or {}).get("page"))
    source = position.get("source") or {}
    start = _page(source.get("anfangsseite") or source.get("seite"))
    end = _page(source.get("endseite") or source.get("seite")) or start
    if None in (top_start, top_end, start, end):
        return None
    return min(end, top_end) - max(start, top_start) + 1


def _boundary_vorgaenge(items: list[Mapping[str, Any]]) -> list[set[str]]:
    """Per TOP, the Vorgänge whose every position reaches it only on one page
    while the same position covers another TOP on more pages (step 5)."""
    result = []
    for index, item in enumerate(items):
        seen: set[str] = set()
        strong: set[str] = set()
        for position in (item.get("api") or {}).get("positions") or []:
            vorgang = str(position.get("vorgang_id"))
            seen.add(vorgang)
            here = _overlap(item, position)
            elsewhere = [_overlap(other, position) for other_index, other in enumerate(items) if other_index != index]
            if here is not None and here <= 1 and any(pages is not None and pages > here for pages in elsewhere):
                continue
            strong.add(vorgang)
            strong |= {str(other.get("id")) for other in position.get("mitberaten") or []}
        result.append(seen - strong)
    return result


def _third_reading(heading: str | None) -> bool:
    """Whether a heading begins, after a list mark, with "Dritte Beratung"."""
    text = derive.clean_text(heading)
    marks = _LEADING_MARKS_RE.match(text)
    return bool(_THIRD_READING_RE.match(text[marks.end():] if marks else text))


def top_links(items: list[Mapping[str, Any]], votes: Iterable[Mapping[str, Any]]) -> dict[str, TopLink]:
    """vote id (``derive.vote_identity``) -> ``TopLink`` for every vote. ``items``
    are a report's agenda items; ``votes`` need ``id``, ``title``,
    ``description`` and ``document_numbers`` (a list page candidate or a fetched
    vote). A vote id given twice is decided by its last entry. The result
    depends on the votes and the TOPs alone, not on their order or on where a
    report placed a vote."""
    printed = [_printed_numbers(item) for item in items]
    documents = [_dip_documents(item) for item in items]
    linked = [_canonical(doc["dokumentnummer"] for doc in docs) for docs in documents]
    titles = [[item.get("heading"), *_position_titles(item)] for item in items]
    called = [_called_numbers(item) for item in items]
    einzelplaene = [einzelplan_numbers(item.get("heading")) for item in items]
    boundary: list[set[str]] | None = None
    result: dict[str, TopLink] = {}
    for vote in votes:
        numbers = _canonical(vote.get("document_numbers") or [])
        matched: dict[int, str] = {}
        shared: dict[int, set[str]] = {}
        for position, (xml_numbers, dip_numbers) in enumerate(zip(printed, linked)):
            if numbers & xml_numbers:
                matched[position] = "drucksache_xml"
            elif numbers & dip_numbers:
                matched[position] = "drucksache_vorgang"
            if position in matched:
                shared[position] = numbers & (xml_numbers | dip_numbers)
        if not matched:
            titled = [
                position for position, candidates in enumerate(titles)
                if any(title_matches(title, vote.get("title")) for title in candidates)
            ]
            if len(titled) == 1:
                matched[titled[0]] = "title"
        first = set(matched)
        step = None
        # Step 2: the section where the chair calls the vote.
        calls = [position for position, chair in enumerate(called) if numbers & chair]
        if len(calls) == 1:
            matched, step = {calls[0]: "drucksache_call"}, "call"
        # Step 3: the Einzelplan.
        if step is None:
            text = f"{derive.clean_text(vote.get('title'))} {derive.clean_text(vote.get('description'))}"
            plans = einzelplan_numbers(text)
            second = "zweiten Beratung" in text or "dritten Beratung" not in text
            motion = derive.clean_text(vote.get("description")).startswith("Entschließungsantrag")
            if len(plans) == 1 and second and not motion:
                plan = next(iter(plans))
                sections = [position for position, named in enumerate(einzelplaene) if plan in named]
                if len(sections) == 1:
                    matched, step = {sections[0]: "einzelplan"}, "einzelplan"
        # Step 4: drop the umbrella.
        if step is None and len(matched) > 1 and all(position in shared for position in matched):
            matched = {
                position: basis for position, basis in matched.items()
                if not any(shared[position] < shared[other] for other in matched if other != position)
            }
        # Step 5: drop the neighbour.
        if step is None and len(matched) > 1:
            if boundary is None:
                boundary = _boundary_vorgaenge(items)

            def holds(position: int) -> bool:
                if matched[position] != "drucksache_vorgang":
                    return True
                return any(
                    str(doc.get("vorgang_id")) not in boundary[position]
                    for doc in documents[position] if derive.canonical_document_number(doc["dokumentnummer"]) in numbers
                )

            kept = {position: basis for position, basis in matched.items() if holds(position)}
            if kept:
                matched = kept
        # Step 6: the third reading.
        if step is None and len(matched) > 1:
            third = [position for position in matched if _third_reading(items[position].get("heading"))]
            if len(third) == 1:
                matched = {third[0]: matched[third[0]]}
        if not matched:
            step = "none"
        elif set(matched) == first:
            step = "match"
        elif step is None:
            step = "narrowed"
        result[derive.vote_identity(vote)] = TopLink(matched, step)
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


def links(report: Mapping[str, Any]) -> dict[str, TopLink]:
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


def attribute_votes(report: dict[str, Any], placed: Mapping[str, TopLink] | None = None) -> dict[str, Any]:
    """Place every vote of ``report`` under the TOPs ``links`` gives it and the
    rest in ``report["sitting_votes"]``, each list in ``_vote_order``. A copy
    already in the right place stays as it is, so a replay that keeps a link
    changes nothing; a new place gets the vote's first copy itself (``report_votes``),
    as the online run puts one fetched vote under every TOP it links to.
    ``placed`` is ``links(report)`` when the caller has run the rule already
    (the online run, over the list candidates); it must cover every vote.
    Returns ``report``."""
    votes = report_votes(report)
    placed = {vote_id: link.tops for vote_id, link in (links(report) if placed is None else placed).items()}
    order = _vote_order(report, votes)
    # A list is written only where it holds a vote or the report has the key, so a
    # report already placed by the rule leaves this unchanged (persist runs it on
    # every report and must not rewrite the cached evidence).
    for position, item in enumerate(report.get("agenda_items") or []):
        existing = {derive.vote_identity(vote): vote for vote in derive.item_votes(item)}
        held = [existing.get(vote_id) or votes[vote_id] for vote_id in order if position in placed[vote_id]]
        if held or "votes" in item:
            item["votes"] = held
    existing = {derive.vote_identity(vote): vote for vote in report.get("sitting_votes") or []}
    sitting = [existing.get(vote_id) or votes[vote_id] for vote_id in order if not placed[vote_id]]
    if sitting or "sitting_votes" in report:
        report["sitting_votes"] = sitting
    return report


def placement_errors(report: Mapping[str, Any]) -> list[str]:
    """Where ``report`` places a vote other than ``links`` does: a vote under a
    TOP the rule does not link it to, or missing under one it does; a vote the
    rule links to no TOP that ``report["sitting_votes"]`` lacks, which persist
    would drop; and a vote the rule links to a TOP that also sits in
    ``report["sitting_votes"]``, which a reader would show twice. Empty for a
    report ``attribute_votes`` placed. Persist refuses a report with any."""
    placed = {vote_id: link.tops for vote_id, link in links(report).items()}
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
