"""Lazy discovery for enabled Bundestag-Puls addon components."""

from __future__ import annotations

import importlib

from . import Component, Selection


MODULES = {
    "votes": "votes",
    "summaries": "summaries",
    "aw-profiles": "aw_profiles",
    "mp-pages": "abgeordnete",
    "bills": "bills",
    "dev-view": "devview",
}


def load(selection: Selection) -> tuple[Component, ...]:
    components = []
    for feature_id, module_name in MODULES.items():
        if feature_id not in selection:
            continue
        module = importlib.import_module(f"{__package__}.{module_name}")
        components.append(module.COMPONENT)
    return tuple(components)
