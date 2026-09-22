"""Lazy discovery for Bundestag-Puls public components.

Public components are product structure, not visitor preferences.  Only the
developer component is conditional, through an explicit build flag.
"""

from __future__ import annotations

import importlib

from . import Component, Selection


PUBLIC_MODULES = {
    "votes": "votes",
    "summaries": "summaries",
    "aw-profiles": "aw_profiles",
    "mp-pages": "abgeordnete",
    "bills": "bills",
    "facts": "facts",
}


def load(
    selection: Selection | None = None,
    *,
    include_dev_view: bool = False,
) -> tuple[Component, ...]:
    """Load every public component plus the explicitly requested dev view.

    ``selection`` remains accepted during the 0.5.x operator migration, but it
    no longer controls which public components exist.
    """
    components = []
    modules = dict(PUBLIC_MODULES)
    if include_dev_view:
        modules["dev-view"] = "devview"
    for module_name in modules.values():
        module = importlib.import_module(f"{__package__}.{module_name}")
        components.append(module.COMPONENT)
    return tuple(components)
