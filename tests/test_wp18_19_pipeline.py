"""A3: a WP 18 and a WP 19 sitting go through persist, render, facts and the
Daten export with the roles and spellings only the old XML carries."""
from __future__ import annotations

import contextlib
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _support
import build_dip_pulse_site as build
import validate_dip_protocol as dip


def report_from(fixture: str, number: str, day: str) -> dict:
    parsed = dip.parse_protocol_xml((_support.FIXTURES / fixture).read_text(encoding="utf-8"))
    wahlperiode, sitting = number.split("/")
    return {
        "protocol": {"id": f"pp-{wahlperiode}-{sitting}", "dokumentnummer": number, "datum": day,
                     "pdf_url": f"https://dserver.bundestag.de/btp/{wahlperiode}/{wahlperiode}{int(sitting):03d}.pdf"},
        "agenda_items": [dict(index=top["index"], **dip.xml_top_fields(top)) for top in parsed["agenda_items"]],
        "xml_contributions": parsed.get("sitting_contributions", []),
        "validation_summary": dip.contribution_summary(parsed["agenda_items"], parsed.get("sitting_contributions")),
    }


class Wp18And19PipelineTests(unittest.TestCase):
    # Value (A3 T13): protects=historical sittings flow through every stage the backfill
    # runs; fails_when=a WP 20/21-only assumption returns (a role, a spelling, a recipe
    # without its Wahlperiode); seam=rebuild_database_from_entries, write_report_files,
    # export_distribution_data on trimmed real XML; no_claim=full-store scale.
    def test_a_wp18_and_a_wp19_sitting_persist_render_and_export(self) -> None:
        reports = [
            report_from("a3-wp18-18-150.xml", "18/150", "2016-01-15"),
            report_from("a3-wp19-19-100.xml", "19/100", "2019-05-09"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "site"
            for name in ("protocols", "data"):
                (output_dir / name).mkdir(parents=True)
            database = output_dir / "data" / "bundestag-pulse.sqlite"
            entries = [{"report": r, "report_path": output_dir / "data" / f"{r['protocol']['id']}.json"} for r in reports]
            with contextlib.redirect_stderr(io.StringIO()):
                build.rebuild_database_from_entries(database, entries)
                pages = [build.write_report_files(r, output_dir, {}, None)["page_path"] for r in reports]
                manifest = build.export_distribution_data(database, output_dir / "data" / "exports", catalog_count=2,
                                                          dossier_count=2, commit="test")
            with sqlite3.connect(database) as conn:
                roles = dict(conn.execute(
                    "SELECT m.display_name, s.sprechrolle FROM speeches s JOIN mps m ON m.id = s.mp_id "
                    "WHERE m.display_name LIKE '%Maas%' OR m.display_name LIKE '%Karliczek%'"
                ).fetchall())
                fraktionen = {row[0] for row in conn.execute("SELECT DISTINCT fraktion FROM speeches WHERE fraktion IS NOT NULL")}
                protocols = {row[0] for row in conn.execute("SELECT document_number FROM protocols")}
            for page in pages:
                self.assertIn("<html", Path(page).read_text(encoding="utf-8"))
        self.assertEqual(protocols, {"18/150", "19/100"})
        self.assertEqual(sorted(roles.values()), ["bundesregierung", "bundesregierung"])
        self.assertIn("BÜNDNIS 90/DIE GRÜNEN", fraktionen)
        self.assertFalse(any("GRÜNE N" in name or "90/ DIE" in name for name in fraktionen))
        r2 = next(r for r in manifest["recipes"] if r["id"] == "r2-redeanteil-fraktion")
        self.assertTrue({row["wahlperiode"] for row in r2["rows"]} <= {18, 19})
        self.assertEqual(manifest["protocols"]["first"], "18/150")


if __name__ == "__main__":
    unittest.main()
