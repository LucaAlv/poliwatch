"""The Bundestag's MdB-Stammdaten (C1): where the cached zip lives and how it
is read into the records ``derive.mdb_zugehoerigkeiten`` takes.

The file's redistribution terms are still open (docs/plans/c1-seat-counts.md,
D7), so the cache lives in the store's private directory, never in the
published OUTPUT tree. The reader keeps only what the seat counts need: ids,
names, Mandate and Fraktion/Gruppe memberships. The biographies in the file
stay out.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import lzma
import os
import sqlite3
import sys
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import derive
import person_registry as registry
from derive import StammdatenError

URL = "https://www.bundestag.de/resource/blob/472878/MdB-Stammdaten.zip"
CACHE_NAME = "mdb-stammdaten.zip"
#: Beside the cache: the ETag of the cached file (for the conditional GET) and
#: when it was fetched. Kept out of the store so a repersist stays byte-identical.
ETAG_NAME = "mdb-stammdaten.json"
#: The real download is 0.95 MB (plan step 1b); a larger body is refused.
MAX_ZIP_BYTES = 32 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 60
XML_MEMBER = "MDB_STAMMDATEN.XML"
#: The real XML is 15.3 MB (plan S1); a member declared or read larger is
#: refused before it is parsed.
MAX_XML_BYTES = 64 * 1024 * 1024

# The elements each record keeps, by the element that holds them.
_NAME_FIELDS = ("NACHNAME", "VORNAME", "ORTSZUSATZ", "ADEL", "PRAEFIX", "HISTORIE_VON")
_WAHLPERIODE_FIELDS = ("WP", "MDBWP_VON", "MDBWP_BIS")
_INSTITUTION_FIELDS = ("INSART_LANG", "INS_LANG", "MDBINS_VON", "MDBINS_BIS")


@dataclass(frozen=True)
class Stammdaten:
    """One read of the file: the ``MDB`` records, the Stand its ``VERSION``
    stamps (ISO UTC) and the sha256 of the zip."""

    records: list[dict[str, Any]]
    stand: str
    sha256: str


def cache_path(database_path: Path) -> Path:
    """The cached zip of the store at ``database_path``: in its private
    directory, which is never published (``person_registry.private_dir``)."""
    return registry.private_dir(database_path) / CACHE_NAME


def etag_path(database_path: Path) -> Path:
    return registry.private_dir(database_path) / ETAG_NAME


def crosscheck_path(database_path: Path) -> Path:
    return registry.private_dir(database_path) / CROSSCHECK_NAME


def _fields(element: ET.Element, names: tuple[str, ...]) -> dict[str, str | None]:
    return {name: (element.findtext(name) or "").strip() or None for name in names}


def _children(element: ET.Element, container: str) -> list[ET.Element]:
    found = element.find(container)
    return list(found) if found is not None else []


def _ascii_digits(text: str) -> bool:
    # str.isdigit alone accepts superscripts such as "²", which int() rejects.
    return text.isascii() and text.isdigit()


def _xml_bytes(path: Path) -> bytes:
    try:
        with zipfile.ZipFile(path) as archive:
            # The Bundestag's zip carries a macOS resource fork (__MACOSX/) beside
            # the XML; only the top-level member is the file.
            info = next((item for item in archive.infolist() if item.filename == XML_MEMBER), None)
            if info is None:
                raise StammdatenError(f"{path.name}: no {XML_MEMBER} in the zip")
            if info.file_size > MAX_XML_BYTES:
                raise StammdatenError(f"{path.name}: {XML_MEMBER} is larger than {MAX_XML_BYTES} bytes")
            with archive.open(info) as member:
                data = member.read(MAX_XML_BYTES + 1)
    # zlib.error: a corrupt deflate stream; lzma.LZMAError: a corrupt LZMA one
    # (a corrupt bzip2 stream raises OSError); RuntimeError: an encrypted member;
    # NotImplementedError: a compression method zipfile lacks.
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, EOFError, zlib.error, lzma.LZMAError,
            RuntimeError, NotImplementedError) as exc:
        raise StammdatenError(f"{path.name}: not a zip file the Stammdaten can be read from ({exc})") from None
    if len(data) > MAX_XML_BYTES:
        raise StammdatenError(f"{path.name}: {XML_MEMBER} is larger than {MAX_XML_BYTES} bytes")
    return data


def read_zip(path: Path) -> Stammdaten:
    """The Stammdaten in the zip at ``path``. Raises StammdatenError naming the
    cause for a file that is no zip, lacks the XML or a ``VERSION`` stamp, does
    not parse, or holds an ``MDB`` without ``ID`` or a non-numeric ``WP``."""
    data = _xml_bytes(path)
    try:
        root = ET.fromstring(data)
    # LookupError: an XML declaration naming an encoding expat does not know.
    except (ET.ParseError, LookupError) as exc:
        raise StammdatenError(f"{path.name}: {XML_MEMBER} does not parse ({exc})") from None
    if root.tag != "DOCUMENT":
        raise StammdatenError(f"{path.name}: root element {root.tag!r}, not DOCUMENT")
    version = (root.findtext("VERSION") or "").strip()
    try:
        stand = datetime.fromtimestamp(int(version), timezone.utc).isoformat() if _ascii_digits(version) else None
    except (OverflowError, OSError, ValueError):
        stand = None
    if stand is None:
        raise StammdatenError(f"{path.name}: VERSION {version!r} is not a Unix timestamp")
    records = []
    for mdb in root.iter("MDB"):
        mdb_id = (mdb.findtext("ID") or "").strip()
        if not mdb_id:
            raise StammdatenError(f"{path.name}: an MDB without ID")
        periods = []
        for period in _children(mdb, "WAHLPERIODEN"):
            fields = _fields(period, _WAHLPERIODE_FIELDS)
            if not _ascii_digits(fields["WP"] or ""):
                raise StammdatenError(f"{path.name}: MdB {mdb_id}: WP {fields['WP']!r} is not a number")
            fields["INSTITUTIONEN"] = [_fields(item, _INSTITUTION_FIELDS) for item in _children(period, "INSTITUTIONEN")]
            periods.append(fields)
        records.append({
            "ID": mdb_id,
            "NAMEN": [_fields(item, _NAME_FIELDS) for item in _children(mdb, "NAMEN")],
            "WAHLPERIODEN": periods,
        })
    return Stammdaten(
        records=records,
        stand=stand,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def seat_rows(records: list[dict[str, Any]], *, since_wahlperiode: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The ``mdb_zugehoerigkeiten`` and ``party_seats`` rows of ``records``,
    after the size check: what the rebuild stores and what a fetched file must
    pass before it replaces the cache. Raises StammdatenError on a broken rule,
    on records with no Mandat from ``since_wahlperiode`` on, which the size
    check, checking only the Wahlperioden present, would let through empty,
    and on rows the store's tables would refuse (``persist_seat_counts``: a
    Zugehörigkeit or seat row that ends no later than it starts, seats of zero
    or less, a repeated primary key), which would otherwise be cached and then
    fail every later rebuild."""
    zugehoerigkeiten = derive.mdb_zugehoerigkeiten(records, since_wahlperiode=since_wahlperiode)
    keys: set[tuple[str, int, str]] = set()
    for row in zugehoerigkeiten:
        key = (row["mdb_id"], row["wahlperiode"], row["valid_from"])
        if row["valid_until"] is not None and row["valid_until"] <= row["valid_from"]:
            raise StammdatenError(f"MdB {key[0]}, WP {key[1]}: a Zugehörigkeit from {key[2]} ends on {row['valid_until']}")
        if key in keys:
            raise StammdatenError(f"MdB {key[0]}, WP {key[1]}: the Zugehörigkeit from {key[2]} is listed twice")
        keys.add(key)
    seats = derive.party_seats(zugehoerigkeiten)
    derive.check_seat_totals(seats)
    keys = set()
    for row in seats:
        key = (row["party"], row["wahlperiode"], row["valid_from"])
        if row["seats"] <= 0:
            raise StammdatenError(f"WP {key[1]} {key[0]}: {row['seats']} seats from {key[2]}")
        if row["valid_until"] is not None and row["valid_until"] <= row["valid_from"]:
            raise StammdatenError(f"WP {key[1]} {key[0]}: a seat count from {key[2]} ends on {row['valid_until']}")
        if key in keys:
            raise StammdatenError(f"WP {key[1]} {key[0]}: the seat count from {key[2]} is listed twice")
        keys.add(key)
    if not seats:
        raise StammdatenError(f"no Mandat from Wahlperiode {since_wahlperiode} on")
    return zugehoerigkeiten, seats


