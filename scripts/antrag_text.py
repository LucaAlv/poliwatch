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

import functools
import gzip
import json
import re
import sys
import zlib
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, NamedTuple, get_args

import derive
import dip_text
import politikfelder

#: Bump when a change to ``extract_forderung`` can change a stored passage; a
#: store persisted by another version is refused until it is re-persisted.
EXTRACTOR_VERSION = 6
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
    """``vote_passages``'s answer: the passages per context Vorgang, and its state.
    ``metadata_missing``: one of the vote's Drucksache numbers has no metadata in
    the cache, so any Vorgang block without a quote may still be missing one."""

    by_vorgang: dict[str, list[Passage]]
    state: PassageState
    metadata_missing: bool = False


# --- extraction -------------------------------------------------------------

# Running heads and page numbers of a Drucksache's PDF layer: "Deutscher Bundestag –
# 21. Wahlperiode – 3 – Drucksache 21/2234", "Drucksache 21/2234 – 2 – Deutscher …",
# a bare "Deutscher Bundestag – 21. Wahlperiode", a bare "– 3 –", and the advance
# copy's "Vorabfassung – wird durch die lektorierte Fassung ersetzt." banner. A bare
# "Drucksache 21/2234" is a running head only when it names the Drucksache's own
# number (``_layout_lines``): a line naming another one is content.
_HEAD = r"(?:Deutscher\s+Bundestag\s*[–-]\s*\d{1,2}\.\s*Wahlperiode|Drucksache\s+\d{1,2}/\d{1,6})"
_LAYOUT_LINE = re.compile(
    r"^\s*(?:"
    r"Deutscher\s+Bundestag\s*[–-]\s*\d{1,2}\.\s*Wahlperiode"
    r"|" + _HEAD + r"\s*[–-]\s*\d{1,4}\s*[–-]\s*" + _HEAD +
    r"|[–-]\s*\d{1,4}\s*[–-]"
    # DIP's text repeats the first-page head at a page break (21/5780):
    # "Deutscher Bundestag Drucksache 21/5780", then "21. Wahlperiode 05.05.2026".
    r"|Deutscher\s+Bundestag\s+Drucksache\s+\d{1,2}/\d{1,6}"
    r"|\d{1,2}\.\s*Wahlperiode(?:\s+\d{2}\.\d{2}\.\d{4})?"
    r"|Vorabfassung\s*[–-]\s*wird\s+durch\s+die\s+lektorierte\s+Fassung\s+ersetzt\.?"
    r")\s*$"
)
_NUMBER = re.compile(r"Drucksache\s+(\d{1,2})/(\d{1,6})")
_BARE_NUMBER_LINE = re.compile(r"^\s*Drucksache\s+(\d{1,2})/(\d{1,6})\s*$")


def _layout_lines(text: str) -> list[str]:
    """The lines of ``text`` without its running heads and page numbers. The
    Drucksache's own number is the first one it names (its first-page header)."""
    own = _NUMBER.search(text)
    own_number = (int(own.group(1)), int(own.group(2))) if own else None
    kept = []
    for line in text.split("\n"):
        if _LAYOUT_LINE.match(line):
            continue
        bare = _BARE_NUMBER_LINE.match(line)
        if bare and (int(bare.group(1)), int(bare.group(2))) == own_number:
            continue
        kept.append(line)
    return kept


def _breakable(word: str) -> str:
    """A pattern for ``word`` that a line-end break hyphen may split anywhere."""
    return "(?:-[ \t]*\n[ \t]*)?".join(re.escape(char) for char in word)


def _words(*words: str) -> str:
    return r"[ \t\n]+".join(_breakable(word) for word in words)


