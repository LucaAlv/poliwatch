"""Values derived from the raw fields of a cached report.

A cached dossier report is a snapshot of what the parser knew when it was
written. Anything that can be worked out from its raw fields (counts, names,
roles) is worked out here, at persist time *and* at render time, and the value
the report cached for it is ignored. A correction to a rule below therefore
reaches the database and the pages with ``--offline --repersist`` and never
needs a re-fetch, and a stale cached report cannot render a value the stored
rows disagree with (plan E2).

Each function follows the CONTEXT.md entry of the same term.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

import publication_state as publication
from stable_ids import document_issuer, document_number, vote_member_occurrence_id

#: The Stimmen a Mehrheitsvotum is chosen among. "nicht abgegeben" (key
#: "absent") is not a Stimme.
MAJORITY_KEYS = ("yes", "no", "abstain")


def majority_vote(counts: Mapping[str, Any] | None) -> str | None:
    """Mehrheitsvotum of one Zusammenschluss in one namentliche Abstimmung.

    The Stimme most of its MdBs gave among Ja, Nein and Enthaltung (a plurality:
    40 Ja / 35 Nein / 25 Enthaltung is Ja). ``None`` when the top count is
    shared by two or more Stimmen, and when no MdB of the Zusammenschluss voted.
    """
    cast = {key: int((counts or {}).get(key) or 0) for key in MAJORITY_KEYS}
    top = max(cast.values())
    if top == 0:
        return None
    leaders = [key for key, count in cast.items() if count == top]
    return leaders[0] if len(leaders) == 1 else None


# --- Zusammenschluss ---------------------------------------------------------

GRUPPE_DIE_LINKE = "Gruppe Die Linke"
GRUPPE_BSW = "Gruppe BSW"

#: Casefolded spelling -> the one name a parties row carries. A Gruppe is its
#: own kind of Zusammenschluss (CONTEXT.md), never a Fraktion: the sources spell
#: it "Gruppe BSW", "BSW (Gruppe)" and, in the XML of a Rede, plain "BSW" (the
#: BSW only ever sat in the Bundestag as a Gruppe). The WP 20 Gruppe Die Linke
#: stays apart from the Fraktion Die Linke of WP 21.
_SPELLINGS = {
    "b90/grüne": "BÜNDNIS 90/DIE GRÜNEN",
    "grüne": "BÜNDNIS 90/DIE GRÜNEN",
    "bündnis 90/die grünen": "BÜNDNIS 90/DIE GRÜNEN",
    "linke": "Die Linke",
    "die linke": "Die Linke",
    "fraktionslose": "fraktionslos",
    "fraktionslos": "fraktionslos",
    "gruppe die linke": GRUPPE_DIE_LINKE,
    "die linke (gruppe)": GRUPPE_DIE_LINKE,
    "linke (gruppe)": GRUPPE_DIE_LINKE,
    "gruppe bsw": GRUPPE_BSW,
    "bsw (gruppe)": GRUPPE_BSW,
    "bsw": GRUPPE_BSW,
}
#: The names a merged record can be made of (see ``zusammenschluss``).
_KNOWN = frozenset(
    {"SPD", "CDU/CSU", "AfD", "FDP", "BÜNDNIS 90/DIE GRÜNEN", "Die Linke", GRUPPE_DIE_LINKE, GRUPPE_BSW, "fraktionslos"}
)


def _clean(value: Any) -> str:
    return " ".join(str(value if value is not None else "").replace("\xa0", " ").split())


def vote_member_key(vote_id: Any, member: Mapping[str, Any]) -> str | None:
    """Stable occurrence key for one member row in a roll-call vote."""
    vote_id_clean = _clean(vote_id) or None
    if vote_id_clean is None:
        return None
    name = _clean(member.get("name")) or None
    faction = zusammenschluss(member.get("faction")) or "Unbekannt"
    return vote_member_occurrence_id(vote_id_clean, name, faction)


def _known(text: str) -> str | None:
    name = _SPELLINGS.get(text.casefold(), text)
    return name if name in _KNOWN else None


def zusammenschluss(value: Any) -> str | None:
    """The name of a Zusammenschluss as a parties row carries it, from any
    spelling the sources use; other names pass through unchanged.

    ``None`` when there is nothing to name: no value, or a value that is two
    names run together. Bundestag's XML has such merged records ("SPDSPD" for
    one person written twice, "SPDCDU/CSU" for two people folded into one
    element). The first is one name, the second cannot be resolved from the
    string alone.
    """
    text = _clean(value)
    if not text:
        return None
    if text.casefold() in _SPELLINGS:
        return _SPELLINGS[text.casefold()]
    for cut in range(1, len(text)):
        left, right = _known(text[:cut]), _known(text[cut:])
        if left and right:
            return left if left == right else None
    return text


#: The Fraktion Die Linke dissolved on 2023-12-06; its members went on as the
#: Gruppe Die Linke. The XML of a Rede spells it "Die Linke" all the same, so a
#: WP 20 Rede from this day on is a Gruppe Die Linke Rede. (The store has no
#: Rede naming Die Linke between 2023-12-01 and 2024-02-21, so the exact day
#: inside that gap decides none.) WP 21 has a Fraktion Die Linke again.
GRUPPE_DIE_LINKE_SINCE = "2023-12-06"


VOTE_COUNT_KEYS = ("yes", "no", "abstain", "absent")


def merge_fractions(fractions: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """The fraction rows of one namentliche Abstimmung, one per Zusammenschluss.

    Rows that name the same Zusammenschluss under two spellings ("Gruppe BSW",
    "BSW (Gruppe)") are one row: their counts add. Persistence, the vote panel
    and the votes archive all go through this, so none of them can show a
    Mehrheitsvotum that another does not hold. Rows come back in first-seen
    order, named as ``zusammenschluss`` names them ("Unbekannt" for none).
    """
    merged: dict[str, dict[str, Any]] = {}
    for fraction in fractions or []:
        counts = fraction.get("counts") or {}
        row = merged.setdefault(
            zusammenschluss(fraction.get("name")) or "Unbekannt",
            {"counts": {key: 0 for key in VOTE_COUNT_KEYS}, "total": 0},
        )
        for key in VOTE_COUNT_KEYS:
            row["counts"][key] += int(counts.get(key) or 0)
        row["total"] += int(fraction.get("total") or 0)
    return [{"name": name, **row} for name, row in merged.items()]


def speech_zusammenschluss(speaker: Mapping[str, Any] | None, protocol: Mapping[str, Any] | None = None) -> str | None:
    """The Zusammenschluss the Plenarprotokoll names beside a Redner for one
    Rede: ``zusammenschluss`` of the raw string, told apart by the Sitzung when
    the same spelling names two Zusammenschlüsse (WP 20 Gruppe Die Linke against
    the Fraktion Die Linke)."""
    name = zusammenschluss((speaker or {}).get("fraktion"))
    if name == "Die Linke" and protocol:
        wahlperiode = str(protocol.get("dokumentnummer") or "").split("/")[0]
        if wahlperiode == "20" and str(protocol.get("datum") or "") >= GRUPPE_DIE_LINKE_SINCE:
            return GRUPPE_DIE_LINKE
    return name


# --- Redner ------------------------------------------------------------------


def redner_ids(value: Any) -> list[str]:
    """The ids in a ``<redner id>`` attribute. Bundestag's merged records carry
    two in one attribute ("11005217 999990074"); the first is the person."""
    return str(value if value is not None else "").split()


def first_redner_id(value: Any) -> str | None:
    ids = redner_ids(value)
    return ids[0] if ids else None


def undouble(text: Any) -> str | None:
    """A name with every word made of two identical halves halved
    ("SvenjaSvenja SchulzeSchulze" -> "Svenja Schulze"): the XML of a merged
    record writes each name field twice. Names start with a capital, so a real
    word never has two identical halves."""
    words = str(text if text is not None else "").split()
    if not words:
        return None
    halved = [word[: len(word) // 2] if len(word) % 2 == 0 and word[: len(word) // 2] == word[len(word) // 2 :] else word for word in words]
    return " ".join(halved)


def speaker_display_name(speaker: Mapping[str, Any] | None) -> str:
    return undouble((speaker or {}).get("display_name")) or "Unbekannt"


# --- Sprechrolle ---------------------------------------------------------------

#: The three sides a Rede in a Sprechrolle counts for (ADR 0001, amendment
#: 2026-09-26). A speaker with no <rolle> has no Sprechrolle (None).
SPRECHROLLE_LABELS = {
    "bundesregierung": "Bundesregierung",
    "bundesrat": "Bundesrat",
    "weitere": "weitere Sprechrolle",
}

_LAENDER = (
    "Baden-Württemberg|Bayern|Berlin|Brandenburg|Bremen|Hamburg|Hessen|Mecklenburg-Vorpommern|Niedersachsen|"
    "Nordrhein-Westfalen|Rheinland-Pfalz|Saarland|Sachsen-Anhalt|Sachsen|Schleswig-Holstein|Thüringen"
)

#: Which side each ``<rolle_lang>`` string counts for: (pattern matching the
#: whole string, side), first match wins. To map a new role add it here (the
#: build names it and where when one is missing).
SPRECHROLLE_RULES: tuple[tuple[str, str], ...] = (
    # A Land in brackets: Ministerpräsident(in), Minister(in), Staatsminister(in),
    # Senator(in), Bürgermeister (Hessen), ... speak for the Bundesrat.
    (rf".+ \(({_LAENDER})\)", "bundesrat"),
    # Auxiliary organs of the Bundestag: neither government nor Bundesrat.
    (r"Wehrbeauftragte[r]? des Deutschen Bundestages", "weitere"),
    (r"Polizeibeauftragte[r]? des Bundes beim Deutschen Bundestag", "weitere"),
    # Who speaks for the Bundesregierung: its members (Art. 62 GG) and those who
    # speak on its behalf (ADR 0001).
    (r"Bundeskanzler(in)?", "bundesregierung"),
    (r"Bundesminister(in)?( .+)?", "bundesregierung"),
    (r"Parl\. Staatssekretär(in)? (beim|bei der|bei) .+", "bundesregierung"),
    # Explicit historical government role in 19/13, Redner 999990013.
    (r"Staatssekretär(in)? im Bundeskanzleramt", "bundesregierung"),
    (r"Staatsminister(in)? (beim|bei der|bei|im) .+", "bundesregierung"),
    (r"Beauftragte[r]? (der Bundesregierung|des Bundesministeriums) .+", "bundesregierung"),
    (r"Koordinator(in)? der Bundesregierung .+", "bundesregierung"),
)
_COMPILED_RULES = tuple((re.compile(pattern), side) for pattern, side in SPRECHROLLE_RULES)


class SprechrolleError(Exception):
    """Speaker roles no rule maps; the message is the finished ``ERROR [sprechrolle]`` line."""


def role_text(speaker: Mapping[str, Any] | None) -> str:
    """The ``<rolle_lang>`` of a speaker (``role``), else its short form."""
    speaker = speaker or {}
    return _clean(speaker.get("role") or speaker.get("role_short"))


def side_of_role(text: str) -> str | None:
    """The side a role string counts for, or None when no rule maps it."""
    for pattern, side in _COMPILED_RULES:
        if pattern.fullmatch(text):
            return side
    return None


def sprechrolle(speaker: Mapping[str, Any] | None, *, strict: bool = True) -> str | None:
    """The side one Rede counts for, None for a speaker without a role.

    A speaker dict that already carries a derived ``sprechrolle`` (a row read
    from the store) keeps it. A role no rule maps raises SprechrolleError under
    ``strict`` (persist: nothing is silently guessed) and reads as None
    otherwise (a page must render).
    """
    if speaker and "sprechrolle" in speaker:
        return speaker["sprechrolle"] or None
    text = role_text(speaker)
    if not text:
        return None
    side = side_of_role(text)
    if side is None and strict:
        raise SprechrolleError(f'no Sprechrolle rule maps the role "{text}"')
    return side


def unmapped_sprechrollen_error(unmapped: Mapping[str, list[str]], *, limit: int = 4) -> SprechrolleError:
    """One error naming every unmapped role with where it occurs (protocol and
    Rede id), where the rules live and what to do."""
    parts = []
    for role in sorted(unmapped):
        where = unmapped[role]
        shown = ", ".join(where[:limit]) + (f" and {len(where) - limit} more" if len(where) > limit else "")
        parts.append(f'"{role}" ({shown})')
    return SprechrolleError(
        f"ERROR [sprechrolle]: {len(unmapped)} speaker role(s) map to no Sprechrolle: {'; '.join(parts)}. "
        "The previous store is untouched. "
        "Fix: add each role to SPRECHROLLE_RULES in scripts/derive.py as bundesregierung, bundesrat or weitere. "
        "Docs: README.md#sprechrolle-rules"
    )


def find_unmapped_sprechrollen(reports: Iterable[Mapping[str, Any]]) -> dict[str, list[str]]:
    """Every distinct role in the reports' speakers that no rule maps, with
    "protocol Rede-id" for each occurrence."""
    unmapped: dict[str, list[str]] = {}
    for report in reports:
        number = _clean((report.get("protocol") or {}).get("dokumentnummer")) or "?"
        for item in [report, *(report.get("agenda_items") or [])]:
            for speech in [*(item.get("xml_speakers") or []), *(item.get("xml_contributions") or [])]:
                text = role_text(speech.get("speaker"))
                if text and side_of_role(text) is None:
                    unmapped.setdefault(text, []).append(f"{number} {speech.get('rede_id') or '?'}")
    return unmapped


def check_sprechrollen(reports: Iterable[Mapping[str, Any]]) -> None:
    """Raise one SprechrolleError listing every unmapped role of ``reports``."""
    unmapped = find_unmapped_sprechrollen(reports)
    if unmapped:
        raise unmapped_sprechrollen_error(unmapped)


#: The Zusammenschluss a speech counts for in SQL, given ``speeches s`` and
#: ``parties pa`` (the speaker's row): none for a Rede in a Sprechrolle (it
#: counts for its side), else the Zusammenschluss the Plenarprotokoll names,
#: else the speaker's party as the store holds it (an approximation of the
#: Zugehörigkeit on the day, ADR 0001).
ZUSAMMENSCHLUSS_SQL = (
    "CASE WHEN s.sprechrolle IS NOT NULL THEN NULL ELSE COALESCE(NULLIF(s.fraktion, ''), pa.name) END"
)


# --- Personenkennung -----------------------------------------------------------

#: The match kind of an abgeordnetenwatch lookup by the Redner-ID sent to its
#: ext_id field. That id is a Personenkennung: the Bundestag assigned it to the
#: Person, and abgeordnetenwatch records it for the same Person. Any other kind
#: ("name": found by searching a name) is a Namensabgleich, a guess.
TRUSTED_AW_MATCH = "ext_id"


def trusted_aw_id(profile: Mapping[str, Any] | None, match: Any = None) -> int | None:
    """The abgeordnetenwatch id of ``profile`` when it may serve as identity,
    else None. An id with no recorded match kind (a cache from before the kind
    was kept) counts as found by name, until it is resolved again."""
    profile = profile or {}
    kind = match if match is not None else profile.get("match")
    value = profile.get("id")
    return value if isinstance(value, int) and kind == TRUSTED_AW_MATCH else None


def item_votes(item: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The roll-call votes listed under one TOP."""
    return item.get("votes") or []


