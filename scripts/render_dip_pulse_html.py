#!/usr/bin/env python3
"""Render a static Bundestag Pulse HTML view from validation JSON."""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from features import (
    CATEGORIES,
    FEATURES,
    NAV_ITEMS,
    Selection,
    default_selection,
    feature_css,
    manifest_json,
)


PARTY_COLORS = {
    "CDU/CSU": "#222222",
    "SPD": "#d71920",
    "AfD": "#2f6fb4",
    "BÜNDNIS 90/DIE GRÜNEN": "#169b62",
    "Die Linke": "#b01873",
    "fraktionslos": "#7a8699",
    "Regierung": "#b06b00",
    "Rolle/Amt": "#b06b00",
    "Unbekannt": "#8b949e",
}

VOTE_LABELS = {
    "yes": "ja",
    "no": "nein",
    "abstain": "enthalten",
    "absent": "nicht abg.",
}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def short(value: str | None, limit: int = 150) -> str:
    if not value:
        return ""
    value = " ".join(str(value).split())
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def format_int(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def percent(value: int, total: int) -> float:
    return value / total * 100 if total > 0 else 0.0


def format_percent(value: float) -> str:
    return f"{value:.1f}".replace(".", ",") + "%"


def global_header_styles() -> str:
    return """
    :root[data-theme="dark"] {
      color-scheme:dark;
      --ink:#e6edf3;
      --muted:#9da7b3;
      --line:#2d3643;
      --paper:#0d1117;
      --panel:#151b23;
      --blue:#8ab4f8;
      --teal:#4fd1c5;
      --amber:#f0b45b;
      --red:#ff8a8a;
      --blue-soft:#16263f;
      --green-soft:#122923;
      --amber-soft:#302312;
      --surface-2:#1b232e;
      --surface-3:#202a36;
      --warning-bg:#332908;
      --warning-line:#8a6a15;
      --warning-ink:#f5d77f;
    }
    .site-header {
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:18px;
      flex-wrap:wrap;
      padding:0 0 18px;
      margin-bottom:22px;
      border-bottom:1px solid var(--line);
    }
    .site-brand {
      display:flex;
      flex-direction:column;
      gap:2px;
      color:var(--ink);
      min-width:180px;
    }
    .site-brand:hover { text-decoration:none; }
    .site-brand strong {
      font-size:18px;
      line-height:1.1;
      font-weight:820;
    }
    .site-brand span {
      color:var(--muted);
      font-size:12px;
      text-transform:uppercase;
      letter-spacing:.05em;
      font-weight:700;
    }
    .site-nav {
      display:flex;
      flex-wrap:wrap;
      justify-content:flex-end;
      gap:8px;
    }
    .site-actions {
      display:flex;
      align-items:center;
      gap:8px;
      margin-left:auto;
    }
    .site-nav a {
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-height:34px;
      padding:5px 11px;
      border:1px solid var(--line);
      border-radius:6px;
      background:var(--panel);
      color:var(--ink);
      font-size:13px;
      font-weight:700;
    }
    .site-nav a:hover,
    .site-nav a[aria-current="page"] {
      border-color:#bdd0ea;
      background:var(--blue-soft, #eef5ff);
      color:var(--blue, #174ea6);
      text-decoration:none;
    }
    .theme-toggle {
      appearance:none;
      display:inline-flex;
      align-items:center;
      justify-content:center;
      gap:6px;
      min-height:34px;
      padding:5px 10px;
      border:1px solid var(--line);
      border-radius:6px;
      background:var(--panel);
      color:var(--ink);
      font:inherit;
      font-size:13px;
      font-weight:750;
      cursor:pointer;
      white-space:nowrap;
    }
    .theme-toggle:hover {
      border-color:#bdd0ea;
      color:var(--blue, #174ea6);
    }
    .settings-wrap { position:relative; }
    .settings-toggle, .settings-close, .settings-reset, .settings-more {
      appearance:none;
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-height:34px;
      padding:5px 10px;
      border:1px solid var(--line);
      border-radius:6px;
      background:var(--panel);
      color:var(--ink);
      font:inherit;
      font-size:13px;
      font-weight:750;
      cursor:pointer;
    }
    .settings-toggle { width:36px; padding:5px; }
    .settings-toggle svg { width:17px; height:17px; }
    .settings-panel[hidden] { display:none !important; }
    .settings-panel {
      position:absolute;
      z-index:100;
      top:calc(100% + 9px);
      right:0;
      width:min(390px, calc(100vw - 28px));
      max-height:min(650px, calc(100vh - 90px));
      overflow:auto;
      padding:0;
      border:1px solid var(--line);
      border-radius:10px;
      background:var(--panel);
      color:var(--ink);
      box-shadow:0 16px 42px rgba(23, 26, 31, .18);
    }
    .settings-panel-head, .settings-panel-foot {
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      padding:13px 15px;
      border-bottom:1px solid var(--line);
    }
    .settings-panel-head strong { font-size:15px; }
    .settings-panel-foot { border-top:1px solid var(--line); border-bottom:0; }
    .settings-close { min-height:28px; width:30px; padding:3px; }
    .settings-groups { padding:8px 15px; }
    .settings-group { padding:7px 0; background:var(--panel); }
    .settings-group h3 { margin:0 0 4px; font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.06em; }
    .settings-item {
      display:flex;
      align-items:flex-start;
      justify-content:space-between;
      gap:14px;
      padding:10px 0;
      border-bottom:1px solid var(--line);
    }
    .settings-item:last-child { border-bottom:0; }
    .settings-switch-text { min-width:0; }
    .settings-switch-text strong { display:block; color:var(--ink); font-size:13px; }
    .settings-switch-text span, .settings-hint, .settings-count { display:block; margin-top:3px; color:var(--muted); font-size:11px; line-height:1.35; }
    .settings-switch { flex:0 0 auto; margin-top:2px; accent-color:var(--blue); cursor:pointer; }
    .settings-switch:disabled { cursor:not-allowed; }
    .settings-badge { display:inline-flex !important; width:max-content; padding:2px 5px; border:1px solid var(--line); border-radius:999px; background:var(--surface-2, #f4f6f9); }
    .settings-item.is-unavailable { opacity:.72; }
    .settings-hint code { font-size:10px; }
    .settings-more { text-decoration:none; }
    .settings-card { border:1px solid var(--line); border-radius:10px; background:var(--panel); padding:18px; }
    .settings-page-grid { display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:16px; }
    .settings-page-grid .settings-group { padding:18px; }
    .settings-page-grid .settings-group h2 { margin:0 0 10px; font-size:18px; }
    .theme-toggle-icon {
      width:15px;
      font-size:14px;
      line-height:1;
    }
    :root[data-theme="dark"] a { color:var(--blue) !important; }
    :root[data-theme="dark"] :is(
      .site-nav a, .theme-toggle, .settings-toggle, .settings-close, .settings-reset, .settings-more,
      .button, .btn, .dev-toggle,
      .page-actions a, .session-links a, .pulse-actions a,
      .feature-link, .doc-link, .top-jump
    ) {
      background:var(--panel) !important;
      border-color:var(--line) !important;
      color:var(--ink) !important;
    }
    :root[data-theme="dark"] :is(.btn-primary, .button.primary) {
      background:var(--blue) !important;
      border-color:var(--blue) !important;
      color:#08111f !important;
    }
    :root[data-theme="dark"] :is(
      .metric, .download-panel, .summary-band div, .panel, .table-card,
      .filter, .sample-table, details, .snapshot, .snapshot-metrics div,
      .stat-band div, .principle, .area-card, .latest-panel, .pulse-feature,
      .context-panel, .feature-microgrid div, .attention-card, .top-card,
      aside, .session-llm-summary, .llm-summary, .source-strip,
      .api-overview, .api-json, .speech-card, .table-nav a,
      .settings-panel, .settings-card, .settings-group
    ) {
      background:var(--panel) !important;
      border-color:var(--line) !important;
      color:var(--ink) !important;
    }
    :root[data-theme="dark"] :is(
      .badge, .summary-count, .session-summary-sources a,
      .session-summary-sources span, .empty, .filter input
    ) {
      background:var(--surface-2) !important;
      border-color:var(--line) !important;
      color:var(--ink) !important;
    }
    :root[data-theme="dark"] :is(
      p, .lead, .subtitle, .feature-body p, .session-summary-item p,
      .llm-summary > p, .summary-sources p, .speech-text,
      .speaker-row span, .position-list span, .doc-list span,
      .activity-list span, .people-list span, .feature-state,
      .aw-profile, .table-head strong, .settings-switch-text strong, .settings-panel-head strong
    ) {
      color:var(--ink) !important;
    }
    :root[data-theme="dark"] :is(
      .muted, .eyebrow, .row-top, .row-metric, label, .card-meta,
      th, .snapshot-date, .snapshot-metrics span, .stat-band span,
      .principle p, .area-card p, .metric span, .feature-microgrid span,
      .speaker-row em, .position-list em, .doc-list em,
      .activity-list em, .people-list em, .summary-sources span,
      .session-summary-note, .settings-switch-text span, .settings-hint, .settings-count
    ) {
      color:var(--muted) !important;
    }
    :root[data-theme="dark"] :is(.notice) {
      background:var(--warning-bg) !important;
      border-color:var(--warning-line) !important;
      color:var(--warning-ink) !important;
    }
    :root[data-theme="dark"] :is(.bar, .stack, .vote-stack) {
      background:var(--surface-3) !important;
    }
    :root[data-theme="dark"] :is(
      .table-head, th, td, .ranking-note, .attention-row,
      .session-summary-item, .summary-sources li, .member-votes,
      .position-list li, .doc-list li, .activity-list li,
      .people-list li, .people-section, .raw-top-api,
      .dev-top-details, .speech-section, details pre,
      .settings-item, .settings-panel-head, .settings-panel-foot
    ) {
      border-color:var(--line) !important;
    }
    :root[data-theme="dark"] pre,
    :root[data-theme="dark"] code {
      color:#dbe7f3;
    }
    @media (max-width: 760px) {
      .site-header { align-items:flex-start; }
      .site-nav { justify-content:flex-start; }
      .site-actions { width:100%; justify-content:flex-start; }
      .settings-panel {
        position:fixed;
        top:70px;
        left:14px;
        right:14px;
        width:auto;
        max-height:calc(100vh - 84px);
      }
      .settings-page-grid { grid-template-columns:1fr; }
    }
    """ + "\n    " + feature_css()


def theme_bootstrap_script() -> str:
    return """
  <script>
    (() => {
      const key = "bundestag-pulse-theme";
      const root = document.documentElement;
      let theme = "light";
      try {
        theme = window.localStorage.getItem(key)
          || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      } catch (_) {}
      root.dataset.theme = theme === "dark" ? "dark" : "light";
    })();
  </script>
"""


def theme_runtime_script() -> str:
    return """
  <script>
    (() => {
      const key = "bundestag-pulse-theme";
      const root = document.documentElement;
      const toggles = document.querySelectorAll("[data-theme-toggle]");
      const setTheme = (theme, persist = true) => {
        const next = theme === "dark" ? "dark" : "light";
        root.dataset.theme = next;
        toggles.forEach((toggle) => {
          const dark = next === "dark";
          toggle.setAttribute("aria-pressed", dark ? "true" : "false");
          toggle.setAttribute("aria-label", dark ? "Helles Design aktivieren" : "Dunkles Design aktivieren");
          toggle.querySelector("[data-theme-icon]").textContent = dark ? "☀" : "☾";
          toggle.querySelector("[data-theme-label]").textContent = dark ? "Hell" : "Dunkel";
        });
        if (persist) {
          try { window.localStorage.setItem(key, next); } catch (_) {}
        }
      };
      setTheme(root.dataset.theme, false);
      toggles.forEach((toggle) => {
        toggle.addEventListener("click", () => {
          setTheme(root.dataset.theme === "dark" ? "light" : "dark");
        });
      });
    })();
  </script>
"""


def feature_bootstrap_script(selection: Selection | None = None) -> str:
    selection = selection or default_selection()
    return f"""
  <script>
    (() => {{
      const key = "bundestag-pulse-features";
      const manifest = {manifest_json(selection)};
      window.__BUNDESTAG_PULSE_FEATURES__ = manifest;
      let overrides = {{}};
      try {{ overrides = JSON.parse(window.localStorage.getItem(key) || "{{}}") || {{}}; }} catch (_) {{}}
      for (const [id, feature] of Object.entries(manifest)) {{
        let on = Object.prototype.hasOwnProperty.call(overrides, id) ? Boolean(overrides[id]) : Boolean(feature.v);
        if (!feature.a) on = false;
        if (feature.c) on = true;
        document.documentElement.toggleAttribute(`data-feature-${{id}}`, on);
      }}
    }})();
  </script>
"""


def feature_runtime_script(selection: Selection | None = None) -> str:
    selection = selection or default_selection()
    return """
  <script>
    (() => {
      const key = "bundestag-pulse-features";
      const root = document.documentElement;
      const manifest = window.__BUNDESTAG_PULSE_FEATURES__ || {};
      const readOverrides = () => {
        try { return JSON.parse(window.localStorage.getItem(key) || "{}") || {}; } catch (_) { return {}; }
      };
      const updateControls = () => {
        const overrides = readOverrides();
        document.querySelectorAll("[data-feature-toggle]").forEach((control) => {
          const id = control.dataset.featureToggle;
          const feature = manifest[id];
          if (!feature) return;
          const inherited = !Object.prototype.hasOwnProperty.call(overrides, id);
          control.checked = root.hasAttribute(`data-feature-${id}`);
          control.dataset.inherited = inherited ? "true" : "false";
        });
        document.querySelectorAll("[data-settings-count]").forEach((node) => {
          const count = Object.keys(manifest).filter((id) => manifest[id].a && root.hasAttribute(`data-feature-${id}`)).length;
          node.textContent = `${count} aktiv`;
        });
      };
      const setFeature = (id, on, persist = true) => {
        const feature = manifest[id];
        if (!feature || !feature.a || feature.c || feature.m === "n") return;
        root.toggleAttribute(`data-feature-${id}`, Boolean(on));
        if (persist) {
          const overrides = readOverrides();
          overrides[id] = Boolean(on);
          try { window.localStorage.setItem(key, JSON.stringify(overrides)); } catch (_) {}
        }
        updateControls();
      };
      document.querySelectorAll("[data-feature-toggle]").forEach((control) => {
        control.addEventListener("change", () => setFeature(control.dataset.featureToggle, control.checked));
      });
      document.querySelectorAll("[data-settings-reset]").forEach((button) => {
        button.addEventListener("click", () => {
          try { window.localStorage.removeItem(key); } catch (_) {}
          for (const [id, feature] of Object.entries(manifest)) {
            root.toggleAttribute(`data-feature-${id}`, Boolean(feature.a && (feature.c || feature.v)));
          }
          updateControls();
        });
      });
      document.querySelectorAll("[data-settings-wrap]").forEach((wrap) => {
        const button = wrap.querySelector("[data-settings-toggle]");
        const panel = wrap.querySelector("[data-settings-panel]");
        if (!button || !panel) return;
        const close = (restore = false) => {
          panel.hidden = true;
          button.setAttribute("aria-expanded", "false");
          if (restore) button.focus();
        };
        const open = () => {
          panel.hidden = false;
          button.setAttribute("aria-expanded", "true");
          panel.querySelector("button, input, a")?.focus();
        };
        button.addEventListener("click", () => panel.hidden ? open() : close());
        panel.querySelector("[data-settings-close]")?.addEventListener("click", () => close(true));
        document.addEventListener("pointerdown", (event) => { if (!panel.hidden && !wrap.contains(event.target)) close(); });
        wrap.addEventListener("focusout", (event) => { if (!panel.hidden && event.relatedTarget && !wrap.contains(event.relatedTarget)) close(); });
        document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !panel.hidden) close(true); });
      });
      document.querySelectorAll(".dev-toggle").forEach((button) => {
        const sync = () => {
          const enabled = root.hasAttribute("data-feature-dev-view");
          button.setAttribute("aria-pressed", enabled ? "true" : "false");
          button.textContent = enabled ? "Dev-Ansicht aus" : "Dev-Ansicht";
        };
        button.addEventListener("click", () => { setFeature("dev-view", !root.hasAttribute("data-feature-dev-view")); sync(); });
        sync();
      });
      updateControls();
    })();
  </script>
"""


def page_head(selection: Selection | None = None) -> str:
    return theme_bootstrap_script() + feature_bootstrap_script(selection)


def page_scripts(selection: Selection | None = None) -> str:
    return feature_runtime_script(selection) + theme_runtime_script()


SETTINGS_ICON_SVG = (
    '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
    '<path fill="currentColor" d="M19.4 13a7.8 7.8 0 0 0 .1-1 7.8 7.8 0 0 0-.1-1l2.1-1.6-2-3.4-2.5 1a8 8 0 0 0-1.7-1L15 3.3h-4L10.6 6a8 8 0 0 0-1.7 1L6.5 6l-2 3.4L6.6 11a7.8 7.8 0 0 0-.1 1 7.8 7.8 0 0 0 .1 1l-2.1 1.6 2 3.4 2.5-1a8 8 0 0 0 1.7 1l.4 2.7h4l.4-2.7a8 8 0 0 0 1.7-1l2.5 1 2-3.4L19.4 13ZM13 15.5a3.5 3.5 0 1 1 0-7 3.5 3.5 0 0 1 0 7Z"/>'
    '</svg>'
)


def render_settings_items(selection: Selection, category: str | None = None) -> str:
    labels = {feature.id: feature.label for feature in FEATURES}
    rows = []
    for feature in FEATURES:
        if category and feature.category != category:
            continue
        available = feature.id in selection
        toggleable = available and not feature.core and feature.client_mode != "none"
        checked = " checked" if available and feature.default_visible else ""
        disabled = "" if toggleable else " disabled"
        classes = "settings-item" + (" is-unavailable" if not available else "")
        if not available:
            status = (
                '<span class="settings-badge">Nicht in diesem Build</span>'
                f'<span class="settings-hint"><code>--enable {esc(feature.id)}</code></span>'
                + (f'<span class="settings-hint">{esc(feature.rebuild_hint)}</span>' if feature.rebuild_hint else "")
            )
        elif feature.core:
            status = '<span class="settings-badge">Immer aktiv</span>'
        elif feature.client_mode == "none":
            status = '<span class="settings-badge">Nur beim Build</span>'
        else:
            status = ""
        enhancement = ""
        if feature.enhances:
            enhancement = (
                '<span class="settings-hint">Ergänzt: '
                + esc(", ".join(labels[feature_id] for feature_id in feature.enhances))
                + ".</span>"
            )
        rows.append(
            f'<label class="{classes}" data-settings-item="{esc(feature.id)}">'
            f'<span class="settings-switch-text"><strong>{esc(feature.label)}</strong>'
            f'<span>{esc(feature.description)}</span>{enhancement}{status}</span>'
            f'<input class="settings-switch" type="checkbox" role="switch" data-feature-toggle="{esc(feature.id)}"'
            f'{checked}{disabled}></label>'
        )
    return "".join(rows)


def render_settings_panel(selection: Selection, *, depth: int = 0) -> str:
    groups = "".join(
        f'<section class="settings-group"><h3>{esc(category)}</h3>{render_settings_items(selection, category)}</section>'
        for category in CATEGORIES
    )
    panel_id = "site-settings-panel"
    prefix = "../" * depth
    return (
        '<div class="settings-wrap" data-settings-wrap>'
        f'<button class="settings-toggle" type="button" data-settings-toggle aria-expanded="false" aria-controls="{panel_id}" aria-label="Bausteine einstellen">{SETTINGS_ICON_SVG}</button>'
        f'<div class="settings-panel" id="{panel_id}" data-settings-panel role="region" aria-label="Bausteine" aria-modal="false" hidden>'
        '<div class="settings-panel-head"><strong>Bausteine</strong><button class="settings-close" type="button" data-settings-close aria-label="Schließen">×</button></div>'
        f'<div class="settings-groups">{groups}</div>'
        '<div class="settings-panel-foot"><span class="settings-count" data-settings-count></span>'
        f'<a class="settings-more" href="{prefix}settings.html">Alle Einstellungen</a></div>'
        '</div></div>'
    )


def render_global_header(*, depth: int = 0, active: str | None = None, features: Selection | None = None) -> str:
    features = features or default_selection()
    prefix = "../" * depth
    brand_href = f"{prefix}index.html"
    links = []
    for item in NAV_ITEMS:
        if item.feature_id and item.feature_id not in features:
            continue
        current = ' aria-current="page"' if active == item.key else ""
        feature_attr = f' data-feature="{item.feature_id}"' if item.feature_id else ""
        links.append(f'<a href="{esc(prefix + item.path)}"{current}{feature_attr}>{esc(item.label)}</a>')
    return (
        '<div class="site-header">'
        f'<a class="site-brand" href="{esc(brand_href)}">'
        "<strong>Bundestag-Puls</strong>"
        "<span>Primärquellen-Monitor</span>"
        "</a>"
        '<div class="site-actions">'
        f'<nav class="site-nav" aria-label="Globale Navigation">{"".join(links)}</nav>'
        '<button class="theme-toggle" type="button" data-theme-toggle aria-pressed="false" '
        'aria-label="Dunkles Design aktivieren">'
        '<span class="theme-toggle-icon" data-theme-icon aria-hidden="true">☾</span>'
        '<span data-theme-label>Dunkel</span>'
        '</button>'
        f'{render_settings_panel(features, depth=depth)}'
        '</div>'
        "</div>"
    )


def page_range_text(item: dict[str, Any]) -> str:
    page_range = item.get("page_range") or {}
    start = page_range.get("start") or {}
    end = page_range.get("end") or {}
    if not start or not end:
        return "keine Seitenangabe"
    start_ref = f"{start.get('page')}{start.get('quadrant') or ''}"
    end_ref = f"{end.get('page')}{end.get('quadrant') or ''}"
    return start_ref if start_ref == end_ref else f"{start_ref}-{end_ref}"


def source_page_text(page: dict[str, Any] | None) -> str:
    if not page:
        return ""
    return f"{page.get('page')}{page.get('quadrant') or ''}"


def speech_anchor(item: dict[str, Any], speech: dict[str, Any], sequence: int) -> str:
    speech_id = speech.get("rede_id")
    if speech_id:
        suffix = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(speech_id)).strip("-")
    else:
        suffix = str(sequence + 1)
    return f"speech-{item.get('index')}-{suffix or sequence + 1}"


