"""What an Antrag demands, quoted from its own text.

DIP writes no abstract for most opposition Anträge, so a vote on one has no
"Worum es geht". Its Drucksache says it in the Antrag's own words: the part that
opens "Der (Deutsche) Bundestag fordert die Bundesregierung auf". A Drucksache
is an amtliches Werk (§ 5 UrhG), so the vote panel quotes that part verbatim,
with its source, where the Vorgang has no abstract (plan
docs/plans/b4-extractive-antrag.md).

Inputs are two parts of a separate cache (``data/dip-drucksache-text-cache.json.gz``,
filled by the online build): ``nummern``, the DIP metadata of each Bundestag
Drucksache number a vote names, and ``texte``, the full DIP text of the Anträge
among them. In memory the cache rides in the Vorgang cache under ``CACHE_KEY``,
so it reaches persist and render wherever the Vorgang cache does. The passage is
derived at persist and render time and never written into a report, so a change
to ``extract_forderung`` reaches the store with ``--offline --repersist``.

This module does no network I/O. Its file access is ``load_cache`` and ``save_cache``.
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, NamedTuple, get_args

import derive
import dip_text
import politikfelder

#: Bump when a change to ``extract_forderung`` can change a stored passage; a
#: store persisted by another version is refused until it is re-persisted.
EXTRACTOR_VERSION = 1
#: Where the Drucksache cache sits in the in-memory Vorgang cache.
CACHE_KEY = "drucksachen"
CACHE_FILENAME = "dip-drucksache-text-cache.json.gz"
#: The Drucksache types whose demands are quoted.
PASSAGE_TYPES: tuple[str, ...] = ("Antrag", "Entschließungsantrag")
#: Text characters read; longer texts are no Antrag worth quoting and would only
#: cost regex time. A long Antrag on the reference sample runs to about 60,000.
MAX_TEXT_CHARS = 400_000
#: A passage outside these bounds is a misread, not a quote.
MIN_PASSAGE_CHARS = 40
MAX_PASSAGE_CHARS = 20_000

#: The state of one document's passage (``documents.forderung_state``).
#: ``extracted``: text fetched, passage found; ``no_passage``: text fetched, no
#: passage found (or an empty text); ``not_fetched``: the text is not in the cache.
DocumentState = Literal["extracted", "no_passage", "not_fetched"]
DOCUMENT_STATES: tuple[str, ...] = get_args(DocumentState)
#: The state of a vote's passages (``votes.passage_state``): ``extracted``, at
#: least one is shown; ``no_passage``, every candidate was read and none has a
#: passage; ``not_fetched``, a candidate's metadata or text is missing;
#: ``not_applicable``, every Vorgang the vote is about has an abstract, or none of
#: the vote's Drucksachen is an Antrag of such a Vorgang.
PassageState = Literal["extracted", "no_passage", "not_fetched", "not_applicable"]
PASSAGE_STATES: tuple[str, ...] = get_args(PassageState)


class Forderung(NamedTuple):
    """The quoted passage: its opening clause and its listed demands, each a
    verbatim paragraph with its own list marker ("1.", "a)", "–")."""

    opening: str
    demands: tuple[str, ...]

    def text(self) -> str:
        return "\n\n".join((self.opening, *self.demands))


class Passage(NamedTuple):
    """One Antrag a vote's context quotes from."""

    number: str
    drucksache_id: str
    vorgang_id: str
    drucksachetyp: str
    titel: str
    urheber: tuple[str, ...]
    pdf_url: str
    state: DocumentState
    forderung: Forderung | None


class VotePassages(NamedTuple):
    """``vote_passages``'s answer: the passages per context Vorgang, and its state."""

    by_vorgang: dict[str, list[Passage]]
    state: PassageState


# --- extraction -------------------------------------------------------------

# Running heads and page numbers of a Drucksache's PDF layer: "Deutscher Bundestag –
# 21. Wahlperiode – 3 – Drucksache 21/2234", "Drucksache 21/2234 – 2 – Deutscher …",
# a bare "– 3 –", and the advance copy's "Vorabfassung – wird durch die lektorierte
# Fassung ersetzt." banner.
_LAYOUT_LINE = re.compile(
    r"^\s*(?:"
    r"(?:Deutscher\s+Bundestag\s*[–-]\s*\d{1,2}\.\s*Wahlperiode|Drucksache\s+\d{1,2}/\d{1,6})"
    r"(?:\s*[–-]\s*\d{1,4}\s*[–-]\s*(?:Deutscher\s+Bundestag\s*[–-]\s*\d{1,2}\.\s*Wahlperiode|Drucksache\s+\d{1,2}/\d{1,6}))?"
    r"|[–-]\s*\d{1,4}\s*[–-]"
    r"|Vorabfassung\s*[–-]\s*wird\s+durch\s+die\s+lektorierte\s+Fassung\s+ersetzt\.?"
    r")\s*$"
)
def _breakable(word: str) -> str:
    """A pattern for ``word`` that a line-end break hyphen may split anywhere."""
    return "(?:-[ \t]*\n[ \t]*)?".join(re.escape(char) for char in word)


