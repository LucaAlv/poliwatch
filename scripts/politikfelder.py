"""Politikfelder: a closed list of 13 policy areas, derived from DIP data.

Every Tagesordnungspunkt and every vote gets 1 to 3 Politikfeld tags, or one
explicit ``untagged`` row. The tags are derived deterministically (no model),
at persist and render time, from three inputs: the report's own fields, the
Vorgang cache (``data/dip-vorgang-cache.json``, filled by the online build)
and the mapping tables below. Nothing is written into a report. A Politikfeld
is not a DIP Sachgebiet (28 labels, folded into the 13 here) and not
``votes.topic`` (the bundestag.de Dachzeile); see CONTEXT.md.

This module does no network I/O. Its one file access is ``load_cache`` and
``save_cache``.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import derive

POLITIKFELDER: tuple[str, ...] = (
    "Migration",
    "Soziales",
    "Wirtschaft & Finanzen",
    "Energie & Klima",
    "Verteidigung",
    "Innere Sicherheit",
    "Justiz",
    "Digitales",
    "Gesundheit",
    "Bildung",
    "Verkehr",
    "Außenpolitik",
    "Staat & Demokratie",
)
UNTAGGED = "untagged"
#: What a stored tag row may say: a Politikfeld, or the explicit untagged row.
ALLOWED_LABELS: tuple[str, ...] = POLITIKFELDER + (UNTAGGED,)
MAX_TAGS = 3

#: Where a tag came from. ``untagged``: the item has no topic data at all (a
#: Fragestunde, a Wahl). ``not_fetched``: the data it needs is not in the cache
#: (offline build, failed fetch), so the item may still get tags later.
SOURCES: tuple[str, ...] = (
    "sachgebiet",
    "drucksache",
    "einzelplan",
    "top",
    "untagged",
    "not_fetched",
    "einzelplan_unknown",
)

#: The 28 DIP Sachgebiete and the Politikfeld each folds into.
SACHGEBIET_TO_POLITIKFELD: dict[str, str] = {
    "Migration und Aufenthaltsrecht": "Migration",
    "Soziale Sicherung": "Soziales",
    "Arbeit und Beschäftigung": "Soziales",
    "Gesellschaftspolitik, soziale Gruppen": "Soziales",
    "Raumordnung, Bau- und Wohnungswesen": "Soziales",
    "Wirtschaft": "Wirtschaft & Finanzen",
    "Öffentliche Finanzen, Steuern und Abgaben": "Wirtschaft & Finanzen",
    "Außenwirtschaft": "Wirtschaft & Finanzen",
    "Landwirtschaft und Ernährung": "Wirtschaft & Finanzen",
    "Energie": "Energie & Klima",
    "Umwelt": "Energie & Klima",
    "Verteidigung": "Verteidigung",
    "Innere Sicherheit": "Innere Sicherheit",
    "Recht": "Justiz",
    "Medien, Kommunikation und Informationstechnik": "Digitales",
    "Gesundheit": "Gesundheit",
    "Bildung und Erziehung": "Bildung",
    "Wissenschaft, Forschung und Technologie": "Bildung",
    "Kultur": "Bildung",
    "Sport, Freizeit und Tourismus": "Bildung",
    "Verkehr": "Verkehr",
    "Außenpolitik und internationale Beziehungen": "Außenpolitik",
    "Europapolitik und Europäische Union": "Außenpolitik",
    "Entwicklungspolitik": "Außenpolitik",
    "Staat und Verwaltung": "Staat & Demokratie",
    "Politisches Leben, Parteien": "Staat & Demokratie",
    "Bundestag": "Staat & Demokratie",
    "Deutsche Einheit / Innerdeutsche Beziehungen (bis 1990)": "Staat & Demokratie",
}

_STAAT = ("Staat & Demokratie",)
_WIRTSCHAFT = ("Wirtschaft & Finanzen",)
#: Haushalt Einzelplan -> Politikfelder, keyed by (Wahlperiode, Einzelplan).
#: The Bundestag recuts ministries between Wahlperioden, so the number alone
#: does not say what an Einzelplan is about. Checked against the Einzelplan
#: headings of the WP 20 and 21 sittings in the cache (2026-10-04); a pair not
#: listed here is stored as ``einzelplan_unknown``.
EINZELPLAN_TO_POLITIKFELDER: dict[tuple[str, str], tuple[str, ...]] = {
    # Wahlperiode 20: Ampel
    ("20", "01"): _STAAT,  # Bundespräsident und Bundespräsidialamt
    ("20", "02"): _STAAT,  # Deutscher Bundestag
    ("20", "03"): _STAAT,  # Bundesrat
    ("20", "04"): _STAAT,  # Bundeskanzler und Bundeskanzleramt
    ("20", "05"): ("Außenpolitik",),  # Auswärtiges Amt
    ("20", "06"): ("Innere Sicherheit", "Migration"),  # Inneres und Heimat
    ("20", "07"): ("Justiz",),
    ("20", "08"): _WIRTSCHAFT,  # Finanzen
    ("20", "09"): ("Wirtschaft & Finanzen", "Energie & Klima"),  # Wirtschaft und Klimaschutz
    ("20", "10"): _WIRTSCHAFT,  # Ernährung und Landwirtschaft
    ("20", "11"): ("Soziales",),  # Arbeit und Soziales
    ("20", "12"): ("Verkehr", "Digitales"),  # Digitales und Verkehr
    ("20", "14"): ("Verteidigung",),
    ("20", "15"): ("Gesundheit",),
    ("20", "16"): ("Energie & Klima",),  # Umwelt
    ("20", "17"): ("Soziales",),  # Familie, Senioren, Frauen und Jugend
    ("20", "19"): _STAAT,  # Bundesverfassungsgericht
    ("20", "20"): _STAAT,  # Bundesrechnungshof
    ("20", "21"): ("Digitales",),  # Bundesbeauftragter für den Datenschutz
    ("20", "22"): _STAAT,  # Unabhängiger Kontrollrat
    ("20", "23"): ("Außenpolitik",),  # wirtschaftliche Zusammenarbeit und Entwicklung
    ("20", "25"): ("Soziales",),  # Wohnen, Stadtentwicklung und Bauwesen
    ("20", "30"): ("Bildung",),  # Bildung und Forschung
    ("20", "32"): _WIRTSCHAFT,  # Bundesschuld
    ("20", "60"): _WIRTSCHAFT,  # Allgemeine Finanzverwaltung
    # Wahlperiode 21: Union and SPD
    ("21", "01"): _STAAT,
    ("21", "02"): _STAAT,
    ("21", "03"): _STAAT,
    ("21", "04"): _STAAT,
    ("21", "05"): ("Außenpolitik",),
    ("21", "06"): ("Innere Sicherheit", "Migration"),  # Inneres
    ("21", "07"): ("Justiz",),  # Justiz und Verbraucherschutz
    ("21", "08"): _WIRTSCHAFT,
    ("21", "09"): ("Wirtschaft & Finanzen", "Energie & Klima"),  # Wirtschaft und Energie
    ("21", "10"): _WIRTSCHAFT,  # Landwirtschaft
    ("21", "11"): ("Soziales",),
    ("21", "12"): ("Verkehr",),
    ("21", "14"): ("Verteidigung",),
    ("21", "15"): ("Gesundheit",),
    ("21", "16"): ("Energie & Klima",),  # Umwelt
    ("21", "17"): ("Bildung", "Soziales"),  # Bildung, Familie, Senioren, Frauen und Jugend
    ("21", "19"): _STAAT,
    ("21", "20"): _STAAT,
    ("21", "21"): ("Digitales",),
    ("21", "22"): _STAAT,
    ("21", "23"): ("Außenpolitik",),
    ("21", "24"): ("Digitales", "Staat & Demokratie"),  # Digitales und Staatsmodernisierung
    ("21", "25"): ("Soziales",),
    ("21", "30"): ("Bildung",),  # Forschung, Technologie und Raumfahrt
    ("21", "32"): _WIRTSCHAFT,
    ("21", "60"): _WIRTSCHAFT,
}

_EINZELPLAN_RE = re.compile(r"\bEinzelplan\s+(\d{1,2})\b")

Tagging = tuple[list[str], str]


def empty_cache() -> dict[str, Any]:
    return {"version": 1, "vorgaenge": {}, "dokumentnummern": {}}


def load_cache(output_dir: Path | str) -> dict[str, Any]:
    """The Vorgang cache of a site directory; empty when absent or unreadable."""
    path = cache_path(output_dir)
    if not path.exists():
        return empty_cache()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        vorgaenge = data["vorgaenge"]
        dokumentnummern = data["dokumentnummern"]
        if not isinstance(vorgaenge, dict) or not isinstance(dokumentnummern, dict):
            raise TypeError("vorgaenge and dokumentnummern must be objects")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Keep the file for inspection: the next online build would overwrite it.
        kept = path.with_name(path.name + ".corrupt")
        try:
            path.replace(kept)
            note = f"moved to {kept.name}"
        except OSError:
            note = "left in place"
        print(
            f"warning: unreadable {path}: {exc} ({note}); Politikfelder fall back to not_fetched "
            "until an online build refills it.",
            file=sys.stderr,
        )
        return empty_cache()
    # A record or number list of the wrong shape is dropped, not trusted: it counts as a cache miss.
    vorgaenge = {str(k): v for k, v in vorgaenge.items() if isinstance(v, dict)}
    dokumentnummern = {str(k): [str(i) for i in v] for k, v in dokumentnummern.items() if isinstance(v, list)}
    return {"version": 1, "vorgaenge": vorgaenge, "dokumentnummern": dokumentnummern}


def cache_path(output_dir: Path | str) -> Path:
    return Path(output_dir) / "data" / "dip-vorgang-cache.json"


def save_cache(output_dir: Path | str, cache: Mapping[str, Any]) -> None:
    path = cache_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(cache, ensure_ascii=False, sort_keys=True, indent=1) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as handle:
        handle.write(text)
    Path(handle.name).replace(path)


def fields_for_sachgebiete(sachgebiete: Iterable[Any]) -> list[str]:
    """The Politikfelder of a Sachgebiet list, in order, without repeats. A label
    outside the 28 known ones is skipped; the mapping test names it."""
    fields: list[str] = []
    for label in sachgebiete or ():
        field = SACHGEBIET_TO_POLITIKFELD.get(str(label))
        if field and field not in fields:
            fields.append(field)
    return fields


def unknown_sachgebiete(cache: Mapping[str, Any]) -> set[str]:
    """Sachgebiet labels in the cache that the mapping does not know."""
    labels: set[str] = set()
    for record in (cache.get("vorgaenge") or {}).values():
        labels.update(str(label) for label in record.get("sachgebiet") or ())
    return labels - set(SACHGEBIET_TO_POLITIKFELD)


def _union(per_vorgang: list[list[str]]) -> list[str]:
    """First Vorgang's fields in its own order, then the others' fields by how
    many Vorgänge carry them (ties: POLITIKFELDER order), at most MAX_TAGS."""
    if not per_vorgang:
        return []
    tags = list(per_vorgang[0])
    counts: Counter[str] = Counter(field for fields in per_vorgang[1:] for field in fields)
    rest = sorted((f for f in counts if f not in tags), key=lambda f: (-counts[f], POLITIKFELDER.index(f)))
    return (tags + rest)[:MAX_TAGS]


def _from_vorgaenge(vorgang_ids: list[str], cache: Mapping[str, Any]) -> tuple[list[str], bool]:
    """(tags, a needed Vorgang is missing from the cache) for ordered ids, lead first."""
    records = cache.get("vorgaenge") or {}
    per_vorgang: list[list[str]] = []
    missing = False
    for vorgang_id in vorgang_ids:
        record = records.get(str(vorgang_id))
        if record is None:
            missing = True
            continue
        fields = fields_for_sachgebiete(record.get("sachgebiet"))
        if fields:
            per_vorgang.append(fields)
    return _union(per_vorgang), missing


def _vorgaenge_of_numbers(numbers: Iterable[str], cache: Mapping[str, Any]) -> tuple[list[str], bool]:
    """Vorgang ids that Drucksache numbers resolve to, and whether a number is
    missing from the cache. A Beschlussempfehlung or Sammelübersicht can resolve
    to several Vorgänge, so ids are ranked by how many of the numbers name them
    (ties: first seen), and the best-supported Vorgang leads."""
    resolved = cache.get("dokumentnummern") or {}
    counts: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    missing = False
    for number in numbers:
        if str(number) not in resolved:
            missing = True
            continue
        for vorgang_id in resolved[str(number)] or ():
            vorgang_id = str(vorgang_id)
            counts[vorgang_id] += 1
            first_seen.setdefault(vorgang_id, len(first_seen))
    return sorted(counts, key=lambda v: (-counts[v], first_seen[v])), missing


def _einzelplan_tags(item: Mapping[str, Any], wahlperiode: str) -> tuple[list[str], bool]:
    """(tags, a named Einzelplan is not in the table) from the item's heading and
    TOP id. In 117 TOPs of the archive (2026-10-09) the Einzelplan is only in
    ``top_id`` ("Einzelplan 04") and the heading is empty."""
    tags: list[str] = []
    unknown = False
    text = f"{item.get('heading') or ''} {item.get('top_id') or ''}"
    for match in _EINZELPLAN_RE.finditer(text):
        fields = EINZELPLAN_TO_POLITIKFELDER.get((wahlperiode, match.group(1).zfill(2)))
        if fields is None:
            unknown = True
            continue
        for field in fields:
            if field not in tags:
                tags.append(field)
    return tags[:MAX_TAGS], unknown


def agenda_item_vorgang_ids(item: Mapping[str, Any]) -> list[str]:
    """The item's Vorgang ids, the lead procedure first."""
    procedures, lead = derive.agenda_procedures(item)
    ids = [p["vorgang_id"] for p in procedures]
    if lead is not None:
        ids.remove(lead["vorgang_id"])
        ids.insert(0, lead["vorgang_id"])
    return ids


