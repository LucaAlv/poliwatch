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
import unicodedata
import xml.etree.ElementTree as ET
from typing import Any, NamedTuple

import derive

#: The counting rule a parsed report was made under. A report without it predates
#: A1 (Kurzinterventionen, Fragen and Antworten counted as Reden) and is warned about.
VERSION = 18

KURZINTERVENTION = "kurzintervention"
ERWIDERUNG = "erwiderung"
ZWISCHENFRAGE = "zwischenfrage"
ZU_PROTOKOLL = "zu_protokoll"
BEFRAGUNG_FRAGE = "befragung_frage"
BEFRAGUNG_ANTWORT = "befragung_antwort"
FRAGESTUNDE_FRAGE = "fragestunde_frage"
FRAGESTUNDE_ANTWORT = "fragestunde_antwort"
#: ADR 0004: an address that is no contribution to a debate, by the presidium or
#: a guest; shown, counted in no Reden figure.
ANSPRACHE = "ansprache"
#: ADR 0002, amendment 2026-11-23: an oral Erklärung zur Aussprache (§ 30), zur
#: Abstimmung (§ 31) or außerhalb der Tagesordnung (§ 32 GO-BT), only where the
#: reviewed list names it.
ERKLAERUNG = "erklaerung"

CONTRIBUTION_KINDS = (
    KURZINTERVENTION,
    ERWIDERUNG,
    ERKLAERUNG,
    ZWISCHENFRAGE,
    ZU_PROTOKOLL,
    BEFRAGUNG_FRAGE,
    BEFRAGUNG_ANTWORT,
    FRAGESTUNDE_FRAGE,
    FRAGESTUNDE_ANTWORT,
    ANSPRACHE,
)

#: Internal labels of a whole ``<rede>`` (ADR 0004), never stored and never a
#: ``CONTRIBUTION_KINDS`` member, so ``validate_kind`` refuses one that reaches
#: persist. A listed Sitzungsleitung or procedural ``<rede>`` takes the status
#: ``procedural``; an unreviewed presidium ``<rede>`` refuses its sitting.
SITZUNGSLEITUNG = "sitzungsleitung_rede"
PROCEDURAL = "procedural_rede"
UNREVIEWED_PRESIDIUM = "unreviewed_presidium"

#: The status a whole ``<rede>`` of the source takes in the parser's reconciliation
#: (``validate_dip_protocol.reconcile_reden``) when it is emitted as this kind;
#: ``None`` is a Rede. Every Kind the parser can make of a whole ``<rede>`` needs a
#: row here, or the sitting is refused; a new Kind adds its row.
REDE_STATUS = {
    None: "speech",
    KURZINTERVENTION: "beitrag",
    ERWIDERUNG: "beitrag",
    ERKLAERUNG: "beitrag",
    BEFRAGUNG_FRAGE: "beitrag",
    BEFRAGUNG_ANTWORT: "beitrag",
    ZU_PROTOKOLL: "zu_protokoll",
    ANSPRACHE: "beitrag",
}
#: Why a Rede is withheld (``withheld_units.reason``, ADR 0005): the short label
#: the Dossier shows, and the German text the data dictionary and DATA.md give.
#: The data dictionary must list exactly these codes.
WITHHELD_REASONS: dict[str, tuple[str, str]] = {
    "refused_nested_contribution": (
        "ein Beitrag eines anderen Redners darin ist keiner Regel zuzuordnen",
        "Ein Beitrag eines anderen Redners in dieser Rede passt zu keiner geprüften Regel "
        "(Zwischenfrage, Kurzintervention, Sitzungsleitung); die Rede wird zurückgehalten.",
    ),
    "refused_nested_question_speaker": (
        "ein Redner darin ist weder Fragesteller noch Antwortender",
        "In einer Befragung der Bundesregierung ist ein Redner in dieser Rede weder als "
        "Fragesteller noch als Antwortender erkennbar; die Rede wird zurückgehalten.",
    ),
    "reviewed": (
        "auf der geprüften Liste",
        "Auf der geprüften Liste (scripts/reviewed_units.json) mit Begründung zurückgehalten, etwa weil eine "
        "ganze Rede als Zwischenfrage gelesen würde.",
    ),
    "unreviewed_presidium": (
        "Präsidium, Eid oder Wahlannahme, noch nicht geprüft",
        "Eine Rede des Präsidiums oder eines Gastes, oder eine kurze Rede, die wie ein Eid oder die Annahme "
        "einer Wahl liest, steht noch nicht auf der geprüften Liste (scripts/reviewed_units.json, ADR 0004); "
        "sie wird zurückgehalten, bis sie als Ansprache, Sitzungsleitung oder Verfahrensschritt eingeordnet ist.",
    ),
    "unreviewed_name_speaker": (
        "Redner wie die Sitzungsleitung gedruckt, noch nicht geprüft",
        "In der Rede steht ein Beitrag, den die Quelle wie einen Satz der Sitzungsleitung druckt, obwohl ihn "
        "jemand anderes spricht; er steht noch nicht auf der geprüften Liste (scripts/reviewed_units.json, "
        "ADR 0004), daher wird die Rede zurückgehalten, bis er einer Person und Art zugeordnet ist.",
    ),
}
#: The status of a ``<rede>`` the parser withholds (ADR 0005): stored in
#: ``withheld_units``, outside every count, instead of under one of the kinds above.
WITHHELD_STATUS = "withheld"
#: Kinds that are never a whole ``<rede>``: a marker inside one (Zwischenfrage) or a
#: Fragestunde turn, which stands outside any ``<rede>``.
NOT_REDE_KINDS = frozenset({ZWISCHENFRAGE, FRAGESTUNDE_FRAGE, FRAGESTUNDE_ANTWORT})