def vote_identity(vote: Mapping[str, Any]) -> str:
    """A vote's identity within a sitting: its id. The scraper always sets one,
    and report loading refuses a vote without it."""
    return str(vote["id"])


def iter_report_votes(report: Mapping[str, Any]):
    """Yield (TOP or None, vote), once per vote identity across a sitting."""
    seen = set()
    for item in report.get("agenda_items") or []:
        for vote in item_votes(item):
            key = vote_identity(vote)
            if key not in seen:
                seen.add(key)
                yield item, vote
    for vote in report.get("sitting_votes") or []:
        key = vote_identity(vote)
        if key not in seen:
            seen.add(key)
            yield None, vote


def _normalised_title(title: Any) -> str:
    return " ".join(str(title or "").split())


def agenda_procedures(item: Mapping[str, Any]) -> tuple[list[dict[str, str]], dict[str, str] | None]:
    """The DIP procedures of one agenda item, and the lead among them.

    Procedures come from ``api.positions`` in DIP order, then from each position's
    ``mitberaten`` twins (they carry id, titel, vorgangstyp and vorgangsposition;
    in 40 TOPs of the archive the only Gesetzgebung procedure is a twin). Dedup is
    first-seen by id; titles are whitespace-normalised.

    Lead = the first Gesetzgebung procedure, else the first procedure, else None.
    """
    positions = (item.get("api") or {}).get("positions") or []
    procedures: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    def add(record: Mapping[str, Any], vorgang_id: Any) -> None:
        key = str(vorgang_id or "")
        if not key or key in seen_ids:
            return
        seen_ids.add(key)
        procedures.append(
            {
                "vorgang_id": key,
                "titel": _normalised_title(record.get("titel")),
                "vorgangstyp": str(record.get("vorgangstyp") or ""),
                "vorgangsposition": str(record.get("vorgangsposition") or ""),
            }
        )

    for position in positions:
        add(position, position.get("vorgang_id"))
    for position in positions:
        for twin in position.get("mitberaten") or []:
            add(twin, twin.get("id"))

    lead = next((p for p in procedures if p["vorgangstyp"] == "Gesetzgebung"), None)
    if lead is None and procedures:
        lead = procedures[0]
    return procedures, lead


