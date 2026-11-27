"""A Protokoll XML that is a first edition and stops partway through its sitting
(docs/source-errors.md E16, docs/plans/cut-protocols.md).

Such a file prints "Der gesamte und damit endgültige Stenografische Bericht der
N. Sitzung wird am D veröffentlicht" and was never replaced by the final one. The
sitting stays stored with what the file prints; DIP's Aktivitäten say whether
anything is missing and what: ``protocol_cut`` lists the Reden DIP places after
the file's last ``<rede>`` and the Reden zu Protokoll no stored one matches.
The list counts nowhere: it is no Rede.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

import speech_kinds

#: The version of the rule below. A cached report parsed under another (or none)
#: is stale (build_dip_pulse_site.stale_causes), and so is a store persisted
#: under another (persist_dip_pulse_store.require_current_speech_rules).
#: 2: a withheld Rede counts as printed in the "whole" test and in rule 3, and a
#: place without a quadrant compares by page alone (``after_cut``).
#: 3: the cut gives ``unplaced_reden`` (``unplaced``), None where DIP has not
#: indexed the sitting.
#: 4: a withheld unit counts as what it would be (``printed_reden``): only one
#: that would be a Rede is a printed Rede, one that would be a Rede zu Protokoll
#: matches DIP's entry as a stored one does, and one not yet reviewed counts as
#: neither; ``cut_summary`` writes that count (``printed_reden``) for rule 3.
#: Two Reden on one page and quadrant are ordered by the Sitzungsverlauf, not by
#: their ids as text (``last_printed_rede``). A DIP Aktivität without an id stops
#: the sitting only where it can become an entry (``_distinct``).
CUT_RULE_VERSION = 4

NOTICE = re.compile(
    r"Der gesamte und damit endgültige Stenografische Bericht der (\d+)\.\s*Sitzung wird am "
    r"(\d{1,2})\.\s*([A-Za-zäÄ]+)\s+(\d{4})\s+veröffentlicht"
)
MONTHS = {name: index for index, name in enumerate(
    ("januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september", "oktober",
     "november", "dezember"), start=1)}
#: DIP types the chair's farewells and greetings as "Rede"; the store holds none
#: of them as one (624 in 806 sittings), so they are no Rede here either.
CHAIR = re.compile(r",\s*(?:Bundestags(?:vize)?präs|Alterspräs)")
DIP_REDE = "Rede"
DIP_ZU_PROTOKOLL = "Rede (zu Protokoll gegeben)"
QUADRANTS = ("A", "B", "C", "D")


class ProtocolCutError(ValueError):
    """The file or DIP says something the rule cannot place: a person reads it."""


def _flat_text(root: ET.Element) -> str:
    return re.sub(r"\s+", " ", "".join(root.itertext()).replace("­", ""))


def _page(value: Any) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


def _quadrant(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return text if text in QUADRANTS else None


def _surname(rede: ET.Element) -> str:
    name = rede.find(".//redner/name/nachname")
    return "".join(name.itertext()).strip() if name is not None else ""


def first_edition_notice(root: ET.Element) -> dict[str, Any] | None:
    """None when the file prints no notice of a first edition. Else the date the
    notice announces the final edition for (ISO) and the file's last ``<rede>``
    of the Sitzungsverlauf (``last_printed_rede``). Annex Reden are never the
    last one.

    Refuses a notice that names another sitting, or two different dates."""
    sitting = f"{root.get('wahlperiode')}/{root.get('sitzung-nr')}"
    found = {match.groups() for match in NOTICE.finditer(_flat_text(root))}
    if not found:
        return None
    numbers = {number for number, *_ in found}
    if numbers != {str(root.get("sitzung-nr"))}:
        raise ProtocolCutError(
            f"{sitting}: the notice of a first edition names the {', '.join(sorted(numbers))}. Sitzung")
    dates = set()
    for _number, day, month, year in found:
        if month.casefold() not in MONTHS:
            raise ProtocolCutError(f"{sitting}: the notice of a first edition names no month: {month!r}")
        dates.add(f"{year}-{MONTHS[month.casefold()]:02d}-{int(day):02d}")
    if len(dates) != 1:
        raise ProtocolCutError(f"{sitting}: the notice of a first edition gives two dates ({', '.join(sorted(dates))})")
    last = last_printed_rede(root)
    if last is None:
        raise ProtocolCutError(f"{sitting}: a first edition without a <rede> in its Sitzungsverlauf")
    return {"announced": dates.pop(), "last_rede": last}


def last_printed_rede(root: ET.Element) -> dict[str, Any] | None:
    """The file's last ``<rede>`` of the Sitzungsverlauf, None without one: the
    latest by page and quadrant in the Inhaltsverzeichnis, the later in the
    Sitzungsverlauf where two share both, or, where it prints no pages
    (20/210), the last in order, without a place."""
    verlauf = root.find("sitzungsverlauf")
    redes = list(verlauf.iter("rede")) if verlauf is not None else []
    if not redes:
        return None
    by_id = {rede.get("id"): rede for rede in redes}
    # Its index in the Sitzungsverlauf, of the element by_id keeps (the last of an id printed twice).
    position = {rede.get("id"): index for index, rede in enumerate(redes)}
    placed = []
    vorspann = root.find("vorspann")
    for xref in vorspann.iter("xref") if vorspann is not None else ():
        page = _page(xref.get("pnr"))
        if xref.get("ref-type") == "rede" and xref.get("rid") in by_id and page is not None:
            placed.append((page, _quadrant(xref.get("div")) or "", position[xref.get("rid")], xref.get("rid")))
    if placed:
        page, quadrant, _position, rede_id = max(placed)
        last = {"rede_id": rede_id, "page": page, "quadrant": quadrant or None}
    else:
        last = {"rede_id": redes[-1].get("id"), "page": None, "quadrant": None}
    last["surname"] = _surname(by_id[last["rede_id"]])
    return last


def _place(activity: dict[str, Any]) -> tuple[int, str] | None:
    """Page and quadrant of a DIP Aktivität, from ``seite`` ("12420B") or the
    separate fields; None without a page."""
    fundstelle = activity.get("fundstelle") or {}
    match = re.match(r"\s*(\d+)\s*([A-D]?)", str(fundstelle.get("seite") or ""))
    if match:
        return int(match[1]), match[2]
    page = _page(fundstelle.get("anfangsseite"))
    return (page, _quadrant(fundstelle.get("anfangsquadrant")) or "") if page is not None else None


def _entry(activity: dict[str, Any], kind: str) -> dict[str, Any]:
    place = _place(activity)
    return {
        "dip_activity_id": str(activity.get("id") or ""),
        "kind": kind,
        "dip_person_id": str(activity["person_id"]) if activity.get("person_id") not in (None, "") else None,
        "speaker": str(activity.get("titel") or "").strip(),
        "page": place[0] if place else None,
        "quadrant": (place[1] or None) if place else None,
    }


def _dip_rede(activity: dict[str, Any]) -> bool:
    """Whether DIP lists the Aktivität as a "Rede" the rule counts: the chair's
    farewells and greetings (``CHAIR``) are none."""
    return activity.get("aktivitaetsart") == DIP_REDE and not CHAIR.search(str(activity.get("titel") or ""))


def _distinct(aktivitaeten: list[dict[str, Any]] | None, sitting: str | None = None) -> list[dict[str, Any]]:
    """DIP's Aktivitäten, each once: the client joins cursor pages, which may
    repeat one. With ``sitting``, an Aktivität without an id that can become an
    entry (a "Rede" the rule counts, or a "Rede (zu Protokoll gegeben)") is
    refused, for an entry is stored under its id; any other, and every one
    without ``sitting``, is kept as it is."""
    seen: set[str] = set()
    distinct = []
    for activity in aktivitaeten or []:
        if not isinstance(activity, dict):
            continue
        activity_id = str(activity.get("id") or "").strip()
        if not activity_id:
            if sitting is not None and (_dip_rede(activity) or activity.get("aktivitaetsart") == DIP_ZU_PROTOKOLL):
                raise ProtocolCutError(f"{sitting}: DIP lists an Aktivität without an id ({activity.get('titel') or '(no title)'})")
            distinct.append(activity)
        elif activity_id not in seen:
            seen.add(activity_id)
            distinct.append(activity)
    return distinct


def after_cut(place: tuple[int, str] | None, cut_at: tuple[int, str]) -> bool:
    """Whether a DIP place (page, quadrant or "") lies after the cut: on a later
    page, or on the cut's page in a later quadrant when both quadrants are known.
    A place without a page, or without a quadrant on the cut's own page, cannot
    be shown to lie after it, and neither can anything on the cut's page when
    the cut has no quadrant: there it may be the last printed Rede itself."""
    if place is None:
        return False
    page, quadrant = place
    if page != cut_at[0]:
        return page > cut_at[0]
    return bool(quadrant and cut_at[1]) and quadrant > cut_at[1]


def before_cut(place: tuple[int, str] | None, cut_at: tuple[int, str]) -> bool:
    """Whether a DIP place lies before the cut: on an earlier page, or on the
    cut's page in an earlier quadrant when both quadrants are known."""
    if place is None:
        return False
    page, quadrant = place
    if page != cut_at[0]:
        return page < cut_at[0]
    return bool(quadrant and cut_at[1]) and quadrant < cut_at[1]


