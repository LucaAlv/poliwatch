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

import glob
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import derive
import person_registry as registry

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

#: A dotted outline number ("Einzelplan 1.7" as the top_id of an Einzelplan 17 item)
#: is not an Einzelplan.
_EINZELPLAN_RE = re.compile(r"\bEinzelplan\s+(\d{1,2})\b(?!\.\d)")

Tagging = tuple[list[str], str]


def empty_cache() -> dict[str, Any]:
    return {"version": 1, "vorgaenge": {}, "dokumentnummern": {}}


class CacheLoadError(RuntimeError):
    pass


def load_cache(output_dir: Path | str) -> dict[str, Any]:
    """Load v1 data, preserving corrupt content; refuse incompatible or unreadable files."""
    path = cache_path(output_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("cache must be an object")
        version = data.get("version", 1)
        if type(version) is not int or version != 1:
            raise CacheLoadError(
                f"Unsupported Vorgang cache version {version!r} at {path}. "
                "Fix: use compatible code or restore a version 1 cache; the file is untouched"
            )
        vorgaenge = data["vorgaenge"]
        dokumentnummern = data["dokumentnummern"]
        if not isinstance(vorgaenge, dict) or not isinstance(dokumentnummern, dict):
            raise TypeError("vorgaenge and dokumentnummern must be objects")
    except FileNotFoundError:
        print(
            f"note: no Vorgang cache at {path} yet; Politikfelder stay not_fetched until an online build fills it.",
            file=sys.stderr,
        )
        return empty_cache()
    except OSError as exc:
        raise CacheLoadError(
            f"Cannot read Vorgang cache {path}: {exc}. "
            "Fix: restore read access or restore the cache; the file is untouched"
        ) from exc
    except (ValueError, KeyError, TypeError, RecursionError) as exc:
        note = "left in place"
        for directory in (registry.private_dir(path), path.parent):
            kept = None
            try:
                directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=directory, prefix=path.name + ".", suffix=".corrupt", delete=False) as handle:
                    kept = Path(handle.name)
                path.replace(kept)
                note = f"moved to {kept}"
                break
            except OSError:
                if kept is not None:
                    try:
                        kept.unlink(missing_ok=True)
                    except OSError:
                        pass
        print(
            f"warning: unreadable {path}: {exc} ({note}); Politikfelder fall back to not_fetched "
            "until an online build refills it.",
            file=sys.stderr,
        )
        return empty_cache()
    # A record or number list of the wrong shape is dropped, not trusted: it counts as a cache miss.
    vorgaenge = {
        str(k): {**v, "sachgebiet": [] if v.get("sachgebiet") is None else v["sachgebiet"]}
        for k, v in vorgaenge.items()
        if isinstance(v, dict)
        and (v.get("sachgebiet") is None or (
            isinstance(v["sachgebiet"], list) and all(isinstance(label, str) for label in v["sachgebiet"])
        ))
    }
    # Keys in the canonical form the lookups use ("21/06561" is "21/6561"); a cache
    # written before numbers were canonicalised keeps its answers, and two spellings
    # of one number keep the union of theirs (an empty answer never erases another).
    canonical: dict[str, list[str]] = {}
    for key, ids in dokumentnummern.items():
        if not isinstance(ids, list):
            continue
        merged = canonical.setdefault(derive.canonical_document_number(key) or str(key), [])
        merged.extend(str(i) for i in ids if str(i) not in merged)
    return {"version": 1, "vorgaenge": vorgaenge, "dokumentnummern": canonical}


#: Age after which a temporary cache file in the private directory counts as a
#: killed save's leftover (a full save takes well under a second).
STALE_TEMP_SECONDS = 3600


def cache_path(output_dir: Path | str) -> Path:
    return Path(output_dir) / "data" / "dip-vorgang-cache.json"


def save_cache(output_dir: Path | str, cache: Mapping[str, Any]) -> None:
    """Write the cache atomically. The temporary file is staged in the private
    directory beside the published tree (``person_registry.private_dir``), so a
    killed build leaves nothing half-written in ``data/``. Only when that
    directory cannot be made or written (a read-only parent of OUTPUT, a directory
    another user left) or is on another file system, where the rename could not be
    atomic, is it staged next to the cache. A temporary file a killed save left in
    either place is removed once it is older than STALE_TEMP_SECONDS (a younger one
    may be a running build's)."""
    path = cache_path(output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    candidates = [path.parent]
    try:
        private = registry.private_dir(path)
        private.mkdir(mode=0o700, parents=True, exist_ok=True)
        if private.stat().st_dev == path.parent.stat().st_dev:
            candidates.insert(0, private)
    except OSError:
        pass
    pattern = f".{glob.escape(path.name)}.*.tmp"
    for directory in candidates:
        for stale in directory.glob(pattern):
            try:
                if time.time() - stale.stat().st_mtime > STALE_TEMP_SECONDS:
                    stale.unlink(missing_ok=True)
            except OSError:
                pass  # another build's save took it first
    text = json.dumps(cache, ensure_ascii=False, sort_keys=True, indent=1) + "\n"
    for staging in candidates:
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=staging, prefix=f".{path.name}.", suffix=".tmp", delete=False
            ) as handle:
                temporary = Path(handle.name)
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
                try:
                    temporary.chmod(0o644)  # the published cache is world-readable
                except OSError:
                    pass
            temporary.replace(path)
            return
        except OSError:
            if staging == candidates[-1]:
                raise
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass


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