#: A Drucksache number's shape, e.g. "21/6561" (ASCII digits, like stable_ids).
DOCUMENT_NUMBER_RE = re.compile(r"\b[0-9]{1,2}/[0-9]{1,6}\b")


def is_bundestag_xml_url(url: Any) -> bool:
    """Whether a Drucksache link of the XML parser points at the Bundestag's XML
    host. Reports cached before ``validate_dip_protocol.extract_drucksachen``
    checked the host still hold numbers read off news-site URLs ("11/09" from a
    dated euronews path); persist and the Politikfelder both skip those."""
    parts = urlsplit(str(url))
    return parts.scheme == "https" and (parts.hostname or "").lower().rstrip(".") in publication.SOURCE_HOSTS["bundestag-xml"]


def report_wahlperiode(report: Mapping[str, Any]) -> str:
    """The Wahlperiode of a sitting, from its protocol number "20/194" ("" if unknown)."""
    number = str((report.get("protocol") or {}).get("dokumentnummer") or "")
    return number.split("/")[0] if "/" in number else ""


def plausible_document_number(number: Any, wahlperiode: str) -> bool:
    """Whether a Drucksache number can belong to a sitting of ``wahlperiode``: its
    prefix is that Wahlperiode or the one before (16 of 5,414 numbers in the archive
    cite the earlier one). Anything else is a case number or a fragment such as
    "76/787" or "2/3"; with no known Wahlperiode nothing is filtered."""
    if not (wahlperiode.isascii() and wahlperiode.isdigit()):
        return True
    return str(number).split("/")[0] in {wahlperiode, str(int(wahlperiode) - 1)}