#: How the pages word a Kind inside a sentence: (singular, plural). Where a label opens
#: a field or a card, ``label_start`` capitalises it.
KIND_LABELS = {
    KURZINTERVENTION: ("Kurzintervention", "Kurzinterventionen"),
    ERWIDERUNG: ("Erwiderung", "Erwiderungen"),
    ERKLAERUNG: ("mündliche Erklärung", "mündliche Erklärungen"),
    ZWISCHENFRAGE: ("Zwischenfrage", "Zwischenfragen"),
    ZU_PROTOKOLL: ("zu Protokoll gegebener Beitrag", "zu Protokoll gegebene Beiträge"),
    BEFRAGUNG_FRAGE: ("Frage in der Befragung der Bundesregierung", "Fragen in der Befragung der Bundesregierung"),
    BEFRAGUNG_ANTWORT: ("Antwort in der Befragung der Bundesregierung", "Antworten in der Befragung der Bundesregierung"),
    FRAGESTUNDE_FRAGE: ("Frage oder Nachfrage in der Fragestunde", "Fragen und Nachfragen in der Fragestunde"),
    FRAGESTUNDE_ANTWORT: ("Antwort in der Fragestunde", "Antworten in der Fragestunde"),
    ANSPRACHE: ("Ansprache", "Ansprachen"),
}


def label_start(label: str) -> str:
    """A ``KIND_LABELS`` wording where it opens a field or a card."""
    return label[:1].upper() + label[1:]


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


#: ``aktivitaetsart`` of DIP whose turn is no Rede (ADR 0002 and its
#: amendment of 2026-11-23), and the Kind it names.
DIP_UNIT_KINDS = {
    "Kurzintervention": KURZINTERVENTION,
    "Erwiderung": ERWIDERUNG,
    "Erklärung zur Aussprache gem. § 30 Geschäftsordnung BT": ERKLAERUNG,
    "Mündliche Erklärung gem. § 31 Geschäftsordnung BT": ERKLAERUNG,
    "Persönliche Erklärung gem. § 32 Geschäftsordnung BT": ERKLAERUNG,
    "Rede (zu Protokoll gegeben)": ZU_PROTOKOLL,
    "Berichterstattung (zu Protokoll gegeben)": ZU_PROTOKOLL,
}
#: ``aktivitaetsart`` of DIP the store keeps as a Rede: the types stored Reden of the
#: 806 sittings meet at their place (measured 2026-11-28). Only these explain a stored
#: Rede; a type DIP adds later explains none, so the guard names more, never fewer.
DIP_REDE_TYPES = frozenset({
    "Rede", "Zur Geschäftsordnung BT", "Einleitende Ausführungen und Beantwortung",
    "Berichterstattung und Beantwortung", "Berichterstattung",
    "Erklärung zum Vermittlungsverfahren (§ 90 GO-BT, § 10 GO-VermA)", "Erklärung zum Plenarprotokoll",
    "Wortbeitrag", "Änderungsantrag",
})
#: What DIP calls the turns of a Befragung the store keeps as Fragen and Antworten.
DIP_BEFRAGUNG_TYPES = DIP_REDE_TYPES | {"Frage", "Antwort", "Zusatzfrage"}
#: Stored Beiträge of a whole ``<rede>`` that a reviewed entry can turn into a Rede, so
#: DIP's "Rede" can contradict them. A Rede zu Protokoll is not one: in an annex its
#: heading decides (20/66 Steffen, which DIP types "Rede", stands in "Zu Protokoll
#: gegebene Reden"), and inside a TOP every one is listed.
_TYPED_BEITRAG_KINDS = frozenset({KURZINTERVENTION, ERWIDERUNG, ERKLAERUNG})


