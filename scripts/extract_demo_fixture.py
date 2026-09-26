#!/usr/bin/env python3
"""Extract the committed Plenarprotokoll 21/84 demo from official XML.

This helper is intentionally network-free. Download the XML separately from
https://dserver.bundestag.de/btp/21/21084.xml, then pass its local path here.
"""

from __future__ import annotations

if __name__ == "__main__":
    from python_version_guard import require_supported_python

    require_supported_python()

import argparse
import json
from pathlib import Path
from typing import Any

import validate_dip_protocol as dip


DOCUMENT_NUMBER = "21/84"
DOCUMENT_ID = "official-demo-21-84"
PDF_URL = "https://dserver.bundestag.de/btp/21/21084.pdf"
XML_URL = "https://dserver.bundestag.de/btp/21/21084.xml"


def extract_report(xml_path: Path) -> dict[str, Any]:
    parsed = dip.parse_protocol_xml(xml_path.read_bytes())
    matches = [
        item
        for item in parsed.get("agenda_items") or []
        if "Deutschland in die KI-Zukunft bringen" in str(item.get("heading") or "")
    ]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one TOP 32 match, found {len(matches)}")

    source_item = matches[0]
    documents = source_item.get("drucksachen") or []
    if [document.get("dokumentnummer") for document in documents] != ["21/6354", "21/4833"]:
        raise ValueError("TOP 32 source documents changed; review the fixture before updating")
    speeches = source_item.get("speeches") or []
    if len(speeches) != 16:
        raise ValueError(f"expected 16 TOP 32 speeches, found {len(speeches)}")

    positions = []
    for index, document in enumerate(documents, 1):
        positions.append(
            {
                "id": f"fixture-position-{index}",
                "vorgang_id": f"fixture-procedure-{document['dokumentnummer'].replace('/', '-')}",
                "vorgangsposition": "Beratung und Ausschussüberweisung",
                "vorgangstyp": "Antrag",
                "titel": source_item.get("heading"),
                "dokumentart": "Drucksache",
                "aktivitaet_anzahl": 0,
                "source": {
                    "dokumentnummer": document["dokumentnummer"],
                    "pdf_url": document["url"],
                },
                "mitberaten": [],
            }
        )

    item = {
        "index": 1,
        "top_id": "Tagesordnungspunkt 32 a/b",
        "heading": source_item.get("heading"),
        "page_range": source_item.get("page_range"),
        "xml_drucksachen": documents,
        "xml_speakers": speeches,
        "xml_speech_count": len(speeches),
        "api": {
            "positions": positions,
            "linked_drucksachen": [
                {
                    "dokumentnummer": document["dokumentnummer"],
                    "url": document["url"],
                    "drucksachetyp": "Antrag",
                    "datum": "2026-06-12",
                    "titel": source_item.get("heading"),
                    "urheber": ["Fraktion der AfD"],
                    "vorgang_id": positions[index]["vorgang_id"],
                    "vorgangsposition_id": positions[index]["id"],
                }
                for index, document in enumerate(documents)
            ],
        },
        "votes": [],
    }
    return {
        "fixture_provenance": {
            "source": XML_URL,
            "extracted_scope": "Plenarprotokoll 21/84, Tagesordnungspunkt 32 a/b",
            "note": "DIP position wrappers are fixture-derived from the two XML Drucksachen.",
        },
        "protocol": {
            "id": DOCUMENT_ID,
            "dokumentnummer": DOCUMENT_NUMBER,
            "datum": "2026-06-12",
            "titel": "Plenarprotokoll 21/84",
            "pdf_url": PDF_URL,
            "xml_url": XML_URL,
            "xml_header": parsed.get("xml_protocol") or {},
        },
        "sampled_people": [],
        "agenda_items": [item],
        "warnings": [],
        "validation_summary": {
            "xml_top_count": 1,
            "xml_speech_count": len(speeches),
            "xml_drucksache_count": len(documents),
            "unique_person_ids": len(
                {
                    (speech.get("speaker") or {}).get("xml_redner_id")
                    for speech in speeches
                    if (speech.get("speaker") or {}).get("xml_redner_id")
                }
            ),
            "extracted_text_char_count": sum(int(speech.get("char_count") or 0) for speech in speeches),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", type=Path, required=True, help="Local official Plenarprotokoll 21/84 XML file.")
    parser.add_argument("--output", type=Path, required=True, help="Fixture JSON path to write.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = extract_report(args.xml)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