def _words(*words: str) -> str:
    return r"[ \t\n]+".join(_breakable(word) for word in words)


# The operative part. "II." may precede it; older Anträge open the whole motion with
# "Der Bundestag wolle beschließen:" and still say "fordert … auf" in section II.
_ANCHOR = re.compile(
    r"(?:^|\n)[ \t]*(?:[IVX]{1,4}\.[ \t]*)?("
    + _words("Der") + r"[ \t\n]+(?:" + _words("Deutsche") + r"[ \t\n]+)?"
    + _words("Bundestag", "fordert", "die", "Bundesregierung")
    + r"[ \t\n]+(?:(?:daher|deshalb|darüber[ \t\n]+hinaus|insbesondere|ferner)[ \t\n]+)?auf\b)"
)
# Where the operative part ends: the date line, the Begründung, or the next section.
_END = re.compile(r"\n[ \t]*(?:Berlin,[ \t]+den\b|Begründung\b|(?:III|IV|V|VI)\.[ \t]+\S)")
# A list item at the start of a line: "1.", "12.", "a)", "aa)", "–", "-", "•".
_ITEM = re.compile(r"^(?:\d{1,2}\.|[a-z]{1,2}\)|[–•-])[ \t]+\S")
# A word a line-end hyphen leaves standing ("Bundes- und Landesrecht").
_KEEPS_HYPHEN = frozenset({"und", "oder", "bzw.", "sowie", "bis", "als", "noch", "wie"})


def _join(previous: str, line: str) -> str:
    """``line`` appended to the wrapped paragraph ``previous``. A line-end hyphen
    before a lower-case word is a break hyphen and goes, unless the word is one a
    truncated compound stands before; before a capital it stays (E-Mobilität)."""
    if previous.endswith("-") and len(previous) > 1 and previous[-2].isalpha():
        word = line.split(None, 1)[0] if line.split() else ""
        if word[:1].islower() and word not in _KEEPS_HYPHEN:
            return previous[:-1] + line
        if word[:1].isupper():
            return previous + line
    return f"{previous} {line}"


def extract_forderung(text: Any) -> Forderung | None:
    """The operative part of an Antrag, or None when it cannot be found with
    confidence (no anchor, a passage outside the bounds, a text too long).

    Only layout is undone: running heads and page numbers are dropped, wrapped
    lines joined, break hyphens removed. Every word stays as the Drucksache prints
    it, in its order."""
    if not isinstance(text, str) or not text or len(text) > MAX_TEXT_CHARS:
        return None
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("­", "").replace(" ", " ")
    text = "\n".join(line for line in text.split("\n") if not _LAYOUT_LINE.match(line))
    anchor = _ANCHOR.search(text)
    if anchor is None:
        return None
    end = _END.search(text, anchor.end())
    body = text[anchor.start(1): end.start() if end else len(text)]
    paragraphs: list[str] = []
    for raw in body.split("\n"):
        line = " ".join(raw.split())
        if not line:
            continue
        if not paragraphs or _ITEM.match(line):
            paragraphs.append(line)
        else:
            paragraphs[-1] = _join(paragraphs[-1], line)
    opening, demands = paragraphs[0], tuple(paragraphs[1:])
    forderung = Forderung(opening, demands)
    size = len(forderung.text())
    if not MIN_PASSAGE_CHARS <= size <= MAX_PASSAGE_CHARS:
        return None
    if not demands and not opening.endswith((".", ";")):
        return None
    return forderung


def forderung_teaser(forderung: Forderung, budget: int = dip_text.CONTEXT_TEASER) -> tuple[list[str], list[str]]:
    """The paragraphs shown inline and those folded away. Inline: the opening and
    as many whole demands as fit ``budget`` characters, at least the first; a
    demand is never cut."""
    shown = [forderung.opening]
    size = len(forderung.opening)
    rest = list(forderung.demands)
    while rest and (len(shown) == 1 or size + len(rest[0]) <= budget):
        size += len(rest[0])
        shown.append(rest.pop(0))
    return shown, rest


# --- which Drucksachen ------------------------------------------------------