def tags_for_agenda_item(item: Mapping[str, Any], cache: Mapping[str, Any], *, wahlperiode: str) -> Tagging:
    """Tags and source of one Tagesordnungspunkt.

    The order is sachgebiet (its Vorgänge), drucksache (the Drucksache numbers
    it names), einzelplan (its heading), then untagged. A rule that finds no
    field falls through to the next, so a Vorgang DIP has not yet given a
    Sachgebiet does not end the search. When nothing yields a tag and a needed
    cache entry is missing, the source is ``not_fetched`` instead of ``untagged``.
    """
    missing = False
    ids = agenda_item_vorgang_ids(item)
    tags, ids_missing = _from_vorgaenge(ids, cache)
    missing |= ids_missing
    if tags:
        return tags, "sachgebiet"

    numbers = derive.item_document_numbers(item, wahlperiode)
    number_ids, numbers_missing = _vorgaenge_of_numbers(numbers, cache)
    missing |= numbers_missing
    tags, ids_missing = _from_vorgaenge(number_ids, cache)
    missing |= ids_missing
    if tags:
        return tags, "drucksache"

    tags, unknown = _einzelplan_tags(item, wahlperiode)
    if tags:
        return tags, "einzelplan"
    if missing:
        return [UNTAGGED], "not_fetched"
    if unknown:
        return [UNTAGGED], "einzelplan_unknown"
    return [UNTAGGED], "untagged"