def canonical_document_number(number: Any) -> str:
    """A Bundestag Drucksache number as the store keys it (``stable_ids.document_number``:
    "21/06561" is "21/6561"), so the Politikfelder look up and cache the same text."""
    return document_number(number, "BT") or ""


def item_document_numbers(item: Mapping[str, Any], wahlperiode: str) -> list[str]:
    """Drucksache numbers an agenda item names, in first-seen order.

    The XML parser's ``xml_drucksachen`` and the API's ``linked_drucksachen``
    (the numbers ``validate_dip_protocol.top_document_numbers`` reads), then
    numbers in the heading. A heading also carries case numbers of other
    shapes ("10/21", "1/22" in Streitsachen lists), so every number counts only
    when ``plausible_document_number`` accepts it. The same rules as persist
    decide what is a Bundestag Drucksache: an XML number only from the XML host,
    a linked paper only when ``stable_ids.document_issuer`` says BT, and every
    number in its canonical form.
    """
    numbers: list[str] = []

    def add(number: Any) -> None:
        text = canonical_document_number(number)
        if text and text not in numbers and plausible_document_number(text, wahlperiode):
            numbers.append(text)

    for doc in item.get("xml_drucksachen") or []:
        if not doc.get("url") or is_bundestag_xml_url(doc["url"]):
            add(doc.get("dokumentnummer"))
    for doc in (item.get("api") or {}).get("linked_drucksachen") or []:
        # A Bundesrat paper ("20/23" at .../brd/2023/0020-23.pdf) shares the shape of a Bundestag number.
        if document_issuer(doc.get("herausgeber"), doc.get("url")) == "BT":
            add(doc.get("dokumentnummer"))
    for number in DOCUMENT_NUMBER_RE.findall(str(item.get("heading") or "")):
        add(number)
    return numbers