# Inline "person" glyph used for the compact abgeordnetenwatch profile link so
# the build stays self-contained (no external icon assets).
PROFILE_ICON_SVG = (
    '<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true" focusable="false">'
    '<circle cx="8" cy="5" r="3" fill="currentColor"></circle>'
    '<path d="M2.5 14c0-3 2.5-4.5 5.5-4.5s5.5 1.5 5.5 4.5z" fill="currentColor"></path>'
    "</svg>"
)


def speaker_profile(speaker: dict[str, Any] | None) -> dict[str, Any] | None:
    profile = (speaker or {}).get("abgeordnetenwatch")
    if isinstance(profile, dict) and profile.get("url"):
        return profile
    return None


def render_profile_icon(speaker: dict[str, Any] | None) -> str:
    """Compact icon link to a speaker's abgeordnetenwatch profile (or empty)."""
    profile = speaker_profile(speaker)
    if not profile:
        return ""
    label = profile.get("label") or "abgeordnetenwatch.de"
    tooltip = f"Profil von {label} auf abgeordnetenwatch.de"
    return (
        f'<a class="aw-profile-icon" data-feature="aw-profiles" href="{esc(profile["url"])}" target="_blank" '
        f'rel="noopener" title="{esc(tooltip)}" aria-label="{esc(tooltip)}">'
        f"{PROFILE_ICON_SVG}</a>"
    )