def vote_document_numbers(vote: Mapping[str, Any], wahlperiode: str = "") -> list[str]:
    """The Drucksache numbers a vote names that can belong to its sitting (the roll-call
    scraper reads every ``12/345``-shaped string, so "76/787" turns up)."""
    return [
        str(number)
        for number in vote.get("document_numbers") or ()
        if derive.plausible_document_number(number, wahlperiode)
    ]


def tags_for_vote(
    vote: Mapping[str, Any],
    linked_item_tags: Iterable[Tagging],
    cache: Mapping[str, Any],
    *,
    wahlperiode: str = "",
    linked_vorgang_ids: Iterable[str] = (),
) -> Tagging:
    """Tags and source of one vote.

    First the vote's own Drucksache numbers (source ``drucksache``), so a vote
    on one Vorgang of a bundled TOP does not inherit the others' fields; then
    the union of the TOPs it is linked to (source ``top``); then untagged, or
    ``not_fetched`` when a needed cache entry is missing. A Beschlussempfehlung or
    Sammelübersicht number can name Vorgänge the vote is not about; when some of the
    resolved Vorgänge are among those of the TOPs the vote sits under
    (``linked_vorgang_ids``), only those count.
    """
    number_ids, missing = _vorgaenge_of_numbers(vote_document_numbers(vote, wahlperiode), cache)
    linked = {str(i) for i in linked_vorgang_ids}
    if linked & set(number_ids):
        number_ids = [i for i in number_ids if i in linked]
    tags, ids_missing = _from_vorgaenge(number_ids, cache)
    missing |= ids_missing
    if tags:
        return tags, "drucksache"

    per_item: list[list[str]] = []
    for item_tags, source in linked_item_tags:
        if source == "not_fetched":
            missing = True
        elif item_tags and item_tags != [UNTAGGED]:
            per_item.append(list(item_tags))
    union: list[str] = []
    for tags_of_item in per_item:
        for field in tags_of_item:
            if field not in union:
                union.append(field)
    if union:
        return union[:MAX_TAGS], "top"
    return [UNTAGGED], "not_fetched" if missing else "untagged"


