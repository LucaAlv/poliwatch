#!/usr/bin/env python3
"""Validate DIP plenary protocol extraction.

This is an exploratory script for the Bundestag Pulse "Assignment": take one
official Plenarprotokoll XML as the canonical transcript and enrich it with DIP
API metadata for proceedings, activities, people, and linked Drucksachen.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any


BASE_URL = "https://search.dip.bundestag.de/api/v1"
QUADRANT_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4}


class DipError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApiClient:
    api_key: str
    base_url: str = BASE_URL
    sleep_seconds: float = 0.0

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        params = dict(params or {})
        params["apikey"] = self.api_key
        params.setdefault("format", "json")
        url = f"{self.base_url}{path}?{urllib.parse.urlencode(params, doseq=True)}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                data = json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise DipError(f"DIP API HTTP {exc.code} for {path}: {body[:500]}") from exc
        except urllib.error.URLError as exc:
            raise DipError(f"DIP API request failed for {path}: {exc}") from exc
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)
        return data

    def list_all(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        params = dict(params or {})
        documents: list[dict[str, Any]] = []
        previous_cursor = None
        while True:
            page = self.get_json(path, params)
            batch = page.get("documents") or []
            documents.extend(batch)
            cursor = page.get("cursor")
            if not batch or not cursor or cursor == previous_cursor:
                break
            previous_cursor = cursor
            params["cursor"] = cursor
        return documents


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"Accept": "application/xml,text/xml,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            return res.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise DipError(f"Failed to fetch XML {url}: {exc}") from exc


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def elem_text(elem: ET.Element | None) -> str:
    if elem is None:
        return ""
    return clean_text("".join(elem.itertext()))


def child_text(elem: ET.Element, path: str) -> str:
    return elem_text(elem.find(path))


def page_sort_key(page: dict[str, Any]) -> tuple[int, int]:
    return (int(page.get("page") or 0), QUADRANT_ORDER.get(str(page.get("quadrant") or ""), 0))


def page_number(value: str | int | None) -> int | None:
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None


def extract_drucksachen(elem: ET.Element) -> list[dict[str, str | None]]:
    docs: list[dict[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for anchor in elem.findall(".//a"):
        href = anchor.attrib.get("href")
        text = elem_text(anchor)
        candidates = re.findall(r"\b\d{1,2}/\d{1,6}\b", text)
        for number in candidates:
            key = (number, href)
            if key not in seen:
                docs.append({"dokumentnummer": number, "url": href})
                seen.add(key)
    return docs


def parse_redner(redner: ET.Element | None) -> dict[str, Any] | None:
    if redner is None:
        return None
    name = redner.find("name")
    if name is None:
        return {"xml_redner_id": redner.attrib.get("id"), "display_name": elem_text(redner)}

    title = child_text(name, "titel")
    first = child_text(name, "vorname")
    last = child_text(name, "nachname")
    fraction = child_text(name, "fraktion") or None
    role_long = child_text(name, "rolle/rolle_lang") or None
    role_short = child_text(name, "rolle/rolle_kurz") or None
    parts = [part for part in (title, first, last) if part]
    display_name = clean_text(" ".join(parts)) or elem_text(redner)
    return {
        "xml_redner_id": redner.attrib.get("id"),
        "display_name": display_name,
        "fraktion": fraction,
        "role": role_long,
        "role_short": role_short,
    }


def parse_toc(root: ET.Element) -> dict[str, dict[str, Any]]:
    toc: dict[str, dict[str, Any]] = {}
    for block in root.findall("./vorspann/inhaltsverzeichnis/ivz-block"):
        title = elem_text(block.find("ivz-block-titel"))
        pages: list[dict[str, Any]] = []
        rid_pages: dict[str, dict[str, Any]] = {}
        for xref in block.findall(".//xref"):
            rid = xref.attrib.get("rid")
            page = page_number(xref.attrib.get("pnr") or child_text(xref, ".//seite"))
            quadrant = xref.attrib.get("div") or child_text(xref, ".//seitenbereich") or None
            if page is None:
                continue
            page_ref = {"page": page, "quadrant": quadrant}
            pages.append(page_ref)
            if rid:
                rid_pages[rid] = page_ref
        key = title or f"toc-block-{len(toc) + 1}"
        toc[key] = {
            "title": title,
            "drucksachen": extract_drucksachen(block),
            "pages": sorted(pages, key=page_sort_key),
            "rid_pages": rid_pages,
        }
    return toc


def speech_text_and_paragraphs(rede: ET.Element) -> tuple[str, int]:
    paragraphs: list[str] = []
    for paragraph in rede.findall("p"):
        if paragraph.attrib.get("klasse") == "redner":
            continue
        text = elem_text(paragraph)
        if text:
            paragraphs.append(text)
    return clean_text(" ".join(paragraphs)), len(paragraphs)


def parse_protocol_xml(xml_text: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    toc = parse_toc(root)
    rid_pages: dict[str, dict[str, Any]] = {}
    for block in toc.values():
        rid_pages.update(block["rid_pages"])

    agenda_items: list[dict[str, Any]] = []
    for index, top in enumerate(root.findall("./sitzungsverlauf/tagesordnungspunkt"), start=1):
        heading_lines: list[str] = []
        transfer_lines: list[str] = []
        for paragraph in top.findall("p"):
            klass = paragraph.attrib.get("klasse", "")
            if klass in {"T_NaS", "T_fett"}:
                text = elem_text(paragraph)
                if text:
                    heading_lines.append(text)
            elif klass == "T_Ueberweisung":
                text = elem_text(paragraph)
                if text:
                    transfer_lines.append(text)

        speeches: list[dict[str, Any]] = []
        pages: list[dict[str, Any]] = []
        for rede in top.findall("rede"):
            rid = rede.attrib.get("id")
            redner = parse_redner(rede.find("./p[@klasse='redner']/redner"))
            text, paragraph_count = speech_text_and_paragraphs(rede)
            page_ref = rid_pages.get(rid or "")
            if page_ref:
                pages.append(page_ref)
            speeches.append(
                {
                    "rede_id": rid,
                    "source_page": page_ref,
                    "speaker": redner,
                    "paragraph_count": paragraph_count,
                    "char_count": len(text),
                    "snippet": text[:240],
                }
            )

        sorted_pages = sorted(pages, key=page_sort_key)
        agenda_items.append(
            {
                "index": index,
                "top_id": top.attrib.get("top-id"),
                "heading": clean_text(" ".join(heading_lines)),
                "drucksachen": extract_drucksachen(top),
                "ueberweisung": transfer_lines,
                "page_range": {
                    "start": sorted_pages[0] if sorted_pages else None,
                    "end": sorted_pages[-1] if sorted_pages else None,
                },
                "speeches": speeches,
            }
        )

    return {
        "xml_protocol": {
            "wahlperiode": root.attrib.get("wahlperiode"),
            "sitzung_nr": root.attrib.get("sitzung-nr"),
            "sitzung_datum": root.attrib.get("sitzung-datum"),
            "sitzung_start": root.attrib.get("sitzung-start-uhrzeit"),
            "sitzung_end": root.attrib.get("sitzung-ende-uhrzeit"),
            "start_page": root.attrib.get("start-seitennr"),
        },
        "toc_block_count": len(toc),
        "agenda_items": agenda_items,
    }


def find_protocol(client: ApiClient, protocol_id: str | None, document_number: str | None) -> dict[str, Any]:
    if protocol_id:
        return client.get_json(f"/plenarprotokoll/{protocol_id}")

    params: dict[str, Any] = {"f.zuordnung": "BT"}
    if document_number:
        params["f.dokumentnummer"] = document_number
    documents = client.list_all("/plenarprotokoll", params)
    if not documents:
        selector = f"document number {document_number}" if document_number else "latest BT protocol"
        raise DipError(f"No Plenarprotokoll found for {selector}")
    return documents[0]


def norm_title(value: str | None) -> str:
    value = clean_text(value).lower()
    value = re.sub(r"[^a-zäöüß0-9]+", " ", value)
    return clean_text(value)


def overlaps(top: dict[str, Any], position: dict[str, Any]) -> bool:
    page_range = top.get("page_range") or {}
    start_ref = page_range.get("start")
    end_ref = page_range.get("end")
    if not start_ref or not end_ref:
        return False
    top_start = page_number(start_ref.get("page"))
    top_end = page_number(end_ref.get("page"))
    fundstelle = position.get("fundstelle") or {}
    pos_start = page_number(fundstelle.get("anfangsseite") or fundstelle.get("seite"))
    pos_end = page_number(fundstelle.get("endseite") or fundstelle.get("seite") or pos_start)
    if None in {top_start, top_end, pos_start, pos_end}:
        return False
    return int(pos_start) <= int(top_end) and int(pos_end) >= int(top_start)


def title_matches(heading: str | None, title: str | None) -> bool:
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


def activity_page(activity: dict[str, Any]) -> int | None:
    fundstelle = activity.get("fundstelle") or {}
    return page_number(fundstelle.get("seite") or fundstelle.get("anfangsseite"))


def activity_in_top(activity: dict[str, Any], top: dict[str, Any]) -> bool:
    page = activity_page(activity)
    page_range = top.get("page_range") or {}
    start_ref = page_range.get("start")
    end_ref = page_range.get("end")
    if page is None or not start_ref or not end_ref:
        return False
    start = page_number(start_ref.get("page"))
    end = page_number(end_ref.get("page"))
    return start is not None and end is not None and start <= page <= end


def compact_position(position: dict[str, Any]) -> dict[str, Any]:
    fundstelle = position.get("fundstelle") or {}
    return {
        "id": position.get("id"),
        "vorgang_id": position.get("vorgang_id"),
        "vorgangsposition": position.get("vorgangsposition"),
        "vorgangstyp": position.get("vorgangstyp"),
        "titel": position.get("titel"),
        "dokumentart": position.get("dokumentart"),
        "aktivitaet_anzahl": position.get("aktivitaet_anzahl"),
        "source": {
            "dokumentnummer": fundstelle.get("dokumentnummer"),
            "seite": fundstelle.get("seite"),
            "anfangsseite": fundstelle.get("anfangsseite"),
            "endseite": fundstelle.get("endseite"),
            "pdf_url": fundstelle.get("pdf_url"),
            "xml_url": fundstelle.get("xml_url"),
        },
        "mitberaten": position.get("mitberaten") or [],
    }


def compact_activity(activity: dict[str, Any]) -> dict[str, Any]:
    fundstelle = activity.get("fundstelle") or {}
    return {
        "id": activity.get("id"),
        "aktivitaetsart": activity.get("aktivitaetsart"),
        "titel": activity.get("titel"),
        "person_id": activity.get("person_id"),
        "seite": fundstelle.get("seite"),
        "pdf_url": fundstelle.get("pdf_url"),
        "vorgangsbezug_anzahl": activity.get("vorgangsbezug_anzahl"),
    }


def compact_drucksache_position(position: dict[str, Any]) -> dict[str, Any]:
    fundstelle = position.get("fundstelle") or {}
    return {
        "vorgang_id": position.get("vorgang_id"),
        "vorgangsposition_id": position.get("id"),
        "vorgangsposition": position.get("vorgangsposition"),
        "titel": position.get("titel"),
        "dokumentnummer": fundstelle.get("dokumentnummer"),
        "drucksachetyp": fundstelle.get("drucksachetyp"),
        "datum": fundstelle.get("datum"),
        "url": fundstelle.get("pdf_url"),
        "urheber": fundstelle.get("urheber") or [],
    }


def unique_by(items: list[dict[str, Any]], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        key = tuple(item.get(k) for k in keys)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def enrich_with_api(
    client: ApiClient,
    protocol: dict[str, Any],
    parsed_xml: dict[str, Any],
    person_limit: int,
) -> dict[str, Any]:
    protocol_id = protocol["id"]
    positions = client.list_all("/vorgangsposition", {"f.plenarprotokoll": protocol_id})
    activities = client.list_all("/aktivitaet", {"f.plenarprotokoll": protocol_id})

    positions_by_vorgang: dict[str, list[dict[str, Any]]] = {}
    linked_drucksachen_by_vorgang: dict[str, list[dict[str, Any]]] = {}

    def load_vorgang_positions(vorgang_id: str) -> list[dict[str, Any]]:
        if vorgang_id not in positions_by_vorgang:
            positions_by_vorgang[vorgang_id] = client.list_all("/vorgangsposition", {"f.vorgang": vorgang_id})
        return positions_by_vorgang[vorgang_id]

    def linked_drucksachen_for_vorgang(vorgang_id: str) -> list[dict[str, Any]]:
        if vorgang_id not in linked_drucksachen_by_vorgang:
            drucksache_positions = [
                compact_drucksache_position(position)
                for position in load_vorgang_positions(vorgang_id)
                if position.get("dokumentart") == "Drucksache"
            ]
            linked_drucksachen_by_vorgang[vorgang_id] = drucksache_positions
        return linked_drucksachen_by_vorgang[vorgang_id]

    def position_drucksache_numbers(position: dict[str, Any]) -> set[str]:
        numbers: set[str] = set()
        if position.get("vorgang_id"):
            numbers.update(
                str(doc.get("dokumentnummer"))
                for doc in linked_drucksachen_for_vorgang(str(position["vorgang_id"]))
                if doc.get("dokumentnummer")
            )
        for linked in position.get("mitberaten") or []:
            if linked.get("id"):
                numbers.update(
                    str(doc.get("dokumentnummer"))
                    for doc in linked_drucksachen_for_vorgang(str(linked["id"]))
                    if doc.get("dokumentnummer")
                )
        return numbers

    def position_matches_top(position: dict[str, Any], top: dict[str, Any]) -> bool:
        if not overlaps(top, position):
            return False
        xml_numbers = {
            str(doc.get("dokumentnummer"))
            for doc in top.get("drucksachen", [])
            if doc.get("dokumentnummer")
        }
        if xml_numbers:
            return bool(xml_numbers & position_drucksache_numbers(position)) or title_matches(
                top.get("heading"), position.get("titel")
            )
        return title_matches(top.get("heading"), position.get("titel"))

    enriched_tops: list[dict[str, Any]] = []
    for top in parsed_xml["agenda_items"]:
        matching_positions = [position for position in positions if position_matches_top(position, top)]
        matching_activities = [activity for activity in activities if activity_in_top(activity, top)]

        linked_drucksachen: list[dict[str, Any]] = []
        vorgang_ids = {str(position.get("vorgang_id")) for position in matching_positions if position.get("vorgang_id")}
        for position in matching_positions:
            for linked in position.get("mitberaten") or []:
                if linked.get("id"):
                    vorgang_ids.add(str(linked["id"]))

        for vorgang_id in sorted(vorgang_ids):
            linked_drucksachen.extend(linked_drucksachen_for_vorgang(vorgang_id))

        enriched_tops.append(
            {
                "index": top["index"],
                "top_id": top["top_id"],
                "heading": top["heading"],
                "page_range": top["page_range"],
                "xml_drucksachen": top["drucksachen"],
                "xml_speech_count": len(top["speeches"]),
                "xml_speakers": [
                    {
                        "rede_id": speech["rede_id"],
                        "source_page": speech["source_page"],
                        "speaker": speech["speaker"],
                        "char_count": speech["char_count"],
                    }
                    for speech in top["speeches"]
                ],
                "xml_speakers_first": [
                    {
                        "rede_id": speech["rede_id"],
                        "source_page": speech["source_page"],
                        "speaker": speech["speaker"],
                        "char_count": speech["char_count"],
                        "snippet": speech["snippet"],
                    }
                    for speech in top["speeches"][:5]
                ],
                "api": {
                    "positions": [compact_position(position) for position in matching_positions],
                    "activities_count": len(matching_activities),
                    "activities_first": [compact_activity(activity) for activity in matching_activities[:5]],
                    "linked_drucksachen": unique_by(linked_drucksachen, ("vorgang_id", "dokumentnummer", "url")),
                },
            }
        )

    unique_person_ids = []
    seen_person_ids: set[str] = set()
    for activity in activities:
        person_id = activity.get("person_id")
        if person_id and person_id not in seen_person_ids:
            seen_person_ids.add(person_id)
            unique_person_ids.append(str(person_id))

    sampled_people: list[dict[str, Any]] = []
    for person_id in unique_person_ids[:person_limit]:
        person = client.get_json(f"/person/{person_id}")
        sampled_people.append(
            {
                "id": person.get("id"),
                "titel": person.get("titel"),
                "fraktion": person.get("fraktion"),
                "funktion": person.get("funktion"),
                "wahlperiode": person.get("wahlperiode"),
            }
        )

    warnings: list[str] = []
    if any(not top["api"]["positions"] for top in enriched_tops):
        warnings.append("At least one XML TOP could not be matched to a DIP Vorgangsposition by page range.")
    if any(top["xml_speech_count"] and top["api"]["activities_count"] == 0 for top in enriched_tops):
        warnings.append("At least one XML TOP with speeches had no matching DIP activities by page range.")
    if len(activities) >= 100:
        warnings.append("Activity count exceeded one API page; cursor pagination was exercised.")

    return {
        "api_totals": {
            "vorgangsposition_count": len(positions),
            "aktivitaet_count": len(activities),
            "unique_person_ids": len(unique_person_ids),
            "sampled_person_count": len(sampled_people),
        },
        "sampled_people": sampled_people,
        "agenda_items": enriched_tops,
        "warnings": warnings,
    }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    api_key = args.api_key or os.environ.get("DIP_API_KEY")
    if not api_key:
        raise DipError("Provide a DIP API key via --api-key or DIP_API_KEY.")

    client = ApiClient(api_key=api_key, sleep_seconds=args.sleep)
    protocol = find_protocol(client, args.protocol_id, args.document_number)
    fundstelle = protocol.get("fundstelle") or {}
    xml_url = fundstelle.get("xml_url")
    if not xml_url:
        raise DipError(f"Protocol {protocol.get('id')} has no fundstelle.xml_url.")

    xml_text = fetch_text(xml_url)
    parsed_xml = parse_protocol_xml(xml_text)
    enrichment = enrich_with_api(client, protocol, parsed_xml, args.person_limit)

    agenda_items = enrichment["agenda_items"]
    if args.limit_tops is not None:
        agenda_items = agenda_items[: args.limit_tops]

    xml_speech_count = sum(len(top["speeches"]) for top in parsed_xml["agenda_items"])
    xml_drucksache_count = sum(len(top["drucksachen"]) for top in parsed_xml["agenda_items"])
    tops_with_xml_drucksachen = sum(1 for top in parsed_xml["agenda_items"] if top["drucksachen"])
    tops_with_api_positions = sum(1 for top in enrichment["agenda_items"] if top["api"]["positions"])
    tops_with_api_drucksachen = sum(1 for top in enrichment["agenda_items"] if top["api"]["linked_drucksachen"])

    return {
        "protocol": {
            "id": protocol.get("id"),
            "dokumentnummer": protocol.get("dokumentnummer"),
            "datum": protocol.get("datum"),
            "titel": protocol.get("titel"),
            "verteildatum": fundstelle.get("verteildatum"),
            "pdf_url": fundstelle.get("pdf_url"),
            "xml_url": xml_url,
            "xml_header": parsed_xml["xml_protocol"],
        },
        "validation_summary": {
            "xml_top_count": len(parsed_xml["agenda_items"]),
            "xml_speech_count": xml_speech_count,
            "xml_drucksache_count": xml_drucksache_count,
            "tops_with_xml_drucksachen": tops_with_xml_drucksachen,
            "tops_with_api_positions": tops_with_api_positions,
            "tops_with_api_linked_drucksachen": tops_with_api_drucksachen,
            **enrichment["api_totals"],
        },
        "warnings": enrichment["warnings"],
        "sampled_people": enrichment["sampled_people"],
        "agenda_items": agenda_items,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--protocol-id", help="DIP Plenarprotokoll ID, e.g. 5799")
    selector.add_argument("--document-number", help="DIP document number, e.g. 21/84")
    parser.add_argument("--api-key", help="DIP API key. Prefer DIP_API_KEY for local use.")
    parser.add_argument("--limit-tops", type=int, help="Only print the first N XML agenda items.")
    parser.add_argument("--person-limit", type=int, default=25, help="Number of distinct person records to sample.")
    parser.add_argument("--sleep", type=float, default=0.0, help="Optional delay between DIP API requests.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build_report(args)
    except DipError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