#: Groups whose MdBs have no Zusammenschluss, so none of them can make an Abweichung.
NO_ZUSAMMENSCHLUSS = frozenset({"fraktionslos", "Unbekannt"})


def vote_abweichler(vote: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """The Abweichler of one namentliche Abstimmung, per Zusammenschluss.

    The Mehrheitsvotum comes from the group's reported fraction counts, never
    from its member list; a member is an Abweichler on Ja against a Nein
    Mehrheitsvotum or Nein against a Ja one. Inversion changes what Ja means,
    not who voted unlike their group, so it plays no part here.

        no member rows, though counts say some ► none     (nobody named)
        member Stimmen ≠ fraction counts ──────► partial  (nobody named)
        counts match ─► Mehrheitsvotum Ja/Nein? ─no─► complete, no members
                                               └yes─► complete, members with
                                                      the opposite Ja/Nein

    fraktionslos and an unknown affiliation are no Zusammenschluss and get no
    entry. Members come back alphabetical, as the Einzelstimmen list them.
    """
    members_by_group: dict[str, list[Mapping[str, Any]]] = {}
    for member in vote.get("members") or []:
        members_by_group.setdefault(zusammenschluss(member.get("faction")) or "Unbekannt", []).append(member)
    result: dict[str, dict[str, Any]] = {}
    for fraction in merge_fractions(vote.get("fractions")):
        name = fraction["name"]
        if name in NO_ZUSAMMENSCHLUSS:
            continue
        members = members_by_group.get(name) or []
        stimmen = Counter(str(member.get("vote") or "") for member in members)
        if not members and stimmen != Counter(fraction["counts"]):
            result[name] = {"members": [], "state": "none"}
            continue
        if stimmen != Counter(fraction["counts"]):
            result[name] = {"members": [], "state": "partial"}
            continue
        leading = majority_vote(fraction["counts"])
        abweichler = [
            member for member in members
            if leading in {"yes", "no"} and member.get("vote") in {"yes", "no"} and member.get("vote") != leading
        ]
        result[name] = {"members": sorted(abweichler, key=lambda member: str(member.get("name") or "")), "state": "complete"}
    return result


def report_drucksachen(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Bundestag Drucksache number -> its DIP record, from every TOP of a sitting.

    A vote's Drucksachen are often linked under another TOP of the same
    sitting than the one the vote sits under (5 of 217 Beschlussempfehlungen
    on the reference store), so a vote is matched against the whole sitting.
    First-seen wins; Bundesrat papers, which share the number shape, are left out.
    """
    documents: dict[str, Mapping[str, Any]] = {}
    for item in report.get("agenda_items") or []:
        for doc in (item.get("api") or {}).get("linked_drucksachen") or []:
            if document_issuer(doc.get("herausgeber"), doc.get("url")) != "BT":
                continue
            number = canonical_document_number(doc.get("dokumentnummer"))
            if number:
                documents.setdefault(number, doc)
    return documents


def vote_committees(vote: Mapping[str, Any], report: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The Beschlussempfehlungen among a vote's Drucksachen, with their urheber.

    One entry per matched Drucksache, in the vote's order: its number, DIP
    type, the committees DIP names as its urheber, and its URL. This cites a
    document and claims no role: a vote on an Entschließungsantrag lists the
    law's Beschlussempfehlung too. A Beschlussempfehlung without an urheber
    names no committee and is left out, as the store's join leaves it out.
    """
    documents = report_drucksachen(report)
    committees: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in vote.get("document_numbers") or []:
        number = canonical_document_number(raw)
        doc = documents.get(number)
        if not doc or number in seen or not str(doc.get("drucksachetyp") or "").startswith("Beschlussempfehlung"):
            continue
        urheber = list(dict.fromkeys(_clean(name) for name in doc.get("urheber") or [] if _clean(name)))
        if not urheber:
            continue
        seen.add(number)
        committees.append(
            {"number": number, "drucksachetyp": str(doc.get("drucksachetyp")), "urheber": urheber, "url": doc.get("url")}
        )
    return committees


def vote_outcome(vote: Mapping[str, Any]) -> str | None:
    """Outcome of the Antrag, separately from the voted recommendation."""
    result = vote.get("result_raw")
    if result not in {"accepted", "rejected"}:
        return None
    if vote.get("inverted") and vote.get("result_scope") != "application":
        return "rejected" if result == "accepted" else "accepted"
    return result


def fraction_position(counts: Mapping[str, Any] | None, inverted: bool | None = None) -> str | None:
    leading = majority_vote(counts)
    if inverted:
        if leading == "yes":
            return "gegen den Antrag"
        if leading == "no":
            return "für den Antrag"
        if leading == "abstain":
            return "Enthaltung"
        if any(int((counts or {}).get(key) or 0) for key in MAJORITY_KEYS):
            return "geteilt"
        return None
    return {"yes": "Ja", "no": "Nein", "abstain": "Enthaltung"}.get(leading)