def _last_word(name: str | None) -> str:
    """The last word of a printed name without its comma and bracketed parts
    ("Volker Beck (Köln), MdB, …" is "beck"), as DIP and the Plenarprotokoll
    both end it."""
    words = re.sub(r"\([^)]*\)", " ", name or "").split(",")[0].split()
    # DIP prints some names without their marks (Dagdelen for Dağdelen).
    plain = unicodedata.normalize("NFKD", words[-1].casefold()) if words else ""
    return "".join(char for char in plain if not unicodedata.combining(char))


def person_name(name: str | None) -> tuple[str, frozenset[str]] | None:
    """The surname and given names of a printed name, as ``_last_word`` folds them
    ("Dr. Heribert Hirte, MdB, CDU/CSU" is ("hirte", {"heribert"})); titles and
    initials end in a point and count as neither. None where no name is left
    ("Dr. h. c.", the shown name of 19/69 ``ID196901400``)."""
    words = [word for word in re.sub(r"\([^)]*\)", " ", name or "").split(",")[0].split() if not word.endswith(".")]
    if not words:
        return None
    given = {_last_word(part) for word in words[:-1] for part in word.split("-")}
    return _last_word(words[-1]), frozenset(given - {""})


def _speaker_person(speaker: dict[str, Any]) -> tuple[str, frozenset[str]] | None:
    """A stored unit's person: the printed ``<vorname>`` and ``<nachname>``, or the
    shown name where the XML prints no surname (19/69, 20/91, 20/94, ...)."""
    if speaker.get("last_name"):
        return person_name(f"{speaker.get('first_name') or ''} {speaker['last_name']}")
    return person_name(speaker.get("display_name"))


def _same_person(stored: tuple[str, frozenset[str]] | None, dip: tuple[str, frozenset[str]]) -> bool:
    """One person by surname and, where both print one, a shared given name (as the
    census of docs/plans/beitraege-as-reden does). A unit with no name at all
    meets every Aktivität of its place."""
    if stored is None:
        return True
    return stored[0] == dip[0] and (not stored[1] or not dip[1] or bool(stored[1] & dip[1]))


def _remedy(unit: dict[str, Any]) -> str:
    """What a reviewed entry can say for a named row (ADR 0002, amendment 2026-11-23)."""
    if unit["stored"] in _TYPED_BEITRAG_KINDS:
        return f"list it as rede if it is a Rede, or as {unit['stored']} where DIP is wrong"
    kinds = ", ".join(unit["dip"])
    if unit["befragung"]:
        return ("list it as erklaerung if DIP is right; no entry yet confirms a Frage or Antwort "
                "of a Befragung where DIP is wrong (TODOS.md)")
    if not re.fullmatch(r"\d+", str((unit["unit"].get("speaker") or {}).get("xml_redner_id") or "")):
        return f"DIP says {kinds}, but its speaker has no Bundestag Redner-ID, which every unit entry needs: record the case in TODOS.md"
    return f"list it as {' or '.join(unit['dip'])}, or as rede where DIP is wrong"


