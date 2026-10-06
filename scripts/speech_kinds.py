"""What in a Plenarprotokoll counts as a Rede, and what is a Beitrag of another Kind.

CONTEXT.md and ADR 0002 define a Rede as a speech held as its own agenda-item
contribution. The XML wraps more than that in ``<rede>``: the Kurzintervention
and its Erwiderung, and every Frage and Antwort of a Befragung der
Bundesregierung. The Fragestunde has no ``<rede>`` at all: each turn is a flat
``<p klasse="redner">`` marker followed by paragraphs. This module labels each
of them so the parser keeps only Reden in ``speeches`` and stores the rest as
Beiträge (``contributions``), typed by ``kind``.

Pure functions over ``ElementTree`` elements; the parser builds the row dicts.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, NamedTuple

import derive

#: The counting rule a parsed report was made under. A report without it predates
#: A1 (Kurzinterventionen, Fragen and Antworten counted as Reden) and is warned about.
VERSION = 4

KURZINTERVENTION = "kurzintervention"
ERWIDERUNG = "erwiderung"
ZWISCHENFRAGE = "zwischenfrage"
ZU_PROTOKOLL = "zu_protokoll"
BEFRAGUNG_FRAGE = "befragung_frage"
BEFRAGUNG_ANTWORT = "befragung_antwort"
FRAGESTUNDE_FRAGE = "fragestunde_frage"
FRAGESTUNDE_ANTWORT = "fragestunde_antwort"

CONTRIBUTION_KINDS = (
    KURZINTERVENTION,
    ERWIDERUNG,
    ZWISCHENFRAGE,
    ZU_PROTOKOLL,
    BEFRAGUNG_FRAGE,
    BEFRAGUNG_ANTWORT,
    FRAGESTUNDE_FRAGE,
    FRAGESTUNDE_ANTWORT,
)

#: How the pages word a Kind: (singular, plural).
KIND_LABELS = {
    KURZINTERVENTION: ("Kurzintervention", "Kurzinterventionen"),
    ERWIDERUNG: ("Erwiderung", "Erwiderungen"),
    ZWISCHENFRAGE: ("Zwischenfrage", "Zwischenfragen"),
    ZU_PROTOKOLL: ("Zu Protokoll gegebener Beitrag", "Zu Protokoll gegebene Beiträge"),
    BEFRAGUNG_FRAGE: ("Frage in der Befragung der Bundesregierung", "Fragen in der Befragung der Bundesregierung"),
    BEFRAGUNG_ANTWORT: ("Antwort in der Befragung der Bundesregierung", "Antworten in der Befragung der Bundesregierung"),
    FRAGESTUNDE_FRAGE: ("Frage oder Nachfrage in der Fragestunde", "Fragen und Nachfragen in der Fragestunde"),
    FRAGESTUNDE_ANTWORT: ("Antwort in der Fragestunde", "Antworten in der Fragestunde"),
}

# DIP records only these two Kinds per Beitrag as an ``aktivitaetsart``. Its
# "Frage" is not comparable to ours: it counts 43 in 21/6 where the XML holds 61
# Fragen of the Befragung and 49 of the Fragestunde with their Nachfragen.
DIP_ACTIVITY_KINDS = {"Kurzintervention": KURZINTERVENTION, "Erwiderung": ERWIDERUNG}


def kind_counts(contributions: Any) -> dict[str, int]:
    """Number of Beiträge per Kind, over any iterable of contribution dicts."""
    counts: dict[str, int] = {}
    for contribution in contributions:
        counts[contribution["kind"]] = counts.get(contribution["kind"], 0) + 1
    return dict(sorted(counts.items()))


def dip_mismatches(counts: dict[str, int], activities: Any) -> list[dict[str, Any]]:
    """Kinds whose XML count differs from the sitting's DIP ``aktivitaetsart``
    count. A check only: neither side is the source of truth."""
    dip: dict[str, int] = {}
    for activity in activities:
        kind = DIP_ACTIVITY_KINDS.get(str(activity.get("aktivitaetsart")))
        if kind:
            dip[kind] = dip.get(kind, 0) + 1
    return [
        {"kind": kind, "xml": counts.get(kind, 0), "dip": dip.get(kind, 0)}
        for kind in DIP_ACTIVITY_KINDS.values()
        if counts.get(kind, 0) != dip.get(kind, 0)
    ]


# --- Question formats ---------------------------------------------------------

# Prefix match on the whitespace-normalised heading; the store also holds
# "Befragung der Bundesregierung (einleitend BMJ)" and Anträge with "Befragung"
# mid-string, which are no question format.
BEFRAGUNG_PREFIXES = ("Befragung der Bundesregierung", "Regierungsbefragung")
FRAGESTUNDE_PREFIX = "Fragestunde"

BEFRAGUNG = "befragung"
FRAGESTUNDE = "fragestunde"


def _clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").replace("\xa0", " ")).strip()


def _text(elem: ET.Element | None) -> str:
    return _clean("".join(elem.itertext())) if elem is not None else ""


def heading_formats(heading: str | None) -> frozenset[str]:
    """The question formats a heading names. 20/136 merges both into one
    heading ("Befragung der Bundesregierung Fragestunde"): its ``<rede>``s are
    a Befragung and its flat turns a Fragestunde."""
    heading = _clean(heading)
    formats = set()
    if heading.startswith(BEFRAGUNG_PREFIXES):
        formats.add(BEFRAGUNG)
        if FRAGESTUNDE_PREFIX in heading:
            formats.add(FRAGESTUNDE)
    elif heading.startswith(FRAGESTUNDE_PREFIX):
        formats.add(FRAGESTUNDE)
    return frozenset(formats)


class TopFormat(NamedTuple):
    formats: frozenset[str]
    continuation: bool


def top_format(heading: str | None, top_id: str | None, seen: dict[str, frozenset[str]]) -> TopFormat:
    """The format of one agenda item. A continuation of a Befragung is a second
    ``<tagesordnungspunkt>`` with the same ``top-id`` and no heading (20/209);
    it inherits the format and has no opening reports of its own. ``seen`` maps
    each top-id to the format of its first item and is updated here."""
    formats = heading_formats(heading)
    continuation = False
    top_id = _clean(top_id)  # 21/5 writes "Tagesordnungspunkt 1" with and without a no-break space
    if not _clean(heading) and top_id and top_id in seen:
        formats, continuation = seen[top_id], True
    elif top_id and top_id not in seen:
        seen[top_id] = formats
    return TopFormat(formats, continuation)


# --- Who speaks ---------------------------------------------------------------

MEMBER = "member"
OFFICIAL = "official"


def effective_role(redner: ET.Element | None) -> tuple[str | None, str | None]:
    """Occurrence-specific structured or printed role; never a person's job."""
    if redner is None:
        return None, None
    long = _text(redner.find("name/rolle/rolle_lang")) or None
    short = _text(redner.find("name/rolle/rolle_kurz")) or None
    printed = None
    # A role follows the printed name and a comma, before the label's colon.
    label = _clean(redner.tail).split(":", 1)[0]
    for match in re.finditer(",", label):
        suffix = label[match.end():].strip()
        if derive.side_of_role(suffix):
            printed = suffix
            break
    structured = long or short
    if structured and printed and derive.side_of_role(structured) != derive.side_of_role(printed):
        raise ValueError(f"conflicting roles at redner {redner.get('id')}: {structured!r} / {printed!r}")
    return (long, short) if structured else (printed, None)


