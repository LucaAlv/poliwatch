"""Cross-run caches of DIP answers that cost requests (owner decisions
2026-10-23, docs/plans/a3-pilot.md): DIP stops answering after about a hundred
requests in a window, so a restarted backfill must not pay again for what an
earlier run fetched.

- ``data/dip-vorgang-drucksachen-cache.json``: a Vorgang's Drucksache positions,
  kept only for a Vorgang met in a sitting of a closed Wahlperiode (one before
  the catalog's newest), with no expiry. A current-Wahlperiode Vorgang is still
  extended by DIP, so it is cached within one build only.
- ``data/dip-person-cache.json``: a /person record, kept for PERSON_MAX_AGE_DAYS
  from its fetch. Only successful fetches are cached (D5).

Both files are saved after every sitting, so a run stopped part-way keeps what
it fetched. An unreadable file is an empty cache, never an error.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import validate_dip_protocol as dip

VORGANG_FILENAME = "dip-vorgang-drucksachen-cache.json"
PERSON_FILENAME = "dip-person-cache.json"
PERSON_MAX_AGE_DAYS = 30
_STAMP = "%Y-%m-%dT%H:%M:%SZ"


def _read(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        print(f"warning: ignoring the unreadable DIP cache {path}: {exc}", file=sys.stderr)
        return {}
    return payload if isinstance(payload, dict) else {}


@dataclass
class DipCache:
    output_dir: Path
    newest_wahlperiode: int | None
    now: datetime
    #: Vorgang id -> {"wahlperiode": int | None, "drucksachen": [...]}, the
    #: ``vorgang_drucksachen_cache`` of enrich_with_api.
    vorgang_drucksachen: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: DIP person id -> /person record, the ``person_cache`` of enrich_with_api.
    persons: dict[str, dict[str, Any]] = field(default_factory=dict)
    person_fetched_at: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, output_dir: Path, *, newest_wahlperiode: int | None, now: datetime | None = None) -> "DipCache":
        cache = cls(output_dir, newest_wahlperiode, now or datetime.now(timezone.utc))
        vorgaenge = _read(output_dir / "data" / VORGANG_FILENAME).get("vorgaenge")
        if isinstance(vorgaenge, dict):
            cache.vorgang_drucksachen.update(
                (str(key), value) for key, value in vorgaenge.items() if cache._closed(value)
            )
        persons = _read(output_dir / "data" / PERSON_FILENAME).get("persons")
        for person_id, entry in (persons or {}).items() if isinstance(persons, dict) else ():
            try:
                fetched = datetime.strptime(entry["fetched_at"], _STAMP).replace(tzinfo=timezone.utc)
            except (KeyError, TypeError, ValueError):
                continue
            if isinstance(entry.get("record"), dict) and cache.now - fetched <= timedelta(days=PERSON_MAX_AGE_DAYS):
                cache.persons[str(person_id)] = entry["record"]
                cache.person_fetched_at[str(person_id)] = entry["fetched_at"]
        return cache

    def _closed(self, entry: Any) -> bool:
        wahlperiode = entry.get("wahlperiode") if isinstance(entry, dict) else None
        return (
            isinstance(wahlperiode, int)
            and self.newest_wahlperiode is not None
            and wahlperiode < self.newest_wahlperiode
            and isinstance(entry.get("drucksachen"), list)
        )

    def save(self) -> None:
        """Write both files atomically. A failed write warns and leaves the run
        going: a cache must never end the build it serves."""
        stamp = self.now.strftime(_STAMP)
        for person_id in self.persons:
            self.person_fetched_at.setdefault(person_id, stamp)
        payloads = {
            VORGANG_FILENAME: {
                "version": 1,
                "vorgaenge": {key: value for key, value in self.vorgang_drucksachen.items() if self._closed(value)},
            },
            PERSON_FILENAME: {
                "version": 1,
                "persons": {
                    person_id: {"fetched_at": self.person_fetched_at[person_id], "record": record}
                    for person_id, record in self.persons.items()
                },
            },
        }
        for name, payload in payloads.items():
            try:
                dip.write_text_atomic(self.output_dir / "data" / name, json.dumps(payload, ensure_ascii=False) + "\n")
            except OSError as exc:
                print(f"warning: could not save the DIP cache {name}: {exc}", file=sys.stderr)
