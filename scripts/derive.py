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
from typing import Any, Iterable, Mapping

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
        for item in report.get("agenda_items") or []:
            for speech in item.get("xml_speakers") or []:
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