def validate_kind(kind: str) -> None:
    if kind not in CONTRIBUTION_KINDS:
        raise ValueError(f"Unknown contribution kind {kind!r}; reparse cached XML with --offline --repersist")


def speaker_class(redner: ET.Element | None) -> str | None:
    """A Redner with a ``<rolle>`` (Bundesregierung, Bundesrat) is an official,
    one with a ``<fraktion>`` and no rolle an MdB, anyone else no one this
    module can place."""
    if redner is None:
        return None
    if any(effective_role(redner)):
        return OFFICIAL
    if _text(redner.find("name/fraktion")):
        return MEMBER
    return None


def _rede_redner(rede: ET.Element) -> ET.Element | None:
    return rede.find("./p[@klasse='redner']/redner")


def _last_name(redner: ET.Element | None) -> str:
    return _text(redner.find("name/nachname")) if redner is not None else ""


def _fraktion(redner: ET.Element | None) -> str:
    return _text(redner.find("name/fraktion")) if redner is not None else ""


def _speech_chars(rede: ET.Element) -> str:
    """The paragraphs of a ``<rede>`` before any Sitzungsleitung ``<name>``: a
    cheap measure of how long the Redner spoke."""
    return " ".join(_text(p) for p in rede.findall("p") if p.attrib.get("klasse") != "redner")


