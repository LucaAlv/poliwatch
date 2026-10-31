"""Shared roll-call helpers for the vote panel and Abweichler tests."""
from __future__ import annotations

from collections.abc import Iterable, Mapping

import _support  # noqa: F401
import politikfelder
from features.votes import VotePanelContext, render_vote_summary


def fractions_of(members: Iterable[Mapping[str, str]]) -> list[dict[str, object]]:
    """Fraction rows whose counts are exactly ``members``' votes, in first-seen order."""
    tallies: dict[str, dict[str, int]] = {}
    for member in members:
        counts = tallies.setdefault(member["faction"], {"yes": 0, "no": 0, "abstain": 0, "absent": 0})
        counts[member["vote"]] += 1
    return [{"name": name, "counts": counts, "total": sum(counts.values())} for name, counts in tallies.items()]


def panel_for(item: dict[str, object], **overrides: object) -> VotePanelContext:
    """The panel context a dossier page passes, for a report holding only ``item``
    unless ``report`` is given; ``vote_contexts`` is derived from the report and
    ``vorgang_cache`` as the page derives it."""
    report = overrides.pop("report", None) or {"agenda_items": [item]}
    cache = overrides.pop("vorgang_cache", None) or politikfelder.empty_cache()
    fields = {
        "report": report,
        "vote_contexts": politikfelder.report_vote_vorgaenge(report, cache),
        "vorgang_cache": cache,
        "mp_lookup": None,
        "mp_prefix": "../abgeordnete/",
        "site_prefix": "../",
    }
    fields.update(overrides)
    return VotePanelContext(**fields)


def vote_summary(item: dict[str, object], acquisition: dict[str, object] | None = None, **overrides: object) -> str:
    return render_vote_summary(item, acquisition, panel_for(item, **overrides))
