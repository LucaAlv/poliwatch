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

from typing import Any, Mapping

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