def render_profile_link(speaker: dict[str, Any] | None) -> str:
    """Full labelled link to a speaker's abgeordnetenwatch profile (or empty)."""
    profile = speaker_profile(speaker)
    if not profile:
        return ""
    return (
        '<p class="aw-profile-line">'
        f'<a class="aw-profile" data-feature="aw-profiles" href="{esc(profile["url"])}" target="_blank" rel="noopener">'
        f"{PROFILE_ICON_SVG}<span>Profil auf abgeordnetenwatch.de</span>"
        '<span class="aw-ext" aria-hidden="true">↗</span></a>'
        "</p>"
    )


def speaker_party(speaker: dict[str, Any] | None) -> str:
    if not speaker:
        return "Unbekannt"
    fraction = speaker.get("fraktion")
    if fraction:
        return str(fraction).replace("\xa0", " ")
    if speaker.get("role") or speaker.get("role_short"):
        return "Regierung"
    return "Unbekannt"


def item_stats(item: dict[str, Any]) -> dict[str, Any]:
    speakers = item.get("xml_speakers") or []
    if not speakers:
        speakers = item.get("xml_speakers_first") or []
    party_counts = Counter(speaker_party(s.get("speaker")) for s in speakers)
    total_chars = sum(int(s.get("char_count") or 0) for s in speakers)
    return {
        "party_counts": party_counts,
        "total_chars": total_chars,
        "speakers": speakers,
        "speech_count": int(item.get("xml_speech_count") or len(speakers)),
    }


def protocol_title(report: dict[str, Any]) -> str:
    protocol = report.get("protocol") or {}
    return f"Bundestag-Puls · {protocol.get('dokumentnummer', 'Plenarprotokoll')}"


def render_badges(items: list[dict[str, Any]], class_name: str = "badge") -> str:
    return "".join(f'<span class="{class_name}">{esc(item)}</span>' for item in items)


def render_party_stack(counter: Counter[str], total: int) -> str:
    if total <= 0:
        return '<div class="stack empty"></div>'
    parts = []
    for party, count in counter.most_common():
        width = max(4, count / total * 100)
        color = PARTY_COLORS.get(party, "#6b7280")
        parts.append(
            f'<span style="width:{width:.2f}%;background:{color}" '
            f'title="{esc(party)}: {count}"></span>'
        )
    return f'<div class="stack">{"".join(parts)}</div>'


def render_vote_stack(counts: dict[str, Any], total: int | None = None) -> str:
    total = total if total is not None else sum(int(counts.get(key) or 0) for key in VOTE_LABELS)
    if total <= 0:
        return '<div class="vote-stack empty"></div>'
    parts = []
    for key, label in VOTE_LABELS.items():
        count = int(counts.get(key) or 0)
        if count <= 0:
            continue
        width = max(3, count / total * 100)
        parts.append(
            f'<span class="vote-{key}" style="width:{width:.2f}%" '
            f'title="{esc(label)}: {count}"></span>'
        )
    return f'<div class="vote-stack">{"".join(parts)}</div>'


def render_vote_pills(counts: dict[str, Any]) -> str:
    return "".join(
        f'<span class="vote-pill vote-{key}">{esc(label)} <strong>{esc(counts.get(key) or 0)}</strong></span>'
        for key, label in VOTE_LABELS.items()
    )


def render_source_links(item: dict[str, Any]) -> str:
    links = []
    for doc in item.get("xml_drucksachen") or []:
        url = doc.get("url")
        number = doc.get("dokumentnummer")
        if url:
            links.append(f'<a class="doc-link" href="{esc(url)}">{esc(number)}</a>')
        else:
            links.append(f'<span class="doc-link muted">{esc(number)}</span>')
    if not links:
        return '<span class="muted">Keine Drucksache im XML</span>'
    return "".join(links)


def render_linked_docs(item: dict[str, Any]) -> str:
    docs = item.get("api", {}).get("linked_drucksachen") or []
    if not docs:
        return '<span class="muted">Keine API-Verknüpfung</span>'
    rows = []
    for doc in docs:
        number = esc(doc.get("dokumentnummer"))
        kind = esc(doc.get("drucksachetyp") or doc.get("vorgangsposition") or "Drucksache")
        date = esc(doc.get("datum") or "")
        origin = ", ".join(doc.get("urheber") or [])
        url = doc.get("url")
        label = f'<a href="{esc(url)}">{number}</a>' if url else number
        rows.append(
            "<li>"
            f"<strong>{label}</strong>"
            f"<span>{kind}</span>"
            f"<span>{date}</span>"
            f"<em>{esc(short(origin, 80))}</em>"
            "</li>"
        )
    return f'<ul class="doc-list">{"".join(rows)}</ul>'


