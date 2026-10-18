"""Versioned identifiers derived only from source natural keys."""
import hashlib
import json
import re
from typing import Any
from urllib.parse import urlsplit

KEY_VERSION = 1

#: The separator between a synthetic rede_id's protocol_id and the rest.
#: facts.is_synthetic_rede_id() checks for "<protocol_id>SYNTHETIC_REDE_ID_SEPARATOR"
#: to recognize a row the store filled, so the two must stay in sync.
SYNTHETIC_REDE_ID_SEPARATOR = ":"

_DIGITS = re.compile(r"[0-9]+")


def stable_key(namespace: str, *source: object) -> str:
    payload = json.dumps([KEY_VERSION, namespace, source], ensure_ascii=False,
                         sort_keys=True, separators=(",", ":"), allow_nan=False)
    return f"{namespace}-v{KEY_VERSION}-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def key_prefix(namespace: str) -> str:
    """The text every ``stable_key(namespace, ...)`` starts with."""
    return f"{namespace}-v{KEY_VERSION}-"


def source_index(value: Any) -> int:
    """An agenda item's source index (``item["index"]`` in a report) as the int
    every key, lookup and anchor uses: 3, "3" and " 03 " are one item. The XML
    numbers items from 1, so a missing index (None) stays 0, as it always has
    been read; the cached-report load refuses an item without one. A bool, a
    negative, non-integral or non-numeric value is a malformed report."""
    if value is None:
        return 0
    if isinstance(value, bool):
        raise ValueError(f"agenda source index must be an integer, got {value!r}")
    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and _DIGITS.fullmatch(value.strip()):
        number = int(value.strip())
    else:
        raise ValueError(f"agenda source index must be an integer, got {value!r}")
    if number < 0:
        raise ValueError(f"agenda source index must not be negative, got {value!r}")
    return number


def synthetic_rede_id(protocol_id: Any, item_index: Any, sequence: Any) -> str:
    """The rede_id a speech gets when the XML carries none: protocol, source item index, sequence."""
    return f"{protocol_id}{SYNTHETIC_REDE_ID_SEPARATOR}{item_index}:{sequence}"


def speech_rede_id(protocol_id: Any, item_index: Any, sequence: Any, rede_id: Any) -> str:
    text = " ".join(str(rede_id).replace("\xa0", " ").split()) if rede_id is not None else ""
    return text or synthetic_rede_id(protocol_id, item_index, sequence)


def speech_occurrence_id(protocol_id: Any, rede_id: str) -> str:
    return stable_key("speech", str(protocol_id), rede_id)


def contribution_occurrence_id(protocol_id: Any, item_index: Any, sequence: Any, rede_id: Any) -> str:
    """A Beitrag by its rede id; a Fragestunde turn has none and goes by its
    source item index and sequence within the item."""
    if rede_id:
        return stable_key("contribution", str(protocol_id), str(rede_id))
    return stable_key("contribution", str(protocol_id), int(item_index), int(sequence))


def canonical_dip_person_id(value: Any) -> str | None:
    """A DIP person id in one canonical form, the decimal text DIP prints:
    7, "7" and " 07 " are all "7". Other text is kept, whitespace collapsed (DIP
    ids are numeric, but nothing here should merge two ids it cannot read).
    None, "", 0, a bool or any other type is no id: the caller skips such a row
    as id-less rather than minting a key from it."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    text = " ".join(str(value).replace("\xa0", " ").split())
    if _DIGITS.fullmatch(text):
        return str(int(text)) if int(text) > 0 else None
    return text or None


def roster_occurrence_id(dip_person_id: Any) -> str | None:
    """A roster row is an occurrence only through its DIP person id; rows without
    one would otherwise all share the key of ``None``."""
    canonical = canonical_dip_person_id(dip_person_id)
    return stable_key("roster", canonical) if canonical else None


def vote_member_occurrence_id(vote_id: Any, name: Any, party: Any) -> str:
    return stable_key("vote-member", vote_id, name, party)


#: Who issued a Drucksache, as DIP's ``herausgeber`` names it. The Bundestag
#: numbers its Drucksachen Wahlperiode/number (20/23), the Bundesrat
#: number/year (23/20, zu40/23, 137/1/23), so one number text can name a
#: document of each.
DOCUMENT_ISSUERS = ("BT", "BR")
_BT_NUMBER = re.compile(r"([0-9]{1,2})/([0-9]{1,6})")


def document_issuer(herausgeber: Any = None, url: Any = None) -> str:
    """BT or BR. DIP's ``herausgeber`` decides; reports cached before it was kept
    fall back to the dserver path (``/btd/`` or ``/brd/``), the only place a URL
    still feeds identity. A number with neither (an XML anchor without a link, a
    roll-call document number) is a Bundestag Drucksache."""
    text = str(herausgeber or "").strip().upper()
    if text in DOCUMENT_ISSUERS:
        return text
    path = urlsplit(str(url or "")).path
    if path.startswith("/brd/"):
        return "BR"
    return "BT"


def document_number(number: Any, issuer: str = "BT") -> str | None:
    """The number text a Drucksache is keyed by: whitespace collapsed, and a
    Bundestag number without leading zeros (20/08601 is 20/8601). Bundesrat
    forms stay as printed: their year part is two digits on purpose."""
    text = " ".join(str(number or "").replace("\xa0", " ").split())
    if not text:
        return None
    match = _BT_NUMBER.fullmatch(text) if issuer == "BT" else None
    if match:
        return f"{int(match.group(1))}/{int(match.group(2))}"
    return text


def document_id(issuer: str, number: str) -> str:
    """A Drucksache by its issuer and number. The URL is an attribute: DIP can
    move a PDF without the document becoming another one."""
    return stable_key("document", issuer, number)


def document_sort_key(number: Any) -> tuple[int, int, int, str]:
    """Order Plenarprotokoll/Drucksache numbers as WP/number, numerically
    (21/9 before 21/10); a malformed number sorts after every well-formed one,
    by its text, so the order stays total."""
    text = str(number or "").strip()
    match = re.fullmatch(r"([0-9]+)/([0-9]+)", text)
    if match:
        return (0, int(match.group(1)), int(match.group(2)), text)
    return (1, 0, 0, text)