#: The causes a disagreeing roll-call is filed under, in the order they are
#: tried (``crosscheck``): drift after the Stand (D6), a Zugehörigkeit change
#: dated on the vote's day, members filed under another group (the totals
#: agree), members missing from the roll-call, and anything else.
CAUSES = ("after_stand", "change_on_vote_day", "shift_between_groups", "roll_call_short", "unexplained")
#: The cross-check report, beside the cached file: never published (D9).
CROSSCHECK_NAME = "seat-crosscheck.json"


@dataclass(frozen=True)
class CrossCheck:
    """The stored seat counts against every stored roll-call's group totals.
    ``compared`` counts the roll-calls checked; ``disagreements`` holds one row
    per roll-call and group whose figures differ, with the roll-call's cause.
    Roll-calls with nothing to compare are listed by id instead: no seat count
    on their date, no group totals, or a group the roll-call could not name
    (``Unbekannt``, plan F3)."""

    stand: str
    sha256: str
    compared: int
    disagreements: list[dict[str, Any]]
    without_seat_count: list[str]
    without_totals: list[str]
    with_unbekannt: list[str]


def _cause(differences: dict[str, int], changes: dict[str, int]) -> str:
    """How a roll-call's differences (roll-call minus Stammdaten, per group) are
    filed, by their shape, first fit wins. ``changes`` counts the Zugehörigkeiten
    of each group that start or end on the roll-call's day: a change explains a
    group's difference only when there are as many as the difference is large,
    so an unrelated Nachrücker that day explains nothing."""
    if all(changes.get(party, 0) >= abs(difference) for party, difference in differences.items()):
        return "change_on_vote_day"
    if sum(differences.values()) == 0:
        return "shift_between_groups"
    if all(difference <= 0 for difference in differences.values()):
        return "roll_call_short"
    return "unexplained"