def _redner_key(redner: ET.Element | None) -> str | None:
    return derive.first_redner_id(redner.attrib.get("id")) if redner is not None else None


# --- Kurzintervention / Erwiderung -------------------------------------------

# The Sitzungsleitung announces a Kurzintervention at the end of the previous
# ``<rede>`` ("Zu einer Kurzintervention darf ich ... das Wort erteilen").
# "Zwischenbemerkung" is the older word for it. It is told from a remark about
# the rules ("Kurzinterventionen gibt es bei einer Aktuellen Stunde nicht. – Das
# Wort hat ...", "keine Zwischenfragen und keine Kurzinterventionen mehr") by
# sentence: the sentence that names a Kurzintervention must not deny or refuse it
# (NOT_GRANTED) and must grant the Wort, name the next Redner in it or in the two
# sentences after it ("Die AfD-Fraktion hat eine Kurzintervention beantragt, die
# ich zulasse. Der Kollege Stöber hat das Wort."), or name the next Redner's
# Fraktion. Only the part of a sentence after a closing remark (CLOSED) can grant;
# a sentence that names a Kurzintervention is granted by an immediate "Bitte schön"
# (INVITES) when it names one pending Kurzintervention, not Kurzinterventionen in
# general ("Kurzinterventionen lasse ich am Ende zu. – Bitte schön."), and the
# Sitzungsleitung did not announce the next Redner for something else ("Nächster
# Redner ist Herr Meier."). The two signals that name no one, the Fraktion and
# "Bitte schön", are held to the length of a Kurzintervention (two minutes,
# WEAK_MAX_CHARS).
KURZINTERVENTION_WORDING = re.compile(r"Kurzintervention|Zwischenbemerkung|Zwischenintervention", re.IGNORECASE)
ONE_KURZINTERVENTION = re.compile(r"(?:Kurzintervention|Zwischenbemerkung|Zwischenintervention)(?!en)", re.IGNORECASE)
GRANTS_WORT = re.compile(r"\bWort\b")
NOT_GRANTED = re.compile(r"\b(?:kein\w*|nicht|nie|ohne|weder|ablehn\w*|abgelehnt|verwehr\w*|untersag\w*)\b", re.IGNORECASE)
# A conditional or subordinate sentence states a rule or a possibility, not a grant
# ("Wenn jemand persönlich angesprochen wird, kann er sich zu einer Kurzintervention
# melden"; "kann man überlegen, ob es eine Kurzintervention gibt"); a withdrawn
# Kurzintervention ("Nein, er zieht zurück") is none.
CONDITIONAL = re.compile(r"\b(?:wenn|falls|ob|sofern)\b", re.IGNORECASE)
WITHDRAWN = re.compile(r"zieht zurück|zurückgezogen|verzichtet", re.IGNORECASE)
# A sentence that closes the Kurzintervention just held ("Damit ist die Kurzintervention
# beendet. Das Wort hat als Nächste die Kollegin Meier.") grants nothing: the Redner
# named after it speaks a Rede of their own.
CLOSED = re.compile(
    r"\b(?:beendet|abgeschlossen|erledigt|vorbei)\b|zu Ende"
    r"|\b(?:Danke|Dank)\b[^;!?]*\bfür\b[^;!?]*"
    r"\b(?:Kurzintervention|Zwischenbemerkung|Zwischenintervention)\b[^;!?]*",
    re.IGNORECASE,
)
# The Sitzungsleitung asks whether a Kurzintervention is wanted and the Redner says yes
# by taking the floor: "Sie möchten eine Kurzintervention machen? – Bitte schön."
INVITES = re.compile(r"^\W*(?:ja\W+)?bitte\s+(?:schön|sehr)\b", re.IGNORECASE)
# A title is no sentence end ("Zu einer Kurzintervention hat die Kollegin Dr. Petra Sitte das Wort.").
_SENTENCE_END = re.compile(r"(?<!Dr\.)(?<!Prof\.)(?<=[.!?])\s+")
FRAKTION_WORDING = {
    "AfD": re.compile(r"\bAfD\b"),
    "SPD": re.compile(r"\bSPD\b"),
    "FDP": re.compile(r"\bFDP\b"),
    "CDU/CSU": re.compile(r"CDU|Union"),
    "BÜNDNIS 90/DIE GRÜNEN": re.compile(r"Grünen|Bündnis|Grüne\b"),
    "DIE LINKE": re.compile(r"Linke"),
    "Die Linke": re.compile(r"Linke"),
    "BSW": re.compile(r"BSW"),
}
WEAK_MAX_CHARS = 5000