# The operative part. "II." may precede it; older Anträge open the whole motion with
# "Der Bundestag wolle beschließen:" and still say "fordert … auf" in section II.
# The adverb can stand before or after the object: "fordert daher die
# Bundesregierung auf" (18/12797), "fordert die Bundesregierung daher auf".
_ADVERB = r"(?:(?:daher|deshalb|darüber[ \t\n]+hinaus|insbesondere|ferner)[ \t\n]+)?"
_ANCHOR = re.compile(
    r"(?:^|\n)[ \t]*(?:[IVX]{1,4}\.[ \t]*)?("
    + _words("Der") + r"[ \t\n]+(?:" + _words("Deutsche") + r"[ \t\n]+)?"
    + _words("Bundestag", "fordert") + r"[ \t\n]+" + _ADVERB
    + _words("die", "Bundesregierung")
    + r"[ \t\n]+" + _ADVERB + r"auf\b)"
)
# Where the operative part may end: the date line, the Begründung, or the next
# section ("III. Der Bundestag …" or "III." on its own line). A candidate counts
# only after a finished clause (``_end_of``), so a wrapped line that happens to
# begin with "Begründung" or "V." does not cut a demand short.
_END = re.compile(
    r"\n[ \t]*(?:Berlin,[ \t]+den\b|Begründung\b|(?:II|III|IV|V|VI|VII|VIII|IX|X)\.(?=[ \t]|\n|$))"
)
# A list item at the start of a line: "1.", "12.", "a)", "aa)", "a.", "–", "-", "•".
_ITEM = re.compile(r"^(?:(\d{1,2})\.|([a-z]{1,2})[.)]|[–•-])[ \t]+\S")
# A word a line-end hyphen leaves standing ("Bundes- und Landesrecht").
_KEEPS_HYPHEN = frozenset({"und", "oder", "bzw.", "sowie", "bis", "als", "noch", "wie"})
# What may close a clause, and what may stand after its full stop.
_CLAUSE_ENDS = (".", ";", ":", "!", "?")
_CLOSERS = "\"'“”»«)]"


def _ends_clause(text: str, ends: tuple[str, ...] = _CLAUSE_ENDS) -> bool:
    return text.rstrip().rstrip(_CLOSERS).endswith(ends)


def _end_of(text: str, start: int) -> int:
    """Where the operative part that starts at ``start`` ends: the first end marker
    after a finished clause, else the end of the text."""
    for match in _END.finditer(text, start):
        if _ends_clause(text[max(start, match.start() - 200): match.start()]):
            return match.start()
    return len(text)


def _successor(label: str) -> str:
    """The list label after ``label``: "b" after "a", "bb" after "aa"."""
    return chr(ord(label[0]) + 1) * len(label)


class _Uncertain(Exception):
    """A line-end hyphen that may be the word's own: the passage is not quoted."""


_WORD = re.compile(r"[\wÄÖÜäöüß-]+")


def _lexicon(text: str) -> frozenset[str]:
    """The words ``text`` prints whole on one line, and the parts of its hyphenated
    compounds: the evidence for how a word a line end splits is spelled
    ("NATO-geführten", or "BAföG" from "BAföG-Reform")."""
    words = _WORD.findall(re.sub(r"\S*-[ \t]*\n", " ", text))
    return frozenset(words) | frozenset(part for word in words for part in word.split("-") if part)


def _join(previous: str, line: str, lexicon: frozenset[str] = frozenset()) -> str:
    """``line`` appended to the wrapped paragraph ``previous``.

    A line-end hyphen before a lower-case word is a break hyphen and goes, unless
    the word is one a truncated compound stands before ("Bundes- und"), or the text
    prints the hyphenated word whole elsewhere. After a capital the hyphen is as
    often the word's own ("NATO-geführten") as a break ("BA-föG", 21/8385): the
    text's own spelling decides, and without one the passage is not quoted
    (``_Uncertain``). A number is never hyphenated, so after a digit, and before a
    capital or a digit, the hyphen is part of the word and the lines join without a
    space (E-Mobilität, CO2-neutral, 49-Euro-Ticket)."""
    if previous.endswith("-") and len(previous) > 1 and previous[-2].isalnum():
        word = line.split(None, 1)[0] if line.split() else ""
        if word[:1].islower():
            if word in _KEEPS_HYPHEN:
                return f"{previous} {line}"
            if previous[-2].isdigit():
                return previous + line
            left = _WORD.findall(previous)[-1].rstrip("-")
            right = _WORD.findall(word)[0] if _WORD.findall(word) else word
            head = right.split("-", 1)[0]
            if f"{left}-{right}" in lexicon or f"{left}-{head}" in lexicon:
                return previous + line
            if previous[-2].isupper() and f"{left}{right}" not in lexicon and f"{left}{head}" not in lexicon:
                raise _Uncertain(f"{left}-{right}")
            return previous[:-1] + line
        if word[:1].isupper() or word[:1].isdigit():
            return previous + line
    return f"{previous} {line}"


# A list marker alone on its line: the PDF's text layer put the item text in
# another block. Its text is the next line; a next line that is a marker or opens
# with one ("2." "3.", "2." "e. …") means the text layer lost the order of the
# list (21/5780, 19/7398), and nothing can be quoted from it.
_BARE_MARKER = re.compile(r"^(?:\d{1,2}\.|[a-z]{1,2}[.)]|[–•-])$")


