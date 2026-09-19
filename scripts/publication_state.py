"""Validated publication-state contract for Bundestag-Puls schema version 2.

Acquisition code records what happened; renderers consume the resulting
presentation state.  Keeping that mapping here prevents a missing record from
being mistaken for an acquisition that was never requested.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping
from urllib.parse import unquote, urlsplit


SCHEMA_VERSION = 2
DOMAIN_IDS = ("catalog", "dossiers", "votes", "profiles", "roster", "bills", "summaries")
SOURCE_IDS = {
    "bundestag-dip",
    "bundestag-xml",
    "bundestag-roll-call",
    "abgeordnetenwatch",
    "derived-dip",
    "llm-with-bundestag-citations",
}
FAILURE_CODES = {
    "source_unavailable",
    "provider_timeout",
    "invalid_payload",
    "invalid_citations",
    "duplicate_citation",
    "missing_target",
    "page_out_of_bounds",
    "partial_fetch",
    "empty_required_dataset",
    "source_changed",
    "summary_budget_exhausted",
    "unsafe_url",
    "unsafe_output_path",
}
SOURCE_HOSTS = {
    "bundestag-dip": {"dip.bundestag.de", "dserver.bundestag.de", "www.bundestag.de", "bundestag.de"},
    "bundestag-xml": {"dserver.bundestag.de", "www.bundestag.de", "bundestag.de"},
    "bundestag-roll-call": {"www.bundestag.de", "bundestag.de"},
    "abgeordnetenwatch": {"www.abgeordnetenwatch.de", "abgeordnetenwatch.de"},
    "public-profile": {
        "www.abgeordnetenwatch.de",
        "abgeordnetenwatch.de",
        "www.bundestag.de",
        "bundestag.de",
    },
}


class PublicationStateError(ValueError):
    """Raised when publication state is inconsistent or unsafe."""


class AcquisitionState(str, Enum):
    NOT_REQUESTED = "not_requested"
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class PresentationState(str, Enum):
    READY = "ready"
    DOMAIN_EMPTY = "domain_empty"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    OMITTED = "omitted"


def _utc_timestamp(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.endswith("Z"):
        raise PublicationStateError(f"{field_name} must be a UTC RFC 3339 timestamp ending in Z")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise PublicationStateError(f"{field_name} is not a valid RFC 3339 timestamp") from exc
    return value


def derive_presentation_state(
    domain: str,
    acquisition_state: AcquisitionState | str,
    *,
    records: int,
    rejected: int = 0,
) -> PresentationState:
    """Map pipeline truth to the public result without guessing from absence."""
    state = AcquisitionState(acquisition_state)
    if state is AcquisitionState.NOT_REQUESTED:
        return PresentationState.OMITTED if domain == "summaries" else PresentationState.UNAVAILABLE
    if state is AcquisitionState.FAILED:
        return PresentationState.UNAVAILABLE
    if state is AcquisitionState.PARTIAL or rejected:
        return PresentationState.PARTIAL
    if records:
        return PresentationState.READY
    if domain in {"votes", "profiles", "bills", "summaries"}:
        return PresentationState.DOMAIN_EMPTY
    if domain == "roster":
        raise PublicationStateError("a complete roster cannot contain zero records")
    raise PublicationStateError(f"a complete {domain} domain cannot contain zero records")


@dataclass(frozen=True)
class DossierItem:
    document_number: str
    presentation_state: str
    report_path: str | None = None
    page_path: str | None = None
    failure_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        state = str(self.presentation_state)
        if state not in {"ready", "unavailable", "not_requested"}:
            raise PublicationStateError(f"unsupported per-dossier state: {state}")
        if not self.document_number.strip():
            raise PublicationStateError("dossier document_number is required")
        reasons = _failure_reasons(self.failure_reasons)
        object.__setattr__(self, "failure_reasons", reasons)
        if state == "ready":
            if not self.report_path or not self.page_path or reasons:
                raise PublicationStateError("a ready dossier requires both paths and no failure reason")
            validate_relative_output_path(self.report_path)
            validate_relative_output_path(self.page_path)
        elif state == "unavailable":
            if self.report_path is not None or self.page_path is not None or not reasons:
                raise PublicationStateError("an unavailable dossier requires null paths and a failure reason")
        elif state == "not_requested":
            if self.report_path is not None or self.page_path is not None or reasons:
                raise PublicationStateError("a not-requested dossier requires null paths and no failure reason")

    def as_dict(self) -> dict[str, Any]:
        return {
            "document_number": self.document_number,
            "presentation_state": self.presentation_state,
            "report_path": self.report_path,
            "page_path": self.page_path,
            "failure_reasons": list(self.failure_reasons),
        }


def _failure_reasons(values: Iterable[str]) -> tuple[str, ...]:
    reasons = tuple(dict.fromkeys(str(value) for value in values))
    unknown = sorted(set(reasons).difference(FAILURE_CODES))
    if unknown:
        raise PublicationStateError(f"unknown failure code(s): {', '.join(unknown)}")
    return reasons


@dataclass(frozen=True)
class DomainFacts:
    domain: str
    acquisition_state: AcquisitionState | str
    source: str
    records: int
    reused: int = 0
    rejected: int = 0
    failure_reasons: tuple[str, ...] = ()
    acquired_at: str | None = None
    attempted_at: str | None = None
    source_updated_at: str | None = None
    attempted: bool = False
    items: tuple[DossierItem, ...] = ()
    counters: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.domain not in DOMAIN_IDS:
            raise PublicationStateError(f"unknown publication domain: {self.domain}")
        state = AcquisitionState(self.acquisition_state)
        object.__setattr__(self, "acquisition_state", state)
        if self.source not in SOURCE_IDS:
            raise PublicationStateError(f"unknown source: {self.source}")
        for name in ("records", "reused", "rejected"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise PublicationStateError(f"{self.domain}.{name} must be a non-negative integer")
        reasons = _failure_reasons(self.failure_reasons)
        object.__setattr__(self, "failure_reasons", reasons)
        for name in ("acquired_at", "attempted_at", "source_updated_at"):
            object.__setattr__(self, name, _utc_timestamp(getattr(self, name), f"{self.domain}.{name}"))
        if state is AcquisitionState.NOT_REQUESTED and self.attempted:
            raise PublicationStateError(f"{self.domain}: not_requested cannot be attempted")
        if not self.attempted and self.attempted_at is not None:
            raise PublicationStateError(f"{self.domain}: attempted_at requires attempted=true")
        if self.attempted and self.attempted_at is None:
            raise PublicationStateError(f"{self.domain}: attempted=true requires attempted_at")
        if state is AcquisitionState.FAILED and not reasons:
            raise PublicationStateError(f"{self.domain}: failed requires a safe failure reason")
        if self.domain == "dossiers" and not self.items and state is not AcquisitionState.NOT_REQUESTED:
            raise PublicationStateError("dossiers.items is required when dossier acquisition is requested")
        if self.domain != "dossiers" and self.items:
            raise PublicationStateError(f"{self.domain}: items are only valid for dossiers")
        counters = dict(self.counters)
        for name, value in counters.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise PublicationStateError(f"{self.domain}.{name} must be a non-negative integer")
        if self.domain == "summaries":
            required = {"eligible", "generated", "omitted", "failed", "fallbacks"}
            missing = required.difference(counters)
            if missing:
                raise PublicationStateError(f"summaries missing counters: {', '.join(sorted(missing))}")
            if counters["generated"] + self.reused + counters["omitted"] + counters["failed"] != counters["eligible"]:
                raise PublicationStateError("summary outcomes must add up to eligible")
            if self.records != counters["generated"] + self.reused:
                raise PublicationStateError("summary records must equal generated + reused")
            if self.rejected != counters["failed"] or counters["fallbacks"] > self.reused:
                raise PublicationStateError("summary rejected/fallback counters are inconsistent")
        elif counters:
            raise PublicationStateError(f"{self.domain}: summary counters are not allowed")
        object.__setattr__(self, "counters", counters)
        derive_presentation_state(self.domain, state, records=self.records, rejected=self.rejected)

    @property
    def presentation_state(self) -> PresentationState:
        return derive_presentation_state(
            self.domain,
            self.acquisition_state,
            records=self.records,
            rejected=self.rejected,
        )

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "acquisition_state": self.acquisition_state.value,
            "presentation_state": self.presentation_state.value,
            "source": self.source,
            "acquired_at": self.acquired_at,
            "attempted_at": self.attempted_at,
            "source_updated_at": self.source_updated_at,
            "attempted": self.attempted,
            "records": self.records,
            "reused": self.reused,
            "rejected": self.rejected,
            "failure_reasons": list(self.failure_reasons),
        }
        if self.domain == "dossiers":
            payload["items"] = [item.as_dict() for item in self.items]
        payload.update(self.counters)
        return payload


def manifest(*, generated_at: str, version: str, development_output: bool, domains: Iterable[DomainFacts]) -> dict[str, Any]:
    _utc_timestamp(generated_at, "generated_at")
    domain_list = tuple(domains)
    by_id = {domain.domain: domain for domain in domain_list}
    missing = set(DOMAIN_IDS).difference(by_id)
    extra = set(by_id).difference(DOMAIN_IDS)
    if missing or extra or len(by_id) != len(domain_list):
        raise PublicationStateError(
            f"publication domains must be exactly {', '.join(DOMAIN_IDS)}; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "presentation": {"mode": "fixed", "ai_summary_default": "expanded"},
        "build": {"version": version, "development_output": bool(development_output)},
        "domains": {domain: by_id[domain].as_dict() for domain in DOMAIN_IDS},
    }


def validate_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise PublicationStateError(f"unsupported schema_version: {payload.get('schema_version')!r}")
    presentation = payload.get("presentation")
    build = payload.get("build")
    if presentation != {"mode": "fixed", "ai_summary_default": "expanded"}:
        raise PublicationStateError("presentation contract must be fixed/expanded")
    if not isinstance(build, Mapping) or not isinstance(build.get("version"), str) or not isinstance(build.get("development_output"), bool):
        raise PublicationStateError("build.version and build.development_output are required")
    raw_domains = payload.get("domains")
    if not isinstance(raw_domains, Mapping) or set(DOMAIN_IDS).difference(raw_domains):
        raise PublicationStateError("all required publication domains are missing")
    parsed = []
    for domain in DOMAIN_IDS:
        raw = raw_domains[domain]
        if not isinstance(raw, Mapping):
            raise PublicationStateError(f"{domain} must be an object")
        base = dict(raw)
        presentation_state = base.pop("presentation_state", None)
        items = tuple(DossierItem(**item) for item in base.pop("items", ()))
        counter_names = {"eligible", "generated", "omitted", "failed", "fallbacks"}
        counters = {name: base.pop(name) for name in tuple(counter_names) if name in base}
        facts = DomainFacts(domain=domain, items=items, counters=counters, **base)
        if presentation_state != facts.presentation_state.value:
            raise PublicationStateError(f"{domain}.presentation_state is inconsistent")
        parsed.append(facts)
    canonical = manifest(
        generated_at=str(payload.get("generated_at") or ""),
        version=build["version"],
        development_output=build["development_output"],
        domains=parsed,
    )
    return canonical


def validate_external_url(url: str, source: str) -> str:
    """Authorize a public source URL; HTML escaping remains a separate step."""
    if source not in SOURCE_HOSTS:
        raise PublicationStateError(f"source {source!r} has no URL allowlist")
    parsed = urlsplit(str(url))
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise PublicationStateError("public source URLs require https and must not embed credentials")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname not in SOURCE_HOSTS[source]:
        raise PublicationStateError(f"host {hostname!r} is not allowed for {source}")
    return url


def validate_relative_output_path(value: str) -> str:
    decoded = unquote(str(value))
    if not decoded or "\\" in decoded or re.search(r"[\x00-\x1f\x7f]", decoded):
        raise PublicationStateError("unsafe relative output path")
    path = PurePosixPath(decoded)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PublicationStateError("output path must remain relative to the publication root")
    return path.as_posix()


DENYLIST = {
    "developer-class": re.compile(r"(?:\.dev-only\b|class=[\"'][^\"']*\bdev-only\b)"),
    "developer-feature": re.compile(r"data-(?:feature-)?dev-view"),
    "retired-feature-state": re.compile(r"data-feature(?:-|=)"),
    "file-url": re.compile(r"file://", re.IGNORECASE),
    "local-path": re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\\\Users\\\\)"),
    "raw-payload": re.compile(r'"(?:raw_api_response|build_command)"\s*:'),
}


def validate_public_output(root: Path) -> list[str]:
    """Return presentation-surface findings for a completed ordinary build."""
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        is_presentation_json = relative in {
            "data/features.json",
            "data/bills.json",
            "data/abgeordnete.json",
        }
        if path.suffix.lower() != ".html" and not is_presentation_json:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"{relative}: undecodable-text")
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for rule, pattern in DENYLIST.items():
                if pattern.search(line):
                    findings.append(f"{relative}:{line_number}: {rule}")
    return findings


def validate_publication_directory(root: Path) -> None:
    manifest_path = root / "data" / "features.json"
    if not manifest_path.is_file():
        raise PublicationStateError("data/features.json is missing")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationStateError(f"data/features.json is invalid: {exc}") from exc
    canonical = validate_manifest(payload)
    if canonical["build"]["development_output"]:
        raise PublicationStateError("development output is not deployable")
    missing = [name for name in ("index.html", "puls.html", "overview.html", "sources.html") if not (root / name).is_file()]
    if missing:
        raise PublicationStateError(f"publication entry points are missing: {', '.join(missing)}")
    findings = validate_public_output(root)
    if findings:
        raise PublicationStateError("public-output validation failed:\n" + "\n".join(findings))