def render_positions(item: dict[str, Any]) -> str:
    positions = item.get("api", {}).get("positions") or []
    if not positions:
        return '<span class="status warn">Keine passende API-Position</span>'
    parts = []
    for position in positions:
        source = position.get("source") or {}
        pdf = source.get("pdf_url")
        title = esc(position.get("titel"))
        kind = esc(position.get("vorgangsposition"))
        vorgang = esc(position.get("vorgang_id"))
        if pdf:
            title_html = f'<a href="{esc(pdf)}">{title}</a>'
        else:
            title_html = title
        mit = position.get("mitberaten") or []
        mit_text = f" · {len(mit)} mitberaten" if mit else ""
        parts.append(f"<li><strong>{kind}</strong><span>{title_html}</span><em>Vorgang {vorgang}{mit_text}</em></li>")
    return f'<ul class="position-list">{"".join(parts)}</ul>'


def render_activities(item: dict[str, Any]) -> str:
    activities = item.get("api", {}).get("activities") or item.get("api", {}).get("activities_first") or []
    if not activities:
        return '<span class="status warn">Keine passende API-Aktivität</span>'
    rows = []
    for activity in activities:
        title = esc(short(activity.get("titel"), 130))
        kind = esc(activity.get("aktivitaetsart") or "Aktivität")
        person = esc(activity.get("person_id") or "")
        page = esc(activity.get("seite") or "")
        pdf = activity.get("pdf_url")
        label = f'<a href="{esc(pdf)}">{title}</a>' if pdf else title
        person_text = f"Person {person}" if person else "Keine Personen-ID"
        page_text = f"Seite {page}" if page else "Keine Seite"
        rows.append(
            "<li>"
            f"<strong>{kind}</strong>"
            f"<span>{label}</span>"
            f"<em>{person_text} · {page_text}</em>"
            "</li>"
        )
    return f'<ul class="activity-list">{"".join(rows)}</ul>'


def render_json_details(title: str, payload: Any, class_name: str = "api-json") -> str:
    empty = payload is None or payload == {} or payload == []
    count = ""
    if isinstance(payload, list):
        count = f" ({len(payload)})"
    elif isinstance(payload, dict):
        count = f" ({len(payload)} Felder)"
    if empty:
        return f'<details class="{class_name}"><summary>{esc(title)}{esc(count)}</summary><pre>Keine API-Datensätze.</pre></details>'
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return f'<details class="{class_name}"><summary>{esc(title)}{esc(count)}</summary><pre>{esc(text)}</pre></details>'


def render_protocol_api_overview(report: dict[str, Any]) -> str:
    records = report.get("api_records") or {}
    people = report.get("sampled_people") or []
    people_rows = []
    for person in people:
        name = " ".join(
            part
            for part in [
                str(person.get("titel") or ""),
                str(person.get("vorname") or ""),
                str(person.get("nachname") or ""),
            ]
            if part
        )
        people_rows.append(
            "<li>"
            f"<strong>{esc(name or person.get('id'))}</strong>"
            f"<span>{esc(person.get('fraktion') or '')}</span>"
            f"<em>{esc(person.get('funktion') or '')}</em>"
            "</li>"
        )
    people_html = '<span class="muted">Keine Personendatensätze geholt.</span>'
    if people_rows:
        people_html = f'<ul class="people-list">{"".join(people_rows)}</ul>'

    return f"""
      <section class="api-overview dev-only">
        <div>
          <h2>API-Datensätze</h2>
          <p>DIP-API-Nutzdaten bleiben im erzeugten JSON erhalten. Kompakte Tabellen halten die Seite lesbar; ausklappbare JSON-Blöcke zeigen die ursprünglichen Felder.</p>
        </div>
        <div class="api-record-grid">
          {render_json_details("Protokoll-Datensatz", records.get("protocol"))}
          {render_json_details("Alle Vorgangspositionen", records.get("vorgangspositionen"))}
          {render_json_details("Alle Aktivitäten", records.get("aktivitaeten"))}
          {render_json_details("Personendatensätze", records.get("persons"))}
          {render_json_details("Kandidaten für namentliche Abstimmungen", records.get("roll_call_vote_candidates"))}
          {render_json_details("Zugeordnete namentliche Abstimmungen", records.get("matched_roll_call_votes"))}
        </div>
        <section class="people-section">
          <h3>Personen aus Aktivitäten</h3>
          {people_html}
        </section>
      </section>
    """


def render_top_dev_details(item: dict[str, Any]) -> str:
    api_positions_count = len(item.get("api", {}).get("positions") or [])
    linked_docs_count = len(item.get("api", {}).get("linked_drucksachen") or [])
    source_url = None
    positions = item.get("api", {}).get("positions") or []
    if positions:
        source_url = (positions[0].get("source") or {}).get("pdf_url")

    return f"""
              <section class="dev-only dev-top-details">
                <h3>Technische Einordnung</h3>
                <div class="source-strip">
                  <div><span>XML Drucksachen</span>{render_source_links(item)}</div>
                  <div><span>API-Anreicherung</span>{api_positions_count} Positionen · {item.get('api', {}).get('activities_count', 0)} Aktivitäten · {linked_docs_count} verknüpfte Dokumente</div>
                  <div><span>Protokoll</span>{f'<a href="{esc(source_url)}">PDF-Quelle</a>' if source_url else '<span class="muted">Keine direkte PDF-Verknüpfung</span>'}</div>
                </div>
                <div class="detail-grid">
                  <section>
                    <h3>API-Positionen</h3>
                    {render_positions(item)}
                  </section>
                  <section>
                    <h3>API-Aktivitäten</h3>
                    {render_activities(item)}
                  </section>
                  <section>
                    <h3>Verknüpfte Dokumente</h3>
                    {render_linked_docs(item)}
                  </section>
                </div>
                <section class="raw-top-api">
                  <h3>Rohdaten der zugeordneten API-Datensätze</h3>
                  <div class="api-record-grid">
                    {render_json_details("Zugeordnete Positionen", item.get('api', {}).get('raw', {}).get('positions'))}
                    {render_json_details("Zugeordnete Aktivitäten", item.get('api', {}).get('raw', {}).get('activities'))}
                    {render_json_details("Abstimmungen", item.get('votes'))}
                  </div>
                </section>
              </section>
    """


def mp_page_href(
    speaker: dict[str, Any],
    mp_lookup: dict[str, int] | None,
    prefix: str = "abgeordnete/",
) -> str | None:
    """Internal Abgeordnete profile URL for a speaker, or None when the speaker
    does not resolve to a known MP. Tries abgeordnetenwatch id, then the
    Bundestagsverwaltung speaker id, then the DIP person id."""
    if not mp_lookup:
        return None
    profile = speaker.get("abgeordnetenwatch") or {}
    candidates = (
        f"aw:{profile.get('id')}" if profile.get("id") else None,
        f"xml:{speaker.get('xml_redner_id')}" if speaker.get("xml_redner_id") else None,
        f"dip:{speaker.get('dip_person_id')}" if speaker.get("dip_person_id") else None,
    )
    for key in candidates:
        if key and key in mp_lookup:
            return f"{prefix}{mp_lookup[key]}.html"
    return None


def render_speakers(
    item: dict[str, Any],
    stats: dict[str, Any],
    mp_lookup: dict[str, int] | None = None,
    mp_href_prefix: str = "abgeordnete/",
    profiles_enabled: bool = True,
) -> str:
    rows = []
    for sequence, speech in enumerate(stats["speakers"]):
        speaker = speech.get("speaker") or {}
        name = esc(speaker.get("display_name") or "Unbekannt")
        party = speaker_party(speaker)
        color = PARTY_COLORS.get(party, "#6b7280")
        role = speaker.get("role") or speaker.get("role_short") or party
        source = source_page_text(speech.get("source_page"))
        anchor = speech_anchor(item, speech, sequence)
        mp_href = mp_page_href(speaker, mp_lookup, mp_href_prefix)
        profile_cell = (
            f'<a class="mp-profile-link" href="{esc(mp_href)}" title="Profil von {name} auf Bundestag-Puls">Profil</a> '
            if mp_href
            else ""
        )
        rows.append(
            '<li class="speaker-row">'
            f'<span class="party-dot" style="background:{color}"></span>'
            f'<strong><a class="speaker-link" href="#{esc(anchor)}">{name}</a></strong>'
            f'<span>{esc(role)}</span>'
            f'<em>{esc(source)}</em>'
            f'<span class="aw-cell">{profile_cell}{render_profile_icon(speaker) if profiles_enabled else ""}</span>'
            "</li>"
        )
    return f'<ul class="speaker-list">{"".join(rows)}</ul>'


def source_chunk_anchor(item: dict[str, Any], stats: dict[str, Any], chunk: dict[str, Any]) -> str | None:
    chunk_rede_id = chunk.get("rede_id")
    for sequence, speech in enumerate(stats["speakers"]):
        if chunk_rede_id and speech.get("rede_id") == chunk_rede_id:
            return speech_anchor(item, speech, sequence)
    return None


