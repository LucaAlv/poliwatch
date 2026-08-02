"""Bundestag-Puls feature registry.

This module deliberately depends on the standard library only.  Renderers may import the
registry, while :mod:`features.loader` performs the lazy component imports after the build
module has finished loading.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator, Protocol


@dataclass(frozen=True)
class Feature:
    id: str
    label: str
    description: str
    category: str
    core: bool = False
    default_built: bool = False
    default_visible: bool = True
    requires: tuple[str, ...] = ()
    enhances: tuple[str, ...] = ()
    nav_key: str | None = None
    client_mode: str = "hide"
    costs_network: bool = False
    rebuild_hint: str = ""


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    path: str
    feature_id: str | None = None


NAV_ITEMS = (
    NavItem("pulse", "Aktueller Puls", "puls.html"),
    NavItem("overview", "Plenarprotokoll-Katalog", "overview.html"),
    NavItem("catalog", "Alle API-Sitzungen", "api-sitzungen.html"),
    NavItem("bills", "Gesetze verfolgen", "bills/index.html", "bills"),
    NavItem("abgeordnete", "Abgeordnete", "abgeordnete/index.html", "mp-pages"),
    NavItem("database", "Datenbank", "database.html"),
    NavItem("sources", "Quellen und Methode", "sources.html"),
)


FEATURES = (
    Feature("dip-fetch", "DIP-Daten", "Ruft die offiziellen DIP-Daten des Bundestags ab.", "Kern", True, True, client_mode="none"),
    Feature("sitting-catalog", "Sitzungskatalog", "Zeigt den Katalog der Plenarprotokolle und API-Sitzungen.", "Kern", True, True, requires=("dip-fetch",), nav_key="overview", client_mode="none"),
    Feature("dossiers", "Protokoll-Dossiers", "Erzeugt die Detailansichten der Plenarprotokolle.", "Kern", True, True, requires=("dip-fetch",), client_mode="none"),
    Feature("store", "Datenbank", "Speichert die verknüpften Parlamentsdaten in SQLite.", "Kern", True, True, requires=("dip-fetch",), nav_key="database", client_mode="none"),
    Feature("votes", "Namentliche Abstimmungen", "Ergänzt Abstimmungssummen, Fraktionen und einzelne Stimmen.", "Analyse", requires=("dip-fetch",), enhances=("mp-pages", "aw-profiles"), costs_network=True, rebuild_hint="Bundestag-Abstimmungen werden beim nächsten Build abgerufen."),
    Feature("summaries", "KI-Zusammenfassungen", "Ergänzt KI-generierte Zusammenfassungen der Sitzung und Tagesordnungspunkte.", "Analyse", requires=("dip-fetch",), costs_network=True, rebuild_hint="Zusammenfassungen können zusätzliche API-Kosten verursachen."),
    Feature("aw-profiles", "abgeordnetenwatch-Profile", "Verknüpft Redner und Abstimmende mit ihren öffentlichen Profilen.", "Analyse", requires=("dip-fetch",), costs_network=True, rebuild_hint="Profildaten werden beim nächsten Build abgerufen."),
    Feature("mp-pages", "Abgeordnete", "Erzeugt Übersichts- und Profilseiten für Abgeordnete.", "Bereiche", requires=("store",), nav_key="abgeordnete"),
    Feature("mp-roster", "Vollständiger MdB-Kader", "Erweitert die Abgeordnetenseiten um den vollständigen DIP-Kader.", "Bereiche", requires=("mp-pages",), client_mode="none", costs_network=True, rebuild_hint="Der vollständige Kader wird beim nächsten Build abgerufen."),
    Feature("bills", "Gesetze verfolgen", "Erzeugt Übersichts- und Detailseiten für Gesetzgebungsvorgänge.", "Bereiche", requires=("dip-fetch",), nav_key="bills"),
    Feature("bill-follow", "Gesetze merken", "Erlaubt es, Gesetze lokal im Browser zu markieren.", "Bereiche", requires=("bills",)),
    Feature("dev-view", "Dev-Ansicht", "Zeigt Rohdaten, API-Antworten und Build-Kommandos.", "Entwicklung", default_visible=False, requires=("dossiers",), client_mode="reveal"),
)

REGISTRY = {feature.id: feature for feature in FEATURES}
CATEGORIES = tuple(dict.fromkeys(feature.category for feature in FEATURES))


class FeatureError(ValueError):
    """Raised for an invalid or impossible feature selection."""


@dataclass(frozen=True)
class Selection:
    ids: frozenset[str]

    def __contains__(self, feature_id: object) -> bool:
        return feature_id in self.ids

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self.ids))

    def __len__(self) -> int:
        return len(self.ids)

    def enabled(self, feature_id: str) -> bool:
        return feature_id in self.ids


def _known(feature_ids: Iterable[str]) -> set[str]:
    result = {str(feature_id).strip() for feature_id in feature_ids if str(feature_id).strip()}
    unknown = result.difference(REGISTRY)
    if unknown:
        choices = ", ".join(REGISTRY)
        raise FeatureError(f"Unbekannter Baustein: {', '.join(sorted(unknown))}. Verfügbar: {choices}")
    return result


def default_selection() -> Selection:
    return resolve(base=(feature.id for feature in FEATURES if feature.default_built))


def all_selection() -> Selection:
    return resolve(base=REGISTRY)


def resolve(
    *,
    base: Iterable[str] | None = None,
    enable: Iterable[str] = (),
    disable: Iterable[str] = (),
) -> Selection:
    """Resolve requirements and explicit vetoes to a stable selection."""
    selected = _known(base if base is not None else (f.id for f in FEATURES if f.default_built))
    enabled = _known(enable)
    vetoed = _known(disable)
    core_vetoes = sorted(feature_id for feature_id in vetoed if REGISTRY[feature_id].core)
    if core_vetoes:
        raise FeatureError(f"Kern-Bausteine können nicht deaktiviert werden: {', '.join(core_vetoes)}")

    selected.update(feature.id for feature in FEATURES if feature.core)
    selected.update(enabled)
    selected.difference_update(vetoed)
    noted: set[tuple[str, str, str]] = set()
    changed = True
    while changed:
        changed = False
        for feature_id in tuple(selected):
            feature = REGISTRY[feature_id]
            blocked = next((required for required in feature.requires if required in vetoed), None)
            if blocked:
                selected.remove(feature_id)
                note = ("drop", feature_id, blocked)
                if note not in noted:
                    print(
                        f"Baustein '{feature_id}' deaktiviert, weil Voraussetzung '{blocked}' ausdrücklich deaktiviert ist.",
                        file=sys.stderr,
                    )
                    noted.add(note)
                changed = True
                continue
            for required in feature.requires:
                if required not in selected:
                    selected.add(required)
                    note = ("add", feature_id, required)
                    if note not in noted:
                        print(
                            f"Baustein '{required}' automatisch aktiviert (Voraussetzung für '{feature_id}').",
                            file=sys.stderr,
                        )
                        noted.add(note)
                    changed = True
    return Selection(frozenset(selected))


def inline_manifest(selection: Selection) -> dict[str, dict[str, int | str]]:
    modes = {"hide": "h", "reveal": "r", "none": "n"}
    return {
        feature.id: {
            "a": int(feature.id in selection),
            "v": int(feature.default_visible),
            "c": int(feature.core),
            "m": modes[feature.client_mode],
        }
        for feature in FEATURES
    }


def manifest_json(selection: Selection) -> str:
    """Return the compact, safe-to-inline browser manifest."""
    return json.dumps(inline_manifest(selection), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def tooling_manifest(selection: Selection, *, generated_at: str | None = None) -> dict[str, Any]:
    return {
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "features": [
            {
                "id": feature.id,
                "label": feature.label,
                "description": feature.description,
                "category": feature.category,
                "available": feature.id in selection,
                "visible": feature.default_visible,
                "core": feature.core,
                "mode": feature.client_mode,
                "requires": list(feature.requires),
                "enhances": list(feature.enhances),
                "rebuild_hint": feature.rebuild_hint,
            }
            for feature in FEATURES
        ],
    }


def feature_css() -> str:
    rules = []
    for feature in FEATURES:
        if feature.client_mode == "hide":
            rules.append(
                f'html:not([data-feature-{feature.id}]) [data-feature="{feature.id}"] '
                "{ display:none !important; }"
            )
    rules.extend(
        (
            ".dev-only { display:none !important; }",
            "html[data-feature-dev-view] .dev-only { display:block !important; }",
        )
    )
    return "\n    ".join(rules)


class Component(Protocol):
    feature: Feature

    def enrich_report(self, report: dict[str, Any], ctx: dict[str, Any]) -> None: ...
    def persist(self, conn: Any, report: dict[str, Any], ctx: dict[str, Any]) -> None: ...
    def after_persist(self, conn: Any, ctx: dict[str, Any]) -> None: ...
    def write_pages(self, output_dir: Any, ctx: dict[str, Any]) -> dict[str, Any]: ...
    def dossier_sections(self, report: dict[str, Any], ctx: dict[str, Any]) -> list[str]: ...
    def styles(self) -> str: ...
    def scripts(self) -> str: ...


@dataclass(frozen=True)
class BaseComponent:
    feature: Feature

    def enrich_report(self, report: dict[str, Any], ctx: dict[str, Any]) -> None:
        return None

    def persist(self, conn: Any, report: dict[str, Any], ctx: dict[str, Any]) -> None:
        return None

    def after_persist(self, conn: Any, ctx: dict[str, Any]) -> None:
        return None

    def write_pages(self, output_dir: Any, ctx: dict[str, Any]) -> dict[str, Any]:
        return {}

    def dossier_sections(self, report: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
        return []

    def styles(self) -> str:
        return ""

    def scripts(self) -> str:
        return ""


def validate_registry() -> None:
    if len(REGISTRY) != len(FEATURES):
        raise FeatureError("Baustein-IDs müssen eindeutig sein.")
    nav_keys = {item.key for item in NAV_ITEMS}
    for feature in FEATURES:
        if not re.fullmatch(r"[a-z][a-z0-9-]*", feature.id):
            raise FeatureError(f"Ungültige Baustein-ID: {feature.id}")
        if feature.client_mode not in {"hide", "reveal", "none"}:
            raise FeatureError(f"Ungültiger Client-Modus für {feature.id}: {feature.client_mode}")
        _known((*feature.requires, *feature.enhances))
        if feature.nav_key and feature.nav_key not in nav_keys:
            raise FeatureError(f"Unbekannter Navigationsschlüssel für {feature.id}: {feature.nav_key}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(feature_id: str) -> None:
        if feature_id in visiting:
            raise FeatureError(f"Zyklische Baustein-Abhängigkeit bei {feature_id}")
        if feature_id in visited:
            return
        visiting.add(feature_id)
        for required in REGISTRY[feature_id].requires:
            visit(required)
        visiting.remove(feature_id)
        visited.add(feature_id)

    for feature_id in REGISTRY:
        visit(feature_id)


validate_registry()