def dip_typed_reden(report: dict[str, Any], listed: Any = frozenset()) -> list[dict[str, Any]]:
    """The stored units of one cached report whose Kind DIP contradicts, and that no
    reviewed entry lists (``listed``: the ids of the sitting's unit entries,
    ``reviewed_units.UNIT_KINDS``). Each row has a ``problem``:

    - ``dip_types_otherwise``: a stored Rede, or a Frage or Antwort of a Befragung
      held as a whole ``<rede>``, that DIP types as a Kurzintervention, an
      Erwiderung, an oral Erklärung or a Rede zu Protokoll (a Befragung turn: an
      Erklärung only);
    - ``dip_types_rede``: a stored Kurzintervention, Erwiderung or Erklärung that
      DIP types as a Rede;
    - ``unchecked``: DIP has not indexed the sitting: it holds more Reden,
      Beiträge of those Kinds and Reden zu Protokoll than DIP lists Aktivitäten
      (none at all included), or Befragung turns and no Aktivität of a Befragung
      type (DIP lists those sparsely: 20/10 has 60 turns and 16). One row, no
      ``rede_id``.

    A unit and an Aktivität belong together by person (``_same_person``), page and
    quadrant. Of the units of one person at one place, DIP's Aktivitäten of the types
    the store keeps that way explain that many; only when more are stored than those
    explain is each unlisted one named. A listed unit counts at its place but is never
    named. DIP is a lead, not the verdict: the entry in ``reviewed_units.json`` is.
    """
    activities = (report.get("api_records") or {}).get("aktivitaeten") or []
    acts: dict[tuple[int, str], list[tuple[tuple[str, frozenset[str]], str]]] = {}
    for activity in activities:
        page = re.fullmatch(r"(\d+)\s*([A-D])", str((activity.get("fundstelle") or {}).get("seite") or ""))
        person = person_name(activity.get("titel"))
        if page and person:
            acts.setdefault((int(page.group(1)), page.group(2)), []).append((person, str(activity.get("aktivitaetsart"))))
    units: list[dict[str, Any]] = []
    for item in [report, *(report.get("agenda_items") or [])]:
        befragung = BEFRAGUNG in (item.get("question_formats") or [])
        candidates = [(speech, "rede") for speech in item.get("xml_speakers") or []]
        candidates += [(c, c.get("kind")) for c in item.get("xml_contributions") or []
                       if c.get("rede_id") and not str(c["rede_id"]).startswith("nested:")
                       and c.get("kind") in _TYPED_BEITRAG_KINDS | {ZU_PROTOKOLL, BEFRAGUNG_FRAGE, BEFRAGUNG_ANTWORT}]
        for unit, stored in candidates:
            ref = unit.get("source_page") or {}
            group = ("beitrag" if stored in _TYPED_BEITRAG_KINDS else "written" if stored == ZU_PROTOKOLL
                     else "befragung" if stored != "rede" else "rede")
            units.append({"unit": unit, "stored": stored, "group": group, "befragung": befragung,
                          "person": _speaker_person(unit.get("speaker") or {}),
                          "place": (int(ref["page"]), ref["quadrant"]) if ref.get("page") is not None and ref.get("quadrant") else None})
    counted = sum(unit["group"] != "befragung" for unit in units)
    turns = len(units) - counted
    if counted > len(activities) or (turns and not any(str(a.get("aktivitaetsart")) in DIP_BEFRAGUNG_TYPES - DIP_REDE_TYPES
                                                       for a in activities)):
        return [{"rede_id": None, "speaker": None, "page": None, "dip": [], "stored": None, "problem": "unchecked",
                 "remedy": f"{counted} Reden and Beiträge and {turns} Befragung turns, {len(activities)} DIP Aktivitäten: "
                           "refresh the sitting online once DIP has indexed it"}]
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for unit in units:
        if unit["place"] is not None and unit["group"] != "written":
            groups.setdefault((unit["person"], unit["place"], unit["group"]), []).append(unit)
    rows = []
    for (person, place, group), members in groups.items():
        if person is None:  # counted by place alone: every unit of the group there
            members = [unit for key, others in groups.items() if key[1:] == (place, group) for unit in others]
        arts = [art for other, art in acts.get(place, []) if _same_person(person, other)]
        if group == "beitrag":
            alarms, explain = (["rede"] if any(art in DIP_REDE_TYPES for art in arts) else []), sum(art in DIP_UNIT_KINDS for art in arts)
            problem = "dip_types_rede"
        else:
            alarms = sorted({DIP_UNIT_KINDS[art] for art in arts if art in DIP_UNIT_KINDS
                             and (group == "rede" or DIP_UNIT_KINDS[art] == ERKLAERUNG)})
            explain = sum(art in (DIP_REDE_TYPES if group == "rede" else DIP_BEFRAGUNG_TYPES) for art in arts)
            problem = "dip_types_otherwise"
        if not alarms or len(members) <= explain:
            continue
        for unit in members:
            if unit["unit"].get("rede_id") in listed or (person is None and unit["person"] is not None):
                continue
            unit = {**unit, "dip": alarms}
            rows.append({"rede_id": unit["unit"].get("rede_id"), "speaker": (unit["unit"].get("speaker") or {}).get("display_name"),
                         "page": f"{place[0]}{place[1]}", "dip": alarms, "stored": unit["stored"], "problem": problem,
                         "remedy": _remedy(unit)})
    return rows


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