#: A number that resolves to more Vorgänge than this (a Plenarprotokoll or a Sammelübersicht;
#: the real cache has numbers with 69) says nothing about any one of them.
MAX_NUMBER_FANOUT = 10
#: A number naming this many Vorgänge or fewer is "narrow": an Antrag and the EU paper it
#: comments on. A Beschlussempfehlung or Sammelübersicht names more.
NARROW_NUMBER_FANOUT = 2


def _ranked(id_lists: list[list[str]]) -> list[str]:
    """Vorgang ids ranked by how many of the lists name them (ties: first seen)."""
    counts: Counter[str] = Counter()
    first_seen: dict[str, int] = {}
    for ids in id_lists:
        for vorgang_id in ids:
            counts[vorgang_id] += 1
            first_seen.setdefault(vorgang_id, len(first_seen))
    return sorted(counts, key=lambda v: (-counts[v], first_seen[v]))


def _vorgaenge_of_numbers(
    numbers: Iterable[str], cache: Mapping[str, Any], *, narrow_first: bool = False
) -> tuple[list[list[str]], bool]:
    """Tiers of Vorgang ids that Drucksache numbers resolve to, and whether a number is
    missing from the cache. Each tier is ranked by how many numbers name a Vorgang
    (ties: first seen), so the best-supported one leads.

    The last tier holds every number with at most ``MAX_NUMBER_FANOUT`` Vorgänge: a
    huge fan-out says nothing about any one of them. With ``narrow_first`` a tier of
    the narrow numbers (at most ``NARROW_NUMBER_FANOUT`` Vorgänge) comes before it,
    for a vote, whose own Antrag is narrow and whose Beschlussempfehlung is a bundle
    that would pull in Vorgänge the vote is not about."""
    resolved = cache.get("dokumentnummern") or {}
    named: list[list[str]] = []
    missing = False
    for number in numbers:
        if str(number) not in resolved:
            missing = True
            continue
        ids = [str(i) for i in resolved[str(number)] or ()]
        if ids:
            named.append(ids)
    tiers = []
    if narrow_first:
        tiers.append(_ranked([ids for ids in named if len(ids) <= NARROW_NUMBER_FANOUT]))
    tiers.append(_ranked([ids for ids in named if len(ids) <= MAX_NUMBER_FANOUT]))
    return tiers, missing


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


def reads_cited_numbers(vorgang_ids: list[str]) -> bool:
    """Whether a TOP's tags may come from the Drucksache numbers it names: only when
    DIP gives it no Vorgang of its own. A TOP with Vorgänge but no Sachgebiet is not
    the TOP of the Drucksachen it merely cites (a Sammelübersicht of 17 Vorgänge
    cites dozens of unrelated numbers). ``fetch_targets`` asks for a TOP's numbers
    by the same rule, so no TOP number is fetched that the tagging never reads."""
    return not vorgang_ids


def shown(tagging: Tagging) -> list[str]:
    """The tags a page shows. A ``not_fetched`` row is stored as ``untagged`` (every
    vote has a row) but is not "no Politikfeld", so pages show it as nothing at all."""
    tags, source = tagging
    return [] if source == "not_fetched" else tags


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

    if reads_cited_numbers(ids):
        numbers = derive.item_document_numbers(item, wahlperiode)
        (number_ids,), numbers_missing = _vorgaenge_of_numbers(numbers, cache)
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
    numbers: list[str] = []
    for number in vote.get("document_numbers") or ():
        text = derive.canonical_document_number(number)
        if text and text not in numbers and derive.plausible_document_number(text, wahlperiode):
            numbers.append(text)
    return numbers


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
    tiers, missing = _vorgaenge_of_numbers(vote_document_numbers(vote, wahlperiode), cache, narrow_first=True)
    linked = {str(i) for i in linked_vorgang_ids}
    # A tier that holds a Vorgang of the vote's TOP is about that TOP and comes first, narrowed
    # to those Vorgänge; the other tiers follow. The first tier that yields a tag wins.
    ordered = [t for t in tiers if linked & set(t)] + [t for t in tiers if not linked & set(t)]
    for tier in ordered:
        number_ids = [i for i in tier if i in linked] if linked & set(tier) else tier
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
    without Vorgänge of its own (``reads_cited_numbers``), that the cache has not
    resolved, plus the Vorgänge already resolved numbers name.
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
            if not reads_cited_numbers(vorgang_ids):
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