class RedeLabel(NamedTuple):
    """``kind`` is None for a Rede. ``parent_rede_id`` is the Rede a
    Kurzintervention or Erwiderung belongs to."""

    kind: str | None
    parent_rede_id: str | None = None


def trailing_sitzungsleitung_text(rede: ET.Element) -> str:
    """What the Sitzungsleitung says after the Redner is done: the paragraphs
    after the Rede's last ``<name>``, unless the Redner resumes after it."""
    children = list(rede)
    last_name = max((i for i, child in enumerate(children) if child.tag == "name"), default=None)
    if last_name is None:
        return ""
    tail = children[last_name + 1 :]
    if any(child.tag == "p" and child.attrib.get("klasse") == "redner" for child in tail):
        return ""
    return " ".join(_text(child) for child in tail if child.tag == "p")


def announces_kurzintervention(
    text: str, next_surname: str = "", next_fraktion: str = "", next_chars: int = 0
) -> bool:
    """Whether the Sitzungsleitung text grants a Kurzintervention to the Redner
    whose surname, Fraktion and text length are given."""
    surname = re.compile(rf"(?<![\w-]){re.escape(next_surname)}(?![\w-])", re.IGNORECASE) if next_surname else None
    fraktion = FRAKTION_WORDING.get(next_fraktion)
    if WITHDRAWN.search(text):
        return False
    sentences = _SENTENCE_END.split(text)
    # The next Redner named where no Kurzintervention is was invited to a Rede.
    # Case-sensitive on word boundaries: "so lange" does not name Frau Lange.
    named = re.compile(rf"\b{re.escape(next_surname)}\b") if next_surname else None
    announced_otherwise = named is not None and any(
        named.search(s) for s in sentences if not KURZINTERVENTION_WORDING.search(s) and not INVITES.match(s)
    )
    for index, sentence in enumerate(sentences):
        # Only what follows a closing remark can grant ("Die Kurzintervention ist
        # beendet; zu einer weiteren Kurzintervention erhält Frau Meier das Wort.").
        closings = list(CLOSED.finditer(sentence))
        if closings:
            sentence = sentence[closings[-1].end() :]
        if (
            not KURZINTERVENTION_WORDING.search(sentence)
            or NOT_GRANTED.search(sentence)
            or CONDITIONAL.search(sentence)
            or (re.search(r"\b(?:möglich|beantwortet)\b", sentence, re.IGNORECASE)
                and not (surname and index + 1 < len(sentences) and surname.search(sentences[index + 1])
                         and re.search(r"In dem Fall.*\bWort\b", sentences[index + 1])))
        ):
            continue
        if GRANTS_WORT.search(sentence):
            return True
        # "Bitte schön" names no one: it may invite an ordinary Redner.
        if (
            index + 1 < len(sentences)
            and INVITES.match(sentences[index + 1])
            and ONE_KURZINTERVENTION.search(sentence)
            and not announced_otherwise
            and next_chars <= WEAK_MAX_CHARS
        ):
            return True
        # A pending intervention can name its recipient in the following
        # chair sentence. Require an explicit pending/grant signal, excluding
        # retrospective explanations and an announcement of the next Rede.
        near = " ".join([sentence, *sentences[index + 1:index + 4]])
        if re.search(r"\bkeine?\s+Kurzintervention(?:en)?\b[^.]*\b(?:zulassen|zulasse|mehr)\b", near, re.IGNORECASE):
            continue
        pending = re.search(
            r"(?:\bes gibt\b|\bgibt es\b|\bwir haben noch\b|\bich habe zwei Bitten\b|\bich lasse\b|"
            r"\blasse ich\b|\bzulasse\b|\bstattgeben\b|\bzugelassen[^.]*vorziehen\b)",
            near if re.search(r"\bangemeldet\b|\bstattgeben\b", sentence, re.IGNORECASE) else sentence,
            re.IGNORECASE,
        )
        next_rede = re.search(r"\b(?:die|der) nächste[nr]? Redner(?:in)?\b", near, re.IGNORECASE)
        retrospective = re.search(r"\b(?:das war|danke für|premiere|für das protokoll)\b", sentence, re.IGNORECASE)
        if surname and surname.search(near) and pending and not next_rede and not retrospective:
            return True
        # Explicit anaphoric grants after a procedural explanation (20/21,
        # 20/22) remain source evidence, even when 'möglich' describes the rule.
        if surname and surname.search(near) and re.search(r"\bWort zu einer solchen\b|In dem Fall.*\bWort\b", near):
            return True
        if surname and surname.search(sentence):
            return True
        if fraktion and fraktion.search(sentence) and next_chars <= WEAK_MAX_CHARS:
            return True
    return False