#: Between two paragraphs of a stored wording. One character, as the space it
#: replaces, so no character count depends on how often the print breaks; inside a
#: paragraph whitespace is collapsed, so a line feed is always a paragraph break.
PARAGRAPH_BREAK = "\n"


def join_paragraphs(paragraphs: list[str]) -> str:
    """A unit's wording as stored: its paragraphs, whitespace collapsed inside each
    and one ``PARAGRAPH_BREAK`` between them."""
    return PARAGRAPH_BREAK.join(text for text in (" ".join(p.replace("\xa0", " ").split()) for p in paragraphs) if text)


class ParagraphFlow:
    """Collects one walk's ``<p>`` texts into the printed paragraphs.

    Where a Zwischenruf or Beifall stands inside a paragraph, the XML ends the
    ``<p>``, prints the ``<kommentar>`` and goes on in a ``<p klasse="O">`` ("ohne
    Einzug": set flush in the print, where a new paragraph, klasse ``J``, is
    indented). That ``<p>`` continues the paragraph before it. Every other ``<p>``
    opens one, as does an ``O`` after anything but a ``<kommentar>``, and an ``O``
    after a block quote (klasse ``Z``), whose own words it does not continue.
    Call ``see`` for each element of the walk and ``add`` for each text kept.
    """

    def __init__(self) -> None:
        self._open: tuple[list[str], ...] = ()
        self._interrupted = False

    def see(self, element: ET.Element) -> None:
        if element.tag == "kommentar":
            self._interrupted = True
        elif (element.tag != "p" and element.tag != "a") or element.get("klasse") == "redner":
            self._open, self._interrupted = (), False

    def add(self, element: ET.Element, text: str, *targets: list[str]) -> None:
        continues = self._interrupted and element.get("klasse") == "O"
        for target in targets:
            if continues and any(target is paragraphs for paragraphs in self._open):
                target[-1] = f"{target[-1]} {text}"
            else:
                target.append(text)
        self._open, self._interrupted = () if element.get("klasse") == "Z" else targets, False


def _text(elem: ET.Element | None) -> str:
    return _clean("".join(elem.itertext())) if elem is not None else ""


def _unspaced(value: str) -> str:
    return re.sub(r"\s+", "", value)


_UNSPACED_BEFRAGUNG_PREFIXES = tuple(_unspaced(prefix) for prefix in BEFRAGUNG_PREFIXES)


def heading_formats(heading: str | None) -> frozenset[str]:
    """The question formats a heading names. 20/136 merges both into one
    heading ("Befragung der Bundesregierung Fragestunde"): its ``<rede>``s are
    a Befragung and its flat turns a Fragestunde. Compared with all whitespace
    removed, because 19/13 prints "Befr agung der Bundesregierung"
    (docs/source-errors.md E10); in the 802 WP 18-21 sittings held, no other
    heading changes format by it."""
    heading = _unspaced(_clean(heading))
    formats = set()
    if heading.startswith(_UNSPACED_BEFRAGUNG_PREFIXES):
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


def _role_text(elem: ET.Element | None) -> str | None:
    return _text(elem).replace("\xad", "") or None


def _same_role(structured: str, printed: str) -> bool:
    """The structured role is the bare title of the printed "(Land)" one (R2).
    A ministry abbreviation and its long form need no reconciling: a Sprechrolle
    rule maps both to the Bundesregierung."""
    return printed.startswith(f"{structured} (") and derive.side_of_role(printed) == "bundesrat"


