#!/usr/bin/env python3
"""Build a deterministic, zero-network Bundestag-Puls demo from test fixtures."""

from __future__ import annotations

if __name__ == "__main__":
    from python_version_guard import require_supported_python

    require_supported_python()

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import build_dip_pulse_site as site
import publication_state as publication
import validate_dip_protocol as dip
from features import EnrichmentSelection


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "demo-report-21-84.json"
DEFAULT_OUTPUT = ROOT / ".context" / "dip-pulse-demo"
DEMO_ACQUIRED_AT = "2026-09-17T00:00:00Z"


def demo_report(fixture: Path) -> dict[str, Any]:
    report = json.loads(fixture.read_text(encoding="utf-8"))
    vote_records = sum(
        len(item.get("votes") or ([item["vote"]] if item.get("vote") else []))
        for item in report.get("agenda_items") or []
    )
    eligible = sum(
        1
        for item in report.get("agenda_items") or []
        if len(
            dip.summary_source_chunks(
                {
                    "top_id": item.get("top_id"),
                    "heading": item.get("heading"),
                    "speeches": item.get("xml_speakers") or [],
                }
            )
        )
        >= dip.SUMMARY_CHUNK_MIN
    )
    report["acquisition"] = {
        "votes": publication.DomainFacts(
            domain="votes",
            acquisition_state="complete",
            source="bundestag-roll-call",
            records=vote_records,
            reused=vote_records,
            acquired_at=DEMO_ACQUIRED_AT,
            attempted_at=DEMO_ACQUIRED_AT,
            attempted=True,
        ).as_dict(),
        "profiles": publication.DomainFacts(
            domain="profiles",
            acquisition_state="not_requested",
            source="abgeordnetenwatch",
            records=0,
        ).as_dict(),
        "summaries": publication.DomainFacts(
            domain="summaries",
            acquisition_state="not_requested",
            source="llm-with-bundestag-citations",
            records=0,
            counters={"eligible": eligible, "generated": 0, "omitted": eligible, "failed": 0, "fallbacks": 0},
        ).as_dict(),
    }
    report["summary_generation"] = {"enabled": False, "mode": "off"}
    return report


def build_demo(
    output_dir: Path,
    fixture: Path = DEFAULT_FIXTURE,
    *,
    include_dev_view: bool = False,
) -> Path:
    output_dir = output_dir.resolve()
    (output_dir / "data").mkdir(parents=True, exist_ok=True)
    (output_dir / "protocols").mkdir(parents=True, exist_ok=True)
    (output_dir / "bills").mkdir(parents=True, exist_ok=True)
    (output_dir / "abgeordnete").mkdir(parents=True, exist_ok=True)

    report = demo_report(fixture)
    entry = site.write_report_files(
        copy.deepcopy(report),
        output_dir,
        include_dev_view=include_dev_view,
    )
    protocol = copy.deepcopy(report["protocol"])
    protocol["wahlperiode"] = str((protocol.get("xml_header") or {}).get("wahlperiode") or "20")
    protocol["fundstelle"] = {
        "pdf_url": protocol.get("pdf_url"),
        "xml_url": protocol.get("xml_url"),
        "verteildatum": protocol.get("verteildatum"),
    }
    index_path = site.render_site(
        output_dir=output_dir,
        database_path=output_dir / "data" / "bundestag-pulse.sqlite",
        no_persist=True,
        protocols=[protocol],
        entries=[entry],
        abg_mps=[],
        mp_lookup={},
        enrichments=EnrichmentSelection(frozenset()),
        summary_mode="off",
        acquisition_attempted=False,
        include_dev_view=include_dev_view,
    )
    if not include_dev_view:
        publication.validate_publication_directory(output_dir)
    return index_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument(
        "--include-dev-view",
        action="store_true",
        help="Build an explicitly development-marked demo artifact for boundary testing.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    index_path = build_demo(
        args.output_dir,
        args.fixture,
        include_dev_view=args.include_dev_view,
    )
    report = json.loads(args.fixture.read_text(encoding="utf-8"))
    document_number = str((report.get("protocol") or {}).get("dokumentnummer") or "")
    dossier_path = index_path.parent / "protocols" / f"plenarprotokoll-{site.slugify_document_number(document_number)}.html"
    print(index_path)
    print(f"Demo dossier: {dossier_path}")
    print("Next online update: scripts/preview_dip_pulse_site.sh update --limit 2 --detail-limit 2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