def classify_reden(top: ET.Element, formats: frozenset[str], continuation: bool = False) -> list[RedeLabel]:
    """One label per ``<rede>`` of the agenda item, in document order.

    In a Befragung the leading ``<rede>``s of officials, up to the first MdB's,
    are the opening reports and stay Reden; every later one is a Frage (MdB) or
    an Antwort (official). Elsewhere a ``<rede>`` is a Kurzintervention when the
    Sitzungsleitung announced one before it, and the Erwiderung when it follows a
    Kurzintervention and comes from the Redner the Kurzintervention answered.
    """
    labels: list[RedeLabel] = []
    befragung = BEFRAGUNG in formats
    opening = befragung and not continuation
    between = ""  # Sitzungsleitung text since the previous <rede>
    main_id: str | None = None  # the last Rede, which a Kurzintervention answers
    main_key: str | None = None
    previous: str | None = None  # kind of the previous <rede>
    seen_rede = False
    for child in top:
        if child.tag == "p" and seen_rede and child.attrib.get("klasse") != "redner":
            between += " " + _text(child)
            continue
        if child.tag != "rede":
            continue
        redner = _rede_redner(child)
        who = speaker_class(redner)
        if befragung:
            if who is None:
                raise ValueError(f"unresolved Befragung turn {child.get('id')} redner {redner.get('id') if redner is not None else None}")
            if opening and who == OFFICIAL:
                label = RedeLabel(None)
            else:
                opening = False
                label = RedeLabel({MEMBER: BEFRAGUNG_FRAGE, OFFICIAL: BEFRAGUNG_ANTWORT}.get(who or ""))
        else:
            same_person = main_key is not None and _redner_key(redner) == main_key
            # The Erwiderung is the Rede of the Redner the Kurzintervention answered. The
            # Sitzungsleitung's wording is no signal: "Möchten Sie antworten? - Nein" is
            # followed by an unrelated Rede (measured on WP 20/21: 10+ real Reden).
            if previous == KURZINTERVENTION and same_person:
                label = RedeLabel(ERWIDERUNG, main_id)
            elif main_id and announces_kurzintervention(
                between, _last_name(redner), _fraktion(redner), len(_speech_chars(child))
            ):
                label = RedeLabel(KURZINTERVENTION, main_id)
            else:
                label = RedeLabel(None)
        labels.append(label)
        if label.kind is None:
            main_id, main_key = child.attrib.get("id"), _redner_key(redner)
        previous = label.kind
        seen_rede = True
        between = trailing_sitzungsleitung_text(child)
    return labels