vote_key = derive.vote_identity


def report_politikfelder(
    report: Mapping[str, Any], cache: Mapping[str, Any]
) -> tuple[list[Tagging], dict[Any, Tagging]]:
    """Tags of every agenda item (a list parallel to ``report["agenda_items"]``)
    and of every vote (keyed by ``vote_key``) of one sitting report. A vote cited
    under several TOPs takes the union over all of them, so persist and render
    agree on one answer."""
    wahlperiode = derive.report_wahlperiode(report)
    item_tags: list[Tagging] = []
    linked: dict[Any, list[Tagging]] = {}
    linked_ids: dict[Any, list[str]] = {}
    for item in report.get("agenda_items") or []:
        tagging = tags_for_agenda_item(item, cache, wahlperiode=wahlperiode)
        item_tags.append(tagging)
        for vote in item.get("votes") or ([item["vote"]] if item.get("vote") else []):
            linked.setdefault(vote_key(vote), []).append(tagging)
            linked_ids.setdefault(vote_key(vote), []).extend(agenda_item_vorgang_ids(item))
    vote_tags: dict[Any, Tagging] = {}
    for _item, vote in derive.iter_report_votes(report):
        key = vote_key(vote)
        vote_tags[key] = tags_for_vote(
            vote, linked.get(key, []), cache, wahlperiode=wahlperiode, linked_vorgang_ids=linked_ids.get(key, ())
        )
    return item_tags, vote_tags