def effective_role(redner: ET.Element | None) -> tuple[str | None, str | None]:
    """Occurrence-specific structured or printed role; never a person's job."""
    if redner is None:
        return None, None
    long = _role_text(redner.find("name/rolle/rolle_lang"))
    short = _role_text(redner.find("name/rolle/rolle_kurz"))
    printed = None
    # A role follows the printed name and a comma, before the label's colon.
    label = _clean(redner.tail).replace("\xad", "").split(":", 1)[0]
    for match in re.finditer(",", label):
        suffix = label[match.end():].strip()
        if derive.side_of_role(suffix):
            printed = suffix
            break
    structured = long or short
    if structured and printed and derive.side_of_role(structured) != derive.side_of_role(printed):
        if not _same_role(structured, printed):
            raise ValueError(f"conflicting roles at redner {redner.get('id')}: {structured!r} / {printed!r}")
        # The printed spelling is the one a Sprechrolle rule maps.
        return printed, short
    return (long, short) if structured else (printed, None)


PRESIDIUM_ROLE = derive.PRESIDIUM_ROLE


def presidium_role(role: str | None, redner: ET.Element | None = None) -> bool:
    """``derive.is_presidium_role`` with the printed name parts of ``redner``."""
    name = redner.find("name") if redner is not None else None
    parts = [_text(name.find(tag)) for tag in ("titel", "vorname", "namenszusatz", "nachname")] if name is not None else []
    return derive.is_presidium_role(role, parts)