def crosscheck(conn: sqlite3.Connection) -> CrossCheck | None:
    """Each roll-call's ``vote_fractions.total_count`` per group against that
    group's ``party_seats`` on the roll-call's date, in the roll-call's
    Wahlperiode (C1 plan step 5). Roll-calls go in date and id order. None when
    the store holds no Stammdaten."""
    provenance = conn.execute("SELECT stand, sha256 FROM mdb_stammdaten_stand").fetchone()
    if provenance is None:
        return None
    # The Stand is a UTC instant; the file covers the whole of its day.
    stand_day = datetime.fromisoformat(provenance[0]).astimezone(timezone.utc).date().isoformat()
    totals: dict[str, dict[str, int]] = {}
    for vote_id, party, total in conn.execute(
        "SELECT vf.vote_id, p.name, vf.total_count FROM vote_fractions vf JOIN parties p ON p.id = vf.party_id"
    ):
        totals.setdefault(vote_id, {})[party] = total
    votes = conn.execute(
        """SELECT v.id, v.date, CAST(substr(pr.document_number, 1, instr(pr.document_number, '/') - 1) AS INTEGER)
           FROM votes v LEFT JOIN protocols pr ON pr.id = v.protocol_id
           ORDER BY v.date, CAST(v.id AS INTEGER), v.id"""
    ).fetchall()
    compared, disagreements = 0, []
    without_seat_count, without_totals, with_unbekannt = [], [], []
    for vote_id, day, protocol_wahlperiode in votes:
        listed = totals.get(vote_id)
        if not listed:
            without_totals.append(vote_id)
            continue
        if "Unbekannt" in listed:
            with_unbekannt.append(vote_id)
            continue
        # On the day one Bundestag hands over to the next both may have seat rows;
        # the vote's protocol says which one it belongs to.
        by_wahlperiode: dict[int, dict[str, int]] = {}
        for wahlperiode, party, count in conn.execute(
            """SELECT ps.wahlperiode, p.name, ps.seats FROM party_seats ps JOIN parties p ON p.id = ps.party_id
               WHERE ps.valid_from <= ? AND (ps.valid_until IS NULL OR ? < ps.valid_until)""",
            (day, day),
        ):
            by_wahlperiode.setdefault(wahlperiode, {})[party] = count
        if protocol_wahlperiode:
            by_wahlperiode = {protocol_wahlperiode: by_wahlperiode.get(protocol_wahlperiode, {})}
        if len(by_wahlperiode) != 1 or not next(iter(by_wahlperiode.values())):
            without_seat_count.append(vote_id)
            continue
        [(wahlperiode, seats)] = by_wahlperiode.items()
        compared += 1
        differences = {party: listed.get(party, 0) - seats.get(party, 0)
                       for party in sorted(seats.keys() | listed.keys())
                       if listed.get(party, 0) != seats.get(party, 0)}
        if not differences:
            continue
        if day > stand_day:
            cause = "after_stand"
        else:
            changes = dict(conn.execute(
                """SELECT p.name, COUNT(*) FROM mdb_zugehoerigkeiten z JOIN parties p ON p.id = z.party_id
                   WHERE z.wahlperiode = ? AND (z.valid_from = ? OR z.valid_until = ?) GROUP BY p.name""",
                (wahlperiode, day, day),
            ))
            cause = _cause(differences, changes)
        disagreements += [
            {"vote_id": vote_id, "date": day, "wahlperiode": wahlperiode, "party": party,
             "stammdaten_seats": seats.get(party, 0), "roll_call_total": listed.get(party, 0),
             "difference": difference, "cause": cause}
            for party, difference in differences.items()
        ]
    return CrossCheck(stand=provenance[0], sha256=provenance[1], compared=compared, disagreements=disagreements,
                      without_seat_count=without_seat_count, without_totals=without_totals, with_unbekannt=with_unbekannt)