# --- Fragestunde --------------------------------------------------------------


class Turn(NamedTuple):
    """One Frage or Antwort of a Fragestunde. ``redner`` is the ``<redner>``
    element of the marker that opened the turn, None for a question read out by
    the Sitzungsleitung whose asker never speaks. ``announced`` names the asker
    as the Sitzungsleitung announced them. A turn has no page: the XML anchors
    only the ``<rede>`` elements in its table of contents."""

    kind: str
    redner: ET.Element | None
    announced: str | None
    paragraphs: list[str]


_ANNOUNCED = re.compile(r"Frage\s+\d+\s*(?P<rest>[^:]*):?")
_ANNOUNCE_NAME = re.compile(
    r"(?:Abgeordnete[nr]?|Kolleg(?:in|en|e)|von|vom)\s+(?P<name>(?:Frau\s+|Herrn?\s+)?[A-ZÄÖÜ].*)$"
)
_ANNOUNCE_TAIL = re.compile(r"\s+(?:von der|von den|von dem|vom|für|aus|auf|gestellt)\b.*$")


def announced_asker_details(announcement: str) -> tuple[str | None, str | None]:
    matches = list(_ANNOUNCED.finditer(announcement))
    if not matches:
        return None, None
    rest = re.sub(r"\s+auf$", "", matches[-1].group("rest").strip())
    named = _ANNOUNCE_NAME.search(rest)
    if named is None:
        return None, None
    name = named.group("name").strip(" ,")
    party = None
    suffix = re.search(r"\s*(?:\(([^)]+)\)|,\s*(.+)|\s+von\s+(?:der\s+|den\s+)?(.+))$", name)
    if suffix:
        candidate = next(value for value in suffix.groups() if value)
        candidate = re.sub(r"-Fraktion$", "", candidate)
        if derive.zusammenschluss(candidate):
            party = candidate
            name = name[:suffix.start()].strip()
    name = _ANNOUNCE_TAIL.sub("", name).strip(" ,")
    name = re.sub(r"^(?:Kolleg(?:in|en|e)|Abgeordnete[nr]?)\s+", "", name)
    if name in {"Ihnen", "Sie", "Herr", "Frau"}:
        return None, party
    return name or None, party


def announced_asker(announcement: str) -> str | None:
    return announced_asker_details(announcement)[0]


def names_asker(redner: ET.Element | None, announcement: str) -> bool:
    """Whether the Sitzungsleitung's announcement names this MdB as the asker:
    their whole surname stands in it. "Müller" is not in "Müller-Rossbach" or
    "Müllermann". A first name is not compared: the Sitzungsleitung misspeaks it
    ("Stefan" for Stephan Brandner, "Rainer" for Reinhard Brandl), and a
    transcript that did so is right about the person."""
    surname = _last_name(redner)
    return bool(surname) and re.search(rf"(?<![\w-]){re.escape(surname)}(?![\w-])", announcement, re.IGNORECASE) is not None


def asker_candidates(redners: Any) -> dict[tuple[str, str], dict[str, ET.Element]]:
    """Unique source candidates for this sitting, using only member occurrences."""
    candidates: dict[tuple[str, str], dict[str, ET.Element]] = {}
    for candidate in redners:
        if speaker_class(candidate) != MEMBER:
            continue
        name = candidate.find("name")
        if name is None:
            continue
        full = _clean(" ".join(_text(name.find(k)) for k in ("titel", "vorname", "nachname")))
        normalized = re.sub(r"^(?:(?:Dr\.|Prof\.|Herr|Frau)\s*)+", "", full).casefold()
        party = derive.zusammenschluss(_fraktion(candidate)) or ""
        candidates.setdefault((normalized, party), {})[_redner_key(candidate) or ""] = candidate
    return candidates


