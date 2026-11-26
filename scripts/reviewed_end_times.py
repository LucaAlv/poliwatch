"""Sitting end times corrected from the printed Plenarprotokoll
(``scripts/reviewed_end_times.json``, docs/plans/cut-protocols.md D2 and step 3b).

The XML head's ``sitzung-ende-uhrzeit`` is what ``laengste-sitzung`` reads. For
four sittings it differs from the "(Schluss: …)" the final PDF prints, by one or
two minutes. One entry per such sitting: ``sitting`` (WP/NR), ``xml_end`` (the
head as the cached XML prints it), ``end`` (the PDF's time), both HH:MM,
``pdf_url``, ``pdf_md5`` (the md5 of the PDF read, DIP's ``pdf_hash``),
``pdf_page`` (page of the file, not the printed page number) and ``reason``.

Persist writes ``end`` to ``protocols.sitting_end_corrected`` and leaves
``xml_header_json`` as the XML prints it. An entry whose ``xml_end`` the report no
longer carries stops the run (the Bundestag may have replaced the file): it is
then deleted or read again. A malformed file raises ``ReviewedEndTimesError``,
which is no ``ValueError``, so no caller takes it for a bad source file.
"""

from __future__ import annotations

import contextlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

PATH = Path(__file__).resolve().with_name("reviewed_end_times.json")
ENTRY_KEYS = frozenset({"sitting", "xml_end", "end", "pdf_url", "pdf_md5", "pdf_page", "reason"})
_SITTING_RE = re.compile(r"\d{2}/\d{1,3}")
_TIME_RE = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")
_MD5_RE = re.compile(r"[0-9a-f]{32}")
_PDF_URL_RE = re.compile(r"https://dserver\.bundestag\.de/btp/\d{2}/\d{5}\.pdf")
_TEXT_LIMIT = 2000


class ReviewedEndTimesError(Exception):
    """The list is missing or malformed, or an entry no longer fits its sitting's XML. Stops the run."""


@dataclass(frozen=True)
class Entry:
    sitting: str
    xml_end: str
    end: str
    pdf_url: str
    pdf_md5: str
    pdf_page: int
    reason: str


def check(data: Any, where: str = PATH.name) -> list[Entry]:
    """The entries of a parsed file, in file order; refuses anything malformed."""
    if not isinstance(data, dict) or set(data) != {"entries"} or not isinstance(data["entries"], list):
        raise ReviewedEndTimesError(f'{where} must be an object with exactly one key, "entries", an array')
    entries: list[Entry] = []
    seen: set[str] = set()
    for position, raw in enumerate(data["entries"], 1):
        label = f"{where} entry {position}"
        if not isinstance(raw, dict) or set(raw) != ENTRY_KEYS:
            raise ReviewedEndTimesError(f"{label} must have exactly the keys {', '.join(sorted(ENTRY_KEYS))}")
        texts = {}
        for name in ("sitting", "xml_end", "end", "pdf_url", "pdf_md5", "reason"):
            value = raw[name]
            if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > _TEXT_LIMIT:
                raise ReviewedEndTimesError(f"{label}: {name} must be a non-empty string without surrounding whitespace")
            texts[name] = value
        if not _SITTING_RE.fullmatch(texts["sitting"]):
            raise ReviewedEndTimesError(f"{label}: sitting {texts['sitting']!r} is not WP/NR, e.g. 19/55")
        for name in ("xml_end", "end"):
            if not _TIME_RE.fullmatch(texts[name]):
                raise ReviewedEndTimesError(f"{label}: {name} {texts[name]!r} is not HH:MM")
        if texts["end"] == texts["xml_end"]:
            raise ReviewedEndTimesError(f"{label}: end equals xml_end; an entry that corrects nothing is deleted")
        if not _PDF_URL_RE.fullmatch(texts["pdf_url"]):
            raise ReviewedEndTimesError(f"{label}: pdf_url {texts['pdf_url']!r} is not a Plenarprotokoll PDF on dserver.bundestag.de")
        if not _MD5_RE.fullmatch(texts["pdf_md5"]):
            raise ReviewedEndTimesError(f"{label}: pdf_md5 must be 32 lower-case hex digits")
        page = raw["pdf_page"]
        if not isinstance(page, int) or isinstance(page, bool) or not 0 < page < 10**4:
            raise ReviewedEndTimesError(f"{label}: pdf_page must be a page number of the file")
        if texts["sitting"] in seen:
            raise ReviewedEndTimesError(f"{label}: {texts['sitting']} is listed twice")
        seen.add(texts["sitting"])
        entries.append(Entry(texts["sitting"], texts["xml_end"], texts["end"], texts["pdf_url"], texts["pdf_md5"],
                             page, texts["reason"]))
    return entries


def load(path: Path = PATH) -> list[Entry]:
    """Every entry of the file, checked whole."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ReviewedEndTimesError(f"{path} is missing; it is checked in, restore it "
                                    "(git checkout -- scripts/reviewed_end_times.json)") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ReviewedEndTimesError(f"{path} cannot be read ({exc})") from exc
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise ReviewedEndTimesError(f"{path.name} is not valid JSON ({exc})") from exc
    return check(data, path.name)


_cache: dict[Path, list[Entry]] = {}
#: Entries ``use`` installed in place of the shipped file (tests), or None.
_in_use: list[Entry] | None = None


def use(entries: Iterable[Entry] | None) -> None:
    """Make ``entries`` the ones in force; ``None`` goes back to the shipped file.
    For tests: synthetic reports reuse real sitting numbers."""
    global _in_use
    _in_use = None if entries is None else list(entries)


@contextlib.contextmanager
def using(entries: Iterable[Entry]) -> Iterator[None]:
    """``use(entries)`` for the duration of a ``with`` block, then the entries before it."""
    global _in_use
    before = _in_use
    use(entries)
    try:
        yield
    finally:
        _in_use = before


def in_force() -> list[Entry]:
    """The entries the run applies: those ``use`` installed, else the shipped
    file, read and checked once per process."""
    if _in_use is not None:
        return _in_use
    if PATH not in _cache:
        _cache[PATH] = load(PATH)
    return _cache[PATH]


def for_sitting(sitting: str) -> Entry | None:
    """The entry of ``sitting`` (WP/NR), or None."""
    return next((entry for entry in in_force() if entry.sitting == sitting), None)