def summary_unavailable_message(
    stats: dict[str, Any],
    summary_generation: dict[str, Any] | None,
) -> str:
    gen = summary_generation or {}
    if gen.get("enabled") is False:
        if gen.get("mode") == "reuse" or gen.get("reason") == "refresh not requested":
            return "Automatische Zusammenfassungen wurden in diesem Build nicht neu erzeugt."
        if gen.get("reason"):
            return "Automatische Zusammenfassungen sind für diese Sitzung nicht aktiviert."
        return "Automatische Zusammenfassungen wurden für diese Sitzung deaktiviert."
    citable_speeches = sum(
        1
        for speech in stats.get("speakers") or []
        if (speech.get("text") or " ".join(speech.get("paragraphs") or [])).strip()
    )
    if citable_speeches < 3:
        return (
            "Für diesen Tagesordnungspunkt liegen zu wenige zitierfähige Redebeiträge "
            "für eine belegte Zusammenfassung vor."
        )
    return "Die automatische Zusammenfassung ist derzeit nicht verfügbar."


def render_llm_summary(
    item: dict[str, Any],
    stats: dict[str, Any],
    summary_generation: dict[str, Any] | None = None,
    protocol: dict[str, Any] | None = None,
) -> str:
    summary = item.get("llm_summary") or {}
    text = summary.get("text")
    chunks = summary.get("source_chunks") or []
    if not text or not chunks:
        return (
            '<section class="llm-summary unavailable" data-feature="summaries">'
            "<h3><span>Automatische Zusammenfassung</span></h3>"
            f"<p>{esc(summary_unavailable_message(stats, summary_generation))}</p>"
            "</section>"
        )

    pdf_url = (protocol or {}).get("pdf_url")
    first_anchor = source_chunk_anchor(item, stats, chunks[0])
    label = esc(summary.get("label") or "Automatische Zusammenfassung — zur Quelle")
    label_html = f'<a href="#{esc(first_anchor)}">{label}</a>' if first_anchor else f"<span>{label}</span>"
    chunk_rows = []
    for chunk in chunks:
        speaker = chunk.get("speaker") or {}
        name = speaker.get("display_name") or "Unbekannt"
        party_or_role = speaker.get("fraktion") or speaker.get("role_short") or speaker.get("role") or "unbekannt"
        source = source_page_text(chunk.get("source_page"))
        anchor = source_chunk_anchor(item, stats, chunk)
        source_ref = f"Seite {source}" if source else "Redebeitrag"
        source_parts = [
            f'<a href="#{esc(anchor)}">{esc(source_ref)}</a>' if anchor else esc(source_ref)
        ]
        if pdf_url:
            source_parts.append(f'<a href="{esc(pdf_url)}">Originalprotokoll (PDF)</a>')
        source_html = " · ".join(source_parts)
        chunk_rows.append(
            "<li>"
            f"<strong>{esc(chunk.get('id'))}</strong>"
            f"<span>{esc(name)} · {esc(party_or_role)} · {source_html}</span>"
            f"<p>{esc(chunk.get('text'))}</p>"
            "</li>"
        )

    return (
        '<section class="llm-summary" data-feature="summaries">'
        f'<h3>{label_html}</h3>'
        f"<p>{esc(text)}</p>"
        f'<ul class="summary-sources">{"".join(chunk_rows)}</ul>'
        "</section>"
    )


def session_summary_unavailable_message(summary_generation: dict[str, Any] | None) -> str:
    gen = summary_generation or {}
    if gen.get("enabled") is False:
        if gen.get("mode") == "reuse" or gen.get("reason") == "refresh not requested":
            return (
                "Automatische Zusammenfassungen wurden in diesem Build nicht neu erzeugt. "
                "Vorhandene Zusammenfassungen werden wiederverwendet."
            )
        if gen.get("reason"):
            return (
                "Automatische Zusammenfassungen wurden bei diesem Build nicht erzeugt. "
                "Es fehlt ein LLM-API-Schlüssel für die Zusammenfassungen."
            )
        return "Automatische Zusammenfassungen wurden für diese Sitzung deaktiviert."
    if gen.get("enabled") is True:
        return "Für diese Sitzung wurden noch keine zitierfähigen automatischen Zusammenfassungen erzeugt."
    return "Die automatische Sitzungszusammenfassung ist derzeit nicht verfügbar."


def render_session_llm_summary(
    items: list[dict[str, Any]],
    stats_by_index: dict[int, dict[str, Any]],
    summary_generation: dict[str, Any] | None,
    protocol: dict[str, Any],
) -> str:
    summarized_items = [
        item
        for item in items
        if (item.get("llm_summary") or {}).get("text")
        and (item.get("llm_summary") or {}).get("source_chunks")
    ]
    if not summarized_items:
        return (
            '<section class="session-llm-summary unavailable" data-feature="summaries">'
            '<div class="session-llm-header">'
            "<div>"
            '<span class="eyebrow">KI-Zusammenfassung</span>'
            "<h2>Automatische Sitzungszusammenfassung</h2>"
            f"<p>{esc(session_summary_unavailable_message(summary_generation))}</p>"
            "</div>"
            "</div>"
            "</section>"
        )

    summarized_items = sorted(
        summarized_items,
        key=lambda item: stats_by_index[item["index"]]["speech_count"],
        reverse=True,
    )
    visible_items = summarized_items[:5]
    total_summaries = len(summarized_items)
    pdf_url = protocol.get("pdf_url")
    rows = []
    for item in visible_items:
        stats = stats_by_index[item["index"]]
        summary = item.get("llm_summary") or {}
        chunk_links = []
        for chunk in (summary.get("source_chunks") or [])[:4]:
            anchor = source_chunk_anchor(item, stats, chunk)
            source = source_page_text(chunk.get("source_page"))
            label = f"{chunk.get('id')} · S. {source}" if source else str(chunk.get("id") or "Quelle")
            if anchor:
                chunk_links.append(f'<a href="#{esc(anchor)}">{esc(label)}</a>')
            else:
                chunk_links.append(f"<span>{esc(label)}</span>")
        if pdf_url:
            chunk_links.append(f'<a href="{esc(pdf_url)}">Originalprotokoll</a>')
        rows.append(
            '<article class="session-summary-item">'
            '<div class="session-summary-item-head">'
            f'<a class="top-jump" href="#top-{esc(item.get("index"))}">{esc(item.get("top_id"))}</a>'
            f"<h3>{esc(short(item.get('heading'), 120))}</h3>"
            "</div>"
            f"<p>{esc(summary.get('text'))}</p>"
            f'<div class="session-summary-sources">{"".join(chunk_links)}</div>'
            "</article>"
        )

    more_note = ""
    if total_summaries > len(visible_items):
        more_note = (
            f"<p class=\"session-summary-note\">Weitere {esc(total_summaries - len(visible_items))} "
            "automatische Zusammenfassungen stehen direkt bei den Tagesordnungspunkten.</p>"
        )

    generated_label = f"{total_summaries} TOP-Zusammenfassung" + ("" if total_summaries == 1 else "en")
    return (
        '<section class="session-llm-summary" data-feature="summaries">'
        '<div class="session-llm-header">'
        "<div>"
        '<span class="eyebrow">KI-Zusammenfassung</span>'
        "<h2>Automatische Sitzungszusammenfassung</h2>"
        "<p>Die wichtigsten automatisch zusammengefassten Tagesordnungspunkte dieser Sitzung, "
        "sortiert nach parlamentarischer Aufmerksamkeit und jeweils mit Protokollquellen belegt.</p>"
        "</div>"
        f'<span class="summary-count">{esc(generated_label)}</span>'
        "</div>"
        f'<div class="session-summary-list">{"".join(rows)}</div>'
        f"{more_note}"
        "</section>"
    )


def render_speech_details(item: dict[str, Any], stats: dict[str, Any], profiles_enabled: bool = True) -> str:
    cards = []
    for sequence, speech in enumerate(stats["speakers"]):
        speaker = speech.get("speaker") or {}
        name = esc(speaker.get("display_name") or "Unbekannt")
        party = speaker_party(speaker)
        color = PARTY_COLORS.get(party, "#6b7280")
        role = speaker.get("role") or speaker.get("role_short") or party
        source = source_page_text(speech.get("source_page"))
        paragraphs = speech.get("paragraphs") or []
        if not paragraphs and speech.get("text"):
            paragraphs = [speech.get("text")]
        if not paragraphs and speech.get("snippet"):
            paragraphs = [speech.get("snippet")]
        paragraph_html = "".join(f"<p>{esc(paragraph)}</p>" for paragraph in paragraphs)
        if not paragraph_html:
            paragraph_html = '<p class="muted">Dieser Bericht enthält keinen Redetext. Erzeuge das JSON mit dem aktuellen Validator neu, um die Rede direkt anzuzeigen.</p>'
        meta = " · ".join(part for part in [esc(role), f"Seite {esc(source)}" if source else ""] if part)
        profile_html = render_profile_link(speaker) if profiles_enabled else ""
        cards.append(
            f"""
            <details class="speech-card" id="{esc(speech_anchor(item, speech, sequence))}">
              <summary>
                <span class="party-dot" style="background:{color}"></span>
                <strong>{name}</strong>
                <em>{meta}</em>
              </summary>
              <div class="speech-text">
                {profile_html}
                {paragraph_html}
              </div>
            </details>
            """
        )
    if not cards:
        return '<span class="muted">Keine Reden im XML</span>'
    return f'<div class="speech-cards">{"".join(cards)}</div>'