def fetch_targets(reports: Iterable[Mapping[str, Any]], cache: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """What an online build still has to fetch for ``reports``.

    Returns (Vorgang ids, Drucksache numbers). Ids: every id the TOPs name that
    is missing from the cache, plus cached ones still without a Sachgebiet (DIP
    may have filled it since). Numbers: those of every vote, and of every TOP
    whose Vorgänge yield no tag, that the cache has not resolved. Call it again
    after fetching the ids, because which TOPs still need numbers depends on them.
    """
    records = cache.get("vorgaenge") or {}
    resolved = cache.get("dokumentnummern") or {}
    ids: list[str] = []
    numbers: list[str] = []

    def want_id(vorgang_id: str) -> None:
        record = records.get(vorgang_id)
        if (record is None or not record.get("sachgebiet")) and vorgang_id not in ids:
            ids.append(vorgang_id)

    def want_number(number: str) -> None:
        # A number DIP has not yet linked to a Vorgang resolves to [] and is asked again.
        if not resolved.get(number) and number not in numbers:
            numbers.append(number)

    for report in reports:
        wahlperiode = derive.report_wahlperiode(report)
        for item in report.get("agenda_items") or []:
            vorgang_ids = agenda_item_vorgang_ids(item)
            for vorgang_id in vorgang_ids:
                want_id(vorgang_id)
            if _from_vorgaenge(vorgang_ids, cache)[0]:
                continue
            for number in derive.item_document_numbers(item, wahlperiode):
                want_number(number)
                for vorgang_id in resolved.get(number) or ():
                    want_id(str(vorgang_id))
        for _item, vote in derive.iter_report_votes(report):
            for number in vote_document_numbers(vote, wahlperiode):
                want_number(number)
                for vorgang_id in resolved.get(str(number)) or ():
                    want_id(str(vorgang_id))
    return ids, numbers