def _lines(body: str) -> list[str] | None:
    """The non-empty lines of ``body``, a bare list marker joined to the line after
    it; None when a bare marker is followed by another or ends the body."""
    lines: list[str] = []
    pending: str | None = None
    for raw in body.split("\n"):
        line = " ".join(raw.split())
        if not line:
            continue
        if _BARE_MARKER.match(line):
            if pending is not None:
                return None
            pending = line
            continue
        if pending is not None and _ITEM.match(line):
            return None
        lines.append(f"{pending} {line}" if pending is not None else line)
        pending = None
    return None if pending is not None else lines


def _paragraphs(body: str, lexicon: frozenset[str] = frozenset()) -> list[str] | None:
    """The wrapped lines of ``body`` joined into its opening and its list items. A
    numbered or lettered line starts an item only in sequence ("2." after "1.", "b)"
    after "a)"), and a dash or bullet only after a finished clause, so a wrapped
    "1. Januar" or "– soweit möglich" stays inside its demand. None when the text
    layer scrambled the list (``_lines``)."""
    lines = _lines(body)
    if lines is None:
        return None
    paragraphs: list[str] = []
    last_number: int | None = None
    last_letter: str | None = None
    for line in lines:
        item = _ITEM.match(line) if paragraphs else None
        starts = False
        if item and item.group(1):
            number = int(item.group(1))
            starts = number == (last_number + 1 if last_number is not None else 1)
            if starts:
                last_number, last_letter = number, None
        elif item and item.group(2):
            letter = item.group(2)
            starts = letter == (_successor(last_letter) if last_letter else "a" * len(letter))
            if starts:
                last_letter = letter
        elif item:
            starts = _ends_clause(paragraphs[-1], (*_CLAUSE_ENDS, ","))
        if not paragraphs or starts:
            paragraphs.append(line)
        else:
            paragraphs[-1] = _join(paragraphs[-1], line, lexicon)
    return paragraphs


def extract_forderung(text: Any) -> Forderung | None:
    """The operative part of an Antrag, or None when it cannot be found with
    confidence (no anchor, a passage outside the bounds or not ending in a full
    clause, a text too long).

    Only layout is undone: running heads and page numbers are dropped, wrapped
    lines joined, break hyphens removed. Every word stays as the Drucksache prints
    it, in its order. Memoised: persist, render and the replay guard ask for the
    same texts."""
    if not isinstance(text, str) or not text or len(text) > MAX_TEXT_CHARS:
        return None
    return _extract(text)


@functools.lru_cache(maxsize=4096)
def _spaced(phrase: str) -> str:
    """A pattern for ``phrase`` with any whitespace, line breaks included, allowed
    between its characters: a watermark's letters are set apart in the text layer."""
    return r"\s*".join(r"\s+" if char == " " else re.escape(char) for char in phrase)


# The advance copy's watermark. DIP's text sets it on every page, letter-spaced over
# three lines ("V" / "orabfassung – w" / "ird durch die lektorierte Fassung
# ersetzt."), anywhere, mid-sentence included (21/8314, 21/8551, 21/8568). It is
# never content, so it goes wherever it stands.
_WATERMARK = re.compile(_spaced("Vorabfassung") + r"\s*[–-]\s*" + _spaced("wird durch die lektorierte Fassung ersetzt") + r"\.?")
# A footnote at a page foot: its number, then its text, which cites ("3 Vgl.
# Bundestagsdrucksache 21/4996, S. 52 …", 21/8385). Inside the operative part it
# splits a demand, often a word, and its reference digits stick to the words they
# follow; neither can be undone with confidence, so such a passage is not quoted.
_FOOTNOTE = re.compile(
    r"^[ \t]*\d{1,3}[ \t]+(?:Vgl\.|vgl\.|Siehe|siehe|Ebd|ebd|Quelle|https?://|www\.|BT-Drs|Bundestagsdrucksache|Drucksache|Dazu|dazu)",
    re.MULTILINE,
)


