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
CUT_RULE_VERSION = 1

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
    of the Sitzungsverlauf: the latest by page and quadrant in the
    Inhaltsverzeichnis, or, where it prints no pages (20/210), the last in
    order, without a place. Annex Reden are never the last one.

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
    verlauf = root.find("sitzungsverlauf")
    redes = list(verlauf.iter("rede")) if verlauf is not None else []
    if not redes:
        raise ProtocolCutError(f"{sitting}: a first edition without a <rede> in its Sitzungsverlauf")
    by_id = {rede.get("id"): rede for rede in redes}
    placed = []
    vorspann = root.find("vorspann")
    for xref in vorspann.iter("xref") if vorspann is not None else ():
        page = _page(xref.get("pnr"))
        if xref.get("ref-type") == "rede" and xref.get("rid") in by_id and page is not None:
            placed.append((page, _quadrant(xref.get("div")) or "", xref.get("rid")))
    if placed:
        page, quadrant, rede_id = max(placed)
        last = {"rede_id": rede_id, "page": page, "quadrant": quadrant or None}
    else:
        last = {"rede_id": redes[-1].get("id"), "page": None, "quadrant": None}
    last["surname"] = _surname(by_id[last["rede_id"]])
    return {"announced": dates.pop(), "last_rede": last}


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


def _order(activity: dict[str, Any]) -> tuple[int, str, str]:
    place = _place(activity) or (0, "")
    return place[0], place[1], str(activity.get("id") or "")


def protocol_cut(parsed: dict[str, Any], aktivitaeten: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """None when the sitting is whole: its XML prints no notice of a first
    edition, or it does and DIP's Aktivitäten are there and list no more "Rede"
    (the chair's left out) than the file's Reden and no more "Rede (zu Protokoll
    gegeben)" than its Reden zu Protokoll (19/107). Otherwise the cut: the
    announced date, the last ``<rede>`` and its place, and the DIP entries in the
    part the file does not print, in page order. A sitting DIP has not indexed
    yet has no Aktivitäten: it is marked, with an empty list.

    An entry is a "Rede" DIP places after the last ``<rede>`` (one in the same
    quadrant may be that Rede's neighbour and is not counted), or a "Rede (zu
    Protokoll gegeben)" that no stored one matches by surname within the
    sitting. Where the Inhaltsverzeichnis gives no page (20/210), the place is
    that of DIP's only "Rede" by the last speaker; none or several refuse."""
    notice = parsed.get("first_edition")
    if not notice:
        return None
    sitting = "{wahlperiode}/{sitzung_nr}".format(**{"wahlperiode": "?", "sitzung_nr": "?", **(parsed.get("xml_protocol") or {})})
    activities = [a for a in aktivitaeten or [] if isinstance(a, dict)]
    reden = sorted((a for a in activities if a.get("aktivitaetsart") == DIP_REDE and not CHAIR.search(str(a.get("titel") or ""))),
                   key=_order)
    written = sorted((a for a in activities if a.get("aktivitaetsart") == DIP_ZU_PROTOKOLL), key=_order)
    speech_count = sum(len(top.get("speeches") or []) for top in parsed.get("agenda_items") or [])
    stored_written = [
        c for c in [*(c for top in parsed.get("agenda_items") or [] for c in top.get("contributions") or []),
                    *(parsed.get("sitting_contributions") or [])]
        if c.get("kind") == speech_kinds.ZU_PROTOKOLL
    ]
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
    if page is not None:
        cut_at = (page, quadrant or "")
        entries += [_entry(a, "rede") for a in reden if (_place(a) or (0, "")) > cut_at]
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
        "entries": entries,
    }


def cut_summary(parsed: dict[str, Any], aktivitaeten: list[dict[str, Any]] | None) -> dict[str, Any]:
    """The ``validation_summary`` keys of the rule, for a built and a re-parsed
    report alike: the cut (or None) and the rule's version."""
    return {"protocol_cut": protocol_cut(parsed, aktivitaeten), "cut_rule_version": CUT_RULE_VERSION}