def unplaced(reden: list[dict[str, Any]], cut_at: tuple[int, str], surname: str | None) -> int:
    """How many of DIP's Reden can be shown to lie neither before nor after the
    cut: those at its place (its quadrant, or its page where a quadrant is
    missing) and those without a page, less one by the last printed Rede's
    speaker, which is that Rede itself. Each may be printed or missing, so a
    count of Reden after the cut is a floor by that many."""
    at_cut = [a for a in reden if not after_cut(_place(a), cut_at) and not before_cut(_place(a), cut_at)]
    own = speech_kinds._last_word(surname) if surname else ""
    last_itself = any(own and speech_kinds._last_word(str(a.get("titel") or "")) == own for a in at_cut)
    return len(at_cut) - (1 if last_itself else 0)


#: The ``would_be`` of a withheld unit (``validate_dip_protocol.withheld_record``)
#: that DIP lists as "Rede", and the one it lists as "Rede (zu Protokoll gegeben)".
WOULD_BE_REDE = "speech"
WOULD_BE_ZU_PROTOKOLL = "zu_protokoll"


def _withheld(parsed: dict[str, Any], would_be: str) -> list[dict[str, Any]]:
    return [w for top in parsed.get("agenda_items") or [] for w in top.get("withheld") or [] if w["would_be"] == would_be]