def _extract(text: str) -> Forderung | None:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = _WATERMARK.sub("\n", text)
    text = "\n".join(_layout_lines(text))
    # A soft hyphen marks where a word may break: at a line end the word goes on.
    text = re.sub("\u00ad[ \t]*\n[ \t]*", "", text).replace("\u00ad", "")
    anchor = _ANCHOR.search(text)
    if anchor is None:
        return None
    body = text[anchor.start(1): _end_of(text, anchor.end())]
    if _FOOTNOTE.search(body):
        return None
    try:
        paragraphs = _paragraphs(body, _lexicon(text))
    except _Uncertain:
        return None
    if not paragraphs:
        return None
    forderung = Forderung(paragraphs[0], tuple(paragraphs[1:]))
    size = len(forderung.text())
    if not MIN_PASSAGE_CHARS <= size <= MAX_PASSAGE_CHARS:
        return None
    # A passage that stops mid-sentence was cut by a misread end, not quoted whole.
    if not _ends_clause(paragraphs[-1], (".", ";")):
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
    return VotePassages(by_vorgang, state, missing)


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


def _wants_metadata(nummern: Mapping[str, Any], number: str) -> bool:
    """Whether a number's metadata is still to be asked for: it is not cached, DIP
    returned no Bundestag record for it, or its Antrag is not yet linked to a
    Vorgang. Like an unresolved number of the Vorgang cache, the last two are
    asked again by every online build, since DIP may fill them in later."""
    if number not in nummern:
        return True
    record = _number_record(nummern[number])
    return record is None or (record.get("drucksachetyp") in PASSAGE_TYPES and not record.get("vorgang_ids"))


def fetch_targets(reports: Iterable[Mapping[str, Any]], vorgang_cache: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """What an online build still has to fetch: (Drucksache numbers whose metadata
    is missing or may since have changed, ``_wants_metadata``; Drucksache ids
    without text). Only votes with a Vorgang to quote for ask; numbers come first,
    since only their metadata says which ids are Anträge, so the build calls this
    again after fetching them."""
    cache = _drucksachen(vorgang_cache)
    nummern = cache.get("nummern") or {}
    texte = cache.get("texte") or {}
    numbers: dict[str, None] = {}
    ids: dict[str, None] = {}
    for report in reports:
        wahlperiode = derive.report_wahlperiode(report)
        contexts = politikfelder.report_vote_vorgaenge(report, vorgang_cache)
        for _item, vote in derive.iter_report_votes(report):
            context = contexts[politikfelder.vote_key(vote)]
            if not _abstractless_vorgaenge(context, vorgang_cache):
                continue
            for number in politikfelder.vote_document_numbers(vote, wahlperiode):
                if _wants_metadata(nummern, number):
                    numbers.setdefault(number)
            passages = vote_passages(vote, context, vorgang_cache, wahlperiode=wahlperiode)
            for group in passages.by_vorgang.values():
                for passage in group:
                    if passage.drucksache_id not in texte:
                        ids.setdefault(passage.drucksache_id)
    return list(numbers), list(ids)


# --- the cache file ---------------------------------------------------------


def cache_path(output_dir: Path | str) -> Path:
    return Path(output_dir) / "data" / CACHE_FILENAME


def load_cache(output_dir: Path | str) -> dict[str, Any]:
    """The Drucksache cache; empty when there is none yet. As with the Vorgang
    cache (``politikfelder.load_cache``), an unsupported version or a read error
    raises ``politikfelder.CacheLoadError`` with the file untouched, so no online
    build overwrites it; corrupt content (bad gzip, JSON or shape) is moved aside
    and read as empty, so passages fall back to ``not_fetched`` (and the replay
    guard refuses to lose known ones) until an online build refills it."""
    path = cache_path(output_dir)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return empty_cache()
    except OSError as exc:
        raise politikfelder.CacheLoadError(
            f"Cannot read Drucksache text cache {path}: {exc}. "
            "Fix: restore read access or restore the cache; the file is untouched"
        ) from exc
    try:
        data = json.loads(gzip.decompress(raw).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("cache must be an object")
        version = data.get("version")
        if type(version) is not int or version != 1:
            raise politikfelder.CacheLoadError(
                f"Unsupported Drucksache text cache version {version!r} at {path}. "
                "Fix: use compatible code or restore a version 1 cache; the file is untouched"
            )
        nummern, texte = data.get("nummern"), data.get("texte")
        if not isinstance(nummern, dict) or not isinstance(texte, dict):
            raise ValueError("nummern and texte must be objects")
    except (ValueError, EOFError, OSError, zlib.error, RecursionError) as exc:  # OSError: gzip.BadGzipFile
        note = politikfelder.preserve_corrupt(path)
        print(f"warning: unreadable {path}: {exc} ({note}); Antrag passages fall back to not_fetched.", file=sys.stderr)
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
