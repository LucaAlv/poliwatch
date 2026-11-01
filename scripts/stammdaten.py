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
import os
import sys
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
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


def _fields(element: ET.Element, names: tuple[str, ...]) -> dict[str, str | None]:
    return {name: (element.findtext(name) or "").strip() or None for name in names}


def _children(element: ET.Element, container: str) -> list[ET.Element]:
    found = element.find(container)
    return list(found) if found is not None else []


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
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, EOFError) as exc:
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
    except ET.ParseError as exc:
        raise StammdatenError(f"{path.name}: {XML_MEMBER} does not parse ({exc})") from None
    if root.tag != "DOCUMENT":
        raise StammdatenError(f"{path.name}: root element {root.tag!r}, not DOCUMENT")
    version = (root.findtext("VERSION") or "").strip()
    if not version.isdigit():
        raise StammdatenError(f"{path.name}: VERSION {version!r} is not a Unix timestamp")
    records = []
    for mdb in root.iter("MDB"):
        mdb_id = (mdb.findtext("ID") or "").strip()
        if not mdb_id:
            raise StammdatenError(f"{path.name}: an MDB without ID")
        periods = []
        for period in _children(mdb, "WAHLPERIODEN"):
            fields = _fields(period, _WAHLPERIODE_FIELDS)
            if not (fields["WP"] or "").isdigit():
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
        stand=datetime.fromtimestamp(int(version), timezone.utc).isoformat(),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def seat_rows(records: list[dict[str, Any]], *, since_wahlperiode: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The ``mdb_zugehoerigkeiten`` and ``party_seats`` rows of ``records``,
    after the size check: what the rebuild stores and what a fetched file must
    pass before it replaces the cache. Raises StammdatenError on a broken rule,
    and on records with no Mandat from ``since_wahlperiode`` on, which the size
    check, checking only the Wahlperioden present, would let through empty."""
    zugehoerigkeiten = derive.mdb_zugehoerigkeiten(records, since_wahlperiode=since_wahlperiode)
    seats = derive.party_seats(zugehoerigkeiten)
    derive.check_seat_totals(seats)
    if not seats:
        raise StammdatenError(f"no Mandat from Wahlperiode {since_wahlperiode} on")
    return zugehoerigkeiten, seats


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
