"""Bundestag-Puls public components and operator enrichments.

This module deliberately depends on the standard library only.  Renderers may import the
registry, while :mod:`features.loader` performs the lazy component imports after the build
module has finished loading.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Protocol


@dataclass(frozen=True)
class ComponentDefinition:
    """Internal component definition; never exposed as a visitor preference."""

    id: str
    label: str
    description: str
    category: str
    core: bool = False
    default_built: bool = False
    requires: tuple[str, ...] = ()
    rebuild_hint: str = ""


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    path: str


NAV_ITEMS = (
    NavItem("pulse", "Aktueller Puls", "puls.html"),
    NavItem("overview", "Sitzungen", "overview.html"),
    NavItem("bills", "Gesetze", "bills/index.html"),
    NavItem("abgeordnete", "Abgeordnete", "abgeordnete/index.html"),
    NavItem("fakten", "Fakten", "fakt/index.html"),
    NavItem("database", "Daten", "database.html"),
    NavItem("sources", "Quellen", "sources.html"),
)


COMPONENTS = (
    ComponentDefinition("dip-fetch", "DIP-Daten", "Ruft die offiziellen DIP-Daten des Bundestags ab.", "Kern", core=True, default_built=True),
    ComponentDefinition("sitting-catalog", "Sitzungskatalog", "Zeigt den Katalog der Plenarprotokolle und API-Sitzungen.", "Kern", core=True, default_built=True, requires=("dip-fetch",)),
    ComponentDefinition("dossiers", "Protokoll-Dossiers", "Erzeugt die Detailansichten der Plenarprotokolle.", "Kern", core=True, default_built=True, requires=("dip-fetch",)),
    ComponentDefinition("store", "Datenbank", "Speichert die verknüpften Parlamentsdaten in SQLite.", "Kern", core=True, default_built=True, requires=("dip-fetch",)),
    ComponentDefinition("votes", "Namentliche Abstimmungen", "Rendert Abstimmungssummen, Fraktionen und einzelne Stimmen.", "Analyse", requires=("dip-fetch",)),
    ComponentDefinition("summaries", "KI-Zusammenfassungen", "Rendert validierte KI-Zusammenfassungen.", "Analyse", requires=("dip-fetch",)),
    ComponentDefinition("aw-profiles", "abgeordnetenwatch-Profile", "Rendert validierte öffentliche Profilverknüpfungen.", "Analyse", requires=("dip-fetch",)),
    ComponentDefinition("mp-pages", "Abgeordnete", "Erzeugt Übersichts- und Profilseiten für Abgeordnete.", "Bereiche", requires=("store",)),
    ComponentDefinition("mp-roster", "Vollständiger MdB-Kader", "Kompatibilitäts-ID für die Kader-Anreicherung.", "Bereiche", requires=("mp-pages",)),
    ComponentDefinition("facts", "Fakt der Woche", "Erzeugt die wöchentlichen Fakt-Karten und ihre Seiten.", "Bereiche", requires=("store",)),
    ComponentDefinition("bills", "Gesetze verfolgen", "Erzeugt Übersichts- und Detailseiten für Gesetzgebungsvorgänge.", "Bereiche", requires=("dip-fetch",)),
    ComponentDefinition("bill-follow", "Gesetze merken", "Erlaubt es, Gesetze lokal im Browser zu markieren.", "Bereiche", requires=("bills",)),
    ComponentDefinition("dev-view", "Dev-Ansicht", "Zeigt Rohdaten, API-Antworten und Build-Kommandos.", "Entwicklung", requires=("dossiers",)),
)

REGISTRY = {component.id: component for component in COMPONENTS}


class FeatureError(ValueError):
    """Raised for an invalid or impossible feature selection."""


@dataclass(frozen=True)
class Enrichment:
    """One optional operator-controlled acquisition job."""

    id: str
    label: str
    module: str
    rebuild_hint: str


ENRICHMENTS = (
    Enrichment("votes", "Namentliche Abstimmungen", "votes", "Ruft Bundestag-Abstimmungsdaten ab."),
    Enrichment("aw-profiles", "abgeordnetenwatch-Profile", "aw_profiles", "Verknüpft öffentliche Profile."),
    Enrichment("mp-roster", "Vollständiger MdB-Kader", "abgeordnete", "Ruft den vollständigen DIP-Kader ab."),
)
ENRICHMENT_REGISTRY = {enrichment.id: enrichment for enrichment in ENRICHMENTS}


@dataclass(frozen=True)
class EnrichmentSelection:
    ids: frozenset[str]
    provenance: tuple[tuple[str, str, str], ...] = ()

    def __post_init__(self) -> None:
        unknown = sorted(set(self.ids).difference(ENRICHMENT_REGISTRY))
        if unknown:
            raise FeatureError(
                f"Unbekannte Anreicherung: {', '.join(unknown)}. "
                f"Verfügbar: {', '.join(ENRICHMENT_REGISTRY)}, all"
            )

    def __contains__(self, enrichment_id: object) -> bool:
        return enrichment_id in self.ids

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self.ids))

    def enabled(self, enrichment_id: str) -> bool:
        return enrichment_id in self.ids


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
    return resolve(base=(component.id for component in COMPONENTS if component.default_built))


def all_selection() -> Selection:
    return resolve(base=REGISTRY)


def publication_selection() -> Selection:
    """Every component in the fixed public product."""
    return all_selection()


def resolve(
    *,
    base: Iterable[str] | None = None,
    enable: Iterable[str] = (),
    disable: Iterable[str] = (),
) -> Selection:
    """Resolve requirements and explicit vetoes to a stable selection."""
    selected = _known(base if base is not None else (component.id for component in COMPONENTS if component.default_built))
    enabled = _known(enable)
    vetoed = _known(disable)
    core_vetoes = sorted(feature_id for feature_id in vetoed if REGISTRY[feature_id].core)
    if core_vetoes:
        raise FeatureError(f"Kern-Bausteine können nicht deaktiviert werden: {', '.join(core_vetoes)}")

    selected.update(component.id for component in COMPONENTS if component.core)
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


class Component(Protocol):
    feature: ComponentDefinition

    def enrich_report(self, report: dict[str, Any], ctx: dict[str, Any]) -> None: ...
    def persist(self, conn: Any, report: dict[str, Any], ctx: dict[str, Any]) -> None: ...
    def after_persist(self, conn: Any, ctx: dict[str, Any]) -> None: ...
    def write_pages(self, output_dir: Any, ctx: dict[str, Any]) -> dict[str, Any]: ...
    def dossier_sections(self, report: dict[str, Any], ctx: dict[str, Any]) -> list[str]: ...
    def styles(self) -> str: ...
    def scripts(self) -> str: ...


@dataclass(frozen=True)
class BaseComponent:
    feature: ComponentDefinition

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
    if len(REGISTRY) != len(COMPONENTS):
        raise FeatureError("Baustein-IDs müssen eindeutig sein.")
    for component in COMPONENTS:
        if not re.fullmatch(r"[a-z][a-z0-9-]*", component.id):
            raise FeatureError(f"Ungültige Komponenten-ID: {component.id}")
        _known(component.requires)

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
