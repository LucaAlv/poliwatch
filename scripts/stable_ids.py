"""Versioned identifiers derived only from source natural keys."""
import hashlib
import json
from typing import Any

KEY_VERSION = 1

#: The separator between a synthetic rede_id's protocol_id and the rest.
#: facts.is_synthetic_rede_id() checks for "<protocol_id>SYNTHETIC_REDE_ID_SEPARATOR"
#: to recognize a row the store filled, so the two must stay in sync.
SYNTHETIC_REDE_ID_SEPARATOR = ":"


def stable_key(namespace: str, *source: object) -> str:
    payload = json.dumps([KEY_VERSION, namespace, source], ensure_ascii=False,
                         sort_keys=True, separators=(",", ":"), allow_nan=False)
    return f"{namespace}-v{KEY_VERSION}-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def key_prefix(namespace: str) -> str:
    """The text every ``stable_key(namespace, ...)`` starts with."""
    return f"{namespace}-v{KEY_VERSION}-"


def synthetic_rede_id(protocol_id: Any, item_index: Any, sequence: Any) -> str:
    """The rede_id a speech gets when the XML carries none: protocol, source item index, sequence."""
    return f"{protocol_id}{SYNTHETIC_REDE_ID_SEPARATOR}{item_index}:{sequence}"


def speech_rede_id(protocol_id: Any, item_index: Any, sequence: Any, rede_id: Any) -> str:
    text = " ".join(str(rede_id).replace("\xa0", " ").split()) if rede_id is not None else ""
    return text or synthetic_rede_id(protocol_id, item_index, sequence)


def speech_occurrence_id(protocol_id: Any, rede_id: str) -> str:
    return stable_key("speech", str(protocol_id), rede_id)


def roster_occurrence_id(dip_person_id: Any) -> str | None:
    """A roster row is an occurrence only through its DIP person id; rows without
    one would otherwise all share the key of ``None``."""
    return stable_key("roster", dip_person_id) if dip_person_id else None


def vote_member_occurrence_id(vote_id: Any, name: Any, party: Any) -> str:
    return stable_key("vote-member", vote_id, name, party)