def presidium_owner(rede: ET.Element) -> bool:
    """Whether the owner marker of ``rede`` carries a presidium role."""
    redner = _rede_redner(rede)
    return redner is not None and presidium_role(effective_role(redner)[0] or effective_role(redner)[1], redner)


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

    A ``<rede>`` the parser marked ``listed_unit`` (a ``reviewed_units.UNIT_KINDS``
    entry) is that kind whatever the wording says. It takes its place in the
    running state: a listed Kurzintervention is answered by the next ``<rede>`` of
    the main Redner, and only a Rede becomes the Rede the next one answers. A
    listed Erwiderung belongs to its Redner's own last Rede of the agenda item
    (where there is none, to the last Rede if it answers a Kurzintervention, else to
    none), and so do the Kurzinterventionen right before it when no Erwiderung of
    another Rede follows them too: the Redner they answered spoke before someone
    else did (19/3, 19/61). In a Befragung only an Erklärung can be listed.
    """
    labels: list[RedeLabel] = []
    befragung = BEFRAGUNG in formats
    opening = befragung and not continuation
    between = ""  # Sitzungsleitung text since the previous <rede>
    main_id: str | None = None  # the last Rede, which a Kurzintervention answers
    main_key: str | None = None
    previous: str | None = None  # kind of the previous <rede>
    seen_rede = False
    previous_rede = None
    own_reden: dict[str, str | None] = {}  # each Redner's last Rede
    listed_replies: set[int] = set()
    for child in top:
        if child.tag == "p" and seen_rede and child.attrib.get("klasse") != "redner":
            between += " " + _text(child)
            continue
        if child.tag != "rede":
            continue
        # ADR 0004: a reviewed or unreviewed presidium <rede> is no Rede, and it
        # leaves the running state alone, so a Kurzintervention announced across
        # it still answers the last real Rede. A Sitzungsleitung <rede> is chair
        # text throughout; the others pass on what the chair says after them.
        reviewed = child.get("reviewed_kind")
        if reviewed or presidium_owner(child):
            labels.append(RedeLabel({"ansprache": ANSPRACHE, "sitzungsleitung": SITZUNGSLEITUNG,
                                     "procedural": PROCEDURAL}.get(reviewed or "", UNREVIEWED_PRESIDIUM)))
            if reviewed == "sitzungsleitung":
                between += " " + " ".join(_text(p) for p in child.findall("p") if p.get("klasse") != "redner")
            else:
                between += " " + trailing_sitzungsleitung_text(child)
            continue
        redner = _rede_redner(child)
        who = speaker_class(redner)
        listed = child.get("listed_unit")
        if befragung and listed:
            # Only an Erklärung is listed there (mark_listed_units): neither a Frage nor
            # an Antwort, and it ends no opening reports (19/191, 20/105).
            label = RedeLabel(listed)
        elif befragung:
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
            delegated_reply = False
            intervention_exchange = ""
            if previous_rede is not None:
                chair = False
                source_key = None
                delegation_requested = False
                for node in previous_rede:
                    if node.tag == "name":
                        chair = True
                    elif node.tag == "p" and node.get("klasse") == "redner":
                        chair = False
                        source_key = _redner_key(node.find("redner"))
                    elif chair and node.tag == "p":
                        intervention_exchange += " " + _text(node)
                    elif node.tag == "p" and source_key == main_key:
                        delegation_requested |= bool(names_asker(redner, _text(node)) and re.fullmatch(
                            r"Darf auch Herr [\wÄÖÜäöüß -]+ antworten\?", _text(node)))
                delegated_reply = (
                    previous == KURZINTERVENTION
                    and names_asker(redner, between)
                    and re.search(r"Sind Sie einverstanden, dass der Abgeordnete .* antwortet\? [–-] Gut\.", between)
                    and delegation_requested)
            if listed:
                parent = main_id if listed == KURZINTERVENTION else None
                if listed == ERWIDERUNG:
                    listed_replies.add(len(labels))
                    # Without a Rede of its own it answers what the Kurzintervention before it
                    # does (18/85); with neither, no Rede is known (20/196).
                    answered = main_id if previous in (KURZINTERVENTION, ERWIDERUNG) else None
                    parent = own_reden.get(_redner_key(redner) or "", answered)
                label = RedeLabel(None if listed == "rede" else listed, parent)
            elif previous == KURZINTERVENTION and (same_person or delegated_reply):
                label = RedeLabel(ERWIDERUNG, main_id)
            elif (main_id and names_asker(redner, intervention_exchange)
                  and re.search(r"Herr [^.]+, Sie können eine Kurzintervention machen, eine einzige\.", intervention_exchange)
                  and re.fullmatch(r"\s*Eine kurze Kurzintervention\.", between)):
                label = RedeLabel(KURZINTERVENTION, main_id)
            elif main_id and announces_kurzintervention(
                between, _last_name(redner), _fraktion(redner), len(_speech_chars(child))
            ):
                label = RedeLabel(KURZINTERVENTION, main_id)
            else:
                label = RedeLabel(None)
        labels.append(label)
        if label.kind is None:
            main_id, main_key = child.attrib.get("id"), _redner_key(redner)
            if main_key:
                own_reden[main_key] = main_id
        previous = label.kind
        seen_rede = True
        between = trailing_sitzungsleitung_text(child)
        previous_rede = child
    # The Kurzinterventionen a listed Erwiderung answers.
    index = 0
    while index < len(labels):
        start = index
        while index < len(labels) and labels[index].kind == KURZINTERVENTION:
            index += 1
        replies = index
        while replies < len(labels) and labels[replies].kind == ERWIDERUNG:
            replies += 1
        parents = {label.parent_rede_id for label in labels[index:replies]}
        if len(parents) == 1 and listed_replies & set(range(index, replies)):
            labels[start:index] = [label._replace(parent_rede_id=min(parents, key=str)) for label in labels[start:index]]
        index = max(replies, start + 1)
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


def fragestunde_turns(top: ET.Element, candidates: dict[tuple[str, str], dict[str, ET.Element]] | None = None,
                     counts: dict[str, int] | None = None) -> tuple[list[Turn], int]:
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

    A marker the caller marked ``sitzungsleitung="1"`` is the chair printed as a
    marker (ADR 0004, 18/62): it opens no turn and is read as a ``<name>`` is.

    ``counts``, when given, receives ``markers``, the turns opened by a marker plus
    the chair's markers, so the caller can account for every marker of the source. A turn with no paragraph
    is left out: the source printed a marker with no words.
    """
    items: list[dict[str, Any]] = []  # question blocks and turns, in order
    speaker = "leadership"
    turn: dict[str, Any] | None = None
    question: dict[str, Any] | None = None
    announcement = ""
    unplaced = 0
    chair_markers = 0  # markers the caller marked as Sitzungsleitung: no turn
    unplaced_open = False  # the last unplaced marker has not yet lost a paragraph
    flow = ParagraphFlow()
    for child in top:
        flow.see(child)
        if child.tag == "name":
            speaker, turn, question = "leadership", None, None
            announcement = ""
        elif child.tag == "p" and child.attrib.get("klasse") == "redner":
            redner = child.find("redner")
            if redner is not None and redner.get("sitzungsleitung") == "1":
                # The chair printed as a marker (18/62): it speaks as a <name> does.
                speaker, turn, question = "leadership", None, None
                announcement = ""
                chair_markers += 1
                continue
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
                flow.add(child, text, turn["paragraphs"])
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
                    flow.add(child, text, question["paragraphs"])
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
    if counts is not None:
        counts["markers"] = sum("announcement" not in item for item in items) + chair_markers
    return [turn for turn in turns if turn.paragraphs], unplaced