def _stand_day(stand: str) -> str:
    return datetime.fromisoformat(stand).astimezone(timezone.utc).strftime("%d.%m.%Y")


def _download(etag: str | None) -> tuple[bytes, str | None] | None:
    """GET the file, conditionally on ``etag``: its body and ETag, or None on
    304 Not Modified. Raises StammdatenError for a body over MAX_ZIP_BYTES."""
    headers = {"Accept": "application/zip"}
    if etag:
        headers["If-None-Match"] = etag
    try:
        with urllib.request.urlopen(urllib.request.Request(URL, headers=headers), timeout=FETCH_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_ZIP_BYTES + 1)
            new_etag = response.headers.get("ETag")
    except urllib.error.HTTPError as exc:
        if exc.fp is not None:
            exc.close()
        # urllib raises on 304 like on any non-2xx status.
        if exc.code == 304:
            return None
        raise
    if len(body) > MAX_ZIP_BYTES:
        raise StammdatenError(f"the download is larger than {MAX_ZIP_BYTES} bytes")
    return body, new_etag


def refresh(database_path: Path, *, since_wahlperiode: int) -> None:
    """``--enrich mdb-stammdaten``: fetch the file into the store's cache when
    it changed. A download replaces the cache only after it passes the checks
    the rebuild applies (``read_zip``, ``seat_rows``); a failed fetch or check
    keeps the previous file and warns, so a Bundestag outage never empties the
    seat tables. Every outcome is one stderr line."""
    path = cache_path(database_path)
    sidecar = etag_path(database_path)
    previous = None
    if path.is_file():
        try:
            previous = read_zip(path)
        except StammdatenError:
            previous = None  # an unreadable cache is replaced, never offered for a 304
    try:
        etag = json.loads(sidecar.read_text(encoding="utf-8")).get("etag") if previous else None
    except (OSError, ValueError, AttributeError):
        etag = None
    kept = (f"keeping the cached file (Stand {_stand_day(previous.stand)})" if previous
            else "no cached file: keine Sitzzahlen until a fetch succeeds")
    try:
        answer = _download(etag if isinstance(etag, str) else None)
    except (StammdatenError, urllib.error.URLError, OSError, http.client.HTTPException) as exc:
        print(f"warning: [stammdaten] fetching {URL} failed ({exc}); {kept}", file=sys.stderr)
        return
    if answer is None:
        if previous is None:  # no If-None-Match was sent, so a 304 names no file
            print(f"warning: [stammdaten] {URL} answered 304 Not Modified to an unconditional request; {kept}", file=sys.stderr)
        else:
            print(f"stammdaten: unchanged (Stand {_stand_day(previous.stand)})", file=sys.stderr)
        return
    body, new_etag = answer
    temp: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # A refresh killed while writing leaves its temp file; refreshes run one
        # per build, before the staged rebuild, so any still here is stale.
        for stale in path.parent.glob(".mdb-stammdaten.*.tmp"):
            stale.unlink(missing_ok=True)
        handle, temp_name = tempfile.mkstemp(prefix=".mdb-stammdaten.", suffix=".tmp", dir=path.parent)
        temp = Path(temp_name)
        with os.fdopen(handle, "wb") as out:
            out.write(body)
        try:
            fetched = read_zip(temp)
            seat_rows(fetched.records, since_wahlperiode=since_wahlperiode)
        except StammdatenError as exc:
            print(f"warning: [stammdaten] the downloaded file fails the seat checks ({exc}); {kept}", file=sys.stderr)
            return
        os.replace(temp, path)
        # Written after the file: a crash in between leaves the new file with the
        # old ETag, which costs one full download next time, never a stale 304.
        sidecar.write_text(json.dumps({"etag": new_etag, "fetched_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}),
                           encoding="utf-8")
    except OSError as exc:
        print(f"warning: [stammdaten] the downloaded file could not be cached ({exc}); {kept}", file=sys.stderr)
        return
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)
    print(f"stammdaten: fetched, Stand {_stand_day(fetched.stand)}, sha256 {fetched.sha256[:12]}…", file=sys.stderr)