def render_html(
    report: dict[str, Any],
    features: Selection | None = None,
    mp_lookup: dict[str, int] | None = None,
) -> str:
    features = features or default_selection()
    from features.loader import load as load_components

    components = {component.feature.id: component for component in load_components(features)}
    protocol = report.get("protocol") or {}
    summary = report.get("validation_summary") or {}
    summary_generation = report.get("summary_generation") or {}
    items = report.get("agenda_items") or []
    stats_by_index = {item["index"]: item_stats(item) for item in items}
    total_speeches = sum(stats["speech_count"] for stats in stats_by_index.values())
    total_chars = sum(stats["total_chars"] for stats in stats_by_index.values())
    total_votes = sum(
        len(item.get("votes") or ([item["vote"]] if item.get("vote") else []))
        for item in items
    )

    attention_rows = []
    for item in sorted(items, key=lambda x: stats_by_index[x["index"]]["speech_count"], reverse=True):
        stats = stats_by_index[item["index"]]
        speech_share = percent(stats["speech_count"], total_speeches)
        text_share = percent(stats["total_chars"], total_chars)
        attention_rows.append(
            '<a class="attention-row" href="#top-{index}">'
            '<span class="row-top">{top}</span>'
            '<span class="row-title">{title}</span>'
            '<span class="mini-bars" title="Türkis: Anteil an allen Reden dieser Sitzung. Ocker: Anteil am extrahierten Redetext."><i style="width:{speech_share:.2f}%"></i><b style="width:{text_share:.2f}%"></b></span>'
            '<span class="row-metric">{speeches} Reden · {speech_share_label} der Sitzung</span>'
            "</a>".format(
                index=item["index"],
                top=esc(item.get("top_id")),
                title=esc(short(item.get("heading"), 78)),
                speech_share=speech_share,
                text_share=text_share,
                speech_share_label=format_percent(speech_share),
                speeches=stats["speech_count"],
            )
        )

    top_sections = []
    for item in items:
        stats = stats_by_index[item["index"]]
        party_total = sum(stats["party_counts"].values())
        speech_share = percent(stats["speech_count"], total_speeches)
        text_share = percent(stats["total_chars"], total_chars)
        party_labels = [
            f"{party} {count}"
            for party, count in stats["party_counts"].most_common()
        ]
        vote_sections = (
            "".join(components["votes"].dossier_sections(report, {"item": item}))
            if "votes" in components
            else ""
        )
        summary_sections = (
            "".join(
                components["summaries"].dossier_sections(
                    report,
                    {
                        "scope": "item",
                        "item": item,
                        "stats": stats,
                        "summary_generation": summary_generation,
                        "protocol": protocol,
                    },
                )
            )
            if "summaries" in components
            else ""
        )
        dev_sections = (
            "".join(
                components["dev-view"].dossier_sections(
                    report,
                    {"scope": "item", "item": item},
                )
            )
            if "dev-view" in components
            else ""
        )
        top_sections.append(
            f"""
            <article class="top-card" id="top-{item['index']}">
              <div class="top-head">
                <div>
                  <span class="eyebrow">{esc(item.get('top_id'))} · {esc(page_range_text(item))}</span>
                  <h2>{esc(item.get('heading'))}</h2>
                </div>
                <div class="score">
                  <strong>{stats['speech_count']}</strong>
                  <span>Reden</span>
                </div>
              </div>
              <div class="top-bars">
                <div>
                  <label>Redeanteil <strong>{format_percent(speech_share)}</strong></label>
                  <div class="bar" title="{stats['speech_count']} von {total_speeches} Reden in dieser Sitzung"><span style="width:{speech_share:.2f}%"></span></div>
                  <p>{stats['speech_count']} von {total_speeches} extrahierten Reden gehören zu diesem Tagesordnungspunkt.</p>
                </div>
                <div>
                  <label>Textumfang <strong>{format_percent(text_share)}</strong></label>
                  <div class="bar alt" title="{stats['total_chars']} von {total_chars} extrahierten Redezeichen in dieser Sitzung"><span style="width:{text_share:.2f}%"></span></div>
                  <p>{format_int(stats['total_chars'])} Zeichen Redetext, {format_percent(text_share)} des aus XML extrahierten Sitzungsprotokolls.</p>
                </div>
              </div>
              <div class="party-block">
                {render_party_stack(stats['party_counts'], party_total)}
                <div class="party-labels">{render_badges(party_labels)}</div>
              </div>
              {summary_sections}
              {vote_sections}
              <div class="detail-grid">
                <section>
                  <h3>Rednerinnen und Redner</h3>
                  {render_speakers(item, stats, mp_lookup if 'mp-pages' in features else None, '../abgeordnete/', 'aw-profiles' in features)}
                </section>
                <section>
                  <h3>Drucksachen</h3>
                  {render_source_links(item)}
                </section>
              </div>
              {dev_sections}
              <section class="speech-section">
                <h3>Reden</h3>
                {render_speech_details(item, stats, 'aw-profiles' in features)}
              </section>
            </article>
            """
        )

    warnings = report.get("warnings") or []
    warning_html = ""
    if warnings:
        warning_html = '<div class="notice">' + " ".join(esc(w) for w in warnings) + "</div>"
    footer_links = [
        '<a href="../overview.html">Plenarprotokoll-Katalog</a>',
        '<a href="../api-sitzungen.html">Alle API-Sitzungen</a>',
    ]
    if "bills" in features:
        footer_links.append('<a href="../bills/index.html" data-feature="bills">Gesetze verfolgen</a>')
    footer_links.extend(('<a href="../sources.html">Quellen und Methode</a>', '<a href="../settings.html">Einstellungen</a>'))
    footer_nav = " · ".join(footer_links)
    footer_nav_html = f" {footer_nav}" if footer_nav else ""
    protocol_dev_sections = (
        "".join(components["dev-view"].dossier_sections(report, {"scope": "protocol"}))
        if "dev-view" in components
        else ""
    )
    session_summary_sections = (
        "".join(
            components["summaries"].dossier_sections(
                report,
                {
                    "scope": "session",
                    "items": items,
                    "stats_by_index": stats_by_index,
                    "summary_generation": summary_generation,
                    "protocol": protocol,
                },
            )
        )
        if "summaries" in components
        else ""
    )

    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(protocol_title(report))}</title>
  {page_head(features)}
  <style>
    :root {{
      --ink:#171a1f;
      --muted:#606a78;
      --line:#d9dee6;
      --paper:#f7f8fa;
      --panel:#ffffff;
      --teal:#0f766e;
      --blue:#2458a6;
      --amber:#b06b00;
      --red:#b91c1c;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color:var(--ink);
      background:var(--paper);
      letter-spacing:0;
    }}
    a {{ color:#174ea6; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .shell {{ max-width:1440px; margin:0 auto; padding:24px; }}
    {global_header_styles()}
    .page-header {{
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:24px;
      align-items:end;
      padding:10px 0 22px;
      border-bottom:1px solid var(--line);
    }}
    h1 {{ margin:0; font-size:34px; line-height:1.1; font-weight:760; }}
    .subtitle {{ margin:8px 0 0; color:var(--muted); font-size:15px; }}
    .meta-grid {{
      display:grid;
      grid-template-columns:repeat(4, minmax(112px, 1fr));
      gap:10px;
    }}
    .metric {{
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:8px;
      padding:10px 12px;
      min-height:62px;
    }}
    .metric span {{ display:block; color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
    .metric strong {{ display:block; margin-top:4px; font-size:22px; }}
    .session-llm-summary {{
      display:grid;
      gap:14px;
      margin-top:18px;
      padding:18px;
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel);
    }}
    .session-llm-header {{
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:16px;
      align-items:start;
    }}
    .session-llm-header h2 {{
      margin:5px 0 0;
      font-size:22px;
      line-height:1.25;
    }}
    .session-llm-header p {{
      max-width:860px;
      margin:8px 0 0;
      color:var(--muted);
      font-size:14px;
      line-height:1.45;
    }}
    .summary-count {{
      display:inline-flex;
      align-items:center;
      min-height:30px;
      padding:4px 10px;
      border:1px solid #d5dde8;
      border-radius:999px;
      background:#f9fafb;
      color:#3f4a59;
      font-size:13px;
      font-weight:700;
      white-space:nowrap;
    }}
    .session-summary-list {{
      display:grid;
      gap:12px;
    }}
    .session-summary-item {{
      display:grid;
      gap:8px;
      padding-top:12px;
      border-top:1px solid #edf0f4;
    }}
    .session-summary-item-head {{
      display:grid;
      grid-template-columns:auto minmax(0,1fr);
      gap:10px;
      align-items:start;
    }}
    .top-jump {{
      display:inline-flex;
      align-items:center;
      min-height:25px;
      padding:2px 8px;
      border:1px solid #d5dde8;
      border-radius:999px;
      color:#174ea6;
      font-size:12px;
      font-weight:750;
      white-space:nowrap;
    }}
    .session-summary-item h3 {{
      margin:3px 0 0;
      color:var(--ink);
      font-size:15px;
      line-height:1.3;
      text-transform:none;
      letter-spacing:0;
    }}
    .session-summary-item p {{
      margin:0;
      color:#252b33;
      font-size:15px;
      line-height:1.5;
    }}
    .session-summary-sources {{
      display:flex;
      flex-wrap:wrap;
      gap:7px;
      font-size:12px;
    }}
    .session-summary-sources a,
    .session-summary-sources span {{
      display:inline-flex;
      align-items:center;
      min-height:24px;
      padding:2px 7px;
      border:1px solid #e1e6ee;
      border-radius:999px;
      background:#fbfcfd;
      color:#4b5563;
    }}
    .session-summary-note {{
      margin:0;
      color:var(--muted);
      font-size:13px;
      line-height:1.4;
    }}
    .session-llm-summary.unavailable {{
      background:#f9fafb;
    }}
    .layout {{
      display:grid;
      grid-template-columns:340px minmax(0,1fr);
      gap:18px;
      margin-top:18px;
      align-items:start;
    }}
    aside {{
      position:sticky;
      top:14px;
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:8px;
      overflow:hidden;
    }}
    aside h2 {{ margin:0; padding:14px 16px; font-size:15px; border-bottom:1px solid var(--line); }}
    .attention-row {{
      display:grid;
      gap:5px;
      padding:12px 16px;
      border-bottom:1px solid #edf0f4;
      color:var(--ink);
    }}
    .ranking-note {{
      display:grid;
      gap:7px;
      padding:12px 16px;
      border-bottom:1px solid #edf0f4;
      color:var(--muted);
      font-size:12px;
      line-height:1.35;
    }}
    .legend {{
      display:flex;
      flex-wrap:wrap;
      gap:8px 12px;
      align-items:center;
    }}
    .legend span {{
      display:inline-flex;
      gap:5px;
      align-items:center;
    }}
    .legend i {{
      width:18px;
      height:3px;
      border-radius:999px;
      background:var(--teal);
    }}
    .legend span:last-child i {{ background:var(--amber); }}
    .attention-row:last-child {{ border-bottom:0; }}
    .row-top, .eyebrow {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
    .row-title {{ font-weight:650; line-height:1.25; }}
    .row-metric {{ color:var(--muted); font-size:12px; }}
    .mini-bars {{ display:grid; gap:3px; height:9px; }}
    .mini-bars i, .mini-bars b {{ display:block; height:3px; border-radius:999px; }}
    .mini-bars i {{ background:var(--teal); }}
    .mini-bars b {{ background:var(--amber); }}
    main {{ display:grid; gap:16px; }}
    .dev-only {{ display:none !important; }}
    .notice {{
      padding:12px 14px;
      border:1px solid #e3c46a;
      background:#fff7d6;
      border-radius:8px;
      color:#614a00;
      font-size:14px;
    }}
    .top-card {{
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:8px;
      padding:18px;
    }}
    .top-head {{
      display:grid;
      grid-template-columns:minmax(0,1fr) 96px;
      gap:18px;
      align-items:start;
    }}
    h2 {{ margin:5px 0 0; font-size:21px; line-height:1.25; }}
    h3 {{ margin:0 0 10px; font-size:13px; text-transform:uppercase; color:var(--muted); letter-spacing:.04em; }}
    .score {{
      text-align:right;
      border-left:1px solid var(--line);
      padding-left:16px;
    }}
    .score strong {{ display:block; font-size:34px; line-height:1; }}
    .score span {{ color:var(--muted); font-size:12px; }}
    .top-bars {{
      display:grid;
      grid-template-columns:1fr 1fr;
      gap:16px;
      margin-top:16px;
    }}
    label {{
      display:flex;
      justify-content:space-between;
      gap:10px;
      color:var(--muted);
      font-size:12px;
      margin-bottom:6px;
    }}
    label strong {{ color:var(--ink); font-size:12px; }}
    .bar {{ height:11px; background:#edf0f4; border-radius:999px; overflow:hidden; }}
    .bar span {{ display:block; height:100%; background:var(--teal); border-radius:999px; }}
    .bar.alt span {{ background:var(--amber); }}
    .top-bars p {{
      margin:6px 0 0;
      color:var(--muted);
      font-size:12px;
      line-height:1.35;
    }}
    .party-block {{ margin-top:14px; }}
    .stack {{ display:flex; overflow:hidden; height:14px; background:#edf0f4; border-radius:999px; }}
    .stack span {{ min-width:3px; }}
    .party-labels {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }}
    .llm-summary {{
      display:grid;
      gap:10px;
      margin-top:16px;
      padding:14px;
      border:1px solid #d5dde8;
      border-radius:8px;
      background:#f9fafb;
    }}
    .llm-summary h3 {{
      margin:0;
      color:#3f4a59;
    }}
    .llm-summary h3 a {{
      color:#3f4a59;
      text-decoration:underline;
      text-decoration-style:dotted;
      text-underline-offset:3px;
    }}
    .llm-summary > p {{
      margin:0;
      color:#252b33;
      font-size:15px;
      line-height:1.5;
    }}
    .llm-summary.unavailable > p {{
      color:var(--muted);
    }}
    .summary-sources {{
      display:grid;
      gap:8px;
    }}
    .summary-sources li {{
      display:grid;
      grid-template-columns:34px minmax(0,1fr);
      gap:6px 10px;
      padding-top:8px;
      border-top:1px solid #e5e9ef;
      font-size:12px;
    }}
    .summary-sources strong {{
      grid-row:span 2;
      color:#3f4a59;
      font-weight:760;
    }}
    .summary-sources span {{
      color:var(--muted);
      overflow-wrap:anywhere;
    }}
    .summary-sources p {{
      margin:0;
      color:#343b46;
      line-height:1.45;
    }}
    .vote-panel {{
      margin-top:16px;
      padding:14px;
      border:1px solid #d7e3df;
      border-radius:8px;
      background:#f7fbfa;
    }}
    .vote-head {{
      display:grid;
      grid-template-columns:minmax(0,1fr) minmax(260px,.42fr);
      gap:16px;
      align-items:start;
    }}
    .vote-head h3 {{ margin-bottom:5px; color:#0f5f59; }}
    .vote-head p {{ margin:0; font-size:13px; }}
    .vote-total {{ display:grid; gap:8px; }}
    .vote-stack {{
      display:flex;
      overflow:hidden;
      height:13px;
      background:#edf0f4;
      border-radius:999px;
    }}
    .vote-stack span {{ min-width:3px; }}
    .vote-yes {{ background:#0f766e; }}
    .vote-no {{ background:#b91c1c; }}
    .vote-abstain {{ background:#b06b00; }}
    .vote-absent {{ background:#7a8699; }}
    .vote-pill {{
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-height:22px;
      padding:2px 7px;
      border-radius:999px;
      color:white;
      font-size:12px;
      font-style:normal;
      font-weight:680;
      white-space:nowrap;
    }}
    .vote-pill strong {{ margin-left:4px; color:inherit; }}
    .vote-total .vote-pill {{ margin-right:5px; }}
    .vote-fractions {{
      display:grid;
      grid-template-columns:repeat(2, minmax(0,1fr));
      gap:9px 14px;
      margin-top:14px;
    }}
    .vote-fraction-row {{
      display:grid;
      grid-template-columns:10px minmax(88px,.55fr) minmax(120px,1fr) auto;
      gap:8px;
      align-items:center;
      min-width:0;
      font-size:13px;
    }}
    .vote-fraction-row strong {{ overflow-wrap:anywhere; }}
    .member-votes {{
      margin-top:14px;
      border-top:1px solid #dce7e3;
      padding-top:10px;
      font-size:13px;
    }}
    .member-votes summary {{
      cursor:pointer;
      color:#174ea6;
      font-weight:700;
    }}
    .member-vote-grid {{
      display:grid;
      grid-template-columns:repeat(3, minmax(0,1fr));
      gap:14px;
      margin-top:12px;
    }}
    .member-vote-group h4 {{
      margin:0 0 7px;
      font-size:12px;
      color:var(--muted);
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .member-vote-list {{ display:grid; gap:5px; }}
    .member-vote-row {{
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:8px;
      align-items:center;
      min-height:25px;
    }}
    .member-vote-row strong {{ min-width:0; overflow-wrap:anywhere; }}
    .badge {{
      display:inline-flex;
      align-items:center;
      min-height:24px;
      padding:3px 8px;
      border:1px solid var(--line);
      border-radius:999px;
      background:#fbfcfd;
      color:#333a45;
      font-size:12px;
      white-space:nowrap;
    }}
    .source-strip {{
      display:grid;
      grid-template-columns:1.1fr 1fr .8fr;
      gap:12px;
      margin-top:16px;
      padding:12px;
      background:#f5f7f9;
      border:1px solid #e3e8ef;
      border-radius:8px;
      font-size:13px;
    }}
    .source-strip > div {{ min-width:0; }}
    .source-strip span:first-child {{
      display:block;
      margin-bottom:6px;
      color:var(--muted);
      font-size:11px;
      text-transform:uppercase;
      letter-spacing:.04em;
    }}
    .doc-link {{
      display:inline-block;
      margin:0 6px 6px 0;
      padding:3px 7px;
      border:1px solid #cfd7e3;
      border-radius:6px;
      background:white;
      font-weight:650;
    }}
    .detail-grid {{
      display:grid;
      grid-template-columns:repeat(2, minmax(0,1fr));
      gap:18px;
      margin-top:18px;
      align-items:start;
    }}
    ul {{ list-style:none; margin:0; padding:0; }}
    .speaker-list, .position-list, .doc-list, .activity-list, .people-list {{
      display:grid;
      gap:7px;
      font-size:13px;
    }}
    .speaker-row {{
      display:grid;
      grid-template-columns:10px minmax(96px, .85fr) minmax(110px, 1fr) 44px 20px;
      gap:8px;
      align-items:center;
      min-height:24px;
    }}
    .party-dot {{ width:8px; height:8px; border-radius:50%; }}
    .speaker-row strong, .position-list strong, .doc-list strong, .activity-list strong, .people-list strong {{ font-weight:680; }}
    .speaker-row span, .position-list span, .doc-list span, .activity-list span, .people-list span {{ color:#3c4654; min-width:0; overflow-wrap:anywhere; }}
    .speaker-row em, .position-list em, .doc-list em, .activity-list em, .people-list em {{ color:var(--muted); font-style:normal; overflow-wrap:anywhere; }}
    .speaker-link {{ color:var(--ink); text-decoration:none; }}
    .speaker-link:hover {{ color:#174ea6; text-decoration:underline; }}
    .speaker-row .aw-cell {{ display:flex; align-items:center; justify-content:center; gap:8px; }}
    .mp-profile-link {{ font-size:12px; font-weight:650; color:#174ea6; text-decoration:none; white-space:nowrap; }}
    .mp-profile-link:hover {{ text-decoration:underline; }}
    .aw-profile-icon {{
      display:inline-flex; align-items:center; justify-content:center;
      color:var(--muted); text-decoration:none; opacity:.65;
      transition:color .12s ease, opacity .12s ease;
    }}
    .aw-profile-icon:hover {{ color:#174ea6; opacity:1; }}
    .aw-profile-line {{ margin:0 0 10px; }}
    .aw-profile {{
      display:inline-flex; align-items:center; gap:6px;
      font-size:12.5px; font-weight:620; line-height:1;
      color:#174ea6; text-decoration:none;
      background:#eef3fb; border:1px solid #d6e2f5; border-radius:999px;
      padding:5px 11px;
    }}
    .aw-profile:hover {{ background:#e2ecfb; border-color:#b9cdf0; }}
    .aw-profile .aw-ext {{ font-weight:400; }}
    .position-list li, .doc-list li, .activity-list li, .people-list li {{
      display:grid;
      grid-template-columns:minmax(78px,.45fr) minmax(0,1fr) minmax(54px,.35fr) minmax(0,.8fr);
      gap:8px;
      padding-bottom:7px;
      border-bottom:1px solid #eef1f5;
    }}
    .position-list li {{ grid-template-columns:minmax(88px,.5fr) minmax(0,1.5fr) minmax(90px,.7fr); }}
    .activity-list li, .people-list li {{ grid-template-columns:minmax(96px,.55fr) minmax(0,1.4fr) minmax(110px,.8fr); }}
    .position-list li:last-child, .doc-list li:last-child, .activity-list li:last-child, .people-list li:last-child {{ border-bottom:0; }}
    .api-overview {{
      margin-top:18px;
      padding:16px;
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel);
    }}
    .api-overview h2 {{
      margin:0;
      font-size:18px;
      line-height:1.25;
    }}
    .api-overview p {{
      margin:6px 0 0;
      color:var(--muted);
      font-size:13px;
      line-height:1.4;
    }}
    .api-record-grid {{
      display:grid;
      grid-template-columns:repeat(2, minmax(0,1fr));
      gap:10px;
      margin-top:12px;
    }}
    .api-json {{
      border:1px solid #dfe5ed;
      border-radius:8px;
      background:#fbfcfd;
      overflow:hidden;
    }}
    .api-json summary {{
      min-height:34px;
      padding:8px 10px;
      cursor:pointer;
      color:#174ea6;
      font-size:13px;
      font-weight:700;
    }}
    .api-json pre {{
      max-height:360px;
      overflow:auto;
      margin:0;
      padding:10px;
      border-top:1px solid #e6ebf2;
      color:#202833;
      font-size:12px;
      line-height:1.45;
      white-space:pre-wrap;
      overflow-wrap:anywhere;
    }}
    .people-section, .raw-top-api {{
      margin-top:16px;
      padding-top:14px;
      border-top:1px solid #eef1f5;
    }}
    .dev-top-details {{
      margin-top:16px;
      padding-top:16px;
      border-top:1px solid #eef1f5;
    }}
    .speech-section {{
      margin-top:18px;
      padding-top:16px;
      border-top:1px solid #eef1f5;
    }}
    .speech-cards {{
      display:grid;
      gap:8px;
    }}
    .speech-card {{
      border:1px solid #e1e6ee;
      border-radius:8px;
      background:#fbfcfd;
      scroll-margin-top:16px;
    }}
    .speech-card[open] {{
      background:#fff;
      border-color:#c8d7eb;
      box-shadow:0 1px 0 rgba(23, 26, 31, .04);
    }}
    .speech-card summary {{
      display:grid;
      grid-template-columns:10px minmax(120px, .5fr) minmax(0,1fr);
      gap:8px;
      align-items:center;
      min-height:36px;
      padding:7px 10px;
      cursor:pointer;
      font-size:13px;
      list-style:none;
    }}
    .speech-card summary::-webkit-details-marker {{ display:none; }}
    .speech-card summary em {{
      color:var(--muted);
      font-style:normal;
      overflow-wrap:anywhere;
    }}
    .speech-text {{
      padding:0 14px 12px 28px;
      font-size:14px;
      line-height:1.55;
      color:#252b33;
    }}
    .speech-text p {{
      margin:10px 0 0;
    }}
    .muted {{ color:var(--muted); }}
    .status.warn {{ color:var(--red); }}
    footer {{
      display:flex;
      justify-content:space-between;
      gap:12px;
      align-items:center;
      padding:22px 0 4px;
      color:var(--muted);
      font-size:12px;
    }}
    .dev-toggle {{
      appearance:none;
      flex:0 0 auto;
      min-height:28px;
      padding:4px 9px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      color:#4b5563;
      font:inherit;
      font-weight:700;
      cursor:pointer;
    }}
    .dev-toggle:hover {{ border-color:#b9c3d0; color:#174ea6; }}
    .dev-toggle[aria-pressed="true"] {{
      border-color:#202833;
      background:#202833;
      color:#fff;
    }}
    @media (max-width: 1120px) {{
      .layout {{ grid-template-columns:1fr; }}
      aside {{ position:static; }}
      .detail-grid {{ grid-template-columns:1fr; }}
      .api-record-grid {{ grid-template-columns:1fr; }}
      .source-strip {{ grid-template-columns:1fr; }}
      .member-vote-grid {{ grid-template-columns:repeat(2, minmax(0,1fr)); }}
    }}
    @media (max-width: 720px) {{
      .shell {{ padding:14px; }}
      .page-header, .top-head {{ grid-template-columns:1fr; }}
      .session-llm-header, .session-summary-item-head {{ grid-template-columns:1fr; }}
      .meta-grid {{ grid-template-columns:1fr 1fr; }}
      h1 {{ font-size:27px; }}
      h2 {{ font-size:18px; }}
      .score {{ text-align:left; border-left:0; padding-left:0; }}
      .top-bars {{ grid-template-columns:1fr; }}
      .vote-head, .vote-fractions, .member-vote-grid {{ grid-template-columns:1fr; }}
      .vote-fraction-row {{ grid-template-columns:10px minmax(0,.7fr) minmax(90px,1fr); }}
      .vote-fraction-row em {{ display:none; }}
      .speaker-row {{ grid-template-columns:10px minmax(0,1fr) 48px 20px; }}
      .speaker-row span:nth-of-type(2) {{ display:none; }}
      .speech-card summary {{ grid-template-columns:10px minmax(0,1fr); }}
      .speech-card summary em {{ grid-column:2; }}
      .speech-text {{ padding-left:14px; }}
      .summary-sources li {{ grid-template-columns:1fr; }}
      .summary-sources strong {{ grid-row:auto; }}
      .position-list li, .doc-list li, .activity-list li, .people-list li {{ grid-template-columns:1fr; }}
      footer {{ align-items:flex-start; flex-direction:column; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    {render_global_header(depth=1, active="pulse", features=features)}
    <header class="page-header">
      <div>
        <h1>Bundestag-Puls</h1>
        <p class="subtitle">{esc(protocol.get('titel'))} · Sitzung vom {esc(protocol.get('datum'))} · verteilt am {esc(protocol.get('verteildatum'))}</p>
      </div>
      <div class="meta-grid">
        <div class="metric"><span>Tagesordnungspunkte</span><strong>{esc(summary.get('xml_top_count'))}</strong></div>
        <div class="metric"><span>Reden</span><strong>{esc(summary.get('xml_speech_count'))}</strong></div>
        <div class="metric"><span>Drucksachen</span><strong>{esc(summary.get('xml_drucksache_count'))}</strong></div>
        <div class="metric"><span>Abstimmungen</span><strong>{esc(total_votes)}</strong></div>
      </div>
    </header>
    {protocol_dev_sections}
    {session_summary_sections}
    <div class="layout">
      <aside>
        <h2>Aufmerksamkeitsrang</h2>
        <div class="ranking-note">
          <span>Sortiert nach Anzahl der Reden. Die Balken zeigen den Anteil jedes Tagesordnungspunktes an der gesamten Sitzung.</span>
          <div class="legend"><span><i></i>Reden</span><span><i></i>Redetext</span></div>
        </div>
        {''.join(attention_rows)}
      </aside>
      <main>
        {warning_html}
        {''.join(top_sections)}
      </main>
    </div>
    <footer>
      <span>Das XML-Protokoll gilt als maßgeblich; verknüpfte DIP-Daten können über die Dev-Ansicht geprüft werden.{footer_nav_html}</span>
      {'<button class="dev-toggle" type="button" aria-pressed="false" data-feature="dev-view">Dev-Ansicht</button>' if 'dev-view' in features else ''}
    </footer>
  </div>
  {page_scripts(features)}
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Validation JSON produced by validate_dip_protocol.py")
    parser.add_argument("output", type=Path, help="Standalone HTML output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_html(report), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