def printed_reden(parsed: dict[str, Any]) -> int:
    """The Reden the file prints: the stored ones and the withheld ones (ADR
    0005) that would be a Rede, which DIP lists as "Rede" too. A withheld unit
    that would be a Beitrag, a procedural step or a Rede zu Protokoll is no
    Rede, and neither is one nobody has reviewed yet ("unreviewed")."""
    return (sum(len(top.get("speeches") or []) for top in parsed.get("agenda_items") or [])
            + len(_withheld(parsed, WOULD_BE_REDE)))


def _order(activity: dict[str, Any]) -> tuple[int, str, str]:
    place = _place(activity) or (0, "")
    return place[0], place[1], str(activity.get("id") or "")


def protocol_cut(parsed: dict[str, Any], aktivitaeten: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """None when the sitting is whole: its XML prints no notice of a first
    edition, or it does and DIP's Aktivitäten are there and list no more "Rede"
    (the chair's left out) than the file's Reden and no more "Rede (zu Protokoll
    gegeben)" than its Reden zu Protokoll (19/107); a withheld unit is printed as
    what it would be (``printed_reden``). Otherwise the cut: the
    announced date, the last ``<rede>`` and its place, and the DIP entries in the
    part the file does not print, in page order, and ``unplaced_reden``, the DIP
    Reden that can lie on either side of the cut (``unplaced``): where it is not
    0, the Reden listed are a floor. A sitting DIP has not indexed yet has no
    Aktivitäten: it is marked, with an empty list and ``unplaced_reden`` None.

    An entry is a "Rede" DIP places after the last ``<rede>`` (``after_cut``: one
    in the same quadrant may be that Rede's neighbour and is not counted), or a "Rede (zu
    Protokoll gegeben)" that no stored one, nor a withheld one that would be a
    Rede zu Protokoll, matches by surname within the sitting. Where the
    Inhaltsverzeichnis gives no page (20/210), the place is that of DIP's only
    "Rede" by the last speaker; none or several refuse."""
    notice = parsed.get("first_edition")
    if not notice:
        return None
    sitting = "{wahlperiode}/{sitzung_nr}".format(**{"wahlperiode": "?", "sitzung_nr": "?", **(parsed.get("xml_protocol") or {})})
    activities = _distinct(aktivitaeten, sitting)
    reden = sorted((a for a in activities if _dip_rede(a)), key=_order)
    written = sorted((a for a in activities if a.get("aktivitaetsart") == DIP_ZU_PROTOKOLL), key=_order)
    speech_count = printed_reden(parsed)
    stored_written = [
        c for c in [*(c for top in parsed.get("agenda_items") or [] for c in top.get("contributions") or []),
                    *(parsed.get("sitting_contributions") or [])]
        if c.get("kind") == speech_kinds.ZU_PROTOKOLL
    ] + _withheld(parsed, WOULD_BE_ZU_PROTOKOLL)
    if activities and len(reden) <= speech_count and len(written) <= len(stored_written):
        return None
    last = notice["last_rede"]
    page, quadrant, place_from = last["page"], last["quadrant"], "inhaltsverzeichnis"
    if page is None and activities:
        surname = speech_kinds._last_word(last["surname"])
        own = [a for a in reden if surname and speech_kinds._last_word(str(a.get("titel") or "")) == surname]
        placed = [_place(a) for a in own]
        if len(own) != 1 or placed[0] is None:
            raise ProtocolCutError(
                f"{sitting}: the Inhaltsverzeichnis gives no page for the last <rede> {last['rede_id']}, and there are "
                f"{len(own)} DIP Reden of {last['surname'] or '(no name)'} to place it by, not one with a page")
        page, quadrant, place_from = placed[0][0], placed[0][1] or None, "dip"
    entries = []
    unplaced_reden = None
    if page is not None:
        cut_at = (page, quadrant or "")
        entries += [_entry(a, "rede") for a in reden if after_cut(_place(a), cut_at)]
        if activities:
            unplaced_reden = unplaced(reden, cut_at, last["surname"])
    remaining: dict[str, int] = {}
    for contribution in stored_written:
        name = speech_kinds._last_word((contribution.get("speaker") or {}).get("display_name"))
        remaining[name] = remaining.get(name, 0) + 1
    for activity in written:
        name = speech_kinds._last_word(str(activity.get("titel") or ""))
        if remaining.get(name):
            remaining[name] -= 1
        else:
            entries.append(_entry(activity, "zu_protokoll"))
    return {
        "announced": notice["announced"],
        "last_rede_id": last["rede_id"],
        "page": page,
        "quadrant": quadrant,
        "place_from": place_from,
        "unplaced_reden": unplaced_reden,
        "entries": entries,
    }


def dip_indexed(report: dict[str, Any]) -> bool:
    """Whether a report holds DIP's Aktivitäten for its sitting: without them a
    cut's list is empty because DIP has not indexed the sitting, not because
    nothing is missing (``facts.CUT_PROTOCOL_UNINDEXED``)."""
    return any(isinstance(activity, dict) for activity in (report.get("api_records") or {}).get("aktivitaeten") or [])


def cut_summary(parsed: dict[str, Any], aktivitaeten: list[dict[str, Any]] | None) -> dict[str, Any]:
    """The ``validation_summary`` keys of the rule, for a built and a re-parsed
    report alike: the cut (or None), the rule's version and its count of the
    Reden the file prints (``printed_reden``), which gate rule 3 reads."""
    return {"protocol_cut": protocol_cut(parsed, aktivitaeten), "cut_rule_version": CUT_RULE_VERSION,
            "printed_reden": printed_reden(parsed)}


#: Rule 3 of docs/plans/cut-protocols.md: a file without the notice that looks
#: cut stops the gate for a person to read. It marks nothing.
RULE3_MIN = 5


def unmarked_cut_evidence(root: ET.Element, aktivitaeten: list[dict[str, Any]] | None, speech_count: int) -> dict[str, Any] | None:
    """For a file without the notice: the counts that make it look cut (at least
    ``RULE3_MIN`` DIP Reden after its last ``<rede>`` by page and quadrant
    (``after_cut``), and at least ``RULE3_MIN`` more DIP Reden, the chair's left
    out, than ``speech_count``, its printed Reden (``printed_reden``)), else
    None. None too where the Inhaltsverzeichnis gives no page."""
    last = last_printed_rede(root)
    if last is None or last["page"] is None:
        return None
    reden = [a for a in _distinct(aktivitaeten) if _dip_rede(a)]
    cut_at = (last["page"], last["quadrant"] or "")
    after = sum(1 for a in reden if after_cut(_place(a), cut_at))
    more = len(reden) - speech_count
    if after >= RULE3_MIN and more >= RULE3_MIN:
        return {"last_rede_id": last["rede_id"], "dip_reden_after": after, "dip_reden_more": more}
    return None