def empty_cache() -> dict[str, Any]:
    return {"version": 1, "nummern": {}, "texte": {}}


def drucksache_record(document: Mapping[str, Any]) -> dict[str, Any] | None:
    """What the cache keeps of a DIP ``/drucksache`` record, or None for one
    without an id or number."""
    drucksache_id = document.get("id")
    number = derive.canonical_document_number(document.get("dokumentnummer"))
    if type(drucksache_id) not in (str, int) or not str(drucksache_id).strip() or not number:
        return None
    urheber = []
    for entry in document.get("urheber") or ():
        if isinstance(entry, Mapping):
            name = entry.get("titel") or entry.get("bezeichnung")
            if isinstance(name, str) and name.strip():
                urheber.append(" ".join(name.split()))
    vorgang_ids = [
        str(ref.get("id")) for ref in document.get("vorgangsbezug") or ()
        if isinstance(ref, Mapping) and type(ref.get("id")) in (str, int)
    ]
    fundstelle = document.get("fundstelle") if isinstance(document.get("fundstelle"), Mapping) else {}
    return {
        "id": str(drucksache_id).strip(),
        "dokumentnummer": number,
        "herausgeber": document.get("herausgeber"),
        "drucksachetyp": document.get("drucksachetyp"),
        "titel": document.get("titel"),
        "datum": document.get("datum"),
        "urheber": urheber,
        "vorgang_ids": vorgang_ids,
        "pdf_url": fundstelle.get("pdf_url"),
        "aktualisiert": document.get("aktualisiert"),
    }


def _drucksachen(vorgang_cache: Mapping[str, Any]) -> Mapping[str, Any]:
    return vorgang_cache.get(CACHE_KEY) or empty_cache()


def _abstractless_vorgaenge(context: politikfelder.VoteContext, vorgang_cache: Mapping[str, Any]) -> list[str]:
    """The context Vorgänge whose cached record has no abstract to show. A Vorgang
    not in the cache is left out: its block already says it was not fetched."""
    records = vorgang_cache.get("vorgaenge") or {}
    return [
        vorgang_id for vorgang_id in context.vorgang_ids
        if vorgang_id in records and not dip_text.abstract_text(records[vorgang_id].get("abstract"))
    ]


def _number_record(records: Any) -> Mapping[str, Any] | None:
    """The Bundestag record of a number: a reprint carries the same number, so the
    latest by date, then by id, stands for it."""
    usable = [r for r in records or () if isinstance(r, Mapping) and r.get("herausgeber") in (None, "BT")]
    if not usable:
        return None
    return max(usable, key=lambda r: (str(r.get("datum") or ""), str(r.get("id"))))


def vote_passages(
    vote: Mapping[str, Any],
    context: politikfelder.VoteContext,
    vorgang_cache: Mapping[str, Any],
    *,
    wahlperiode: str = "",
) -> VotePassages:
    """The Anträge a vote's "Worum es geht" quotes, per context Vorgang.

    Only Vorgänge without an abstract are quoted for, and only from the vote's own
    Drucksache numbers: a number counts when DIP types it as an Antrag or
    Entschließungsantrag and links it to one of those Vorgänge, so a bundled
    Beschlussempfehlung cannot quote a neighbouring Antrag."""
    targets = _abstractless_vorgaenge(context, vorgang_cache)
    if not targets:
        return VotePassages({}, "not_applicable")
    cache = _drucksachen(vorgang_cache)
    nummern = cache.get("nummern") or {}
    texte = cache.get("texte") or {}
    missing = False
    by_vorgang: dict[str, list[Passage]] = {}
    for number in politikfelder.vote_document_numbers(vote, wahlperiode):
        if number not in nummern:
            missing = True
            continue
        record = _number_record(nummern[number])
        if record is None or record.get("drucksachetyp") not in PASSAGE_TYPES:
            continue
        vorgang_id = next((v for v in targets if v in (record.get("vorgang_ids") or ())), None)
        if vorgang_id is None:
            continue
        entry = texte.get(str(record["id"]))
        if entry is None:
            state, forderung = "not_fetched", None
        else:
            forderung = extract_forderung(entry.get("text"))
            state = "extracted" if forderung else "no_passage"
        by_vorgang.setdefault(vorgang_id, []).append(Passage(
            number=number,
            drucksache_id=str(record["id"]),
            vorgang_id=vorgang_id,
            drucksachetyp=str(record.get("drucksachetyp")),
            titel=" ".join(str(record.get("titel") or "").split()),
            urheber=tuple(record.get("urheber") or ()),
            pdf_url=str(record.get("pdf_url") or ""),
            state=state,
            forderung=forderung,
        ))
    passages = [p for group in by_vorgang.values() for p in group]
    if any(p.state == "extracted" for p in passages):
        state: PassageState = "extracted"
    elif missing or any(p.state == "not_fetched" for p in passages):
        state = "not_fetched"
    elif passages:
        state = "no_passage"
    else:
        state = "not_applicable"
    return VotePassages(by_vorgang, state)