def fragestunde_turns(top: ET.Element, candidates: dict[tuple[str, str], dict[str, ET.Element]] | None = None) -> tuple[list[Turn], int]:
    """The Fragen and Antworten of a Fragestunde, in document order, and the
    number of turns left out because their marker names no one.

    Each ``<p klasse="redner">`` opens a turn that runs to the next marker or
    ``<name>`` (the Sitzungsleitung). An MdB's turn is a ``fragestunde_frage``
    (a Nachfrage), an official's a ``fragestunde_antwort``. The question itself
    is read out by the Sitzungsleitung as ``<p klasse="p">``: it is a
    ``fragestunde_frage`` of the MdB the announcement names, taken from the first
    turn after it by that MdB (``names_asker``).

    A marker with neither ``<rolle>`` nor ``<fraktion>`` names no one the parser
    can place (a guest, say): its paragraphs are no turn, and the caller reports
    how many markers lost text this way so the omission is counted, not silent.
    """
    items: list[dict[str, Any]] = []  # question blocks and turns, in order
    speaker = "leadership"
    turn: dict[str, Any] | None = None
    question: dict[str, Any] | None = None
    announcement = ""
    unplaced = 0
    unplaced_open = False  # the last unplaced marker has not yet lost a paragraph
    for child in top:
        if child.tag == "name":
            speaker, turn, question = "leadership", None, None
            announcement = ""
        elif child.tag == "p" and child.attrib.get("klasse") == "redner":
            redner = child.find("redner")
            who = speaker_class(redner)
            question = None
            if who is None:
                raise ValueError(f"unresolved Fragestunde marker redner {redner.get('id') if redner is not None else None}")
            speaker = "turn"
            turn = {
                "kind": FRAGESTUNDE_FRAGE if who == MEMBER else FRAGESTUNDE_ANTWORT,
                "redner": redner,
                "paragraphs": [],
            }
            items.append(turn)
        elif child.tag == "p":
            text = _text(child)
            if not text:
                continue
            if speaker == "turn" and turn is not None:
                turn["paragraphs"].append(text)
            elif speaker == "unplaced" and unplaced_open:
                unplaced, unplaced_open = unplaced + 1, False
            elif speaker == "leadership":
                if child.attrib.get("klasse") in {"p", "P"}:
                    if question is None:
                        question = {
                            "kind": FRAGESTUNDE_FRAGE,
                            "redner": None,
                            "announced": announced_asker(announcement),
                            "announcement": announcement,
                            "paragraphs": [],
                        }
                        items.append(question)
                    question["paragraphs"].append(text)
                else:
                    announcement, question = text, None

    candidates = candidates if candidates is not None else asker_candidates(top.iter("redner"))
    turns: list[Turn] = []
    for index, item in enumerate(items):
        if "announcement" in item:
            for follower in items[index + 1 :]:
                if "announcement" in follower:
                    break
                if follower["kind"] == FRAGESTUNDE_FRAGE and _last_name(follower["redner"]):
                    if names_asker(follower["redner"], item["announcement"]):
                        item["redner"] = follower["redner"]
                    break
            if item["redner"] is None:
                announced, party = announced_asker_details(item["announcement"])
                normalized = re.sub(r"^(?:(?:Dr\.|Prof\.|Herr|Frau)\s*)+", "", announced or "").casefold()
                matches = {key: candidate for (name, faction), group in candidates.items()
                           if name == normalized and (not party or faction == derive.zusammenschluss(party))
                           for key, candidate in group.items() if key}
                if len(matches) == 1:
                    item["redner"] = next(iter(matches.values()))
        turns.append(Turn(item["kind"], item["redner"], item.get("announced"), item["paragraphs"]))
    return [turn for turn in turns if turn.paragraphs], unplaced