def report_vote_passages(
    report: Mapping[str, Any],
    vorgang_cache: Mapping[str, Any],
    contexts: Mapping[str, politikfelder.VoteContext] | None = None,
) -> dict[str, VotePassages]:
    """``vote_passages`` of every vote of one sitting report, keyed by
    ``politikfelder.vote_key``. Persist and render both read it, with the same
    cache, so the stored passages and the panels agree."""
    if contexts is None:
        contexts = politikfelder.report_vote_vorgaenge(report, vorgang_cache)
    wahlperiode = derive.report_wahlperiode(report)
    return {
        politikfelder.vote_key(vote): vote_passages(
            vote, contexts[politikfelder.vote_key(vote)], vorgang_cache, wahlperiode=wahlperiode
        )
        for _item, vote in derive.iter_report_votes(report)
    }


def fetch_targets(reports: Iterable[Mapping[str, Any]], vorgang_cache: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """What an online build still has to fetch: (Drucksache numbers without
    metadata, Drucksache ids without text). Only votes with a Vorgang to quote for
    ask; numbers come first, since only their metadata says which ids are Anträge,
    so the build calls this again after fetching them."""
    cache = _drucksachen(vorgang_cache)
    nummern = cache.get("nummern") or {}
    texte = cache.get("texte") or {}
    numbers: list[str] = []
    ids: list[str] = []
    for report in reports:
        wahlperiode = derive.report_wahlperiode(report)
        contexts = politikfelder.report_vote_vorgaenge(report, vorgang_cache)
        for _item, vote in derive.iter_report_votes(report):
            context = contexts[politikfelder.vote_key(vote)]
            if not _abstractless_vorgaenge(context, vorgang_cache):
                continue
            for number in politikfelder.vote_document_numbers(vote, wahlperiode):
                if number not in nummern and number not in numbers:
                    numbers.append(number)
            passages = vote_passages(vote, context, vorgang_cache, wahlperiode=wahlperiode)
            for group in passages.by_vorgang.values():
                for passage in group:
                    if passage.drucksache_id not in texte and passage.drucksache_id not in ids:
                        ids.append(passage.drucksache_id)
    return numbers, ids


# --- the cache file ---------------------------------------------------------


def cache_path(output_dir: Path | str) -> Path:
    return Path(output_dir) / "data" / CACHE_FILENAME


def load_cache(output_dir: Path | str) -> dict[str, Any]:
    """The Drucksache cache; empty when there is none yet. An unreadable or
    wrongly shaped file is left in place, warned about, and read as empty, so
    passages fall back to ``not_fetched`` (and the replay guard refuses to lose
    known ones) until an online build refills it."""
    path = cache_path(output_dir)
    try:
        data = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError(f"unsupported cache version {data.get('version') if isinstance(data, dict) else None!r}")
        nummern, texte = data.get("nummern"), data.get("texte")
        if not isinstance(nummern, dict) or not isinstance(texte, dict):
            raise ValueError("nummern and texte must be objects")
    except FileNotFoundError:
        return empty_cache()
    except (OSError, ValueError, EOFError, gzip.BadGzipFile) as exc:
        print(f"warning: unreadable {path}: {exc}; Antrag passages fall back to not_fetched.", file=sys.stderr)
        return empty_cache()
    return {
        "version": 1,
        "nummern": {
            str(number): [r for r in records if isinstance(r, dict)]
            for number, records in nummern.items() if isinstance(records, list)
        },
        "texte": {
            str(key): {"text": entry.get("text") if isinstance(entry.get("text"), str) else ""}
            for key, entry in texte.items() if isinstance(entry, dict)
        },
    }


def save_cache(output_dir: Path | str, cache: Mapping[str, Any]) -> None:
    """Write the cache atomically, byte-identical for identical content: sorted
    keys and a gzip header without time or name, so an unchanged replay leaves the
    file as it was."""
    payload = {"version": 1, "nummern": cache.get("nummern") or {}, "texte": cache.get("texte") or {}}
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=0) + "\n"
    data = gzip.compress(text.encode("utf-8"), compresslevel=6, mtime=0)
    politikfelder.write_atomic(cache_path(output_dir), data)
